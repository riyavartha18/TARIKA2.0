import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Flame,
  Tag,
  ArrowRight,
  Clock,
  ChevronRight,
  Gift,
  Zap,
} from 'lucide-react';
import ProductCard from '../../components/customer/ProductCard';
import {
  getCategories,
  getNewArrivals,
  getTrending,
  getSale,
} from '../../services/api';

export default function CustomerHome() {
  const navigate = useNavigate();

  // Dynamic API state
  const [categories, setCategories] = useState([]);
  const [newArrivals, setNewArrivals] = useState([]);
  const [trending, setTrending] = useState([]);
  const [saleItems, setSaleItems] = useState([]);
  const [loading, setLoading] = useState(true);

  // Live Flash Sale Countdown Timer (resets to 5h 24m 12s on fresh session)
  const [timeLeft, setTimeLeft] = useState({
    hours: 5,
    minutes: 24,
    seconds: 12,
  });

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev.seconds > 0) {
          return { ...prev, seconds: prev.seconds - 1 };
        } else if (prev.minutes > 0) {
          return { ...prev, minutes: prev.minutes - 1, seconds: 59 };
        } else if (prev.hours > 0) {
          return { hours: prev.hours - 1, minutes: 59, seconds: 59 };
        }
        return { hours: 12, minutes: 0, seconds: 0 };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch live catalog data
  useEffect(() => {
    async function loadHomeCatalog() {
      setLoading(true);
      try {
        const [catRes, newRes, trendRes, saleRes] = await Promise.all([
          getCategories(),
          getNewArrivals(8),
          getTrending(8),
          getSale(8),
        ]);

        if (catRes.success) setCategories(catRes.categories || []);
        if (newRes.success) setNewArrivals(newRes.products || []);
        if (trendRes.success) setTrending(trendRes.products || []);
        if (saleRes.success) setSaleItems(saleRes.products || []);
      } catch (err) {
        console.error('Failed to load home catalog', err);
      } finally {
        setLoading(false);
      }
    }
    loadHomeCatalog();
  }, []);

  // Trend Translation Editorial Cards (inspired by reference layout in pink luxury aesthetic)
  const trendTranslations = [
    {
      title: 'Campus Days',
      tagline: 'Effortless cool & casual coordinates',
      image: 'https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=700&q=80',
      category: 'Tops',
    },
    {
      title: 'Work Mode',
      tagline: 'Tailored silhouettes & crisp blouses',
      image: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=700&q=80',
      category: 'Bottoms',
    },
    {
      title: "Let's Celebrate",
      tagline: 'Cocktail midi gowns & satin couture',
      image: 'https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=700&q=80',
      category: 'Dresses',
    },
    {
      title: 'Brunch Club',
      tagline: 'Pastel ruffles & delicate sundresses',
      image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=700&q=80',
      category: 'Co-ords',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '3.5rem', paddingBottom: '4rem' }}>
      {/* 1. FLASH SALE HERO BANNER WITH LIVE COUNTDOWN */}
      <div className="flash-sale-banner">
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '2rem',
          }}
        >
          <div style={{ maxWidth: '580px' }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 14px',
                borderRadius: '9999px',
                backgroundColor: 'rgba(255, 255, 255, 0.85)',
                color: '#B8505E',
                fontSize: '0.78rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: '1rem',
              }}
            >
              <Sparkles size={14} />
              <span>Exclusive Member Drop</span>
            </div>

            <h1
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '2.5rem',
                fontWeight: 700,
                color: '#1F191B',
                lineHeight: 1.15,
                margin: '0 0 0.75rem 0',
              }}
            >
              FLASH SALE <span style={{ color: '#D8727E' }}>UP TO 70% OFF</span>
            </h1>

            <p style={{ margin: '0 0 1.5rem 0', color: '#6B5E63', fontSize: '1rem', lineHeight: 1.5 }}>
              Handcrafted evening gowns, structured co-ords, and seasonal blouses curated for your story.
            </p>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <Link to="/customer/sale" className="tarika-btn-primary">
                <span>Shop Flash Sale</span>
                <ArrowRight size={16} />
              </Link>
              <Link to="/customer/new-in" className="tarika-btn-outline">
                Explore New In
              </Link>
            </div>
          </div>

          {/* Live Countdown Display */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '10px',
              padding: '1.5rem 2rem',
              background: 'rgba(255, 255, 255, 0.7)',
              backdropFilter: 'blur(12px)',
              borderRadius: '20px',
              border: '1px solid rgba(216, 114, 126, 0.25)',
              boxShadow: '0 8px 30px rgba(184, 80, 94, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#8E3642' }}>
              <Clock size={16} />
              <span style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Deals Ending In
              </span>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <div className="countdown-box">
                <span className="countdown-number">
                  {String(timeLeft.hours).padStart(2, '0')}
                </span>
                <span className="countdown-label">Hours</span>
              </div>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#B8505E', alignSelf: 'center' }}>
                :
              </span>
              <div className="countdown-box">
                <span className="countdown-number">
                  {String(timeLeft.minutes).padStart(2, '0')}
                </span>
                <span className="countdown-label">Mins</span>
              </div>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#B8505E', alignSelf: 'center' }}>
                :
              </span>
              <div className="countdown-box">
                <span className="countdown-number">
                  {String(timeLeft.seconds).padStart(2, '0')}
                </span>
                <span className="countdown-label">Secs</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. SPECIAL PROMOTIONAL OFFERS (Circular & Card Deals adapted to TARIKA Blush) */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
          <div>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.12em', color: '#8E3642', textTransform: 'uppercase' }}>
              Limited Time Perks
            </span>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.85rem', fontWeight: 700, margin: '2px 0 0 0', color: '#1F191B' }}>
              Special Offers
            </h2>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {/* Offer 1: All under ₹499 */}
          <div
            onClick={() => navigate('/customer/shop?max_price=500')}
            style={{
              background: 'linear-gradient(135deg, #FFF1F2 0%, #FFE4E6 100%)',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              borderRadius: '20px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 16px rgba(184, 80, 94, 0.08)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-4px)')}
            onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
          >
            <div
              style={{
                width: '100px',
                height: '100px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #FBF1F0 0%, #F5D3D1 100%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 6px 18px rgba(184, 80, 94, 0.15)',
                marginBottom: '1rem',
              }}
            >
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#6B5E63' }}>UNDER</span>
              <span style={{ fontSize: '1.4rem', fontWeight: 800, color: '#1F191B' }}>₹499</span>
            </div>
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
              Everyday Staples
            </span>
            <span className="offer-pill-btn">SHOP NOW &gt;&gt;</span>
          </div>

          {/* Offer 2: Buy 1 Get 1 */}
          <div
            onClick={() => navigate('/customer/shop')}
            style={{
              background: 'linear-gradient(135deg, #FBF1F0 0%, #F7E4E2 100%)',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              borderRadius: '20px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 16px rgba(184, 80, 94, 0.08)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-4px)')}
            onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
          >
            <div
              style={{
                width: '100px',
                height: '100px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #FFFFFF 0%, #FBF1F0 100%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 6px 18px rgba(184, 80, 94, 0.15)',
                marginBottom: '1rem',
              }}
            >
              <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>Buy 1</span>
              <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#D8727E' }}>Get 1</span>
            </div>
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
              Mix & Match Tops
            </span>
            <span className="offer-pill-btn">SHOP NOW &gt;&gt;</span>
          </div>

          {/* Offer 3: 20% Coupon Voucher */}
          <div
            onClick={() => navigate('/customer/sale')}
            style={{
              background: 'linear-gradient(135deg, #FFFDFB 0%, #FDF4F2 100%)',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              borderRadius: '20px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 16px rgba(184, 80, 94, 0.08)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-4px)')}
            onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
          >
            <div
              style={{
                width: '100px',
                height: '100px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #FBF1F0 0%, #F5D3D1 100%)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 6px 18px rgba(184, 80, 94, 0.15)',
                marginBottom: '1rem',
              }}
            >
              <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#8E3642' }}>COUPON</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#B8505E' }}>20% OFF</span>
            </div>
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
              TARIKA20 applied
            </span>
            <span className="offer-pill-btn">SHOP NOW &gt;&gt;</span>
          </div>

          {/* Offer 4: The Final Call Up to 60% */}
          <div
            onClick={() => navigate('/customer/sale')}
            style={{
              background: 'linear-gradient(135deg, #F9ECE9 0%, #F0CFCD 100%)',
              border: '1px solid rgba(216, 114, 126, 0.35)',
              borderRadius: '20px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 16px rgba(184, 80, 94, 0.08)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-4px)')}
            onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
          >
            <div
              style={{
                width: '100px',
                height: '100px',
                borderRadius: '50%',
                background: '#FFFFFF',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 6px 18px rgba(184, 80, 94, 0.15)',
                marginBottom: '1rem',
              }}
            >
              <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#6B5E63' }}>FINAL CALL</span>
              <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#B8505E' }}>-60%</span>
            </div>
            <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
              Archival Silhouettes
            </span>
            <span className="offer-pill-btn">SHOP NOW &gt;&gt;</span>
          </div>
        </div>
      </div>

      {/* 3. HORIZONTAL CATEGORIES SLIDER */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.12em', color: '#8E3642', textTransform: 'uppercase' }}>
              Explore By Wardrobe
            </span>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.85rem', fontWeight: 700, margin: '2px 0 0 0', color: '#1F191B' }}>
              Departments & Categories
            </h2>
          </div>
          <Link
            to="/customer/shop"
            style={{
              fontSize: '0.84rem',
              fontWeight: 700,
              color: '#B8505E',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>All Categories</span>
            <ChevronRight size={16} />
          </Link>
        </div>

        <div className="horizontal-scroll-row">
          {categories.map((cat) => (
            <div
              key={cat.id}
              className="scroll-snap-card"
              onClick={() => navigate(`/customer/shop?category=${encodeURIComponent(cat.slug || cat.name)}`)}
              style={{
                width: '140px',
                padding: '1rem 0.75rem',
                backgroundColor: '#FFFFFF',
                borderRadius: '16px',
                border: '1px solid rgba(240, 226, 224, 0.9)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all 0.25s ease',
                boxShadow: '0 4px 12px rgba(184, 80, 94, 0.04)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#D8727E';
                e.currentTarget.style.transform = 'translateY(-3px)';
                e.currentTarget.style.boxShadow = '0 8px 20px rgba(184, 80, 94, 0.12)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(240, 226, 224, 0.9)';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(184, 80, 94, 0.04)';
              }}
            >
              <div
                style={{
                  width: '54px',
                  height: '54px',
                  borderRadius: '50%',
                  backgroundColor: '#FAF7F5',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '0.75rem',
                  color: '#B8505E',
                  fontWeight: 700,
                  fontSize: '1.2rem',
                }}
              >
                {cat.name[0]}
              </div>
              <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#1F191B', lineHeight: 1.2 }}>
                {cat.name}
              </span>
              <span style={{ fontSize: '0.7rem', color: '#9E8F94', marginTop: '4px' }}>
                {cat.product_count !== undefined ? `${cat.product_count} items` : 'Explore'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 4. TREND TRANSLATION MOOD BOARDS (Reference-inspired layout in TARIKA Pink) */}
      <div>
        <div style={{ marginBottom: '1.5rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.12em', color: '#8E3642', textTransform: 'uppercase' }}>
            Curated Aesthetics
          </span>
          <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.85rem', fontWeight: 700, margin: '2px 0 0 0', color: '#1F191B' }}>
            Trend Translation
          </h2>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {trendTranslations.map((trend, idx) => (
            <div
              key={idx}
              className="mood-card"
              onClick={() => navigate(`/customer/shop?category=${encodeURIComponent(trend.category)}`)}
            >
              <img src={trend.image} alt={trend.title} loading="lazy" />
              <div className="mood-card-overlay">
                <span style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#F0CFCD' }}>
                  {trend.category}
                </span>
                <h3 style={{ margin: 0, fontFamily: "'Playfair Display', serif", fontSize: '1.4rem', fontWeight: 700 }}>
                  {trend.title}
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: 'rgba(255, 255, 255, 0.85)' }}>
                  {trend.tagline}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 5. NEW IN DROPS (Horizontal Product Slider) */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#8E3642' }}>
              <Sparkles size={14} />
              <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                Just Arrived
              </span>
            </div>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.85rem', fontWeight: 700, margin: '2px 0 0 0', color: '#1F191B' }}>
              New In
            </h2>
          </div>
          <Link
            to="/customer/new-in"
            style={{
              fontSize: '0.84rem',
              fontWeight: 700,
              color: '#B8505E',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>View All New Drops</span>
            <ChevronRight size={16} />
          </Link>
        </div>

        <div className="horizontal-scroll-row">
          {newArrivals.map((prod) => (
            <div key={prod.product_id || prod.id} className="scroll-snap-card" style={{ width: '230px' }}>
              <ProductCard product={prod} />
            </div>
          ))}
        </div>
      </div>

      {/* 6. TRENDING PICKS (Grid) */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#8E3642' }}>
              <Flame size={14} />
              <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                Most Wanted
              </span>
            </div>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.85rem', fontWeight: 700, margin: '2px 0 0 0', color: '#1F191B' }}>
              Trending Now
            </h2>
          </div>
          <Link
            to="/customer/trending"
            style={{
              fontSize: '0.84rem',
              fontWeight: 700,
              color: '#B8505E',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>Explore Trending</span>
            <ChevronRight size={16} />
          </Link>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {trending.map((prod) => (
            <ProductCard key={prod.product_id || prod.id} product={prod} />
          ))}
        </div>
      </div>

      {/* 7. FLASH SALE PICKS */}
      <div>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#8E3642' }}>
              <Tag size={14} />
              <span style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                Limited Quantities
              </span>
            </div>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.85rem', fontWeight: 700, margin: '2px 0 0 0', color: '#1F191B' }}>
              Flash Deals & Reductions
            </h2>
          </div>
          <Link
            to="/customer/sale"
            style={{
              fontSize: '0.84rem',
              fontWeight: 700,
              color: '#B8505E',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>View All Sale</span>
            <ChevronRight size={16} />
          </Link>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {saleItems.map((prod) => (
            <ProductCard key={prod.product_id || prod.id} product={prod} />
          ))}
        </div>
      </div>
    </div>
  );
}
