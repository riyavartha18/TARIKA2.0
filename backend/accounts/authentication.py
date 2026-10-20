import uuid
from datetime import datetime, timezone
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from accounts.models import Employee, Customer, Role
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

        # 1. Check if the user is an Employee (ADMIN, WAREHOUSE_MANAGER, DELIVERY_PARTNER)
        employee = Employee.objects.filter(auth_user_id=auth_user_id).first()
        if employee:
            if not employee.is_active:
                raise AuthenticationFailed("This employee account has been deactivated.")
            
            user = AuthenticatedUser(
                auth_user_id=auth_user_id,
                email=employee.email,
                role=employee.role,
                profile=employee,
                warehouse_id=employee.warehouse_id,
                is_active=employee.is_active
            )
            request.role = user.role
            request.warehouse_id = user.warehouse_id
            return (user, raw_token)

        # 2. Check if the user is a Customer
        customer = Customer.objects.filter(auth_user_id=auth_user_id).first()
        if not customer:
            # Fallback lookup by email (e.g. pre-existing customer or Google OAuth)
            email_claim = payload.get('email')
            if email_claim:
                customer = Customer.objects.filter(email__iexact=email_claim).first()
                if customer and not customer.auth_user_id:
                    customer.auth_user_id = auth_user_id
                    customer.save(update_fields=['auth_user_id'])

        # 3. Auto-provision Customer if logged in via Google OAuth or missing profile
        if not customer:
            email_claim = payload.get('email')
            if email_claim:
                user_meta = payload.get('user_metadata', {})
                full_name = user_meta.get('full_name') or user_meta.get('name') or email_claim.split('@')[0].capitalize()
                now = datetime.now(timezone.utc)
                customer = Customer.objects.create(
                    customer_id=str(uuid.uuid4()),
                    auth_user_id=auth_user_id,
                    email=email_claim,
                    full_name=full_name,
                    registration_date=now.strftime('%Y-%m-%d'),
                    is_active=True,
                    created_at=now.isoformat(),
                    updated_at=now.isoformat()
                )

        if customer:
            if not customer.is_active:
                raise AuthenticationFailed("This customer account has been deactivated.")

            user = AuthenticatedUser(
                auth_user_id=auth_user_id,
                email=customer.email,
                role=Role.CUSTOMER,
                profile=customer,
                warehouse_id=None,
                is_active=customer.is_active
            )
            request.role = user.role
            request.warehouse_id = None
            return (user, raw_token)

        raise AuthenticationFailed("No profile record found in IRAS for this authenticated user.")

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
