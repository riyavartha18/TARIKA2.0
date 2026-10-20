import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ChevronRight,
  Sparkles,
  Tag,
  Check,
  ArrowRight,
  ArrowDown,
  Flower2,
  Shirt,
  RotateCcw
} from 'lucide-react';
import ProductCard from '../../components/customer/ProductCard';
import { getProductPricing } from '../../utils/pricing';
import { getCategories, getProducts } from '../../services/api';

// Creative Presentation metadata matching the attached reference image
const CREATIVE_CATEGORIES = [
  {
    id: 'dresses',
    dbCategory: 'Dresses',
    creativeTitle: 'THE DRESS STORY',
    tag: 'DRESSES',
    subtitle: 'Dresses for every you.',
    bannerQuote: 'Same dress. A different you.',
    image: 'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=800&auto=format&fit=crop&q=85',
    layout: 'media-left',
    isArch: true,
    subcategories: ['All Dresses', 'Mini Dresses', 'Midi Dresses', 'Maxi Dresses', 'Party Dresses', 'Formal Dresses', 'Casual Dresses']
  },
  {
    id: 'tops',
    dbCategory: 'Tops',
    creativeTitle: 'TOP STORIES',
    tag: 'TOPS',
    subtitle: 'Tops that speak you.',
    bannerQuote: 'Unapologetic silhouettes. Effortless you.',
    image: 'https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=800&auto=format&fit=crop&q=85',
    layout: 'media-left',
    isArch: false,
    subcategories: ['All Tops', 'Crop Tops', 'Corset Blouses', 'Satin Camisoles', 'Ribbed Knits', 'Party Tops']
  },
  {
    id: 'bottom-wear',
    dbCategory: 'Bottom Wear',
    creativeTitle: 'BOTTOM LINE',
    tag: 'BOTTOM WEAR',
    subtitle: 'Foundations for your looks.',
    bannerQuote: 'Tailored drape. Architectural lines.',
    image: 'https://images.unsplash.com/photo-1509551388413-e18d0ac5d495?w=800&auto=format&fit=crop&q=85',
    layout: 'media-right',
    isArch: false,
    subcategories: ['All Bottoms', 'Wide-Leg Trousers', 'Pleated Slacks', 'Palazzos', 'High-Rise Pants', 'Formal Trousers']
  },
  {
    id: 'jeans',
    dbCategory: 'Jeans',
    creativeTitle: 'DENIM DIARIES',
    tag: 'JEANS',
    subtitle: 'Denim for every mood.',
    bannerQuote: 'Good denim, better days.',
    scriptOverlay: 'Good Denim Better Days',
    image: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=800&auto=format&fit=crop&q=85',
    layout: 'media-right',
    isArch: false,
    subcategories: ['All Jeans', 'Wide-Leg Jeans', 'Straight Fit', 'Bootcut Jeans', 'Skinny Jeans', 'Relaxed Fit']
  },
  {
    id: 'jackets',
    dbCategory: 'Jackets',
    creativeTitle: 'THE LAYER ROOM',
    tag: 'JACKETS',
    subtitle: 'Jackets to complete the look.',
    bannerQuote: 'Layer your story. Define your presence.',
    scriptOverlay: 'Layers Your Story',
    image: 'https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&auto=format&fit=crop&q=85',
    layout: 'media-right',
    isArch: false,
    subcategories: ['All Jackets', 'Tailored Blazers', 'Leather Jackets', 'Bombers', 'Denim Jackets', 'Trench Coats']
  },
  {
    id: 'shirts',
    dbCategory: 'Shirts',
    creativeTitle: 'SHIRT THEORY',
    tag: 'SHIRTS',
    subtitle: 'Shirts for new perspectives.',
    bannerQuote: 'Crisp poplins. Everyday poetry.',
    image: 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=800&auto=format&fit=crop&q=85',
    layout: 'media-right',
    isArch: false,
    subcategories: ['All Shirts', 'Oversized Poplin', 'Linen Shirts', 'Silk Button-Downs', 'Formal Shirts', 'Casual Shirts']
  },
  {
    id: 'ethnic-edit',
    isMulti: true,
    creativeTitle: 'ETHNIC EDIT',
    subtitle: 'Tradition reimagined for today.',
    bannerQuote: 'Heritage looms. Contemporary grace.',
    layout: 'multi',
    items: [
      { name: 'Kurtis', dbCategory: 'Kurtis', image: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&auto=format&fit=crop&q=85' },
      { name: 'Sarees', dbCategory: 'Sarees', image: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&auto=format&fit=crop&q=85' },
      { name: 'Ethnic Wear', dbCategory: 'Ethnic Wear', image: 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?w=600&auto=format&fit=crop&q=85' }
    ]
  },
  {
    id: 'style-accessories',
    isMulti: true,
    creativeTitle: 'STYLE & ACCESSORIES',
    subtitle: 'The details that do more.',
    bannerQuote: 'The finishing touch that speaks volumes.',
    layout: 'multi',
    items: [
      { name: 'Handbags', dbCategory: 'Handbags', image: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop&q=85' },
      { name: 'Footwear', dbCategory: 'Footwear', image: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600&auto=format&fit=crop&q=85' },
      { name: 'Accessories', dbCategory: 'Accessories', image: 'https://images.unsplash.com/photo-1611652022419-a9419f74343d?w=600&auto=format&fit=crop&q=85' }
    ]
  }
];

export default function ShopCategories() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialCategory = searchParams.get('category') || 'Dresses';
  const initialSearch = searchParams.get('search') || '';

  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [rawProducts, setRawProducts] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [activeSubcategory, setActiveSubcategory] = useState('All');

  // Filters
  const [selectedSort, setSelectedSort] = useState('newest');
  const [onlySale, setOnlySale] = useState(false);
  const [onlyInStock, setOnlyInStock] = useState(false);
  const [maxPriceFilter, setMaxPriceFilter] = useState('');
  const [selectedSize, setSelectedSize] = useState('All');
  const [selectedColor, setSelectedColor] = useState('All');

  const productsSectionRef = useRef(null);

  // Fetch all customer-facing categories, strictly excluding Kids Wear
  useEffect(() => {
    async function fetchCatList() {
      const res = await getCategories();
      if (res.success && res.categories) {
        const filtered = res.categories.filter(
          (c) => (c.category_name || c.name || '').toLowerCase() !== 'kids wear'
        );
        setCategories(filtered);
      }
    }
    fetchCatList();
  }, []);

  // When query param changes in URL
  useEffect(() => {
    const urlCategory = searchParams.get('category');
    if (urlCategory && urlCategory !== selectedCategory) {
      setSelectedCategory(urlCategory);
      setActiveSubcategory('All');
    }
  }, [searchParams]);

  // Fetch products when category or API filters change
  useEffect(() => {
    async function fetchCategoryProducts() {
      setLoadingProducts(true);
      try {
        const params = {
          sort: selectedSort,
          page_size: 40,
        };

        if (selectedCategory && selectedCategory !== 'ALL') {
          params.category = selectedCategory;
        }
        if (initialSearch) {
          params.search = initialSearch;
        }
        if (onlyInStock) {
          params.in_stock = 'true';
        }
        if (maxPriceFilter) {
          params.max_price = maxPriceFilter;
        }

        const res = await getProducts(params);
        if (res.success) {
          setRawProducts(res.products || []);
        }
      } catch (err) {
        console.error('Error fetching category products', err);
      } finally {
        setLoadingProducts(false);
      }
    }

    fetchCategoryProducts();
  }, [selectedCategory, selectedSort, onlyInStock, maxPriceFilter, initialSearch]);

  // Client-side filtering for sale, size, color and subcategory
  const filteredProducts = React.useMemo(() => {
    let list = [...rawProducts];

    // Sale filter
    if (onlySale) {
      list = list.filter((p) => {
        return getProductPricing(p).isOnSale;
      });
    }

    // Size filter
    if (selectedSize !== 'All') {
      list = list.filter(
        (p) => (p.size || '').toLowerCase() === selectedSize.toLowerCase()
      );
    }

    // Color filter
    if (selectedColor !== 'All') {
      list = list.filter((p) =>
        (p.color || '').toLowerCase().includes(selectedColor.toLowerCase())
      );
    }

    // Subcategory keyword filter if active and not 'All'
    if (activeSubcategory && !activeSubcategory.startsWith('All')) {
      const keyword = activeSubcategory
        .replace(/(Dresses|Tops|Bottoms|Jeans|Jackets|Shirts|Kurtis|Sarees|Ethnic Wear|Handbags|Footwear|Accessories)/gi, '')
        .trim()
        .toLowerCase();
      if (keyword) {
        const subFiltered = list.filter((p) => {
          const name = (p.product_name || p.name || '').toLowerCase();
          const desc = (p.description || '').toLowerCase();
          return name.includes(keyword) || desc.includes(keyword);
        });
        if (subFiltered.length > 0) {
          list = subFiltered;
        }
      }
    }

    return list;
  }, [rawProducts, onlySale, selectedSize, selectedColor, activeSubcategory]);

  const handleCategorySelect = (categoryName, smoothScroll = true) => {
    setSelectedCategory(categoryName);
    setActiveSubcategory('All');
    setSelectedSize('All');
    setSelectedColor('All');
    setSearchParams({ category: categoryName });
    if (smoothScroll && productsSectionRef.current) {
      setTimeout(() => {
        productsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 120);
    }
  };

  // Find active creative category metadata
  const activeCreativeMeta = CREATIVE_CATEGORIES.find(
    (c) =>
      c.dbCategory?.toLowerCase() === selectedCategory?.toLowerCase() ||
      c.items?.some((it) => it.dbCategory.toLowerCase() === selectedCategory?.toLowerCase())
  );

  const activeCreativeTitle = activeCreativeMeta?.creativeTitle || selectedCategory.toUpperCase();
  const activeSubtitle = activeCreativeMeta?.subtitle || 'Curated with refined craftsmanship for the modern wardrobe.';
  const activeBannerQuote = activeCreativeMeta?.bannerQuote || 'Same dress. A different you.';

  // Determine subcategories
  let activeSubcategories = activeCreativeMeta?.subcategories;
  if (!activeSubcategories) {
    if (activeCreativeMeta?.isMulti) {
      activeSubcategories = [
        `All ${selectedCategory}`,
        `New ${selectedCategory}`,
        `Classic ${selectedCategory}`,
        `Embroidered ${selectedCategory}`,
        `Atelier ${selectedCategory}`,
      ];
    } else {
      activeSubcategories = [
        `All ${selectedCategory}`,
        `Classic ${selectedCategory}`,
        `Casual ${selectedCategory}`,
        `Formal ${selectedCategory}`,
        `Atelier ${selectedCategory}`,
      ];
    }
  }

  return (
    <div style={{ paddingBottom: '4rem' }}>
      {/* =================================================================
          1. CREATIVE CATEGORIES LANDING SECTION (Matching Reference Image)
         ================================================================= */}
      <section className="cat-editorial-landing">
        {/* Editorial Masthead */}
        <div className="cat-editorial-masthead">
          <div className="cat-masthead-left">
            <div className="cat-masthead-eyebrow">EXPLORE BY STYLE</div>
            <h1 className="cat-masthead-main-title">CATEGORIES</h1>
            <p className="cat-masthead-script">Find your style. Tell your story..</p>
            <div className="cat-masthead-meta-tags">
              - CURATED LOOKS &nbsp;/&nbsp; TIMELESS TRENDS &nbsp;/&nbsp; MADE FOR YOU
            </div>
          </div>

          {/* Right Accent with Arched Floral Photo & Vertical Motto */}
          <div className="cat-masthead-right">
            <div className="cat-masthead-quote-wrap">
              <p className="cat-masthead-quote">
                More than just fashion,
                <br />
                it's a new chapter every day.
              </p>
              <div
                style={{
                  width: '32px',
                  height: '1.5px',
                  backgroundColor: '#D8727E',
                  margin: '4px 0',
                }}
              />
            </div>

            <div className="cat-masthead-arch-art">
              <img
                src="https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=400&auto=format&fit=crop&q=80"
                alt="Botanical floral silhouette"
                loading="lazy"
              />
            </div>

            <div className="cat-masthead-motto-stack">
              <span>WEAR</span>
              <span>EXPLORE</span>
              <span>EXPRESS</span>
              <span>REPEAT</span>
            </div>
          </div>
        </div>

        {/* 4x2 Editorial Category Cards Grid */}
        <div className="cat-editorial-grid">
          {CREATIVE_CATEGORIES.map((cat, index) => {
            if (cat.isMulti) {
              // Multi-Item Card: ETHNIC EDIT or STYLE & ACCESSORIES
              const isAnySelected = cat.items.some(
                (sub) => selectedCategory.toLowerCase() === sub.dbCategory.toLowerCase()
              );

              return (
                <div
                  key={cat.id}
                  className="cat-card-interactive"
                  style={{
                    animationDelay: `${index * 80}ms`,
                    borderColor: isAnySelected ? '#D8727E' : 'rgba(216, 114, 126, 0.2)',
                    boxShadow: isAnySelected
                      ? '0 12px 30px rgba(216, 114, 126, 0.2)'
                      : '0 6px 25px rgba(184, 80, 94, 0.05)',
                    cursor: 'default',
                  }}
                >
                  <div className="cat-multi-card-layout">
                    {/* Header */}
                    <div className="cat-multi-card-header">
                      {/* Corner SVG flourishes */}
                      {cat.id === 'ethnic-edit' ? (
                        <svg
                          className="cat-multi-corner-accent"
                          viewBox="0 0 100 100"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            d="M85 10C65 20 50 45 45 75M85 10C75 35 78 58 88 75M85 10C55 18 30 35 18 65"
                            stroke="#D8727E"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            opacity="0.4"
                          />
                        </svg>
                      ) : (
                        <svg
                          className="cat-multi-corner-accent"
                          viewBox="0 0 100 100"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <circle cx="70" cy="30" r="24" stroke="#E2B755" strokeWidth="2.8" opacity="0.45" />
                          <circle cx="50" cy="52" r="14" stroke="#D8727E" strokeWidth="2" opacity="0.35" />
                        </svg>
                      )}

                      <h3 className="cat-multi-card-title">{cat.creativeTitle}</h3>
                      <p className="cat-multi-card-subtitle">{cat.subtitle}</p>
                    </div>

                    {/* 3 Sub-items in a Row */}
                    <div className="cat-multi-items-row">
                      {cat.items.map((sub) => {
                        const isSubSelected =
                          selectedCategory.toLowerCase() === sub.dbCategory.toLowerCase();
                        return (
                          <button
                            key={sub.dbCategory}
                            type="button"
                            className="cat-multi-subitem-btn"
                            onClick={() => handleCategorySelect(sub.dbCategory)}
                            style={{
                              borderColor: isSubSelected ? '#D8727E' : 'rgba(216, 114, 126, 0.22)',
                              backgroundColor: isSubSelected ? '#FBF1F0' : '#FFFFFF',
                              boxShadow: isSubSelected
                                ? '0 4px 14px rgba(216, 114, 126, 0.22)'
                                : 'none',
                            }}
                          >
                            <div className="cat-multi-subitem-thumb">
                              <img src={sub.image} alt={sub.name} loading="lazy" />
                            </div>
                            <span
                              className="cat-multi-subitem-label"
                              style={{ color: isSubSelected ? '#B8505E' : '#1F191B' }}
                            >
                              {sub.name} <ArrowRight size={11} color="#D8727E" />
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            }

            // Single Category Cards: THE DRESS STORY, TOP STORIES, BOTTOM LINE, etc.
            const isMediaLeft = cat.layout === 'media-left' || cat.id === 'dresses' || cat.id === 'tops';
            const isSelected = selectedCategory.toLowerCase() === cat.dbCategory.toLowerCase();

            return (
              <div
                key={cat.id}
                className="cat-card-interactive"
                onClick={() => handleCategorySelect(cat.dbCategory)}
                style={{
                  animationDelay: `${index * 80}ms`,
                  borderColor: isSelected ? '#D8727E' : 'rgba(216, 114, 126, 0.2)',
                  boxShadow: isSelected
                    ? '0 12px 30px rgba(216, 114, 126, 0.22)'
                    : '0 6px 25px rgba(184, 80, 94, 0.05)',
                }}
              >
                <div className={`cat-split-layout ${isMediaLeft ? 'is-media-left' : 'is-media-right'}`}>
                  {/* Media Wrapper */}
                  <div className={`cat-split-media ${cat.isArch ? 'is-arch' : ''}`}>
                    <img src={cat.image} alt={cat.creativeTitle} loading="lazy" />
                    {cat.scriptOverlay && (
                      <span className="cat-split-media-script">{cat.scriptOverlay}</span>
                    )}
                  </div>

                  {/* Info Wrapper */}
                  <div className="cat-split-info">
                    <div className="cat-split-info-top">
                      <h3 className="cat-split-title">{cat.creativeTitle}</h3>
                      <p className="cat-split-subtitle">{cat.subtitle}</p>
                      <div className="cat-split-action">
                        <div className="cat-circle-arrow-btn">
                          <ArrowRight size={14} />
                        </div>
                      </div>
                    </div>
                    <span className="cat-split-bottom-tag">{cat.tag}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Affirmation Quality Strip */}
        <div className="cat-features-affirmation-strip">
          <div className="cat-affirmation-item">
            <Flower2 size={18} color="#D8727E" />
            <span>Every category. A new you.</span>
          </div>

          <div className="cat-affirmation-divider" />

          <div className="cat-affirmation-item">
            <Shirt size={18} color="#D8727E" />
            <span>Curated for your next favorite look.</span>
          </div>

          <div className="cat-affirmation-divider" />

          <div className="cat-affirmation-item">
            <Sparkles size={18} color="#D8727E" />
            <span>Fashion that feels like you.</span>
          </div>

          <div className="cat-affirmation-brand">
            TARIKA — <em>More than fashion</em>
          </div>
        </div>

        {/* Transition Indicator Badge */}
        <div className="cat-transition-indicator">
          <span>Smooth transition animation</span>
          <ArrowDown size={14} />
        </div>
      </section>

      {/* =================================================================
          2. CATEGORY PRODUCT SECTION (Loaded with Actual Database Products)
         ================================================================= */}
      <div ref={productsSectionRef} id="category-products-view" style={{ scrollMarginTop: '110px' }}>
        {/* Breadcrumb Navigation */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.78rem',
            color: '#9E8F94',
            marginBottom: '1rem',
          }}
        >
          <span>Customer Portal</span>
          <ChevronRight size={12} />
          <button
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: '#9E8F94',
              cursor: 'pointer',
              fontSize: 'inherit',
            }}
          >
            Shop
          </button>
          <ChevronRight size={12} />
          <span style={{ color: '#B8505E', fontWeight: 600 }}>{selectedCategory}</span>
        </div>

        {/* Dual Pane Layout (Sidebar + Hero Banner + Products) */}
        <div
          style={{
            display: 'flex',
            gap: '2.5rem',
            alignItems: 'flex-start',
          }}
          className="department-dual-pane"
        >
          {/* LEFT SIDEBAR: Sub-categories and Department Switcher */}
          <aside className="department-tabs-sidebar">
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 800,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                color: '#8E3642',
                padding: '0 8px 8px 8px',
              }}
            >
              {selectedCategory}
            </span>

            {/* Subcategories */}
            {activeSubcategories.map((sub, index) => {
              const isActive =
                activeSubcategory === sub || (index === 0 && activeSubcategory === 'All');
              return (
                <button
                  key={sub}
                  type="button"
                  className={`department-tab-btn ${isActive ? 'is-active' : ''}`}
                  onClick={() => setActiveSubcategory(sub)}
                >
                  <span>{sub}</span>
                  {index === 0 && (
                    <span
                      style={{
                        fontSize: '0.72rem',
                        color: isActive ? '#B8505E' : '#9E8F94',
                      }}
                    >
                      ({filteredProducts.length})
                    </span>
                  )}
                </button>
              );
            })}

            <div
              style={{
                margin: '1.5rem 0 0.5rem 0',
                borderTop: '1px solid rgba(216, 114, 126, 0.15)',
                paddingTop: '1rem',
              }}
            >
              <span
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  color: '#9E8F94',
                  padding: '0 8px 8px 8px',
                }}
              >
                Other Departments
              </span>
            </div>

            {/* Other customer-facing categories from DB (Kids Wear already excluded) */}
            {categories
              .filter(
                (cat) =>
                  (cat.category_name || '').toLowerCase() !== selectedCategory?.toLowerCase()
              )
              .map((cat) => (
                <button
                  key={cat.category_id || cat.id}
                  type="button"
                  className="department-tab-btn"
                  onClick={() => handleCategorySelect(cat.category_name)}
                >
                  <span>{cat.category_name}</span>
                  <span style={{ fontSize: '0.72rem', color: '#9E8F94' }}>
                    {cat.product_count !== undefined ? `(${cat.product_count})` : ''}
                  </span>
                </button>
              ))}
          </aside>

          {/* RIGHT COLUMN: Hero Banner & Products Grid */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Category Hero Banner matching reference image */}
            <div className="cat-selected-hero-banner">
              <div>
                <span
                  style={{
                    fontSize: '0.74rem',
                    fontWeight: 800,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    color: '#8E3642',
                  }}
                >
                  FEATURED DEPARTMENT
                </span>
                <h2
                  style={{
                    fontFamily: "'Playfair Display', serif",
                    fontSize: '2.2rem',
                    fontWeight: 700,
                    margin: '4px 0',
                    color: '#1F191B',
                  }}
                >
                  {activeCreativeTitle}
                </h2>
                <p style={{ margin: 0, color: '#6B5E63', fontSize: '0.92rem' }}>
                  {activeSubtitle}
                </p>
              </div>

              {/* Right Side Quote & Vignette */}
              <div className="cat-hero-right-accent">
                <p className="cat-hero-script-tagline">{activeBannerQuote}</p>
                <div className="cat-hero-vignette-circle">
                  <img
                    src={
                      activeCreativeMeta?.image ||
                      'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=300&auto=format&fit=crop&q=80'
                    }
                    alt={activeCreativeTitle}
                    loading="lazy"
                  />
                </div>
              </div>
            </div>

            {/* Quick Filter Bar */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem',
                padding: '12px 16px',
                backgroundColor: '#FFFFFF',
                borderRadius: '18px',
                border: '1px solid rgba(240, 226, 224, 0.9)',
                marginBottom: '1.75rem',
                boxShadow: '0 4px 15px rgba(184, 80, 94, 0.04)',
              }}
            >
              {/* Filter Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setOnlySale(!onlySale)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 14px',
                    borderRadius: '9999px',
                    border: `1px solid ${onlySale ? '#D8727E' : '#F0E2E0'}`,
                    backgroundColor: onlySale ? '#FBF1F0' : '#FAF7F5',
                    color: onlySale ? '#B8505E' : '#1F191B',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <Tag size={13} />
                  <span>On Sale</span>
                  {onlySale && <Check size={12} />}
                </button>

                <button
                  type="button"
                  onClick={() => setOnlyInStock(!onlyInStock)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 14px',
                    borderRadius: '9999px',
                    border: `1px solid ${onlyInStock ? '#D8727E' : '#F0E2E0'}`,
                    backgroundColor: onlyInStock ? '#FBF1F0' : '#FAF7F5',
                    color: onlyInStock ? '#B8505E' : '#1F191B',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <span>In Stock Only</span>
                  {onlyInStock && <Check size={12} />}
                </button>

                <button
                  type="button"
                  onClick={() => setMaxPriceFilter(maxPriceFilter === '1000' ? '' : '1000')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '9999px',
                    border: `1px solid ${maxPriceFilter === '1000' ? '#D8727E' : '#F0E2E0'}`,
                    backgroundColor: maxPriceFilter === '1000' ? '#FBF1F0' : '#FAF7F5',
                    color: maxPriceFilter === '1000' ? '#B8505E' : '#1F191B',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  Under ₹1,000
                </button>

                <button
                  type="button"
                  onClick={() => setMaxPriceFilter(maxPriceFilter === '2000' ? '' : '2000')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '9999px',
                    border: `1px solid ${maxPriceFilter === '2000' ? '#D8727E' : '#F0E2E0'}`,
                    backgroundColor: maxPriceFilter === '2000' ? '#FBF1F0' : '#FAF7F5',
                    color: maxPriceFilter === '2000' ? '#B8505E' : '#1F191B',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  Under ₹2,000
                </button>

                {/* Size Selector */}
                <select
                  value={selectedSize}
                  onChange={(e) => setSelectedSize(e.target.value)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '9999px',
                    border: `1px solid ${selectedSize !== 'All' ? '#D8727E' : '#F0E2E0'}`,
                    backgroundColor: selectedSize !== 'All' ? '#FBF1F0' : '#FAF7F5',
                    color: selectedSize !== 'All' ? '#B8505E' : '#1F191B',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    outline: 'none',
                  }}
                >
                  <option value="All">Size: All</option>
                  <option value="XS">Size: XS</option>
                  <option value="S">Size: S</option>
                  <option value="M">Size: M</option>
                  <option value="L">Size: L</option>
                  <option value="XL">Size: XL</option>
                </select>

                {/* Color Selector */}
                <select
                  value={selectedColor}
                  onChange={(e) => setSelectedColor(e.target.value)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '9999px',
                    border: `1px solid ${selectedColor !== 'All' ? '#D8727E' : '#F0E2E0'}`,
                    backgroundColor: selectedColor !== 'All' ? '#FBF1F0' : '#FAF7F5',
                    color: selectedColor !== 'All' ? '#B8505E' : '#1F191B',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    outline: 'none',
                  }}
                >
                  <option value="All">Color: All</option>
                  <option value="Black">Color: Black</option>
                  <option value="White">Color: White</option>
                  <option value="Pink">Color: Pink</option>
                  <option value="Blue">Color: Blue</option>
                  <option value="Beige">Color: Beige</option>
                  <option value="Green">Color: Green</option>
                  <option value="Red">Color: Red</option>
                </select>
              </div>

              {/* Sorting Dropdown & Count */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '0.8rem', color: '#6B5E63', fontWeight: 600 }}>Sort by:</span>
                <select
                  value={selectedSort}
                  onChange={(e) => setSelectedSort(e.target.value)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '10px',
                    border: '1px solid #F0E2E0',
                    backgroundColor: '#FAF7F5',
                    fontSize: '0.82rem',
                    color: '#1F191B',
                    fontWeight: 600,
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  <option value="newest">Newest First</option>
                  <option value="price_low_high">Price: Low to High</option>
                  <option value="price_high_low">Price: High to Low</option>
                  <option value="name">Name: A to Z</option>
                </select>
              </div>
            </div>

            {/* Products Count Header */}
            <div
              style={{
                marginBottom: '1.25rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span style={{ fontSize: '0.86rem', color: '#6B5E63', fontWeight: 600 }}>
                {filteredProducts.length} Products
              </span>
              {(activeSubcategory !== 'All' || selectedSize !== 'All' || selectedColor !== 'All' || onlySale || onlyInStock || maxPriceFilter) && (
                <button
                  type="button"
                  onClick={() => {
                    setActiveSubcategory('All');
                    setSelectedSize('All');
                    setSelectedColor('All');
                    setOnlySale(false);
                    setOnlyInStock(false);
                    setMaxPriceFilter('');
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    background: 'none',
                    border: 'none',
                    fontSize: '0.78rem',
                    color: '#D8727E',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  <RotateCcw size={12} />
                  Reset all filters
                </button>
              )}
            </div>

            {/* Products Grid */}
            {loadingProducts ? (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                  gap: '1.5rem',
                }}
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <div
                    key={n}
                    style={{
                      aspectRatio: '3 / 4',
                      borderRadius: '18px',
                      backgroundColor: '#F5ECEB',
                      animation: 'pulseGlow 2s infinite ease-in-out',
                    }}
                  />
                ))}
              </div>
            ) : filteredProducts.length > 0 ? (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                  gap: '1.5rem',
                }}
              >
                {filteredProducts.map((prod) => (
                  <ProductCard key={prod.product_id || prod.id} product={prod} />
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: '4rem 2rem',
                  textAlign: 'center',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '20px',
                  border: '1px solid #F0E2E0',
                }}
              >
                <Sparkles size={36} color="#D8727E" style={{ marginBottom: '1rem' }} />
                <h3
                  style={{
                    fontFamily: "'Playfair Display', serif",
                    fontSize: '1.4rem',
                    color: '#1F191B',
                    margin: '0 0 0.5rem 0',
                  }}
                >
                  No Products Found In This Selection
                </h3>
                <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: '0 0 1.5rem 0' }}>
                  Try resetting your price, size, or stock filters to view available styles in{' '}
                  {selectedCategory}.
                </p>
                <button
                  type="button"
                  className="tarika-btn-outline"
                  onClick={() => {
                    setOnlySale(false);
                    setOnlyInStock(false);
                    setMaxPriceFilter('');
                    setSelectedSize('All');
                    setSelectedColor('All');
                    setActiveSubcategory('All');
                  }}
                >
                  Reset Filters
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
