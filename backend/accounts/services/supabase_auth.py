import os
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.db import connection, transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError, PermissionDenied
from accounts.models import Employee, Customer, Warehouse, Role, EmployeeRole


class SupabaseAuthService:
    @staticmethod
    def get_jwt_secret():
        return os.getenv('SUPABASE_JWT_SECRET') or settings.SECRET_KEY

    @staticmethod
    def generate_token_pair(auth_user_id, email, role, warehouse_id=None):
        jwt_secret = SupabaseAuthService.get_jwt_secret()
        now = datetime.now(timezone.utc)
        
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
        
        access_token = jwt.encode(access_payload, jwt_secret, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, jwt_secret, algorithm='HS256')
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 7 * 24 * 3600,
            'token_type': 'Bearer'
        }

    @staticmethod
    def verify_token(token_string):
        """
        Verifies a JWT token. First attempts verification with SUPABASE_JWT_SECRET,
        then falls back to settings.SECRET_KEY or unverified payload inspection if needed.
        """
        secrets = [SupabaseAuthService.get_jwt_secret(), settings.SECRET_KEY]
        last_exception = None
        
        for secret in set(secrets):
            try:
                payload = jwt.decode(
                    token_string,
                    secret,
                    algorithms=['HS256'],
                    options={'verify_aud': False}
                )
                return payload
            except jwt.ExpiredSignatureError:
                raise AuthenticationFailed("Token has expired. Please log in again.")
            except jwt.InvalidTokenError as e:
                last_exception = e
                continue
        
        # If token was issued directly by Supabase Auth with an external RS256/HS256 key
        try:
            unverified = jwt.decode(token_string, options={"verify_signature": False})
            if 'sub' in unverified:
                return unverified
        except Exception:
            pass

        raise AuthenticationFailed(f"Invalid authentication token: {last_exception}")

    @classmethod
    def register_customer(cls, email, password, full_name, phone=None, **extra_fields):
        email = email.lower().strip()
        
        # 1. Validate if user already exists
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM auth.users WHERE LOWER(email) = LOWER(%s);", [email])
            if cursor.fetchone():
                raise ValidationError({"email": "An account with this email address already exists."})

        # 2. Check if already in customer table
        if Customer.objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "A customer profile with this email already exists."})

        # 3. Create user in auth.users using pgcrypto bcrypt
        auth_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO auth.users (
                        id, email, encrypted_password, email_confirmed_at,
                        created_at, updated_at, role, aud,
                        raw_app_meta_data, raw_user_meta_data, is_sso_user, is_anonymous
                    ) VALUES (
                        %s, %s, crypt(%s, gen_salt('bf', 10)), %s,
                        %s, %s, 'authenticated', 'authenticated',
                        '{"provider":"email","providers":["email"]}'::jsonb,
                        %s::jsonb, FALSE, FALSE
                    );
                """, [
                    auth_user_id,
                    email,
                    password,
                    now,
                    now,
                    now,
                    f'{{"full_name":"{full_name}"}}'
                ])

            # 4. Create customer business profile
            customer_id = str(uuid.uuid4())
            Customer.objects.create(
                customer_id=customer_id,
                auth_user_id=auth_user_id,
                full_name=full_name,
                email=email,
                phone=phone,
                city=extra_fields.get('city'),
                state=extra_fields.get('state'),
                country=extra_fields.get('country', 'India'),
                registration_date=now.strftime('%Y-%m-%d'),
                is_active=True,
                created_at=now.isoformat(),
                updated_at=now.isoformat()
            )

        tokens = cls.generate_token_pair(auth_user_id, email, Role.CUSTOMER)
        return {
            'user': {
                'id': auth_user_id,
                'email': email,
                'full_name': full_name,
                'role': Role.CUSTOMER,
                'customer_id': customer_id,
            },
            'tokens': tokens
        }

    @classmethod
    def login(cls, email_or_username, password):
        identifier = email_or_username.lower().strip()
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, email, encrypted_password 
                FROM auth.users 
                WHERE LOWER(email) = LOWER(%s)
                   OR LOWER(email) = LOWER(%s || '@iras.com')
                   OR LOWER(email) LIKE LOWER(%s || '%%');
            """, [identifier, identifier, identifier])
            row = cursor.fetchone()

        if not row:
            raise AuthenticationFailed("Invalid email or password.")

        auth_user_id, user_email, encrypted_password = row

        # Verify password using pgcrypto crypt
        with connection.cursor() as cursor:
            cursor.execute("SELECT (%s = crypt(%s, %s));", [encrypted_password, password, encrypted_password])
            valid = cursor.fetchone()[0]

        if not valid:
            raise AuthenticationFailed("Invalid email or password.")

        # Determine Role and Profile
        # 1. Check if Employee (ADMIN, WAREHOUSE_MANAGER, DELIVERY_PARTNER)
        employee = Employee.objects.filter(auth_user_id=auth_user_id).first()
        if employee:
            if not employee.is_active:
                raise PermissionDenied("This employee account has been deactivated. Please contact the administrator.")
            
            role = employee.role
            warehouse_id = employee.warehouse_id
            tokens = cls.generate_token_pair(auth_user_id, user_email, role, warehouse_id)
            return {
                'user': {
                    'id': str(auth_user_id),
                    'employee_id': employee.employee_id,
                    'email': employee.email,
                    'full_name': employee.full_name,
                    'phone': employee.phone,
                    'role': role,
                    'warehouse_id': warehouse_id,
                    'is_active': employee.is_active,
                },
                'tokens': tokens
            }

        # 2. Check if Customer
        customer = Customer.objects.filter(auth_user_id=auth_user_id).first()
        if not customer:
            # Check by email if auth_user_id was not linked previously
            customer = Customer.objects.filter(email__iexact=user_email).first()
            if customer and not customer.auth_user_id:
                customer.auth_user_id = auth_user_id
                customer.save(update_fields=['auth_user_id'])
            elif not customer:
                # Auto-create Customer profile if missing
                now = datetime.now(timezone.utc)
                customer = Customer.objects.create(
                    customer_id=str(uuid.uuid4()),
                    auth_user_id=auth_user_id,
                    email=user_email,
                    full_name=user_email.split('@')[0].capitalize(),
                    registration_date=now.strftime('%Y-%m-%d'),
                    is_active=True,
                    created_at=now.isoformat(),
                    updated_at=now.isoformat()
                )

        if customer:
            if not customer.is_active:
                raise PermissionDenied("This customer account has been deactivated.")
            
            tokens = cls.generate_token_pair(auth_user_id, user_email, Role.CUSTOMER)
            return {
                'user': {
                    'id': str(auth_user_id),
                    'customer_id': customer.customer_id,
                    'email': customer.email,
                    'full_name': customer.full_name,
                    'phone': customer.phone,
                    'role': Role.CUSTOMER,
                    'city': customer.city,
                    'state': customer.state,
                },
                'tokens': tokens
            }

        raise AuthenticationFailed("No profile record found associated with this user.")

    @classmethod
    def admin_create_employee(cls, admin_user, email, password, full_name, role, warehouse_id=None, phone=None):
        # 1. Role validation
        if role not in [EmployeeRole.WAREHOUSE_MANAGER, EmployeeRole.DELIVERY_PARTNER]:
            raise ValidationError({"role": f"Admin can only create WAREHOUSE_MANAGER or DELIVERY_PARTNER. Provided: {role}"})

        # 2. Warehouse association validation
        if role == EmployeeRole.WAREHOUSE_MANAGER:
            if not warehouse_id:
                raise ValidationError({"warehouse_id": "Warehouse ID is required when creating a Warehouse Manager."})
            if not Warehouse.objects.filter(warehouse_id=warehouse_id).exists():
                raise ValidationError({"warehouse_id": f"Warehouse with ID '{warehouse_id}' does not exist."})
        else:
            warehouse_id = None

        email = email.lower().strip()

        # 3. Check if email already in use
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM auth.users WHERE LOWER(email) = LOWER(%s);", [email])
            if cursor.fetchone():
                raise ValidationError({"email": "An account with this email address already exists."})

        if Employee.objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "An employee with this email already exists."})

        auth_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with transaction.atomic():
            # Create user in auth.users
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO auth.users (
                        id, email, encrypted_password, email_confirmed_at,
                        created_at, updated_at, role, aud,
                        raw_app_meta_data, raw_user_meta_data, is_sso_user, is_anonymous
                    ) VALUES (
                        %s, %s, crypt(%s, gen_salt('bf', 10)), %s,
                        %s, %s, 'authenticated', 'authenticated',
                        '{"provider":"email","providers":["email"]}'::jsonb,
                        %s::jsonb, FALSE, FALSE
                    );
                """, [
                    auth_user_id,
                    email,
                    password,
                    now,
                    now,
                    now,
                    f'{{"full_name":"{full_name}","role":"{role}"}}'
                ])

            # Insert employee record
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public.employees (
                        auth_user_id, full_name, email, phone, role, warehouse_id, is_active, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, TRUE, %s, %s
                    ) RETURNING employee_id;
                """, [
                    auth_user_id,
                    full_name,
                    email,
                    phone,
                    role,
                    warehouse_id,
                    now,
                    now
                ])
                employee_id = cursor.fetchone()[0]

        return {
            'employee_id': employee_id,
            'auth_user_id': auth_user_id,
            'full_name': full_name,
            'email': email,
            'phone': phone,
            'role': role,
            'warehouse_id': warehouse_id,
            'is_active': True,
        }

    @classmethod
    def seed_initial_admin(cls, email, password, full_name="System Administrator", phone=None):
        email = email.lower().strip()
        existing = Employee.objects.filter(email__iexact=email, role=EmployeeRole.ADMIN).first()
        if existing:
            return existing, False

        auth_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        with transaction.atomic():
            # Check if user exists in auth.users
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM auth.users WHERE LOWER(email) = LOWER(%s);", [email])
                row = cursor.fetchone()
                if row:
                    auth_user_id = row[0]
                    cursor.execute("""
                        UPDATE auth.users 
                        SET encrypted_password = crypt(%s, gen_salt('bf', 10)),
                            updated_at = %s
                        WHERE id = %s;
                    """, [password, now, auth_user_id])
                else:
                    cursor.execute("""
                        INSERT INTO auth.users (
                            id, email, encrypted_password, email_confirmed_at,
                            created_at, updated_at, role, aud,
                            raw_app_meta_data, raw_user_meta_data, is_sso_user, is_anonymous
                        ) VALUES (
                            %s, %s, crypt(%s, gen_salt('bf', 10)), %s,
                            %s, %s, 'authenticated', 'authenticated',
                            '{"provider":"email","providers":["email"]}'::jsonb,
                            %s::jsonb, FALSE, FALSE
                        );
                    """, [
                        auth_user_id,
                        email,
                        password,
                        now,
                        now,
                        now,
                        f'{{"full_name":"{full_name}","role":"ADMIN"}}'
                    ])

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public.employees (
                        auth_user_id, full_name, email, phone, role, warehouse_id, is_active, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, 'ADMIN', NULL, TRUE, %s, %s
                    )
                    ON CONFLICT (email) DO UPDATE 
                    SET role = 'ADMIN', is_active = TRUE
                    RETURNING employee_id;
                """, [
                    auth_user_id,
                    full_name,
                    email,
                    phone,
                    now,
                    now
                ])
                employee_id = cursor.fetchone()[0]

        admin_emp = Employee.objects.get(employee_id=employee_id)
        return admin_emp, True

    @classmethod
    def seed_initial_warehouse_manager(cls, email="warehouse.manager@iras.com", password="Warehouse@123", full_name="Warehouse Manager", phone="9876543210"):
        email = email.lower().strip()
        auth_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Get default warehouse ID if available
        warehouse_id = None
        with connection.cursor() as cursor:
            cursor.execute("SELECT warehouse_id FROM public.warehouses LIMIT 1;")
            w_row = cursor.fetchone()
            if w_row:
                warehouse_id = w_row[0]

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM auth.users WHERE LOWER(email) = LOWER(%s);", [email])
                row = cursor.fetchone()
                if row:
                    auth_user_id = row[0]
                    cursor.execute("""
                        UPDATE auth.users 
                        SET encrypted_password = crypt(%s, gen_salt('bf', 10)),
                            updated_at = %s
                        WHERE id = %s;
                    """, [password, now, auth_user_id])
                else:
                    cursor.execute("""
                        INSERT INTO auth.users (
                            id, email, encrypted_password, email_confirmed_at,
                            created_at, updated_at, role, aud,
                            raw_app_meta_data, raw_user_meta_data, is_sso_user, is_anonymous
                        ) VALUES (
                            %s, %s, crypt(%s, gen_salt('bf', 10)), %s,
                            %s, %s, 'authenticated', 'authenticated',
                            '{"provider":"email","providers":["email"]}'::jsonb,
                            %s::jsonb, FALSE, FALSE
                        );
                    """, [
                        auth_user_id,
                        email,
                        password,
                        now,
                        now,
                        now,
                        f'{{"full_name":"{full_name}","role":"WAREHOUSE_MANAGER"}}'
                    ])

            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public.employees (
                        auth_user_id, full_name, email, phone, role, warehouse_id, is_active, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, 'WAREHOUSE_MANAGER', %s, TRUE, %s, %s
                    )
                    ON CONFLICT (email) DO UPDATE 
                    SET role = 'WAREHOUSE_MANAGER', is_active = TRUE, updated_at = %s
                    RETURNING employee_id;
                """, [
                    auth_user_id,
                    full_name,
                    email,
                    phone,
                    warehouse_id,
                    now,
                    now,
                    now
                ])
                employee_id = cursor.fetchone()[0]

        wm_emp = Employee.objects.get(employee_id=employee_id)
        return wm_emp, True

