import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, Heart, ShoppingBag, User, LogOut, Sparkles } from 'lucide-react';
import { useAuth, ROLE_ROUTES } from '../../auth/AuthContext';

export default function Navbar() {
  const { user, isAuthenticated, role, logout } = useAuth();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const dashboardRoute = (role && ROLE_ROUTES[role]) || '/customer';

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        backgroundColor: scrolled ? 'rgba(255, 255, 255, 0.94)' : 'rgba(255, 255, 255, 0.88)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: scrolled ? '1px solid rgba(216, 114, 126, 0.18)' : '1px solid rgba(216, 114, 126, 0.1)',
        boxShadow: scrolled ? '0 4px 25px rgba(216, 114, 126, 0.08)' : 'none',
        transition: 'all 0.35s ease'
      }}
    >
      <div
        style={{
          maxWidth: '1680px',
          margin: '0 auto',
          padding: '0.85rem 2.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1.5rem'
        }}
      >
        {/* Left: Brand Logo & Tagline */}
        <Link
          to="/"
          style={{
            textDecoration: 'none',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            cursor: 'pointer'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span
              className="tarika-serif"
              style={{
                fontSize: '1.75rem',
                fontWeight: 700,
                letterSpacing: '0.22em',
                color: '#1C1819',
                lineHeight: 1.1
              }}
            >
              TARIKA
            </span>
          </div>
          <span
            style={{
              fontSize: '0.58rem',
              fontWeight: 600,
              letterSpacing: '0.2em',
              color: '#D8727E',
              textTransform: 'uppercase',
              marginTop: '0.1rem'
            }}
          >
            STYLE YOUR STORY
          </span>
        </Link>

        {/* Center: Navigation Links */}
        <nav
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '2.2rem'
          }}
        >
          <a
            href="#new-arrivals"
            style={{
              textDecoration: 'none',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#382E32',
              letterSpacing: '0.02em',
              transition: 'color 0.2s ease',
              position: 'relative'
            }}
            onMouseEnter={(e) => (e.target.style.color = '#D8727E')}
            onMouseLeave={(e) => (e.target.style.color = '#382E32')}
          >
            New Arrivals
          </a>

          <a
            href="#categories"
            style={{
              textDecoration: 'none',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#382E32',
              letterSpacing: '0.02em',
              transition: 'color 0.2s ease'
            }}
            onMouseEnter={(e) => (e.target.style.color = '#D8727E')}
            onMouseLeave={(e) => (e.target.style.color = '#382E32')}
          >
            Women
          </a>

          <a
            href="#categories"
            style={{
              textDecoration: 'none',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#382E32',
              letterSpacing: '0.02em',
              transition: 'color 0.2s ease'
            }}
            onMouseEnter={(e) => (e.target.style.color = '#D8727E')}
            onMouseLeave={(e) => (e.target.style.color = '#382E32')}
          >
            Men
          </a>

          <a
            href="#trending"
            style={{
              textDecoration: 'none',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#382E32',
              letterSpacing: '0.02em',
              transition: 'color 0.2s ease'
            }}
            onMouseEnter={(e) => (e.target.style.color = '#D8727E')}
            onMouseLeave={(e) => (e.target.style.color = '#382E32')}
          >
            Collections
          </a>

          <a
            href="#promos"
            style={{
              textDecoration: 'none',
              fontSize: '0.88rem',
              fontWeight: 700,
              color: '#D8727E',
              letterSpacing: '0.04em',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            Sale
            <span
              style={{
                fontSize: '0.62rem',
                backgroundColor: '#D8727E',
                color: '#ffffff',
                padding: '0.1rem 0.4rem',
                borderRadius: '9999px',
                fontWeight: 700
              }}
            >
              50% OFF
            </span>
          </a>
        </nav>

        {/* Right: Search, Wishlist, Bag, Auth Buttons */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1.25rem'
          }}
        >
          {/* Search Bar matching reference pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: '#F7EFEF',
              borderRadius: '9999px',
              padding: '0.5rem 1.15rem',
              width: '260px',
              border: '1px solid rgba(216, 114, 126, 0.15)',
              transition: 'all 0.25s ease'
            }}
          >
            <input
              type="text"
              placeholder="Search for dresses, tops, more..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                border: 'none',
                background: 'transparent',
                outline: 'none',
                width: '100%',
                fontSize: '0.82rem',
                color: '#1C1819',
                fontFamily: 'inherit'
              }}
            />
            <Search size={16} color="#9E8F94" style={{ flexShrink: 0, marginLeft: '0.4rem' }} />
          </div>

          {/* Wishlist Heart Icon */}
          <button
            aria-label="Wishlist"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0.4rem',
              color: '#382E32',
              transition: 'color 0.2s ease'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#D8727E')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#382E32')}
          >
            <Heart size={21} />
            <span
              style={{
                position: 'absolute',
                top: '0px',
                right: '0px',
                backgroundColor: '#D8727E',
                color: '#FFFFFF',
                fontSize: '0.62rem',
                fontWeight: 700,
                width: '15px',
                height: '15px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              2
            </span>
          </button>

          {/* Bag Icon */}
          <button
            aria-label="Shopping Bag"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0.4rem',
              color: '#382E32',
              transition: 'color 0.2s ease'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#D8727E')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#382E32')}
          >
            <ShoppingBag size={21} />
            <span
              style={{
                position: 'absolute',
                top: '0px',
                right: '0px',
                backgroundColor: '#1C1819',
                color: '#FFFFFF',
                fontSize: '0.62rem',
                fontWeight: 700,
                width: '15px',
                height: '15px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              1
            </span>
          </button>

          {/* Auth Action Buttons */}
          {isAuthenticated ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Link
                to={dashboardRoute}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  backgroundColor: '#F7E4E2',
                  color: '#8E3642',
                  padding: '0.5rem 1rem',
                  borderRadius: '9999px',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  fontWeight: 600
                }}
              >
                <User size={15} />
                <span>{user?.first_name || 'My Account'}</span>
              </Link>
              <button
                onClick={handleLogout}
                title="Sign Out"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#6B5E63',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0.4rem',
                  transition: 'color 0.2s ease'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#E11D48')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#6B5E63')}
              >
                <LogOut size={18} />
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <Link
                to="/login"
                style={{
                  textDecoration: 'none',
                  fontSize: '0.86rem',
                  fontWeight: 600,
                  color: '#1C1819',
                  padding: '0.55rem 1.25rem',
                  borderRadius: '9999px',
                  border: '1px solid #E5D0CD',
                  backgroundColor: '#FFFFFF',
                  transition: 'all 0.25s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#D8727E';
                  e.currentTarget.style.color = '#D8727E';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#E5D0CD';
                  e.currentTarget.style.color = '#1C1819';
                }}
              >
                Login
              </Link>

              <Link
                to="/signup"
                style={{
                  textDecoration: 'none',
                  fontSize: '0.86rem',
                  fontWeight: 600,
                  color: '#FFFFFF',
                  padding: '0.55rem 1.45rem',
                  borderRadius: '9999px',
                  background: 'linear-gradient(135deg, #D8727E 0%, #C45766 100%)',
                  boxShadow: '0 4px 14px rgba(216, 114, 126, 0.35)',
                  transition: 'all 0.25s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 6px 18px rgba(216, 114, 126, 0.45)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 4px 14px rgba(216, 114, 126, 0.35)';
                }}
              >
                Sign Up
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
