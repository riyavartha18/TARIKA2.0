import os
import sys
import django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def run_migration():
    print("Applying digital_wardrobe database schema migration...")
    with connection.cursor() as cursor:
        # 1. Add missing columns to wardrobe_items safely
        cursor.execute("""
            ALTER TABLE wardrobe_items
            ADD COLUMN IF NOT EXISTS flat_image_url text,
            ADD COLUMN IF NOT EXISTS thumb_url text,
            ADD COLUMN IF NOT EXISTS original_image_url text,
            ADD COLUMN IF NOT EXISTS source character varying(32) DEFAULT 'upload',
            ADD COLUMN IF NOT EXISTS product_key character varying(255),
            ADD COLUMN IF NOT EXISTS slot_type character varying(32) DEFAULT 'top',
            ADD COLUMN IF NOT EXISTS subtype character varying(64) DEFAULT 'other',
            ADD COLUMN IF NOT EXISTS formality integer DEFAULT 3,
            ADD COLUMN IF NOT EXISTS pattern character varying(64) DEFAULT 'solid',
            ADD COLUMN IF NOT EXISTS dominant_colours jsonb DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS style_family character varying(64) DEFAULT 'western',
            ADD COLUMN IF NOT EXISTS footwear_type character varying(64),
            ADD COLUMN IF NOT EXISTS accessory_type character varying(64),
            ADD COLUMN IF NOT EXISTS metal_tone character varying(32),
            ADD COLUMN IF NOT EXISTS includes_blouse boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS includes_dupatta boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS confidence double precision DEFAULT 1.0,
            ADD COLUMN IF NOT EXISTS needs_review boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS user_verified boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true,
            ADD COLUMN IF NOT EXISTS retake_prompt text,
            ADD COLUMN IF NOT EXISTS render_status character varying(32) DEFAULT 'completed',
            ADD COLUMN IF NOT EXISTS display_mode character varying(32) DEFAULT 'render';

            ALTER TABLE wardrobe_items ALTER COLUMN category DROP NOT NULL;
            ALTER TABLE wardrobe_items ALTER COLUMN primary_color DROP NOT NULL;
        """)

        # Add indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wardrobe_items_cust ON wardrobe_items(customer_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wardrobe_items_slot ON wardrobe_items(slot_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wardrobe_items_active ON wardrobe_items(is_active);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wardrobe_items_render_status ON wardrobe_items(render_status);")

        # Backfill existing 2 rows if any
        cursor.execute("""
            UPDATE wardrobe_items
            SET slot_type = CASE
                WHEN LOWER(category) LIKE '%shoe%' OR LOWER(category) LIKE '%footwear%' THEN 'footwear'
                WHEN LOWER(category) LIKE '%bottom%' OR LOWER(category) LIKE '%pant%' OR LOWER(category) LIKE '%jean%' THEN 'bottom'
                WHEN LOWER(category) LIKE '%dress%' OR LOWER(category) LIKE '%saree%' THEN 'one_piece'
                WHEN LOWER(category) LIKE '%bag%' THEN 'bag'
                WHEN LOWER(category) LIKE '%acc%' THEN 'accessory'
                ELSE 'top'
            END,
            dominant_colours = jsonb_build_array(COALESCE(NULLIF(LOWER(primary_color), ''), 'neutral'))
            WHERE dominant_colours = '[]'::jsonb;
        """)

        # 2. Create wardrobe_matches cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wardrobe_matches (
                id bigserial PRIMARY KEY,
                customer_id text NOT NULL,
                product_key text NOT NULL,
                wardrobe_item_id bigint NOT NULL REFERENCES wardrobe_items(id) ON DELETE CASCADE,
                score double precision DEFAULT 0.0,
                reasons jsonb DEFAULT '[]'::jsonb,
                computed_at timestamp with time zone DEFAULT NOW(),
                CONSTRAINT unq_cust_prod_item UNIQUE (customer_id, product_key, wardrobe_item_id)
            );
            CREATE INDEX IF NOT EXISTS idx_wardrobe_matches_lookup ON wardrobe_matches(customer_id, product_key);
        """)

        # 3. Create wardrobe_outfits table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wardrobe_outfits (
                id bigserial PRIMARY KEY,
                customer_id text NOT NULL,
                name character varying(128) DEFAULT 'Curated Look',
                item_ids jsonb DEFAULT '[]'::jsonb,
                is_valid boolean DEFAULT true,
                validation_notes jsonb DEFAULT '[]'::jsonb,
                created_at timestamp with time zone DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_wardrobe_outfits_cust ON wardrobe_outfits(customer_id);
        """)

        # 4. Create wardrobe_collections & m2m table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wardrobe_collections (
                id bigserial PRIMARY KEY,
                customer_id text NOT NULL,
                name character varying(128) NOT NULL,
                created_at timestamp with time zone DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_wardrobe_colls_cust ON wardrobe_collections(customer_id);

            CREATE TABLE IF NOT EXISTS wardrobe_collections_items (
                id bigserial PRIMARY KEY,
                wardrobecollection_id bigint NOT NULL REFERENCES wardrobe_collections(id) ON DELETE CASCADE,
                wardrobeitem_id bigint NOT NULL REFERENCES wardrobe_items(id) ON DELETE CASCADE,
                CONSTRAINT unq_coll_item UNIQUE (wardrobecollection_id, wardrobeitem_id)
            );
        """)

        # 5. Create wardrobe_notification_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wardrobe_notification_logs (
                id bigserial PRIMARY KEY,
                customer_id text NOT NULL,
                product_key text NOT NULL,
                score double precision DEFAULT 0.0,
                matches_count integer DEFAULT 0,
                sent_at timestamp with time zone DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_wardrobe_notifs_cust_date ON wardrobe_notification_logs(customer_id, sent_at);
        """)

    print("Successfully applied Digital Wardrobe database migration!")

if __name__ == '__main__':
    run_migration()
