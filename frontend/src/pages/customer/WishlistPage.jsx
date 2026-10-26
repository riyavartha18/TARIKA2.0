import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Heart, ShoppingBag, Trash2, ArrowRight, Sparkles, Check } from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';
import { getProductPricing } from '../../utils/pricing';

export default function WishlistPage() {
  const { wishlistItems, wishlistLoading, toggleWishlist, addToBag, openProductDetail } = useCustomer();
  const [movingId, setMovingId] = useState(null);

  const handleMoveToBag = async (item) => {
    const pId = item.product_id;
    setMovingId(pId);
    const res = await addToBag(item, 1);
    if (res && res.success) {
      // Remove from wishlist after moving to bag
      await toggleWishlist(item);
    }
    setMovingId(null);
  };

  // Group saved items by their product category, mirroring the Warehouse
  // portal's category-wise layout (real category_name, alphabetical order).
  const groupedWishlist = useMemo(() => {
    const map = {};
    wishlistItems.forEach((item) => {
      const catName = item.category_name || 'Uncategorized';
      if (!map[catName]) {
        map[catName] = { category_name: catName, items: [] };
      }
      map[catName].items.push(item);
    });
    return Object.values(map).sort((a, b) => a.category_name.localeCompare(b.category_name));
  }, [wishlistItems]);

  return (
    <div style={{ paddingBottom: '4rem' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '1rem',
          marginBottom: '2rem',
          borderBottom: '1px solid rgba(216, 114, 126, 0.2)',
          paddingBottom: '1.25rem',
        }}
      >
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '4px' }}>
            <Heart size={16} fill="#D8727E" color="#D8727E" />
            <span style={{ fontSize: '0.76rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Saved Silhouettes
            </span>
          </div>
          <h1
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '2.2rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: 0,
            }}
          >
            My Wishlist ({wishlistItems.length})
          </h1>
        </div>

        {wishlistItems.length > 0 && (
          <Link to="/customer/shop" className="tarika-btn-outline" style={{ fontSize: '0.84rem', padding: '0.65rem 1.4rem' }}>
            Continue Shopping
          </Link>
        )}
      </div>

      {/* Wishlist Items Grid */}
      {wishlistLoading ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              style={{
                aspectRatio: '3 / 4',
                borderRadius: '18px',
                backgroundColor: '#F5ECEB',
                animation: 'pulseGlow 2s infinite ease-in-out',
              }}
            />
          ))}
        </div>
      ) : wishlistItems.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {groupedWishlist.map((category) => (
            <section
              key={category.category_name}
              style={{
                background: '#FFFFFF',
                borderRadius: '20px',
                padding: '1.75rem',
                border: '1px solid rgba(216, 114, 126, 0.18)',
                boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)',
                display: 'flex',
                flexDirection: 'column',
                gap: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', paddingBottom: '1rem', borderBottom: '1.5px solid #F0E2E0' }}>
                <div
                  style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '12px',
                    background: 'linear-gradient(135deg, #FBF1F0 0%, #F7E4E2 100%)',
                    border: '1px solid rgba(216, 114, 126, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#B8505E',
                    fontWeight: 700,
                  }}
                >
                  {category.category_name ? category.category_name[0].toUpperCase() : 'C'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.45rem', fontWeight: 700, margin: 0, color: '#1F191B' }}>
                    {category.category_name}
                  </h3>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.65rem', borderRadius: '9999px', backgroundColor: 'rgba(216, 114, 126, 0.12)', color: '#B8505E' }}>
                    {category.items.length} {category.items.length === 1 ? 'Item' : 'Items'}
                  </span>
                </div>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                  gap: '1.75rem',
                }}
              >
                {category.items.map((item) => {
            const { basePrice, currentPrice, isOnSale } = getProductPricing(item);
            const isOutOfStock = item.total_stock !== undefined && item.total_stock <= 0;
            const isBusy = movingId === item.product_id;

            const imageUrl =
              item.primary_image ||
              'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=700&q=80';

            return (
              <div
                key={item.id || item.product_id}
                className="tarika-product-card"
                style={{ position: 'relative' }}
              >
                {/* Image Wrap */}
                <div
                  className="product-image-wrap"
                  onClick={() => openProductDetail(item.product_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <img src={imageUrl} alt={item.product_name} loading="lazy" />

                  {/* Remove button */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleWishlist(item);
                    }}
                    style={{
                      position: 'absolute',
                      top: '12px',
                      right: '12px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '50%',
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid rgba(216, 114, 126, 0.3)',
                      color: '#E04D60',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      zIndex: 10,
                      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
                      transition: 'all 0.2s ease',
                    }}
                    title="Remove from wishlist"
                  >
                    <Trash2 size={16} />
                  </button>

                  {/* Out of stock tag */}
                  {isOutOfStock && (
                    <span
                      style={{
                        position: 'absolute',
                        bottom: '12px',
                        left: '12px',
                        backgroundColor: '#1F191B',
                        color: '#FFFFFF',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        padding: '4px 8px',
                        borderRadius: '6px',
                      }}
                    >
                      Sold Out
                    </span>
                  )}
                </div>

                {/* Details */}
                <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {item.category_name || 'Ready to Wear'}
                  </span>

                  <h3
                    style={{
                      margin: 0,
                      fontSize: '0.92rem',
                      fontWeight: 600,
                      color: '#1F191B',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      cursor: 'pointer',
                    }}
                    onClick={() => openProductDetail(item.product_id)}
                  >
                    {item.product_name}
                  </h3>

                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                    <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#B8505E' }}>
                      ₹{currentPrice.toLocaleString('en-IN')}
                    </span>
                    {isOnSale && (
                      <span style={{ fontSize: '0.84rem', color: '#9E8F94', textDecoration: 'line-through' }}>
                        ₹{basePrice.toLocaleString('en-IN')}
                      </span>
                    )}
                  </div>

                  {/* Move to Bag Action */}
                  <button
                    type="button"
                    onClick={() => handleMoveToBag(item)}
                    disabled={isOutOfStock || isBusy}
                    style={{
                      marginTop: '4px',
                      width: '100%',
                      padding: '0.65rem 1rem',
                      backgroundColor: isOutOfStock ? '#FAF7F5' : '#FBF1F0',
                      border: `1px solid ${isOutOfStock ? '#E5D0CD' : '#D8727E'}`,
                      color: isOutOfStock ? '#9E8F94' : '#B8505E',
                      borderRadius: '9999px',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      cursor: isOutOfStock ? 'not-allowed' : 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isOutOfStock) {
                        e.currentTarget.style.backgroundColor = '#D8727E';
                        e.currentTarget.style.color = '#FFFFFF';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isOutOfStock) {
                        e.currentTarget.style.backgroundColor = '#FBF1F0';
                        e.currentTarget.style.color = '#B8505E';
                      }
                    }}
                  >
                    <ShoppingBag size={14} />
                    <span>{isBusy ? 'Moving...' : isOutOfStock ? 'Out of Stock' : 'Move to Bag'}</span>
                  </button>
                </div>
              </div>
                );
              })}
              </div>
            </section>
          ))}
        </div>
      ) : (
        /* Empty State */
        <div
          style={{
            padding: '5rem 2rem',
            textAlign: 'center',
            backgroundColor: '#FFFFFF',
            borderRadius: '24px',
            border: '1px solid #F0E2E0',
            maxWidth: '560px',
            margin: '2rem auto',
            boxShadow: '0 8px 30px rgba(184, 80, 94, 0.05)',
          }}
        >
          <div
            style={{
              width: '72px',
              height: '72px',
              borderRadius: '50%',
              backgroundColor: '#FBF1F0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.5rem auto',
            }}
          >
            <Heart size={32} color="#D8727E" />
          </div>
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.85rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: '0 0 0.75rem 0',
            }}
          >
            Your Wishlist is Empty
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.92rem', lineHeight: 1.6, margin: '0 0 2rem 0' }}>
            Save couture pieces you adore while browsing. When you're ready, move them effortlessly into your shopping bag.
          </p>
          <Link to="/customer/shop" className="tarika-btn-primary">
            <span>Explore The Collection</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </div>
  );
}
