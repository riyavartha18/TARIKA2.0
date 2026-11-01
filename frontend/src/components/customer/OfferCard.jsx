import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Ticket, Copy, Check, CalendarDays, ArrowRight } from 'lucide-react';
import { offerDisplayName, offerStatusLabel } from '../../utils/offerNames';

// One personalized offer card. Every offer is rendered through this single
// component, so all cards share identical typography, spacing, coupon treatment
// and button styling - no offer looks more important because of the RFM segment
// it belongs to. The Available / Used / Expired state comes from the backend
// (campaign dates + this customer's redemption rows), never from the browser.
const STATUS_STYLES = {
  AVAILABLE: { color: '#8E3642', background: 'rgba(216,114,126,0.12)' },
  USED: { color: '#5B6B62', background: 'rgba(91,107,98,0.12)' },
  EXPIRED: { color: '#6B5E63', background: 'rgba(158,143,148,0.16)' },
};

function OfferCard({ offer, shopTo = '/customer/shop' }) {
  const [copied, setCopied] = useState(false);

  const status = STATUS_STYLES[offer.status] ? offer.status : 'AVAILABLE';
  const badge = STATUS_STYLES[status];
  const badgeLabel = offerStatusLabel(status);
  const redeemable = status === 'AVAILABLE';

  const title = offerDisplayName(offer.name);
  const summary = offer.offer_summary
    || (offer.discount_type === 'PERCENTAGE'
      ? `${offer.discount_value}% off`
      : `₹${Number(offer.discount_value).toLocaleString('en-IN')} off`);

  const copy = async () => {
    if (!redeemable) return;
    try {
      await navigator.clipboard.writeText(offer.coupon_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable; the code is shown on the card anyway */
    }
  };

  return (
    <div
      style={{
        backgroundColor: redeemable ? '#FFFFFF' : '#FCFAF9',
        border: '1px solid rgba(216,114,126,0.22)',
        borderRadius: 18,
        padding: '1.2rem 1.3rem',
        boxShadow: '0 6px 22px rgba(184,80,94,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        height: '100%',
        boxSizing: 'border-box',
        transition: 'transform 0.25s ease, box-shadow 0.25s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-3px)';
        e.currentTarget.style.boxShadow = '0 12px 30px rgba(184,80,94,0.14)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '0 6px 22px rgba(184,80,94,0.08)';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#B8505E', fontWeight: 700, minWidth: 0 }}>
          <Ticket size={18} style={{ flexShrink: 0 }} />
          <span style={{ fontSize: '1rem', lineHeight: 1.35 }}>{title}</span>
        </div>
        <span
          style={{
            flexShrink: 0, borderRadius: 9999, padding: '3px 10px',
            backgroundColor: badge.background, color: badge.color,
            fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          {badgeLabel}
        </span>
      </div>

      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#1F191B', lineHeight: 1.3 }}>
        {summary}
      </div>

      {offer.description && (
        <p style={{ margin: 0, fontSize: '0.82rem', color: '#6B5E63', lineHeight: 1.45 }}>
          {offer.description}
        </p>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem 0.9rem', fontSize: '0.76rem', color: '#9E8F94' }}>
        {offer.min_order_amount > 0 && (
          <span>Min order ₹{Number(offer.min_order_amount).toLocaleString('en-IN')}</span>
        )}
        {offer.max_discount != null && (
          <span>Max discount ₹{Number(offer.max_discount).toLocaleString('en-IN')}</span>
        )}
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <CalendarDays size={13} />
          {status === 'USED'
            ? `Redeemed ${new Date(offer.used_at).toLocaleDateString()}`
            : `Valid till ${new Date(offer.end_date).toLocaleDateString()}`}
        </span>
      </div>

      <button
        type="button"
        onClick={copy}
        disabled={!redeemable}
        title={redeemable ? 'Copy coupon code' : `${badgeLabel} coupon`}
        style={{
          marginTop: '0.4rem',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 8, border: '1px dashed #D8727E', background: 'rgba(216,114,126,0.08)',
          borderRadius: 10, padding: '0.55rem 0.75rem',
          cursor: redeemable ? 'pointer' : 'not-allowed',
          color: '#B8505E', fontWeight: 700, letterSpacing: '0.05em',
          opacity: redeemable ? 1 : 0.5,
        }}
      >
        <span style={{ textDecoration: redeemable ? 'none' : 'line-through' }}>
          {offer.coupon_code}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.72rem' }}>
          {!redeemable
            ? badgeLabel
            : copied
              ? <><Check size={14} /> Copied</>
              : <><Copy size={14} /> Copy Coupon</>}
        </span>
      </button>

      <Link
        to={shopTo}
        style={{
          marginTop: 'auto',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          padding: '0.55rem 0.9rem', borderRadius: 9999,
          border: '1px solid rgba(184,80,94,0.35)', backgroundColor: '#FFFFFF',
          color: '#B8505E', fontSize: '0.8rem', fontWeight: 700, textDecoration: 'none',
          transition: 'background-color 0.2s ease',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FBF1F0')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FFFFFF')}
      >
        <span>Shop Now</span>
        <ArrowRight size={14} />
      </Link>
    </div>
  );
}

// Memoized on the offer object: an unrelated re-render of the surrounding page
// (bag badge, toast, navbar scroll state) never re-renders the cards again.
export default React.memo(OfferCard);
