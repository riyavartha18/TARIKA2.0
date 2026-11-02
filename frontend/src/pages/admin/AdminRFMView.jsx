import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '../../auth/AuthContext';
import {
  getRfmSummary, getRfmSegmentCustomers, getRfmClusterCustomers,
} from '../../services/api';
import { KMEANS_CATEGORY_META } from '../../data/rfmSegments';
import { ArrowLeft, Search, Loader2, X } from 'lucide-react';

// Light palette kept only for the unchanged "View Customers" detail screen.
const PALETTE = {
  ink: '#1F191B', muted: '#6B5E63', faint: '#9E8F94',
  rose: '#D8727E', roseDeep: '#B8505E', border: '#F0E2E0', bg: '#FFFFFF',
};

// Overview tokens now follow the existing Tarika Admin Dashboard: warm light
// surfaces, charcoal text, muted grey, subtle rose borders and rose/pink bars.
// (The variable name is kept so the layout/animations are untouched.)
const DARK = {
  bg: '#FFFFFF',
  panel: '#FAF7F5',
  text: '#1F191B',
  label: '#6B5E63',
  value: '#1F191B',
  divider: 'rgba(216,114,126,0.15)',
  track: 'rgba(31,25,27,0.06)',
  bar: '#B8505E',
  barSecondary: '#D8727E',
};

const formatMoney = (value) =>
  `₹${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

// "Last clustered 2 Nov 2026, 15:04" for the clustering run stamp, so the page
// always says when the stored labels were actually computed.
const formatStamp = (iso) => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

// Indian compact notation (K / L / Cr) for the big monetary totals; the exact
// rupee amount stays available on hover via the tooltip.
const trimZeros = (s) => (s.includes('.') ? s.replace(/\.?0+$/, '').replace(/\.$/, '') : s);
const formatCompactMoney = (value) => {
  const n = Number(value || 0);
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${trimZeros((n / 1e7).toFixed(2))} Cr`;
  if (abs >= 1e5) return `₹${trimZeros((n / 1e5).toFixed(2))} L`;
  if (abs >= 1e3) return `₹${trimZeros((n / 1e3).toFixed(2))} K`;
  return formatMoney(n);
};
const exactMoney = (value) =>
  `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const useDebounced = (value, delay = 350) => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
};

// Honour the OS "reduce motion" setting so every animation is opt-out.
function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);
  return reduced;
}

// Short, eased count-up used for the overview metric values.
function useCountUp(target, { duration = 700, enabled = true } = {}) {
  const [value, setValue] = useState(enabled ? 0 : target);
  useEffect(() => {
    if (!enabled) { setValue(target); return undefined; }
    let raf;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) raf = requestAnimationFrame(step);
      else setValue(target);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, enabled]);
  return value;
}

function Divider() {
  return <div style={{ height: 1, background: DARK.divider, margin: '1.25rem 0' }} />;
}

// Compact label + medium value metric (no icon, no card decoration). The value
// counts up on load unless the user prefers reduced motion. `title` shows the
// exact amount behind a compact display.
function DarkMetric({ label, value, format, title }) {
  const reduced = usePrefersReducedMotion();
  const animated = useCountUp(Number(value) || 0, { enabled: !reduced });
  const fmt = format || ((v) => Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 }));
  return (
    <div title={title} style={{ padding: '0.2rem 0' }}>
      <div style={{ fontSize: '0.72rem', color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: '1.45rem', fontWeight: 650, color: DARK.value, lineHeight: 1.15, fontVariantNumeric: 'tabular-nums' }}>{fmt(animated)}</div>
    </div>
  );
}

// One horizontal progress-bar row: category name left, "count (pct%)" right,
// rose fill underneath that animates to the cluster's share of the clustered
// buyers on load and transitions smoothly when the data refreshes. Clicking
// opens that cluster's actual customers.
function SegmentBar({ label, count, pct, onClick, color = DARK.bar, index = 0, caution = false }) {
  const reduced = usePrefersReducedMotion();
  const target = Math.min(100, Math.max(0, pct));
  const [width, setWidth] = useState(reduced ? target : 0);
  useEffect(() => {
    if (reduced) { setWidth(target); return undefined; }
    // Deactivate the transition for the reset, then animate to the target so a
    // data refresh eases smoothly instead of jumping.
    const id = requestAnimationFrame(() => setWidth(target));
    return () => cancelAnimationFrame(id);
  }, [target, reduced]);

  const countAnim = useCountUp(Number(count) || 0, { enabled: !reduced });

  return (
    <button
      type="button"
      onClick={onClick}
      className="rfm-bar-row"
      style={{ animationDelay: `${Math.min(index, 8) * 45}ms` }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ fontSize: '0.95rem', color: DARK.text, fontWeight: 500 }}>
          {label}
          {caution && (
            <span style={{ marginLeft: 8, fontSize: '0.66rem', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#8A5A00', backgroundColor: 'rgba(176,138,46,0.14)', borderRadius: 6, padding: '2px 6px', verticalAlign: 'middle' }}>
              label not supported
            </span>
          )}
        </span>
        <span style={{ fontSize: '0.88rem', color: DARK.label, fontVariantNumeric: 'tabular-nums' }}>
          {Math.round(countAnim).toLocaleString('en-IN')} <span style={{ color: '#9E8F94' }}>({pct}%)</span>
        </span>
      </div>
      <div style={{ height: 8, borderRadius: 8, background: DARK.track, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%', width: `${width}%`, background: color, borderRadius: 8,
            transition: reduced ? 'none' : 'width 0.7s cubic-bezier(0.22, 1, 0.36, 1)',
          }}
        />
      </div>
    </button>
  );
}

export default function AdminRFMView({ onBack }) {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // The K-Means cluster whose actual customers are open, and (for the two
  // independent secondary-insight rows) the legacy label being listed.
  const [activeCluster, setActiveCluster] = useState(null);
  const [activeInsight, setActiveInsight] = useState(null);

  const loadSummary = useCallback(async () => {
    const res = await getRfmSummary(token);
    if (res.success) { setSummary(res); setError(null); return res; }
    setError(res.error);
    return null;
  }, [token]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    loadSummary().then(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [loadSummary]);

  // Reading the summary endpoint also nudges the backend to auto-refresh, so
  // there is no Run button. Poll only while a completed snapshot is pending.
  useEffect(() => {
    const needsPoll = !summary?.available || summary?.refreshing;
    if (!needsPoll) return undefined;
    const timer = setInterval(loadSummary, 3000);
    return () => clearInterval(timer);
  }, [summary, loadSummary]);

  if (loading) {
    return (
      <div style={{ backgroundColor: DARK.bg, borderRadius: 20, border: `1px solid ${PALETTE.border}`, boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)', padding: '3rem', textAlign: 'center' }}>
        <Loader2 size={26} color={PALETTE.roseDeep} style={{ animation: 'spin 0.8s linear infinite' }} />
        <p style={{ color: PALETTE.muted, marginTop: '0.8rem' }}>Loading RFM analytics…</p>
      </div>
    );
  }

  const totals = summary?.totals || {};
  const available = summary?.available;
  const buyers = Number(summary?.buyer_count || totals.total_eligible_buyers || 0) || 1;
  const customers = Number(totals.total_customers || 0) || 1;
  const orders = Number(totals.total_eligible_orders || 0);
  const avgFrequency = buyers ? (orders / buyers) : 0;
  const pctOfBuyers = (n) => Math.round((Number(n || 0) / buyers) * 100);
  const pctOfCustomers = (n) => Math.round((Number(n || 0) / customers) * 100);

  return (
    <div style={{ backgroundColor: DARK.bg, borderRadius: 20, padding: '1.6rem 1.8rem', color: DARK.text, border: `1px solid ${PALETTE.border}`, boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)' }}>
      <style>{`
        .rfm-metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.4rem 2.5rem; }
        @media (max-width: 480px) { .rfm-metrics { grid-template-columns: 1fr; } }
        .rfm-bar-row {
          display: block; width: calc(100% + 0.8rem); margin-left: -0.4rem;
          text-align: left; background: transparent; border: none; cursor: pointer;
          padding: 0.5rem 0.4rem; margin-bottom: 0.15rem; border-radius: 10px; font: inherit;
          opacity: 0; animation: rfm-fadein 0.45s ease forwards;
          transition: background 0.18s ease;
        }
        .rfm-bar-row:hover { background: rgba(216,114,126,0.06); }
        .rfm-bar-row:hover span:first-child { color: #B8505E; }
        @keyframes rfm-fadein { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
        @media (prefers-reduced-motion: reduce) {
          .rfm-bar-row { animation: none; opacity: 1; transition: none; }
          .rfm-bar-row > div > div { transition: none !important; }
        }
      `}</style>

      {/* 1. Top overview */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
          {onBack && (
            <button type="button" onClick={onBack} style={{ border: `1px solid ${DARK.divider}`, background: 'transparent', borderRadius: 8, padding: '0.4rem 0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, color: DARK.label, fontSize: '0.78rem' }}>
              <ArrowLeft size={15} /> Back
            </button>
          )}
          <div>
            <h2 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.35rem', fontWeight: 650, color: DARK.value, margin: 0, letterSpacing: '-0.01em' }}>Customer RFM Analysis</h2>
          </div>
        </div>
      </div>

      <Divider />

      {!available ? (
        <div style={{ padding: '2.5rem 0', textAlign: 'center', color: DARK.label }}>
          <Loader2 size={22} color={PALETTE.roseDeep} style={{ animation: 'spin 0.8s linear infinite' }} />
          <p style={{ marginTop: '0.7rem', fontSize: '0.85rem' }}>Preparing your customer segmentation… this updates automatically.</p>
        </div>
      ) : (
        <>
          {/* Four key metrics, clean 2-column layout */}
          <div className="rfm-metrics">
            <DarkMetric label="Total Customers" value={Number(totals.total_customers || 0)} />
            <DarkMetric label="Active Buyers" value={Number(totals.total_eligible_buyers || 0)} />
            <DarkMetric label="Total Monetary Value" value={Number(totals.total_eligible_revenue || 0)} format={(v) => formatCompactMoney(v)} title={exactMoney(totals.total_eligible_revenue)} />
            <DarkMetric label="Average Frequency" value={avgFrequency} format={(v) => v.toFixed(1)} />
          </div>

          <Divider />

          {/* 2. K-Means++ customer segmentation: the page's only segmentation,
              in the same horizontal progress-bar format the old rule-based
              distribution used. Counts, shares and labels all come from the
              stored K-Means++ assignment of the persisted RFM values. */}
          <div style={{ fontSize: '0.95rem', fontWeight: 650, color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: '0.7rem', marginBottom: '0.5rem' }}>
            K-Means customer segmentation (4 clusters)
          </div>
          {(() => {
            const kmeans = summary?.kmeans;
            const clusters = kmeans?.clusters || [];
            if (!kmeans?.available || clusters.length === 0) {
              return (
                <p style={{ margin: '0 0 0.35rem', fontSize: '0.78rem', color: '#9E8F94' }}>
                  No clustering results yet.
                </p>
              );
            }
            const state = kmeans.state || {};
            const stamp = formatStamp(state.completed_at);
            const basis = Number(kmeans.total || buyers);
            return (
              <>
                {clusters.map((c, i) => (
                  <SegmentBar
                    key={`${c.category}-${c.cluster_id}`}
                    index={i}
                    label={c.category}
                    count={c.customer_count}
                    pct={c.percent ?? pctOfBuyers(c.customer_count)}
                    color={(KMEANS_CATEGORY_META[c.category] || {}).color || DARK.barSecondary}
                    caution={c.supported === false}
                    onClick={() => setActiveCluster(c)}
                  />
                ))}
                
                {kmeans.unsupported_categories?.length > 0 && (
                  <p style={{ margin: '0.4rem 0 0', fontSize: '0.74rem', color: '#9E8F94' }}>
                    No cluster maps onto: {kmeans.unsupported_categories.join(', ')}
                  </p>
                )}
                {kmeans.ambiguities?.length > 0 && (
                  <div style={{ marginTop: '0.6rem', fontSize: '0.76rem', color: '#6B5E63', backgroundColor: 'rgba(176,138,46,0.08)', border: '1px solid rgba(176,138,46,0.25)', borderRadius: 10, padding: '0.6rem 0.75rem' }}>
                    <div style={{ fontWeight: 700, marginBottom: 3, color: '#8A5A00' }}>What the data does not support</div>
                    <ul style={{ margin: 0, paddingLeft: '1rem', display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {kmeans.ambiguities.map((text) => (<li key={text}>{text}</li>))}
                    </ul>
                  </div>
                )}
              </>
            );
          })()}

          {/* 3. Secondary insights: independent measures, not clustering results.
              Never Purchased is a population count, not one of the four clusters,
              so it is listed separately with its own denominator. */}
          <div style={{ height: 1, background: DARK.divider, margin: '2rem 0 0.85rem' }} />
          <div style={{ fontSize: '0.95rem', fontWeight: 650, color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.15rem' }}>
            Secondary insights
          </div>
          <SegmentBar
            index={0}
            label="Never Purchased"
            count={totals.never_purchased_customers}
            pct={pctOfCustomers(totals.never_purchased_customers)}
            color={DARK.barSecondary}
            onClick={() => setActiveInsight('Never Purchased')}
          />

          {error && <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#B3261E' }}>{error}</div>}
        </>
      )}

      {/* Clicking a cluster bar opens that cluster's actual customers (the rows
          carrying the latest K-Means assignment), server-side paginated. */}
      {activeCluster && (
        <ClusterCustomersModal
          key={`${activeCluster.category}-${activeCluster.cluster_id}`}
          cluster={activeCluster}
          token={token}
          onClose={() => setActiveCluster(null)}
        />
      )}

      {/* The two independent insight rows still list from the persisted rows. */}
      {activeInsight && (
        <SegmentCustomersModal
          key={activeInsight}
          segment={activeInsight}
          token={token}
          onClose={() => setActiveInsight(null)}
        />
      )}
    </div>
  );
}

// Only identity is shown: the individual Recency / Frequency / Value scores are
// no longer displayed per customer. The cluster membership itself is what the
// list is about, so the row shows the K-Means cluster (id + business category).
const DETAIL_COLUMNS = [
  { key: 'customer_name', label: 'Customer', sortable: false },
  { key: 'customer_id', label: 'Customer ID', sortable: true },
];

// The K-Means cluster drill-down additionally shows each buyer's ORIGINAL
// (unscaled) Recency / Frequency / Monetary, straight from the persisted RFM row
// (never the standardized clustering values). Sort keys match the backend
// SEGMENT_SORT_FIELDS so server-side ordering stays an indexed scan.
const CLUSTER_DETAIL_COLUMNS = [
  { key: 'customer_name', label: 'Customer', sortable: false },
  { key: 'customer_id', label: 'Customer ID', sortable: true },
  { key: 'recency', label: 'Recency (days)', sortable: true },
  { key: 'frequency', label: 'Frequency', sortable: true },
  { key: 'monetary', label: 'Monetary', sortable: true, format: formatMoney },
];

function SkeletonRows() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '1.1rem' }}>
      {[...Array(8)].map((_, i) => (
        <div key={i} className="rfm-skeleton-row" style={{ height: 20, borderRadius: 8, background: 'linear-gradient(90deg,#F5ECEC 25%,#FBF5F4 50%,#F5ECEC 75%)', backgroundSize: '200% 100%' }} />
      ))}
    </div>
  );
}

// Full-screen modal listing the actual customers behind the independent
// secondary-insight row (Never Purchased). It is not a segmentation category but
// a population count, so the list shows the clicked label only and never
// presents an old segment name as a current clustering result. Portal + high
// z-index keep the dashboard hidden.
function SegmentCustomersModal({ segment, token, onClose }) {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ count: 0, page: 1, total_pages: 1 });
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('customer_id');
  const [dir, setDir] = useState('asc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const search = useDebounced(searchInput.trim(), 350);
  const requestSeq = useRef(0);

  useEffect(() => { setPage(1); }, [search, sort, dir]);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    const res = await getRfmSegmentCustomers(token, segment, { page, search, sort, dir });
    if (seq !== requestSeq.current) return; // a newer request already answered
    if (res.success) {
      setRows(res.results || []);
      setMeta({ count: res.count || 0, page: res.page || 1, total_pages: res.total_pages || 1 });
    } else {
      setError(res.error);
    }
    setLoading(false);
  }, [token, segment, page, search, sort, dir]);

  useEffect(() => { load(); }, [load]);

  const toggleSort = (field) => {
    if (sort === field) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSort(field); setDir('asc'); }
  };

  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31,25,27,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 3000, padding: '1rem' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ backgroundColor: '#fff', borderRadius: 18, maxWidth: 860, width: '100%', maxHeight: '85vh', overflowY: 'auto', padding: '1.5rem 1.6rem', position: 'relative' }}>
        <style>{`@keyframes rfm-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} } .rfm-skeleton-row{ animation: rfm-shimmer 1.2s infinite; }`}</style>
        <button type="button" onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: '1rem', right: '1rem', border: 'none', background: 'transparent', cursor: 'pointer', color: PALETTE.faint }}>
          <X size={18} />
        </button>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.8rem', flexWrap: 'wrap', paddingRight: '2rem' }}>
          <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.2rem', color: PALETTE.ink, margin: 0 }}>{segment}</h3>
          <span style={{ color: PALETTE.faint, fontSize: '0.82rem' }}>
            {Number(meta.count).toLocaleString('en-IN')} customers with this label
          </span>
          <div style={{ marginLeft: 'auto', position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: PALETTE.faint }} />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search name or ID…"
              style={{ border: `1px solid ${PALETTE.border}`, borderRadius: 10, padding: '0.5rem 0.75rem 0.5rem 1.8rem', fontSize: '0.85rem', width: 200 }}
            />
          </div>
        </div>

        {error && <div style={{ color: '#B3261E', fontSize: '0.85rem', margin: '0.8rem 0 0' }}>{error}</div>}

        <div style={{ overflowX: 'auto', backgroundColor: '#fff', border: `1px solid ${PALETTE.border}`, borderRadius: 14, marginTop: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#FBF5F4' }}>
                {DETAIL_COLUMNS.map((col) => (
                  <th key={col.key} onClick={() => col.sortable && toggleSort(col.key)} style={{ padding: '0.7rem 0.9rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700, cursor: col.sortable ? 'pointer' : 'default', whiteSpace: 'nowrap' }}>
                    {col.label}{col.sortable && sort === col.key ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}
                  </th>
                ))}
                <th style={{ padding: '0.7rem 0.9rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700 }}>Label</th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? null : rows.map((r) => (
                <tr key={r.customer_id} style={{ borderTop: `1px solid ${PALETTE.border}`, opacity: loading ? 0.55 : 1 }}>
                  {DETAIL_COLUMNS.map((col) => (
                    <td key={col.key} style={{ padding: '0.65rem 0.9rem', color: PALETTE.ink, whiteSpace: 'nowrap' }}>
                      {r[col.key] ?? '—'}
                    </td>
                  ))}
                  <td style={{ padding: '0.65rem 0.9rem' }}>
                    <span style={{ backgroundColor: 'rgba(216,114,126,0.12)', color: PALETTE.roseDeep, borderRadius: 8, padding: '2px 8px', fontSize: '0.74rem', fontWeight: 700 }}>{segment}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {loading && rows.length === 0 && <SkeletonRows />}
          {!loading && rows.length === 0 && (
            <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint, fontSize: '0.85rem' }}>No customers found.</div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.6rem', marginTop: '0.8rem' }}>
          <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={meta.page <= 1} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.4rem 0.8rem', cursor: meta.page <= 1 ? 'not-allowed' : 'pointer', opacity: meta.page <= 1 ? 0.4 : 1 }}>Previous</button>
          <span style={{ color: PALETTE.muted, fontSize: '0.85rem' }}>Page {meta.page} of {meta.total_pages}</span>
          <button type="button" onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))} disabled={meta.page >= meta.total_pages} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.4rem 0.8rem', cursor: meta.page >= meta.total_pages ? 'not-allowed' : 'pointer', opacity: meta.page >= meta.total_pages ? 0.4 : 1 }}>Next</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// Full-screen modal listing the ACTUAL customers of one K-Means cluster. The
// members come from the persisted cluster labels (`/clusters/customers`), always
// one server-side page at a time, so a cluster of ~100k buyers never loads into
// the browser. The header names the cluster (business category + its numeric
// K-Means id) and its total customer count; the rows show Customer name, ID and
// the buyer's original (unscaled) Recency / Frequency / Monetary. Search,
// pagination, a loading state and an explicit back-to-analysis action are
// inside. Opening another bar remounts this component (keyed by category +
// cluster id), so a previous cluster's list can never linger.
function ClusterCustomersModal({ cluster, token, onClose }) {
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ count: cluster.customer_count || 0, page: 1, total_pages: 1 });
  const [searchInput, setSearchInput] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('customer_id');
  const [dir, setDir] = useState('asc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const search = useDebounced(searchInput.trim(), 350);
  const requestSeq = useRef(0);

  useEffect(() => { setPage(1); }, [search, sort, dir]);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);
    const res = await getRfmClusterCustomers(token, cluster.category, {
      cluster_id: cluster.cluster_id, page, search, sort, dir,
    });
    if (seq !== requestSeq.current) return; // a newer request already answered
    if (res.success) {
      setRows(res.results || []);
      setMeta({ count: res.count || 0, page: res.page || 1, total_pages: res.total_pages || 1 });
    } else {
      setError(res.error);
    }
    setLoading(false);
  }, [token, cluster.category, cluster.cluster_id, page, search, sort, dir]);

  useEffect(() => { load(); }, [load]);

  const toggleSort = (field) => {
    if (sort === field) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSort(field); setDir('asc'); }
  };

  const chip = (text) => (
    <span style={{ backgroundColor: 'rgba(216,114,126,0.12)', color: PALETTE.roseDeep, borderRadius: 8, padding: '2px 8px', fontSize: '0.74rem', fontWeight: 700 }}>{text}</span>
  );

  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31,25,27,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 3000, padding: '1rem' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ backgroundColor: '#fff', borderRadius: 18, maxWidth: 860, width: '100%', maxHeight: '85vh', overflowY: 'auto', padding: '1.5rem 1.6rem', position: 'relative' }}>
        <style>{`@keyframes rfm-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} } .rfm-skeleton-row{ animation: rfm-shimmer 1.2s infinite; }`}</style>
        <button type="button" onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: '1rem', right: '1rem', border: 'none', background: 'transparent', cursor: 'pointer', color: PALETTE.faint }}>
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', paddingRight: '2rem' }}>
          <button type="button" onClick={onClose} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.35rem 0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, color: PALETTE.muted, fontSize: '0.75rem' }}>
            <ArrowLeft size={14} /> Back to RFM analysis
          </button>
          <div style={{ marginLeft: 'auto', position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: PALETTE.faint }} />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search name or ID…"
              aria-label="Search customers"
              style={{ border: `1px solid ${PALETTE.border}`, borderRadius: 10, padding: '0.5rem 0.75rem 0.5rem 1.8rem', fontSize: '0.85rem', width: 200 }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.8rem', flexWrap: 'wrap', marginTop: '0.9rem' }}>
          <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.2rem', color: PALETTE.ink, margin: 0 }}>{cluster.category}</h3>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {chip(`${Number(meta.count).toLocaleString('en-IN')} customers`)}
            {cluster.percent != null && chip(`${cluster.percent}% of eligible buyers`)}
          </span>
        </div>

        {cluster.cautions?.length > 0 && (
          <div style={{ marginTop: '0.7rem', fontSize: '0.76rem', color: '#6B5E63', backgroundColor: 'rgba(176,138,46,0.08)', border: '1px solid rgba(176,138,46,0.25)', borderRadius: 10, padding: '0.55rem 0.7rem' }}>
            <div style={{ fontWeight: 700, marginBottom: 2, color: '#8A5A00' }}>The “{cluster.category}” label is not fully supported by this cluster</div>
            {cluster.cautions.map((text) => (<div key={text}>{text}</div>))}
          </div>
        )}

        {loading && rows.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.9rem 0 0', color: PALETTE.muted, fontSize: '0.8rem' }}>
            <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite' }} /> Loading customers in this cluster…
          </div>
        )}
        {error && <div style={{ color: '#B3261E', fontSize: '0.85rem', margin: '0.8rem 0 0' }}>{error}</div>}

        <div style={{ overflowX: 'auto', backgroundColor: '#fff', border: `1px solid ${PALETTE.border}`, borderRadius: 14, marginTop: '1rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#FBF5F4' }}>
                {CLUSTER_DETAIL_COLUMNS.map((col) => (
                  <th key={col.key} onClick={() => col.sortable && toggleSort(col.key)} style={{ padding: '0.7rem 0.9rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700, cursor: col.sortable ? 'pointer' : 'default', whiteSpace: 'nowrap' }}>
                    {col.label}{col.sortable && sort === col.key ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.customer_id} style={{ borderTop: `1px solid ${PALETTE.border}`, opacity: loading ? 0.55 : 1 }}>
                  {CLUSTER_DETAIL_COLUMNS.map((col) => (
                    <td key={col.key} style={{ padding: '0.65rem 0.9rem', color: PALETTE.ink, whiteSpace: 'nowrap' }}>
                      {r[col.key] == null ? '—' : (col.format ? col.format(r[col.key]) : r[col.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {loading && rows.length === 0 && <SkeletonRows />}
          {!loading && rows.length === 0 && (
            <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint, fontSize: '0.85rem' }}>No customers found in this cluster.</div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.6rem', marginTop: '0.8rem' }}>
          <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={meta.page <= 1} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.4rem 0.8rem', cursor: meta.page <= 1 ? 'not-allowed' : 'pointer', opacity: meta.page <= 1 ? 0.4 : 1 }}>Previous</button>
          <span style={{ color: PALETTE.muted, fontSize: '0.85rem' }}>Page {meta.page} of {meta.total_pages}</span>
          <button type="button" onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))} disabled={meta.page >= meta.total_pages} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.4rem 0.8rem', cursor: meta.page >= meta.total_pages ? 'not-allowed' : 'pointer', opacity: meta.page >= meta.total_pages ? 0.4 : 1 }}>Next</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
