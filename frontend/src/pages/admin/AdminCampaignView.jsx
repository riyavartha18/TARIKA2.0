import React, { useState, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import {
  createCampaign,
  updateCampaign,
  setCampaignStatus,
} from '../../services/api';
import CampaignForm from './campaigns/CampaignForm';
import CampaignList from './campaigns/CampaignList';
import { PALETTE, emptyForm, formFromCampaign } from './campaigns/offerCatalog';

/**
 * Campaign Management (upgraded): discount offers, Buy & Get offers or both,
 * with mandatory RFM segment targeting. Everything is persisted through the
 * existing /api/campaigns/ endpoints; customer visibility and coupon
 * eligibility are enforced on the backend against the latest RFM analysis.
 */
export default function AdminCampaignView() {
  const { token } = useAuth();
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  const refreshList = useCallback(() => setRefreshToken((t) => t + 1), []);

  const handleEdit = useCallback((c) => {
    if (!c) { setError(null); return; }
    setEditingId(c.campaign_id);
    setForm(formFromCampaign(c));
    setNotice(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  // Editing exits through the form's own cancel; list actions call onEdit(null)
  // only to clear banners, so keep the form state there.
  const handleCancelEdit = () => { setEditingId(null); setForm(emptyForm()); };

  const handleSubmit = async (payload, statusAction) => {
    setSaving(true);
    setError(null); setNotice(null);
    let res;
    if (editingId) {
      res = await updateCampaign(token, editingId, payload);
      if (res.success) {
        setNotice('Campaign updated.');
        setEditingId(null);
        setForm(emptyForm());
      }
    } else {
      res = await createCampaign(token, payload);
      if (res.success) {
        if (statusAction === 'PUBLISHED') {
          const statusRes = await setCampaignStatus(token, res.campaign.campaign_id, 'PUBLISHED');
          if (!statusRes.success) {
            setNotice(`Campaign saved as draft, but publishing failed: ${statusRes.error}`);
            setSaving(false);
            refreshList();
            return;
          }
          setNotice('Campaign published. Only customers in the selected segments can see it.');
        } else {
          setNotice('Campaign created as draft.');
        }
        setEditingId(null);
        setForm(emptyForm());
      }
    }
    if (!res.success) setError(res.error);
    setSaving(false);
    refreshList();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
      <div>
        <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.7rem', color: PALETTE.ink, margin: 0 }}>Campaign Management</h2>
        <p style={{ color: PALETTE.muted, margin: '0.35rem 0 0', fontSize: '0.9rem' }}>
          Create discount offers, Buy &amp; Get offers or both, and choose exactly which RFM
          segments receive them. Nothing is visible to customers until you <strong>Publish</strong> it.
        </p>
      </div>

      {error && <Banner color="#B3261E" bg="#FDECEA" border="#F5C6C0" text={error} />}
      {notice && <Banner color="#2E7D32" bg="#EAF5EB" border="#C6E5C9" text={notice} />}

      <div style={{ position: 'relative' }}>
        <CampaignForm
          editingId={editingId}
          initialForm={form}
          saving={saving}
          onSubmit={handleSubmit}
        />
        {editingId && (
          <button type="button" onClick={handleCancelEdit}
            style={{ position: 'absolute', top: '1.3rem', right: '1.3rem', border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.35rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem', color: PALETTE.muted }}>
            Cancel edit
          </button>
        )}
      </div>

      <CampaignList token={token} editingId={editingId} onEdit={handleEdit} refreshToken={refreshToken} />
    </div>
  );
}

function Banner({ color, bg, border, text }) {
  return <div style={{ color, backgroundColor: bg, border: `1px solid ${border}`, borderRadius: 12, padding: '0.8rem 1rem', fontSize: '0.88rem' }}>{text}</div>;
}
