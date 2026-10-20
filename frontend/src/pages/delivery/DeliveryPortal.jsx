import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import {
  Truck,
  Package,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Search,
  RefreshCw,
  LogOut,
  MapPin,
  Phone,
  Eye,
  ShieldCheck,
  CheckCircle,
  RotateCcw,
  CornerUpLeft,
  XCircle,
  PackageCheck
} from 'lucide-react';
import {
  fetchDeliveryDashboard,
  fetchMyDeliveries,
  updateDeliveryStatus,
  fetchMyReturnPickups,
  updateReturnPickupStatus
} from './deliveryApi';
import DeliveryDetailsModal from './DeliveryDetailsModal';
import DeliveryExceptionModal from './DeliveryExceptionModal';
import ReturnExceptionModal from './ReturnExceptionModal';
import '../../styles/tarika.css';
import '../../styles/delivery-portal.css';

const FORWARD_STATUS_TABS = [
  { id: 'all', label: 'All Packages' },
  { id: 'Assigned', label: 'Ready for Pickup' },
  { id: 'Picked Up', label: 'Picked Up' },
  { id: 'In Transit', label: 'In Transit' },
  { id: 'Delivered', label: 'Delivered' },
  { id: 'exceptions', label: 'Exceptions' },
];

const RETURN_STATUS_TABS = [
  { id: 'all', label: 'All Returns' },
  { id: 'Pickup Assigned', label: 'Assigned' },
  { id: 'Pickup Accepted', label: 'Accepted' },
  { id: 'Picked Up', label: 'Picked Up' },
  { id: 'Received at Warehouse', label: 'At Warehouse' },
  { id: 'Completed', label: 'Completed' },
  { id: 'Failed', label: 'Exceptions' },
];

export default function DeliveryPortal() {
  const { user, token, logout } = useAuth();

  // Mode: 'forward' for outbound deliveries, 'returns' for customer return pickups
  const [portalMode, setPortalMode] = useState('forward');

  // Forward deliveries metrics
  const [metrics, setMetrics] = useState({
    total_assigned: 0,
    active_deliveries: 0,
    pending_pickup: 0,
    picked_up: 0,
    in_transit: 0,
    delivered: 0,
    delayed: 0,
    failed: 0,
    exceptions: 0,
  });

  const [partnerProfile, setPartnerProfile] = useState(null);
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Return pickups state
  const [returnPickups, setReturnPickups] = useState([]);
  const [returnLoading, setReturnLoading] = useState(false);
  const [returnActiveTab, setReturnActiveTab] = useState('all');
  const [returnMetrics, setReturnMetrics] = useState({
    total: 0,
    assigned: 0,
    accepted: 0,
    picked_up: 0,
    at_warehouse: 0,
    completed: 0,
    failed: 0,
  });

  // Modals state
  const [selectedDetailId, setSelectedDetailId] = useState(null);
  const [selectedExceptionDelivery, setSelectedExceptionDelivery] = useState(null);
  const [selectedExceptionReturn, setSelectedExceptionReturn] = useState(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [feedbackToast, setFeedbackToast] = useState(null);

  useEffect(() => {
    document.title = portalMode === 'returns'
      ? 'TARIKA — Return Pickups Dispatch'
      : 'TARIKA — Delivery Partner Dispatch';
  }, [portalMode]);

  // Search debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Show auto-dismiss toast
  const showToast = (message, type = 'success') => {
    setFeedbackToast({ message, type });
    setTimeout(() => {
      setFeedbackToast(null);
    }, 4000);
  };

  // Load Dashboard Metrics
  const loadMetrics = useCallback(async () => {
    if (!token) return;
    const res = await fetchDeliveryDashboard(token);
    if (res.success && res.data) {
      setMetrics(res.data.metrics || {});
      setPartnerProfile(res.data.employee || null);
    }
  }, [token]);

  // Load Deliveries list
  const loadDeliveries = useCallback(async (isRefresh = false) => {
    if (!token) return;
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    let statusParam = activeTab;
    if (activeTab === 'exceptions') {
      statusParam = '';
    }

    const res = await fetchMyDeliveries(token, {
      status: statusParam,
      search: debouncedSearch,
    });

    if (res.success) {
      let items = res.deliveries || [];
      if (activeTab === 'exceptions') {
        items = items.filter(d => ['delayed', 'failed'].includes((d.delivery_status || '').toLowerCase()));
      }
      setDeliveries(items);
    } else {
      showToast(res.error || 'Could not refresh deliveries.', 'error');
    }

    setLoading(false);
    setRefreshing(false);
  }, [token, activeTab, debouncedSearch]);

  // Load Return Pickups list & compute return metrics
  const loadReturnPickups = useCallback(async (isRefresh = false) => {
    if (!token) return;
    if (isRefresh) setRefreshing(true);
    else setReturnLoading(true);

    const res = await fetchMyReturnPickups(token, {
      status: returnActiveTab === 'all' ? '' : returnActiveTab,
      search: debouncedSearch,
    });

    if (res.success) {
      const items = res.returnPickups || [];
      setReturnPickups(items);

      // Fetch all returns without filter once to update metrics accurately
      const allRes = await fetchMyReturnPickups(token, { status: '', search: '' });
      if (allRes.success && Array.isArray(allRes.returnPickups)) {
        const all = allRes.returnPickups;
        setReturnMetrics({
          total: all.length,
          assigned: all.filter(r => (r.return_status || '').toLowerCase() === 'pickup assigned').length,
          accepted: all.filter(r => (r.return_status || '').toLowerCase() === 'pickup accepted').length,
          picked_up: all.filter(r => (r.return_status || '').toLowerCase() === 'picked up').length,
          at_warehouse: all.filter(r => (r.return_status || '').toLowerCase() === 'received at warehouse').length,
          completed: all.filter(r => (r.return_status || '').toLowerCase() === 'completed').length,
          failed: all.filter(r => (r.return_status || '').toLowerCase() === 'failed').length,
        });
      }
    } else {
      showToast(res.error || 'Could not load return pickups.', 'error');
    }

    setReturnLoading(false);
    setRefreshing(false);
  }, [token, returnActiveTab, debouncedSearch]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  useEffect(() => {
    if (portalMode === 'forward') {
      loadDeliveries();
    } else {
      loadReturnPickups();
    }
  }, [portalMode, loadDeliveries, loadReturnPickups]);

  const handleManualRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      loadMetrics(),
      portalMode === 'forward' ? loadDeliveries(true) : loadReturnPickups(true)
    ]);
    setRefreshing(false);
    showToast('Manifest updated to latest live status.');
  };

  // Handle Forward Lifecycle Transitions
  const handleStatusTransition = async (deliveryId, newStatus, reason = '') => {
    if (!token) return;
    setIsUpdatingStatus(true);

    const res = await updateDeliveryStatus(token, deliveryId, { status: newStatus, reason });
    setIsUpdatingStatus(false);

    if (res.success) {
      showToast(`Package ${deliveryId} updated to '${newStatus}'.`, 'success');
      loadMetrics();
      loadDeliveries(true);
    } else {
      showToast(res.error || `Failed to update status to '${newStatus}'.`, 'error');
    }
  };

  const handleConfirmException = async (deliveryId, statusType, reasonText) => {
    setSelectedExceptionDelivery(null);
    await handleStatusTransition(deliveryId, statusType, reasonText);
  };

  // Handle Return Pickup Status Transitions
  const handleReturnStatusTransition = async (returnId, newStatus, reason = '') => {
    if (!token) return;
    setIsUpdatingStatus(true);

    const res = await updateReturnPickupStatus(token, returnId, { status: newStatus, reason });
    setIsUpdatingStatus(false);

    if (res.success) {
      showToast(`Return ${returnId} updated to '${newStatus}'.`, 'success');
      loadReturnPickups(true);
    } else {
      showToast(res.error || `Failed to update return to '${newStatus}'.`, 'error');
    }
  };

  const handleConfirmReturnException = async (returnId, statusType, reasonText) => {
    setSelectedExceptionReturn(null);
    await handleReturnStatusTransition(returnId, statusType, reasonText);
  };


  return (
    <div className="delivery-portal-root">
      {/* Toast Notification */}
      {feedbackToast && (
        <div style={{
          position: 'fixed',
          bottom: '2rem',
          right: '2rem',
          zIndex: 9999,
          background: feedbackToast.type === 'error' ? '#BE123C' : '#1F191B',
          color: '#FFFFFF',
          padding: '0.85rem 1.4rem',
          borderRadius: '12px',
          boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
          fontSize: '0.88rem',
          fontWeight: 600,
          animation: 'fadeIn 0.25s ease-out'
        }}>
          {feedbackToast.type === 'error' ? <AlertTriangle size={18} /> : <CheckCircle size={18} color="#A7F3D0" />}
          <span>{feedbackToast.message}</span>
        </div>
      )}

      {/* Top Header */}
      <header className="delivery-header">
        <div className="delivery-header-inner">
          <div className="delivery-brand-group">
            <Link to="/delivery" className="delivery-brand-logo">
              <span className="delivery-brand-name">TARIKA</span>
              <span className="delivery-brand-tagline">Logistics Dispatch</span>
            </Link>

            <span className="delivery-role-badge">
              <ShieldCheck size={14} />
              <span>Delivery Partner</span>
            </span>

            {(partnerProfile?.courier_company || user?.courier_company) && (
              <span className="delivery-courier-chip">
                <Truck size={14} color="#8E3642" />
                <span>{partnerProfile?.courier_company || user?.courier_company}</span>
              </span>
            )}
          </div>

          <div className="delivery-profile-menu">
            <div className="delivery-user-info">
              <span className="delivery-user-name">
                {partnerProfile?.full_name || user?.full_name || 'Courier Agent'}
              </span>
              <span className="delivery-user-email">
                {partnerProfile?.email || user?.email}
              </span>
            </div>

            <button
              className="delivery-btn-icon"
              onClick={handleManualRefresh}
              title="Refresh deliveries"
              disabled={refreshing}
            >
              <RefreshCw size={17} className={refreshing ? 'animate-spin' : ''} />
            </button>

            <button className="delivery-btn-signout" onClick={logout}>
              <LogOut size={16} />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="delivery-container">
        {/* Hero Welcome Banner */}
        <section className="delivery-hero-banner">
          <div>
            <h1 className="delivery-hero-title">
              Delivery Operations
            </h1>
            <p className="delivery-hero-subtitle">
              Manage your assigned forward shipments and customer return pickups, update live tracking milestones, and report logistics progress in real time.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{
              background: '#FFFFFF',
              border: '1px solid #E5D0CD',
              borderRadius: '12px',
              padding: '0.55rem 1rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: '#8E3642',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}>
              <Clock size={15} />
              <span>Today: {new Date().toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            </span>
          </div>
        </section>

        {/* Primary Flow Switcher: Forward Shipments vs Return Pickups */}
        <div className="delivery-flow-switcher">
          <button
            type="button"
            className={`delivery-flow-btn ${portalMode === 'forward' ? 'active' : ''}`}
            onClick={() => {
              setPortalMode('forward');
              setActiveTab('all');
            }}
          >
            <Truck size={18} />
            <span>Forward Deliveries</span>
            <span className="flow-count-badge">
              {metrics.total_assigned || 0}
            </span>
          </button>

          <button
            type="button"
            className={`delivery-flow-btn return-mode ${portalMode === 'returns' ? 'active' : ''}`}
            onClick={() => {
              setPortalMode('returns');
              setReturnActiveTab('all');
            }}
          >
            <RotateCcw size={16} />
            <span>Return Pickups</span>
            {returnMetrics.total > 0 && (
              <span className="flow-count-badge return-badge">
                {returnMetrics.total}
              </span>
            )}
          </button>
        </div>

        {portalMode === 'forward' ? (
          <>
            {/* Forward Dashboard Performance Metrics */}
            <section className="delivery-metrics-grid" style={{ marginTop: '1.5rem' }}>
              <div className="delivery-metric-card metric-total">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Assigned Workload</span>
                  <div className="delivery-metric-icon-wrap">
                    <Package size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{metrics.total_assigned || 0}</div>
                <div className="delivery-metric-hint">Total packages assigned</div>
              </div>

              <div className="delivery-metric-card metric-pending">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Pending Pickup</span>
                  <div className="delivery-metric-icon-wrap">
                    <Clock size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{metrics.pending_pickup || 0}</div>
                <div className="delivery-metric-hint">Awaiting warehouse dispatch</div>
              </div>

              <div className="delivery-metric-card metric-transit">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">In Transit</span>
                  <div className="delivery-metric-icon-wrap">
                    <Truck size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{metrics.in_transit || 0}</div>
                <div className="delivery-metric-hint">En route to customers</div>
              </div>

              <div className="delivery-metric-card metric-delivered">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Delivered</span>
                  <div className="delivery-metric-icon-wrap">
                    <CheckCircle2 size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{metrics.delivered || 0}</div>
                <div className="delivery-metric-hint">Successfully handed over</div>
              </div>

              <div className="delivery-metric-card metric-exception">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Exceptions</span>
                  <div className="delivery-metric-icon-wrap">
                    <AlertTriangle size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{metrics.exceptions || 0}</div>
                <div className="delivery-metric-hint">Delayed or failed attempts</div>
              </div>
            </section>

            {/* Forward Toolbar & Filters */}
            <section className="delivery-toolbar">
              <div className="delivery-search-box">
                <Search size={17} color="#9E8F94" />
                <input
                  type="text"
                  placeholder="Search by Delivery ID, Order, Customer, City..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9E8F94' }}
                  >
                    ×
                  </button>
                )}
              </div>

              <div className="delivery-filter-tabs">
                {FORWARD_STATUS_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`delivery-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>
            </section>

            {/* Forward Package Manifest Cards */}
            {loading ? (
              <div style={{ padding: '4rem', textAlign: 'center', color: '#8E3642' }}>
                <RefreshCw size={36} className="animate-spin" style={{ margin: '0 auto 1rem' }} />
                <p style={{ fontWeight: 600 }}>Loading assigned packages...</p>
              </div>
            ) : deliveries.length === 0 ? (
              <div className="delivery-empty-state">
                <div className="delivery-empty-icon">
                  <Package size={32} />
                </div>
                <h3 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: '1.4rem', margin: '0 0 0.5rem 0' }}>
                  No deliveries found
                </h3>
                <p style={{ color: '#6B5E63', fontSize: '0.88rem', maxWidth: '420px', margin: '0 auto' }}>
                  {searchQuery
                    ? `No shipments match your search "${searchQuery}". Try a different keyword.`
                    : activeTab !== 'all'
                    ? `There are currently no deliveries with status "${activeTab}".`
                    : 'You have no assigned shipments currently. Check back once new orders are dispatched.'}
                </p>
              </div>
            ) : (
              <div className="delivery-cards-grid">
                {deliveries.map((deliv) => {
                  const statusNormalized = (deliv.delivery_status || '').toLowerCase().replace(/\s+/g, '-');
                  const rawStatus = (deliv.delivery_status || '').toLowerCase();

                  return (
                    <div key={deliv.delivery_id} className="delivery-card">
                      <div>
                        {/* Card Top / IDs */}
                        <div className="delivery-card-header">
                          <div className="delivery-ids-group">
                            <span className="delivery-id-title">{deliv.delivery_id}</span>
                            <span className="delivery-order-id-sub">Order #{deliv.order_id?.slice(0, 16)}...</span>
                          </div>
                          <span className={`delivery-status-pill status-${statusNormalized}`}>
                            {deliv.delivery_status}
                          </span>
                        </div>

                        {/* Customer & Address Details */}
                        <div className="delivery-recipient-box">
                          <div className="delivery-recipient-name">
                            <span>{deliv.customer_name || 'Valued Customer'}</span>
                          </div>
                          <div className="delivery-recipient-address">
                            <MapPin size={14} style={{ display: 'inline', marginRight: '4px', color: '#9E8F94' }} />
                            {deliv.customer_address
                              ? `${deliv.customer_address}${deliv.customer_city ? `, ${deliv.customer_city}` : ''}`
                              : deliv.customer_city || 'Delivery Address on file'}
                          </div>
                          {deliv.customer_phone && (
                            <div className="delivery-contact-row">
                              <a href={`tel:${deliv.customer_phone}`} className="delivery-tel-link">
                                <Phone size={12} />
                                <span>Call {deliv.customer_phone}</span>
                              </a>
                            </div>
                          )}
                        </div>

                        {/* Meta info strip */}
                        <div className="delivery-meta-strip">
                          <div className="delivery-meta-item">
                            <span className="delivery-meta-title">Expected</span>
                            <span className="delivery-meta-val" style={{ color: '#16A34A' }}>
                              {deliv.expected_delivery_date || 'Standard'}
                            </span>
                          </div>
                          <div className="delivery-meta-item">
                            <span className="delivery-meta-title">Order Total</span>
                            <span className="delivery-meta-val">
                              ₹{Number(deliv.total_amount || 0).toLocaleString()}
                            </span>
                          </div>
                          <div className="delivery-meta-item">
                            <span className="delivery-meta-title">Items</span>
                            <span className="delivery-meta-val">
                              {deliv.item_count || 1} pcs
                            </span>
                          </div>
                        </div>

                        {/* Exception Alert if marked delayed or failed */}
                        {deliv.failure_reason && (
                          <div className="delivery-exception-banner">
                            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                            <div>
                              <strong>Reason:</strong> {deliv.failure_reason}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Action Toolbar */}
                      <div className="delivery-card-actions">
                        <button
                          type="button"
                          className="delivery-btn-secondary"
                          onClick={() => setSelectedDetailId(deliv.delivery_id)}
                          title="View manifest details"
                        >
                          <Eye size={15} />
                          <span>Details</span>
                        </button>

                        {rawStatus === 'assigned' && (
                          <button
                            type="button"
                            className="delivery-btn-primary"
                            disabled={isUpdatingStatus}
                            onClick={() => handleStatusTransition(deliv.delivery_id, 'Picked Up')}
                          >
                            <Package size={15} />
                            <span>Confirm Pickup</span>
                          </button>
                        )}

                        {rawStatus === 'picked up' && (
                          <button
                            type="button"
                            className="delivery-btn-primary"
                            disabled={isUpdatingStatus}
                            onClick={() => handleStatusTransition(deliv.delivery_id, 'In Transit')}
                          >
                            <Truck size={15} />
                            <span>Start Delivery</span>
                          </button>
                        )}

                        {rawStatus === 'in transit' && (
                          <>
                            <button
                              type="button"
                              className="delivery-btn-issue"
                              disabled={isUpdatingStatus}
                              onClick={() => setSelectedExceptionDelivery(deliv)}
                            >
                              <AlertTriangle size={14} />
                              <span>Issue</span>
                            </button>
                            <button
                              type="button"
                              className="delivery-btn-primary"
                              disabled={isUpdatingStatus}
                              onClick={() => handleStatusTransition(deliv.delivery_id, 'Delivered')}
                            >
                              <CheckCircle size={15} />
                              <span>Delivered</span>
                            </button>
                          </>
                        )}

                        {['delayed', 'failed'].includes(rawStatus) && (
                          <button
                            type="button"
                            className="delivery-btn-primary"
                            disabled={isUpdatingStatus}
                            onClick={() => handleStatusTransition(deliv.delivery_id, 'In Transit')}
                          >
                            <Truck size={15} />
                            <span>Resume Delivery</span>
                          </button>
                        )}

                        {rawStatus === 'delivered' && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            fontSize: '0.8rem',
                            fontWeight: 700,
                            color: '#059669',
                            marginLeft: 'auto'
                          }}>
                            <CheckCircle size={15} />
                            <span>Completed</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          /* ========================================================
             RETURN PICKUPS SECTION
             ======================================================== */
          <>
            {/* Return Metrics Grid */}
            <section className="delivery-metrics-grid" style={{ marginTop: '1.5rem' }}>
              <div className="delivery-metric-card metric-total">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Return Pickups</span>
                  <div className="delivery-metric-icon-wrap" style={{ background: '#FEF3C7', color: '#92400E' }}>
                    <RotateCcw size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{returnMetrics.total}</div>
                <div className="delivery-metric-hint">Total reverse shipments assigned</div>
              </div>

              <div className="delivery-metric-card metric-pending">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Assigned</span>
                  <div className="delivery-metric-icon-wrap">
                    <Clock size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{returnMetrics.assigned}</div>
                <div className="delivery-metric-hint">Awaiting driver acceptance</div>
              </div>

              <div className="delivery-metric-card metric-transit">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Accepted</span>
                  <div className="delivery-metric-icon-wrap">
                    <Truck size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{returnMetrics.accepted}</div>
                <div className="delivery-metric-hint">En route to customer address</div>
              </div>

              <div className="delivery-metric-card metric-delivered">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Picked Up</span>
                  <div className="delivery-metric-icon-wrap">
                    <PackageCheck size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{returnMetrics.picked_up}</div>
                <div className="delivery-metric-hint">Collected from customer</div>
              </div>

              <div className="delivery-metric-card metric-delivered">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">At Warehouse</span>
                  <div className="delivery-metric-icon-wrap">
                    <CheckCircle2 size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{returnMetrics.at_warehouse + returnMetrics.completed}</div>
                <div className="delivery-metric-hint">Returned to hub / Completed</div>
              </div>

              <div className="delivery-metric-card metric-exception">
                <div className="delivery-metric-top">
                  <span className="delivery-metric-label">Exceptions</span>
                  <div className="delivery-metric-icon-wrap">
                    <AlertTriangle size={18} />
                  </div>
                </div>
                <div className="delivery-metric-value">{returnMetrics.failed}</div>
                <div className="delivery-metric-hint">Failed pickup attempts</div>
              </div>
            </section>

            {/* Return Toolbar & Filters */}
            <section className="delivery-toolbar">
              <div className="delivery-search-box">
                <Search size={17} color="#9E8F94" />
                <input
                  type="text"
                  placeholder="Search by Return ID, Order, Customer, Reason..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9E8F94' }}
                  >
                    ×
                  </button>
                )}
              </div>

              <div className="delivery-filter-tabs">
                {RETURN_STATUS_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`delivery-tab-btn ${returnActiveTab === tab.id ? 'active' : ''}`}
                    onClick={() => setReturnActiveTab(tab.id)}
                  >
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>
            </section>

            {/* Return Pickups Grid */}
            {returnLoading ? (
              <div style={{ padding: '4rem', textAlign: 'center', color: '#8E3642' }}>
                <RefreshCw size={36} className="animate-spin" style={{ margin: '0 auto 1rem' }} />
                <p style={{ fontWeight: 600 }}>Loading return pickups...</p>
              </div>
            ) : returnPickups.length === 0 ? (
              <div className="delivery-empty-state">
                <div className="delivery-empty-icon" style={{ background: '#FEF3C7', color: '#92400E' }}>
                  <RotateCcw size={32} />
                </div>
                <h3 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: '1.4rem', margin: '0 0 0.5rem 0' }}>
                  No return pickups found
                </h3>
                <p style={{ color: '#6B5E63', fontSize: '0.88rem', maxWidth: '420px', margin: '0 auto' }}>
                  {searchQuery
                    ? `No return pickups match "${searchQuery}".`
                    : returnActiveTab !== 'all'
                    ? `There are currently no return pickups with status "${returnActiveTab}".`
                    : 'You currently have no return pickups assigned to your courier ID.'}
                </p>
              </div>
            ) : (
              <div className="delivery-cards-grid">
                {returnPickups.map((ret) => {
                  const rawStatus = (ret.return_status || '').toLowerCase();
                  const statusClass = rawStatus.replace(/\s+/g, '-');

                  return (
                    <div key={ret.return_id} className="delivery-card return-card">
                      <div>
                        {/* Header / Badges */}
                        <div className="delivery-card-header">
                          <div className="delivery-ids-group">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span className="delivery-id-title">{ret.return_id}</span>
                              <span className="return-flow-tag">
                                <RotateCcw size={11} />
                                <span>Return</span>
                              </span>
                            </div>
                            <span className="delivery-order-id-sub">
                              Order #{ret.order_id ? ret.order_id.slice(0, 16) : 'N/A'}...
                            </span>
                          </div>
                          <span className={`delivery-status-pill status-${statusClass}`}>
                            {ret.return_status}
                          </span>
                        </div>

                        {/* Customer & Address Details */}
                        <div className="delivery-recipient-box">
                          <div className="delivery-recipient-name">
                            <span>{ret.customer_name || 'Customer'}</span>
                            <span style={{ fontSize: '0.75rem', fontWeight: 500, color: '#9E8F94', marginLeft: '0.5rem' }}>
                              (Pickup Origin)
                            </span>
                          </div>
                          <div className="delivery-recipient-address">
                            <MapPin size={14} style={{ display: 'inline', marginRight: '4px', color: '#D97706' }} />
                            {ret.customer_address
                              ? `${ret.customer_address}${ret.customer_city ? `, ${ret.customer_city}` : ''}`
                              : ret.customer_city || 'Address on file'}
                          </div>
                          {ret.customer_phone && (
                            <div className="delivery-contact-row">
                              <a href={`tel:${ret.customer_phone}`} className="delivery-tel-link">
                                <Phone size={12} />
                                <span>Call Customer: {ret.customer_phone}</span>
                              </a>
                            </div>
                          )}
                        </div>

                        {/* Product info summary */}
                        <div className="return-product-summary">
                          {ret.image ? (
                            <img src={ret.image} alt={ret.product_name} className="return-product-img" />
                          ) : (
                            <div className="return-product-img" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9E8F94' }}>
                              <Package size={20} />
                            </div>
                          )}
                          <div className="return-product-info">
                            <div className="return-product-title">
                              {ret.product_name || 'Haute Atelier Garment'}
                            </div>
                            <div className="return-product-sub">
                              Qty: <strong>{ret.quantity || 1} unit</strong> • SKU: {ret.sku || 'N/A'}
                            </div>
                          </div>
                          {ret.refund_amount > 0 && (
                            <div style={{ textAlign: 'right', flexShrink: 0 }}>
                              <div style={{ fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>Refund</div>
                              <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B' }}>₹{Number(ret.refund_amount).toLocaleString()}</div>
                            </div>
                          )}
                        </div>

                        {/* Return Reason Box */}
                        <div className="return-reason-box">
                          <div className="return-reason-label">
                            <CornerUpLeft size={13} />
                            <span>Return Reason:</span>
                          </div>
                          <div style={{ fontWeight: 600 }}>{ret.return_reason || 'Customer requested return'}</div>
                          {ret.condition_on_return && (
                            <div style={{ fontSize: '0.76rem', color: '#92400E', marginTop: '3px' }}>
                              <strong>Notes:</strong> {ret.condition_on_return}
                            </div>
                          )}
                        </div>

                        {/* Exception / Failure banner */}
                        {rawStatus === 'failed' && (
                          <div className="delivery-exception-banner" style={{ marginTop: '0.75rem' }}>
                            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                            <div>
                              <strong>Pickup Exception:</strong> {ret.condition_on_return || 'Customer unavailable or item issue'}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Action Toolbar */}
                      <div className="delivery-card-actions">
                        {rawStatus === 'pickup assigned' && (
                          <button
                            type="button"
                            className="delivery-btn-primary"
                            style={{ width: '100%', justifyContent: 'center' }}
                            disabled={isUpdatingStatus}
                            onClick={() => handleReturnStatusTransition(ret.return_id, 'Pickup Accepted')}
                          >
                            <Truck size={15} />
                            <span>Accept Pickup</span>
                          </button>
                        )}

                        {rawStatus === 'pickup accepted' && (
                          <>
                            <button
                              type="button"
                              className="delivery-btn-issue"
                              disabled={isUpdatingStatus}
                              onClick={() => setSelectedExceptionReturn(ret)}
                            >
                              <AlertTriangle size={14} />
                              <span>Issue</span>
                            </button>
                            <button
                              type="button"
                              className="delivery-btn-primary"
                              disabled={isUpdatingStatus}
                              onClick={() => handleReturnStatusTransition(ret.return_id, 'Picked Up')}
                            >
                              <PackageCheck size={15} />
                              <span>Mark Picked Up</span>
                            </button>
                          </>
                        )}

                        {rawStatus === 'picked up' && (
                          <button
                            type="button"
                            className="delivery-btn-primary"
                            style={{ width: '100%', justifyContent: 'center', background: '#0D9488', borderColor: '#0D9488' }}
                            disabled={isUpdatingStatus}
                            onClick={() => handleReturnStatusTransition(ret.return_id, 'Received at Warehouse')}
                          >
                            <PackageCheck size={15} />
                            <span>Hand Over at Warehouse</span>
                          </button>
                        )}

                        {rawStatus === 'received at warehouse' && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            fontSize: '0.82rem',
                            fontWeight: 700,
                            color: '#0D9488',
                            marginLeft: 'auto'
                          }}>
                            <Clock size={15} />
                            <span>Awaiting Warehouse Inspection</span>
                          </div>
                        )}

                        {rawStatus === 'completed' && (
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            fontSize: '0.82rem',
                            fontWeight: 700,
                            color: '#059669',
                            marginLeft: 'auto'
                          }}>
                            <CheckCircle size={15} />
                            <span>Return Completed</span>
                          </div>
                        )}

                        {rawStatus === 'failed' && (
                          <button
                            type="button"
                            className="delivery-btn-primary"
                            style={{ width: '100%', justifyContent: 'center' }}
                            disabled={isUpdatingStatus}
                            onClick={() => handleReturnStatusTransition(ret.return_id, 'Pickup Accepted')}
                          >
                            <RotateCcw size={15} />
                            <span>Retry Pickup</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* Forward Package Detail Modal */}
      {selectedDetailId && (
        <DeliveryDetailsModal
          deliveryId={selectedDetailId}
          token={token}
          onClose={() => setSelectedDetailId(null)}
          onStatusChange={handleStatusTransition}
          onOpenIssueModal={(deliv) => setSelectedExceptionDelivery(deliv)}
        />
      )}

      {/* Forward Exception Reason Modal */}
      {selectedExceptionDelivery && (
        <DeliveryExceptionModal
          delivery={selectedExceptionDelivery}
          onClose={() => setSelectedExceptionDelivery(null)}
          onSubmitException={handleConfirmException}
          isSubmitting={isUpdatingStatus}
        />
      )}

      {/* Return Exception Reason Modal */}
      {selectedExceptionReturn && (
        <ReturnExceptionModal
          returnPickup={selectedExceptionReturn}
          onClose={() => setSelectedExceptionReturn(null)}
          onSubmitException={handleConfirmReturnException}
          isSubmitting={isUpdatingStatus}
        />
      )}
    </div>
  );
}
