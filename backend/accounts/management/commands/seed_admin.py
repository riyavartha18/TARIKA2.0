from django.core.management.base import BaseCommand
from accounts.services.supabase_auth import SupabaseAuthService


class Command(BaseCommand):
    help = "Seeds the initial IRAS Administrator account into auth.users and public.employees."

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='admin@iras.com',
            help='Admin email address (default: admin@iras.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='Admin@IRAS2026!',
            help='Admin password (default: Admin@IRAS2026!)'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='IRAS System Administrator',
            help='Admin full name'
        )
        parser.add_argument(
            '--phone',
            type=str,
            default='9999999999',
            help='Admin contact phone'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        name = options['name']
        phone = options['phone']

        self.stdout.write(f"Seeding initial Admin account ({email})...")

        try:
            admin_emp, created = SupabaseAuthService.seed_initial_admin(
                email=email,
                password=password,
                full_name=name,
                phone=phone
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully created initial Admin account: {admin_emp.email} (ID: {admin_emp.employee_id})"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Admin account already exists: {admin_emp.email} (ID: {admin_emp.employee_id})"
                ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to seed admin account: {str(e)}"))
