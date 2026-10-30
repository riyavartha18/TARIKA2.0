import React, { useState, useEffect } from 'react';
import { Sparkles, Copy, Check, Ticket, CalendarDays } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { getMyOffers } from '../../services/api';

// Personalized offers card rail. Every value is fetched from the backend
// (which reads the latest completed RFM analysis + published campaigns from
// Neon); nothing about a customer, offer or coupon code is hardcoded here.
export default function CustomerOffers() {
  const { token } = useAuth();
  const [state, setState] = useState({ loading: true, offers: [], segment: null, tags: [] });
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    let alive = true;
    getMyOffers(token)
      .then((res) => {
        if (alive) {
          setState({
            loading: false,
            offers: res.success ? res.offers : [],
            segment: res.success ? res.segment : null,
            tags: res.success ? res.tags : [],
          });
        }
      })
      .catch(() => { if (alive) setState((s) => ({ ...s, loading: false })); });
    return () => { alive = false; };
  }, [token]);

  const copy = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(code);
      setTimeout(() => setCopied((c) => (c === code ? null : c)), 1600);
    } catch {
      /* clipboard unavailable; the code is shown on the card anyway */
    }
  };

  if (state.loading) return null;
  if (!state.offers.length) return null;

  return (
    <section aria-label="Your personalized offers" style={{ marginBottom: '2.25rem' }}>
      <div className="section-head">
        <div>
          <div className="section-eyebrow section-eyebrow--inline">
            <Sparkles size={14} />
            <span>Offers picked for you{state.segment ? ` · ${state.segment}` : ''}</span>
          </div>
          <h2 className="section-title">Your Exclusive Privileges</h2>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '1rem' }}>
        {state.offers.map((offer) => (
          <div
            key={offer.campaign_id}
            style={{
              backgroundColor: '#FFFFFF',
              border: '1px solid rgba(216,114,126,0.22)',
              borderRadius: 18,
              padding: '1.2rem 1.3rem',
              boxShadow: '0 6px 22px rgba(184,80,94,0.08)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#B8505E', fontWeight: 700 }}>
              <Ticket size={18} />
              <span>{offer.name}</span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1F191B' }}>
              {offer.discount_type === 'PERCENTAGE' ? `${offer.discount_value}% off` : `₹${Number(offer.discount_value).toLocaleString('en-IN')} off`}
            </div>
            {offer.description && (
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#6B5E63' }}>{offer.description}</p>
            )}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem 0.9rem', fontSize: '0.76rem', color: '#9E8F94' }}>
              {offer.min_order_amount > 0 && <span>Min order ₹{Number(offer.min_order_amount).toLocaleString('en-IN')}</span>}
              {offer.max_discount != null && <span>Max discount ₹{Number(offer.max_discount).toLocaleString('en-IN')}</span>}
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <CalendarDays size={13} />
                {new Date(offer.end_date).toLocaleDateString()}
              </span>
            </div>

            <button
              type="button"
              onClick={() => copy(offer.coupon_code)}
              style={{
                marginTop: '0.4rem',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: 8, border: '1px dashed #D8727E', background: 'rgba(216,114,126,0.08)',
                borderRadius: 10, padding: '0.55rem 0.75rem', cursor: 'pointer',
                color: '#B8505E', fontWeight: 700, letterSpacing: '0.05em',
              }}
            >
              <span>{offer.coupon_code}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.72rem' }}>
                {copied === offer.coupon_code ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
              </span>
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
