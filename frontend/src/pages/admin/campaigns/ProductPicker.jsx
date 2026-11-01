import React, { useEffect, useRef, useState } from 'react';
import { Search, X, Check } from 'lucide-react';
import { getProducts } from '../../../services/api';
import { PALETTE } from './offerCatalog';

/**
 * Simple searchable multi-select over the real catalog (products come from
 * /api/catalog/products/, nothing is hardcoded). Selected products are stored
 * by product id; names are kept only for display.
 */
export default function ProductPicker({ selected, onChange }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [names, setNames] = useState({}); // id -> name, for the chips
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (!query.trim()) { setResults([]); return; }
    timer.current = setTimeout(async () => {
      setLoading(true);
      const res = await getProducts({ search: query.trim(), page: 1 });
      setResults(res.success ? res.products : []);
      setLoading(false);
    }, 350);
    return () => clearTimeout(timer.current);
  }, [query]);

  // Remember names of pre-selected ids (editing an existing campaign).
  useEffect(() => {
    const unknown = (selected || []).filter((id) => !names[id]);
    if (!unknown.length) return;
    (async () => {
      const found = { ...names };
      for (const id of unknown.slice(0, 10)) {
        const res = await getProducts({ search: String(id), page: 1 });
        if (res.success) {
          const match = res.products.find((p) => String(p.product_id) === String(id));
          if (match) found[id] = match.product_name || String(id);
        }
      }
      setNames(found);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const add = (p) => {
    const id = String(p.product_id);
    setNames((n) => ({ ...n, [id]: p.product_name || id }));
    if (!(selected || []).includes(id)) onChange([...(selected || []), id]);
  };

  const remove = (id) => onChange((selected || []).filter((x) => x !== id));

  const inputStyle = {
    width: '100%', boxSizing: 'border-box', border: `1px solid ${PALETTE.border}`,
    borderRadius: 9, padding: '0.5rem 0.6rem', fontSize: '0.85rem', color: PALETTE.ink,
  };

  return (
    <div>
      <div style={{ position: 'relative' }}>
        <Search size={14} style={{ position: 'absolute', left: 10, top: 11, color: PALETTE.faint }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search products by name…"
          style={{ ...inputStyle, paddingLeft: 30 }}
        />
      </div>

      {(selected || []).length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '0.6rem 0' }}>
          {selected.map((id) => (
            <span key={id} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: 'rgba(216,114,126,0.12)', color: PALETTE.roseDeep,
              border: `1px solid ${PALETTE.rose}`, borderRadius: 16,
              padding: '0.22rem 0.4rem 0.22rem 0.65rem', fontSize: '0.76rem', fontWeight: 600,
              maxWidth: 230,
            }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {names[id] || id}
              </span>
              <button type="button" onClick={() => remove(id)}
                style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 2, color: PALETTE.roseDeep, display: 'inline-flex' }}>
                <X size={13} />
              </button>
            </span>
          ))}
        </div>
      )}

      {loading && <div style={{ fontSize: '0.78rem', color: PALETTE.faint, marginTop: 6 }}>Searching…</div>}
      {!loading && results.length > 0 && (
        <div style={{
          maxHeight: 180, overflowY: 'auto', border: `1px solid ${PALETTE.border}`,
          borderRadius: 10, marginTop: 6, backgroundColor: '#fff',
        }}>
          {results.map((p) => {
            const chosen = (selected || []).includes(String(p.product_id));
            return (
              <button key={p.product_id} type="button" onClick={() => add(p)}
                style={{
                  display: 'flex', width: '100%', alignItems: 'center', gap: 8,
                  border: 'none', borderBottom: `1px solid ${PALETTE.border}`,
                  background: chosen ? 'rgba(216,114,126,0.07)' : '#fff',
                  padding: '0.5rem 0.7rem', cursor: 'pointer', textAlign: 'left', fontSize: '0.82rem',
                  color: PALETTE.ink,
                }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.product_name}
                  {p.main_category ? (
                    <span style={{ color: PALETTE.faint, fontSize: '0.72rem', marginLeft: 6 }}>{p.main_category}</span>
                  ) : null}
                </span>
                {p.selling_price != null && (
                  <span style={{ color: PALETTE.muted, fontSize: '0.76rem' }}>
                    ₹{Number(p.selling_price).toLocaleString('en-IN')}
                  </span>
                )}
                {chosen && <Check size={14} color={PALETTE.roseDeep} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
