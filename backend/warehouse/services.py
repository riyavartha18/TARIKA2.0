from django.db.models import Count, Q, Sum, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from catalog.models import Category, Product, Inventory
from .models import Order, Delivery, Return, Payment
import datetime



class WarehouseService:
    @staticmethod
    def get_grouped_category_products(warehouse_id=None):
        """
        Fetch all active products in ONE query, then group by category in Python.
        Annotates total stock quantity from the inventory table.
        Returns a list of plain dicts ready for direct JSON serialization.
        """
        from catalog.serializers import CATEGORY_IMAGE_MAPPING

        # Query all active products with category, manufacturer & total inventory stock
        products = (
            Product.objects
            .filter(Q(is_active=True) | Q(is_active__isnull=True))
            .select_related('category', 'manufacturer')
            .annotate(stock_qty=Coalesce(Sum('inventory_items__stock_quantity'), 0))
            .order_by('category__category_name', 'product_name')
        )

        # Group in Python
        cat_map = {}
        for p in products:
            cat = p.category
            if cat is None:
                continue
            cid = cat.category_id
            if cid not in cat_map:
                cat_name = cat.category_name or ''
                cat_map[cid] = {
                    'category_id': cid,
                    'category_name': cat_name,
                    'parent_category_id': cat.parent_category_id,
                    'description': cat.description or '',
                    'image': CATEGORY_IMAGE_MAPPING.get(cat_name.strip().lower()),
                    'product_count': 0,
                    'products': []
                }
            cat_name_lower = (p.category.category_name or '').strip().lower()
            total_stock_val = int(getattr(p, 'stock_qty', 0) or 0)
            cat_map[cid]['products'].append({
                'product_id': p.product_id,
                'product_name': p.product_name,
                'category_id': cid,
                'category_name': cat.category_name,
                'manufacturer_id': p.manufacturer_id,
                'manufacturer_name': p.manufacturer.manufacturer_name if p.manufacturer else None,
                'sku': p.sku,
                'description': p.description,
                'gender': p.gender,
                'color': p.color,
                'size': p.size,
                'material': p.material,
                'base_price': p.base_price,
                'selling_price': p.selling_price,
                'launch_date': p.launch_date,
                'is_active': p.is_active,
                'in_stock': total_stock_val > 0,
                'total_stock': total_stock_val,
                'image': CATEGORY_IMAGE_MAPPING.get(cat_name_lower),
            })
            cat_map[cid]['product_count'] += 1

        return sorted(cat_map.values(), key=lambda c: c['category_name'])

    @staticmethod
    def get_product_detail(product_id):
        """
        Fetch a single product by product_id with category, manufacturer,
        and prefetched inventory items so the serializer can compute
        total_stock without extra queries.

        Returns the Product ORM instance or raises Product.DoesNotExist.
        """
        return (
            Product.objects
            .select_related('category', 'manufacturer')
            .prefetch_related('inventory_items')
            .get(product_id=product_id)
        )

    @staticmethod
    def update_product(product_id, validated_data):
        """
        Apply validated_data to the product identified by product_id and
        persist it to the database.  All business-rule validation is expected
        to have been done by the serializer before calling this method.

        Returns the updated Product instance (with inventory prefetched so the
        response serializer can compute in_stock / total_stock immediately).

        Raises Product.DoesNotExist if no product matches product_id.
        """
        product = (
            Product.objects
            .select_related('category', 'manufacturer')
            .get(product_id=product_id)
        )

        # Apply each validated field
        updatable_fields = [
            'product_name', 'description', 'gender', 'color',
            'size', 'material', 'base_price', 'selling_price',
            'launch_date', 'is_active',
        ]
        for field in updatable_fields:
            if field in validated_data:
                value = validated_data[field]
                # Normalise empty strings to None for optional text fields
                if value == '' and field in ('description', 'gender', 'color', 'size', 'material', 'launch_date'):
                    value = None
                setattr(product, field, value)

        # Stamp updated_at with current UTC timestamp string
        product.updated_at = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        product.save()

        # Update stock quantity in inventory table if provided
        if 'stock_quantity' in validated_data and validated_data['stock_quantity'] is not None:
            new_stock = validated_data['stock_quantity']
            inventory_items = Inventory.objects.filter(product_id=product_id)
            if inventory_items.exists():
                first_item = inventory_items.first()
                first_item.stock_quantity = new_stock
                first_item.last_restock_date = datetime.datetime.utcnow().strftime('%Y-%m-%d')
                first_item.save()
            else:
                import uuid
                Inventory.objects.create(
                    inventory_id=str(uuid.uuid4()),
                    product_id=product_id,
                    stock_quantity=new_stock,
                    last_restock_date=datetime.datetime.utcnow().strftime('%Y-%m-%d')
                )

        # Re-fetch with inventory so caller can serialise stock fields
        return (
            Product.objects
            .select_related('category', 'manufacturer')
            .prefetch_related('inventory_items')
            .get(product_id=product_id)
        )

    @staticmethod
    def get_orders(search=None, status=None, warehouse_id=None):
        """
        Queries database orders with pre-fetched customer and warehouse relations.
        Supports search across order_id, customer full_name, email, shipping_address.
        """
        qs = Order.objects.select_related('customer', 'warehouse').all()


        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        if status and status.lower() != 'all':
            qs = qs.filter(order_status__iexact=status)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(order_id__icontains=q) |
                Q(customer__full_name__icontains=q) |
                Q(customer__email__icontains=q) |
                Q(shipping_address__icontains=q)
            )

        return qs.order_by('-order_date', '-created_at')

    @staticmethod
    def get_order_detail(order_id):
        """
        Fetch a single order by order_id with pre-fetched customer and warehouse relations.
        Raises Order.DoesNotExist if not found.
        """
        return Order.objects.select_related('customer', 'warehouse').get(order_id=order_id)


    @staticmethod
    def get_deliveries(search=None, status=None, partner=None, warehouse_id=None):
        """
        Queries database deliveries with pre-fetched order, customer, and warehouse.
        """
        qs = Delivery.objects.select_related('order__customer', 'warehouse').all()

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        if status and status.lower() != 'all':
            qs = qs.filter(delivery_status__iexact=status)

        if partner and partner.lower() != 'all':
            qs = qs.filter(delivery_partner__icontains=partner)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(delivery_id__icontains=q) |
                Q(order_id__icontains=q) |
                Q(delivery_partner__icontains=q) |
                Q(order__customer__full_name__icontains=q)
            )

        return qs.order_by('-dispatch_date')

    @staticmethod
    def get_returns(search=None, status=None, reason=None):
        """
        Queries database returns with pre-fetched order_item, product, and customer.
        When no status filter is applied, returns with status 'requested' appear FIRST.
        """
        qs = Return.objects.select_related('order_item__product', 'customer').all()

        if status and status.lower() != 'all':
            qs = qs.filter(return_status__iexact=status)

        if reason and reason.lower() != 'all':
            qs = qs.filter(return_reason__icontains=reason)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(return_id__icontains=q) |
                Q(order_item__order_id__icontains=q) |
                Q(customer__full_name__icontains=q) |
                Q(order_item__product__product_name__icontains=q) |
                Q(return_reason__icontains=q)
            )

        # Annotate: 'requested' returns get priority 0, all others get 1
        qs = qs.annotate(
            is_requested=Case(
                When(return_status__iexact='requested', then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            )
        )

        return qs.order_by('is_requested', '-return_date')

    @staticmethod
    def _check_return_warehouse_auth(ret, manager_user):
        """
        Validates that the authenticated Warehouse Manager is authorized to manage this return.
        Admins have global access.
        """
        if manager_user and getattr(manager_user, 'is_authenticated', False):
            user_role = getattr(manager_user, 'role', None)
            user_wh = getattr(manager_user, 'warehouse_id', None)
            if user_role == 'WAREHOUSE_MANAGER' and user_wh:
                order = None
                if ret.order_item and ret.order_item.order_id:
                    order = Order.objects.filter(order_id=ret.order_item.order_id).first()
                if order and order.warehouse_id:
                    if str(order.warehouse_id).strip() != str(user_wh).strip():
                        raise PermissionError(
                            f"Permission denied: You are assigned to warehouse '{user_wh}', "
                            f"but return '{ret.return_id}' belongs to warehouse '{order.warehouse_id}'."
                        )

    @staticmethod
    def accept_return(return_id, manager_user=None):
        """
        Approve/Accept a return request. Only allowed when return_status is 'requested'.
        Updates return_status to 'Approved'. Computes refund_amount from order_item
        if not already set. Persists changes to the database.
        """
        try:
            ret = Return.objects.select_related(
                'order_item__product', 'customer'
            ).get(return_id=return_id)
        except Return.DoesNotExist:
            raise Return.DoesNotExist(f"Return '{return_id}' not found.")

        WarehouseService._check_return_warehouse_auth(ret, manager_user)

        if (ret.return_status or '').strip().lower() not in ['requested']:
            raise ValueError(
                f"Cannot approve return '{return_id}': current status is '{ret.return_status}'. "
                "Only 'Requested' returns can be approved."
            )

        ret.return_status = 'Approved'

        # Compute refund_amount from order_item if not already set
        if ret.refund_amount is None or ret.refund_amount == 0:
            if ret.order_item:
                subtotal = getattr(ret.order_item, 'subtotal', None)
                if not subtotal:
                    unit_price = getattr(ret.order_item, 'unit_price', None)
                    qty = getattr(ret.order_item, 'quantity', 1) or 1
                    if unit_price:
                        subtotal = float(unit_price) * int(qty)
                if subtotal:
                    ret.refund_amount = float(subtotal)

        ret.save()

        return Return.objects.select_related(
            'order_item__product', 'customer', 'assigned_employee'
        ).get(return_id=return_id)

    @staticmethod
    def reject_return(return_id, manager_user=None):
        """
        Reject a return request. Only allowed when return_status is 'requested'.
        Updates return_status to 'Rejected' and persists to the database.
        """
        try:
            ret = Return.objects.select_related(
                'order_item__product', 'customer'
            ).get(return_id=return_id)
        except Return.DoesNotExist:
            raise Return.DoesNotExist(f"Return '{return_id}' not found.")

        WarehouseService._check_return_warehouse_auth(ret, manager_user)

        if (ret.return_status or '').strip().lower() not in ['requested']:
            raise ValueError(
                f"Cannot reject return '{return_id}': current status is '{ret.return_status}'. "
                "Only 'Requested' returns can be rejected."
            )

        ret.return_status = 'Rejected'
        ret.save()

        return Return.objects.select_related(
            'order_item__product', 'customer', 'assigned_employee'
        ).get(return_id=return_id)

    @staticmethod
    def assign_return_pickup(return_id, delivery_partner, assigned_employee_id, manager_user=None):
        """
        Assigns an approved return to a real active delivery partner employee.
        - Validates return exists and belongs to manager's warehouse.
        - Validates return status is 'Approved' (or 'Accepted').
        - Validates courier company and employee match.
        - Sets return status to 'Pickup Assigned'.
        - Creates/updates Delivery record with delivery_type='RETURN' and status='Assigned'.
        """
        import uuid
        from accounts.models import Employee

        try:
            ret = Return.objects.select_related('order_item__product', 'customer').get(return_id=return_id)
        except Return.DoesNotExist:
            raise Return.DoesNotExist(f"Return '{return_id}' not found.")

        WarehouseService._check_return_warehouse_auth(ret, manager_user)

        cur_status = (ret.return_status or '').strip().lower()
        if cur_status not in ['approved', 'accepted']:
            raise ValueError(
                f"Cannot assign pickup for return '{return_id}'. Current status is '{ret.return_status}'. "
                "Only approved returns can be assigned for pickup."
            )

        partner_clean = (delivery_partner or '').strip()
        if not partner_clean:
            raise ValueError("Courier company name is required.")

        try:
            emp = Employee.objects.get(
                employee_id=assigned_employee_id,
                role='DELIVERY_PARTNER',
                is_active=True
            )
        except Employee.DoesNotExist:
            raise ValueError(
                f"Employee ID {assigned_employee_id} does not exist, is inactive, "
                "or does not possess the 'DELIVERY_PARTNER' role."
            )

        if (emp.courier_company or '').strip().lower() != partner_clean.lower():
            raise ValueError(
                f"Employee '{emp.full_name}' belongs to courier company '{emp.courier_company}', "
                f"which does not match the selected company '{delivery_partner}'."
            )

        today_str = datetime.date.today().isoformat()
        ret.return_status = 'Pickup Assigned'
        ret.delivery_partner = partner_clean
        ret.assigned_employee = emp
        ret.pickup_date = today_str
        ret.save()

        # Create or update corresponding Delivery record for pickup
        order = None
        if ret.order_item and ret.order_item.order_id:
            order = Order.objects.filter(order_id=ret.order_item.order_id).first()

        del_rec = Delivery.objects.filter(return_record=ret).first()
        if not del_rec:
            del_rec = Delivery(
                delivery_id=f"DEL-RET-{uuid.uuid4().hex[:8].upper()}",
                order=order,
                warehouse_id=order.warehouse_id if order else getattr(manager_user, 'warehouse_id', None),
                delivery_type='RETURN',
                return_record=ret,
            )
        del_rec.delivery_partner = partner_clean
        del_rec.assigned_employee = emp
        del_rec.delivery_status = 'Assigned'
        del_rec.dispatch_date = today_str
        del_rec.save()

        return Return.objects.select_related(
            'order_item__product', 'customer', 'assigned_employee'
        ).get(return_id=return_id)

    @staticmethod
    def receive_return(return_id, manager_user=None):
        """
        Confirms receipt of returned merchandise at the warehouse.
        Only allowed when return has been picked up by the delivery partner.
        Sets return_status to 'Completed' and marks delivery record as 'Delivered'.
        """
        try:
            ret = Return.objects.select_related('order_item__product', 'customer').get(return_id=return_id)
        except Return.DoesNotExist:
            raise Return.DoesNotExist(f"Return '{return_id}' not found.")

        WarehouseService._check_return_warehouse_auth(ret, manager_user)

        cur_status = (ret.return_status or '').strip().lower()
        if cur_status not in ['picked up', 'received at warehouse']:
            raise ValueError(
                f"Cannot confirm receipt for return '{return_id}'. Current status is '{ret.return_status}'. "
                "Merchandise must be picked up before confirming warehouse receipt."
            )

        today_str = datetime.date.today().isoformat()
        ret.return_status = 'Completed'
        ret.save()

        del_rec = Delivery.objects.filter(return_record=ret).first()
        if del_rec:
            del_rec.delivery_status = 'Delivered'
            del_rec.actual_delivery_date = today_str
            del_rec.save()

        return Return.objects.select_related(
            'order_item__product', 'customer', 'assigned_employee'
        ).get(return_id=return_id)

    @staticmethod
    def get_courier_partners():
        """
        Returns a sorted list of unique courier company names from existing delivery records
        and registered active delivery partner employees.
        """
        from accounts.models import Employee, EmployeeRole

        delivery_partners = set(
            Delivery.objects
            .exclude(delivery_partner__isnull=True)
            .exclude(delivery_partner__exact='')
            .values_list('delivery_partner', flat=True)
            .distinct()
        )
        employee_partners = set(
            Employee.objects
            .filter(role=EmployeeRole.DELIVERY_PARTNER, is_active=True)
            .exclude(courier_company__isnull=True)
            .exclude(courier_company__exact='')
            .values_list('courier_company', flat=True)
            .distinct()
        )
        all_partners = {p.strip() for p in (delivery_partners | employee_partners) if p and p.strip()}
        return sorted(list(all_partners))

    @staticmethod
    def get_delivery_employees(company=None):
        """
        Returns active employees with role 'DELIVERY_PARTNER'.
        If company is provided, filters by courier_company.
        """
        from accounts.models import Employee, EmployeeRole
        qs = Employee.objects.filter(role=EmployeeRole.DELIVERY_PARTNER, is_active=True)
        if company and company.strip().lower() != 'all':
            qs = qs.filter(courier_company__iexact=company.strip())
        return [
            {
                'employee_id': emp.employee_id,
                'full_name': emp.full_name,
                'email': emp.email,
                'phone': emp.phone,
                'courier_company': emp.courier_company,
                'warehouse': emp.warehouse_id,
                'is_active': emp.is_active,
            }
            for emp in qs.order_by('full_name')
        ]

    @staticmethod
    def dispatch_order(order_id, delivery_partner, assigned_employee_id, expected_delivery_date, manager_user=None):
        """
        Dispatches an order:
        - Validates order existence
        - Validates warehouse manager's assigned warehouse if manager_user is provided
        - Validates order is confirmed and ready for shipment
        - Validates courier company and assigned employee
        - Validates expected_delivery_date
        - Creates or updates Delivery row with status 'Assigned' (prevents duplicates)
        - Updates Order status to 'shipped'
        """
        import uuid
        from accounts.models import Employee, EmployeeRole

        try:
            order = Order.objects.select_related('customer', 'warehouse').get(order_id=order_id)
        except Order.DoesNotExist:
            raise Order.DoesNotExist(f"Order '{order_id}' not found.")

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

