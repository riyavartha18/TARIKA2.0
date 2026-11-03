"""K-Means cluster targeting for personalized coupon campaigns.

Entirely additive, as the campaign feature requires: no column is dropped, no
table is renamed, no stored value is reinterpreted.

* `rfm_kmeans_runs` - one append-only row per completed clustering run, so a
  campaign can name the exact run its audience came from (the existing
  `rfm_kmeans_run_state` singleton only ever describes the latest run).
* `rfm_campaign_audience` - the per-customer coupon assignments of a K-Means
  campaign, written when the campaign is published.
* Four new columns on `rfm_campaigns`, plus a pointer on the clustering
  singleton.

Backward compatibility is carried by the defaults: every pre-existing campaign
row gets `targeting_mode = 'LEGACY_RFM'` and empty cluster lists, so an already
published rule-based segment campaign keeps targeting, issuing and redeeming
exactly as before - nothing in this migration can silently re-read its old
segment labels as new cluster ids, because cluster ids are only ever consulted
for a row explicitly marked `KMEANS`. Issued coupons and redemption rows are
untouched (no foreign key is added to them at all).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rfm_analysis', '0010_kmeans_run_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClusteringRun',
            fields=[
                ('run_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('algorithm', models.CharField(default='KMeans(k-means++)', max_length=64)),
                ('rfm_version', models.PositiveIntegerField(default=0)),
                ('n_clusters', models.PositiveIntegerField(default=0)),
                ('clustered', models.PositiveIntegerField(default=0)),
                ('mapping', models.JSONField(blank=True, default=list)),
                ('started_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField()),
            ],
            options={
                'db_table': 'rfm_kmeans_runs',
                'ordering': ['-run_id'],
            },
        ),
        migrations.AddField(
            model_name='campaign',
            name='targeting_mode',
            field=models.CharField(
                choices=[('LEGACY_RFM', 'Rule-based RFM segment (legacy)'),
                         ('KMEANS', 'K-Means cluster')],
                default='LEGACY_RFM', max_length=20),
        ),
        migrations.AddField(
            model_name='campaign',
            name='target_cluster_ids',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='campaign',
            name='target_cluster_labels',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='campaign',
            name='clustering_run',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='campaigns',
                                    to='rfm_analysis.clusteringrun'),
        ),
        migrations.AddField(
            model_name='kmeansrunstate',
            name='run',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='+',
                                    to='rfm_analysis.clusteringrun'),
        ),
        migrations.CreateModel(
            name='CampaignAudience',
            fields=[
                ('assignment_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('customer_id', models.CharField(max_length=255)),
                ('cluster_id', models.PositiveIntegerField()),
                ('cluster_label', models.CharField(blank=True, default='', max_length=40)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audience_assignments',
                    to='rfm_analysis.campaign')),
            ],
            options={
                'db_table': 'rfm_campaign_audience',
                'ordering': ['assignment_id'],
                'indexes': [models.Index(
                    fields=['customer_id', 'campaign'],
                    name='audience_customer_campaign')],
                'constraints': [models.UniqueConstraint(
                    fields=('campaign', 'customer_id'),
                    name='unique_coupon_assignment_per_customer')],
            },
        ),
    ]
