from rest_framework import serializers
from accounts.services.supabase_auth import SupabaseAuthService
from accounts.models import Employee, Customer, Warehouse, Role, EmployeeRole

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