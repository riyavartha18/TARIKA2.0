import React, { useState } from 'react';
import { Heart, ShoppingBag, Eye, Star } from 'lucide-react';
import { NEW_ARRIVALS } from '../../data/tarikaData';

export default function NewArrivalsSection() {
  const [activeTab, setActiveTab] = useState('All');
  const [wishlist, setWishlist] = useState({});
  const [bagNotification, setBagNotification] = useState('');

  const tabs = ['All', 'Dresses', 'Co-ords', 'Knitwear', 'Accessories'];

  const filteredProducts = activeTab === 'All'
    ? NEW_ARRIVALS
    : NEW_ARRIVALS.filter((p) => p.category.toLowerCase() === activeTab.toLowerCase());

  const toggleWishlist = (id) => {
    setWishlist((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleAddToBag = (product) => {
    setBagNotification(`Added ${product.name} to bag`);
    setTimeout(() => setBagNotification(''), 3000);
  };

  return (
    <section
      id="new-arrivals"
      style={{
        padding: '3rem 2.5rem 4.5rem',
        maxWidth: '1680px',
        margin: '0 auto'
      }}
    >
      {/* Editorial Title & Filter Tabs */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          marginBottom: '2.5rem'
        }}
      >
        <span
          style={{
            fontSize: '0.78rem',
            fontWeight: 700,
            letterSpacing: '0.2em',
            color: '#D8727E',
            textTransform: 'uppercase',
            marginBottom: '0.4rem'
          }}
        >
          AUTUMN / WINTER 2026
        </span>

        <h2
          className="tarika-serif"
          style={{
            fontSize: '2.8rem',
            fontWeight: 700,
            color: '#1C1819',
            marginBottom: '0.6rem'
          }}
        >
          New Arrivals
        </h2>

        <p
          style={{
            fontSize: '1rem',
            color: '#6B5E63',
            maxWidth: '520px',
            marginBottom: '1.8rem'
          }}
        >
          Curated silhouettes, ethereal draping, and modern romantic tailoring engineered for your signature presence.
        </p>

        {/* Filter Tabs */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            backgroundColor: '#F7EFEF',
            padding: '0.35rem',
            borderRadius: '9999px',
            border: '1px solid rgba(216, 114, 126, 0.15)'
          }}
        >
          {tabs.map((tab) => {
            const isActive = tab === activeTab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  border: 'none',
                  backgroundColor: isActive ? '#FFFFFF' : 'transparent',
                  color: isActive ? '#8E3642' : '#6B5E63',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.84rem',
                  padding: '0.5rem 1.4rem',
                  borderRadius: '9999px',
                  cursor: 'pointer',
                  boxShadow: isActive ? '0 4px 12px rgba(216, 114, 126, 0.15)' : 'none',
                  transition: 'all 0.25s ease'
                }}
              >
                {tab}
              </button>
            );
          })}
        </div>
      </div>

      {/* Bag Notification Toast */}
      {bagNotification && (
        <div
          style={{
            position: 'fixed',
            bottom: '2rem',
            right: '2rem',
            backgroundColor: '#1C1819',
            color: '#FFFFFF',
            padding: '0.8rem 1.4rem',
            borderRadius: '12px',
            fontSize: '0.88rem',
            fontWeight: 500,
            boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            animation: 'fadeIn 0.3s ease'
          }}
        >
          <ShoppingBag size={18} color="#D8727E" />
          <span>{bagNotification}</span>
        </div>
      )}

      {/* 6 Product Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '1.4rem'
        }}
      >
        {filteredProducts.map((product) => {
          const isWishlisted = !!wishlist[product.id];
          return (
            <div
              key={product.id}
              className="tarika-product-card"
              style={{
                borderRadius: '18px',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              {/* Product Visual */}
              <div
                className="zoom-container"
                style={{
                  position: 'relative',
                  aspectRatio: '3 / 4',
                  backgroundColor: '#F5ECEB',
                  overflow: 'hidden'
                }}
              >
                <img
                  src={product.image}
                  alt={product.name}
                  loading="lazy"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    objectPosition: 'center top'
                  }}
                />

                {/* Badges: Left Top */}
                <div
                  style={{
                    position: 'absolute',
                    top: '0.8rem',
                    left: '0.8rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.35rem',
                    zIndex: 2
                  }}
                >
                  <span
                    className="tarika-badge"
                    style={{
                      backgroundColor: product.badgeType === 'new' ? '#D8727E' : '#B8505E'
                    }}
                  >
                    {product.badge}
                  </span>

                  {product.originalPrice > product.price && (
                    <span
                      className="tarika-badge"
                      style={{
                        backgroundColor: 'rgba(28, 24, 25, 0.85)',
                        backdropFilter: 'blur(4px)',
                        color: '#FFFFFF'
                      }}
                    >
                      ₹{(product.originalPrice - product.price).toLocaleString('en-IN')} OFF
                    </span>
                  )}
                </div>

                {/* Wishlist Heart Button */}
                <button
                  onClick={() => toggleWishlist(product.id)}
                  className={`wishlist-btn ${isWishlisted ? 'active' : ''}`}
                  aria-label={`Save ${product.name}`}
                >
                  <Heart
                    size={17}
                    fill={isWishlisted ? '#D8727E' : 'none'}
                    color={isWishlisted ? '#D8727E' : '#7D6F74'}
                  />
                </button>
              </div>

              {/* Product Info */}
              <div
                style={{
                  padding: '1.1rem 1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  flex: 1
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '0.35rem'
                  }}
                >
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      color: '#9E8F94',
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em'
                    }}
                  >
                    {product.category}
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                    <Star size={12} fill="#EAB308" color="#EAB308" />
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6B5E63' }}>
                      {product.rating}
                    </span>
                  </div>
                </div>

                <h3
                  style={{
                    fontSize: '0.92rem',
                    fontWeight: 600,
                    color: '#1C1819',
                    marginBottom: '0.6rem',
                    lineHeight: 1.35,
                    minHeight: '2.5rem',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden'
                  }}
                >
                  {product.name}
                </h3>

                {/* Price */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '0.5rem',
                    marginBottom: '0.9rem'
                  }}
                >
                  <span
                    style={{
                      fontSize: '1.05rem',
                      fontWeight: 700,
                      color: '#1C1819'
                    }}
                  >
                    ₹{product.price.toLocaleString('en-IN')}
                  </span>
                  {product.originalPrice && (
                    <span
                      style={{
                        fontSize: '0.82rem',
                        color: '#A3969B',
                        textDecoration: 'line-through'
                      }}
                    >
                      ₹{product.originalPrice.toLocaleString('en-IN')}
                    </span>
                  )}
                </div>

                {/* Add To Bag Button */}
                <button
                  onClick={() => handleAddToBag(product)}
                  style={{
                    marginTop: 'auto',
                    width: '100%',
                    padding: '0.65rem 0.8rem',
                    borderRadius: '10px',
                    border: '1px solid #E5D0CD',
                    backgroundColor: '#FAF7F5',
                    color: '#1C1819',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.45rem',
                    cursor: 'pointer',
                    transition: 'all 0.25s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#D8727E';
                    e.currentTarget.style.color = '#FFFFFF';
                    e.currentTarget.style.borderColor = '#D8727E';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#FAF7F5';
                    e.currentTarget.style.color = '#1C1819';
                    e.currentTarget.style.borderColor = '#E5D0CD';
                  }}
                >
                  <ShoppingBag size={14} />
                  <span>Add to Bag</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
