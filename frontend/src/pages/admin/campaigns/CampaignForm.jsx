import React, { useEffect, useState } from 'react';
import {
  Loader2, ChevronLeft, ChevronRight, Eye, Tag, Percent,
  Users, CalendarDays, ShieldCheck,
} from 'lucide-react';
import { getCategories } from '../../../services/api';
import ProductPicker from './ProductPicker';
import {
  PALETTE, SEGMENTS, DISCOUNT_OPTIONS, BUY_GET_OPTIONS,
  emptyForm, buildPayload, previewSummary, buyGetRuleText,
} from './offerCatalog';

const STEPS = [
  { key: 'basic', label: 'Basic Info', icon: Tag },
  { key: 'offer', label: 'Choose Your Offer', icon: Percent },
  { key: 'customers', label: 'Choose Your Customers', icon: Users },
  { key: 'conditions', label: 'Conditions & Limits', icon: ShieldCheck },
  { key: 'validity', label: 'Campaign Validity', icon: CalendarDays },
  { key: 'preview', label: 'Preview & Publish', icon: Eye },
];

const labelStyle = { fontSize: '0.76rem', fontWeight: 700, color: PALETTE.muted, display: 'block', marginBottom: 4 };
const inputStyle = { width: '100%', boxSizing: 'border-box', border: `1px solid ${PALETTE.border}`, borderRadius: 9, padding: '0.5rem 0.6rem', fontSize: '0.85rem', color: PALETTE.ink, backgroundColor: '#fff' };
const hintStyle = { fontSize: '0.74rem', color: PALETTE.faint, margin: '4px 0 0' };

export default function CampaignForm({ editingId, initialForm, saving, onSubmit }) {
  const [form, setForm] = useState(initialForm || emptyForm());
  const [step, setStep] = useState(0);
  const [localError, setLocalError] = useState(null);
  const [categories, setCategories] = useState([]);

  useEffect(() => { setForm(initialForm || emptyForm()); setStep(0); }, [initialForm]);

  useEffect(() => {
    let alive = true;
    getCategories().then((res) => {
      if (alive && res.success) setCategories(res.categories.map((c) => c.category_name).filter(Boolean));
    });
    return () => { alive = false; };
  }, []);

  const set = (key, value) => { setForm((f) => ({ ...f, [key]: value })); setLocalError(null); };
  const toggleSegment = (s) => set('target_segments',
    form.target_segments.includes(s)
      ? form.target_segments.filter((x) => x !== s)
      : [...form.target_segments, s]);
  const toggleCategory = (c) => set('scope_categories',
    form.scope_categories.includes(c)
      ? form.scope_categories.filter((x) => x !== c)
      : [...form.scope_categories, c]);

  const showDiscount = form.offer_category !== 'BUY_GET';
  const showBuyGet = form.offer_category !== 'DISCOUNT';
  // The bundle deal and the product-based offer only make sense on chosen
  // products, so the product picker lives right inside their panels.
  const bundleActive = showBuyGet && form.buy_get_type === 'BUNDLE';
  const productOfferActive = showBuyGet && form.buy_get_type === 'PRODUCT_DISCOUNT';

  const stepReady = (index) => {
    if (index === 0) return form.name.trim() && form.coupon_code.trim();
    if (index === 1) {
      if (bundleActive && !form.scope_products.length) return false;
      if (form.offer_category !== 'BUY_GET' && form.discount_type === 'BUY_MORE_SAVE_MORE'
          && !(form.tiers || []).some((t) => Number(t.buy) >= 2 && Number(t.percent) > 0)) return false;
      if (showBuyGet && form.buy_get_type === 'FREE_GIFT' && !form.gift_name.trim()) return false;
      if (productOfferActive && form.scope_mode === 'PRODUCTS' && !form.scope_products.length) return false;
      if (showBuyGet && ['BUY_X_GET_Y_FREE', 'BUY_X_GET_Y_DISCOUNT'].includes(form.buy_get_type)
          && (!Number(form.buy_qty) || !Number(form.get_qty))) return false;
      return true;
    }
    if (index === 2) return form.target_segments.length > 0;
    if (index === 3) {
      if (form.usage_type === 'LIMITED' && !Number(form.per_customer_limit)) return false;
      if (form.scope_mode === 'PRODUCTS' && !bundleActive && !form.scope_products.length) return false;
      if (form.scope_mode === 'CATEGORIES' && !form.scope_categories.length) return false;
      return true;
    }
    if (index === 4) return Boolean(form.start_date && form.end_date);
    return true;
  };

  const goNext = () => {
    if (!stepReady(step)) {
      setLocalError(stepHintError(step));
      return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const submit = async (statusAction) => {
    if (!stepReady(0)) { setStep(0); setLocalError('Campaign name and coupon code are required.'); return; }
    if (!form.target_segments.length) { setStep(2); setLocalError('Select at least one target segment - offers must never go to all customers.'); return; }
    if (!form.start_date || !form.end_date) { setStep(4); setLocalError('Pick the campaign start and end dates.'); return; }
    await onSubmit(buildPayload(form), statusAction);
  };

  const preview = previewSummary(form);

  return (
    <div style={{ backgroundColor: PALETTE.bg, border: `1px solid ${PALETTE.border}`, borderRadius: 16, padding: '1.3rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.9rem' }}>
        <h3 style={{ margin: 0, fontSize: '1.05rem', color: PALETTE.ink }}>
          {editingId ? `Edit campaign #${editingId}` : 'Create a campaign'}
        </h3>
        <span style={{ fontSize: '0.76rem', color: PALETTE.faint }}>Step {step + 1} of {STEPS.length}</span>
      </div>

      {/* Step tabs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: '1.1rem' }}>
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const state = i === step ? 'current' : i < step ? 'done' : 'todo';
          return (
            <button key={s.key} type="button" onClick={() => i <= step && setStep(i)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, cursor: i <= step ? 'pointer' : 'default',
                border: `1px solid ${state === 'current' ? PALETTE.roseDeep : PALETTE.border}`,
                background: state === 'current' ? 'rgba(216,114,126,0.14)' : state === 'done' ? '#FDF7F6' : '#fff',
                color: state === 'todo' ? PALETTE.faint : PALETTE.roseDeep,
                borderRadius: 20, padding: '0.3rem 0.7rem', fontSize: '0.74rem', fontWeight: 700,
              }}>
              <Icon size={13} />{s.label}
            </button>
          );
        })}
      </div>

      {localError && (
        <div style={{ color: '#B3261E', backgroundColor: '#FDECEA', border: '1px solid #F5C6C0', borderRadius: 10, padding: '0.6rem 0.8rem', fontSize: '0.82rem', marginBottom: '0.9rem' }}>
          {localError}
        </div>
      )}

      {/* Step 1 — Basic information */}
      {step === 0 && (
        <div style={{ display: 'grid', gap: '0.9rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          <div>
            <label style={labelStyle}>Campaign Name</label>
            <input style={inputStyle} value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Champions VIP Shopping Offer" />
          </div>
          <div>
            <label style={labelStyle}>Coupon Code</label>
            <input style={inputStyle} value={form.coupon_code} onChange={(e) => set('coupon_code', e.target.value.toUpperCase())} placeholder="VIP15" />
            <p style={hintStyle}>Customers type this code at checkout. Leave as-is if this campaign should not use a coupon you must announce.</p>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <label style={labelStyle}>Short Description</label>
            <textarea style={{ ...inputStyle, minHeight: 64, resize: 'vertical' }} value={form.description}
              onChange={(e) => set('description', e.target.value)} placeholder="A one-line thank-you offer for our best customers." />
          </div>
        </div>
      )}

      {/* Step 2 — Choose your offer */}
      {step === 1 && (
        <div style={{ display: 'grid', gap: '1.1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
            <OfferCategoryCard active={form.offer_category === 'DISCOUNT'} onClick={() => set('offer_category', 'DISCOUNT')}
              title="Discount Offers" note="Percentage, flat, spend-based, cashback…" />
            <OfferCategoryCard active={form.offer_category === 'BUY_GET'} onClick={() => set('offer_category', 'BUY_GET')}
              title="Buy & Get Offers" note="Buy X Get Y, BOGO, bundle, free gift…" />
            <OfferCategoryCard active={form.offer_category === 'COMBINED'} onClick={() => set('offer_category', 'COMBINED')}
              title="Both Together" note="One campaign, two benefits" />
          </div>

          {showDiscount && (
            <div>
              <label style={labelStyle}>Discount offer type</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 6 }}>
                {DISCOUNT_OPTIONS.map((o) => (
                  <TypeCard key={o.type} active={form.discount_type === o.type}
                    onClick={() => set('discount_type', o.type)} label={o.label} example={o.example} />
                ))}
              </div>
              <DiscountFields form={form} set={set} />
            </div>
          )}

          {showBuyGet && (
            <div>
              <label style={labelStyle}>Buy &amp; Get offer type</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 6 }}>
                {BUY_GET_OPTIONS.map((o) => (
                  <TypeCard key={o.type} active={form.buy_get_type === o.type}
                    onClick={() => set('buy_get_type', o.type)} label={o.label} example={o.example} />
                ))}
              </div>
              <BuyGetFields form={form} set={set} />
              {(bundleActive || productOfferActive) && (
                <div style={{ marginTop: '0.8rem' }}>
                  <label style={labelStyle}>{bundleActive ? 'Products in the bundle' : 'Applicable products'}</label>
                  {productOfferActive && (
                    <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                      {['ALL', 'PRODUCTS', 'CATEGORIES'].map((m) => (
                        <button key={m} type="button" onClick={() => set('scope_mode', m)} style={pill(form.scope_mode === m)}>
                          {m === 'ALL' ? 'All products' : m === 'PRODUCTS' ? 'Selected products' : 'Categories'}
                        </button>
                      ))}
                    </div>
                  )}
                  {(bundleActive || form.scope_mode === 'PRODUCTS') && (
                    <ProductPicker selected={form.scope_products} onChange={(ids) => set('scope_products', ids)} />
                  )}
                  {productOfferActive && form.scope_mode === 'CATEGORIES' && (
                    <CategoryChips categories={categories} selected={form.scope_categories} onToggle={toggleCategory} />
                  )}
                  {bundleActive && <p style={hintStyle}>A bundle needs at least two selected products.</p>}
                </div>
              )}
            </div>
          )}

          {form.offer_category === 'COMBINED' && (
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.84rem', color: PALETTE.ink }}>
              <input type="checkbox" checked={form.benefits_combinable}
                onChange={(e) => set('benefits_combinable', e.target.checked)} style={{ marginTop: 3 }} />
              <span>
                <strong>Combine both benefits at checkout.</strong>
                <br />
                <span style={{ color: PALETTE.muted, fontSize: '0.78rem' }}>
                  If unchecked, the customer gets whichever benefit is better for them (prevents accidental double discounts).
                </span>
              </span>
            </label>
          )}
        </div>
      )}

      {/* Step 3 — Choose your customers */}
      {step === 2 && (
        <div style={{ display: 'grid', gap: '1rem' }}>
          <div>
            <label style={labelStyle}>Target RFM segments (choose one or more) — required</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {SEGMENTS.map((s) => (
                <Chip key={s} active={form.target_segments.includes(s)} onClick={() => toggleSegment(s)} label={s} />
              ))}
            </div>
            <p style={hintStyle}>
              Only customers currently in the selected segments will see and be able to use this offer.
              Everyone else — including other segments — never receives it.
            </p>
          </div>
          <div>
            <label style={labelStyle}>Optional extra condition</label>
            <Chip active={form.big_spender_only} onClick={() => set('big_spender_only', !form.big_spender_only)}
              label="Big Spenders only" />
            <p style={hintStyle}>Narrows the chosen segments further; Big Spender is a tag, not a segment.</p>
          </div>
          {form.target_segments.length > 0 && (
            <div style={{ backgroundColor: '#FDF7F6', border: `1px solid ${PALETTE.border}`, borderRadius: 12, padding: '0.7rem 0.9rem', fontSize: '0.83rem', color: PALETTE.ink }}>
              This offer will reach: <strong>{form.target_segments.join(' + ')}</strong>
              {form.big_spender_only ? ' who are Big Spenders' : ''}.
            </div>
          )}
        </div>
      )}

      {/* Step 4 — Conditions & limits */}
      {step === 3 && (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {!bundleActive && !productOfferActive && (
            <div>
              <label style={labelStyle}>Applicable products</label>
              <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                {['ALL', 'PRODUCTS', 'CATEGORIES'].map((m) => (
                  <button key={m} type="button" onClick={() => set('scope_mode', m)} style={pill(form.scope_mode === m)}>
                    {m === 'ALL' ? 'All products' : m === 'PRODUCTS' ? 'Selected products' : 'Categories'}
                  </button>
                ))}
              </div>
              {form.scope_mode === 'PRODUCTS' && (
                <ProductPicker selected={form.scope_products} onChange={(ids) => set('scope_products', ids)} />
              )}
              {form.scope_mode === 'CATEGORIES' && (
                <CategoryChips categories={categories} selected={form.scope_categories} onToggle={toggleCategory} />
              )}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.9rem' }}>
            <div>
              <label style={labelStyle}>Minimum order value (₹)</label>
              <input style={inputStyle} type="number" min="0" step="0.01" value={form.min_order_amount}
                onChange={(e) => set('min_order_amount', e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Maximum discount (₹, optional)</label>
              <input style={inputStyle} type="number" min="0" step="0.01" value={form.max_discount}
                onChange={(e) => set('max_discount', e.target.value)} placeholder="e.g. 500" />
              <p style={hintStyle}>Caps percentage-based discounts. Leave empty for no cap.</p>
            </div>
            <div>
              <label style={labelStyle}>Per-customer usage</label>
              <select style={inputStyle} value={form.usage_type} onChange={(e) => set('usage_type', e.target.value)}>
                <option value="ONCE">Once per customer</option>
                <option value="LIMITED">Limited uses</option>
                <option value="UNLIMITED">Unlimited</option>
              </select>
            </div>
            {form.usage_type === 'LIMITED' && (
              <div>
                <label style={labelStyle}>Uses per customer</label>
                <input style={inputStyle} type="number" min="1" value={form.per_customer_limit}
                  onChange={(e) => set('per_customer_limit', e.target.value)} />
              </div>
            )}
            <div>
              <label style={labelStyle}>Global usage limit (0 = none)</label>
              <input style={inputStyle} type="number" min="0" value={form.global_usage_limit}
                onChange={(e) => set('global_usage_limit', e.target.value)} />
            </div>
          </div>
        </div>
      )}

      {/* Step 5 — Validity */}
      {step === 4 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.9rem' }}>
          <div>
            <label style={labelStyle}>Start date</label>
            <input style={inputStyle} type="datetime-local" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>End date</label>
            <input style={inputStyle} type="datetime-local" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} />
          </div>
          <p style={{ ...hintStyle, gridColumn: '1 / -1' }}>
            The offer appears to eligible customers only between these dates, and stops automatically after the end date.
          </p>
        </div>
      )}

      {/* Step 6 — Preview & publish */}
      {step === 5 && (
        <div>
          <div style={{ backgroundColor: '#FDF7F6', border: `1px solid ${PALETTE.rose}`, borderRadius: 14, padding: '1.1rem 1.2rem' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase', color: PALETTE.roseDeep, marginBottom: 8 }}>
              Campaign Preview
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 800, color: PALETTE.ink, marginBottom: 10 }}>{preview.name}</div>
            <PreviewRow label="Target customers" value={preview.audience} />
            <PreviewRow label="Offer" value={preview.offer} />
            <PreviewRow label="Applicable products" value={preview.products} />
            <PreviewRow label="Validity" value={preview.validity} />
            {form.min_order_amount > 0 && <PreviewRow label="Minimum order" value={`₹${Number(form.min_order_amount).toLocaleString('en-IN')}`} />}
            {form.max_discount !== '' && form.max_discount != null && <PreviewRow label="Maximum discount" value={`₹${Number(form.max_discount).toLocaleString('en-IN')}`} />}
            <PreviewRow label="Coupon code" value={form.coupon_code || '—'} />
          </div>
          <p style={hintStyle}>
            Publishing makes the offer visible immediately to the selected segments only. You can pause it any time from the campaign list.
          </p>
        </div>
      )}

      {/* Footer navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: '1.2rem' }}>
        {step > 0 && (
          <button type="button" onClick={() => setStep((s) => s - 1)}
            style={{ border: `1px solid ${PALETTE.border}`, background: '#fff', borderRadius: 9, padding: '0.45rem 0.8rem', cursor: 'pointer', fontSize: '0.82rem', color: PALETTE.muted, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <ChevronLeft size={15} /> Back
          </button>
        )}
        {step < STEPS.length - 1 ? (
          <button type="button" onClick={goNext}
            style={{ marginLeft: 'auto', border: 'none', background: PALETTE.roseDeep, color: '#fff', borderRadius: 10, padding: '0.55rem 1.2rem', fontWeight: 700, cursor: 'pointer', fontSize: '0.84rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Next <ChevronRight size={15} />
          </button>
        ) : (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            <button type="button" onClick={() => submit('DRAFT')} disabled={saving}
              style={{ border: `1px solid ${PALETTE.roseDeep}`, background: '#fff', color: PALETTE.roseDeep, borderRadius: 10, padding: '0.55rem 1.1rem', fontWeight: 700, cursor: 'pointer', fontSize: '0.84rem', opacity: saving ? 0.6 : 1 }}>
              {editingId ? 'Save changes' : 'Save as Draft'}
            </button>
            {!editingId && (
              <button type="button" onClick={() => submit('PUBLISHED')} disabled={saving}
                style={{ border: 'none', background: PALETTE.roseDeep, color: '#fff', borderRadius: 10, padding: '0.55rem 1.2rem', fontWeight: 700, cursor: 'pointer', fontSize: '0.84rem', display: 'inline-flex', alignItems: 'center', gap: 6, opacity: saving ? 0.6 : 1 }}>
                {saving && <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite' }} />}
                Publish Campaign
              </button>
            )}
            {editingId && saving && <Loader2 size={15} style={{ animation: 'spin 0.8s linear infinite', color: PALETTE.roseDeep }} />}
          </div>
        )}
      </div>
    </div>
  );
}

function stepHintError(step) {
  if (step === 0) return 'Campaign name and coupon code are required.';
  if (step === 1) return 'Please complete the offer details (bundle deals need at least two selected products).';
  if (step === 2) return 'Select at least one target segment - campaigns must never go to all customers.';
  if (step === 3) return 'Finish the conditions (usage limits and product selection).';
  if (step === 4) return 'Pick both the start and end dates.';
  return 'Please review the campaign.';
}

const pill = (active) => ({
  border: `1px solid ${active ? PALETTE.roseDeep : PALETTE.border}`,
  background: active ? 'rgba(216,114,126,0.14)' : '#fff',
  color: active ? PALETTE.roseDeep : PALETTE.muted,
  borderRadius: 20, padding: '0.32rem 0.75rem', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 600,
});

export function Chip({ active, onClick, label }) {
  return (
    <button type="button" onClick={onClick} style={pill(active)}>{label}</button>
  );
}

function OfferCategoryCard({ active, onClick, title, note }) {
  return (
    <button type="button" onClick={onClick} style={{
      textAlign: 'left', cursor: 'pointer', borderRadius: 12, padding: '0.8rem 0.9rem',
      border: `1.5px solid ${active ? PALETTE.roseDeep : PALETTE.border}`,
      background: active ? 'rgba(216,114,126,0.08)' : '#fff',
    }}>
      <div style={{ fontWeight: 800, fontSize: '0.88rem', color: active ? PALETTE.roseDeep : PALETTE.ink }}>{title}</div>
      <div style={{ fontSize: '0.75rem', color: PALETTE.muted, marginTop: 2 }}>{note}</div>
    </button>
  );
}

function TypeCard({ active, onClick, label, example }) {
  return (
    <button type="button" onClick={onClick} style={{
      textAlign: 'left', cursor: 'pointer', borderRadius: 10, padding: '0.55rem 0.7rem',
      border: `1px solid ${active ? PALETTE.roseDeep : PALETTE.border}`,
      background: active ? 'rgba(216,114,126,0.10)' : '#fff',
    }}>
      <div style={{ fontWeight: 700, fontSize: '0.8rem', color: active ? PALETTE.roseDeep : PALETTE.ink }}>{label}</div>
      <div style={{ fontSize: '0.7rem', color: PALETTE.faint, marginTop: 2 }}>{example}</div>
    </button>
  );
}

function CategoryChips({ categories, selected, onToggle }) {
  if (!categories.length) {
    return <p style={hintStyle}>Loading categories… (or pick “Selected products” instead)</p>;
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, maxHeight: 140, overflowY: 'auto' }}>
      {categories.map((c) => (
        <Chip key={c} active={selected.includes(c)} onClick={() => onToggle(c)} label={c} />
      ))}
    </div>
  );
}

function NumField({ label, value, onChange, min = 0, step = 1, hint }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input style={inputStyle} type="number" min={min} step={step} value={value} onChange={(e) => onChange(e.target.value)} />
      {hint && <p style={hintStyle}>{hint}</p>}
    </div>
  );
}

function DiscountFields({ form, set }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.8rem', marginTop: '0.8rem' }}>
      {form.discount_type === 'PERCENTAGE' && (
        <NumField label="Discount (%)" value={form.percent} onChange={(v) => set('percent', v)} min="1" step="0.5" hint="Cap it below with Maximum discount if needed." />
      )}
      {form.discount_type === 'FLAT' && (
        <NumField label="Discount amount (₹)" value={form.flat} onChange={(v) => set('flat', v)} min="1" />
      )}
      {form.discount_type === 'SPEND_BASED' && (
        <>
          <NumField label="Customer spends at least (₹)" value={form.spend_threshold} onChange={(v) => set('spend_threshold', v)} min="1" />
          <NumField label="They get OFF (₹)" value={form.spend_discount} onChange={(v) => set('spend_discount', v)} min="1" />
        </>
      )}
      {form.discount_type === 'CASHBACK' && (
        <NumField label="Cashback amount (₹)" value={form.cashback} onChange={(v) => set('cashback', v)} min="1"
          hint="Credited after purchase — it does not reduce the checkout total." />
      )}
      {form.discount_type === 'FREE_SHIPPING' && (
        <p style={{ ...hintStyle, gridColumn: '1 / -1' }}>No extra settings needed — delivery is free for eligible orders.</p>
      )}
      {form.discount_type === 'BUY_MORE_SAVE_MORE' && (
        <div style={{ gridColumn: '1 / -1' }}>
          <label style={labelStyle}>Tiers</label>
          {(form.tiers || []).map((t, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <input style={{ ...inputStyle, width: 90 }} type="number" min="2" value={t.buy}
                onChange={(e) => { const next = [...form.tiers]; next[i] = { ...t, buy: Number(e.target.value) }; set('tiers', next); }} />
              <span style={{ fontSize: '0.78rem', color: PALETTE.muted }}>buy</span>
              <input style={{ ...inputStyle, width: 90 }} type="number" min="1" max="100" value={t.percent}
                onChange={(e) => { const next = [...form.tiers]; next[i] = { ...t, percent: Number(e.target.value) }; set('tiers', next); }} />
              <span style={{ fontSize: '0.78rem', color: PALETTE.muted }}>% save</span>
              <button type="button" onClick={() => set('tiers', form.tiers.filter((_, j) => j !== i))}
                style={{ border: 'none', background: 'none', color: PALETTE.faint, cursor: 'pointer', fontSize: '0.8rem' }}>Remove</button>
            </div>
          ))}
          <button type="button" onClick={() => set('tiers', [...(form.tiers || []), { buy: (form.tiers?.length ? Number(form.tiers[form.tiers.length - 1].buy) + 1 : 2), percent: 15 }])}
            style={{ border: `1px dashed ${PALETTE.rose}`, background: 'none', color: PALETTE.roseDeep, borderRadius: 8, padding: '0.3rem 0.7rem', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700 }}>
            + Add tier
          </button>
        </div>
      )}
    </div>
  );
}

function BuyGetFields({ form, set }) {
  const needsQty = ['BUY_X_GET_Y_FREE', 'BUY_X_GET_Y_DISCOUNT'].includes(form.buy_get_type);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.8rem', marginTop: '0.8rem' }}>
      {needsQty && (
        <>
          <NumField label="Buy quantity" value={form.buy_qty} onChange={(v) => set('buy_qty', v)} min="1" />
          <NumField label="Get quantity" value={form.get_qty} onChange={(v) => set('get_qty', v)} min="1" />
          {form.buy_get_type === 'BUY_X_GET_Y_DISCOUNT' && (
            <NumField label="Discount on the “get” items (%)" value={form.get_discount_percent} onChange={(v) => set('get_discount_percent', v)} min="1" step="5" />
          )}
        </>
      )}
      {form.buy_get_type === 'BOGO' && (
        <p style={{ ...hintStyle, gridColumn: '1 / -1' }}>Buy 1, get 1 free — no extra settings needed.</p>
      )}
      {form.buy_get_type === 'BUNDLE' && (
        <NumField label="Bundle price (₹)" value={form.bundle_price} onChange={(v) => set('bundle_price', v)} min="1"
          hint="The customer pays this for the whole selected set." />
      )}
      {form.buy_get_type === 'FREE_GIFT' && (
        <>
          <div>
            <label style={labelStyle}>Gift name</label>
            <input style={inputStyle} value={form.gift_name} onChange={(e) => set('gift_name', e.target.value)} placeholder="Silk Scarf" />
          </div>
          <NumField label="Gift value (₹)" value={form.gift_value} onChange={(v) => set('gift_value', v)} min="0" />
          <NumField label="Free on orders above (₹)" value={form.gift_min_order} onChange={(v) => set('gift_min_order', v)} min="0" />
        </>
      )}
      {form.buy_get_type === 'PRODUCT_DISCOUNT' && (
        <>
          <div>
            <label style={labelStyle}>Offer style</label>
            <select style={inputStyle} value={form.product_offer_mode} onChange={(e) => set('product_offer_mode', e.target.value)}>
              <option value="PERCENTAGE">Percentage OFF</option>
              <option value="FLAT">Flat ₹ OFF per item</option>
            </select>
          </div>
          {form.product_offer_mode === 'PERCENTAGE' ? (
            <NumField label="Discount (%)" value={form.product_discount_percent} onChange={(v) => set('product_discount_percent', v)} min="1" max="100" />
          ) : (
            <NumField label="Discount per item (₹)" value={form.product_discount_flat} onChange={(v) => set('product_discount_flat', v)} min="1" />
          )}
        </>
      )}
      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '1rem', fontSize: '0.8rem', color: PALETTE.muted }}>
        <span>Offer: <strong style={{ color: PALETTE.roseDeep }}>{buyGetRuleText(form)}</strong></span>
      </div>
    </div>
  );
}

function PreviewRow({ label, value }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: '0.85rem', marginBottom: 4 }}>
      <span style={{ color: PALETTE.muted, minWidth: 150 }}>{label}:</span>
      <span style={{ color: PALETTE.ink, fontWeight: 600 }}>{value}</span>
    </div>
  );
}
