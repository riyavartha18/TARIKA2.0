import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getStaffList, createStaffMember, updateStaffMember, toggleStaffStatus } from '../../services/api';
import {
  Users, UserCheck, ShieldCheck, Search, Filter, Plus, X, Edit3,
  ToggleLeft, ToggleRight, AlertCircle, CheckCircle2, RefreshCw, Mail, Lock,
} from 'lucide-react';

// Canonical app_users roles (lowercase) -> friendly labels.
const ROLE_LABELS = {
  admin: 'Admin',
  warehouse_manager: 'Warehouse Manager',
  delivery: 'Delivery Partner',
};

const ROLE_BADGE = {
  admin: { bg: 'rgba(212,175,55,0.15)', fg: '#997A15', border: 'rgba(212,175,55,0.3)' },
  warehouse_manager: { bg: '#F1F5F9', fg: '#2563EB', border: '#BFDBFE' },
  delivery: { bg: '#FFFBEB', fg: '#D97706', border: '#FDE68A' },
};

const emptyForm = { email: '', password: '', role: 'warehouse_manager' };

export default function AdminStaffView() {
  const { token, user: authUser } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState({ total_staff: 0, admins: 0, warehouse_managers: 0, delivery_partners: 0, active_staff: 0 });
  const [staff, setStaff] = useState([]);

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState(null);          // staff row being edited
  const [createForm, setCreateForm] = useState(emptyForm);
  const [editForm, setEditForm] = useState({ role: '', is_active: true, password: '' });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [formSuccess, setFormSuccess] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const isSelf = (userId) => String(userId) === String(authUser?.id);

  const fetchStaff = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await getStaffList(token, { search, role: roleFilter, status: statusFilter });
    if (res.success) {
      setSummary(res.summary || {});
      setStaff(res.staff || []);
    } else {
      setError(res.error || 'Failed to load staff members.');
    }
    setLoading(false);
  }, [token, search, roleFilter, statusFilter]);

  useEffect(() => { fetchStaff(); }, [fetchStaff]);

  const submitCreate = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    setFormSuccess(null);
    if (!createForm.email.trim()) { setFormError('Email address is required.'); return; }
    if (!createForm.password || createForm.password.length < 6) { setFormError('Password must be at least 6 characters.'); return; }
    if (!createForm.role) { setFormError('A role is required.'); return; }

    setSubmitting(true);
    const res = await createStaffMember(token, {
      email: createForm.email.trim(),
      password: createForm.password,
      role: createForm.role,
    });
    setSubmitting(false);
    if (res.success) {
      setFormSuccess(res.message || 'Staff account created.');
      setCreateForm(emptyForm);
      fetchStaff();                         // reconcile with the persisted DB state
      setTimeout(() => { setShowCreate(false); setFormSuccess(null); }, 1200);
    } else {
      setFormError(res.error || 'Failed to create staff member.');
    }
  };

  const openEdit = (s) => {
    setEditing(s);
    setEditForm({ role: s.role, is_active: s.is_active, password: '' });
    setFormError(null);
    setFormSuccess(null);
  };

  const submitEdit = async (e) => {
    e.preventDefault();
    if (!editing || submitting) return;
    setFormError(null);
    const payload = { role: editForm.role, is_active: editForm.is_active };
    if (editForm.password) payload.password = editForm.password;

    setSubmitting(true);
    const res = await updateStaffMember(token, editing.user_id, payload);
    setSubmitting(false);
    if (res.success) {
      setStaff((prev) => prev.map((s) => (s.user_id === editing.user_id ? { ...s, ...res.staff } : s)));
      setEditing(null);
      fetchStaff();
    } else {
      setFormError(res.error || 'Failed to update staff member.');
    }
  };

  const handleToggle = async (s) => {
    if (busyId) return;
    setBusyId(s.user_id);
    const res = await toggleStaffStatus(token, s.user_id, !s.is_active);
    if (res.success) {
      setStaff((prev) => prev.map((x) => (x.user_id === s.user_id ? { ...x, ...res.staff } : x)));
      fetchStaff();
    } else {
      alert(res.error || 'Failed to update status.');
    }
    setBusyId(null);
  };

  const renderRoleBadge = (role) => {
    const b = ROLE_BADGE[role] || { bg: '#F4F4F5', fg: '#52525B', border: '#E4E4E7' };
    return (
      <span className="admin-status-badge" style={{ backgroundColor: b.bg, color: b.fg, border: `1px solid ${b.border}` }}>
        {role === 'admin' && <ShieldCheck size={12} />} {ROLE_LABELS[role] || role}
      </span>
    );
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: '0 0 0.35rem' }}>
            Staff Management
          </h1>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: 0 }}>
            Provision, assign and manage staff accounts (backed by the app_users table).
          </p>
        </div>
        <button onClick={() => { setShowCreate(true); setFormError(null); setFormSuccess(null); }}
          className="tarika-btn-primary" style={{ padding: '0.75rem 1.4rem', fontSize: '0.875rem' }}>
          <Plus size={16} /><span>Add Staff Member</span>
        </button>
      </div>

      {/* Summary KPI cards */}
      <div className="admin-metrics-grid" style={{ marginBottom: '1.75rem' }}>
        <div className="admin-metric-card">
          <div className="admin-metric-top"><div className="admin-metric-icon"><Users size={22} /></div><span className="admin-metric-status">All</span></div>
          <div><p className="admin-metric-title">Total Staff</p><p className="admin-metric-val">{summary.total_staff || 0}</p>
            <p className="admin-metric-subtext">{summary.active_staff || 0} active in database</p></div>
        </div>
        <div className="admin-metric-card">
          <div className="admin-metric-top"><div className="admin-metric-icon"><ShieldCheck size={22} /></div></div>
          <div><p className="admin-metric-title">Admins</p><p className="admin-metric-val">{summary.admins || 0}</p></div>
        </div>
        <div className="admin-metric-card">
          <div className="admin-metric-top"><div className="admin-metric-icon"><UserCheck size={22} /></div></div>
          <div><p className="admin-metric-title">Warehouse Managers</p><p className="admin-metric-val">{summary.warehouse_managers || 0}</p></div>
        </div>
        <div className="admin-metric-card">
          <div className="admin-metric-top"><div className="admin-metric-icon"><Users size={22} /></div></div>
          <div><p className="admin-metric-title">Delivery Partners</p><p className="admin-metric-val">{summary.delivery_partners || 0}</p></div>
        </div>
      </div>

      {/* Search & filters */}
      <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.15rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 280px', position: 'relative' }}>
            <Search size={17} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9E8F94' }} />
            <input type="text" placeholder="Search by email…" value={search} onChange={(e) => setSearch(e.target.value)}
              style={{ width: '100%', padding: '0.65rem 0.85rem 0.65rem 2.4rem', borderRadius: '10px', border: '1.5px solid var(--tarika-border, #F0E2E0)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Filter size={15} color="#6B5E63" /><span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#6B5E63' }}>Role:</span>
            <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} style={{ padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1.5px solid var(--tarika-border, #F0E2E0)', fontSize: '0.85rem', backgroundColor: '#FFFFFF', cursor: 'pointer' }}>
              <option value="ALL">All Roles</option><option value="admin">Admin</option><option value="warehouse_manager">Warehouse Manager</option><option value="delivery">Delivery Partner</option>
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#6B5E63' }}>Status:</span>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1.5px solid var(--tarika-border, #F0E2E0)', fontSize: '0.85rem', backgroundColor: '#FFFFFF', cursor: 'pointer' }}>
              <option value="ALL">All Statuses</option><option value="ACTIVE">Active Only</option><option value="INACTIVE">Inactive Only</option>
            </select>
          </div>
          <button onClick={fetchStaff} title="Refresh" style={{ padding: '0.65rem', borderRadius: '10px', border: '1.5px solid var(--tarika-border, #F0E2E0)', backgroundColor: '#FFFFFF', color: '#6B5E63', cursor: 'pointer', display: 'flex' }}>
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Staff table */}
      <div className="admin-card">
        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
            <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216,114,126,0.25)', borderTopColor: '#D8727E' }} />
            <p style={{ color: '#6B5E63', fontWeight: 600 }}>Loading staff records from database…</p>
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#DC2626' }}>
            <AlertCircle size={28} style={{ margin: '0 auto 0.5rem' }} /><p style={{ margin: 0, fontWeight: 600 }}>{error}</p>
          </div>
        ) : staff.length === 0 ? (
          <div style={{ padding: '3rem 1rem', textAlign: 'center', color: '#6B5E63' }}>
            <Users size={36} color="#9E8F94" style={{ margin: '0 auto 0.75rem' }} />
            <h4 style={{ margin: '0 0 0.35rem', color: '#1F191B', fontFamily: 'var(--font-serif)' }}>No Staff Members Found</h4>
            <p style={{ margin: 0, fontSize: '0.85rem' }}>No staff records match your current search or filters.</p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead><tr><th>Staff Email</th><th>Role</th><th>Status</th><th>Created</th><th>Last Updated</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
              <tbody>
                {staff.map((s) => (
                  <tr key={s.user_id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div style={{ width: 38, height: 38, borderRadius: '50%', background: s.role === 'admin' ? 'linear-gradient(135deg,#D4AF37,#997A15)' : 'linear-gradient(135deg,#D8727E,#8E3642)', color: '#FFF', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          {(s.email?.[0] || 'S').toUpperCase()}
                        </div>
                        <span style={{ fontWeight: 600, color: '#1F191B' }}>{s.email}</span>
                      </div>
                    </td>
                    <td>{renderRoleBadge(s.role)}</td>
                    <td>{s.is_active ? <span className="admin-status-badge admin-status-delivered">Active</span> : <span className="admin-status-badge admin-status-cancelled">Inactive</span>}</td>
                    <td style={{ fontSize: '0.78rem', color: '#6B5E63' }}>{s.created_at ? String(s.created_at).slice(0, 10) : '—'}</td>
                    <td style={{ fontSize: '0.78rem', color: '#6B5E63' }}>{s.updated_at ? String(s.updated_at).slice(0, 10) : '—'}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                        <button onClick={() => openEdit(s)} style={{ padding: '0.4rem 0.65rem', borderRadius: '8px', border: '1px solid var(--tarika-border,#F0E2E0)', backgroundColor: '#FFF', color: '#6B5E63', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }} title="Edit role / status">
                          <Edit3 size={14} /><span>Edit</span>
                        </button>
                        {!isSelf(s.user_id) && (
                          <button onClick={() => handleToggle(s)} disabled={busyId === s.user_id} style={{ padding: '0.4rem 0.65rem', borderRadius: '8px', border: `1px solid ${s.is_active ? '#FECACA' : '#A7F3D0'}`, backgroundColor: s.is_active ? '#FEF2F2' : '#ECFDF5', color: s.is_active ? '#DC2626' : '#059669', fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }} title={s.is_active ? 'Deactivate' : 'Activate'}>
                            {s.is_active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}<span>{busyId === s.user_id ? 'Saving…' : s.is_active ? 'Deactivate' : 'Activate'}</span>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <>
          <div onClick={() => !submitting && setShowCreate(false)} style={{ position: 'fixed', inset: 0, zIndex: 200, backgroundColor: 'rgba(31,25,27,0.55)', backdropFilter: 'blur(4px)' }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 201, width: 'min(520px,92vw)', maxHeight: '90vh', overflowY: 'auto', backgroundColor: '#FFF', borderRadius: '20px', border: '1px solid var(--tarika-border,#F0E2E0)', boxShadow: '0 24px 60px rgba(31,25,27,0.2)', padding: '2rem' }}>
            <ModalHeader title="Add Staff Member" subtitle="Create app_users credentials and role" onClose={() => !submitting && setShowCreate(false)} />
            {formError && <Alert error={formError} />}
            {formSuccess && <Success msg={formSuccess} />}
            <form onSubmit={submitCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Role *</label>
                <select value={createForm.role} onChange={(e) => setCreateForm((p) => ({ ...p, role: e.target.value }))} className="tarika-input" style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1.5px solid var(--tarika-border,#F0E2E0)', boxSizing: 'border-box' }}>
                  <option value="warehouse_manager">Warehouse Manager</option>
                  <option value="delivery">Delivery Partner</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Email Address *</label>
                <div className="tarika-input-wrap"><Mail size={16} className="tarika-input-icon" />
                  <input type="email" className="tarika-input" placeholder="name@iras.com" value={createForm.email} onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))} required /></div>
              </div>
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Password * (min 6 characters)</label>
                <div className="tarika-input-wrap"><Lock size={16} className="tarika-input-icon" />
                  <input type="password" className="tarika-input" placeholder="••••••••" value={createForm.password} onChange={(e) => setCreateForm((p) => ({ ...p, password: e.target.value }))} required minLength={6} /></div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="button" onClick={() => setShowCreate(false)} className="tarika-btn-outline" style={{ flex: 1, padding: '0.75rem' }}>Cancel</button>
                <button type="submit" disabled={submitting} className="tarika-btn-primary" style={{ flex: 1.5, padding: '0.75rem' }}>{submitting ? 'Creating…' : 'Create Staff'}</button>
              </div>
            </form>
          </div>
        </>
      )}

      {/* Edit modal */}
      {editing && (
        <>
          <div onClick={() => !submitting && setEditing(null)} style={{ position: 'fixed', inset: 0, zIndex: 200, backgroundColor: 'rgba(31,25,27,0.55)', backdropFilter: 'blur(4px)' }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 201, width: 'min(520px,92vw)', backgroundColor: '#FFF', borderRadius: '20px', border: '1px solid var(--tarika-border,#F0E2E0)', boxShadow: '0 24px 60px rgba(31,25,27,0.2)', padding: '2rem' }}>
            <ModalHeader title="Edit Staff Member" subtitle={editing.email} onClose={() => !submitting && setEditing(null)} />
            {formError && <Alert error={formError} />}
            <form onSubmit={submitEdit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">Role *</label>
                <select value={editForm.role} onChange={(e) => setEditForm((p) => ({ ...p, role: e.target.value }))} className="tarika-input" style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1.5px solid var(--tarika-border,#F0E2E0)', boxSizing: 'border-box' }}>
                  <option value="warehouse_manager">Warehouse Manager</option>
                  <option value="delivery">Delivery Partner</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <input type="checkbox" id="staff-active" checked={editForm.is_active} onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.checked }))} disabled={isSelf(editing.user_id)} />
                <label htmlFor="staff-active" style={{ fontSize: '0.85rem', color: '#1F191B', fontWeight: 600 }}>Account active</label>
                {isSelf(editing.user_id) && <span style={{ fontSize: '0.72rem', color: '#9E8F94' }}>(cannot change your own status)</span>}
              </div>
              <div className="tarika-form-group" style={{ margin: 0 }}>
                <label className="tarika-form-label">New Password (optional — leave blank to keep)</label>
                <div className="tarika-input-wrap"><Lock size={16} className="tarika-input-icon" />
                  <input type="password" className="tarika-input" placeholder="••••••••" value={editForm.password} onChange={(e) => setEditForm((p) => ({ ...p, password: e.target.value }))} minLength={6} /></div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="button" onClick={() => setEditing(null)} className="tarika-btn-outline" style={{ flex: 1, padding: '0.75rem' }}>Cancel</button>
                <button type="submit" disabled={submitting} className="tarika-btn-primary" style={{ flex: 1.5, padding: '0.75rem' }}>{submitting ? 'Saving…' : 'Save Changes'}</button>
              </div>
            </form>
          </div>
        </>
      )}
    </div>
  );
}

function ModalHeader({ title, subtitle, onClose }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', paddingBottom: '0.85rem', borderBottom: '1px solid #F0E2E0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: '#FBF1F0', color: '#B8505E', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><UserCheck size={18} /></div>
        <div><h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>{title}</h3>
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63' }}>{subtitle}</p></div>
      </div>
      <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FAF7F5', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><X size={16} /></button>
    </div>
  );
}

function Alert({ error }) {
  return <div className="tarika-auth-alert" style={{ marginBottom: '1rem' }}><AlertCircle size={18} /><span>{error}</span></div>;
}

function Success({ msg }) {
  return <div style={{ backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669', padding: '0.75rem 1rem', borderRadius: '12px', fontSize: '0.85rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={18} /><span>{msg}</span></div>;
}
