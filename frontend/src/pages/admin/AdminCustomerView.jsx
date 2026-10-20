import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Users,
  CheckCircle2,
  AlertTriangle,
  Search,
  Filter,
  Eye,
  RefreshCw,
  X,
  Mail,
  Phone,
  MapPin,
  Calendar,
  AlertCircle,
  ShoppingBag,
  Clock,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { getAdminCustomers, getAdminCustomerDetail } from '../../services/api';

/* ─── Status Badge Helper ────────────────────────────────────────────────── */
function StatusBadge({ isActive }) {
  if (isActive) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
        padding: '0.25rem 0.7rem', borderRadius: '9999px',
        backgroundColor: '#ECFDF5', color: '#059669', border: '1px solid #A7F3D0',
        fontSize: '0.75rem', fontWeight: 700, whiteSpace: 'nowrap',
      }}>
        <CheckCircle2 size={12} />
        Active
      </span>
    );
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
      padding: '0.25rem 0.7rem', borderRadius: '9999px',
      backgroundColor: '#FEF2F2', color: '#B91C1C', border: '1px solid #FECACA',
      fontSize: '0.75rem', fontWeight: 700, whiteSpace: 'nowrap',
    }}>
      <AlertTriangle size={12} />
      Inactive
    </span>
  );
}

/* ─── KPI Summary Card ───────────────────────────────────────────────────── */
function KpiCard({ label, value, icon: Icon, iconBg, iconColor, accentColor }) {
  return (
    <div className="admin-metric-card" style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '1rem', padding: '1.15rem 1.35rem' }}>
      <div style={{
        width: 46, height: 46, borderRadius: 12, flexShrink: 0,
        backgroundColor: iconBg, color: iconColor,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={22} />
      </div>
      <div>
        <p className="admin-metric-title" style={{ marginBottom: 2 }}>{label}</p>
        <p className="admin-metric-val" style={{ fontSize: '1.65rem', color: accentColor || '#1F191B' }}>{value}</p>
      </div>
    </div>
  );
}

/* ─── Main Component ─────────────────────────────────────────────────────── */
export default function AdminCustomerView() {
  const { token } = useAuth();

  const [metrics, setMetrics] = useState({
    total_customers: 0,
    active_customers: 0,
    inactive_customers: 0,
  });
  
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Pagination & Filtering
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Search Debounce Ref
  const searchTimeoutRef = useRef(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Modals
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  // Handle Search Input with Debounce
  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchTerm(val);
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearch(val);
      setCurrentPage(1); // Reset to page 1 on new search
    }, 400); // 400ms debounce
  };

  const handleStatusChange = (e) => {
    setStatusFilter(e.target.value);
    setCurrentPage(1); // Reset to page 1 on filter change
  };

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    setError(null);
    const activeToken = token || localStorage.getItem('iras_token') || localStorage.getItem('token');
    
    const res = await getAdminCustomers(activeToken, {
      search: debouncedSearch,
      status: statusFilter,
      page: currentPage,
    });

    if (res.success) {
      setCustomers(res.customers || []);
      setMetrics(res.metrics || {});
      setTotalPages(res.total_pages || 1);
      setTotalCount(res.count || 0);
    } else {
      setError(res.error || 'Failed to load customers.');
    }
    setLoading(false);
  }, [token, debouncedSearch, statusFilter, currentPage]);

  useEffect(() => {
    fetchCustomers();
  }, [fetchCustomers]);

  const handleViewDetails = async (customerId) => {
    setDetailsLoading(true);
    setDetailsError(null);
    setSelectedCustomer(null); // Clear previous

    const activeToken = token || localStorage.getItem('iras_token') || localStorage.getItem('token');
    const res = await getAdminCustomerDetail(activeToken, customerId);

    if (res.success) {
      setSelectedCustomer(res.customer);
    } else {
      setDetailsError(res.error || 'Failed to load customer details.');
    }
    setDetailsLoading(false);
  };

  const closeDetails = () => {
    setSelectedCustomer(null);
    setDetailsError(null);
  };

  // Currency formatting helper
  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val || 0);
  };

  return (
    <div style={{ paddingBottom: '3rem' }}>
      {/* 1. Header Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span style={{ padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.72rem', fontWeight: 700, backgroundColor: '#F0F9FF', color: '#0369A1', border: '1px solid #BAE6FD' }}>
              User Management
            </span>
            <span style={{ fontSize: '0.78rem', color: '#9E8F94' }}>Customer Directory</span>
          </div>
          <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: 0 }}>
            Customers
          </h1>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: '0.35rem 0 0' }}>
            View and manage registered customers, their contact information, and order history.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={fetchCustomers}
            disabled={loading}
            style={{
              padding: '0.65rem 1.1rem',
              borderRadius: '12px',
              border: '1px solid #F0E2E0',
              backgroundColor: '#FFFFFF',
              color: '#1F191B',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              opacity: loading ? 0.6 : 1,
            }}
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div style={{ padding: '0.9rem 1.25rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', borderRadius: '14px', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.875rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={18} color="#DC2626" />
            <span style={{ fontWeight: 600 }}>{error}</span>
          </div>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: '#DC2626', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* 2. KPIs */}
      <div className="admin-metrics-grid" style={{ marginBottom: '1.5rem' }}>
        <KpiCard
          label="Total Customers"
          value={metrics.total_customers?.toLocaleString() || '0'}
          icon={Users}
          iconBg="#F3F4F6"
          iconColor="#4B5563"
        />
        <KpiCard
          label="Active Accounts"
          value={metrics.active_customers?.toLocaleString() || '0'}
          icon={CheckCircle2}
          iconBg="#ECFDF5"
          iconColor="#059669"
          accentColor="#059669"
        />
        <KpiCard
          label="Inactive / Suspended"
          value={metrics.inactive_customers?.toLocaleString() || '0'}
          icon={ShieldAlert}
          iconBg="#FEF2F2"
          iconColor="#DC2626"
          accentColor="#DC2626"
        />
      </div>

      {/* 3. Search & Filters */}
      <div className="admin-card" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: '1', minWidth: '260px' }}>
          <Search size={16} color="#9E8F94" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            placeholder="Search customers by name, email, city..."
            value={searchTerm}
            onChange={handleSearchChange}
            style={{
              width: '100%',
              padding: '0.65rem 0.85rem 0.65rem 2.4rem',
              borderRadius: '10px',
              border: '1px solid #F0E2E0',
              backgroundColor: '#FFFFFF',
              fontSize: '0.875rem',
              color: '#1F191B',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          {searchTerm && (
            <button
              onClick={() => { setSearchTerm(''); setDebouncedSearch(''); setCurrentPage(1); }}
              style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#9E8F94', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Status Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Filter size={15} color="#9E8F94" />
          <select
            value={statusFilter}
            onChange={handleStatusChange}
            style={{
              padding: '0.65rem 0.85rem',
              borderRadius: '10px',
              border: '1px solid #F0E2E0',
              backgroundColor: '#FFFFFF',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: '#1F191B',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            <option value="ALL">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {/* 4. Data Table */}
      <div className="admin-table-wrapper">
        <div style={{ overflowX: 'auto' }}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Customer Details</th>
                <th>Contact</th>
                <th>Location</th>
                <th>Registration Date</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#6B5E63' }}>
                    <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 1rem', color: '#8E3642' }} />
                    Loading customers...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#6B5E63' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                      <Users size={32} color="#D4C9CC" />
                      <p style={{ fontWeight: 600, color: '#1F191B', margin: '0.5rem 0 0' }}>No customers found</p>
                      <p style={{ fontSize: '0.85rem' }}>Try adjusting your search or filters.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.customer_id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: '50%', backgroundColor: '#F0E2E0', color: '#8E3642',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1rem', flexShrink: 0
                        }}>
                          {(c.full_name || 'U').charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, color: '#1F191B', fontSize: '0.9rem' }}>{c.full_name}</div>
                          <div style={{ color: '#6B5E63', fontSize: '0.75rem', marginTop: 2 }}>ID: {c.customer_id.substring(0, 8)}...</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        {c.email && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#4B5563', fontSize: '0.8rem' }}>
                            <Mail size={12} color="#9E8F94" />
                            {c.email}
                          </div>
                        )}
                        {c.phone && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#4B5563', fontSize: '0.8rem' }}>
                            <Phone size={12} color="#9E8F94" />
                            {c.phone}
                          </div>
                        )}
                      </div>
                    </td>
                    <td>
                      {(c.city || c.country) ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#4B5563', fontSize: '0.85rem' }}>
                          <MapPin size={14} color="#9E8F94" />
                          {[c.city, c.state, c.country].filter(Boolean).join(', ')}
                        </div>
                      ) : (
                        <span style={{ color: '#9E8F94', fontSize: '0.85rem' }}>Not specified</span>
                      )}
                    </td>
                    <td>
                      <div style={{ color: '#4B5563', fontSize: '0.85rem' }}>
                        {c.registration_date ? new Date(c.registration_date).toLocaleDateString() : 'Unknown'}
                      </div>
                    </td>
                    <td>
                      <StatusBadge isActive={c.is_active} />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => handleViewDetails(c.customer_id)}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        <Eye size={14} />
                        View
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination Controls */}
        {!loading && customers.length > 0 && totalPages > 1 && (
          <div style={{ padding: '1rem 1.25rem', borderTop: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#FAFAFA', borderBottomLeftRadius: '16px', borderBottomRightRadius: '16px' }}>
            <div style={{ fontSize: '0.85rem', color: '#6B5E63' }}>
              Showing page <span style={{ fontWeight: 600, color: '#1F191B' }}>{currentPage}</span> of <span style={{ fontWeight: 600, color: '#1F191B' }}>{totalPages}</span> ({totalCount} total)
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                style={{
                  padding: '0.4rem 0.6rem', borderRadius: '8px', border: '1px solid #E5E7EB',
                  backgroundColor: currentPage === 1 ? '#F3F4F6' : '#FFFFFF',
                  color: currentPage === 1 ? '#9CA3AF' : '#374151',
                  cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center'
                }}
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                style={{
                  padding: '0.4rem 0.6rem', borderRadius: '8px', border: '1px solid #E5E7EB',
                  backgroundColor: currentPage === totalPages ? '#F3F4F6' : '#FFFFFF',
                  color: currentPage === totalPages ? '#9CA3AF' : '#374151',
                  cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center'
                }}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 5. Detail Modal */}
      {(detailsLoading || detailsError || selectedCustomer) && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(31, 25, 27, 0.4)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#FFFFFF', borderRadius: '20px', width: '100%', maxWidth: '650px',
            maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            display: 'flex', flexDirection: 'column'
          }}>
            {/* Header */}
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, backgroundColor: '#FFFFFF', zIndex: 10, borderTopLeftRadius: '20px', borderTopRightRadius: '20px' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Users size={18} color="#8E3642" />
                Customer Profile
              </h2>
              <button onClick={closeDetails} style={{ background: 'none', border: 'none', color: '#9E8F94', cursor: 'pointer', padding: '0.2rem', borderRadius: '50%' }}>
                <X size={20} />
              </button>
            </div>

            {/* Content */}
            <div style={{ padding: '1.5rem', flex: 1 }}>
              {detailsLoading ? (
                <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                  <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 1rem', color: '#8E3642' }} />
                  <p style={{ color: '#6B5E63', fontWeight: 500 }}>Loading profile...</p>
                </div>
              ) : detailsError ? (
                <div style={{ textAlign: 'center', padding: '2rem 1rem', color: '#DC2626' }}>
                  <AlertCircle size={32} style={{ margin: '0 auto 1rem' }} />
                  <p style={{ fontWeight: 600 }}>{detailsError}</p>
                </div>
              ) : selectedCustomer ? (
                <div>
                  {/* Top Profile Card */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1.5rem', marginBottom: '2rem', padding: '1.5rem', backgroundColor: '#FAF7F5', borderRadius: '16px', border: '1px solid #F0E2E0' }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: '50%', backgroundColor: '#FFFFFF', color: '#8E3642',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1.8rem', flexShrink: 0, border: '1px solid #F0E2E0'
                    }}>
                      {(selectedCustomer.full_name || 'U').charAt(0).toUpperCase()}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                        <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#1F191B' }}>
                          {selectedCustomer.full_name}
                        </h3>
                        <StatusBadge isActive={selectedCustomer.is_active} />
                      </div>
                      <p style={{ margin: '0 0 0.75rem 0', color: '#6B5E63', fontSize: '0.85rem' }}>
                        Customer ID: <span style={{ fontFamily: 'monospace' }}>{selectedCustomer.customer_id}</span>
                      </p>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                        {selectedCustomer.email && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#4B5563', fontSize: '0.85rem' }}>
                            <Mail size={14} color="#9E8F94" />
                            {selectedCustomer.email}
                          </div>
                        )}
                        {selectedCustomer.phone && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#4B5563', fontSize: '0.85rem' }}>
                            <Phone size={14} color="#9E8F94" />
                            {selectedCustomer.phone}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                    {/* Demographics & Location */}
                    <div>
                      <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#9E8F94', margin: '0 0 0.75rem 0', borderBottom: '1px solid #F0E2E0', paddingBottom: '0.5rem' }}>
                        Demographics & Location
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                          <Calendar size={15} color="#6B5E63" style={{ marginTop: '0.1rem' }} />
                          <div>
                            <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>Gender / DOB</div>
                            <div style={{ fontSize: '0.9rem', color: '#1F191B', fontWeight: 500 }}>
                              {selectedCustomer.gender || 'Not specified'} {selectedCustomer.date_of_birth ? `/ ${selectedCustomer.date_of_birth}` : ''}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                          <MapPin size={15} color="#6B5E63" style={{ marginTop: '0.1rem' }} />
                          <div>
                            <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>Address</div>
                            <div style={{ fontSize: '0.9rem', color: '#1F191B', fontWeight: 500 }}>
                              {[selectedCustomer.city, selectedCustomer.state, selectedCustomer.country].filter(Boolean).join(', ') || 'Not specified'}
                              {selectedCustomer.postal_code && ` - ${selectedCustomer.postal_code}`}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Order Summary */}
                    <div>
                      <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#9E8F94', margin: '0 0 0.75rem 0', borderBottom: '1px solid #F0E2E0', paddingBottom: '0.5rem' }}>
                        Purchase Summary
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', backgroundColor: '#F9FAFB', padding: '1rem', borderRadius: '12px', border: '1px solid #E5E7EB' }}>
                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6B5E63', marginBottom: '0.25rem' }}>Total Orders</div>
                          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1F191B' }}>
                            {selectedCustomer.order_summary?.total_orders || 0}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6B5E63', marginBottom: '0.25rem' }}>Total Spent</div>
                          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#059669' }}>
                            {formatCurrency(selectedCustomer.order_summary?.total_spent)}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Recent Orders */}
                  <div>
                    <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#9E8F94', margin: '0 0 0.75rem 0', borderBottom: '1px solid #F0E2E0', paddingBottom: '0.5rem' }}>
                      Recent Orders
                    </h4>
                    {selectedCustomer.recent_orders && selectedCustomer.recent_orders.length > 0 ? (
                      <div style={{ border: '1px solid #F0E2E0', borderRadius: '12px', overflow: 'hidden' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                          <thead style={{ backgroundColor: '#FAF7F5', borderBottom: '1px solid #F0E2E0' }}>
                            <tr>
                              <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: '#6B5E63' }}>Order ID</th>
                              <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: '#6B5E63' }}>Date</th>
                              <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: '#6B5E63' }}>Status</th>
                              <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: '#6B5E63', textAlign: 'right' }}>Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedCustomer.recent_orders.map((o, idx) => (
                              <tr key={idx} style={{ borderBottom: idx < selectedCustomer.recent_orders.length - 1 ? '1px solid #F0E2E0' : 'none' }}>
                                <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#1F191B' }}>{o.order_id.substring(0, 8)}...</td>
                                <td style={{ padding: '0.75rem 1rem', color: '#4B5563' }}>{o.order_date ? new Date(o.order_date).toLocaleDateString() : ''}</td>
                                <td style={{ padding: '0.75rem 1rem' }}>
                                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: o.order_status?.toLowerCase() === 'delivered' ? '#059669' : '#1D4ED8' }}>
                                    {o.order_status}
                                  </span>
                                </td>
                                <td style={{ padding: '0.75rem 1rem', textAlign: 'right', fontWeight: 600, color: '#1F191B' }}>
                                  {formatCurrency(o.total_amount)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ padding: '1.5rem', textAlign: 'center', backgroundColor: '#FAFAFA', borderRadius: '12px', border: '1px dashed #D1D5DB' }}>
                        <ShoppingBag size={24} color="#9CA3AF" style={{ margin: '0 auto 0.5rem' }} />
                        <p style={{ margin: 0, color: '#6B7280', fontSize: '0.9rem' }}>No orders found for this customer.</p>
                      </div>
                    )}
                  </div>

                </div>
              ) : null}
            </div>
            
            {/* Footer */}
            <div style={{ padding: '1.25rem 1.5rem', borderTop: '1px solid #F0E2E0', backgroundColor: '#FAFAFA', display: 'flex', justifyContent: 'flex-end', borderBottomLeftRadius: '20px', borderBottomRightRadius: '20px' }}>
              <button
                onClick={closeDetails}
                className="tarika-btn-outline"
                style={{ padding: '0.5rem 1.25rem', borderRadius: '10px', fontSize: '0.85rem' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
