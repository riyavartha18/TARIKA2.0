"""Seed the 30 predefined segment campaigns into the existing campaign system.

Nothing here invents data: every product id, product name, category, price and
bundle comes from the live `public.products` table (combos prefer real best
sellers from `fact_product_analysis`), and each offer is expressed through the
same structured rule shapes the CampaignSerializer / benefits engine already
validate and price. Re-running the command updates the same rows (matched by a
deterministic coupon code) instead of creating duplicates, and it never
re-publishes a campaign an admin has paused.

Usage:
    python manage.py seed_segment_campaigns [--replace-existing]

`--replace-existing` archives the pre-existing campaigns once: rows with
redemption history are kept but marked EXPIRED (history preserved), rows
without any redemptions are deleted. Admin campaigns created later are never
touched by a plain re-run.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from catalog.models import Product
from catalog.pricing import get_product_selling_price_map
from rfm_analysis import cache_manager, utils
from rfm_analysis.models import Campaign, CampaignStatus, OfferCategory
from rfm_analysis.serializers import CampaignSerializer

VALIDITY_DAYS = 90


def _round_rupee(value):
    return float(int(round(value)))


class Command(BaseCommand):
    help = 'Create/refresh the predefined RFM segment campaigns (active).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace-existing', action='store_true',
            help='Archive/delete campaigns that are not part of the '
                 'predefined set (redemption history is always preserved).')

    # ------------------------------------------------------------------ main

    def handle(self, *args, **options):
        now = timezone.now()
        catalog = self._load_catalog()
        if len(catalog['priced']) < 24:
            self.stderr.write('Not enough priced, active products to seed '
                              f"product-scoped offers (found {len(catalog['priced'])}).")
            return

        definitions = self._campaign_definitions(now, catalog)
        codes = {d['coupon_code'] for d in definitions}

        if options['replace_existing']:
            self._retire_other_campaigns(codes)

        created = updated = drafted = 0
        for definition in definitions:
            outcome = self._upsert(definition, now)
            if outcome == 'created':
                created += 1
            elif outcome == 'updated':
                updated += 1
            else:
                drafted += 1
            self.stdout.write(f"  {outcome:8s} {definition['coupon_code']:14s} "
                              f"[{definition['target_segments'][0]}] {definition['name']}")

        self.stdout.write(self.style.SUCCESS(
            f'Segment campaigns ready: {created} created, {updated} updated, '
            f'{drafted} draft-only (no redeemable checkout benefit exists for it).'))
        # Cached customer offer lists are keyed on this epoch, so the newly
        # published campaigns are visible to customers on their next request.
        cache_manager.bump_campaign_epoch()

    # ------------------------------------------------------- campaign catalog

    def _campaign_definitions(self, now, catalog):
        start = now - timedelta(minutes=1)
        end = now + timedelta(days=VALIDITY_DAYS)
        champ, loyal = utils.SEGMENT_CHAMPIONS, utils.SEGMENT_LOYAL
        potential, new = utils.SEGMENT_POTENTIAL_LOYALISTS, utils.SEGMENT_NEW
        risk, hib = utils.SEGMENT_AT_RISK, utils.SEGMENT_HIBERNATING

        ids = catalog['ids']
        combos = catalog['combos']        # four 3-product real combos, priced
        gifts = catalog['gifts']          # five distinct low-price real items
        categories = catalog['categories']

        def base(segment, name, code, description):
            return {
                'name': name, 'coupon_code': code, 'description': description,
                'target_segments': [segment], 'target_tags': [],
                'start_date': start, 'end_date': end,
                'min_order_amount': 0, 'max_discount': None,
                'usage_type': 'UNLIMITED', 'per_customer_limit': 0,
                'global_usage_limit': 0, 'stacking_allowed': False,
                'scope': {'mode': 'ALL'}, 'benefits_combinable': False,
            }

        def buy_get(c, rule, scope=None, usage='UNLIMITED'):
            c.update(offer_category=OfferCategory.BUY_GET, discount_rule={},
                     buy_get_rule=rule, usage_type=usage)
            if scope:
                c['scope'] = scope
            return c

        def discount(c, rule, **overrides):
            c.update(offer_category=OfferCategory.DISCOUNT, discount_rule=rule,
                     buy_get_rule={}, **overrides)
            return c

        selected_scope = lambda product_ids: {  # noqa: E731
            'mode': 'PRODUCTS', 'product_ids': product_ids}

        defs = [
            # ------------------------------------------------ Champions
            buy_get(base(champ, 'Champions: Buy 2 Get 1 Free',
                         'CHAMP_B2G1', 'Buy any 2 of the selected VIP products, get 1 free.'),
                    {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
                    scope=selected_scope(ids['champions'])),
            buy_get(base(champ, 'Champions: Exclusive VIP Gift',
                         'CHAMP_GIFT', 'A complimentary gift with every order above Rs.3,000.'),
                    {'type': 'FREE_GIFT', 'gift_name': gifts[0]['name'],
                     'gift_value': gifts[0]['price'], 'min_order_amount': 3000},
                    usage='ONCE'),
            discount(base(champ, 'Champions: VIP 15% OFF',
                          'CHAMP_VIP15', 'An exclusive 15% discount for our Champions.'),
                     {'type': 'PERCENTAGE', 'percent': 15}),
            buy_get(base(champ, 'Champions: Premium Combo Deals',
                         'CHAMP_COMBO', 'Premium product combinations at a VIP price.'),
                    {'type': 'BUNDLE', 'bundle_price': combos[4]['bundle_price'],
                     'product_ids': combos[4]['product_ids']}),
            self._early_access_definition(base(champ, 'Champions: Early Access to New Collections',
                                               'CHAMP_EARLY',
                                               'Announcement-only offer: early access to new '
                                               'collections. No checkout coupon benefit is '
                                               'configured, so this campaign stays a draft '
                                               'until an early-access mechanism exists.')),

            # ------------------------------------------------ Loyal Customers
            buy_get(base(loyal, 'Loyal Customers: Buy 2 Get 1 at 50% OFF',
                         'LOYAL_B2G50', 'Buy 2 items, get the third at half price.'),
                    {'type': 'BUY_X_GET_Y_DISCOUNT', 'buy_qty': 2, 'get_qty': 1,
                     'discount_percent': 50}),
            discount(base(loyal, 'Loyal Customers: Buy 3 Save 20%',
                          'LOYAL_B3S20', 'Any 3 items in the bag: 20% off.'),
                     {'type': 'BUY_MORE_SAVE_MORE', 'tiers': [{'buy': 3, 'percent': 20}]}),
            discount(base(loyal, 'Loyal Customers: Free Shipping',
                          'LOYAL_FSHIP', 'Free delivery on orders above Rs.1,499.'),
                     {'type': 'FREE_SHIPPING'}, min_order_amount=1499),
            discount(base(loyal, 'Loyal Customers: Rs.200 Cashback',
                          'LOYAL_CASH200', 'Rs.200 cashback credited after delivery on '
                                            'orders above Rs.2,000.'),
                     {'type': 'CASHBACK', 'cashback': 200},
                     min_order_amount=2000, usage_type='ONCE'),
            buy_get(base(loyal, 'Loyal Customers: Frequently Bought Combo',
                         'LOYAL_COMBO', 'Our three most-bought pieces at a special combo price.'),
                    {'type': 'BUNDLE', 'bundle_price': combos[0]['bundle_price'],
                     'product_ids': combos[0]['product_ids']}),

            # ------------------------------------------------ Potential Loyalists
            buy_get(base(potential, 'Potential Loyalists: Buy 2 Get 1 Free',
                         'POT_B2G1', 'Buy 2 of the selected styles, get 1 free.'),
                    {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
                    scope=selected_scope(ids['potential'])),
            discount(base(potential, 'Potential Loyalists: Buy 2 Save 15%',
                          'POT_B2S15', 'Two items in the bag: 15% off.'),
                     {'type': 'BUY_MORE_SAVE_MORE', 'tiers': [{'buy': 2, 'percent': 15}]}),
            discount(base(potential, 'Potential Loyalists: Rs.150 OFF Next Order',
                          'POT_FLAT150', 'Flat Rs.150 off any order above Rs.999.'),
                     {'type': 'FLAT', 'flat': 150}, min_order_amount=999),
            buy_get(base(potential, 'Potential Loyalists: Free Gift',
                         'POT_GIFT', 'A complimentary gift on orders above Rs.1,499.'),
                    {'type': 'FREE_GIFT', 'gift_name': gifts[1]['name'],
                     'gift_value': gifts[1]['price'], 'min_order_amount': 1499},
                    usage='ONCE'),
            # PRODUCT_DISCOUNT is a Buy & Get rule type, and the campaign's
            # scope narrows it to the two most-populated live categories.
            buy_get(base(potential, 'Potential Loyalists: Category Combo Discount',
                         'POT_COMBO', f'15% off {", ".join(categories)} styles.'),
                    {'type': 'PRODUCT_DISCOUNT', 'discount_percent': 15},
                    scope={'mode': 'CATEGORIES', 'categories': categories}),

            # ------------------------------------------------ New Customers
            discount(base(new, 'New Customers: 10% OFF Second Order',
                          'NEW_10OFF', 'A thank-you discount on the next order, '
                                       'for our newest customers.'),
                     {'type': 'PERCENTAGE', 'percent': 10}),
            buy_get(base(new, 'New Customers: Buy 2 Get 1 Free',
                         'NEW_B2G1', 'Buy 2 of the selected starter pieces, get 1 free.'),
                    {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1},
                    scope=selected_scope(ids['new'])),
            buy_get(base(new, 'New Customers: Free Welcome Gift',
                         'NEW_GIFT', 'A complimentary welcome gift with the next order.'),
                    {'type': 'FREE_GIFT', 'gift_name': gifts[2]['name'],
                     'gift_value': gifts[2]['price'], 'min_order_amount': 0},
                    usage='ONCE'),
            discount(base(new, 'New Customers: Free Shipping',
                          'NEW_FSHIP', 'Free delivery on the next purchase.'),
                     {'type': 'FREE_SHIPPING'}),
            buy_get(base(new, 'New Customers: First Combo at Special Price',
                         'NEW_COMBO', 'Three hand-picked pieces at a starter combo price.'),
                    {'type': 'BUNDLE', 'bundle_price': combos[1]['bundle_price'],
                     'product_ids': combos[1]['product_ids']}),

            # ------------------------------------------------ At-Risk
            discount(base(risk, 'At-Risk: 20% OFF Comeback',
                          'RISK_20OFF', 'Flat 20% off, up to Rs.500 — we miss you.'),
                     {'type': 'PERCENTAGE', 'percent': 20}, max_discount=500),
            buy_get(base(risk, 'At-Risk: Buy 2 Get 1 Free',
                         'RISK_B2G1', 'Buy any 2 items, get 1 free.'),
                    {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1}),
            discount(base(risk, 'At-Risk: Rs.300 Cashback',
                          'RISK_CASH300', 'Rs.300 cashback credited after delivery on '
                                           'orders above Rs.1,999.'),
                     {'type': 'CASHBACK', 'cashback': 300},
                     min_order_amount=1999, usage_type='ONCE'),
            buy_get(base(risk, 'At-Risk: Comeback Combo',
                         'RISK_COMBO', 'A three-piece favourite combo at a comeback price.'),
                    {'type': 'BUNDLE', 'bundle_price': combos[2]['bundle_price'],
                     'product_ids': combos[2]['product_ids']}),
            buy_get(base(risk, 'At-Risk: Free Gift on Return',
                         'RISK_GIFT', 'A complimentary gift with your return order.'),
                    {'type': 'FREE_GIFT', 'gift_name': gifts[3]['name'],
                     'gift_value': gifts[3]['price'], 'min_order_amount': 0},
                    usage='ONCE'),

            # ------------------------------------------------ Hibernating
            buy_get(base(hib, 'Hibernating: Buy 1 Get 1 Free',
                         'HIB_BOGO', 'Buy one of the selected pieces, get another free.'),
                    {'type': 'BOGO'}, scope=selected_scope(ids['hibernating'])),
            discount(base(hib, 'Hibernating: 25% OFF',
                          'HIB_25OFF', '25% off, up to Rs.400 — come back and browse.'),
                     {'type': 'PERCENTAGE', 'percent': 25}, max_discount=400),
            buy_get(base(hib, 'Hibernating: Buy 2 Get 1 Free',
                         'HIB_B2G1', 'Buy any 2 items, get 1 free.'),
                    {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1}),
            buy_get(base(hib, 'Hibernating: Free Comeback Gift',
                         'HIB_GIFT', 'A complimentary gift with your comeback order.'),
                    {'type': 'FREE_GIFT', 'gift_name': gifts[4]['name'],
                     'gift_value': gifts[4]['price'], 'min_order_amount': 0},
                    usage='ONCE'),
            buy_get(base(hib, 'Hibernating: Reactivation Combo',
                         'HIB_COMBO', 'A three-piece combo at a special reactivation price.'),
                    {'type': 'BUNDLE', 'bundle_price': combos[3]['bundle_price'],
                     'product_ids': combos[3]['product_ids']}),
        ]
        return defs

    @staticmethod
    def _early_access_definition(base):
        """Announcement-only campaign: it has no redeemable checkout benefit,
        so it is created (and stays) a DRAFT instead of a fake "active" offer."""
        return dict(base, _draft_only=True, offer_category=OfferCategory.DISCOUNT,
                    discount_rule={}, buy_get_rule={})

    # ------------------------------------------------------------ upsert logic

    def _upsert(self, definition, now):
        draft_only = definition.pop('_draft_only', False)
        coupon_code = definition['coupon_code']
        existing = Campaign.objects.filter(coupon_code=coupon_code).first()

        if draft_only:
            if existing:
                return 'unchanged'
            Campaign.objects.create(
                name=definition['name'], coupon_code=coupon_code,
                description=definition['description'],
                offer_category=OfferCategory.DISCOUNT,
                discount_rule={}, buy_get_rule={}, scope=definition['scope'],
                target_segments=definition['target_segments'], target_tags=[],
                start_date=definition['start_date'], end_date=definition['end_date'],
                usage_type=definition['usage_type'],
                status=CampaignStatus.DRAFT,
            )
            return 'drafted'

        payload = dict(definition)
        if existing:
            # An admin may have paused this campaign deliberately: refresh the
            # configuration and, when the window is about to lapse, extend it,
            # but never force a paused/expired campaign back to Published.
            if existing.end_date < now + timedelta(days=7):
                payload['start_date'] = now - timedelta(minutes=1)
                payload['end_date'] = now + timedelta(days=VALIDITY_DAYS)
            serializer = CampaignSerializer(existing, data=payload, partial=True)
            action = 'updated'
        else:
            payload['status'] = CampaignStatus.PUBLISHED   # activate on first seed
            serializer = CampaignSerializer(data=payload)
            action = 'created'

        if not serializer.is_valid():
            self.stderr.write(f"  REJECTED {coupon_code}: {serializer.errors}")
            return 'failed'
        serializer.save()
        return action

    # ------------------------------------------------------- legacy cleanup

    def _retire_other_campaigns(self, seed_codes):
        """Remove/archive campaign rows outside the predefined set."""
        for campaign in Campaign.objects.exclude(coupon_code__in=seed_codes):
            if campaign.redemptions.exists():
                # History must survive: archive instead of delete.
                if campaign.status != CampaignStatus.EXPIRED:
                    campaign.status = CampaignStatus.EXPIRED
                    campaign.save(update_fields=['status', 'updated_at'])
                    self.stdout.write(f"  archived {campaign.coupon_code} "
                                      f"(redemption history preserved)")
            else:
                campaign.delete()
                self.stdout.write(f"  deleted  {campaign.coupon_code} (no history)")

    # ------------------------------------------------------ real product data

    def _load_catalog(self):
        products = list(Product.objects.filter(is_active=True)
                        .order_by('product_id'))
        price_map = get_product_selling_price_map(p.product_id for p in products)
        priced = [p for p in products if float(price_map.get(str(p.product_id)) or 0) > 0]
        by_id = {str(p.product_id): p for p in priced}
        ids = [str(p.product_id) for p in priced]

        # Stable, deterministic slices for the "selected products" offers.
        slices = {
            'champions': ids[0:6],
            'new': ids[6:12],
            'potential': ids[12:18],
            'hibernating': ids[18:24],
        }

        # Combos: prefer real best sellers (units_sold), fall back to the
        # deterministic catalogue order if the analytics table is unavailable.
        ordered_ids = self._top_seller_ids(fallback=ids)
        combo_pool = [by_id[i] for i in ordered_ids if i in by_id]
        combos = []
        for chunk in (combo_pool[0:3], combo_pool[3:6], combo_pool[6:9], combo_pool[9:12],
                      combo_pool[12:15]):
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
