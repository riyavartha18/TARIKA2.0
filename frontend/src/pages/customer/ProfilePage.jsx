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
  Shield,
  Crown,
  LogOut,
  Gift,
  Truck,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { useCustomer } from '../../context/CustomerContext';

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const { wishlistItems, totalItems } = useCustomer();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/');
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
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '4px' }}>
              <Crown size={15} />
              <span style={{ fontSize: '0.74rem', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                TARIKA VIP HAUTE CIRCLE
              </span>
            </div>
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
              Member since 2026 • Exclusive Privileges Active
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
            <span style={{ fontSize: '1.2rem', fontWeight: 800, color: '#1F191B', display: 'block', lineHeight: 1.2 }}>
              Tier: Rose Gold
            </span>
            <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>VIP Haute Circle</span>
          </div>
        </div>
      </div>

      {/* Account Details & VIP Privileges Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '2rem',
        }}
      >
        {/* Contact & Delivery Details */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '20px',
            padding: '2rem',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            boxShadow: '0 4px 20px rgba(184, 80, 94, 0.05)',
          }}
        >
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.35rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: '0 0 1.25rem 0',
              borderBottom: '1px solid #F0E2E0',
              paddingBottom: '0.75rem',
            }}
          >
            Account & Destination
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Mail size={16} color="#B8505E" />
              <div>
                <span style={{ fontSize: '0.72rem', color: '#9E8F94', display: 'block' }}>Email Address</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#1F191B' }}>
                  {user?.email || 'customer@tarika.com'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Phone size={16} color="#B8505E" />
              <div>
                <span style={{ fontSize: '0.72rem', color: '#9E8F94', display: 'block' }}>Contact Phone</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#1F191B' }}>
                  {user?.phone ? `+91 ${user.phone}` : 'Registered via email'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <MapPin size={16} color="#B8505E" />
              <div>
                <span style={{ fontSize: '0.72rem', color: '#9E8F94', display: 'block' }}>City & State</span>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#1F191B' }}>
                  {user?.city ? `${user.city}, ${user.state || ''}` : 'India (National Delivery)'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Member Benefits */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '20px',
            padding: '2rem',
            border: '1px solid rgba(240, 226, 224, 0.9)',
            boxShadow: '0 4px 20px rgba(184, 80, 94, 0.05)',
          }}
        >
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.35rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: '0 0 1.25rem 0',
              borderBottom: '1px solid #F0E2E0',
              paddingBottom: '0.75rem',
            }}
          >
            VIP Member Privileges
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Truck size={18} color="#D8727E" />
              <div>
                <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1F191B', display: 'block' }}>
                  Priority Express Dispatch
                </span>
                <span style={{ fontSize: '0.76rem', color: '#6B5E63' }}>
                  Zero delivery fees on all orders across India
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Gift size={18} color="#D8727E" />
              <div>
                <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1F191B', display: 'block' }}>
                  20% Secret Coupon
                </span>
                <span style={{ fontSize: '0.76rem', color: '#6B5E63' }}>
                  Use code <strong>TARIKA20</strong> at flash events
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Shield size={18} color="#D8727E" />
              <div>
                <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1F191B', display: 'block' }}>
                  Authentic Couture Guarantee
                </span>
                <span style={{ fontSize: '0.76rem', color: '#6B5E63' }}>
                  Direct atelier verification on every garment
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
