import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getStaffList, createStaffMember, toggleStaffStatus } from '../../services/api';
import {
  Users,
  UserCheck,
  Building2,
  Truck,
  ShieldCheck,
  Search,
  Filter,
  Plus,
  X,
  Eye,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Phone,
  Mail,
  User,
  Calendar,
  Lock,
  Building,
} from 'lucide-react';

export default function AdminStaffView() {
  const { token, user: authUser } = useAuth();

  // Main data states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState({
    total_staff: 0,
    warehouse_managers: 0,
    delivery_partners: 0,
    active_staff: 0,
  });
  const [employees, setEmployees] = useState([]);
  const [warehouses, setWarehouses] = useState([]);

  // Search & Filter states
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState(null);

  // Create Staff Form State
  const [createForm, setCreateForm] = useState({
    full_name: '',
    email: '',
    password: '',
    phone: '',
    role: 'WAREHOUSE_MANAGER',
    warehouse_id: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [formSuccess, setFormSuccess] = useState(null);

  // Status toggle state
  const [togglingId, setTogglingId] = useState(null);

  const fetchStaffData = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await getStaffList(token, {
      search,
      role: roleFilter,
      status: statusFilter,
    });

    if (res.success) {
      setSummary(res.summary);
      setEmployees(res.employees);
      setWarehouses(res.warehouses);
      // Pre-select first warehouse if available and no warehouse_id set
      if (res.warehouses?.length > 0 && !createForm.warehouse_id) {
        setCreateForm((prev) => ({ ...prev, warehouse_id: res.warehouses[0].warehouse_id }));
      }
    } else {
      setError(res.error || 'Failed to load staff members.');
    }
    setLoading(false);
  }, [token, search, roleFilter, statusFilter]);

  useEffect(() => {
    fetchStaffData();
  }, [fetchStaffData]);

  // Handle Staff Creation Submit
  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    // Client-side validation
    if (!createForm.full_name.trim()) {
      setFormError('Full Name is required.');
      return;
    }
    if (!createForm.email.trim()) {
      setFormError('Email address is required.');
      return;
    }
    if (!createForm.password || createForm.password.length < 6) {
      setFormError('Password must be at least 6 characters.');
      return;
    }
    if (createForm.role === 'WAREHOUSE_MANAGER' && !createForm.warehouse_id) {
      setFormError('Please select an assigned Warehouse for the Manager.');
      return;
    }

    setSubmitting(true);
    const payload = {
      full_name: createForm.full_name.trim(),
      email: createForm.email.trim(),
      password: createForm.password,
      phone: createForm.phone.trim() || undefined,
      role: createForm.role,
      warehouse_id: createForm.role === 'WAREHOUSE_MANAGER' ? createForm.warehouse_id : null,
    };

    const res = await createStaffMember(token, payload);
    setSubmitting(false);

    if (res.success) {
      setFormSuccess(res.message || 'Staff account created successfully!');
      // Reset form
      setCreateForm({
        full_name: '',
        email: '',
        password: '',
        phone: '',
        role: 'WAREHOUSE_MANAGER',
        warehouse_id: warehouses[0]?.warehouse_id || '',
      });
      // Refresh list
      fetchStaffData();
      // Auto close after 1.5s
      setTimeout(() => {
        setShowCreateModal(false);
        setFormSuccess(null);
      }, 1500);
    } else {
      setFormError(res.error || 'Failed to create staff member.');
    }
  };

  // Handle Active/Inactive Toggle
  const handleToggleStatus = async (employee) => {
    if (togglingId) return;
    setTogglingId(employee.employee_id);

    const targetStatus = !employee.is_active;
    const res = await toggleStaffStatus(token, employee.employee_id, targetStatus);

    if (res.success) {
      // Optimistic update
      setEmployees((prev) =>
        prev.map((emp) =>
          emp.employee_id === employee.employee_id
            ? { ...emp, is_active: targetStatus }
            : emp
        )
      );
      // Refresh summary KPIs
      fetchStaffData();
    } else {
      alert(res.error || 'Failed to update status.');
    }
    setTogglingId(null);
  };

  return (
    <div>
      {/* Header & Title Section */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: '0 0 0.35rem' }}>
            Staff Management
          </h1>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: 0 }}>
            Provision, assign, and manage operational staff accounts across TARIKA Retail facilities.
          </p>
        </div>

        <button
          onClick={() => {
            setShowCreateModal(true);
            setFormError(null);
            setFormSuccess(null);
          }}
          className="tarika-btn-primary"
          style={{ padding: '0.75rem 1.4rem', fontSize: '0.875rem' }}
        >
          <Plus size={16} />
          <span>Provision New Staff</span>
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="admin-metrics-grid" style={{ marginBottom: '1.75rem' }}>
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Users size={22} />
            </div>
            <span className="admin-metric-status">All Operational</span>
          </div>
          <div>
            <p className="admin-metric-title">Total Staff Members</p>
            <p className="admin-metric-val">{summary.total_staff || 0}</p>
            <p className="admin-metric-subtext">{summary.active_staff || 0} active in database</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Building2 size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#EFF6FF', color: '#2563EB', borderColor: '#BFDBFE' }}>
              Facility Managers
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Warehouse Managers</p>
            <p className="admin-metric-val">{summary.warehouse_managers || 0}</p>
            <p className="admin-metric-subtext">Assigned to fulfillment hubs</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Truck size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#FFFBEB', color: '#D97706', borderColor: '#FDE68A' }}>
              Logistics Partners
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Delivery Partners</p>
            <p className="admin-metric-val">{summary.delivery_partners || 0}</p>
            <p className="admin-metric-subtext">Dispatch & order delivery team</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <UserCheck size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' }}>
              Active Credentials
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Active Accounts</p>
            <p className="admin-metric-val">{summary.active_staff || 0}</p>
            <p className="admin-metric-subtext">Enabled access permissions</p>
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.15rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {/* Search Box */}
          <div style={{ flex: '1 1 280px', position: 'relative' }}>
            <Search size={17} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9E8F94' }} />
            <input
              type="text"
              placeholder="Search staff by name, email, or phone..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem 0.65rem 2.4rem',
                borderRadius: '10px',
                border: '1.5px solid var(--tarika-border, #F0E2E0)',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Role Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Filter size={15} color="#6B5E63" />
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#6B5E63' }}>Role:</span>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              style={{
                padding: '0.65rem 0.85rem',
                borderRadius: '10px',
                border: '1.5px solid var(--tarika-border, #F0E2E0)',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
                backgroundColor: '#FFFFFF',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Roles</option>
              <option value="ADMIN">Admin</option>
              <option value="WAREHOUSE_MANAGER">Warehouse Manager</option>
              <option value="DELIVERY_PARTNER">Delivery Partner</option>
            </select>
          </div>

          {/* Status Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#6B5E63' }}>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '0.65rem 0.85rem',
                borderRadius: '10px',
                border: '1.5px solid var(--tarika-border, #F0E2E0)',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
                backgroundColor: '#FFFFFF',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active Only</option>
              <option value="INACTIVE">Inactive Only</option>
            </select>
          </div>

          {/* Refresh Action */}
          <button
            onClick={fetchStaffData}
            style={{
              padding: '0.65rem',
              borderRadius: '10px',
              border: '1.5px solid var(--tarika-border, #F0E2E0)',
              backgroundColor: '#FFFFFF',
              color: '#6B5E63',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title="Refresh Staff List"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Main Staff Table Card */}
      <div className="admin-card">
        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
            <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216, 114, 126, 0.25)', borderTopColor: '#D8727E' }} />
            <p style={{ color: '#6B5E63', fontWeight: 600 }}>Loading staff records from database...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#DC2626' }}>
            <AlertCircle size={28} style={{ margin: '0 auto 0.5rem' }} />
            <p style={{ margin: 0, fontWeight: 600 }}>{error}</p>
          </div>
        ) : employees.length === 0 ? (
          <div style={{ padding: '3rem 1rem', textAlign: 'center', color: '#6B5E63' }}>
            <Users size={36} color="#9E8F94" style={{ margin: '0 auto 0.75rem' }} />
            <h4 style={{ margin: '0 0 0.35rem', color: '#1F191B', fontFamily: 'var(--font-serif)' }}>No Staff Members Found</h4>
            <p style={{ margin: 0, fontSize: '0.85rem' }}>No staff records match your current search or filter criteria.</p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Staff Member</th>
                  <th>Role</th>
                  <th>Phone / Contact</th>
                  <th>Facility Assignment</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp) => {
                  const initial = (emp.full_name?.[0] || emp.email?.[0] || 'E').toUpperCase();
                  const isAdmin = emp.role === 'ADMIN';

                  return (
                    <tr key={emp.employee_id}>
                      {/* Name & Email */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <div style={{
                            width: '38px', height: '38px', borderRadius: '50%',
                            background: isAdmin ? 'linear-gradient(135deg, #D4AF37 0%, #997A15 100%)' : 'linear-gradient(135deg, #D8727E 0%, #8E3642 100%)',
                            color: '#FFFFFF', fontWeight: 700, fontSize: '0.85rem',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                          }}>
                            {initial}
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: '#1F191B' }}>{emp.full_name}</div>
                            <div style={{ fontSize: '0.75rem', color: '#6B5E63' }}>{emp.email}</div>
                          </div>
                        </div>
                      </td>

                      {/* Role Badge */}
                      <td>
                        {emp.role === 'ADMIN' && (
                          <span className="admin-status-badge" style={{ backgroundColor: 'rgba(212, 175, 55, 0.15)', color: '#997A15', border: '1px solid rgba(212, 175, 55, 0.3)' }}>
                            <ShieldCheck size={12} />
                            ADMIN
                          </span>
                        )}
                        {emp.role === 'WAREHOUSE_MANAGER' && (
                          <span className="admin-status-badge admin-status-processing">
                            <Building2 size={12} />
                            Warehouse Manager
                          </span>
                        )}
                        {emp.role === 'DELIVERY_PARTNER' && (
                          <span className="admin-status-badge admin-status-pending">
                            <Truck size={12} />
                            Delivery Partner
                          </span>
                        )}
                      </td>

                      {/* Phone */}
                      <td style={{ color: '#6B5E63', fontSize: '0.8rem' }}>
                        {emp.phone ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                            <Phone size={12} color="#9E8F94" />
                            {emp.phone}
                          </span>
                        ) : (
                          <span style={{ color: '#9E8F94', fontStyle: 'italic' }}>Not provided</span>
                        )}
                      </td>

                      {/* Facility */}
                      <td style={{ fontSize: '0.8rem' }}>
                        {emp.warehouse_name ? (
                          <span style={{ fontWeight: 600, color: '#1F191B' }}>
                            {emp.warehouse_name} <code style={{ fontSize: '0.7rem', color: '#6B5E63' }}>({emp.warehouse_id})</code>
                          </span>
                        ) : (
                          <span style={{ color: '#9E8F94' }}>System Unrestricted</span>
                        )}
                      </td>

                      {/* Status Badge */}
                      <td>
                        {emp.is_active ? (
                          <span className="admin-status-badge admin-status-delivered">
                            Active
                          </span>
                        ) : (
                          <span className="admin-status-badge admin-status-cancelled">
                            Inactive
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                          <button
                            onClick={() => setSelectedStaff(emp)}
                            style={{
                              padding: '0.4rem 0.65rem',
                              borderRadius: '8px',
                              border: '1px solid var(--tarika-border, #F0E2E0)',
                              backgroundColor: '#FFFFFF',
                              color: '#6B5E63',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.3rem',
                            }}
                            title="Inspect Details"
                          >
                            <Eye size={14} />
                            <span>Details</span>
                          </button>

                          {!isAdmin && (
                            <button
                              onClick={() => handleToggleStatus(emp)}
                              disabled={togglingId === emp.employee_id}
                              style={{
                                padding: '0.4rem 0.65rem',
                                borderRadius: '8px',
                                border: `1px solid ${emp.is_active ? '#FECACA' : '#A7F3D0'}`,
                                backgroundColor: emp.is_active ? '#FEF2F2' : '#ECFDF5',
                                color: emp.is_active ? '#DC2626' : '#059669',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.3rem',
                              }}
                              title={emp.is_active ? 'Deactivate staff account' : 'Activate staff account'}
                            >
                              {emp.is_active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                              <span>{emp.is_active ? 'Deactivate' : 'Activate'}</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ==========================================================================
         CREATE STAFF MODAL
         ========================================================================== */}
      {showCreateModal && (
        <>
          <div
            onClick={() => setShowCreateModal(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              backgroundColor: 'rgba(31, 25, 27, 0.55)',
              backdropFilter: 'blur(4px)',
            }}
          />

          <div
            style={{
              position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
              zIndex: 201, width: 'min(540px, 92vw)', maxHeight: '90vh', overflowY: 'auto',
              backgroundColor: '#FFFFFF', borderRadius: '20px',
              border: '1px solid var(--tarika-border, #F0E2E0)',
              boxShadow: '0 24px 60px rgba(31, 25, 27, 0.2)',
              padding: '2rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.85rem', borderBottom: '1px solid #F0E2E0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#FBF1F0', color: '#B8505E', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <UserCheck size={18} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                    Provision Operational Staff
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63' }}>Create staff credentials and role permissions</p>
                </div>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FAF7F5', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={16} />
              </button>
            </div>

            {formError && (
              <div className="tarika-auth-alert" style={{ marginBottom: '1rem' }}>
                <AlertCircle size={18} />
                <span>{formError}</span>
              </div>
            )}

            {formSuccess && (
              <div style={{ backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669', padding: '0.75rem 1rem', borderRadius: '12px', fontSize: '0.85rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CheckCircle2 size={18} />
                <span>{formSuccess}</span>
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Role Selection */}
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Select Staff Role *</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <button
                    type="button"
                    onClick={() => setCreateForm((prev) => ({ ...prev, role: 'WAREHOUSE_MANAGER' }))}
                    style={{
                      padding: '0.75rem', borderRadius: '12px',
                      border: `1.5px solid ${createForm.role === 'WAREHOUSE_MANAGER' ? '#D8727E' : '#F0E2E0'}`,
                      backgroundColor: createForm.role === 'WAREHOUSE_MANAGER' ? '#FBF1F0' : '#FFFFFF',
                      color: createForm.role === 'WAREHOUSE_MANAGER' ? '#B8505E' : '#6B5E63',
                      fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem'
                    }}
                  >
                    <Building2 size={16} />
                    <span>Warehouse Manager</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setCreateForm((prev) => ({ ...prev, role: 'DELIVERY_PARTNER' }))}
                    style={{
                      padding: '0.75rem', borderRadius: '12px',
                      border: `1.5px solid ${createForm.role === 'DELIVERY_PARTNER' ? '#D8727E' : '#F0E2E0'}`,
                      backgroundColor: createForm.role === 'DELIVERY_PARTNER' ? '#FBF1F0' : '#FFFFFF',
                      color: createForm.role === 'DELIVERY_PARTNER' ? '#B8505E' : '#6B5E63',
                      fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem'
                    }}
                  >
                    <Truck size={16} />
                    <span>Delivery Partner</span>
                  </button>
                </div>
              </div>

              {/* Warehouse Selection if Manager */}
              {createForm.role === 'WAREHOUSE_MANAGER' && (
                <div className="tarika-form-group" style={{ margin: 0 }}>
                  <label className="tarika-form-label">Assigned Warehouse Facility *</label>
                  <div className="tarika-input-wrap">
                    <Building size={16} className="tarika-input-icon" />
                    <select
                      value={createForm.warehouse_id}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, warehouse_id: e.target.value }))}
                      className="tarika-input"
                      style={{ paddingLeft: '2.75rem' }}
                      required
                    >
                      <option value="" disabled>Select a Warehouse Facility</option>
                      {warehouses.map((wh) => (
                        <option key={wh.warehouse_id} value={wh.warehouse_id}>
                          {wh.warehouse_name} ({wh.warehouse_id} - {wh.city})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {/* Full Name */}
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Full Name *</label>
                <div className="tarika-input-wrap">
                  <User size={16} className="tarika-input-icon" />
                  <input
                    type="text"
                    className="tarika-input"
                    placeholder="e.g. Rahul Sharma"
                    value={createForm.full_name}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, full_name: e.target.value }))}
                    required
                  />
                </div>
              </div>

              {/* Email */}
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Email Address *</label>
                <div className="tarika-input-wrap">
                  <Mail size={16} className="tarika-input-icon" />
                  <input
                    type="email"
                    className="tarika-input"
                    placeholder="e.g. rahul@iras.com"
                    value={createForm.email}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, email: e.target.value }))}
                    required
                  />
                </div>
              </div>

              {/* Password */}
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Password * (min 6 characters)</label>
                <div className="tarika-input-wrap">
                  <Lock size={16} className="tarika-input-icon" />
                  <input
                    type="password"
                    className="tarika-input"
                    placeholder="••••••••"
                    value={createForm.password}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
                    required
                    minLength={6}
                  />
                </div>
              </div>

              {/* Phone */}
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Phone Number (Optional)</label>
                <div className="tarika-input-wrap">
                  <Phone size={16} className="tarika-input-icon" />
                  <input
                    type="text"
                    className="tarika-input"
                    placeholder="e.g. 9876543210"
                    value={createForm.phone}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, phone: e.target.value }))}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="tarika-btn-outline"
                  style={{ flex: 1, padding: '0.75rem' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="tarika-btn-primary"
                  style={{ flex: 1.5, padding: '0.75rem' }}
                >
                  {submitting ? (
                    <div className="tarika-auth-spinner" style={{ margin: '0 auto' }} />
                  ) : (
                    <span>Create Staff Credential</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </>
      )}

      {/* ==========================================================================
         STAFF DETAIL INSPECTION MODAL
         ========================================================================== */}
      {selectedStaff && (
        <>
          <div
            onClick={() => setSelectedStaff(null)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              backgroundColor: 'rgba(31, 25, 27, 0.55)',
              backdropFilter: 'blur(4px)',
            }}
          />

          <div
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201,
              width: 'min(480px, 100vw)', backgroundColor: '#FFFFFF',
              boxShadow: '-8px 0 60px rgba(31, 25, 27, 0.18)',
              display: 'flex', flexDirection: 'column', overflowY: 'auto',
            }}
          >
            <div style={{ padding: '1.25rem 1.5rem', backgroundColor: '#FAF7F5', borderBottom: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                Staff Member Profile
              </h3>
              <button
                onClick={() => setSelectedStaff(null)}
                style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FFFFFF', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Header Card */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', background: '#FBF1F0', padding: '1.25rem', borderRadius: '16px', border: '1px solid #F0CFCD' }}>
                <div style={{
                  width: '48px', height: '48px', borderRadius: '50%',
                  background: 'linear-gradient(135deg, #D8727E 0%, #8E3642 100%)',
                  color: '#FFFFFF', fontWeight: 800, fontSize: '1.1rem',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {(selectedStaff.full_name?.[0] || selectedStaff.email?.[0] || 'E').toUpperCase()}
                </div>
                <div>
                  <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#1F191B' }}>
                    {selectedStaff.full_name}
                  </h4>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.8rem', color: '#6B5E63' }}>
                    {selectedStaff.email}
                  </p>
                </div>
              </div>

              {/* Attributes Grid */}
              <div style={{ border: '1px solid #F0E2E0', borderRadius: '16px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Employee Record ID</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B', fontFamily: 'monospace' }}>#{selectedStaff.employee_id}</p>
                </div>

                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Auth User Unique Identifier (UUID)</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 600, color: '#6B5E63', fontFamily: 'monospace', fontSize: '0.78rem', wordBreak: 'break-all' }}>{selectedStaff.auth_user_id}</p>
                </div>

                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Assigned Operational Role</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B' }}>{selectedStaff.role}</p>
                </div>

                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Facility Assignment</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B' }}>
                    {selectedStaff.warehouse_name ? `${selectedStaff.warehouse_name} (${selectedStaff.warehouse_id})` : 'System Unrestricted / Global'}
                  </p>
                </div>

                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Phone / Contact</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 600, color: '#1F191B' }}>{selectedStaff.phone || 'N/A'}</p>
                </div>

                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Account Status</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: selectedStaff.is_active ? '#059669' : '#DC2626' }}>
                    {selectedStaff.is_active ? 'Active' : 'Inactive'}
                  </p>
                </div>

                {selectedStaff.created_at && (
                  <div>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Date Provisioned</span>
                    <p style={{ margin: '0.2rem 0 0', fontWeight: 600, color: '#1F191B' }}>{selectedStaff.created_at}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
