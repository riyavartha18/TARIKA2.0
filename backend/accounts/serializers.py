from rest_framework import serializers
from accounts.models import Employee, Customer, Warehouse, Role, EmployeeRole
from accounts.services.supabase_auth import SupabaseAuthService, MAX_PASSWORD_LENGTH


class CustomerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    # bcrypt uses at most 72 bytes of the password; longer values cannot be
    # verified reliably, so they are refused at signup instead of silently
    # truncated in the stored hash.
    password = serializers.CharField(
        write_only=True, required=True, min_length=6,
        max_length=MAX_PASSWORD_LENGTH, trim_whitespace=False
    )
    full_name = serializers.CharField(required=True, max_length=255)
    gender = serializers.CharField(required=False, allow_blank=True, max_length=50)

    def validate(self, attrs):
        # Strict security rule: Any incoming 'role' parameter is purged/disallowed.
        # Customers are always strictly assigned CUSTOMER role.
        return attrs

    def create(self, validated_data):
        return SupabaseAuthService.register_customer(
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data['full_name'],
            gender=validated_data.get('gender'),
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True, help_text="Username or Email address")
    # Trimmed, never stripped of case: the password is compared exactly as
    # submitted. write_only keeps it out of every response payload.
    password = serializers.CharField(write_only=True, required=True, trim_whitespace=False)

    def validate(self, attrs):
        email_or_username = str(attrs.get('email') or '').strip()
        password = attrs.get('password')
        if not email_or_username or not str(password or '').strip():
            # Same generic wording as a credential mismatch, so a malformed
            # request cannot reveal whether an email is registered.
            raise serializers.ValidationError("Invalid email or password.")
        auth_result = SupabaseAuthService.login(email_or_username, password)
        attrs['auth_result'] = auth_result
        return attrs


class AdminStaffCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    full_name = serializers.CharField(required=True, max_length=255)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=50)
    role = serializers.ChoiceField(
        choices=[
            EmployeeRole.WAREHOUSE_MANAGER,
            EmployeeRole.DELIVERY_PARTNER
        ],
        required=True
    )
    warehouse_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        role = attrs.get('role')
        warehouse_id = attrs.get('warehouse_id')

        if role == EmployeeRole.WAREHOUSE_MANAGER:
            if not warehouse_id or not str(warehouse_id).strip():
                raise serializers.ValidationError({
                    "warehouse_id": "warehouse_id is required when creating a Warehouse Manager."
                })
            warehouse_exists = Warehouse.objects.filter(warehouse_id=warehouse_id).exists()
            if not warehouse_exists:
                raise serializers.ValidationError({
                    "warehouse_id": f"No warehouse exists with ID '{warehouse_id}'."
                })
        else:
            # Delivery Partner does NOT have a warehouse association in Part 1
            attrs['warehouse_id'] = None

        return attrs

    def create(self, validated_data):
        admin_user = self.context.get('request').user
        return SupabaseAuthService.admin_create_employee(
            admin_user=admin_user,
            email=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data['full_name'],
            role=validated_data['role'],
            warehouse_id=validated_data.get('warehouse_id'),
            phone=validated_data.get('phone')
        )


class UserProfileSerializer(serializers.Serializer):
    id = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    warehouse_id = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()
    details = serializers.DictField(required=False)
