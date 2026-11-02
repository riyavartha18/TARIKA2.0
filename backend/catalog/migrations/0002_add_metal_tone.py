from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_add_product_attributes'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE products ADD COLUMN IF NOT EXISTS metal_tone varchar(50) DEFAULT 'unknown';
            CREATE INDEX IF NOT EXISTS idx_products_metal_tone ON products(metal_tone);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_products_metal_tone;
            ALTER TABLE products DROP COLUMN IF EXISTS metal_tone;
            """
        )
    ]
