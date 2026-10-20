import React, { useState, useEffect, useRef } from 'react';
import { ArrowRight, ChevronLeft, ChevronRight, Star, ArrowDown } from 'lucide-react';
import { HERO_SLIDES } from '../../data/tarikaData';

export default function HeroSlideshow() {
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const timerRef = useRef(null);

  const currentSlide = HERO_SLIDES[currentSlideIndex];

  // 5-second autoplay timer
  useEffect(() => {
    if (isPaused) return;

    timerRef.current = setInterval(() => {
      setCurrentSlideIndex((prev) => (prev + 1) % HERO_SLIDES.length);
    }, 5000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPaused, currentSlideIndex]);

  const handlePrev = () => {
    setCurrentSlideIndex((prev) => (prev === 0 ? HERO_SLIDES.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setCurrentSlideIndex((prev) => (prev + 1) % HERO_SLIDES.length);
  };

  const goToSlide = (idx) => {
    setCurrentSlideIndex(idx);
  };

  return (
    <section
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      style={{
        position: 'relative',
        minHeight: '740px',
        maxHeight: '880px',
        height: '84vh',
        background: currentSlide.bgGradient,
        overflow: 'hidden',
        transition: 'background 0.8s ease'
      }}
    >
      <div
        style={{
          maxWidth: '1680px',
          margin: '0 auto',
          height: '100%',
          padding: '0 3.5rem',
          display: 'grid',
          gridTemplateColumns: '1.05fr 1.15fr',
          alignItems: 'center',
          position: 'relative',
          zIndex: 2
        }}
      >
        {/* Left Column: Editorial Headline & Actions */}
        <div
          key={`text-${currentSlide.id}`}
          className="animate-fade-in"
          style={{
            paddingRight: '2rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center'
          }}
        >
          {/* Brand/Eyebrow Tag */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
              marginBottom: '1rem'
            }}
          >
            <span
              className="tarika-serif"
              style={{
                fontSize: '1rem',
                fontWeight: 600,
                letterSpacing: '0.2em',
                color: '#8E3642',
                textTransform: 'uppercase'
              }}
            >
              {currentSlide.eyebrow || 'TARIKA'}
            </span>
          </div>

          {/* Main Headline with Serif + Script */}
          <h1
            className="tarika-serif"
            style={{
              fontSize: '4.4rem',
              fontWeight: 700,
              lineHeight: 1.08,
              color: '#1C1819',
              marginBottom: '0.2rem',
              letterSpacing: '-0.01em'
            }}
          >
            {currentSlide.titleLine1}
            <br />
            {currentSlide.titleLine2}
          </h1>

          {/* Calligraphic Script Accent */}
          <div
            className="tarika-script"
            style={{
              fontSize: '4.8rem',
              color: '#D8727E',
              lineHeight: 0.95,
              marginBottom: '1.5rem',
              paddingLeft: '0.5rem',
              textShadow: '0 2px 10px rgba(216, 114, 126, 0.15)'
            }}
          >
            {currentSlide.scriptText}
          </div>

          {/* Subtitle */}
          <p
            style={{
              fontSize: '1.1rem',
              lineHeight: 1.6,
              color: '#524348',
              maxWidth: '460px',
              marginBottom: '2.2rem',
              fontWeight: 400
            }}
          >
            {currentSlide.description}
          </p>

          {/* Buttons: Shop New Arrivals & Explore Sale */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1.25rem',
              marginBottom: '2.8rem'
            }}
          >
            <a
              href={currentSlide.primaryCta.href}
              className="tarika-btn-primary"
              style={{
                padding: '0.95rem 2.2rem',
                fontSize: '0.95rem'
              }}
            >
              <span>{currentSlide.primaryCta.label}</span>
              <ArrowRight size={18} />
            </a>

            <a
              href={currentSlide.secondaryCta.href}
              className="tarika-btn-outline"
              style={{
                padding: '0.95rem 2rem',
                fontSize: '0.95rem'
              }}
            >
              <span>{currentSlide.secondaryCta.label}</span>
            </a>
          </div>

          {/* Social Proof Badges matching reference */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              paddingTop: '0.8rem',
              borderTop: '1px solid rgba(216, 114, 126, 0.2)',
              maxWidth: '420px'
            }}
          >
            {/* Avatars */}
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <img
                src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"
                alt="Client 1"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  border: '2px solid #FFFFFF',
                  objectFit: 'cover'
                }}
              />
              <img
                src="https://images.unsplash.com/photo-1517841905240-472988babdf9?w=100&auto=format&fit=crop&q=80"
                alt="Client 2"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  border: '2px solid #FFFFFF',
                  objectFit: 'cover',
                  marginLeft: '-10px'
                }}
              />
              <img
                src="https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=100&auto=format&fit=crop&q=80"
                alt="Client 3"
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  border: '2px solid #FFFFFF',
                  objectFit: 'cover',
                  marginLeft: '-10px'
                }}
              />
            </div>

            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1C1819' }}>
                10K+ Happy Customers
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.1rem' }}>
                <div style={{ display: 'flex', color: '#EAB308' }}>
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} size={12} fill="#EAB308" color="#EAB308" />
                  ))}
                </div>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#6B5E63' }}>
                  4.8/5
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Hero Fashion Visual */}
        <div
          key={`img-${currentSlide.id}`}
          className="animate-fade-in"
          style={{
            position: 'relative',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          {/* Main Visual Frame */}
          <div
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '580px',
              height: '92%',
              maxHeight: '680px',
              borderRadius: '28px',
              overflow: 'hidden',
              boxShadow: '0 25px 60px rgba(184, 80, 94, 0.18)',
              border: '4px solid #FFFFFF'
            }}
          >
            <img
              src={currentSlide.image}
              alt={currentSlide.titleLine1}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                objectPosition: 'center top',
                transition: 'transform 8s ease'
              }}
            />

            {/* Subtle editorial gradient overlay at bottom */}
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: '18%',
                background: 'linear-gradient(to top, rgba(0, 0, 0, 0.35) 0%, transparent 100%)',
                pointerEvents: 'none'
              }}
            />
          </div>

          {/* Editorial Caption Tag in reference: "FASHION BEGINS WITH A FEELING" */}
          <div
            style={{
              position: 'absolute',
              bottom: '2.5rem',
              right: '-1rem',
              textAlign: 'right',
              pointerEvents: 'none'
            }}
          >
            <div
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                letterSpacing: '0.22em',
                color: '#6B5E63',
                textTransform: 'uppercase'
              }}
            >
              FASHION
            </div>
            <div
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                letterSpacing: '0.22em',
                color: '#6B5E63',
                textTransform: 'uppercase'
              }}
            >
              BEGINS
            </div>
            <div
              className="tarika-serif"
              style={{
                fontSize: '0.92rem',
                fontWeight: 700,
                letterSpacing: '0.14em',
                color: '#8E3642',
                textTransform: 'uppercase',
                marginTop: '0.2rem'
              }}
            >
              WITH A FEELING
            </div>
          </div>
        </div>
      </div>

      {/* Slide Navigation Controls */}
      {/* Previous / Next Arrow Buttons */}
      <button
        onClick={handlePrev}
        aria-label="Previous Slide"
        style={{
          position: 'absolute',
          left: '1.5rem',
          top: '50%',
          transform: 'translateY(-50%)',
          zIndex: 10,
          width: '46px',
          height: '46px',
          borderRadius: '50%',
          backgroundColor: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          color: '#1C1819',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          boxShadow: '0 4px 15px rgba(0, 0, 0, 0.06)',
          transition: 'all 0.25s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#FFFFFF';
          e.currentTarget.style.color = '#D8727E';
          e.currentTarget.style.transform = 'translateY(-50%) scale(1.08)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.85)';
          e.currentTarget.style.color = '#1C1819';
          e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
        }}
      >
        <ChevronLeft size={22} />
      </button>

      <button
        onClick={handleNext}
        aria-label="Next Slide"
        style={{
          position: 'absolute',
          right: '1.5rem',
          top: '50%',
          transform: 'translateY(-50%)',
          zIndex: 10,
          width: '46px',
          height: '46px',
          borderRadius: '50%',
          backgroundColor: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(8px)',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          color: '#1C1819',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          boxShadow: '0 4px 15px rgba(0, 0, 0, 0.06)',
          transition: 'all 0.25s ease'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#FFFFFF';
          e.currentTarget.style.color = '#D8727E';
          e.currentTarget.style.transform = 'translateY(-50%) scale(1.08)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.85)';
          e.currentTarget.style.color = '#1C1819';
          e.currentTarget.style.transform = 'translateY(-50%) scale(1)';
        }}
      >
        <ChevronRight size={22} />
      </button>

      {/* Vertical Slide Indicators (01, 02, 03, 04) matching reference */}
      <div
        style={{
          position: 'absolute',
          right: '3.5rem',
          top: '20%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '0.8rem',
          zIndex: 10
        }}
      >
        {HERO_SLIDES.map((slide, idx) => {
          const isActive = idx === currentSlideIndex;
          return (
            <button
              key={slide.id}
              onClick={() => goToSlide(idx)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.2rem',
                color: isActive ? '#D8727E' : '#A3969B',
                transition: 'all 0.2s ease'
              }}
            >
              <span
                style={{
                  fontSize: '0.78rem',
                  fontWeight: isActive ? 700 : 500,
                  letterSpacing: '0.08em'
                }}
              >
                {slide.slideNum}
              </span>
              <div
                style={{
                  width: isActive ? '24px' : '8px',
                  height: '2px',
                  backgroundColor: isActive ? '#D8727E' : 'rgba(216, 114, 126, 0.3)',
                  borderRadius: '2px',
                  transition: 'all 0.3s ease'
                }}
              />
            </button>
          );
        })}
      </div>

      {/* Down Arrow scroll trigger circle button */}
      <a
        href="#categories"
        aria-label="Scroll to Categories"
        style={{
          position: 'absolute',
          bottom: '2.5rem',
          right: '5.5rem',
          width: '42px',
          height: '42px',
          borderRadius: '50%',
          backgroundColor: '#FFFFFF',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#8E3642',
          boxShadow: '0 6px 18px rgba(216, 114, 126, 0.15)',
          cursor: 'pointer',
          textDecoration: 'none',
          transition: 'all 0.25s ease',
          zIndex: 10
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(3px)';
          e.currentTarget.style.backgroundColor = '#FDF1F0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.backgroundColor = '#FFFFFF';
        }}
      >
        <ArrowDown size={18} />
      </a>
    </section>
  );
}
