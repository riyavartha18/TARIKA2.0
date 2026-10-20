from rest_framework import serializers
from accounts.models import Employee, Customer, Warehouse, Role, EmployeeRole
from accounts.services.supabase_auth import SupabaseAuthService


class CustomerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    full_name = serializers.CharField(required=True, max_length=255)
    phone = serializers.IntegerField(required=False, allow_null=True)
    city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    state = serializers.CharField(required=False, allow_blank=True, max_length=100)
    country = serializers.CharField(required=False, allow_blank=True, max_length=100, default='India')

    def validate(self, attrs):
        # Strict security rule: Any incoming 'role' parameter is purged/disallowed.
        # Customers are always strictly assigned CUSTOMER role.
        return attrs

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        full_name = validated_data['full_name']
        phone = validated_data.get('phone')
        extra_fields = {
            'city': validated_data.get('city'),
            'state': validated_data.get('state'),
            'country': validated_data.get('country', 'India')
        }
        return SupabaseAuthService.register_customer(
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            **extra_fields
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(required=True, help_text="Username or Email address")
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email_or_username = attrs.get('email')
        password = attrs.get('password')
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
