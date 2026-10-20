import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../auth/AuthContext';
import {
  getWishlist,
  addToWishlist as apiAddToWishlist,
  removeFromWishlist as apiRemoveFromWishlist,
  getBag,
  addToBag as apiAddToBag,
  updateBagQuantity as apiUpdateBagQuantity,
  removeFromBag as apiRemoveFromBag,
  clearBag as apiClearBag,
  getProductDetail as apiGetProductDetail,
} from '../services/api';

const CustomerContext = createContext(null);

export function CustomerProvider({ children }) {
  const { token, isAuthenticated, role } = useAuth();
  const isCustomer = isAuthenticated && role === 'CUSTOMER';

  // Wishlist state
  const [wishlistItems, setWishlistItems] = useState([]);
  const [wishlistLoading, setWishlistLoading] = useState(false);

  // Bag / Cart state
  const [bagItems, setBagItems] = useState([]);
  const [totalItems, setTotalItems] = useState(0);
  const [subtotal, setSubtotal] = useState(0);
  const [total, setTotal] = useState(0);
  const [bagLoading, setBagLoading] = useState(false);

  // Micro-animation triggers for navbar badges
  const [wishlistBounced, setWishlistBounced] = useState(false);
  const [bagBounced, setBagBounced] = useState(false);

  // Product Detail Modal state
  const [activeModalProduct, setActiveModalProduct] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);

  // Toast feedback state
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'success', duration = 3200) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 7);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Quick lookup set for wishlisted product IDs
  const wishlistIds = useMemo(() => {
    return new Set(wishlistItems.map((item) => String(item.product_id)));
  }, [wishlistItems]);

  const isWishlisted = useCallback(
    (productId) => {
      if (!productId) return false;
      return wishlistIds.has(String(productId));
    },
    [wishlistIds]
  );

  // Fetch initial customer data (Wishlist & Bag)
  const fetchCustomerData = useCallback(async () => {
    if (!isCustomer || !token) {
      setWishlistItems([]);
      setBagItems([]);
      setTotalItems(0);
      setSubtotal(0);
      setTotal(0);
      return;
    }

    setWishlistLoading(true);
    setBagLoading(true);

    try {
      const [wishlistRes, bagRes] = await Promise.all([
        getWishlist(token),
        getBag(token),
      ]);

      if (wishlistRes.success) {
        setWishlistItems(wishlistRes.items);
      }
      if (bagRes.success) {
        setBagItems(bagRes.items);
        setTotalItems(bagRes.totalItems);
        setSubtotal(bagRes.subtotal);
        setTotal(bagRes.total);
      }
    } catch (err) {
      console.error('Failed to load customer cart/wishlist', err);
    } finally {
      setWishlistLoading(false);
      setBagLoading(false);
    }
  }, [isCustomer, token]);

  useEffect(() => {
    fetchCustomerData();
  }, [fetchCustomerData]);

  // Wishlist Actions
  const toggleWishlist = useCallback(
    async (product) => {
      if (!token) {
        addToast('Please sign in to save items to your wishlist', 'info');
        return;
      }
      const pId = String(product.product_id || product.id);
      const currentlyWishlisted = wishlistIds.has(pId);

      // Trigger navbar badge micro-animation
      setWishlistBounced(true);
      setTimeout(() => setWishlistBounced(false), 600);

      if (currentlyWishlisted) {
        // Optimistic removal
        const prev = [...wishlistItems];
        setWishlistItems((current) => current.filter((item) => String(item.product_id) !== pId));
        const res = await apiRemoveFromWishlist(token, pId);
        if (res.success) {
          addToast(`Removed "${product.name || 'item'}" from your wishlist`, 'info');
        } else {
          setWishlistItems(prev);
          addToast(res.error || 'Failed to remove from wishlist', 'error');
        }
      } else {
        // Optimistic add
        const dummyItem = {
          id: 'temp-' + Date.now(),
          product_id: pId,
          product_name: product.name,
          product_slug: product.slug,
          category_name: product.category?.name || product.category_name,
          base_price: product.base_price,
          sale_price: product.sale_price,
          is_on_sale: product.is_on_sale,
          primary_image: product.primary_image || (product.images && product.images[0]?.image_url),
          total_stock: product.total_stock,
          is_in_stock: product.is_in_stock !== false,
          created_at: new Date().toISOString(),
        };
        setWishlistItems((current) => [dummyItem, ...current]);
        const res = await apiAddToWishlist(token, pId);
        if (res.success) {
          addToast(`Added "${product.name || 'item'}" to your wishlist!`, 'success');
          // Update with real server object if needed
          if (res.item) {
            setWishlistItems((current) =>
              current.map((item) => (String(item.product_id) === pId ? res.item : item))
            );
          }
        } else {
          setWishlistItems((current) => current.filter((item) => String(item.product_id) !== pId));
          addToast(res.error || 'Failed to add to wishlist', 'error');
        }
      }
    },
    [token, wishlistIds, wishlistItems, addToast]
  );

  // Bag Actions
  const addToBag = useCallback(
    async (product, quantity = 1) => {
      if (!token) {
        addToast('Please sign in to add items to your shopping bag', 'info');
        return { success: false };
      }
      const pId = String(product.product_id || product.id);

      setBagBounced(true);
      setTimeout(() => setBagBounced(false), 700);

      const res = await apiAddToBag(token, pId, quantity);
      if (res.success) {
        if (res.cart) {
          setBagItems(res.cart.items || []);
          setTotalItems(res.cart.total_items || 0);
          setSubtotal(res.cart.subtotal || 0);
          setTotal(res.cart.total || 0);
        } else {
          // Refetch fresh bag
          const freshBag = await getBag(token);
          if (freshBag.success) {
            setBagItems(freshBag.items);
            setTotalItems(freshBag.totalItems);
            setSubtotal(freshBag.subtotal);
            setTotal(freshBag.total);
          }
        }
        addToast(`Added "${product.name || 'item'}" to your bag!`, 'success');
        return { success: true };
      } else {
        addToast(res.error || 'Could not add to bag. Check stock availability.', 'error');
        return { success: false, error: res.error };
      }
    },
    [token, addToast]
  );

  const updateBagQuantity = useCallback(
    async (productId, quantity) => {
      if (!token) return;
      const res = await apiUpdateBagQuantity(token, productId, quantity);
      if (res.success) {
        if (res.cart) {
          setBagItems(res.cart.items || []);
          setTotalItems(res.cart.total_items || 0);
          setSubtotal(res.cart.subtotal || 0);
          setTotal(res.cart.total || 0);
        } else {
          const freshBag = await getBag(token);
          if (freshBag.success) {
            setBagItems(freshBag.items);
            setTotalItems(freshBag.totalItems);
            setSubtotal(freshBag.subtotal);
            setTotal(freshBag.total);
          }
        }
      } else {
        addToast(res.error || 'Could not update quantity.', 'error');
      }
    },
    [token, addToast]
  );

  const removeFromBag = useCallback(
    async (productId) => {
      if (!token) return;
      const res = await apiRemoveFromBag(token, productId);
      if (res.success) {
        if (res.cart) {
          setBagItems(res.cart.items || []);
          setTotalItems(res.cart.total_items || 0);
          setSubtotal(res.cart.subtotal || 0);
          setTotal(res.cart.total || 0);
        } else {
          const freshBag = await getBag(token);
          if (freshBag.success) {
            setBagItems(freshBag.items);
            setTotalItems(freshBag.totalItems);
            setSubtotal(freshBag.subtotal);
            setTotal(freshBag.total);
          }
        }
        addToast('Item removed from your bag', 'info');
      } else {
        addToast(res.error || 'Could not remove item from bag', 'error');
      }
    },
    [token, addToast]
  );

  const clearBag = useCallback(async () => {
    if (!token) return;
    const res = await apiClearBag(token);
    if (res.success) {
      setBagItems([]);
      setTotalItems(0);
      setSubtotal(0);
      setTotal(0);
      addToast('Shopping bag cleared', 'info');
    } else {
      addToast(res.error || 'Failed to clear bag', 'error');
    }
  }, [token, addToast]);

  // Product Details Modal
  const openProductDetail = useCallback(async (productOrId) => {
    if (!productOrId) return;
    const productId = typeof productOrId === 'object' ? productOrId.product_id || productOrId.id : productOrId;
    if (typeof productOrId === 'object') {
      setActiveModalProduct(productOrId);
    } else {
      setActiveModalProduct({ product_id: productId, name: 'Loading...' });
    }
    setModalLoading(true);
    const res = await apiGetProductDetail(productId);
    if (res.success && res.product) {
      setActiveModalProduct(res.product);
    }
    setModalLoading(false);
  }, []);

  const refreshProductDetail = useCallback(async (productId) => {
    if (!productId) return;
    const res = await apiGetProductDetail(productId);
    if (res.success && res.product) {
      setActiveModalProduct(res.product);
    }
  }, []);

  const closeProductDetail = useCallback(() => {
    setActiveModalProduct(null);
  }, []);

  const value = {
    wishlistItems,
    wishlistLoading,
    wishlistIds,
    isWishlisted,
    toggleWishlist,
    wishlistBounced,

    bagItems,
    totalItems,
    subtotal,
    total,
    bagLoading,
    addToBag,
    updateBagQuantity,
    removeFromBag,
    clearBag,
    bagBounced,

    activeModalProduct,
    modalLoading,
    openProductDetail,
    refreshProductDetail,
    closeProductDetail,

    toasts,
    addToast,
    removeToast,

    refreshCustomerData: fetchCustomerData,
  };

  return <CustomerContext.Provider value={value}>{children}</CustomerContext.Provider>;
}

export function useCustomer() {
  const context = useContext(CustomerContext);
  if (!context) {
    throw new Error('useCustomer must be used within a CustomerProvider');
  }
  return context;
}
