import React, { useState } from 'react';
import { ArrowRight, Heart } from 'lucide-react';

export default function PromoBanners() {
  const [wishlistActive1, setWishlistActive1] = useState(false);
  const [wishlistActive2, setWishlistActive2] = useState(false);

  return (
    <section
      id="promos"
      style={{
        padding: '1.5rem 2.5rem 3.5rem',
        maxWidth: '1680px',
        margin: '0 auto'
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '2rem'
        }}
      >
        {/* Banner 1: NEW SEASON NEW YOU */}
        <div
          style={{
            position: 'relative',
            borderRadius: '24px',
            backgroundColor: '#FDEEEB',
            background: 'linear-gradient(135deg, #FDEEEB 0%, #F8DFDC 100%)',
            overflow: 'hidden',
            display: 'grid',
            gridTemplateColumns: '1fr 1.15fr',
            alignItems: 'center',
            minHeight: '380px',
            boxShadow: '0 12px 35px rgba(216, 114, 126, 0.12)',
            border: '1px solid rgba(216, 114, 126, 0.2)'
          }}
        >
          {/* Wishlist Heart Icon */}
          <button
            onClick={() => setWishlistActive1(!wishlistActive1)}
            className={`wishlist-btn ${wishlistActive1 ? 'active' : ''}`}
            aria-label="Save to Wishlist"
          >
            <Heart size={18} fill={wishlistActive1 ? '#D8727E' : 'none'} color={wishlistActive1 ? '#D8727E' : '#7D6F74'} />
          </button>

          {/* Text Content */}
          <div style={{ padding: '2.5rem 2rem 2.5rem 2.5rem', zIndex: 2 }}>
            <h2
              className="tarika-serif"
              style={{
                fontSize: '2.6rem',
                fontWeight: 700,
                lineHeight: 1.12,
                color: '#1C1819',
                marginBottom: '1rem',
                letterSpacing: '-0.01em'
              }}
            >
              NEW SEASON
              <br />
              NEW YOU
            </h2>

            <p
              style={{
                fontSize: '0.95rem',
                lineHeight: 1.55,
                color: '#524348',
                marginBottom: '1.8rem',
                maxWidth: '240px'
              }}
            >
              Fresh styles. Bolder looks.
              <br />
              Make it yours.
            </p>

            <a
              href="#new-arrivals"
              className="tarika-btn-primary"
              style={{
                padding: '0.8rem 1.6rem',
                fontSize: '0.88rem'
              }}
            >
              <span>Explore Collection</span>
              <ArrowRight size={16} />
            </a>
          </div>

          {/* Right Image */}
          <div
            className="zoom-container"
            style={{
              height: '100%',
              minHeight: '380px',
              position: 'relative'
            }}
          >
            <img
              src="/images/tarika_promo_new_season.jpg"
              alt="New Season New You"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                objectPosition: 'center'
              }}
            />
          </div>
        </div>

        {/* Banner 2: SALE UP TO 50% OFF */}
        <div
          style={{
            position: 'relative',
            borderRadius: '24px',
            backgroundColor: '#FDECE9',
            background: 'linear-gradient(135deg, #FDECE9 0%, #F5DAD7 100%)',
            overflow: 'hidden',
            display: 'grid',
            gridTemplateColumns: '1fr 1.15fr',
            alignItems: 'center',
            minHeight: '380px',
            boxShadow: '0 12px 35px rgba(216, 114, 126, 0.12)',
            border: '1px solid rgba(216, 114, 126, 0.2)'
          }}
        >
          {/* Wishlist Heart Icon */}
          <button
            onClick={() => setWishlistActive2(!wishlistActive2)}
            className={`wishlist-btn ${wishlistActive2 ? 'active' : ''}`}
            aria-label="Save to Wishlist"
          >
            <Heart size={18} fill={wishlistActive2 ? '#D8727E' : 'none'} color={wishlistActive2 ? '#D8727E' : '#7D6F74'} />
          </button>

          {/* Text Content */}
          <div style={{ padding: '2.5rem 2rem 2.5rem 2.5rem', zIndex: 2 }}>
            <h2
              className="tarika-serif"
              style={{
                fontSize: '2.6rem',
                fontWeight: 700,
                lineHeight: 1.12,
                color: '#D8727E',
                marginBottom: '1rem',
                letterSpacing: '-0.01em'
              }}
            >
              SALE
              <br />
              <span style={{ fontSize: '2.1rem', color: '#1C1819', fontWeight: 600 }}>
                UP TO 50% OFF
              </span>
            </h2>

            <p
              style={{
                fontSize: '0.95rem',
                lineHeight: 1.55,
                color: '#524348',
                marginBottom: '1.8rem',
                maxWidth: '240px'
              }}
            >
              On selected styles
              <br />
              Only for a limited time.
            </p>

            <a
              href="#trending"
              className="tarika-btn-primary"
              style={{
                padding: '0.8rem 1.6rem',
                fontSize: '0.88rem'
              }}
            >
              <span>Shop Sale</span>
              <ArrowRight size={16} />
            </a>
          </div>

          {/* Right Image */}
          <div
            className="zoom-container"
            style={{
              height: '100%',
              minHeight: '380px',
              position: 'relative'
            }}
          >
            <img
              src="/images/tarika_promo_sale.jpg"
              alt="Sale Up to 50% Off"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                objectPosition: 'center'
              }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
