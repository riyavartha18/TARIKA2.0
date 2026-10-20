import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShoppingBag,
  Package,
  Truck,
  CheckCircle2,
  Clock,
  RotateCcw,
  XCircle,
  ChevronRight,
  ExternalLink,
  Copy,
  Check,
  MapPin,
  Calendar,
  CreditCard,
  Banknote,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
  Sparkles,
  ArrowRight,
  X,
  Star,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { useCustomer } from '../../context/CustomerContext';
import { getCustomerOrders, submitProductReview, requestCustomerReturn } from '../../services/api';

export default function MyOrdersPage() {
  const { token, user } = useAuth();
  const { addToast, openProductDetail } = useCustomer();
  const navigate = useNavigate();

  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('ALL');

  // Modals state
  const [detailsModalOrder, setDetailsModalOrder] = useState(null);
  const [trackingModalOrder, setTrackingModalOrder] = useState(null);
  const [copiedId, setCopiedId] = useState(false);

  // Rate & Review Modal state
  const [reviewModalItem, setReviewModalItem] = useState(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [hoverRating, setHoverRating] = useState(0);
  const [reviewText, setReviewText] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewError, setReviewError] = useState('');

  // Return Request Modal state
  const [returnModalItem, setReturnModalItem] = useState(null);
  const [returnReason, setReturnReason] = useState('Quality Issue');
  const [returnCondition, setReturnCondition] = useState('Unused, original packaging with tags intact');
  const [submittingReturn, setSubmittingReturn] = useState(false);
  const [returnError, setReturnError] = useState('');

  // Return Tracking Modal state
  const [returnTrackingItem, setReturnTrackingItem] = useState(null);

  const handleOpenReturnModal = (item) => {
    setReturnModalItem(item);
    setReturnReason('Quality Issue');
    setReturnCondition('Unused, original packaging with tags intact');
    setReturnError('');
  };

  const handleSubmitReturnRequest = async (e) => {
    e.preventDefault();
    if (!returnModalItem) return;
    if (!returnReason.trim()) {
      setReturnError('Please select or specify a reason for return.');
      return;
    }

    setSubmittingReturn(true);
    setReturnError('');

    const res = await requestCustomerReturn(
      returnModalItem.order.order_id,
      {
        order_item_id: returnModalItem.orderItemId,
        return_reason: returnReason,
        condition_on_return: returnCondition,
      },
      token
    );

    setSubmittingReturn(false);

    if (res.success && res.return) {
      addToast('Return request submitted successfully. Our atelier team will review it shortly.', 'success');
      // Update local state
      setOrders(prevOrders => {
        return prevOrders.map(ord => {
          if (ord.order_id === returnModalItem.order.order_id) {
            const updatedItems = (ord.items || []).map(itm => {
              if (itm.order_item_id === returnModalItem.orderItemId) {
                return { ...itm, return_info: res.return };
              }
              return itm;
            });
            return { ...ord, items: updatedItems };
          }
          return ord;
        });
      });
      setReturnModalItem(null);
    } else {
      setReturnError(res.error || 'Failed to submit return request.');
    }
  };

  useEffect(() => {
    document.title = 'My Orders — TARIKA Luxury';
  }, []);

  const fetchOrders = async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const res = await getCustomerOrders(token);
      if (res.success) {
        setOrders(res.orders || []);
      } else {
        setError(res.error || 'Failed to retrieve your order history.');
      }
    } catch (err) {
      setError('Network error retrieving your orders. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [token]);

  const handleCopyOrderId = (id) => {
    if (id) {
      navigator.clipboard.writeText(id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
      if (addToast) addToast('Order ID copied to clipboard.', 'info', 2000);
    }
  };

  // Status mapping and styling helpers
  const getStatusConfig = (status, delivery) => {
    const s = (status || '').toLowerCase();
    const dStatus = (delivery?.delivery_status || '').toLowerCase();

    if (s === 'delivered' || dStatus === 'delivered') {
      return {
        label: 'Delivered',
        bg: '#ECFDF5',
        color: '#065F46',
        border: 'rgba(16, 185, 129, 0.25)',
        icon: CheckCircle2,
      };
    }
    if (s === 'returned') {
      return {
        label: 'Returned',
        bg: '#FDF2F8',
        color: '#9D174D',
        border: 'rgba(219, 39, 119, 0.25)',
        icon: RotateCcw,
      };
    }
    if (s === 'cancelled') {
      return {
        label: 'Cancelled',
        bg: '#F3F4F6',
        color: '#4B5563',
        border: 'rgba(107, 114, 128, 0.25)',
        icon: XCircle,
      };
    }
    if (s === 'shipped' || dStatus === 'in transit' || dStatus === 'picked up') {
      return {
        label: 'Shipped & In Transit',
        bg: '#EFF6FF',
        color: '#1E40AF',
        border: 'rgba(59, 130, 246, 0.25)',
        icon: Truck,
      };
    }
    // confirmed or pending
    return {
      label: s === 'confirmed' ? 'Order Confirmed' : 'Processing',
      bg: '#FFFBEB',
      color: '#92400E',
      border: 'rgba(245, 158, 11, 0.25)',
      icon: Clock,
    };
  };

  // Flatten orders into PRODUCT-WISE items (Part 6 requirement)
  const productWiseItems = useMemo(() => {
    const items = [];
    orders.forEach((order) => {
      const orderItems = order.items || [];
      if (orderItems.length === 0) {
        // Fallback for an order without line items
        items.push({
          key: `${order.order_id}-general`,
          order,
          orderItem: null,
          productName: 'Haute Couture Order',
          sku: order.order_id.slice(0, 8),
          image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80',
          quantity: 1,
          unitPrice: Number(order.total_amount || 0),
          lineTotal: Number(order.total_amount || 0),
          status: order.order_status,
          delivery: order.delivery,
        });
      } else {
        orderItems.forEach((item, idx) => {
          items.push({
            key: `${order.order_id}-${item.order_item_id || idx}`,
            order,
            orderItem: item,
            productId: item.product_id,
            orderItemId: item.order_item_id,
            productName: item.product_name || 'Designer Ensemble',
            sku: item.sku || `SKU-${idx + 1}`,
            image:
              item.image ||
              'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80',
            quantity: item.quantity || 1,
            unitPrice: Number(item.unit_price || 0),
            lineTotal: Number(item.subtotal || item.unit_price * (item.quantity || 1) || 0),
            status: order.order_status,
            delivery: order.delivery,
            returnInfo: item.return_info,
            customerReview: item.customer_review || null,
          });
        });
      }
    });
    return items;
  }, [orders]);

  const handleOpenReviewModal = (productItem) => {
    setReviewModalItem(productItem);
    if (productItem.customerReview) {
      setReviewRating(Number(productItem.customerReview.rating) || 5);
      setReviewText(productItem.customerReview.review_text || '');
    } else {
      setReviewRating(5);
      setReviewText('');
    }
    setHoverRating(0);
    setReviewError('');
  };

  const handleCloseReviewModal = () => {
    setReviewModalItem(null);
    setReviewError('');
    setSubmittingReview(false);
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!token) {
      if (addToast) addToast('Please sign in to submit a review.', 'error');
      return;
    }
    if (!reviewModalItem || !reviewModalItem.productId) {
      setReviewError('Product identification is missing.');
      return;
    }
    if (!reviewText.trim()) {
      setReviewError('Please write your review thoughts before submitting.');
      return;
    }

    setSubmittingReview(true);
    setReviewError('');

    try {
      const res = await submitProductReview(token, reviewModalItem.productId, {
        rating: reviewRating,
        review_text: reviewText.trim(),
      });

      if (res.success) {
        const updatedReview = res.review || {
          review_id: 'rev-' + Date.now(),
          rating: reviewRating,
          review_text: reviewText.trim(),
          review_date: new Date().toISOString().split('T')[0],
          is_verified_purchase: true,
        };

        setOrders((prevOrders) =>
          prevOrders.map((ord) => {
            if (ord.order_id === reviewModalItem.order.order_id) {
              const updatedItems = (ord.items || []).map((itm) => {
                if (itm.product_id === reviewModalItem.productId) {
                  return { ...itm, customer_review: updatedReview };
                }
                return itm;
              });
              return { ...ord, items: updatedItems };
            }
            return ord;
          })
        );

        if (addToast) {
          addToast('Thank you! Your rating and review have been published.', 'success', 4000);
        }
        handleCloseReviewModal();
      } else {
        setReviewError(res.error || 'Failed to submit review. Please try again.');
      }
    } catch (err) {
      setReviewError('Network error submitting your review. Please try again.');
    } finally {
      setSubmittingReview(false);
    }
  };

  // Tab Filtering
  const filteredProductItems = useMemo(() => {
    if (activeTab === 'ALL') return productWiseItems;
    if (activeTab === 'PROCESSING') {
      return productWiseItems.filter((i) => {
        const s = (i.status || '').toLowerCase();
        return s === 'confirmed' || s === 'pending';
      });
    }
    if (activeTab === 'SHIPPED') {
      return productWiseItems.filter((i) => {
        const s = (i.status || '').toLowerCase();
        const d = (i.delivery?.delivery_status || '').toLowerCase();
        return s === 'shipped' || d === 'in transit' || d === 'picked up';
      });
    }
    if (activeTab === 'DELIVERED') {
      return productWiseItems.filter((i) => {
        const s = (i.status || '').toLowerCase();
        const d = (i.delivery?.delivery_status || '').toLowerCase();
        return s === 'delivered' || d === 'delivered';
      });
    }
    if (activeTab === 'RETURNED') {
      return productWiseItems.filter((i) => {
        const s = (i.status || '').toLowerCase();
        return s === 'returned' || Boolean(i.returnInfo);
      });
    }
    if (activeTab === 'CANCELLED') {
      return productWiseItems.filter((i) => (i.status || '').toLowerCase() === 'cancelled');
    }
    return productWiseItems;
  }, [productWiseItems, activeTab]);

  return (
    <div style={{ paddingBottom: '5rem', maxWidth: '1440px', margin: '0 auto' }}>
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .order-card-hover {
          transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .order-card-hover:hover {
          transform: translateY(-3px);
          box-shadow: 0 12px 32px rgba(184, 80, 94, 0.08) !important;
          border-color: rgba(216, 114, 126, 0.45) !important;
        }
        .tab-btn {
          transition: all 0.2s ease;
          border: 1px solid transparent;
        }
        .tab-btn:hover {
          background-color: #FBF1F0 !important;
          color: #8E3642 !important;
        }
        .timeline-step-completed {
          background-color: #16A34A;
          color: #FFFFFF;
        }
        .timeline-step-active {
          background-color: #B8505E;
          color: #FFFFFF;
          box-shadow: 0 0 0 4px rgba(184, 80, 94, 0.2);
        }
        .timeline-step-inactive {
          background-color: #F0E2E0;
          color: #9E8F94;
        }
      `}</style>

      {/* Breadcrumb Navigation */}
      <nav
        aria-label="Breadcrumb"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '1.75rem',
          fontSize: '0.84rem',
          color: '#9E8F94',
        }}
      >
        <Link
          to="/customer"
          style={{
            color: '#8E3642',
            textDecoration: 'none',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span>Home</span>
        </Link>
        <ChevronRight size={14} />
        <span style={{ color: '#1F191B', fontWeight: 700 }}>My Orders</span>
      </nav>

      {/* Part 4: Header & Tagline */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          gap: '1.5rem',
          marginBottom: '2rem',
          borderBottom: '1px solid rgba(216, 114, 126, 0.2)',
          paddingBottom: '1.5rem',
        }}
      >
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: '#8E3642',
              marginBottom: '4px',
            }}
          >
            <Sparkles size={15} color="#B8505E" />
            <span
              style={{
                fontSize: '0.76rem',
                fontWeight: 700,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
              }}
            >
              Wardrobe Archive
            </span>
          </div>
          <h1
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '2.4rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: '0 0 6px 0',
              letterSpacing: '-0.01em',
            }}
          >
            My Orders
          </h1>
          <p style={{ margin: 0, fontSize: '0.92rem', color: '#6B5E63', fontStyle: 'italic' }}>
            Your style journey, all in one place.
          </p>
        </div>

        {/* Refresh Action */}
        <button
          type="button"
          onClick={fetchOrders}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '0.5rem 1rem',
            borderRadius: '9999px',
            backgroundColor: '#FFFFFF',
            border: '1px solid rgba(216, 114, 126, 0.25)',
            color: '#8E3642',
            fontSize: '0.84rem',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} style={loading ? { animation: 'spin 1s linear infinite' } : {}} />
          <span>Refresh Orders</span>
        </button>
      </div>

      {/* Part 4: Authentic Status Filter Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          paddingBottom: '1rem',
          marginBottom: '2rem',
          scrollbarWidth: 'none',
        }}
      >
        {[
          { key: 'ALL', label: 'All Orders', count: productWiseItems.length },
          {
            key: 'PROCESSING',
            label: 'Confirmed / Processing',
            count: productWiseItems.filter((i) => ['confirmed', 'pending'].includes((i.status || '').toLowerCase())).length,
          },
          {
            key: 'SHIPPED',
            label: 'Shipped',
            count: productWiseItems.filter((i) => (i.status || '').toLowerCase() === 'shipped' || ['in transit', 'picked up'].includes((i.delivery?.delivery_status || '').toLowerCase())).length,
          },
          {
            key: 'DELIVERED',
            label: 'Delivered',
            count: productWiseItems.filter((i) => (i.status || '').toLowerCase() === 'delivered' || (i.delivery?.delivery_status || '').toLowerCase() === 'delivered').length,
          },
          {
            key: 'RETURNED',
            label: 'Returned',
            count: productWiseItems.filter((i) => (i.status || '').toLowerCase() === 'returned' || Boolean(i.returnInfo)).length,
          },
          {
            key: 'CANCELLED',
            label: 'Cancelled',
            count: productWiseItems.filter((i) => (i.status || '').toLowerCase() === 'cancelled').length,
          },
        ].map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className="tab-btn"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '0.65rem 1.15rem',
                borderRadius: '9999px',
                fontSize: '0.84rem',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                backgroundColor: isActive ? '#B8505E' : '#FFFFFF',
                color: isActive ? '#FFFFFF' : '#6B5E63',
                border: isActive ? '1px solid #B8505E' : '1px solid #EAD4D7',
                boxShadow: isActive ? '0 4px 14px rgba(184, 80, 94, 0.25)' : 'none',
              }}
            >
              <span>{tab.label}</span>
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  padding: '1px 7px',
                  borderRadius: '9999px',
                  backgroundColor: isActive ? 'rgba(255, 255, 255, 0.25)' : '#FAF3F2',
                  color: isActive ? '#FFFFFF' : '#8E3642',
                }}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Loading Skeleton */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '20px',
                border: '1px solid #F0E2E0',
                padding: '1.75rem',
                display: 'flex',
                gap: '1.5rem',
                alignItems: 'center',
              }}
            >
              <div
                style={{
                  width: '90px',
                  height: '115px',
                  borderRadius: '12px',
                  backgroundColor: '#FAF0EE',
                }}
              />
              <div style={{ flex: 1 }}>
                <div style={{ width: '40%', height: '20px', backgroundColor: '#FAF0EE', borderRadius: '4px', marginBottom: '8px' }} />
                <div style={{ width: '25%', height: '14px', backgroundColor: '#FAF0EE', borderRadius: '4px', marginBottom: '16px' }} />
                <div style={{ width: '20%', height: '18px', backgroundColor: '#FAF0EE', borderRadius: '4px' }} />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        /* Error State */
        <div
          style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '24px',
            border: '1px solid #FCA5A5',
            padding: '3rem 2rem',
            textAlign: 'center',
            maxWidth: '560px',
            margin: '2rem auto',
            boxShadow: '0 8px 30px rgba(220, 38, 38, 0.05)',
          }}
        >
          <AlertCircle size={36} color="#DC2626" style={{ margin: '0 auto 1rem auto' }} />
          <h2 style={{ fontFamily: "'Playfair Display', serif", fontSize: '1.5rem', color: '#1F191B', marginBottom: '0.5rem' }}>
            Unable to Load Orders
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
            {error}
          </p>
          <button
            type="button"
            onClick={fetchOrders}
            className="tarika-btn-primary"
            style={{ display: 'inline-flex', padding: '0.75rem 1.5rem' }}
          >
            <span>Try Again</span>
          </button>
        </div>
      ) : filteredProductItems.length === 0 ? (
        /* Part 18: Empty State */
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
              margin: '0 auto 1.25rem auto',
              border: '1px solid #EAD4D7',
            }}
          >
            <Package size={32} color="#B8505E" />
          </div>
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.75rem',
              fontWeight: 700,
              color: '#1F191B',
              marginBottom: '0.5rem',
            }}
          >
            {activeTab === 'ALL' ? 'No orders yet' : `No ${activeTab.toLowerCase()} orders`}
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.95rem', marginBottom: '2rem', lineHeight: 1.5 }}>
            {activeTab === 'ALL'
              ? 'Your next favourite piece is waiting for you.'
              : `You do not have any orders matching the "${activeTab.toLowerCase()}" filter right now.`}
          </p>
          <Link
            to="/customer/shop"
            className="tarika-btn-primary"
            style={{ textDecoration: 'none', display: 'inline-flex', padding: '0.85rem 1.75rem' }}
          >
            <span>Explore Collections</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        /* Part 6: PRODUCT-WISE ORDER CARDS GRID */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {filteredProductItems.map((item) => {
            const statusConfig = getStatusConfig(item.status, item.delivery);
            const StatusIcon = statusConfig.icon;
            const isDelivered = (item.status || '').toLowerCase() === 'delivered' || (item.delivery?.delivery_status || '').toLowerCase() === 'delivered';
            const isReturned = (item.status || '').toLowerCase() === 'returned' || Boolean(item.returnInfo);

            return (
              <div
                key={item.key}
                className="order-card-hover"
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '24px',
                  border: '1px solid rgba(240, 226, 224, 0.95)',
                  boxShadow: '0 4px 20px rgba(184, 80, 94, 0.04)',
                  padding: '1.5rem 1.75rem',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '1.5rem',
                  position: 'relative',
                }}
              >
                {/* 1. Actual Product Image (Click to View Product Details) */}
                <div
                  onClick={() => item.productId && openProductDetail && openProductDetail(item.productId)}
                  title={item.productId ? 'View product details' : ''}
                  style={{
                    width: '95px',
                    height: '125px',
                    borderRadius: '14px',
                    overflow: 'hidden',
                    flexShrink: 0,
                    backgroundColor: '#FAF7F5',
                    border: '1px solid #F0E2E0',
                    cursor: item.productId ? 'pointer' : 'default',
                    transition: 'transform 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (item.productId) e.currentTarget.style.transform = 'scale(1.03)';
                  }}
                  onMouseLeave={(e) => {
                    if (item.productId) e.currentTarget.style.transform = 'scale(1)';
                  }}
                >
                  <img
                    src={item.image}
                    alt={item.productName}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                </div>

                {/* 2. Product Name, Quantity & Pricing */}
                <div style={{ flex: 1, minWidth: '220px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        color: '#8E3642',
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                      }}
                    >
                      {item.sku}
                    </span>
                  </div>

                  <h3
                    onClick={() => item.productId && openProductDetail && openProductDetail(item.productId)}
                    title={item.productId ? 'View product details' : ''}
                    style={{
                      fontFamily: "'Playfair Display', serif",
                      fontSize: '1.25rem',
                      fontWeight: 700,
                      color: '#1F191B',
                      margin: '0 0 6px 0',
                      cursor: item.productId ? 'pointer' : 'default',
                    }}
                    onMouseEnter={(e) => {
                      if (item.productId) e.currentTarget.style.color = '#B8505E';
                    }}
                    onMouseLeave={(e) => {
                      if (item.productId) e.currentTarget.style.color = '#1F191B';
                    }}
                  >
                    {item.productName}
                  </h3>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.84rem', color: '#6B5E63' }}>
                      Quantity: <strong style={{ color: '#1F191B' }}>{item.quantity}</strong>
                    </span>
                    <span style={{ color: '#D8727E' }}>•</span>
                    <span
                      style={{
                        fontSize: '1.05rem',
                        fontWeight: 800,
                        color: '#B8505E',
                        fontFamily: "'Plus Jakarta Sans', sans-serif",
                      }}
                    >
                      ₹{item.lineTotal.toLocaleString('en-IN')}
                    </span>
                  </div>

                  {/* Delivery Status / Date Information Pill */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                    {isDelivered && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          color: '#065F46',
                        }}
                      >
                        <CheckCircle2 size={14} color="#059669" />
                        <span>
                          Delivered {item.delivery?.actual_delivery_date ? `on ${item.delivery.actual_delivery_date}` : (item.order.order_date ? `on ${item.order.order_date}` : '')}
                        </span>
                      </span>
                    )}

                    {!isDelivered && item.delivery?.expected_delivery_date && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          color: '#1E40AF',
                        }}
                      >
                        <Truck size={14} color="#2563EB" />
                        <span>Expected by {item.delivery.expected_delivery_date}</span>
                      </span>
                    )}

                    {!isDelivered && !item.delivery?.expected_delivery_date && (
                      <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                        Order placed on {item.order.order_date || 'Recently'}
                      </span>
                    )}

                    {/* Return Indicator Pill */}
                    {isReturned && (
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.74rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '9999px',
                          backgroundColor: '#FDF2F8',
                          color: '#9D174D',
                          border: '1px solid rgba(219, 39, 119, 0.25)',
                        }}
                      >
                        <RotateCcw size={12} />
                        <span>Return {item.returnInfo?.return_status ? `(${item.returnInfo.return_status})` : 'Processed'}</span>
                      </span>
                    )}
                  </div>

                  {/* Customer's Submitted Rating Display (Numeric rating and stars only - No review text) */}
                  {item.customerReview && (
                    <div
                      style={{
                        marginTop: '10px',
                        padding: '8px 14px',
                        backgroundColor: '#FAF7F5',
                        borderRadius: '12px',
                        border: '1px solid rgba(216, 114, 126, 0.2)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '12px',
                        flexWrap: 'wrap',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#8E3642' }}>
                          Your Rating:
                        </span>
                        <div style={{ display: 'flex', gap: '2px', color: '#EAB308' }}>
                          {[1, 2, 3, 4, 5].map((s) => (
                            <Star
                              key={s}
                              size={13}
                              fill={s <= Number(item.customerReview.rating) ? '#EAB308' : '#F1E8E6'}
                              color={s <= Number(item.customerReview.rating) ? '#CA8A04' : '#D1C2C0'}
                            />
                          ))}
                        </div>
                        <span style={{ fontSize: '0.78rem', color: '#6B5E63', fontWeight: 600 }}>
                          ({item.customerReview.rating}/5)
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleOpenReviewModal(item)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#B8505E',
                          fontSize: '0.76rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          padding: 0,
                        }}
                      >
                        Edit Review
                      </button>
                    </div>
                  )}
                </div>

                {/* 3. Status Badge */}
                <div style={{ textAlign: 'right', minWidth: '160px' }}>
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 14px',
                      borderRadius: '9999px',
                      backgroundColor: statusConfig.bg,
                      color: statusConfig.color,
                      border: `1px solid ${statusConfig.border}`,
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      marginBottom: '1rem',
                    }}
                  >
                    <StatusIcon size={14} />
                    <span>{statusConfig.label}</span>
                  </div>

                    {/* 4. Action Buttons */}
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                    {item.productId && !item.customerReview && (
                      <button
                        type="button"
                        onClick={() => handleOpenReviewModal(item)}
                        style={{
                          padding: '0.55rem 1rem',
                          borderRadius: '9999px',
                          backgroundColor: '#FFF7ED',
                          border: '1px solid #FDBA74',
                          color: '#C2410C',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          transition: 'all 0.2s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#FFEDD5';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#FFF7ED';
                        }}
                      >
                        <Star size={13} fill="#FB923C" color="#EA580C" />
                        <span>Rate this product</span>
                      </button>
                    )}

                    {/* Return Request or Return Status Button */}
                    {(() => {
                      const isDelivered = (item.status || '').toLowerCase() === 'delivered' || (item.delivery?.delivery_status || '').toLowerCase() === 'delivered';
                      const ret = item.returnInfo;

                      if (ret) {
                        return (
                          <button
                            type="button"
                            onClick={() => setReturnTrackingItem(item)}
                            style={{
                              padding: '0.55rem 1rem',
                              borderRadius: '9999px',
                              backgroundColor: '#F3E8FF',
                              border: '1px solid #D8B4FE',
                              color: '#7E22CE',
                              fontSize: '0.82rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              transition: 'all 0.2s ease',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#EDE9FE';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#F3E8FF';
                            }}
                          >
                            <RotateCcw size={13} color="#7E22CE" />
                            <span>Return: {ret.return_status}</span>
                          </button>
                        );
                      }

                      if (isDelivered && item.orderItemId) {
                        return (
                          <button
                            type="button"
                            onClick={() => handleOpenReturnModal(item)}
                            style={{
                              padding: '0.55rem 1rem',
                              borderRadius: '9999px',
                              backgroundColor: '#FFF1F2',
                              border: '1px solid #FECDD3',
                              color: '#BE123C',
                              fontSize: '0.82rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              transition: 'all 0.2s ease',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#FFE4E6';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#FFF1F2';
                            }}
                          >
                            <RotateCcw size={13} color="#BE123C" />
                            <span>Request Return</span>
                          </button>
                        );
                      }

                      return null;
                    })()}

                    <button
                      type="button"
                      onClick={() => setDetailsModalOrder(item.order)}
                      style={{
                        padding: '0.55rem 1rem',
                        borderRadius: '9999px',
                        backgroundColor: '#FFFFFF',
                        border: '1px solid #E5D7D5',
                        color: '#1F191B',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#FAF7F5';
                        e.currentTarget.style.borderColor = '#B8505E';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#FFFFFF';
                        e.currentTarget.style.borderColor = '#E5D7D5';
                      }}
                    >
                      View Details
                    </button>

                    <button
                      type="button"
                      onClick={() => setTrackingModalOrder(item.order)}
                      style={{
                        padding: '0.55rem 1.1rem',
                        borderRadius: '9999px',
                        backgroundColor: '#B8505E',
                        border: '1px solid #B8505E',
                        color: '#FFFFFF',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        transition: 'all 0.2s ease',
                        boxShadow: '0 2px 10px rgba(184, 80, 94, 0.2)',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#8E3642')}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#B8505E')}
                    >
                      <Truck size={13} />
                      <span>Track Order</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Part 8, 11, 12: VIEW DETAILS MODAL */}
      {detailsModalOrder && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(31, 25, 27, 0.65)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            zIndex: 1000,
            animation: 'fadeIn 0.2s ease-out',
          }}
          onClick={() => setDetailsModalOrder(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '28px',
              maxWidth: '680px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              boxShadow: '0 20px 60px rgba(31, 25, 27, 0.2)',
              padding: '2.25rem',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              type="button"
              onClick={() => setDetailsModalOrder(null)}
              aria-label="Close"
              style={{
                position: 'absolute',
                top: '1.5rem',
                right: '1.5rem',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#9E8F94',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <X size={20} />
            </button>

            {/* Modal Title */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '4px' }}>
                <Package size={15} color="#B8505E" />
                <span style={{ fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  Order Details
                </span>
              </div>
              <h2
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.8rem',
                  fontWeight: 700,
                  margin: 0,
                  color: '#1F191B',
                }}
              >
                Order Summary
              </h2>
            </div>

            {/* ORDER INFORMATION (Order ID prominently inside details) */}
            <div
              style={{
                backgroundColor: '#FAF7F5',
                borderRadius: '16px',
                border: '1px solid #EAD4D7',
                padding: '1.25rem',
                marginBottom: '1.5rem',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '1rem',
              }}
            >
              <div>
                <span style={{ display: 'block', fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                  Order ID
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px' }}>
                  <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#1F191B', fontFamily: 'monospace' }}>
                    {detailsModalOrder.order_id.slice(0, 16)}...
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCopyOrderId(detailsModalOrder.order_id)}
                    title="Copy full Order ID"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: copiedId ? '#16A34A' : '#8E3642' }}
                  >
                    {copiedId ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              </div>

              <div>
                <span style={{ display: 'block', fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                  Order Date
                </span>
                <span style={{ display: 'block', fontSize: '0.84rem', fontWeight: 700, color: '#1F191B', marginTop: '3px' }}>
                  {detailsModalOrder.order_date || 'Recent'}
                </span>
              </div>

              <div>
                <span style={{ display: 'block', fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                  Order Status
                </span>
                <span
                  style={{
                    display: 'inline-block',
                    fontSize: '0.74rem',
                    fontWeight: 700,
                    textTransform: 'capitalize',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    backgroundColor: '#FAF3F2',
                    color: '#8E3642',
                    marginTop: '3px',
                  }}
                >
                  {detailsModalOrder.order_status || 'Confirmed'}
                </span>
              </div>

              <div>
                <span style={{ display: 'block', fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                  Payment Method
                </span>
                <span style={{ display: 'block', fontSize: '0.84rem', fontWeight: 700, color: '#1F191B', marginTop: '3px' }}>
                  {detailsModalOrder.payment_method === 'COD' ? 'Cash on Delivery' : detailsModalOrder.payment_method}
                </span>
              </div>
            </div>

            {/* PRODUCT DETAILS */}
            <div style={{ marginBottom: '1.75rem' }}>
              <h3 style={{ fontSize: '0.94rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.85rem' }}>
                Items Ordered ({(detailsModalOrder.items || []).length})
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {(detailsModalOrder.items || []).map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 12px',
                      borderRadius: '14px',
                      backgroundColor: '#FAF7F5',
                      border: '1px solid #F0E2E0',
                    }}
                  >
                    <div style={{ width: '48px', height: '62px', borderRadius: '8px', overflow: 'hidden', flexShrink: 0 }}>
                      <img src={item.image} alt={item.product_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h4 style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: '#1F191B', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {item.product_name}
                      </h4>
                      <p style={{ margin: '2px 0 0 0', fontSize: '0.76rem', color: '#6B5E63' }}>
                        Qty: <strong>{item.quantity}</strong> × ₹{Number(item.unit_price).toLocaleString('en-IN')}
                      </p>
                    </div>
                    <span style={{ fontSize: '0.92rem', fontWeight: 700, color: '#B8505E' }}>
                      ₹{Number(item.subtotal || item.unit_price * item.quantity).toLocaleString('en-IN')}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* PRICE SUMMARY */}
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '16px',
                border: '1px solid #F0E2E0',
                padding: '1.25rem',
                marginBottom: '1.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.86rem', color: '#6B5E63' }}>
                <span>Subtotal</span>
                <span style={{ fontWeight: 600, color: '#1F191B' }}>
                  ₹{Number(detailsModalOrder.total_amount).toLocaleString('en-IN')}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.86rem', color: '#6B5E63' }}>
                <span>Complimentary Delivery</span>
                <span style={{ fontWeight: 700, color: '#16A34A' }}>Free</span>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '1.05rem',
                  fontWeight: 800,
                  color: '#1F191B',
                  borderTop: '1px solid #F0E2E0',
                  paddingTop: '10px',
                  marginTop: '4px',
                }}
              >
                <span>Total Amount</span>
                <span style={{ color: '#B8505E' }}>
                  ₹{Number(detailsModalOrder.total_amount).toLocaleString('en-IN')}
                </span>
              </div>
            </div>

            {/* DELIVERY INFORMATION */}
            <div
              style={{
                borderRadius: '16px',
                border: '1px solid #F0E2E0',
                padding: '1.25rem',
                marginBottom: '1.5rem',
                backgroundColor: '#FAF7F5',
              }}
            >
              <h3 style={{ fontSize: '0.86rem', fontWeight: 700, color: '#8E3642', margin: '0 0 8px 0', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Delivery Information
              </h3>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <MapPin size={18} color="#B8505E" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <p style={{ margin: 0, fontSize: '0.86rem', color: '#1F191B', lineHeight: 1.5 }}>
                    {detailsModalOrder.shipping_address || 'Address provided at checkout'}
                  </p>
                  {detailsModalOrder.delivery?.delivery_partner && (
                    <p style={{ margin: '6px 0 0 0', fontSize: '0.78rem', color: '#6B5E63' }}>
                      Courier Partner: <strong>{detailsModalOrder.delivery.delivery_partner}</strong>
                    </p>
                  )}
                  {detailsModalOrder.delivery?.expected_delivery_date && (
                    <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: '#16A34A', fontWeight: 600 }}>
                      Expected Delivery: {detailsModalOrder.delivery.expected_delivery_date}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* RETURN & REFUND INFORMATION (Part 11 & 12) */}
            {detailsModalOrder.items?.some((i) => i.return_info) && (
              <div
                style={{
                  borderRadius: '16px',
                  border: '1px solid rgba(219, 39, 119, 0.3)',
                  backgroundColor: '#FDF2F8',
                  padding: '1.25rem',
                  marginBottom: '1.5rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <RotateCcw size={16} color="#9D174D" />
                  <h3 style={{ fontSize: '0.86rem', fontWeight: 700, color: '#9D174D', margin: 0, textTransform: 'uppercase' }}>
                    Return & Refund Status
                  </h3>
                </div>

                {detailsModalOrder.items
                  .filter((i) => i.return_info)
                  .map((item, idx) => {
                    const ret = item.return_info;
                    return (
                      <div
                        key={idx}
                        style={{
                          borderTop: idx > 0 ? '1px dashed rgba(219, 39, 119, 0.2)' : 'none',
                          paddingTop: idx > 0 ? '8px' : '0',
                          marginTop: idx > 0 ? '8px' : '0',
                        }}
                      >
                        <p style={{ margin: '0 0 4px 0', fontSize: '0.84rem', fontWeight: 600, color: '#1F191B' }}>
                          Product: {item.product_name}
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
                          <div>
                            <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Return Status:</span>
                            <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 700, color: '#9D174D', textTransform: 'capitalize' }}>
                              {ret.return_status}
                            </p>
                          </div>
                          <div>
                            <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Refund Amount:</span>
                            <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 700, color: '#1F191B' }}>
                              ₹{Number(ret.refund_amount || 0).toLocaleString('en-IN')}
                            </p>
                          </div>
                          <div>
                            <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Return Date:</span>
                            <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 600, color: '#1F191B' }}>
                              {ret.return_date || 'N/A'}
                            </p>
                          </div>
                          <div>
                            <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Reason:</span>
                            <p style={{ margin: 0, fontSize: '0.82rem', color: '#1F191B' }}>
                              {ret.return_reason || 'Customer request'}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}

            {/* Modal Bottom CTA */}
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button
                type="button"
                onClick={() => {
                  const targetOrder = detailsModalOrder;
                  setDetailsModalOrder(null);
                  setTrackingModalOrder(targetOrder);
                }}
                className="tarika-btn-primary"
                style={{ padding: '0.75rem 1.5rem', fontSize: '0.88rem' }}
              >
                <Truck size={15} />
                <span>Track This Order</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Part 9: TRACK ORDER MODAL */}
      {trackingModalOrder && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(31, 25, 27, 0.65)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            zIndex: 1000,
            animation: 'fadeIn 0.2s ease-out',
          }}
          onClick={() => setTrackingModalOrder(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '28px',
              maxWidth: '600px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              boxShadow: '0 20px 60px rgba(31, 25, 27, 0.2)',
              padding: '2.25rem',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              type="button"
              onClick={() => setTrackingModalOrder(null)}
              aria-label="Close"
              style={{
                position: 'absolute',
                top: '1.5rem',
                right: '1.5rem',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#9E8F94',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <X size={20} />
            </button>

            {/* Header */}
            <div style={{ marginBottom: '1.75rem' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#8E3642', marginBottom: '4px' }}>
                <Truck size={15} color="#B8505E" />
                <span style={{ fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  Live Fulfillment Tracking
                </span>
              </div>
              <h2
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.8rem',
                  fontWeight: 700,
                  margin: 0,
                  color: '#1F191B',
                }}
              >
                Track Your Wardrobe
              </h2>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#6B5E63' }}>
                Order #{trackingModalOrder.order_id.slice(0, 14)}...
              </p>
            </div>

            {/* Delivery Partner Banner */}
            {trackingModalOrder.delivery && (
              <div
                style={{
                  backgroundColor: '#FAF7F5',
                  borderRadius: '16px',
                  border: '1px solid #EAD4D7',
                  padding: '1rem 1.25rem',
                  marginBottom: '2rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '1rem',
                }}
              >
                <div>
                  <span style={{ fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                    Courier Express
                  </span>
                  <p style={{ margin: '2px 0 0 0', fontSize: '0.9rem', fontWeight: 700, color: '#1F191B' }}>
                    {trackingModalOrder.delivery.delivery_partner || 'Atelier Courier Service'}
                  </p>
                </div>
                {trackingModalOrder.delivery.expected_delivery_date && (
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                      Estimated Arrival
                    </span>
                    <p style={{ margin: '2px 0 0 0', fontSize: '0.9rem', fontWeight: 700, color: '#16A34A' }}>
                      {trackingModalOrder.delivery.expected_delivery_date}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* VERTICAL TRACKING TIMELINE (Derived strictly from real DB statuses) */}
            {(() => {
              const oStatus = (trackingModalOrder.order_status || '').toLowerCase();
              const dStatus = (trackingModalOrder.delivery?.delivery_status || '').toLowerCase();

              // Calculate active stage index:
              // 0: Order Placed
              // 1: Confirmed
              // 2: Processing / Dispatched
              // 3: In Transit
              // 4: Delivered
              let activeIndex = 0;
              if (oStatus === 'confirmed' || oStatus === 'pending') activeIndex = 1;
              if (oStatus === 'shipped' || trackingModalOrder.delivery?.dispatch_date || ['assigned', 'picked up'].includes(dStatus)) activeIndex = 2;
              if (dStatus === 'in transit') activeIndex = 3;
              if (oStatus === 'delivered' || dStatus === 'delivered') activeIndex = 4;
              if (oStatus === 'returned') activeIndex = 4;

              const stages = [
                {
                  title: 'Order Placed',
                  desc: trackingModalOrder.order_date ? `Received on ${trackingModalOrder.order_date}` : 'Order initiated',
                },
                {
                  title: 'Confirmed by Atelier',
                  desc: 'Inventory allocated & quality approved',
                },
                {
                  title: 'Dispatched from Fulfillment Center',
                  desc: trackingModalOrder.delivery?.dispatch_date
                    ? `Dispatched on ${trackingModalOrder.delivery.dispatch_date}`
                    : 'Packed in signature luxury gift box',
                },
                {
                  title: 'In Transit',
                  desc: trackingModalOrder.delivery?.delivery_partner
                    ? `With ${trackingModalOrder.delivery.delivery_partner}`
                    : 'On route with express courier partner',
                },
                {
                  title: oStatus === 'returned' ? 'Returned to Boutique' : 'Delivered to Doorstep',
                  desc: trackingModalOrder.delivery?.actual_delivery_date
                    ? `Completed on ${trackingModalOrder.delivery.actual_delivery_date}`
                    : (oStatus === 'delivered' ? 'Package handed over successfully' : 'Final doorstep delivery'),
                },
              ];

              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0', position: 'relative', marginBottom: '2rem' }}>
                  {stages.map((stg, i) => {
                    const isPassed = i < activeIndex;
                    const isCurrent = i === activeIndex;
                    const isFuture = i > activeIndex;

                    return (
                      <div key={i} style={{ display: 'flex', gap: '1.25rem', position: 'relative' }}>
                        {/* Connecting Line */}
                        {i < stages.length - 1 && (
                          <div
                            style={{
                              position: 'absolute',
                              top: '26px',
                              left: '14px',
                              width: '2px',
                              bottom: '-6px',
                              backgroundColor: isPassed ? '#16A34A' : '#F0E2E0',
                              zIndex: 1,
                            }}
                          />
                        )}

                        {/* Step Circle Indicator */}
                        <div
                          className={
                            isPassed
                              ? 'timeline-step-completed'
                              : isCurrent
                              ? 'timeline-step-active'
                              : 'timeline-step-inactive'
                          }
                          style={{
                            width: '30px',
                            height: '30px',
                            borderRadius: '50%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                            zIndex: 2,
                            fontSize: '0.8rem',
                            fontWeight: 700,
                          }}
                        >
                          {isPassed ? <Check size={16} /> : i + 1}
                        </div>

                        {/* Step Text Info */}
                        <div style={{ paddingBottom: '1.75rem' }}>
                          <h4
                            style={{
                              margin: '0 0 3px 0',
                              fontSize: '0.92rem',
                              fontWeight: isCurrent ? 700 : 600,
                              color: isFuture ? '#9E8F94' : '#1F191B',
                            }}
                          >
                            {stg.title}
                          </h4>
                          <p style={{ margin: 0, fontSize: '0.78rem', color: isFuture ? '#C4B5B8' : '#6B5E63' }}>
                            {stg.desc}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()}

            {/* Destination Address */}
            <div
              style={{
                backgroundColor: '#FAF7F5',
                borderRadius: '16px',
                border: '1px solid #EAD4D7',
                padding: '1rem 1.25rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
              }}
            >
              <MapPin size={18} color="#B8505E" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <span style={{ fontSize: '0.72rem', color: '#9E8F94', textTransform: 'uppercase', fontWeight: 600 }}>
                  Destination Address
                </span>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.84rem', color: '#1F191B' }}>
                  {trackingModalOrder.shipping_address || 'Shipping address on file'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================
          RATE & REVIEW MODAL
          ======================================================== */}
      {reviewModalItem && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(31, 25, 27, 0.65)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            zIndex: 9999,
            animation: 'fadeIn 0.25s ease-out',
          }}
          onClick={handleCloseReviewModal}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              maxWidth: '560px',
              width: '100%',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.3)',
              border: '1px solid #F0E2E0',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              animation: 'fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '1.25rem 1.75rem',
                borderBottom: '1px solid #F0E2E0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                backgroundColor: '#FAF7F5',
              }}
            >
              <div>
                <h3
                  style={{
                    margin: 0,
                    fontFamily: "'Playfair Display', serif",
                    fontSize: '1.3rem',
                    fontWeight: 700,
                    color: '#1F191B',
                  }}
                >
                  {reviewModalItem.customerReview ? 'Edit Your Review' : 'Rate & Review'}
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: '#6B5E63' }}>
                  {reviewModalItem.productName}
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseReviewModal}
                style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: '50%',
                  border: '1px solid #F0E2E0',
                  backgroundColor: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: '#1F191B',
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleSubmitReview} style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Product Preview Banner */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 14px',
                  borderRadius: '12px',
                  backgroundColor: '#FAF7F5',
                  border: '1px solid #F0E2E0',
                }}
              >
                <div style={{ width: '42px', height: '54px', borderRadius: '6px', overflow: 'hidden', flexShrink: 0 }}>
                  <img src={reviewModalItem.image} alt={reviewModalItem.productName} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h4 style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: '#1F191B', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {reviewModalItem.productName}
                  </h4>
                  <p style={{ margin: '2px 0 0 0', fontSize: '0.74rem', color: '#8E3642', fontWeight: 600 }}>
                    Verified Purchase
                  </p>
                </div>
              </div>

              {/* Star Rating Selector */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#1F191B', marginBottom: '8px' }}>
                  Your Rating
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {[1, 2, 3, 4, 5].map((star) => {
                      const active = star <= (hoverRating || reviewRating);
                      return (
                        <button
                          key={star}
                          type="button"
                          onClick={() => setReviewRating(star)}
                          onMouseEnter={() => setHoverRating(star)}
                          onMouseLeave={() => setHoverRating(0)}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '4px',
                            transition: 'transform 0.15s ease',
                            transform: active ? 'scale(1.15)' : 'scale(1)',
                          }}
                          aria-label={`${star} star`}
                        >
                          <Star
                            size={28}
                            fill={active ? '#EAB308' : '#F1E8E6'}
                            color={active ? '#CA8A04' : '#D1C2C0'}
                          />
                        </button>
                      );
                    })}
                  </div>
                  <span
                    style={{
                      fontSize: '0.88rem',
                      fontWeight: 700,
                      color: '#B8505E',
                      marginLeft: '8px',
                    }}
                  >
                    {(hoverRating || reviewRating) === 5
                      ? '5 Stars — Excellent'
                      : (hoverRating || reviewRating) === 4
                      ? '4 Stars — Very Good'
                      : (hoverRating || reviewRating) === 3
                      ? '3 Stars — Good'
                      : (hoverRating || reviewRating) === 2
                      ? '2 Stars — Fair'
                      : '1 Star — Poor'}
                  </span>
                </div>
              </div>

              {/* Written Review Textarea */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#1F191B', marginBottom: '8px' }}>
                  Written Review
                </label>
                <textarea
                  rows={4}
                  value={reviewText}
                  onChange={(e) => setReviewText(e.target.value)}
                  placeholder="Share details regarding fabric quality, fit, craftsmanship, styling, or delivery..."
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    borderRadius: '12px',
                    border: '1px solid #E0D2D0',
                    fontSize: '0.88rem',
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

              {/* Error Message */}
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

              {/* Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '4px' }}>
                <button
                  type="button"
                  onClick={handleCloseReviewModal}
                  disabled={submittingReview}
                  style={{
                    padding: '0.75rem 1.4rem',
                    borderRadius: '9999px',
                    border: '1px solid #E0D2D0',
                    backgroundColor: '#FFFFFF',
                    color: '#6B5E63',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReview}
                  className="tarika-btn-primary"
                  style={{
                    padding: '0.75rem 1.6rem',
                    fontSize: '0.85rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  {submittingReview ? (
                    <span>Submitting...</span>
                  ) : (
                    <>
                      <Sparkles size={14} />
                      <span>{reviewModalItem.customerReview ? 'Update Review' : 'Submit Review'}</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RETURN REQUEST MODAL */}
      {returnModalItem && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(31, 25, 27, 0.65)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            zIndex: 1000,
            animation: 'fadeIn 0.2s ease-out',
          }}
          onClick={() => setReturnModalItem(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              maxWidth: '560px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              boxShadow: '0 20px 60px rgba(31, 25, 27, 0.2)',
              padding: '2rem',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              type="button"
              onClick={() => setReturnModalItem(null)}
              aria-label="Close"
              style={{
                position: 'absolute',
                top: '1.5rem',
                right: '1.5rem',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#9E8F94',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <X size={20} />
            </button>

            {/* Modal Title */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#BE123C', marginBottom: '4px' }}>
                <RotateCcw size={15} color="#BE123C" />
                <span style={{ fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  Atelier Concierge
                </span>
              </div>
              <h2
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: '#1F191B',
                  margin: '0.25rem 0',
                }}
              >
                Request Item Return
              </h2>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#6B5E63' }}>
                Submit a return request for doorstep pickup and refund processing.
              </p>
            </div>

            {/* Item Card */}
            <div
              style={{
                display: 'flex',
                gap: '14px',
                padding: '12px',
                borderRadius: '16px',
                backgroundColor: '#FAF7F5',
                border: '1px solid #F0E2E0',
                marginBottom: '1.5rem',
              }}
            >
              <img
                src={returnModalItem.image}
                alt={returnModalItem.productName}
                style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: '10px' }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: '0 0 2px 0', fontSize: '0.9rem', fontWeight: 700, color: '#1F191B' }}>
                  {returnModalItem.productName}
                </p>
                <p style={{ margin: 0, fontSize: '0.76rem', color: '#6B5E63' }}>
                  Order #{returnModalItem.order?.order_id?.slice(0, 14)}...
                </p>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', fontWeight: 700, color: '#059669' }}>
                  Estimated Refund: ₹{Number(returnModalItem.lineTotal || 0).toLocaleString('en-IN')}
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmitReturnRequest} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Reason Dropdown */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
                  Reason for Return <span style={{ color: '#DC2626' }}>*</span>
                </label>
                <select
                  value={returnReason}
                  onChange={(e) => setReturnReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '12px',
                    border: '1.5px solid #F0E2E0',
                    backgroundColor: '#FFFFFF',
                    color: '#1F191B',
                    fontSize: '0.88rem',
                    fontWeight: 600,
                    outline: 'none',
                  }}
                >
                  <option value="Quality Issue">Quality Issue / Fabric not as expected</option>
                  <option value="Size Issue">Size Issue / Fit not suitable</option>
                  <option value="Defective / Damaged">Defective / Damaged in transit</option>
                  <option value="Wrong Product Delivered">Wrong Product / Style delivered</option>
                  <option value="Color Difference">Color / Pattern difference</option>
                  <option value="Changed Mind">Changed Mind / Found alternative</option>
                </select>
              </div>

              {/* Remarks / Condition */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 700, color: '#1F191B', marginBottom: '6px' }}>
                  Merchandise Condition
                </label>
                <textarea
                  rows={3}
                  value={returnCondition}
                  onChange={(e) => setReturnCondition(e.target.value)}
                  placeholder="e.g. Unused with original tags and luxury box packaging..."
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '12px',
                    border: '1.5px solid #F0E2E0',
                    fontSize: '0.88rem',
                    color: '#1F191B',
                    lineHeight: 1.5,
                    resize: 'vertical',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Error Message */}
              {returnError && (
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
                  <span>{returnError}</span>
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setReturnModalItem(null)}
                  disabled={submittingReturn}
                  style={{
                    padding: '0.75rem 1.4rem',
                    borderRadius: '9999px',
                    border: '1px solid #E0D2D0',
                    backgroundColor: '#FFFFFF',
                    color: '#6B5E63',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReturn}
                  className="tarika-btn-primary"
                  style={{
                    padding: '0.75rem 1.6rem',
                    fontSize: '0.85rem',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: '#BE123C',
                    borderColor: '#BE123C',
                  }}
                >
                  {submittingReturn ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      <span>Submitting...</span>
                    </>
                  ) : (
                    <>
                      <RotateCcw size={14} />
                      <span>Confirm Return Request</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* RETURN TRACKING MODAL */}
      {returnTrackingItem && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(31, 25, 27, 0.65)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
            zIndex: 1000,
            animation: 'fadeIn 0.2s ease-out',
          }}
          onClick={() => setReturnTrackingItem(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              maxWidth: '560px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid rgba(216, 114, 126, 0.3)',
              boxShadow: '0 20px 60px rgba(31, 25, 27, 0.2)',
              padding: '2rem',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              type="button"
              onClick={() => setReturnTrackingItem(null)}
              aria-label="Close"
              style={{
                position: 'absolute',
                top: '1.5rem',
                right: '1.5rem',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#9E8F94',
                padding: '6px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <X size={20} />
            </button>

            {/* Modal Title */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#7E22CE', marginBottom: '4px' }}>
                <RotateCcw size={15} color="#7E22CE" />
                <span style={{ fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  Reverse Logistics
                </span>
              </div>
              <h2
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.6rem',
                  fontWeight: 700,
                  color: '#1F191B',
                  margin: '0.25rem 0',
                }}
              >
                Return & Refund Progress
              </h2>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#6B5E63' }}>
                Tracking real-time reverse fulfillment and refund verification.
              </p>
            </div>

            {/* Return Item Card */}
            {(() => {
              const ret = returnTrackingItem.returnInfo || {};
              const st = (ret.return_status || '').toLowerCase();

              let activeIdx = 0;
              if (st.includes('request')) activeIdx = 0;
              else if (st === 'approved' || st === 'accepted') activeIdx = 1;
              else if (st === 'pickup assigned') activeIdx = 2;
              else if (st === 'pickup accepted') activeIdx = 3;
              else if (st === 'picked up') activeIdx = 4;
              else if (st === 'received at warehouse') activeIdx = 5;
              else if (st === 'completed' || st === 'refunded') activeIdx = 6;

              const isRejected = st === 'rejected';
              const isFailed = st === 'failed';

              const stages = [
                { title: 'Return Requested', desc: ret.return_date ? `Submitted on ${ret.return_date}` : 'Request registered' },
                { title: 'Return Approved', desc: 'Approved by fulfillment center' },
                { title: 'Pickup Assigned', desc: ret.delivery_partner ? `Assigned to ${ret.delivery_partner}` : 'Courier driver assignment' },
                { title: 'Pickup Accepted', desc: 'Driver accepted pickup' },
                { title: 'Picked Up', desc: 'Merchandise collected from customer' },
                { title: 'Received at Warehouse', desc: 'Arrived at fulfillment center' },
                { title: 'Return Completed', desc: ret.refund_amount ? `Refund ₹${Number(ret.refund_amount).toLocaleString('en-IN')} confirmed` : 'Inspection & refund complete' },
              ];

              return (
                <div>
                  <div
                    style={{
                      display: 'flex',
                      gap: '14px',
                      padding: '12px',
                      borderRadius: '16px',
                      backgroundColor: '#FAF7F5',
                      border: '1px solid #F0E2E0',
                      marginBottom: '1.5rem',
                    }}
                  >
                    <img
                      src={returnTrackingItem.image}
                      alt={returnTrackingItem.productName}
                      style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: '10px' }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ margin: '0 0 2px 0', fontSize: '0.9rem', fontWeight: 700, color: '#1F191B' }}>
                        {returnTrackingItem.productName}
                      </p>
                      <p style={{ margin: 0, fontSize: '0.76rem', color: '#6B5E63' }}>
                        Return Ref: <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{ret.return_id}</span>
                      </p>
                      <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', fontWeight: 700, color: '#7E22CE' }}>
                        Status: {ret.return_status || 'Requested'}
                      </p>
                    </div>
                  </div>

                  {/* Exception Banner if Rejected or Failed */}
                  {isRejected && (
                    <div
                      style={{
                        padding: '12px 14px',
                        borderRadius: '12px',
                        backgroundColor: '#FEF2F2',
                        border: '1px solid #FECACA',
                        color: '#DC2626',
                        fontSize: '0.85rem',
                        marginBottom: '1.5rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      <XCircle size={18} />
                      <span>This return request was reviewed and rejected by the warehouse facility.</span>
                    </div>
                  )}

                  {isFailed && (
                    <div
                      style={{
                        padding: '12px 14px',
                        borderRadius: '12px',
                        backgroundColor: '#FFFBEB',
                        border: '1px solid #FDE68A',
                        color: '#D97706',
                        fontSize: '0.85rem',
                        marginBottom: '1.5rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                      }}
                    >
                      <AlertCircle size={18} />
                      <span>Pickup attempt unsuccessful: {ret.condition_on_return || 'Customer unavailable'}</span>
                    </div>
                  )}

                  {/* Vertical Timeline */}
                  {!isRejected && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, position: 'relative', marginBottom: '1.5rem' }}>
                      {stages.map((stg, i) => {
                        const isPassed = i < activeIdx;
                        const isCurrent = i === activeIdx;
                        const isFuture = i > activeIdx;

                        return (
                          <div key={i} style={{ display: 'flex', gap: '1.25rem', position: 'relative' }}>
                            {i < stages.length - 1 && (
                              <div
                                style={{
                                  position: 'absolute',
                                  top: '24px',
                                  left: '13px',
                                  width: '2px',
                                  bottom: '-4px',
                                  backgroundColor: isPassed ? '#7E22CE' : '#F0E2E0',
                                  zIndex: 1,
                                }}
                              />
                            )}

                            <div style={{ zIndex: 2, padding: '2px 0' }}>
                              {isPassed ? (
                                <div
                                  style={{
                                    width: '28px',
                                    height: '28px',
                                    borderRadius: '50%',
                                    backgroundColor: '#7E22CE',
                                    color: '#FFFFFF',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 2px 8px rgba(126, 34, 206, 0.25)',
                                  }}
                                >
                                  <Check size={14} strokeWidth={3} />
                                </div>
                              ) : isCurrent ? (
                                <div
                                  style={{
                                    width: '28px',
                                    height: '28px',
                                    borderRadius: '50%',
                                    backgroundColor: '#FFFFFF',
                                    border: '3px solid #7E22CE',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    boxShadow: '0 0 0 4px rgba(126, 34, 206, 0.15)',
                                  }}
                                >
                                  <div
                                    style={{
                                      width: '10px',
                                      height: '10px',
                                      borderRadius: '50%',
                                      backgroundColor: '#7E22CE',
                                    }}
                                  />
                                </div>
                              ) : (
                                <div
                                  style={{
                                    width: '28px',
                                    height: '28px',
                                    borderRadius: '50%',
                                    backgroundColor: '#FAF7F5',
                                    border: '1.5px solid #F0E2E0',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                  }}
                                >
                                  <div
                                    style={{
                                      width: '6px',
                                      height: '6px',
                                      borderRadius: '50%',
                                      backgroundColor: '#D1C4C2',
                                    }}
                                  />
                                </div>
                              )}
                            </div>

                            <div style={{ paddingBottom: '1.5rem', flex: 1 }}>
                              <p
                                style={{
                                  margin: '3px 0 2px 0',
                                  fontSize: '0.88rem',
                                  fontWeight: isCurrent || isPassed ? 700 : 500,
                                  color: isCurrent ? '#7E22CE' : isPassed ? '#1F191B' : '#9E8F94',
                                }}
                              >
                                {stg.title}
                              </p>
                              <p style={{ margin: 0, fontSize: '0.78rem', color: isCurrent ? '#4B5563' : '#6B5E63' }}>
                                {stg.desc}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      type="button"
                      onClick={() => setReturnTrackingItem(null)}
                      className="tarika-btn-outline"
                      style={{ padding: '0.65rem 1.4rem', fontSize: '0.85rem' }}
                    >
                      Close Tracking
                    </button>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

    </div>
  );
}
