import React, { useState } from 'react';
import { ArrowRight, Heart, ChevronRight, ShoppingBag } from 'lucide-react';
import { TRENDING_PRODUCTS } from '../../data/tarikaData';

export default function TrendingSection() {
  const [wishlist, setWishlist] = useState({});

  const toggleWishlist = (id) => {
    setWishlist((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  return (
    <section
      id="trending"
      style={{
        padding: '2rem 2.5rem 4rem',
        maxWidth: '1680px',
        margin: '0 auto'
      }}
    >
      {/* Editorial Header with Horizontal Line & View All */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '2rem',
          gap: '1.5rem'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flex: 1 }}>
          <h2
            className="tarika-serif"
            style={{
              fontSize: '2.2rem',
              fontWeight: 700,
              color: '#1C1819',
              whiteSpace: 'nowrap'
            }}
          >
            Trending Now
          </h2>
          <div
            style={{
              height: '1px',
              backgroundColor: '#E5D0CD',
              flex: 1
            }}
          />
        </div>

        <a
          href="#new-arrivals"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            fontSize: '0.88rem',
            fontWeight: 600,
            color: '#8E3642',
            textDecoration: 'none',
            whiteSpace: 'nowrap',
            transition: 'color 0.2s ease'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = '#D8727E')}
          onMouseLeave={(e) => (e.currentTarget.style.color = '#8E3642')}
        >
          <span>View All</span>
          <ArrowRight size={16} />
        </a>
      </div>

      {/* 6 Products Grid matching reference */}
      <div style={{ position: 'relative' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(6, 1fr)',
            gap: '1.25rem'
          }}
        >
          {TRENDING_PRODUCTS.map((product) => {
            const isWishlisted = !!wishlist[product.id];
            return (
              <div
                key={product.id}
                className="tarika-product-card"
                style={{ borderRadius: '16px' }}
              >
                {/* Image & Badges */}
                <div
                  className="zoom-container"
                  style={{
                    position: 'relative',
                    aspectRatio: '3 / 4',
                    backgroundColor: '#F7EFEF',
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

                  {/* Badge */}
                  {product.badge && (
                    <div
                      style={{
                        position: 'absolute',
                        top: '0.85rem',
                        left: '0.85rem',
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
                    </div>
                  )}

                  {/* Wishlist Heart */}
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

                {/* Info */}
                <div style={{ padding: '1rem 0.85rem 1.15rem' }}>
                  <h3
                    style={{
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      color: '#1C1819',
                      marginBottom: '0.35rem',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}
                  >
                    {product.name}
                  </h3>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{
                        fontSize: '0.96rem',
                        fontWeight: 700,
                        color: '#1C1819'
                      }}
                    >
                      ₹{product.price.toLocaleString('en-IN')}
                    </span>
                    {product.originalPrice && (
                      <span
                        style={{
                          fontSize: '0.8rem',
                          color: '#A3969B',
                          textDecoration: 'line-through'
                        }}
                      >
                        ₹{product.originalPrice.toLocaleString('en-IN')}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Carousel Next Arrow Circle on the right edge */}
        <button
          aria-label="Next Products"
          style={{
            position: 'absolute',
            right: '-1.25rem',
            top: '40%',
            transform: 'translateY(-50%)',
            width: '42px',
            height: '42px',
            borderRadius: '50%',
            backgroundColor: '#FFFFFF',
            border: '1px solid rgba(216, 114, 126, 0.25)',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#1C1819',
            zIndex: 10,
            transition: 'all 0.25s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#FDF1F0';
            e.currentTarget.style.color = '#D8727E';
            e.currentTarget.style.transform = 'translateY(-50%) scale(1.08)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#FFFFFF';
            e.currentTarget.style.color = '#1C1819';
            e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
          }}
        >
          <ChevronRight size={20} />
        </button>
      </div>
    </section>
  );
}
