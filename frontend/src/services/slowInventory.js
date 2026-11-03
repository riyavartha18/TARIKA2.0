// Slow‑Moving / Inventory‑Velocity API helper
// Provides getSlowMovingInventory used by the admin analytics view.
// The heavy per-product metrics are aggregated once on the server and cached;
// every search / filter / sort / page change is an indexed server-side read, so
// the WHOLE catalog is analysed (no 50-product cap, no silent truncation).

import { API_BASE_URL } from './api'; // Re‑use the base URL constant defined in api.js

export async function getSlowMovingInventory(token, {
  page = 1,
  page_size = 50,
  search = '',
  category = 'ALL',
  movement_status = 'ALL',
  sort = 'days_of_stock',
  refresh = false,
} = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    query.append('page', page);
    query.append('page_size', page_size);
    if (search) query.append('search', search);
    if (category && category !== 'ALL') query.append('category', category);
    if (movement_status && movement_status !== 'ALL') query.append('movement_status', movement_status);
    if (sort) query.append('sort', sort);
    if (refresh) query.append('refresh', '1');
    const qs = query.toString();
    const url = `${API_BASE_URL}/api/demand-prediction/slow-inventory/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch inventory velocity data.' };
    }
    // Preserve the full response structure from the backend
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching inventory velocity data.' };
  }
}
