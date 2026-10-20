const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

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
export async function registerCustomer({ fullName, email, phone, password, city, state }) {
  try {
    const payload = {
      full_name: fullName.trim(),
      email: email.trim(),
      password,
    };

    if (phone) {
      const parsedPhone = parseInt(phone.replace(/\D/g, ''), 10);
      if (!isNaN(parsedPhone)) {
        payload.phone = parsedPhone;
      }
    }
    if (city) payload.city = city.trim();
    if (state) payload.state = state.trim();

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

/**
 * Fetch all categories with product counts.
 */
export async function getCategories() {
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
}

/**
 * Fetch products list with optional filters, search, sorting and pagination.
 */
export async function getProducts(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.category) query.append('category', params.category);
    if (params.search) query.append('search', params.search);
    if (params.min_price) query.append('min_price', params.min_price);
    if (params.max_price) query.append('max_price', params.max_price);
    if (params.in_stock !== undefined && params.in_stock !== '') query.append('in_stock', params.in_stock);
    if (params.sort) query.append('sort', params.sort);
    if (params.page) query.append('page', params.page);
    if (params.page_size) query.append('page_size', params.page_size);

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

/**
 * Fetch products grouped according to their actual database categories.
 */
export async function getGroupedProducts() {
  try {
    let response = await fetch(`${API_BASE_URL}/api/warehouse/products/grouped/`);
    if (!response.ok) {
      response = await fetch(`${API_BASE_URL}/api/catalog/grouped-products/`);
    }

    if (response.ok) {
      const data = await response.json();
      const categoriesList = Array.isArray(data) ? data : (data.categories || []);
      if (categoriesList.length > 0) {
        return {
          success: true,
          categories: categoriesList,
          count: Array.isArray(data) ? data.length : (data.count || categoriesList.length)
        };
      }
    }

    // Fallback: Fetch products from Django catalog API & group by category
    const prodsRes = await getProducts({ page_size: 500 });
    if (prodsRes.success && prodsRes.products.length > 0) {
      const groupedMap = {};
      prodsRes.products.forEach((prod) => {
        const catName = prod.category_name || 'General Catalog';
        const catId = prod.category_id || catName.toLowerCase().replace(/\s+/g, '-');
        if (!groupedMap[catId]) {
          groupedMap[catId] = {
            category_id: catId,
            category_name: catName,
            description: `Database products in ${catName}`,
            product_count: 0,
            products: []
          };
        }
        groupedMap[catId].products.push(prod);
        groupedMap[catId].product_count += 1;
      });
      const categoriesList = Object.values(groupedMap);
      return {
        success: true,
        categories: categoriesList,
        count: categoriesList.length
      };
    }

    return { success: false, error: 'Failed to fetch database products' };
  } catch (err) {
    return { success: false, error: 'Network error fetching grouped products' };
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
 * Sends validated form fields to Django; Django validates and persists.
 * Returns the updated product on success, or validation errors on failure.
 */
export async function updateWarehouseProduct(productId, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/warehouse/products/${productId}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
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
export async function getNewArrivals(limit = 10) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/new-arrivals/?limit=${limit}`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch new arrivals' };
    }
    return { success: true, products: data.results || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching new arrivals' };
  }
}

/**
 * Fetch Trending Products.
 */
export async function getTrending(limit = 10) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/trending/?limit=${limit}`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch trending products' };
    }
    return { success: true, products: data.results || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching trending products' };
  }
}

/**
 * Fetch Sale / Discounted Products.
 */
export async function getSale(limit = 10) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/catalog/sale/?limit=${limit}`);
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to fetch sale products' };
    }
    return { success: true, products: data.results || [] };
  } catch (err) {
    return { success: false, error: 'Network error fetching sale products' };
  }
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
 * Fetch system staff members (Warehouse Managers, Delivery Partners) with filters.
 */
export async function getStaffList(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.role && params.role !== 'ALL') query.append('role', params.role);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);

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
      employees: data.employees || [],
      warehouses: data.warehouses || [],
    };
  } catch (err) {
    return { success: false, error: 'Network error fetching staff list.' };
  }
}

/**
 * Create a new staff member (Warehouse Manager or Delivery Partner).
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
        ? Object.entries(data.errors).map(([f, m]) => `${f}: ${m}`).join(', ')
        : (data.detail || (typeof data === 'object' && Object.values(data)[0] && (Array.isArray(Object.values(data)[0]) ? Object.values(data)[0][0] : Object.values(data)[0])) || 'Failed to create staff member.');
      return { success: false, error: errorMsg };
    }
    return { success: true, message: data.message, employee: data.employee };
  } catch (err) {
    return { success: false, error: 'Network error creating staff member.' };
  }
}

/**
 * Toggle staff active status (activate / deactivate).
 */
export async function toggleStaffStatus(token, employeeId, targetStatus = null) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const body = targetStatus !== null ? JSON.stringify({ is_active: targetStatus }) : undefined;

    const response = await fetch(`${API_BASE_URL}/api/admin/staff/${employeeId}/toggle-status/`, {
      method: 'PATCH',
      headers,
      body,
    });
    const data = await response.json();
    if (!response.ok) {
      return { success: false, error: data.detail || 'Failed to toggle staff status.' };
    }
    return { success: true, message: data.message, employee: data.employee };
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
 */
export async function getDemandPredictionAnalytics(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.demand_level && params.demand_level !== 'ALL') query.append('demand_level', params.demand_level);
    if (params.category && params.category !== 'ALL') query.append('category', params.category);

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
 * Fetch Revenue Forecasting analytics (Admin Analysis feature).
 * Consumes the existing predicted-sales output and returns expected revenue
 * (expected_revenue = predicted_sales x selling_price) calculated in Django.
 *
 * @param {string} token  - Bearer token (Admin only)
 * @param {Object} params - Optional filters: { search, category, demand_level }
 */
export async function getRevenueForecast(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.category && params.category !== 'ALL') query.append('category', params.category);
    if (params.demand_level && params.demand_level !== 'ALL') query.append('demand_level', params.demand_level);

    const qs = query.toString();
    const url = `${API_BASE_URL}/api/revenue-forecasting/${qs ? '?' + qs : ''}`;
    const response = await fetch(url, { headers });
    const data = await response.json();

    if (!response.ok) {
      return { success: false, error: data.error || data.detail || 'Failed to fetch revenue forecast.' };
    }
    return { success: true, ...data };
  } catch (err) {
    return { success: false, error: 'Network error fetching revenue forecast.' };
  }
}

/* ==========================================================================
   STOCK TO BE ORDERED API HELPERS  (Warehouse Manager only)
   ========================================================================== */

/**
 * Fetch next-month Stock to Be Ordered forecast via OLS regression pipeline.
 * Access: Warehouse Manager only.
 *
 * @param {string} token  - Bearer token
 * @param {Object} params - Optional filters: { search, category, status }
 */
export async function getStockToBeOrdered(token, params = {}) {
  try {
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.category && params.category !== 'ALL') query.append('category', params.category);
    if (params.status && params.status !== 'ALL') query.append('status', params.status);

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
