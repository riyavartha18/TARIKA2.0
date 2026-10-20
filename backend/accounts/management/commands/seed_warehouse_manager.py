from django.core.management.base import BaseCommand
from accounts.services.supabase_auth import SupabaseAuthService


class Command(BaseCommand):
    help = "Seeds the initial Warehouse Manager account into auth.users and public.employees."

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='warehouse.manager@iras.com',
            help='Warehouse manager email (default: warehouse.manager@iras.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='Warehouse@123',
            help='Warehouse manager password (default: Warehouse@123)'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Warehouse Manager',
            help='Warehouse manager full name'
        )
        parser.add_argument(
            '--phone',
            type=str,
            default='9876543210',
            help='Warehouse manager contact phone'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        name = options['name']
        phone = options['phone']

        self.stdout.write(f"Seeding Warehouse Manager account ({email})...")

        try:
            wm_emp, created = SupabaseAuthService.seed_initial_warehouse_manager(
                email=email,
                password=password,
                full_name=name,
                phone=phone
            )
            self.stdout.write(self.style.SUCCESS(
                f"Successfully ensured Warehouse Manager account: {wm_emp.email} (ID: {wm_emp.employee_id}, Role: {wm_emp.role})"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to seed Warehouse Manager account: {str(e)}"))
