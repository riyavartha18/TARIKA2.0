import logging

from django.db import connection, transaction, DatabaseError, IntegrityError
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError, NotFound

from accounts.models import Customer
from accounts.models import Role
from catalog.models import Product
from .models import WishlistItem, CartItem
from .serializers import CartItemSerializer


logger = logging.getLogger(__name__)

# Upper bound for a single cart line. The catalogue's own rows never exceed a
# handful of units, and stock is additionally checked against the product row.
MAX_QUANTITY_PER_LINE = 99

# wishkey / cartkey are plain text primary keys with no sequence or default.
# The dataset allocates them as PREFIX + zero-padded running number.
KEY_ALLOCATORS = {
    'wishlist': {'key': 'wishkey', 'prefix': 'WISH', 'width': 7},
    'cart': {'key': 'cartkey', 'prefix': 'CART', 'width': 7},
    'orders': {'key': 'orderid', 'prefix': 'ORD', 'width': 7},
}


class ServiceUnavailable(APIException):
    """Raised for database failures; carries no driver detail."""
    status_code = 503
    default_detail = 'Service temporarily unavailable. Please try again later.'
    default_code = 'service_unavailable'


def safe_database_failure(context, exc):
    """Log only the exception class and raise a client-safe error.

    Driver messages quote the failing statement, so they are never returned or
    logged.
    """
    logger.error("%s: database error (%s)", context, type(exc).__name__)
    raise ServiceUnavailable()


def allocate_key(table):
    """Return the next sequential key for `table`, e.g. 'WISH00306214'.

    Must run inside transaction.atomic(): the transaction-scoped advisory lock
    serialises allocation for concurrent requests, which the table needs
    because the column has no sequence backing it.
    """
    spec = KEY_ALLOCATORS[table]
    key_column, prefix, width = spec['key'], spec['prefix'], spec['width']

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s));", [f'{table}_key'])
        cursor.execute(
            f"""
            SELECT coalesce(max(substring({key_column} from {len(prefix) + 1})::bigint), 0) + 1
            FROM public.{table}
            WHERE {key_column} LIKE %s
              AND substring({key_column} from {len(prefix) + 1}) ~ '^[0-9]+$';
            """,
            [f'{prefix}%'],
        )
        next_number = cursor.fetchone()[0]

    return f"{prefix}{int(next_number):0{width}d}"


class CustomerResolver:
    """Resolves the Customer row that owns the current request."""

    @staticmethod
    def get_customer_for_user(user):
        """Return the authenticated customer's own `public.customers` row.

        The identity comes only from the verified JWT subject (its profile),
        never from request data, and no customer is created on the fly: a token
        whose subject no longer maps to a row is refused. Every wishlist, cart
        and order query is then scoped to this row, so one customer cannot read
        or write another customer's data.
        """
        if getattr(user, 'role', None) != Role.CUSTOMER:
            raise PermissionDenied("Customer access required.")

        profile = getattr(user, 'profile', None)
        if isinstance(profile, Customer) and profile.customer_id:
            return profile

        customer_id = getattr(user, 'auth_user_id', None) or getattr(user, 'id', None)
        if not customer_id:
            raise PermissionDenied("No customer identity is bound to this session.")

        try:
            customer = Customer.objects.filter(customer_id=customer_id).first()
        except DatabaseError as exc:
            safe_database_failure("customer lookup", exc)

        if not customer:
            # The account no longer exists (or the subject is not a customer).
            raise PermissionDenied("Your customer account could not be found.")

        return customer


def _get_active_product(product_id):
    """Load a product by its real key, or raise 404.

    `public.products` has no active flag, so a row's existence is the only
    availability signal the schema provides; stock is checked separately.
    """
    cleaned = str(product_id or '').strip()
    if not cleaned:
        raise ValidationError({"product_id": "A product id is required."})
    product = Product.objects.filter(product_id=cleaned).first()
    if not product:
        raise NotFound("Product not found.")
    return product


class WishlistService:
    """Reads and writes rows in the existing `public.wishlist` table."""

    @classmethod
    def get_customer_wishlist(cls, customer):
        return (
            WishlistItem.objects
            .filter(customer=customer)
            .select_related('product')
            .order_by('-wishkey')
        )

    @classmethod
    def add_to_wishlist(cls, customer, product_id):
        """Save the product for this customer, or report it already saved.

        The unique index on (customer_id, product_id) makes the second insert
        of the same pair impossible: an IntegrityError from a concurrent
        request falls back to the existing row instead of duplicating it.
        """
        product = _get_active_product(product_id)

        existing = WishlistItem.objects.filter(customer=customer, product=product).first()
        if existing:
            return existing, False

        try:
            with transaction.atomic():
                wishkey = allocate_key('wishlist')
                item = WishlistItem.objects.create(
                    wishkey=wishkey, customer=customer, product=product
                )
        except IntegrityError:
            raced = WishlistItem.objects.filter(customer=customer, product=product).first()
            if raced:
                return raced, False
            raise
        except DatabaseError as exc:
            safe_database_failure("wishlist add", exc)

        return item, True

    @classmethod
    def remove_from_wishlist(cls, customer, product_id):
        """Delete only this customer's row for the given product."""
        try:
            deleted_count, _ = (
                WishlistItem.objects
                .filter(customer=customer, product_id=str(product_id or '').strip())
                .delete()
            )
        except DatabaseError as exc:
            safe_database_failure("wishlist remove", exc)
        return deleted_count > 0


class CartService:
    """Reads and writes rows in the existing `public.cart` table."""

    @staticmethod
    def get_available_stock(product):
        """Stock carried on the product row (`available_quantity`).

        There is no separate inventory table in this database. A missing value
        is treated as unknown stock rather than zero, so products without
        recorded quantities are not blocked at the cart level.
        """
        quantity = getattr(product, 'available_quantity', None)
        if quantity is None:
            return None
        try:
            return int(quantity)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _guard_quantity(cls, product, quantity, current_in_cart=0):
        available = cls.get_available_stock(product)
        if available is not None and quantity > available:
            raise ValidationError(
                f"Only {available} unit(s) of '{product.product_name}' are in stock "
                f"(you have {current_in_cart} in your bag)."
            )
        if quantity > MAX_QUANTITY_PER_LINE:
            raise ValidationError(
                f"A single line can hold at most {MAX_QUANTITY_PER_LINE} item(s)."
            )

    @classmethod
    def get_customer_cart_items(cls, customer):
        return (
            CartItem.objects
            .filter(customer=customer)
            .select_related('product')
            .order_by('-cartkey')
        )

    @classmethod
    def get_cart_summary(cls, customer):
        """Build the cart payload from the database rows themselves."""
        items = list(cls.get_customer_cart_items(customer))
        item_data = CartItemSerializer(items, many=True).data

        total_items = sum(item.quantity or 0 for item in items)
        subtotal = sum(
            float(line['unit_price'] or 0) * int(line['quantity'] or 0)
            for line in item_data
        )

        return {
            'items': item_data,
            'total_items': total_items,
            'subtotal': round(subtotal, 2),
            'total': round(subtotal, 2),
        }

    @classmethod
    def add_to_cart(cls, customer, product_id, quantity=1):
        """Add one line, or raise the quantity of the existing line.

        Existing behaviour is kept: the same product is never stored twice for
        one customer. The row is locked for the duration of the transaction so
        concurrent adds to the same line accumulate instead of overwriting each
        other.
        """
        product = _get_active_product(product_id)
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValidationError({"quantity": "Quantity must be a whole number."})
        if quantity < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})

        available = cls.get_available_stock(product)
        if available is not None and available <= 0:
            raise ValidationError(f"'{product.product_name}' is currently out of stock.")

        try:
            with transaction.atomic():
                existing = (
                    CartItem.objects
                    .select_for_update()
                    .filter(customer=customer, product=product)
                    .first()
                )
                if existing:
                    cls._guard_quantity(product, (existing.quantity or 0) + quantity,
                                        existing.quantity or 0)
                    existing.quantity = (existing.quantity or 0) + quantity
                    existing.save(update_fields=['quantity'])
                    return existing, False

                cls._guard_quantity(product, quantity, 0)
                cartkey = allocate_key('cart')
                new_item = CartItem.objects.create(
                    cartkey=cartkey, customer=customer, product=product,
                    quantity=quantity,
                )
        except IntegrityError:
            # Another request inserted the same (customer, product) line first:
            # accumulate onto it instead of failing or duplicating.
            with transaction.atomic():
                raced = (
                    CartItem.objects
                    .select_for_update()
                    .filter(customer=customer, product=product)
                    .first()
                )
                if not raced:
                    # Another writer removed the row between our two reads; the
                    # client can simply retry the add.
                    raise ServiceUnavailable()
                cls._guard_quantity(product, (raced.quantity or 0) + quantity,
                                    raced.quantity or 0)
                raced.quantity = (raced.quantity or 0) + quantity
                raced.save(update_fields=['quantity'])
                return raced, False
        except DatabaseError as exc:
            safe_database_failure("cart add", exc)

        return new_item, True

    @classmethod
    def update_cart_quantity(cls, customer, product_id, quantity):
        """Set a line's quantity (never deletes; removal is its own action)."""
        try:
            item = (
                CartItem.objects
                .select_related('product')
                .filter(customer=customer, product_id=str(product_id or '').strip())
                .first()
            )
        except DatabaseError as exc:
            safe_database_failure("cart quantity read", exc)

        if not item:
            raise NotFound("Item not found in your shopping bag.")

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValidationError({"quantity": "Quantity must be a whole number."})
        if quantity < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})

        cls._guard_quantity(item.product, quantity)

        try:
            with transaction.atomic():
                item.quantity = quantity
                item.save(update_fields=['quantity'])
        except DatabaseError as exc:
            safe_database_failure("cart quantity update", exc)

        return item

    @classmethod
    def remove_from_cart(cls, customer, product_id):
        try:
            deleted_count, _ = (
                CartItem.objects
                .filter(customer=customer, product_id=str(product_id or '').strip())
                .delete()
            )
        except DatabaseError as exc:
            safe_database_failure("cart remove", exc)
        return deleted_count > 0

    @classmethod
    def clear_cart(cls, customer):
        try:
            with transaction.atomic():
                CartItem.objects.filter(customer=customer).delete()
        except DatabaseError as exc:
            safe_database_failure("cart clear", exc)
