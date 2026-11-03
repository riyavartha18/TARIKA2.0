import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, Coins, ArrowRight, X, Copy, Check, Award } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { useCustomer } from '../../context/CustomerContext';
import { getCustomerCoins, spinRewardWheel } from '../../services/api';

const WHEEL_SEGMENTS = [
  { index: 0, label: '10% OFF', code: 'SPIN10', desc: 'Extra 10% off on your next order', bg: '#FFF5F2', color: '#8E3642' },
  { index: 1, label: '₹300 OFF', code: 'SPIN300', desc: 'Flat ₹300 off on orders above ₹1,999', bg: '#FCD8D2', color: '#B8505E' },
  { index: 2, label: 'FREE DELIVERY', code: 'FREESHIP', desc: 'Free express shipping on your order', bg: '#FEF6E4', color: '#9E671E' },
  { index: 3, label: '₹150 OFF', code: 'SPIN150', desc: 'Flat ₹150 off on orders above ₹999', bg: '#FCE4DF', color: '#B8505E' },
  { index: 4, label: '5% OFF', code: 'SPIN5', desc: 'Extra 5% off boutique styles', bg: '#FFF5F2', color: '#8E3642' },
  { index: 5, label: '20% OFF', code: 'SPIN20', desc: 'Extra 20% off on orders above ₹2,499', bg: '#FCD8D2', color: '#B8505E' },
];

export default function SpinRewardsWheelSection() {
  const { user, token } = useAuth();
  const { addToast } = useCustomer();

  const [availableCoins, setAvailableCoins] = useState(850); // Default elegant fallback matching screenshot
  const [isSpinning, setIsSpinning] = useState(false);
  const [rotationDegree, setRotationDegree] = useState(0);
  const [rewardModal, setRewardModal] = useState(null);
  const [copiedCode, setCopiedCode] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Fetch real customer coin balance if authenticated
  useEffect(() => {
    let alive = true;
    const cid = user?.customer_id || user?.id;
    if (cid || token) {
      getCustomerCoins(cid, token)
        .then((res) => {
          if (alive && res?.success && res.coins) {
            setAvailableCoins(res.coins.available_coins);
          }
        })
        .catch(() => {});
    }
    return () => { alive = false; };
  }, [user, token]);

  const handleSpin = async () => {
    if (isSpinning) return;
    setErrorMessage('');

    const cid = user?.customer_id || user?.id || 'CUST-0001';

    // Verify coin balance
    if (availableCoins < 50) {
      setErrorMessage('Each spin requires 50 coins. Shop to collect more coins!');
      addToast('Insufficient coins (50 required)', 'warning');
      return;
    }

    setIsSpinning(true);

    try {
      const res = await spinRewardWheel({ customerId: cid, token });

      let targetIndex = 1; // Default ₹300 OFF
      let rewardItem = WHEEL_SEGMENTS[1];

      if (res && res.success) {
        targetIndex = res.segment_index ?? 1;
        rewardItem = WHEEL_SEGMENTS[targetIndex] || WHEEL_SEGMENTS[1];
        if (res.new_available_coins !== undefined) {
          setAvailableCoins(res.new_available_coins);
        } else {
          setAvailableCoins((prev) => Math.max(0, prev - 50));
        }
      } else {
        // Graceful client fallback for demo if offline/guest
        targetIndex = Math.floor(Math.random() * WHEEL_SEGMENTS.length);
        rewardItem = WHEEL_SEGMENTS[targetIndex];
        setAvailableCoins((prev) => Math.max(0, prev - 50));
      }

      // Calculation of rotation:
      // 6 segments -> 60 degrees each
      // Top pointer points to the winning slice at top (0 deg).
      // Segment 0 is at [0, 60], center 30
      // To bring segment `targetIndex` under top pointer (270 or 0 deg), we rotate:
      const segmentAngle = 360 / WHEEL_SEGMENTS.length;
      const targetAngle = 360 - (targetIndex * segmentAngle + segmentAngle / 2);
      const extraSpins = 5 * 360; // 5 full rotations for drama
      const finalRotation = rotationDegree + extraSpins + targetAngle - (rotationDegree % 360);

      setRotationDegree(finalRotation);

      // Stop spinning after animation duration (4.2 seconds)
      setTimeout(() => {
        setIsSpinning(false);
        setRewardModal(rewardItem);
        addToast(`Won ${rewardItem.label}! Code: ${rewardItem.code}`, 'success');
      }, 4200);
    } catch (err) {
      console.error('Error during spin:', err);
      setIsSpinning(false);
      setErrorMessage('Something went wrong. Please try again.');
    }
  };

  const handleCopyCode = (code) => {
    navigator.clipboard?.writeText(code);
    setCopiedCode(true);
    addToast(`Coupon "${code}" copied!`, 'info');
    setTimeout(() => setCopiedCode(false), 2500);
  };

  return (
    <section
      aria-label="Spin and Earn Rewards"
      style={{
        marginBottom: '3.5rem',
        position: 'relative',
      }}
    >
      {/* Container Card with Blush Pink Satin Silk Waves & Gold Sparkles */}
      <div
        style={{
          background: 'linear-gradient(135deg, #FFF1EE 0%, #FEE5E1 45%, #FCD4CE 100%)',
          borderRadius: '24px',
          padding: '2.5rem 3rem',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          boxShadow: '0 12px 35px rgba(184, 80, 94, 0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '2rem',
          flexWrap: 'wrap',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Subtle Decorative Golden Sparkles in Background */}
        <div style={{ position: 'absolute', top: '15px', right: '40%', opacity: 0.7, pointerEvents: 'none' }}>
          <Sparkles size={20} color="#D48B38" />
        </div>
        <div style={{ position: 'absolute', bottom: '20px', left: '32%', opacity: 0.6, pointerEvents: 'none' }}>
          <Sparkles size={16} color="#D48B38" />
        </div>

        {/* 1. Left Text Info */}
        <div style={{ flex: '1 1 260px', zIndex: 2 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Sparkles size={22} color="#D48B38" />
            <h2
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '2rem',
                fontWeight: 700,
                color: '#1F191B',
                margin: 0,
                lineHeight: 1.15,
              }}
            >
              Spin &amp; Earn Coins
            </h2>
          </div>
          <p
            style={{
              fontSize: '0.94rem',
              color: '#6B5E63',
              lineHeight: 1.55,
              margin: '0 0 1rem 0',
              maxWidth: '320px',
            }}
          >
            Collect coins and unlock exciting discounts on your next purchase!
          </p>
          {errorMessage && (
            <div
              style={{
                fontSize: '0.8rem',
                color: '#B8505E',
                backgroundColor: '#FAF0F2',
                padding: '6px 12px',
                borderRadius: '8px',
                display: 'inline-block',
                marginBottom: '0.5rem',
              }}
            >
              {errorMessage}
            </div>
          )}
        </div>

        {/* 2. Center: Circular Fortune Wheel with Golden Lights and Top Pointer */}
        <div
          style={{
            flex: '0 0 auto',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            zIndex: 3,
            margin: '0 auto',
          }}
        >
          {/* Top Golden Fixed Pointer Arrow */}
          <div
            style={{
              position: 'absolute',
              top: '-14px',
              zIndex: 20,
              filter: 'drop-shadow(0 4px 6px rgba(0, 0, 0, 0.25))',
            }}
          >
            <div
              style={{
                width: 0,
                height: 0,
                borderLeft: '14px solid transparent',
                borderRight: '14px solid transparent',
                borderTop: '24px solid #C4384E',
              }}
            />
            <div
              style={{
                position: 'absolute',
                top: '-4px',
                left: '-10px',
                width: '20px',
                height: '8px',
                backgroundColor: '#FFD700',
                borderRadius: '4px',
              }}
            />
          </div>

          {/* Outer Golden Rim with Illuminated Light Bulbs */}
          <div
            style={{
              width: '280px',
              height: '280px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #F3D279 0%, #D49C30 50%, #FAF0CD 100%)',
              padding: '12px',
              boxShadow: '0 12px 30px rgba(184, 80, 94, 0.2), inset 0 2px 4px rgba(255, 255, 255, 0.8)',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {/* 16 Perimeter Golden Light Bulbs */}
            {Array.from({ length: 16 }).map((_, i) => {
              const angle = (i * 360) / 16;
              const rad = (angle * Math.PI) / 180;
              const r = 132;
              const x = r * Math.sin(rad);
              const y = -r * Math.cos(rad);
              return (
                <div
                  key={i}
                  style={{
                    position: 'absolute',
                    width: '9px',
                    height: '9px',
                    borderRadius: '50%',
                    backgroundColor: '#FFF7D6',
                    boxShadow: '0 0 8px 2px rgba(255, 235, 140, 0.9)',
                    transform: `translate(${x}px, ${y}px)`,
                  }}
                />
              );
            })}

            {/* Rotating Wheel Body */}
            <div
              style={{
                width: '100%',
                height: '100%',
                borderRadius: '50%',
                position: 'relative',
                overflow: 'hidden',
                boxShadow: 'inset 0 0 10px rgba(0, 0, 0, 0.15)',
                transform: `rotate(${rotationDegree}deg)`,
                transition: isSpinning
                  ? 'transform 4.2s cubic-bezier(0.12, 0.95, 0.2, 1)'
                  : 'none',
              }}
            >
              {/* SVG Slices */}
              <svg viewBox="0 0 200 200" style={{ width: '100%', height: '100%', display: 'block' }}>
                <defs>
                  <linearGradient id="slicePink" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#FEE4DE" />
                    <stop offset="100%" stopColor="#F8C8BF" />
                  </linearGradient>
                  <linearGradient id="sliceCream" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#FFF9F5" />
                    <stop offset="100%" stopColor="#FAEFEA" />
                  </linearGradient>
                  <linearGradient id="sliceGold" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#FFF7E6" />
                    <stop offset="100%" stopColor="#FBE9C4" />
                  </linearGradient>
                </defs>

                {/* 6 Segments of 60 degrees each */}
                {WHEEL_SEGMENTS.map((seg, i) => {
                  const startAngle = i * 60;
                  const endAngle = (i + 1) * 60;
                  const x1 = 100 + 100 * Math.cos((Math.PI * (startAngle - 90)) / 180);
                  const y1 = 100 + 100 * Math.sin((Math.PI * (startAngle - 90)) / 180);
                  const x2 = 100 + 100 * Math.cos((Math.PI * (endAngle - 90)) / 180);
                  const y2 = 100 + 100 * Math.sin((Math.PI * (endAngle - 90)) / 180);
                  const pathData = `M 100 100 L ${x1} ${y1} A 100 100 0 0 1 ${x2} ${y2} Z`;

                  const fill = i % 2 === 0 ? 'url(#sliceCream)' : (i === 2 ? 'url(#sliceGold)' : 'url(#slicePink)');

                  // Text rotation at middle of slice
                  const midAngle = startAngle + 30;
                  const textRad = (Math.PI * (midAngle - 90)) / 180;
                  const tx = 100 + 64 * Math.cos(textRad);
                  const ty = 100 + 64 * Math.sin(textRad);

                  return (
                    <g key={seg.index}>
                      <path d={pathData} fill={fill} stroke="#E8C2B8" strokeWidth="0.8" />
                      <text
                        x={tx}
                        y={ty}
                        fill={seg.color}
                        fontSize={seg.label.length > 8 ? '8.5' : '10'}
                        fontWeight="800"
                        fontFamily="'Plus Jakarta Sans', sans-serif"
                        textAnchor="middle"
                        dominantBaseline="central"
                        transform={`rotate(${midAngle + 90}, ${tx}, ${ty})`}
                      >
                        {seg.label}
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* Center Golden Badge: TARIKA REWARDS */}
              <div
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: '74px',
                  height: '74px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #FFF3D1 0%, #E8B44A 50%, #C48C24 100%)',
                  border: '3px solid #FFFFFF',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  lineHeight: 1.1,
                  textAlign: 'center',
                  color: '#6E4508',
                  padding: '4px',
                  boxSizing: 'border-box',
                }}
              >
                <span
                  style={{
                    fontFamily: "'Playfair Display', serif",
                    fontSize: '0.64rem',
                    fontWeight: 800,
                    letterSpacing: '0.08em',
                  }}
                >
                  TARIKA
                </span>
                <span
                  style={{
                    fontFamily: "'Plus Jakarta Sans', sans-serif",
                    fontSize: '0.48rem',
                    fontWeight: 700,
                    letterSpacing: '0.1em',
                  }}
                >
                  REWARDS
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Right: Coins Counter Pill and Spin Now CTA */}
        <div
          style={{
            flex: '1 1 220px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            justifyContent: 'center',
            gap: '1rem',
            zIndex: 2,
          }}
        >
          {/* Current Coins Pill Badge */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: '#FFFFFF',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              borderRadius: '9999px',
              padding: '0.6rem 1.4rem',
              boxShadow: '0 4px 16px rgba(184, 80, 94, 0.08)',
            }}
          >
            <div
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #F3D279 0%, #D49C30 100%)',
                color: '#6E4508',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.85rem',
                fontWeight: 800,
              }}
            >
              🪙
            </div>
            <span
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.25rem',
                fontWeight: 700,
                color: '#1F191B',
              }}
            >
              {availableCoins.toLocaleString()} Coins
            </span>
          </div>

          {/* Prominent Spin Now Button */}
          <button
            type="button"
            onClick={handleSpin}
            disabled={isSpinning}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: isSpinning ? '#D48B96' : '#B8505E',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '9999px',
              padding: '0.8rem 2rem',
              fontSize: '0.95rem',
              fontWeight: 700,
              cursor: isSpinning ? 'not-allowed' : 'pointer',
              boxShadow: '0 6px 20px rgba(184, 80, 94, 0.25)',
              transition: 'all 0.25s ease',
            }}
            onMouseEnter={(e) => {
              if (!isSpinning) e.currentTarget.style.backgroundColor = '#8E3642';
            }}
            onMouseLeave={(e) => {
              if (!isSpinning) e.currentTarget.style.backgroundColor = '#B8505E';
            }}
          >
            <span>{isSpinning ? 'Spinning...' : 'Spin Now'}</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>

      {/* 4. Celebratory Reward Modal */}
      {rewardModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(31, 25, 27, 0.55)',
            backdropFilter: 'blur(8px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
          }}
          onClick={() => setRewardModal(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              padding: '2.5rem 2rem',
              maxWidth: '420px',
              width: '100%',
              textAlign: 'center',
              boxShadow: '0 20px 50px rgba(0, 0, 0, 0.2)',
              position: 'relative',
              animation: 'scaleUp 0.3s ease',
              border: '1px solid #F0D0D5',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setRewardModal(null)}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                background: 'none',
                border: 'none',
                color: '#9E8F94',
                cursor: 'pointer',
              }}
            >
              <X size={20} />
            </button>

            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: '#FFF0F2',
                color: '#B8505E',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1.25rem auto',
                border: '2px solid #F5D3CD',
              }}
            >
              <Award size={32} />
            </div>

            <span
              style={{
                fontSize: '0.78rem',
                fontWeight: 800,
                color: '#B8505E',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}
            >
              Congratulations!
            </span>

            <h3
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.85rem',
                fontWeight: 700,
                color: '#1F191B',
                margin: '6px 0 8px 0',
              }}
            >
              You Won {rewardModal.label}!
            </h3>

            <p style={{ fontSize: '0.9rem', color: '#6B5E63', margin: '0 0 1.5rem 0' }}>
              {rewardModal.desc}
            </p>

            {/* Coupon Code Pill */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                backgroundColor: '#FAF5F5',
                border: '1px dashed #B8505E',
                borderRadius: '12px',
                padding: '0.75rem 1rem',
                marginBottom: '1.5rem',
              }}
            >
              <div>
                <span style={{ fontSize: '0.7rem', color: '#9E8F94', display: 'block', textAlign: 'left' }}>
                  PROMO CODE
                </span>
                <span
                  style={{
                    fontFamily: "'Plus Jakarta Sans', monospace",
                    fontSize: '1.1rem',
                    fontWeight: 800,
                    color: '#8E3642',
                    letterSpacing: '0.08em',
                  }}
                >
                  {rewardModal.code}
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleCopyCode(rewardModal.code)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  backgroundColor: '#B8505E',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '0.45rem 0.85rem',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {copiedCode ? <Check size={14} /> : <Copy size={14} />}
                <span>{copiedCode ? 'Copied' : 'Copy'}</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => setRewardModal(null)}
              style={{
                width: '100%',
                backgroundColor: '#1F191B',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '9999px',
                padding: '0.75rem',
                fontSize: '0.9rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Claim &amp; Continue Shopping
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
