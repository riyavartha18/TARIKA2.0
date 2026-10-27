import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ChevronRight,
  Sparkles,
  Tag,
  Check,
  RotateCcw
} from 'lucide-react';
import ProductCard from '../../components/customer/ProductCard';
import { getCategories, getProducts } from '../../services/api';

// Neutral banner copy used when a category carries no creative metadata.
// Category names, counts and subcategories all come from the database.
const DEFAULT_SUBTITLE = 'Curated with refined craftsmanship for the modern wardrobe.';
const FALLBACK_CATEGORY_IMAGE =
  'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80';

const normalizeName = (value) => String(value || '').trim().toLowerCase();

export default function ShopCategories() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch = searchParams.get('search') || '';

  const [categories, setCategories] = useState([]);
  // '' until the database category list has loaded, so the page can never
  // render or query an invented category.
  const [selectedCategory, setSelectedCategory] = useState(
    searchParams.get('category') || ''
  );
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

  // Customer-facing categories straight from the database (products
  // main_category GROUP BY), strictly excluding Kids Wear.
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

  // Ensure the active category is always a real database category: keep the
  // URL selection when it matches, otherwise fall back to the first DB one.
  useEffect(() => {
    if (!categories.length) return;
    const matchesDb = categories.some(
      (c) => normalizeName(c.category_name) === normalizeName(selectedCategory)
    );
    if (matchesDb) {
      const canonical = categories.find(
        (c) => normalizeName(c.category_name) === normalizeName(selectedCategory)
      ).category_name;
      if (canonical !== selectedCategory) setSelectedCategory(canonical);
    } else {
      setSelectedCategory(categories[0].category_name);
      setActiveSubcategory('All');
    }
  }, [categories, selectedCategory]);

  // The DB entry for the active category, with its real sub_categories.
  const activeCategory = useMemo(
    () =>
      categories.find(
        (c) => normalizeName(c.category_name) === normalizeName(selectedCategory)
      ) || null,
    [categories, selectedCategory]
  );

  // When a query param changes in URL. Only real database categories are
  // applied, so an old bookmark (e.g. ?category=Dresses) can never re-enter
  // the selection and fight the reconciliation effect above.
  useEffect(() => {
    const urlCategory = searchParams.get('category');
    if (!urlCategory || urlCategory === selectedCategory || !categories.length) return;
    const match = categories.find(
      (c) => normalizeName(c.category_name) === normalizeName(urlCategory)
    );
    if (match) {
      setSelectedCategory(match.category_name);
      setActiveSubcategory('All');
    }
  }, [searchParams, selectedCategory, categories]);

  // Build the server query from the currently active filters.
  const buildProductParams = useCallback((pageNum) => {
    const params = {
      sort: selectedSort,
      page_size: 20,
      page: pageNum,
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
    if (onlySale) params.on_sale = 'true';
    if (selectedSize !== 'All') params.size = selectedSize;
    if (selectedColor !== 'All') params.color = selectedColor;
    // Subcategory filtering only ever uses real database sub_category values.
    if (activeSubcategory && activeSubcategory !== 'All' && activeCategory) {
      const isRealSubcategory = (activeCategory.sub_categories || []).some(
        (subcategory) => subcategory.sub_category === activeSubcategory
      );
      if (isRealSubcategory) {
        params.sub_category = activeSubcategory;
      }
    }
    return params;
  }, [selectedCategory, initialSearch, onlyInStock, maxPriceFilter, onlySale,
    selectedSize, selectedColor, activeSubcategory, activeCategory, selectedSort]);

  // Fetch the first page whenever the active filters change.
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

  // Append the next page without duplicating already-loaded products.
  const handleLoadMore = async () => {
    if (loadingMore || !hasMore) return;
    const seq = reqSeq.current;
    const nextPage = page + 1;
    setLoadingMore(true);
    setProductsError(null);
    try {
      const res = await getProducts(buildProductParams(nextPage));
      if (seq !== reqSeq.current) return; // filters changed mid-flight
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

  const activeCreativeTitle = selectedCategory ? selectedCategory.toUpperCase() : '';
  const activeSubtitle = DEFAULT_SUBTITLE;
  const activeBannerQuote = activeCategory?.image
    ? 'Curated from the latest drops.'
    : 'Chosen from the real collection.';

  // Sidebar subcategory list built ONLY from database sub_category values.
  const activeSubcategories = useMemo(() => {
    if (!activeCategory) return [];
    return ['All', ...(activeCategory.sub_categories || []).map((s) => s.sub_category)];
  }, [activeCategory]);

  return (
    <div style={{ paddingBottom: '4rem' }}>
      {/* =================================================================
          CATEGORY PRODUCT SECTION (Loaded with Actual Database Products)
          The category-card landing now lives on the Customer Home page.
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
          {/* LEFT SIDEBAR: database sub-categories and department switcher */}
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

            {/* Subcategories straight from the database sub_category column */}
            {activeSubcategories.map((sub, index) => {
              const isActive = activeSubcategory === sub || (index === 0 && activeSubcategory === 'All');
              const subCount =
                index === 0
                  ? activeCategory?.product_count
                  : (activeCategory?.sub_categories || []).find(
                      (s) => s.sub_category === sub
                    )?.product_count;
              return (
                <button
                  key={sub}
                  type="button"
                  className={`department-tab-btn ${isActive ? 'is-active' : ''}`}
                  onClick={() => setActiveSubcategory(sub)}
                >
                  <span>{sub === 'All' ? `All ${selectedCategory}` : sub}</span>
                  {subCount !== undefined && (
                    <span
                      style={{
                        fontSize: '0.72rem',
                        color: isActive ? '#B8505E' : '#9E8F94',
                      }}
                    >
                      ({subCount.toLocaleString('en-IN')})
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
                  normalizeName(cat.category_name) !== normalizeName(selectedCategory)
              )
              .map((cat) => (
                <button
                  key={cat.category_id || cat.category_name}
                  type="button"
                  className="department-tab-btn"
                  onClick={() => handleCategorySelect(cat.category_name)}
                >
                  <span>{cat.category_name}</span>
                  <span style={{ fontSize: '0.72rem', color: '#9E8F94' }}>
                    {cat.product_count !== undefined
                      ? `(${cat.product_count.toLocaleString('en-IN')})`
                      : ''}
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
                    src={activeCategory?.image || FALLBACK_CATEGORY_IMAGE}
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
                  {categories.length === 0
                    ? 'Categories Are Loading'
                    : 'No Products Found In This Selection'}
                </h3>
                <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: '0 0 1.5rem 0' }}>
                  {categories.length === 0
                    ? 'The category list could not be loaded. Please refresh the page.'
                    : `Try resetting your price, size, or stock filters to view available styles in ${selectedCategory}.`}
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
