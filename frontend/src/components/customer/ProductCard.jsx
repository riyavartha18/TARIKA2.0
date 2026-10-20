import React, { useState } from 'react';
import { Heart, ShoppingBag, Zap, Check, Eye } from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';
import { getProductPricing } from '../../utils/pricing';

export default function ProductCard({ product, onCardClick }) {
  const { isWishlisted, toggleWishlist, addToBag, openProductDetail } = useCustomer();
  const [addingToBag, setAddingToBag] = useState(false);
  const [justAdded, setJustAdded] = useState(false);

  if (!product) return null;

  const productId = product.product_id || product.id;
  const wishlisted = isWishlisted(productId);
  const productName = product.product_name || product.name || 'Artisanal Garment';

  const { basePrice, currentPrice, discountAmount, isOnSale } = getProductPricing(product);

  // Club special price (5% lower than current price for VIP feel)
  const clubPrice = Math.round(currentPrice * 0.95);

  // Image source with fallback
  const imageUrl =
    product.image ||
    product.primary_image ||
    (product.images && product.images[0]?.image_url) ||
    'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=700&q=80';

  const isOutOfStock = product.total_stock !== undefined && product.total_stock <= 0;

  const handleHeartClick = (e) => {
    e.stopPropagation();
    toggleWishlist(product);
  };

  const handleQuickAdd = async (e) => {
    e.stopPropagation();
    if (isOutOfStock || addingToBag) return;

    setAddingToBag(true);
    const result = await addToBag(product, 1);
    setAddingToBag(false);

    if (result && result.success) {
      setJustAdded(true);
      setTimeout(() => setJustAdded(false), 1600);
    }
  };

  const handleOpenDetails = () => {
    if (onCardClick) {
      onCardClick(product);
    } else {
      openProductDetail(product);
    }
  };

  return (
    <div
      className="tarika-product-card"
      onClick={handleOpenDetails}
      style={{
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      {/* Image Container with 3:4 Aspect Ratio */}
      <div className="product-image-wrap">
        <img
          src={imageUrl}
          alt={productName}
          loading="lazy"
          onError={(e) => {
            e.target.src =
              'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=700&q=80';
          }}
        />

        {/* Sale Discount Badge */}
        {isOnSale && discountAmount > 0 && (
          <span className="product-badge-sale">
            ₹{discountAmount.toLocaleString('en-IN')} OFF
          </span>
        )}

        {/* New Arrival Badge (if not on sale) */}
        {!isOnSale && product.is_new_arrival && (
          <span
            className="product-badge-sale"
            style={{
              background: 'linear-gradient(135deg, #1F191B 0%, #3D2F33 100%)',
              boxShadow: '0 4px 10px rgba(0, 0, 0, 0.2)',
            }}
          >
            NEW DROP
          </span>
        )}

        {/* Wishlist Heart Button with Micro-Animation */}
        <button
          type="button"
          className={`product-heart-btn ${wishlisted ? 'is-active' : ''}`}
          onClick={handleHeartClick}
          aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
        >
          <Heart
            size={18}
            fill={wishlisted ? '#D8727E' : 'none'}
            color={wishlisted ? '#D8727E' : '#6B5E63'}
            className={wishlisted ? 'animate-heart-beat' : ''}
          />
        </button>

        {/* Fast Delivery Badge */}
        <div className="product-badge-fast">
          <Zap size={11} color="#E2B755" fill="#E2B755" />
          <span>Fast Delivery</span>
        </div>

        {/* Quick Add To Bag Button (hover reveal) */}
        {!isOutOfStock ? (
          <button
            type="button"
            className="product-quick-add-btn"
            onClick={handleQuickAdd}
            disabled={addingToBag}
          >
            {justAdded ? (
              <>
                <Check size={14} color="#10B981" />
                <span style={{ color: '#10B981' }}>Added to Bag!</span>
              </>
            ) : addingToBag ? (
              <span>Adding...</span>
            ) : (
              <>
                <ShoppingBag size={14} />
                <span>Quick Add</span>
              </>
            )}
          </button>
        ) : (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.65)',
              backdropFilter: 'blur(2px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span
              style={{
                backgroundColor: '#1F191B',
                color: '#FFFFFF',
                padding: '6px 14px',
                borderRadius: '9999px',
                fontSize: '0.74rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}
            >
              Sold Out
            </span>
          </div>
        )}
      </div>

      {/* Product Information */}
      <div style={{ padding: '0.9rem 1rem', display: 'flex', flexDirection: 'column', gap: '5px' }}>
        {/* Category tag */}
        <span
          style={{
            fontSize: '0.68rem',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            color: '#8E3642',
            fontWeight: 700,
          }}
        >
          {product.category?.name || product.category_name || 'Ready-to-Wear'}
        </span>

        {/* Product Title */}
        <h4
          style={{
            margin: 0,
            fontSize: '0.88rem',
            fontWeight: 600,
            color: '#1F191B',
            lineHeight: 1.3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={productName}
        >
          {productName}
        </h4>

        {/* Price Row */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '2px' }}>
          <span
            style={{
              fontSize: '1rem',
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
                fontSize: '0.82rem',
                color: '#9E8F94',
                textDecoration: 'line-through',
              }}
            >
              ₹{basePrice.toLocaleString('en-IN')}
            </span>
          )}
        </div>

        {/* VIP Member perk strip (Savana-inspired luxury touch) */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.72rem',
            color: '#6B5E63',
            marginTop: '2px',
          }}
        >
          <span>Get it for</span>
          <span style={{ fontWeight: 700, color: '#1F191B' }}>
            ₹{clubPrice.toLocaleString('en-IN')}
          </span>
          <span
            style={{
              fontSize: '0.62rem',
              padding: '1px 5px',
              backgroundColor: '#FBF1F0',
              color: '#B8505E',
              borderRadius: '4px',
              fontWeight: 700,
            }}
          >
            VIP
          </span>
        </div>
      </div>
    </div>
  );
}
