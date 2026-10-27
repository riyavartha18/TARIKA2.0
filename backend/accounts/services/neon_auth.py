import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from accounts.models import Employee, EmployeeRole, Role, Warehouse


class NeonAuthService:
    STAFF_ROLE_MAP = {
        'admin': Role.ADMIN,
        'warehouse_manager': Role.WAREHOUSE_MANAGER,
        'delivery': Role.DELIVERY_PARTNER,
    }

    @staticmethod
    def _normalize_email(email):
        return str(email or '').strip().lower()

    @staticmethod
    def generate_token_pair(auth_user_id, email, role, warehouse_id=None):
        now = timezone.now()
        access_payload = {
            'sub': str(auth_user_id),
            'email': email,
            'role': role,
            'warehouse_id': warehouse_id,
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(days=7)).timestamp()),
            'aud': 'authenticated',
        }
        refresh_payload = {
            'sub': str(auth_user_id),
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(days=30)).timestamp()),
            'token_type': 'refresh',
        }
        secret = NeonAuthService._jwt_secret()
        return {
            'access_token': jwt.encode(access_payload, secret, algorithm='HS256'),
            'refresh_token': jwt.encode(refresh_payload, secret, algorithm='HS256'),
            'expires_in': 7 * 24 * 3600,
            'token_type': 'Bearer',
        }

    @staticmethod
    def _jwt_secret():
        return getattr(settings, 'AUTH_JWT_SECRET', None) or settings.SECRET_KEY

    @classmethod
    def verify_token(cls, token_string):
        try:
            return jwt.decode(
                token_string,
                cls._jwt_secret(),
                algorithms=['HS256'],
                audience='authenticated',
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationFailed("Token has expired. Please log in again.") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationFailed("Invalid authentication token.") from exc

    @classmethod
    def _create_django_user(cls, email, password, full_name=''):
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User(
                username=f'user_{uuid.uuid4().hex}',
                email=email,
                first_name=full_name[:150],
                is_active=True,
            )
        else:
            user.email = email
            user.first_name = full_name[:150]
            user.is_active = True
        user.set_password(password)
        user.save()
        return user

    @classmethod
    def register_customer(cls, email, password, full_name, phone=None, **extra_fields):
        email = cls._normalize_email(email)
        unsupported_fields = [
            name
            for name, value in (
                ('phone', phone),
                ('city', extra_fields.get('city')),
                ('state', extra_fields.get('state')),
            )
            if value not in (None, '')
        ]
        if unsupported_fields:
            raise ValidationError({
                "profile": (
                    "The Neon public.customers table does not have columns for "
                    f"{', '.join(unsupported_fields)}. Add those columns before collecting these details."
                )
            })
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "An account with this email address already exists."})

        auth_user_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT customer_id FROM public.customers WHERE LOWER(email) = LOWER(%s) LIMIT 1;",
                [email],
            )
            customer_row = cursor.fetchone()

        customer_id = customer_row[0] if customer_row else f'U{uuid.uuid4().hex[:10].upper()}'
        with transaction.atomic():
            cls._create_django_user(email, password, full_name)
            with connection.cursor() as cursor:
                if customer_row:
                    cursor.execute(
                        "UPDATE public.customers SET customer_name = %s WHERE customer_id = %s;",
                        [full_name, customer_id],
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO public.customers (customer_id, customer_name, email)
                        VALUES (%s, %s, %s);
                        """,
                        [customer_id, full_name, email],
                    )

        tokens = cls.generate_token_pair(auth_user_id, email, Role.CUSTOMER)
        return {
            'user': {
                'id': str(auth_user_id),
                'email': email,
                'full_name': full_name,
                'role': Role.CUSTOMER,
                'customer_id': customer_id,
            },
            'tokens': tokens,
        }

    @classmethod
    def verify_staff_credentials(cls, email, password):
        email = cls._normalize_email(email)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, email, role, is_active,
                       (password_hash = crypt(%s, password_hash)) AS password_ok
                FROM public.app_users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1;
                """,
                [password, email],
            )
            row = cursor.fetchone()

        if not row:
            raise AuthenticationFailed("Invalid email or password.")

        user_id, db_email, db_role, is_active, password_ok = row
        if not is_active:
            raise AuthenticationFailed("This account is inactive. Please contact the administrator.")
        if not password_ok:
            raise AuthenticationFailed("Invalid email or password.")

        role = cls.STAFF_ROLE_MAP.get(str(db_role).strip().lower())
        if not role:
            raise AuthenticationFailed("Unrecognized staff role.")

        return {'user_id': str(user_id), 'email': db_email, 'role': role, 'is_active': True}

    @classmethod
    def login(cls, email_or_username, password):
        email = cls._normalize_email(email_or_username)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM public.app_users WHERE LOWER(email) = LOWER(%s) LIMIT 1;",
                [email],
            )
            is_legacy_staff = cursor.fetchone() is not None

        if is_legacy_staff:
            staff = cls.verify_staff_credentials(email, password)
            tokens = cls.generate_token_pair(staff['user_id'], staff['email'], staff['role'])
            display_name = staff['email'].split('@')[0].replace('.', ' ').replace('_', ' ').title()
            return {
                'user': {
                    'id': staff['user_id'],
                    'email': staff['email'],
                    'full_name': display_name,
                    'role': staff['role'],
                    'warehouse_id': None,
                    'is_active': True,
                },
                'tokens': tokens,
            }

        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.check_password(password):
            raise AuthenticationFailed("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationFailed("This account is inactive.")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT customer_id, customer_name, email
                FROM public.customers
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1;
                """,
                [email],
            )
            customer = cursor.fetchone()
        if not customer:
            raise AuthenticationFailed("No customer profile is associated with this account.")

        profile_id, full_name, profile_email = customer
        role = Role.CUSTOMER
        warehouse_id = None
        auth_user_id = uuid.uuid4()
        phone = None

        tokens = cls.generate_token_pair(auth_user_id, profile_email or email, role, warehouse_id)
        return {
            'user': {
                'id': str(auth_user_id),
                'customer_id': profile_id,
                'email': profile_email or email,
                'full_name': full_name,
                'phone': phone,
                'role': role,
                'warehouse_id': warehouse_id,
            },
            'tokens': tokens,
        }

    @classmethod
    def admin_create_employee(cls, admin_user, email, password, full_name, role, warehouse_id=None, phone=None):
        del admin_user
        if role not in [EmployeeRole.WAREHOUSE_MANAGER, EmployeeRole.DELIVERY_PARTNER]:
            raise ValidationError({"role": f"Admin can only create WAREHOUSE_MANAGER or DELIVERY_PARTNER. Provided: {role}"})

        if role == EmployeeRole.WAREHOUSE_MANAGER:
            if not warehouse_id:
                raise ValidationError({"warehouse_id": "Warehouse ID is required when creating a Warehouse Manager."})
            if not Warehouse.objects.filter(warehouse_id=warehouse_id).exists():
                raise ValidationError({"warehouse_id": f"Warehouse with ID '{warehouse_id}' does not exist."})
        else:
            warehouse_id = None

        email = NeonAuthService._normalize_email(email)
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "An account with this email address already exists."})
        if Employee.objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "An employee with this email already exists."})
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM public.app_users WHERE LOWER(email) = LOWER(%s) LIMIT 1;",
                [email],
            )
            if cursor.fetchone():
                raise ValidationError({"email": "An account with this email address already exists."})

        auth_user_id = uuid.uuid4()
        now = timezone.now()
        with transaction.atomic():
            NeonAuthService._create_django_user(email, password, full_name)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.employees (
                        auth_user_id, full_name, email, phone, role, warehouse_id,
                        is_active, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                    RETURNING employee_id;
                    """,
                    [auth_user_id, full_name, email, phone, role, warehouse_id, now, now],
                )
                employee_id = cursor.fetchone()[0]

        return {
            'employee_id': employee_id,
            'auth_user_id': str(auth_user_id),
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'role': role,
            'warehouse_id': warehouse_id,
            'is_active': True,
        }

    @classmethod
    def _ensure_seed_employee(cls, email, password, full_name, phone, role, warehouse_id=None):
        email = cls._normalize_email(email)
        now = timezone.now()
        with transaction.atomic():
            employee = Employee.objects.filter(email__iexact=email).first()
            if employee:
                auth_user_id = employee.auth_user_id or uuid.uuid4()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE public.employees
                        SET auth_user_id = %s, full_name = %s, phone = %s, role = %s,
                            warehouse_id = %s, is_active = TRUE, updated_at = %s
                        WHERE employee_id = %s;
                        """,
                        [auth_user_id, full_name, phone, role, warehouse_id, now, employee.employee_id],
                    )
                employee_id = employee.employee_id
            else:
                auth_user_id = uuid.uuid4()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO public.employees (
                            auth_user_id, full_name, email, phone, role, warehouse_id,
                            is_active, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                        RETURNING employee_id;
                        """,
                        [auth_user_id, full_name, email, phone, role, warehouse_id, now, now],
                    )
                    employee_id = cursor.fetchone()[0]

            cls._create_django_user(email, password, full_name)

        return Employee.objects.get(employee_id=employee_id)

    @classmethod
    def seed_initial_admin(cls, email, password, full_name="System Administrator", phone=None):
        email = cls._normalize_email(email)
        existing = Employee.objects.filter(email__iexact=email, role=EmployeeRole.ADMIN).first()
        if existing:
            return existing, False
        employee = cls._ensure_seed_employee(email, password, full_name, phone, EmployeeRole.ADMIN)
        return employee, True

    @classmethod
    def seed_initial_warehouse_manager(
        cls,
        email="warehouse.manager@iras.com",
        password="Warehouse@123",
        full_name="Warehouse Manager",
        phone="9876543210",
    ):
        email = cls._normalize_email(email)
        with connection.cursor() as cursor:
            cursor.execute("SELECT warehouse_id FROM public.warehouses LIMIT 1;")
            row = cursor.fetchone()
        warehouse_id = row[0] if row else None
        employee = cls._ensure_seed_employee(
            email, password, full_name, phone, EmployeeRole.WAREHOUSE_MANAGER, warehouse_id
        )
        return employee, True
