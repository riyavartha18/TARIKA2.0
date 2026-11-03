import React, { useCallback, useEffect, useState } from 'react';
import {
  Loader2, Search, Pencil, Send, Pause, Play, Eye, CalendarX2, Trash2, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { getCampaigns, getCampaignDetail, setCampaignStatus, deleteCampaign } from '../../../services/api';
import {
  PALETTE, STATUS_COLORS, statusLabel, OFFER_CATEGORY_LABELS, effectiveStatus,
  audienceGroups, isLegacyAudience,
} from './offerCatalog';

const PAGE_SIZE = 10;
const selectStyle = {
  border: `1px solid ${PALETTE.border}`, borderRadius: 9, padding: '0.45rem 0.6rem',
  fontSize: '0.8rem', color: PALETTE.ink, backgroundColor: '#fff', cursor: 'pointer',
};

/**
 * The campaign table. Every row states the customer groups it is aimed at (the
 * four K-Means clusters for a new campaign, the old rule-based segments for a
 * historical one, clearly labelled), its coupon figures from the persisted
 * assignments and redemptions, and its status.
 */
export default function CampaignList({
  token, editingId, onEdit, refreshToken, clusters = [], onPublished,
}) {
  const [campaigns, setCampaigns] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [groupFilter, setGroupFilter] = useState('ALL');
  const [offerFilter, setOfferFilter] = useState('ALL');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [detail, setDetail] = useState(null); // loaded campaign for the modal
  const [detailLoading, setDetailLoading] = useState(false);
  const [legacyAudience, setLegacyAudience] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await getCampaigns(token, {
      status: statusFilter, cluster: groupFilter, offer_type: offerFilter,
      search, page, page_size: PAGE_SIZE,
    });
    if (res.success) {
      setCampaigns(res.campaigns);
      setTotal(res.count);
      setTotalPages(res.totalPages);
      setPage(res.currentPage);
      setLegacyAudience(res.legacyAudience || null);
    }
    setLoading(false);
  }, [token, statusFilter, groupFilter, offerFilter, search, page]);

  useEffect(() => { load(); }, [load, refreshToken]);

  // Debounce the free-text search so typing does not spam the API.
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput.trim()); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const changeStatus = async (c, newStatus) => {
    const status = effectiveStatus(c);
    const groups = audienceGroups(c).join(', ') || 'no group yet';
    const messages = {
      PAUSED: `Deactivate "${c.name}"? Customers can no longer claim or redeem its coupon at checkout, but every issued coupon and redemption record is kept.`,
      EXPIRED: `Expire "${c.name}"? It will end early and no customer can use it any more.`,
      PUBLISHED: status === 'PAUSED'
        ? `Reactivate "${c.name}"? Its dates, offer rules and eligibility are re-checked first, and it goes back to exactly the customers its coupons were already issued to.`
        : `Publish "${c.name}"? Its coupon will be issued to the customers of: ${groups}.`,
      DRAFT: `Move "${c.name}" back to draft? It will be hidden from all customers.`,
    };
    if (newStatus !== 'DRAFT' && !window.confirm(messages[newStatus] || 'Change status?')) return;
    const res = await setCampaignStatus(token, c.campaign_id, newStatus);
    if (res.success) {
      await load();
      onEdit(null);
      if (newStatus === 'PUBLISHED' && onPublished) onPublished(res.audience, c);
    } else {
      window.alert(res.error || 'Could not change the campaign status.');
    }
  };

  const remove = async (c) => {
    if (!window.confirm(`Delete the draft "${c.name}"? Published campaigns cannot be deleted - their issued coupons and redemption history stay on record; deactivate them instead.`)) return;
    const res = await deleteCampaign(token, c.campaign_id);
    if (res.success) await load();
    else window.alert(res.error || 'Could not delete the campaign.');
  };

  const openDetail = async (c) => {
    setDetailLoading(true);
    setDetail({ campaign: c });
    const res = await getCampaignDetail(token, c.campaign_id);
    if (res.success) setDetail({ campaign: res.campaign });
    setDetailLoading(false);
  };

  const setFilter = (setter) => (value) => { setter(value); setPage(1); };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div>
        <h3 style={{ margin: 0, fontFamily: "'Playfair Display', serif", fontSize: '1.3rem', color: PALETTE.ink }}>Your Campaigns</h3>
        <p style={{ color: PALETTE.muted, margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
          {total} campaign{total === 1 ? '' : 's'}. Eligible-customer and coupon counts come from the latest
          completed K-Means clustering and the issued-coupon records.
        </p>
      </div>

      {/* Old rule-segment campaigns stay on record but no longer reach customers,
          because their segments are not the customer's K-Means group. */}
      {legacyAudience && legacyAudience.campaign_count > 0 && !legacyAudience.visible_to_customers && (
        <div style={{ backgroundColor: '#FFF8E7', border: '1px solid #F0DFAE', borderRadius: 12, padding: '0.7rem 0.9rem', fontSize: '0.8rem', color: '#7A5B12' }}>
          <strong>{legacyAudience.campaign_count} campaign{legacyAudience.campaign_count === 1 ? '' : 's'}</strong>
          {' '}still target the previous rule-based RFM segments, so customers are not shown
          those offers: a customer only ever sees the coupon of their own K-Means group.
          Nothing is deleted — the campaigns, their issued coupons and their redemption
          history are intact, and to serve such an offer again create a new campaign aimed
          at the matching customer groups.
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <label style={{ fontSize: '0.74rem', fontWeight: 700, color: PALETTE.muted }}>Status</label>
        <select style={selectStyle} value={statusFilter} onChange={(e) => setFilter(setStatusFilter)(e.target.value)}>
          <option value="ALL">All</option>
          <option value="ACTIVE">Active</option>
          <option value="DRAFT">Draft</option>
          <option value="PAUSED">Deactivated</option>
          <option value="EXPIRED">Expired</option>
        </select>
        <label style={{ fontSize: '0.74rem', fontWeight: 700, color: PALETTE.muted }}>Customer Group</label>
        <select style={selectStyle} value={groupFilter} onChange={(e) => setFilter(setGroupFilter)(e.target.value)}>
          <option value="ALL">All Groups</option>
          {clusters.map((c) => <option key={c.cluster_id} value={c.category}>{c.category}</option>)}
        </select>
        <label style={{ fontSize: '0.74rem', fontWeight: 700, color: PALETTE.muted }}>Offer</label>
        <select style={selectStyle} value={offerFilter} onChange={(e) => setFilter(setOfferFilter)(e.target.value)}>
          <option value="ALL">All Offers</option>
          <option value="DISCOUNT">Discount Offers</option>
          <option value="BUY_GET">Buy &amp; Get Offers</option>
          <option value="COMBINED">Combined Offers</option>
        </select>
        <div style={{ position: 'relative', marginLeft: 'auto', minWidth: 200, flex: '0 1 260px' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: PALETTE.faint }} />
          <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search name or coupon code…"
            style={{ ...selectStyle, width: '100%', boxSizing: 'border-box', cursor: 'auto', paddingLeft: 30 }} />
        </div>
      </div>

      {/* Table */}
      <div style={{ backgroundColor: PALETTE.bg, border: `1px solid ${PALETTE.border}`, borderRadius: 16, overflowX: 'auto' }}>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            <Loader2 size={16} style={{ animation: 'spin 0.8s linear infinite' }} /> Loading campaigns…
          </div>
        ) : campaigns.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: PALETTE.faint }}>
            No campaigns match these filters.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#FBF5F4' }}>
                {['Campaign', 'Offer Type', 'Offer Details', 'Target Customer Group', 'Validity', 'Status', 'Eligible Customers', 'Coupons (Issued / Redeemed / Left)', 'Actions'].map((h) => (
                  <th key={h} style={{ padding: '0.7rem 0.8rem', textAlign: 'left', color: PALETTE.muted, fontWeight: 700, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => {
                const status = effectiveStatus(c);
                return (
                  <tr key={c.campaign_id} style={{ borderTop: `1px solid ${PALETTE.border}`, backgroundColor: c.campaign_id === editingId ? '#FDF7F6' : undefined }}>
                    <td style={{ padding: '0.7rem 0.8rem' }}>
                      <div style={{ color: PALETTE.ink, fontWeight: 600 }}>{c.name}</div>
                      <code style={{ backgroundColor: '#F7EFEE', padding: '2px 6px', borderRadius: 6, fontSize: '0.72rem' }}>{c.coupon_code}</code>
                    </td>
                    <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.muted }}>{OFFER_CATEGORY_LABELS[c.offer_category] || 'Discount Offer'}</td>
                    <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.ink, maxWidth: 260 }}>
                      {c.offer_summary || '—'}
                      {c.offer_category === 'COMBINED' && (
                        <div style={{ fontSize: '0.7rem', color: PALETTE.faint }}>
                          {c.benefits_combinable ? 'Both benefits stack' : 'Better benefit only'}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '0.7rem 0.8rem' }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {audienceGroups(c).map((g) => (
                          <span key={g} style={{ background: 'rgba(216,114,126,0.12)', color: PALETTE.roseDeep, borderRadius: 12, padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700 }}>{g}</span>
                        ))}
                        {audienceGroups(c).length === 0 && (
                          <span style={{ fontSize: '0.72rem', color: PALETTE.faint }}>None selected</span>
                        )}
                      </div>
                      {isLegacyAudience(c) ? (
                        <div style={{ fontSize: '0.68rem', color: '#7A5B12', marginTop: 2 }}>
                          Previous RFM segmentation
                        </div>
                      ) : (
                        <div style={{ fontSize: '0.68rem', color: PALETTE.faint, marginTop: 2 }}>
                          K-Means run #{c.clustering_run_id ?? '—'}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.faint, fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                      {new Date(c.start_date).toLocaleDateString()} → {new Date(c.end_date).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '0.7rem 0.8rem' }}>
                      <span style={{ color: STATUS_COLORS[status] || PALETTE.muted, fontWeight: 700, fontSize: '0.75rem' }}>{statusLabel(status)}</span>
                    </td>
                    <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.ink, whiteSpace: 'nowrap' }}>
                      {c.eligible_audience_count == null ? 'Run clustering first' : c.eligible_audience_count.toLocaleString('en-IN')}
                    </td>
                    <td style={{ padding: '0.7rem 0.8rem', color: PALETTE.ink, whiteSpace: 'nowrap', fontSize: '0.78rem' }}>
                      {(c.coupons_issued ?? 0).toLocaleString('en-IN')} / {(c.coupons_redeemed ?? 0).toLocaleString('en-IN')} / {(c.coupons_remaining ?? 0).toLocaleString('en-IN')}
                    </td>
                    <td style={{ padding: '0.7rem 0.5rem', whiteSpace: 'nowrap' }}>
                      <IconBtn title="View details" onClick={() => openDetail(c)}><Eye size={15} /></IconBtn>
                      <IconBtn title="Edit" onClick={() => onEdit(c)}><Pencil size={15} /></IconBtn>
                      {c.status === 'PUBLISHED' ? (
                        <IconBtn title="Deactivate campaign" onClick={() => changeStatus(c, 'PAUSED')}><Pause size={15} /></IconBtn>
                      ) : (
                        <IconBtn title={status === 'EXPIRED' ? 'Publish (dates ended)' : 'Activate / Reactivate'} onClick={() => changeStatus(c, 'PUBLISHED')}><Play size={15} /></IconBtn>
                      )}
                      {c.status !== 'EXPIRED' && status !== 'EXPIRED' && (
                        <IconBtn title="Expire campaign now" onClick={() => changeStatus(c, 'EXPIRED')}><CalendarX2 size={15} /></IconBtn>
                      )}
                      {c.status === 'DRAFT' && (
                        <>
                          <IconBtn title="Publish" onClick={() => changeStatus(c, 'PUBLISHED')}><Send size={15} /></IconBtn>
                          <IconBtn title="Delete draft" danger onClick={() => remove(c)}><Trash2 size={15} /></IconBtn>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, fontSize: '0.8rem', color: PALETTE.muted }}>
          <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
            style={{ ...selectStyle, opacity: page <= 1 ? 0.4 : 1, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <ChevronLeft size={14} /> Previous
          </button>
          <span>Page {page} of {totalPages}</span>
          <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}
            style={{ ...selectStyle, opacity: page >= totalPages ? 0.4 : 1, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}

      {detail && (
        <DetailModal campaign={detail.campaign} loading={detailLoading} onClose={() => setDetail(null)} />
      )}
    </div>
  );
}

function DetailModal({ campaign, loading, onClose }) {
  const c = campaign;
  const row = (label, value) => (
    <div style={{ display: 'flex', gap: 10, fontSize: '0.84rem', marginBottom: 6 }}>
      <span style={{ color: PALETTE.muted, minWidth: 160 }}>{label}</span>
      <span style={{ color: PALETTE.ink, fontWeight: 600 }}>{value ?? '—'}</span>
    </div>
  );
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(31,25,27,0.45)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: '#fff', borderRadius: 18, padding: '1.4rem', maxWidth: 560, width: '100%',
        maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(31,25,27,0.25)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.9rem' }}>
          <h4 style={{ margin: 0, fontSize: '1.05rem', color: PALETTE.ink }}>{c.name}</h4>
          <button type="button" onClick={onClose} style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 8, padding: '0.25rem 0.6rem', cursor: 'pointer', color: PALETTE.muted }}>Close</button>
        </div>
        {loading ? (
          <div style={{ color: PALETTE.faint, fontSize: '0.85rem' }}>Loading details…</div>
        ) : (
          <>
            {row('Coupon code', c.coupon_code)}
            {row('Offer type', OFFER_CATEGORY_LABELS[c.offer_category])}
            {row('Offer details', c.offer_summary)}
            {row('Target customer group', audienceGroups(c).join(', ') || '—')}
            {row('Segmentation used', isLegacyAudience(c)
              ? 'Previous rule-based RFM segments (historical)'
              : `K-Means clusters${c.clustering_run ? ` (run #${c.clustering_run.run_id}, RFM v${c.clustering_run.rfm_version}, completed ${c.clustering_run.completed_at ? new Date(c.clustering_run.completed_at).toLocaleString() : '—'})` : ''}`)}
            {(c.audience_clusters || []).map((g) => row(
              `   Cluster #${g.cluster_id}`,
              `${g.category} — ${Number(g.eligible_customers || 0).toLocaleString('en-IN')} eligible, ${Number(g.coupons_issued || 0).toLocaleString('en-IN')} issued`,
            ))}
            {row('Eligible customers', c.eligible_audience_count == null ? 'Run clustering first' : c.eligible_audience_count.toLocaleString('en-IN'))}
            {row('Coupons issued', (c.coupons_issued ?? 0).toLocaleString('en-IN'))}
            {row('Coupons redeemed', (c.coupons_redeemed ?? c.redemption_count ?? 0).toLocaleString('en-IN'))}
            {row('Coupons still valid', (c.coupons_remaining ?? 0).toLocaleString('en-IN'))}
            {row('Total redemptions', c.redemption_count)}
            {row('Minimum order', c.min_order_amount ? `₹${Number(c.min_order_amount).toLocaleString('en-IN')}` : 'None')}
            {row('Maximum discount', c.max_discount ? `₹${Number(c.max_discount).toLocaleString('en-IN')}` : 'None')}
            {row('Usage limit', `${c.usage_type}${c.usage_type === 'LIMITED' ? ` (${c.per_customer_limit} per customer)` : ''}`)}
            {row('Global usage limit', c.global_usage_limit || 'Unlimited')}
            {row('Validity', `${new Date(c.start_date).toLocaleString()} → ${new Date(c.end_date).toLocaleString()}`)}
            {row('Status', statusLabel(effectiveStatus(c)))}
            {c.description && row('Description', c.description)}
          </>
        )}
      </div>
    </div>
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
