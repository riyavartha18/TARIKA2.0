from django.db.models import Count, Q, Sum, CharField
from django.db.models.functions import Concat, Substr
from django.db import connection, transaction
from catalog.models import Category, Product
from .models import Order, Delivery, Return, Payment
import datetime



class WarehouseFeatureUnavailable(Exception):
    """Raised when a workflow cannot be persisted against this database schema.

    The connected database has no return-status, courier, dispatch or fulfilment
    warehouse columns/tables, so approving, rejecting, assigning a pickup or
    dispatching an order has nowhere to be written. Rather than silently
    pretending (or fabricating a row), the service refuses and the API answers
    409 with the reason.
    """


class WarehouseService:
    # The real delivery_status values on public.orders. 'Delivered' is the only
    # state that counts as a completed delivery; 'Returned' and 'In Transit' are
    # separate real states and are never lumped in with it.
    DELIVERED = 'Delivered'
    IN_TRANSIT = 'In Transit'
    RETURNED = 'Returned'

    # UI status word -> the real delivery_status it means.
    STATUS_ALIASES = {
        'delivered': DELIVERED,
        'shipped': IN_TRANSIT,
        'in transit': IN_TRANSIT,
        'in_transit': IN_TRANSIT,
        'returned': RETURNED,
    }
    # Words the dashboard offers that this schema simply does not record. They
    # match only rows with no delivery status at all, never a wrong subset.
    UNSET_STATUSES = {'pending', 'confirmed', 'processing', 'cancelled'}
    # Columns the warehouse product views actually render — selecting just these
    # keeps the grouped-endpoint rows narrow (image/link/text columns are large).
    GROUPED_PRODUCT_FIELDS = [
        'product_id', 'product_name', 'main_category', 'sub_category',
        'link', 'discount_price', 'actual_price_text', 'discounted_price',
        'available_quantity', 'image',
    ]

    @staticmethod
    def get_grouped_category_products(warehouse_id=None, letter=None):
        """
        Fetch all products from the real `public.products` table in ONE query,
        then group by main_category in Python.  Stock is read directly from the
        real `available_quantity` column (there is no inventory table in this
        schema).  Returns a list of plain dicts ready for direct JSON
        serialization.
        """
        from catalog.serializers import CATEGORY_IMAGE_MAPPING
        from catalog.normalize import normalize_category, canonical_display

        products = (
            Product.objects
            .filter(is_active=True)
            .only(*WarehouseService.GROUPED_PRODUCT_FIELDS)
            .order_by('main_category', 'product_name')
        )
        if letter:
            import re
            letter_str = str(letter).strip()
            if letter_str and letter_str.upper() != 'ALL':
                char = letter_str[:1]
                from django.db.models import Q
                products = products.filter(
                    Q(product_name__istartswith=char) |
                    Q(product_name__iregex=rf'^\s*{re.escape(char)}')
                )

        # Group in Python by the CASE- AND WHITESPACE-INSENSITIVE category key
        # (centralized normalize_category), so "Dress"/"dress"/" DRESS " form one
        # group. The display name comes from the first-seen raw value.
        cat_map = {}
        for p in products:
            key = normalize_category(p.main_category)
            if not key:
                continue
            if key not in cat_map:
                cat_name = canonical_display(p.main_category)
                cat_map[key] = {
                    'category_id': key.replace(' ', '-'),
                    'category_name': cat_name,
                    'parent_category_id': None,
                    'description': '',
                    'image': CATEGORY_IMAGE_MAPPING.get(key),
                    'product_count': 0,
                    'products': []
                }
            entry = cat_map[key]
            cid = entry['category_id']
            # Real DB stock: keep None as None (missing data) — never invent it.
            total_stock_val = p.available_quantity if p.available_quantity is not None else None
            image_url = p.image or entry['image']
            entry['products'].append({
                'product_id': p.product_id,
                'product_name': p.product_name,
                'category_id': cid,
                'category_name': entry['category_name'],
                'sub_category': p.sub_category,
                'link': p.link,
                'base_price': p.base_price,
                'selling_price': p.selling_price,
                # Discount AMOUNT in currency + derived percentage (never stored).
                'discount_price': p.discount_price,
                'discount_percentage': p.discount_percentage,
                'in_stock': (total_stock_val or 0) > 0,
                'total_stock': total_stock_val,
                'available_quantity': total_stock_val,
                'hidden': bool(p.hidden),
                'image': image_url,
            })
            entry['product_count'] += 1

        return sorted(cat_map.values(), key=lambda c: c['category_name'].lower())

    # Serializer key -> real Product model field name, for the PUT endpoint.
    # (update_fields must receive these FIELD names, not db_column names.)
    #
    # The wire keys keep the meaning the warehouse editor already speaks, while
    # the columns they land in are the ones this schema really has:
    #   initial_price (ORIGINAL)  -> products.actual_price     (TEXT)
    #   discount_price (AMOUNT)   -> products.discount_price
    #   actual_price / discounted_price (FINAL) -> products.discounted_price
    # `hidden` is deliberately not editable here: it is the storefront
    # visibility flag carried by the dataset, not a warehouse field.
    UPDATE_FIELD_MAP = {
        'product_name': 'product_name',            # -> products.name
        'main_category': 'main_category',          # -> products.main_category
        'sub_category': 'sub_category',            # -> products.sub_category
        'image': 'image',                          # -> products.image
        'link': 'link',                            # -> products.link
        'initial_price': 'actual_price_text',      # ORIGINAL price (TEXT column)
        'discount_price': 'discount_price',        # discount AMOUNT in currency
        'actual_price': 'discounted_price',        # FINAL selling price column
        'discounted_price': 'discounted_price',    # FINAL selling price column
        'available_quantity': 'available_quantity',  # double precision
        'is_active': 'is_active',
        'hidden': 'hidden',
        'confidence': 'confidence',
    }

    @staticmethod
    def get_product_detail(product_id):
        """
        Fetch a single product by product_key from the real `public.products`
        table.  Stock lives directly on the product row (`available_quantity`),
        so no related queries are needed.

        Returns the Product ORM instance or raises Product.DoesNotExist.
        """
        return Product.objects.get(product_id=product_id)

    @staticmethod
    def update_product(product_id, validated_data):
        """
        Apply validated_data to the product identified by product_key and
        persist it to the real `public.products` table.  All business-rule
        validation is expected to have been done by the serializer before
        calling this method.

        Returns the freshly re-read Product instance so callers respond with
        the values actually saved in the database (not optimistic state).

        Raises Product.DoesNotExist if no product matches product_id.
        """
        product = Product.objects.get(product_id=product_id)

        updated_fields = []
        for data_key, model_attr in WarehouseService.UPDATE_FIELD_MAP.items():
            if data_key in validated_data:
                setattr(product, model_attr, validated_data[data_key])
                # Two wire keys can write one column (`actual_price` and
                # `discounted_price` both mean the final price here, and the
                # later map entry wins), but listing a column twice in
                # update_fields is not valid SQL — so record each column once.
                if model_attr not in updated_fields:
                    updated_fields.append(model_attr)

        if updated_fields:
            # update_fields takes model FIELD names (Django maps them to the
            # db_column values like 'name' / 'actual_price' itself).
            product.save(update_fields=updated_fields)

        # Re-read the row so the response reflects persisted database values.
        return Product.objects.get(product_id=product_id)

    # Referencing tables that carry a real FK to products.product_key. A product
    # still present in any of these is never hard-deleted: it is archived so the
    # historical / live rows keep their foreign key and no business history is
    # lost.
    HISTORY_TABLES = ('orders', 'cart', 'wishlist')

    # Replenishment purchase orders also reference the product (by product_key),
    # but deliberately WITHOUT a foreign key so a purchase order survives product
    # archiving. A product with any purchase-order row is therefore never
    # hard-deleted either, so outstanding supplier orders are never orphaned.
    PO_TABLE = 'replenishment_orders'

    @staticmethod
    def _count_product_references(product_id):
        """Return (sales_refs, purchase_order_refs) for the product.

        ``sales_refs`` counts live/historical rows in orders, cart and wishlist
        (all keyed by ``product_id``). ``po_refs`` counts rows in
        replenishment_orders (keyed by ``product_key``). A non-zero value in
        either one blocks a hard DELETE.
        """
        sales_refs = 0
        with connection.cursor() as cursor:
            for table in WarehouseService.HISTORY_TABLES:
                cursor.execute(
                    f"SELECT COUNT(*) FROM public.{table} WHERE product_id = %s",
                    [product_id],
                )
                sales_refs += int(cursor.fetchone()[0] or 0)
            cursor.execute(
                f"SELECT COUNT(*) FROM public.{WarehouseService.PO_TABLE} "
                "WHERE product_key = %s",
                [product_id],
            )
            po_refs = int(cursor.fetchone()[0] or 0)
        return sales_refs, po_refs

    @staticmethod
    def delete_product(product_id):
        """FK-safe product removal, persisted to the real database.

        * No historical/live references -> hard ``DELETE`` of the product row
          (the row and every storefront entry genuinely disappear).
        * Referenced by an order, cart or wishlist -> archive instead
          (``is_active = False``), so it vanishes from all listings while the
          foreign keys and sales history stay intact.

        Returns a dict describing what happened. Raises Product.DoesNotExist.
        """
        product = Product.objects.get(product_id=product_id)
        sales_refs, po_refs = WarehouseService._count_product_references(product_id)
        reference_count = sales_refs + po_refs

        with transaction.atomic():
            if reference_count == 0:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM public.products WHERE product_key = %s",
                        [product_id],
                    )
                    deleted = cursor.rowcount
                if not deleted:
                    raise Product.DoesNotExist(f"Product '{product_id}' not found.")
                return {
                    'action': 'deleted',
                    'product_id': product_id,
                    'product_name': product.product_name,
                    'reference_count': 0,
                    'sales_refs': 0,
                    'po_refs': 0,
                }

            product.is_active = False
            product.save(update_fields=['is_active'])
            return {
                'action': 'archived',
                'product_id': product_id,
                'product_name': product.product_name,
                'reference_count': reference_count,
                'sales_refs': sales_refs,
                'po_refs': po_refs,
            }

    @staticmethod
    def get_orders(search=None, status=None, warehouse_id=None):
        """Real rows of `public.orders`, filtered and searchable.

        `status` is the dashboard's order-status word. The table has no
        order_status column: `delivery_status` is the only progression signal, so
        'delivered' filters `delivery_status = 'Delivered'` exactly, and the
        statuses this schema does not track are matched only against rows that
        genuinely carry no delivery status. `warehouse_id` is accepted for API
        compatibility but ignored, because orders carry no warehouse column.
        """
        qs = Order.objects.select_related('customer', 'product').all()

        cleaned = (status or '').strip()
        if cleaned and cleaned.lower() != 'all':
            key = cleaned.lower()
            if key in WarehouseService.STATUS_ALIASES:
                qs = qs.filter(delivery_status=WarehouseService.STATUS_ALIASES[key])
            elif key in WarehouseService.UNSET_STATUSES:
                qs = qs.filter(Q(delivery_status__isnull=True) | Q(delivery_status=''))
            else:
                # Any other word is compared to the real column verbatim, so an
                # unknown filter returns nothing rather than the wrong rows.
                qs = qs.filter(delivery_status__iexact=cleaned)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(order_id__icontains=q) |
                Q(customer__customer_name__icontains=q) |
                Q(customer__email__icontains=q) |
                Q(product__product_name__icontains=q) |
                Q(product_id__icontains=q)
            )

        # purchase_date is TEXT 'DD-MM-YYYY', which does not sort as a date, so
        # the newest-first ordering is built from the real day/month/year parts.
        return qs.annotate(
            order_date_key=Concat(
                Substr('purchase_date', 7, 4),
                Substr('purchase_date', 4, 2),
                Substr('purchase_date', 1, 2),
                output_field=CharField(),
            )
        ).order_by('-order_date_key', 'order_id')

    @staticmethod
    def get_order_detail(order_id):
        """Fetch one order by its real `orderid`. Raises Order.DoesNotExist."""
        return Order.objects.select_related('customer', 'product').get(order_id=order_id)

    @staticmethod
    def get_deliveries(search=None, status=None, partner=None, warehouse_id=None):
        """Delivery rows, derived from `public.orders` delivery_status.

        This schema has no `deliveries` table, so a delivery IS the order's own
        delivery state. The queryset is restricted to rows that actually carry
        one of the three recorded statuses, and defaults to DELIVERED work (the
        dashboard's Delivered view); a courier/partner or warehouse filter can
        never be honoured because no such column exists, so those requests are
        refused with an explicit error instead of quietly ignoring the filter.
        """
        if (partner and partner.strip().upper() != 'ALL') or warehouse_id:
            raise WarehouseFeatureUnavailable(
                'Courier partner and warehouse filters are not available: the '
                'connected database has no deliveries table and no warehouse '
                'column on orders.'
            )

        cleaned = (status or '').strip()
        if not cleaned or cleaned.upper() == 'ALL':
            qs = Order.objects.filter(
                delivery_status__in=[
                    WarehouseService.DELIVERED,
                    WarehouseService.IN_TRANSIT,
                    WarehouseService.RETURNED,
                ]
            )
        else:
            key = cleaned.lower()
            if key in WarehouseService.STATUS_ALIASES:
                qs = Order.objects.filter(
                    delivery_status=WarehouseService.STATUS_ALIASES[key]
                )
            else:
                qs = Order.objects.filter(delivery_status__iexact=cleaned)

        qs = qs.select_related('customer', 'product')
        if search:
            q = search.strip()
            qs = qs.filter(
                Q(order_id__icontains=q) |
                Q(customer__customer_name__icontains=q) |
                Q(customer__email__icontains=q)
            )
        return qs.order_by('order_id')

    @staticmethod
    def delivery_row(order):
        """Shape one real order row into the deliveries payload.

        Only the columns the database actually has are filled; the courier,
        dispatch/expected/actual dates, failure reason and warehouse stay None so
        the dashboard can say the workflow is not tracked rather than invent
        'Standard Express' or a dispatch date.
        """
        return {
            'delivery_id': order.order_id,
            'order_id': order.order_id,
            'warehouse_id': None,
            'warehouse_name': None,
            'warehouse_city': None,
            'customer_name': order.customer.customer_name if order.customer else None,
            'customer_city': None,
            'delivery_partner': None,
            'dispatch_date': None,
            'expected_delivery_date': None,
            'actual_delivery_date': None,
            'delivery_status': order.delivery_status,
            'failure_reason': None,
            'shipping_time_days': int(order.shipping_time_days) if order.shipping_time_days is not None else None,
            'purchase_date': order.purchase_date,
        }

    @staticmethod
    def get_returns(search=None, status=None, reason=None):
        """Real rows of `public.returns`, joined to customer and product.

        `status` cannot be honoured: the table has no return_status column, so a
        status filter is refused rather than silently returning everything. The
        `reason` filter and the free-text search run on real values.
        """
        cleaned_status = (status or '').strip()
        if cleaned_status and cleaned_status.upper() != 'ALL':
            raise WarehouseFeatureUnavailable(
                'Return status filtering is not available: public.returns has no '
                'status column, so returns cannot be split by workflow state.'
            )

        qs = Return.objects.select_related('customer', 'product').all()

        cleaned_reason = (reason or '').strip()
        if cleaned_reason and cleaned_reason.upper() != 'ALL':
            qs = qs.filter(return_reason__iexact=cleaned_reason)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(return_id__icontains=q) |
                Q(customer__customer_name__icontains=q) |
                Q(customer__email__icontains=q) |
                Q(product__product_name__icontains=q) |
                Q(product_id__icontains=q) |
                Q(return_reason__icontains=q) |
                Q(abuse_type__icontains=q)
            )

        return qs.order_by('return_id')

    # Why the return / dispatch workflow cannot run against this database.
    RETURN_WORKFLOW_UNAVAILABLE = (
        'Return workflow actions are not available in this database: '
        'public.returns has no status, refund, condition or pickup column, so an '
        'approval cannot be persisted. The recorded returns themselves are '
        'listed in full.'
    )
    DISPATCH_UNAVAILABLE = (
        'Order dispatch is not available in this database: there is no '
        'deliveries table, no order status column and no employees table, so a '
        'courier assignment has nowhere to be recorded. Orders are read-only here.'
    )

    @staticmethod
    def accept_return(return_id, manager_user=None):
        """Refused: no return_status column exists to approve into.

        The row is still looked up first, so an unknown reference keeps failing
        as "not found" instead of masking a bad id behind the 409.
        """
        WarehouseService._get_return_or_raise(return_id)
        raise WarehouseFeatureUnavailable(WarehouseService.RETURN_WORKFLOW_UNAVAILABLE)

    @staticmethod
    def reject_return(return_id, manager_user=None):
        """Refused for the same schema reason as accept_return."""
        WarehouseService._get_return_or_raise(return_id)
        raise WarehouseFeatureUnavailable(WarehouseService.RETURN_WORKFLOW_UNAVAILABLE)

    @staticmethod
    def assign_return_pickup(return_id, delivery_partner=None, assigned_employee_id=None,
                             manager_user=None):
        """Refused: no pickup / courier / employee columns or table exist."""
        WarehouseService._get_return_or_raise(return_id)
        raise WarehouseFeatureUnavailable(WarehouseService.RETURN_WORKFLOW_UNAVAILABLE)

    @staticmethod
    def receive_return(return_id, manager_user=None):
        """Refused: warehouse receipt has no status column to record."""
        WarehouseService._get_return_or_raise(return_id)
        raise WarehouseFeatureUnavailable(WarehouseService.RETURN_WORKFLOW_UNAVAILABLE)

    @staticmethod
    def _get_return_or_raise(return_id):
        try:
            return Return.objects.select_related('customer', 'product').get(return_id=return_id)
        except Return.DoesNotExist:
            raise Return.DoesNotExist(f"Return '{return_id}' not found.")

    @staticmethod
    def get_courier_partners():
        """Courier companies recorded in this database: none exist.

        `public.deliveries` and `public.employees` are absent, so there is no
        real courier list to return. An empty list is reported (with the reason
        added by the view) instead of a fabricated dropdown.
        """
        return []

    @staticmethod
    def get_delivery_employees(company=None):
        """Delivery-partner employees: no employees table in this schema."""
        return []

    @staticmethod
    def dispatch_order(order_id, delivery_partner=None, assigned_employee_id=None,
                       expected_delivery_date=None, manager_user=None):
        """Refused: dispatch has nowhere to be recorded in this schema.

        The order is looked up first so an unknown reference still reports "not
        found". `public.deliveries` does not exist, `public.orders` has no
        status column to move to 'shipped' and there is no employees table to
        assign a courier to, so writing a dispatch would mean inventing either a
        table or a value. Orders are therefore read-only for the warehouse.
        """
        try:
            Order.objects.select_related('customer', 'product').get(order_id=order_id)
        except Order.DoesNotExist:
            raise Order.DoesNotExist(f"Order '{order_id}' not found.")

        raise WarehouseFeatureUnavailable(WarehouseService.DISPATCH_UNAVAILABLE)

        # Enforce warehouse assignment check:
        # Warehouse Manager must only be able to dispatch orders belonging to their assigned warehouse.
        if manager_user and getattr(manager_user, 'is_authenticated', False):
            user_role = getattr(manager_user, 'role', None)
            user_wh = getattr(manager_user, 'warehouse_id', None)
            if user_role == 'WAREHOUSE_MANAGER' and user_wh and order.warehouse_id:
                if str(order.warehouse_id).strip() != str(user_wh).strip():
                    raise PermissionError(
                        f"Permission denied: You are assigned to warehouse '{user_wh}', "
                        f"but order '{order_id}' belongs to warehouse '{order.warehouse_id}'."
                    )

        # Validate order readiness for shipment
        current_status = (order.order_status or '').strip().lower()
        if current_status not in ['confirmed', 'pending', 'ready']:
            raise ValueError(
                f"Order '{order_id}' cannot be dispatched. Current status is '{order.order_status}'. "
                "Only confirmed orders can be dispatched."
            )

        # Validate courier company
        partner_clean = (delivery_partner or '').strip()
        if not partner_clean:
            raise ValueError("Courier company name is required.")

        # Validate employee
        try:
            employee = Employee.objects.get(
                employee_id=assigned_employee_id,
                role=EmployeeRole.DELIVERY_PARTNER,
                is_active=True
            )
        except Employee.DoesNotExist:
            raise ValueError(f"Delivery employee #{assigned_employee_id} not found or is inactive.")

        if employee.courier_company and employee.courier_company.strip().lower() != partner_clean.lower():
            raise ValueError(
                f"Employee '{employee.full_name}' belongs to '{employee.courier_company}', "
                f"not '{partner_clean}'."
            )

        # Validate expected_delivery_date
        expected_str = str(expected_delivery_date or '').strip()
        if not expected_str:
            raise ValueError("Expected delivery date must be explicitly provided.")

        today_str = datetime.date.today().strftime('%Y-%m-%d')

        # Update or create Delivery row (prevent duplicates)
        delivery = Delivery.objects.filter(order_id=order.order_id).first()
        if delivery:
            delivery.delivery_partner = partner_clean
            delivery.assigned_employee = employee
            delivery.dispatch_date = today_str
            delivery.expected_delivery_date = expected_str
            delivery.delivery_status = 'Assigned'
            delivery.failure_reason = None
            if not delivery.warehouse and order.warehouse:
                delivery.warehouse = order.warehouse
            delivery.save()
        else:
            deliv_id = f"DEL-{uuid.uuid4().hex[:10].upper()}"
            delivery = Delivery.objects.create(
                delivery_id=deliv_id,
                order=order,
                warehouse=order.warehouse,
                delivery_partner=partner_clean,
                assigned_employee=employee,
                dispatch_date=today_str,
                expected_delivery_date=expected_str,
                delivery_status='Assigned',
                failure_reason=None
            )

        # Update Order status
        order.order_status = 'shipped'
        order.updated_at = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        order.save()

        return order, delivery
