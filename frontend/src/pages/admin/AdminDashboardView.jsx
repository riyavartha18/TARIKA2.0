import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getAdminDashboardStats } from '../../services/api';
import {
  ShieldCheck,
  Users,
  Building2,
  Package,
  ShoppingBag,
  Truck,
  RotateCcw,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Activity,
  DollarSign,
  Warehouse as WarehouseIcon,
} from 'lucide-react';

export default function AdminDashboardView() {
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);

  // Authenticated user display name
  const firstName = user?.first_name?.trim();
  const lastName = user?.last_name?.trim();
  const fullName = user?.full_name?.trim() || user?.name?.trim();
  const displayName = (firstName || lastName)
    ? `${firstName || ''} ${lastName || ''}`.trim()
    : (fullName || 'Admin');

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    const res = await getAdminDashboardStats(token);
    if (res.success && res.data) {
      setStats(res.data);
    } else {
      setError(res.error || 'Unable to load dashboard summary.');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchStats();
  }, [token]);

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
          Loading system-wide dashboard metrics from database…
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
        <p style={{ color: '#6B5E63', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
          {error}
        </p>
        <button
          onClick={fetchStats}
          className="tarika-btn-primary"
          style={{ margin: '0 auto', padding: '0.65rem 1.5rem', fontSize: '0.85rem' }}
        >
          <RefreshCw size={14} />
          <span>Retry Connection</span>
        </button>
      </div>
    );
  }

  const kpis = stats?.kpis || {};
  const orderOverview = stats?.order_overview || {};
  const recentOrders = stats?.recent_orders || [];
  const inventory = stats?.inventory_snapshot || {};
  const alerts = stats?.operational_alerts || {};
  const activityFeed = stats?.recent_activity || [];

  // Revenue Formatter
  const formattedRevenue = kpis.total_revenue !== undefined
    ? `₹${Math.round(kpis.total_revenue).toLocaleString('en-IN')}`
    : '₹0';

  // Calculate order progress percentages safely
  const totalOrdersCount = orderOverview.total || 1;
  const pendingPct = Math.round(((orderOverview.pending || 0) / totalOrdersCount) * 100);
  const processingPct = Math.round(((orderOverview.processing || 0) / totalOrdersCount) * 100);
  const deliveredPct = Math.round(((orderOverview.delivered || 0) / totalOrdersCount) * 100);
  const cancelledPct = Math.round(((orderOverview.cancelled || 0) / totalOrdersCount) * 100);

  return (
    <div>
      {/* 1. Executive Hero Header */}
      <div className="admin-dashboard-hero">
        <Sparkles size={160} className="admin-dashboard-hero-bg" />
        <span className="admin-hero-badge">
          <ShieldCheck size={13} />
          Live Executive Oversight
        </span>
        <h1 className="admin-hero-title">
          Welcome, {displayName}
        </h1>
        <p className="admin-hero-desc">
          System-wide performance overview for TARIKA Retail. Real-time metrics across customers, orders, catalog products, fulfillment warehouses, and logistics operations.
        </p>
      </div>

      {/* 2. KPI Summary Cards Grid */}
      <div className="admin-metrics-grid">
        {/* Total Revenue */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <DollarSign size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' }}>
              Gross Sales
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Total Revenue</p>
            <p className="admin-metric-val">{formattedRevenue}</p>
            <p className="admin-metric-subtext">Calculated from confirmed non-cancelled orders</p>
          </div>
        </div>

        {/* Total Orders */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <ShoppingBag size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#EFF6FF', color: '#2563EB', borderColor: '#BFDBFE' }}>
              System Orders
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Total Orders</p>
            <p className="admin-metric-val">{(kpis.total_orders || 0).toLocaleString('en-IN')}</p>
            <p className="admin-metric-subtext">{orderOverview.delivered || 0} delivered, {orderOverview.processing || 0} in fulfillment</p>
          </div>
        </div>

        {/* Total Customers */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Users size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#FAF7F5', color: '#8E3642', borderColor: '#F0E2E0' }}>
              Registered Base
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Total Customers</p>
            <p className="admin-metric-val">{(kpis.total_customers || 0).toLocaleString('en-IN')}</p>
            <p className="admin-metric-subtext">Active accounts in customer database</p>
          </div>
        </div>

        {/* Total Products */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Package size={22} />
            </div>
            <span className="admin-metric-status">Active Catalog</span>
          </div>
          <div>
            <p className="admin-metric-title">Total Products</p>
            <p className="admin-metric-val">{(kpis.total_products || 0).toLocaleString('en-IN')}</p>
            <p className="admin-metric-subtext">Across {(inventory.total_warehouses || 0)} warehouse facilities</p>
          </div>
        </div>
      </div>

      {/* 3. Main Split Section: Order Overview + Operational Alerts */}
      <div className="admin-grid-2col">
        {/* Order Overview & Breakdown */}
        <div className="admin-card">
          <div className="admin-card-header">
            <div className="admin-card-title-group">
              <ShoppingBag size={18} color="#B8505E" />
              <h3 className="admin-card-title">Order Fulfillment Status</h3>
            </div>
            <span style={{ fontSize: '0.75rem', color: '#6B5E63', fontWeight: 600 }}>
              Total: {orderOverview.total || 0} Orders
            </span>
          </div>

          <div className="admin-order-stats-grid">
            <div className="admin-order-stat-chip">
              <span className="admin-stat-label">Pending</span>
              <span className="admin-stat-count" style={{ color: '#D97706' }}>{orderOverview.pending || 0}</span>
            </div>
            <div className="admin-order-stat-chip">
              <span className="admin-stat-label">Processing</span>
              <span className="admin-stat-count" style={{ color: '#2563EB' }}>{orderOverview.processing || 0}</span>
            </div>
            <div className="admin-order-stat-chip">
              <span className="admin-stat-label">Delivered</span>
              <span className="admin-stat-count" style={{ color: '#059669' }}>{orderOverview.delivered || 0}</span>
            </div>
            <div className="admin-order-stat-chip">
              <span className="admin-stat-label">Cancelled</span>
              <span className="admin-stat-count" style={{ color: '#DC2626' }}>{orderOverview.cancelled || 0}</span>
            </div>
          </div>

          <div className="admin-progress-container">
            <div className="admin-progress-item">
              <div className="admin-progress-info">
                <span>Delivered Orders</span>
                <span>{deliveredPct}% ({orderOverview.delivered || 0})</span>
              </div>
              <div className="admin-progress-track">
                <div className="admin-progress-fill" style={{ width: `${deliveredPct}%`, backgroundColor: '#059669' }} />
              </div>
            </div>

            <div className="admin-progress-item">
              <div className="admin-progress-info">
                <span>Processing in Warehouse</span>
                <span>{processingPct}% ({orderOverview.processing || 0})</span>
              </div>
              <div className="admin-progress-track">
                <div className="admin-progress-fill" style={{ width: `${processingPct}%`, backgroundColor: '#2563EB' }} />
              </div>
            </div>

            <div className="admin-progress-item">
              <div className="admin-progress-info">
                <span>Pending Confirmation</span>
                <span>{pendingPct}% ({orderOverview.pending || 0})</span>
              </div>
              <div className="admin-progress-track">
                <div className="admin-progress-fill" style={{ width: `${pendingPct}%`, backgroundColor: '#D97706' }} />
              </div>
            </div>

            <div className="admin-progress-item">
              <div className="admin-progress-info">
                <span>Cancelled Orders</span>
                <span>{cancelledPct}% ({orderOverview.cancelled || 0})</span>
              </div>
              <div className="admin-progress-track">
                <div className="admin-progress-fill" style={{ width: `${cancelledPct}%`, backgroundColor: '#DC2626' }} />
              </div>
            </div>
          </div>
        </div>

        {/* Operational Alerts / Requires Attention */}
        <div className="admin-card">
          <div className="admin-card-header">
            <div className="admin-card-title-group">
              <AlertTriangle size={18} color="#D97706" />
              <h3 className="admin-card-title">Operational Alerts</h3>
            </div>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '9999px', backgroundColor: '#FFFBEB', color: '#D97706', border: '1px solid #FDE68A' }}>
              Action Needed
            </span>
          </div>

          <div className="admin-alerts-list">
            <div className="admin-alert-item alert-warning">
              <div className="admin-alert-left">
                <RotateCcw size={18} color="#D97706" />
                <div>
                  <p style={{ margin: 0, fontWeight: 700, fontSize: '0.85rem', color: '#78350F' }}>Pending Return Requests</p>
                  <p style={{ margin: 0, fontSize: '0.75rem', color: '#92400E' }}>Requires inspection and approval</p>
                </div>
              </div>
              <span className="admin-alert-badge" style={{ backgroundColor: '#FEF3C7', color: '#B45309' }}>
                {alerts.pending_returns || 0}
              </span>
            </div>

            <div className="admin-alert-item alert-info">
              <div className="admin-alert-left">
                <Truck size={18} color="#2563EB" />
                <div>
                  <p style={{ margin: 0, fontWeight: 700, fontSize: '0.85rem', color: '#1E40AF' }}>Pending Deliveries</p>
                  <p style={{ margin: 0, fontSize: '0.75rem', color: '#1D4ED8' }}>In transit or dispatching</p>
                </div>
              </div>
              <span className="admin-alert-badge" style={{ backgroundColor: '#DBEAFE', color: '#1E40AF' }}>
                {alerts.pending_deliveries || 0}
              </span>
            </div>

            <div className="admin-alert-item alert-danger">
              <div className="admin-alert-left">
                <Package size={18} color="#DC2626" />
                <div>
                  <p style={{ margin: 0, fontWeight: 700, fontSize: '0.85rem', color: '#991B1B' }}>Low-Stock Products</p>
                  <p style={{ margin: 0, fontSize: '0.75rem', color: '#B91C1C' }}>Stock level ≤ 5 units</p>
                </div>
              </div>
              <span className="admin-alert-badge" style={{ backgroundColor: '#FEE2E2', color: '#991B1B' }}>
                {alerts.low_stock_products || 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Recent Orders Table & Activity Feed */}
      <div className="admin-grid-2col" style={{ gridTemplateColumns: '1.6fr 1fr' }}>
        {/* Recent Orders Card */}
        <div className="admin-card">
          <div className="admin-card-header">
            <div className="admin-card-title-group">
              <ShoppingBag size={18} color="#B8505E" />
              <h3 className="admin-card-title">Recent System Orders</h3>
            </div>
          </div>

          {recentOrders.length === 0 ? (
            <p style={{ color: '#6B5E63', fontStyle: 'italic', fontSize: '0.85rem', padding: '1rem 0' }}>
              No order records found in database.
            </p>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Order Reference</th>
                    <th>Customer</th>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentOrders.map((ord, idx) => {
                    const statusLower = (ord.order_status || '').toLowerCase();
                    let badgeClass = 'admin-status-pending';
                    if (statusLower === 'delivered' || statusLower === 'completed') badgeClass = 'admin-status-delivered';
                    else if (statusLower === 'processing' || statusLower === 'dispatched') badgeClass = 'admin-status-processing';
                    else if (statusLower === 'cancelled') badgeClass = 'admin-status-cancelled';

                    return (
                      <tr key={ord.order_id || idx}>
                        <td style={{ fontWeight: 700, fontFamily: 'monospace' }}>
                          #{ord.order_id}
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{ord.customer_name}</div>
                          {ord.customer_email && (
                            <div style={{ fontSize: '0.72rem', color: '#6B5E63' }}>{ord.customer_email}</div>
                          )}
                        </td>
                        <td style={{ color: '#6B5E63', fontSize: '0.8rem' }}>
                          {ord.order_date}
                        </td>
                        <td style={{ fontWeight: 800, color: '#B8505E' }}>
                          ₹{Number(ord.total_amount || 0).toLocaleString('en-IN')}
                        </td>
                        <td>
                          <span className={`admin-status-badge ${badgeClass}`}>
                            {ord.order_status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Recent Activity Timeline Feed */}
        <div className="admin-card">
          <div className="admin-card-header">
            <div className="admin-card-title-group">
              <Activity size={18} color="#B8505E" />
              <h3 className="admin-card-title">Recent System Activity</h3>
            </div>
          </div>

          {activityFeed.length === 0 ? (
            <p style={{ color: '#6B5E63', fontStyle: 'italic', fontSize: '0.85rem', padding: '1rem 0' }}>
              No recent activity logs available.
            </p>
          ) : (
            <div className="admin-activity-list">
              {activityFeed.map((act) => (
                <div key={act.id} className="admin-activity-item">
                  <div className="admin-activity-icon">
                    {act.type === 'ORDER' && <ShoppingBag size={16} />}
                    {act.type === 'RETURN' && <RotateCcw size={16} />}
                    {act.type === 'DELIVERY' && <Truck size={16} />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <p style={{ margin: 0, fontWeight: 700, fontSize: '0.825rem', color: '#1F191B' }}>
                        {act.title}
                      </p>
                      <span style={{ fontSize: '0.7rem', color: '#9E8F94' }}>{act.timestamp}</span>
                    </div>
                    <p style={{ margin: '0.15rem 0 0', fontSize: '0.75rem', color: '#6B5E63' }}>
                      {act.subtitle}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 5. Inventory & Warehouse Snapshot */}
      <div className="admin-card" style={{ marginBottom: '1rem' }}>
        <div className="admin-card-header">
          <div className="admin-card-title-group">
            <WarehouseIcon size={18} color="#B8505E" />
            <h3 className="admin-card-title">Inventory & Warehouse Facilities Snapshot</h3>
          </div>
          <span style={{ fontSize: '0.78rem', color: '#6B5E63', fontWeight: 600 }}>
            {inventory.total_warehouses || 0} Facilities • {inventory.total_stock_units || 0} Total Stock Units
          </span>
        </div>

        <div className="admin-warehouse-mini-grid">
          {(inventory.warehouses || []).map((wh) => (
            <div key={wh.warehouse_id} className="admin-warehouse-mini-card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {wh.warehouse_id}
                </span>
                <span style={{ fontSize: '0.7rem', color: '#059669', fontWeight: 700 }}>Active</span>
              </div>
              <p style={{ margin: 0, fontWeight: 700, fontSize: '0.9rem', color: '#1F191B' }}>
                {wh.warehouse_name}
              </p>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63' }}>
                City: <strong>{wh.city}</strong>
              </p>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63' }}>
                Manager: <strong>{wh.manager_name}</strong>
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
