import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShoppingBag,
  Trash2,
  ArrowRight,
  ShieldCheck,
  Truck,
  Sparkles,
  Info,
  AlertCircle,
} from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';

export default function BagPage() {
  const navigate = useNavigate();
  const {
    bagItems,
    totalItems,
    subtotal,
    total,
    bagLoading,
    bagError,
    updateBagQuantity,
    removeFromBag,
    clearBag,
    addToast,
    openProductDetail,
    refreshCustomerData,
  } = useCustomer();
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    await refreshCustomerData();
    setRetrying(false);
  };

  const handleCheckoutClick = () => {
    navigate('/customer/checkout');
  };

  // Group cart lines by their product category, mirroring the Warehouse
  // portal's category-wise layout. Grouping is display-only: each item keeps
  // its own product_id, so quantity updates / removal / totals are unaffected.
  const groupedBag = useMemo(() => {
    const map = {};
    bagItems.forEach((item) => {
      const catName = (item.product && item.product.category_name) || 'Uncategorized';
      if (!map[catName]) {
        map[catName] = { category_name: catName, items: [] };
      }
      map[catName].items.push(item);
    });
    return Object.values(map).sort((a, b) => a.category_name.localeCompare(b.category_name));
  }, [bagItems]);

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
            <ShoppingBag size={16} color="#B8505E" />
            <span style={{ fontSize: '0.76rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              Your Wardrobe Selection
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
            Shopping Bag ({totalItems} {totalItems === 1 ? 'item' : 'items'})
          </h1>
        </div>

        {bagItems.length > 0 && (
          <button
            type="button"
            onClick={clearBag}
            style={{
              background: 'none',
              border: 'none',
              color: '#9E8F94',
              fontSize: '0.84rem',
              fontWeight: 600,
              cursor: 'pointer',
              textDecoration: 'underline',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <Trash2 size={14} />
            <span>Clear Bag</span>
          </button>
        )}
      </div>

      {bagError && !bagLoading && (
        <div className="tarika-portal-alert" role="alert">
          <AlertCircle size={18} style={{ flexShrink: 0 }} />
          <span>{bagError}</span>
          <button type="button" className="tarika-portal-alert-action" onClick={handleRetry} disabled={retrying}>
            {retrying ? 'Retrying...' : 'Retry'}
          </button>
        </div>
      )}

      {bagLoading ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: '#B8505E' }}>
          Loading your shopping bag...
        </div>
      ) : bagItems.length > 0 ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.8fr) minmax(0, 1fr)',
            gap: '2.5rem',
            alignItems: 'start',
          }}
          className="bag-page-grid"
        >
          {/* LEFT: Cart Items List (grouped category-wise) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {groupedBag.map((category) => (
              <section key={category.category_name} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', paddingBottom: '0.9rem', borderBottom: '1.5px solid rgba(216, 114, 126, 0.2)' }}>
                  <div
                    style={{
                      width: '40px',
                      height: '40px',
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
                    <h3 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.3rem', fontWeight: 700, margin: 0, color: '#1F191B' }}>
                      {category.category_name}
                    </h3>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.65rem', borderRadius: '9999px', backgroundColor: 'rgba(216, 114, 126, 0.12)', color: '#B8505E' }}>
                      {category.items.length} {category.items.length === 1 ? 'item' : 'items'}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {category.items.map((item) => {
              const product = item.product || {};
              const pId = item.product_id;
              const unitPrice = Number(item.unit_price || 0);
              const lineTotal = Number(item.line_total || 0);
              // null stock means the catalogue does not record a quantity, so
              // the line is not capped rather than capped at an invented number.
              const maxStock = item.available_stock == null ? null : Number(item.available_stock);
              const quantity = Number(item.quantity || 0);
              const atMaxStock = maxStock !== null && quantity >= maxStock;
              const outOfStock = item.is_stock_available === false;
              const imageUrl =
                product.primary_image ||
                'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80';

              return (
                <div
                  key={item.id || pId}
                  className="bag-line"
                >
                  {/* Thumbnail */}
                  <div
                    onClick={() => openProductDetail(pId)}
                    className="bag-line-thumb"
                    style={{
                      width: '90px',
                      height: '115px',
                      borderRadius: '12px',
                      overflow: 'hidden',
                      backgroundColor: '#FAF7F5',
                      flexShrink: 0,
                      cursor: 'pointer',
                    }}
                  >
                    <img
                      src={imageUrl}
                      alt={item.product_name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  </div>

                  {/* Info */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      {product.category_name || 'Ready to Wear'}
                    </span>
                    <h3
                      onClick={() => openProductDetail(pId)}
                      style={{
                        margin: 0,
                        fontSize: '0.98rem',
                        fontWeight: 600,
                        color: '#1F191B',
                        cursor: 'pointer',
                      }}
                    >
                      {item.product_name}
                    </h3>
                    <span style={{ fontSize: '0.84rem', color: '#6B5E63' }}>
                      Price: <strong>₹{unitPrice.toLocaleString('en-IN')}</strong>
                    </span>

                    {/* Stock status indicator, taken from the backend's check */}
                    {outOfStock ? (
                      <span style={{ fontSize: '0.74rem', color: '#B42318', fontWeight: 600 }}>
                        Only {maxStock} in stock - reduce the quantity to continue
                      </span>
                    ) : maxStock === null ? (
                      <span style={{ fontSize: '0.74rem', color: '#166534', fontWeight: 600 }}>
                        ✓ In Stock
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.74rem', color: '#166534', fontWeight: 600 }}>
                        ✓ In Stock ({maxStock} available)
                      </span>
                    )}
                  </div>

                  {/* Quantity and Line Total */}
                  <div className="bag-line-actions">
                    {/* Quantity Selector */}
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
                        onClick={() =>
                          // Going below 1 removes the line instead of asking
                          // the API for an invalid quantity.
                          quantity <= 1 ? removeFromBag(pId) : updateBagQuantity(pId, quantity - 1)
                        }
                        aria-label={quantity <= 1 ? `Remove ${item.product_name} from bag` : 'Decrease quantity'}
                        style={{
                          width: '30px',
                          height: '30px',
                          border: 'none',
                          background: 'none',
                          cursor: 'pointer',
                          fontSize: '1rem',
                          fontWeight: 700,
                          color: '#1F191B',
                        }}
                      >
                        -
                      </button>
                      <span
                        style={{
                          width: '32px',
                          textAlign: 'center',
                          fontSize: '0.84rem',
                          fontWeight: 700,
                          color: '#1F191B',
                        }}
                      >
                        {item.quantity}
                      </span>
                      <button
                        type="button"
                        onClick={() => updateBagQuantity(pId, quantity + 1)}
                        disabled={atMaxStock}
                        aria-label="Increase quantity"
                        style={{
                          width: '30px',
                          height: '30px',
                          border: 'none',
                          background: 'none',
                          cursor: atMaxStock ? 'not-allowed' : 'pointer',
                          fontSize: '1rem',
                          fontWeight: 700,
                          color: atMaxStock ? '#C4B5B8' : '#1F191B',
                        }}
                      >
                        +
                      </button>
                    </div>

                    {/* Total Price for line */}
                    <span
                      style={{
                        fontSize: '1.15rem',
                        fontWeight: 700,
                        color: '#B8505E',
                        fontFamily: "'Plus Jakarta Sans', sans-serif",
                      }}
                    >
                      ₹{lineTotal.toLocaleString('en-IN')}
                    </span>

                    {/* Delete Item */}
                    <button
                      type="button"
                      onClick={() => removeFromBag(pId)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#E04D60',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <Trash2 size={13} />
                      <span>Remove</span>
                    </button>
                  </div>
                </div>
              );
                })}
                </div>
              </section>
            ))}
          </div>

          {/* RIGHT: Order Summary Card */}
          <div
            style={{
              padding: '2rem',
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              border: '1px solid rgba(216, 114, 126, 0.25)',
              boxShadow: '0 8px 30px rgba(184, 80, 94, 0.08)',
              position: 'sticky',
              top: '120px',
            }}
          >
            <h2
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.5rem',
                fontWeight: 700,
                color: '#1F191B',
                margin: '0 0 1.25rem 0',
                borderBottom: '1px solid #F0E2E0',
                paddingBottom: '0.75rem',
              }}
            >
              Order Summary
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
                <span>Subtotal ({totalItems} items)</span>
                <span style={{ fontWeight: 600, color: '#1F191B' }}>
                  ₹{Number(subtotal).toLocaleString('en-IN')}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
                <span>Estimated Courier Delivery</span>
                <span style={{ fontWeight: 700, color: '#16A34A' }}>FREE</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
                <span>Goods & Service Tax</span>
                <span style={{ color: '#9E8F94' }}>Included in price</span>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  paddingTop: '1rem',
                  borderTop: '1px solid #F0E2E0',
                  marginTop: '0.5rem',
                }}
              >
                <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1F191B' }}>Total Amount</span>
                <span
                  style={{
                    fontSize: '1.6rem',
                    fontWeight: 800,
                    color: '#B8505E',
                    fontFamily: "'Plus Jakarta Sans', sans-serif",
                  }}
                >
                  ₹{Number(total).toLocaleString('en-IN')}
                </span>
              </div>
            </div>

            {/* Proceed to Checkout CTA */}
            <button
              type="button"
              className="tarika-btn-primary"
              onClick={handleCheckoutClick}
              style={{
                width: '100%',
                padding: '0.95rem 1.5rem',
                fontSize: '0.95rem',
                marginBottom: '1rem',
              }}
            >
              <span>Proceed to Checkout</span>
              <ArrowRight size={16} />
            </button>

            <p style={{ margin: 0, fontSize: '0.72rem', color: '#9E8F94', textAlign: 'center' }}>
              🔒 Protected by 256-Bit SSL Encryption
            </p>

            {/* Perks */}
            <div
              style={{
                marginTop: '1.5rem',
                paddingTop: '1rem',
                borderTop: '1px solid #F0E2E0',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Truck size={14} color="#8E3642" />
                <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>Complimentary Express Courier</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={14} color="#8E3642" />
                <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>100% Genuine Luxury Guarantee</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Empty Bag State */
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
            <ShoppingBag size={32} color="#B8505E" />
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
            Your Shopping Bag is Empty
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.92rem', lineHeight: 1.6, margin: '0 0 2rem 0' }}>
            Explore trending couture, fresh seasonal drops, and limited edition garments tailored for you.
          </p>
          <Link to="/customer/shop" className="tarika-btn-primary">
            <span>Discover The Catalog</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </div>
  );
}
