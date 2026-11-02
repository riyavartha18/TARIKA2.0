// Slow‑Moving Inventory API helper
// This file provides the missing getSlowMovingInventory function used by the admin analytics view.
// It follows the same authentication and error‑handling conventions as the other admin helpers.

import { API_BASE_URL } from './api'; // Re‑use the base URL constant defined in api.js

export async function getSlowMovingInventory(token, { limit = 50, offset = 0 } = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    query.append('limit', limit);
    query.append('offset', offset);
    const qs = query.toString();
    const url = `${API_BASE_URL}/api/demand-prediction/slow-inventory/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch slow‑moving inventory data.' };
    }
    // Preserve the full response structure from the backend
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching slow‑moving inventory data.' };
  }
}

