import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';

export default function CtaBanner() {
  const { isAuthenticated } = useAuth();

  return (
    <section
      style={{
        padding: '2rem 2.5rem 4rem',
        maxWidth: '1680px',
        margin: '0 auto'
      }}
    >
      <div
        style={{
          borderRadius: '32px',
          background: 'radial-gradient(ellipse at 50% 50%, #FDEEEB 0%, #FCE3DF 45%, #F9DAD5 100%)',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          overflow: 'hidden',
          display: 'grid',
          gridTemplateColumns: '1fr 1.2fr 1.15fr',
          alignItems: 'center',
          boxShadow: '0 20px 60px rgba(184, 80, 94, 0.12)',
          position: 'relative',
          minHeight: '420px'
        }}
      >
        {/* Left: Calligraphic Art & Boutique Accents */}
        <div
          style={{
            padding: '3rem 2rem 3rem 3rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            height: '100%',
            position: 'relative'
          }}
        >
          <div
            className="tarika-script"
            style={{
              fontSize: '3.4rem',
              color: '#8E3642',
              lineHeight: 1.15,
              opacity: 0.85,
              textShadow: '0 2px 8px rgba(216, 114, 126, 0.2)'
            }}
          >
            Style
            <br />
            Create
            <br />
            Inspire
            <br />
            Repeat ♡
          </div>
        </div>

        {/* Center: Headline & Interactive Action */}
        <div
          style={{
            padding: '3rem 1.5rem',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center'
          }}
        >
          <h2
            className="tarika-serif"
            style={{
              fontSize: '3.2rem',
              fontWeight: 700,
              lineHeight: 1.15,
              color: '#1C1819',
              marginBottom: '1rem',
              letterSpacing: '-0.01em'
            }}
          >
            There's More
            <br />
            Waiting For You
          </h2>

          <p
            style={{
              fontSize: '0.95rem',
              lineHeight: 1.6,
              color: '#524348',
              maxWidth: '380px',
              marginBottom: '2rem'
            }}
          >
            Sign in to unlock your personal fashion space — save your favourites, get recommendations, and enjoy a seamless shopping experience.
          </p>

          <Link
            to={isAuthenticated ? '/customer' : '/login'}
            className="tarika-btn-primary"
            style={{
              padding: '0.95rem 2.2rem',
              fontSize: '0.95rem',
              marginBottom: '1rem'
            }}
          >
            <span>{isAuthenticated ? 'Go to My Wardrobe' : 'Login to Explore More'}</span>
            <ArrowRight size={18} />
          </Link>

          {!isAuthenticated && (
            <Link
              to="/signup"
              style={{
                fontSize: '0.86rem',
                fontWeight: 600,
                color: '#8E3642',
                textDecoration: 'none',
                transition: 'color 0.2s ease'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#D8727E')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#8E3642')}
            >
              New to TARIKA? <span style={{ textDecoration: 'underline' }}>Create Account</span>
            </Link>
          )}
        </div>

        {/* Right: Boutique Archway with Neon T */}
        <div
          className="zoom-container"
          style={{
            height: '100%',
            minHeight: '420px',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem 2rem 1.5rem 0'
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '400px',
              height: '360px',
              borderRadius: '200px 200px 24px 24px',
              overflow: 'hidden',
              boxShadow: '0 15px 40px rgba(184, 80, 94, 0.2)',
              border: '4px solid #FFFFFF'
            }}
          >
            <img
              src="/images/tarika_boutique_archway.jpg"
              alt="TARIKA Haute Boutique"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover'
              }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
