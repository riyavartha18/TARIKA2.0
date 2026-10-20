import React, { useState, useEffect, useMemo } from 'react';
import { getStockToBeOrdered } from '../../services/api';
import './StockToBeOrdered.css';

/* ─────────────────────────────────────────────
   Skeleton row for loading state
───────────────────────────────────────────── */
function SkeletonRows({ count = 8 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <tr key={i} className="stbo-skeleton-tr">
          <td className="stbo-td stbo-td-rank"><span className="stbo-skel stbo-skel-sm" /></td>
          <td className="stbo-td stbo-td-name"><span className="stbo-skel stbo-skel-lg" /></td>
          <td className="stbo-td stbo-td-variant"><span className="stbo-skel stbo-skel-sm" /></td>
          <td className="stbo-td stbo-td-variant"><span className="stbo-skel stbo-skel-sm" /></td>
          <td className="stbo-td stbo-td-num"><span className="stbo-skel stbo-skel-sm" /></td>
          <td className="stbo-td stbo-td-num"><span className="stbo-skel stbo-skel-sm" /></td>
          <td className="stbo-td stbo-td-num"><span className="stbo-skel stbo-skel-sm" /></td>
        </tr>
      ))}
    </>
  );
}

/* ─────────────────────────────────────────────
   Sortable column header
───────────────────────────────────────────── */
function SortableTh({ label, sortKey, current, dir, onSort }) {
  const isActive = current === sortKey;
  return (
    <th
      className={`stbo-th stbo-th-sortable${isActive ? ' stbo-th-active' : ''}`}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {isActive && <span className="stbo-sort-arrow">{dir === 'asc' ? ' ↑' : ' ↓'}</span>}
    </th>
  );
}

/* ─────────────────────────────────────────────
   Main component — auto-loads on mount
───────────────────────────────────────────── */
const ITEMS_PER_PAGE = 25;

export default function StockToBeOrdered({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Search
  const [search, setSearch] = useState('');

  // Sort
  const [sortKey, setSortKey] = useState('need_to_order');
  const [sortDir, setSortDir] = useState('desc');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);

  /* ── Auto-load on mount ────────────────────── */
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      const result = await getStockToBeOrdered(token);

      if (cancelled) return;

      setLoading(false);
      if (!result.success) {
        setError(result.error || 'Failed to load forecast.');
      } else {
        setData(result);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [token]); // Only re-run if token changes (i.e. login)

  /* ── Filtered + sorted product list ─────────── */
  const filtered = useMemo(() => {
    if (!data?.products) return [];
    let rows = [...data.products];

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter(p => (p.product_name || '').toLowerCase().includes(q));
    }

    rows.sort((a, b) => {
      let aVal = a[sortKey] ?? 0;
      let bVal = b[sortKey] ?? 0;
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();
      return sortDir === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });

    return rows;
  }, [data, search, sortKey, sortDir]);

  /* ── Pagination ────────────────────────────── */
  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const paged = filtered.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE,
  );

  /* ── Sort toggle ───────────────────────────── */
  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
    setCurrentPage(1);
  };

  /* ── Search handler ────────────────────────── */
  const handleSearchChange = (e) => {
    setSearch(e.target.value);
    setCurrentPage(1);
  };

  /* ─────────────────────────────────────────────
     RENDER
  ───────────────────────────────────────────── */
  return (
    <div className="stbo-wrapper">

      {/* ── Page Header ──────────────────────────── */}
      <div className="stbo-page-header">
        <div className="stbo-page-header-left">
          <div className="stbo-header-icon-wrap">
            <span className="stbo-header-icon">📦</span>
          </div>
          <div>
            <h2 className="stbo-title">Stock to Be Ordered</h2>
            {data && !loading && (
              <p className="stbo-subtitle">
                Forecast for:{' '}
                <strong className="stbo-forecast-month">{data.forecast_month_label}</strong>
              </p>
            )}
            {loading && <p className="stbo-subtitle">Loading forecast…</p>}
          </div>
        </div>

        {/* Right-side controls: Search */}
        <div className="stbo-header-right">
          {data && !loading && (
            <div className="stbo-search-wrap">
              <span className="stbo-search-icon">🔍</span>
              <input
                id="stbo-search"
                type="text"
                placeholder="Search product…"
                value={search}
                onChange={handleSearchChange}
                className="stbo-search-input"
              />
            </div>
          )}
        </div>
      </div>

      {/* ── Error ──────────────────────────────── */}
      {error && (
        <div className="stbo-error">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* ── Table ──────────────────────────────── */}
      <div className="stbo-table-card">
        <div className="stbo-table-wrap">
          <table className="stbo-table">
            <thead>
              <tr>
                <th className="stbo-th stbo-th-rank">#</th>
                <SortableTh label="Product" sortKey="product_name" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortableTh label="Color" sortKey="color" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortableTh label="Size" sortKey="size" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortableTh label="Current Stock" sortKey="current_stock" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortableTh label="Predicted Demand" sortKey="predicted_demand" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortableTh label="Need to Order" sortKey="need_to_order" current={sortKey} dir={sortDir} onSort={toggleSort} />
              </tr>
            </thead>
            <tbody>
              {loading && <SkeletonRows count={10} />}

              {!loading && paged.map((p, idx) => {
                const rowNum = (currentPage - 1) * ITEMS_PER_PAGE + idx + 1;
                const needsOrder = p.need_to_order > 0;
                return (
                  <tr key={p.product_key ?? p.product_id} className={`stbo-row${needsOrder ? ' stbo-row-urgent' : ''}`}>
                    <td className="stbo-td stbo-td-rank">{rowNum}</td>
                    <td className="stbo-td stbo-td-name">{p.product_name}</td>
                    <td className="stbo-td stbo-td-variant">{p.color || '—'}</td>
                    <td className="stbo-td stbo-td-variant">{p.size || '—'}</td>
                    <td className="stbo-td stbo-td-num">
                      <span className="stbo-stock-num">{p.current_stock}</span>
                    </td>
                    <td className="stbo-td stbo-td-num">
                      <span className="stbo-demand-num">{p.predicted_demand}</span>
                    </td>
                    <td className="stbo-td stbo-td-num">
                      {needsOrder ? (
                        <span className="stbo-order-badge stbo-order-needed">{p.need_to_order}</span>
                      ) : (
                        <span className="stbo-order-badge stbo-order-ok">0</span>
                      )}
                    </td>
                  </tr>
                );
              })}

              {!loading && !error && data && filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="stbo-empty-row">
                    {search ? 'No products match your search.' : 'No forecast data available.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Footer: count + pagination ─────────── */}
        {!loading && data && filtered.length > 0 && (
          <div className="stbo-table-footer">
            <span className="stbo-footer-count">
              {filtered.length} product{filtered.length !== 1 ? 's' : ''}
              {search && ` matching "${search}"`}
            </span>

            {totalPages > 1 && (
              <div className="stbo-pagination">
                <button
                  className="stbo-page-btn"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1}
                >«</button>
                <button
                  className="stbo-page-btn"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >‹</button>
                <span className="stbo-page-info">
                  {currentPage} / {totalPages}
                </span>
                <button
                  className="stbo-page-btn"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >›</button>
                <button
                  className="stbo-page-btn"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage === totalPages}
                >»</button>
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
