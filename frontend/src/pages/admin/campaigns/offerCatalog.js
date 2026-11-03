// Shared vocabulary for the Campaigns module: the two offer families, their
// simple human-readable options, the K-Means customer groups and the payload
// <-> form mapping. Everything here mirrors the backend rules in rfm_analysis
// (benefits.py, serializers.py, cluster_targeting.py); nothing customer- or
// campaign-specific is hardcoded - the four groups, their labels, their ids and
// their counts always come from the persisted clustering run through the API.

export const PALETTE = {
  ink: '#1F191B', muted: '#6B5E63', faint: '#9E8F94',
  rose: '#D8727E', roseDeep: '#B8505E', border: '#F0E2E0', bg: '#FFFFFF',
};

// Which segmentation a campaign's audience was chosen from. Campaign targeting
// uses the four K-Means groups; `LEGACY_RFM` only ever marks a historical row so
// the page can say so without repeating the segment names it once used.
export const KMEANS_MODE = 'KMEANS';
export const LEGACY_MODE = 'LEGACY_RFM';

// Shown instead of the old segment names of a historical campaign, so no
// previous RFM label appears anywhere in the campaign UI.
export const LEGACY_AUDIENCE_LABEL = 'Previous RFM targeting (no longer shown to customers)';

/** The customer groups one campaign targets, as names for a table cell. */
export function audienceGroups(campaign) {
  if (!campaign) return [];
  if ((campaign.targeting_mode || LEGACY_MODE) !== KMEANS_MODE) {
    return [LEGACY_AUDIENCE_LABEL];
  }
  const labels = campaign.target_cluster_labels || [];
  return labels.length
    ? labels
    : (campaign.target_cluster_ids || []).map((id) => `Cluster ${id}`);
}

/** A campaign authored before the switch to K-Means groups. */
export function isLegacyAudience(campaign) {
  return Boolean(campaign)
    && (campaign.targeting_mode || LEGACY_MODE) === LEGACY_MODE;
}

export const STATUS_COLORS = {
  DRAFT: '#6B5E63', PUBLISHED: '#2E7D32', PAUSED: '#B8505E', EXPIRED: '#9E8F94',
};

// The stored status vocabulary is unchanged (PAUSED keeps meaning "not available
// to customers, history intact"); only the admin wording is what the campaign
// feature actually offers: Deactivate and Reactivate, never a delete of a
// published campaign.
export const STATUS_LABELS = {
  DRAFT: 'Draft', PUBLISHED: 'Published', PAUSED: 'Deactivated', EXPIRED: 'Expired',
};

export const statusLabel = (status) => STATUS_LABELS[status] || status;

export const DISCOUNT_OPTIONS = [
  { type: 'PERCENTAGE', label: 'Percentage Discount', example: 'e.g. 15% OFF' },
  { type: 'FLAT', label: 'Flat Discount', example: 'e.g. ₹200 OFF' },
  { type: 'SPEND_BASED', label: 'Spend-Based Discount', example: 'Spend ₹3,000, get ₹300 OFF' },
  { type: 'BUY_MORE_SAVE_MORE', label: 'Buy More Save More', example: 'Buy 2 save 10%, buy 3 save 20%' },
  { type: 'CASHBACK', label: 'Cashback', example: 'e.g. ₹200 cashback on eligible orders' },
  { type: 'FREE_SHIPPING', label: 'Free Shipping', example: 'Free delivery on eligible orders' },
];

export const BUY_GET_OPTIONS = [
  { type: 'BUY_X_GET_Y_FREE', label: 'Buy X Get Y Free', example: 'Buy 2 Get 1 Free' },
  { type: 'BUY_X_GET_Y_DISCOUNT', label: 'Buy X Get Y Discount', example: 'Buy 2 Get 1 at 50% OFF' },
  { type: 'BOGO', label: 'Buy One Get One Free', example: 'BOGO on selected products' },
  { type: 'BUNDLE', label: 'Bundle / Combo Deal', example: '3 selected products for ₹999' },
  { type: 'FREE_GIFT', label: 'Free Gift', example: 'Free gift on orders above ₹2,000' },
  { type: 'PRODUCT_DISCOUNT', label: 'Product-Based Special Offer', example: 'Discount on selected products or categories' },
];

export const emptyForm = () => ({
  name: '', coupon_code: '', description: '',
  offer_category: 'DISCOUNT',          // DISCOUNT | BUY_GET | COMBINED
  // Discount offer
  discount_type: 'PERCENTAGE',
  percent: 15, flat: 200,
  spend_threshold: 3000, spend_discount: 300,
  cashback: 200,
  tiers: [{ buy: 2, percent: 10 }, { buy: 3, percent: 20 }],
  // Buy & Get offer
  buy_get_type: 'BUY_X_GET_Y_FREE',
  buy_qty: 2, get_qty: 1, get_discount_percent: 50,
  bundle_price: 999, gift_name: '', gift_value: 499, gift_min_order: 2000,
  product_discount_percent: 25, product_discount_flat: 150,
  product_offer_mode: 'PERCENTAGE',    // PERCENTAGE | FLAT (PRODUCT_DISCOUNT)
  // Applicable products
  scope_mode: 'ALL', scope_products: [], scope_categories: [],
  // Customers: the four K-Means groups of the latest persisted clustering run.
  targeting_mode: KMEANS_MODE,
  target_cluster_ids: [],
  // Conditions & validity
  min_order_amount: 0, max_discount: '',
  start_date: '', end_date: '',
  usage_type: 'UNLIMITED', per_customer_limit: 0, global_usage_limit: 0,
  benefits_combinable: false, stacking_allowed: false,
});

const num = (v) => (v === '' || v === null || v === undefined ? 0 : Number(v));

export function buildDiscountRule(form) {
  switch (form.discount_type) {
    case 'FLAT': return { type: 'FLAT', flat: num(form.flat) };
    case 'SPEND_BASED': return {
      type: 'SPEND_BASED',
      spend_threshold: num(form.spend_threshold),
      spend_discount: num(form.spend_discount),
    };
    case 'BUY_MORE_SAVE_MORE': return {
      type: 'BUY_MORE_SAVE_MORE',
      tiers: (form.tiers || [])
        .filter((t) => Number(t.buy) >= 2 && Number(t.percent) > 0)
        .map((t) => ({ buy: Number(t.buy), percent: Number(t.percent) })),
    };
    case 'CASHBACK': return { type: 'CASHBACK', cashback: num(form.cashback) };
    case 'FREE_SHIPPING': return { type: 'FREE_SHIPPING' };
    default: return { type: 'PERCENTAGE', percent: num(form.percent) };
  }
}

export function buildBuyGetRule(form) {
  switch (form.buy_get_type) {
    case 'BUY_X_GET_Y_DISCOUNT': return {
      type: 'BUY_X_GET_Y_DISCOUNT',
      buy_qty: num(form.buy_qty), get_qty: num(form.get_qty),
      discount_percent: num(form.get_discount_percent),
    };
    case 'BOGO': return { type: 'BOGO' };
    case 'BUNDLE': return {
      type: 'BUNDLE', bundle_price: num(form.bundle_price),
      product_ids: form.scope_products || [],
    };
    case 'FREE_GIFT': return {
      type: 'FREE_GIFT', gift_name: form.gift_name,
      gift_value: num(form.gift_value), min_order_amount: num(form.gift_min_order),
    };
    case 'PRODUCT_DISCOUNT': return form.product_offer_mode === 'FLAT'
      ? { type: 'PRODUCT_DISCOUNT', discount_flat: num(form.product_discount_flat) }
      : { type: 'PRODUCT_DISCOUNT', discount_percent: num(form.product_discount_percent) };
    default: return {
      type: 'BUY_X_GET_Y_FREE', buy_qty: num(form.buy_qty), get_qty: num(form.get_qty),
    };
  }
}

export function buildScope(form) {
  if (form.scope_mode === 'PRODUCTS') {
    return { mode: 'PRODUCTS', product_ids: form.scope_products || [] };
  }
  if (form.scope_mode === 'CATEGORIES') {
    return { mode: 'CATEGORIES', categories: form.scope_categories || [] };
  }
  return { mode: 'ALL' };
}

/** Form state -> the exact JSON the CampaignSerializer expects. */
export function buildPayload(form) {
  const hasDiscount = form.offer_category !== 'BUY_GET';
  const hasBuyGet = form.offer_category !== 'DISCOUNT';
  return {
    name: form.name.trim(),
    coupon_code: form.coupon_code.trim().toUpperCase(),
    description: form.description.trim(),
    offer_category: form.offer_category,
    discount_rule: hasDiscount ? buildDiscountRule(form) : {},
    buy_get_rule: hasBuyGet ? buildBuyGetRule(form) : {},
    scope: buildScope(form),
    benefits_combinable: form.offer_category === 'COMBINED' ? form.benefits_combinable : false,
    // The audience is always the K-Means groups: the old segment fields are
    // sent empty so a campaign can never carry both targeting kinds.
    targeting_mode: KMEANS_MODE,
    target_cluster_ids: form.target_cluster_ids,
    target_segments: [],
    target_tags: [],
    min_order_amount: num(form.min_order_amount),
    max_discount: form.max_discount === '' || form.max_discount === null
      ? null : num(form.max_discount),
    start_date: form.start_date ? new Date(form.start_date).toISOString() : '',
    end_date: form.end_date ? new Date(form.end_date).toISOString() : '',
    usage_type: form.usage_type,
    per_customer_limit: num(form.per_customer_limit),
    global_usage_limit: num(form.global_usage_limit),
    stacking_allowed: form.stacking_allowed,
  };
}

const toLocalInput = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** Stored campaign -> form state (inverse of buildPayload, best effort). */
export function formFromCampaign(c) {
  const base = emptyForm();
  const rule = c.discount_rule || {};
  const bg = c.buy_get_rule || {};
  const scope = c.scope || {};
  return {
    ...base,
    name: c.name, coupon_code: c.coupon_code, description: c.description || '',
    offer_category: c.offer_category || 'DISCOUNT',
    discount_type: rule.type || 'PERCENTAGE',
    percent: rule.percent ?? c.discount_value ?? 15,
    flat: rule.flat ?? 200,
    spend_threshold: rule.spend_threshold ?? 3000,
    spend_discount: rule.spend_discount ?? 300,
    cashback: rule.cashback ?? 200,
    tiers: (rule.tiers && rule.tiers.length) ? rule.tiers : base.tiers,
    buy_get_type: bg.type || 'BUY_X_GET_Y_FREE',
    buy_qty: bg.buy_qty ?? 2, get_qty: bg.get_qty ?? 1,
    get_discount_percent: bg.discount_percent ?? 50,
    bundle_price: bg.bundle_price ?? 999,
    gift_name: bg.gift_name || '', gift_value: bg.gift_value ?? 499,
    gift_min_order: bg.min_order_amount ?? 2000,
    product_discount_percent: bg.discount_percent ?? 25,
    product_discount_flat: bg.discount_flat ?? 150,
    product_offer_mode: bg.discount_flat ? 'FLAT' : 'PERCENTAGE',
    scope_mode: scope.mode || 'ALL',
    scope_products: scope.product_ids || (bg.product_ids || []),
    scope_categories: scope.categories || [],
    targeting_mode: KMEANS_MODE,
    // A historical campaign's stored segments are not offered as a target: an
    // edit of one moves it onto the K-Means groups (only a draft can be saved).
    target_cluster_ids: (c.targeting_mode || LEGACY_MODE) === KMEANS_MODE
      ? (c.target_cluster_ids || []) : [],
    min_order_amount: c.min_order_amount ?? 0,
    max_discount: c.max_discount ?? '',
    start_date: toLocalInput(c.start_date), end_date: toLocalInput(c.end_date),
    usage_type: c.usage_type || 'UNLIMITED',
    per_customer_limit: c.per_customer_limit ?? 0,
    global_usage_limit: c.global_usage_limit ?? 0,
    benefits_combinable: Boolean(c.benefits_combinable),
    stacking_allowed: Boolean(c.stacking_allowed),
  };
}

const inr = (v) => `₹${Number(v || 0).toLocaleString('en-IN')}`;
const trim = (v) => {
  const n = Number(v || 0);
  return Number.isInteger(n) ? String(n) : String(n);
};

export function discountRuleText(form) {
  switch (form.discount_type) {
    case 'FLAT': return `${inr(form.flat)} OFF`;
    case 'SPEND_BASED': return `Spend ${inr(form.spend_threshold)}, get ${inr(form.spend_discount)} OFF`;
    case 'BUY_MORE_SAVE_MORE': return (form.tiers || [])
      .filter((t) => t.buy && t.percent)
      .map((t) => `Buy ${t.buy} save ${t.percent}%`).join(', ');
    case 'CASHBACK': return `${inr(form.cashback)} cashback`;
    case 'FREE_SHIPPING': return 'Free shipping';
    default: return `${trim(form.percent)}% OFF`;
  }
}

export function buyGetRuleText(form) {
  switch (form.buy_get_type) {
    case 'BUY_X_GET_Y_DISCOUNT': return `Buy ${form.buy_qty} Get ${form.get_qty} at ${trim(form.get_discount_percent)}% OFF`;
    case 'BOGO': return 'Buy 1 Get 1 Free';
    case 'BUNDLE': return `Bundle of ${(form.scope_products || []).length} for ${inr(form.bundle_price)}`;
    case 'FREE_GIFT': return `Free gift${form.gift_min_order > 0 ? ` above ${inr(form.gift_min_order)}` : ''}`;
    case 'PRODUCT_DISCOUNT': return form.product_offer_mode === 'FLAT'
      ? `${inr(form.product_discount_flat)} OFF on eligible items`
      : `${trim(form.product_discount_percent)}% OFF on eligible items`;
    default: return `Buy ${form.buy_qty} Get ${form.get_qty} Free`;
  }
}

export function scopeText(form) {
  if (form.scope_mode === 'PRODUCTS') return `${(form.scope_products || []).length} selected products`;
  if (form.scope_mode === 'CATEGORIES') return (form.scope_categories || []).join(', ') || 'selected categories';
  return 'all products';
}

/** The admin-facing preview: exactly what will be offered, and to whom. */
export function previewSummary(form, clusters = []) {
  const offers = [];
  if (form.offer_category !== 'BUY_GET') offers.push(discountRuleText(form));
  if (form.offer_category !== 'DISCOUNT') offers.push(buyGetRuleText(form));
  const days = form.start_date && form.end_date
    ? Math.max(0, Math.round((new Date(form.end_date) - new Date(form.start_date)) / 86400000))
    : null;
  const clusterMode = (form.targeting_mode || KMEANS_MODE) === KMEANS_MODE;
  const audience = clusterMode && form.target_cluster_ids.length
    ? form.target_cluster_ids
      .map((id) => clusterName(clusters, id))
      .join(' + ') + ` (~${clusterCustomerCount(clusters, form.target_cluster_ids).toLocaleString('en-IN')} customers)`
    : 'No customer group selected yet';
  return {
    name: form.name || 'Untitled campaign',
    audience,
    offer: offers.filter(Boolean).join(' + ') || 'No offer configured yet',
    products: scopeText(form),
    validity: days === null ? 'No dates selected yet' : `${days} day${days === 1 ? '' : 's'}`,
  };
}

/** Business label of one cluster of the stored run (never assumed by id). */
export function clusterName(clusters, clusterId) {
  const found = (clusters || []).find((c) => Number(c.cluster_id) === Number(clusterId));
  return found ? found.category : `Cluster ${clusterId}`;
}

/** Customers the stored assignment puts in these clusters. */
export function clusterCustomerCount(clusters, clusterIds) {
  return (clusterIds || []).reduce((total, id) => {
    const found = (clusters || []).find((c) => Number(c.cluster_id) === Number(id));
    return total + (found ? Number(found.customer_count || 0) : 0);
  }, 0);
}

/** Effective badge for the list: a published-but-lapsed row shows Expired. */
export function effectiveStatus(campaign) {
  const now = new Date();
  if (campaign.status === 'PUBLISHED' && new Date(campaign.end_date) < now) return 'EXPIRED';
  return campaign.status;
}

export const OFFER_CATEGORY_LABELS = {
  DISCOUNT: 'Discount Offer',
  BUY_GET: 'Buy & Get Offer',
  COMBINED: 'Combined Offer',
};
