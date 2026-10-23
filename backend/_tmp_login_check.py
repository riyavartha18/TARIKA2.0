"""Temporary: check seeded staff password works for warehouse manager (read-only)."""
import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from accounts.services.supabase_auth import SupabaseAuthService
from rest_framework.exceptions import AuthenticationFailed

try:
    staff = SupabaseAuthService.verify_staff_credentials('warehouse.manager@iras.com', 'Warehouse@123')
    print('LOGIN OK:', json.dumps(staff))
except AuthenticationFailed as e:
    print('LOGIN FAILED:', e)
