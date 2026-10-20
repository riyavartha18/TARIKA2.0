from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from admin.serializers import AdminStaffCreateSerializer

import uuid
import datetime

from accounts.models import Employee, Customer, Role, Warehouse
from catalog.models import Product, Inventory, Category, Manufacturer
from catalog.serializers import CATEGORY_IMAGE_MAPPING
from warehouse.models import Order, Delivery, Return
from warehouse.services import WarehouseService
from warehouse.serializers import WarehouseOrderSerializer, WarehouseOrderDetailSerializer
from warehouse.views import StandardWarehousePagination


class AdminCreateStaffView(APIView):
    """
    Admin-only endpoint for provisioning staff members:
    - WAREHOUSE_MANAGER (requires valid warehouse_id)
    - DELIVERY_PARTNER (warehouse_id = NULL)
    
    Customers, Warehouse Managers, and Delivery Partners cannot access this endpoint (403 Forbidden).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def post(self, request):
        serializer = AdminStaffCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            created_employee = serializer.save()
            return Response({
                "message": f"Staff account ({created_employee['role']}) created successfully.",
                "employee": created_employee
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminDashboardStatsView(APIView):
    """
    Admin-only endpoint for aggregating system-wide retail statistics:
    - KPIs: Total Customers, Total Orders, Total Products, Total Revenue
    - Order Overview: status counts (Pending, Processing, Delivered, Cancelled)
    - Recent Orders: latest database order records
    - Inventory Snapshot: warehouse count, stock total, low stock items
    - Operational Alerts: pending returns, pending deliveries, low stock
    - Recent Activity: aggregated timeline feed from latest DB events
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        # 1. KPIs
        total_customers = Customer.objects.count()
        total_orders = Order.objects.count()
        total_products = Product.objects.count()
        total_revenue_val = Order.objects.exclude(order_status__iexact='Cancelled').aggregate(
            rev=Coalesce(Sum('total_amount'), 0.0)
        )['rev'] or 0.0

        # 2. Order Breakdown
        pending_orders = Order.objects.filter(order_status__iexact='Pending').count()
        processing_orders = Order.objects.filter(order_status__iexact='Processing').count()
        delivered_orders = Order.objects.filter(
            Q(order_status__iexact='Delivered') | Q(order_status__iexact='Completed')
        ).count()
        cancelled_orders = Order.objects.filter(order_status__iexact='Cancelled').count()

        # 3. Recent Orders (limit 6)
        recent_orders_qs = Order.objects.select_related('customer', 'warehouse').all()[:6]
        recent_orders = []
        for o in recent_orders_qs:
            recent_orders.append({
                'order_id': o.order_id,
                'customer_name': o.customer.full_name if o.customer else 'Registered Customer',
                'customer_email': o.customer.email if o.customer else None,
                'order_date': o.order_date or o.created_at or 'N/A',
                'total_amount': o.total_amount or 0.0,
                'order_status': o.order_status or 'Confirmed',
                'warehouse_name': o.warehouse.warehouse_name if o.warehouse else 'Fulfillment Center'
            })

        # 4. Inventory Snapshot
        total_warehouses = Warehouse.objects.count()
        total_stock_units = Inventory.objects.aggregate(
            total=Coalesce(Sum('stock_quantity'), 0)
        )['total'] or 0
        low_stock_count = Inventory.objects.filter(stock_quantity__lte=5).count()

        warehouses_qs = Warehouse.objects.all()[:6]
        warehouses_list = []
        for w in warehouses_qs:
            warehouses_list.append({
                'warehouse_id': w.warehouse_id,
                'warehouse_name': w.warehouse_name or w.warehouse_id,
                'city': w.city or 'N/A',
                'capacity': w.capacity or 0,
                'manager_name': w.manager_name or 'Assigned Manager'
            })

        # 5. Operational Alerts
        pending_returns = Return.objects.filter(return_status__iexact='Requested').count()
        pending_deliveries = Delivery.objects.filter(
            Q(delivery_status__iexact='Pending') |
            Q(delivery_status__iexact='Dispatched') |
            Q(delivery_status__iexact='In Transit')
        ).count()

        # 6. Recent Activity Feed
        recent_activity = []
        for o in recent_orders_qs[:3]:
            recent_activity.append({
                'id': f'order-{o.order_id}',
                'type': 'ORDER',
                'title': f'Order #{o.order_id}',
                'subtitle': f'{o.customer.full_name if o.customer else "Customer"} • ₹{int(o.total_amount or 0):,}',
                'timestamp': o.order_date or 'Recent',
                'status': o.order_status or 'Confirmed'
            })

        for r in Return.objects.select_related('customer').all()[:2]:
            recent_activity.append({
                'id': f'return-{r.return_id}',
                'type': 'RETURN',
                'title': f'Return Request #{r.return_id}',
                'subtitle': f'{r.customer.full_name if r.customer else "Customer"} • {r.return_reason or "Return"}',
                'timestamp': r.return_date or 'Recent',
                'status': r.return_status or 'Requested'
            })

        for d in Delivery.objects.select_related('order__customer').all()[:2]:
            recent_activity.append({
                'id': f'delivery-{d.delivery_id}',
                'type': 'DELIVERY',
                'title': f'Delivery #{d.delivery_id}',
                'subtitle': f'{d.delivery_partner or "Partner"} • Order #{d.order_id}',
                'timestamp': d.dispatch_date or 'Recent',
                'status': d.delivery_status or 'In Transit'
            })

        return Response({
            'kpis': {
                'total_customers': total_customers,
                'total_orders': total_orders,
                'total_products': total_products,
                'total_revenue': total_revenue_val,
            },
            'order_overview': {
                'total': total_orders,
                'pending': pending_orders,
                'processing': processing_orders,
                'delivered': delivered_orders,
                'cancelled': cancelled_orders,
            },
            'recent_orders': recent_orders,
            'inventory_snapshot': {
                'total_warehouses': total_warehouses,
                'total_stock_units': total_stock_units,
                'low_stock_count': low_stock_count,
                'warehouses': warehouses_list,
            },
            'operational_alerts': {
                'pending_returns': pending_returns,
                'pending_deliveries': pending_deliveries,
                'low_stock_products': low_stock_count,
                'cancelled_orders': cancelled_orders,
            },
            'recent_activity': recent_activity,
        }, status=status.HTTP_200_OK)


class AdminStaffListView(APIView):
    """
    Admin-only endpoint for querying staff members, summary KPI counts,
    and available warehouses for staff creation.
    Supports search (name, email, phone), role filtering, and status filtering.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        search = request.query_params.get('search')
        role = request.query_params.get('role')
        status_param = request.query_params.get('status')

        qs = Employee.objects.select_related('warehouse').all()

        if role and role.upper() != 'ALL':
            qs = qs.filter(role__iexact=role)

        if status_param and status_param.upper() != 'ALL':
            if status_param.lower() in ('active', 'true', '1'):
                qs = qs.filter(is_active=True)
            elif status_param.lower() in ('inactive', 'false', '0'):
                qs = qs.filter(is_active=False)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q)
            )

        employees_list = []
        for emp in qs.order_by('-created_at', 'full_name'):
            employees_list.append({
                'employee_id': emp.employee_id,
                'auth_user_id': str(emp.auth_user_id),
                'full_name': emp.full_name,
                'email': emp.email,
                'phone': emp.phone,
                'role': emp.role,
                'warehouse_id': emp.warehouse_id,
                'warehouse_name': emp.warehouse.warehouse_name if emp.warehouse else None,
                'is_active': emp.is_active,
                'created_at': emp.created_at.strftime('%Y-%m-%d') if emp.created_at else None,
            })

        # Summary KPIs
        total_staff = Employee.objects.count()
        warehouse_managers = Employee.objects.filter(role='WAREHOUSE_MANAGER').count()
        delivery_partners = Employee.objects.filter(role='DELIVERY_PARTNER').count()
        active_staff = Employee.objects.filter(is_active=True).count()

        # Warehouse options for Create Staff dropdown
        warehouses_qs = Warehouse.objects.all().order_by('warehouse_name')
        warehouse_options = []
        for w in warehouses_qs:
            warehouse_options.append({
                'warehouse_id': w.warehouse_id,
                'warehouse_name': w.warehouse_name or w.warehouse_id,
                'city': w.city or '',
            })

        return Response({
            'summary': {
                'total_staff': total_staff,
                'warehouse_managers': warehouse_managers,
                'delivery_partners': delivery_partners,
                'active_staff': active_staff,
            },
            'warehouses': warehouse_options,
            'employees': employees_list,
        }, status=status.HTTP_200_OK)


class AdminStaffToggleStatusView(APIView):
    """
    Admin-only endpoint for toggling an employee's active status (activate/deactivate).
    Prevents admins from deactivating their own admin account.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def patch(self, request, employee_id):
        try:
            employee = Employee.objects.get(employee_id=employee_id)
        except Employee.DoesNotExist:
            return Response(
                {'detail': f'Employee with ID "{employee_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Prevent admin from deactivating their own account
        if str(employee.auth_user_id) == str(request.user.auth_user_id):
            return Response(
                {'detail': 'You cannot deactivate your own active Administrator account.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Explicitly set status if provided, else toggle
        target_status = request.data.get('is_active')
        if target_status is not None:
            employee.is_active = bool(target_status)
        else:
            employee.is_active = not employee.is_active

        employee.save(update_fields=['is_active'])

        return Response({
            'message': f'Staff member "{employee.full_name}" is now {"Active" if employee.is_active else "Inactive"}.',
            'employee': {
                'employee_id': employee.employee_id,
                'full_name': employee.full_name,
                'email': employee.email,
                'role': employee.role,
                'is_active': employee.is_active,
            }
        }, status=status.HTTP_200_OK)


class AdminWarehouseListView(APIView):
    """
    Admin-only endpoint for system-wide warehouse management & oversight:
    - Network Summary KPIs: total warehouses, network capacity, total inventory stock, capacity utilization %
    - Per-Warehouse Detailed Aggregations: location (city, state, country), capacity, inventory units,
      distinct product count, low-stock count, active orders count, assigned manager details (joined with Employee table).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        search = request.query_params.get('search')

        qs = Warehouse.objects.all()

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(warehouse_name__icontains=q) |
                Q(city__icontains=q) |
                Q(state__icontains=q) |
                Q(country__icontains=q) |
                Q(manager_name__icontains=q) |
                Q(warehouse_id__icontains=q)
            )

        # Network Summary Aggregates
        total_warehouses = Warehouse.objects.count()
        total_capacity = Warehouse.objects.aggregate(
            tot=Coalesce(Sum('capacity'), 0)
        )['tot'] or 0

        total_inventory_units = Inventory.objects.aggregate(
            tot=Coalesce(Sum('stock_quantity'), 0)
        )['tot'] or 0

        network_utilization_pct = 0.0
        if total_capacity > 0:
            network_utilization_pct = round((total_inventory_units / total_capacity) * 100, 1)

        # Pre-query managers from Employee table for relationship matching
        managers = Employee.objects.filter(
            role='WAREHOUSE_MANAGER',
            warehouse_id__isnull=False
        ).select_related('warehouse')
        manager_map = {emp.warehouse_id: emp for emp in managers}

        warehouses_list = []
        for w in qs.order_by('warehouse_name', 'warehouse_id'):
            # Assigned manager lookup
            assigned_emp = manager_map.get(w.warehouse_id)
            mgr_name = assigned_emp.full_name if assigned_emp else (w.manager_name or 'Unassigned')
            mgr_email = assigned_emp.email if assigned_emp else None
            mgr_phone = assigned_emp.phone if assigned_emp else (w.contact_number or None)

            # Inventory statistics for this warehouse
            w_inv_qs = Inventory.objects.filter(warehouse_id=w.warehouse_id)
            stock_units = w_inv_qs.aggregate(tot=Coalesce(Sum('stock_quantity'), 0))['tot'] or 0
            product_count = w_inv_qs.values('product_id').distinct().count()
            low_stock_count = w_inv_qs.filter(stock_quantity__lte=5).count()

            # Active orders fulfilled by this warehouse
            active_orders_count = Order.objects.filter(warehouse_id=w.warehouse_id).exclude(order_status__iexact='Cancelled').count()

            # Safe capacity utilization calculation
            capacity_val = w.capacity or 0
            utilization_pct = 0.0
            if capacity_val > 0:
                utilization_pct = round((stock_units / capacity_val) * 100, 1)

            warehouses_list.append({
                'warehouse_id': w.warehouse_id,
                'warehouse_name': w.warehouse_name or w.warehouse_id,
                'city': w.city or 'N/A',
                'state': w.state or '',
                'country': w.country or '',
                'capacity': capacity_val,
                'stock_units': stock_units,
                'product_count': product_count,
                'low_stock_count': low_stock_count,
                'active_orders_count': active_orders_count,
                'utilization_pct': utilization_pct,
                'manager_name': mgr_name,
                'manager_email': mgr_email,
                'manager_phone': mgr_phone,
                'contact_number': w.contact_number,
                'created_at': w.created_at,
            })

        return Response({
            'summary': {
                'total_warehouses': total_warehouses,
                'total_capacity': total_capacity,
                'total_inventory_units': total_inventory_units,
                'network_utilization_pct': network_utilization_pct,
            },
            'warehouses': warehouses_list,
        }, status=status.HTTP_200_OK)


class AdminProductListView(APIView):
    """
    Admin-only endpoint for product catalog management:
    - Real DB summary metrics: Total Products, Total Categories, In-Stock Products, Low-Stock Products
    - Live search by product_name, sku, category_name, description, color, material
    - Category filter dynamically using existing Category records
    - Stock status filter (ALL, IN_STOCK, LOW_STOCK, OUT_OF_STOCK)
    - Detailed product listing with inventory stock, warehouse breakdown, image URL
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        search = request.query_params.get('search')
        category_filter = request.query_params.get('category')
        stock_filter = request.query_params.get('stock_status')

        # Real DB KPIs
        total_products = Product.objects.count()
        total_categories = Category.objects.count()

        # Prefetch categories list for dropdown filter
        categories_qs = Category.objects.all().order_by('category_name')
        categories_list = [
            {
                'category_id': c.category_id,
                'category_name': c.category_name or c.category_id
            }
            for c in categories_qs
        ]

        # Query all products annotated with aggregate inventory stock
        products_qs = Product.objects.select_related('category', 'manufacturer').prefetch_related('inventory_items__warehouse').annotate(
            total_stock_annotated=Coalesce(Sum('inventory_items__stock_quantity'), 0)
        )

        # System-wide KPI stock calculations
        all_annotated = Product.objects.annotate(
            total_stock_annotated=Coalesce(Sum('inventory_items__stock_quantity'), 0)
        )
        in_stock_products = all_annotated.filter(total_stock_annotated__gt=0).count()
        low_stock_products = all_annotated.filter(total_stock_annotated__gt=0, total_stock_annotated__lte=5).count()

        # Search filtering
        if search:
            q = search.strip()
            products_qs = products_qs.filter(
                Q(product_name__icontains=q) |
                Q(sku__icontains=q) |
                Q(category__category_name__icontains=q) |
                Q(description__icontains=q) |
                Q(color__icontains=q) |
                Q(material__icontains=q)
            )

        # Category filtering
        if category_filter:
            c_val = category_filter.strip()
            products_qs = products_qs.filter(
                Q(category__category_id=c_val) | Q(category__category_name__iexact=c_val)
            )

        # Stock status filtering
        if stock_filter:
            st = stock_filter.strip().upper()
            if st == 'IN_STOCK':
                products_qs = products_qs.filter(total_stock_annotated__gt=0)
            elif st == 'LOW_STOCK':
                products_qs = products_qs.filter(total_stock_annotated__gt=0, total_stock_annotated__lte=5)
            elif st == 'OUT_OF_STOCK':
                products_qs = products_qs.filter(total_stock_annotated=0)

        products_list = []
        for p in products_qs.order_by('-created_at', 'product_name'):
            cat_name = p.category.category_name if p.category else ''
            cat_name_lower = (cat_name or '').strip().lower()
            img_url = CATEGORY_IMAGE_MAPPING.get(cat_name_lower, None)

            tot_stock = int(getattr(p, 'total_stock_annotated', 0) or 0)
            is_low = (0 < tot_stock <= 5)

            # Warehouse stock breakdown
            wh_breakdown = []
            for inv in p.inventory_items.all():
                if inv.warehouse:
                    wh_breakdown.append({
                        'warehouse_id': inv.warehouse_id,
                        'warehouse_name': inv.warehouse.warehouse_name or inv.warehouse_id,
                        'stock_quantity': inv.stock_quantity or 0,
                        'reorder_level': inv.reorder_level or 5
                    })

            products_list.append({
                'product_id': p.product_id,
                'product_name': p.product_name or 'Unnamed Product',
                'category_id': p.category_id,
                'category_name': cat_name or 'Uncategorized',
                'sku': p.sku or 'N/A',
                'description': p.description or '',
                'gender': p.gender or 'Unisex',
                'color': p.color or '',
                'size': p.size or '',
                'material': p.material or '',
                'base_price': p.base_price or p.selling_price or 0,
                'selling_price': p.selling_price or 0,
                'cost_price': p.cost_price or 0,
                'is_active': p.is_active if p.is_active is not None else True,
                'launch_date': p.launch_date or '',
                'total_stock': tot_stock,
                'in_stock': tot_stock > 0,
                'is_low_stock': is_low,
                'image': img_url,
                'warehouse_inventory': wh_breakdown
            })

        return Response({
            'metrics': {
                'total_products': total_products,
                'total_categories': total_categories,
                'in_stock_products': in_stock_products,
                'low_stock_products': low_stock_products,
            },
            'categories': categories_list,
            'products': products_list,
        }, status=status.HTTP_200_OK)


class AdminProductCreateView(APIView):
    """
    Admin-only endpoint to create a new retail product in the catalog:
    - Validates product attributes (name, category, price)
    - Persists product to real database table (`products`)
    - Provisions initial inventory record in real database table (`inventory`)
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def post(self, request):
        data = request.data
        product_name = (data.get('product_name') or '').strip()
        category_id = (data.get('category_id') or '').strip()
        selling_price_raw = data.get('selling_price')

        errors = {}

        if not product_name:
            errors['product_name'] = ['Product name is required.']
        elif len(product_name) < 2:
            errors['product_name'] = ['Product name must be at least 2 characters.']

        if not category_id:
            errors['category_id'] = ['Category is required.']
        else:
            try:
                category_obj = Category.objects.get(category_id=category_id)
            except Category.DoesNotExist:
                errors['category_id'] = [f'Category with ID "{category_id}" does not exist.']

        if selling_price_raw is None or selling_price_raw == '':
            errors['selling_price'] = ['Selling price is required.']
        else:
            try:
                selling_price = float(selling_price_raw)
                if selling_price < 0:
                    errors['selling_price'] = ['Selling price cannot be negative.']
            except ValueError:
                errors['selling_price'] = ['Selling price must be a valid number.']

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        category_obj = Category.objects.get(category_id=category_id)
        base_price_val = data.get('base_price') or selling_price_raw
        cost_price_val = data.get('cost_price') or 0
        sku_val = (data.get('sku') or '').strip() or f"SKU-{uuid.uuid4().hex[:8].upper()}"

        new_product_id = str(uuid.uuid4())
        now_str = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        new_product = Product.objects.create(
            product_id=new_product_id,
            product_name=product_name,
            category=category_obj,
            sku=sku_val,
            description=(data.get('description') or '').strip(),
            gender=(data.get('gender') or 'Unisex').strip(),
            color=(data.get('color') or '').strip(),
            size=(data.get('size') or '').strip(),
            material=(data.get('material') or '').strip(),
            base_price=int(float(base_price_val)),
            selling_price=int(float(selling_price_raw)),
            cost_price=int(float(cost_price_val)),
            is_active=bool(data.get('is_active', True)),
            created_at=now_str,
            updated_at=now_str,
            launch_date=now_str[:10]
        )

        # Initial inventory provisioning
        initial_stock = int(data.get('initial_stock') or 10)
        warehouse_id_val = data.get('warehouse_id')

        warehouse_obj = None
        if warehouse_id_val:
            warehouse_obj = Warehouse.objects.filter(warehouse_id=warehouse_id_val).first()
        if not warehouse_obj:
            warehouse_obj = Warehouse.objects.first()

        if warehouse_obj and initial_stock >= 0:
            inv_id = str(uuid.uuid4())
            Inventory.objects.create(
                inventory_id=inv_id,
                product=new_product,
                warehouse=warehouse_obj,
                stock_quantity=initial_stock,
                reorder_level=5,
                last_restock_date=now_str[:10]
            )

        cat_name = category_obj.category_name or ''
        img_url = CATEGORY_IMAGE_MAPPING.get(cat_name.strip().lower(), None)

        return Response({
            'message': 'Product created successfully.',
            'product': {
                'product_id': new_product.product_id,
                'product_name': new_product.product_name,
                'category_id': category_obj.category_id,
                'category_name': cat_name,
                'sku': new_product.sku,
                'selling_price': new_product.selling_price,
                'base_price': new_product.base_price,
                'total_stock': initial_stock,
                'is_active': new_product.is_active,
                'image': img_url
            }
        }, status=status.HTTP_201_CREATED)



class AdminOrderListView(APIView):
    """
    GET /api/accounts/admin/orders/
    System-wide orders for the administrator. Supports search, status, and warehouse filtering.
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        search = request.query_params.get('search')
        order_status = request.query_params.get('status')
        warehouse_id = request.query_params.get('warehouse')

        queryset = WarehouseService.get_orders(
            search=search,
            status=order_status,
            warehouse_id=warehouse_id
        )

        metrics = {
            'total_orders': queryset.count(),
            'pending_orders': queryset.filter(order_status__iexact='Pending').count(),
            'processing_orders': queryset.filter(order_status__iexact='Processing').count(),
            'completed_orders': queryset.filter(order_status__iexact='Delivered').count(),
            'cancelled_orders': queryset.filter(order_status__iexact='Cancelled').count(),
        }

        paginator = StandardWarehousePagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = WarehouseOrderSerializer(page, many=True)
            response = paginator.get_paginated_response(serializer.data)
            response.data['metrics'] = metrics
            return response

        serializer = WarehouseOrderSerializer(queryset, many=True)
        return Response({'results': serializer.data, 'metrics': metrics}, status=status.HTTP_200_OK)


class AdminOrderDetailView(APIView):
    """
    GET /api/accounts/admin/orders/<order_id>/
    Fetch complete order detail for the administrator.
    """
    permission_classes = [IsAdmin]

    def get(self, request, order_id):
        try:
            order = WarehouseService.get_order_detail(order_id)
        except Order.DoesNotExist:
            return Response(
                {'detail': f'Order "{order_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = WarehouseOrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminCustomerListView(APIView):
    """
    GET /api/admin/customers/
    Admin-only endpoint for system-wide customer management.
    Returns paginated customer list + summary KPIs.
    Supports search by name, email, phone, city.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        search = request.query_params.get('search')
        status_param = request.query_params.get('status')  # 'active' | 'inactive' | 'ALL'

        qs = Customer.objects.all()

        if status_param and status_param.upper() != 'ALL':
            if status_param.lower() in ('active', 'true'):
                qs = qs.filter(is_active=True)
            elif status_param.lower() in ('inactive', 'false'):
                qs = qs.filter(is_active=False)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(email__icontains=q) |
                Q(city__icontains=q) |
                Q(state__icontains=q)
            )

        qs = qs.order_by('-registration_date', '-created_at', 'full_name')

        # Summary KPIs (always on full unfiltered table)
        total_customers = Customer.objects.count()
        active_customers = Customer.objects.filter(is_active=True).count()
        inactive_customers = Customer.objects.filter(is_active=False).count()

        paginator = StandardWarehousePagination()
        page = paginator.paginate_queryset(qs, request)

        def serialize_customer(c):
            return {
                'customer_id': c.customer_id,
                'full_name': c.full_name or 'Unknown',
                'email': c.email or '',
                'phone': str(c.phone) if c.phone else '',
                'gender': c.gender or '',
                'date_of_birth': c.date_of_birth or '',
                'city': c.city or '',
                'state': c.state or '',
                'country': c.country or '',
                'postal_code': str(c.postal_code) if c.postal_code else '',
                'registration_date': c.registration_date or c.created_at or '',
                'is_active': c.is_active if c.is_active is not None else True,
            }

        metrics = {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'inactive_customers': inactive_customers,
        }

        if page is not None:
            customers_data = [serialize_customer(c) for c in page]
            response = paginator.get_paginated_response(customers_data)
            response.data['metrics'] = metrics
            return response

        customers_data = [serialize_customer(c) for c in qs]
        return Response({'results': customers_data, 'metrics': metrics}, status=status.HTTP_200_OK)


class AdminCustomerDetailView(APIView):
    """
    GET /api/admin/customers/<customer_id>/
    Fetch a single customer record with order summary.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request, customer_id):
        try:
            c = Customer.objects.get(customer_id=customer_id)
        except Customer.DoesNotExist:
            return Response(
                {'detail': f'Customer "{customer_id}" not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Order summary for this customer
        customer_orders = Order.objects.filter(customer_id=customer_id)
        total_orders = customer_orders.count()
        total_spent = customer_orders.exclude(
            order_status__iexact='Cancelled'
        ).aggregate(total=Coalesce(Sum('total_amount'), 0.0))['total'] or 0.0

        recent_orders = []
        for o in customer_orders.order_by('-order_date', '-created_at')[:5]:
            recent_orders.append({
                'order_id': o.order_id,
                'order_date': o.order_date or '',
                'order_status': o.order_status or '',
                'total_amount': float(o.total_amount or 0),
            })

        return Response({
            'customer_id': c.customer_id,
            'full_name': c.full_name or 'Unknown',
            'email': c.email or '',
            'phone': str(c.phone) if c.phone else '',
            'gender': c.gender or '',
            'date_of_birth': c.date_of_birth or '',
            'city': c.city or '',
            'state': c.state or '',
            'country': c.country or '',
            'postal_code': str(c.postal_code) if c.postal_code else '',
            'registration_date': c.registration_date or c.created_at or '',
            'is_active': c.is_active if c.is_active is not None else True,
            'order_summary': {
                'total_orders': total_orders,
                'total_spent': round(float(total_spent), 2),
            },
            'recent_orders': recent_orders,
        }, status=status.HTTP_200_OK)
