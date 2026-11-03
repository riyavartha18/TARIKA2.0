import React, { memo } from 'react';
import { Loader2, Users, Ticket, CheckCircle2 } from 'lucide-react';
import { PALETTE } from './offerCatalog';

const formatStamp = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
};

/**
 * The four K-Means customer groups, always visible on the Campaign page.
 *
 * Everything here is read from the persisted clustering run through the API: the
 * business label each cluster carries (never assumed from its numeric id), how
 * many customers are actually assigned to it, how many coupons this run's
 * campaigns have issued into it, how many of those were redeemed, and which
 * campaigns are live for it right now. Clicking a group selects it for the
 * campaign being authored, so the admin sees the audience before publishing.
 */
function CustomerGroupPanel({
  clusters = [], loading = false, error = null, run = null,
  selected = [], onToggle,
}) {
  return (
    <div style={{ backgroundColor: PALETTE.bg, border: `1px solid ${PALETTE.border}`, borderRadius: 16, padding: '1.1rem 1.2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: 0, fontFamily: "'Playfair Display', serif", fontSize: '1.2rem', color: PALETTE.ink }}>
            Customer Groups (K-Means clusters)
          </h3>
          <p style={{ margin: '0.25rem 0 0', color: PALETTE.muted, fontSize: '0.82rem' }}>
            {run
              ? `Counts come from clustering run #${run.run_id} (RFM v${run.rfm_version}${formatStamp(run.completed_at) ? `, ${formatStamp(run.completed_at)}` : ''}). Click a group to include it in the campaign audience.`
              : 'Choose exactly which groups a personalised coupon is issued to.'}
          </p>
        </div>
        {selected.length > 0 && (
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: PALETTE.roseDeep }}>
            {selected.length} group{selected.length === 1 ? '' : 's'} selected for this campaign
          </span>
        )}
      </div>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: PALETTE.faint, fontSize: '0.84rem', padding: '1.2rem 0' }}>
          <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite' }} /> Loading the customer groups…
        </div>
      ) : error ? (
        <div style={{ color: '#B3261E', backgroundColor: '#FDECEA', border: '1px solid #F5C6C0', borderRadius: 10, padding: '0.65rem 0.8rem', fontSize: '0.82rem', marginTop: '0.8rem' }}>
          {error}
        </div>
      ) : clusters.length === 0 ? (
        <p style={{ color: PALETTE.faint, fontSize: '0.84rem', marginTop: '0.8rem' }}>
          No K-Means clustering has been persisted yet, so there are no groups to target.
        </p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 10, marginTop: '0.9rem' }}>
          {clusters.map((group) => (
            <GroupCard key={group.cluster_id} group={group}
              active={selected.includes(group.cluster_id)} onToggle={() => onToggle(group.cluster_id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function GroupCard({ group, active, onToggle }) {
  const campaigns = group.campaigns || [];
  const live = campaigns.filter((c) => c.is_live);
  const status = live.length
    ? `${live.length} active coupon offer${live.length === 1 ? '' : 's'}`
    : campaigns.length
      ? `${campaigns.length} campaign${campaigns.length === 1 ? '' : 's'}, none live`
      : 'No campaign yet';
  return (
    <button type="button" onClick={onToggle} aria-pressed={active} style={{
      textAlign: 'left', cursor: 'pointer', borderRadius: 14, padding: '0.85rem 0.9rem',
      border: `1.5px solid ${active ? PALETTE.roseDeep : PALETTE.border}`,
      background: active ? 'rgba(216,114,126,0.10)' : '#fff',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontWeight: 800, fontSize: '0.92rem', color: active ? PALETTE.roseDeep : PALETTE.ink }}>
          {group.category || `Cluster ${group.cluster_id}`}
        </span>
        <span style={{ fontSize: '0.66rem', color: PALETTE.faint }}>#{group.cluster_id}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: PALETTE.muted }}>
        <Users size={13} color={PALETTE.rose} />
        {Number(group.customer_count || 0).toLocaleString('en-IN')} eligible customers
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: PALETTE.muted }}>
        <Ticket size={13} color={PALETTE.rose} />
        {Number(group.coupons_assigned || 0).toLocaleString('en-IN')} coupons assigned
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: PALETTE.muted }}>
        <CheckCircle2 size={13} color={PALETTE.rose} />
        {Number(group.coupons_redeemed || 0).toLocaleString('en-IN')} redeemed
      </div>

      <div style={{ borderTop: `1px solid ${PALETTE.border}`, paddingTop: 6, fontSize: '0.72rem', color: active ? PALETTE.roseDeep : PALETTE.faint }}>
        {status}
        {live.length > 0 && (
          <div style={{ marginTop: 2, color: PALETTE.muted }}>
            {live.map((c) => <span key={c.campaign_id}>{c.name} ({c.coupon_code}){'\u2009'}</span>)}
          </div>
        )}
      </div>
      <div style={{ fontSize: '0.7rem', fontWeight: 700, color: active ? PALETTE.roseDeep : PALETTE.faint }}>
        {active ? 'Selected — click to remove' : 'Click to select for this campaign'}
      </div>
    </button>
  );
}

export default memo(CustomerGroupPanel);
