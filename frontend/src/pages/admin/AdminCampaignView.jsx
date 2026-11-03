import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import {
  createCampaign,
  updateCampaign,
  setCampaignStatus,
  getCampaignClusters,
} from '../../services/api';
import CampaignForm from './campaigns/CampaignForm';
import CampaignList from './campaigns/CampaignList';
import CustomerGroupPanel from './campaigns/CustomerGroupPanel';
import { PALETTE, emptyForm, formFromCampaign, KMEANS_MODE } from './campaigns/offerCatalog';

/**
 * Campaign Management: discount offers, Buy & Get offers or both, aimed at one
 * or more of the four K-Means customer groups of the latest persisted clustering
 * run. Everything is persisted through the existing /api/campaigns/ endpoints;
 * publishing issues the coupon to those customers and customer visibility and
 * coupon eligibility are enforced on the backend against the stored assignments.
 * Campaigns published earlier against the old rule-based segments stay exactly
 * as they were - the page only shows them their own historical audience.
 */
export default function AdminCampaignView() {
  const { token } = useAuth();
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [editingId, setEditingId] = useState(null);
  const [editingStatus, setEditingStatus] = useState(null);
  // True while a campaign authored on the previous RFM segmentation is open: its
  // stored segments are history, not a target the page offers.
  const [editingLegacyAudience, setEditingLegacyAudience] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const [clusters, setClusters] = useState([]);
  const [clusteringRun, setClusteringRun] = useState(null);
  const [clustersLoading, setClustersLoading] = useState(true);
  const [clustersError, setClustersError] = useState(null);
  // The audience currently chosen in the form, mirrored here so the always-visible
  // group panel can highlight it, and the pulse that pushes a panel click into
  // the form without re-seeding (and resetting) it.
  const [selectedClusters, setSelectedClusters] = useState([]);
  const [audiencePulse, setAudiencePulse] = useState(null);

  const refreshList = useCallback(() => setRefreshToken((t) => t + 1), []);

  // The selectable groups, their labels and their customer counts always come
  // from the persisted clustering run the backend reports.
  const loadClusters = useCallback(async () => {
    setClustersLoading(true);
    setClustersError(null);
    const res = await getCampaignClusters(token);
    if (res.success) {
      setClusters(res.clusters);
      setClusteringRun(res.run);
      if (!res.available) setClustersError(res.message || 'No K-Means clustering has been persisted yet.');
    } else {
      setClustersError(res.error);
    }
    setClustersLoading(false);
  }, [token]);

  useEffect(() => { loadClusters(); }, [loadClusters]);

  const handleEdit = useCallback((c) => {
    if (!c) { setError(null); return; }
    setEditingId(c.campaign_id);
    setEditingStatus(c.status);
    setEditingLegacyAudience((c.targeting_mode || '') !== KMEANS_MODE);
    setForm(formFromCampaign(c));
    setSelectedClusters(c.target_cluster_ids || []);
    setNotice(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  // Editing exits through the form's own cancel; list actions call onEdit(null)
  // only to clear banners, so keep the form state there.
  const handleCancelEdit = () => {
    setEditingId(null); setEditingStatus(null); setEditingLegacyAudience(false);
    setForm(emptyForm()); setSelectedClusters([]);
  };

  // The form reports its audience here; the panel pushes clicks into the form.
  const handleAudienceChange = useCallback((ids) => setSelectedClusters(ids || []), []);
  const toggleFromPanel = useCallback((clusterId) => {
    setAudiencePulse((prev) => ({ clusterId, seq: (prev?.seq || 0) + 1 }));
    setSelectedClusters((prev) => (prev.includes(clusterId)
      ? prev.filter((x) => x !== clusterId)
      : [...prev, clusterId]));
  }, []);

  // What publishing actually did: the customers targeted and the coupons handed
  // out through the existing assignment records.
  const publishNotice = (audience, campaign) => {
    if (!audience) { setNotice('Campaign published. Only its targeted customers can see it.'); return; }
    const groups = (audience.clusters || []).map((g) => g.category).filter(Boolean).join(' + ');
    setNotice(`Campaign published${campaign ? ` "${campaign.name}"` : ''}`
      + `${groups ? ` to ${groups}` : ''}: ${Number(audience.targeted || 0).toLocaleString('en-IN')} customers targeted,`
      + ` ${Number(audience.newly_assigned || 0).toLocaleString('en-IN')} coupons newly issued`
      + ` (${Number(audience.coupons_issued || 0).toLocaleString('en-IN')} in total).`);
  };

  const handleSubmit = async (payload, statusAction) => {
    setSaving(true);
    setError(null); setNotice(null);
    let res;
    if (editingId) {
      res = await updateCampaign(token, editingId, payload);
      if (res.success) {
        setNotice('Campaign updated.'
          + (payload.targeting_mode === KMEANS_MODE
            ? ' Its audience stays the customers its coupons were already issued to; publishing again only extends it to newly selected groups.'
            : ''));
        setEditingId(null);
        setEditingStatus(null);
        setEditingLegacyAudience(false);
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
            loadClusters();
            return;
          }
          publishNotice(statusRes.audience, res.campaign);
        } else {
          setNotice('Campaign created as draft.');
        }
        setEditingId(null);
        setEditingStatus(null);
        setEditingLegacyAudience(false);
        setForm(emptyForm());
      }
    }
    if (!res.success) setError(res.error);
    setSaving(false);
    refreshList();
    loadClusters();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.4rem' }}>
      <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.7rem', color: PALETTE.ink, margin: 0 }}>Campaign Management</h2>

      {error && <Banner color="#B3261E" bg="#FDECEA" border="#F5C6C0" text={error} />}
      {notice && <Banner color="#2E7D32" bg="#EAF5EB" border="#C6E5C9" text={notice} />}

      {/* All four customer groups, always visible: audience, issued and redeemed
          coupons, and the live campaign status of each group. */}
      <CustomerGroupPanel
        clusters={clusters}
        loading={clustersLoading}
        error={clustersError}
        run={clusteringRun}
        selected={selectedClusters}
        onToggle={toggleFromPanel}
      />

      <div style={{ position: 'relative' }}>
        <CampaignForm
          editingId={editingId}
          editingStatus={editingStatus}
          editingLegacyAudience={editingLegacyAudience}
          initialForm={form}
          saving={saving}
          onSubmit={handleSubmit}
          clusters={clusters}
          clustersLoading={clustersLoading}
          clustersError={clustersError}
          clusteringRun={clusteringRun}
          audiencePulse={audiencePulse}
          onAudienceChange={handleAudienceChange}
        />
        {editingId && (
          <button type="button" onClick={handleCancelEdit}
            style={{ position: 'absolute', top: '1.3rem', right: '1.3rem', border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.35rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem', color: PALETTE.muted }}>
            Cancel edit
          </button>
        )}
      </div>

      <CampaignList
        token={token}
        editingId={editingId}
        onEdit={handleEdit}
        refreshToken={refreshToken}
        clusters={clusters}
        onPublished={publishNotice}
      />
    </div>
  );
}

function Banner({ color, bg, border, text }) {
  return <div style={{ color, backgroundColor: bg, border: `1px solid ${border}`, borderRadius: 12, padding: '0.8rem 1rem', fontSize: '0.88rem' }}>{text}</div>;
}
