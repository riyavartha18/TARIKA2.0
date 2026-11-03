import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Heart,
  Eye,
  ShoppingBag,
  ArrowRight,
} from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';
import { getNewArrivals, getCategories } from '../../services/api';

const CATEGORY_TABS = [
  { id: 'all', label: 'All' },
  { id: 'dresses', label: 'Dresses' },
  { id: 'tops', label: 'Tops' },
  { id: 'co-ords', label: 'Co-ords' },
  { id: 'ethnic', label: 'Ethnic' },
  { id: 'jumpsuits', label: 'Jumpsuits' },
];

export default function TrendingFashionCarousel() {
  const { isWishlisted, toggleWishlist, openProductModal, addItemToBag, addToast } = useCustomer();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('all');
  const [allProducts, setAllProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getNewArrivals(50)
      .then((res) => {
        if (alive && res.success) {
          setAllProducts(res.products || []);
        }
      })
      .catch((err) => {
        console.error('Error loading trending products:', err);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
  }, []);

  // Filter products by selected category tab
  const filteredProducts = React.useMemo(() => {
    if (!allProducts.length) return [];
    if (activeTab === 'all') return allProducts;

    return allProducts.filter((p) => {
      const name = (p.product_name || p.name || '').toLowerCase();
      const cat = (p.category_name || p.category || p.sub_category || '').toLowerCase();
      const style = (p.style_mode || p.garment_type || '').toLowerCase();

      if (activeTab === 'dresses') {
        return (
          (cat.includes('dress') || name.includes('dress') || style.includes('dress')) &&
          !name.includes('anarkali') &&
          !name.includes('kurti')
        );
      }
      if (activeTab === 'tops') {
        return (
          cat.includes('top') ||
          cat.includes('shirt') ||
          cat.includes('blouse') ||
          name.includes('top') ||
          name.includes('shirt') ||
          name.includes('blouse')
        );
      }
      if (activeTab === 'co-ords') {
        return (
          cat.includes('coord') ||
          cat.includes('co-ord') ||
          cat.includes('set') ||
          name.includes('co-ord') ||
          name.includes('coord') ||
          name.includes('set')
        );
      }
      if (activeTab === 'ethnic') {
        return (
          cat.includes('ethnic') ||
          cat.includes('saree') ||
          cat.includes('kurti') ||
          cat.includes('anarkali') ||
          cat.includes('lehenga') ||
          name.includes('saree') ||
          name.includes('kurti') ||
          name.includes('anarkali')
        );
      }
      if (activeTab === 'jumpsuits') {
        return cat.includes('jumpsuit') || name.includes('jumpsuit') || name.includes('romper');
      }
      return true;
    });
  }, [allProducts, activeTab]);

  const handleScroll = (direction) => {
    if (!scrollContainerRef.current) return;
    const scrollAmount = 300;
    scrollContainerRef.current.scrollBy({
      left: direction === 'next' ? scrollAmount : -scrollAmount,
      behavior: 'smooth',
    });
  };

  return (
    <section aria-label="Trending in TARIKA" style={{ marginBottom: '3rem' }}>
      {/* 1. Header Row: Title on Left, Category Filter Tabs on Right */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.25rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={16} color="#B8505E" />
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.35rem',
              fontWeight: 700,
              color: '#8E3642',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              margin: 0,
            }}
          >
            TRENDING IN TARIKA
          </h2>
        </div>

        {/* Category Pills */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            overflowX: 'auto',
            paddingBottom: '2px',
            scrollbarWidth: 'none',
          }}
        >
          {CATEGORY_TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '0.4rem 1rem',
                  borderRadius: '9999px',
                  fontSize: '0.82rem',
                  fontWeight: isActive ? 700 : 500,
                  backgroundColor: isActive ? '#B8505E' : '#FFFFFF',
                  color: isActive ? '#FFFFFF' : '#6B5E63',
                  border: isActive ? '1px solid #B8505E' : '1px solid rgba(216, 114, 126, 0.25)',
                  cursor: 'pointer',
                  transition: 'all 0.25s ease',
                  whiteSpace: 'nowrap',
                  boxShadow: isActive ? '0 2px 8px rgba(184, 80, 94, 0.25)' : 'none',
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Horizontal Cards Rail with Left & Right Arrows */}
      <div style={{ position: 'relative' }}>
        {/* Left Arrow Button */}
        <button
          type="button"
          onClick={() => handleScroll('prev')}
          aria-label="Previous products"
          style={{
            position: 'absolute',
            left: '-16px',
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 10,
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            backgroundColor: '#FFFFFF',
            border: '1px solid rgba(184, 80, 94, 0.3)',
            color: '#8E3642',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
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
          <ChevronLeft size={18} />
        </button>

        {/* Scrollable Container */}
        <div
          ref={scrollContainerRef}
          style={{
            display: 'flex',
            gap: '1rem',
            overflowX: 'auto',
            scrollSnapType: 'x mandatory',
            scrollbarWidth: 'none',
            msOverflowStyle: 'none',
            padding: '4px 2px 8px 2px',
          }}
        >
          {loading ? (
            Array.from({ length: 7 }).map((_, i) => (
              <div
                key={i}
                style={{
                  flex: '0 0 170px',
                  height: '240px',
                  backgroundColor: '#F5ECEB',
                  borderRadius: '16px',
                  animation: 'pulse 1.5s infinite',
                }}
              />
            ))
          ) : filteredProducts.length ? (
            filteredProducts.map((p) => {
              const pId = p.product_id || p.id;
              const wishlisted = isWishlisted(pId);
              const price = p.discounted_price || p.price || 1499;
              const originalPrice = p.original_price || p.mrp || (price * 1.3).toFixed(0);
              const imgUrl = p.primary_image || p.image || '/images/tarika_hero_pink_gown.jpg';

              return (
                <div
                  key={pId}
                  style={{
                    flex: '0 0 165px',
                    width: '165px',
                    scrollSnapAlign: 'start',
                    position: 'relative',
                    borderRadius: '16px',
                    backgroundColor: '#FFFFFF',
                    border: '1px solid rgba(216, 114, 126, 0.2)',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'all 0.25s ease',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)',
                  }}
                  className="trending-product-card"
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-4px)';
                    e.currentTarget.style.boxShadow = '0 8px 20px rgba(184, 80, 94, 0.12)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'none';
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.03)';
                  }}
                >
                  {/* Image Container with Floating Heart Icon */}
                  <div
                    style={{
                      width: '100%',
                      height: '200px',
                      position: 'relative',
                      backgroundColor: '#FAF5F5',
                      cursor: 'pointer',
                      overflow: 'hidden',
                    }}
                    onClick={() => openProductModal?.(p)}
                  >
                    <img
                      src={imgUrl}
                      alt={p.product_name || p.name || 'Fashion Product'}
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        objectPosition: 'top center',
                        transition: 'transform 0.4s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'scale(1)';
                      }}
                    />

                    {/* Floating Heart Wishlist Icon */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleWishlist(p);
                      }}
                      aria-label="Wishlist product"
                      style={{
                        position: 'absolute',
                        top: '8px',
                        right: '8px',
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        backgroundColor: 'rgba(255, 255, 255, 0.85)',
                        backdropFilter: 'blur(4px)',
                        border: '1px solid rgba(216, 114, 126, 0.25)',
                        color: '#B8505E',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <Heart
                        size={14}
                        color="#B8505E"
                        fill={wishlisted ? '#B8505E' : 'none'}
                      />
                    </button>
                  </div>

                  {/* Product Details */}
                  <div
                    style={{
                      padding: '0.65rem 0.75rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '2px',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        color: '#1F191B',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={p.product_name || p.name}
                    >
                      {p.product_name || p.name}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '5px' }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#B8505E' }}>
                        ₹{Number(price).toLocaleString('en-IN')}
                      </span>
                      {originalPrice > price && (
                        <span
                          style={{
                            fontSize: '0.7rem',
                            color: '#9E8F94',
                            textDecoration: 'line-through',
                          }}
                        >
                          ₹{Number(originalPrice).toLocaleString('en-IN')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div style={{ padding: '2rem', color: '#8E3642', width: '100%', textAlign: 'center' }}>
              No products found in this category.
            </div>
          )}
        </div>

        {/* Right Arrow Button */}
        <button
          type="button"
          onClick={() => handleScroll('next')}
          aria-label="Next products"
          style={{
            position: 'absolute',
            right: '-16px',
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 10,
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            backgroundColor: '#FFFFFF',
            border: '1px solid rgba(184, 80, 94, 0.3)',
            color: '#8E3642',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
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
          <ChevronRight size={18} />
        </button>
      </div>
    </section>
  );
}
