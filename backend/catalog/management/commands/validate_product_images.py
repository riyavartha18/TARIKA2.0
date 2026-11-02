import time
import urllib.request
import urllib.error
import re
from django.core.management.base import BaseCommand
from django.db.models import Q
from catalog.models import Product
from catalog.serializers import sanitize_product_image_url


class Command(BaseCommand):
    help = (
        "Validates product image URLs via HTTP HEAD requests with rate limiting. "
        "Flags bad/unreachable images by setting is_image_valid = False without deleting data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of products to check (default: all active products)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.05,
            help='Delay in seconds between HTTP requests for rate limiting (default: 0.05s)'
        )
        parser.add_argument(
            '--timeout',
            type=float,
            default=4.0,
            help='Timeout in seconds for each HTTP request (default: 4.0s)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report status without saving changes to the database'
        )
        parser.add_argument(
            '--flag-id',
            type=str,
            default=None,
            help='Manually flag a specific product as having an invalid/mismatched image (sets is_image_valid = False)'
        )
        parser.add_argument(
            '--unflag-id',
            type=str,
            default=None,
            help='Manually unflag a specific product (sets is_image_valid = True)'
        )
        parser.add_argument(
            '--fix-db-urls',
            action='store_true',
            help='Permanently sanitize obsolete Amazon /images/W/... URLs in the database to clean /images/I/... paths'
        )
        parser.add_argument(
            '--only-unverified',
            action='store_true',
            help='Only check products that have not been checked yet or are currently marked valid'
        )

    def check_url(self, url, timeout=4.0):
        """
        Sends an HTTP HEAD request with no-referrer user agent.
        Falls back to a 1-byte GET request if HEAD returns 405 Method Not Allowed.
        Returns (is_valid, status_code_or_error).
        """
        if not url or not isinstance(url, str) or not url.strip():
            return False, 'Empty URL'

        cleaned_url = sanitize_product_image_url(url)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        }

        # 1. Try HEAD request
        try:
            req = urllib.request.Request(cleaned_url, headers=headers, method='HEAD')
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if 200 <= resp.status < 400:
                    return True, resp.status
                return False, f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code == 405:
                # HEAD not allowed, retry with Range GET for first 128 bytes
                try:
                    headers['Range'] = 'bytes=0-127'
                    get_req = urllib.request.Request(cleaned_url, headers=headers, method='GET')
                    with urllib.request.urlopen(get_req, timeout=timeout) as resp:
                        if 200 <= resp.status < 400 or resp.status == 206:
                            return True, resp.status
                        return False, f"HTTP {resp.status}"
                except Exception as get_err:
                    return False, f"HTTP {e.code} / GET fallback failed: {get_err}"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)

    def handle(self, *args, **options):
        # 1. Manual single product flag / unflag
        flag_id = options.get('flag_id')
        if flag_id:
            try:
                p = Product.objects.get(product_id=flag_id)
                p.is_image_valid = False
                p.save(update_fields=['is_image_valid'])
                self.stdout.write(self.style.SUCCESS(f"Successfully flagged product {flag_id} ('{p.product_name}'): is_image_valid = False"))
            except Product.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Product {flag_id} not found in database."))
            return

        unflag_id = options.get('unflag_id')
        if unflag_id:
            try:
                p = Product.objects.get(product_id=unflag_id)
                p.is_image_valid = True
                p.save(update_fields=['is_image_valid'])
                self.stdout.write(self.style.SUCCESS(f"Successfully unflagged product {unflag_id} ('{p.product_name}'): is_image_valid = True"))
            except Product.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Product {unflag_id} not found in database."))
            return

        # 2. Fix DB URLs if requested
        if options.get('fix_db_urls'):
            self.stdout.write("Checking for obsolete Amazon /images/W/... paths in database...")
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute("SELECT count(*) FROM products WHERE image LIKE '%/images/W/%';")
                total_w = cur.fetchone()[0]
                self.stdout.write(f"Found {total_w} products with obsolete Amazon paths.")
                if total_w > 0:
                    if not options['dry_run']:
                        cur.execute(
                            "UPDATE products SET image = REGEXP_REPLACE(image, '/images/W/[^/]+/images/I/', '/images/I/') "
                            "WHERE image LIKE '%/images/W/%';"
                        )
                        self.stdout.write(self.style.SUCCESS(f"Successfully sanitized {total_w} URLs in database!"))
                    else:
                        self.stdout.write(f"DRY RUN: Would sanitize {total_w} URLs.")

        # 3. Batch check URLs via HTTP
        limit = options.get('limit')
        delay = options.get('delay', 0.05)
        timeout = options.get('timeout', 4.0)
        dry_run = options.get('dry_run', False)

        qs = Product.objects.all().order_by('product_id')
        if options.get('only_unverified'):
            qs = qs.filter(is_image_valid=True)
        if limit:
            qs = qs[:limit]

        total_to_check = qs.count() if limit else Product.objects.count()
        self.stdout.write(self.style.NOTICE(
            f"Starting image validation for {total_to_check} products "
            f"(delay: {delay}s, timeout: {timeout}s, dry_run: {dry_run})..."
        ))

        valid_count = 0
        invalid_count = 0
        empty_count = 0

        flagged_batch = []
        start_time = time.time()
        chunk_size = 500
        idx = 0

        for offset in range(0, total_to_check, chunk_size):
            chunk = list(qs[offset:offset + chunk_size])
            if not chunk:
                break
            for prod in chunk:
                idx += 1
            url = prod.image
            if not url or not str(url).strip():
                empty_count += 1
                invalid_count += 1
                if not dry_run and prod.is_image_valid:
                    prod.is_image_valid = False
                    flagged_batch.append(prod)
                continue

            is_valid, msg = self.check_url(url, timeout=timeout)
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                self.stdout.write(self.style.WARNING(
                    f"[{idx}/{total_to_check}] INVALID: Product {prod.product_id} - Reason: {msg} (URL: {url[:70]}...)"
                ))
                if not dry_run and prod.is_image_valid:
                    prod.is_image_valid = False
                    flagged_batch.append(prod)

            if len(flagged_batch) >= 100:
                Product.objects.bulk_update(flagged_batch, ['is_image_valid'], batch_size=100)
                flagged_batch = []

            if delay > 0:
                time.sleep(delay)

            if idx % 100 == 0 or idx == total_to_check:
                elapsed = time.time() - start_time
                self.stdout.write(
                    f"Progress: {idx}/{total_to_check} checked | "
                    f"Valid: {valid_count} | Invalid: {invalid_count} | "
                    f"Elapsed: {elapsed:.1f}s"
                )

        if flagged_batch and not dry_run:
            Product.objects.bulk_update(flagged_batch, ['is_image_valid'], batch_size=100)

        elapsed_total = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n=== Image Validation Complete ===\n"
            f"Total Checked: {valid_count + invalid_count}\n"
            f"Valid Images:  {valid_count}\n"
            f"Invalid/Empty: {invalid_count} (Flagged: is_image_valid=False)\n"
            f"Total Time:    {elapsed_total:.1f}s\n"
            f"Mode:          {'DRY RUN (no DB writes)' if dry_run else 'COMMITTED TO DB'}\n"
        ))
