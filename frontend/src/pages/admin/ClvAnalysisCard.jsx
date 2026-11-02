import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getClvSummary, getClvSegments } from '../../services/api';
import { Wallet, CheckCircle2, Loader2, ChevronRight } from 'lucide-react';

// Compact CLV overview card for the Admin Analysis page. It follows the same
// .admin-card design as the RFM / demand-forecasting modules and only reads
// the small cached summary + tier distribution, so it never bloats the
// initial page load. Clicking View More opens the full CLV dashboard.
const formatMoney = (value) =>
  `₹${Number(value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export default function ClvAnalysisCard({ onOpen }) {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [segments, setSegments] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await getClvSummary(token);
    if (res.success) {
      setSummary(res);
      const seg = await getClvSegments(token);
      if (seg.success) setSegments(seg);
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const available = summary?.available;

  // Only poll while the first state build is still in flight; a completed
  // snapshot keeps the card static (refreshes happen on dashboard opens).
  useEffect(() => {
    if (available) return undefined;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [available, load]);

  const totals = summary?.totals || {};
  const base = Number(summary?.buyer_count || 0) || 1;
  const tiers = segments?.tiers || [];
  const atRisk = segments?.at_risk || {};

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
          <div style={{ width: '52px', height: '52px', borderRadius: '14px', backgroundColor: '#FBF0E9', color: '#B8505E', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Wallet size={26} />
          </div>
          <div>
            <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.6rem', fontWeight: 700, color: '#1F191B', margin: 0, lineHeight: 1.2 }}>
              Customer Lifetime Value
            </h2>
            <span style={{ fontSize: '0.75rem', color: '#9E8F94', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              FEATURE #4 &bull; HISTORICAL &amp; PREDICTED CUSTOMER VALUE
            </span>
          </div>
        </div>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.95rem', borderRadius: '9999px', backgroundColor: available ? '#ECFDF5' : '#FBF5F4', border: `1px solid ${available ? '#A7F3D0' : '#F0E2E0'}`, color: available ? '#059669' : '#9E8F94', fontSize: '0.82rem', fontWeight: 600 }}>
          {available ? <><CheckCircle2 size={14} /> Active</> : <><Loader2 size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> Preparing</>}
        </span>
      </div>

      {/* Headline KPIs + value distribution preview */}
      <div style={{ marginBottom: '1.5rem', borderRadius: '14px', background: '#FAF7F5', border: '1px solid rgba(216, 114, 126, 0.1)', padding: '1.25rem' }}>
        {loading ? (
          <div style={{ height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94', fontSize: '0.85rem' }}>Loading CLV preview…</div>
        ) : !available ? (
          <div style={{ height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94', fontSize: '0.85rem', textAlign: 'center' }}>
            The first CLV analysis is being prepared automatically.<br />Open the dashboard to watch it build.
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.9rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63' }}>
                Avg Historical CLV {formatMoney(totals.avg_historical_clv)}
              </span>
              <span style={{ fontSize: '0.78rem', color: '#9E8F94' }}>
                {Number(totals.high_value_count || 0).toLocaleString()} high-value ({totals.high_value_pct || 0}%)
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {[...tiers, { tier: 'At Risk (RFM)', count: atRisk.count || 0 }].map((t) => {
                const pct = Math.round((Number(t.count || 0) / base) * 100);
                const isOverlay = String(t.tier).startsWith('At Risk');
                return (
                  <div key={t.tier} style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                    <span style={{ fontSize: '0.8rem', color: '#1F191B', fontWeight: 600, width: 140, flexShrink: 0 }}>{t.tier}</span>
                    <span style={{ flex: 1, height: 8, borderRadius: 6, background: 'rgba(31,25,27,0.06)', overflow: 'hidden' }}>
                      <span style={{ display: 'block', height: '100%', width: `${Math.min(100, pct)}%`, background: isOverlay ? '#D8727E' : '#B8505E', borderRadius: 6 }} />
                    </span>
                    <span style={{ fontSize: '0.78rem', color: '#6B5E63', fontWeight: 700, width: 60, textAlign: 'right' }}>{Number(t.count || 0).toLocaleString()}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Bottom Row Action */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '1.25rem', borderTop: '1px solid rgba(216, 114, 126, 0.15)', flexWrap: 'wrap', gap: '0.75rem' }}>
        <span style={{ fontSize: '0.9rem', color: '#6B5E63' }}>Open the full Customer Lifetime Value dashboard</span>
        <button
          style={{
            background: 'linear-gradient(135deg, #B8505E 0%, #8E3642 100%)',
            color: '#FFFFFF', padding: '0.7rem 1.5rem', borderRadius: '9999px', border: 'none',
            fontSize: '0.88rem', fontWeight: 600, cursor: 'pointer', display: 'inline-flex',
            alignItems: 'center', gap: '0.5rem', boxShadow: '0 4px 14px rgba(184, 80, 94, 0.25)',
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
