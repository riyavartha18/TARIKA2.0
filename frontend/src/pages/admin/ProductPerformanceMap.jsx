import React, { useEffect, useMemo, useState } from 'react';
import { PackageSearch, X, ArrowRight } from 'lucide-react';

/* ==========================================================================
   PRODUCT PERFORMANCE MAP — four-quadrant map (pure SVG, no plotted points).

   Sales increases to the right, revenue increases upwards; the dashed cross is
   the median split, so the four fields are exactly the four performance groups.

   The map is a clean label-only layout: each quadrant carries its name and its
   one-line definition, and nothing else. All figures — totals, the subcategories
   filed in a group and their best-selling products — open in a sheet when the
   admin clicks a quadrant, and a subcategory's own detail opens when they click
   its name in that sheet.

   The analytics are untouched: the classification, the subcategory totals and the
   product rows all come from the same backend payload as before.
   ========================================================================== */

const QUADRANT_STYLE = {
  star: { color: '#059669', tint: 'rgba(5, 150, 105, 0.07)', soft: '#ECFDF5', text: '#065F46' },
  premium: { color: '#2563EB', tint: 'rgba(37, 99, 235, 0.06)', soft: '#EFF6FF', text: '#1E40AF' },
  volume: { color: '#D97706', tint: 'rgba(217, 119, 6, 0.06)', soft: '#FFFBEB', text: '#92400E' },
  attention: { color: '#DC2626', tint: 'rgba(220, 38, 38, 0.05)', soft: '#FEF2F2', text: '#991B1B' },
};

// The single line under each quadrant heading, as specified for the map.
const QUADRANT_LINE = {
  star: 'High sales + high revenue',
  premium: 'Low sales + high revenue',
  volume: 'High sales + low revenue',
  attention: 'Low sales + low revenue',
};

// Layout box inside the 1000 x 620 viewBox (the axes keep their place).
const VB = { w: 1000, h: 620, left: 84, right: 26, top: 36, bottom: 62 };
const PLOT = {
  x: VB.left,
  y: VB.top,
  w: VB.w - VB.left - VB.right,
  h: VB.h - VB.top - VB.bottom,
};

/** log10(1+v) — the transform the split positions are measured on. */
const logScale = (v) => Math.log10(1 + Math.max(0, Number(v) || 0));

const fmtInt = (n) => Number(n || 0).toLocaleString('en-IN');

/** Rupees with Indian grouping, rounded to whole rupees for readability. */
const fmtRupee = (n) => `₹${Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export default function ProductPerformanceMap({ payload }) {
  // Opened detail: { type: 'quadrant' | 'subcategory', key } or null.
  const [detail, setDetail] = useState(null);

  const points = useMemo(() => payload?.points || [], [payload]);
  const quadrants = useMemo(() => payload?.quadrants || [], [payload]);

  // Where the dashed cross goes. The medians are positioned on the same log
  // ranges the subcategory totals span, so the split stays where the data puts
  // it even though no points are drawn any more.
  const dividers = useMemo(() => {
    const list = payload?.points || [];
    const thresholds = payload?.thresholds || { sales: { value: 0 }, revenue: { value: 0 } };
    const maxUnits = Math.max(1, ...list.map((p) => p.units_sold));
    const maxRevenue = Math.max(1, ...list.map((p) => p.revenue));
    const xFrac = logScale(thresholds.sales.value) / (logScale(maxUnits) || 1);
    const yFrac = logScale(thresholds.revenue.value) / (logScale(maxRevenue) || 1);
    return {
      x: PLOT.x + Math.min(1, Math.max(0, xFrac)) * PLOT.w,
      y: PLOT.y + PLOT.h - Math.min(1, Math.max(0, yFrac)) * PLOT.h,
    };
  }, [payload]);

  // Escape closes the detail sheet.
  useEffect(() => {
    if (!detail) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') setDetail(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [detail]);

  if (!payload?.data_available || points.length === 0) {
    return (
      <div className="ppm-empty">
        <PackageSearch size={30} />
        <h3 className="ppm-empty-title">No performance data to plot yet</h3>
        <p className="ppm-empty-text">
          {payload?.note
            || 'The connected database has no delivered (completed) sales for the active catalog, '
            + 'so nothing can be classified. No figures have been estimated.'}
        </p>
      </div>
    );
  }

  const cutX = dividers.x;
  const cutY = dividers.y;

  // The four clickable fields: heading + definition line, centred in the field.
  const quadrantFields = [
    { key: 'star', x: cutX, y: PLOT.y, w: PLOT.x + PLOT.w - cutX, h: cutY - PLOT.y },
    { key: 'premium', x: PLOT.x, y: PLOT.y, w: cutX - PLOT.x, h: cutY - PLOT.y },
    { key: 'volume', x: cutX, y: cutY, w: PLOT.x + PLOT.w - cutX, h: PLOT.y + PLOT.h - cutY },
    { key: 'attention', x: PLOT.x, y: cutY, w: cutX - PLOT.x, h: PLOT.y + PLOT.h - cutY },
  ].map((rect) => ({
    ...rect,
    meta: quadrants.find((q) => q.key === rect.key),
    cx: rect.x + rect.w / 2,
    // Sits slightly above the geometric centre so the two lines read as one block.
    cy: rect.y + rect.h / 2,
  }));

  const activeQuadrant = detail?.type === 'quadrant'
    ? quadrants.find((q) => q.key === detail.key)
    : null;
  const activePoint = detail?.type === 'subcategory'
    ? points.find((p) => p.key === detail.key)
    : null;
  const activeStyleKey = activePoint ? activePoint.quadrant : activeQuadrant?.key;

  const openPoint = (point) => setDetail({ type: 'subcategory', key: point.key });
  const openQuadrant = (key) => setDetail({ type: 'quadrant', key });

  // Best sellers of the clicked group: the real top products of its subcategories.
  const groupProducts = activeQuadrant
    ? points
      .filter((p) => p.quadrant === activeQuadrant.key)
      .flatMap((p) => p.top_products.map((prod) => ({ ...prod, subcategory: p.subcategory })))
      .sort((a, b) => b.units_sold - a.units_sold || b.revenue - a.revenue)
      .slice(0, 10)
    : [];

  return (
    <div className="ppm">
      <div className="ppm-chart-wrap">
        <svg
          className="ppm-svg"
          viewBox={`0 0 ${VB.w} ${VB.h}`}
          role="img"
          aria-label="Product performance map: four quadrants of delivered sales and delivered revenue"
        >
          {/* Quadrant fields: name + definition line, nothing else */}
          {quadrantFields.map((rect) => {
            const style = QUADRANT_STYLE[rect.key];
            const isOpen = detail?.type === 'quadrant' && detail.key === rect.key;
            return (
              <g key={rect.key}>
                <rect
                  x={rect.x}
                  y={rect.y}
                  width={rect.w}
                  height={rect.h}
                  fill={style.tint}
                  stroke={isOpen ? style.color : 'rgba(216, 114, 126, 0.12)'}
                  strokeWidth={isOpen ? 2 : 1}
                  className="ppm-quadrant-rect"
                  onClick={() => openQuadrant(rect.key)}
                />
                <text
                  x={rect.cx}
                  y={rect.cy - 12}
                  textAnchor="middle"
                  className="ppm-quadrant-name"
                  fill={style.text}
                  onClick={() => openQuadrant(rect.key)}
                >
                  {rect.meta?.label || rect.key}
                </text>
                <text
                  x={rect.cx}
                  y={rect.cy + 22}
                  textAnchor="middle"
                  className="ppm-quadrant-line"
                  fill={style.text}
                  onClick={() => openQuadrant(rect.key)}
                >
                  {QUADRANT_LINE[rect.key]}
                </text>
              </g>
            );
          })}

          {/* Median split */}
          <line x1={cutX} y1={PLOT.y} x2={cutX} y2={PLOT.y + PLOT.h} className="ppm-divider" />
          <line x1={PLOT.x} y1={cutY} x2={PLOT.x + PLOT.w} y2={cutY} className="ppm-divider" />

          {/* Axes */}
          <line x1={PLOT.x} y1={PLOT.y + PLOT.h} x2={PLOT.x + PLOT.w} y2={PLOT.y + PLOT.h} className="ppm-axis" />
          <line x1={PLOT.x} y1={PLOT.y} x2={PLOT.x} y2={PLOT.y + PLOT.h} className="ppm-axis" />
          <text x={PLOT.x + PLOT.w / 2} y={VB.h - 12} textAnchor="middle" className="ppm-axis-title">
            Sales → (units sold, delivered orders only)
          </text>
          <text
            x={20}
            y={PLOT.y + PLOT.h / 2}
            textAnchor="middle"
            className="ppm-axis-title"
            transform={`rotate(-90 20 ${PLOT.y + PLOT.h / 2})`}
          >
            Revenue ↑ (₹ realised, delivered orders only)
          </text>
        </svg>
      </div>

      {/* ------------------------------------------------------------------
          Click detail: quadrant group, or one subcategory
         ------------------------------------------------------------------ */}
      {(activeQuadrant || activePoint) && (
        <>
          <div className="ppm-sheet-backdrop" onClick={() => setDetail(null)} />
          <aside className="ppm-sheet" role="dialog" aria-modal="true" aria-label="Performance details">
            <div className="ppm-sheet-head">
              <div>
                <span
                  className="ppm-sheet-eyebrow"
                  style={{
                    color: QUADRANT_STYLE[activeStyleKey].text,
                    backgroundColor: QUADRANT_STYLE[activeStyleKey].soft,
                  }}
                >
                  {quadrants.find((q) => q.key === activeStyleKey)?.label}
                </span>
                <h3 className="ppm-sheet-title">
                  {activePoint ? activePoint.subcategory : activeQuadrant.label}
                </h3>
                <p className="ppm-sheet-sub">
                  {QUADRANT_LINE[activeStyleKey]}
                </p>
              </div>
              <button type="button" className="ppm-sheet-close" onClick={() => setDetail(null)} aria-label="Close details">
                <X size={17} />
              </button>
            </div>

            <div className="ppm-sheet-stats">
              <div className="ppm-sheet-stat">
                <span className="ppm-sheet-stat-label">Total products</span>
                <span className="ppm-sheet-stat-value">
                  {fmtInt(activePoint ? activePoint.product_count : activeQuadrant.product_count)}
                </span>
              </div>
              <div className="ppm-sheet-stat">
                <span className="ppm-sheet-stat-label">Total revenue</span>
                <span className="ppm-sheet-stat-value ppm-rev">
                  {fmtRupee(activePoint ? activePoint.revenue : activeQuadrant.revenue)}
                </span>
              </div>
              <div className="ppm-sheet-stat">
                <span className="ppm-sheet-stat-label">Total sales</span>
                <span className="ppm-sheet-stat-value">
                  {fmtInt(activePoint ? activePoint.units_sold : activeQuadrant.units_sold)} units
                </span>
              </div>
              <div className="ppm-sheet-stat">
                <span className="ppm-sheet-stat-label">Revenue / unit</span>
                <span className="ppm-sheet-stat-value">
                  {fmtRupee(activePoint
                    ? activePoint.revenue_per_unit
                    : (activeQuadrant.units_sold ? activeQuadrant.revenue / activeQuadrant.units_sold : 0))}
                </span>
              </div>
            </div>

            {/* Subcategories of the clicked quadrant */}
            {activeQuadrant && (
              <section className="ppm-sheet-block">
                <h4 className="ppm-sheet-block-title">Subcategories in this group</h4>
                <div className="ppm-table-wrap">
                  <table className="ppm-table">
                    <thead>
                      <tr>
                        <th>Subcategory</th>
                        <th className="ppm-num">Products</th>
                        <th className="ppm-num">Units</th>
                        <th className="ppm-num">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {points
                        .filter((p) => p.quadrant === activeQuadrant.key)
                        .map((p) => (
                          <tr key={p.key}>
                            <td>
                              <button type="button" className="ppm-link" onClick={() => openPoint(p)}>
                                {p.subcategory}
                              </button>
                            </td>
                            <td className="ppm-num">{fmtInt(p.product_count)}</td>
                            <td className="ppm-num">{fmtInt(p.units_sold)}</td>
                            <td className="ppm-num ppm-rev">{fmtRupee(p.revenue)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* Best-selling products: the clicked subcategory, or the whole group */}
            <section className="ppm-sheet-block">
              <h4 className="ppm-sheet-block-title">
                {activePoint ? 'Best-selling products' : 'Top products in this group'}
              </h4>
              <div className="ppm-table-wrap">
                <table className="ppm-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      {activeQuadrant && <th>Subcategory</th>}
                      <th className="ppm-num">Units</th>
                      <th className="ppm-num">Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activePoint ? activePoint.top_products : groupProducts).map((prod) => (
                      <tr key={`${prod.product_key}-${prod.subcategory || ''}`}>
                        <td>
                          <div className="ppm-product-name">{prod.product_name}</div>
                          <code className="ppm-product-key">{prod.product_key}</code>
                        </td>
                        {activeQuadrant && <td className="ppm-muted">{prod.subcategory}</td>}
                        <td className="ppm-num">{fmtInt(prod.units_sold)}</td>
                        <td className="ppm-num ppm-rev">{fmtRupee(prod.revenue)}</td>
                      </tr>
                    ))}
                    {activePoint && activePoint.top_products.length === 0 && (
                      <tr>
                        <td colSpan={activeQuadrant ? 4 : 3} className="ppm-muted">
                          No delivered sales recorded for this subcategory yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <button type="button" className="ppm-sheet-close-link" onClick={() => setDetail(null)}>
              Back to map
              <ArrowRight size={14} />
            </button>
          </aside>
        </>
      )}
    </div>
  );
}
