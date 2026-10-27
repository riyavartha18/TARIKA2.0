import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
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

const round2 = (value) => Math.round((Number(value) || 0) * 100) / 100;

// Minimal optimistic cart line built from a server summary's own lines, so a
// just-added product paints immediately instead of waiting for the response.
function optimisticBaseLine(items, product, pId) {
  const template = items.find(
    (i) => i.product && String(i.product.product_id) === String(pId)
  );
  const source = template ? template.product : (items[0] && items[0].product) || {};
  const unitPrice = Number(
    product.sale_price ?? product.selling_price ?? product.discount_price ??
    source.selling_price ?? source.sale_price
  ) || 0;
  return {
    id: 'temp-' + pId,
    product_id: String(pId),
    product_name: product.product_name || product.name || source.product_name || null,
    category_name: product.category_name || source.category_name || null,
    primary_image: product.primary_image || product.image || source.primary_image || null,
    image: product.image || product.primary_image || source.image || null,
    product: { ...source, ...product, product_id: String(pId) },
    quantity: 0,
    unit_price: unitPrice,
    line_total: 0,
  };
}

export function CustomerProvider({ children }) {
  const { token, isAuthenticated, role } = useAuth();
  const isCustomer = isAuthenticated && role === 'CUSTOMER';

  // Wishlist state
  const [wishlistItems, setWishlistItems] = useState([]);
  const [wishlistLoading, setWishlistLoading] = useState(false);
  const [wishlistError, setWishlistError] = useState('');

  // Bag / Cart state
  const [bagItems, setBagItems] = useState([]);
  const [totalItems, setTotalItems] = useState(0);
  const [subtotal, setSubtotal] = useState(0);
  const [total, setTotal] = useState(0);
  const [bagLoading, setBagLoading] = useState(false);
  const [bagError, setBagError] = useState('');

  // Micro-animation triggers for navbar badges
  const [wishlistBounced, setWishlistBounced] = useState(false);
  const [bagBounced, setBagBounced] = useState(false);

  // Cart sync internals (optimistic UI + debounced persistence).
  // Bump on every locally-driven change so an older server snapshot can never
  // overwrite a newer local state (rapid +/- clicks, overlapping adds).
  const bagSeq = useRef(0);
  // product_id -> { qty, seq } optimistic delta applied locally but not yet
  // confirmed by the server; folded into older server summaries until the add
  // resolves (only deltas created at or after that request started apply).
  const pendingAddDeltas = useRef(new Map());
  // product_id -> debounce timer for the latest desired quantity.
  const qtyTimers = useRef(new Map());
  const QTY_DEBOUNCE_MS = 400;

  // Mirrors wishlist state inside async actions, so an action started earlier
  // can still revert to the true latest list after concurrent changes.
  const wishlistStateRef = useRef([]);
  useEffect(() => {
    wishlistStateRef.current = wishlistItems;
  }, [wishlistItems]);

  // Mirrors cart lines for synchronous reads inside stable callbacks.
  const bagItemsRef = useRef([]);
  useEffect(() => {
    bagItemsRef.current = bagItems;
  }, [bagItems]);

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

  // ---- Cart sync helpers (optimistic UI + confirmed server snapshots) -----
  const bumpBagSeq = useCallback(() => {
    bagSeq.current += 1;
    return bagSeq.current;
  }, []);

  const computeBagTotals = (items) => {
    const totalItems = items.reduce((sum, item) => sum + (Number(item.quantity) || 0), 0);
    const subtotal = items.reduce(
      (sum, item) => sum + (Number(item.unit_price ?? item.selling_price) || 0) * (Number(item.quantity) || 0),
      0
    );
    return { totalItems, subtotal: round2(subtotal), total: round2(subtotal) };
  };

  // Apply a backend cart summary. `minSeq` is the request's start marker: a
  // response for an older operation than the current local state is dropped
  // outright; otherwise still-unconfirmed optimistic deltas are folded on top
  // so rapid clicks between request start and response are never lost.
  const applyCartSummary = useCallback((cart, minSeq, foldDeltas = true) => {
    if (!cart) return;
    if (minSeq < bagSeq.current) return;
    let items = (cart.items || []).map((item) => ({ ...item }));
    if (foldDeltas) {
      pendingAddDeltas.current.forEach(({ qty, seq }, pId) => {
        // Only fold deltas that were still pending when this request began;
        // newer optimistic values are already reflected in `minSeq`.
        if (seq >= minSeq) {
          const key = String(pId);
          const existing = items.find((i) => String(i.product_id) === key);
          if (existing) {
            existing.quantity = (Number(existing.quantity) || 0) + qty;
            existing.line_total = round2(
              (Number(existing.unit_price) || 0) * existing.quantity
            );
          } else if (qty > 0) {
            items = [{ ...optimisticBaseLine(items, {}, key), quantity: qty }, ...items];
          }
        }
      });
    }
    const totals = computeBagTotals(items);
    setBagItems(items);
    setTotalItems(totals.totalItems);
    setSubtotal(totals.subtotal);
    setTotal(totals.total);
  }, []);

  // Apply a plain database snapshot (initial load / reconciliation): pending
  // deltas describe the same optimistic values the snapshot already reflects,
  // so they are dropped and the database state wins.
  const applyCartSnapshot = useCallback((payload) => {
    pendingAddDeltas.current.clear();
    applyCartSummary(payload, 0, false);
  }, [applyCartSummary]);

  const applyCartTotals = useCallback((items) => {
    const totals = computeBagTotals(items);
    setTotalItems(totals.totalItems);
    setSubtotal(totals.subtotal);
    setTotal(totals.total);
  }, []);

  // Exact inverse of the optimistic add: restore the previous quantity (or
  // drop the temporary line) for the add that the backend rejected.
  const revertAddedLine = useCallback((current, pId, addQty, prevItems) => {
    const prevEntry = prevItems.find((item) => String(item.product_id) === pId);
    if (prevEntry) {
      return current.map((item) =>
        String(item.product_id) === pId
          ? { ...item, quantity: prevEntry.quantity, line_total: prevEntry.line_total }
          : item
      );
    }
    return current.filter((item) => String(item.product_id) !== pId);
  }, []);

  // Paint a new line quantity (and totals) synchronously, before the DB write.
  const applyQuantityLocally = useCallback((pId, targetQty) => {
    bagSeq.current += 1;
    const nextItems = bagItemsRef.current.map((item) =>
      String(item.product_id) === String(pId)
        ? {
            ...item,
            quantity: targetQty,
            line_total: round2((Number(item.unit_price) || 0) * targetQty),
          }
        : item
    );
    setBagItems(nextItems);
    applyCartTotals(nextItems);
  }, [applyCartTotals]);

  // Persist one line's final debounced quantity. The target already bakes in
  // any optimistic add delta for that line, so the pending delta is cleared
  // when the request starts and the response can be applied as-is.
  const flushQuantity = useCallback(
    async (pId, targetQty) => {
      pendingAddDeltas.current.delete(pId);
      const startSeq = bagSeq.current;
      const res = await apiUpdateBagQuantity(token, pId, targetQty);
      if (res.success) {
        if (res.cart) {
          applyCartSummary(res.cart, startSeq);
        } else {
          const freshBag = await getBag(token);
          if (freshBag.success) applyCartSnapshot(freshBag);
        }
      } else {
        // Server refused (stock, ownership): re-read the cart so the UI
        // matches the database rows rather than an invented value.
        const freshBag = await getBag(token);
        if (freshBag.success) applyCartSnapshot(freshBag);
        addToast(res.error || 'Could not update quantity.', 'error');
      }
    },
    [token, applyCartSummary, applyCartSnapshot, addToast]
  );

  // Re-read the cart from Neon after a failed write, so the UI is reconciled
  // with what is actually persisted.
  const reconcileBagFromServer = useCallback(async () => {
    const seq = bagSeq.current;
    const freshBag = await getBag(token);
    if (freshBag.success && seq === bagSeq.current) applyCartSnapshot(freshBag);
  }, [token, applyCartSnapshot]);

  // Never leave debounce timers running after unmount.
  useEffect(() => {
    const timers = qtyTimers.current;
    return () => {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    };
  }, []);

  // Fetch initial customer data (Wishlist & Bag)
  const fetchCustomerData = useCallback(async () => {
    if (!isCustomer || !token) {
      setWishlistItems([]);
      bumpBagSeq();
      setBagItems([]);
      setTotalItems(0);
      setSubtotal(0);
      setTotal(0);
      setWishlistError('');
      setBagError('');
      return;
    }

    setWishlistLoading(true);
    setBagLoading(true);
    setWishlistError('');
    setBagError('');

    try {
      const [wishlistRes, bagRes] = await Promise.all([
        getWishlist(token),
        getBag(token),
      ]);

      if (wishlistRes.success) {
        setWishlistItems(wishlistRes.items);
      } else {
        // Keep the page usable: show the failure instead of an empty wishlist.
        setWishlistError(wishlistRes.error || 'Could not load your wishlist.');
      }
      if (bagRes.success) {
        // Plain server snapshot on initial load.
        applyCartSnapshot(bagRes);
      } else {
        setBagError(bagRes.error || 'Could not load your shopping bag.');
      }
    } catch (err) {
      console.error('Failed to load customer cart/wishlist', err);
      setWishlistError('Could not load your wishlist. Please check your connection.');
      setBagError('Could not load your shopping bag. Please check your connection.');
    } finally {
      setWishlistLoading(false);
      setBagLoading(false);
    }
  }, [isCustomer, token, applyCartSnapshot, bumpBagSeq]);

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
        // Optimistic removal; the badge and card state update before the
        // round trip completes and the row is deleted server-side.
        const listBefore = wishlistStateRef.current;
        const listAfter = listBefore.filter((item) => String(item.product_id) !== pId);
        wishlistStateRef.current = listAfter;
        setWishlistItems(listAfter);
        const res = await apiRemoveFromWishlist(token, pId);
        if (!res.success) {
          // Restore the full previous list (re-checking membership so a
          // concurrent add is never duplicated).
          wishlistStateRef.current = wishlistStateRef.current.some(
            (item) => String(item.product_id) === pId
          )
            ? wishlistStateRef.current
            : [listBefore.find((item) => String(item.product_id) === pId), ...wishlistStateRef.current];
          setWishlistItems(wishlistStateRef.current);
          addToast(res.error || 'Failed to remove from wishlist', 'error');
        }
      } else {
        // Optimistic add from the card's own data, replaced by the real
        // server row when the insert into public.wishlist confirms.
        const tempItem = {
          id: 'temp-' + Date.now(),
          product_id: pId,
          product_name: product.product_name || product.name,
          category_name: product.category?.name || product.category_name,
          base_price: product.base_price,
          selling_price: product.sale_price ?? product.selling_price,
          sale_price: product.sale_price ?? product.selling_price,
          primary_image: product.primary_image || product.image,
          image: product.image || product.primary_image,
          total_stock: product.total_stock,
          in_stock: product.in_stock !== false,
          product: { ...product, product_id: pId },
        };
        wishlistStateRef.current = [tempItem, ...wishlistStateRef.current];
        setWishlistItems(wishlistStateRef.current);
        const res = await apiAddToWishlist(token, pId);
        if (res.success) {
          if (res.item) {
            wishlistStateRef.current = wishlistStateRef.current.map((item) =>
              String(item.product_id) === pId ? res.item : item
            );
            setWishlistItems(wishlistStateRef.current);
          }
        } else {
          wishlistStateRef.current = wishlistStateRef.current.filter(
            (item) => String(item.product_id) !== pId
          );
          setWishlistItems(wishlistStateRef.current);
          addToast(res.error || 'Failed to add to wishlist', 'error');
        }
      }
    },
    [token, wishlistIds, addToast]
  );

  // Bag Actions
  // The button/line state and navbar count update in the same paint as the
  // click; the Neon `public.cart` write is confirmed in the background and its
  // authoritative summary reconciles the optimistic view.
  const addToBag = useCallback(
    async (product, quantity = 1) => {
      if (!token) {
        addToast('Please sign in to add items to your shopping bag', 'info');
        return { success: false };
      }
      const pId = String(product.product_id || product.id);
      const addQty = Math.max(1, Number(quantity) || 1);

      setBagBounced(true);
      setTimeout(() => setBagBounced(false), 700);

      const prevItems = bagItemsRef.current;
      const startSeq = bagSeq.current;
      const entry = prevItems.find((item) => String(item.product_id) === pId);
      if (entry) {
        applyQuantityLocally(pId, (Number(entry.quantity) || 0) + addQty);
      } else {
        const tempLine = {
          ...optimisticBaseLine(prevItems, product, pId),
          quantity: addQty,
          line_total: round2((Number(optimisticBaseLine(prevItems, product, pId).unit_price) || 0) * addQty),
        };
        bagSeq.current += 1;
        setBagItems([tempLine, ...prevItems]);
        applyCartTotals([tempLine, ...prevItems]);
      }

      // Register the optimistic delta after the bump above, so this request's
      // own summary (startSeq) still folds it.
      const prior = pendingAddDeltas.current.get(pId);
      pendingAddDeltas.current.set(pId, {
        qty: (prior ? prior.qty : 0) + addQty,
        seq: prior ? prior.seq : startSeq,
      });

      const res = await apiAddToBag(token, pId, addQty);
      if (res.success) {
        if (res.cart) {
          applyCartSummary(res.cart, startSeq);
        } else {
          const freshBag = await getBag(token);
          if (freshBag.success) applyCartSnapshot(freshBag);
        }
        return { success: true };
      }

      // Revert the optimistic line exactly (the row never reached the cart
      // table) and surface the backend's reason, e.g. a stock rejection.
      const pending = pendingAddDeltas.current.get(pId);
      if (pending) {
        const remaining = pending.qty - addQty;
        if (remaining > 0) pendingAddDeltas.current.set(pId, { ...pending, qty: remaining });
        else pendingAddDeltas.current.delete(pId);
      }
      bagSeq.current += 1;
      const reverted = revertAddedLine(bagItemsRef.current, pId, addQty, prevItems);
      setBagItems(reverted);
      applyCartTotals(reverted);
      addToast(res.error || 'Could not add to bag. Check stock availability.', 'error');
      return { success: false, error: res.error };
    },
    [token, addToast, applyCartSummary, applyCartSnapshot, applyQuantityLocally, applyCartTotals, revertAddedLine]
  );

  // Quantity changes are optimistically immediate; persistence is debounced
  // so a burst of +/- clicks collapses into one PATCH carrying the final
  // quantity, and the bagSeq watermark makes older responses impossible to
  // overwrite newer state.
  const updateBagQuantity = useCallback(
    async (productId, quantity, { immediate = false } = {}) => {
      if (!token) return;
      const pId = String(productId);
      const currentLine = bagItemsRef.current.find(
        (item) => String(item.product_id) === pId
      );
      if (!currentLine) return;

      const maxStock = currentLine.available_stock == null
        ? null
        : Number(currentLine.available_stock);
      let target = Math.max(1, Math.round(Number(quantity) || 1));
      if (maxStock !== null && !Number.isNaN(maxStock) && target > maxStock) {
        target = maxStock;
      }

      applyQuantityLocally(pId, target);

      const existing = qtyTimers.current.get(pId);
      if (existing) clearTimeout(existing);

      if (immediate) {
        qtyTimers.current.delete(pId);
        await flushQuantity(pId, target);
        return;
      }
      qtyTimers.current.set(
        pId,
        setTimeout(() => {
          qtyTimers.current.delete(pId);
          flushQuantity(pId, target);
        }, QTY_DEBOUNCE_MS)
      );
    },
    [token, addToast, flushQuantity, applyQuantityLocally]
  );

  const removeFromBag = useCallback(
    async (productId) => {
      if (!token) return;
      const pId = String(productId);
      // Cancel any pending quantity persistence for the removed line.
      const timer = qtyTimers.current.get(pId);
      if (timer) {
        clearTimeout(timer);
        qtyTimers.current.delete(pId);
      }
      pendingAddDeltas.current.delete(pId);

      // Optimistic removal paints instantly.
      const prevItems = bagItemsRef.current;
      bagSeq.current += 1;
      const nextItems = prevItems.filter((item) => String(item.product_id) !== pId);
      setBagItems(nextItems);
      applyCartTotals(nextItems);

      const res = await apiRemoveFromBag(token, pId);
      if (res.success) {
        if (res.cart) applyCartSummary(res.cart, 0);
        addToast('Item removed from your bag', 'info');
      } else {
        // Reconcile with the database instead of blindly re-inserting, so the
        // UI always ends up matching the real cart rows.
        await reconcileBagFromServer();
        addToast(res.error || 'Could not remove item from bag', 'error');
      }
    },
    [token, addToast, applyCartSummary, applyCartTotals, reconcileBagFromServer]
  );

  // Empty the bag in the UI without a request: used right after a successful
  // checkout, where the backend transaction has already deleted exactly the
  // ordered rows in Neon.
  const clearCartLocal = useCallback(() => {
    qtyTimers.current.forEach((timer) => clearTimeout(timer));
    qtyTimers.current.clear();
    pendingAddDeltas.current.clear();
    bagSeq.current += 1;
    setBagItems([]);
    setTotalItems(0);
    setSubtotal(0);
    setTotal(0);
  }, []);

  const clearBag = useCallback(async () => {
    if (!token) return;
    clearCartLocal();
    const res = await apiClearBag(token);
    if (!res.success) {
      await reconcileBagFromServer();
      addToast(res.error || 'Failed to clear bag', 'error');
    } else {
      addToast('Shopping bag cleared', 'info');
    }
  }, [token, addToast, clearCartLocal, reconcileBagFromServer]);

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
    wishlistError,
    wishlistIds,
    isWishlisted,
    toggleWishlist,
    wishlistBounced,

    bagItems,
    totalItems,
    subtotal,
    total,
    bagLoading,
    bagError,
    addToBag,
    updateBagQuantity,
    removeFromBag,
    clearBag,
    clearCartLocal,
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
