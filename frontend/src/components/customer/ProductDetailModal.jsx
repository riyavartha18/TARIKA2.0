import React, { useState, useEffect } from 'react';
import {
  X,
  Heart,
  ShoppingBag,
  Zap,
  ShieldCheck,
  Truck,
  RotateCcw,
  Sparkles,
  Check,
  MapPin,
  Star,
  MessageSquare,
  AlertCircle,
  Edit3,
} from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';
import { getProductPricing } from '../../utils/pricing';
import { useAuth } from '../../auth/AuthContext';
import ProductCard from './ProductCard';
import { submitProductReview, getProductRecommendations, getProductDetail } from '../../services/api';

export default function ProductDetailModal() {
  const { token, user, isAuthenticated } = useAuth();
  const {
    activeModalProduct,
    closeProductDetail,
    openProductDetail,
    isWishlisted,
    toggleWishlist,
    addToBag,
    refreshProductDetail,
    addToast,
  } = useCustomer();

  const [quantity, setQuantity] = useState(1);
  const [justAdded, setJustAdded] = useState(false);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);

  // Review & Rating local states
  const [localReviews, setLocalReviews] = useState([]);
  const [myRatingRecord, setMyRatingRecord] = useState(null);
  const [userRating, setUserRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [reviewText, setReviewText] = useState('');
  const [isEditingReview, setIsEditingReview] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [reviewSuccess, setReviewSuccess] = useState('');

  useEffect(() => {
    setQuantity(1);
    setSelectedImageIndex(0);
    setJustAdded(false);
  }, [activeModalProduct]);

  useEffect(() => {
    if (!activeModalProduct) return;
    const initialReviews = Array.isArray(activeModalProduct.reviews) ? [...activeModalProduct.reviews] : [];
    setLocalReviews(initialReviews);

    const currentCustId = user?.customer_id || user?.id;
    const existing = initialReviews.find(
      (r) => currentCustId && String(r.customer_id) === String(currentCustId)
    );
    if (existing) {
      setMyRatingRecord(existing);
      setUserRating(Number(existing.rating) || 5);
      setReviewText(existing.review_text || '');
      setIsEditingReview(false);
    } else {
      setMyRatingRecord(null);
      setUserRating(5);
      setReviewText('');
      setIsEditingReview(false);
    }
    setHoverRating(0);
    setReviewError('');
    setReviewSuccess('');
  }, [activeModalProduct, user]);

  // Frequently Bought Together recommendations state
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);

  const currentProductId = activeModalProduct
    ? String(activeModalProduct.product_id || activeModalProduct.id || '').trim()
    : '';

  useEffect(() => {
    if (!currentProductId) {
      setRecommendations([]);
      setLoadingRecommendations(false);
      return;
    }

    let isMounted = true;
    setLoadingRecommendations(true);

    getProductRecommendations(currentProductId)
      .then(async (res) => {
        if (!isMounted) return;

        if (res && res.success && Array.isArray(res.recommendations) && res.recommendations.length > 0) {
          const currentPName = String(
            activeModalProduct?.product_name ||
            activeModalProduct?.name ||
            res.product_name ||
            ''
          ).trim().toLowerCase();

          // Collect candidate recommendation objects and their product IDs
          const candidates = [];
          const seenIds = new Set();
          if (currentProductId) {
            seenIds.add(currentProductId);
          }

          for (const item of res.recommendations) {
            // Find recommended product ID from all possible response keys
            const recObj = item.recommended_product || {};
            const recId = String(
              recObj.product_id ||
              recObj.id ||
              item.recommended_product_id ||
              item.product_id ||
              (item.matching_products && item.matching_products[0]?.product_id) ||
              ''
            ).trim();

            const recName = String(
              recObj.product_name ||
              recObj.name ||
              item.frequently_bought_with ||
              item.product_name ||
              ''
            ).trim().toLowerCase();

            // Filter out current product by ID and by name
            if (recId && recId === currentProductId) continue;
            if (currentPName && recName && recName === currentPName) continue;

            if (recId && !seenIds.has(recId)) {
              seenIds.add(recId);
              candidates.push({
                recId,
                rawItem: item,
                rawProduct: recObj,
              });
            }
          }

          if (candidates.length === 0) {
            if (isMounted) setRecommendations([]);
            return;
          }

          // Fetch full product details using existing catalog API service
          const resolvedProducts = await Promise.all(
            candidates.map(async ({ recId, rawItem, rawProduct }) => {
              try {
                const detailRes = await getProductDetail(recId);
                if (detailRes && detailRes.success && detailRes.product) {
                  return {
                    ...rawProduct,
                    ...detailRes.product,
                    confidence: rawItem.confidence,
                    lift: rawItem.lift,
                    support: rawItem.support,
                  };
                }
              } catch (e) {
                console.warn('Could not fetch detail for recommendation:', recId);
              }
              // Fallback to recommended_product info from recommendations endpoint
              return {
                ...rawProduct,
                product_id: recId,
                confidence: rawItem.confidence,
                lift: rawItem.lift,
                support: rawItem.support,
                total_stock: rawProduct.total_stock ?? 10,
                is_in_stock: rawProduct.is_active !== false,
              };
            })
          );

          if (!isMounted) return;

          // Double check filter against currentProductId in case activeModalProduct updated
          const finalList = resolvedProducts.filter((p) => {
            const pid = String(p.product_id || p.id || '').trim();
            const pname = String(p.product_name || p.name || '').trim().toLowerCase();
            return pid !== currentProductId && (!currentPName || pname !== currentPName);
          });

          setRecommendations(finalList);
        } else {
          setRecommendations([]);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error('Failed to load product recommendations', err);
        setRecommendations([]);
      })
      .finally(() => {
        if (isMounted) {
          setLoadingRecommendations(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [currentProductId]);

  const handleRecommendationClick = (recProduct) => {
    const modalContent = document.querySelector('.modal-content-card');
    if (modalContent) {
      modalContent.scrollTo({ top: 0, behavior: 'smooth' });
    }
    openProductDetail(recProduct);
  };

  if (!activeModalProduct) return null;

  const product = activeModalProduct;
  const productId = product.product_id || product.id;
  const wishlisted = isWishlisted(productId);

  const { basePrice, currentPrice, discountAmount, isOnSale } = getProductPricing(product);

  // Rating and reviews from database / local state
  const reviewCount = localReviews.length;
  const validRatings = localReviews
    .map((r) => Number(r.rating))
    .filter((n) => !isNaN(n) && n > 0);
  const averageRating =
    validRatings.length > 0
      ? Number((validRatings.reduce((a, b) => a + b, 0) / validRatings.length).toFixed(1))
      : (product.rating_summary?.average_rating ? Number(product.rating_summary.average_rating) : null);

  const ratingDistribution = [5, 4, 3, 2, 1].map((stars) => {
    const count = localReviews.filter((r) => Number(r.rating) === stars).length;
    const pct = reviewCount > 0 ? Math.round((count / reviewCount) * 100) : 0;
    return { stars, count, pct };
  });

  const handleSubmitProductReview = async (e) => {
    e.preventDefault();
    if (!isAuthenticated || !token) {
      setReviewError('Please sign in as a customer to rate and review this product.');
      return;
    }
    if (!reviewText.trim()) {
      setReviewError('Please write your review thoughts before submitting.');
      return;
    }

    setSubmittingReview(true);
    setReviewError('');
    setReviewSuccess('');

    try {
      const res = await submitProductReview(token, productId, {
        rating: userRating,
        review_text: reviewText.trim(),
      });

      if (res.success) {
        const todayStr = new Date().toISOString().split('T')[0];
        const savedReview = res.review || {
          review_id: myRatingRecord?.review_id || 'rev-' + Date.now(),
          product_id: productId,
          customer_id: user?.customer_id || user?.id,
          customer_name: user?.full_name || 'Verified Buyer',
          rating: userRating,
          review_text: reviewText.trim(),
          review_date: todayStr,
          is_verified_purchase: true,
        };
        if (!savedReview.customer_name) {
          savedReview.customer_name = user?.full_name || 'Verified Buyer';
        }

        setMyRatingRecord(savedReview);
        setIsEditingReview(false);
        setReviewSuccess('Thank you! Your rating and review have been published.');
        if (addToast) addToast('Review saved successfully!', 'success');

        setLocalReviews((prev) => {
          const currentCustId = user?.customer_id || user?.id;
          const idx = prev.findIndex(
            (r) =>
              (r.review_id && r.review_id === savedReview.review_id) ||
              (currentCustId && String(r.customer_id) === String(currentCustId))
          );
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], ...savedReview };
            return updated;
          }
          return [savedReview, ...prev];
        });

        if (refreshProductDetail) {
          refreshProductDetail(productId);
        }
      } else {
        setReviewError(res.error || 'Failed to submit review.');
      }
    } catch (err) {
      setReviewError('Network error submitting review.');
    } finally {
      setSubmittingReview(false);
    }
  };

  const totalStock = product.total_stock !== undefined ? product.total_stock : 10;
  const isOutOfStock = totalStock <= 0;

  // Build image array — priority: products.image (the real DB column, returned
  // as `image` by the catalog API and used by ProductCard), then legacy keys.
  const images = [];
  if (product.image) images.push(product.image);
  if (product.primary_image && !images.includes(product.primary_image)) {
    images.push(product.primary_image);
  }
  if (Array.isArray(product.images) && product.images.length > 0) {
    product.images.forEach((img) => {
      const url = typeof img === 'string' ? img : img.image_url;
      if (url && !images.includes(url)) images.push(url);
    });
  }
  // Graceful fallback: category artwork (mirrors backend serializer), then the
  // same generic image ProductCard falls back to.
  if (images.length === 0) {
    const catName = String(
      product.category?.name || product.category_name || ''
    ).trim().toLowerCase();
    const categoryImages = {
      dresses: 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80',
      't-shirts': 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop&q=80',
      tops: 'https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=600&auto=format&fit=crop&q=80',
      shirts: 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=600&auto=format&fit=crop&q=80',
      jeans: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop&q=80',
      sarees: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&auto=format&fit=crop&q=80',
      kurtis: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&auto=format&fit=crop&q=80',
      footwear: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600&auto=format&fit=crop&q=80',
      handbags: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop&q=80',
      accessories: 'https://images.unsplash.com/photo-1611652022419-a9419f74343d?w=600&auto=format&fit=crop&q=80',
    };
    images.push(
      categoryImages[catName] ||
      'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=800&q=80'
    );
  }

  const activeImage = images[selectedImageIndex] || images[0];

  const handleDecrease = () => {
    if (quantity > 1) setQuantity(quantity - 1);
  };

  const handleIncrease = () => {
    if (quantity < totalStock) setQuantity(quantity + 1);
  };

  const handleAdd = async () => {
    if (isOutOfStock) return;
    // Optimistic feedback, matching the card's Quick Add: the badge and this
    // button react in the same paint while the context confirms the Neon
    // write and reverts with an error toast if it fails.
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 2000);
    addToBag(product, quantity);
  };

  return (
    <div className="modal-overlay" onClick={closeProductDetail}>
      <div
        className="modal-content-card"
        onClick={(e) => e.stopPropagation()}
        style={{ padding: '2rem' }}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={closeProductDetail}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            backgroundColor: '#FAF7F5',
            border: '1px solid rgba(216, 114, 126, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#1F191B',
            zIndex: 10,
            transition: 'all 0.2s ease',
          }}
          aria-label="Close product modal"
        >
          <X size={18} />
        </button>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.1fr) minmax(0, 1.4fr)',
            gap: '2.5rem',
            alignItems: 'start',
          }}
          className="product-modal-grid"
        >
          {/* LEFT: Image Gallery */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div
              style={{
                width: '100%',
                aspectRatio: '3 / 4',
                borderRadius: '16px',
                overflow: 'hidden',
                backgroundColor: '#FAF7F5',
                position: 'relative',
              }}
              className="zoom-container"
            >
              <img
                src={activeImage}
                alt={product.name || product.product_name || 'Product image'}
                onError={(e) => {
                  // Same broken-image fallback used by ProductCard.
                  if (e.target.dataset.fallbackApplied) return;
                  e.target.dataset.fallbackApplied = '1';
                  e.target.src =
                    'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=700&q=80';
                }}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                }}
              />
              {isOnSale && (
                <span className="product-badge-sale" style={{ top: '16px', left: '16px' }}>
                  ₹{discountAmount.toLocaleString('en-IN')} OFF
                </span>
              )}
            </div>

            {/* Thumbnail selector if multiple images */}
            {images.length > 1 && (
              <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '4px' }}>
                {images.map((img, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedImageIndex(idx)}
                    style={{
                      width: '64px',
                      height: '80px',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      border: idx === selectedImageIndex ? '2px solid #D8727E' : '1px solid #F0E2E0',
                      padding: 0,
                      cursor: 'pointer',
                      flexShrink: 0,
                      backgroundColor: '#FAF7F5',
                    }}
                  >
                    <img
                      src={img}
                      alt={`Thumbnail ${idx + 1}`}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* RIGHT: Product Specs & Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            <div>
              <span
                style={{
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.12em',
                  color: '#8E3642',
                  fontWeight: 700,
                }}
              >
                {product.category?.name || product.category_name || 'Ready to Wear'}
              </span>
              <h2
                style={{
                  margin: '4px 0 6px 0',
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.85rem',
                  fontWeight: 700,
                  color: '#1F191B',
                  lineHeight: 1.25,
                }}
              >
                {product.name || product.product_name}
              </h2>
              {product.sku && (
                <p style={{ margin: '0 0 6px 0', fontSize: '0.78rem', color: '#9E8F94' }}>
                  SKU: {product.sku}
                </p>
              )}

              {/* Real Database Rating in Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '4px 0 8px 0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '2px', color: '#EAB308' }}>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <Star
                      key={star}
                      size={15}
                      fill={star <= Math.round(averageRating || 0) ? '#EAB308' : '#F1E8E6'}
                      color={star <= Math.round(averageRating || 0) ? '#CA8A04' : '#D1C2C0'}
                    />
                  ))}
                </div>
                <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1F191B' }}>
                  {averageRating ? averageRating.toFixed(1) : 'New'}
                </span>
                <span style={{ fontSize: '0.82rem', color: '#9E8F94' }}>
                  ({reviewCount > 0 ? `${reviewCount.toLocaleString('en-IN')} ${reviewCount === 1 ? 'Review' : 'Reviews'}` : '0 Reviews'})
                </span>
              </div>
            </div>

            {/* Price section */}
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: '12px',
                padding: '12px 16px',
                backgroundColor: '#FAF7F5',
                borderRadius: '12px',
                border: '1px solid rgba(216, 114, 126, 0.2)',
              }}
            >
              <span
                style={{
                  fontSize: '1.75rem',
                  fontWeight: 700,
                  color: '#B8505E',
                  fontFamily: "'Plus Jakarta Sans', sans-serif",
                }}
              >
                ₹{currentPrice.toLocaleString('en-IN')}
              </span>
              {isOnSale && (
                <span
                  style={{
                    fontSize: '1.1rem',
                    color: '#9E8F94',
                    textDecoration: 'line-through',
                  }}
                >
                  ₹{basePrice.toLocaleString('en-IN')}
                </span>
              )}
              {isOnSale && (
                <span
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    color: '#D8727E',
                    backgroundColor: '#FBF1F0',
                    padding: '3px 8px',
                    borderRadius: '6px',
                  }}
                >
                  Save ₹{discountAmount.toLocaleString('en-IN')}
                </span>
              )}
            </div>

            {/* Description */}
            <p
              style={{
                margin: 0,
                fontSize: '0.9rem',
                lineHeight: 1.6,
                color: '#6B5E63',
              }}
            >
              {product.description ||
                'Designed with precision couture craftsmanship. Created for effortless high-fashion wear with sumptuous comfort and delicate contouring.'}
            </p>

            {/* Live Real-time Stock Inventory Breakdown */}
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '12px',
                backgroundColor: isOutOfStock ? '#FFF1F2' : '#F0FDF4',
                border: `1px solid ${isOutOfStock ? '#FECDD3' : '#BBF7D0'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: isOutOfStock ? '#E04D60' : '#16A34A',
                  }}
                />
                <span
                  style={{
                    fontSize: '0.84rem',
                    fontWeight: 700,
                    color: isOutOfStock ? '#9F1239' : '#166534',
                  }}
                >
                  {isOutOfStock
                    ? 'Currently Out of Stock'
                    : `In Stock — ${totalStock} units available for instant dispatch`}
                </span>
              </div>

              {/* Warehouse distribution details if present */}
              {product.inventory_by_warehouse && product.inventory_by_warehouse.length > 0 && (
                <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '0.72rem', color: '#6B5E63', fontWeight: 600 }}>
                    TARIKA Fulfillment Centers:
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {product.inventory_by_warehouse.map((wh, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: '0.72rem',
                          backgroundColor: '#FFFFFF',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          border: '1px solid rgba(0, 0, 0, 0.08)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          color: '#1F191B',
                        }}
                      >
                        <MapPin size={10} color="#B8505E" />
                        {wh.warehouse_name}: <strong>{wh.quantity}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Quantity Selector */}
            {!isOutOfStock && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span style={{ fontSize: '0.84rem', fontWeight: 600, color: '#1F191B' }}>
                  Quantity:
                </span>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    border: '1px solid #F0E2E0',
                    borderRadius: '9999px',
                    backgroundColor: '#FAF7F5',
                    overflow: 'hidden',
                  }}
                >
                  <button
                    type="button"
                    onClick={handleDecrease}
                    disabled={quantity <= 1}
                    style={{
                      width: '36px',
                      height: '36px',
                      border: 'none',
                      background: 'none',
                      cursor: quantity <= 1 ? 'not-allowed' : 'pointer',
                      fontSize: '1.1rem',
                      fontWeight: 700,
                      color: quantity <= 1 ? '#C4B5B8' : '#1F191B',
                    }}
                  >
                    -
                  </button>
                  <span
                    style={{
                      width: '40px',
                      textAlign: 'center',
                      fontSize: '0.92rem',
                      fontWeight: 700,
                      color: '#1F191B',
                    }}
                  >
                    {quantity}
                  </span>
                  <button
                    type="button"
                    onClick={handleIncrease}
                    disabled={quantity >= totalStock}
                    style={{
                      width: '36px',
                      height: '36px',
                      border: 'none',
                      background: 'none',
                      cursor: quantity >= totalStock ? 'not-allowed' : 'pointer',
                      fontSize: '1.1rem',
                      fontWeight: 700,
                      color: quantity >= totalStock ? '#C4B5B8' : '#1F191B',
                    }}
                  >
                    +
                  </button>
                </div>
                <span style={{ fontSize: '0.74rem', color: '#9E8F94' }}>
                  Max {totalStock} per order
                </span>
              </div>
            )}

            {/* Action Buttons: Add to Bag & Wishlist */}
            <div style={{ display: 'flex', gap: '12px', marginTop: '0.5rem' }}>
              <button
                type="button"
                className="tarika-btn-primary"
                onClick={handleAdd}
                disabled={isOutOfStock}
                style={{
                  flex: 1,
                  padding: '0.95rem 1.5rem',
                  fontSize: '0.92rem',
                }}
              >
                {justAdded ? (
                  <>
                    <Check size={18} />
                    <span>Added to Bag!</span>
                  </>
                ) : (
                  <>
                    <ShoppingBag size={18} />
                    <span>{isOutOfStock ? 'Sold Out' : 'Add to Shopping Bag'}</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => toggleWishlist(product)}
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '50%',
                  border: `1px solid ${wishlisted ? '#D8727E' : 'rgba(216, 114, 126, 0.3)'}`,
                  backgroundColor: wishlisted ? '#FBF1F0' : '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  flexShrink: 0,
                  transition: 'all 0.25s ease',
                }}
                aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
              >
                <Heart
                  size={22}
                  fill={wishlisted ? '#D8727E' : 'none'}
                  color="#D8727E"
                  className={wishlisted ? 'animate-heart-beat' : ''}
                />
              </button>
            </div>

            {/* Boutique Perks */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '10px',
                paddingTop: '1rem',
                borderTop: '1px solid #F0E2E0',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Truck size={16} color="#8E3642" />
                <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>Express Courier</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={16} color="#8E3642" />
                <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>Authentic Couture</span>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================
            FREQUENTLY BOUGHT TOGETHER SECTION
            ======================================================== */}
        {loadingRecommendations ? (
          <div
            style={{
              marginTop: '2.5rem',
              paddingTop: '2rem',
              borderTop: '1px solid #F0E2E0',
            }}
          >
            <div
              style={{
                width: '240px',
                height: '24px',
                borderRadius: '6px',
                backgroundColor: '#F5ECEB',
                marginBottom: '1.25rem',
                animation: 'pulseGlow 2s infinite ease-in-out',
              }}
            />
            <div
              style={{
                display: 'flex',
                gap: '1.5rem',
                overflowX: 'hidden',
              }}
            >
              {[1, 2].map((n) => (
                <div
                  key={n}
                  style={{
                    width: '260px',
                    height: '350px',
                    borderRadius: '18px',
                    backgroundColor: '#F5ECEB',
                    flexShrink: 0,
                    animation: 'pulseGlow 2s infinite ease-in-out',
                  }}
                />
              ))}
            </div>
          </div>
        ) : recommendations.length > 0 ? (
          <section
            style={{
              marginTop: '2.5rem',
              paddingTop: '2rem',
              borderTop: '1px solid #F0E2E0',
            }}
            aria-label="Frequently Bought Together"
          >
            <h3
              style={{
                margin: '0 0 1.5rem 0',
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.5rem',
                fontWeight: 700,
                color: '#1F191B',
                letterSpacing: '-0.01em',
              }}
            >
              Frequently Bought Together
            </h3>

            <div className="frequently-bought-grid">
              {recommendations.map((recProd) => (
                <ProductCard
                  key={recProd.product_id || recProd.id}
                  product={recProd}
                  onCardClick={() => handleRecommendationClick(recProd)}
                />
              ))}
            </div>
          </section>
        ) : null}

        {/* ========================================================
            CUSTOMER REVIEWS SECTION
            ======================================================== */}
        <div
          style={{
            marginTop: '2.5rem',
            paddingTop: '2rem',
            borderTop: '1px solid #F0E2E0',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1.5rem',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <h3
                style={{
                  margin: 0,
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.5rem',
                  fontWeight: 700,
                  color: '#1F191B',
                }}
              >
                Customer Reviews
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.82rem', color: '#6B5E63' }}>
                Verified feedback from TARIKA patrons who purchased this product
              </p>
            </div>

            {reviewCount > 0 && (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 14px',
                  borderRadius: '9999px',
                  backgroundColor: '#FAF7F5',
                  border: '1px solid #F0E2E0',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  color: '#8E3642',
                }}
              >
                <Sparkles size={14} color="#B8505E" />
                <span>{reviewCount} Verified {reviewCount === 1 ? 'Review' : 'Reviews'}</span>
              </div>
            )}
          </div>

          {/* Rating Summary Card & Distribution */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.6fr)',
              gap: '2rem',
              backgroundColor: '#FAF7F5',
              borderRadius: '20px',
              border: '1px solid #F0E2E0',
              padding: '1.75rem',
              marginBottom: '2rem',
              alignItems: 'center',
            }}
            className="reviews-summary-grid"
          >
            {/* Left: Overall Score */}
            <div style={{ textAlign: 'center', borderRight: '1px solid #EADCDA', paddingRight: '1.5rem' }}>
              <div
                style={{
                  fontSize: '3.2rem',
                  fontFamily: "'Playfair Display', serif",
                  fontWeight: 800,
                  color: '#1F191B',
                  lineHeight: 1,
                  marginBottom: '6px',
                }}
              >
                {averageRating ? averageRating.toFixed(1) : '—'}
              </div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '3px', marginBottom: '8px' }}>
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star
                    key={s}
                    size={18}
                    fill={s <= Math.round(averageRating || 0) ? '#EAB308' : '#E8DDD9'}
                    color={s <= Math.round(averageRating || 0) ? '#CA8A04' : '#D1C2C0'}
                  />
                ))}
              </div>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#6B5E63' }}>
                {reviewCount > 0
                  ? `Based on ${reviewCount.toLocaleString('en-IN')} customer ${reviewCount === 1 ? 'rating' : 'ratings'}`
                  : 'Awaiting first patron rating'}
              </p>
            </div>

            {/* Right: Distribution Bars */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {ratingDistribution.map(({ stars, count, pct }) => (
                <div key={stars} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.78rem' }}>
                  <span style={{ width: '42px', fontWeight: 600, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '3px' }}>
                    {stars} <Star size={11} fill="#EAB308" color="#CA8A04" />
                  </span>
                  <div
                    style={{
                      flex: 1,
                      height: '8px',
                      borderRadius: '9999px',
                      backgroundColor: '#EDE4E2',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        height: '100%',
                        backgroundColor: '#B8505E',
                        borderRadius: '9999px',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                  <span style={{ width: '36px', textAlign: 'right', color: '#6B5E63', fontWeight: 500 }}>
                    {count}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ========================================================
              RATE THIS PRODUCT SECTION (Persists after submission, shows selected rating)
              ======================================================== */}
          <div
            style={{
              backgroundColor: '#FAF7F5',
              borderRadius: '20px',
              border: '1px solid #EADCDA',
              padding: '1.5rem 1.75rem',
              marginBottom: '2rem',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '10px',
                marginBottom: myRatingRecord && !isEditingReview ? '0' : '1.25rem',
              }}
            >
              <div>
                <h4
                  style={{
                    margin: 0,
                    fontFamily: "'Playfair Display', serif",
                    fontSize: '1.2rem',
                    fontWeight: 700,
                    color: '#1F191B',
                  }}
                >
                  Rate This Product
                </h4>
                <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: '#6B5E63' }}>
                  {myRatingRecord
                    ? 'Your feedback has been recorded for this design'
                    : 'Share your authentic experience with fellow TARIKA patrons'}
                </p>
              </div>

              {myRatingRecord && !isEditingReview && (
                <button
                  type="button"
                  onClick={() => {
                    setIsEditingReview(true);
                    setReviewError('');
                    setReviewSuccess('');
                  }}
                  style={{
                    background: 'none',
                    border: '1px solid #D8727E',
                    borderRadius: '9999px',
                    color: '#8E3642',
                    padding: '6px 14px',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#FBF1F0';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <Edit3 size={13} />
                  <span>Edit Review</span>
                </button>
              )}
            </div>

            {/* Display submitted rating when review exists and not currently editing */}
            {myRatingRecord && !isEditingReview ? (
              <div
                style={{
                  marginTop: '1rem',
                  padding: '12px 16px',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '14px',
                  border: '1px solid rgba(216, 114, 126, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '10px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#8E3642' }}>
                    Your Rating:
                  </span>
                  <div style={{ display: 'flex', gap: '3px', color: '#EAB308' }}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Star
                        key={s}
                        size={15}
                        fill={s <= Number(myRatingRecord.rating) ? '#EAB308' : '#F1E8E6'}
                        color={s <= Number(myRatingRecord.rating) ? '#CA8A04' : '#D1C2C0'}
                      />
                    ))}
                  </div>
                  <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#1F191B' }}>
                    ({myRatingRecord.rating}/5)
                  </span>
                </div>

                {reviewSuccess && (
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#065F46' }}>
                    ✓ {reviewSuccess}
                  </span>
                )}
              </div>
            ) : (
              /* Review submission / edit form */
              <form onSubmit={handleSubmitProductReview} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#1F191B', marginBottom: '8px' }}>
                    Select Your Rating
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {[1, 2, 3, 4, 5].map((star) => {
                        const active = star <= (hoverRating || userRating);
                        return (
                          <button
                            key={star}
                            type="button"
                            onClick={() => setUserRating(star)}
                            onMouseEnter={() => setHoverRating(star)}
                            onMouseLeave={() => setHoverRating(0)}
                            style={{
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              padding: '2px',
                              transition: 'transform 0.15s ease',
                              transform: active ? 'scale(1.18)' : 'scale(1)',
                            }}
                            aria-label={`${star} star`}
                          >
                            <Star
                              size={24}
                              fill={active ? '#EAB308' : '#F1E8E6'}
                              color={active ? '#CA8A04' : '#D1C2C0'}
                            />
                          </button>
                        );
                      })}
                    </div>
                    <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#B8505E', marginLeft: '6px' }}>
                      {(hoverRating || userRating) === 5
                        ? '5 Stars — Excellent'
                        : (hoverRating || userRating) === 4
                        ? '4 Stars — Very Good'
                        : (hoverRating || userRating) === 3
                        ? '3 Stars — Good'
                        : (hoverRating || userRating) === 2
                        ? '2 Stars — Fair'
                        : '1 Star — Poor'}
                    </span>
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
                    Written Review
                  </label>
                  <textarea
                    rows={3}
                    value={reviewText}
                    onChange={(e) => setReviewText(e.target.value)}
                    placeholder="Share your thoughts on craftsmanship, fit, fabric quality, and styling..."
                    style={{
                      width: '100%',
                      padding: '12px 14px',
                      borderRadius: '12px',
                      border: '1px solid #E0D2D0',
                      backgroundColor: '#FFFFFF',
                      fontSize: '0.86rem',
                      fontFamily: 'inherit',
                      color: '#1F191B',
                      lineHeight: 1.5,
                      resize: 'vertical',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                    onFocus={(e) => (e.target.style.borderColor = '#B8505E')}
                    onBlur={(e) => (e.target.style.borderColor = '#E0D2D0')}
                  />
                </div>

                {reviewError && (
                  <div
                    style={{
                      padding: '10px 14px',
                      borderRadius: '10px',
                      backgroundColor: '#FEF2F2',
                      border: '1px solid #FECACA',
                      color: '#DC2626',
                      fontSize: '0.82rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <AlertCircle size={16} />
                    <span>{reviewError}</span>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  {isEditingReview && myRatingRecord && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsEditingReview(false);
                        setUserRating(Number(myRatingRecord.rating) || 5);
                        setReviewText(myRatingRecord.review_text || '');
                        setReviewError('');
                      }}
                      style={{
                        padding: '0.65rem 1.25rem',
                        borderRadius: '9999px',
                        border: '1px solid #E0D2D0',
                        backgroundColor: '#FFFFFF',
                        color: '#6B5E63',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={submittingReview}
                    className="tarika-btn-primary"
                    style={{
                      padding: '0.65rem 1.5rem',
                      fontSize: '0.84rem',
                    }}
                  >
                    {submittingReview
                      ? 'Submitting...'
                      : isEditingReview
                      ? 'Update Review'
                      : 'Submit Review'}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* Customer Reviews List */}
          {localReviews.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '3rem 2rem',
                backgroundColor: '#FFFFFF',
                borderRadius: '16px',
                border: '1px dashed #E0D2D0',
              }}
            >
              <MessageSquare size={32} color="#D8727E" style={{ margin: '0 auto 10px auto', opacity: 0.6 }} />
              <h4 style={{ margin: '0 0 6px 0', fontFamily: "'Playfair Display', serif", fontSize: '1.15rem', color: '#1F191B' }}>
                No Customer Reviews Yet
              </h4>
              <p style={{ margin: 0, fontSize: '0.84rem', color: '#6B5E63', maxWidth: '380px', marginInline: 'auto' }}>
                Have you purchased this piece? Rate and share your review from your <span style={{ fontWeight: 600, color: '#8E3642' }}>My Orders</span> dashboard.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {localReviews.map((rev, idx) => (
                <div
                  key={rev.review_id || idx}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '16px',
                    border: '1px solid #F0E2E0',
                    padding: '1.25rem 1.5rem',
                    boxShadow: '0 2px 10px rgba(184, 80, 94, 0.03)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                  }}
                >
                  {/* Card Top: Stars + Customer Name + Verified Badge + Date */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                      <div style={{ display: 'flex', gap: '2px', color: '#EAB308' }}>
                        {[1, 2, 3, 4, 5].map((s) => (
                          <Star
                            key={s}
                            size={14}
                            fill={s <= Number(rev.rating) ? '#EAB308' : '#F1E8E6'}
                            color={s <= Number(rev.rating) ? '#CA8A04' : '#D1C2C0'}
                          />
                        ))}
                      </div>
                      <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B' }}>
                        {rev.customer_name || 'Verified Buyer'}
                      </span>
                      {rev.is_verified_purchase && (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '9999px',
                            backgroundColor: '#ECFDF5',
                            color: '#065F46',
                            border: '1px solid rgba(16, 185, 129, 0.2)',
                          }}
                        >
                          <Check size={11} />
                          <span>Verified Purchase</span>
                        </span>
                      )}
                    </div>

                    {rev.review_date && (
                      <span style={{ fontSize: '0.76rem', color: '#9E8F94' }}>
                        {rev.review_date}
                      </span>
                    )}
                  </div>

                  {/* Card Body: Written Review */}
                  <p
                    style={{
                      margin: 0,
                      fontSize: '0.88rem',
                      lineHeight: 1.55,
                      color: '#382D32',
                    }}
                  >
                    "{rev.review_text}"
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
