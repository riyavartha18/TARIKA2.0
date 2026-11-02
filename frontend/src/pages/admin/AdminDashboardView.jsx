import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { getAdminProductPerformance } from '../../services/api';
import ProductPerformanceMap from './ProductPerformanceMap';
import {
  Sparkles,
  ShieldCheck,
  Layers,
  RefreshCw,
  AlertCircle,
  ArrowRight,
} from 'lucide-react';

export default function AdminDashboardView() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [map, setMap] = useState(null);

  // Authenticated user display name
  const firstName = user?.first_name?.trim();
  const lastName = user?.last_name?.trim();
  const fullName = user?.full_name?.trim() || user?.name?.trim();
  const displayName = (firstName || lastName)
    ? `${firstName || ''} ${lastName || ''}`.trim()
    : (fullName || 'Admin');

  const fetchMap = async () => {
    setLoading(true);
    setError(null);
    const res = await getAdminProductPerformance(token);
    if (res.success && res.data) {
      setMap(res.data);
    } else {
      setError(res.error || 'Unable to load the product performance map.');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchMap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // The existing Demand Forecasting module inside Admin Analysis: the analytics
  // view opens that module when the ?view= deep link is present on mount.
  const handleViewMore = () => {
    navigate('/admin/analysis?view=demand-forecasting');
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '5rem 1rem' }}>
        <div
          className="tarika-auth-spinner"
          style={{
            margin: '0 auto 1.25rem',
            width: '2.5rem',
            height: '2.5rem',
            borderColor: 'rgba(216, 114, 126, 0.25)',
            borderTopColor: '#D8727E',
          }}
        />
        <p style={{ color: '#6B5E63', fontWeight: 600, fontSize: '0.95rem' }}>
          Reading delivered sales and revenue for every catalog subcategory from Neon…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="admin-card" style={{ maxWidth: '600px', margin: '3rem auto', textAlign: 'center' }}>
        <div
          style={{
            width: '54px',
            height: '54px',
            borderRadius: '50%',
            backgroundColor: '#FEF2F2',
            color: '#DC2626',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1rem',
          }}
        >
          <AlertCircle size={28} />
        </div>
        <h3 style={{ margin: '0 0 0.5rem', fontFamily: 'var(--font-serif)', color: '#1F191B' }}>
          Dashboard Loading Error
        </h3>
        <p style={{ color: '#6B5E63', fontSize: '0.9rem', marginBottom: '1.5rem' }}>{error}</p>
        <button
          onClick={fetchMap}
          className="tarika-btn-primary"
          style={{ margin: '0 auto', padding: '0.65rem 1.5rem', fontSize: '0.85rem' }}
        >
          <RefreshCw size={14} />
          <span>Retry Connection</span>
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* 1. Project branding + admin overview */}
      <div className="admin-dashboard-hero">
        <Sparkles size={160} className="admin-dashboard-hero-bg" />
        <span className="admin-hero-badge">
          <ShieldCheck size={13} />
          Intelligent Retail Analytics
        </span>
        <h1 className="admin-hero-title tarika-project-title">
          TARIKA: Intelligent Retail Analytics System
        </h1>
        <p className="admin-hero-eyebrow">Admin Overview</p>
        <p className="admin-hero-desc">
          Welcome{displayName && displayName !== 'Admin' ? ` back, ${displayName}` : ' back'}! Monitor how
          TARIKA&apos;s product catalog performs across sales, revenue, and demand.
        </p>
      </div>

      {/* 2. Product Performance Map — the graph is the whole section; every
            figure lives inside it and opens on click. */}
      <section className="admin-card ppm-section">
        <div className="admin-card-header ppm-head">
          <div className="admin-card-title-group">
            <div className="ppm-head-icon">
              <Layers size={20} />
            </div>
            <div>
              <h2 className="ppm-head-title">Product Performance Map</h2>
              <p className="ppm-head-subtitle">Analyze product performance based on sales and revenue.</p>
            </div>
          </div>

          {/* Transparent View More — outline/text only, never a filled button. */}
          <button type="button" className="ppm-view-more" onClick={handleViewMore}>
            <span>View More</span>
            <ArrowRight size={15} />
          </button>
        </div>

        <ProductPerformanceMap payload={map} />
      </section>
    </div>
  );
}
