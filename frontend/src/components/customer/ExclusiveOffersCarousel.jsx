import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Tag,
  Zap,
  Gift,
  Coins,
  ChevronLeft,
  ChevronRight,
  ArrowRight,
  Copy,
  Check,
} from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';
import { useAuth } from '../../auth/AuthContext';
import usePersonalizedOffers from '../../hooks/usePersonalizedOffers';

export default function ExclusiveOffersCarousel() {
  const { user } = useAuth();
  const { addToast } = useCustomer();
  const navigate = useNavigate();
  const { offers, loading } = usePersonalizedOffers();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [copiedCode, setCopiedCode] = useState(null);

  // Live countdown timer for first offer
  const [timeLeft, setTimeLeft] = useState({
    hours: '02',
    minutes: '14',
    seconds: '36',
  });

  useEffect(() => {
    let target = Date.now() + (2 * 3600 + 14 * 60 + 36) * 1000;
    const interval = setInterval(() => {
      const diff = Math.max(0, target - Date.now());
      const h = String(Math.floor(diff / (1000 * 60 * 60))).padStart(2, '0');
      const m = String(Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))).padStart(2, '0');
      const s = String(Math.floor((diff % (1000 * 60)) / 1000)).padStart(2, '0');
      setTimeLeft({ hours: h, minutes: m, seconds: s });
      if (diff <= 0) {
        target = Date.now() + 3 * 3600 * 1000;
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // CRITICAL REQUIREMENT: If the customer has NO applicable offers, do NOT show the section!
  if (loading) return null;
  if (!offers || offers.length === 0) {
    return null;
  }

  const handleCopy = (code) => {
    if (!code) return;
    navigator.clipboard?.writeText(code);
    setCopiedCode(code);
    addToast(`Offer coupon "${code}" copied to clipboard!`, 'success');
    setTimeout(() => setCopiedCode(null), 3000);
  };

  const firstName = (user?.full_name || user?.customer_name || 'Riya').trim().split(' ')[0];

  // Map each server-returned eligible offer directly to a themed carousel card
  const cards = offers.map((offer, idx) => {
    const segName = offer.target_segments?.[0] || 'EXCLUSIVE';
    const themeIndex = idx % 3;

    if (themeIndex === 0) {
      return {
        id: `offer-${offer.campaign_id || idx}`,
        theme: 'rose',
        badge: `${segName.toUpperCase()} SPECIAL`,
        icon: <Zap size={12} fill="#FFF" />,
        title: offer.offer_summary || offer.name || 'Special Discount',
        subtitle: offer.description || 'On selected boutique styles',
        code: offer.coupon_code,
        actionText: 'Explore Offer',
        actionLink: '/customer/shop',
        image: '/images/tarika_hero_pink_gown.jpg',
      };
    } else if (themeIndex === 1) {
      return {
        id: `offer-${offer.campaign_id || idx}`,
        theme: 'blush',
        badge: `${segName.toUpperCase()} BENEFIT`,
        icon: <Gift size={12} color="#B8505E" />,
        title: offer.offer_summary || offer.name || 'Member Reward',
        subtitle: offer.description || 'On your next order',
        code: offer.coupon_code,
        actionText: 'Apply Offer',
        actionLink: '/customer/shop',
        image: '/images/tarika_gift_box.jpg',
      };
    } else {
      return {
        id: `offer-${offer.campaign_id || idx}`,
        theme: 'gold',
        badge: `${segName.toUpperCase()} REWARD`,
        icon: <Coins size={12} color="#B5701B" />,
        title: offer.offer_summary || offer.name || 'Exclusive Privilege',
        subtitle: offer.description || 'Special boutique reward',
        code: offer.coupon_code,
        actionText: 'Use Coupon',
        actionLink: '/customer/shop',
        image: '/images/tarika_gold_coins.jpg',
      };
    }
  });

  // If customer only has 1 or 2 segment offers, append the Rewards Coins card as the 3rd card
  if (cards.length < 3) {
    cards.push({
      id: 'rewards-offer-perk',
      theme: 'gold',
      badge: 'REWARDS PRIVILEGE',
      icon: <Coins size={12} color="#B5701B" />,
      title: 'Redeem Your Coins',
      subtitle: 'Get up to ₹300 off on curated looks',
      code: 'COINS300',
      actionText: 'Use Coins',
      actionLink: '/customer/stylist',
      image: '/images/tarika_gold_coins.jpg',
    });
  }

  const nextSlide = () => {
    setCurrentIndex((prev) => (prev + 1) % cards.length);
  };

  const prevSlide = () => {
    setCurrentIndex((prev) => (prev - 1 + cards.length) % cards.length);
  };

  // Determine cards to display based on currentIndex
  const visibleCards = cards.length <= 3 
    ? cards 
    : [
        cards[currentIndex % cards.length],
        cards[(currentIndex + 1) % cards.length],
        cards[(currentIndex + 2) % cards.length],
      ];

  return (
    <section aria-label="Exclusive offers for you" style={{ marginBottom: '2.75rem' }}>
      {/* 1. Header Bar: Title on left, Counter & Controls on right */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.25rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              backgroundColor: '#FAF0F2',
              color: '#B8505E',
              border: '1px solid #F0D0D5',
            }}
          >
            <Tag size={15} />
          </div>
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.35rem',
              fontWeight: 700,
              color: '#8E3642',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <span>YOUR EXCLUSIVE OFFERS</span>
            <span style={{ color: '#C8A0A6', fontWeight: 300, fontSize: '1.2rem' }}>|</span>
            <span
              style={{
                fontFamily: "'Playfair Display', cursive, serif",
                fontStyle: 'italic',
                fontWeight: 500,
                fontSize: '1.25rem',
                color: '#B8505E',
                textTransform: 'none',
              }}
            >
              Just for you, {firstName}.
            </span>
          </h2>
        </div>

        {/* Counter and Arrows */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span
            style={{
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontSize: '0.86rem',
              fontWeight: 600,
              color: '#8E3642',
              letterSpacing: '0.08em',
            }}
          >
            0{currentIndex + 1} / 0{cards.length}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              type="button"
              onClick={prevSlide}
              aria-label="Previous Offer"
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                border: '1px solid rgba(184, 80, 94, 0.25)',
                backgroundColor: '#FFFFFF',
                color: '#8E3642',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#B8505E';
                e.currentTarget.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#FFFFFF';
                e.currentTarget.style.color = '#8E3642';
              }}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              type="button"
              onClick={nextSlide}
              aria-label="Next Offer"
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                border: '1px solid #B8505E',
                backgroundColor: '#B8505E',
                color: '#FFFFFF',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
                boxShadow: '0 2px 8px rgba(184, 80, 94, 0.2)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#8E3642';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#B8505E';
              }}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Offers Grid / Carousel */}
      <div
        className="exclusive-offers-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '1.25rem',
        }}
      >
        {visibleCards.map((card, cardIndex) => {
          if (card.theme === 'rose') {
            return (
              <div
                key={card.id}
                style={{
                  background: 'linear-gradient(135deg, #B83B50 0%, #8C2234 100%)',
                  borderRadius: '20px',
                  padding: '1.5rem',
                  color: '#FFFFFF',
                  position: 'relative',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  minHeight: '210px',
                  boxShadow: '0 8px 24px rgba(140, 34, 52, 0.18)',
                }}
              >
                {/* Top row: Badge and Countdown */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', zIndex: 2 }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      backgroundColor: 'rgba(255, 255, 255, 0.2)',
                      padding: '4px 10px',
                      borderRadius: '9999px',
                      backdropFilter: 'blur(8px)',
                    }}
                  >
                    {card.icon} {card.badge}
                  </span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '0.72rem', opacity: 0.85, fontWeight: 500 }}>Ends in</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <span
                        style={{
                          backgroundColor: '#FFFFFF',
                          color: '#8C2234',
                          padding: '2px 5px',
                          borderRadius: '4px',
                          fontSize: '0.74rem',
                          fontWeight: 800,
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {timeLeft.hours}
                      </span>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>:</span>
                      <span
                        style={{
                          backgroundColor: '#FFFFFF',
                          color: '#8C2234',
                          padding: '2px 5px',
                          borderRadius: '4px',
                          fontSize: '0.74rem',
                          fontWeight: 800,
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {timeLeft.minutes}
                      </span>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>:</span>
                      <span
                        style={{
                          backgroundColor: '#FFFFFF',
                          color: '#8C2234',
                          padding: '2px 5px',
                          borderRadius: '4px',
                          fontSize: '0.74rem',
                          fontWeight: 800,
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {timeLeft.seconds}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Middle: Title & Subtitle */}
                <div style={{ margin: '1rem 0', zIndex: 2, maxWidth: '65%' }}>
                  <h3
                    style={{
                      fontFamily: "'Playfair Display', serif",
                      fontSize: '1.75rem',
                      fontWeight: 700,
                      lineHeight: 1.15,
                      margin: '0 0 4px 0',
                    }}
                  >
                    {card.title}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.88rem', opacity: 0.9 }}>
                    {card.subtitle}
                  </p>
                </div>

                {/* Bottom Action */}
                <div style={{ zIndex: 2, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Link
                    to={card.actionLink}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      backgroundColor: '#FFFFFF',
                      color: '#8C2234',
                      padding: '0.45rem 1rem',
                      borderRadius: '9999px',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      textDecoration: 'none',
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.12)',
                    }}
                  >
                    <span>{card.actionText}</span>
                    <ArrowRight size={13} />
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleCopy(card.code)}
                    title="Copy code"
                    style={{
                      border: '1px solid rgba(255, 255, 255, 0.4)',
                      backgroundColor: 'rgba(255, 255, 255, 0.15)',
                      color: '#FFFFFF',
                      padding: '0.45rem 0.8rem',
                      borderRadius: '9999px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {copiedCode === card.code ? <Check size={12} /> : <Copy size={12} />}
                    <span>{card.code}</span>
                  </button>
                </div>

                {/* Right Background Model Overlay */}
                <div
                  style={{
                    position: 'absolute',
                    right: '-10px',
                    bottom: 0,
                    top: 0,
                    width: '45%',
                    overflow: 'hidden',
                    pointerEvents: 'none',
                  }}
                >
                  <img
                    src={card.image}
                    alt="Offer Model"
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      objectPosition: 'top center',
                      maskImage: 'linear-gradient(to right, transparent 0%, black 50%)',
                      WebkitMaskImage: 'linear-gradient(to right, transparent 0%, black 50%)',
                    }}
                  />
                </div>
              </div>
            );
          }

          if (card.theme === 'blush') {
            return (
              <div
                key={card.id}
                style={{
                  background: 'linear-gradient(135deg, #FFF6F5 0%, #FEECE9 100%)',
                  border: '1px solid #F5D3CD',
                  borderRadius: '20px',
                  padding: '1.5rem',
                  position: 'relative',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  minHeight: '210px',
                  boxShadow: '0 8px 24px rgba(184, 80, 94, 0.06)',
                }}
              >
                {/* Top Tag */}
                <div style={{ zIndex: 2 }}>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: '#B8505E',
                      backgroundColor: '#FAF0F2',
                      border: '1px solid #F0D0D5',
                      padding: '3px 9px',
                      borderRadius: '9999px',
                    }}
                  >
                    {card.icon} {card.badge}
                  </span>
                </div>

                {/* Middle Content */}
                <div style={{ margin: '1rem 0', zIndex: 2, maxWidth: '62%' }}>
                  <h3
                    style={{
                      fontFamily: "'Playfair Display', serif",
                      fontSize: '1.75rem',
                      fontWeight: 700,
                      color: '#1F191B',
                      lineHeight: 1.15,
                      margin: '0 0 4px 0',
                    }}
                  >
                    {card.title}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.88rem', color: '#6B5E63' }}>
                    {card.subtitle}
                  </p>
                </div>

                {/* Bottom Action */}
                <div style={{ zIndex: 2, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => {
                      handleCopy(card.code);
                      navigate(card.actionLink);
                    }}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      backgroundColor: '#B8505E',
                      color: '#FFFFFF',
                      padding: '0.45rem 1rem',
                      borderRadius: '9999px',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      boxShadow: '0 4px 12px rgba(184, 80, 94, 0.2)',
                    }}
                  >
                    <span>{card.actionText}</span>
                    <ArrowRight size={13} />
                  </button>
                  <span
                    style={{
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      color: '#8E3642',
                      backgroundColor: '#FAF0F2',
                      border: '1px dashed #F0D0D5',
                      padding: '0.35rem 0.65rem',
                      borderRadius: '6px',
                      cursor: 'pointer',
                    }}
                    onClick={() => handleCopy(card.code)}
                    title="Click to copy code"
                  >
                    {card.code}
                  </span>
                </div>

                {/* Right 3D Gift Box Graphic */}
                <div
                  style={{
                    position: 'absolute',
                    right: '12px',
                    bottom: '12px',
                    width: '125px',
                    height: '125px',
                    pointerEvents: 'none',
                  }}
                >
                  <img
                    src={card.image}
                    alt="Gift Graphic"
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'contain',
                      filter: 'drop-shadow(0 8px 16px rgba(184, 80, 94, 0.15))',
                    }}
                  />
                </div>
              </div>
            );
          }

          // Gold theme
          return (
            <div
              key={card.id}
              style={{
                background: 'linear-gradient(135deg, #FFFBF4 0%, #FDF3E5 100%)',
                border: '1px solid #F6E2C2',
                borderRadius: '20px',
                padding: '1.5rem',
                position: 'relative',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                minHeight: '210px',
                boxShadow: '0 8px 24px rgba(212, 139, 56, 0.06)',
              }}
            >
              {/* Top Tag */}
              <div style={{ zIndex: 2 }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    fontSize: '0.68rem',
                    fontWeight: 800,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: '#B5701B',
                    backgroundColor: '#FFF8EC',
                    border: '1px solid #F5E0BA',
                    padding: '3px 9px',
                    borderRadius: '9999px',
                  }}
                >
                  {card.icon} {card.badge}
                </span>
              </div>

              {/* Middle Content */}
              <div style={{ margin: '1rem 0', zIndex: 2, maxWidth: '62%' }}>
                <h3
                  style={{
                    fontFamily: "'Playfair Display', serif",
                    fontSize: '1.75rem',
                    fontWeight: 700,
                    color: '#1F191B',
                    lineHeight: 1.15,
                    margin: '0 0 4px 0',
                  }}
                >
                  {card.title}
                </h3>
                <p style={{ margin: 0, fontSize: '0.88rem', color: '#6B5E63' }}>
                  {card.subtitle}
                </p>
              </div>

              {/* Bottom Action */}
              <div style={{ zIndex: 2, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Link
                  to={card.actionLink}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: '#B8505E',
                    color: '#FFFFFF',
                    padding: '0.45rem 1rem',
                    borderRadius: '9999px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    textDecoration: 'none',
                    boxShadow: '0 4px 12px rgba(184, 80, 94, 0.2)',
                  }}
                >
                  <span>{card.actionText}</span>
                  <ArrowRight size={13} />
                </Link>
                <button
                  type="button"
                  onClick={() => handleCopy(card.code)}
                  title="Copy code"
                  style={{
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    color: '#945C16',
                    backgroundColor: '#FFF6E6',
                    border: '1px solid #F5E0BA',
                    padding: '0.35rem 0.65rem',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  {copiedCode === card.code ? <Check size={12} /> : <Copy size={12} />}
                  <span>{card.code}</span>
                </button>
              </div>

              {/* Right 3D Gold Coins Graphic */}
              <div
                style={{
                  position: 'absolute',
                  right: '12px',
                  bottom: '10px',
                  width: '120px',
                  height: '120px',
                  pointerEvents: 'none',
                }}
              >
                <img
                  src={card.image}
                  alt="Reward Coins"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    filter: 'drop-shadow(0 8px 16px rgba(212, 139, 56, 0.18))',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* 3. Subtle Pagination Dots */}
      {cards.length > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            marginTop: '1.25rem',
          }}
        >
          {cards.map((c, i) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setCurrentIndex(i)}
              aria-label={`Go to slide ${i + 1}`}
              style={{
                width: currentIndex === i ? '20px' : '8px',
                height: '8px',
                borderRadius: '9999px',
                backgroundColor: currentIndex === i ? '#B8505E' : '#E8D2D5',
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                padding: 0,
              }}
            />
          ))}
        </div>
      )}
    </section>
  );
}
