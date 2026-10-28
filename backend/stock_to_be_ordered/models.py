from django.db import models


class ReplenishmentOrder(models.Model):
    """Row of the `public.replenishment_orders` table.

    A supplier replenishment order (warehouse restocks a product) is distinct
    from a customer sales order and is therefore kept in its own table, never in
    `public.orders`. Created idempotently by `manage.py ensure_inventory_schema`.

    `status` moves 'Pending' -> 'Received' once the goods are physically received
    (the receipt is what increases `products.available_quantity`, never the
    act of ordering).
    """
    STATUS_PENDING = 'Pending'
    STATUS_RECEIVED = 'Received'
    STATUS_CANCELLED = 'Cancelled'

    po_key = models.CharField(max_length=32, primary_key=True, db_column='po_key')
    product_key = models.CharField(max_length=255, db_column='product_key')
    product_name = models.TextField(blank=True, null=True, db_column='product_name')
    quantity_ordered = models.IntegerField(db_column='quantity_ordered')
    quantity_received = models.IntegerField(default=0, db_column='quantity_received')
    status = models.CharField(max_length=20, default=STATUS_PENDING)
    demand_tier = models.CharField(max_length=20, blank=True, null=True, db_column='demand_tier')
    # True when placing the order has ALREADY added quantity_ordered units to
    # products.available_quantity (single-product reorder). A goods receipt on
    # such a purchase order must not increment stock a second time.
    stock_applied = models.BooleanField(default=False, db_column='stock_applied')
    created_by = models.CharField(max_length=255, blank=True, null=True, db_column='created_by')
    created_at = models.CharField(max_length=100, blank=True, null=True, db_column='created_at')
    updated_at = models.CharField(max_length=100, blank=True, null=True, db_column='updated_at')
    received_at = models.CharField(max_length=100, blank=True, null=True, db_column='received_at')

    class Meta:
        db_table = 'replenishment_orders'
        managed = False
        ordering = ['-created_at', '-po_key']

    def __str__(self):
        return f"PO {self.po_key}: {self.product_key} x{self.quantity_ordered} ({self.status})"


__all__ = ['ReplenishmentOrder']
