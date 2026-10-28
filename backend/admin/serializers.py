from rest_framework import serializers

# app_users stores these three canonical (lowercase) staff roles. The Staff
# Management UI sends exactly these values; aliases are normalised defensively.
ALLOWED_ROLES = ('admin', 'warehouse_manager', 'delivery')
_ROLE_ALIASES = {
    'admin': 'admin',
    'warehouse_manager': 'warehouse_manager',
    'warehouse manager': 'warehouse_manager',
    'delivery': 'delivery',
    'delivery_partner': 'delivery',
    'delivery partner': 'delivery',
}

MAX_PASSWORD_LENGTH = 72  # bcrypt reads at most 72 bytes


def normalize_role(raw):
    return _ROLE_ALIASES.get(str(raw or '').strip().lower())


class AdminStaffCreateSerializer(serializers.Serializer):
    """Create a staff account in the real public.app_users table."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    role = serializers.CharField(required=True)

    def validate_email(self, value):
        return str(value).strip().lower()

    def validate_password(self, value):
        if len(str(value).encode('utf-8')) > MAX_PASSWORD_LENGTH:
            raise serializers.ValidationError('Password is too long.')
        return value

    def validate_role(self, value):
        canonical = normalize_role(value)
        if canonical not in ALLOWED_ROLES:
            raise serializers.ValidationError(
                f"Unsupported role. Choose one of: {', '.join(ALLOWED_ROLES)}."
            )
        return canonical


class AdminStaffUpdateSerializer(serializers.Serializer):
    """Edit the supported app_users fields: role, active flag, optional password."""
    role = serializers.CharField(required=False)
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(required=False, write_only=True, min_length=6)

    def validate_role(self, value):
        canonical = normalize_role(value)
        if canonical not in ALLOWED_ROLES:
            raise serializers.ValidationError(
                f"Unsupported role. Choose one of: {', '.join(ALLOWED_ROLES)}."
            )
        return canonical

    def validate_password(self, value):
        if len(str(value).encode('utf-8')) > MAX_PASSWORD_LENGTH:
            raise serializers.ValidationError('Password is too long.')
        return value

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('No changes supplied.')
        return attrs
