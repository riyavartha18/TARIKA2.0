"""Initial schema: campaign configuration and order-level redemption audit.

Both tables are managed (owned by Django) because they are genuinely new
infrastructure the inspected Neon database lacked; the dataset tables
(`orders`, `customers`, ...) stay unmanaged elsewhere. See `models.py` for why
identity is stored as text keys rather than foreign keys.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('campaign_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('coupon_code', models.CharField(max_length=64, unique=True)),
                ('description', models.TextField(blank=True, default='')),
                ('discount_type', models.CharField(choices=[('PERCENTAGE', 'Percentage'), ('FIXED', 'Fixed amount')], default='PERCENTAGE', max_length=20)),
                ('discount_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('max_discount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('target_segments', models.JSONField(blank=True, default=list)),
                ('target_tags', models.JSONField(blank=True, default=list)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('min_order_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('usage_type', models.CharField(choices=[('ONCE', 'Once per customer'), ('LIMITED', 'Limited uses per customer'), ('UNLIMITED', 'Unlimited uses per customer')], default='UNLIMITED', max_length=20)),
                ('per_customer_limit', models.PositiveIntegerField(default=0)),
                ('global_usage_limit', models.PositiveIntegerField(default=0)),
                ('stacking_allowed', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published'), ('PAUSED', 'Paused'), ('EXPIRED', 'Expired')], default='DRAFT', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'rfm_campaigns',
                'ordering': ['-campaign_id'],
            },
        ),
        migrations.CreateModel(
            name='CampaignRedemption',
            fields=[
                ('redemption_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('order_id', models.CharField(max_length=32)),
                ('customer_id', models.CharField(max_length=255)),
                ('discount_applied', models.DecimalField(decimal_places=2, max_digits=12)),
                ('redeemed_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='redemptions', to='rfm_analysis.campaign')),
            ],
            options={
                'db_table': 'rfm_campaign_redemptions',
                'ordering': ['-redemption_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='campaignredemption',
            constraint=models.UniqueConstraint(fields=('campaign', 'order_id'), name='unique_coupon_per_order'),
        ),
        migrations.AddIndex(
            model_name='campaignredemption',
            index=models.Index(fields=['campaign', 'customer_id'], name='redemption_campaign_customer'),
        ),
    ]
