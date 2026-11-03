"""Durable dashboard aggregate cache + the cluster-targeting index.

Both operations are additive; no column is dropped and no stored value is
changed.

* `rfm_dashboard_snapshot` keeps the assembled RFM dashboard aggregate (KPIs,
  segment mix, K-Means cluster counts) per analysis version, so a restarted
  process reads one primary-key row instead of re-running the grouped aggregate
  over ~100k persisted buyers on the first admin's critical path. It is a derived
  cache: emptying the table only costs one recompute per version.
* `rfm_kmeans_by_cluster` indexes `(kmeans_cluster_id, kmeans_category)`, the
  column pair every cluster aggregation and every campaign-audience resolution
  filters and groups by (the existing `rfm_kmeans_by_category` index leads with
  the label, which those queries never filter on first).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rfm_analysis', '0011_campaign_kmeans_targeting'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardSnapshot',
            fields=[
                ('version', models.PositiveIntegerField(primary_key=True, serialize=False)),
                ('clustering_run_id', models.PositiveIntegerField(blank=True, null=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('computed_at', models.DateTimeField()),
            ],
            options={
                'db_table': 'rfm_dashboard_snapshot',
                'ordering': ['-version'],
            },
        ),
        migrations.AddIndex(
            model_name='customersegment',
            index=models.Index(fields=['kmeans_cluster_id', 'kmeans_category'], name='rfm_kmeans_by_cluster'),
        ),
    ]
