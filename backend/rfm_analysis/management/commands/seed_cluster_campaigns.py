"""Seed personalised coupon campaigns for the four K-Means customer groups.

Formerly `seed_segment_campaigns`, which authored one campaign set per rule-based
RFM segment. Campaign targeting now uses the current K-Means clustering only, so
this command resolves the four business groups from the LATEST persisted
clustering run (`cluster_targeting.available_clusters`) and creates one offer set
per group through the existing CampaignSerializer + `campaign_publishing`
workflow - the same models, validation, coupon assignment and publishing path
the admin Campaign page uses. Nothing here is a second targeting system.

Nothing is invented: every product id, name, category, price and bundle comes
from the live `public.products` table (combos prefer real best sellers from
`fact_product_analysis`), and each offer uses a rule shape the benefits engine
already prices. Re-running is idempotent:

* a campaign that does not exist yet is created and published, which issues its
  coupon to exactly the customers of that group's cluster;
* a campaign that exists is left alone (reported as `kept`). Its issued coupons
  are in customers' accounts, so the command never rewrites their terms or dates;
  an admin changes those deliberately from the Campaign page;
* a campaign that exists as a DRAFT (e.g. it was created when no clustering was
  available) is completed and published now that the audience resolves.

Usage:
    python manage.py seed_cluster_campaigns
    python manage.py seed_cluster_campaigns --retire-other   # expire the rest

`--retire-other` marks campaigns outside this set EXPIRED. It never deletes a
campaign: rows with issued coupons or redemption history are history, and a row
without any is still kept so the admin list remains a complete record.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from catalog.models import Product
from catalog.pricing import get_product_selling_price_map
from rfm_analysis import cache_manager, cluster_targeting
from rfm_analysis.models import Campaign, CampaignStatus, OfferCategory
from rfm_analysis.serializers import CampaignSerializer

VALIDITY_DAYS = 90

# The offers each group gets, keyed by the business LABEL (never a numeric
# cluster id: which id carries which label is re-derived on every run). Every
# entry is (suffix, name, description, builder) and the builder turns the loaded
# catalogue into the rule payload for that offer type.
OFFER_SETS = {
    'Frequent Buyers': ('FB', [
        ('B2G1', 'Buy 2 Get 1 Free', 'Buy any 2 of these pieces, get 1 free.',
         'buy_get_free_selected'),
        ('B2S15', 'Buy 2 Save 15%', 'Two items in the bag: 15% off.',
         'buy_more_save'),
        ('FSHIP', 'Free Delivery', 'Free delivery on orders above Rs.999.',
         'free_shipping'),
        ('COMBO', 'Everyday Favourites Combo',
         'Our three most-bought pieces at a combo price.', 'bundle_0'),
    ]),
    'Moderate Spending': ('MOD', [
        ('FLAT150', 'Rs.150 OFF Next Order', 'Flat Rs.150 off any order above Rs.999.',
         'flat_150'),
        ('B2G50', 'Buy 2 Get 1 at 50% OFF', 'Buy 2 items, get the third at half price.',
         'buy_get_discount'),
        ('CAT15', 'Category Combo Discount', '15% off our most-worn categories.',
         'product_discount_categories'),
        ('GIFT', 'Complimentary Gift', 'A free gift on orders above Rs.1,499.',
         'free_gift_1'),
    ]),
    'High Spending': ('HIGH', [
        ('VIP15', 'VIP 15% OFF', 'An exclusive 15% discount on your next order.',
         'percentage_15'),
        ('B2G1', 'Buy 2 Get 1 Free', 'Buy any 2 of these premium picks, get 1 free.',
         'buy_get_free_selected_2'),
        ('PREM', 'Premium Combo Deals', 'A premium combination at a special price.',
         'bundle_4'),
        ('CASH200', 'Rs.200 Cashback',
         'Rs.200 cashback credited after delivery on orders above Rs.2,000.',
         'cashback_200'),
    ]),
    'At Risk': ('RISK', [
        ('20OFF', '20% OFF Comeback', 'Flat 20% off, up to Rs.500 — we miss you.',
         'percentage_20_capped'),
        ('B2G1', 'Buy 2 Get 1 Free', 'Buy any 2 items, get 1 free.',
         'buy_get_free_any'),
        ('CASH300', 'Rs.300 Cashback',
         'Rs.300 cashback credited after delivery on orders above Rs.1,999.',
         'cashback_300'),
        ('COMBO', 'Comeback Combo', 'A three-piece favourite at a comeback price.',
         'bundle_2'),
        ('GIFT', 'Free Gift on Return', 'A complimentary gift with your return order.',
         'free_gift_3'),
    ]),
}


def _round_rupee(value):
    return float(int(round(value)))


class Command(BaseCommand):
    help = ('Create/refresh the personalised coupon campaigns of the four '
            'K-Means customer groups (published).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--retire-other', action='store_true',
            help='Mark campaigns outside this set EXPIRED (never deleted).')

    # ------------------------------------------------------------------ main

    def handle(self, *args, **options):
        now = timezone.now()
        groups = cluster_targeting.available_clusters(include_campaign_stats=False)
        if not groups['available']:
            self.stderr.write(
                'No persisted K-Means clustering run is available, so no customer '
                f'group can be targeted: {groups["message"]}\n'
                'Run the clustering on the RFM analysis page first '
                '(python manage.py run_kmeans_segmentation).')
            return

        by_label = {group['category']: group for group in groups['clusters']}
        missing = [label for label in OFFER_SETS if label not in by_label]
        if missing:
            self.stderr.write(
                'The stored clustering does not carry these business groups yet: '
                f'{", ".join(missing)}. Re-run the clustering before seeding.')
            return

        catalog = self._load_catalog()
        if len(catalog['priced']) < 24:
            self.stderr.write('Not enough priced, active products to seed '
                              f"product-scoped offers (found {len(catalog['priced'])}).")
            return

        run = groups['run']
        self.stdout.write(
            f"Targeting clustering run #{run['run_id']} (RFM v{run['rfm_version']}):")
        for label in sorted(by_label):
            group = by_label[label]
            self.stdout.write(f"  #{group['cluster_id']} {label}: "
                              f"{group['customer_count']:,} customers")

        if options['retire_other']:
            self._retire_other_campaigns(by_label, run['run_id'])

        counts = {'created': 0, 'published': 0, 'kept': 0, 'failed': 0}
        for label, (suffix, offers) in OFFER_SETS.items():
            for code_suffix, name, description, rule in offers:
                definition = self._definition(
                    label, by_label[label], suffix, code_suffix, name, description,
                    rule, catalog, now)
                outcome = self._upsert(definition)
                counts[outcome] = counts.get(outcome, 0) + 1
                self.stdout.write(f"  {outcome:8s} {definition['coupon_code']:16s} "
                                  f"[{label}] {definition['name']}")

        self.stdout.write(self.style.SUCCESS(
            f"Group campaigns: {counts['created']} created, "
            f"{counts['published']} drafted-then-published, "
            f"{counts['kept']} kept as they are, {counts['failed']} rejected."))
        cache_manager.bump_campaign_epoch()

    # ------------------------------------------------------- campaign catalog

    def _definition(self, label, group, suffix, code_suffix, name, description,
                    rule, catalog, now):
        """One campaign payload: the offer, and its cluster as the audience."""
        return {
            'name': name,
            'coupon_code': f'{suffix}_{code_suffix}',
            'description': description,
            # The audience is the cluster this run mapped onto the group's label.
            'targeting_mode': 'KMEANS',
            'target_cluster_ids': [group['cluster_id']],
            'start_date': now - timedelta(minutes=1),
            'end_date': now + timedelta(days=VALIDITY_DAYS),
            'min_order_amount': 0, 'max_discount': None,
            'usage_type': 'UNLIMITED', 'per_customer_limit': 0,
            'global_usage_limit': 0, 'stacking_allowed': False,
            'scope': {'mode': 'ALL'}, 'benefits_combinable': False,
            'offer_category': OfferCategory.DISCOUNT,
            'discount_rule': {}, 'buy_get_rule': {},
            **self._rule_payload(rule, catalog),
        }

    @staticmethod
    def _rule_payload(kind, catalog):
        """The offer rules, expressed in the existing structured rule shapes."""
        ids = catalog['ids']
        combos = catalog['combos']
        gifts = catalog['gifts']
        categories = catalog['categories']
        selected = lambda product_ids: {  # noqa: E731
            'mode': 'PRODUCTS', 'product_ids': product_ids}

        def buy_get(rule, scope=None, usage='UNLIMITED'):
            return {'offer_category': OfferCategory.BUY_GET, 'discount_rule': {},
                    'buy_get_rule': rule, 'usage_type': usage,
                    **({'scope': scope} if scope else {})}

        def discount(rule, **overrides):
            payload = {'offer_category': OfferCategory.DISCOUNT,
                       'discount_rule': rule, 'buy_get_rule': {}}
            payload.update(overrides)
            return payload

        builders = {
            'buy_get_free_selected': lambda: buy_get(
                {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
                scope=selected(ids['slice_a'])),
            'buy_get_free_selected_2': lambda: buy_get(
                {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
                scope=selected(ids['slice_b'])),
            'buy_get_free_any': lambda: buy_get(
                {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1}),
            'buy_get_discount': lambda: buy_get(
                {'type': 'BUY_X_GET_Y_DISCOUNT', 'buy_qty': 2, 'get_qty': 1,
                 'discount_percent': 50}),
            'buy_more_save': lambda: discount(
                {'type': 'BUY_MORE_SAVE_MORE', 'tiers': [{'buy': 2, 'percent': 15}]}),
            'free_shipping': lambda: discount({'type': 'FREE_SHIPPING'},
                                              min_order_amount=999),
            'flat_150': lambda: discount({'type': 'FLAT', 'flat': 150},
                                         min_order_amount=999),
            'percentage_15': lambda: discount({'type': 'PERCENTAGE', 'percent': 15}),
            'percentage_20_capped': lambda: discount({'type': 'PERCENTAGE',
                                                      'percent': 20},
                                                     max_discount=500),
            'cashback_200': lambda: discount({'type': 'CASHBACK', 'cashback': 200},
                                             min_order_amount=2000, usage_type='ONCE'),
            'cashback_300': lambda: discount({'type': 'CASHBACK', 'cashback': 300},
                                             min_order_amount=1999, usage_type='ONCE'),
            'product_discount_categories': lambda: buy_get(
                {'type': 'PRODUCT_DISCOUNT', 'discount_percent': 15},
                scope={'mode': 'CATEGORIES', 'categories': categories}),
            'bundle_0': lambda: _bundle(combos, 0),
            'bundle_2': lambda: _bundle(combos, 2),
            'bundle_4': lambda: _bundle(combos, 4),
            'free_gift_1': lambda: _gift(gifts, 1, 1499),
            'free_gift_3': lambda: _gift(gifts, 3, 0),
        }
        return builders[kind]()

    # ------------------------------------------------------------ upsert logic

    def _upsert(self, definition):
        """Create + publish a group campaign, or leave an existing one alone."""
        from rfm_analysis import campaign_publishing

        coupon_code = definition['coupon_code']
        existing = Campaign.objects.filter(coupon_code=coupon_code).first()
        if existing and existing.status != CampaignStatus.DRAFT:
            # Its coupons are already in customers' accounts: the terms, dates
            # and audience it was published with are history, not this command's
            # to rewrite. The admin changes them deliberately from the UI.
            return 'kept'

        payload = dict(definition)
        if existing:
            serializer = CampaignSerializer(existing, data=payload, partial=True)
        else:
            serializer = CampaignSerializer(data=payload)
        if not serializer.is_valid():
            self.stderr.write(f"  REJECTED {coupon_code}: {serializer.errors}")
            return 'failed'
        campaign = serializer.save()

        # Publishing runs the one workflow the admin page uses: re-check the
        # audience, dates and offer, then issue the coupon to that group's
        # customers and report how many were reached.
        audience, error = campaign_publishing.change_status(
            campaign, CampaignStatus.PUBLISHED)
        if error:
            self.stderr.write(f"  NOT PUBLISHED {coupon_code}: {error}")
            return 'failed'
        if audience:
            self.stdout.write(
                f"           issued {audience['coupons_issued']:,} coupon(s) to "
                f"{audience['targeted']:,} customer(s) of "
                f"{', '.join(c['category'] for c in audience['clusters'])}")
        return 'published' if existing else 'created'

    # ------------------------------------------------------- legacy cleanup

    def _retire_other_campaigns(self, by_label, run_id):
        """Expire every campaign outside this set; delete nothing, ever."""
        from rfm_analysis.models import CampaignAudience

        keep = {f'{suffix}_{code}'
                for _label, (suffix, offers) in OFFER_SETS.items()
                for code, *_rest in offers}
        seed_labels = set(by_label)
        for campaign in Campaign.objects.exclude(coupon_code__in=keep):
            if campaign.status == CampaignStatus.EXPIRED:
                continue
            audience = CampaignAudience.objects.filter(campaign=campaign).count()
            campaign.status = CampaignStatus.EXPIRED
            campaign.save(update_fields=['status', 'updated_at'])
            self.stdout.write(
                f"  expired  {campaign.coupon_code:16s} "
                f"(coupons issued: {audience}, redemptions: "
                f"{campaign.redemptions.count()}; history kept)")
        if seed_labels:
            self.stdout.write('  (the previous rule-segment campaigns are also '
                              'expired above; a customer now only ever sees the '
                              'offer of their own K-Means group)')

    # ------------------------------------------------------ real product data

    def _load_catalog(self):
        products = list(Product.objects.filter(is_active=True)
                        .order_by('product_id'))
        price_map = get_product_selling_price_map(p.product_id for p in products)
        priced = [p for p in products if float(price_map.get(str(p.product_id)) or 0) > 0]
        by_id = {str(p.product_id): p for p in priced}
        ids = [str(p.product_id) for p in priced]

        # Stable, deterministic slices for the "selected products" offers.
        slices = {'slice_a': ids[0:6], 'slice_b': ids[6:12]}

        # Combos: prefer real best sellers (units_sold), fall back to the
        # deterministic catalogue order if the analytics table is unavailable.
        ordered_ids = self._top_seller_ids(fallback=ids)
        combo_pool = [by_id[i] for i in ordered_ids if i in by_id]
        combos = []
        for start in range(0, 15, 3):
            chunk = combo_pool[start:start + 3]
            if len(chunk) < 3:
                continue
            gross = sum(float(price_map.get(str(p.product_id))) for p in chunk)
            combos.append({
                'product_ids': [str(p.product_id) for p in chunk],
                'bundle_price': _round_rupee(gross * 0.8),
            })
        while len(combos) < 5:  # extremely small catalogues: reuse order slices
            chunk = priced[len(combos) * 3:len(combos) * 3 + 3]
            if len(chunk) < 3:
                break
            gross = sum(float(price_map.get(str(p.product_id))) for p in chunk)
            combos.append({
                'product_ids': [str(p.product_id) for p in chunk],
                'bundle_price': _round_rupee(gross * 0.8),
            })

        # Gifts: five distinct real, low-priced items.
        cheapest = sorted(priced, key=lambda p: (float(price_map.get(str(p.product_id))),
                                                 str(p.product_id)))
        gifts = [{'name': f'Complimentary {p.product_name or p.product_id}',
                  'price': _round_rupee(float(price_map.get(str(p.product_id))))}
                 for p in cheapest[:5]]

        # Categories: the two most common main categories in the live catalog,
        # counted CASE/WHITESPACE-INSENSITIVELY so "Dress"/"dress" form one.
        from catalog.normalize import normalize_category
        counts = {}
        displays = {}
        for p in priced:
            key = normalize_category(p.main_category)
            if key:
                counts[key] = counts.get(key, 0) + 1
                displays.setdefault(key, (p.main_category or '').strip())
        categories = [displays[c] for c, _n in sorted(counts.items(),
                                                       key=lambda kv: (-kv[1], kv[0]))][:2]

        if len(combos) < 5 or len(gifts) < 5 or not categories:
            raise RuntimeError('Live catalog too small to seed combos/gifts/categories')
        return {'priced': priced, 'ids': slices, 'combos': combos,
                'gifts': gifts, 'categories': categories}

    @staticmethod
    def _top_seller_ids(fallback):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT product_key FROM public.fact_product_analysis
                    WHERE units_sold IS NOT NULL AND units_sold > 0
                    ORDER BY units_sold DESC, product_key ASC
                    """
                )
                ranked = [str(row[0]) for row in cursor.fetchall()]
            merged = ranked + [i for i in fallback if i not in set(ranked)]
            return merged
        except Exception:
            return list(fallback)


def _bundle(combos, index):
    combo = combos[index]
    return {'offer_category': OfferCategory.BUY_GET, 'discount_rule': {},
            'buy_get_rule': {'type': 'BUNDLE',
                             'bundle_price': combo['bundle_price'],
                             'product_ids': combo['product_ids']}}


def _gift(gifts, index, min_order):
    return {'offer_category': OfferCategory.BUY_GET, 'discount_rule': {},
            'usage_type': 'ONCE',
            'buy_get_rule': {'type': 'FREE_GIFT', 'gift_name': gifts[index]['name'],
                             'gift_value': gifts[index]['price'],
                             'min_order_amount': min_order}}
