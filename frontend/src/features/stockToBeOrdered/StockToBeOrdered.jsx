import React, { useState, useEffect, useCallback, useRef } from 'react';
import { X, Truck, PackagePlus, AlertCircle } from 'lucide-react';
import {
  getStockToBeOrdered,
  createReplenishmentOrder,
  getDemandPreview,
  orderAllDemand,
  receiveReplenishmentOrder,
  getReplenishmentOrders,
  getWarehouseProductDetail,
} from '../../services/api';
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

/* ─────────────────────────────────────────────────
   REPLENISHMENT DRAWER
   Opens when a warehouse manager clicks a product image in Stock to Be
   Ordered. Mirrors the Warehouse "Edit Product" side panel — same layout,
   spacing, typography, buttons and animations — adapted for supplier
   replenishment: it never edits product details and never touches
   products.available_quantity. Only a receipt changes stock.
   ───────────────────────────────────────────────── */
const drawerLabelStyle = {
  display: 'block',
  fontSize: '0.72rem',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: '#6B5E63',
  marginBottom: '4px',
};
const drawerInputStyle = {
  width: '100%',
  padding: '0.6rem 0.85rem',
  borderRadius: '10px',
  border: '1.5px solid var(--tarika-border, #F0E2E0)',
  backgroundColor: '#FAF7F5',
  color: '#1F191B',
  fontSize: '0.88rem',
  outline: 'none',
  transition: 'border-color 0.2s ease',
  boxSizing: 'border-box',
};

function ReplenishmentDrawer({ row, token, onClose, onResult }) {
  // Full product data + the latest pending supplier order are fetched on open
  // (same flow as the Edit Product panel). The parent mounts the drawer keyed
  // by product_key, so clicking another image can never show the previously
  // selected product's data.
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);   // fresh product row from Django
  const [fetchError, setFetchError] = useState(null);
  const [po, setPo] = useState(null);           // latest Pending supplier order (or null)
  const [qty, setQty] = useState('');
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState(null);

  const productKey = row.product_key ?? row.product_id;

  useEffect(() => {
    let cancelled = false;
    const suggested = String(row.order_now_qty ?? row.need_to_order ?? '');
    setLoading(true);
    Promise.all([
      getWarehouseProductDetail(productKey),
      getReplenishmentOrders(token, { status: 'Pending', productKey }),
    ]).then(([detailRes, ordersRes]) => {
      if (cancelled) return;
      if (detailRes.success && detailRes.product) {
        setDetail(detailRes.product);
      } else {
        setFetchError(detailRes.error || 'Could not load the latest product details. Showing the list data instead.');
      }
      if (ordersRes.success) {
        const latest = ordersRes.orders?.[0] || null;
        setPo(latest);
        setQty(String(latest?.quantity_ordered ?? suggested));
      } else {
        setFetchError(ordersRes.error || 'Could not check pending supplier orders.');
        setQty(suggested);
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productKey]);

  // Lock body scroll while the drawer is open (same behaviour as Edit Product).
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const product = detail || row;
  const productName = product.product_name || row.product_name || 'Product';
  const rawStock = detail
    ? (detail.available_quantity !== undefined ? detail.available_quantity : detail.total_stock)
    : row.current_stock;
  const stockUnknown = rawStock === null || rawStock === undefined || !Number.isFinite(Number(rawStock));
  const stockUnits = stockUnknown ? null : Number(rawStock);
  const availLabel = detail?.availability_label
    || (!stockUnknown && stockUnits > 0 ? 'Available' : stockUnknown ? 'Stock Data Unavailable' : 'Out of Stock');
  const isAvailable = availLabel === 'Available';
  const imageUrl = product.image || row.image
    || 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=700&q=80';
  const tier = TIER_META[row.demand_tier] || null;
  const suggested = Math.max(0, Number(row.need_to_order ?? 0));

  const parseQty = (raw) => {
    const str = String(raw ?? '').trim();
    if (str === '') return { ok: false, error: 'Reorder quantity is required.' };
    const num = Number(str);
    if (!Number.isFinite(num)) return { ok: false, error: 'Reorder quantity must be a valid number.' };
    if (!Number.isInteger(num)) return { ok: false, error: 'Reorder quantity must be a whole number (e.g. 25, not 25.5).' };
    if (num <= 0) return { ok: false, error: 'Reorder quantity must be greater than zero.' };
    return { ok: true, value: num };
  };

  // Place Order — creates a supplier PO through the existing API AND, for this
  // app's reorder rule, immediately adds the ordered quantity to
  // products.available_quantity. The committed stock is returned by the server,
  // so the card is refreshed from that authoritative DB value — never a local
  // guess. Duplicate submissions are blocked here (placing guard) and again
  // server-side (an already-pending PO is refused), so the stock cannot be
  // incremented twice by a double-click or retry.
  const handlePlace = async () => {
    if (placing) return;
    if (po) {
      setError(`A supplier order (${po.po_key}) is already pending for this product. Receive it before placing another.`);
      return;
    }
    const parsed = parseQty(qty);
    if (!parsed.ok) { setError(parsed.error); return; }
    setPlacing(true);
    setError(null);
    const res = await createReplenishmentOrder(token, productKey, parsed.value);
    if (res.success) {
      const createdQty = Number(res.order?.quantity_ordered ?? parsed.value);
      const serverStock = Number(res.availableQuantity);
      const baseStock = Number.isFinite(Number(stockUnits))
        ? Number(stockUnits)
        : Number(row.current_stock ?? 0);
      // Prefer the persisted database value; fall back to base + ordered only if
      // the response omitted it (the server still committed the increment).
      const newStock = Number.isFinite(serverStock) ? serverStock : baseStock + createdQty;
      const predicted = Number(row.predicted_demand ?? 0);
      if (onResult) {
        onResult(productKey, {
          placed: true,
          current_stock: newStock,
          pending_order: true,
          pending_qty: createdQty,
          need_to_order: Math.max(0, predicted - newStock),
          order_now_qty: Math.max(0, suggested - createdQty),
        }, res.message || `Ordered ${createdQty} unit(s). Available stock is now ${newStock}.`);
      }
      return;
    }
    // Failure: the drawer keeps the product visible and allows a safe retry.
    // Nothing was added to stock (the server rolled the transaction back), so no
    // false success is shown and the displayed quantity is left untouched.
    setError(res.error || 'Could not place the supplier order. Nothing was ordered — you can retry.');
    setPlacing(false);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 200,
          backgroundColor: 'rgba(31, 25, 27, 0.55)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Slide-in Panel (right) */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Supplier replenishment"
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201,
          width: 'min(640px, 100vw)',
          backgroundColor: '#FFFFFF',
          boxShadow: '-8px 0 60px rgba(31, 25, 27, 0.18)',
          display: 'flex', flexDirection: 'column',
          animation: 'slideInRight 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          overflowY: 'auto',
        }}
      >
        {/* Panel Header */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.96)',
          backdropFilter: 'blur(10px)',
          borderBottom: '1px solid var(--tarika-border, #F0E2E0)',
          padding: '1rem 1.5rem',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: '1rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0 }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0,
              background: 'linear-gradient(135deg, #FBF1F0 0%, #F5DDE0 100%)',
              border: '1px solid rgba(216, 114, 126, 0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#B8505E',
            }}>
              <Truck size={17} />
            </div>
            <div style={{ minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                Supplier Replenishment
              </p>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#6B5E63', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {loading ? 'Loading…' : productName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '36px', height: '36px', borderRadius: '50%', flexShrink: 0,
              border: '1px solid var(--tarika-border, #F0E2E0)',
              backgroundColor: '#FAF7F5', color: '#6B5E63',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'all 0.2s ease',
            }}
            aria-label="Close replenishment panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem', padding: '3rem' }}>
            <div className="tarika-auth-spinner" style={{ width: '2.5rem', height: '2.5rem', borderColor: 'rgba(216, 114, 126, 0.25)', borderTopColor: '#D8727E' }} />
            <p style={{ color: '#6B5E63', fontWeight: 600, margin: 0 }}>Fetching product and supplier orders…</p>
          </div>
        )}

        {/* Content */}
        {!loading && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0 }}>

            {/* Hero: Product Image + Key Info */}
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: '1.25rem', padding: '1.5rem',
              background: 'linear-gradient(135deg, #FAF7F5 0%, #FBF1F0 100%)',
              borderBottom: '1px solid var(--tarika-border, #F0E2E0)',
            }}>
              <div style={{ width: '120px', height: '150px', flexShrink: 0, borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(216,114,126,0.15)', boxShadow: '0 4px 16px rgba(184,80,94,0.08)' }}>
                <img
                  src={imageUrl}
                  alt={productName}
                  onError={(e) => { e.target.src = 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=300&q=80'; }}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              </div>

              <div style={{ flex: '1 1 220px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem', justifyContent: 'center' }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                  {product.category_name || row.category_name || 'Ready-to-Wear'}
                </span>
                <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#1F191B', lineHeight: 1.3 }}>
                  {productName}
                </h2>
                <code style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 700, color: '#1F191B', background: '#FFFFFF', padding: '0.2rem 0.55rem', borderRadius: '6px', border: '1px solid #F0E2E0', alignSelf: 'flex-start', wordBreak: 'break-all' }}>
                  {productKey}
                </code>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '2px' }}>
                  <span style={{
                    fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.75rem',
                    borderRadius: '9999px',
                    backgroundColor: isAvailable ? '#ECFDF5' : '#FEF2F2',
                    color: isAvailable ? '#059669' : '#DC2626',
                    border: `1px solid ${isAvailable ? '#A7F3D0' : '#FECACA'}`,
                  }}>
                    {availLabel}
                  </span>
                  {tier && <Pill bg={tier.bg} fg={tier.fg} border={tier.border}>{tier.label}</Pill>}
                  <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    {stockUnits === null ? 'Stock data unavailable' : `${stockUnits.toLocaleString('en-IN')} units available`}
                  </span>
                </div>
              </div>
            </div>

            {/* Fetch notice (non-blocking) */}
            {fetchError && (
              <div style={{ margin: '1rem 1.5rem 0', padding: '0.7rem 1rem', borderRadius: '10px', background: '#FFFBEB', border: '1px solid #FDE68A', color: '#D97706', fontSize: '0.8rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} />
                <span>{fetchError}</span>
              </div>
            )}

            {/* Read-only Replenishment Facts */}
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--tarika-border, #F0E2E0)' }}>
              <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                Replenishment Overview
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem 1.5rem' }}>
                {[
                  { label: 'Demand level', value: row.demand_tier || '—' },
                  { label: 'Predicted demand', value: `${(row.predicted_demand ?? 0).toLocaleString('en-IN')} units` },
                  { label: 'Suggested reorder', value: suggested > 0 ? `${suggested.toLocaleString('en-IN')} units` : 'None — stock covers demand' },
                  { label: 'Pending from supplier', value: po ? `${(po.quantity_ordered ?? 0).toLocaleString('en-IN')} units (${po.po_key})` : 'No open order' },
                  { label: 'Already received', value: po ? `${(po.quantity_received ?? 0).toLocaleString('en-IN')} units` : '—' },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p style={{ margin: '0 0 2px 0', fontSize: '0.7rem', fontWeight: 600, color: '#9E8F94', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</p>
                    <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 600, color: '#1F191B', wordBreak: 'break-all' }}>{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Proposed Reorder Quantity */}
            <div style={{ padding: '1.25rem 1.5rem', flex: 1 }}>
              <p style={{ margin: '0 0 1rem 0', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                Proposed Reorder Quantity
              </p>
              <div style={{ maxWidth: '260px' }}>
                <label style={drawerLabelStyle} htmlFor="stbo-drawer-qty">Reorder quantity (units) *</label>
                <input
                  id="stbo-drawer-qty"
                  type="number"
                  min="1"
                  step="1"
                  value={qty}
                  onChange={(e) => { setQty(e.target.value); setError(null); }}
                  placeholder="e.g. 25"
                  disabled={placing || !!po}
                  style={drawerInputStyle}
                />
              </div>
              <p style={{ margin: '0.85rem 0 0', fontSize: '0.78rem', color: '#6B5E63', lineHeight: 1.5 }}>
                ℹ️ Placing a supplier order <strong>requests stock from the supplier</strong> — available
                stock only increases when the goods are received (“Mark Received” on the card).
                {po && (
                  <> A supplier order ({po.po_key}) is already pending for this product, so ordering is blocked until it is received.</>
                )}
              </p>
            </div>

            {/* Error banner — the drawer stays open so staff can retry */}
            {error && (
              <div style={{ margin: '0 1.5rem 1rem', padding: '0.8rem 1rem', borderRadius: '10px', background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', fontSize: '0.82rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Sticky Footer — Place Order and Cancel only */}
            <div style={{
              position: 'sticky', bottom: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.97)',
              borderTop: '1px solid var(--tarika-border, #F0E2E0)',
              padding: '1rem 1.5rem',
              display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', alignItems: 'center',
              flexWrap: 'wrap',
            }}>
              <button
                type="button"
                onClick={onClose}
                disabled={placing}
                style={{
                  padding: '0.65rem 1.4rem', borderRadius: '10px',
                  border: '1px solid var(--tarika-border, #F0E2E0)',
                  backgroundColor: '#FAF7F5', color: '#6B5E63',
                  fontSize: '0.88rem', fontWeight: 600,
                  cursor: placing ? 'not-allowed' : 'pointer',
                  opacity: placing ? 0.6 : 1,
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePlace}
                disabled={placing || !!po}
                title={po ? `Order ${po.po_key} is already pending` : 'Create the supplier replenishment order'}
                style={{
                  padding: '0.65rem 1.6rem', borderRadius: '10px', border: 'none',
                  background: (placing || po) ? 'rgba(184,80,94,0.5)' : 'linear-gradient(135deg, #D8727E 0%, #B8505E 100%)',
                  color: '#FFFFFF', fontSize: '0.88rem', fontWeight: 700,
                  cursor: (placing || po) ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  boxShadow: placing ? 'none' : '0 4px 15px rgba(184,80,94,0.3)',
                  transition: 'all 0.2s ease',
                }}
              >
                {placing ? (
                  <>
                    <div className="tarika-auth-spinner" style={{ width: '16px', height: '16px', borderWidth: '2px', borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#FFFFFF', flexShrink: 0 }} />
                    Placing…
                  </>
                ) : (
                  <><PackagePlus size={15} /> Place Order</>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Same keyframes the Edit Product panel injects */}
      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);   opacity: 1; }
        }
      `}</style>
    </>
  );
}

/* ─────────────────────────────────────────────────
   Main component — server-paged, loads on mount
─────────────────────────────────────────────── */
const PAGE_SIZE = 12;

/* Bulk actions — one per demand group. All three share the page's existing
   bulk-button style; the icon + label is what differentiates them. */
const BULK_ACTIONS = [
  { tier: 'High', icon: '⚡', label: 'Order All High Demand' },
  { tier: 'Medium', icon: '📊', label: 'Order All Medium Demand' },
  { tier: 'Low', icon: '📉', label: 'Order All Low Demand' },
];

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

  // Ordering workflow state
  const [busyKey, setBusyKey] = useState(null);         // product being received
  const [flash, setFlash] = useState(null);             // { type, text }
  const [bulk, setBulk] = useState({
    open: false, tier: 'High', loading: false, items: [], total: 0,
    selected: {}, error: null, submitting: false, result: null,
  });
  // Supplier replenishment drawer — opened by clicking a product image.
  const [drawerRow, setDrawerRow] = useState(null);   // product row whose drawer is open
  // Products whose reorder need got fully covered this session: they fade out
  // and stay filtered out of refetched pages (dismissedRef) until a real
  // state change makes them eligible again.
  const [exiting, setExiting] = useState({});
  const dismissedRef = useRef(new Set());

  const notify = (type, text) => {
    setFlash({ type, text });
    setTimeout(() => setFlash(null), 5000);
  };

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
      // Never let a stale (or newly arriving) response resurrect a product
      // whose successful PO already covered its reorder need.
      setRows((result.products || []).filter(
        (p) => !dismissedRef.current.has(p.product_key ?? p.product_id),
      ));
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

  // Patch one card locally from an authoritative server response instead of
  // refetching the whole (multi-second) forecast list after every action.
  const updateRow = (productKey, patch) =>
    setRows((rs) => rs.map((r) => (
      (r.product_key ?? r.product_id) === productKey ? { ...r, ...patch(r) } : r
    )));

  // ── Receive handler ─────────────────────────
  // Ordering runs through the image-click drawer (Place Order) and the bulk
  // High/Medium/Low actions; the card itself shows no quantity input or Order
  // button anymore.

  const handleReceive = async (p) => {
    setBusyKey(p.product_key);
    const pending = await getReplenishmentOrders(token, { status: 'Pending', productKey: p.product_key });
    if (!pending.success || !pending.orders?.length) {
      notify('err', 'No pending order found to receive.');
      setBusyKey(null);
      return;
    }
    const res = await receiveReplenishmentOrder(token, pending.orders[0].po_key);
    if (res.success) {
      notify('ok', res.message);
      // The server returns the persisted available_quantity; patch the card
      // with it instead of refetching the whole page.
      const newStock = Number(res.availableQuantity ?? p.current_stock);
      updateRow(p.product_key, () => ({
        current_stock: newStock,
        pending_order: false,
        pending_qty: 0,
        need_to_order: Math.max(0, (p.predicted_demand || 0) - newStock),
      }));
    } else {
      notify('err', res.error);
    }
    setBusyKey(null);
  };

  // ── Drawer result handler ────────────────────
  // Server-confirmed success only: close the drawer, reconcile the card with
  // the authoritative quantities, and dismiss it when nothing is left to
  // order. Failures never reach here — the drawer keeps them visible.
  const handleDrawerResult = (productKey, patch, message) => {
    const { placed, ...rowPatch } = patch;
    setDrawerRow(null);
    updateRow(productKey, () => rowPatch);
    if (message) notify('ok', message);
    if (placed) {
      // Eligibility check against the existing rules: still short even after
      // counting ALL pending supplier orders → stay visible, updated in place.
      if ((rowPatch.order_now_qty ?? 0) > 0) return;
      dismissProduct(productKey);
    }
  };

  // Premium exit: CSS plays the success-highlight → fade → collapse
  // (.stbo-card-exit); only then is the node removed. No page reload, no
  // full-list refetch; remaining cards reflow naturally.
  const dismissProduct = (productKey) => {
    dismissedRef.current.add(productKey);
    setExiting((e) => ({ ...e, [productKey]: true }));
    const reduceMotion = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.setTimeout(() => {
      setRows((rs) => rs.filter((r) => (r.product_key ?? r.product_id) !== productKey));
      setExiting(({ [productKey]: _gone, ...rest }) => rest);
    }, reduceMotion ? 80 : 900);
  };

  const openBulk = async (tier) => {
    setBulk({
      open: true, tier, loading: true, items: [], total: 0,
      selected: {}, error: null, submitting: false, result: null,
    });
    const res = await getDemandPreview(token, tier);
    if (res.success) {
      // Every listed product starts selected; staff can deselect before confirming.
      const selected = {};
      res.items.forEach((it) => { selected[it.product_key] = true; });
      setBulk((b) => ({ ...b, loading: false, items: res.items, total: res.totalQuantity, selected }));
    } else {
      setBulk((b) => ({ ...b, loading: false, error: res.error }));
    }
  };

  const toggleBulkItem = (key) =>
    setBulk((b) => ({ ...b, selected: { ...b.selected, [key]: !b.selected[key] } }));

  const allSelected = bulk.items.length > 0 && bulk.items.every((it) => bulk.selected[it.product_key]);
  const toggleAllBulk = () => setBulk((b) => {
    const turnOn = !(b.items.length > 0 && b.items.every((it) => b.selected[it.product_key]));
    const selected = {};
    if (turnOn) b.items.forEach((it) => { selected[it.product_key] = true; });
    return { ...b, selected };
  });

  const selectedItems = bulk.items.filter((it) => bulk.selected[it.product_key]);
  const selectedUnits = selectedItems.reduce((sum, it) => sum + (it.recommended_qty || 0), 0);

  const confirmBulk = async () => {
    // Guard against double-clicks / retries: only the first submit runs, and
    // the server still refuses products that already have a Pending PO.
    if (bulk.submitting) return;
    setBulk((b) => ({ ...b, submitting: true }));
    const res = await orderAllDemand(token, bulk.tier, selectedItems.map((it) => it.product_key));
    if (res.success) {
      setBulk((b) => ({
        ...b,
        submitting: false,
        result: {
          created: res.createdCount, skipped: res.skippedCount,
          failed: res.failedCount, total: res.totalQuantity,
          failures: res.failures || [], attempted: selectedItems.length,
        },
      }));
      // The selection spanned many products, so one authoritative refresh is
      // the honest (and cheapest correct) way to show every new badge.
      load();
    } else {
      setBulk((b) => ({ ...b, submitting: false, error: res.error }));
    }
  };

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
          <div className="stbo-bulk-btns" role="group" aria-label="Bulk replenishment actions">
            {BULK_ACTIONS.map((a) => {
              const busy = bulk.open && (bulk.loading || bulk.submitting);
              return (
                <button
                  key={a.tier}
                  className="stbo-bulk-btn"
                  onClick={() => openBulk(a.tier)}
                  disabled={busy}
                  title={`Order the recommended quantity for every ${a.tier.toLowerCase()}-demand product`}
                >
                  {busy && a.tier === bulk.tier ? '⏳ Working…' : `${a.icon} ${a.label}`}
                </button>
              );
            })}
          </div>
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

      {/* ── Flash / error banner ──────────────── */}
      {flash && (
        <div className="stbo-flash" data-type={flash.type}>
          <span>{flash.type === 'ok' ? '✅' : '⚠️'}</span><span>{flash.text}</span>
        </div>
      )}

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
            const pk = p.product_key ?? p.product_id;
            const tier = TIER_META[p.demand_tier] || TIER_META.Medium;
            const prio = PRIORITY_META[p.priority] || PRIORITY_META['Low Priority'];
            const orderNeeded = p.need_to_order > 0;
            return (
              <div key={pk} className={`stbo-pcard${exiting[pk] ? ' stbo-card-exit' : ''}`} style={{ borderTop: `3px solid ${prio.accent}` }}>
                <div
                  className="stbo-pcard-media"
                  role="button"
                  tabIndex={0}
                  aria-label={`Open supplier panel for ${p.product_name}`}
                  title="View product & manage supplier order"
                  style={{ cursor: 'pointer' }}
                  onClick={() => setDrawerRow(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setDrawerRow(p); }
                  }}
                >
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

                  {/* ── Supplier-order status row ── */}
                  {(p.pending_order || !orderNeeded) && (
                  <div className="stbo-order-actions">
                    {p.pending_order ? (
                      <>
                        <span className="stbo-pending-tag">
                          ⏳ {p.pending_qty.toLocaleString('en-IN')} on order (awaiting receipt)
                        </span>
                        <button
                          className="stbo-edit-btn"
                          onClick={() => setDrawerRow(p)}
                          disabled={busyKey === p.product_key}
                          title="Open the supplier order panel"
                        >
                          ✏️ Edit
                        </button>
                        <button
                          className="stbo-receive-btn"
                          onClick={() => handleReceive(p)}
                          disabled={busyKey === p.product_key}
                        >
                          {busyKey === p.product_key ? 'Receiving…' : 'Mark Received'}
                        </button>
                      </>
                    ) : (
                      <span className="stbo-ok-note">Stock covers predicted demand ✓</span>
                    )}
                  </div>
                  )}
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

      {/* ── Supplier replenishment drawer (product image click) ── */}
      {drawerRow && (
        <ReplenishmentDrawer
          key={drawerRow.product_key ?? drawerRow.product_id}
          row={drawerRow}
          token={token}
          onClose={() => setDrawerRow(null)}
          onResult={handleDrawerResult}
        />
      )}

      {/* ── Bulk "Order All <tier> Demand Products" dialog ─────── */}
      {bulk.open && (
        <div className="stbo-modal-backdrop" onClick={() => !bulk.submitting && setBulk((b) => ({ ...b, open: false }))}>
          <div className="stbo-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={`Order all ${bulk.tier.toLowerCase()}-demand products`}>
            <h3 className="stbo-modal-title">{BULK_ACTIONS.find((a) => a.tier === bulk.tier)?.icon} Order All {bulk.tier} Demand Products</h3>

            <p className="stbo-modal-hint">
              ℹ️ Ordering <strong>requests stock from a supplier</strong> — your available stock
              only increases once the goods are <strong>received</strong> (“Mark Received”).
            </p>

            {bulk.loading && <p className="stbo-modal-muted">Loading {bulk.tier.toLowerCase()}-demand products…</p>}
            {bulk.error && <p className="stbo-modal-error">{bulk.error}</p>}

            {bulk.result ? (
              <>
                <p className="stbo-modal-summary">
                  {bulk.result.created > 0 && (
                    <>✅ Ordered <strong>{bulk.result.created.toLocaleString('en-IN')}</strong> product(s) ·{' '}
                      {bulk.result.total.toLocaleString('en-IN')} units total.</>
                  )}
                  {bulk.result.created === 0 && bulk.result.failed === 0 && (
                    <>No new orders were placed — every product is already covered by a pending order.</>
                  )}
                </p>
                {bulk.result.skipped > 0 && (
                  <p className="stbo-modal-muted">{bulk.result.skipped} product(s) skipped — already on order or no longer needs stock.</p>
                )}
                {bulk.result.failed > 0 && (
                  <>
                    <p className="stbo-modal-error">{bulk.result.failed} product(s) could not be ordered:</p>
                    <div className="stbo-modal-list">
                      {(bulk.result.failures || []).map((f) => (
                        <div key={f.product_key} className="stbo-modal-row">
                          <span className="stbo-modal-name">{f.product_name || f.product_key}</span>
                          <span className="stbo-modal-fail">{f.error}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                <div className="stbo-modal-actions">
                  <button className="stbo-modal-close" onClick={() => setBulk((b) => ({ ...b, open: false }))}>Done</button>
                </div>
              </>
            ) : (!bulk.loading && !bulk.error && (
              <>
                <p className="stbo-modal-summary">
                  <strong>{bulk.items.length.toLocaleString('en-IN')}</strong>{' '}
                  {bulk.tier.toLowerCase()}-demand product(s) need restocking ({bulk.total.toLocaleString('en-IN')}{' '}
                  units in total using each product’s recommended order quantity).{' '}
                  Review the list and untick anything you do not want to order.
                </p>
                {bulk.items.length > 0 && (
                  <label className="stbo-modal-toggle-all">
                    <input type="checkbox" checked={allSelected} onChange={toggleAllBulk} />
                    <span>{allSelected ? 'Deselect all' : 'Select all'} ({selectedItems.length} of {bulk.items.length} selected · {selectedUnits.toLocaleString('en-IN')} units)</span>
                  </label>
                )}
                <div className="stbo-modal-list">
                  {bulk.items.slice(0, 300).map((it) => (
                    <label key={it.product_key} className="stbo-modal-row stbo-modal-check-row">
                      <input
                        type="checkbox"
                        checked={!!bulk.selected[it.product_key]}
                        onChange={() => toggleBulkItem(it.product_key)}
                        disabled={bulk.submitting}
                        aria-label={`Include ${it.product_name} in this order`}
                      />
                      <span className="stbo-modal-name">{it.product_name}</span>
                      <span className="stbo-modal-qty">+{it.recommended_qty.toLocaleString('en-IN')}</span>
                    </label>
                  ))}
                  {bulk.items.length > 300 && (
                    <div className="stbo-modal-muted">…and {bulk.items.length - 300} more selected product(s) — the full list stays selected; adjust individually from the filtered view below if needed.</div>
                  )}
                  {bulk.items.length === 0 && (
                    <div className="stbo-modal-muted">Nothing to order — every {bulk.tier.toLowerCase()}-demand product has enough stock or is already on order.</div>
                  )}
                </div>
                <div className="stbo-modal-actions">
                  <button className="stbo-modal-cancel" onClick={() => setBulk((b) => ({ ...b, open: false }))} disabled={bulk.submitting}>Cancel</button>
                  <button
                    className="stbo-modal-confirm"
                    onClick={confirmBulk}
                    disabled={bulk.submitting || selectedItems.length === 0}
                  >
                    {bulk.submitting
                      ? 'Placing orders…'
                      : `Confirm ${selectedItems.length.toLocaleString('en-IN')} Order(s) · ${selectedUnits.toLocaleString('en-IN')} units`}
                  </button>
                </div>
              </>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
