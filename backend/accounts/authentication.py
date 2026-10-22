from types import SimpleNamespace
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from django.db import connection
from accounts.models import Role
from accounts.services.supabase_auth import SupabaseAuthService


class AuthenticatedUser:
    """
    Lightweight user object attached to request.user representing
    an authenticated identity from Supabase Auth + IRAS profile.
    """
    def __init__(self, auth_user_id, email, role, profile=None, warehouse_id=None, is_active=True):
        self.auth_user_id = str(auth_user_id)
        self.id = self.auth_user_id
        self.pk = self.auth_user_id
        self.email = email
        self.role = role
        self.profile = profile
        self.warehouse_id = warehouse_id
        self.is_active = is_active
        self.is_authenticated = True
        self.is_anonymous = False

    @property
    def is_staff(self):
        return self.role in [Role.ADMIN, Role.WAREHOUSE_MANAGER, Role.DELIVERY_PARTNER]

    @property
    def is_superuser(self):
        return self.role == Role.ADMIN

    def __str__(self):
        return f"{self.email} ({self.role})"


class SupabaseAuthentication(authentication.BaseAuthentication):
    """
    DRF Authentication class that validates Supabase JWT Bearer tokens
    and attaches an AuthenticatedUser instance with trusted role and
    warehouse assignment to request.user.
    """
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None

        raw_token = parts[1]
        payload = SupabaseAuthService.verify_token(raw_token)

        auth_user_id = payload.get('sub')
        if not auth_user_id:
            raise AuthenticationFailed("Token payload missing subject ('sub').")

        # ---- Staff: the JWT subject is the numeric public.app_users.user_id ----
        # The role is always re-read from the database here; the role claim inside
        # the token is never trusted for authorization.
        if str(auth_user_id).isdigit():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT email, role, is_active FROM public.app_users WHERE user_id = %s LIMIT 1;",
                    [auth_user_id],
                )
                row = cursor.fetchone()
            if row:
                email, db_role, is_active = row
                if not is_active:
                    raise AuthenticationFailed("This account is inactive.")
                role = SupabaseAuthService.STAFF_ROLE_MAP.get(str(db_role).strip().lower())
                if not role:
                    raise AuthenticationFailed("Unrecognized staff role.")
                display_name = str(email or '').split('@')[0].replace('.', ' ').replace('_', ' ').title()
                profile = SimpleNamespace(
                    employee_id=str(auth_user_id),
                    email=email,
                    full_name=display_name,
                    role=role,
                    is_active=is_active,
                )
                user = AuthenticatedUser(
                    auth_user_id=auth_user_id,
                    email=email,
                    role=role,
                    profile=profile,
                    warehouse_id=None,
                    is_active=is_active,
                )
                request.role = user.role
                request.warehouse_id = None
                return (user, raw_token)

        # ---- Customer: the JWT subject is the Supabase Auth (auth.users) UUID ----
        email_claim = payload.get('email')
        if not email_claim:
            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM auth.users WHERE id = %s LIMIT 1;", [auth_user_id])
                r = cursor.fetchone()
            email_claim = r[0] if r else None

        customer = None
        if email_claim:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT customer_id, customer_name, email, phone FROM public.customers WHERE LOWER(email) = LOWER(%s) LIMIT 1;",
                    [email_claim],
                )
                customer = cursor.fetchone()

        if customer:
            customer_id, customer_name, cust_email, phone = customer
            profile = SimpleNamespace(
                customer_id=customer_id,
                full_name=customer_name,
                name=customer_name,
                email=cust_email,
                phone=phone,
                is_active=True,
            )
            user = AuthenticatedUser(
                auth_user_id=auth_user_id,
                email=cust_email,
                role=Role.CUSTOMER,
                profile=profile,
                warehouse_id=None,
                is_active=True,
            )
            request.role = user.role
            request.warehouse_id = None
            return (user, raw_token)

        raise AuthenticationFailed("No profile record found for this authenticated user.")

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
