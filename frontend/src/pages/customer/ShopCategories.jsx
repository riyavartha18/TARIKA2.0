import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ChevronRight,
  Sparkles,
  Tag,
  Check,
  RotateCcw,
} from 'lucide-react';
import ProductCard from '../../components/customer/ProductCard';
import CategoryEditorialSection from '../../components/customer/CategoryEditorialSection';
import { getCategories, getProducts } from '../../services/api';
import {
  EDITORIAL_CATEGORIES,
  CATEGORY_BY_NAME_MAP,
} from '../../data/editorialCategories';

const DEFAULT_SUBTITLE = 'Curated with refined craftsmanship for the modern wardrobe.';
const FALLBACK_CATEGORY_IMAGE =
  'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80';

const normalizeName = (value) => String(value || '').trim().toLowerCase();

export default function ShopCategories() {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlCategory = searchParams.get('category');
  const currentSearch = (searchParams.get('search') || '').trim();
  const isSearchActive = Boolean(currentSearch);

  const initialCategory = urlCategory || (isSearchActive ? 'ALL' : 'The Dress Story');

  const [dbCategories, setDbCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [rawProducts, setRawProducts] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [productsError, setProductsError] = useState(null);
  const [activeSubcategory, setActiveSubcategory] = useState('All');

  // Filters
  const [selectedSort, setSelectedSort] = useState('newest');
  const [onlySale, setOnlySale] = useState(false);
  const [onlyInStock, setOnlyInStock] = useState(false);
  const [maxPriceFilter, setMaxPriceFilter] = useState('');
  const [selectedSize, setSelectedSize] = useState('All');
  const [selectedColor, setSelectedColor] = useState('All');

  const productsSectionRef = useRef(null);

  // Incremental loading state (server-side pagination)
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // Guards against stale responses when filters change rapidly.
  const reqSeq = useRef(0);

  // Fetch all customer-facing database categories for fallback & other departments list
  useEffect(() => {
    async function fetchCatList() {
      const res = await getCategories();
      if (res.success && res.categories) {
        const filtered = res.categories.filter(
          (c) => (c.category_name || c.name || '').toLowerCase() !== 'kids wear'
        );
        setDbCategories(filtered);
      }
    }
    fetchCatList();
  }, []);

  // Listen to URL query params (both category and search)
  useEffect(() => {
    const urlCat = searchParams.get('category');
    const urlSrch = (searchParams.get('search') || '').trim();

    if (urlCat) {
      setSelectedCategory(urlCat);
      setActiveSubcategory('All');
    } else if (urlSrch) {
      setSelectedCategory('ALL');
      setActiveSubcategory('All');
    } else {
      setSelectedCategory((prev) => (prev === 'ALL' ? 'The Dress Story' : prev));
      setActiveSubcategory('All');
    }
  }, [searchParams]);

  // Find metadata for the active category (either editorial or database)
  const activeEditorial = useMemo(() => {
    const norm = normalizeName(selectedCategory);
    return CATEGORY_BY_NAME_MAP[norm] || null;
  }, [selectedCategory]);

  const activeDbCategory = useMemo(() => {
    const norm = normalizeName(selectedCategory);
    return (
      dbCategories.find(
        (c) => normalizeName(c.category_name) === norm || normalizeName(c.name) === norm
      ) || null
    );
  }, [dbCategories, selectedCategory]);

  // Titles, subtitles, quotes and images for the hero banner
  const activeCreativeTitle = isSearchActive
    ? `SEARCH: "${currentSearch.toUpperCase()}"`
    : activeEditorial
    ? activeEditorial.creativeTitle
    : selectedCategory.toUpperCase();

  const activeSubtitle = isSearchActive
    ? `Curated styles matching "${currentSearch}" across the TARIKA collection.`
    : activeEditorial
    ? activeEditorial.subtitle
    : DEFAULT_SUBTITLE;

  const activeBannerQuote = isSearchActive
    ? `Showing items matching your search.`
    : activeEditorial
    ? activeEditorial.bannerQuote
    : 'Curated from our latest drops.';

  const activeHeroImage =
    activeEditorial?.image || activeDbCategory?.image || FALLBACK_CATEGORY_IMAGE;

  // Active subcategories list
  const activeSubcategories = useMemo(() => {
    if (activeEditorial?.subcategories?.length) {
      return activeEditorial.subcategories;
    }
    if (activeDbCategory?.sub_categories?.length) {
      return ['All', ...activeDbCategory.sub_categories.map((s) => s.sub_category)];
    }
    return ['All'];
  }, [activeEditorial, activeDbCategory]);

  // Build the server query from the currently active filters
  const buildProductParams = useCallback(
    (pageNum) => {
      const params = {
        sort: selectedSort,
        page_size: 20,
        page: pageNum,
      };

      if (selectedCategory && selectedCategory !== 'ALL') {
        params.category = selectedCategory;
      }
      if (currentSearch) {
        params.search = currentSearch;
      }
      if (onlyInStock) {
        params.in_stock = 'true';
      }
      if (maxPriceFilter) {
        params.max_price = maxPriceFilter;
      }
      if (onlySale) params.on_sale = 'true';
      if (selectedSize !== 'All') params.size = selectedSize;
      if (selectedColor !== 'All') params.color = selectedColor;

      // Subcategory filter: pass cleaned subcategory keyword
      if (activeSubcategory && !activeSubcategory.startsWith('All')) {
        const cleanedSub = activeSubcategory
          .replace(/^(All|all)\s*/, '')
          .replace(/(Dresses|Tops|Bottoms|Jeans|Jackets|Shirts|Tailored|Denim|Footwear|Jewellery|Accents|Bags)/gi, '')
          .trim();
        params.sub_category = cleanedSub || activeSubcategory;
      }

      return params;
    },
    [
      selectedCategory,
      currentSearch,
      onlyInStock,
      maxPriceFilter,
      onlySale,
      selectedSize,
      selectedColor,
      activeSubcategory,
      selectedSort,
    ]
  );

  // Fetch the first page whenever the active filters change
  useEffect(() => {
    if (!selectedCategory) return;
    const seq = ++reqSeq.current;

    async function fetchCategoryProducts() {
      setLoadingProducts(true);
      setLoadingMore(false);
      setProductsError(null);
      try {
        const res = await getProducts(buildProductParams(1));
        if (seq !== reqSeq.current) return; // a newer request already started
        if (res.success) {
          setRawProducts(res.products || []);
          setPage(1);
          setHasMore(Boolean(res.hasNext));
        } else {
          setRawProducts([]);
          setHasMore(false);
          setProductsError(res.error || 'Failed to load products.');
        }
      } catch (err) {
        if (seq === reqSeq.current) {
          console.error('Error fetching category products', err);
          setProductsError('Unable to load products. Please try again.');
        }
      } finally {
        if (seq === reqSeq.current) setLoadingProducts(false);
      }
    }

    fetchCategoryProducts();
  }, [buildProductParams, selectedCategory]);

  // Append the next page without duplicating already-loaded products
  const handleLoadMore = async () => {
    if (loadingMore || !hasMore) return;
    const seq = reqSeq.current;
    const nextPage = page + 1;
    setLoadingMore(true);
    setProductsError(null);
    try {
      const res = await getProducts(buildProductParams(nextPage));
      if (seq !== reqSeq.current) return;
      if (res.success) {
        const incoming = res.products || [];
        setRawProducts((prev) => {
          const seen = new Set(prev.map((p) => p.product_id || p.id));
          const merged = [...prev];
          incoming.forEach((p) => {
            const id = p.product_id || p.id;
            if (!seen.has(id)) {
              seen.add(id);
              merged.push(p);
            }
          });
          return merged;
        });
        setPage(nextPage);
        setHasMore(Boolean(res.hasNext));
      } else {
        setProductsError(res.error || 'Failed to load more products.');
      }
    } catch (err) {
      if (seq === reqSeq.current) {
        console.error('Error loading more products', err);
        setProductsError('Unable to load more products. Please try again.');
      }
    } finally {
      if (seq === reqSeq.current) setLoadingMore(false);
    }
  };

  const filteredProducts = rawProducts;

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

  // Other editorial collections for the left sidebar
  const otherEditorialCategories = useMemo(() => {
    return EDITORIAL_CATEGORIES.filter((c) => {
      const normCat = normalizeName(c.dbCategory);
      const normCur = normalizeName(selectedCategory);
      return normCat !== normCur && normalizeName(c.creativeTitle) !== normCur;
    });
  }, [selectedCategory]);

  return (
    <div style={{ paddingBottom: '4rem' }}>
      {/* =================================================================
          1. RECREATED EDITORIAL CATEGORY CARDS SECTION (Top Landing)
         ================================================================= */}
      <CategoryEditorialSection
        selectedCategory={selectedCategory}
        onSelectCategory={handleCategorySelect}
        showMasthead={true}
        defaultDepartment="all"
      />

      {/* =================================================================
          2. DUAL-PANE PRODUCT LISTING SECTION (Loaded from Database)
         ================================================================= */}
      <div
        ref={productsSectionRef}
        id="category-products-view"
        style={{ scrollMarginTop: '110px', paddingTop: '1rem' }}
      >
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
          <span style={{ color: '#B8505E', fontWeight: 600 }}>{activeCreativeTitle}</span>
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
          {/* LEFT SIDEBAR: subcategories and department switcher */}
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
              {activeCreativeTitle}
            </span>

            {/* Subcategories list */}
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
                Other Collections
              </span>
            </div>

            {/* Other Editorial Collections Switcher */}
            {otherEditorialCategories.slice(0, 8).map((cat) => (
              <button
                key={cat.id}
                type="button"
                className="department-tab-btn"
                onClick={() => handleCategorySelect(cat.dbCategory)}
              >
                <span>{cat.creativeTitle}</span>
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
                    src={activeHeroImage}
                    alt={activeCreativeTitle}
                    loading="lazy"
                  />
                </div>
              </div>
            </div>

            {/* Active Search Banner */}
            {isSearchActive && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  backgroundColor: '#FFF5F6',
                  border: '1px solid rgba(216, 114, 126, 0.35)',
                  borderRadius: '16px',
                  padding: '10px 18px',
                  marginBottom: '1.25rem',
                  gap: '12px',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={16} color="#B8505E" />
                  <span style={{ fontSize: '0.88rem', color: '#1F191B' }}>
                    Showing search results for: <strong style={{ color: '#B8505E' }}>"{currentSearch}"</strong>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    next.delete('search');
                    setSearchParams(next);
                  }}
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #D8727E',
                    borderRadius: '9999px',
                    color: '#B8505E',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    padding: '4px 12px',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#D8727E';
                    e.currentTarget.style.color = '#FFFFFF';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#FFFFFF';
                    e.currentTarget.style.color = '#B8505E';
                  }}
                >
                  Clear Search ✕
                </button>
              </div>
            )}

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
              {(activeSubcategory !== 'All' ||
                selectedSize !== 'All' ||
                selectedColor !== 'All' ||
                onlySale ||
                onlyInStock ||
                maxPriceFilter) && (
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

            {productsError && (
              <div className="tarika-auth-alert" role="alert" style={{ marginBottom: '1rem' }}>
                {productsError}
              </div>
            )}

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
              <>
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
                {hasMore && (
                  <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2rem' }}>
                    <button
                      type="button"
                      className="tarika-btn-outline"
                      onClick={handleLoadMore}
                      disabled={loadingMore}
                    >
                      {loadingMore ? 'Loading…' : 'Load More Products'}
                    </button>
                  </div>
                )}
              </>
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
                  {activeCreativeTitle}.
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
