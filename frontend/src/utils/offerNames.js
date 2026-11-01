// Campaigns are authored with an internal RFM label in their name
// ("Champions: VIP 15% OFF") so the back office stays readable. A customer must
// only ever see the offer itself, for every segment alike. The backend already
// strips this prefix on /api/customer/me/offers; this is a defensive repeat so a
// stale cached response can never leak a segment label into the UI.
const SEGMENT_LABELS = [
  'Champions',
  'Loyal Customers',
  'Potential Loyalists',
  'New Customers',
  'At-Risk',
  'Hibernating',
  'Never Purchased',
  'Big Spender',
];

const SEGMENT_PREFIX = new RegExp(
  `^\\s*(?:${SEGMENT_LABELS.join('|')})\\s*[:\\-–—]\\s*`,
  'i',
);

/** Offer title without any leading RFM segment / tag label. */
export function offerDisplayName(name) {
  if (!name) return '';
  return String(name).replace(SEGMENT_PREFIX, '').trim();
}

// Redemption state labels. The state itself (AVAILABLE / USED / EXPIRED) is
// decided by the backend from the campaign dates and this customer's own
// redemption rows; only the wording lives here, so every surface agrees.
const STATUS_LABELS = {
  AVAILABLE: 'Available',
  USED: 'Used',
  EXPIRED: 'Expired',
};

export function offerStatusLabel(status) {
  return STATUS_LABELS[status] || STATUS_LABELS.AVAILABLE;
}
