import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getStockToBeOrdered } from '../../services/api';
import './StockToBeOrdered.css';

/* ─────────────────────────────────────────────
   Skeleton card for loading state
───────────────────────────────────────────── */
function SkeletonCards({ count = 8 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="stbo-pcard stbo-pcard-skeleton">
          <div className="stbo-skel stbo-skel-img" />
          <div className="stbo-pcard-body">
            <div className="stbo-skel stbo-skel-lg" />
            <div className="stbo-skel stbo-skel-sm" />
            <div className="stbo-skel stbo-skel-md" />
          </div>
        </div>
      ))}
    </>
  );
}

/* Demand + priority indicators — readable labels, not colour alone. */
const TIER_META = {
  High: { label: 'High demand', bg: '#ECFDF5', fg: '#059669', border: '#A7F3D0' },
  Medium: { label: 'Medium demand', bg: '#FFFBEB', fg: '#D97706', border: '#FDE68A' },
  Low: { label: 'Low demand', bg: '#FEF2F2', fg: '#DC2626', border: '#FCA5A5' },
};

const PRIORITY_META = {
  Urgent: { label: 'Urgent', icon: '🔴', bg: '#FEF2F2', fg: '#DC2626', border: '#FCA5A5', accent: '#DC2626' },
  Soon: { label: 'Soon', icon: '🟠', bg: '#FFFBEB', fg: '#D97706', border: '#FDE68A', accent: '#D97706' },
  'Low Priority': { label: 'Low priority', icon: '🟢', bg: '#ECFDF5', fg: '#059669', border: '#A7F3D0', accent: '#059669' },
};

function Pill({ bg, fg, border, children }) {
  return (
    <span className="stbo-pill" style={{ backgroundColor: bg, color: fg, borderColor: border }}>
      {children}
    </span>
  );
}

/* ─────────────────────────────────────────────
   Summary card (counts from live data)
───────────────────────────────────────────── */
function SummaryCard({ icon, label, value, sub, accent }) {
  return (
    <div className="stbo-summary-card" style={{ borderTop: `3px solid ${accent}` }}>
      <div className="stbo-summary-icon" style={{ backgroundColor: `${accent}1A`, color: accent }}>{icon}</div>
      <div>
        <div className="stbo-summary-value" style={{ color: accent }}>{value.toLocaleString('en-IN')}</div>
        <div className="stbo-summary-label">{label}</div>
        {sub && <div className="stbo-summary-sub">{sub}</div>}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main component — server-paged, loads on mount
───────────────────────────────────────────── */
const PAGE_SIZE = 12;

const SORT_OPTIONS = [
  { value: 'priority', label: 'Restock priority' },
  { value: 'need_to_order', label: 'Recommended order qty' },
  { value: 'predicted_demand', label: 'Predicted demand' },
  { value: 'current_stock', label: 'Current stock' },
  { value: 'product_name', label: 'Product name' },
];

export default function StockToBeOrdered({ token }) {
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: PAGE_SIZE, total_filtered: 0, total_pages: 1 });
  const [summary, setSummary] = useState({});
  const [forecastLabel, setForecastLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  const [sortKey, setSortKey] = useState('priority');
  const [sortDir, setSortDir] = useState('desc');
  const [page, setPage] = useState(1);

  const searchTimer = useRef(null);
  useEffect(() => {
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(searchTimer.current);
  }, [search]);

  // Reset to first page whenever a filter/sort changes.
  useEffect(() => { setPage(1); }, [tierFilter, sortKey, sortDir]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await getStockToBeOrdered(token, {
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch,
      demand_tier: tierFilter,
      sort: sortKey,
      dir: sortDir,
    });
    if (result.success) {
      setRows(result.products || []);
      setPagination(result.pagination || pagination);
      setSummary(result.summary || {});
      setForecastLabel(result.forecast_month_label || '');
    } else {
      setError(result.error || 'Failed to load forecast.');
    }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, page, debouncedSearch, tierFilter, sortKey, sortDir]);

  useEffect(() => { load(); }, [load]);

  const totals = summary.tier_counts || {};
  const needsReplenishment = summary.needs_replenishment ?? 0;
  const urgent = summary.urgent ?? 0;
  const highDemand = summary.high_demand ?? (totals.High || 0);
  const lowOrZero = summary.low_or_zero_stock ?? 0;
  const zeroStock = summary.zero_stock ?? 0;

  return (
    <div className="stbo-wrapper">

      {/* ── Page Header ──────────────────────────── */}
      <div className="stbo-page-header">
        <div className="stbo-page-header-left">
          <div className="stbo-header-icon-wrap"><span className="stbo-header-icon">📦</span></div>
          <div>
            <h2 className="stbo-title">Stock to Be Ordered</h2>
            <p className="stbo-subtitle">
              Demand-driven replenishment, synchronised with Demand Forecasting
              {forecastLabel && <> · <strong className="stbo-forecast-month">{forecastLabel}</strong></>}
            </p>
          </div>
        </div>
        <div className="stbo-header-right">
          <div className="stbo-search-wrap">
            <span className="stbo-search-icon">🔍</span>
            <input
              id="stbo-search"
              type="text"
              placeholder="Search product or category…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="stbo-search-input"
            />
          </div>
        </div>
      </div>

      {/* ── Summary Cards ────────────────────────── */}
      <div className="stbo-summary-grid">
        <SummaryCard icon="🛒" accent="#B8505E"
          label="Needs Replenishment" value={needsReplenishment}
          sub={`${summary.total_need_to_order ? summary.total_need_to_order.toLocaleString('en-IN') : 0} units to order in total`} />
        <SummaryCard icon="🔴" accent="#DC2626"
          label="Urgent Restocking" value={urgent}
          sub="High demand or out of stock" />
        <SummaryCard icon="📈" accent="#059669"
          label="High-Demand Products" value={highDemand}
          sub={`of ${summary.total_products ? summary.total_products.toLocaleString('en-IN') : 0} catalog items`} />
        <SummaryCard icon="📦" accent="#D97706"
          label="Low or Zero Stock" value={lowOrZero}
          sub={`${zeroStock.toLocaleString('en-IN')} completely out of stock`} />
      </div>

      {/* ── Controls: tier filter + sort ─────────── */}
      <div className="stbo-controls">
        <div className="stbo-tier-pills">
          {['ALL', 'High', 'Medium', 'Low'].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setTierFilter(lvl)}
              className={`stbo-tier-pill${tierFilter === lvl ? ' stbo-tier-pill-active' : ''}`}
            >
              {lvl === 'ALL' ? 'All demand' : `${lvl} demand`}
            </button>
          ))}
        </div>

        <div className="stbo-sort-controls">
          <label className="stbo-sort-label" htmlFor="stbo-sort">Sort by</label>
          <select
            id="stbo-sort"
            className="stbo-sort-select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
          >
            {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button className="stbo-dir-btn" onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}>
            {sortDir === 'asc' ? 'Ascending ↑' : 'Descending ↓'}
          </button>
        </div>
      </div>

      {/* ── Error ──────────────────────────────── */}
      {error && (
        <div className="stbo-error">
          <span>⚠️</span><span>{error}</span>
        </div>
      )}

      {/* ── Product Cards ──────────────────────── */}
      {!error && (
        <div className="stbo-cards-grid">
          {loading && <SkeletonCards count={8} />}

          {!loading && rows.map((p) => {
            const tier = TIER_META[p.demand_tier] || TIER_META.Medium;
            const prio = PRIORITY_META[p.priority] || PRIORITY_META['Low Priority'];
            const orderNeeded = p.need_to_order > 0;
            return (
              <div key={p.product_key ?? p.product_id} className="stbo-pcard" style={{ borderTop: `3px solid ${prio.accent}` }}>
                <div className="stbo-pcard-media">
                  {p.image ? (
                    <img
                      src={p.image}
                      alt={p.product_name}
                      loading="lazy"
                      className="stbo-pcard-img"
                      onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }}
                    />
                  ) : (
                    <div className="stbo-pcard-img stbo-pcard-img-ph">🖼️</div>
                  )}
                  <div className="stbo-pcard-badges">
                    <Pill bg={tier.bg} fg={tier.fg} border={tier.border}>{tier.label}</Pill>
                    <Pill bg={prio.bg} fg={prio.fg} border={prio.border}>{prio.icon} {prio.label}</Pill>
                  </div>
                </div>

                <div className="stbo-pcard-body">
                  <div className="stbo-pcard-name" title={p.product_name}>{p.product_name}</div>
                  <div className="stbo-pcard-cat">{p.category_name}{p.sub_category ? ` · ${p.sub_category}` : ''}</div>

                  <div className="stbo-stats">
                    <div className="stbo-stat">
                      <span className="stbo-stat-label">Current stock</span>
                      <span className="stbo-stat-value" style={{ color: p.current_stock <= 0 ? '#DC2626' : '#1F191B' }}>
                        {p.current_stock.toLocaleString('en-IN')} units
                      </span>
                    </div>
                    <div className="stbo-stat">
                      <span className="stbo-stat-label">Predicted demand</span>
                      <span className="stbo-stat-value">{p.predicted_demand.toLocaleString('en-IN')} units</span>
                    </div>
                    <div className="stbo-stat stbo-stat-order">
                      <span className="stbo-stat-label">Recommended order</span>
                      <span className={`stbo-order-badge ${orderNeeded ? 'stbo-order-needed' : 'stbo-order-ok'}`}>
                        {orderNeeded ? `${p.need_to_order.toLocaleString('en-IN')} units` : 'None'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {!loading && !error && rows.length === 0 && (
            <div className="stbo-empty">
              {search || tierFilter !== 'ALL'
                ? 'No products match your search or filters.'
                : 'No forecast data available.'}
            </div>
          )}
        </div>
      )}

      {/* ── Footer: count + pagination (server-driven) ─────────── */}
      {!loading && pagination.total_filtered > 0 && (
        <div className="stbo-table-footer">
          <span className="stbo-footer-count">
            Showing {rows.length} of {pagination.total_filtered.toLocaleString('en-IN')} products
            {debouncedSearch && ` matching "${debouncedSearch}"`}
            {tierFilter !== 'ALL' && ` · ${tierFilter} demand only`}
          </span>

          {pagination.total_pages > 1 && (
            <div className="stbo-pagination">
              <button className="stbo-page-btn" onClick={() => setPage(1)} disabled={pagination.page <= 1}>«</button>
              <button className="stbo-page-btn" onClick={() => setPage((v) => Math.max(1, v - 1))} disabled={pagination.page <= 1}>‹</button>
              <span className="stbo-page-info">{pagination.page} / {pagination.total_pages}</span>
              <button className="stbo-page-btn" onClick={() => setPage((v) => Math.min(pagination.total_pages, v + 1))} disabled={pagination.page >= pagination.total_pages}>›</button>
              <button className="stbo-page-btn" onClick={() => setPage(pagination.total_pages)} disabled={pagination.page >= pagination.total_pages}>»</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
