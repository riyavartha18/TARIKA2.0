import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  ArrowLeft,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Calendar,
  IndianRupee,
  Layers,
  BarChart3,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronRight,
  ChevronLeft,
  Filter,
  Eye,
  EyeOff,
  ShoppingBag,
  Package,
  Scissors,
  Grid,
  Award,
  Search,
  ArrowUpDown,
  FileText,
} from 'lucide-react';
import { getRevenueOLAP } from '../../services/api';
import { useAuth } from '../../auth/AuthContext';

/**
 * Currency & Number formatters for Indian Rupees in Crores / Lakhs / Exact.
 */
function formatCrores(amount) {
  if (amount == null || isNaN(amount)) return '₹0';
  const cr = amount / 10000000;
  return `₹${cr.toFixed(2)} Cr`;
}

function formatLakhs(amount) {
  if (amount == null || isNaN(amount)) return '₹0';
  const lk = amount / 100000;
  return `₹${lk.toFixed(2)} L`;
}

function formatExactINR(amount) {
  if (amount == null || isNaN(amount)) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatExactRevenue(amount) {
  if (amount == null || isNaN(amount)) return '—';
  return `₹${Number(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatExactCount(count) {
  if (count == null || isNaN(count)) return '—';
  return Number(count).toLocaleString('en-US');
}

function formatExactAOV(amount) {
  if (amount == null || isNaN(amount)) return '—';
  return `₹${Number(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPercent(val) {
  if (val == null || isNaN(val)) return '—';
  const sign = val > 0 ? '+' : '';
  return `${sign}${Number(val).toFixed(2)}%`;
}

const MONTH_SHORT = {
  1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
  7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
};

export default function RevenueOLAPDashboard({ onBack }) {
  const auth = useAuth?.() || {};
  const contextToken = auth.token;

  // Active operation tab: 'rollup' | 'drilldown' | 'slice' | 'dice' | 'pivot' | 'ranking' | 'drillthrough' | 'trend'
  const [activeTab, setActiveTab] = useState('rollup');

  // Operation 1: Roll-up state
  const [rollupLevel, setRollupLevel] = useState('quarter'); // 'month' | 'quarter' | 'year'
  const [showRollupGraph, setShowRollupGraph] = useState(true);

  // Operation 2: Drill-down state
  const [drilldownLevel, setDrilldownLevel] = useState('quarter'); // 'year' | 'quarter' | 'month'
  const [selectedYear, setSelectedYear] = useState('2025');
  const [selectedQuarter, setSelectedQuarter] = useState('ALL');
  const [showDrilldownGraph, setShowDrilldownGraph] = useState(true);

  // Operation 3: Slice state
  const [sliceType, setSliceType] = useState('year'); // 'year' | 'quarter'
  const [sliceValue, setSliceValue] = useState('2025');
  const [showSliceGraph, setShowSliceGraph] = useState(true);

  // Operation 4: Dice state
  const [diceYears, setDiceYears] = useState(['2024', '2025', '2026']);
  const [diceMonths, setDiceMonths] = useState([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  const [showDiceGraph, setShowDiceGraph] = useState(true);

  // Operation 5: Pivot state
  const [showPivotGraph, setShowPivotGraph] = useState(true);

  // Operation 6: Ranking state
  const [rankingGranularity, setRankingGranularity] = useState('month'); // 'month' | 'quarter' | 'year'
  const [rankingSortOrder, setRankingSortOrder] = useState('desc'); // 'desc' | 'asc'
  const [showRankingGraph, setShowRankingGraph] = useState(true);

  // Operation 7: Drill-Through state
  const [dtPeriodType, setDtPeriodType] = useState('month'); // 'month' | 'quarter' | 'year' | 'all'
  const [dtPeriodKey, setDtPeriodKey] = useState('2024-03');
  const [dtPage, setDtPage] = useState(1);
  const [dtPageSize, setDtPageSize] = useState(50);

  // Operation 8: Trend Analysis state
  const [showTrendGraph, setShowTrendGraph] = useState(true);
  const [excludeInceptionArtifactInGraph, setExcludeInceptionArtifactInGraph] = useState(true);

  // Shared fetching & UI state
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);

  // Request tracking ref to prevent race conditions / outdated responses overwriting newer state
  const requestIdRef = useRef(0);

  const loadOLAP = useCallback(async (force = false) => {
    const currentRequestId = ++requestIdRef.current;
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const params = {
        operation: activeTab,
        forceRefresh: force,
      };

      if (activeTab === 'rollup') {
        params.level = rollupLevel;
      } else if (activeTab === 'drilldown') {
        params.level = drilldownLevel;
        params.year = selectedYear;
        params.quarter = (drilldownLevel === 'month' && selectedQuarter !== 'ALL') ? selectedQuarter : null;
      } else if (activeTab === 'slice') {
        params.sliceType = sliceType;
        params.sliceValue = sliceValue;
      } else if (activeTab === 'dice') {
        params.years = diceYears;
        params.months = diceMonths;
      } else if (activeTab === 'pivot') {
        // default pivot has no extra params
      } else if (activeTab === 'ranking') {
        params.granularity = rankingGranularity;
        params.sortOrder = rankingSortOrder;
      } else if (activeTab === 'drillthrough') {
        params.periodType = dtPeriodType;
        params.periodKey = dtPeriodType === 'all' ? null : dtPeriodKey;
        params.page = dtPage;
        params.pageSize = dtPageSize;
      } else if (activeTab === 'trend') {
        // trend uses default params
      }

      const res = await getRevenueOLAP(params, contextToken);

      // Prevent outdated API responses from overwriting newer filter/tab results
      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      if (res.success) {
        setData(res);
      } else {
        setError(res.error || 'Failed to load Revenue OLAP analysis.');
      }
    } catch (err) {
      if (currentRequestId === requestIdRef.current) {
        setError(err?.message || 'Failed to load Revenue OLAP analysis.');
      }
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [
    activeTab,
    rollupLevel,
    drilldownLevel,
    selectedYear,
    selectedQuarter,
    sliceType,
    sliceValue,
    diceYears,
    diceMonths,
    rankingGranularity,
    rankingSortOrder,
    dtPeriodType,
    dtPeriodKey,
    dtPage,
    dtPageSize,
    contextToken,
  ]);

  useEffect(() => {
    loadOLAP(false);
  }, [loadOLAP]);

  // Handle Inspect Orders action from ANY row across the dashboard
  const handleInspectOrders = (pType, pKey) => {
    setDtPeriodType(pType || 'month');
    setDtPeriodKey(pKey || 'ALL');
    setDtPage(1);
    setActiveTab('drillthrough');
  };

  const records = data?.records || [];
  const reconciliation = data?.data_reconciliation;
  const allTiers = data?.all_tiers_summary;
  const dataQuality = data?.data_quality_report;
  const notices = data?.notices;
  const availableFilters = data?.available_filters;

  // Top-tier reconciliation summary metrics from live API response (no hardcoded fallback)
  const summaryRevenue = reconciliation?.monthly_total_revenue ?? null;
  const summaryOrders = reconciliation?.total_delivered_orders ?? null;
  const summaryAOV = reconciliation?.overall_aov ?? null;

  // Chart max value calculation for standard bar charts
  const chartMetrics = useMemo(() => {
    if (!records || records.length === 0) return { maxRevenue: 1, minRevenue: 0 };
    const maxRev = Math.max(...records.map((r) => r.total_revenue || r.actual_revenue || 0));
    const minRev = Math.min(...records.map((r) => r.total_revenue || r.actual_revenue || 0));
    return {
      maxRevenue: maxRev > 0 ? maxRev * 1.15 : 100,
      minRevenue: Math.max(0, minRev),
    };
  }, [records]);

  // Toggle year selection in Dice
  const handleToggleDiceYear = (y) => {
    setDiceYears((prev) => {
      if (prev.includes(y)) return prev.filter((item) => item !== y);
      return [...prev, y].sort();
    });
  };

  // Toggle month selection in Dice
  const handleToggleDiceMonth = (m) => {
    setDiceMonths((prev) => {
      if (prev.includes(m)) return prev.filter((item) => item !== m);
      return [...prev, m].sort((a, b) => a - b);
    });
  };

  return (
    <div className="tarika-page-container" style={{ padding: '1.75rem 2rem', maxWidth: '1440px', margin: '0 auto' }}>
      {/* 1. Header & Navigation Back */}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <button
            onClick={onBack}
            className="tarika-btn-outline"
            style={{
              padding: '0.45rem 0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
            title="Return to Revenue Forecasting Dashboard"
          >
            <ArrowLeft size={15} />
            <span>Back to Forecasting</span>
          </button>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#1F191B', margin: 0, letterSpacing: '-0.02em' }}>
              Revenue OLAP Analysis (Time Dimension)
            </h1>
            <p style={{ fontSize: '0.82rem', color: '#6B5E63', margin: '2px 0 0' }}>
              Academic DWM Practical &bull; Multidimensional Retail Analytics along the Time Dimension &bull; 8 Verified Operations
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => loadOLAP(true)}
            disabled={refreshing || loading}
            className="tarika-btn-outline"
            style={{
              padding: '0.45rem 0.95rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              cursor: refreshing || loading ? 'not-allowed' : 'pointer',
            }}
            title="Refetch actual database records and recompute OLAP aggregations"
          >
            <RefreshCw size={14} className={refreshing ? 'tarika-spin' : ''} />
            <span>{refreshing ? 'Refreshing…' : 'Refresh OLAP'}</span>
          </button>
        </div>
      </div>

      {/* 2. Analytical Notices & Exact Three-Tier Reconciliation Banner */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        {/* Exact Reconciliation Banner */}
        <div
          style={{
            padding: '1rem 1.25rem',
            borderRadius: '14px',
            backgroundColor: '#FAF7F5',
            border: '1px solid rgba(216, 114, 126, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                backgroundColor: '#FDF2F4',
                color: '#B8505E',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Layers size={18} />
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1F191B' }}>
                Three-Tier Time Reconciliation Formula:
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6B5E63', marginTop: '1px' }}>
                {reconciliation?.reconciliation_formula || (
                  loading ? (
                    <span style={{ color: '#9CA3AF' }}>Loading live reconciliation metrics…</span>
                  ) : error ? (
                    <span style={{ color: '#DC2626' }}>Reconciliation formula unavailable due to API error</span>
                  ) : (
                    'Monthly Total = Quarterly Total = Yearly Total'
                  )
                )}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.8rem', color: '#6B5E63', flexWrap: 'wrap' }}>
            <div>
              Total Realised Revenue:{' '}
              {loading && !data ? (
                <span style={{ color: '#9CA3AF' }}>Loading…</span>
              ) : error && !data ? (
                <span style={{ color: '#DC2626' }}>Unavailable</span>
              ) : summaryRevenue != null ? (
                <strong style={{ color: '#B8505E' }}>{formatExactRevenue(summaryRevenue)}</strong>
              ) : (
                <span style={{ color: '#9CA3AF' }}>Unavailable</span>
              )}
            </div>
            <div>
              Delivered Orders:{' '}
              {loading && !data ? (
                <span style={{ color: '#9CA3AF' }}>Loading…</span>
              ) : error && !data ? (
                <span style={{ color: '#DC2626' }}>Unavailable</span>
              ) : summaryOrders != null ? (
                <strong style={{ color: '#1F191B' }}>{formatExactCount(summaryOrders)}</strong>
              ) : (
                <span style={{ color: '#9CA3AF' }}>Unavailable</span>
              )}
            </div>
            <div>
              Overall AOV:{' '}
              {loading && !data ? (
                <span style={{ color: '#9CA3AF' }}>Loading…</span>
              ) : error && !data ? (
                <span style={{ color: '#DC2626' }}>Unavailable</span>
              ) : summaryAOV != null ? (
                <strong style={{ color: '#059669' }}>{formatExactAOV(summaryAOV)}</strong>
              ) : (
                <span style={{ color: '#9CA3AF' }}>Unavailable</span>
              )}
            </div>
          </div>
        </div>

        {/* Partial Year Non-Comparability Notice */}
        <div
          style={{
            padding: '0.85rem 1.25rem',
            borderRadius: '12px',
            backgroundColor: '#FFFBEB',
            border: '1px solid #FDE68A',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            fontSize: '0.82rem',
            color: '#92400E',
            lineHeight: 1.45,
          }}
        >
          <AlertTriangle size={18} style={{ color: '#D97706', flexShrink: 0 }} />
          <div>
            <strong>Analytical Notice (Partial Calendar Periods):</strong> Year 2024 (9 Months + 1 Day, March 31 to Dec 31) and Year 2026 (3 Months, Jan 1 to Mar 31) are partial-year records and must <em>not</em> be compared directly against Year 2025 (Full 12 Months) as full annual performance. March 2024 represents a single recorded day (March 31, 2024; 841 orders, ₹61.26 L).
          </div>
        </div>
      </div>

      {/* 3. Navigation Bar: 8 Clearly Named OLAP Operation Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '2px solid rgba(216, 114, 126, 0.15)',
          marginBottom: '1.75rem',
          overflowX: 'auto',
          paddingBottom: '2px',
        }}
      >
        {[
          { id: 'rollup', label: '1. Roll-up', icon: TrendingUp, color: '#B8505E' },
          { id: 'drilldown', label: '2. Drill-down', icon: Layers, color: '#4F46E5' },
          { id: 'slice', label: '3. Slice', icon: Scissors, color: '#0891B2' },
          { id: 'dice', label: '4. Dice', icon: Filter, color: '#D97706' },
          { id: 'pivot', label: '5. Pivot', icon: Grid, color: '#7C3AED' },
          { id: 'ranking', label: '6. Ranking', icon: Award, color: '#059669' },
          { id: 'drillthrough', label: '7. Drill-Through', icon: Search, color: '#DC2626' },
          { id: 'trend', label: '8. Trend Analysis', icon: BarChart3, color: '#2563EB' },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '0.65rem 1.1rem',
                fontSize: '0.88rem',
                fontWeight: 700,
                border: 'none',
                borderBottom: isActive ? `3px solid ${tab.color}` : '3px solid transparent',
                backgroundColor: isActive ? 'rgba(216, 114, 126, 0.06)' : 'transparent',
                color: isActive ? tab.color : '#6B5E63',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
                borderRadius: '8px 8px 0 0',
              }}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Loading Skeleton */}
      {loading && (
        <div style={{ padding: '3rem', textAlign: 'center', color: '#9E8F94' }}>
          <RefreshCw size={32} className="tarika-spin" style={{ margin: '0 auto 1rem', display: 'block', color: '#B8505E' }} />
          <p style={{ fontSize: '0.95rem', margin: 0 }}>Executing Time Dimension OLAP Aggregation…</p>
        </div>
      )}

      {/* Error View */}
      {error && !loading && (
        <div
          style={{
            padding: '1.5rem',
            borderRadius: '12px',
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            color: '#B91C1C',
            marginBottom: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontWeight: 700 }}>
            <AlertTriangle size={18} />
            <span>Failed to Execute OLAP Aggregation</span>
          </div>
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.85rem' }}>{error}</p>
        </div>
      )}

      {/* Loaded Views */}
      {!loading && !error && data && (
        <div>
          {/* ================================================================= */}
          {/* TAB 1: ROLL-UP                                                    */}
          {/* ================================================================= */}
          {activeTab === 'rollup' && (
            <div>
              {/* Roll-up Controls */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  marginBottom: '1.25rem',
                  padding: '1rem 1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '12px',
                  border: '1px solid #E5E7EB',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                    Roll-up Hierarchy Level
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    Aggregate delivered revenue upward from Month (Level 1) &rarr; Quarter (Level 2) &rarr; Year (Level 3)
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', backgroundColor: '#F3F4F6', padding: '3px', borderRadius: '10px' }}>
                    {[
                      { id: 'month', label: 'Monthly Base (25M)' },
                      { id: 'quarter', label: 'Roll-up to Quarters (9Q)' },
                      { id: 'year', label: 'Roll-up to Years (3Y)' },
                    ].map((lvl) => (
                      <button
                        key={lvl.id}
                        onClick={() => setRollupLevel(lvl.id)}
                        style={{
                          padding: '0.4rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          border: 'none',
                          backgroundColor: rollupLevel === lvl.id ? '#B8505E' : 'transparent',
                          color: rollupLevel === lvl.id ? '#FFFFFF' : '#6B5E63',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {lvl.label}
                      </button>
                    ))}
                  </div>

                  <button
                    onClick={() => setShowRollupGraph((prev) => !prev)}
                    className="tarika-btn-outline"
                    style={{
                      padding: '0.45rem 0.95rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      backgroundColor: showRollupGraph ? '#FAF7F5' : '#FFFFFF',
                    }}
                  >
                    {showRollupGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                    <span>{showRollupGraph ? 'Hide Graph' : 'View Graph'}</span>
                  </button>
                </div>
              </div>

              {/* Roll-up Graph */}
              {showRollupGraph && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#FAF7F5', border: '1px solid rgba(216, 114, 126, 0.18)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={16} style={{ color: '#B8505E' }} />
                      <span>{data.chart_config?.chart_title || 'Roll-up Revenue Aggregation'}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                      Values in Crores (₹ Cr) &bull; Hover columns to inspect exact values
                    </div>
                  </div>

                  <InteractiveOLAPBarChart
                    records={records}
                    metrics={chartMetrics}
                    hoveredPoint={hoveredPoint}
                    onHover={setHoveredPoint}
                    themeColor="#B8505E"
                  />
                </div>
              )}

              {/* Roll-up Data Table */}
              <OLAPDataTable
                records={records}
                level={rollupLevel}
                themeColor="#B8505E"
                onInspectOrders={handleInspectOrders}
              />
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 2: DRILL-DOWN                                                 */}
          {/* ================================================================= */}
          {activeTab === 'drilldown' && (
            <div>
              {/* Drill-down Controls */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  marginBottom: '1.25rem',
                  padding: '1rem 1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '12px',
                  border: '1px solid #E5E7EB',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                    Drill-down Navigation Hierarchy
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    Navigate downward from Year (Top Level) &rarr; Quarter &rarr; Month for granular sales analysis
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {/* Select Level */}
                  <div style={{ display: 'flex', backgroundColor: '#F3F4F6', padding: '3px', borderRadius: '10px' }}>
                    {[
                      { id: 'year', label: '1. Year Level' },
                      { id: 'quarter', label: '2. Quarters Level' },
                      { id: 'month', label: '3. Months Level' },
                    ].map((lvl) => (
                      <button
                        key={lvl.id}
                        onClick={() => setDrilldownLevel(lvl.id)}
                        style={{
                          padding: '0.4rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          border: 'none',
                          backgroundColor: drilldownLevel === lvl.id ? '#4F46E5' : 'transparent',
                          color: drilldownLevel === lvl.id ? '#FFFFFF' : '#6B5E63',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {lvl.label}
                      </button>
                    ))}
                  </div>

                  {/* Year Selector */}
                  {drilldownLevel !== 'year' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}>
                      <span style={{ fontWeight: 600, color: '#374151' }}>Year:</span>
                      <select
                        value={selectedYear}
                        onChange={(e) => setSelectedYear(e.target.value)}
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: '8px',
                          border: '1px solid #D1D5DB',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                          backgroundColor: '#FFFFFF',
                          color: '#1F2937',
                        }}
                      >
                        {(availableFilters?.years || ['2024', '2025', '2026']).map((y) => (
                          <option key={y} value={y}>
                            {y} {y === '2025' ? '(Full Year)' : '(Partial)'}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Quarter Selector (only when Month level selected) */}
                  {drilldownLevel === 'month' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}>
                      <span style={{ fontWeight: 600, color: '#374151' }}>Quarter:</span>
                      <select
                        value={selectedQuarter}
                        onChange={(e) => setSelectedQuarter(e.target.value)}
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: '8px',
                          border: '1px solid #D1D5DB',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                          backgroundColor: '#FFFFFF',
                          color: '#1F2937',
                        }}
                      >
                        <option value="ALL">All Quarters</option>
                        {(availableFilters?.quarters_by_year?.[selectedYear] || ['Q1', 'Q2', 'Q3', 'Q4']).map((q) => (
                          <option key={q} value={q}>
                            {selectedYear} {q}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Toggle Graph */}
                  <button
                    onClick={() => setShowDrilldownGraph((prev) => !prev)}
                    className="tarika-btn-outline"
                    style={{
                      padding: '0.45rem 0.95rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      backgroundColor: showDrilldownGraph ? '#EEF2FF' : '#FFFFFF',
                    }}
                  >
                    {showDrilldownGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                    <span>{showDrilldownGraph ? 'Hide Graph' : 'View Graph'}</span>
                  </button>
                </div>
              </div>

              {/* Drill-down Graph */}
              {showDrilldownGraph && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#F5F3FF', border: '1px solid rgba(79, 70, 229, 0.18)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={16} style={{ color: '#4F46E5' }} />
                      <span>{data.chart_config?.chart_title || 'Drill-down Revenue Chart'}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                      Hover columns to inspect exact values &bull; Currency in Crores (₹ Cr)
                    </div>
                  </div>

                  <InteractiveOLAPBarChart
                    records={records}
                    metrics={chartMetrics}
                    hoveredPoint={hoveredPoint}
                    onHover={setHoveredPoint}
                    themeColor="#4F46E5"
                  />
                </div>
              )}

              {/* Drill-down Data Table */}
              <OLAPDataTable
                records={records}
                level={drilldownLevel}
                themeColor="#4F46E5"
                onInspectOrders={handleInspectOrders}
              />
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 3: SLICE                                                      */}
          {/* ================================================================= */}
          {activeTab === 'slice' && (
            <div>
              {/* Slice Controls */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  marginBottom: '1.25rem',
                  padding: '1rem 1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '12px',
                  border: '1px solid #E5E7EB',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                    OLAP Slice: Dimensional Coordinate Filter
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    Fix exactly ONE time coordinate (Year or Quarter) to project its constituent sales breakdown
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {/* Slice Type */}
                  <div style={{ display: 'flex', backgroundColor: '#F3F4F6', padding: '3px', borderRadius: '10px' }}>
                    <button
                      onClick={() => {
                        setSliceType('year');
                        setSliceValue('2025');
                      }}
                      style={{
                        padding: '0.4rem 0.85rem',
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        borderRadius: '8px',
                        border: 'none',
                        backgroundColor: sliceType === 'year' ? '#0891B2' : 'transparent',
                        color: sliceType === 'year' ? '#FFFFFF' : '#6B5E63',
                        cursor: 'pointer',
                      }}
                    >
                      Slice by Year
                    </button>
                    <button
                      onClick={() => {
                        setSliceType('quarter');
                        setSliceValue('2025-Q1');
                      }}
                      style={{
                        padding: '0.4rem 0.85rem',
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        borderRadius: '8px',
                        border: 'none',
                        backgroundColor: sliceType === 'quarter' ? '#0891B2' : 'transparent',
                        color: sliceType === 'quarter' ? '#FFFFFF' : '#6B5E63',
                        cursor: 'pointer',
                      }}
                    >
                      Slice by Quarter
                    </button>
                  </div>

                  {/* Slice Value Picker */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}>
                    <span style={{ fontWeight: 600, color: '#374151' }}>Coordinate:</span>
                    <select
                      value={sliceValue}
                      onChange={(e) => setSliceValue(e.target.value)}
                      style={{
                        padding: '0.35rem 0.65rem',
                        borderRadius: '8px',
                        border: '1px solid #D1D5DB',
                        fontSize: '0.8rem',
                        fontWeight: 700,
                        backgroundColor: '#FFFFFF',
                        color: '#1F2937',
                      }}
                    >
                      {sliceType === 'year' ? (
                        <>
                          <option value="2024">Calendar Year 2024 (Partial)</option>
                          <option value="2025">Calendar Year 2025 (Complete Year)</option>
                          <option value="2026">Calendar Year 2026 (Partial)</option>
                        </>
                      ) : (
                        <>
                          <option value="2024-Q1">2024-Q1 (Partial: 1 Day)</option>
                          <option value="2024-Q2">2024-Q2 (Full 3M)</option>
                          <option value="2024-Q3">2024-Q3 (Full 3M)</option>
                          <option value="2024-Q4">2024-Q4 (Full 3M)</option>
                          <option value="2025-Q1">2025-Q1 (Full 3M)</option>
                          <option value="2025-Q2">2025-Q2 (Full 3M)</option>
                          <option value="2025-Q3">2025-Q3 (Full 3M)</option>
                          <option value="2025-Q4">2025-Q4 (Full 3M)</option>
                          <option value="2026-Q1">2026-Q1 (Full 3M)</option>
                        </>
                      )}
                    </select>
                  </div>

                  <button
                    onClick={() => setShowSliceGraph((prev) => !prev)}
                    className="tarika-btn-outline"
                    style={{
                      padding: '0.45rem 0.95rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      backgroundColor: showSliceGraph ? '#ECFEFF' : '#FFFFFF',
                    }}
                  >
                    {showSliceGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                    <span>{showSliceGraph ? 'Hide Graph' : 'View Graph'}</span>
                  </button>
                </div>
              </div>

              {/* Sliced Parent Summary Card */}
              {data.slice_summary && (
                <div
                  style={{
                    padding: '1.1rem 1.4rem',
                    borderRadius: '12px',
                    backgroundColor: '#ECFEFF',
                    border: '1px solid #A5F3FC',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.78rem', color: '#0E7490', fontWeight: 600, textTransform: 'uppercase' }}>
                      Active Slice Parent Coordinate
                    </div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0E7490', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span>{data.slice_summary.parent_label}</span>
                      {data.slice_summary.is_partial && (
                        <span style={{ fontSize: '0.72rem', backgroundColor: '#FEF3C7', color: '#92400E', padding: '2px 8px', borderRadius: '9999px' }}>
                          {data.slice_summary.status_badge}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#155E75', marginTop: '2px' }}>
                      {data.slice_summary.span_description}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#0E7490' }}>Slice Revenue</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0E7490' }}>
                        {formatExactRevenue(data.slice_summary.parent_revenue)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#0E7490' }}>Delivered Orders</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#155E75' }}>
                        {formatExactCount(data.slice_summary.parent_orders)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#0E7490' }}>Slice AOV</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#047857' }}>
                        {formatExactAOV(data.slice_summary.parent_aov)}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Slice Graph */}
              {showSliceGraph && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#F0FDFA', border: '1px solid rgba(8, 145, 178, 0.2)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#0E7490', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={16} />
                      <span>{data.chart_config?.chart_title || 'Slice Revenue Distribution'}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                      Values in Crores (₹ Cr) &bull; Percentage share within sliced coordinate
                    </div>
                  </div>

                  <InteractiveOLAPBarChart
                    records={records}
                    metrics={chartMetrics}
                    hoveredPoint={hoveredPoint}
                    onHover={setHoveredPoint}
                    themeColor="#0891B2"
                  />
                </div>
              )}

              {/* Slice Table */}
              <OLAPDataTable
                records={records}
                level={sliceType === 'year' ? 'month' : 'month'}
                themeColor="#0891B2"
                onInspectOrders={handleInspectOrders}
              />
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 4: DICE                                                       */}
          {/* ================================================================= */}
          {activeTab === 'dice' && (
            <div>
              {/* Dice Filter Card */}
              <div
                style={{
                  padding: '1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                      OLAP Dice: Multi-Dimensional Subcube Builder
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                      Select arbitrary combinations of Years AND Months to construct a customized analytical subcube
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => {
                        setDiceYears(['2024', '2025', '2026']);
                        setDiceMonths([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
                      }}
                      className="tarika-btn-outline"
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
                    >
                      All Years & Months
                    </button>
                    <button
                      onClick={() => {
                        setDiceYears(['2024', '2025']);
                        setDiceMonths([4, 5, 6]);
                      }}
                      className="tarika-btn-outline"
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
                    >
                      Q2 Benchmark (2024 & 2025)
                    </button>
                    <button
                      onClick={() => {
                        setDiceYears([]);
                        setDiceMonths([]);
                      }}
                      className="tarika-btn-outline"
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', color: '#991B1B' }}
                    >
                      Clear All
                    </button>
                    <button
                      onClick={() => setShowDiceGraph((prev) => !prev)}
                      className="tarika-btn-outline"
                      style={{
                        padding: '0.35rem 0.75rem',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                      }}
                    >
                      {showDiceGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                      <span>{showDiceGraph ? 'Hide Graph' : 'View Graph'}</span>
                    </button>
                  </div>
                </div>

                {/* Years Selector Pills */}
                <div style={{ marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#374151' }}>
                      1. Select Years:
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => setDiceYears(['2024', '2025', '2026'])}
                        style={{ fontSize: '0.72rem', padding: '0.1rem 0.35rem', cursor: 'pointer', border: 'none', background: 'none', color: '#D97706', textDecoration: 'underline', fontWeight: 600 }}
                      >
                        All Years
                      </button>
                      <button
                        onClick={() => setDiceYears([])}
                        style={{ fontSize: '0.72rem', padding: '0.1rem 0.35rem', cursor: 'pointer', border: 'none', background: 'none', color: '#6B7280', textDecoration: 'underline' }}
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {['2024', '2025', '2026'].map((y) => {
                      const isSel = diceYears.includes(y);
                      return (
                        <button
                          key={y}
                          onClick={() => handleToggleDiceYear(y)}
                          style={{
                            padding: '0.4rem 0.85rem',
                            borderRadius: '8px',
                            border: `1px solid ${isSel ? '#D97706' : '#D1D5DB'}`,
                            backgroundColor: isSel ? '#FEF3C7' : '#FFFFFF',
                            color: isSel ? '#92400E' : '#4B5563',
                            fontWeight: 700,
                            fontSize: '0.8rem',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                          }}
                        >
                          <input type="checkbox" checked={isSel} readOnly style={{ cursor: 'pointer' }} />
                          <span>Year {y} {y === '2025' ? '(12M)' : '(Partial)'}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Months Selector Pills */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#374151' }}>
                      2. Select Months:
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => setDiceMonths([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])}
                        style={{ fontSize: '0.72rem', padding: '0.1rem 0.35rem', cursor: 'pointer', border: 'none', background: 'none', color: '#D97706', textDecoration: 'underline', fontWeight: 600 }}
                      >
                        All Months
                      </button>
                      <button
                        onClick={() => setDiceMonths([])}
                        style={{ fontSize: '0.72rem', padding: '0.1rem 0.35rem', cursor: 'pointer', border: 'none', background: 'none', color: '#6B7280', textDecoration: 'underline' }}
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
                      const isSel = diceMonths.includes(m);
                      return (
                        <button
                          key={m}
                          onClick={() => handleToggleDiceMonth(m)}
                          style={{
                            padding: '0.35rem 0.75rem',
                            borderRadius: '8px',
                            border: `1px solid ${isSel ? '#D97706' : '#E5E7EB'}`,
                            backgroundColor: isSel ? '#D97706' : '#F9FAFB',
                            color: isSel ? '#FFFFFF' : '#374151',
                            fontWeight: 700,
                            fontSize: '0.78rem',
                            cursor: 'pointer',
                            transition: 'all 0.12s ease',
                          }}
                        >
                          {MONTH_SHORT[m]}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Subcube Summary Card */}
              {data.subcube_summary && records.length > 0 && (
                <div
                  style={{
                    padding: '1.1rem 1.4rem',
                    borderRadius: '12px',
                    backgroundColor: '#FFFBEB',
                    border: '1px solid #FDE68A',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.78rem', color: '#92400E', fontWeight: 600, textTransform: 'uppercase' }}>
                      Constructed Subcube Aggregate
                    </div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#92400E' }}>
                      {records.length} Matching Monthly Record{records.length !== 1 ? 's' : ''} in Selected Subcube
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#B45309', marginTop: '2px' }}>
                      Share of Total Historical Revenue: <strong>{data.subcube_summary.share_of_global_pct}%</strong>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#92400E' }}>Subcube Revenue</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#92400E' }}>
                        {formatExactRevenue(data.subcube_summary.total_revenue)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#92400E' }}>Delivered Orders</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1F191B' }}>
                        {formatExactCount(data.subcube_summary.order_count)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: '#92400E' }}>Subcube AOV</div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#047857' }}>
                        {formatExactAOV(data.subcube_summary.avg_order_value)}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Empty Selection Handler */}
              {records.length === 0 && (
                <div
                  style={{
                    padding: '2.5rem',
                    textAlign: 'center',
                    backgroundColor: '#FFFFFF',
                    borderRadius: '12px',
                    border: '1px dashed #D1D5DB',
                    color: '#6B7280',
                    marginBottom: '1.5rem',
                  }}
                >
                  <Filter size={32} style={{ margin: '0 auto 0.75rem', color: '#9CA3AF' }} />
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#374151' }}>Empty Subcube Selection</div>
                  <p style={{ fontSize: '0.82rem', margin: '0.4rem 0 0' }}>
                    No time coordinates selected. Please select at least one year and one month above to define the OLAP subcube.
                  </p>
                </div>
              )}

              {/* Dice Graph */}
              {showDiceGraph && records.length > 0 && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#FFFDF5', border: '1px solid rgba(217, 119, 6, 0.2)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#92400E', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={16} />
                      <span>{data.chart_config?.chart_title || 'Diced Subcube Distribution'}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                      Hover bars to inspect exact revenue and order metrics
                    </div>
                  </div>

                  <InteractiveOLAPBarChart
                    records={records}
                    metrics={chartMetrics}
                    hoveredPoint={hoveredPoint}
                    onHover={setHoveredPoint}
                    themeColor="#D97706"
                  />
                </div>
              )}

              {/* Dice Table */}
              {records.length > 0 && (
                <OLAPDataTable
                  records={records}
                  level="month"
                  themeColor="#D97706"
                  onInspectOrders={handleInspectOrders}
                />
              )}
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 5: PIVOT                                                      */}
          {/* ================================================================= */}
          {activeTab === 'pivot' && (
            <div>
              {/* Pivot Explanation Banner */}
              <div
                style={{
                  padding: '1rem 1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '12px',
                  border: '1px solid #E5E7EB',
                  marginBottom: '1.5rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                    OLAP Pivot: Year &times; Quarter Cross-Tabulation Matrix
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    Reorients the 1D Time Dimension into a 2D seasonal matrix (Years along Rows, Quarters along Columns) without fabricating non-time dimensions
                  </div>
                </div>

                <button
                  onClick={() => setShowPivotGraph((prev) => !prev)}
                  className="tarika-btn-outline"
                  style={{
                    padding: '0.45rem 0.95rem',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    backgroundColor: showPivotGraph ? '#F5F3FF' : '#FFFFFF',
                  }}
                >
                  {showPivotGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                  <span>{showPivotGraph ? 'Hide Graph' : 'View Graph'}</span>
                </button>
              </div>

              {/* Pivot 2D Matrix Table */}
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  overflow: 'hidden',
                  marginBottom: '1.75rem',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                }}
              >
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#334155' }}>
                        <th style={{ padding: '0.85rem 1.2rem', fontWeight: 700 }}>Calendar Year (Rows)</th>
                        <th style={{ padding: '0.85rem 1rem', fontWeight: 700, textAlign: 'right' }}>Q1 (Jan – Mar)</th>
                        <th style={{ padding: '0.85rem 1rem', fontWeight: 700, textAlign: 'right' }}>Q2 (Apr – Jun)</th>
                        <th style={{ padding: '0.85rem 1rem', fontWeight: 700, textAlign: 'right' }}>Q3 (Jul – Sep)</th>
                        <th style={{ padding: '0.85rem 1rem', fontWeight: 700, textAlign: 'right' }}>Q4 (Oct – Dec)</th>
                        <th style={{ padding: '0.85rem 1.2rem', fontWeight: 800, textAlign: 'right', backgroundColor: '#F1F5F9', color: '#0F172A' }}>
                          Yearly Total (Row Total)
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.matrix_rows || []).map((row) => (
                        <tr key={row.year} style={{ borderBottom: '1px solid #F1F5F9' }}>
                          {/* Row Header */}
                          <td style={{ padding: '1rem 1.2rem', fontWeight: 700, color: '#1E293B' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ fontSize: '0.95rem' }}>Year {row.year}</span>
                              {row.is_partial ? (
                                <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '6px', backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: 600 }}>
                                  {row.status_badge}
                                </span>
                              ) : (
                                <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '6px', backgroundColor: '#ECFDF5', color: '#065F46', fontWeight: 600 }}>
                                  Full Year (12M)
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Quarters Cells */}
                          {['Q1', 'Q2', 'Q3', 'Q4'].map((q) => {
                            const cell = row.cells?.[q];
                            if (!cell || !cell.recorded) {
                              return (
                                <td key={q} style={{ padding: '1rem', textAlign: 'right', color: '#94A3B8' }}>
                                  <span
                                    style={{
                                      fontSize: '0.74rem',
                                      padding: '2px 8px',
                                      borderRadius: '6px',
                                      backgroundColor: '#F8FAFC',
                                      color: '#94A3B8',
                                      border: '1px dashed #CBD5E1',
                                      fontStyle: 'italic',
                                    }}
                                  >
                                    N/A (Unrecorded)
                                  </span>
                                </td>
                              );
                            }

                            return (
                              <td key={q} style={{ padding: '1rem', textAlign: 'right' }}>
                                <div style={{ fontWeight: 700, color: cell.is_partial ? '#B45309' : '#1E293B' }}>
                                  {formatExactRevenue(cell.revenue)}
                                </div>
                                <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '1px' }}>
                                  {formatExactCount(cell.order_count)} orders &bull; AOV: ₹{cell.avg_order_value?.toFixed(2)}
                                </div>
                                {cell.is_partial && (
                                  <div style={{ fontSize: '0.68rem', color: '#D97706', fontWeight: 600 }}>
                                    {cell.status_badge}
                                  </div>
                                )}
                              </td>
                            );
                          })}

                          {/* Row Total (Yearly Total) */}
                          <td style={{ padding: '1rem 1.2rem', textAlign: 'right', backgroundColor: '#F8FAFC', fontWeight: 800, color: '#7C3AED' }}>
                            <div style={{ fontSize: '0.92rem' }}>
                              {formatExactRevenue(row.row_total_revenue)}
                            </div>
                            <div style={{ fontSize: '0.72rem', color: '#6B7280', marginTop: '1px' }}>
                              {formatExactCount(row.row_total_orders)} orders &bull; AOV: ₹{row.row_aov?.toFixed(2)}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>

                    {/* Column Totals Footer */}
                    <tfoot>
                      <tr style={{ backgroundColor: '#F1F5F9', borderTop: '2px solid #CBD5E1', color: '#0F172A' }}>
                        <td style={{ padding: '1rem 1.2rem', fontWeight: 800 }}>
                          Quarterly Total (Column Total)
                        </td>
                        {['Q1', 'Q2', 'Q3', 'Q4'].map((q) => {
                          const col = data.column_totals?.[q];
                          return (
                            <td key={q} style={{ padding: '1rem', textAlign: 'right', fontWeight: 800 }}>
                              <div style={{ color: '#0F172A' }}>
                                {formatExactRevenue(col?.total_revenue)}
                              </div>
                              <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '1px' }}>
                                {formatExactCount(col?.total_orders)} orders &bull; AOV: ₹{col?.avg_order_value?.toFixed(2)}
                              </div>
                            </td>
                          );
                        })}
                        {/* Grand Total Intersection */}
                        <td style={{ padding: '1rem 1.2rem', textAlign: 'right', backgroundColor: '#EDE9FE', fontWeight: 900, color: '#5B21B6' }}>
                          <div style={{ fontSize: '1rem' }}>
                            {formatExactRevenue(data.grand_total?.revenue)}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: '#6D28D9', marginTop: '1px' }}>
                            {formatExactCount(data.grand_total?.orders)} orders &bull; AOV: ₹{data.grand_total?.aov?.toFixed(2)}
                          </div>
                          <div style={{ fontSize: '0.68rem', color: '#059669', fontWeight: 700, marginTop: '2px' }}>
                            Exact Reconciled (100%)
                          </div>
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Pivot Seasonal Comparison Chart */}
              {showPivotGraph && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#FAF5FF', border: '1px solid rgba(124, 58, 237, 0.2)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#7C3AED', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={16} />
                      <span>{data.chart_config?.chart_title || 'Quarterly Seasonal Comparison across Years'}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                      Values in Crores (₹ Cr) &bull; Q1, Q2, Q3, Q4 breakdown
                    </div>
                  </div>

                  {/* Render Pivot Grouped Column Chart */}
                  <PivotGroupedBarChart matrixRows={data.matrix_rows || []} />
                </div>
              )}
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 6: RANKING                                                    */}
          {/* ================================================================= */}
          {activeTab === 'ranking' && (
            <div>
              {/* Ranking Controls */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '1rem',
                  marginBottom: '1.25rem',
                  padding: '1rem 1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '12px',
                  border: '1px solid #E5E7EB',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                    OLAP Ranking: Revenue Performance Leaderboards
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    Deterministic revenue ranking with clear warning badges for partial-duration periods
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {/* Granularity Selector */}
                  <div style={{ display: 'flex', backgroundColor: '#F3F4F6', padding: '3px', borderRadius: '10px' }}>
                    {[
                      { id: 'month', label: 'Rank Months (25)' },
                      { id: 'quarter', label: 'Rank Quarters (9)' },
                      { id: 'year', label: 'Rank Years (3)' },
                    ].map((g) => (
                      <button
                        key={g.id}
                        onClick={() => setRankingGranularity(g.id)}
                        style={{
                          padding: '0.4rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          border: 'none',
                          backgroundColor: rankingGranularity === g.id ? '#059669' : 'transparent',
                          color: rankingGranularity === g.id ? '#FFFFFF' : '#6B5E63',
                          cursor: 'pointer',
                        }}
                      >
                        {g.label}
                      </button>
                    ))}
                  </div>

                  {/* Sort Order Toggle */}
                  <button
                    onClick={() => setRankingSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))}
                    className="tarika-btn-outline"
                    style={{
                      padding: '0.45rem 0.85rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <ArrowUpDown size={14} />
                    <span>{rankingSortOrder === 'desc' ? 'Highest First (DESC)' : 'Lowest First (ASC)'}</span>
                  </button>

                  <button
                    onClick={() => setShowRankingGraph((prev) => !prev)}
                    className="tarika-btn-outline"
                    style={{
                      padding: '0.45rem 0.95rem',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      backgroundColor: showRankingGraph ? '#ECFDF5' : '#FFFFFF',
                    }}
                  >
                    {showRankingGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                    <span>{showRankingGraph ? 'Hide Graph' : 'View Graph'}</span>
                  </button>
                </div>
              </div>

              {/* Top & Bottom Performer Highlights */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                {data.top_performer && (
                  <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#047857', textTransform: 'uppercase' }}>
                      Rank #1 Leader (Peak Revenue)
                    </div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#065F46', marginTop: '2px' }}>
                      {data.top_performer.label}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#047857', marginTop: '2px' }}>
                      Revenue: <strong>{formatExactRevenue(data.top_performer.total_revenue)}</strong> &bull; Share: {data.top_performer.share_of_total_pct}%
                    </div>
                  </div>
                )}

                {data.bottom_performer && (
                  <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', backgroundColor: '#FEF3C7', border: '1px solid #FDE68A' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#92400E', textTransform: 'uppercase' }}>
                      Lowest Ranked Period
                    </div>
                    <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#78350F', marginTop: '2px' }}>
                      {data.bottom_performer.label}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#92400E', marginTop: '2px' }}>
                      {data.bottom_performer.comparison_warning || `Revenue: ${formatExactRevenue(data.bottom_performer.total_revenue)}`}
                    </div>
                  </div>
                )}
              </div>

              {/* Ranking Chart */}
              {showRankingGraph && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#F0FDF4', border: '1px solid rgba(5, 150, 105, 0.2)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#059669', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Award size={16} />
                      <span>{data.chart_config?.chart_title || 'Revenue Leaderboard Chart'}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                      Ranked by realised revenue &bull; Partial periods flagged in yellow
                    </div>
                  </div>

                  <InteractiveOLAPBarChart
                    records={records}
                    metrics={chartMetrics}
                    hoveredPoint={hoveredPoint}
                    onHover={setHoveredPoint}
                    themeColor="#059669"
                  />
                </div>
              )}

              {/* Ranking Table */}
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  overflow: 'hidden',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                }}
              >
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#475569' }}>
                        <th style={{ padding: '0.75rem 1rem', width: '70px', fontWeight: 700, textAlign: 'center' }}>Rank</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Time Period</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Realised Revenue</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Delivered Orders</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Units Sold</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>AOV</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Revenue Share</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Period Status & Warnings</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'center' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((r) => (
                        <tr
                          key={r.period_key}
                          style={{
                            borderBottom: '1px solid #F1F5F9',
                            backgroundColor: r.rank === 1 ? '#F0FDF4' : r.is_partial ? '#FFFBEB' : '#FFFFFF',
                          }}
                        >
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'center', fontWeight: 800 }}>
                            <span
                              style={{
                                display: 'inline-block',
                                width: '28px',
                                height: '28px',
                                lineHeight: '28px',
                                borderRadius: '9999px',
                                backgroundColor: r.rank === 1 ? '#059669' : r.rank === 2 ? '#3B82F6' : r.rank === 3 ? '#8B5CF6' : '#F1F5F9',
                                color: r.rank <= 3 ? '#FFFFFF' : '#475569',
                                fontSize: '0.75rem',
                              }}
                            >
                              #{r.rank}
                            </span>
                          </td>
                          <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: '#1E293B' }}>
                            <div>{r.label}</div>
                            <div style={{ fontSize: '0.72rem', color: '#64748B' }}>{r.period_key}</div>
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 800, color: '#059669' }}>
                            {formatExactRevenue(r.total_revenue)}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#1E293B' }}>
                            {formatExactCount(r.order_count)}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#1E293B' }}>
                            {formatExactCount(r.units_sold)}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#047857', fontWeight: 600 }}>
                            {formatExactAOV(r.avg_order_value)}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 700 }}>
                            {r.share_of_total_pct}%
                          </td>
                          <td style={{ padding: '0.85rem 1rem' }}>
                            {r.is_partial ? (
                              <div>
                                <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: 700 }}>
                                  {r.status_badge}
                                </span>
                                {r.comparison_warning && (
                                  <div style={{ fontSize: '0.72rem', color: '#B45309', marginTop: '3px' }}>
                                    {r.comparison_warning}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#ECFDF5', color: '#065F46', fontWeight: 700 }}>
                                Complete Period
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '0.85rem 1rem', textAlign: 'center' }}>
                            <button
                              onClick={() => handleInspectOrders(rankingGranularity, r.period_key)}
                              className="tarika-btn-outline"
                              style={{
                                padding: '0.3rem 0.6rem',
                                fontSize: '0.72rem',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.3rem',
                              }}
                              title="Inspect raw underlying delivered orders in Drill-Through"
                            >
                              <Search size={12} />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 7: DRILL-THROUGH (INSPECT ATOMIC ORDERS)                       */}
          {/* ================================================================= */}
          {activeTab === 'drillthrough' && (
            <div>
              {/* Drill-through Filter & Search Header */}
              <div
                style={{
                  padding: '1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Search size={18} style={{ color: '#DC2626' }} />
                      <span>OLAP Drill-Through: Raw Atomic Sales Transaction Inspection</span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                      Inspects the authentic underlying delivered records directly in public.orders &bull; Max 50 records/page &bull; Customer IDs Masked
                    </div>
                  </div>

                  {/* Period Filter Pickers */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', backgroundColor: '#F3F4F6', padding: '3px', borderRadius: '10px' }}>
                      {[
                        { id: 'month', label: 'Month' },
                        { id: 'quarter', label: 'Quarter' },
                        { id: 'year', label: 'Year' },
                        { id: 'all', label: 'All Orders' },
                      ].map((t) => (
                        <button
                          key={t.id}
                          onClick={() => {
                            setDtPeriodType(t.id);
                            setDtPage(1);
                            if (t.id === 'month') setDtPeriodKey('2024-03');
                            else if (t.id === 'quarter') setDtPeriodKey('2024-Q1');
                            else if (t.id === 'year') setDtPeriodKey('2024');
                          }}
                          style={{
                            padding: '0.4rem 0.75rem',
                            fontSize: '0.78rem',
                            fontWeight: 700,
                            borderRadius: '8px',
                            border: 'none',
                            backgroundColor: dtPeriodType === t.id ? '#DC2626' : 'transparent',
                            color: dtPeriodType === t.id ? '#FFFFFF' : '#6B5E63',
                            cursor: 'pointer',
                          }}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>

                    {dtPeriodType === 'month' && (
                      <input
                        type="text"
                        value={dtPeriodKey}
                        onChange={(e) => {
                          setDtPeriodKey(e.target.value);
                          setDtPage(1);
                        }}
                        placeholder="YYYY-MM (e.g. 2024-03)"
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: '8px',
                          border: '1px solid #D1D5DB',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                          width: '140px',
                        }}
                      />
                    )}

                    {dtPeriodType === 'quarter' && (
                      <input
                        type="text"
                        value={dtPeriodKey}
                        onChange={(e) => {
                          setDtPeriodKey(e.target.value);
                          setDtPage(1);
                        }}
                        placeholder="YYYY-QX (e.g. 2024-Q1)"
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: '8px',
                          border: '1px solid #D1D5DB',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                          width: '140px',
                        }}
                      />
                    )}

                    {dtPeriodType === 'year' && (
                      <select
                        value={dtPeriodKey}
                        onChange={(e) => {
                          setDtPeriodKey(e.target.value);
                          setDtPage(1);
                        }}
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: '8px',
                          border: '1px solid #D1D5DB',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                        }}
                      >
                        <option value="2024">Year 2024 (Partial)</option>
                        <option value="2025">Year 2025 (Full Year)</option>
                        <option value="2026">Year 2026 (Partial)</option>
                      </select>
                    )}
                  </div>
                </div>

                {/* Period Summary & Privacy Safeguards Banner */}
                {data.period_summary && (
                  <div
                    style={{
                      padding: '0.9rem 1.25rem',
                      borderRadius: '10px',
                      backgroundColor: '#FEF2F2',
                      border: '1px solid #FCA5A5',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '1rem',
                      fontSize: '0.82rem',
                    }}
                  >
                    <div>
                      Filter: <strong style={{ color: '#991B1B' }}>{dtPeriodType.toUpperCase()}: {dtPeriodKey || 'ALL DELIVERED'}</strong> &bull;{' '}
                      Matching Records in DB: <strong style={{ color: '#1F191B' }}>{formatExactCount(data.period_summary.total_orders)}</strong>
                    </div>
                    <div style={{ display: 'flex', gap: '1.25rem' }}>
                      <span>Revenue: <strong style={{ color: '#991B1B' }}>{formatExactRevenue(data.period_summary.total_revenue)}</strong></span>
                      <span>Units: <strong>{formatExactCount(data.period_summary.total_units)}</strong></span>
                      <span>AOV: <strong style={{ color: '#047857' }}>{formatExactAOV(data.period_summary.overall_aov)}</strong></span>
                    </div>
                  </div>
                )}
              </div>

              {/* Paginated Orders Table */}
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  overflow: 'hidden',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#475569' }}>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Order ID</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Purchase Date</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Customer ID (Masked)</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Product ID</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Payment Method</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Qty</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Final Price</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'center' }}>Shipping (Days)</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'center' }}>Rating</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.orders || []).length === 0 ? (
                        <tr>
                          <td colSpan={9} style={{ padding: '2.5rem', textAlign: 'center', color: '#94A3B8' }}>
                            No delivered order transactions found matching period criteria.
                          </td>
                        </tr>
                      ) : (
                        (data.orders || []).map((ord) => (
                          <tr key={ord.orderid} style={{ borderBottom: '1px solid #F1F5F9' }}>
                            <td style={{ padding: '0.75rem 1rem', fontWeight: 700, fontFamily: 'monospace', color: '#1E293B' }}>
                              {ord.orderid}
                            </td>
                            <td style={{ padding: '0.75rem 1rem', color: '#475569' }}>
                              {ord.purchase_date}
                            </td>
                            <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#0891B2', fontWeight: 600 }}>
                              {ord.customer_id_masked}
                            </td>
                            <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#475569' }}>
                              {ord.product_id}
                            </td>
                            <td style={{ padding: '0.75rem 1rem' }}>
                              <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '6px', backgroundColor: '#F3F4F6', color: '#374151', fontWeight: 600 }}>
                                {ord.payment_method}
                              </span>
                            </td>
                            <td style={{ padding: '0.75rem 1rem', textAlign: 'right', fontWeight: 600 }}>
                              {ord.quantity}
                            </td>
                            <td style={{ padding: '0.75rem 1rem', textAlign: 'right', fontWeight: 800, color: '#B8505E' }}>
                              ₹{Number(ord.final_price).toFixed(2)}
                            </td>
                            <td style={{ padding: '0.75rem 1rem', textAlign: 'center', color: '#64748B' }}>
                              {ord.shipping_time_days != null ? `${ord.shipping_time_days}d` : '—'}
                            </td>
                            <td style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                              {ord.rating != null ? (
                                <span style={{ color: '#D97706', fontWeight: 700 }}>★ {ord.rating}</span>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Server-Side Pagination Bar */}
              {data.pagination && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '1rem',
                    padding: '0.85rem 1.25rem',
                    backgroundColor: '#FFFFFF',
                    borderRadius: '12px',
                    border: '1px solid #E5E7EB',
                    fontSize: '0.82rem',
                  }}
                >
                  <div style={{ color: '#6B7280' }}>
                    Showing page <strong>{data.pagination.page}</strong> of <strong>{data.pagination.total_pages}</strong> &bull;{' '}
                    Total Matching Orders: <strong>{formatExactCount(data.pagination.total_orders)}</strong> (Page Size: {data.pagination.page_size})
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button
                      onClick={() => setDtPage((p) => Math.max(1, p - 1))}
                      disabled={!data.pagination.has_prev || loading}
                      className="tarika-btn-outline"
                      style={{
                        padding: '0.4rem 0.85rem',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        cursor: !data.pagination.has_prev || loading ? 'not-allowed' : 'pointer',
                        opacity: !data.pagination.has_prev ? 0.5 : 1,
                      }}
                    >
                      <ChevronLeft size={14} />
                      <span>Previous Page</span>
                    </button>

                    <button
                      onClick={() => setDtPage((p) => p + 1)}
                      disabled={!data.pagination.has_next || loading}
                      className="tarika-btn-outline"
                      style={{
                        padding: '0.4rem 0.85rem',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        cursor: !data.pagination.has_next || loading ? 'not-allowed' : 'pointer',
                        opacity: !data.pagination.has_next ? 0.5 : 1,
                      }}
                    >
                      <span>Next Page</span>
                      <ChevronRight size={14} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ================================================================= */}
          {/* TAB 8: TREND ANALYSIS                                             */}
          {/* ================================================================= */}
          {activeTab === 'trend' && (
            <div>
              {/* Trend Header & Metrics Banner */}
              <div
                style={{
                  padding: '1.25rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '1rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <TrendingUp size={18} style={{ color: '#2563EB' }} />
                      <span>Historical Actual Revenue Trend Analysis (25 Chronological Months)</span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                      Strictly evaluates historical delivered sales &bull; Calculates MoM Change, MoM %, YoY %, and 3-Month Simple Moving Average (SMA-3) &bull; Zero forecasting mixed in
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <button
                      onClick={() => setExcludeInceptionArtifactInGraph((prev) => !prev)}
                      className="tarika-btn-outline"
                      style={{
                        padding: '0.4rem 0.75rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        backgroundColor: excludeInceptionArtifactInGraph ? '#EFF6FF' : '#FFFFFF',
                        color: excludeInceptionArtifactInGraph ? '#1D4ED8' : '#4B5563',
                        borderColor: excludeInceptionArtifactInGraph ? '#93C5FD' : '#D1D5DB',
                      }}
                      title="Toggle suppressing the +2,516% single-day inception artifact on growth charts"
                    >
                      {excludeInceptionArtifactInGraph ? 'Artifact Suppressed on Chart' : 'Show Full Artifact on Chart'}
                    </button>

                    <button
                      onClick={() => setShowTrendGraph((prev) => !prev)}
                      className="tarika-btn-outline"
                      style={{
                        padding: '0.45rem 0.95rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.45rem',
                        backgroundColor: showTrendGraph ? '#EFF6FF' : '#FFFFFF',
                      }}
                    >
                      {showTrendGraph ? <EyeOff size={14} /> : <Eye size={14} />}
                      <span>{showTrendGraph ? 'Hide Graph' : 'View Graph'}</span>
                    </button>
                  </div>
                </div>

                {/* Statistical Summary KPI Cards */}
                {data.trend_summary && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                    <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD' }}>
                      <div style={{ fontSize: '0.72rem', color: '#0369A1', fontWeight: 700, textTransform: 'uppercase' }}>
                        Full Months Average Revenue
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0C4A6E', marginTop: '2px' }}>
                        {formatCrores(data.trend_summary.average_monthly_revenue_full_months)}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#0284C7', marginTop: '1px' }}>
                        {formatCrores(data.trend_summary.average_monthly_revenue_full_months)}/month across {data.trend_summary.full_months_observed || 24} full months
                      </div>
                    </div>

                    <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', backgroundColor: '#F0FDF4', border: '1px solid #BBF7D0' }}>
                      <div style={{ fontSize: '0.72rem', color: '#15803D', fontWeight: 700, textTransform: 'uppercase' }}>
                        Average YoY Growth Rate
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#14532D', marginTop: '2px' }}>
                        {formatPercent(data.trend_summary.average_yoy_growth_rate_pct)}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#16A34A', marginTop: '1px' }}>
                        Stable seasonal variance across 12 full months
                      </div>
                    </div>

                    <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', backgroundColor: '#FEF3C7', border: '1px solid #FDE68A' }}>
                      <div style={{ fontSize: '0.72rem', color: '#B45309', fontWeight: 700, textTransform: 'uppercase' }}>
                        Peak Historical Revenue Month
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#78350F', marginTop: '2px' }}>
                        {data.trend_summary.peak_revenue_month?.label}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#92400E', marginTop: '1px' }}>
                        {formatExactRevenue(data.trend_summary.peak_revenue_month?.revenue)}
                      </div>
                    </div>

                    <div style={{ padding: '0.85rem 1rem', borderRadius: '10px', backgroundColor: '#F1F5F9', border: '1px solid #CBD5E1' }}>
                      <div style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase' }}>
                        Lowest Full Month
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
                        {data.trend_summary.lowest_revenue_full_month?.label}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '1px' }}>
                        {data.trend_summary.lowest_revenue_full_month?.note}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Inception Baseline Warning Alert */}
              <div
                style={{
                  padding: '0.85rem 1.25rem',
                  borderRadius: '12px',
                  backgroundColor: '#EFF6FF',
                  border: '1px solid #BFDBFE',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  fontSize: '0.82rem',
                  color: '#1E40AF',
                  marginBottom: '1.5rem',
                  lineHeight: 1.45,
                }}
              >
                <Info size={18} style={{ color: '#2563EB', flexShrink: 0 }} />
                <div>
                  <strong>Academic Explanation of Inception Anomalies:</strong> March 2024 has only 1 recorded day (March 31, 2024; ₹61.26 L). Consequently, April 2024 displays an artificial MoM growth surge of <strong>+2,516.55%</strong>, and March 2025 displays a non-comparable YoY surge of <strong>+2,707.66%</strong>. March 2024 is excluded from moving averages; the first valid 3-Month Moving Average (SMA-3) is June 2024, evaluating April, May, and June 2024.
                </div>
              </div>

              {/* Trend Chart (Actual Revenue & 3-Month Moving Average) */}
              {showTrendGraph && (
                <div style={{ marginBottom: '2rem', padding: '1.25rem', borderRadius: '14px', backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1E293B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <BarChart3 size={16} style={{ color: '#2563EB' }} />
                      <span>Actual Monthly Realised Revenue & 3-Month Moving Average (SMA-3)</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.75rem', color: '#64748B' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <span style={{ display: 'inline-block', width: '12px', height: '12px', backgroundColor: '#2563EB', borderRadius: '3px' }}></span>
                        <span>Monthly Revenue</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <span style={{ display: 'inline-block', width: '14px', height: '3px', backgroundColor: '#F59E0B' }}></span>
                        <span>SMA-3 Trendline</span>
                      </div>
                    </div>
                  </div>

                  <TrendLineSMAChart records={records} />
                </div>
              )}

              {/* 25-Month Trend Analysis Table */}
              <div
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid #E5E7EB',
                  overflow: 'hidden',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                }}
              >
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#475569' }}>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Month ($t$)</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Actual Revenue (₹)</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>MoM Change (₹)</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>MoM Growth %</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>YoY Growth %</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>3-Month SMA (₹)</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Analytical Note & Status</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'center' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((r, idx) => {
                        const isMomPositive = (r.mom_growth_pct || 0) > 0;
                        const isYoyPositive = (r.yoy_growth_pct || 0) > 0;
                        return (
                          <tr
                            key={r.period_key}
                            style={{
                              borderBottom: '1px solid #F1F5F9',
                              backgroundColor: r.is_partial ? '#FFFBEB' : '#FFFFFF',
                            }}
                          >
                            <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: '#1E293B' }}>
                              <div>{r.label}</div>
                              <div style={{ fontSize: '0.72rem', color: '#64748B' }}>{r.period_key} &bull; t = {idx + 1}</div>
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 800, color: '#1E293B' }}>
                              {formatExactRevenue(r.actual_revenue)}
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 600 }}>
                              {r.mom_change != null ? (
                                <span style={{ color: r.mom_change >= 0 ? '#059669' : '#DC2626' }}>
                                  {r.mom_change >= 0 ? '+' : ''}{formatExactRevenue(r.mom_change)}
                                </span>
                              ) : (
                                <span style={{ color: '#9CA3AF' }}>—</span>
                              )}
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 700 }}>
                              {r.mom_growth_pct != null ? (
                                r.is_mom_artifact ? (
                                  <span style={{ color: '#D97706', backgroundColor: '#FEF3C7', padding: '2px 6px', borderRadius: '4px' }}>
                                    +{r.mom_growth_pct}% [Artifact]
                                  </span>
                                ) : (
                                  <span style={{ color: isMomPositive ? '#059669' : '#DC2626' }}>
                                    {formatPercent(r.mom_growth_pct)}
                                  </span>
                                )
                              ) : (
                                <span style={{ color: '#9CA3AF' }}>—</span>
                              )}
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 700 }}>
                              {r.yoy_growth_pct != null ? (
                                r.is_yoy_non_comparable ? (
                                  <span style={{ color: '#B45309', backgroundColor: '#FEF3C7', padding: '2px 6px', borderRadius: '4px' }}>
                                    +{r.yoy_growth_pct}% [Non-Comp]
                                  </span>
                                ) : (
                                  <span style={{ color: isYoyPositive ? '#059669' : '#DC2626' }}>
                                    {formatPercent(r.yoy_growth_pct)}
                                  </span>
                                )
                              ) : (
                                <span style={{ color: '#9CA3AF' }}>—</span>
                              )}
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#B45309', fontWeight: 600 }}>
                              {r.sma_3 != null ? (
                                formatExactRevenue(r.sma_3)
                              ) : (
                                <span
                                  style={{
                                    color: '#6B7280',
                                    fontSize: '0.74rem',
                                    fontWeight: 700,
                                    backgroundColor: '#F3F4F6',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    display: 'inline-block',
                                  }}
                                  title={r.sma_3_note || 'N/A: March 2024 partial baseline excluded from SMA-3'}
                                >
                                  N/A
                                </span>
                              )}
                            </td>
                            <td style={{ padding: '0.85rem 1rem' }}>
                              {r.is_partial ? (
                                <div>
                                  <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: 700 }}>
                                    {r.status_badge}
                                  </span>
                                  <div style={{ fontSize: '0.72rem', color: '#92400E', marginTop: '2px' }}>
                                    {r.mom_note}
                                  </div>
                                </div>
                              ) : (
                                <div style={{ fontSize: '0.76rem', color: '#4B5563' }}>
                                  {r.is_mom_artifact ? (
                                    <span style={{ color: '#B45309', fontWeight: 600 }}>Inception baseline comparison artifact (1-day baseline)</span>
                                  ) : r.is_yoy_non_comparable ? (
                                    <span style={{ color: '#B45309', fontWeight: 600 }}>Partial-to-full prior year non-comparable (Mar 2024 1-day)</span>
                                  ) : r.period_key === '2024-05' ? (
                                    <span style={{ color: '#6B7280' }}>Standard full month (SMA-3 pending full 3-month window; Mar 2024 excluded)</span>
                                  ) : r.period_key === '2024-06' ? (
                                    <span style={{ color: '#059669', fontWeight: 600 }}>First complete 3-month SMA baseline (Apr–Jun 2024)</span>
                                  ) : (
                                    <span style={{ color: '#059669' }}>Standard historical monthly observation</span>
                                  )}
                                </div>
                              )}
                            </td>
                            <td style={{ padding: '0.85rem 1rem', textAlign: 'center' }}>
                              <button
                                onClick={() => handleInspectOrders('month', r.period_key)}
                                className="tarika-btn-outline"
                                style={{
                                  padding: '0.3rem 0.6rem',
                                  fontSize: '0.72rem',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '0.3rem',
                                }}
                                title="Inspect raw delivered order transactions in Drill-Through"
                              >
                                <Search size={12} />
                                <span>Inspect</span>
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Standard OLAP Data Table component for Roll-up, Drill-down, and Slice.
 */
function OLAPDataTable({ records, level, themeColor, onInspectOrders }) {
  if (!records || records.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', backgroundColor: '#FFFFFF', borderRadius: '12px', border: '1px dashed #D1D5DB', color: '#6B7280' }}>
        No OLAP records found for the selected coordinate.
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '14px',
        border: '1px solid #E5E7EB',
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#475569' }}>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Time Period</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Realised Revenue</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Delivered Orders</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Distinct IDs</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Units Sold</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>AOV</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'right' }}>Share of Revenue</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Period Status</th>
              <th style={{ padding: '0.75rem 1rem', fontWeight: 700, textAlign: 'center' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => {
              const sharePct = r.share_of_slice_pct ?? r.share_of_total_pct ?? 0;
              return (
                <tr key={r.period_key} style={{ borderBottom: '1px solid #F1F5F9', backgroundColor: r.is_partial ? '#FFFBEB' : '#FFFFFF' }}>
                  <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: '#1E293B' }}>
                    <div>{r.label}</div>
                    <div style={{ fontSize: '0.72rem', color: '#64748B' }}>{r.period_key}</div>
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 800, color: themeColor }}>
                    {formatExactRevenue(r.total_revenue)}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#1E293B' }}>
                    {formatExactCount(r.order_count)}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#64748B' }}>
                    {formatExactCount(r.distinct_orders)}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#1E293B' }}>
                    {formatExactCount(r.units_sold)}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right', color: '#047857', fontWeight: 600 }}>
                    {formatExactAOV(r.avg_order_value)}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>
                    <div style={{ fontWeight: 700, color: '#1E293B' }}>{sharePct}%</div>
                    <div style={{ width: '80px', height: '4px', backgroundColor: '#E2E8F0', borderRadius: '2px', marginLeft: 'auto', marginTop: '4px', overflow: 'hidden' }}>
                      <div style={{ width: `${Math.min(100, sharePct * 2)}%`, height: '100%', backgroundColor: themeColor }} />
                    </div>
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    {r.is_partial ? (
                      <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: 700 }}>
                        {r.status_badge}
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '9999px', backgroundColor: '#ECFDF5', color: '#065F46', fontWeight: 700 }}>
                        Complete Period
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'center' }}>
                    <button
                      onClick={() => onInspectOrders(level, r.period_key)}
                      className="tarika-btn-outline"
                      style={{
                        padding: '0.3rem 0.6rem',
                        fontSize: '0.72rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                      }}
                      title="Inspect raw delivered order transactions in Drill-Through"
                    >
                      <Search size={12} />
                      <span>Inspect</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Interactive SVG Bar Chart for Roll-up, Drill-down, Slice, Dice, and Ranking.
 */
function InteractiveOLAPBarChart({ records, metrics, hoveredPoint, onHover, themeColor = '#B8505E' }) {
  if (!records || records.length === 0) return null;

  const n = records.length;
  const chartW = 920;
  const chartH = 220;
  const padLeft = 60;
  const padRight = 30;
  const padTop = 25;
  const padBottom = 40;
  const plotW = chartW - padLeft - padRight;
  const step = plotW / n;
  const colWidth = Math.max(8, Math.min(42, step * 0.7));
  const maxRev = metrics.maxRevenue || 1;

  return (
    <div>
      <svg
        viewBox={`0 0 ${chartW} ${chartH + padTop + padBottom}`}
        style={{ width: '100%', height: 'auto', display: 'block', overflow: 'visible' }}
      >
        <defs>
          <pattern id="partialHatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="#FDE68A" />
            <line x1="0" y1="0" x2="0" y2="8" stroke="#D97706" strokeWidth="2.5" />
          </pattern>
        </defs>

        {/* Horizontal grid lines */}
        {[0, 0.25, 0.5, 0.75, 1.0].map((frac, i) => {
          const y = padTop + chartH * (1 - frac);
          const val = maxRev * frac;
          return (
            <g key={i}>
              <line x1={padLeft} y1={y} x2={chartW - padRight} y2={y} stroke="#E2E8F0" strokeDasharray="3 3" />
              <text x={padLeft - 8} y={y + 3} textAnchor="end" fontSize="10" fill="#64748B" fontWeight="600">
                {formatCrores(val)}
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {records.map((r, i) => {
          const rev = r.total_revenue || r.actual_revenue || 0;
          const barH = (rev / maxRev) * chartH;
          const x = padLeft + i * step + (step - colWidth) / 2;
          const y = padTop + chartH - barH;
          const isHovered = hoveredPoint?.period_key === r.period_key;

          return (
            <g
              key={r.period_key || i}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => onHover(r)}
            >
              <rect x={padLeft + i * step} y={padTop} width={step} height={chartH} fill="transparent" />

              <rect
                x={x}
                y={y}
                width={colWidth}
                height={Math.max(2, barH)}
                rx="4"
                ry="4"
                fill={r.is_partial ? 'url(#partialHatch)' : themeColor}
                stroke={r.is_partial ? '#D97706' : themeColor}
                strokeWidth={isHovered ? 2.5 : 1}
                opacity={isHovered ? 1 : 0.88}
                style={{ transition: 'all 0.15s ease' }}
              />

              {n <= 12 && (
                <text
                  x={x + colWidth / 2}
                  y={y - 6}
                  textAnchor="middle"
                  fontSize="10"
                  fontWeight="700"
                  fill={r.is_partial ? '#B45309' : '#1E293B'}
                >
                  {formatCrores(rev)}
                </text>
              )}

              <text
                x={x + colWidth / 2}
                y={padTop + chartH + 18}
                textAnchor={n > 12 ? 'end' : 'middle'}
                transform={n > 12 ? `rotate(-40, ${x + colWidth / 2}, ${padTop + chartH + 18})` : undefined}
                fontSize={n > 15 ? '9.5' : '11'}
                fontWeight={isHovered ? '700' : '500'}
                fill={isHovered ? '#0F172A' : '#64748B'}
              >
                {r.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip Card */}
      <div
        style={{
          marginTop: '0.85rem',
          padding: '0.75rem 1rem',
          borderRadius: '10px',
          backgroundColor: '#FFFFFF',
          border: '1px solid #E2E8F0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          fontSize: '0.82rem',
        }}
      >
        {hoveredPoint ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  padding: '0.2rem 0.5rem',
                  borderRadius: '9999px',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  backgroundColor: themeColor,
                  color: '#FFFFFF',
                }}
              >
                {hoveredPoint.label}
              </span>
              <strong style={{ color: '#1E293B' }}>{hoveredPoint.status_badge || 'Complete'}</strong>
              {hoveredPoint.span_description && <span style={{ color: '#64748B' }}>({hoveredPoint.span_description})</span>}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
              <span>
                Realised Revenue: <strong style={{ color: themeColor }}>{formatExactRevenue(hoveredPoint.total_revenue || hoveredPoint.actual_revenue)}</strong>
              </span>
              <span>
                Orders: <strong>{formatExactCount(hoveredPoint.order_count)}</strong>
              </span>
              {hoveredPoint.avg_order_value != null && (
                <span>
                  AOV: <strong style={{ color: '#059669' }}>{formatExactAOV(hoveredPoint.avg_order_value)}</strong>
                </span>
              )}
            </div>
          </>
        ) : (
          <span style={{ color: '#94A3B8', fontStyle: 'italic' }}>
            Tip: Hover over any column to inspect delivered revenue, order volume, and AOV.
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Grouped Bar Chart for 2D Year x Quarter Pivot Matrix.
 */
function PivotGroupedBarChart({ matrixRows }) {
  if (!matrixRows || matrixRows.length === 0) return null;

  const quarters = ['Q1', 'Q2', 'Q3', 'Q4'];
  const colors = { '2024': '#D97706', '2025': '#7C3AED', '2026': '#0891B2' };

  let maxVal = 1;
  matrixRows.forEach((row) => {
    quarters.forEach((q) => {
      const v = row.cells?.[q]?.revenue || 0;
      if (v > maxVal) maxVal = v;
    });
  });
  maxVal *= 1.15;

  const chartW = 900;
  const chartH = 200;
  const padLeft = 60;
  const padRight = 30;
  const padTop = 20;
  const padBottom = 35;
  const plotW = chartW - padLeft - padRight;
  const groupW = plotW / 4;
  const barW = groupW / 4;

  return (
    <div>
      <svg viewBox={`0 0 ${chartW} ${chartH + padTop + padBottom}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {/* Horizontal grid lines */}
        {[0, 0.33, 0.66, 1.0].map((frac, i) => {
          const y = padTop + chartH * (1 - frac);
          return (
            <g key={i}>
              <line x1={padLeft} y1={y} x2={chartW - padRight} y2={y} stroke="#E2E8F0" strokeDasharray="3 3" />
              <text x={padLeft - 8} y={y + 3} textAnchor="end" fontSize="10" fill="#64748B" fontWeight="600">
                {formatCrores(maxVal * frac)}
              </text>
            </g>
          );
        })}

        {/* Grouped Bars per Quarter */}
        {quarters.map((q, qIdx) => {
          const groupX = padLeft + qIdx * groupW;
          return (
            <g key={q}>
              {matrixRows.map((row, rIdx) => {
                const cell = row.cells?.[q];
                const rev = cell?.revenue || 0;
                const barH = cell?.recorded ? (rev / maxVal) * chartH : 0;
                const x = groupX + rIdx * (barW + 4) + 12;
                const y = padTop + chartH - barH;

                return (
                  <g key={row.year}>
                    <rect
                      x={x}
                      y={y}
                      width={barW}
                      height={Math.max(cell?.recorded ? 2 : 0, barH)}
                      rx="3"
                      ry="3"
                      fill={cell?.recorded ? colors[row.year] || '#7C3AED' : '#F1F5F9'}
                      opacity={cell?.recorded ? 0.88 : 0.3}
                    />
                    {cell?.recorded && barH > 15 && (
                      <text
                        x={x + barW / 2}
                        y={y - 5}
                        textAnchor="middle"
                        fontSize="9"
                        fontWeight="700"
                        fill="#334155"
                      >
                        {formatCrores(rev)}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* Group X Axis Label */}
              <text
                x={groupX + groupW / 2}
                y={padTop + chartH + 20}
                textAnchor="middle"
                fontSize="12"
                fontWeight="700"
                fill="#1E293B"
              >
                {q}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '1.5rem', marginTop: '0.75rem', fontSize: '0.78rem' }}>
        {matrixRows.map((row) => (
          <div key={row.year} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ display: 'inline-block', width: '12px', height: '12px', backgroundColor: colors[row.year], borderRadius: '3px' }} />
            <strong style={{ color: '#1E293B' }}>Year {row.year}</strong>
            <span style={{ color: '#64748B' }}>({row.is_partial ? 'Partial' : 'Full Year'})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Line Chart with Simple Moving Average (SMA-3) for Trend Analysis.
 */
function TrendLineSMAChart({ records }) {
  if (!records || records.length === 0) return null;

  const chartW = 920;
  const chartH = 220;
  const padLeft = 65;
  const padRight = 30;
  const padTop = 25;
  const padBottom = 45;
  const plotW = chartW - padLeft - padRight;
  const step = plotW / (records.length - 1 || 1);

  const maxRev = Math.max(...records.map((r) => r.actual_revenue || 0)) * 1.15 || 1;

  // Build points for actual revenue line
  const revPoints = records.map((r, i) => {
    const x = padLeft + i * step;
    const y = padTop + chartH - ((r.actual_revenue || 0) / maxRev) * chartH;
    return { x, y, record: r };
  });

  // Build points for SMA-3 line (only where sma_3 is not null)
  const smaPoints = records
    .map((r, i) => {
      if (r.sma_3 == null) return null;
      const x = padLeft + i * step;
      const y = padTop + chartH - (r.sma_3 / maxRev) * chartH;
      return { x, y, record: r };
    })
    .filter(Boolean);

  const revPathStr = revPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const smaPathStr = smaPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

  return (
    <div>
      <svg viewBox={`0 0 ${chartW} ${chartH + padTop + padBottom}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1.0].map((frac, i) => {
          const y = padTop + chartH * (1 - frac);
          return (
            <g key={i}>
              <line x1={padLeft} y1={y} x2={chartW - padRight} y2={y} stroke="#E2E8F0" strokeDasharray="3 3" />
              <text x={padLeft - 8} y={y + 3} textAnchor="end" fontSize="10" fill="#64748B" fontWeight="600">
                {formatCrores(maxRev * frac)}
              </text>
            </g>
          );
        })}

        {/* SMA-3 Line (Orange Dashed) */}
        {smaPathStr && (
          <path d={smaPathStr} fill="none" stroke="#F59E0B" strokeWidth="2.5" strokeDasharray="5 3" />
        )}

        {/* Actual Revenue Line (Blue Solid) */}
        <path d={revPathStr} fill="none" stroke="#2563EB" strokeWidth="2.5" />

        {/* Dots on Actual Line */}
        {revPoints.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r={p.record.is_partial ? 5 : 3.5}
            fill={p.record.is_partial ? '#D97706' : '#2563EB'}
            stroke="#FFFFFF"
            strokeWidth="1.5"
          />
        ))}

        {/* X Axis Labels */}
        {records.map((r, i) => {
          const x = padLeft + i * step;
          return (
            <text
              key={r.period_key}
              x={x}
              y={padTop + chartH + 18}
              textAnchor="end"
              transform={`rotate(-40, ${x}, ${padTop + chartH + 18})`}
              fontSize="9"
              fill={r.is_partial ? '#D97706' : '#64748B'}
              fontWeight={r.is_partial ? '700' : '500'}
            >
              {r.label}
            </text>
          );
        })}
      </svg>
    </div>
  );
}
