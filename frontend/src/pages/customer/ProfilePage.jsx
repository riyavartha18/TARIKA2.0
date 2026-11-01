import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  User,
  Mail,
  Phone,
  MapPin,
  Heart,
  ShoppingBag,
  Sparkles,
  Gift,
  LogOut,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { useCustomer } from '../../context/CustomerContext';
import PersonalizedOffers from '../../components/customer/PersonalizedOffers';
import usePersonalizedOffers from '../../hooks/usePersonalizedOffers';
import { offerDisplayName, offerStatusLabel } from '../../utils/offerNames';

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const { wishlistItems, totalItems } = useCustomer();
  // Same campaigns, same eligibility logic as every other customer surface:
  // one list from the customer context, and both blocks below render that
  // identical list. The counts are memoized in the hook, not recomputed here.
  const { loading, syncing, offers, availableCount, usedCount } = usePersonalizedOffers();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const sectionTitleStyle = {
    fontFamily: "'Playfair Display', serif",
    fontSize: '1.35rem',
    fontWeight: 700,
    color: '#1F191B',
    margin: '0 0 1.25rem 0',
    borderBottom: '1px solid #F0E2E0',
    paddingBottom: '0.75rem',
  };

  const panelStyle = {
    backgroundColor: '#FFFFFF',
    borderRadius: '20px',
    padding: '2rem',
    border: '1px solid rgba(240, 226, 224, 0.9)',
    boxShadow: '0 4px 20px rgba(184, 80, 94, 0.05)',
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', paddingBottom: '4rem' }}>
      {/* Profile Header Hero */}
      <div
        style={{
          borderRadius: '24px',
          padding: '2.5rem',
          background: 'linear-gradient(135deg, #FBF1F0 0%, #F7E4E2 50%, #F5D3D1 100%)',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          boxShadow: '0 8px 30px rgba(184, 80, 94, 0.08)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '2rem',
          marginBottom: '2.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <div
            style={{
              width: '84px',
              height: '84px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #D8727E 0%, #B8505E 100%)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '2.2rem',
              fontWeight: 700,
              fontFamily: "'Playfair Display', serif",
              boxShadow: '0 8px 24px rgba(184, 80, 94, 0.35)',
            }}
          >
            {user?.full_name ? user.full_name[0].toUpperCase() : 'M'}
          </div>

          <div>
            <h1
              style={{
                margin: '0 0 4px 0',
                fontFamily: "'Playfair Display', serif",
                fontSize: '2rem',
                fontWeight: 700,
                color: '#1F191B',
              }}
            >
              {user?.full_name || 'Valued Member'}
            </h1>
            <p style={{ margin: 0, fontSize: '0.86rem', color: '#6B5E63' }}>
              Member since 2026
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '0.65rem 1.4rem',
            backgroundColor: '#FFFFFF',
            border: '1px solid rgba(224, 77, 96, 0.3)',
            borderRadius: '9999px',
            color: '#E04D60',
            fontSize: '0.84rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FFF1F2')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FFFFFF')}
        >
          <LogOut size={15} />
          <span>Sign Out</span>
        </button>
      </div>

      {/* Metrics Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2.5rem',
        }}
      >
        <Link
          to="/customer/wishlist"
          style={{
            textDecoration: 'none',
            backgroundColor: '#FFFFFF',
            padding: '1.5rem',
            borderRadius: '20px',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            boxShadow: '0 4px 16px rgba(184, 80, 94, 0.04)',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            transition: 'all 0.25s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-3px)')}
          onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: '#FBF1F0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Heart size={22} color="#D8727E" fill="#D8727E" />
          </div>
          <div>
            <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#1F191B', display: 'block', lineHeight: 1 }}>
              {wishlistItems.length}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>Wishlist Items</span>
          </div>
        </Link>

        <Link
          to="/customer/bag"
          style={{
            textDecoration: 'none',
            backgroundColor: '#FFFFFF',
            padding: '1.5rem',
            borderRadius: '20px',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            boxShadow: '0 4px 16px rgba(184, 80, 94, 0.04)',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            transition: 'all 0.25s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-3px)')}
          onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: '#FBF1F0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ShoppingBag size={22} color="#B8505E" />
          </div>
          <div>
            <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#1F191B', display: 'block', lineHeight: 1 }}>
              {totalItems}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>Bag Items</span>
          </div>
        </Link>

        <div
          style={{
            backgroundColor: '#FFFFFF',
            padding: '1.5rem',
            borderRadius: '20px',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            boxShadow: '0 4px 16px rgba(184, 80, 94, 0.04)',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: '#FBF1F0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Sparkles size={22} color="#8E3642" />
          </div>
          <div>
            <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#1F191B', display: 'block', lineHeight: 1 }}>
              {loading || syncing ? '—' : availableCount}
            </span>
            <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>Offers Ready to Use</span>
          </div>
        </div>
      </div>

      {/* My Profile — a summary of the live offers on this account. The cards
          themselves live in Member Privileges below (and on Your Offers), so
          the same campaign is never printed twice on one page. */}
      {(offers.length > 0 || syncing) && (
        <section
          aria-label="My offer summary"
          style={{
            ...panelStyle,
            marginBottom: '2.5rem',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            background: 'linear-gradient(135deg, #FBF1F0 0%, #F7E4E2 100%)',
            border: '1px solid rgba(216, 114, 126, 0.25)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0 }}>
            <Sparkles size={22} color="#8E3642" />
            <div style={{ minWidth: 0 }}>
              <span style={{ fontSize: '1rem', fontWeight: 800, color: '#1F191B', display: 'block', lineHeight: 1.3 }}>
                {syncing && !offers.length
                  ? 'Tailoring your offers…'
                  : `${availableCount} offer${availableCount === 1 ? '' : 's'} ready to use${
                    usedCount ? ` · ${usedCount} already used` : ''}`}
              </span>
              {offers.length > 0 && (
                <span style={{ fontSize: '0.82rem', color: '#6B5E63', display: 'block' }}>
                  {offers.slice(0, 3).map(
                    (offer) => `${offerDisplayName(offer.name)} (${offerStatusLabel(offer.status)})`,
                  ).join(' • ')}
                  {offers.length > 3 ? ' • …' : ''}
                </span>
              )}
            </div>
          </div>

          <Link
            to="/customer/offers"
            className="tarika-btn-outline"
            style={{ fontSize: '0.82rem', padding: '0.6rem 1.3rem' }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              View All Offers
              <ArrowRight size={14} />
            </span>
          </Link>
        </section>
      )}

      {/* Account & Destination, then Member Privileges - both full width, so
          the two cards share exactly the same measure and alignment. */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        {/* Contact & Delivery Details */}
        <div style={panelStyle}>
          <h2 style={sectionTitleStyle}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
              <User size={18} color="#B8505E" />
              Account &amp; Destination
            </span>
          </h2>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '1.75rem 2rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <Mail size={16} color="#B8505E" />
              <div>
                <span style={{ fontSize: '0.74rem', color: '#9E8F94', display: 'block', letterSpacing: '0.04em', textTransform: 'uppercase' }}>Email Address</span>
                <span style={{ fontSize: '0.98rem', fontWeight: 600, color: '#1F191B', display: 'block', marginTop: '2px' }}>
                  {user?.email || 'customer@tarika.com'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <Phone size={16} color="#B8505E" />
              <div>
                <span style={{ fontSize: '0.74rem', color: '#9E8F94', display: 'block', letterSpacing: '0.04em', textTransform: 'uppercase' }}>Contact Phone</span>
                <span style={{ fontSize: '0.98rem', fontWeight: 600, color: '#1F191B', display: 'block', marginTop: '2px' }}>
                  {user?.phone ? `+91 ${user.phone}` : 'Registered via email'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <MapPin size={16} color="#B8505E" />
              <div>
                <span style={{ fontSize: '0.74rem', color: '#9E8F94', display: 'block', letterSpacing: '0.04em', textTransform: 'uppercase' }}>City &amp; State</span>
                <span style={{ fontSize: '0.98rem', fontWeight: 600, color: '#1F191B', display: 'block', marginTop: '2px' }}>
                  {user?.city ? `${user.city}, ${user.state || ''}` : 'India (National Delivery)'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Member Privileges — the customer's eligible campaigns, the same
            server-decided list as the Your Offers page and the home feature. */}
        <div style={panelStyle}>
          <h2
            style={{
              ...sectionTitleStyle,
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '0.5rem',
            }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
              <Gift size={18} color="#B8505E" />
              Member Privileges
            </span>
            {offers.length > 0 && (
              <Link to="/customer/offers" className="section-link" style={{ fontFamily: 'inherit', fontSize: '0.82rem' }}>
                <span>View All Offers</span>
                <ArrowRight size={14} />
              </Link>
            )}
          </h2>

          {loading ? (
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#9E8F94' }}>Loading your offers…</p>
          ) : syncing && !offers.length ? (
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#6B5E63' }}>
              Tailoring your offers — your latest shopping analysis is being prepared. This
              refreshes on its own in a moment.
            </p>
          ) : offers.length ? (
            <PersonalizedOffers offers={offers} minColumnWidth={250} />
          ) : (
            <p style={{ margin: 0, fontSize: '0.84rem', color: '#6B5E63' }}>
              No offers are active for your account right now. New ones appear here as soon as
              they are published.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
