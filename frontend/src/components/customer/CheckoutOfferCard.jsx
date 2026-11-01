import React from 'react';
import { Ticket, Check, Loader2 } from 'lucide-react';
import { offerDisplayName, offerStatusLabel } from '../../utils/offerNames';

// One eligible campaign inside the checkout "Offers & Coupons" section.
// The card shows exactly what the same campaign shows in Your Offers, Customer
// Home, My Profile and Member Privileges, because it is the very same object
// from the same server-decided offer list - no second fetch, no second campaign
// configuration, no local filtering.
//
// The state badge and the Apply button follow the rules the backend already
// enforces: only an Available coupon can be applied, Used and Expired ones stay
// visible but inert, and the Applied card is clearly the selected one. Nothing
// here decides a discount amount.
const STATUS_COLORS = {
  AVAILABLE: { color: '#8E3642', background: 'rgba(216,114,126,0.12)' },
  USED: { color: '#5B6B62', background: 'rgba(91,107,98,0.12)' },
  EXPIRED: { color: '#6B5E63', background: 'rgba(158,143,148,0.16)' },
};

function CheckoutOfferCard({ offer, applied, applying, onApply, onRemove }) {
  const status = STATUS_COLORS[offer.status] ? offer.status : 'AVAILABLE';
  const applicable = status === 'AVAILABLE';
  const colors = STATUS_COLORS[status];
  const label = applied ? 'Applied' : offerStatusLabel(status);

  const title = offerDisplayName(offer.name);
  const benefit = offer.offer_summary
    || (offer.discount_type === 'PERCENTAGE'
      ? `${offer.discount_value}% OFF`
      : `\u20B9${Number(offer.discount_value).toLocaleString('en-IN')} OFF`);

  return (
    <div
      style={{
        border: applied ? '1px solid #B8505E' : '1px solid rgba(216,114,126,0.22)',
        background: applied ? 'rgba(216,114,126,0.07)' : '#FFFFFF',
        borderRadius: 14,
        padding: '0.8rem 0.9rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        boxSizing: 'border-box',
        opacity: applicable || applied ? 1 : 0.78,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#B8505E', fontWeight: 700, fontSize: '0.86rem', minWidth: 0, flex: 1 }}>
          <Ticket size={15} style={{ flexShrink: 0 }} />
          <span style={{ lineHeight: 1.3 }}>{title}</span>
        </span>
        <span
          style={{
            flexShrink: 0, borderRadius: 9999, padding: '2px 8px',
            background: applied ? '#B8505E' : colors.background,
            color: applied ? '#FFFFFF' : colors.color,
            fontSize: '0.62rem', fontWeight: 800, letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          {label}
        </span>
      </div>

      <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B', lineHeight: 1.3 }}>
        {benefit}
      </div>

      {offer.description && (
        <p style={{ margin: 0, fontSize: '0.72rem', color: '#6B5E63', lineHeight: 1.4 }}>
          {offer.description}
        </p>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px 8px', fontSize: '0.68rem', color: '#9E8F94' }}>
        <span
          style={{
            border: '1px dashed rgba(184,80,94,0.5)', borderRadius: 6, padding: '1px 6px',
            fontWeight: 700, letterSpacing: '0.05em', color: '#B8505E',
            textDecoration: applicable ? 'none' : 'line-through',
          }}
        >
          {offer.coupon_code}
        </span>
        {offer.min_order_amount > 0 && (
          <span>Min order ₹{Number(offer.min_order_amount).toLocaleString('en-IN')}</span>
        )}
        <span>
          {status === 'USED'
            ? `Used ${new Date(offer.used_at).toLocaleDateString()}`
            : `Valid till ${new Date(offer.end_date).toLocaleDateString()}`}
        </span>
      </div>

      {applied ? (
        <button
          type="button"
          onClick={onRemove}
          style={{
            marginTop: '6px', width: '100%', border: '1px solid #F0E2E0', background: '#FFFFFF',
            borderRadius: 9, padding: '0.45rem 0.6rem', cursor: 'pointer',
            fontSize: '0.76rem', fontWeight: 700, color: '#6B5E63',
          }}
        >
          Remove Offer
        </button>
      ) : (
        <button
          type="button"
          onClick={() => onApply(offer.coupon_code)}
          disabled={!applicable || applying}
          title={applicable ? 'Apply this offer to the order' : `${label} coupon`}
          style={{
            marginTop: '6px', width: '100%', border: 'none',
            background: applicable ? '#B8505E' : '#E7DDDC',
            color: applicable ? '#FFFFFF' : '#8A8084',
            borderRadius: 9, padding: '0.45rem 0.6rem',
            cursor: applicable && !applying ? 'pointer' : 'not-allowed',
            fontSize: '0.76rem', fontWeight: 800, letterSpacing: '0.03em',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          }}
        >
          {applying
            ? <><Loader2 size={13} /> Checking…</>
            : applicable
              ? <><Check size={13} /> Apply Offer</>
              : label}
        </button>
      )}
    </div>
  );
}

// Memoized so an address keystroke or a payment toggle never re-renders the
// offer cards (their data comes from the shared, already-fetched offer list).
export default React.memo(CheckoutOfferCard);
