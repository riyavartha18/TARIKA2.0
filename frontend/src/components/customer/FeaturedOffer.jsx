import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Copy, Check, CalendarDays, ArrowRight, Ticket } from 'lucide-react';
import { offerDisplayName } from '../../utils/offerNames';

// The newest campaign the signed-in customer is eligible for, featured as a
// promotional banner on the home page. Which campaign this is (and whether it
// exists at all) is decided by the backend against the customer's latest
// completed RFM segment, so a customer never sees another segment's offer here.
export default function FeaturedOffer({ offer, onCopyNote }) {
  const [copied, setCopied] = useState(false);

  if (!offer) return null;

  const title = offerDisplayName(offer.name);
  const summary = offer.offer_summary
    || (offer.discount_type === 'PERCENTAGE'
      ? `${offer.discount_value}% OFF`
      : `₹${Number(offer.discount_value).toLocaleString('en-IN')} OFF`);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(offer.coupon_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
      if (onCopyNote) onCopyNote(offer.coupon_code);
    } catch {
      /* clipboard unavailable; the code is shown on the banner anyway */
    }
  };

  return (
    <div aria-label="Exclusive offer for you" style={{ marginBottom: '1.5rem' }}>
      <div
        style={{
          borderRadius: '24px',
          border: '1px solid rgba(216, 114, 126, 0.28)',
          background: 'linear-gradient(135deg, #FBF1F0 0%, #F7E4E2 55%, #F5D3D1 100%)',
          boxShadow: '0 10px 34px rgba(184, 80, 94, 0.12)',
          padding: '2rem 2.2rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1.75rem',
        }}
      >
        <div style={{ flex: '1 1 320px', minWidth: 0 }}>
          <span
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              backgroundColor: 'rgba(184, 80, 94, 0.10)', color: '#8E3642',
              borderRadius: '9999px', padding: '4px 12px',
              fontSize: '0.7rem', fontWeight: 800, letterSpacing: '0.12em',
              textTransform: 'uppercase',
            }}
          >
            <Sparkles size={13} /> Live Now
          </span>

          <h3
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.9rem', fontWeight: 700, color: '#1F191B',
              margin: '0.7rem 0 0.2rem 0', lineHeight: 1.2,
            }}
          >
            {title}
          </h3>

          <p style={{ margin: '0 0 0.6rem 0', fontSize: '1.15rem', fontWeight: 800, color: '#B8505E' }}>
            {summary}
          </p>

          {offer.description && (
            <p style={{ margin: '0 0 0.9rem 0', fontSize: '0.88rem', color: '#6B5E63', maxWidth: '52ch' }}>
              {offer.description}
            </p>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.1rem' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#8E3642', fontWeight: 600 }}>
              <CalendarDays size={14} />
              Valid till {new Date(offer.end_date).toLocaleDateString()}
            </span>
            {offer.min_order_amount > 0 && (
              <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                Min order ₹{Number(offer.min_order_amount).toLocaleString('en-IN')}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link to="/customer/shop" className="tarika-btn-primary">
              <span>Shop Now</span>
              <ArrowRight size={16} />
            </Link>
            <Link to="/customer/offers" className="tarika-btn-outline">
              View All Offers
            </Link>
          </div>
        </div>

        {/* Coupon panel */}
        <button
          type="button"
          onClick={copy}
          style={{
            flex: '0 0 auto',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
            padding: '1.4rem 1.8rem', borderRadius: '18px', cursor: 'pointer',
            backgroundColor: '#FFFFFF', border: '1px dashed #D8727E',
            boxShadow: '0 8px 24px rgba(184, 80, 94, 0.10)',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#9E8F94' }}>
            <Ticket size={13} /> Coupon Code
          </span>
          <span style={{ fontSize: '1.35rem', fontWeight: 800, letterSpacing: '0.06em', color: '#B8505E' }}>
            {offer.coupon_code}
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.74rem', fontWeight: 700, color: copied ? '#3F8F6B' : '#8E3642' }}>
            {copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy Coupon</>}
          </span>
        </button>
      </div>
    </div>
  );
}
