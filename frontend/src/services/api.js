export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Universal Login for all user types: Customer, Admin, Warehouse Manager, Delivery Partner.
 * The backend automatically determines the user's role.
 */
export async function loginUser(email, password) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      const errorMsg = data.detail || 
                       data.non_field_errors?.[0] || 
                       data.email?.[0] || 
                       data.password?.[0] || 
                       'Invalid email or password. Please try again.';
      return { success: false, error: errorMsg, status: response.status };
    }

    return {
      success: true,
      user: data.user,
      tokens: data.tokens,
      role: data.user?.role,
      warehouseId: data.user?.warehouse_id,
    };
  } catch (err) {
    return {
      success: false,
      error: 'Unable to connect to the backend server. Please make sure the Django server is running.',
      status: 0,
    };
  }
}

/**
 * Public Customer Registration.
 * Strictly assigns role CUSTOMER (no role is ever sent from the frontend).
 */
export async function registerCustomer({ fullName, email, gender, password }) {
  try {
    const payload = {
      full_name: fullName.trim(),
      email: email.trim(),
      password,
    };

    if (gender) payload.gender = gender.trim();

    const response = await fetch(`${API_BASE_URL}/api/auth/register/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      let errorMsg = 'Registration failed. Please check your information.';
      if (data.email) {
        errorMsg = Array.isArray(data.email) ? data.email[0] : data.email;
      } else if (data.password) {
        errorMsg = Array.isArray(data.password) ? data.password[0] : data.password;
      } else if (data.full_name) {
        errorMsg = Array.isArray(data.full_name) ? data.full_name[0] : data.full_name;
      } else if (data.detail) {
        errorMsg = data.detail;
      }
      return { success: false, error: errorMsg, status: response.status };
    }

    return {
      success: true,
      user: data.user,
      tokens: data.tokens,
      role: 'CUSTOMER',
    };
  } catch (err) {
    return {
      success: false,
      error: 'Unable to connect to the backend server. Please check your network connection.',
      status: 0,
    };
  }
}

/**
 * Log out the authenticated user.
 */
export async function logoutUser(token) {
  try {
    await fetch(`${API_BASE_URL}/api/auth/logout/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
  } catch (err) {
    console.warn('Logout request failed or server unreachable', err);
  }
  return { success: true };
}

/**
 * Fetch authenticated profile from /api/auth/me/
 */
export async function getMe(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        return { success: false, error: 'Session expired', status: response.status };
      }
      return { success: false, error: 'Server error', status: response.status };
    }

    const data = await response.json();
    return { success: true, user: data.user };
  } catch (err) {
    return { success: false, error: 'Network error', status: 0 };
  }
}

/* ==========================================================================
   CATALOG API HELPERS (Part 2A)
   ========================================================================== */

// Lightweight category cache: the category list is derived from products and
// only needs refreshing after mutations (e.g. a warehouse product edit).
let categoriesCache = null; // { promise }

/**
 * Fetch all categories with product counts (cached across the app session;
 * call invalidateCategoriesCache() after any product mutation).
 */
export async function getCategories() {
  if (!categoriesCache) {
    categoriesCache = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/catalog/categories/`);
        const data = await response.json();
        if (!response.ok) {
          return { success: false, error: data.detail || 'Failed to fetch categories' };
        }
        return {
          success: true,
          categories: Array.isArray(data) ? data : (data.categories || [])
        };
      } catch (err) {
        return { success: false, error: 'Network error fetching categories' };
      }
    })();
    // Do not keep failed lookups cached — next call should retry.
    categoriesCache.then((res) => {
      if (res && res.success === false) categoriesCache = null;
    });
  }
  return categoriesCache;
}

/** Clears the category cache so the next getCategories() refetches. */
export function invalidateCategoriesCache() {
  categoriesCache = null;
}

/**
 * Fetch products list with optional filters, search, sorting and pagination.
 */
function appendProductFilters(query, params = {}) {
  [
    'category',
    'sub_category',
    'subcategory_search',
    'search',
    'min_price',
    'max_price',
    'in_stock',
    'on_sale',
    'size',
    'color',
    'letter',
    'sort',
    'starts_with',
    'page',
  ].forEach((key) => {
    if (params[key] !== undefined && params[key] !== '') query.append(key, params[key]);
  });
  if (params.page_size) {
    query.append('page_size', Math.min(Number(params.page_size) || 20, 20));
  }
}

export async function getProducts(params = {}) {
  try {
    const query = new URLSearchParams();
    appendProductFilters(query, params);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/catalog/products/${qs ? '?' + qs : ''}`;
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch products' };
    }

    return {
      success: true,
      products: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.current_page || 1,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching products' };
  }
}

export async function getWarehouseProducts(params = {}, token = null) {
  try {
    const query = new URLSearchParams();
    appendProductFilters(query, params);
    const authToken = token || localStorage.getItem('iras_token');
    const headers = {};
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    const qs = query.toString();
    const response = await fetch(
      `${API_BASE_URL}/api/warehouse/products/${qs ? '?' + qs : ''}`,
      { headers }
    );
    const data = await response.json();
    if (!response.ok) {
      return {
        success: false,
        error: data.detail || 'Failed to fetch warehouse products',
        status: response.status,
      };
    }
    return {
      success: true,
      products: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.current_page || 1,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching warehouse products' };
  }
}

async function getCuratedProducts(endpoint, limit, params) {
  const query = new URLSearchParams();
  if (params) appendProductFilters(query, params);
  else query.append('limit', Math.min(Number(limit) || 20, 20));
  const qs = query.toString();
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/${endpoint}/${qs ? '?' + qs : ''}`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || `Failed to fetch ${endpoint}` };
    }
    return {
      success: true,
      products: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.current_page || 1,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
    };
  } catch {
    return { success: false, error: `Network error fetching ${endpoint}` };
  }
}

/**
 * Fetch real database Orders with search, status filter, and pagination.
 */
export async function getWarehouseOrders(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.warehouse) query.append('warehouse', params.warehouse);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/warehouse/orders/${qs ? '?' + qs : ''}`;
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch orders' };
    }

    return {
      success: true,
      orders: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.current_page || 1,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching orders' };
  }
}

/**
 * Fetch real database Deliveries with search, status filter, partner filter, and pagination.
 */
export async function getWarehouseDeliveries(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.partner && params.partner !== 'ALL') query.append('partner', params.partner);
    if (params.warehouse) query.append('warehouse', params.warehouse);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/warehouse/deliveries/${qs ? '?' + qs : ''}`;
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch deliveries' };
    }

    return {
      success: true,
      deliveries: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.current_page || 1,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching deliveries' };
  }
}

/**
 * Fetch real database Returns with search, status filter, reason filter, and pagination.
 */
export async function getWarehouseReturns(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.reason && params.reason !== 'ALL') query.append('reason', params.reason);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/warehouse/returns/${qs ? '?' + qs : ''}`;
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch returns' };
    }

    return {
      success: true,
      returnsList: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.current_page || 1,
      hasNext: Boolean(data.next),
      hasPrevious: Boolean(data.previous),
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching returns' };
  }
}

/**
 * Fetch complete order details including customer info and all order items from Django.
 */
export async function getWarehouseOrderDetail(orderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/warehouse/orders/${orderId}/`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch order details' };
    }
    return { success: true, order: data };
  } catch (err) {
    return { success: false, error: 'Network error fetching order details' };
  }
}

/**
 * Fetch distinct courier companies dynamically from backend.
 */
export async function getCourierPartners() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/warehouse/courier-partners/`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch courier partners' };
    }
    return { success: true, partners: data.partners || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching courier partners' };
  }
}

/**
 * Fetch active delivery partner employees (optionally filtered by courier company).
 */
export async function getDeliveryEmployees(company = '') {
  try {
    const qs = company ? `?company=${encodeURIComponent(company)}` : '';
    const response = await fetch(`${API_BASE_URL}/api/warehouse/delivery-employees/${qs}`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch delivery employees' };
    }
    return { success: true, employees: data.employees || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching delivery employees' };
  }
}

/**
 * Dispatch an order to a delivery partner employee.
 */
export async function dispatchWarehouseOrder(orderId, payload, token = null) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/warehouse/orders/${orderId}/dispatch/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorMsg = data.errors
        ? Object.entries(data.errors).map(([f, m]) => `${f}: ${m}`).join(', ')
        : (data.detail || 'Failed to dispatch order');
      return { success: false, error: errorMsg };
    }
    return { success: true, message: data.message, order: data.order, delivery: data.delivery };
  } catch (err) {
    return { success: false, error: 'Network error dispatching order' };
  }
}


/**
 * Fetch a single product's full details from the warehouse endpoint.

 * Returns product fields + availability_label / total_stock / in_stock
 * computed by Django (not by React).
 */
export async function getWarehouseProductDetail(productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/warehouse/products/${productId}/`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch product details' };
    }
    return { success: true, product: data };
  } catch (err) {
    return { success: false, error: 'Network error fetching product details' };
  }
}

/**
 * Update a product via the Warehouse Manager endpoint.
 * Sends validated form fields to Django; Django authenticates the Bearer
 * token, enforces the warehouse_manager role, validates and persists.
 * Returns the updated product (re-read from the database) on success.
 */
export async function updateWarehouseProduct(productId, payload, token = null) {
  try {
    const authToken = token || localStorage.getItem('iras_token');
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE_URL}/api/warehouse/products/${encodeURIComponent(productId)}/`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (response.status === 401 || response.status === 403) {
      return {
        success: false,
        error: data.detail || 'You are not authorised to edit products. Please sign in as a Warehouse Manager.',
        status: response.status,
      };
    }
    if (!response.ok) {
      // Django returns { errors: { field: [...] } } on 400
      const errors = data.errors || {};
      const firstError = Object.values(errors).flat()[0] || data.detail || 'Validation failed.';
      return { success: false, error: firstError, errors };
    }
    return { success: true, product: data.product, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error updating product' };
  }
}

/**
 * Accept a return request (status must be 'Requested').
 * Django validates, updates DB status to 'Accepted', and computes refund_amount.
 */
export async function acceptWarehouseReturn(returnId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/warehouse/returns/${returnId}/accept/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to accept return.' };
    }
    return { success: true, return: data.return, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error accepting return.' };
  }
}

/**
 * Reject a return request (status must be 'Requested').
 * Django validates and updates DB status to 'Rejected'.
 */
export async function rejectWarehouseReturn(returnId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/warehouse/returns/${returnId}/reject/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to reject return.' };
    }
    return { success: true, return: data.return, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error rejecting return.' };
  }
}

/**
 * Assign an approved return request to an active delivery partner employee.
 */
export async function assignWarehouseReturnPickup(returnId, { delivery_partner, assigned_employee_id }) {
  try {
    const token = localStorage.getItem('tarika_auth_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/warehouse/returns/${returnId}/assign/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ delivery_partner, assigned_employee_id }),
    });
    const data = await response.json();
    if (!response.ok) {
      const err = data.detail || data.errors?.delivery_partner?.[0] || data.errors?.assigned_employee_id?.[0] || 'Failed to assign return pickup.';
      return { success: false, error: err };
    }
    return { success: true, return: data.return, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error assigning return pickup.' };
  }
}

/**
 * Confirm returned merchandise received at the warehouse.
 */
export async function receiveWarehouseReturn(returnId) {
  try {
    const token = localStorage.getItem('tarika_auth_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/warehouse/returns/${returnId}/receive/`, {
      method: 'PATCH',
      headers,
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to confirm return received.' };
    }
    return { success: true, return: data.return, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error confirming return received.' };
  }
}

/**
 * Customer submits return request for a delivered item.
 */
export async function requestCustomerReturn(orderId, { order_item_id, return_reason, condition_on_return = '' }, token = null) {
  try {
    const authToken = token || localStorage.getItem('tarika_auth_token');
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}/return/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ order_item_id, return_reason, condition_on_return }),
    });
    const data = await response.json();
    if (!response.ok) {
      const err = data.detail || data.order_item_id?.[0] || data.return_reason?.[0] || 'Failed to submit return request.';
      return { success: false, error: err };
    }
    return { success: true, return: data.return, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error submitting return request.' };
  }
}


/**
 * Fetch the stored return reason for one returned order, on demand.
 * Scoped to the signed-in customer on the backend; the internal abuse
 * classification is never part of the response.
 */
export async function getOrderReturnReason(orderId, token = null) {
  try {
    const authToken = token || localStorage.getItem('tarika_auth_token');
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}/returns/`, {
      method: 'GET',
      headers,
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch return details.' };
    }
    return { success: true, found: Boolean(data.found), returnReason: data.return_reason || '' };
  } catch (err) {
    return { success: false, error: 'Network error fetching return details.' };
  }
}



export async function getProductDetail(productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/products/${productId}/`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch product details' };
    }
    return { success: true, product: data };
  } catch (err) {
    return { success: false, error: 'Network error fetching product' };
  }
}

/**
 * Fetch Apriori-based Frequently Bought Together product recommendations.
 */
export async function getProductRecommendations(productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/recommendations/${productId}/`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch recommendations' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching recommendations' };
  }
}


/**
 * Fetch New Arrivals.
 */
export async function getNewArrivals(limit = 10, params = null) {
  return getCuratedProducts('new-arrivals', limit, params);
}

/**
 * Fetch Trending Products.
 */
export async function getTrending(limit = 10, params = null) {
  return getCuratedProducts('trending', limit, params);
}

/**
 * Fetch Sale / Discounted Products.
 */
export async function getSale(limit = 10, params = null) {
  return getCuratedProducts('sale', limit, params);
}

/* ==========================================================================
   WISHLIST API HELPERS (Part 2B)
   ========================================================================== */

/**
 * Get authenticated customer's wishlist.
 */
export async function getWishlist(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/wishlist/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch wishlist' };
    }
    return {
      success: true,
      items: data.results || data.items || [],
      count: data.count || (data.results ? data.results.length : 0),
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching wishlist' };
  }
}

/**
 * Add a product to customer's wishlist.
 */
export async function addToWishlist(token, productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/wishlist/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ product_id: productId }),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to add to wishlist' };
    }
    return { success: true, item: data.item, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error adding to wishlist' };
  }
}

/**
 * Remove a product from customer's wishlist.
 */
export async function removeFromWishlist(token, productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/wishlist/${productId}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to remove from wishlist' };
    }
    return { success: true, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error removing from wishlist' };
  }
}

/* ==========================================================================
   BAG / CART API HELPERS (Part 2B)
   ========================================================================== */

/**
 * Get authenticated customer's bag/cart.
 */
export async function getBag(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/cart/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch bag' };
    }
    return {
      success: true,
      items: data.items || [],
      totalItems: data.total_items || 0,
      subtotal: data.subtotal || 0,
      total: data.total || 0,
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching bag' };
  }
}

/**
 * Add a product to customer's bag.
 */
export async function addToBag(token, productId, quantity = 1) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/cart/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ product_id: productId, quantity }),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to add product to bag' };
    }
    return {
      success: true,
      item: data.item,
      cart: data.cart,
      message: data.message,
    };
  } catch (err) {
    return { success: false, error: 'Network error adding product to bag' };
  }
}

/**
 * Update quantity of a bag item.
 */
export async function updateBagQuantity(token, productId, quantity) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/cart/${productId}/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ quantity }),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to update quantity' };
    }
    return {
      success: true,
      item: data.item,
      cart: data.cart,
      message: data.message,
    };
  } catch (err) {
    return { success: false, error: 'Network error updating bag quantity' };
  }
}

/**
 * Remove an item completely from the customer's bag.
 */
export async function removeFromBag(token, productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/cart/${productId}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to remove from bag' };
    }
    return {
      success: true,
      cart: data.cart,
      message: data.message,
    };
  } catch (err) {
    return { success: false, error: 'Network error removing from bag' };
  }
}

/**
 * Clear the entire bag.
 */
export async function clearBag(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/cart/clear/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to clear bag' };
    }
    return {
      success: true,
      message: data.message,
    };
  } catch (err) {
    return { success: false, error: 'Network error clearing bag' };
  }
}

/**
 * Place a customer order from current bag items.
 * Validates address and payment method, creates Order & Payment, and clears bag.
 */
export async function createOrder(token, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/orders/checkout/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorMsg =
        data.detail ||
        (Array.isArray(data.non_field_errors) && data.non_field_errors[0]) ||
        (typeof data === 'object' && Object.values(data)[0] && (Array.isArray(Object.values(data)[0]) ? Object.values(data)[0][0] : Object.values(data)[0])) ||
        'Failed to place order. Please try again.';
      return { success: false, error: errorMsg };
    }
    return {
      success: true,
      message: data.message || 'Order placed successfully.',
      order: data.order,
    };
  } catch (err) {
    return { success: false, error: 'Network error placing order. Please check your connection.' };
  }
}

/**
 * Fetch detailed information for a specific order.
 */
export async function getOrderDetails(token, orderId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}/`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch order details.' };
    }
    return { success: true, order: data };
  } catch (err) {
    return { success: false, error: 'Network error retrieving order details.' };
  }
}

/**
 * Fetch all orders placed by the authenticated customer.
 * Strictly scoped to the logged-in customer's session on the backend.
 */
export async function getCustomerOrders(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/orders/`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch customer orders.' };
    }
    return {
      success: true,
      orders: data.results || (Array.isArray(data) ? data : []),
      count: data.count || (Array.isArray(data.results) ? data.results.length : 0),
    };
  } catch (err) {
    return { success: false, error: 'Network error retrieving your orders. Please check your connection.' };
  }
}

/**
 * Submit or update a product rating and review.
 * @param {string} token
 * @param {string} productId
 * @param {{ rating: number, review_text: string }} payload
 */
export async function submitProductReview(token, productId, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/products/${productId}/reviews/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to submit review.' };
    }
    return {
      success: true,
      message: data.message,
      review: data.review,
      ratingSummary: data.rating_summary,
    };
  } catch (err) {
    return { success: false, error: 'Network error submitting review.' };
  }
}

/**
 * Fetch all reviews and rating summary for a product.
 * @param {string} productId
 */
export async function getProductReviews(productId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/products/${productId}/reviews/`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch reviews.' };
    }
    return {
      success: true,
      ratingSummary: data.rating_summary,
      reviews: data.reviews || [],
      count: data.count || 0,
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching reviews.' };
  }
}

/* ==========================================================================
   ADMIN PORTAL API HELPERS
   ========================================================================== */

/**
 * Fetch executive dashboard statistics and live system overview.
 */
export async function getAdminDashboardStats(token) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/admin/dashboard/`, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to load dashboard metrics.' };
    }
    return { success: true, data };
  } catch (err) {
    return { success: false, error: 'Network error fetching admin dashboard stats.' };
  }
}

/**
 * Fetch the Product Performance Map: every real products.sub_category of the
 * active catalog, measured on delivered sales/revenue and classified into the
 * four performance quadrants by the backend (admin/performance_map.py).
 */
export async function getAdminProductPerformance(token) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/admin/product-performance/`, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to load the product performance map.' };
    }
    return { success: true, data };
  } catch (err) {
    return { success: false, error: 'Network error fetching the product performance map.' };
  }
}

/**
 * Fetch the aggregated sales history (units sold over time) for ONE product,
 * from real delivered orders. granularity: 'day' | 'week' | 'month'.
 */
export async function getProductSalesHistory(token, productKey, granularity = 'month') {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const params = new URLSearchParams({ product_key: productKey, granularity });
    const response = await fetch(`${API_BASE_URL}/api/demand-prediction/history/?${params.toString()}`, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to load sales history.' };
    }
    return { success: true, points: data.points || [], totalUnits: data.total_units || 0, granularity: data.granularity };
  } catch (err) {
    return { success: false, error: 'Network error loading sales history.' };
  }
}

/**
 * Fetch staff members from the backend (public.app_users). Supports search,
 * role + status filters and server-side pagination.
 */
export async function getStaffList(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.role && params.role !== 'ALL') query.append('role', params.role);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/admin/staff/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch staff list.' };
    }
    return {
      success: true,
      summary: data.summary || {},
      staff: data.staff || [],
      roles: data.roles || [],
      pagination: data.pagination || {},
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching staff list.' };
  }
}

/**
 * Create a staff account in public.app_users (password hashed server-side).
 */
export async function createStaffMember(token, payload) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/admin/staff/create/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorMsg = data.errors
        ? Object.values(data.errors).flat().join(', ')
        : (data.detail || 'Failed to create staff member.');
      return { success: false, error: errorMsg };
    }
    return { success: true, message: data.message, staff: data.staff };
  } catch (err) {
    return { success: false, error: 'Network error creating staff member.' };
  }
}

/**
 * Edit a staff account (role / active / optional password reset).
 */
export async function updateStaffMember(token, userId, payload) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/admin/staff/${userId}/`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorMsg = data.errors
        ? Object.values(data.errors).flat().join(', ')
        : (data.detail || 'Failed to update staff member.');
      return { success: false, error: errorMsg };
    }
    return { success: true, message: data.message, staff: data.staff };
  } catch (err) {
    return { success: false, error: 'Network error updating staff member.' };
  }
}

/**
 * Toggle staff active status (activate / deactivate).
 */
export async function toggleStaffStatus(token, userId, targetStatus = null) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const body = targetStatus !== null ? JSON.stringify({ is_active: targetStatus }) : undefined;

    const response = await fetch(`${API_BASE_URL}/api/admin/staff/${userId}/toggle-status/`, {
      method: 'PATCH',
      headers,
      body,
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to toggle staff status.' };
    }
    return { success: true, message: data.message, staff: data.staff };
  } catch (err) {
    return { success: false, error: 'Network error toggling staff status.' };
  }
}

/**
 * Fetch network warehouses list with stock utilization.
 */
export async function getAdminWarehouseList(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/admin/warehouses/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch warehouse list.' };
    }
    return {
      success: true,
      summary: data.summary || {},
      warehouses: data.warehouses || [],
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching warehouse list.' };
  }
}

/**
 * Fetch admin catalog products list with filters.
 */
export async function getAdminProductList(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.category && params.category !== 'ALL') query.append('category', params.category);
    if (params.stock_status && params.stock_status !== 'ALL') query.append('stock_status', params.stock_status);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/admin/products/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch admin product catalog.' };
    }
    return {
      success: true,
      metrics: data.metrics || {},
      categories: data.categories || [],
      products: data.products || [],
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching admin products.' };
  }
}

/**
 * Create a new product in the catalog with initial stock allocation.
 */
export async function createAdminProduct(token, payload) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/admin/products/create/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorMsg = data.errors
        ? Object.entries(data.errors).map(([f, m]) => `${f}: ${m}`).join(', ')
        : (data.detail || 'Failed to create product.');
      return { success: false, error: errorMsg };
    }
    return { success: true, message: data.message, product: data.product };
  } catch (err) {
    return { success: false, error: 'Network error creating product.' };
  }
}

/**
 * Fetch all system orders for admin oversight.
 */
export async function getAdminOrders(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/admin/orders/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch admin orders.' };
    }
    return {
      success: true,
      metrics: data.metrics || {},
      orders: data.results || data.orders || [],
      count: data.count,
      total_pages: data.total_pages,
      current_page: data.current_page,
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching admin orders.' };
  }
}

/**
 * Fetch detailed order information for admin.
 */
export async function getAdminOrderDetail(token, orderId) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/admin/orders/${orderId}/`, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch order detail.' };
    }
    return { success: true, order: data };
  } catch (err) {
    return { success: false, error: 'Network error fetching admin order detail.' };
  }
}

/**
 * Fetch system customers for admin oversight.
 */
export async function getAdminCustomers(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.page) query.append('page', params.page);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/admin/customers/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch customers.' };
    }
    return {
      success: true,
      metrics: data.metrics || {},
      customers: data.results || [],
      count: data.count,
      total_pages: data.total_pages,
      current_page: data.current_page,
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching admin customers.' };
  }
}

/**
 * Fetch a single customer's detailed record.
 */
export async function getAdminCustomerDetail(token, customerId) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const url = `${API_BASE_URL}/api/admin/customers/${encodeURIComponent(customerId)}/`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch customer detail.' };
    }
    return { success: true, customer: data };
  } catch (err) {
    return { success: false, error: 'Network error fetching customer detail.' };
  }
}

/* ==========================================================================
   DATA MINING & DEMAND PREDICTION API HELPERS
   ========================================================================== */

/**
 * Fetch Demand Prediction analytics & Decision Tree results.
 * Returns the ID3 model explanation + demand-class distribution only
 * (no per-product rows -- those come from getDemandPredictionProducts).
 */
export async function getDemandPredictionAnalytics(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.refresh) query.append('refresh', '1');

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/demand-prediction/analytics/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch demand prediction analytics.' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching demand prediction analytics.' };
  }
}

/**
 * Fetch one page of per-product demand predictions (server-side filter/sort/page).
 * @param {string} token
 * @param {Object} params - { page, page_size, search, demand_level, category, sort, dir }
 */
export async function getDemandPredictionProducts(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    if (params.search) query.append('search', params.search);
    if (params.demand_level && params.demand_level !== 'ALL') query.append('demand_level', params.demand_level);
    if (params.category && params.category !== 'ALL') query.append('category', params.category);
    if (params.sort) query.append('sort', params.sort);
    if (params.dir) query.append('dir', params.dir);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/demand-prediction/products/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch demand predictions.' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching demand predictions.' };
  }
}

/**
 * Fetch the distinct product categories for the demand forecasting filter.
 */
export async function getDemandPredictionCategories(token) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const url = `${API_BASE_URL}/api/demand-prediction/categories/`;
    const response = await fetch(url, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch categories.' };
    }
    return { success: true, categories: data.categories || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching categories.' };
  }
}

/* ==========================================================================
   STOCK TO BE ORDERED API HELPERS  (Warehouse Manager only)
   ========================================================================== */

/**
 * Fetch demand-driven Stock to Be Ordered rows (server-side paged).
 * Access: Warehouse Manager only. Synchronised with the Demand Prediction model.
 *
 * @param {string} token  - Bearer token
 * @param {Object} params - { page, page_size, search, demand_tier, category, sort, dir }
 */
export async function getStockToBeOrdered(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    if (params.search) query.append('search', params.search);
    if (params.demand_tier && params.demand_tier !== 'ALL') query.append('demand_tier', params.demand_tier);
    if (params.category && params.category !== 'ALL') query.append('category', params.category);
    if (params.sort) query.append('sort', params.sort);
    if (params.dir) query.append('dir', params.dir);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/stock-to-be-ordered/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: data.error || data.detail || 'Failed to fetch stock forecast.',
      };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching stock forecast.' };
  }
}

/**
 * Fetch distinct product categories for the Stock to Be Ordered filter.
 */
export async function getStockCategories(token) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/categories/`, { headers });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch categories.' };
    }
    return { success: true, categories: data.categories || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching stock categories.' };
  }
}

/* ==========================================================================
   WAREHOUSE DELETE + REPLENISHMENT ORDERING API HELPERS
   ========================================================================== */

/**
 * Permanently remove (or archive, if it has history) a product via Warehouse.
 * Django authenticates the Bearer token, enforces the warehouse role and chooses
 * hard-delete vs archive based on foreign-key references. Invalidates the
 * cached category list so the storefront refreshes.
 */
export async function deleteWarehouseProduct(productId, token = null) {
  try {
    const authToken = token || localStorage.getItem('iras_token');
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE_URL}/api/warehouse/products/${encodeURIComponent(productId)}/`, {
      method: 'DELETE',
      headers,
    });
    const data = await response.json();
    if (response.status === 401 || response.status === 403) {
      return { success: false, error: data.detail || 'You are not authorised to delete products.' };
    }
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to delete product.' };
    }
    invalidateCategoriesCache();
    return { success: true, message: data.message, action: data.action };
  } catch (err) {
    return { success: false, error: 'Network error deleting product' };
  }
}

/** Place a single-product replenishment (restock) order. */
export async function createReplenishmentOrder(token, productKey, quantity) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/order/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ product_key: productKey, quantity }),
    });
    const data = await response.json();
    if (!response.ok) {
      const err = data.detail || (data.errors && Object.values(data.errors).flat()[0]) || 'Failed to place order.';
      return { success: false, error: err };
    }
    // The reorder committed a stock increment, so drop the cached catalog so the
    // Warehouse inventory re-reads the new available_quantity (no full reload).
    invalidateCategoriesCache();
    return {
      success: true,
      message: data.message,
      order: data.order,
      availableQuantity: data.available_quantity,
      addedQuantity: data.added_quantity,
    };
  } catch (err) {
    return { success: false, error: 'Network error placing replenishment order.' };
  }
}

/** Preview which products a bulk “Order All <tier> Demand Products” action would order. */
export async function getDemandPreview(token, tier = 'High') {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/demand-preview/?tier=${encodeURIComponent(tier)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to load demand products.' };
    }
    return { success: true, items: data.items || [], productCount: data.product_count, totalQuantity: data.total_quantity };
  } catch (err) {
    return { success: false, error: 'Network error loading bulk-order preview.' };
  }
}

/** Confirm a bulk replenishment order for a demand tier, optionally only the
 *  reviewed product subset (staff can deselect individual products). */
export async function orderAllDemand(token, tier = 'High', productKeys = null) {
  try {
    const body = { tier };
    if (Array.isArray(productKeys)) body.product_keys = productKeys;
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/demand-order/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to place bulk order.' };
    }
    return {
      success: true,
      message: data.message,
      createdCount: data.created_count,
      skippedCount: data.skipped_count,
      failedCount: data.failed_count,
      totalQuantity: data.total_quantity,
      orders: data.orders || [],
      failures: data.failures || [],
    };
  } catch (err) {
    return { success: false, error: 'Network error placing bulk order.' };
  }
}

/** Record that a replenishment order's goods were received (adds to stock). */
export async function receiveReplenishmentOrder(token, poKey, quantityReceived = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/orders/${encodeURIComponent(poKey)}/receive/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(quantityReceived == null ? {} : { quantity_received: quantityReceived }),
    });
    const data = await response.json();
    if (!response.ok) {
      const err = data.detail || (data.errors && Object.values(data.errors).flat()[0]) || 'Failed to record receipt.';
      return { success: false, error: err };
    }
    invalidateCategoriesCache();
    return { success: true, message: data.message, addedQuantity: data.added_quantity, availableQuantity: data.available_quantity };
  } catch (err) {
    return { success: false, error: 'Network error recording receipt.' };
  }
}

/** Edit the proposed supplier quantity of a Pending purchase order.
 *  Persisted through Django into Neon; never changes available stock. */
export async function updateReplenishmentOrder(token, poKey, quantity) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/orders/${encodeURIComponent(poKey)}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ quantity }),
    });
    const data = await response.json();
    if (!response.ok) {
      const err = data.detail || (data.errors && Object.values(data.errors).flat()[0]) || 'Failed to update order quantity.';
      return { success: false, error: err };
    }
    return { success: true, message: data.message, order: data.order };
  } catch (err) {
    return { success: false, error: 'Network error updating replenishment order.' };
  }
}

/** Cancel a Pending supplier purchase order (stock is never affected). */
export async function cancelReplenishmentOrder(token, poKey) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/orders/${encodeURIComponent(poKey)}/`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to cancel order.' };
    }
    return { success: true, message: data.message, order: data.order };
  } catch (err) {
    return { success: false, error: 'Network error cancelling replenishment order.' };
  }
}

/** List replenishment purchase orders (optionally by status / product). */
export async function getReplenishmentOrders(token, params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.productKey) query.append('product_key', params.productKey);
    const qs = query.toString();
    const response = await fetch(`${API_BASE_URL}/api/stock-to-be-ordered/orders/${qs ? '?' + qs : ''}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch purchase orders.' };
    }
    return { success: true, orders: data.orders || [], count: data.count };
  } catch (err) {
    return { success: false, error: 'Network error fetching purchase orders.' };
  }
}

/**
 * Fetch Slow-Moving Inventory analysis data.
 */
export async function getSlowMovingInventory(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.movement_status && params.movement_status !== 'ALL') query.append('movement_status', params.movement_status);
    if (params.warehouse_id && params.warehouse_id !== 'ALL') query.append('warehouse_id', params.warehouse_id);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/demand-prediction/slow-inventory/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch slow-moving inventory data.' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching slow-moving inventory data.' };
  }
}

/**
 * GET /api/demand-prediction/revenue-forecast/
 * Fetches historical monthly revenue aggregates, Holt-Winters 3-month forecast,
 * validation metrics, baseline comparison, and business insights.
 */
export async function getRevenueForecast(token = null, forceRefresh = false) {
  try {
    const activeToken = token || localStorage.getItem('iras_token') || localStorage.getItem('token') || localStorage.getItem('tarika_auth_token');
    const headers = { 'Content-Type': 'application/json' };
    if (activeToken) headers['Authorization'] = `Bearer ${activeToken}`;

    const url = `${API_BASE_URL}/api/demand-prediction/revenue-forecast/${forceRefresh ? '?force_refresh=true' : ''}`;
    const response = await fetch(url, { headers });

    let data;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      data = { error: text || `HTTP ${response.status} ${response.statusText}` };
    }

    if (!response.ok) {
      let errorMsg = data.error || data.detail;
      if (!errorMsg) {
        if (response.status === 401) {
          errorMsg = 'Authentication required. Please log in as an administrator.';
        } else if (response.status === 403) {
          errorMsg = 'Access denied. Administrator privileges required to access Revenue Forecasting.';
        } else if (response.status >= 500) {
          errorMsg = `Server error (${response.status}) while generating revenue forecast.`;
        } else {
          errorMsg = `Failed to fetch revenue forecast (HTTP ${response.status}).`;
        }
      }
      return { success: false, error: errorMsg, status: response.status };
    }
    return { success: true, ...data };
  } catch (err) {
    console.error('getRevenueForecast network error:', err);
    return {
      success: false,
      error: 'Network error fetching revenue forecast data. Please check that the backend server is running and accessible.',
    };
  }
}

/**
 * GET /api/demand-prediction/revenue-olap/
 * Fetches Online Analytical Processing (OLAP) aggregations on delivered order revenue
 * along the Time Dimension (Roll-up, Drill-down, Slice, Dice, Pivot, Ranking,
 * Drill-Through, Trend Analysis).
 */
export async function getRevenueOLAP({
  operation = 'rollup',
  level = 'quarter',
  year = null,
  quarter = null,
  sliceType = null,
  sliceValue = null,
  years = null,
  months = null,
  granularity = null,
  sortOrder = null,
  periodType = null,
  periodKey = null,
  page = 1,
  pageSize = 50,
  forceRefresh = false,
} = {}, token = null) {
  try {
    const activeToken =
      token ||
      localStorage.getItem('iras_token') ||
      localStorage.getItem('tarika_auth_token') ||
      localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json' };
    if (activeToken) headers['Authorization'] = `Bearer ${activeToken}`;

    const params = new URLSearchParams();
    if (operation) params.append('operation', operation);
    if (level) params.append('level', level);
    if (year) params.append('year', year);
    if (quarter) params.append('quarter', quarter);
    if (sliceType) params.append('slice_type', sliceType);
    if (sliceValue) params.append('slice_value', sliceValue);

    if (years !== null && years !== undefined) {
      if (Array.isArray(years)) params.append('years', years.join(','));
      else params.append('years', String(years));
    }
    if (months !== null && months !== undefined) {
      if (Array.isArray(months)) params.append('months', months.join(','));
      else params.append('months', String(months));
    }

    if (granularity) params.append('granularity', granularity);
    if (sortOrder) params.append('sort_order', sortOrder);
    if (periodType) params.append('period_type', periodType);
    if (periodKey) params.append('period_key', periodKey);

    if (page != null) params.append('page', String(page));
    if (pageSize != null) params.append('page_size', String(pageSize));
    if (forceRefresh) params.append('force_refresh', 'true');

    const url = `${API_BASE_URL}/api/demand-prediction/revenue-olap/?${params.toString()}`;
    const response = await fetch(url, { headers });
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    if (!response.ok) {
      return {
        success: false,
        error: data?.error || data?.detail || `Server returned error (${response.status}).`,
        status: response.status,
      };
    }
    return { success: true, ...data };
  } catch (err) {
    return {
      success: false,
      error: err?.message ? `Network error: ${err.message}` : 'Network error fetching Revenue OLAP data.',
    };
  }
}

/* ==========================================================================
   RFM SEGMENTATION, CAMPAIGN & PERSONALIZED OFFER API HELPERS
   ========================================================================== */

function authHeaders(token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

/** POST /api/analytics/rfm/run -> start a background RFM analysis. */
export async function runRfmAnalysis(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analytics/rfm/run`, {
      method: 'POST', headers: authHeaders(token),
    });
    const data = await response.json();
    // 202 accepted, 409 already running -> both are normal responses.
    if (!response.ok && response.status !== 409) {
      return { success: false, error: data.detail || 'Failed to start RFM analysis.' };
    }
    return { success: true, status: data.status, message: data.message, conflict: response.status === 409 };
  } catch (err) {
    return { success: false, error: 'Network error starting RFM analysis.' };
  }
}

/** GET /api/analytics/rfm/run -> current run status (for polling). */
export async function getRfmRunStatus(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analytics/rfm/run`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch run status.' };
    return { success: true, status: data.status };
  } catch (err) {
    return { success: false, error: 'Network error fetching RFM run status.' };
  }
}

/** GET /api/analytics/rfm/summary -> aggregate KPIs and segment cards.
 *
 *  Deduplicated and briefly cached on the client: the Analysis overview shows a
 *  compact RFM card and the full dashboard reads the same payload, so opening
 *  one from the other must not pay twice, and React mounting a component twice
 *  (dev StrictMode, or a back-and-forth navigation) must not send two requests.
 *  `peekRfmSummaryCache` hands the stored payload to a component synchronously,
 *  which is what lets the dashboard paint instantly and refresh in background.
 */
const RFM_SUMMARY_TTL_MS = 15000;
const rfmSummaryCache = { token: null, at: 0, data: null, inflight: null };

function rfmSummaryCacheFresh(token) {
  return rfmSummaryCache.token === token
    && rfmSummaryCache.data
    && (Date.now() - rfmSummaryCache.at) < RFM_SUMMARY_TTL_MS;
}

export function peekRfmSummaryCache(token) {
  return rfmSummaryCacheFresh(token) ? rfmSummaryCache.data : null;
}

export async function getRfmSummary(token, { force = false } = {}) {
  if (!force && rfmSummaryCacheFresh(token)) return { success: true, ...rfmSummaryCache.data };
  if (!force && rfmSummaryCache.inflight && rfmSummaryCache.token === token) {
    return rfmSummaryCache.inflight;      // one request serves every caller
  }
  const request = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/analytics/rfm/summary`, {
        headers: authHeaders(token),
      });
      const data = await response.json();
      if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch RFM summary.' };
      rfmSummaryCache.token = token;
      rfmSummaryCache.at = Date.now();
      rfmSummaryCache.data = data;
      return { success: true, ...data };
    } catch (err) {
      return { success: false, error: 'Network error fetching RFM summary.' };
    } finally {
      if (rfmSummaryCache.inflight === request) rfmSummaryCache.inflight = null;
    }
  })();
  rfmSummaryCache.token = token;
  rfmSummaryCache.inflight = request;
  return request;
}

/** GET /api/analytics/rfm/analytics -> the heavy analytics, read after paint.
 *
 *  Per-cluster RFM profiles, the mapping confidence, the ambiguity report, the
 *  clustering run bookkeeping and the legacy segment mix. The dashboard renders
 *  without it, so it is fetched once the first paint is on screen.
 */
export async function getRfmAnalyticsDetail(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analytics/rfm/analytics`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch RFM analytics.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching RFM analytics.' };
  }
}

/** GET /api/analytics/rfm/segments/{segment} -> one paginated segment list. */
export async function getRfmSegmentCustomers(token, segment, params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    if (params.search) query.append('search', params.search);
    if (params.sort) query.append('sort', params.sort);
    if (params.dir) query.append('dir', params.dir);
    const qs = query.toString();
    const url = `${API_BASE_URL}/api/analytics/rfm/segments/${encodeURIComponent(segment)}${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers: authHeaders(token) });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch segment customers.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching segment customers.' };
  }
}

/** GET /api/analytics/rfm/clusters -> current K-Means++ (k=4) clustering. */
export async function getRfmClusters(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analytics/rfm/clusters`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch K-Means clusters.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching K-Means clusters.' };
  }
}

/** POST /api/analytics/rfm/clusters -> run K-Means++ over the persisted RFM. */
export async function runRfmClustering(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/analytics/rfm/clusters`, {
      method: 'POST', headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to run K-Means clustering.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error running K-Means clustering.' };
  }
}

/**
 * Fetch Personalized Recommendations based on past orders, interests and gender.
 */
export async function getPersonalizedRecommendations(token, gender = null) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (gender) query.append('gender', gender);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/recommendations/personalized/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch personalized recommendations' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching personalized recommendations' };
  }
}

/**
 * GET /api/analytics/rfm/clusters/customers -> one page of a cluster's buyers.
 * Always server-side paginated (page/page_size/search/sort/dir), so a cluster
 * of ~100k customers never reaches the browser at once.
 */
export async function getRfmClusterCustomers(token, category, params = {}) {
  try {
    const query = new URLSearchParams();
    query.append('category', category);
    if (params.cluster_id !== undefined && params.cluster_id !== null) {
      query.append('cluster_id', params.cluster_id);
    }
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    if (params.search) query.append('search', params.search);
    if (params.sort) query.append('sort', params.sort);
    if (params.dir) query.append('dir', params.dir);
    const url = `${API_BASE_URL}/api/analytics/rfm/clusters/customers?${query.toString()}`;
    const response = await fetch(url, { headers: authHeaders(token) });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch cluster customers.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching cluster customers.' };
  }
}

/** GET /api/campaigns/clusters/ -> the K-Means customer groups a campaign may
 *  target (admin). One entry per cluster of the latest persisted clustering
 *  run: its business label, its cluster id and how many customers are actually
 *  assigned to it. Nothing here is inferred from a fixed id -> label table.
 */
export async function getCampaignClusters(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/campaigns/clusters/`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch customer groups.' };
    return {
      success: true,
      available: Boolean(data.available),
      clusters: data.clusters || [],
      run: data.run || null,
      message: data.message || '',
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching customer groups.' };
  }
}

/** GET /api/campaigns/ -> list campaigns with admin filters (admin). */
export async function getCampaigns(token, params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.status && params.status !== 'ALL') query.append('status', params.status);
    if (params.segment && params.segment !== 'ALL') query.append('segment', params.segment);
    if (params.cluster && params.cluster !== 'ALL') query.append('cluster', params.cluster);
    if (params.offer_type && params.offer_type !== 'ALL') query.append('offer_type', params.offer_type);
    if (params.search) query.append('search', params.search);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    const qs = query.toString();
    const url = `${API_BASE_URL}/api/campaigns/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers: authHeaders(token) });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch campaigns.' };
    return {
      success: true,
      campaigns: data.results || [],
      count: data.count || 0,
      totalPages: data.total_pages || 1,
      currentPage: data.page || 1,
      legacyAudience: data.legacy_audience || null,
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching campaigns.' };
  }
}

/** POST /api/campaigns/ -> create a campaign (admin). */
export async function createCampaign(token, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/campaigns/`, {
      method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorText = data.errors ? Object.values(data.errors).flat().join(', ') : (data.detail || 'Failed to create campaign.');
      return { success: false, error: errorText };
    }
    return { success: true, campaign: data };
  } catch (err) {
    return { success: false, error: 'Network error creating campaign.' };
  }
}

/** PUT /api/campaigns/{id}/ -> edit a campaign (admin). */
export async function updateCampaign(token, campaignId, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/campaigns/${campaignId}/`, {
      method: 'PUT', headers: authHeaders(token), body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      const errorText = data.errors ? Object.values(data.errors).flat().join(', ') : (data.detail || 'Failed to update campaign.');
      return { success: false, error: errorText };
    }
    return { success: true, campaign: data };
  } catch (err) {
    return { success: false, error: 'Network error updating campaign.' };
  }
}

/** DELETE /api/campaigns/{id}/ -> remove a campaign (admin). */
export async function deleteCampaign(token, campaignId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/campaigns/${campaignId}/`, {
      method: 'DELETE', headers: authHeaders(token),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return { success: false, error: data.detail || 'Failed to delete campaign.' };
    return { success: true, message: data.message };
  } catch (err) {
    return { success: false, error: 'Network error deleting campaign.' };
  }
}

/** POST /api/campaigns/{id}/status/ -> publish / pause / resume / expire (admin).
 *
 *  Publishing a K-Means campaign also assigns its coupon to the customers of the
 *  selected clusters, so the response carries `audience` - how many customers
 *  were targeted and how many were actually issued a coupon.
 */
export async function setCampaignStatus(token, campaignId, status) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/campaigns/${campaignId}/status/`, {
      method: 'POST', headers: authHeaders(token), body: JSON.stringify({ status }),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to change campaign status.' };
    return { success: true, campaign: data, audience: data.audience || null };
  } catch (err) {
    return { success: false, error: 'Network error changing campaign status.' };
  }
}

/** GET /api/campaigns/{id}/ -> one campaign with audience + redemption counts. */
export async function getCampaignDetail(token, campaignId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/campaigns/${campaignId}/`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch campaign.' };
    return { success: true, campaign: data };
  } catch (err) {
    return { success: false, error: 'Network error fetching campaign.' };
  }
}

/** GET /api/customer/me/offers -> the signed-in customer's eligible offers.
 *
 *  Only the offers themselves are handed to the UI. The internal RFM segment
 *  and tags stay server-side (they drive eligibility, they are never shown).
 *  `syncing` means the backend is computing the latest analysis; retry shortly.
 */
export async function getMyOffers(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/customer/me/offers`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch your offers.' };
    return { success: true, offers: data.offers || [], syncing: Boolean(data.syncing) };
  } catch (err) {
    return { success: false, error: 'Network error fetching your offers.' };
  }
}

/** POST /api/checkout/validate-coupon -> backend coupon check + reprice. */
export async function validateCheckoutCoupon(token, couponCode, cartValue) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/checkout/validate-coupon`, {
      method: 'POST', headers: authHeaders(token),
      body: JSON.stringify({ coupon_code: couponCode, cart_value: cartValue }),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, valid: false, error: data.detail || (data.coupon_code && String(data.coupon_code)) || 'Coupon is not valid.' };
    }
    return {
      success: true, valid: true,
      discount: data.discount, payable: data.payable, coupon_code: data.coupon_code,
      // Extra benefits computed by the backend (Buy & Get / combined offers).
      cashback: data.cashback || 0,
      free_shipping: Boolean(data.free_shipping),
      gift: data.gift || null,
      offer_summary: data.offer_summary || '',
      benefit_labels: data.benefit_labels || [],
    };
  } catch (err) {
    return { success: false, valid: false, error: 'Network error validating coupon.' };
  }
}

/* ==========================================================================
   CUSTOMER LIFETIME VALUE (CLV) API HELPERS  -  admin analysis dashboard
   ========================================================================== */

/** GET /api/clv/summary -> overview cards, cutoff date and future-CLV status. */
export async function getClvSummary(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/clv/summary`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch CLV summary.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching CLV summary.' };
  }
}

/** GET /api/clv/customers -> paginated per-customer CLV table (server-side filters). */
export async function getClvCustomers(token, params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);
    if (params.search) query.append('search', params.search);
    if (params.tier) query.append('tier', params.tier);
    if (params.segment) query.append('segment', params.segment);
    if (params.future_state) query.append('future_state', params.future_state);
    if (params.future_min !== undefined && params.future_min !== null && params.future_min !== '') {
      query.append('future_min', params.future_min);
    }
    if (params.future_max !== undefined && params.future_max !== null && params.future_max !== '') {
      query.append('future_max', params.future_max);
    }
    if (params.sort) query.append('sort', params.sort);
    if (params.dir) query.append('dir', params.dir);
    const qs = query.toString();
    const url = `${API_BASE_URL}/api/clv/customers${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers: authHeaders(token) });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch CLV customers.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching CLV customers.' };
  }
}

/** GET /api/clv/customers/{id} -> one customer's CLV details. */
export async function getClvCustomerDetail(token, customerId) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/clv/customers/${encodeURIComponent(customerId)}`,
      { headers: authHeaders(token) },
    );
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch customer CLV.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching customer CLV.' };
  }
}

/** GET /api/clv/segments -> value tiers + RFM segment-wise CLV analysis. */
export async function getClvSegments(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/clv/segments`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch CLV segments.' };
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching CLV segments.' };
  }
}

/** POST /api/clv/recalculate -> rebuild CLV from current data (admin-only). */
export async function recalculateClv(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/clv/recalculate`, {
      method: 'POST', headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok && response.status !== 409) {
      return { success: false, error: data.detail || 'Failed to start CLV recalculation.' };
    }
    return { success: true, status: data.status, message: data.message, conflict: response.status === 409 };
  } catch (err) {
    return { success: false, error: 'Network error starting CLV recalculation.' };
  }
}

/** GET /api/clv/recalculate -> recalculation status (for polling). */
export async function getClvRecalculateStatus(token) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/clv/recalculate`, {
      headers: authHeaders(token),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Failed to fetch CLV status.' };
    return { success: true, status: data.status };
  } catch (err) {
    return { success: false, error: 'Network error fetching CLV status.' };
  }
}
 /* Fetch Smart Budget Outfits based on color theory, occasion harmony, and knapsack price optimization.
 */
export async function getSmartBudgetOutfits({
  budget = 2000,
  gender = 'women',
  occasion = 'casual',
  style = 'chic',
  color = null,
  category_direction = 'all',
  sort = 'best',
  wardrobe_item_ids = [],
  customer_id = null,
  personalise = true,
  token = null,
} = {}) {
  try {
    const query = new URLSearchParams();
    query.append('budget', budget);
    query.append('gender', gender);
    query.append('occasion', occasion);
    if (style) query.append('style', style);
    if (color) query.append('color', color);
    if (category_direction) query.append('category_direction', category_direction);
    if (sort) query.append('sort', sort);
    if (customer_id) query.append('customer_id', customer_id);
    query.append('personalise', String(Boolean(personalise)));
    if (wardrobe_item_ids && (Array.isArray(wardrobe_item_ids) ? wardrobe_item_ids.length > 0 : Boolean(wardrobe_item_ids))) {
      query.append('wardrobe_item_ids', Array.isArray(wardrobe_item_ids) ? wardrobe_item_ids.join(',') : wardrobe_item_ids);
    }
    query.append('_t', Date.now());

    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const url = `${API_BASE_URL}/api/recommendations/smart-budget/?${query.toString()}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || data.message || 'Failed to generate budget outfits' };
    }
    return { success: true, ...data };
  } catch (err) {
    console.error('[getSmartBudgetOutfits network error]:', err);
    return { success: false, error: 'Network error generating budget outfits' };
  }
}

/**
 * Fetch customer coin balance & loyalty benefits from the server.
 */
export async function getCustomerCoins(customerId = null, token = null) {
  try {
    const query = new URLSearchParams();
    if (customerId) query.append('customer_id', customerId);
    query.append('_t', Date.now());

    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const url = `${API_BASE_URL}/api/recommendations/smart-budget/coins/?${query.toString()}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch coins' };
    }
    return { success: true, coins: data.coins };
  } catch (err) {
    console.error('[getCustomerCoins network error]:', err);
    return { success: false, error: 'Network error fetching coin balance' };
  }
}

export const getCoinBalance = getCustomerCoins;

/**
 * Redeem loyalty coins for an outfit combination.
 */
export async function redeemCoinsForOutfit({ customerId, outfitId, coins, token = null }) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/recommendations/smart-budget/redeem-coins/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ customer_id: customerId, outfit_id: outfitId, coins }),
    });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to redeem coins' };
    }
    return { success: true, ...data };
  } catch (err) {
    console.error('[redeemCoinsForOutfit network error]:', err);
    return { success: false, error: 'Network error redeeming coins' };
  }
}

/**
 * Fetch Wheel Configuration (segments, spin cost)
 */
export async function getWheelConfig() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/recommendations/spin-reward/`, {
      headers: { 'Accept': 'application/json' }
    });
    const data = await response.json();
    return data;
  } catch (err) {
    return { success: false, error: 'Failed to fetch wheel configuration' };
  }
}

/**
 * Spin Rewards Wheel with server-side validation
 */
export async function spinRewardWheel({ customerId = null, token = null } = {}) {
  try {
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/recommendations/spin-reward/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ customer_id: customerId }),
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to spin wheel' };
    }
    return { success: true, ...data };
  } catch (err) {
    console.error('[spinRewardWheel network error]:', err);
    return { success: false, error: 'Network error spinning wheel' };
  }
}



/**
 * Resolves a media URL (relative or absolute) to a full URL pointing to the active backend.
 */
export function resolveMediaUrl(url) {
  if (!url) return '';
  if (typeof url !== 'string') return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:') || url.startsWith('blob:')) {
    return url;
  }
  const cleanBase = API_BASE_URL.replace(/\/+$/, '');
  const cleanPath = url.startsWith('/') ? url : `/${url}`;
  return `${cleanBase}${cleanPath}`;
}

/**
 * Digital Wardrobe API: Fetch items in authenticated customer's wardrobe.
 */
export async function getWardrobeItems(token, filters = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (filters.slot_type && filters.slot_type !== 'all') query.append('slot_type', filters.slot_type);
    if (filters.category && filters.category !== 'all') query.append('category', filters.category);
    if (filters.color && filters.color !== 'all') query.append('color', filters.color);
    if (filters.search) query.append('search', filters.search);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/wardrobe/items/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch wardrobe items' };
    }
    return { success: true, results: data.results || data || [], count: data.count || (Array.isArray(data) ? data.length : 0) };
  } catch (err) {
    return { success: false, error: 'Network error fetching wardrobe items' };
  }
}

/**
 * Digital Wardrobe API: Upload new garment photo with background removal & auto-tagging.
 */
export async function uploadWardrobeItem(token, payload) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let body;
    if (payload instanceof FormData) {
      body = payload;
    } else {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(payload);
    }

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/items/`, {
      method: 'POST',
      headers,
      body,
    });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to process wardrobe upload' };
    }
    return { success: true, item: data, ...data };
  } catch (err) {
    return { success: false, error: 'Network error uploading wardrobe item' };
  }
}

export const addWardrobeItem = uploadWardrobeItem;

/**
 * Digital Wardrobe API: Update tags on a wardrobe piece (marks user_verified = true).
 */
export async function updateWardrobeItem(token, itemId, patchData) {
  try {
    const headers = {
      'Content-Type': 'application/json',
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/items/${itemId}/`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(patchData),
    });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to update tags' };
    }
    return { success: true, item: data };
  } catch (err) {
    return { success: false, error: 'Network error updating wardrobe item' };
  }
}

/**
 * Digital Wardrobe API: Delete piece from wardrobe (removes DB row & stored files).
 */
export async function deleteWardrobeItem(token, itemId) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/items/${itemId}/`, {
      method: 'DELETE',
      headers,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return { success: false, error: data.error || 'Failed to delete wardrobe item' };
    }
    return { success: true };
  } catch (err) {
    return { success: false, error: 'Network error deleting wardrobe item' };
  }
}

/**
 * Digital Wardrobe API: Toggle between the studio render and original photo.
 */
export async function toggleWardrobeDisplayMode(token, itemId, mode = null) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const body = mode ? JSON.stringify({ mode }) : JSON.stringify({});
    const response = await fetch(`${API_BASE_URL}/api/wardrobe/items/${itemId}/toggle-display/`, {
      method: 'POST',
      headers,
      body,
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to toggle display mode' };
    }
    return { success: true, item: data };
  } catch (err) {
    return { success: false, error: 'Network error toggling wardrobe display mode' };
  }
}

/**
 * Digital Wardrobe API: Re-run studio rendering on the original photo.
 */
export async function reprocessWardrobeItem(token, itemId) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/items/${itemId}/reprocess/`, {
      method: 'POST',
      headers,
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to reprocess studio render' };
    }
    return { success: true, item: data };
  } catch (err) {
    return { success: false, error: 'Network error reprocessing studio render' };
  }
}

/**
 * Digital Wardrobe API: Idempotently import delivered, non-returned customer purchases.
 */
export async function importOrdersToWardrobe(token) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/import-orders/`, {
      method: 'POST',
      headers,
    });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to import orders' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error importing orders' };
  }
}

/**
 * Digital Wardrobe API: Complete this look with matching catalog products.
 * Supports slot filtering, slot tabs, and pagination for 'Show more'.
 */
export async function getCompleteLook(token, itemId, budget = 10000, slot = null, offset = 0, limit = 6) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let url = `${API_BASE_URL}/api/wardrobe/items/${itemId}/complete-look/?budget=${budget}&offset=${offset}&limit=${limit}`;
    if (slot && slot !== 'all') {
      url += `&slot=${encodeURIComponent(slot)}`;
    }

    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || 'Failed to generate complete look pairings' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error retrieving complete look pairings' };
  }
}

/**
 * Digital Wardrobe API: Get wardrobe matches for a store product with 'Show more' pagination.
 */
export async function getProductWardrobeMatches(token, productKey, offset = 0, limit = 6) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/products/${productKey}/wardrobe-matches/?offset=${offset}&limit=${limit}`, {
      headers,
    });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || 'Failed to fetch matches' };
    }
    return {
      success: true,
      matches: data.matches || [],
      total_count: data.total_count || (data.matches || []).length,
      has_more: Boolean(data.has_more)
    };
  } catch (err) {
    return { success: false, error: 'Network error checking product wardrobe matches' };
  }
}

/**
 * Digital Wardrobe API: Confirm and save selected parsed items from multi-garment photo.
 */
export async function confirmParsedItems(token, pieces) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/items/confirm-parsed-items/`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ pieces }),
    });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || 'Failed to confirm pieces' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error confirming wardrobe pieces' };
  }
}

/**
 * Digital Wardrobe API: Fetch saved wardrobe outfits.
 */
export async function getWardrobeOutfits(token) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/outfits/`, { headers });
    const data = await response.json();
    return { success: response.ok, outfits: data.results || data || [] };
  } catch (err) {
    return { success: false, outfits: [] };
  }
}

/**
 * Digital Wardrobe API: Save outfit crafted from wardrobe items.
 */
export async function saveWardrobeOutfit(token, outfitPayload) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/outfits/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(outfitPayload),
    });
    const data = await response.json();
    return { success: response.ok, outfit: data };
  } catch (err) {
    return { success: false, error: 'Network error saving outfit' };
  }
}

/**
 * Digital Wardrobe API: Fetch customer collections.
 */
export async function getWardrobeCollections(token) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/collections/`, { headers });
    const data = await response.json();
    return { success: response.ok, collections: data.results || data || [] };
  } catch (err) {
    return { success: false, collections: [] };
  }
}

/**
 * Digital Wardrobe API: Create customer collection.
 */
export async function createWardrobeCollection(token, collectionPayload) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${API_BASE_URL}/api/wardrobe/collections/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(collectionPayload),
    });
    const data = await response.json();
    return { success: response.ok, collection: data };
  } catch (err) {
    return { success: false, error: 'Network error creating collection' };
  }
}
