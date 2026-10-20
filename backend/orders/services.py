import uuid
from datetime import date
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from accounts.models import Customer, Warehouse
from catalog.models import Product, Inventory, OrderItem
from catalog.pricing import get_dim_product_selling_price_map
from cart.models import CartItem
from cart.services import CartService, CustomerResolver
from warehouse.models import Return, Delivery
from .models import Order, Payment


class WarehouseAllocationService:
    """
    Selects a single fulfillment warehouse that has sufficient stock for ALL items in the customer's cart.
    If no single warehouse can fulfill the complete cart, raises a ValidationError.
    Isolated in a dedicated service for future geocoding / PIN-based allocation.
    """
    @classmethod
    def allocate_warehouse(cls, cart_items):
        warehouses = list(Warehouse.objects.all())
        if not warehouses:
            raise ValidationError("No fulfillment warehouse is currently active.")

        qualifying_warehouses = []
        for wh in warehouses:
            can_fulfill_all = True
            for item in cart_items:
                inv = Inventory.objects.filter(warehouse=wh, product=item.product).first()
                available = inv.stock_quantity if inv and inv.stock_quantity is not None else 0
                required_qty = item.quantity or 1
                if available < required_qty:
                    can_fulfill_all = False
                    break

            if can_fulfill_all:
                qualifying_warehouses.append(wh)

        if not qualifying_warehouses:
            raise ValidationError(
                "None of our fulfillment centers currently has sufficient stock to fulfill all items in your bag together. Please adjust item quantities."
            )

        # Select the first fulfillment center meeting all stock requirements
        return qualifying_warehouses[0]


class StockVerificationService:
    """
    Verifies real-time stock availability across warehouses before finalizing checkout.
    """
    @classmethod
    def verify_stock(cls, cart_items):
        for item in cart_items:
            product = item.product
            if not product or not product.is_active:
                raise ValidationError(
                    f"Product '{getattr(item, 'product_name', 'Item')}' is no longer active or available."
                )

            available_stock = CartService.get_available_stock(product)
            required_qty = item.quantity or 1
            if available_stock < required_qty:
                raise ValidationError(
                    f"Insufficient stock for '{product.product_name}'. Requested {required_qty}, but only {available_stock} available in stock."
                )


class OrderCreationService:
    """
    Transactional order creation:
    1. Authenticates customer and reads actual database CartItem records.
    2. Recalculates prices and totals from authoritative database records (never trusts client inputs).
    3. Re-checks real-time inventory and allocates a single qualifying warehouse.
    4. Creates Order, OrderItem(s), and Payment in transaction.atomic().
    5. Clears the customer's cart ONLY upon successful order creation.
    """
    @classmethod
    def create_order_from_cart(cls, customer, checkout_data):
        cart_items = list(
            CartItem.objects.filter(customer=customer)
            .select_related('product')
        )

        if not cart_items:
            raise ValidationError("Your shopping bag is empty. Please add items before placing an order.")

        # Re-verify stock levels from live database inventory
        StockVerificationService.verify_stock(cart_items)

        # Allocate single warehouse that has stock for ALL items
        warehouse = WarehouseAllocationService.allocate_warehouse(cart_items)

        price_map = get_dim_product_selling_price_map(
            item.product.product_id for item in cart_items if item.product
        )

        # Authoritative server-side price calculation
        subtotal = 0.0
        for item in cart_items:
            unit_price = float(price_map.get(str(item.product.product_id), 0) or 0)
            qty = int(item.quantity or 1)
            subtotal += unit_price * qty

        discount_amount = 0.0
        total_amount = subtotal

        # Format shipping address
        raw_address = checkout_data.get('shipping_address', '').strip()
        city = checkout_data.get('city', '').strip()
        state = checkout_data.get('state', '').strip()
        postal_code = checkout_data.get('postal_code', '').strip()

        address_parts = [raw_address]
        location_parts = [p for p in [city, state, postal_code] if p]
        if location_parts and not any(p.lower() in raw_address.lower() for p in location_parts):
            address_parts.append(", ".join(location_parts))
        formatted_address = ", ".join(address_parts)

        # Payment details: COD is the only operational method
        payment_method = checkout_data.get('payment_method', 'COD')
        if payment_method != 'COD':
            raise ValidationError("Online payment is launching soon. Please choose Cash on Delivery to place your order.")

        today_date = date.today()
        now = timezone.now()
        order_payment_status = 'unpaid'
        payment_record_status = 'Pending'
        txn_prefix = 'COD'

        order_id = str(uuid.uuid4())
        txn_ref = f"{txn_prefix}{int(now.timestamp())}"

        # Atomic execution guarantees no partial state
        with transaction.atomic():
            # 1. Create Order record
            order = Order.objects.create(
                order_id=order_id,
                customer=customer,
                warehouse=warehouse,
                order_date=today_date,
                order_status='confirmed',
                payment_status=order_payment_status,
                total_amount=total_amount,
                discount_amount=discount_amount,
                shipping_address=formatted_address,
                created_at=now,
                updated_at=now,
            )

            # 2. Create OrderItem records
            for item in cart_items:
                item_unit_price = int(price_map.get(str(item.product.product_id), 0) or 0)
                item_qty = int(item.quantity or 1)
                item_subtotal = float(item_unit_price * item_qty)

                OrderItem.objects.create(
                    order_item_id=str(uuid.uuid4()),
                    order_id=order_id,
                    product=item.product,
                    quantity=item_qty,
                    unit_price=item_unit_price,
                    discount=0.0,
                    subtotal=item_subtotal,
                )

            # 3. Create Payment record
            Payment.objects.create(
                payment_id=str(uuid.uuid4()),
                order=order,
                customer=customer,
                payment_method=payment_method,
                payment_amount=total_amount,
                payment_status=payment_record_status,
                payment_date=today_date,
                transaction_reference=txn_ref,
            )

            # 4. Clear Cart ONLY after successful order and payment record creation
            CartService.clear_cart(customer)

        return order


class OrderQueryService:
    """
    Securely queries customer orders with strict authorization checks.
    """
    @classmethod
    def get_customer_order(cls, customer, order_id):
        try:
            order = (
                Order.objects.select_related('customer', 'warehouse')
                .prefetch_related('payments')
                .get(order_id=order_id)
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        # Ensure Customer A cannot access Customer B's order
        if order.customer_id != customer.customer_id:
            raise PermissionDenied("You do not have permission to view this order.")

        return order


class CustomerReturnService:
    """
    Handles customer return requests with strict validation:
    - Order belongs to the authenticated customer.
    - Order is in delivered status.
    - Selected order item exists in order.
    - Prevents duplicate active returns for the same item.
    - Creates canonical Return record with status 'Requested'.
    """
    @classmethod
    def request_return(cls, customer, order_id, order_item_id, return_reason, condition_on_return=None):
        order = OrderQueryService.get_customer_order(customer, order_id)

        # Ensure order is delivered
        order_st = (order.order_status or '').strip().lower()
        forward_delivery = Delivery.objects.filter(order_id=order.order_id).exclude(delivery_type__iexact='RETURN').first()
        delivery_st = (forward_delivery.delivery_status or '').strip().lower() if forward_delivery else ''

        if order_st != 'delivered' and delivery_st != 'delivered':
            raise ValidationError("Returns can only be requested for orders that have been successfully delivered.")

        # Ensure order item belongs to this order
        try:
            order_item = OrderItem.objects.select_related('product').get(
                order_item_id=order_item_id,
                order_id=order.order_id
            )
        except OrderItem.DoesNotExist:
            raise ValidationError("Selected item does not belong to this order.")

        # Check existing return
        existing_return = Return.objects.filter(order_item_id=order_item.order_item_id).first()
        if existing_return:
            cur_st = (existing_return.return_status or '').strip().lower()
            if cur_st not in ['rejected', 'failed']:
                raise ValidationError(
                    f"A return request for this item is already active (Current status: {existing_return.return_status})."
                )

        # Calculate refund amount
        refund_amount = order_item.subtotal
        if refund_amount is None or refund_amount == 0:
            unit_price = getattr(order_item, 'unit_price', 0) or 0
            qty = getattr(order_item, 'quantity', 1) or 1
            refund_amount = float(unit_price) * int(qty)

        reason_clean = (return_reason or '').strip()
        if not reason_clean:
            raise ValidationError("Please provide a reason for the return.")

        cond_clean = (condition_on_return or '').strip() or 'Unused, original packaging'

        return_id = f"RET-{uuid.uuid4().hex[:8].upper()}"

        if existing_return and (existing_return.return_status or '').strip().lower() in ['rejected', 'failed']:
            # Re-activate return
            existing_return.return_reason = reason_clean
            existing_return.condition_on_return = cond_clean
            existing_return.return_status = 'Requested'
            existing_return.return_date = date.today().isoformat()
            existing_return.refund_amount = float(refund_amount)
            existing_return.assigned_employee_id = None
            existing_return.delivery_partner = None
            existing_return.pickup_date = None
            existing_return.save()
            return existing_return

        new_return = Return.objects.create(
            return_id=return_id,
            order_item=order_item,
            customer=customer,
            return_reason=reason_clean,
            return_date=date.today().isoformat(),
            return_status='Requested',
            refund_amount=float(refund_amount),
            condition_on_return=cond_clean
        )
        return new_return
