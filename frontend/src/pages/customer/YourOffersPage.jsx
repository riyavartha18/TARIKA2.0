import React from 'react';
import { Link } from 'react-router-dom';
import { Ticket, Sparkles, RefreshCw } from 'lucide-react';
import PersonalizedOffers from '../../components/customer/PersonalizedOffers';
import usePersonalizedOffers from '../../hooks/usePersonalizedOffers';

// "Your Offers" - the dedicated page behind the top navigation item. It shows
// exactly the campaigns the backend has already matched to this customer's
// latest completed RFM segment: same list, same order, same cards as the home
// page feature and Member Privileges. Nothing is fetched or filtered twice, and
// no segment label is ever displayed.
export default function YourOffersPage() {
  const {
    loading, syncing, offers, availableCount, usedCount, refreshOffers,
  } = usePersonalizedOffers();

  return (
    <div style={{ paddingBottom: '4rem' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '2rem',
          borderBottom: '1px solid rgba(216, 114, 126, 0.2)',
          paddingBottom: '1.25rem',
        }}
      >
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '4px' }}>
            <Ticket size={16} />
            <span style={{ fontSize: '0.76rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Just For You
            </span>
          </div>
          <h1
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '2.2rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: 0,
            }}
          >
            Your Offers {!loading && !syncing ? `(${availableCount})` : ''}
          </h1>
          {!loading && !syncing && offers.length > 0 && (
            <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.82rem', color: '#6B5E63' }}>
              {availableCount} ready to use
              {usedCount ? ` · ${usedCount} already redeemed` : ''}
            </p>
          )}
        </div>

        {offers.length > 0 && (
          <Link to="/customer/shop" className="tarika-btn-outline" style={{ fontSize: '0.84rem', padding: '0.65rem 1.4rem' }}>
            Continue Shopping
          </Link>
        )}
      </div>

      {loading || syncing ? (
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '20px',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            padding: '2.5rem 2rem',
            textAlign: 'center',
            boxShadow: '0 4px 20px rgba(184, 80, 94, 0.05)',
          }}
        >
          <Sparkles size={26} color="#D8727E" />
          <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.95rem', fontWeight: 700, color: '#1F191B' }}>
            {syncing ? 'Tailoring your offers…' : 'Loading your offers…'}
          </p>
          <p style={{ margin: '0.35rem auto 0', fontSize: '0.84rem', color: '#6B5E63', maxWidth: '46ch' }}>
            {syncing
              ? 'Your latest shopping analysis is being prepared, so the offers that truly apply to you can be listed. This page refreshes itself in a moment.'
              : 'One moment while we fetch the campaigns that apply to your account.'}
          </p>
          <button
            type="button"
            onClick={() => refreshOffers()}
            className="tarika-btn-outline"
            style={{ marginTop: '1.25rem', fontSize: '0.8rem', padding: '0.55rem 1.2rem' }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <RefreshCw size={14} /> Check Again
            </span>
          </button>
        </div>
      ) : offers.length ? (
        <PersonalizedOffers offers={offers} minColumnWidth={270} />
      ) : (
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '20px',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            padding: '3rem 2rem',
            textAlign: 'center',
            boxShadow: '0 4px 20px rgba(184, 80, 94, 0.05)',
          }}
        >
          <Ticket size={26} color="#D8727E" />
          <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.95rem', fontWeight: 700, color: '#1F191B' }}>
            No offers are active for your account right now
          </p>
          <p style={{ margin: '0.35rem auto 0', fontSize: '0.84rem', color: '#6B5E63', maxWidth: '46ch' }}>
            New campaigns appear here, on your home page and inside Member
            Privileges as soon as they are published for you.
          </p>
          <Link to="/customer/shop" className="tarika-btn-primary" style={{ marginTop: '1.25rem' }}>
            <span>Explore The Collection</span>
          </Link>
        </div>
      )}
    </div>
  );
}
