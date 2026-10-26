"""Order services over the existing `public.orders` table.

The dataset records one product per order (orderid is the primary key and there
is no order-items table), so a customer's order history is a filtered, joined
read of `orders` and `products`.

Price interpretation - the table stores `initial_price`, `additional_discount`
and `final_price` where `final_price = initial_price - additional_discount`,
i.e. `final_price` is the amount actually paid for the order. The UI needs a
unit price that is consistent with the line total, so the API derives
`unit_price = final_price / quantity` and reports `subtotal = final_price`.
Orders placed through checkout follow the same rule: `final_price` is
`unit price x quantity` from the product row, so both old and new rows satisfy
unit_price x quantity == total_amount.
"""

from datetime import date

from django.db import transaction, DatabaseError
from django.db.models import DateField
from django.db.models.expressions import RawSQL
from rest_framework.exceptions import ValidationError, NotFound

from cart.models import CartItem
from cart.services import (
    CartService,
    allocate_key,
    safe_database_failure,
)
from catalog.pricing import get_dim_product_selling_price_map
from .models import Order

# 'DD-MM-YYYY', matching the format the existing rows already use.
PURCHASE_DATE_FORMAT = '%d-%m-%Y'


class OrderQueryService:
    """Customer-scoped order reads with strict ownership."""

    # purchase_date is TEXT, so ordering has to compare parsed dates: a plain
    # string sort would put 31-12-2025 before 01-01-2026.
    DATE_SORT = RawSQL("to_date(purchase_date, 'DD-MM-YYYY')", [], output_field=DateField())

    @classmethod
    def _base_queryset(cls):
        return (
            Order.objects
            .select_related('product', 'customer')
            .annotate(order_date_parsed=cls.DATE_SORT)
        )

    @classmethod
    def get_customer_orders(cls, customer, limit=None, offset=0):
        """Every order that belongs to this customer, newest first."""
        queryset = (
            cls._base_queryset()
            .filter(customer=customer)
            .order_by('-order_date_parsed', '-order_id')
        )
        if offset:
            queryset = queryset[offset:]
        if limit:
            queryset = queryset[:limit]
        return list(queryset)

    @classmethod
    def count_customer_orders(cls, customer):
        return Order.objects.filter(customer=customer).count()

    @classmethod
    def get_customer_order(cls, customer, order_id):
        """Fetch one order, scoped to the requesting customer.

        Ownership is part of the WHERE clause rather than a post-check, so an
        order id typed into the URL or an API call simply does not exist for
        anyone else - it can neither be read nor leaked.
        """
        cleaned = str(order_id or '').strip()
        if not cleaned:
            raise NotFound("Order not found.")

        order = cls._base_queryset().filter(customer=customer, order_id=cleaned).first()
        if not order:
            raise NotFound("Order not found.")
        return order


class OrderCreationService:
    """Turns the customer's cart rows into `public.orders` rows.

    Prices are recalculated from the database (never from the client), stock is
    re-checked, the rows are written in one transaction and the cart is cleared
    only after the inserts succeed.
    """

    @classmethod
    def create_orders_from_cart(cls, customer, checkout_data):
        payment_method = cls._resolve_payment_method(checkout_data)

        try:
            with transaction.atomic():
                cart_items = list(
                    CartItem.objects
                    .select_for_update()
                    .filter(customer=customer)
                    .select_related('product')
                    .order_by('cartkey')
                )
                if not cart_items:
                    raise ValidationError(
                        "Your shopping bag is empty. Please add items before placing an order."
                    )

                # Authoritative prices, straight from the product rows.
                price_map = get_dim_product_selling_price_map(
                    item.product_id for item in cart_items if item.product
                )

                created_orders = []
                purchase_date = date.today().strftime(PURCHASE_DATE_FORMAT)

                for item in cart_items:
                    product = item.product
                    if not product:
                        raise ValidationError("A product in your bag is no longer available.")

                    available = CartService.get_available_stock(product)
                    if available is not None and available < (item.quantity or 1):
                        raise ValidationError(
                            f"Insufficient stock for '{product.product_name}'. "
                            f"Requested {item.quantity}, only {available} available."
                        )

                    unit_price = float(price_map.get(str(product.product_id)) or 0) or 0.0
                    quantity = int(item.quantity or 1)
                    gross = round(unit_price * quantity, 2)

                    order_id = allocate_key('orders')
                    order = Order.objects.create(
                        order_id=order_id,
                        product=product,
                        customer=customer,
                        quantity=quantity,
                        # No discount is applied at checkout in this schema.
                        initial_price=gross,
                        additional_discount=0.0,
                        final_price=gross,
                        purchase_date=purchase_date,
                        # Nothing has shipped yet: no status is invented.
                        delivery_status=None,
                        shipping_time_days=None,
                        payment_method=payment_method,
                        rating=None,
                    )
                    created_orders.append(order)

                CartService.clear_cart(customer)
        except DatabaseError as exc:
            safe_database_failure("checkout", exc)

        return created_orders

    @staticmethod
    def _resolve_payment_method(checkout_data):
        """Map the chosen method onto the values the table already stores."""
        raw = str(checkout_data.get('payment_method') or 'COD').strip().upper()
        if raw in ('COD', 'CASH ON DELIVERY'):
            return 'Cash on Delivery'
        raise ValidationError(
            "Online payment is launching soon. Please choose Cash on Delivery to place your order."
        )


class CustomerReturnService:
    """Return requests need a returns table, which this database does not have."""

    @classmethod
    def request_return(cls, customer, order_id, order_item_id, return_reason,
                       condition_on_return=None):
        # Validate ownership first, so the answer never confirms that someone
        # else's order exists.
        OrderQueryService.get_customer_order(customer, order_id)
        raise ValidationError(
            "Return requests are not available for this store yet: the current "
            "database has no returns records. Please contact support."
        )
