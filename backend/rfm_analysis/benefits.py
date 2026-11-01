"""Checkout-benefit computation for every supported offer type.

A campaign's offer is described by up to two structured rules (persisted as
JSON on `Campaign`):

* ``discount_rule`` – the monetary offer. Shapes per ``type``::

    {'type': 'PERCENTAGE', 'percent': 15}
    {'type': 'FLAT', 'flat': 200}
    {'type': 'SPEND_BASED', 'spend_threshold': 3000, 'spend_discount': 300}
    {'type': 'BUY_MORE_SAVE_MORE', 'tiers': [{'buy': 2, 'percent': 10},
                                             {'buy': 3, 'percent': 20}]}
    {'type': 'CASHBACK', 'cashback': 200}
    {'type': 'FREE_SHIPPING'}

* ``buy_get_rule`` – the quantity / product-based offer. Shapes per ``type``::

    {'type': 'BUY_X_GET_Y_FREE', 'buy_qty': 2, 'get_qty': 1}
    {'type': 'BUY_X_GET_Y_DISCOUNT', 'buy_qty': 2, 'get_qty': 1,
     'discount_percent': 50}
    {'type': 'BOGO'}                                  # Buy 1 Get 1 Free
    {'type': 'BUNDLE', 'bundle_price': 999, 'product_ids': ['p1','p2','p3']}
    {'type': 'FREE_GIFT', 'gift_name': 'Scarf', 'gift_value': 499}
    {'type': 'PRODUCT_DISCOUNT', 'discount_percent': 25}
    {'type': 'PRODUCT_DISCOUNT', 'discount_flat': 150}

* ``scope`` – which cart lines an offer applies to::

    {'mode': 'ALL'}
    {'mode': 'PRODUCTS', 'product_ids': [...]}
    {'mode': 'CATEGORIES', 'categories': [...]}

Everything is computed from server-side cart lines (product id, quantity,
authoritative unit price) – never from a client-supplied total. Monetary
benefits can never exceed the cart value, cashback is credited after purchase
(so it never reduces the payable), free shipping only flags the checkout, and
a free gift is an added item, not a discount. For COMBINED campaigns the
admin decides via ``benefits_combinable`` whether both benefits stack or only
the better one is granted, which prevents unintended double discounts.
"""

from .models import OfferCategory

DISCOUNT_TYPES = {'PERCENTAGE', 'FLAT', 'SPEND_BASED', 'BUY_MORE_SAVE_MORE',
                  'CASHBACK', 'FREE_SHIPPING'}
BUY_GET_TYPES = {'BUY_X_GET_Y_FREE', 'BUY_X_GET_Y_DISCOUNT', 'BOGO',
                 'BUNDLE', 'FREE_GIFT', 'PRODUCT_DISCOUNT'}
SCOPE_MODES = {'ALL', 'PRODUCTS', 'CATEGORIES'}

EMPTY_BENEFITS = {'discount': 0.0, 'cashback': 0.0, 'free_shipping': False,
                  'gift': None}


def _round(value):
    return round(float(value or 0), 2)


def normalise_line(line):
    """Coerce one cart line into the shape every calculator expects."""
    return {
        'product_id': str(line.get('product_id') or ''),
        'name': line.get('name') or '',
        'category': line.get('category') or '',
        'quantity': max(int(line.get('quantity') or 0), 0),
        'unit_price': _round(line.get('unit_price')),
    }


def lines_subtotal(lines):
    return _round(sum(l['unit_price'] * l['quantity'] for l in lines))


def in_scope(line, scope):
    mode = (scope or {}).get('mode') or 'ALL'
    if mode == 'PRODUCTS':
        return line['product_id'] in {str(p) for p in (scope.get('product_ids') or [])}
    if mode == 'CATEGORIES':
        wanted = {str(c).strip().lower() for c in (scope.get('categories') or [])}
        return str(line['category'] or '').strip().lower() in wanted
    return True


def scoped_lines(lines, scope):
    return [l for l in lines if in_scope(l, scope)]


def _units(lines):
    """Flatten scoped lines into unit prices, most expensive first.

    Buy-X-Get-Y grouping works on individual units: within each group of
    ``buy + get`` units the cheapest ``get`` ones are the free/discounted
    ones, which is what "get" means on a mixed bag of products.
    """
    prices = []
    for line in lines:
        prices.extend([line['unit_price']] * line['quantity'])
    return sorted(prices, reverse=True)


# ---------------------------------------------------------------------------
# Discount-offer family
# ---------------------------------------------------------------------------

def discount_benefit(rule, lines, subtotal, max_discount=None):
    """Return {discount, cashback, free_shipping, label} for a discount rule."""
    result = dict(EMPTY_BENEFITS, label='')
    if not rule or not rule.get('type'):
        return result
    kind = rule['type']
    scoped = _round(lines_subtotal(scoped_lines(lines, rule.get('_scope')))
                    if rule.get('_scope') else subtotal)

    if kind == 'PERCENTAGE':
        percent = float(rule.get('percent') or 0)
        discount = scoped * (percent / 100.0)
        if max_discount is not None:
            discount = min(discount, float(max_discount))
        result['discount'] = discount
        result['label'] = f"{_trim(percent)}% OFF"
    elif kind == 'FLAT':
        result['discount'] = float(rule.get('flat') or 0)
        result['label'] = f"₹{_trim(rule.get('flat'))} OFF"
    elif kind == 'SPEND_BASED':
        threshold = float(rule.get('spend_threshold') or 0)
        off = float(rule.get('spend_discount') or 0)
        if subtotal >= threshold:
            result['discount'] = off
        result['label'] = f"Spend ₹{_trim(threshold)}, get ₹{_trim(off)} OFF"
    elif kind == 'BUY_MORE_SAVE_MORE':
        units = sum(l['quantity'] for l in scoped_lines(lines, rule.get('_scope')))
        best = None
        for tier in (rule.get('tiers') or []):
            buy = int(tier.get('buy') or 0)
            if buy and units >= buy:
                if best is None or buy > int(best.get('buy') or 0):
                    best = tier
        if best:
            result['discount'] = scoped * (float(best.get('percent') or 0) / 100.0)
            if max_discount is not None:
                result['discount'] = min(result['discount'], float(max_discount))
        result['label'] = _bmsm_label(rule.get('tiers') or [])
    elif kind == 'CASHBACK':
        # Cashback is credited after purchase: it never reduces the payable.
        result['cashback'] = float(rule.get('cashback') or 0)
        result['label'] = f"₹{_trim(rule.get('cashback'))} cashback"
    elif kind == 'FREE_SHIPPING':
        result['free_shipping'] = True
        result['label'] = 'Free shipping'
    result['discount'] = _round(result['discount'])
    result['cashback'] = _round(result['cashback'])
    return result


def _bmsm_label(tiers):
    parts = [f"Buy {t.get('buy')} save {_trim(t.get('percent'))}%"
             for t in sorted(tiers, key=lambda t: int(t.get('buy') or 0))]
    return ', '.join(parts)


# ---------------------------------------------------------------------------
# Buy & Get-offer family
# ---------------------------------------------------------------------------

def buy_get_benefit(rule, lines, subtotal):
    """Return {discount, gift, label} for a Buy & Get rule."""
    result = dict(EMPTY_BENEFITS, gift=None, label='')
    if not rule or not rule.get('type'):
        return result
    kind = rule['type']
    scoped = scoped_lines(lines, rule.get('_scope'))
    scope_subtotal = _round(lines_subtotal(scoped))

    if kind == 'BOGO':
        rule = dict(rule, type='BUY_X_GET_Y_FREE', buy_qty=1, get_qty=1)
        kind = 'BUY_X_GET_Y_FREE'

    if kind in ('BUY_X_GET_Y_FREE', 'BUY_X_GET_Y_DISCOUNT'):
        buy = int(rule.get('buy_qty') or 0)
        get = int(rule.get('get_qty') or 0)
        percent = float(rule.get('discount_percent') or 0)
        groups = _group_free_units(_units(scoped), buy, get)
        if kind == 'BUY_X_GET_Y_FREE':
            result['discount'] = sum(price for price in groups)
        else:
            result['discount'] = sum(price * percent / 100.0 for price in groups)
        if kind == 'BUY_X_GET_Y_FREE' and buy == 1 and get == 1:
            result['label'] = 'Buy 1 Get 1 Free'
        elif kind == 'BUY_X_GET_Y_FREE':
            result['label'] = f'Buy {buy} Get {get} Free'
        else:
            result['label'] = f'Buy {buy} Get {get} at {_trim(percent)}% OFF'
    elif kind == 'BUNDLE':
        result.update(_bundle_benefit(rule, scoped, lines))
    elif kind == 'FREE_GIFT':
        minimum = float(rule.get('min_order_amount') or 0)
        if subtotal >= minimum:
            result['gift'] = {
                'name': str(rule.get('gift_name') or 'Free gift'),
                'value': _round(rule.get('gift_value')),
            }
        minimum_text = f' on orders above ₹{_trim(minimum)}' if minimum else ''
        result['label'] = f"Free gift{minimum_text}"
    elif kind == 'PRODUCT_DISCOUNT':
        percent = float(rule.get('discount_percent') or 0)
        flat = float(rule.get('discount_flat') or 0)
        if percent:
            result['discount'] = scope_subtotal * (percent / 100.0)
            result['label'] = f"{_trim(percent)}% OFF on {_scope_label(rule)}"
        else:
            units = sum(l['quantity'] for l in scoped)
            result['discount'] = flat * units
            result['label'] = f"₹{_trim(flat)} OFF per item on {_scope_label(rule)}"
    # A gift or a bundle saving can never exceed what the cart is actually worth.
    result['discount'] = _round(max(0.0, min(result['discount'], subtotal)))
    return result


def _group_free_units(unit_prices, buy, get):
    """Prices of the units the customer gets free/discounted.

    Units are already sorted most-expensive-first; they are processed in
    groups of ``buy + get`` and the (cheapest) trailing ``get`` of every full
    group is the rewarded unit.
    """
    if buy < 1 or get < 1:
        return []
    group = buy + get
    rewarded = []
    for index, price in enumerate(unit_prices):
        if index % group >= buy:
            rewarded.append(price)
    return rewarded


def _bundle_benefit(rule, scoped, lines):
    """All bundle products present -> they are repriced to the bundle price."""
    wanted = [str(p) for p in (rule.get('product_ids') or [])]
    bundle_price = float(rule.get('bundle_price') or 0)
    present = {l['product_id']: l for l in scoped}
    if not wanted or bundle_price <= 0 or any(p not in present for p in wanted):
        return {'discount': 0.0, 'label': f'Bundle of {len(wanted)} for ₹{_trim(bundle_price)}'}
    # One unit per bundle product is the bundled set; extra units stay at list price.
    gross = _round(sum(present[p]['unit_price'] for p in wanted))
    return {
        'discount': max(0.0, gross - bundle_price),
        'label': f'Bundle of {len(wanted)} for ₹{_trim(bundle_price)}',
    }


def _scope_label(rule):
    scope = rule.get('_scope') or {}
    if (scope.get('mode') or 'ALL') == 'ALL':
        return 'all products'
    return 'selected products'


# ---------------------------------------------------------------------------
# Campaign-level resolution
# ---------------------------------------------------------------------------

def _with_scope(rule, scope):
    """Shallow-copy a rule and pin the campaign's product scope into it."""
    if not rule:
        return None
    rule = dict(rule)
    rule['_scope'] = scope or {'mode': 'ALL'}
    return rule


def compute_benefits(campaign, lines, subtotal):
    """Every benefit a campaign grants against these (server-side) cart lines.

    Falls back to the legacy flat/percentage fields when a campaign carries no
    structured rules, so campaigns authored before this upgrade keep working.
    """
    subtotal = _round(subtotal)
    lines = [normalise_line(l) for l in (lines or [])]

    discount = dict(EMPTY_BENEFITS, label='')
    buy_get = dict(EMPTY_BENEFITS, gift=None, label='')

    if campaign.discount_rule or campaign.buy_get_rule:
        if campaign.discount_rule:
            discount = discount_benefit(_with_scope(campaign.discount_rule, campaign.scope),
                                        lines, subtotal,
                                        float(campaign.max_discount)
                                        if campaign.max_discount is not None else None)
        if campaign.buy_get_rule:
            buy_get = buy_get_benefit(_with_scope(campaign.buy_get_rule, campaign.scope),
                                      lines, subtotal)
    else:
        discount = _legacy_benefit(campaign, subtotal)

    if (campaign.offer_category == OfferCategory.COMBINED
            and campaign.benefits_combinable):
        # Admin explicitly allowed both halves to apply to one checkout.
        total_discount = _round(max(
            0.0, min(discount['discount'] + buy_get['discount'], subtotal)))
        cashback = discount['cashback']
        free_shipping = discount['free_shipping']
        gift = buy_get['gift']
    else:
        # Single-benefit campaign, or a COMBINED campaign configured as
        # best-of: the customer is granted whichever half is worth more, so
        # two benefits can never stack by accident (no double discounts).
        discount_side = discount['discount'] + discount['cashback']
        buy_get_side = buy_get['discount'] + (
            float(buy_get['gift']['value']) if buy_get['gift'] else 0.0)
        if discount_side >= buy_get_side:
            total_discount = _round(max(0.0, min(discount['discount'], subtotal)))
            cashback = discount['cashback']
            free_shipping = discount['free_shipping']
            gift = None
        else:
            total_discount = _round(max(0.0, min(buy_get['discount'], subtotal)))
            cashback = 0.0
            free_shipping = False
            gift = buy_get['gift']

    labels = [label for label in (discount['label'], buy_get['label']) if label]
    return {
        'discount': total_discount,
        'cashback': _round(cashback),
        'free_shipping': bool(free_shipping),
        'gift': gift,
        'benefit_applied': bool(total_discount > 0 or cashback > 0
                                or free_shipping or gift),
        'benefit_labels': labels,
    }


def _legacy_benefit(campaign, subtotal):
    """Pre-upgrade campaigns: plain percentage/fixed off the whole cart."""
    from .models import DiscountType
    value = float(campaign.discount_value or 0)
    result = dict(EMPTY_BENEFITS)
    if campaign.discount_type == DiscountType.PERCENTAGE:
        discount = subtotal * (value / 100.0)
        if campaign.max_discount is not None:
            discount = min(discount, float(campaign.max_discount))
        label = f"{_trim(value)}% OFF"
    else:
        discount = value
        label = f"₹{_trim(value)} OFF"
    result['discount'] = _round(max(0.0, min(discount, subtotal)))
    result['label'] = label
    return result


def _trim(value):
    """₹200.00 -> 200, 12.50 -> 12.5 (labels should read like a human wrote them)."""
    number = float(value or 0)
    return str(int(number)) if number == int(number) else f"{number:g}"


def offer_summary(campaign):
    """One-line human description of what a campaign actually offers.

    Used identically by the admin list, the campaign preview and the customer
    offer cards, so all three surfaces always describe an offer the same way.
    """
    parts = []
    scope_note = _scope_note(campaign)
    if campaign.discount_rule:
        parts.append(_rule_summary(campaign.discount_rule))
    elif (not campaign.buy_get_rule
          or campaign.offer_category != OfferCategory.BUY_GET):
        # Legacy mirror values (also covers a DISCOUNT campaign authored
        # before the structured rules existed).
        from .models import DiscountType
        if campaign.discount_value and campaign.discount_type == DiscountType.PERCENTAGE:
            parts.append(f"{_trim(campaign.discount_value)}% OFF")
        elif campaign.discount_value:
            parts.append(f"₹{_trim(campaign.discount_value)} OFF")
    if campaign.buy_get_rule:
        parts.append(_rule_summary(campaign.buy_get_rule))
    if not parts:
        return ''
    summary = ' + '.join(p for p in parts if p)
    if scope_note and campaign.buy_get_rule:
        summary += f' ({scope_note})'
    if campaign.min_order_amount:
        summary += f' • Min order ₹{_trim(campaign.min_order_amount)}'
    return summary


def _scope_note(campaign):
    scope = campaign.scope or {}
    mode = scope.get('mode') or 'ALL'
    if mode == 'PRODUCTS':
        return 'on selected products'
    if mode == 'CATEGORIES':
        cats = scope.get('categories') or []
        return f"on {', '.join(str(c) for c in cats[:3])}" if cats else ''
    return ''


def _rule_summary(rule):
    kind = (rule or {}).get('type') or ''
    if kind == 'PERCENTAGE':
        return f"{_trim(rule.get('percent'))}% OFF"
    if kind == 'FLAT':
        return f"₹{_trim(rule.get('flat'))} OFF"
    if kind == 'SPEND_BASED':
        return f"Spend ₹{_trim(rule.get('spend_threshold'))} get ₹{_trim(rule.get('spend_discount'))} OFF"
    if kind == 'BUY_MORE_SAVE_MORE':
        return _bmsm_label(rule.get('tiers') or [])
    if kind == 'CASHBACK':
        return f"₹{_trim(rule.get('cashback'))} cashback"
    if kind == 'FREE_SHIPPING':
        return 'Free shipping'
    if kind == 'BOGO':
        return 'Buy 1 Get 1 Free'
    if kind == 'BUY_X_GET_Y_FREE':
        return f"Buy {_trim(rule.get('buy_qty'))} Get {_trim(rule.get('get_qty'))} Free"
    if kind == 'BUY_X_GET_Y_DISCOUNT':
        return (f"Buy {_trim(rule.get('buy_qty'))} Get {_trim(rule.get('get_qty'))}"
                f" at {_trim(rule.get('discount_percent'))}% OFF")
    if kind == 'BUNDLE':
        n = len(rule.get('product_ids') or [])
        return f"Bundle of {n} for ₹{_trim(rule.get('bundle_price'))}"
    if kind == 'FREE_GIFT':
        minimum = float(rule.get('min_order_amount') or 0)
        base = f"Free gift: {rule.get('gift_name') or 'gift'}"
        return f"{base} on orders above ₹{_trim(minimum)}" if minimum else base
    if kind == 'PRODUCT_DISCOUNT':
        if rule.get('discount_percent'):
            return f"{_trim(rule.get('discount_percent'))}% OFF on eligible items"
        return f"₹{_trim(rule.get('discount_flat'))} OFF on eligible items"
    return ''
