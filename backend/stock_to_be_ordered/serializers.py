from rest_framework import serializers


class ReplenishmentOrderSerializer(serializers.Serializer):
    """Individual product replenishment order payload."""
    product_key = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_key(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError("A product is required.")
        return cleaned


class ReplenishmentReceiveSerializer(serializers.Serializer):
    """Optional explicit received quantity (defaults to the full outstanding)."""
    quantity_received = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class BulkDemandOrderSerializer(serializers.Serializer):
    """Bulk 'Order All <tier> Demand Products' payload.

    ``tier`` selects the shared ID3 demand group; ``product_keys`` optionally
    narrows the confirmed order to the products staff kept selected in the
    review dialog.
    """
    tier = serializers.ChoiceField(choices=('High', 'Medium', 'Low'), default='High')
    product_keys = serializers.ListField(
        child=serializers.CharField(max_length=255), required=False, allow_null=True,
    )


class ReplenishmentAmendSerializer(serializers.Serializer):
    """Edit the proposed supplier reorder quantity of a Pending purchase order."""
    quantity = serializers.IntegerField(min_value=1)

    def validate_quantity(self, value):
        if value is None:
            raise serializers.ValidationError("Order quantity is required.")
        return int(value)


class ReplenishmentOrderOutSerializer(serializers.Serializer):
    """Read representation of a replenishment purchase order."""
    po_key = serializers.CharField()
    product_key = serializers.CharField()
    product_name = serializers.CharField(allow_null=True)
    quantity_ordered = serializers.IntegerField()
    quantity_received = serializers.IntegerField()
    status = serializers.CharField()
    demand_tier = serializers.CharField(allow_null=True)
    created_by = serializers.CharField(allow_null=True)
    created_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)
    received_at = serializers.CharField(allow_null=True)
