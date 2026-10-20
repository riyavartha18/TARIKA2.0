import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  Search,
  Heart,
  ShoppingBag,
  User,
  LogOut,
  Sparkles,
  ChevronDown,
  X,
  Flame,
  Tag,
  Compass,
  Package,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { useCustomer } from '../../context/CustomerContext';

export default function CustomerNavbar({ onSearchChange, searchTerm = '' }) {
  const { user, logout } = useAuth();
  const { wishlistItems, totalItems, subtotal, wishlistBounced, bagBounced } = useCustomer();
  const navigate = useNavigate();
  const location = useLocation();

  const [scrolled, setScrolled] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [localSearch, setLocalSearch] = useState(searchTerm);

  useEffect(() => {
    setLocalSearch(searchTerm);
  }, [searchTerm]);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (onSearchChange) {
      onSearchChange(localSearch);
    } else {
      navigate(`/customer/shop?search=${encodeURIComponent(localSearch)}`);
    }
  };

  const handleClearSearch = () => {
    setLocalSearch('');
    if (onSearchChange) {
      onSearchChange('');
    }
  };

  const navLinks = [
    { label: 'Customer Home', path: '/customer', icon: null },
    { label: 'Shop / Categories', path: '/customer/shop', icon: <Compass size={14} /> },
    { label: 'New In', path: '/customer/new-in', icon: <Sparkles size={14} /> },
    { label: 'Trending', path: '/customer/trending', icon: <Flame size={14} /> },
    { label: 'Sale', path: '/customer/sale', icon: <Tag size={14} /> },
  ];

  const currentPath = location.pathname;

  return (
    <header style={{ position: 'sticky', top: 0, zIndex: 200 }}>
      {/* 1. CONTINUOUS MOVING TICKER MARQUEE */}
      <div className="customer-marquee-wrap">
        <div className="customer-marquee-track">
          {[1, 2, 3].map((loop) => (
            <React.Fragment key={loop}>
              <span className="customer-marquee-item">
                <Sparkles size={13} /> TRENDING TOPS
              </span>
              <span className="customer-marquee-separator">•</span>
              <span className="customer-marquee-item">
                <Flame size={13} /> NEW DROPS
              </span>
              <span className="customer-marquee-separator">•</span>
              <span className="customer-marquee-item">
                NEW DRESSES
              </span>
              <span className="customer-marquee-separator">•</span>
              <span className="customer-marquee-item">
                EVERYDAY STYLES
              </span>
              <span className="customer-marquee-separator">•</span>
              <span className="customer-marquee-item">
                <Tag size={13} /> FLASH SALE UP TO 50% OFF
              </span>
              <span className="customer-marquee-separator">•</span>
              <span className="customer-marquee-item">
                COMPLIMENTARY EXPRESS DELIVERY
              </span>
              <span className="customer-marquee-separator">•</span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* 2. MAIN NAVIGATION BAR */}
      <nav
        style={{
          backgroundColor: scrolled ? 'rgba(255, 255, 255, 0.96)' : 'rgba(255, 255, 255, 0.92)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderBottom: '1px solid rgba(216, 114, 126, 0.18)',
          boxShadow: scrolled ? '0 4px 20px rgba(184, 80, 94, 0.08)' : '0 2px 10px rgba(0, 0, 0, 0.03)',
          transition: 'all 0.3s ease',
        }}
      >
        <div
          style={{
            maxWidth: '1680px',
            margin: '0 auto',
            padding: '0.75rem 2rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1.5rem',
          }}
        >
          {/* Brand Logo */}
          <Link
            to="/customer"
            style={{
              textDecoration: 'none',
              display: 'flex',
              flexDirection: 'column',
              lineHeight: 1,
              flexShrink: 0,
            }}
          >
            <span
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.75rem',
                fontWeight: 700,
                letterSpacing: '0.12em',
                background: 'linear-gradient(135deg, #1F191B 0%, #B8505E 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              TARIKA
            </span>
            <span
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontSize: '0.58rem',
                letterSpacing: '0.28em',
                color: '#8E3642',
                fontWeight: 700,
                textTransform: 'uppercase',
                marginTop: '2px',
              }}
            >
              HAUTE BOUTIQUE
            </span>
          </Link>

          {/* Navigation Categories / Sections */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1.5rem',
            }}
            className="customer-nav-desktop"
          >
            {navLinks.map((tab) => {
              const isActive =
                tab.path === '/customer'
                  ? currentPath === '/customer'
                  : currentPath.startsWith(tab.path);

              return (
                <Link
                  key={tab.path}
                  to={tab.path}
                  className={`customer-nav-link ${isActive ? 'active' : ''}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                  }}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </Link>
              );
            })}
          </div>

          {/* Search Input Bar */}
          <form
            onSubmit={handleSearchSubmit}
            style={{
              position: 'relative',
              maxWidth: '320px',
              width: '100%',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <input
              type="text"
              placeholder="Search tops, dresses, coords..."
              value={localSearch}
              onChange={(e) => {
                setLocalSearch(e.target.value);
                if (onSearchChange) onSearchChange(e.target.value);
              }}
              style={{
                width: '100%',
                padding: '0.55rem 2.2rem 0.55rem 2.2rem',
                backgroundColor: '#FAF7F5',
                border: '1px solid rgba(216, 114, 126, 0.25)',
                borderRadius: '9999px',
                fontSize: '0.85rem',
                color: '#1F191B',
                fontFamily: 'inherit',
                outline: 'none',
                transition: 'all 0.25s ease',
              }}
              onFocus={(e) => {
                e.target.style.borderColor = '#D8727E';
                e.target.style.backgroundColor = '#FFFFFF';
                e.target.style.boxShadow = '0 0 0 3px rgba(216, 114, 126, 0.15)';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'rgba(216, 114, 126, 0.25)';
                e.target.style.backgroundColor = '#FAF7F5';
                e.target.style.boxShadow = 'none';
              }}
            />
            <Search
              size={15}
              color="#B8505E"
              style={{
                position: 'absolute',
                left: '12px',
                pointerEvents: 'none',
              }}
            />
            {localSearch && (
              <button
                type="button"
                onClick={handleClearSearch}
                style={{
                  position: 'absolute',
                  right: '10px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#9E8F94',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={14} />
              </button>
            )}
          </form>

          {/* Action Icons: Wishlist, Bag, Profile */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
            {/* Wishlist Icon */}
            <Link
              to="/customer/wishlist"
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: currentPath === '/customer/wishlist' ? '#FBF1F0' : 'rgba(250, 247, 245, 0.8)',
                border: '1px solid rgba(216, 114, 126, 0.2)',
                color: currentPath === '/customer/wishlist' ? '#D8727E' : '#1F191B',
                transition: 'all 0.25s ease',
                textDecoration: 'none',
              }}
              title="View Wishlist"
            >
              <Heart
                size={18}
                className={wishlistBounced ? 'animate-heart-beat' : ''}
                fill={wishlistItems.length > 0 ? '#D8727E' : 'none'}
                color="#D8727E"
              />
              {wishlistItems.length > 0 && (
                <span className="customer-icon-badge">{wishlistItems.length}</span>
              )}
            </Link>

            {/* Shopping Bag Icon */}
            <Link
              to="/customer/bag"
              style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '0.45rem 0.85rem',
                borderRadius: '9999px',
                backgroundColor: currentPath === '/customer/bag' ? '#FBF1F0' : 'rgba(250, 247, 245, 0.8)',
                border: '1px solid rgba(216, 114, 126, 0.25)',
                color: '#1F191B',
                transition: 'all 0.25s ease',
                textDecoration: 'none',
              }}
              title="View Shopping Bag"
            >
              <ShoppingBag
                size={18}
                className={bagBounced ? 'animate-bag-bounce' : ''}
                color="#B8505E"
              />
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#B8505E' }}>
                  ₹{Number(subtotal).toLocaleString('en-IN')}
                </span>
              </div>
              {totalItems > 0 && (
                <span className="customer-icon-badge" style={{ position: 'static', marginLeft: '2px' }}>
                  {totalItems}
                </span>
              )}
            </Link>

            {/* User Profile Menu */}
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '0.45rem 0.75rem',
                  borderRadius: '9999px',
                  backgroundColor: '#FAF7F5',
                  border: '1px solid rgba(216, 114, 126, 0.2)',
                  cursor: 'pointer',
                  color: '#1F191B',
                  fontSize: '0.84rem',
                  fontWeight: 600,
                  transition: 'all 0.2s ease',
                }}
              >
                <div
                  style={{
                    width: '26px',
                    height: '26px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #D8727E 0%, #B8505E 100%)',
                    color: '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                  }}
                >
                  {user?.full_name ? user.full_name[0].toUpperCase() : 'C'}
                </div>
                <span style={{ maxWidth: '90px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {user?.full_name?.split(' ')[0] || 'Member'}
                </span>
                <ChevronDown size={14} color="#9E8F94" />
              </button>

              {/* Profile Dropdown Menu */}
              {profileDropdownOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: 'calc(100% + 8px)',
                    right: 0,
                    width: '210px',
                    backgroundColor: '#FFFFFF',
                    borderRadius: '16px',
                    border: '1px solid rgba(216, 114, 126, 0.2)',
                    boxShadow: '0 12px 36px rgba(184, 80, 94, 0.14)',
                    padding: '8px',
                    zIndex: 250,
                    animation: 'fadeIn 0.2s ease-out',
                  }}
                >
                  <div
                    style={{
                      padding: '8px 12px',
                      borderBottom: '1px solid rgba(240, 226, 224, 0.8)',
                      marginBottom: '4px',
                    }}
                  >
                    <p style={{ margin: 0, fontSize: '0.84rem', fontWeight: 700, color: '#1F191B' }}>
                      {user?.full_name || 'Valued Member'}
                    </p>
                    <p style={{ margin: 0, fontSize: '0.72rem', color: '#8E3642', fontWeight: 600 }}>
                      TARIKA VIP Club
                    </p>
                  </div>

                  <Link
                    to="/customer/profile"
                    onClick={() => setProfileDropdownOpen(false)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '9px 12px',
                      borderRadius: '10px',
                      textDecoration: 'none',
                      color: '#1F191B',
                      fontSize: '0.84rem',
                      fontWeight: 500,
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FBF1F0')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <User size={15} color="#B8505E" />
                    <span>My Profile & Perks</span>
                  </Link>

                  <Link
                    to="/customer/orders"
                    onClick={() => setProfileDropdownOpen(false)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '9px 12px',
                      borderRadius: '10px',
                      textDecoration: 'none',
                      color: '#1F191B',
                      fontSize: '0.84rem',
                      fontWeight: 500,
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FBF1F0')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <Package size={15} color="#B8505E" />
                    <span>My Orders</span>
                  </Link>

                  <Link
                    to="/customer/wishlist"
                    onClick={() => setProfileDropdownOpen(false)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '9px 12px',
                      borderRadius: '10px',
                      textDecoration: 'none',
                      color: '#1F191B',
                      fontSize: '0.84rem',
                      fontWeight: 500,
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FBF1F0')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <Heart size={15} color="#B8505E" />
                    <span>My Wishlist ({wishlistItems.length})</span>
                  </Link>

                  <Link
                    to="/customer/bag"
                    onClick={() => setProfileDropdownOpen(false)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '9px 12px',
                      borderRadius: '10px',
                      textDecoration: 'none',
                      color: '#1F191B',
                      fontSize: '0.84rem',
                      fontWeight: 500,
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FBF1F0')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <ShoppingBag size={15} color="#B8505E" />
                    <span>Shopping Bag ({totalItems})</span>
                  </Link>

                  <button
                    type="button"
                    onClick={() => {
                      setProfileDropdownOpen(false);
                      handleLogout();
                    }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '9px 12px',
                      borderRadius: '10px',
                      border: 'none',
                      background: 'none',
                      color: '#E04D60',
                      fontSize: '0.84rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      textAlign: 'left',
                      marginTop: '4px',
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#FFF1F2')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <LogOut size={15} color="#E04D60" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>
    </header>
  );
}
