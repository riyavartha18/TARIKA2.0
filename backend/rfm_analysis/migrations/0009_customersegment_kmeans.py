# Generated for the K-Means++ (k=4) RFM clustering feature.
"""Add the K-Means cluster columns to the durable RFM result table.

`rfm_customer_segments` already stores one row per buyer with their *original*
Recency / Frequency / Monetary and the rule-based `segment`. This migration adds
two independent, nullable columns for the four-cluster K-Means++ result:

* `kmeans_cluster_id` - the raw numeric cluster (0-3), no business meaning.
* `kmeans_category`   - the business label mapped from that cluster's *unscaled*
                        RFM profile (Moderate Spending / High Spending /
                        At Risk / Frequent Buyers).

Both are nullable with no default, so applying this to the populated Neon table
rewrites no existing row and leaves the original RFM values and the rule-based
segment untouched. `rfm_segment_by_monetary` is carried forward unchanged; the
new `rfm_kmeans_by_category` index backs the dashboard's cluster aggregation.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rfm_analysis', '0008_full_rfm_result_storage'),
    ]

    operations = [
        migrations.AddField(
            model_name='customersegment',
            name='kmeans_cluster_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customersegment',
            name='kmeans_category',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddIndex(
            model_name='customersegment',
            index=models.Index(fields=['kmeans_category', 'kmeans_cluster_id'],
                               name='rfm_kmeans_by_category'),
        ),
    ]
