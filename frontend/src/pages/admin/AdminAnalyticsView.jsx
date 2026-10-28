import React, { useState, useEffect, useCallback } from 'react';
import demandForecastingVisual from '../../assets/demand_forecasting_visual.png';
import { useAuth } from '../../auth/AuthContext';
import {
  getDemandPredictionAnalytics,
  getDemandPredictionProducts,
  getDemandPredictionCategories,
  getSlowMovingInventory,
  getProductSalesHistory,
} from '../../services/api';
import {
  BrainCircuit,
  Search,
  RefreshCw,
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  PackageSearch,
  TrendingDown,
  AlertTriangle,
  Archive,
  Box,
  IndianRupee,
  TrendingUp,
  Flame,
  Activity,
  ThumbsDown,
  Heart,
  ShoppingCart,
  Package,
  Images,
  X,
} from 'lucide-react';
import '../../styles/admin-portal.css';

export default function AdminAnalyticsView() {
  const { token: authContextToken } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  // Active view: 'overview' | 'demand_forecasting' | 'slow_inventory'
  const [activeView, setActiveView] = useState('overview');

  // Filters for product predictions (server-driven)
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [demandFilter, setDemandFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [sortKey, setSortKey] = useState('demand');
  const [sortDirection, setSortDirection] = useState('desc');

  // Paged product predictions + categories (fetched from the backend)
  const [productItems, setProductItems] = useState([]);
  const [productPagination, setProductPagination] = useState({ page: 1, page_size: 12, total_filtered: 0, total_pages: 0, filtered_distribution: {} });
  const [productsPage, setProductsPage] = useState(1);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState(null);
  const [categoriesList, setCategoriesList] = useState([]);

  // === Slow-Moving Inventory State ===
  const [slowLoading, setSlowLoading] = useState(false);
  const [slowError, setSlowError] = useState(null);
  const [slowData, setSlowData] = useState(null);
  const [slowSearchQuery, setSlowSearchQuery] = useState('');
  const [slowStatusFilter, setSlowStatusFilter] = useState('ALL');
  const [slowWarehouseFilter, setSlowWarehouseFilter] = useState('ALL');

  // Product detail drawer (image click) + sales-history graph
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [history, setHistory] = useState({ loading: false, error: null, points: [], totalUnits: 0, granularity: 'month' });

  const getActiveToken = () =>
    authContextToken || localStorage.getItem('iras_token') || localStorage.getItem('token');

  const loadHistory = useCallback(async (productKey, granularity = 'month') => {
    setHistory({ loading: true, error: null, points: [], totalUnits: 0, granularity });
    const res = await getProductSalesHistory(
      authContextToken || localStorage.getItem('iras_token') || localStorage.getItem('token'),
      productKey, granularity,
    );
    setHistory(res.success
      ? { loading: false, error: null, points: res.points || [], totalUnits: res.totalUnits || 0, granularity }
      : { loading: false, error: res.error || 'Failed to load sales history.', points: [], totalUnits: 0, granularity });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authContextToken]);

  const openProductDetail = (p) => {
    setSelectedProduct(p);
    loadHistory(p.product_key, 'month');
  };

  const changeGranularity = (g) => {
    if (selectedProduct) loadHistory(selectedProduct.product_key, g);
  };

  const fetchAnalyticsData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getDemandPredictionAnalytics(getActiveToken());
      if (res.success) {
        setData(res);
      } else {
        setError(res.error || 'Failed to load demand prediction analytics.');
      }
    } catch (err) {
      setError('An unexpected error occurred while fetching demand prediction analytics.');
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await getDemandPredictionCategories(getActiveToken());
      if (res.success) setCategoriesList(res.categories);
    } catch (err) {
      /* non-fatal: filters just fall back to an empty list */
    }
  };

  const fetchProducts = useCallback(async () => {
    setProductsLoading(true);
    setProductsError(null);
    try {
      const res = await getDemandPredictionProducts(getActiveToken(), {
        page: productsPage,
        page_size: productPagination.page_size,
        search: debouncedSearch,
        demand_level: demandFilter,
        category: categoryFilter,
        sort: sortKey,
        dir: sortDirection,
      });
      if (res.success) {
        setProductItems(res.items || []);
        setProductPagination(res.pagination || productPagination);
      } else {
        setProductsError(res.error || 'Failed to load demand predictions.');
      }
    } catch (err) {
      setProductsError('An unexpected error occurred while loading demand predictions.');
    } finally {
      setProductsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productsPage, productPagination.page_size, debouncedSearch, demandFilter, categoryFilter, sortKey, sortDirection]);

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 350);
    return () => clearTimeout(id);
  }, [searchQuery]);

  // Reset to first page whenever a filter/sort changes.
  useEffect(() => {
    setProductsPage(1);
  }, [debouncedSearch, demandFilter, categoryFilter, sortKey, sortDirection]);

  // Fetch the current page whenever the paged query changes (only while open).
  useEffect(() => {
    if (activeView === 'demand_forecasting') {
      fetchProducts();
    }
  }, [activeView, fetchProducts]);

  const fetchSlowInventoryData = async () => {
    setSlowLoading(true);
    setSlowError(null);
    try {
      const res = await getSlowMovingInventory(getActiveToken());
      if (res.success) {
        setSlowData(res);
      } else {
        setSlowError(res.error || 'Failed to load slow-moving inventory data.');
      }
    } catch (err) {
      setSlowError('An unexpected error occurred while fetching slow-moving inventory data.');
    } finally {
      setSlowLoading(false);
    }
  };

  // Open the demand forecasting detail view (loads analytics + categories once).
  const handleOpenDetailView = () => {
    setActiveView('demand_forecasting');
    if (!data) {
      fetchAnalyticsData();
    }
    if (categoriesList.length === 0) {
      fetchCategories();
    }
  };

  const handleOpenSlowInventoryView = () => {
    setActiveView('slow_inventory');
    if (!slowData) {
      fetchSlowInventoryData();
    }
  };

  const { summary = {} } = data || {};

  // Demand metrics come from the cached analytics model (whole-catalog truth);
  // per-product rows come from the paged products endpoint.
  const distribution = summary.predicted_distribution || {};
  const highCount = distribution.High || 0;
  const medCount = distribution.Medium || 0;
  const lowCount = distribution.Low || 0;
  const totalCount = summary.total_products || 0;

  // === Slow-Moving Inventory Filtering (client-side) ===
  const slowItems = slowData?.items || [];
  const slowSummary = slowData?.summary || {};
  const slowWarehouses = slowData?.warehouses || [];

  const filteredSlowItems = slowItems.filter((item) => {
    const matchesSearch =
      item.product_name.toLowerCase().includes(slowSearchQuery.toLowerCase()) ||
      item.category_name.toLowerCase().includes(slowSearchQuery.toLowerCase());
    const matchesStatus = slowStatusFilter === 'ALL' || item.movement_status === slowStatusFilter;
    const matchesWarehouse = slowWarehouseFilter === 'ALL' || String(item.warehouse_id) === slowWarehouseFilter;
    return matchesSearch && matchesStatus && matchesWarehouse;
  });

  // Movement status badge style helper
  const getStatusStyle = (status) => {
    switch (status) {
      case 'VERY SLOW':
        return { backgroundColor: '#FEF2F2', color: '#DC2626', borderColor: '#FCA5A5' };
      case 'SLOW':
        return { backgroundColor: '#FFFBEB', color: '#D97706', borderColor: '#FDE68A' };
      case 'NORMAL':
        return { backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' };
      default:
        return { backgroundColor: '#F3F4F6', color: '#6B7280', borderColor: '#D1D5DB' };
    }
  };

  return (
    <div>
      {/* ==========================================================================
          MAIN OVERVIEW PAGE: PREDICTIVE DATA MINING MODULES
         ========================================================================== */}
      {activeView === 'overview' && (
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          {/* Section Title */}
          <div style={{ marginBottom: '1.75rem' }}>
            <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '2rem', fontWeight: 700, color: '#1F191B', margin: '0 0 0.35rem 0' }}>
              Predictive Data Mining Modules
            </h1>
            <p style={{ color: '#6B5E63', fontSize: '0.92rem', margin: 0 }}>
              Independent analytical modules designed for machine learning, forecasting, and pattern discovery.
            </p>
          </div>

          {/* Analysis feature cards — two per row (responsive via .admin-grid-2col) */}
          <div className="admin-grid-2col">

          {/* DEMAND FORECASTING CARD */}
          <div
            className="admin-card"
            style={{
              padding: '2.25rem',
              borderRadius: '20px',
              border: '1px solid rgba(216, 114, 126, 0.2)',
              cursor: 'pointer',
              transition: 'all 0.25s ease',
              boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)',
              backgroundColor: '#FFFFFF'
            }}
            onClick={handleOpenDetailView}
          >
            {/* Card Top Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div
                  style={{
                    width: '52px',
                    height: '52px',
                    borderRadius: '14px',
                    backgroundColor: '#FDF2F4',
                    color: '#B8505E',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <BrainCircuit size={26} />
                </div>
                <div>
                  <h2 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.6rem', fontWeight: 700, color: '#1F191B', margin: 0, lineHeight: 1.2 }}>
                    Demand Forecasting
                  </h2>
                  <span style={{ fontSize: '0.75rem', color: '#9E8F94', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    FEATURE #1 &bull; PREDICTIVE CLASSIFIER
                  </span>
                </div>
              </div>

              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.4rem 0.95rem',
                  borderRadius: '9999px',
                  backgroundColor: '#ECFDF5',
                  border: '1px solid #A7F3D0',
                  color: '#059669',
                  fontSize: '0.82rem',
                  fontWeight: 600
                }}
              >
                <CheckCircle2 size={14} />
                Active Engine
              </span>
            </div>

            {/* Description */}
            <p style={{ color: '#6B5E63', fontSize: '0.95rem', lineHeight: 1.6, margin: '0 0 1.75rem 0' }}>
              Classifies catalog products into demand tiers (High, Medium, Low) from live customer demand signals ( <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>wishlist_count</code> , <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>cart_count</code> , <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>purchase_count</code> ) to predict demand strength ( <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>units_sold</code> ), using a manual ID3 Decision Tree over <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>fact_product_analysis</code> joined to <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>products</code> on <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>product_key</code>.
            </p>

            {/* Demand Forecasting Visual Banner */}
            <div style={{ marginBottom: '2rem', borderRadius: '14px', overflow: 'hidden', background: '#FAF7F5', border: '1px solid rgba(216, 114, 126, 0.1)' }}>
              <img
                src={demandForecastingVisual}
                alt="Demand Forecasting — High, Medium, Low tier distribution visual"
                style={{ width: '100%', maxHeight: '220px', objectFit: 'cover', display: 'block' }}
              />
            </div>

            {/* Bottom Row Action */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '1.25rem', borderTop: '1px solid rgba(216, 114, 126, 0.15)', flexWrap: 'wrap', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.9rem', color: '#6B5E63' }}>
                Open product-level demand predictions
              </span>

              <button
                style={{
                  background: 'linear-gradient(135deg, #B8505E 0%, #8E3642 100%)',
                  color: '#FFFFFF',
                  padding: '0.7rem 1.5rem',
                  borderRadius: '9999px',
                  border: 'none',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  boxShadow: '0 4px 14px rgba(184, 80, 94, 0.25)'
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenDetailView();
                }}
              >
                <span>View Demand Details</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {/* ================================================================
              SLOW-MOVING INVENTORY CARD
             ================================================================ */}
          <div
            className="admin-card"
            style={{
              padding: '2.25rem',
              borderRadius: '20px',
              border: '1px solid rgba(216, 114, 126, 0.2)',
              cursor: 'pointer',
              transition: 'all 0.25s ease',
              boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)',
              backgroundColor: '#FFFFFF'
            }}
            onClick={handleOpenSlowInventoryView}
          >
            {/* Card Top Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div
                  style={{
                    width: '52px',
                    height: '52px',
                    borderRadius: '14px',
                    backgroundColor: '#FEF3C7',
                    color: '#D97706',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <PackageSearch size={26} />
                </div>
                <div>
                  <h2 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.6rem', fontWeight: 700, color: '#1F191B', margin: 0, lineHeight: 1.2 }}>
                    Slow-Moving Inventory
                  </h2>
                  <span style={{ fontSize: '0.75rem', color: '#9E8F94', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    FEATURE #2 &bull; INVENTORY VELOCITY ANALYSIS
                  </span>
                </div>
              </div>

              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.4rem 0.95rem',
                  borderRadius: '9999px',
                  backgroundColor: '#ECFDF5',
                  border: '1px solid #A7F3D0',
                  color: '#059669',
                  fontSize: '0.82rem',
                  fontWeight: 600
                }}
              >
                <CheckCircle2 size={14} />
                Active Engine
              </span>
            </div>

            {/* Description */}
            <p style={{ color: '#6B5E63', fontSize: '0.95rem', lineHeight: 1.6, margin: '0 0 1.75rem 0' }}>
              Identifies products whose current inventory is moving slowly based on historical sales velocity. Calculates <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>days_of_stock</code> from <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>current_stock</code> ÷ <code style={{ background: '#FAF7F5', border: '1px solid rgba(216,114,126,0.15)', padding: '0.15rem 0.45rem', borderRadius: '5px', color: '#1F191B', fontSize: '0.85rem' }}>avg_daily_sales</code> and classifies each product-warehouse pair as <strong style={{ color: '#DC2626' }}>Very Slow</strong>, <strong style={{ color: '#D97706' }}>Slow</strong>, or <strong style={{ color: '#059669' }}>Normal</strong>.
            </p>

            {/* Visual Banner for Slow-Moving Inventory */}
            <div style={{
              marginBottom: '2rem',
              borderRadius: '14px',
              overflow: 'hidden',
              background: 'linear-gradient(135deg, #FEF3C7 0%, #FDE68A 40%, #FBBF24 100%)',
              border: '1px solid rgba(216, 114, 126, 0.1)',
              padding: '2rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '2rem',
              flexWrap: 'wrap'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Archive size={28} style={{ color: '#92400E' }} />
                <div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#92400E' }}>Very Slow</div>
                  <div style={{ fontSize: '0.8rem', color: '#78350F' }}>0 sales or 180+ days stock</div>
                </div>
              </div>
              <div style={{ width: '1px', height: '40px', background: 'rgba(146, 64, 14, 0.2)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <TrendingDown size={28} style={{ color: '#B45309' }} />
                <div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#92400E' }}>Slow</div>
                  <div style={{ fontSize: '0.8rem', color: '#78350F' }}>60–180 days of stock</div>
                </div>
              </div>
              <div style={{ width: '1px', height: '40px', background: 'rgba(146, 64, 14, 0.2)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Box size={28} style={{ color: '#15803D' }} />
                <div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#15803D' }}>Normal</div>
                  <div style={{ fontSize: '0.8rem', color: '#166534' }}>≤ 60 days of stock</div>
                </div>
              </div>
            </div>

            {/* Bottom Row Action */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '1.25rem', borderTop: '1px solid rgba(216, 114, 126, 0.15)', flexWrap: 'wrap', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.9rem', color: '#6B5E63' }}>
                Open product-level inventory velocity analysis
              </span>

              <button
                style={{
                  background: 'linear-gradient(135deg, #D97706 0%, #B45309 100%)',
                  color: '#FFFFFF',
                  padding: '0.7rem 1.5rem',
                  borderRadius: '9999px',
                  border: 'none',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  boxShadow: '0 4px 14px rgba(217, 119, 6, 0.25)'
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenSlowInventoryView();
                }}
              >
                <span>View Inventory Analysis</span>
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          </div>
        </div>
      )}

      {/* ==========================================================================
          DEDICATED DETAILED VIEW: DEMAND FORECASTING RESULTS
         ========================================================================== */}
      {activeView === 'demand_forecasting' && (
        <>
          {/* Back Navigation Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <button
                onClick={() => setActiveView('overview')}
                className="tarika-btn-outline"
                style={{ padding: '0.55rem 1.1rem', fontSize: '0.82rem' }}
              >
                <ArrowLeft size={16} />
                <span>Back to Analytics Hub</span>
              </button>
              <div>
                <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: '0 0 0.2rem 0' }}>
                  Demand Forecasting Results
                </h1>
                <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: 0 }}>
                  Product demand tiers (High, Medium, Low) predicted by the ID3 model from customer demand signals.
                </p>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {loading && (
            <div style={{ padding: '4rem 1rem', textAlign: 'center' }}>
              <RefreshCw size={36} className="animate-spin" style={{ color: '#B8505E', marginBottom: '1rem' }} />
              <h3 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", color: '#1F191B', margin: '0 0 0.5rem 0' }}>
                Running Demand Prediction Engine...
              </h3>
              <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: 0 }}>
                Processing historical demand data from Supabase...
              </p>
            </div>
          )}

          {/* Error State */}
          {!loading && error && (
            <div style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', padding: '1.5rem', borderRadius: '12px', color: '#991B1B', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
                <AlertCircle size={20} color="#DC2626" />
                <strong style={{ fontSize: '1.05rem' }}>Demand Forecasting Engine Notice</strong>
              </div>
              <p style={{ margin: '0 0 1rem 0', fontSize: '0.92rem' }}>{error}</p>
              <button className="tarika-btn-outline" onClick={fetchAnalyticsData}>
                <RefreshCw size={14} /> Retry
              </button>
            </div>
          )}

          {/* Data Loaded */}
          {!loading && !error && data && (
            <>
              {/* Metrics Grid */}
              <div className="admin-metrics-grid" style={{ marginBottom: '1.5rem' }}>
                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title">Matching Products</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem' }}>{(productPagination.total_filtered ?? totalCount).toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Of {totalCount.toLocaleString('en-IN')} catalog items</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#059669' }}><Flame size={13} style={{ verticalAlign: '-2px' }} /> High Demand</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#059669' }}>{highCount.toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Strong purchase &amp; sales signals</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#D97706' }}><Activity size={13} style={{ verticalAlign: '-2px' }} /> Medium Demand</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#D97706' }}>{medCount.toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Steady order volume</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#DC2626' }}><ThumbsDown size={13} style={{ verticalAlign: '-2px' }} /> Low Demand</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#DC2626' }}>{lowCount.toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Limited demand signals</p>
                </div>
              </div>

              {/* Search & Filter Bar */}
              <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.15rem 1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                  {/* Search Box */}
                  <div style={{ flex: '1 1 280px', position: 'relative' }}>
                    <Search size={17} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9E8F94' }} />
                    <input
                      type="text"
                      placeholder="Search product name or category..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.6rem 0.85rem 0.6rem 2.5rem',
                        border: '1px solid rgba(216, 114, 126, 0.25)',
                        borderRadius: '8px',
                        fontSize: '0.88rem',
                        outline: 'none',
                        backgroundColor: '#FAF7F5',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>

                  {/* Demand Tier Filter Pills */}
                  <div style={{ display: 'flex', gap: '0.35rem', background: '#FAF7F5', padding: '0.25rem', borderRadius: '8px', border: '1px solid rgba(216, 114, 126, 0.2)' }}>
                    {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
                      <button
                        key={lvl}
                        onClick={() => setDemandFilter(lvl)}
                        style={{
                          padding: '0.35rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          borderRadius: '6px',
                          border: 'none',
                          cursor: 'pointer',
                          background: demandFilter === lvl ? '#FFFFFF' : 'transparent',
                          color: demandFilter === lvl ? '#B8505E' : '#6B5E63',
                          boxShadow: demandFilter === lvl ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        {lvl}
                      </button>
                    ))}
                  </div>

                  {/* Category Dropdown */}
                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    style={{
                      padding: '0.6rem 0.85rem',
                      fontSize: '0.85rem',
                      borderRadius: '8px',
                      border: '1px solid rgba(216, 114, 126, 0.25)',
                      backgroundColor: '#FAF7F5',
                      color: '#1F191B',
                      outline: 'none'
                    }}
                  >
                    <option value="ALL">All Categories ({categoriesList.length})</option>
                    {categoriesList.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>

                  {/* Sort Dropdown */}
                  <select
                    value={sortKey}
                    onChange={(e) => setSortKey(e.target.value)}
                    style={{
                      padding: '0.6rem 0.85rem',
                      fontSize: '0.85rem',
                      borderRadius: '8px',
                      border: '1px solid rgba(216, 114, 126, 0.25)',
                      backgroundColor: '#FAF7F5',
                      color: '#1F191B',
                      outline: 'none'
                    }}
                  >
                    <option value="demand">Sort: Demand tier</option>
                    <option value="units_sold">Sort: Units sold</option>
                    <option value="total_sales">Sort: Total sales</option>
                    <option value="available_quantity">Sort: Stock on hand</option>
                    <option value="product_name">Sort: Product name</option>
                  </select>

                  <button
                    onClick={() => setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))}
                    className="tarika-btn-outline"
                    style={{ padding: '0.55rem 0.9rem', fontSize: '0.78rem' }}
                    title="Toggle sort direction"
                  >
                    {sortDirection === 'asc' ? 'Ascending ↑' : 'Descending ↓'}
                  </button>
                </div>
              </div>

              {/* Products Loading / Error */}
              {productsLoading && (
                <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: '#6B5E63' }}>
                  <RefreshCw size={26} className="animate-spin" style={{ color: '#B8505E', marginBottom: '0.6rem' }} />
                  <p style={{ margin: 0, fontSize: '0.9rem' }}>Loading product demand predictions…</p>
                </div>
              )}

              {!productsLoading && productsError && (
                <div style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', padding: '1.25rem', borderRadius: '12px', color: '#991B1B', marginBottom: '1.25rem' }}>
                  <strong>{productsError}</strong>
                  <div style={{ marginTop: '0.75rem' }}>
                    <button className="tarika-btn-outline" onClick={fetchProducts}><RefreshCw size={14} /> Retry</button>
                  </div>
                </div>
              )}

              {/* Product Demand Cards */}
              {!productsLoading && !productsError && (
                productItems.length > 0 ? (
                  <div className="df-cards-grid">
                    {productItems.map((p) => {
                      const tier = (p.predicted_demand || 'Medium');
                      const badge = tier === 'High'
                        ? { backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' }
                        : tier === 'Medium'
                        ? { backgroundColor: '#FFFBEB', color: '#D97706', borderColor: '#FDE68A' }
                        : { backgroundColor: '#FEF2F2', color: '#DC2626', borderColor: '#FCA5A5' };
                      const accent = tier === 'High' ? '#059669' : tier === 'Medium' ? '#D97706' : '#DC2626';
                      const lowStock = Number(p.available_quantity) <= 0;
                      const fmtNum = (n) => Number(n || 0).toLocaleString('en-IN');

                      return (
                        <div key={p.product_key} className="df-card" style={{ borderTop: `3px solid ${accent}` }}>
                          <div className="df-card-media" role="button" tabIndex={0}
                            onClick={() => openProductDetail(p)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openProductDetail(p); } }}
                            title="View product details & sales history"
                            style={{ cursor: 'pointer' }}>
                            {p.image ? (
                              <img src={p.image} alt={p.product_name} loading="lazy" className="df-card-img"
                                onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />
                            ) : (
                              <div className="df-card-img df-card-img-placeholder"><Images size={26} /></div>
                            )}
                            <span className="df-card-badge" style={badge}>{tier} Demand</span>
                          </div>

                          <div className="df-card-body">
                            <div className="df-card-title" title={p.product_name}>{p.product_name}</div>
                            <div className="df-card-cat">
                              {p.main_category}{p.sub_category ? ` · ${p.sub_category}` : ''}
                            </div>

                            <div className="df-evidence">
                              <span className="df-chip" title="Units sold"><TrendingUp size={12} /> {fmtNum(p.units_sold)} sold</span>
                              <span className="df-chip" title="Cart count"><ShoppingCart size={12} /> {fmtNum(p.cart_count)}</span>
                              <span className="df-chip" title="Wishlist count"><Heart size={12} /> {fmtNum(p.wishlist_count)}</span>
                              <span className="df-chip" title="Total Revenue (fact_product_analysis.total_sales)"><IndianRupee size={12} /> Total Revenue {fmtNum(Math.round(p.total_sales))}</span>
                            </div>

                            <div className="df-stock" style={{ color: lowStock ? '#DC2626' : '#1F191B' }}>
                              <Package size={13} /> Available stock:{' '}
                              <strong>{fmtNum(p.available_quantity)}</strong>
                              {lowStock ? ' · out of stock' : ''}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="admin-card" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#9E8F94' }}>
                    No products found matching the selected search, category or demand filters.
                  </div>
                )
              )}

              {/* Pagination */}
              {!productsLoading && productItems.length > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>
                    Page <strong>{productPagination.page}</strong> of {productPagination.total_pages || 1}
                    {' '}· {productPagination.total_filtered.toLocaleString('en-IN')} matching products
                  </span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="tarika-btn-outline"
                      style={{ padding: '0.5rem 0.9rem', fontSize: '0.8rem', opacity: productPagination.page <= 1 ? 0.5 : 1 }}
                      disabled={productPagination.page <= 1}
                      onClick={() => setProductsPage((pg) => Math.max(1, pg - 1))}
                    >
                      <ChevronLeft size={15} /> Prev
                    </button>
                    <button
                      className="tarika-btn-outline"
                      style={{ padding: '0.5rem 0.9rem', fontSize: '0.8rem', opacity: productPagination.page >= productPagination.total_pages ? 0.5 : 1 }}
                      disabled={productPagination.page >= productPagination.total_pages}
                      onClick={() => setProductsPage((pg) => pg + 1)}
                    >
                      Next <ChevronRight size={15} />
                    </button>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem', fontSize: '0.82rem', color: '#6B5E63' }}>
                <span>Showing <strong>{productItems.length}</strong> of {productPagination.total_filtered?.toLocaleString('en-IN') ?? totalCount.toLocaleString('en-IN')} products</span>
                <span>Dataset Source: <code style={{ fontSize: '0.75rem' }}>public.fact_product_analysis</code> + <code style={{ fontSize: '0.75rem' }}>public.products</code></span>
              </div>
            </>
          )}
        </>
      )}

      {/* ==========================================================================
          DEDICATED DETAILED VIEW: SLOW-MOVING INVENTORY ANALYSIS
         ========================================================================== */}
      {activeView === 'slow_inventory' && (
        <>
          {/* Back Navigation Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <button
                onClick={() => setActiveView('overview')}
                className="tarika-btn-outline"
                style={{ padding: '0.55rem 1.1rem', fontSize: '0.82rem' }}
              >
                <ArrowLeft size={16} />
                <span>Back to Analytics Hub</span>
              </button>
              <div>
                <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: '0 0 0.2rem 0' }}>
                  Slow-Moving Inventory Analysis
                </h1>
                <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: 0 }}>
                  Product inventory velocity classification based on last 30 days of sales data.
                </p>
              </div>
            </div>

            <button
              onClick={fetchSlowInventoryData}
              className="tarika-btn-outline"
              style={{ padding: '0.55rem 1.1rem', fontSize: '0.82rem' }}
            >
              <RefreshCw size={14} />
              <span>Refresh Analysis</span>
            </button>
          </div>

          {/* Loading State */}
          {slowLoading && (
            <div style={{ padding: '4rem 1rem', textAlign: 'center' }}>
              <RefreshCw size={36} className="animate-spin" style={{ color: '#D97706', marginBottom: '1rem' }} />
              <h3 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", color: '#1F191B', margin: '0 0 0.5rem 0' }}>
                Analyzing Inventory Velocity...
              </h3>
              <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: 0 }}>
                Calculating sales velocity and stock movement from database...
              </p>
            </div>
          )}

          {/* Error State */}
          {!slowLoading && slowError && (
            <div style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', padding: '1.5rem', borderRadius: '12px', color: '#991B1B', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
                <AlertCircle size={20} color="#DC2626" />
                <strong style={{ fontSize: '1.05rem' }}>Slow-Moving Inventory Engine Notice</strong>
              </div>
              <p style={{ margin: '0 0 1rem 0', fontSize: '0.92rem' }}>{slowError}</p>
              <button className="tarika-btn-outline" onClick={fetchSlowInventoryData}>
                <RefreshCw size={14} /> Retry
              </button>
            </div>
          )}

          {/* Data Loaded */}
          {!slowLoading && !slowError && slowData && (
            <>
              {/* Analysis Info Banner */}
              <div style={{
                background: 'linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%)',
                border: '1px solid rgba(217, 119, 6, 0.25)',
                borderRadius: '14px',
                padding: '1.25rem 1.5rem',
                marginBottom: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{
                    width: '44px', height: '44px', borderRadius: '12px',
                    backgroundColor: '#FEF3C7', color: '#D97706',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <PackageSearch size={22} />
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#92400E', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Inventory Velocity Analysis
                    </span>
                    <h3 style={{ margin: '0.1rem 0 0', fontSize: '1.25rem', fontWeight: 800, color: '#1F191B', fontFamily: "var(--font-serif, 'Playfair Display', serif)" }}>
                      Sales Window: <span style={{ color: '#D97706' }}>{slowData.sales_window_start} → {slowData.analysis_date}</span>
                    </h3>
                  </div>
                </div>
                <div style={{ fontSize: '0.85rem', color: '#6B5E63' }}>
                  Analysis Date: <strong style={{ color: '#1F191B' }}>{slowData.analysis_date}</strong>
                </div>
              </div>

              {/* Summary Metrics Grid */}
              <div className="admin-metrics-grid" style={{ marginBottom: '1.5rem' }}>
                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title">Total Inventory</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem' }}>{slowSummary.total_inventory || 0}</p>
                  <p className="admin-metric-subtext">Product-warehouse entries</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#DC2626' }}>Very Slow</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#DC2626' }}>{slowSummary.very_slow || 0}</p>
                  <p className="admin-metric-subtext">No sales or 180+ days stock</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#D97706' }}>Slow</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#D97706' }}>{slowSummary.slow || 0}</p>
                  <p className="admin-metric-subtext">60–180 days of stock</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#059669' }}>Normal</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#059669' }}>{slowSummary.normal || 0}</p>
                  <p className="admin-metric-subtext">Healthy movement ≤ 60 days</p>
                </div>
              </div>

              {/* Search & Filter Bar */}
              <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.15rem 1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                  {/* Search Box */}
                  <div style={{ flex: '1 1 280px', position: 'relative' }}>
                    <Search size={17} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9E8F94' }} />
                    <input
                      type="text"
                      placeholder="Search product name or category..."
                      value={slowSearchQuery}
                      onChange={(e) => setSlowSearchQuery(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.6rem 0.85rem 0.6rem 2.5rem',
                        border: '1px solid rgba(216, 114, 126, 0.25)',
                        borderRadius: '8px',
                        fontSize: '0.88rem',
                        outline: 'none',
                        backgroundColor: '#FAF7F5',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>

                  {/* Movement Status Filter Pills */}
                  <div style={{ display: 'flex', gap: '0.35rem', background: '#FAF7F5', padding: '0.25rem', borderRadius: '8px', border: '1px solid rgba(216, 114, 126, 0.2)' }}>
                    {['ALL', 'VERY SLOW', 'SLOW', 'NORMAL'].map((lvl) => (
                      <button
                        key={lvl}
                        onClick={() => setSlowStatusFilter(lvl)}
                        style={{
                          padding: '0.35rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          borderRadius: '6px',
                          border: 'none',
                          cursor: 'pointer',
                          background: slowStatusFilter === lvl ? '#FFFFFF' : 'transparent',
                          color: slowStatusFilter === lvl ? '#D97706' : '#6B5E63',
                          boxShadow: slowStatusFilter === lvl ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                          transition: 'all 0.2s ease',
                          whiteSpace: 'nowrap'
                        }}
                      >
                        {lvl}
                      </button>
                    ))}
                  </div>

                  {/* Warehouse Dropdown */}
                  <select
                    value={slowWarehouseFilter}
                    onChange={(e) => setSlowWarehouseFilter(e.target.value)}
                    style={{
                      padding: '0.6rem 0.85rem',
                      fontSize: '0.85rem',
                      borderRadius: '8px',
                      border: '1px solid rgba(216, 114, 126, 0.25)',
                      backgroundColor: '#FAF7F5',
                      color: '#1F191B',
                      outline: 'none'
                    }}
                  >
                    <option value="ALL">All Warehouses ({slowWarehouses.length})</option>
                    {slowWarehouses.map((wh) => (
                      <option key={wh.warehouse_id} value={String(wh.warehouse_id)}>{wh.warehouse_name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Slow-Moving Inventory Table */}
              <div className="admin-table-wrapper">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Category</th>
                      <th>Warehouse</th>
                      <th>Current Stock</th>
                      <th>Sales Last 30 Days</th>
                      <th>Avg Daily Sales</th>
                      <th>Days of Stock</th>
                      <th>Movement Status</th>
                      <th>Recommended Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSlowItems.length > 0 ? (
                      filteredSlowItems.map((item, idx) => {
                        const badgeStyle = getStatusStyle(item.movement_status);
                        const daysDisplay = item.days_of_stock >= 999999 ? '∞' : item.days_of_stock;

                        return (
                          <tr key={`${item.product_id}-${item.warehouse_id}-${idx}`}>
                            <td>
                              <strong style={{ color: '#1F191B', fontWeight: 600 }}>{item.product_name}</strong>
                            </td>
                            <td>
                              <span style={{ color: '#6B5E63', fontSize: '0.85rem' }}>{item.category_name}</span>
                            </td>
                            <td>
                              <span style={{ color: '#6B5E63', fontSize: '0.85rem' }}>{item.warehouse_name}</span>
                            </td>
                            <td>
                              <span style={{ fontWeight: 700, color: '#1F191B' }}>{item.current_stock}</span>
                            </td>
                            <td>
                              <span style={{ fontWeight: 600, color: item.sales_last_30_days === 0 ? '#DC2626' : '#1F191B' }}>
                                {item.sales_last_30_days}
                              </span>
                            </td>
                            <td>
                              <span style={{ color: '#6B5E63' }}>{item.avg_daily_sales}</span>
                            </td>
                            <td>
                              <span style={{
                                fontWeight: 700,
                                color: daysDisplay === '∞' ? '#DC2626' : item.days_of_stock > 180 ? '#DC2626' : item.days_of_stock > 60 ? '#D97706' : '#059669'
                              }}>
                                {daysDisplay}
                              </span>
                            </td>
                            <td>
                              <span className="admin-metric-status" style={badgeStyle}>
                                {item.movement_status}
                              </span>
                            </td>
                            <td>
                              <span style={{ fontSize: '0.82rem', color: '#6B5E63', fontStyle: 'italic' }}>
                                {item.recommended_action}
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan="9" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#9E8F94' }}>
                          No inventory items found matching the selected filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem', fontSize: '0.82rem', color: '#6B5E63' }}>
                <span>Showing <strong>{filteredSlowItems.length}</strong> of {slowSummary.total_inventory || 0} inventory entries</span>
                <span>Dataset Source: <code style={{ fontSize: '0.75rem' }}>public.inventory</code> + <code style={{ fontSize: '0.75rem' }}>public.order_items</code> (Supabase)</span>
              </div>
            </>
          )}
        </>
      )}

      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          history={history}
          onClose={() => setSelectedProduct(null)}
          onChangeGranularity={changeGranularity}
        />
      )}
    </div>
  );
}

/* Sales-history bar chart drawn from real delivered-order aggregates. */
function SalesHistoryChart({ points, granularity }) {
  if (!points || points.length === 0) {
    return (
      <div style={{ padding: '2rem 1rem', textAlign: 'center', color: '#9E8F94', border: '1px dashed #F0E2E0', borderRadius: '12px' }}>
        <PackageSearch size={26} style={{ marginBottom: '0.4rem' }} />
        <p style={{ margin: 0, fontSize: '0.85rem' }}>No delivered sales recorded for this product yet.</p>
      </div>
    );
  }
  const width = 640;
  const height = 220;
  const pad = 8;
  const max = Math.max(1, ...points.map((pt) => pt.units));
  const step = (width - pad * 2) / points.length;
  const baseline = height - 24;
  const plotH = height - 40;
  const fmtTick = (period) => (granularity === 'day' ? period.slice(8, 10) : granularity === 'week' ? period.slice(5, 10) : period.slice(0, 7));
  const coords = points.map((pt, i) => ({
    x: pad + i * step + step / 2,
    y: baseline - (pt.units / max) * plotH,
    pt,
  }));
  const linePts = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
  const areaPts = `${pad},${baseline} ${linePts} ${width - pad},${baseline}`;
  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label="Units sold over time">
        {coords.length > 1 && (
          <>
            <polygon points={areaPts} fill="rgba(216, 114, 126, 0.15)" stroke="none" />
            <polyline
              points={linePts}
              fill="none"
              stroke="#D8727E"
              strokeWidth={2.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        )}
        <line x1={pad} y1={baseline} x2={width - pad} y2={baseline} stroke="#F0E2E0" />
        {coords.map((c, i) => (
          <g key={c.pt.period + i}>
            <title>{`${c.pt.period}: ${c.pt.units} units`}</title>
            <circle cx={c.x} cy={c.y} r={coords.length > 40 ? 1.5 : 3} fill="#B8505E" />
          </g>
        ))}
        {points.map((pt, i) => {
          if (points.length > 12 && i % Math.ceil(points.length / 8) !== 0) return null;
          const x = pad + i * step + step / 2;
          return (
            <text key={`t-${pt.period}-${i}`} x={x} y={height - 8} fontSize="9" fill="#9E8F94" textAnchor="middle">
              {fmtTick(pt.period)}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function ProductDetailModal({ product, history, onClose, onChangeGranularity }) {
  const fmtNum = (n) => Number(n || 0).toLocaleString('en-IN');
  const tier = product.predicted_demand || 'Medium';
  const tierBadge = tier === 'High'
    ? { backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' }
    : tier === 'Medium'
    ? { backgroundColor: '#FFFBEB', color: '#D97706', borderColor: '#FDE68A' }
    : { backgroundColor: '#FEF2F2', color: '#DC2626', borderColor: '#FCA5A5' };
  const last = history.points.length ? history.points[history.points.length - 1] : null;
  const imageUrl = product.image || '';

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 200, backgroundColor: 'rgba(31,25,27,0.55)', backdropFilter: 'blur(4px)' }} />
      <div role="dialog" aria-modal="true" aria-label="Product details" style={{ position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201, width: 'min(640px,100vw)', backgroundColor: '#FFF', boxShadow: '-8px 0 60px rgba(31,25,27,0.18)', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
        <div style={{ position: 'sticky', top: 0, zIndex: 10, backgroundColor: 'rgba(255,255,255,0.96)', backdropFilter: 'blur(10px)', borderBottom: '1px solid var(--tarika-border,#F0E2E0)', padding: '1rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>Product Details</span>
          <button onClick={onClose} aria-label="Close" style={{ width: 36, height: 36, borderRadius: '50%', border: '1px solid var(--tarika-border,#F0E2E0)', backgroundColor: '#FAF7F5', color: '#6B5E63', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><X size={18} /></button>
        </div>

        <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Hero */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.25rem', padding: '1.25rem', background: 'linear-gradient(135deg,#FAF7F5 0%,#FBF1F0 100%)', borderBottom: '1px solid var(--tarika-border,#F0E2E0)', borderRadius: '14px' }}>
            <div style={{ width: 120, height: 150, flexShrink: 0, borderRadius: 12, overflow: 'hidden', border: '1px solid rgba(216,114,126,0.15)' }}>
              {imageUrl ? (<img src={imageUrl} alt={product.product_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} />) : (<div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94' }}><Images size={26} /></div>)}
            </div>
            <div style={{ flex: '1 1 220px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem', justifyContent: 'center' }}>
              <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>{product.main_category}{product.sub_category ? ` · ${product.sub_category}` : ''}</span>
              <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#1F191B', lineHeight: 1.3 }}>{product.product_name}</h2>
              <code style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 700, color: '#1F191B', background: '#FFF', padding: '0.2rem 0.55rem', borderRadius: 6, border: '1px solid #F0E2E0', alignSelf: 'flex-start', wordBreak: 'break-all' }}>{product.product_key}</code>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: 2 }}>
                <span style={{ ...tierBadge, fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.75rem', borderRadius: '9999px', border: `1px solid ${tierBadge.borderColor}` }}>{tier} demand</span>
              </div>
            </div>
          </div>

          {/* Facts: sales demand vs stock, clearly separated */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: '0.75rem 1.5rem' }}>
            {[
              { label: 'Units sold (delivered)', value: `${fmtNum(product.units_sold)} units` },
              { label: 'Available stock', value: `${fmtNum(product.available_quantity)} units` },
              { label: 'Total sales value', value: `₹${fmtNum(Math.round(product.total_sales))}` },
              { label: 'Wishlist signals', value: `${fmtNum(product.wishlist_count)}` },
              { label: 'Cart signals', value: `${fmtNum(product.cart_count)}` },
            ].map(({ label, value }) => (
              <div key={label}>
                <p style={{ margin: '0 0 2px', fontSize: '0.7rem', fontWeight: 600, color: '#9E8F94', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</p>
                <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: '#1F191B' }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Sales history graph */}
          <div style={{ border: '1px solid #F0E2E0', borderRadius: 16, padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                <TrendingUp size={15} style={{ verticalAlign: '-2px', marginRight: 4 }} /> Sales History
              </h4>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <select value={history.granularity} onChange={(e) => onChangeGranularity(e.target.value)} style={{ padding: '0.4rem 0.6rem', borderRadius: 8, border: '1.5px solid var(--tarika-border,#F0E2E0)', fontSize: '0.78rem', backgroundColor: '#FFF', cursor: 'pointer' }}>
                  <option value="day">By day</option><option value="week">By week</option><option value="month">By month</option>
                </select>
              </div>
            </div>

            {history.loading ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#6B5E63' }}>
                <div className="tarika-auth-spinner" style={{ margin: '0 auto 0.75rem', width: '1.75rem', height: '1.75rem', borderColor: 'rgba(216,114,126,0.25)', borderTopColor: '#D8727E' }} />
                Loading real sales data…
              </div>
            ) : history.error ? (
              <div style={{ padding: '1rem', color: '#DC2626', fontSize: '0.85rem' }}>{history.error}</div>
            ) : (
              <>
                <SalesHistoryChart points={history.points} granularity={history.granularity} />
                <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem', fontSize: '0.8rem', color: '#6B5E63' }}>
                  <span>Total sold: <strong style={{ color: '#1F191B' }}>{fmtNum(history.totalUnits)} units</strong></span>
                  {last && <span>Most recent {history.granularity}: <strong style={{ color: '#1F191B' }}>{fmtNum(last.units)} units</strong> ({last.period})</span>}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
