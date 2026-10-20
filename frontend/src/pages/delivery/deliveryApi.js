const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function getAuthHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

/**
 * Fetch delivery partner dashboard metrics and profile summary.
 */
export async function fetchDeliveryDashboard(token) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/delivery/dashboard/`, {
      method: 'GET',
      headers: getAuthHeaders(token),
    });

    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to fetch dashboard metrics.' };
    }
    return { success: true, data };
  } catch (err) {
    console.error(err);
    return { success: false, error: 'Network error fetching dashboard metrics.' };
  }
}

/**
 * Fetch deliveries assigned to authenticated delivery employee.
 */
export async function fetchMyDeliveries(token, { status = '', search = '', page = 1 } = {}) {
  try {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.append('status', status);
    if (search && search.trim()) params.append('search', search.trim());
    if (page && page > 1) params.append('page', page);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE_URL}/api/delivery/my-deliveries/${queryString}`, {
      method: 'GET',
      headers: getAuthHeaders(token),
    });

    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to fetch deliveries.' };
    }

    // Handles both paginated { count, results } and plain array response
    const results = Array.isArray(data) ? data : (data.results || []);
    const count = Array.isArray(data) ? data.length : (data.count || results.length);
    const hasNext = Boolean(data.next);
    const hasPrev = Boolean(data.previous);

    return {
      success: true,
      deliveries: results,
      count,
      hasNext,
      hasPrev,
    };
  } catch (err) {
    console.error(err);
    return { success: false, error: 'Network error fetching deliveries.' };
  }
}

/**
 * Fetch detailed view for a single delivery.
 */
export async function fetchDeliveryDetail(token, deliveryId) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/delivery/deliveries/${deliveryId}/`, {
      method: 'GET',
      headers: getAuthHeaders(token),
    });

    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to fetch delivery details.' };
    }
    return { success: true, delivery: data };
  } catch (err) {
    console.error(err);
    return { success: false, error: 'Network error fetching delivery details.' };
  }
}

/**
 * Update the status of an assigned delivery.
 * Lifecycle: Assigned -> Picked Up -> In Transit -> Delivered (or Delayed / Failed).
 */
export async function updateDeliveryStatus(token, deliveryId, { status, reason = '' }) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/delivery/deliveries/${deliveryId}/status/`, {
      method: 'PATCH',
      headers: getAuthHeaders(token),
      body: JSON.stringify({ status, reason }),
    });

    const data = await res.json();
    if (!res.ok) {
      const err = data.detail || data.status?.[0] || 'Failed to update delivery status.';
      return { success: false, error: err };
    }
    return { success: true, message: data.message, delivery: data.delivery };
  } catch (err) {
    console.error(err);
    return { success: false, error: 'Network error updating delivery status.' };
  }
}

/**
 * Fetch return pickups assigned to authenticated delivery employee.
 */
export async function fetchMyReturnPickups(token, { status = '', search = '', page = 1 } = {}) {
  try {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.append('status', status);
    if (search && search.trim()) params.append('search', search.trim());
    if (page && page > 1) params.append('page', page);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE_URL}/api/delivery/return-pickups/${queryString}`, {
      method: 'GET',
      headers: getAuthHeaders(token),
    });

    const data = await res.json();
    if (!res.ok) {
      return { success: false, error: data.detail || 'Failed to fetch return pickups.' };
    }

    const results = Array.isArray(data) ? data : (data.results || []);
    const count = Array.isArray(data) ? data.length : (data.count || results.length);
    const hasNext = Boolean(data.next);
    const hasPrev = Boolean(data.previous);

    return {
      success: true,
      returnPickups: results,
      count,
      hasNext,
      hasPrev,
    };
  } catch (err) {
    console.error(err);
    return { success: false, error: 'Network error fetching return pickups.' };
  }
}

/**
 * Update the status of an assigned return pickup.
 * Lifecycle: Pickup Assigned -> Pickup Accepted -> Picked Up -> Received at Warehouse (or Failed).
 */
export async function updateReturnPickupStatus(token, returnId, { status, reason = '' }) {
  try {
    const res = await fetch(`${API_BASE_URL}/api/delivery/return-pickups/${returnId}/status/`, {
      method: 'PATCH',
      headers: getAuthHeaders(token),
      body: JSON.stringify({ status, reason }),
    });

    const data = await res.json();
    if (!res.ok) {
      const err = data.detail || data.status?.[0] || 'Failed to update return pickup status.';
      return { success: false, error: err };
    }
    return { success: true, message: data.message, return: data.return };
  } catch (err) {
    console.error(err);
    return { success: false, error: 'Network error updating return pickup status.' };
  }
}
