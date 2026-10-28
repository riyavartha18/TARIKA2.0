from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from django.db import connection, transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.permissions import IsAuthenticatedUser, IsAdmin
from admin.serializers import (
    AdminStaffCreateSerializer,
    AdminStaffUpdateSerializer,
    normalize_role,
    ALLOWED_ROLES,
)

import uuid
import datetime

from accounts.models import Employee, Customer, Role, Warehouse, AppUser
from catalog.models import Product, Inventory, Category, Manufacturer
from catalog.cache import bump_catalog_version
from catalog.serializers import CATEGORY_IMAGE_MAPPING
from warehouse.models import Order, Delivery, Return
from warehouse.services import WarehouseService
from warehouse.serializers import WarehouseOrderSerializer, WarehouseOrderDetailSerializer
from warehouse.views import StandardWarehousePagination


ROLE_LABELS = {
    'admin': 'Admin',
    'warehouse_manager': 'Warehouse Manager',
    'delivery': 'Delivery Partner',
}


def _serialize_staff(row):
    """row: dict of user_id/email/role/is_active/created_at/updated_at.

    password_hash is deliberately never part of ``row`` and never returned.
    """
    role = str(row.get('role') or '')
    created = row.get('created_at')
    updated = row.get('updated_at')
    return {
        'user_id': row.get('user_id'),
        'email': row.get('email'),
        'role': role,
        'role_label': ROLE_LABELS.get(role.lower(), role),
        'is_active': bool(row.get('is_active')),
        'created_at': created.isoformat() if hasattr(created, 'isoformat') else created,
        'updated_at': updated.isoformat() if hasattr(updated, 'isoformat') else updated,
    }


def _active_admin_count():
    return AppUser.objects.filter(role='admin', is_active=True).count()


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class AdminCreateStaffView(APIView):
    """
    Admin-only endpoint that creates a staff account in the real
    public.app_users table. Role is one of: admin / warehouse_manager /
    delivery.
    
    Customers, Warehouse Managers, and Delivery Partners cannot access this endpoint (403 Forbidden).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def post(self, request):
        serializer = AdminStaffCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        role = serializer.validated_data['role']

        # Reject duplicate accounts (case-insensitive email).
        if AppUser.objects.filter(email__iexact=email).exists():
            return Response(
                {'errors': {'email': ['A staff account with this email already exists.']}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Password is stored ONLY as a pgcrypto bcrypt hash computed inside
        # PostgreSQL; the plaintext never leaves this statement and the hash is
        # never returned.
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.app_users
                        (email, password_hash, role, is_active, created_at, updated_at)
                    VALUES (%s, crypt(%s, gen_salt('bf', 12)), %s, TRUE, now(), now())
                    RETURNING user_id, email, role, is_active, created_at, updated_at;
                    """,
                    [email, password, role],
                )
                cols = [c.name for c in cursor.description]
                row = dict(zip(cols, cursor.fetchone()))
        except Exception as exc:  # noqa: BLE001 - never report success on failure
            return Response({'detail': f'Could not create staff account: {type(exc).__name__}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': f'Staff account ({ROLE_LABELS.get(role, role)}) created successfully.',
            'staff': _serialize_staff(row),
        }, status=status.HTTP_201_CREATED)


class AdminDashboardStatsView(APIView):
    """
    Admin-only system overview.

    Catalog and stock KPIs are computed from the real ``public.products`` schema
    (``main_category`` for catalog, ``available_quantity`` for stock). Sections
    that would require tables/columns absent from the inspected database —
    order-status breakdowns, revenue, warehouse and delivery/return alerts (the
    ``warehouses``, ``deliveries``, ``returns`` tables and ``orders.order_status``
    / ``orders.total_amount`` columns do not exist) — are reported as
    ``None`` / empty and listed under ``not_available`` instead of being
    fabricated. The endpoint therefore always answers, and never invents data.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        active_products = Product.objects.filter(is_active=True)

        # ---- KPIs (schema-backed) --------------------------------------
        total_customers = Customer.objects.count()
        total_products = active_products.count()

        # Order count is available (the ``orders`` table exists); the richer
        # order-status / revenue breakdown is not, so those stay unavailable.
        try:
            total_orders = Order.objects.count()
        except Exception:  # pragma: no cover - defensive
            total_orders = None

        # ---- Catalog / stock snapshot from products --------------------
        from django.db.models import Sum as _Sum
        stock_total = active_products.aggregate(
            total=_Sum('available_quantity')
        )['total']
        total_stock_units = int(stock_total) if stock_total is not None else 0
        low_stock_count = active_products.filter(
            available_quantity__gt=0, available_quantity__lte=5
        ).count()
        in_stock_count = active_products.filter(available_quantity__gt=0).count()
        out_of_stock_count = active_products.filter(
            Q(available_quantity__lte=0) | Q(available_quantity__isnull=True)
        ).count()

        not_available = [
            'order_status_breakdown',
            'total_revenue',
            'recent_orders',
            'warehouses',
            'pending_returns',
            'pending_deliveries',
            'recent_activity',
        ]

        return Response({
            'kpis': {
                'total_customers': total_customers,
                'total_orders': total_orders,
                'total_products': total_products,
                'total_revenue': None,
            },
            'order_overview': {
                'total': total_orders,
                'pending': None,
                'processing': None,
                'delivered': None,
                'cancelled': None,
            },
            'recent_orders': [],
            'inventory_snapshot': {
                'source': 'products.available_quantity',
                'total_warehouses': None,
                'total_stock_units': total_stock_units,
                'low_stock_count': low_stock_count,
                'in_stock_products': in_stock_count,
                'out_of_stock_products': out_of_stock_count,
                'warehouses': [],
            },
            'operational_alerts': {
                'pending_returns': None,
                'pending_deliveries': None,
                'low_stock_products': low_stock_count,
                'cancelled_orders': None,
            },
            'recent_activity': [],
            'not_available': not_available,
            'note': (
                'Order-status, revenue, warehouse and delivery/return metrics '
                'are unavailable because those tables/columns are not present in '
                'the connected database. Catalog and stock metrics are computed '
                'from public.products.'
            ),
        }, status=status.HTTP_200_OK)


class AdminStaffListView(APIView):
    """
    Admin-only list of staff from the real public.app_users table.

    Supports search (email/role), role + status filters and server-side
    pagination. Only the non-secret columns are read, so password_hash is never
    fetched or returned.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def get(self, request):
        search = (request.query_params.get('search') or '').strip()
        role = (request.query_params.get('role') or '').strip()
        status_param = (request.query_params.get('status') or '').strip()

        qs = AppUser.objects.all()

        if role and role.upper() != 'ALL':
            canon = normalize_role(role)
            qs = qs.filter(role=canon) if canon else qs.none()

        if status_param and status_param.upper() != 'ALL':
            if status_param.lower() in ('active', 'true', '1'):
                qs = qs.filter(is_active=True)
            elif status_param.lower() in ('inactive', 'false', '0'):
                qs = qs.filter(is_active=False)

        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(role__icontains=search))

        try:
            page = max(1, int(request.query_params.get('page', 1) or 1))
            page_size = int(request.query_params.get('page_size', 25) or 25)
        except (TypeError, ValueError):
            page, page_size = 1, 25
        page_size = min(max(page_size, 1), 200)

        total = qs.count()
        start = (page - 1) * page_size
        rows = list(
            qs.order_by('-created_at', 'user_id')
            .values('user_id', 'email', 'role', 'is_active', 'created_at', 'updated_at')[start:start + page_size]
        )

        summary = {
            'total_staff': AppUser.objects.count(),
            'admins': AppUser.objects.filter(role='admin').count(),
            'warehouse_managers': AppUser.objects.filter(role='warehouse_manager').count(),
            'delivery_partners': AppUser.objects.filter(role='delivery').count(),
            'active_staff': AppUser.objects.filter(is_active=True).count(),
        }

        return Response({
            'summary': summary,
            'roles': list(ALLOWED_ROLES),
            'staff': [_serialize_staff(r) for r in rows],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size else 1,
            },
        }, status=status.HTTP_200_OK)


class AdminStaffToggleStatusView(APIView):
    """
    Activate / deactivate a staff account in public.app_users.

    Guards: an admin cannot deactivate their own account, and the last active
    administrator can never be deactivated (prevents locking everyone out).
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def patch(self, request, user_id):
        target = AppUser.objects.defer('password_hash').filter(user_id=user_id).first()
        if not target:
            return Response({'detail': 'Staff member not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        requested = request.data.get('is_active')
        new_active = (not target.is_active) if requested is None else bool(requested)

        if not new_active:
            if str(user_id) == str(getattr(request.user, 'auth_user_id', '')):
                return Response({'detail': 'You cannot deactivate your own account.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if str(target.role).lower() == 'admin' and _active_admin_count() <= 1:
                return Response({'detail': 'Cannot deactivate the last active administrator.'},
                                status=status.HTTP_400_BAD_REQUEST)

        target.is_active = new_active
        target.updated_at = _utcnow()
        target.save(update_fields=['is_active', 'updated_at'])

        return Response({
            'message': f'Staff member is now {"Active" if new_active else "Inactive"}.',
            'staff': _serialize_staff({
                'user_id': target.user_id, 'email': target.email, 'role': target.role,
                'is_active': target.is_active, 'created_at': target.created_at,
                'updated_at': target.updated_at,
            }),
        }, status=status.HTTP_200_OK)


class AdminStaffUpdateView(APIView):
    """
    Edit a staff account (role, active flag, optional password reset) in
    public.app_users. Every accepted change is persisted atomically; password
    is rehashed with pgcrypto and never returned. Self-demotion and removal of
    the last active administrator are refused.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    def put(self, request, user_id):
        serializer = AdminStaffUpdateSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        target = AppUser.objects.defer('password_hash').filter(user_id=user_id).first()
        if not target:
            return Response({'detail': 'Staff member not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        data = serializer.validated_data
        new_role = data.get('role', target.role)
        new_active = data.get('is_active', target.is_active)
        was_admin = str(target.role).lower() == 'admin'
        stops_being_admin = was_admin and (str(new_role).lower() != 'admin' or not new_active)

        if stops_being_admin and _active_admin_count() <= 1:
            return Response(
                {'detail': 'Cannot demote or deactivate the last active administrator.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not new_active and str(user_id) == str(getattr(request.user, 'auth_user_id', '')):
            return Response({'detail': 'You cannot deactivate your own account.'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            target.role = new_role
            target.is_active = bool(new_active)
            target.updated_at = _utcnow()
            target.save(update_fields=['role', 'is_active', 'updated_at'])

            if data.get('password'):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.app_users SET password_hash = crypt(%s, gen_salt('bf', 12)) "
                        "WHERE user_id = %s",
                        [data['password'], target.user_id],
                    )

        return Response({
            'message': 'Staff account updated.',
            'staff': _serialize_staff({
                'user_id': target.user_id, 'email': target.email, 'role': target.role,
                'is_active': target.is_active, 'created_at': target.created_at,
                'updated_at': target.updated_at,
            }),
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
    Admin-only product catalog overview, read straight from the real
    ``public.products`` schema.

    Only columns that actually exist are used:
      * catalog grouping  -> ``main_category`` (there is no ``categories`` table)
      * stock             -> ``available_quantity`` (there is no ``inventory`` table)
      * price             -> ``discount_price`` / ``actual_price`` (TEXT)

    Legacy fields that the old form assumed (``sku``, ``description``, ``color``,
    ``size``, ``material``, ``gender``, per-warehouse ``inventory``) are NOT part
    of this schema, so they are intentionally absent rather than fabricated.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    LIST_LIMIT = 500

    def get(self, request):
        search = (request.query_params.get('search') or '').strip()
        category_filter = (request.query_params.get('category') or '').strip()
        stock_filter = (request.query_params.get('stock_status') or '').strip().upper()

        active_qs = Product.objects.filter(is_active=True)

        total_products = active_qs.count()

        # Distinct catalog categories come from products.main_category directly.
        category_names = list(
            active_qs
            .exclude(main_category__isnull=True)
            .exclude(main_category='')
            .values_list('main_category', flat=True)
            .distinct()
            .order_by('main_category')
        )
        categories_list = [
            {'category_id': name, 'category_name': name} for name in category_names
        ]

        in_stock_products = active_qs.filter(available_quantity__gt=0).count()
        low_stock_products = active_qs.filter(
            available_quantity__gt=0, available_quantity__lte=5
        ).count()

        products_qs = active_qs
        if search:
            products_qs = products_qs.filter(
                Q(product_name__icontains=search) |
                Q(main_category__icontains=search) |
                Q(sub_category__icontains=search)
            )
        if category_filter and category_filter.upper() != 'ALL':
            products_qs = products_qs.filter(main_category__iexact=category_filter)
        if stock_filter == 'IN_STOCK':
            products_qs = products_qs.filter(available_quantity__gt=0)
        elif stock_filter == 'LOW_STOCK':
            products_qs = products_qs.filter(
                available_quantity__gt=0, available_quantity__lte=5
            )
        elif stock_filter == 'OUT_OF_STOCK':
            products_qs = products_qs.filter(
                Q(available_quantity__lte=0) | Q(available_quantity__isnull=True)
            )

        products_list = []
        for p in products_qs.order_by('product_name', 'product_id')[:self.LIST_LIMIT]:
            qty = p.available_quantity
            cat_name = (p.main_category or '').strip()
            img_url = p.image or CATEGORY_IMAGE_MAPPING.get(cat_name.lower(), None)
            products_list.append({
                'product_id': p.product_id,
                'product_name': p.product_name or 'Unnamed Product',
                'main_category': p.main_category,
                'sub_category': p.sub_category,
                'category_name': cat_name or 'Uncategorized',
                'image': img_url,
                'link': p.link,
                'discount_price': p.discount_price,
                'selling_price': p.selling_price,
                'base_price': p.base_price,
                'actual_price': p.actual_price_text,
                'available_quantity': qty,
                'total_stock': (int(qty) if qty is not None else None),
                'in_stock': (qty or 0) > 0,
                'is_low_stock': (qty is not None and 0 < qty <= 5),
                'is_active': p.is_active,
            })

        return Response({
            'metrics': {
                'total_products': total_products,
                'total_categories': len(categories_list),
                'in_stock_products': in_stock_products,
                'low_stock_products': low_stock_products,
            },
            'categories': categories_list,
            'products': products_list,
            'truncated': products_qs.count() > self.LIST_LIMIT,
        }, status=status.HTTP_200_OK)


class AdminProductCreateView(APIView):
    """
    Admin-only endpoint to create a new catalog product directly in the real
    ``public.products`` table. Only supported columns are written; a product_key
    is generated (unique) and stock is seeded from ``available_quantity``. There
    is no ``inventory`` / ``categories`` table, so no related rows are created.
    """
    permission_classes = [IsAuthenticatedUser, IsAdmin]

    SUPPORTED_FIELDS = {
        'product_name', 'main_category', 'sub_category', 'image', 'link',
        'discount_price', 'actual_price', 'available_quantity',
    }

    def _generate_product_key(self):
        for _ in range(5):
            candidate = f"P{uuid.uuid4().hex[:12].upper()}"
            if not Product.objects.filter(product_id=candidate).exists():
                return candidate
        return f"P{uuid.uuid4().hex}"

    def post(self, request):
        data = request.data or {}

        # Reject unknown fields instead of silently dropping them.
        unknown = sorted(set(data.keys()) - self.SUPPORTED_FIELDS - {'product_key'})
        if unknown:
            return Response(
                {'errors': {f: ['This field is not supported by the product schema.']
                            for f in unknown}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = {}
        product_name = (data.get('product_name') or '').strip()
        main_category = (data.get('main_category') or '').strip()

        if not product_name or len(product_name) < 2:
            errors['product_name'] = ['Product name must be at least 2 characters.']
        if not main_category:
            errors['main_category'] = ['A main category is required.']

        def _whole_non_negative(field, label, required=False, default=None):
            raw = data.get(field)
            if raw is None or raw == '':
                if required:
                    errors[field] = [f'{label} is required.']
                return default
            try:
                val = float(raw)
            except (TypeError, ValueError):
                errors[field] = [f'{label} must be a number.']
                return default
            if val < 0:
                errors[field] = [f'{label} cannot be negative.']
                return default
            if val != int(val):
                errors[field] = [f'{label} must be a whole number.']
                return default
            return val

        discount_price = _whole_non_negative('discount_price', 'Selling price', required=True)
        available_quantity = _whole_non_negative(
            'available_quantity', 'Available quantity', default=0.0
        )

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        product_key = (data.get('product_key') or '').strip() or self._generate_product_key()
        if Product.objects.filter(product_id=product_key).exists():
            return Response(
                {'errors': {'product_key': ['A product with this key already exists.']}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actual_price_raw = data.get('actual_price')
        product = Product.objects.create(
            product_id=product_key,
            product_name=product_name,
            main_category=main_category,
            sub_category=(data.get('sub_category') or '').strip() or None,
            image=(data.get('image') or '').strip() or None,
            link=(data.get('link') or '').strip() or None,
            discount_price=discount_price,
            actual_price_text=(str(actual_price_raw).strip() if actual_price_raw not in (None, '') else None),
            available_quantity=available_quantity,
            is_active=True,
        )

        # A brand-new catalog item changes every cached listing / category rail.
        bump_catalog_version()

        return Response({
            'message': 'Product created successfully.',
            'product': {
                'product_id': product.product_id,
                'product_name': product.product_name,
                'main_category': product.main_category,
                'sub_category': product.sub_category,
                'category_name': product.main_category,
                'image': product.image,
                'link': product.link,
                'discount_price': product.discount_price,
                'selling_price': product.selling_price,
                'base_price': product.base_price,
                'actual_price': product.actual_price_text,
                'available_quantity': product.available_quantity,
                'total_stock': (int(product.available_quantity)
                                if product.available_quantity is not None else None),
                'is_active': product.is_active,
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
