import React from 'react';
import { Truck, RotateCcw, ShieldCheck, Headphones, Mail } from 'lucide-react';
import { TRUST_FEATURES } from '../../data/tarikaData';

export default function FeatureFooter() {
  const getIcon = (iconName) => {
    switch (iconName) {
      case 'Truck':
        return <Truck size={24} color="#8E3642" />;
      case 'RotateCcw':
        return <RotateCcw size={24} color="#8E3642" />;
      case 'ShieldCheck':
        return <ShieldCheck size={24} color="#8E3642" />;
      case 'Headphones':
        return <Headphones size={24} color="#8E3642" />;
      default:
        return <Truck size={24} color="#8E3642" />;
    }
  };

  return (
    <footer
      style={{
        backgroundColor: '#FFFFFF',
        borderTop: '1px solid #F0E2E0',
        marginTop: '2rem'
      }}
    >
      {/* Trust Features Bar matching reference */}
      <div
        style={{
          maxWidth: '1680px',
          margin: '0 auto',
          padding: '2.5rem 3.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #F0E2E0',
          flexWrap: 'wrap',
          gap: '2rem'
        }}
      >
        {/* 4 Trust Badges */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '3.5rem',
            flexWrap: 'wrap'
          }}
        >
          {TRUST_FEATURES.map((feat) => (
            <div
              key={feat.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem'
              }}
            >
              <div
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: '#FDEEEB',
                  border: '1px solid rgba(216, 114, 126, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}
              >
                {getIcon(feat.icon)}
              </div>
              <div>
                <div style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1C1819' }}>
                  {feat.title}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#6B5E63', marginTop: '0.1rem' }}>
                  {feat.subtitle}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Right: Signature Handwritten Calligraphy matching reference */}
        <div style={{ textAlign: 'right' }}>
          <div
            className="tarika-serif"
            style={{
              fontSize: '1.6rem',
              fontWeight: 700,
              letterSpacing: '0.18em',
              color: '#8E3642',
              lineHeight: 1
            }}
          >
            TARIKA
          </div>
          <div
            className="tarika-script"
            style={{
              fontSize: '1.9rem',
              color: '#D8727E',
              lineHeight: 1.1,
              marginTop: '0.2rem'
            }}
          >
            Style Your Story ♡
          </div>
        </div>
      </div>

      {/* Main Footer Sitemap & Copyright */}
      <div
        style={{
          maxWidth: '1680px',
          margin: '0 auto',
          padding: '3rem 3.5rem 2rem',
          display: 'grid',
          gridTemplateColumns: '1.8fr 1fr 1fr 1.2fr',
          gap: '3rem'
        }}
      >
        {/* Brand Bio */}
        <div>
          <span
            className="tarika-serif"
            style={{
              fontSize: '1.5rem',
              fontWeight: 700,
              letterSpacing: '0.2em',
              color: '#1C1819'
            }}
          >
            TARIKA
          </span>
          <p
            style={{
              fontSize: '0.86rem',
              lineHeight: 1.6,
              color: '#6B5E63',
              marginTop: '0.8rem',
              maxWidth: '320px'
            }}
          >
            A high-fashion house celebrating modern romantic femininity, timeless silhouette precision, and conscientious luxury.
          </p>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.8rem',
              marginTop: '1.2rem'
            }}
          >
            {/* Instagram Icon */}
            <a
              href="#social"
              aria-label="Instagram"
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#FAF7F5',
                border: '1px solid #E5D0CD',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6B5E63',
                transition: 'all 0.2s ease'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="20" height="20" x="2" y="2" rx="5" ry="5"/>
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
                <line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/>
              </svg>
            </a>
            {/* Facebook Icon */}
            <a
              href="#social"
              aria-label="Facebook"
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#FAF7F5',
                border: '1px solid #E5D0CD',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6B5E63',
                transition: 'all 0.2s ease'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>
              </svg>
            </a>
            {/* Twitter/X Icon */}
            <a
              href="#social"
              aria-label="Twitter"
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#FAF7F5',
                border: '1px solid #E5D0CD',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6B5E63',
                transition: 'all 0.2s ease'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"/>
              </svg>
            </a>
          </div>
        </div>

        {/* Column 2: Collections */}
        <div>
          <h4
            style={{
              fontSize: '0.88rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: '#1C1819',
              textTransform: 'uppercase',
              marginBottom: '1rem'
            }}
          >
            Collections
          </h4>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {['Haute Couture Dresses', 'Summer Pastels Edit', 'Capsule Co-ords', 'Cashmere Knitwear', 'Designer Handbags'].map((item) => (
              <li key={item}>
                <a
                  href="#categories"
                  style={{
                    fontSize: '0.84rem',
                    color: '#6B5E63',
                    textDecoration: 'none',
                    transition: 'color 0.2s ease'
                  }}
                  onMouseEnter={(e) => (e.target.style.color = '#D8727E')}
                  onMouseLeave={(e) => (e.target.style.color = '#6B5E63')}
                >
                  {item}
                </a>
              </li>
            ))}
          </ul>
        </div>

        {/* Column 3: Customer Care */}
        <div>
          <h4
            style={{
              fontSize: '0.88rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: '#1C1819',
              textTransform: 'uppercase',
              marginBottom: '1rem'
            }}
          >
            Customer Care
          </h4>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {['Order Tracking', 'Shipping & Delivery', 'Returns & Exchanges', 'Size Guide', 'Contact Stylist'].map((item) => (
              <li key={item}>
                <a
                  href="#care"
                  style={{
                    fontSize: '0.84rem',
                    color: '#6B5E63',
                    textDecoration: 'none',
                    transition: 'color 0.2s ease'
                  }}
                  onMouseEnter={(e) => (e.target.style.color = '#D8727E')}
                  onMouseLeave={(e) => (e.target.style.color = '#6B5E63')}
                >
                  {item}
                </a>
              </li>
            ))}
          </ul>
        </div>

        {/* Column 4: Newsletter */}
        <div>
          <h4
            style={{
              fontSize: '0.88rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: '#1C1819',
              textTransform: 'uppercase',
              marginBottom: '0.6rem'
            }}
          >
            Join The Haute Club
          </h4>
          <p style={{ fontSize: '0.84rem', color: '#6B5E63', lineHeight: 1.5, marginBottom: '1rem' }}>
            Receive exclusive seasonal previews, bespoke styling consultations, and 15% off your initial order.
          </p>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: '#FAF7F5',
              borderRadius: '9999px',
              padding: '0.4rem 0.5rem 0.4rem 1rem',
              border: '1px solid #E5D0CD'
            }}
          >
            <input
              type="email"
              placeholder="Enter your email"
              style={{
                border: 'none',
                background: 'transparent',
                outline: 'none',
                fontSize: '0.82rem',
                width: '100%',
                color: '#1C1819'
              }}
            />
            <button
              style={{
                background: 'linear-gradient(135deg, #D8727E 0%, #C45766 100%)',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '9999px',
                padding: '0.45rem 1rem',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Subscribe
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Copyright */}
      <div
        style={{
          borderTop: '1px solid #F0E2E0',
          padding: '1.5rem 3.5rem',
          maxWidth: '1680px',
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.78rem',
          color: '#9E8F94'
        }}
      >
        <div>
          © {new Date().getFullYear()} TARIKA Haute Couture. All rights reserved. "Style Your Story."
        </div>
        <div style={{ display: 'flex', gap: '1.5rem' }}>
          <a href="#privacy" style={{ color: '#9E8F94', textDecoration: 'none' }}>Privacy Policy</a>
          <a href="#terms" style={{ color: '#9E8F94', textDecoration: 'none' }}>Terms of Service</a>
          <a href="#cookies" style={{ color: '#9E8F94', textDecoration: 'none' }}>Cookie Preferences</a>
        </div>
      </div>
    </footer>
  );
}
