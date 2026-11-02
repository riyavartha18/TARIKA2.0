import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getClvCustomers } from '../../services/api';
import { Search, X, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';

// Shared palette tokens (kept in sync with AdminClvView).
const PALETTE = {
  ink: '#1F191B', muted: '#6B5E63', faint: '#9E8F94',
  rose: '#D8727E', roseDeep: '#B8505E', border: '#F0E2E0',
  panel: '#FAF7F5', label: '#6B5E63',
};

const PAGE_SIZE = 50;

const trimZeros = (s) => (s.includes('.') ? s.replace(/\.?0+$/, '').replace(/\.$/, '') : s);
const formatCompact = (value) => {
  if (value === null || value === undefined) return null; // handled as badge
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${trimZeros((n / 1e7).toFixed(2))} Cr`;
  if (abs >= 1e5) return `₹${trimZeros((n / 1e5).toFixed(2))} L`;
  if (abs >= 1e3) return `₹${trimZeros((n / 1e3).toFixed(2))} K`;
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
};
const exactMoney = (value) =>
  `₹${Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const useDebounced = (value, delay = 350) => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
};

// Windowed page numbers: always show 1, gap, window around current, gap, last.
function pageWindow(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const items = [1];
  if (current > 3) items.push('gap-start');
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let p = start; p <= end; p += 1) items.push(p);
  if (current < total - 2) items.push('gap-end');
  items.push(total);
  return items;
}

function PaginationBar({ page, totalPages, count, onChange }) {
  const btnStyle = (enabled) => ({
    border: `1px solid ${PALETTE.border}`,
    background: '#fff',
    borderRadius: 8,
    padding: '0.35rem 0.55rem',
    cursor: enabled ? 'pointer' : 'not-allowed',
    opacity: enabled ? 1 : 0.4,
    color: PALETTE.muted,
    display: 'flex',
    alignItems: 'center',
    fontFamily: 'inherit',
  });
  const numStyle = (active) => ({
    border: `1px solid ${active ? PALETTE.rose : PALETTE.border}`,
    background: active ? PALETTE.roseDeep : '#fff',
    color: active ? '#fff' : PALETTE.muted,
    borderRadius: 8,
    padding: '0.35rem 0.6rem',
    cursor: active ? 'default' : 'pointer',
    fontSize: '0.8rem',
    fontWeight: 700,
    fontFamily: 'inherit',
    minWidth: 32,
    textAlign: 'center',
  });
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.3rem', marginTop: '0.8rem', flexWrap: 'wrap' }}>
      <button type="button" aria-label="Previous page" onClick={() => onChange(Math.max(1, page - 1))} disabled={page <= 1} style={btnStyle(page > 1)}>
        <ChevronLeft size={15} />
      </button>
      {pageWindow(page, totalPages).map((item) =>
        typeof item === 'number' ? (
          <button key={item} type="button" onClick={() => onChange(item)} aria-current={item === page ? 'page' : undefined} style={numStyle(item === page)}>{item}</button>
        ) : (
          <span key={item} style={{ color: PALETTE.faint, fontSize: '0.8rem', padding: '0 0.15rem' }}>…</span>
        )
      )}
      <button type="button" aria-label="Next page" onClick={() => onChange(Math.min(totalPages, page + 1))} disabled={page >= totalPages} style={btnStyle(page < totalPages)}>
        <ChevronRight size={15} />
      </button>
      <span style={{ color: PALETTE.muted, fontSize: '0.8rem', marginLeft: '0.3rem' }}>
        Page {page} of {totalPages}
      </span>
    </div>
  );
}

// Full-screen popup listing the ACTUAL customers behind one clicked bar of
// the Customer Value Distribution chart, or behind a tier button click.
// Shows Customer ID, Customer Name, Future CLV (₹) and Historical CLV (₹).
// Supports search by name/ID, server-side pagination (50/page),
// numbered pages with Previous/Next arrows, and a close button.
// No per-row action button — clicking a row opens the customer detail popup.
export default function ClvCustomersModal({ token, category, onClose, onOpenDetail }) {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ count: 0, page: 1, total_pages: 1 });
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('historical_clv');
  const [dir, setDir] = useState('desc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestSeq = useRef(0);

  const search = useDebounced(searchInput.trim(), 350);
  useEffect(() => { setPage(1); }, [search, sort, dir, category]);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    const res = await getClvCustomers(token, {
      page,
      page_size: PAGE_SIZE,
      search,
      sort,
      dir,
      tier: category.tier || undefined,
      segment: category.segment || undefined,
    });
    if (seq !== requestSeq.current) return;
    if (res.success) {
      setRows(res.results || []);
      setMeta({ count: res.count || 0, page: res.page || 1, total_pages: res.total_pages || 1 });
      setError(null);
    } else {
      setError(res.error);
    }
    setLoading(false);
  }, [token, category, page, search, sort, dir]);

  useEffect(() => { load(); }, [load]);

  const toggleSort = (field) => {
    if (sort === field) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSort(field); setDir('asc'); }
  };

  const columns = [
    { key: 'customer_id', label: 'Customer ID', sortable: true },
    { key: 'customer_name', label: 'Customer Name', sortable: true },
    { key: 'future_clv', label: 'Future CLV (₹)', sortable: true, money: true },
    { key: 'historical_clv', label: 'Historical CLV (₹)', sortable: true, money: true },
  ];

  // Derive a friendly title for the modal header.
  const tierLabel = category.label || (category.tier ? category.tier : 'Customers');

  return createPortal(
    <div
      id="clv-category-modal-overlay"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        backgroundColor: 'rgba(31,25,27,0.52)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 3000, padding: '1rem',
        backdropFilter: 'blur(2px)',
        animation: 'clv-modal-in 0.22s cubic-bezier(0.22,1,0.36,1)',
      }}
    >
      <style>{`
        @keyframes clv-modal-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes clv-panel-in { from { opacity: 0; transform: scale(0.97) translateY(12px); } to { opacity: 1; transform: none; } }
        @keyframes rfm-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @keyframes spin { to { transform: rotate(360deg); } }
        .clv-modal-row:hover { background: rgba(216,114,126,0.05) !important; }
      `}</style>
      <div
        id="clv-category-modal-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: '#fff',
          borderRadius: 20,
          maxWidth: 980,
          width: '100%',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          boxShadow: '0 24px 80px rgba(31,25,27,0.22)',
          overflow: 'hidden',
          animation: 'clv-panel-in 0.28s cubic-bezier(0.22,1,0.36,1)',
        }}
      >
        {/* Modal header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1.2rem 1.5rem 1rem',
          borderBottom: `1px solid ${PALETTE.border}`,
          flexShrink: 0, gap: '1rem', flexWrap: 'wrap',
        }}>
          <div>
            <h3 style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.15rem', fontWeight: 700,
              color: PALETTE.ink, margin: '0 0 0.2rem',
              letterSpacing: '-0.01em',
            }}>
              {tierLabel} Customers
            </h3>
            <p style={{ margin: 0, fontSize: '0.75rem', color: PALETTE.faint }}>
              {Number(meta.count).toLocaleString('en-IN')} customers in this tier · {PAGE_SIZE} per page
            </p>
          </div>

          {/* Search box */}
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <Search size={14} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: PALETTE.faint }} />
            <input
              id="clv-category-modal-search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by name or ID…"
              style={{
                border: `1px solid ${PALETTE.border}`,
                borderRadius: 10,
                padding: '0.48rem 0.75rem 0.48rem 1.9rem',
                fontSize: '0.85rem',
                width: 220,
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Close button */}
          <button
            type="button"
            id="clv-category-modal-close"
            onClick={onClose}
            aria-label="Close tier customers popup"
            style={{
              border: `1px solid ${PALETTE.border}`,
              background: '#fff',
              borderRadius: 10,
              padding: '0.4rem 0.5rem',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: PALETTE.muted,
              transition: 'background 0.15s',
              flexShrink: 0,
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 1.5rem 1.4rem' }}>
          {error && <div style={{ color: '#B3261E', fontSize: '0.85rem', margin: '0.8rem 0 0' }}>{error}</div>}

          <div style={{ overflowX: 'auto', border: `1px solid ${PALETTE.border}`, borderRadius: 14, marginTop: '1rem' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#FBF5F4' }}>
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      onClick={() => col.sortable && toggleSort(col.key)}
                      style={{
                        padding: '0.7rem 0.9rem',
                        textAlign: 'left',
                        color: PALETTE.muted,
                        fontWeight: 700,
                        cursor: col.sortable ? 'pointer' : 'default',
                        whiteSpace: 'nowrap',
                        userSelect: 'none',
                      }}
                    >
                      {col.label}{col.sortable && sort === col.key ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!loading && rows.map((r) => (
                  <tr
                    key={r.customer_id}
                    className="clv-modal-row"
                    onClick={() => onOpenDetail && onOpenDetail(r.customer_id)}
                    title="Click for this customer's full details"
                    style={{
                      borderTop: `1px solid ${PALETTE.border}`,
                      cursor: 'pointer',
                      opacity: loading ? 0.55 : 1,
                      transition: 'background 0.12s',
                    }}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        title={col.money && r[col.key] != null ? exactMoney(r[col.key]) : undefined}
                        style={{ padding: '0.65rem 0.9rem', color: PALETTE.ink, whiteSpace: 'nowrap' }}
                      >
                        {col.money
                          ? (r[col.key] == null
                            ? <span style={{ color: PALETTE.faint, fontWeight: 600, fontSize: '0.78rem' }}>Insufficient Data</span>
                            : formatCompact(r[col.key]))
                          : (r[col.key] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            {loading && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', padding: '1rem' }}>
                {[...Array(8)].map((_, i) => (
                  <div key={i} style={{ height: 20, borderRadius: 8, background: 'linear-gradient(90deg,#F5ECEC 25%,#FBF5F4 50%,#F5ECEC 75%)', backgroundSize: '200% 100%', animation: 'rfm-shimmer 1.2s infinite' }} />
                ))}
              </div>
            )}
            {!loading && rows.length === 0 && (
              <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint, fontSize: '0.85rem' }}>
                No customers found.
              </div>
            )}
          </div>

          <PaginationBar page={meta.page} totalPages={meta.total_pages} count={meta.count} onChange={setPage} />
        </div>
      </div>
    </div>,
    document.body,
  );
}
