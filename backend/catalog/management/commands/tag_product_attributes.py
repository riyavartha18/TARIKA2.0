import time
import json
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Q
from catalog.models import Product
from catalog.classifier import classify_product


class Command(BaseCommand):
    help = (
        "Classifies and tags product attributes (slot_type, formality, pattern, "
        "dominant_colours, style_family, footwear_type, subtype, etc.) for the Smart Budget Stylist. "
        "Idempotent and safe: never deletes data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of products to tag (default: all active products)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk updates (default: 1000)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.0,
            help='Rate limit delay in seconds between batches (default: 0.0s)'
        )
        parser.add_argument(
            '--sample-images',
            action='store_true',
            help='Sample image dominant colour via HTTP (rate-limited)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run classification and print the audit report without committing to the database'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            dest='tag_all',
            help='Re-tag all products (default is only untagged products to conserve database storage on Neon)'
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        batch_size = options.get('batch_size', 1000)
        delay = options.get('delay', 0.0)
        sample_images = options.get('sample_images', False)
        dry_run = options.get('dry_run', False)
        tag_all = options.get('tag_all', False)

        if tag_all:
            qs = Product.objects.all().order_by('product_id')
        else:
            qs = Product.objects.filter(slot_type__isnull=True).order_by('product_id')

        if limit:
            qs = qs[:limit]

        total_products = qs.count()
        if total_products == 0 and not tag_all:
            self.stdout.write(self.style.SUCCESS(
                "All catalog products are already tagged! Use --all if you want to force re-tagging all products."
            ))
            return
        self.stdout.write(self.style.NOTICE(
            f"Starting attribute tagging for {total_products} products "
            f"(batch_size={batch_size}, sample_images={sample_images}, dry_run={dry_run})..."
        ))

        tagged_count = 0
        excluded_count = 0
        unclassified_footwear_count = 0
        mismatch_products = []

        exclusion_reasons = {
            'low_confidence': 0,
            'missing_slot_type': 0,
            'hidden_flagged': 0,
            'invalid_image': 0,
            'empty_image': 0,
            'innerwear_or_junk': 0
        }

        slot_breakdown = {}
        subtype_breakdown = {}

        batch = []
        start_time = time.time()
        offset = 0

        # Chunked offset processing (avoids pgbouncer named cursor issues)
        while offset < total_products:
            chunk_qs = qs[offset:offset + batch_size]
            chunk_list = list(chunk_qs)
            if not chunk_list:
                break

            for p in chunk_list:
                res = classify_product(
                    product_name=p.product_name,
                    main_category=p.main_category,
                    sub_category=p.sub_category,
                    image_url=p.image,
                    sample_image=sample_images
                )

                # Set attributes on model instance
                p.slot_type = res.get('slot_type')
                p.formality = res.get('formality', 3)
                p.pattern = res.get('pattern', 'solid')
                p.dominant_colours = res.get('dominant_colours', '[]')
                p.style_family = res.get('style_family', 'western')
                p.season = res.get('season', 'all')
                p.footwear_type = res.get('footwear_type')
                p.accessory_type = res.get('accessory_type')
                p.subtype = res.get('subtype', 'other')
                p.includes_blouse = res.get('includes_blouse', False)
                p.includes_dupatta = res.get('includes_dupatta', False)
                p.metal_tone = res.get('metal_tone', 'unknown')
                p.confidence = res.get('confidence', 0.95)
                p.hidden = res.get('hidden', False)

                # Track metrics
                tagged_count += 1
                slot = res['slot_type'] or 'unclassified'
                slot_breakdown[slot] = slot_breakdown.get(slot, 0) + 1

                st = res['subtype'] or 'other'
                subtype_breakdown[st] = subtype_breakdown.get(st, 0) + 1

                if res['slot_type'] == 'footwear' and res['footwear_type'] == 'other':
                    unclassified_footwear_count += 1

                # Track mismatches
                if res['mismatch_reason']:
                    mismatch_products.append({
                        'id': p.product_id,
                        'name': p.product_name[:60] if p.product_name else '',
                        'reason': res['mismatch_reason']
                    })

                # Check if this item is excluded from the Stylist
                is_excluded = False
                if not p.image or not str(p.image).strip():
                    exclusion_reasons['empty_image'] += 1
                    is_excluded = True
                elif getattr(p, 'is_image_valid', True) is False:
                    exclusion_reasons['invalid_image'] += 1
                    is_excluded = True
                elif not res['slot_type']:
                    exclusion_reasons['missing_slot_type'] += 1
                    is_excluded = True
                elif res['confidence'] < 0.6:
                    exclusion_reasons['low_confidence'] += 1
                    is_excluded = True
                elif res['hidden']:
                    exclusion_reasons['hidden_flagged'] += 1
                    is_excluded = True

                if is_excluded:
                    excluded_count += 1

                batch.append(p)

            # Bulk update chunk to DB if not dry run
            if not dry_run:
                Product.objects.bulk_update(
                    batch,
                    [
                        'slot_type', 'formality', 'pattern', 'dominant_colours',
                        'style_family', 'season', 'footwear_type', 'accessory_type',
                        'subtype', 'includes_blouse', 'includes_dupatta', 'metal_tone', 'confidence', 'hidden'
                    ],
                    batch_size=batch_size
                )

            batch = []
            offset += len(chunk_list)
            elapsed = time.time() - start_time
            self.stdout.write(f"Processed {offset}/{total_products} products ({elapsed:.1f}s)...")

            if delay > 0:
                time.sleep(delay)

        total_elapsed = time.time() - start_time

        # Base type counts
        base1_tops = slot_breakdown.get('top', 0)
        base1_bottoms = slot_breakdown.get('bottom', 0)
        base2_onepiece = slot_breakdown.get('one_piece', 0)
        base3_sarees = subtype_breakdown.get('saree', 0)
        base3_lehengas = subtype_breakdown.get('lehenga_set', 0) + subtype_breakdown.get('lehenga_skirt', 0)

        # Print audit report
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("PRODUCT ATTRIBUTE TAGGING AUDIT REPORT"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total Products Processed:          {tagged_count}")
        self.stdout.write(f"Stylist-Eligible Products:         {tagged_count - excluded_count} ({(tagged_count - excluded_count) / max(1, tagged_count) * 100:.1f}%)")
        self.stdout.write(f"Stylist-Excluded Products:         {excluded_count} ({excluded_count / max(1, tagged_count) * 100:.1f}%)")
        self.stdout.write("\nExclusion Reasons Breakdown:")
        for reason, cnt in exclusion_reasons.items():
            self.stdout.write(f"  - {reason.replace('_', ' ').title()}: {cnt}")

        self.stdout.write("\nClothing Base Product Distribution:")
        self.stdout.write(f"  - Base 1 (Two-Piece Tops):             {base1_tops}")
        self.stdout.write(f"  - Base 1 (Two-Piece Bottoms):          {base1_bottoms}")
        self.stdout.write(f"  - Base 2 (One-Piece Dresses/Jumpsuits): {base2_onepiece}")
        self.stdout.write(f"  - Base 3 (Sarees):                     {base3_sarees}")
        self.stdout.write(f"  - Base 3 (Lehengas):                   {base3_lehengas}")

        self.stdout.write("\nSlot Type Classification Breakdown:")
        for slot, cnt in sorted(slot_breakdown.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  - {slot}: {cnt}")

        self.stdout.write("\nEthnic Subtype Breakdown:")
        for st, cnt in sorted(subtype_breakdown.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  - {st}: {cnt}")

        self.stdout.write(f"\nFootwear Items Unclassified / 'other': {unclassified_footwear_count}")

        self.stdout.write(f"\nRule-Based Contradictions / Mismatches Flagged: {len(mismatch_products)}")
        if mismatch_products:
            self.stdout.write("Sample Flagged Mismatches (first 10):")
            for item in mismatch_products[:10]:
                self.stdout.write(f"  * [{item['id']}] {item['name']} -> {item['reason']}")

        self.stdout.write(f"\nTotal Time Taken: {total_elapsed:.1f} seconds")
        self.stdout.write(f"Mode: {'DRY RUN (no database changes)' if dry_run else 'COMMITTED TO DATABASE'}")
        self.stdout.write("=" * 60 + "\n")
