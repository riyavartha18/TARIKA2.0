import React, { useState, useEffect, useCallback, useMemo, useRef, lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import demandForecastingVisual from '../../assets/demand_forecasting_visual.png';
import { useAuth } from '../../auth/AuthContext';
import {
  getDemandPredictionAnalytics,
  getDemandPredictionProducts,
  getDemandPredictionCategories,
  getProductSalesHistory,
} from '../../services/api';
import { getSlowMovingInventory } from '../../services/slowInventory';
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
import RfmAnalysisCard from './RfmAnalysisCard';
import ClvAnalysisCard from './ClvAnalysisCard';
import ClvDashboard from './AdminClvView';

// The full RFM dashboard is only needed when the admin actually opens it, so it
// (and its drill-down screens) is loaded on demand instead of being parsed and
// hashed before the overview is even readable.
const RfmDashboard = lazy(() => import('./AdminRFMView'));

export default function AdminAnalyticsView() {
  const { token: authContextToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  // Active view: 'overview' | 'demand_forecasting' | 'slow_inventory' | 'rfm' | 'clv'
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

  // === Inventory Velocity (Slow-Moving) State — server-driven ===
  const [slowLoading, setSlowLoading] = useState(false);
  const [slowError, setSlowError] = useState(null);
  const [slowData, setSlowData] = useState(null);
  const [slowSearchQuery, setSlowSearchQuery] = useState('');
  const [slowDebouncedSearch, setSlowDebouncedSearch] = useState('');
  const [slowStatusFilter, setSlowStatusFilter] = useState('ALL');
  const [slowCategoryFilter, setSlowCategoryFilter] = useState('ALL');
  const [slowSort, setSlowSort] = useState('movement');
  const [slowPage, setSlowPage] = useState(1);
  const slowPageSize = 50;
  // Guards against out-of-order responses when filters change quickly.
  const slowReqId = useRef(0);

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

  const fetchSlowInventoryData = useCallback(async (opts = {}) => {
    const reqId = ++slowReqId.current;
    setSlowLoading(true);
    setSlowError(null);
    try {
      const res = await getSlowMovingInventory(getActiveToken(), {
        page: opts.page ?? slowPage,
        page_size: slowPageSize,
        search: opts.search ?? slowDebouncedSearch,
        category: opts.category ?? slowCategoryFilter,
        movement_status: opts.movement_status ?? slowStatusFilter,
        sort: opts.sort ?? slowSort,
        refresh: opts.refresh ?? false,
      });
      // Ignore a stale response superseded by a newer filter change.
      if (reqId !== slowReqId.current) return;
      if (res.success) {
        setSlowData(res);
      } else {
        setSlowError(res.error || 'Failed to load inventory velocity data.');
      }
    } catch (err) {
      if (reqId !== slowReqId.current) return;
      setSlowError('An unexpected error occurred while fetching inventory velocity data.');
    } finally {
      if (reqId === slowReqId.current) setSlowLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slowPage, slowDebouncedSearch, slowCategoryFilter, slowStatusFilter, slowSort]);

  // Debounce the velocity search box (no request per keystroke).
  useEffect(() => {
    const id = setTimeout(() => setSlowDebouncedSearch(slowSearchQuery.trim()), 350);
    return () => clearTimeout(id);
  }, [slowSearchQuery]);

  // Any filter/sort change returns to the first page.
  useEffect(() => {
    setSlowPage(1);
  }, [slowDebouncedSearch, slowCategoryFilter, slowStatusFilter, slowSort]);

  // Fetch the current page whenever the paged query changes (only while open).
  useEffect(() => {
    if (activeView === 'slow_inventory') {
      fetchSlowInventoryData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView, slowPage, slowDebouncedSearch, slowCategoryFilter, slowStatusFilter, slowSort]);

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

  // Deep link used by the Admin Dashboard "View More":
  // /admin/analysis?view=demand-forecasting opens this very module instead of the
  // hub, so Demand Forecasting stays a single page with a single route. Leaving
  // it clears the parameter again so the URL keeps describing what is on screen.
  useEffect(() => {
    if (searchParams.get('view') === 'demand-forecasting') {
      handleOpenDetailView();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleBackToHub = () => {
    setActiveView('overview');
    if (searchParams.get('view')) setSearchParams({}, { replace: true });
  };

  const handleOpenSlowInventoryView = () => {
    setActiveView('slow_inventory');
    if (categoriesList.length === 0) {
      fetchCategories();
    }
  };

  // The RFM card and dashboard fetch their own lightweight cached summary, so
  // opening them is just a view switch (no eager heavy load on the overview).
  const handleOpenRfmView = () => setActiveView('rfm');

  // The CLV card and dashboard fetch their own lightweight cached state, so
  // opening them is just a view switch as well.
  const handleOpenClvView = () => setActiveView('clv');

  const { summary = {} } = data || {};

  // Demand metrics come from the cached analytics model (whole-catalog truth);
  // per-product rows come from the paged products endpoint.
  const distribution = summary.predicted_distribution || {};
  const highCount = distribution.High || 0;
  const medCount = distribution.Medium || 0;
  const lowCount = distribution.Low || 0;
  const totalCount = summary.total_products || 0;

  // === Inventory Velocity rows (already filtered/paged server-side) ===
  const slowItems = useMemo(() => slowData?.items || [], [slowData]);
  const slowSummary = slowData?.summary || {};
  const slowPagination = slowData?.pagination || {};

  // Movement status badge style helper — 4 sales-quantity tiers
  const getStatusStyle = (status) => {
    switch (status) {
      case 'FAST MOVING':
        return { backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' };
      case 'NORMAL MOVING':
        return { backgroundColor: '#EFF6FF', color: '#2563EB', borderColor: '#BFDBFE' };
      case 'SLOW MOVING':
        return { backgroundColor: '#FFFBEB', color: '#D97706', borderColor: '#FDE68A' };
      case 'NOT MOVING':
        return { backgroundColor: '#FEF2F2', color: '#DC2626', borderColor: '#FCA5A5' };
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
                    Inventory Velocity
                  </h2>
                  <span style={{ fontSize: '0.75rem', color: '#9E8F94', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    FEATURE #2 &bull; MOVEMENT ANALYSIS
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

            {/* Visual Banner — 4 movement tiers */}
            <div style={{
              marginBottom: '2rem',
              borderRadius: '14px',
              overflow: 'hidden',
              background: 'linear-gradient(135deg, #ECFDF5 0%, #EFF6FF 35%, #FFFBEB 65%, #FEF2F2 100%)',
              border: '1px solid rgba(0, 0, 0, 0.06)',
              padding: '1.75rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '1.5rem',
              flexWrap: 'wrap'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Flame size={24} style={{ color: '#059669' }} />
                <div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#059669' }}>Fast Moving</div>
                  <div style={{ fontSize: '0.76rem', color: '#065F46' }}>Highest sales</div>
                </div>
              </div>
              <div style={{ width: '1px', height: '34px', background: 'rgba(0,0,0,0.1)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Box size={24} style={{ color: '#2563EB' }} />
                <div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#2563EB' }}>Normal Moving</div>
                  <div style={{ fontSize: '0.76rem', color: '#1E40AF' }}>Moderate sales</div>
                </div>
              </div>
              <div style={{ width: '1px', height: '34px', background: 'rgba(0,0,0,0.1)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <TrendingDown size={24} style={{ color: '#D97706' }} />
                <div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#D97706' }}>Slow Moving</div>
                  <div style={{ fontSize: '0.76rem', color: '#92400E' }}>Low sales</div>
                </div>
              </div>
              <div style={{ width: '1px', height: '34px', background: 'rgba(0,0,0,0.1)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Archive size={24} style={{ color: '#DC2626' }} />
                <div>
                  <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#DC2626' }}>Not Moving</div>
                  <div style={{ fontSize: '0.76rem', color: '#991B1B' }}>Zero sales (30d)</div>
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

          {/* ================================================================
              RFM CUSTOMER SEGMENTATION CARD
             ================================================================ */}
          <RfmAnalysisCard onOpen={handleOpenRfmView} />

          {/* ================================================================
              CUSTOMER LIFETIME VALUE CARD
             ================================================================ */}
          <ClvAnalysisCard onOpen={handleOpenClvView} />

          </div>
        </div>
      )}

      {/* ==========================================================================
          DEDICATED DETAILED VIEW: RFM CUSTOMER SEGMENTATION DASHBOARD
         ========================================================================== */}
      {activeView === 'rfm' && (
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <Suspense fallback={(
            <div style={{ padding: '3rem', textAlign: 'center', color: '#6B5E63' }}>
              Loading the RFM dashboard…
            </div>
          )}>
            <RfmDashboard onBack={() => setActiveView('overview')} />
          </Suspense>
        </div>
      )}

      {/* ==========================================================================
          DEDICATED DETAILED VIEW: CUSTOMER LIFETIME VALUE DASHBOARD
         ========================================================================== */}
      {activeView === 'clv' && (
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <ClvDashboard onBack={() => setActiveView('overview')} />
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
                onClick={handleBackToHub}
                className="tarika-btn-outline"
                style={{ padding: '0.55rem 1.1rem', fontSize: '0.82rem' }}
              >
                <ArrowLeft size={16} />
                <span>Back to Analytics Hub</span>
              </button>
              <div>
                <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: 0 }}>
                  Demand Forecasting Results
                </h1>
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
                Processing historical demand data…
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
                              <span className="df-chip" title="Total Revenue"><IndianRupee size={12} /> Total Revenue {fmtNum(Math.round(p.total_sales))}</span>
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

              <div style={{ marginTop: '1.25rem', fontSize: '0.82rem', color: '#6B5E63' }}>
                <span>Showing <strong>{productItems.length}</strong> of {productPagination.total_filtered?.toLocaleString('en-IN') ?? totalCount.toLocaleString('en-IN')} products</span>
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
                onClick={handleBackToHub}
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
                  Product movement classification from actual sales quantity in the last 30 days.
                </p>
              </div>
            </div>

            <button
              onClick={() => fetchSlowInventoryData({ refresh: true, page: 1 })}
              className="tarika-btn-outline"
              style={{ padding: '0.55rem 1.1rem', fontSize: '0.82rem' }}
              disabled={slowLoading}
            >
              <RefreshCw size={14} className={slowLoading ? 'animate-spin' : ''} />
              <span>Refresh Analysis</span>
            </button>
          </div>

          {/* Loading State (first load only — later pages keep the table visible) */}
          {slowLoading && !slowData && (
            <div style={{ padding: '4rem 1rem', textAlign: 'center' }}>
              <RefreshCw size={36} className="animate-spin" style={{ color: '#D97706', marginBottom: '1rem' }} />
              <h3 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", color: '#1F191B', margin: '0 0 0.5rem 0' }}>
                Analyzing Inventory Velocity...
              </h3>
              <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: 0 }}>
                Aggregating sales and stock for every catalog product on the database...
              </p>
            </div>
          )}

          {/* Data Loaded */}
          {!slowLoading && slowError && (
            <div style={{ background: '#FEF2F2', border: '1px solid #FCA5A5', padding: '1.5rem', borderRadius: '12px', color: '#991B1B', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
                <AlertCircle size={20} color="#DC2626" />
                <strong style={{ fontSize: '1.05rem' }}>Slow-Moving Inventory Engine Notice</strong>
              </div>
              <p style={{ margin: '0 0 1rem 0', fontSize: '0.92rem' }}>{slowError}</p>
              <button className="tarika-btn-outline" onClick={() => fetchSlowInventoryData({ refresh: true })}>
                <RefreshCw size={14} /> Retry
              </button>
            </div>
          )}

          {/* Data Loaded */}
          {slowData && !slowError && (
            <>
              {/* Summary Metrics Grid — 5 tiles for 4 tiers */}
              <div className="admin-metrics-grid" style={{ marginBottom: '1.5rem' }}>
                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title">Total Products</p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem' }}>{(slowSummary.total_products || 0).toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Analyzed from catalog</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#059669' }}>
                    <Flame size={13} style={{ verticalAlign: '-2px' }} /> Fast Moving
                  </p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#059669' }}>{(slowSummary.fast_moving || 0).toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Highest sales ({'> '}{Math.round(slowData?.thresholds?.fast_cut ?? 0)} units/30d)</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#2563EB' }}>
                    <Activity size={13} style={{ verticalAlign: '-2px' }} /> Normal Moving
                  </p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#2563EB' }}>{(slowSummary.normal_moving || 0).toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Moderate sales ({'> '}{Math.round(slowData?.thresholds?.normal_cut ?? 0)} units/30d)</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#D97706' }}>
                    <TrendingDown size={13} style={{ verticalAlign: '-2px' }} /> Slow Moving
                  </p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#D97706' }}>{(slowSummary.slow_moving || 0).toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Low but positive sales</p>
                </div>

                <div className="admin-metric-card" style={{ padding: '1.1rem 1.25rem' }}>
                  <p className="admin-metric-title" style={{ color: '#DC2626' }}>
                    <AlertTriangle size={13} style={{ verticalAlign: '-2px' }} /> Not Moving
                  </p>
                  <p className="admin-metric-val" style={{ fontSize: '1.5rem', color: '#DC2626' }}>{(slowSummary.not_moving || 0).toLocaleString('en-IN')}</p>
                  <p className="admin-metric-subtext">Zero sales in last 30 days</p>
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

                  {/* Movement Status Filter Pills — 4 tiers */}
                  <div style={{ display: 'flex', gap: '0.35rem', background: '#FAF7F5', padding: '0.25rem', borderRadius: '8px', border: '1px solid rgba(216, 114, 126, 0.2)', flexWrap: 'wrap' }}>
                    {['ALL', 'FAST MOVING', 'NORMAL MOVING', 'SLOW MOVING', 'NOT MOVING'].map((lvl) => {
                      const activeColors = {
                        'ALL':           { color: '#B8505E', bg: '#FFFFFF' },
                        'FAST MOVING':   { color: '#059669', bg: '#FFFFFF' },
                        'NORMAL MOVING': { color: '#2563EB', bg: '#FFFFFF' },
                        'SLOW MOVING':   { color: '#D97706', bg: '#FFFFFF' },
                        'NOT MOVING':    { color: '#DC2626', bg: '#FFFFFF' },
                      };
                      const ac = activeColors[lvl];
                      const isActive = slowStatusFilter === lvl;
                      return (
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
                            background: isActive ? ac.bg : 'transparent',
                            color: isActive ? ac.color : '#6B5E63',
                            boxShadow: isActive ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                            transition: 'all 0.2s ease',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          {lvl === 'ALL' ? 'All' : lvl}
                        </button>
                      );
                    })}
                  </div>

                  {/* Category Dropdown (server-side filter) */}
                  <select
                    value={slowCategoryFilter}
                    onChange={(e) => setSlowCategoryFilter(e.target.value)}
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
                    <option value="ALL">All Categories</option>
                    {categoriesList.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>

                  {/* Sort Dropdown (server-side ordering) */}
                  <select
                    value={slowSort}
                    onChange={(e) => setSlowSort(e.target.value)}
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
                    <option value="movement">Sort: Movement (Fast → Not)</option>
                    <option value="sales_last_30_days">Sort: Sales Last 30 Days</option>
                    <option value="current_stock">Sort: Current Stock</option>
                    <option value="product_name">Sort: Product Name</option>
                  </select>
                </div>
              </div>

              {/* Inventory Velocity Table — redesigned with 4-tier status badges */}
              <div className="admin-table-wrapper" style={{ position: 'relative', opacity: slowLoading ? 0.6 : 1, transition: 'opacity 0.15s ease' }}>
                {slowLoading && (
                  <div style={{ position: 'absolute', top: '0.6rem', right: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#D97706', fontSize: '0.78rem', zIndex: 2 }}>
                    <RefreshCw size={13} className="animate-spin" /> Updating…
                  </div>
                )}
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Category</th>
                      <th>Current Stock</th>
                      <th>Sales Last 30 Days</th>
                      <th>Movement Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slowItems.length > 0 ? (
                      slowItems.map((item, idx) => {
                        const badgeStyle = getStatusStyle(item.movement_status);

                        return (
                          <tr key={`${item.product_key}-${idx}`}>
                            <td>
                              <strong style={{ color: '#1F191B', fontWeight: 600 }}>{item.product_name}</strong>
                            </td>
                            <td>
                              <span style={{ color: '#6B5E63', fontSize: '0.85rem' }}>
                                {item.category_name}{item.sub_category ? ` · ${item.sub_category}` : ''}
                              </span>
                            </td>
                            <td>
                              <span style={{ fontWeight: 700, color: '#1F191B' }}>
                                {(item.current_stock ?? 0).toLocaleString('en-IN')}
                              </span>
                            </td>
                            <td>
                              <span style={{ fontWeight: 600, color: (item.sales_last_30_days ?? 0) === 0 ? '#DC2626' : '#1F191B' }}>
                                {(item.sales_last_30_days ?? 0).toLocaleString('en-IN')}
                              </span>
                            </td>
                            <td>
                              <span style={{
                                ...badgeStyle,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                padding: '0.3rem 0.8rem',
                                borderRadius: '9999px',
                                border: `1px solid ${badgeStyle.borderColor}`,
                                fontSize: '0.78rem',
                                fontWeight: 700,
                                letterSpacing: '0.02em',
                                whiteSpace: 'nowrap',
                              }}>
                                <span style={{
                                  width: '7px', height: '7px', borderRadius: '50%',
                                  backgroundColor: badgeStyle.color, flexShrink: 0
                                }} />
                                {item.movement_status}
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      !slowLoading && (
                        <tr>
                          <td colSpan="5" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#9E8F94' }}>
                            No inventory items found matching the selected filters.
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination — database-side paging over the full catalog */}
              {(slowPagination.total_pages || 0) > 1 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>
                    Page <strong>{slowPagination.page}</strong> of {slowPagination.total_pages}
                    {' '}· {slowPagination.total_filtered?.toLocaleString('en-IN')} matching products
                  </span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="tarika-btn-outline"
                      style={{ padding: '0.5rem 0.9rem', fontSize: '0.8rem', opacity: slowPagination.page <= 1 ? 0.5 : 1 }}
                      disabled={slowPagination.page <= 1 || slowLoading}
                      onClick={() => setSlowPage((pg) => Math.max(1, pg - 1))}
                    >
                      <ChevronLeft size={15} /> Prev
                    </button>
                    <button
                      className="tarika-btn-outline"
                      style={{ padding: '0.5rem 0.9rem', fontSize: '0.8rem', opacity: slowPagination.page >= slowPagination.total_pages ? 0.5 : 1 }}
                      disabled={slowPagination.page >= slowPagination.total_pages || slowLoading}
                      onClick={() => setSlowPage((pg) => pg + 1)}
                    >
                      Next <ChevronRight size={15} />
                    </button>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.25rem', fontSize: '0.82rem', color: '#6B5E63', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span>Showing <strong>{slowItems.length}</strong> of {(slowPagination.total_filtered ?? slowSummary.total_products ?? 0).toLocaleString('en-IN')} analyzed products</span>
                <span>Data: <code style={{ fontSize: '0.75rem' }}>public.products</code> + <code style={{ fontSize: '0.75rem' }}>public.orders</code> (Neon PostgreSQL)</span>
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
