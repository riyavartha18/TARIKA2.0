import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getRfmSummary } from '../../services/api';
import { KMEANS_CATEGORY_META } from '../../data/rfmSegments';
import { Users, CheckCircle2, Loader2, ChevronRight } from 'lucide-react';

// Compact RFM overview card for the Admin Analysis page. It follows the same
// .admin-card design as the other analysis modules and only reads the small
// cached summary meta, so it never bloats the initial page load. Clicking
// View More opens the full dashboard (handled by the parent).
export default function RfmAnalysisCard({ onOpen }) {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await getRfmSummary(token);
    setSummary(res.success ? res : null);
    setLoading(false);
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const available = summary?.available;

  // Only poll while the analysis is still being prepared. Once a completed
  // snapshot is available the card is static, keeping the page lightweight.
  useEffect(() => {
    if (available) return undefined;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [available, load]);

  const totals = summary?.totals || {};
  const kmeans = summary?.kmeans;
  const clusters = kmeans?.clusters || [];
  // Percentages are relative to the clustered buyer population, so the four
  // K-Means shares add up to ~100% exactly as the dashboard reports them.
  const base = Number(kmeans?.total || totals.total_eligible_buyers || 0) || 1;

  return (
    <div
      className="admin-card"
      onClick={onOpen}
      style={{
        padding: '2.25rem',
        borderRadius: '20px',
        border: '1px solid rgba(216, 114, 126, 0.2)',
        cursor: 'pointer',
        transition: 'all 0.25s ease',
        boxShadow: '0 8px 30px rgba(31, 25, 27, 0.04)',
        backgroundColor: '#FFFFFF',
      }}
    >
      {/* Card Top Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ width: '52px', height: '52px', borderRadius: '14px', backgroundColor: '#EAF3FB', color: '#3E7CB1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Users size={26} />
          </div>
          <div>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.6rem', fontWeight: 700, color: '#1F191B', margin: 0, lineHeight: 1.2 }}>
              RFM Customer Segmentation
            </h2>
            <span style={{ fontSize: '0.75rem', color: '#9E8F94', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              FEATURE #3 &bull; K-MEANS CUSTOMER GROUPING
            </span>
          </div>
        </div>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.95rem', borderRadius: '9999px', backgroundColor: available ? '#ECFDF5' : '#FBF5F4', border: `1px solid ${available ? '#A7F3D0' : '#F0E2E0'}`, color: available ? '#059669' : '#9E8F94', fontSize: '0.82rem', fontWeight: 600 }}>
          {available ? <><CheckCircle2 size={14} /> Active</> : <><Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> Preparing</>}
        </span>
      </div>

      {/* Segment distribution preview */}
      <div style={{ marginBottom: '1.5rem', borderRadius: '14px', background: '#FAF7F5', border: '1px solid rgba(216, 114, 126, 0.1)', padding: '1.25rem' }}>
        {loading ? (
          <div style={{ height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94', fontSize: '0.85rem' }}>Loading segmentation preview…</div>
        ) : !available ? (
          <div style={{ height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94', fontSize: '0.85rem', textAlign: 'center' }}>
            The first analysis is being prepared automatically.<br />Open the dashboard to watch it build.
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.9rem' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63' }}>{Number(totals.total_customers || 0).toLocaleString()} customers analyzed</span>
              <span style={{ fontSize: '0.78rem', color: '#9E8F94' }}>{Number(totals.total_eligible_buyers || 0).toLocaleString()} buyers</span>
            </div>
            {clusters.length === 0 ? (
              <div style={{ minHeight: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94', fontSize: '0.85rem', textAlign: 'center' }}>
                No K-Means clustering yet.<br />Open the dashboard to run it over the stored RFM values.
              </div>
            ) : (
              <>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#6B5E63', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.6rem' }}>
                  K-Means segmentation (4 clusters)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {clusters.slice(0, 4).map((c) => {
                    const pct = Math.round((Number(c.customer_count || 0) / base) * 100);
                    const meta = KMEANS_CATEGORY_META[c.category] || { color: '#B8505E' };
                    return (
                      <div key={`${c.category}-${c.cluster_id}`} style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                        <span style={{ fontSize: '0.8rem', color: '#1F191B', fontWeight: 600, width: 140, flexShrink: 0 }}>{c.category}</span>
                        <span style={{ flex: 1, height: 8, borderRadius: 6, background: 'rgba(31,25,27,0.06)', overflow: 'hidden' }}>
                          <span style={{ display: 'block', height: '100%', width: `${Math.min(100, pct)}%`, background: meta.color, borderRadius: 6 }} />
                        </span>
                        <span style={{ fontSize: '0.78rem', color: '#6B5E63', fontWeight: 700, width: 60, textAlign: 'right' }}>{Number(c.customer_count || 0).toLocaleString()}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Bottom Row Action */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '1.25rem', borderTop: '1px solid rgba(216, 114, 126, 0.15)', flexWrap: 'wrap', gap: '0.75rem' }}>
        <span style={{ fontSize: '0.9rem', color: '#6B5E63' }}>Open the full segmentation dashboard</span>
        <button
          style={{
            background: 'linear-gradient(135deg, #3E7CB1 0%, #2C5E88 100%)',
            color: '#FFFFFF', padding: '0.7rem 1.5rem', borderRadius: '9999px', border: 'none',
            fontSize: '0.88rem', fontWeight: 600, cursor: 'pointer', display: 'inline-flex',
            alignItems: 'center', gap: '0.5rem', boxShadow: '0 4px 14px rgba(62, 124, 177, 0.25)',
          }}
          onClick={(e) => { e.stopPropagation(); onOpen(); }}
        >
          <span>View More</span>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
