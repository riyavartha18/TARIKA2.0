import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import {
  getCampaigns,
  createCampaign,
  updateCampaign,
  deleteCampaign,
  setCampaignStatus,
} from '../../services/api';
import { Loader2, Plus, Trash2, Send, Pause, RotateCcw, Pencil } from 'lucide-react';

const PALETTE = {
  ink: '#1F191B', muted: '#6B5E63', faint: '#9E8F94',
  rose: '#D8727E', roseDeep: '#B8505E', border: '#F0E2E0', bg: '#FFFFFF',
};

const SEGMENTS = ['Champions', 'Loyal Customers', 'Potential Loyalists', 'New Customers', 'At-Risk', 'Hibernating', 'Never Purchased'];
const TAGS = ['Big Spender'];
const STATUS_COLORS = {
  DRAFT: '#6B5E63', PUBLISHED: '#2E7D32', PAUSED: '#B8505E', EXPIRED: '#9E8F94',
};

const emptyForm = () => ({
  name: '', coupon_code: '', description: '',
  discount_type: 'PERCENTAGE', discount_value: 10, max_discount: '',
  target_segments: [], target_tags: [],
  start_date: '', end_date: '',
  min_order_amount: 0, usage_type: 'UNLIMITED', per_customer_limit: 0,
  global_usage_limit: 0, stacking_allowed: false, status: 'DRAFT',
});

function toLocalInput(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AdminCampaignView() {
  const { token } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await getCampaigns(token);
    if (res.success) setCampaigns(res.campaigns);
    else setError(res.error);
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const toggleList = (key, value) =>
    setForm((f) => {
      const list = f[key].includes(value) ? f[key].filter((x) => x !== value) : [...f[key], value];
      return { ...f, [key]: list };
    });

  const resetForm = () => { setForm(emptyForm()); setEditingId(null); };

  const startEdit = (c) => {
    setEditingId(c.campaign_id);
    setForm({
      name: c.name, coupon_code: c.coupon_code, description: c.description || '',
      discount_type: c.discount_type, discount_value: c.discount_value,
      max_discount: c.max_discount ?? '', target_segments: c.target_segments || [],
      target_tags: c.target_tags || [],
      start_date: toLocalInput(c.start_date), end_date: toLocalInput(c.end_date),
      min_order_amount: c.min_order_amount, usage_type: c.usage_type,
      per_customer_limit: c.per_customer_limit, global_usage_limit: c.global_usage_limit,
      stacking_allowed: c.stacking_allowed, status: c.status,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null); setNotice(null);
    const payload = {
      ...form,
      discount_value: Number(form.discount_value) || 0,
      min_order_amount: Number(form.min_order_amount) || 0,
      per_customer_limit: Number(form.per_customer_limit) || 0,
      global_usage_limit: Number(form.global_usage_limit) || 0,
      max_discount: form.max_discount === '' ? null : Number(form.max_discount),
      start_date: form.start_date ? new Date(form.start_date).toISOString() : '',
      end_date: form.end_date ? new Date(form.end_date).toISOString() : '',
    };
    const res = editingId
      ? await updateCampaign(token, editingId, payload)
      : await createCampaign(token, payload);
    setSaving(false);
    if (res.success) {
      setNotice(editingId ? 'Campaign updated.' : 'Campaign created as draft.');
      resetForm();
      await load();
    } else {
      setError(res.error);
    }
  };

  const changeStatus = async (c, status) => {
    const res = await setCampaignStatus(token, c.campaign_id, status);
    if (res.success) { setNotice(`Campaign ${status.toLowerCase()}.`); await load(); }
    else setError(res.error);
  };

  const remove = async (c) => {
    if (!window.confirm(`Delete campaign "${c.name}"?`)) return;
    const res = await deleteCampaign(token, c.campaign_id);
    if (res.success) { setNotice('Campaign deleted.'); await load(); }
    else setError(res.error);
  };

  const labelStyle = { fontSize: '0.76rem', fontWeight: 700, color: PALETTE.muted, display: 'block', marginBottom: 4 };
  const inputStyle = { width: '100%', boxSizing: 'border-box', border: `1px solid ${PALETTE.border}`, borderRadius: 9, padding: '0.5rem 0.6rem', fontSize: '0.85rem', color: PALETTE.ink };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
      <div>
        <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.7rem', color: PALETTE.ink, margin: 0 }}>Campaign Management</h2>
        <p style={{ color: PALETTE.muted, margin: '0.35rem 0 0', fontSize: '0.9rem' }}>
          Author, target and publish coupon campaigns. Nothing is visible to customers until you <strong>Publish</strong> it.
        </p>
      </div>

      {error && <Banner color="#B3261E" bg="#FDECEA" border="#F5C6C0" text={error} />}
      {notice && <Banner color="#2E7D32" bg="#EAF5EB" border="#C6E5C9" text={notice} />}

      {/* Create / edit form */}
      <form onSubmit={handleSubmit} style={{ backgroundColor: PALETTE.bg, border: `1px solid ${PALETTE.border}`, borderRadius: 16, padding: '1.3rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0, fontSize: '1.05rem', color: PALETTE.ink }}>{editingId ? `Edit campaign #${editingId}` : 'New campaign'}</h3>
          {editingId && <button type="button" onClick={resetForm} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.35rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem', color: PALETTE.muted }}>Cancel edit</button>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem' }}>
          <div><label style={labelStyle}>Name</label><input style={inputStyle} value={form.name} onChange={(e) => setField('name', e.target.value)} required /></div>
          <div><label style={labelStyle}>Coupon code</label><input style={inputStyle} value={form.coupon_code} onChange={(e) => setField('coupon_code', e.target.value.toUpperCase())} required /></div>
          <div>
            <label style={labelStyle}>Discount type</label>
            <select style={inputStyle} value={form.discount_type} onChange={(e) => setField('discount_type', e.target.value)}>
              <option value="PERCENTAGE">Percentage</option>
              <option value="FIXED">Fixed amount</option>
            </select>
          </div>
          <div><label style={labelStyle}>Discount value</label><input style={inputStyle} type="number" step="0.01" min="0" value={form.discount_value} onChange={(e) => setField('discount_value', e.target.value)} required /></div>
          <div><label style={labelStyle}>Max discount (optional)</label><input style={inputStyle} type="number" step="0.01" min="0" value={form.max_discount} onChange={(e) => setField('max_discount', e.target.value)} /></div>
          <div><label style={labelStyle}>Minimum order amount</label><input style={inputStyle} type="number" step="0.01" min="0" value={form.min_order_amount} onChange={(e) => setField('min_order_amount', e.target.value)} /></div>
          <div><label style={labelStyle}>Start date</label><input style={inputStyle} type="datetime-local" value={form.start_date} onChange={(e) => setField('start_date', e.target.value)} required /></div>
          <div><label style={labelStyle}>End date</label><input style={inputStyle} type="datetime-local" value={form.end_date} onChange={(e) => setField('end_date', e.target.value)} required /></div>
          <div>
            <label style={labelStyle}>Per-customer usage</label>
            <select style={inputStyle} value={form.usage_type} onChange={(e) => setField('usage_type', e.target.value)}>
              <option value="ONCE">Once per customer</option>
              <option value="LIMITED">Limited uses</option>
              <option value="UNLIMITED">Unlimited</option>
            </select>
          </div>
          {form.usage_type === 'LIMITED' && (
            <div><label style={labelStyle}>Uses per customer</label><input style={inputStyle} type="number" min="1" value={form.per_customer_limit} onChange={(e) => setField('per_customer_limit', e.target.value)} /></div>
          )}
          <div><label style={labelStyle}>Global usage limit (0 = none)</label><input style={inputStyle} type="number" min="0" value={form.global_usage_limit} onChange={(e) => setField('global_usage_limit', e.target.value)} /></div>
        </div>

        <div style={{ marginTop: '1rem' }}>
          <label style={labelStyle}>Target primary segments</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {SEGMENTS.map((s) => (
              <Chip key={s} active={form.target_segments.includes(s)} onClick={() => toggleList('target_segments', s)} label={s} />
            ))}
          </div>
        </div>
        <div style={{ marginTop: '0.9rem' }}>
          <label style={labelStyle}>Required secondary tags</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {TAGS.map((t) => (
              <Chip key={t} active={form.target_tags.includes(t)} onClick={() => toggleList('target_tags', t)} label={t} />
            ))}
          </div>
        </div>

        <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '1.2rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: PALETTE.muted }}>
            <input type="checkbox" checked={form.stacking_allowed} onChange={(e) => setField('stacking_allowed', e.target.checked)} /> Allow stacking
          </label>
          <button type="submit" disabled={saving} style={{ marginLeft: 'auto', border: 'none', background: PALETTE.roseDeep, color: '#fff', borderRadius: 10, padding: '0.65rem 1.4rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, opacity: saving ? 0.6 : 1 }}>
            {saving ? <Loader2 size={16} style={{ animation: 'spin 0.8s linear infinite' }} /> : <Plus size={16} />}
            {editingId ? 'Save changes' : 'Create draft'}
          </button>
        </div>
      </form>

      {/* Campaign list */}
      <div style={{ backgroundColor: PALETTE.bg, border: `1px solid ${PALETTE.border}`, borderRadius: 16, overflowX: 'auto' }}>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint }}>Loading campaigns…</div>
        ) : campaigns.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint }}>No campaigns yet.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#FBF5F4' }}>
                {['Campaign', 'Coupon', 'Discount', 'Segments', 'Validity', 'Usage', 'Status', 'Actions'].map((h) => (
                  <th key={h} style={{ padding: '0.7rem 0.8rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.campaign_id} style={{ borderTop: `1px solid ${PALETTE.border}` }}>
                  <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.ink, fontWeight: 600 }}>{c.name}</td>
                  <td style={{ padding: '0.7rem 0.8rem' }}><code style={{ backgroundColor: '#F7EFEE', padding: '2px 6px', borderRadius: 6 }}>{c.coupon_code}</code></td>
                  <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.ink }}>{c.discount_type === 'PERCENTAGE' ? `${c.discount_value}%` : `₹${c.discount_value}`}</td>
                  <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.muted }}>{(c.target_segments || []).join(', ')}</td>
                  <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.faint, fontSize: '0.76rem' }}>{new Date(c.start_date).toLocaleDateString()} → {new Date(c.end_date).toLocaleDateString()}</td>
                  <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.muted }}>{c.usage_type}{c.usage_type === 'LIMITED' ? ` (${c.per_customer_limit})` : ''}</td>
                  <td style={{ padding: '0.7rem 0.8rem' }}>
                    <span style={{ color: STATUS_COLORS[c.status] || PALETTE.muted, fontWeight: 700, fontSize: '0.76rem' }}>{c.status}</span>
                  </td>
                  <td style={{ padding: '0.7rem 0.8rem', whiteSpace: 'nowrap' }}>
                    <IconBtn title="Edit" onClick={() => startEdit(c)}><Pencil size={15} /></IconBtn>
                    {c.status !== 'PUBLISHED' ? (
                      <IconBtn title="Publish" onClick={() => changeStatus(c, 'PUBLISHED')}><Send size={15} /></IconBtn>
                    ) : (
                      <IconBtn title="Pause" onClick={() => changeStatus(c, 'PAUSED')}><Pause size={15} /></IconBtn>
                    )}
                    {c.status !== 'DRAFT' && <IconBtn title="Back to draft" onClick={() => changeStatus(c, 'DRAFT')}><RotateCcw size={15} /></IconBtn>}
                    <IconBtn title="Delete" danger onClick={() => remove(c)}><Trash2 size={15} /></IconBtn>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Chip({ active, onClick, label }) {
  return (
    <button type="button" onClick={onClick} style={{
      border: `1px solid ${active ? PALETTE.roseDeep : PALETTE.border}`,
      backgroundColor: active ? 'rgba(216,114,126,0.14)' : '#fff',
      color: active ? PALETTE.roseDeep : PALETTE.muted,
      borderRadius: 20, padding: '0.32rem 0.75rem', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 600,
    }}>{label}</button>
  );
}

function IconBtn({ children, onClick, title, danger }) {
  return (
    <button type="button" title={title} onClick={onClick} style={{
      border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8,
      padding: '0.3rem', cursor: 'pointer', marginRight: 4, color: danger ? '#B3261E' : PALETTE.roseDeep,
      display: 'inline-flex', alignItems: 'center',
    }}>{children}</button>
  );
}

function Banner({ color, bg, border, text }) {
  return <div style={{ color, backgroundColor: bg, border: `1px solid ${border}`, borderRadius: 12, padding: '0.8rem 1rem', fontSize: '0.88rem' }}>{text}</div>;
}
