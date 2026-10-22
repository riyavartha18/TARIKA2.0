import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { Sparkles, Flame, Tag, Check, SlidersHorizontal, ChevronRight } from 'lucide-react';
import ProductCard from '../../components/customer/ProductCard';
import { getProductPricing } from '../../utils/pricing';
import {
  getNewArrivals,
  getTrending,
  getSale,
  getProducts,
  getCategories,
} from '../../services/api';

export default function ProductListingPage({ type }) {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  // Determine section type: 'new-in', 'trending', 'sale', or 'general'
  let sectionType = type;
  if (!sectionType) {
    if (location.pathname.includes('/new-in')) sectionType = 'new-in';
    else if (location.pathname.includes('/trending')) sectionType = 'trending';
    else if (location.pathname.includes('/sale')) sectionType = 'sale';
    else sectionType = 'general';
  }

  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active filters
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get('category') || 'ALL');
  const [selectedSort, setSelectedSort] = useState('newest');
  const [onlyInStock, setOnlyInStock] = useState(false);
  const [maxPrice, setMaxPrice] = useState('');

  // Incremental loading (server-side pagination) for the general catalogue
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const reqSeq = useRef(0);

  // Titles and metadata
  const meta = {
    'new-in': {
      title: 'New In Drops',
      subtitle: 'The latest runway silhouettes, fresh arrivals, and seasonal must-haves.',
      icon: <Sparkles size={20} color="#D8727E" />,
      badge: 'Fresh Off The Atelier',
    },
    trending: {
      title: 'Trending Haute Picks',
      subtitle: 'Most coveted styles trending among TARIKA fashion connoisseurs.',
      icon: <Flame size={20} color="#D8727E" />,
      badge: 'High Demand',
    },
    sale: {
      title: 'Flash Sale & Reductions',
      subtitle: 'Seasonal luxury pieces at exclusive member markdown prices.',
      icon: <Tag size={20} color="#D8727E" />,
      badge: 'Limited Quantities',
    },
    general: {
      title: 'Curated Catalog',
      subtitle: 'Browse TARIKA ready-to-wear garments and accessories.',
      icon: <Sparkles size={20} color="#D8727E" />,
      badge: 'All Styles',
    },
  }[sectionType] || {
    title: 'Curated Collection',
    subtitle: 'High fashion for your story.',
    icon: <Sparkles size={20} color="#D8727E" />,
    badge: 'Collection',
  };

  useEffect(() => {
    async function loadCategories() {
      const res = await getCategories();
      if (res.success) setCategories(res.categories || []);
    }
    loadCategories();
  }, []);

  const mapSortParam = (s) =>
    s === 'price_asc' ? 'price_low_high' : s === 'price_desc' ? 'price_high_low' : 'newest';

  const buildGeneralParams = (pageNum) => {
    const params = { page_size: 24, page: pageNum, sort: mapSortParam(selectedSort) };
    if (selectedCategory && selectedCategory !== 'ALL') params.category = selectedCategory;
    if (onlyInStock) params.in_stock = 'true';
    if (maxPrice) params.max_price = maxPrice;
    return params;
  };

  // Curated sections (new-in / trending / sale) return a limited list, so their
  // extra filters are applied on the client exactly as before.
  const applyClientFilters = (inputList) => {
    let list = [...(inputList || [])];
    if (selectedCategory && selectedCategory !== 'ALL') {
      list = list.filter(
        (p) =>
          (p.category?.slug && p.category.slug.toLowerCase() === selectedCategory.toLowerCase()) ||
          (p.category?.name && p.category.name.toLowerCase() === selectedCategory.toLowerCase()) ||
          (p.category_name && p.category_name.toLowerCase() === selectedCategory.toLowerCase())
      );
    }
    if (onlyInStock) {
      list = list.filter((p) => p.total_stock > 0 || p.is_in_stock);
    }
    if (maxPrice) {
      list = list.filter((p) => getProductPricing(p).currentPrice <= Number(maxPrice));
    }
    if (selectedSort === 'price_asc') {
      list.sort((a, b) => getProductPricing(a).currentPrice - getProductPricing(b).currentPrice);
    } else if (selectedSort === 'price_desc') {
      list.sort((a, b) => getProductPricing(b).currentPrice - getProductPricing(a).currentPrice);
    }
    return list;
  };

  useEffect(() => {
    const seq = ++reqSeq.current;
    let active = true;
    async function loadData() {
      setLoading(true);
      try {
        if (sectionType === 'general') {
          // Server-side filtering + pagination for the full catalogue.
          const res = await getProducts(buildGeneralParams(1));
          if (!active || seq !== reqSeq.current) return;
          if (res.success) {
            setProducts(res.products || []);
            setPage(1);
            setHasMore(Boolean(res.hasNext));
          }
        } else {
          let res;
          if (sectionType === 'new-in') res = await getNewArrivals(24);
          else if (sectionType === 'trending') res = await getTrending(24);
          else res = await getSale(24);
          if (!active || seq !== reqSeq.current) return;
          if (res.success) {
            setProducts(applyClientFilters(res.products || []));
            setHasMore(false);
          }
        }
      } catch (err) {
        if (active && seq === reqSeq.current) console.error('Error loading products', err);
      } finally {
        if (active && seq === reqSeq.current) setLoading(false);
      }
    }

    loadData();
    return () => {
      active = false;
    };
  }, [sectionType, selectedCategory, selectedSort, onlyInStock, maxPrice]);

  const handleLoadMore = async () => {
    if (sectionType !== 'general' || loadingMore || !hasMore) return;
    const seq = reqSeq.current;
    const nextPage = page + 1;
    setLoadingMore(true);
    try {
      const res = await getProducts(buildGeneralParams(nextPage));
      if (seq !== reqSeq.current) return;
      if (res.success) {
        const incoming = res.products || [];
        setProducts((prev) => {
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
      }
    } catch (err) {
      if (seq === reqSeq.current) console.error('Error loading more products', err);
    } finally {
      if (seq === reqSeq.current) setLoadingMore(false);
    }
  };

  return (
    <div style={{ paddingBottom: '4rem' }}>
      {/* Header Banner */}
      <div
        style={{
          borderRadius: '24px',
          padding: '2.5rem 3rem',
          background: 'linear-gradient(135deg, #FBF1F0 0%, #F7E4E2 50%, #F5D3D1 100%)',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          marginBottom: '2.5rem',
          boxShadow: '0 8px 30px rgba(184, 80, 94, 0.06)',
        }}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '8px' }}>
          {meta.icon}
          <span style={{ fontSize: '0.76rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            {meta.badge}
          </span>
        </div>
        <h1
          style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: '2.5rem',
            fontWeight: 700,
            color: '#1F191B',
            margin: '0 0 0.5rem 0',
          }}
        >
          {meta.title}
        </h1>
        <p style={{ margin: 0, color: '#6B5E63', fontSize: '1rem', maxWidth: '650px' }}>
          {meta.subtitle}
        </p>
      </div>

      {/* Filter & Sort Bar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          padding: '14px 20px',
          backgroundColor: '#FFFFFF',
          borderRadius: '16px',
          border: '1px solid rgba(240, 226, 224, 0.9)',
          boxShadow: '0 4px 16px rgba(184, 80, 94, 0.04)',
          marginBottom: '2rem',
        }}
      >
        {/* Category Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setSelectedCategory('ALL')}
            style={{
              padding: '6px 14px',
              borderRadius: '9999px',
              border: `1px solid ${selectedCategory === 'ALL' ? '#D8727E' : '#F0E2E0'}`,
              backgroundColor: selectedCategory === 'ALL' ? '#FBF1F0' : '#FAF7F5',
              color: selectedCategory === 'ALL' ? '#B8505E' : '#1F191B',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            All Categories
          </button>

          {categories.slice(0, 6).map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.slug || cat.name)}
              style={{
                padding: '6px 14px',
                borderRadius: '9999px',
                border: `1px solid ${selectedCategory === cat.slug || selectedCategory === cat.name ? '#D8727E' : '#F0E2E0'}`,
                backgroundColor: selectedCategory === cat.slug || selectedCategory === cat.name ? '#FBF1F0' : '#FAF7F5',
                color: selectedCategory === cat.slug || selectedCategory === cat.name ? '#B8505E' : '#1F191B',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              {cat.name}
            </button>
          ))}
        </div>

        {/* Right side: In stock, max price, sort */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
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
            }}
          >
            <span>In Stock Only</span>
            {onlyInStock && <Check size={12} />}
          </button>

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
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
          </select>
        </div>
      </div>

      {/* Product count */}
      <div style={{ marginBottom: '1.25rem', fontSize: '0.84rem', color: '#6B5E63' }}>
        Showing <strong>{products.length}</strong> items
      </div>

      {/* Grid */}
      {loading ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
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
      ) : products.length > 0 ? (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
              gap: '1.5rem',
            }}
          >
            {products.map((prod) => (
              <ProductCard key={prod.product_id || prod.id} product={prod} />
            ))}
          </div>
          {sectionType === 'general' && hasMore && (
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
            padding: '5rem 2rem',
            textAlign: 'center',
            backgroundColor: '#FFFFFF',
            borderRadius: '24px',
            border: '1px solid #F0E2E0',
          }}
        >
          <Sparkles size={40} color="#D8727E" style={{ marginBottom: '1rem' }} />
          <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.5rem', color: '#1F191B', margin: '0 0 0.5rem 0' }}>
            No Products Found
          </h3>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: '0 0 1.5rem 0' }}>
            There are currently no garments matching these exact filter specifications.
          </p>
          <button
            type="button"
            className="tarika-btn-outline"
            onClick={() => {
              setSelectedCategory('ALL');
              setOnlyInStock(false);
              setMaxPrice('');
            }}
          >
            Reset All Filters
          </button>
        </div>
      )}
    </div>
  );
}
