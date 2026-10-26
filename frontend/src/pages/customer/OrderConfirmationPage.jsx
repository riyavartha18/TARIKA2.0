import React, { useEffect, useState } from 'react';
import { useParams, useLocation, Link } from 'react-router-dom';
import {
  CheckCircle2,
  Copy,
  Check,
  ShoppingBag,
  ArrowRight,
  Package,
  Truck,
  CreditCard,
  MapPin,
  Calendar,
  Sparkles
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { getOrderDetails } from '../../services/api';

export default function OrderConfirmationPage() {
  const { orderId } = useParams();
  const location = useLocation();
  const { token } = useAuth();

  const [order, setOrder] = useState(location.state?.order || null);
  const [loading, setLoading] = useState(!order);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!order && orderId && token) {
      setLoading(true);
      getOrderDetails(token, orderId).then((res) => {
        if (res.success) {
          setOrder(res.order);
        } else {
          setError(res.error || 'Failed to load order details.');
        }
        setLoading(false);
      });
    }
  }, [order, orderId, token]);

  const handleCopyOrderId = () => {
    if (order?.order_id) {
      navigator.clipboard.writeText(order.order_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '6rem 2rem', textAlign: 'center', color: '#B8505E' }}>
        <div style={{ fontSize: '1.2rem', fontWeight: 600 }}>Loading your confirmed order...</div>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div
        style={{
          padding: '4rem 2rem',
          textAlign: 'center',
          backgroundColor: '#FFFFFF',
          borderRadius: '24px',
          border: '1px solid #F0E2E0',
          maxWidth: '560px',
          margin: '3rem auto',
        }}
      >
        <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.8rem', color: '#1F191B', marginBottom: '1rem' }}>
          Order Not Found
        </h2>
        <p style={{ color: '#6B5E63', marginBottom: '2rem' }}>
          {error || "We couldn't retrieve the specified order. It may belong to another account or does not exist."}
        </p>
        <Link to="/customer/shop" className="tarika-btn-primary">
          <span>Explore Catalog</span>
          <ArrowRight size={16} />
        </Link>
      </div>
    );
  }

  const items = order.items || [];
  const paymentMethodLabel = order.payment_method === 'COD'
    ? 'Cash on Delivery'
    : (order.payment_method === 'ONLINE' ? 'Online Payment' : order.payment_method);
  const isPaid = order.payment_status?.toLowerCase() === 'paid';

  return (
    <div style={{ paddingBottom: '5rem', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Luxury Celebration Hero Header */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '28px',
          border: '1px solid rgba(216, 114, 126, 0.25)',
          boxShadow: '0 10px 40px rgba(184, 80, 94, 0.08)',
          padding: '3rem 2.5rem',
          textAlign: 'center',
          marginBottom: '2.5rem',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            backgroundColor: '#FBF1F0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.25rem auto',
            border: '2px solid #EAD4D7',
          }}
        >
          <CheckCircle2 size={44} color="#16A34A" />
        </div>

        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '6px' }}>
          <Sparkles size={16} color="#B8505E" />
          <span style={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            Atelier Order Confirmed
          </span>
        </div>

        <h1
          style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: '2.5rem',
            fontWeight: 700,
            color: '#1F191B',
            margin: '0 0 0.75rem 0',
          }}
        >
          Thank you for choosing TARIKA
        </h1>

        <p style={{ color: '#6B5E63', fontSize: '1rem', maxWidth: '640px', margin: '0 auto 1.5rem auto', lineHeight: 1.6 }}>
          Your order has been placed successfully. Our master artisans are preparing your wardrobe pieces for express dispatch.
        </p>

        {/* Order ID Pill with Copy Action */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: '#FAF7F5',
            padding: '0.65rem 1.25rem',
            borderRadius: '9999px',
            border: '1px solid #EAD4D7',
          }}
        >
          <span style={{ fontSize: '0.86rem', color: '#6B5E63' }}>Order ID:</span>
          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1F191B', fontFamily: 'monospace' }}>
            {order.order_id}
          </span>
          <button
            type="button"
            onClick={handleCopyOrderId}
            title="Copy Order ID"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: copied ? '#16A34A' : '#8E3642',
              display: 'flex',
              alignItems: 'center',
              padding: '2px',
            }}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>
      </div>

      {/* 2-Column Content Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)',
          gap: '2.5rem',
          alignItems: 'start',
        }}
        className="confirmation-grid"
      >
        {/* LEFT: Ordered Items Breakdown */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '24px',
            border: '1px solid rgba(240, 226, 224, 0.95)',
            boxShadow: '0 4px 20px rgba(184, 80, 94, 0.04)',
            padding: '2rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1.5rem', borderBottom: '1px solid #FAF0EE', paddingBottom: '0.85rem' }}>
            <Package size={20} color="#B8505E" />
            <h2 style={{ fontSize: '1.3rem', fontFamily: "'Playfair Display', serif", fontWeight: 700, margin: 0, color: '#1F191B' }}>
              Ordered Items ({items.length})
            </h2>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginBottom: '1.5rem' }}>
            {items.map((item) => (
              <div
                key={item.order_item_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1.25rem',
                  padding: '1rem',
                  borderRadius: '16px',
                  backgroundColor: '#FAF7F5',
                  border: '1px solid #F0E2E0',
                }}
              >
                <img
                  src={item.image || 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80'}
                  alt={item.product_name}
                  style={{
                    width: '68px',
                    height: '84px',
                    borderRadius: '10px',
                    objectFit: 'cover',
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3 style={{ margin: '0 0 4px 0', fontSize: '0.98rem', fontWeight: 600, color: '#1F191B' }}>
                    {item.product_name}
                  </h3>
                  {item.sku && (
                    <span style={{ fontSize: '0.74rem', color: '#8E3642', fontWeight: 600 }}>
                      SKU: {item.sku}
                    </span>
                  )}
                  <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#6B5E63' }}>
                    Quantity: <strong>{item.quantity}</strong> × ₹{Number(item.unit_price).toLocaleString('en-IN')}
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#B8505E' }}>
                    ₹{Number(item.subtotal).toLocaleString('en-IN')}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Totals Summary */}
          <div style={{ borderTop: '1px solid #F0E2E0', paddingTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
              <span>Subtotal</span>
              <span style={{ fontWeight: 600, color: '#1F191B' }}>
                ₹{Number(order.total_amount).toLocaleString('en-IN')}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
              <span>Delivery</span>
              <span style={{ fontWeight: 700, color: '#16A34A' }}>FREE</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
              <span>Discount</span>
              <span style={{ color: '#9E8F94' }}>
                ₹{Number(order.discount_amount || 0).toLocaleString('en-IN')}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                borderTop: '1px solid #F0E2E0',
                paddingTop: '0.85rem',
                marginTop: '4px',
              }}
            >
              <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1F191B' }}>Total Amount</span>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: '#B8505E' }}>
                ₹{Number(order.total_amount).toLocaleString('en-IN')}
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT: Delivery & Dispatch Metadata */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Order Details Card */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              border: '1px solid rgba(240, 226, 224, 0.95)',
              boxShadow: '0 4px 20px rgba(184, 80, 94, 0.04)',
              padding: '2rem',
            }}
          >
            <h3
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.25rem',
                fontWeight: 700,
                color: '#1F191B',
                margin: '0 0 1.25rem 0',
                borderBottom: '1px solid #FAF0EE',
                paddingBottom: '0.75rem',
              }}
            >
              Order Information
            </h3>

            {/* Delivery Address */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '1.25rem' }}>
              <MapPin size={18} color="#B8505E" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase' }}>
                  Delivery Address
                </span>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#1F191B', lineHeight: 1.5, fontWeight: 500 }}>
                  {/* public.orders has no address column, so nothing is stored */}
                  {order.shipping_address || 'Address provided at checkout'}
                </p>
                {order.customer_name && (
                  <span style={{ fontSize: '0.8rem', color: '#6B5E63' }}>
                    Recipient: {order.customer_name}
                  </span>
                )}
              </div>
            </div>

            {/* Payment Method */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '1.25rem' }}>
              <CreditCard size={18} color="#B8505E" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase' }}>
                  Payment Method & Status
                </span>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#1F191B', fontWeight: 600 }}>
                  {paymentMethodLabel}
                </p>
                <div style={{ marginTop: '4px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '9999px',
                      backgroundColor: isPaid ? '#DCFCE7' : '#FEF3C7',
                      color: isPaid ? '#166534' : '#92400E',
                      textTransform: 'capitalize',
                    }}
                  >
                    Payment: {order.payment_status || 'Pending'}
                  </span>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '9999px',
                      backgroundColor: '#E0F2FE',
                      color: '#0369A1',
                      textTransform: 'capitalize',
                    }}
                  >
                    Order: {order.order_status || 'Confirmed'}
                  </span>
                </div>
              </div>
            </div>

            {/* Estimated Timeline */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '1.25rem' }}>
              <Calendar size={18} color="#B8505E" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <span style={{ fontSize: '0.76rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase' }}>
                  Order Date & Delivery
                </span>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#1F191B', fontWeight: 500 }}>
                  Placed on {order.order_date || 'Today'}
                </p>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#16A34A', fontWeight: 600 }}>
                  Estimated Delivery: 3 to 5 business days
                </p>
              </div>
            </div>

            {/* Warehouse */}
            {order.warehouse_name && (
              <div style={{ display: 'flex', gap: '12px', borderTop: '1px solid #F0E2E0', paddingTop: '1rem' }}>
                <Truck size={18} color="#8E3642" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <span style={{ fontSize: '0.74rem', color: '#9E8F94' }}>Dispatch Fulfillment Center:</span>
                  <p style={{ margin: '2px 0 0 0', fontSize: '0.84rem', fontWeight: 600, color: '#1F191B' }}>
                    {order.warehouse_name}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Action CTAs */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <Link
              to="/customer/shop"
              className="tarika-btn-primary"
              style={{
                width: '100%',
                padding: '0.95rem 1.5rem',
                fontSize: '0.95rem',
                textAlign: 'center',
                textDecoration: 'none',
              }}
            >
              <span>Continue Shopping</span>
              <ArrowRight size={16} />
            </Link>

            <Link
              to="/customer/bag"
              style={{
                width: '100%',
                padding: '0.85rem 1.5rem',
                fontSize: '0.88rem',
                textAlign: 'center',
                textDecoration: 'none',
                color: '#8E3642',
                backgroundColor: '#FFFFFF',
                borderRadius: '9999px',
                border: '1px solid #E5D7D5',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <ShoppingBag size={15} />
              <span>View Shopping Bag</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
