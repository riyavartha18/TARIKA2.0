"""Persist the RFM lifetime Monetary value per buyer (CLV data sharing).

The CLV module must reuse the exact RFM revenue definition instead of
re-aggregating the 1M-row orders table, so a completed RFM run now also stores
each buyer's Monetary value on the existing `rfm_customer_segments` row. This
is the only database change the CLV feature needs: no new tables, no duplicate
first/last-date or order-count columns (those stay derived from `orders`).

The column is nullable, so applying this migration never rewrites or invalidates
existing rows; the next completed analysis fills in real values, and until then
the CLV module falls back to its own aggregate over the same eligibility rules.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rfm_analysis', '0006_campaignredemption_redemption_customer_campaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='customersegment',
            name='monetary',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
    ]
