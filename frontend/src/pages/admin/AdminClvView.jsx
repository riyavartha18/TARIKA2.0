import React, { useState, useEffect, useCallback, useRef, memo } from 'react';
import { createPortal } from 'react-dom';
import { useAuth } from '../../auth/AuthContext';
import {
  getClvSummary,
  getClvSegments,
  getClvCustomers,
  getClvCustomerDetail,
  recalculateClv,
} from '../../services/api';
import ClvCustomersModal from './ClvCustomersModal';
import { ArrowLeft, Search, Loader2, RefreshCw, X, ChevronLeft, ChevronRight, Users } from 'lucide-react';

// CLV dashboard integrated into the existing Admin Analysis page. Tokens and
// layout idioms match the RFM dashboard (AdminRFMView): warm light surfaces,
// charcoal text, rose bars, no chart library dependency (the project has none)
// - the customer value distribution is built from styled, responsive bars.
const PALETTE = {
  ink: '#1F191B', muted: '#6B5E63', faint: '#9E8F94',
  rose: '#D8727E', roseDeep: '#B8505E', border: '#F0E2E0', bg: '#FFFFFF',
};

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

const INSUFFICIENT = 'Insufficient historical data';

// Commit-time measurement for the dashboard: durations are pushed to a small
// window buffer (readable from the browser console / perf tools in ANY build)
// and logged to the console in dev only. No-op cost otherwise.
const onClvRender = (id, phase, actualDuration) => {
  const buf = (window.__CLV_RENDER_MS = window.__CLV_RENDER_MS || []);
  buf.push({ phase, ms: Math.round(actualDuration * 100) / 100 });
  if (buf.length > 50) buf.shift();
  if (import.meta.env.DEV) {
    // eslint-disable-next-line no-console
    console.debug(`[CLV render] phase=${phase} commit=${actualDuration.toFixed(2)}ms`);
  }
};

const formatMoney = (value) => {
  if (value === null || value === undefined) return INSUFFICIENT;
  return `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
};

// Large amounts render in Indian compact notation (K / L / Cr) so cards and
// tables stay readable; the exact rupee value is never lost - it is always
// available in the hover tooltip or the popup's secondary line.
const trimZeros = (s) => (s.includes('.') ? s.replace(/\.?0+$/, '').replace(/\.$/, '') : s);
const formatCompact = (value) => {
  if (value === null || value === undefined) return INSUFFICIENT;
  const n = Number(value);
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${trimZeros((n / 1e7).toFixed(2))} Cr`;
  if (abs >= 1e5) return `₹${trimZeros((n / 1e5).toFixed(2))} L`;
  if (abs >= 1e3) return `₹${trimZeros((n / 1e3).toFixed(2))} K`;
  return formatMoney(n);
};

// Exact amount kept as the tooltip text wherever a compact value is shown.
const exactMoney = (value) => {
  if (value === null || value === undefined) return '';
  return `₹${Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-IN');
};

const useDebounced = (value, delay = 350) => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
};

function Divider() {
  return <div style={{ height: 1, background: DARK.divider, margin: '1.25rem 0' }} />;
}

function SectionTitle({ children, note }) {
  return (
    <div style={{ marginBottom: '0.5rem' }}>
      <div style={{ fontSize: '0.82rem', fontWeight: 650, color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {children}
      </div>
      {note && <p style={{ margin: '0.25rem 0 0', fontSize: '0.76rem', color: DARK.faint }}>{note}</p>}
    </div>
  );
}

// One summary card of the four-metric overview grid. `exact` renders the full
// un-compounded amount as the hover tooltip behind the compact value.
function SummaryCard({ label, value, sub, unavailable, exact }) {
  return (
    <div title={exact || undefined} style={{ backgroundColor: DARK.panel, border: `1px solid ${DARK.divider}`, borderRadius: 14, padding: '1.1rem 1.2rem' }}>
      <div style={{ fontSize: '0.72rem', color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: unavailable ? '1rem' : '1.55rem', fontWeight: 650, color: unavailable ? DARK.label : DARK.value, lineHeight: 1.2, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      <div style={{ fontSize: '0.75rem', color: DARK.faint, marginTop: 4 }}>{sub}</div>
    </div>
  );
}

// Customer Value Distribution: a VERTICAL bar (column) chart. The four value
// categories sit on the X-axis and customer counts on a scaled numerical
// Y-axis; bars extend upward from the baseline and the exact count shows
// above each bar and in its hover tooltip. Categories are laid out on an
// even CSS-Grid scale (equal column widths and gaps) so bars and labels
// never crowd, overlap or clip. High/Medium/Low come from the existing CLV
// value tiers, At Risk from the existing RFM At-Risk segment. Clicking a bar
// opens the actual customers behind that bar.
const CATEGORY_COLORS = {
  'High Value': '#8E3642',
  'Medium Value': '#B8505E',
  'Low Value': '#E3A6AE',
  'At Risk': '#C08A3E',
};

// Round an axis maximum up to a friendly step so ticks read 0/10k/20k/... .
function niceAxisMax(maxValue, tickCount) {
  const rawStep = Math.max(1, maxValue / tickCount);
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const stepMultiplier = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  const step = stepMultiplier * magnitude;
  return { axisMax: step * tickCount, step };
}

// Memoized: the chart only re-renders when its snapshot payload or the
// stable open handler changes, so table/filter typing never repaints it.
const ValueDistributionChart = memo(function ValueDistributionChart({ segmentsData, onOpenCategory }) {
  const tiers = segmentsData?.tiers || [];
  const atRisk = segmentsData?.at_risk || {};

  const categories = [
    ...tiers.map((t) => ({ label: t.tier, count: Number(t.count || 0), tier: t.tier })),
    { label: 'At Risk', count: Number(atRisk.count || 0), segment: atRisk.segment },
  ];

  const maxCount = Math.max(1, ...categories.map((c) => c.count));
  const tickCount = 4;
  const { axisMax, step } = niceAxisMax(maxCount, tickCount);
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => i * step);
  const notLoaded = !segmentsData;
  const PLOT_HEIGHT = 240;
  // Identical horizontal padding on the bars row and the labels row keeps
  // every label exactly centred under its bar at any screen width.
  const GRID = 'repeat(4, minmax(0, 1fr))';
  const GRID_PAD = '0 clamp(0.75rem, 4%, 2.5rem)';

  return (
    <section>
      <SectionTitle>Customer Value Distribution</SectionTitle>

      {notLoaded ? (
        <div style={{ height: PLOT_HEIGHT + 40, borderRadius: 12, background: 'linear-gradient(90deg,#F5ECEC 25%,#FBF5F4 50%,#F5ECEC 75%)', backgroundSize: '200% 100%', animation: 'rfm-shimmer 1.2s infinite' }} />
      ) : (
        <div>
          <div style={{ display: 'flex' }}>
            {/* Y-axis: numerical ticks */}
            <div style={{ position: 'relative', width: 60, height: PLOT_HEIGHT, flex: '0 0 60px' }}>
              {ticks.map((t) => (
                <span key={t} style={{ position: 'absolute', right: 8, bottom: `${(t / axisMax) * 100}%`, transform: 'translateY(50%)', fontSize: '0.68rem', color: DARK.faint, fontVariantNumeric: 'tabular-nums' }}>
                  {t.toLocaleString('en-IN')}
                </span>
              ))}
            </div>

            {/* Plot area with gridlines and evenly scaled upward bars */}
            <div style={{ position: 'relative', flex: 1, height: PLOT_HEIGHT, borderLeft: `1px solid ${DARK.divider}`, borderBottom: `1px solid ${DARK.label}` }}>
              {ticks.map((t) => (
                <div key={t} style={{ position: 'absolute', left: 0, right: 0, bottom: `${(t / axisMax) * 100}%`, height: 1, background: DARK.divider }} />
              ))}
              <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: GRID, gap: 'clamp(0.5rem, 2%, 1.25rem)', padding: GRID_PAD, alignItems: 'end' }}>
                {categories.map((c) => {
                  const pct = (c.count / axisMax) * 100;
                  return (
                    <div key={c.label} style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 650, color: DARK.label, marginBottom: 4, fontVariantNumeric: 'tabular-nums' }}>
                        {c.count.toLocaleString('en-IN')}
                      </span>
                      <button
                        type="button"
                        className="clv-bar"
                        title={`${c.label}: ${c.count.toLocaleString('en-IN')} customers - click to view`}
                        onClick={() => onOpenCategory(c)}
                        style={{
                          width: 'min(70%, 96px)',
                          height: `${pct}%`,
                          minHeight: c.count > 0 ? 4 : 0,
                          background: CATEGORY_COLORS[c.label] || DARK.bar,
                          borderRadius: '8px 8px 0 0',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          transition: 'height 0.7s cubic-bezier(0.22, 1, 0.36, 1)',
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* X-axis: one centred label per grid column, aligned with the bars */}
          <div style={{ display: 'flex', paddingLeft: 60 }}>
            <div style={{ flex: 1, display: 'grid', gridTemplateColumns: GRID, gap: 'clamp(0.5rem, 2%, 1.25rem)', padding: GRID_PAD }}>
              {categories.map((c) => (
                <button
                  key={c.label}
                  type="button"
                  onClick={() => onOpenCategory(c)}
                  style={{ textAlign: 'center', fontSize: '0.78rem', color: DARK.text, fontWeight: 500, background: 'transparent', border: 'none', padding: '0.5rem 0.25rem 0', cursor: 'pointer', fontFamily: 'inherit' }}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
});

export default function AdminClvView({ onBack }) {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [segmentsData, setSegmentsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [recalculating, setRecalculating] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [chartCategory, setChartCategory] = useState(null);


  const loadAll = useCallback(async () => {
    // Summary and the (chart) segments payload are independent reads of the
    // same published snapshot: fetch them in parallel so the dashboard waits
    // on one round trip, not two sequential ones.
    const [res, seg] = await Promise.all([getClvSummary(token), getClvSegments(token)]);
    if (!res.success) { setError(res.error); setLoading(false); return; }
    setSummary(res);
    setLoading(false);
    if (res.available && seg.success) setSegmentsData(seg);
    setError(null);
  }, [token]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    loadAll().then(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [loadAll]);

  // Poll while the first build is in flight or a recalculation is running.
  const busy = !summary?.available
    || summary?.refreshing
    || (summary?.run_status?.status === 'queued')
    || (summary?.run_status?.status === 'running');
  useEffect(() => {
    if (!busy) return undefined;
    const timer = setInterval(loadAll, 3000);
    return () => clearInterval(timer);
  }, [busy, loadAll]);

  const handleRecalculate = async () => {
    setRecalculating(true);
    await recalculateClv(token);
    setTimeout(async () => { await loadAll(); setRecalculating(false); }, 1500);
  };

  if (loading && !summary) {
    return (
      <div style={{ backgroundColor: DARK.bg, borderRadius: 20, border: `1px solid ${PALETTE.border}`, boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)', padding: '3rem', textAlign: 'center' }}>
        <Loader2 size={26} color={PALETTE.roseDeep} style={{ animation: 'spin 0.8s linear infinite' }} />
        <p style={{ color: PALETTE.muted, marginTop: '0.8rem' }}>Loading Customer Lifetime Value…</p>
      </div>
    );
  }

  const available = summary?.available;
  const totals = summary?.totals || {};
  const futureOk = summary?.future_clv_status === 'ok';

  return (
    <React.Profiler id="CLV dashboard" onRender={onClvRender}>
    <div style={{ backgroundColor: DARK.bg, borderRadius: 20, padding: '1.6rem 1.8rem', color: DARK.text, border: `1px solid ${PALETTE.border}`, boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)' }}>
      <style>{`
        .clv-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
        @media (max-width: 900px) { .clv-cards { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 480px) { .clv-cards { grid-template-columns: 1fr; } }
        .clv-bar-row { opacity: 0; animation: clv-fadein 0.45s ease forwards; }
        @keyframes clv-fadein { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
        @keyframes rfm-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
        .clv-bar:hover { filter: brightness(1.1); }
        .clv-bar:focus-visible { outline: 2px solid #B8505E; outline-offset: 2px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (prefers-reduced-motion: reduce) { .clv-bar-row { animation: none; opacity: 1; } .clv-bar { transition: none; } }
        .clv-view-btn:hover { background: #9E3A48 !important; transform: translateY(-1px); box-shadow: 0 6px 20px rgba(184,80,94,0.35) !important; }
        .clv-view-btn:active { transform: translateY(0); }
        .clv-modal-overlay { animation: clv-modal-in 0.22s cubic-bezier(0.22,1,0.36,1); }
        .clv-modal-panel { animation: clv-panel-in 0.28s cubic-bezier(0.22,1,0.36,1); }
        @keyframes clv-modal-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes clv-panel-in { from { opacity: 0; transform: scale(0.96) translateY(16px); } to { opacity: 1; transform: none; } }
      `}</style>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
          {onBack && (
            <button type="button" onClick={onBack} style={{ border: `1px solid ${DARK.divider}`, background: 'transparent', borderRadius: 8, padding: '0.4rem 0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, color: DARK.label, fontSize: '0.78rem' }}>
              <ArrowLeft size={15} /> Back
            </button>
          )}
          <div>
            <h2 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.35rem', fontWeight: 650, color: DARK.value, margin: 0, letterSpacing: '-0.01em' }}>Customer Lifetime Value</h2>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <button type="button" onClick={handleRecalculate} disabled={recalculating || !available} style={{ border: `1px solid ${DARK.divider}`, background: 'transparent', borderRadius: 8, padding: '0.45rem 0.8rem', cursor: available && !recalculating ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', gap: 6, color: DARK.label, fontSize: '0.78rem', opacity: available && !recalculating ? 1 : 0.5 }}>
            <RefreshCw size={14} style={recalculating ? { animation: 'spin 0.8s linear infinite' } : undefined} /> Recalculate
          </button>
        </div>
      </div>

      <Divider />

      {!available ? (
        <div style={{ padding: '2.5rem 0', textAlign: 'center', color: DARK.label }}>
          <Loader2 size={22} color={PALETTE.roseDeep} style={{ animation: 'spin 0.8s linear infinite' }} />
          <p style={{ marginTop: '0.7rem', fontSize: '0.85rem' }}>Preparing the CLV analysis… this runs automatically in the background.</p>
        </div>
      ) : (
        <>
          {/* 1. Customer Lifetime Value Overview: four summary cards.
              Compact money (K/L/Cr); hover a card for the exact amount. */}
          <SectionTitle>Customer Lifetime Value Overview</SectionTitle>
          <div className="clv-cards" style={{ marginBottom: '0.5rem' }}>
            <SummaryCard label="Average Historical CLV" value={formatCompact(totals.avg_historical_clv)} exact={exactMoney(totals.avg_historical_clv)} sub="Per customer" />
            <SummaryCard label="High-value Customers" value={Number(totals.high_value_count || 0).toLocaleString('en-IN')} sub={`${totals.high_value_pct || 0}% of customers`} />
            <SummaryCard label="Total Customer Revenue" value={formatCompact(totals.total_historical_revenue)} exact={exactMoney(totals.total_historical_revenue)} sub="Historical revenue - all customers combined" />
            {futureOk ? (
              <SummaryCard
                label="Expected Future CLV"
                value={formatCompact(totals.avg_future_clv)}
                exact={exactMoney(totals.avg_future_clv)}
                sub="Average predicted per customer"
              />
            ) : (
              <SummaryCard label="Expected Future CLV" value={INSUFFICIENT} sub={summary.future_clv_message || 'Cohort history cannot yet support a lifespan estimate'} />
            )}
          </div>

          <Divider />



          {/* 3. Customer Value Distribution: the three mutually exclusive CLV
              value tiers (High/Medium/Low partition every analyzed buyer),
              plus the RFM At-Risk engagement segment shown as an overlay.
              Every bar is clickable and opens its actual customers. */}
          <ValueDistributionChart segmentsData={segmentsData} onOpenCategory={setChartCategory} />

          {/* Top Customers section — heading + top-5 leaderboard below the chart */}
          <div style={{ marginTop: '1.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.6rem', marginBottom: '1.1rem' }}>
              <h3 style={{
                fontFamily: "var(--font-serif, 'Playfair Display', serif)",
                fontSize: '1.25rem',
                fontWeight: 750,
                color: DARK.value,
                margin: 0,
                letterSpacing: '-0.02em',
              }}>
                Top Customers by Historical CLV
              </h3>
              <span style={{ fontSize: '0.75rem', color: DARK.faint, fontWeight: 500 }}>Top 5</span>
            </div>
            <TopCustomersLeaderboard token={token} onOpenDetail={setDetailId} />
          </div>
        </>
      )}

      {error && <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#B3261E' }}>{error}</div>}

      {/* Chart-category / tier-button popup */}
      {chartCategory && (
        <ClvCustomersModal
          token={token}
          category={chartCategory}
          onClose={() => setChartCategory(null)}
          onOpenDetail={setDetailId}
        />
      )}

      {/* Customer detail popup */}
      {detailId && (
        <CustomerDetailModal token={token} customerId={detailId} onClose={() => setDetailId(null)} />
      )}
    </div>
    </React.Profiler>
  );
}

/* -------------------------------------------------------------------------- */
/* Individual Customers Modal — full popup with search/filter/sort/pagination  */
/* -------------------------------------------------------------------------- */

// Server-side page size for the customer-level CLV table.
const PAGE_SIZE = 50;

// Identity plus each customer's OWN Historical and Future CLV (both come from
// the per-row CLV derivation, never a population average) and the value tier.
// There is no per-row action column: the whole row opens the detail popup.
const TABLE_COLUMNS = [
  { key: 'customer_id', label: 'Customer ID', sortable: true },
  { key: 'customer_name', label: 'Customer Name', sortable: true },
  { key: 'historical_clv', label: 'Historical CLV (₹)', sortable: true, money: true },
  { key: 'future_clv', label: 'Future CLV (₹)', sortable: true, money: true },
];

/**
 * Full-screen modal containing the paginated individual customer CLV table.
 * Rendered via createPortal so it always sits above everything else.
 * The customer list NEVER appears on the main dashboard — only inside here.
 */
function IndividualCustomersModal({ token, onClose, onOpenDetail }) {
  return createPortal(
    <div
      id="clv-individual-modal-overlay"
      className="clv-modal-overlay"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(31,25,27,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 3000,
        padding: '1rem',
        backdropFilter: 'blur(2px)',
      }}
    >
      <div
        id="clv-individual-modal-panel"
        className="clv-modal-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: '#fff',
          borderRadius: 20,
          width: '100%',
          maxWidth: 1100,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          boxShadow: '0 24px 80px rgba(31,25,27,0.22)',
          overflow: 'hidden',
        }}
      >
        {/* Modal header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '1.3rem 1.6rem 1rem',
          borderBottom: `1px solid ${PALETTE.border}`,
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              backgroundColor: 'rgba(184,80,94,0.12)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Users size={18} color={PALETTE.roseDeep} />
            </div>
            <div>
              <h3 style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.15rem',
                fontWeight: 700,
                color: PALETTE.ink,
                margin: 0,
                letterSpacing: '-0.01em',
              }}>
                Individual Customer CLV
              </h3>
              <p style={{ margin: 0, fontSize: '0.75rem', color: PALETTE.faint }}>
                Historical &amp; Future CLV per customer · {PAGE_SIZE} per page
              </p>
            </div>
          </div>
          <button
            type="button"
            id="clv-individual-modal-close"
            onClick={onClose}
            aria-label="Close individual customers popup"
            style={{
              border: `1px solid ${PALETTE.border}`,
              background: '#fff',
              borderRadius: 10,
              padding: '0.4rem 0.5rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: PALETTE.muted,
              transition: 'background 0.15s',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable body containing the full table + controls */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.2rem 1.6rem 1.5rem' }}>
          <CustomerSection token={token} onOpenDetail={onOpenDetail} />
        </div>
      </div>
    </div>,
    document.body,
  );
}

// Rank medals for positions 1–3; plain number for 4–5.
const RANK_MEDAL = ['🥇', '🥈', '🥉'];
const RANK_ACCENT = [
  { bar: '#8E3642', bg: 'rgba(142,54,66,0.08)', badge: 'rgba(142,54,66,0.14)', text: '#8E3642' },
  { bar: '#A0727E', bg: 'rgba(160,114,126,0.07)', badge: 'rgba(160,114,126,0.13)', text: '#A0727E' },
  { bar: '#B8505E', bg: 'rgba(184,80,94,0.06)', badge: 'rgba(184,80,94,0.11)', text: '#B8505E' },
  { bar: '#6B5E63', bg: 'rgba(107,94,99,0.05)', badge: 'rgba(107,94,99,0.10)', text: '#6B5E63' },
  { bar: '#6B5E63', bg: 'rgba(107,94,99,0.04)', badge: 'rgba(107,94,99,0.09)', text: '#6B5E63' },
];

// Top-5 leaderboard: clean ranked rows, compact CLV, no table/pagination below.
function TopCustomersLeaderboard({ token, onOpenDetail }) {
  const [top, setTop] = useState([]);
  useEffect(() => {
    let alive = true;
    getClvCustomers(token, { page: 1, page_size: 5, sort: 'historical_clv', dir: 'desc' })
      .then((res) => { if (alive && res.success) setTop(res.results || []); });
    return () => { alive = false; };
  }, [token]);

  return (
    <div style={{
      border: `1px solid ${DARK.divider}`,
      borderRadius: 14,
      overflow: 'hidden',
      backgroundColor: DARK.panel,
    }}>
      {top.slice(0, 5).map((r, i) => {
        const accent = RANK_ACCENT[i] || RANK_ACCENT[4];
        const isLast = i === Math.min(top.length, 5) - 1;
        return (
          <button
            key={r.customer_id}
            type="button"
            onClick={() => onOpenDetail(r.customer_id)}
            title={exactMoney(r.historical_clv)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.9rem',
              width: '100%',
              textAlign: 'left',
              background: accent.bg,
              border: 'none',
              borderBottom: isLast ? 'none' : `1px solid ${DARK.divider}`,
              padding: '0.85rem 1.1rem',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'filter 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.filter = 'brightness(0.96)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.filter = ''; }}
          >
            {/* Rank badge */}
            <div style={{
              width: 32, height: 32, borderRadius: 10,
              backgroundColor: accent.badge,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
              fontSize: i < 3 ? '1rem' : '0.8rem',
              fontWeight: 800,
              color: accent.text,
            }}>
              {i < 3 ? RANK_MEDAL[i] : `#${i + 1}`}
            </div>

            {/* Customer identity */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.92rem', fontWeight: 650, color: DARK.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {r.customer_name || r.customer_id}
              </div>
              <div style={{ fontSize: '0.72rem', color: DARK.faint, marginTop: 1, fontVariantNumeric: 'tabular-nums' }}>
                {r.customer_id}
              </div>
            </div>

            {/* CLV value */}
            <div style={{ fontSize: '1.05rem', fontWeight: 750, color: accent.bar, fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
              {formatCompact(r.historical_clv)}
            </div>
          </button>
        );
      })}
    </div>
  );
}

function CustomerSection({ token, onOpenDetail }) {
  const [top, setTop] = useState([]);
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ count: 0, page: 1, total_pages: 1 });
  const [searchInput, setSearchInput] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  const [futureMinInput, setFutureMinInput] = useState('');
  const [futureMaxInput, setFutureMaxInput] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState('customer_id');
  const [dir, setDir] = useState('asc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestSeq = useRef(0);

  const search = useDebounced(searchInput.trim(), 350);
  // Range boxes debounce on their own so typing does not fire a query per key.
  const futureMin = useDebounced(futureMinInput.trim(), 500);
  const futureMax = useDebounced(futureMaxInput.trim(), 500);
  useEffect(() => { setPage(1); }, [search, sort, dir, tierFilter, futureMin, futureMax]);

  // Top-6 leaderboard: same endpoint, server-sorted by historical CLV.
  useEffect(() => {
    let alive = true;
    getClvCustomers(token, { page: 1, page_size: 10, sort: 'historical_clv', dir: 'desc' })
      .then((res) => { if (alive && res.success) setTop(res.results || []); });
    return () => { alive = false; };
  }, [token]);

  const load = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    // Every filter/sort/page decision is a backend query parameter: the
    // server filters and sorts the FULL dataset, never just the loaded page.
    const res = await getClvCustomers(token, {
      page, page_size: PAGE_SIZE, search, tier: tierFilter, sort, dir,
      future_min: futureMin || undefined,
      future_max: futureMax || undefined,
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
  }, [token, page, search, tierFilter, sort, dir, futureMin, futureMax]);

  useEffect(() => { load(); }, [load]);

  const toggleSort = (field) => {
    if (sort === field) setDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSort(field); setDir('asc'); }
  };

  return (
    <>
      {/* Top-6 leaderboard cards (bar graph) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.7rem', marginBottom: '0.6rem' }}>
        {top.slice(0, 6).map((r, i) => (
          <button key={r.customer_id} type="button" onClick={() => onOpenDetail(r.customer_id)}
            title={exactMoney(r.historical_clv)}
            style={{ textAlign: 'left', backgroundColor: DARK.panel, border: `1px solid ${DARK.divider}`, borderRadius: 12, padding: '0.7rem 0.85rem', cursor: 'pointer' }}>
            <div style={{ fontSize: '0.7rem', color: DARK.faint, fontWeight: 700 }}>#{i + 1} • {r.customer_id}</div>
            <div style={{ fontSize: '0.85rem', color: DARK.text, fontWeight: 600, margin: '2px 0' }}>{r.customer_name || r.customer_id}</div>
            <div style={{ fontSize: '1rem', color: DARK.bar, fontWeight: 700 }}>{formatCompact(r.historical_clv)}</div>
          </button>
        ))}
      </div>
      {/* Heading appears BELOW the bar graph */}
      <SectionTitle>Top Customers by Historical CLV</SectionTitle>

      <Divider />

      {/* Filters and search bar */}
      <SectionTitle note={`${PAGE_SIZE} customers per page, filtered and sorted on the server`}>Customer CLV Table</SectionTitle>
      <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '0.8rem' }}>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: PALETTE.faint }} />
          <input
            id="clv-individual-search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search name or ID…"
            style={{ border: `1px solid ${PALETTE.border}`, borderRadius: 10, padding: '0.5rem 0.75rem 0.5rem 1.8rem', fontSize: '0.85rem', width: 200 }}
          />
        </div>
        <select
          id="clv-individual-tier-filter"
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          style={{ border: `1px solid ${PALETTE.border}`, borderRadius: 10, padding: '0.5rem 0.7rem', fontSize: '0.85rem', color: PALETTE.muted, backgroundColor: '#fff' }}
        >
          <option value="ALL">All value tiers</option>
          <option value="High Value">High Value</option>
          <option value="Medium Value">Medium Value</option>
          <option value="Low Value">Low Value</option>
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: PALETTE.muted }}>
          Future CLV ₹
          <input
            type="number" min="0" value={futureMinInput}
            onChange={(e) => setFutureMinInput(e.target.value)} placeholder="min"
            style={{ border: `1px solid ${PALETTE.border}`, borderRadius: 10, padding: '0.45rem 0.6rem', fontSize: '0.85rem', width: 92 }}
          />
          <span>–</span>
          <input
            type="number" min="0" value={futureMaxInput}
            onChange={(e) => setFutureMaxInput(e.target.value)} placeholder="max"
            style={{ border: `1px solid ${PALETTE.border}`, borderRadius: 10, padding: '0.45rem 0.6rem', fontSize: '0.85rem', width: 92 }}
          />
        </label>
        <span style={{ color: PALETTE.faint, fontSize: '0.8rem', marginLeft: 'auto' }}>
          {Number(meta.count).toLocaleString('en-IN')} customers total
        </span>
      </div>

      {error && <div style={{ color: '#B3261E', fontSize: '0.85rem', marginBottom: '0.6rem' }}>{error}</div>}

      {/* Table */}
      <div style={{ overflowX: 'auto', backgroundColor: '#fff', border: `1px solid ${PALETTE.border}`, borderRadius: 14 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#FBF5F4' }}>
              {TABLE_COLUMNS.map((col) => (
                <th key={col.key} onClick={() => col.sortable && toggleSort(col.key)}
                  style={{ padding: '0.7rem 0.9rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700, cursor: col.sortable ? 'pointer' : 'default', whiteSpace: 'nowrap' }}>
                  {col.label}{col.sortable && sort === col.key ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
              <th style={{ padding: '0.7rem 0.9rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700 }}>CLV Tier</th>
            </tr>
          </thead>
          <tbody>
            {!loading && rows.map((r) => (
              <tr key={r.customer_id} onClick={() => onOpenDetail(r.customer_id)} title="Click for this customer's full details"
                style={{ borderTop: `1px solid ${PALETTE.border}`, cursor: 'pointer', opacity: loading ? 0.55 : 1 }}>
                {TABLE_COLUMNS.map((col) => (
                  <td key={col.key} title={col.money && r[col.key] != null ? exactMoney(r[col.key]) : undefined}
                    style={{ padding: '0.65rem 0.9rem', color: PALETTE.ink, whiteSpace: 'nowrap' }}>
                    {col.money
                      ? (r[col.key] == null ? <span style={{ color: PALETTE.faint, fontWeight: 600 }}>Insufficient Data</span> : formatCompact(r[col.key]))
                      : (r[col.key] ?? '—')}
                  </td>
                ))}
                <td style={{ padding: '0.65rem 0.9rem' }}>
                  <TierBadge tier={r.clv_tier} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '1.1rem' }}>
            {[...Array(6)].map((_, i) => (
              <div key={i} style={{ height: 20, borderRadius: 8, background: 'linear-gradient(90deg,#F5ECEC 25%,#FBF5F4 50%,#F5ECEC 75%)', backgroundSize: '200% 100%', animation: 'rfm-shimmer 1.2s infinite' }} />
            ))}
            <style>{`@keyframes rfm-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
          </div>
        )}
        {!loading && rows.length === 0 && (
          <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint, fontSize: '0.85rem' }}>No customers found.</div>
        )}
      </div>

      <PaginationBar page={meta.page} totalPages={meta.total_pages} count={meta.count} onChange={setPage} />
    </>
  );
}

// Windowed page numbers: 1, a gap, current-1..current+1, a gap, last.
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

// Previous/Next arrows plus numbered pages (server-side page changes only).
function PaginationBar({ page, totalPages, count, onChange }) {
  const btnStyle = (enabled) => ({ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.35rem 0.6rem', cursor: enabled ? 'pointer' : 'not-allowed', opacity: enabled ? 1 : 0.4, color: PALETTE.muted, display: 'flex', alignItems: 'center', fontFamily: 'inherit' });
  const numberStyle = (active) => ({ border: `1px solid ${active ? PALETTE.rose : PALETTE.border}`, background: active ? PALETTE.roseDeep : '#fff', color: active ? '#fff' : PALETTE.muted, borderRadius: 8, padding: '0.35rem 0.65rem', cursor: active ? 'default' : 'pointer', fontSize: '0.8rem', fontWeight: 700, fontFamily: 'inherit' });
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '0.35rem', marginTop: '0.8rem', flexWrap: 'wrap' }}>
      <button type="button" aria-label="Previous page" onClick={() => onChange(Math.max(1, page - 1))} disabled={page <= 1} style={btnStyle(page > 1)}>
        <ChevronLeft size={15} />
      </button>
      {pageWindow(page, totalPages).map((item) => (
        typeof item === 'number' ? (
          <button key={item} type="button" onClick={() => onChange(item)}
            aria-current={item === page ? 'page' : undefined}
            style={numberStyle(item === page)}>{item}</button>
        ) : (
          <span key={item} style={{ color: PALETTE.faint, fontSize: '0.8rem', padding: '0 0.1rem' }}>…</span>
        )
      ))}
      <button type="button" aria-label="Next page" onClick={() => onChange(Math.min(totalPages, page + 1))} disabled={page >= totalPages} style={btnStyle(page < totalPages)}>
        <ChevronRight size={15} />
      </button>
      <span style={{ color: PALETTE.muted, fontSize: '0.8rem', marginLeft: '0.4rem' }}>Page {page} of {totalPages}</span>
    </div>
  );
}

const TIER_COLORS = {
  'High Value': { bg: 'rgba(184,80,94,0.16)', color: '#8E3642' },
  'Medium Value': { bg: 'rgba(216,114,126,0.12)', color: '#B8505E' },
  'Low Value': { bg: 'rgba(31,25,27,0.06)', color: '#6B5E63' },
};

function TierBadge({ tier }) {
  if (!tier) return <span style={{ color: PALETTE.faint }}>—</span>;
  const c = TIER_COLORS[tier] || TIER_COLORS['Low Value'];
  return <span style={{ backgroundColor: c.bg, color: c.color, borderRadius: 8, padding: '2px 8px', fontSize: '0.74rem', fontWeight: 700, whiteSpace: 'nowrap' }}>{tier}</span>;
}

/* -------------------------------------------------------------------------- */
/* Customer detail                                                             */
/* -------------------------------------------------------------------------- */

// Identity + purchase history of ONE customer, opened by clicking a table row.
// The payload is only rendered when it belongs to the requested customer, so
// switching customers can never show the previously selected one.
function CustomerDetailModal({ token, customerId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getClvCustomerDetail(token, customerId).then((res) => {
      if (!alive) return;
      if (res.success) { setData(res); setError(null); } else { setError(res.error); }
      setLoading(false);
    });
    return () => { alive = false; };
  }, [token, customerId]);

  // A response is only ever rendered when it belongs to the customer that was
  // requested, so a slow reply for the previously opened customer - or a
  // mismatching payload - can never be shown as if it were this one.
  const matches = data != null
    && String(data.customer_id ?? customerId) === String(customerId);
  const status = (matches ? data.calculation_status : null) || {};
  const name = matches ? (data.customer_name || customerId) : 'Loading customer…';
  const segment = matches ? (data.rfm_segment || data.segment) : null;

  return createPortal(
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(31,25,27,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 3100, padding: '1rem' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ backgroundColor: '#fff', borderRadius: 18, maxWidth: 620, width: '100%', maxHeight: '85vh', overflowY: 'auto', padding: '1.6rem 1.7rem', position: 'relative' }}>
        <button type="button" onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: '1rem', right: '1rem', border: 'none', background: 'transparent', cursor: 'pointer', color: PALETTE.faint }}>
          <X size={18} />
        </button>
        <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.2rem', color: PALETTE.ink, margin: '0 0 0.2rem' }}>
          {name}
        </h3>
        <p style={{ margin: '0 0 1rem', fontSize: '0.8rem', color: PALETTE.faint }}>
          Customer ID: {customerId}
        </p>

        {loading ? (
          <div style={{ padding: '1.5rem 0', textAlign: 'center', color: PALETTE.faint }}>
            <Loader2 size={20} style={{ animation: 'spin 0.8s linear infinite' }} />
          </div>
        ) : error ? (
          <div style={{ color: '#B3261E', fontSize: '0.85rem' }}>{error}</div>
        ) : !matches ? (
          <div style={{ padding: '1.5rem 0', textAlign: 'center', color: PALETTE.faint }}>No details available for this customer.</div>
        ) : (
          <>
            {/* Headline numbers: this customer's own historical value and tier. */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', marginBottom: '1rem' }}>
              <div style={{ backgroundColor: DARK.panel, border: `1px solid ${DARK.divider}`, borderRadius: 12, padding: '0.85rem 0.95rem' }} title={exactMoney(data.historical_clv)}>
                <div style={{ fontSize: '0.7rem', color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Historical CLV</div>
                <div style={{ fontSize: '1.3rem', fontWeight: 700, color: DARK.bar }}>{formatCompact(data.historical_clv)}</div>
                <div style={{ fontSize: '0.72rem', color: DARK.faint, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>{exactMoney(data.historical_clv)}</div>
              </div>
              <div style={{ backgroundColor: DARK.panel, border: `1px solid ${DARK.divider}`, borderRadius: 12, padding: '0.85rem 0.95rem' }}>
                <div style={{ fontSize: '0.7rem', color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.05em' }}>CLV Tier</div>
                <div style={{ fontSize: '1.3rem', fontWeight: 700 }}><TierBadge tier={data.clv_tier} /></div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem 1.2rem' }}>
              <DetailItem label="RFM Segment" value={segment || '—'} />
              <DetailItem label="Total Orders" value={data.order_count == null ? '—' : Number(data.order_count).toLocaleString('en-IN')} />
              <DetailItem label="Average Order Value" value={formatMoney(data.aov)} />
              <DetailItem label="Customer Tenure" value={data.tenure_days == null ? '—' : `${Number(data.tenure_days).toLocaleString('en-IN')} days`} />
              <DetailItem label="First Purchase" value={formatDate(data.first_purchase_date)} />
              <DetailItem label="Last Purchase" value={formatDate(data.last_purchase_date)} />
            </div>

            {status.cutoff_date && (
              <p style={{ margin: '1rem 0 0', fontSize: '0.72rem', color: PALETTE.faint, lineHeight: 1.55 }}>
                Historical CLV is the total revenue from this customer's eligible orders, reported up to {formatDate(status.cutoff_date)}.
              </p>
            )}
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

function DetailItem({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: '0.7rem', color: DARK.label, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: '0.95rem', color: DARK.text, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
