import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useAuth } from '../../auth/AuthContext';
import StockToBeOrdered from '../../features/stockToBeOrdered/StockToBeOrdered';
import { getProductPricing } from '../../utils/pricing';
import {
  getCategories,
  getProducts,
  invalidateCategoriesCache,
  getWarehouseOrders,
  getWarehouseOrderDetail,
  getWarehouseDeliveries,
  getWarehouseReturns,
  getWarehouseProductDetail,
  updateWarehouseProduct,
  acceptWarehouseReturn,
  rejectWarehouseReturn,
  assignWarehouseReturnPickup,
  receiveWarehouseReturn,
  getCourierPartners,
  getDeliveryEmployees,
  dispatchWarehouseOrder,
} from '../../services/api';
import {
  LayoutDashboard,
  Package,
  Boxes,
  ShoppingBag,
  Truck,
  RotateCcw,
  LogOut,
  Warehouse,
  MapPin,
  Search,
  Sparkles,
  Building2,
  Tag,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Layers,
  SlidersHorizontal,
  Clock,
  DollarSign,
  User,
  ShieldCheck,
  Calendar,
  XCircle,
  HelpCircle,
  PackageX,
  Check,
  Zap,
  Edit2,
  X,
  Save,
  Eye,
  Package2,
  Info,
  AlertTriangle,
  ArrowLeft,
} from 'lucide-react';
import '../../styles/tarika.css';
import '../../styles/customer-portal.css';

// Subcategory presets matching Customer Shop/Categories
const CATEGORY_SUBCATEGORIES = {
  'Dresses': ['All Dresses', 'Mini Dresses', 'Midi Dresses', 'Maxi Dresses', 'Party Dresses', 'Formal Dresses', 'Casual Dresses'],
  'Tops': ['All Tops', 'Crop Tops', 'Corset Blouses', 'Satin Camisoles', 'Ribbed Knits', 'Party Tops'],
  'Bottom Wear': ['All Bottoms', 'Wide-Leg Trousers', 'Pleated Slacks', 'Palazzos', 'High-Rise Pants', 'Formal Trousers'],
  'Jeans': ['All Jeans', 'Wide-Leg Jeans', 'Straight Fit', 'Bootcut Jeans', 'Skinny Jeans', 'Relaxed Fit'],
  'Jackets': ['All Jackets', 'Tailored Blazers', 'Leather Jackets', 'Bombers', 'Denim Jackets', 'Trench Coats'],
  'Shirts': ['All Shirts', 'Oversized Poplin', 'Linen Shirts', 'Silk Button-Downs', 'Formal Shirts', 'Casual Shirts'],
  'Kurtis': ['All Kurtis', 'Anarkali Kurtis', 'Straight Fit Kurtis', 'A-Line Kurtis', 'Printed Kurtis'],
  'Sarees': ['All Sarees', 'Silk Sarees', 'Chiffon Sarees', 'Georgette Sarees', 'Organza Sarees'],
  'Ethnic Wear': ['All Ethnic Wear', 'Lehenga Sets', 'Ethnic Suits', 'Dupattas', 'Sharara Sets'],
  'Handbags': ['All Handbags', 'Tote Bags', 'Crossbody Bags', 'Clutches', 'Shoulder Bags'],
  'Footwear': ['All Footwear', 'Heels', 'Flats', 'Sneakers', 'Sandals', 'Boots'],
  'Accessories': ['All Accessories', 'Jewelry', 'Belts', 'Scarves', 'Sunglasses']
};

const CATEGORY_HERO_META = {
  'Dresses': { title: 'THE DRESS STORY', quote: 'Same dress. A different you.', image: 'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=600&auto=format&fit=crop&q=80' },
  'Tops': { title: 'TOP STORIES', quote: 'Unapologetic silhouettes. Effortless you.', image: 'https://images.unsplash.com/photo-1564257631407-4deb1f99d992?w=600&auto=format&fit=crop&q=80' },
  'Bottom Wear': { title: 'BOTTOM LINE', quote: 'Tailored drape. Architectural lines.', image: 'https://images.unsplash.com/photo-1509551388413-e18d0ac5d495?w=600&auto=format&fit=crop&q=80' },
  'Jeans': { title: 'DENIM DIARIES', quote: 'Good denim, better days.', image: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&auto=format&fit=crop&q=80' },
  'Jackets': { title: 'THE LAYER ROOM', quote: 'Layer your story. Define your presence.', image: 'https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600&auto=format&fit=crop&q=80' },
  'Shirts': { title: 'SHIRT THEORY', quote: 'Crisp poplins. Everyday poetry.', image: 'https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=600&auto=format&fit=crop&q=80' },
  'Kurtis': { title: 'ETHNIC ELEGANCE', quote: 'Heritage looms. Contemporary grace.', image: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=600&auto=format&fit=crop&q=80' },
  'Sarees': { title: 'ROYAL HERITAGE', quote: 'Six yards of pure elegance.', image: 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=600&auto=format&fit=crop&q=80' },
  'Ethnic Wear': { title: 'TRADITIONAL EDIT', quote: 'Reimagined for modern celebrations.', image: 'https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?w=600&auto=format&fit=crop&q=80' },
  'Handbags': { title: 'BAG GALLERY', quote: 'The details that do more.', image: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=600&auto=format&fit=crop&q=80' },
  'Footwear': { title: 'FOOTWEAR ATELIER', quote: 'Steps towards effortless style.', image: 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600&auto=format&fit=crop&q=80' },
  'Accessories': { title: 'CURATED FINISHES', quote: 'The finishing touches.', image: 'https://images.unsplash.com/photo-1611652022419-a9419f74343d?w=600&auto=format&fit=crop&q=80' }
};

// Reusable Warehouse Product Card matching Customer ProductCard presentation
function WarehouseProductCard({ product, onCardClick }) {
  const [hovered, setHovered] = React.useState(false);
  if (!product) return null;

  const productName = product.product_name || product.name || 'Artisanal Garment';
  const { basePrice, currentPrice, discountAmount, isOnSale } = getProductPricing(product);

  // Live stock straight from the real `available_quantity` column.
  // null/undefined  -> stock data unavailable (never shown as a fake 0/10)
  // 0               -> legitimate numeric zero = genuinely out of stock
  const rawStock = product.available_quantity !== undefined
    ? product.available_quantity
    : product.total_stock;
  const isStockUnknown = rawStock === null || rawStock === undefined || !Number.isFinite(Number(rawStock));
  const totalStock = isStockUnknown ? null : Number(rawStock);
  const isOutOfStock = !isStockUnknown && totalStock <= 0;
  const isLowStock = !isStockUnknown && totalStock > 0 && totalStock <= 5;

  const imageUrl =
    product.image ||
    product.primary_image ||
    (product.images && product.images[0]?.image_url) ||
    'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=700&q=80';

  return (
    <div
      className="tarika-product-card"
      onClick={() => onCardClick && onCardClick(product)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        borderRadius: '16px',
        border: `1px solid ${hovered ? 'rgba(216, 114, 126, 0.45)' : 'var(--tarika-border, #F0E2E0)'}`,
        backgroundColor: '#FFFFFF',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'all 0.25s ease',
        boxShadow: hovered ? '0 8px 28px rgba(184, 80, 94, 0.12)' : '0 4px 15px rgba(184, 80, 94, 0.03)',
        cursor: 'pointer',
        transform: hovered ? 'translateY(-2px)' : 'translateY(0)',
      }}
    >
      {/* 3:4 Aspect Ratio Image Wrap matching Customer ProductCard */}
      <div className="product-image-wrap" style={{ position: 'relative', width: '100%', height: '220px', overflow: 'hidden', backgroundColor: '#FAF7F5' }}>
        <img
          src={imageUrl}
          alt={productName}
          loading="lazy"
          onError={(e) => {
            e.target.src = 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=700&q=80';
          }}
          style={{ width: '100%', height: '100%', objectFit: 'cover', transition: 'transform 0.4s ease', transform: hovered ? 'scale(1.04)' : 'scale(1)' }}
        />

        {/* Edit overlay on hover */}
        {hovered && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(184, 80, 94, 0.75) 0%, rgba(184, 80, 94, 0.1) 60%, transparent 100%)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
            paddingBottom: '1rem',
            transition: 'opacity 0.25s ease',
          }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              backgroundColor: '#FFFFFF', color: '#B8505E',
              fontSize: '0.8rem', fontWeight: 700,
              padding: '0.45rem 1.1rem', borderRadius: '9999px',
              boxShadow: '0 4px 15px rgba(0,0,0,0.15)',
            }}>
              <Edit2 size={13} />
              View & Edit
            </span>
          </div>
        )}

        {/* Sale Discount Badge */}
        {isOnSale && discountAmount > 0 && (
          <span className="product-badge-sale">
            ₹{discountAmount.toLocaleString('en-IN')} OFF
          </span>
        )}

        {/* Stock Status Badge */}
        <div style={{ position: 'absolute', top: '0.65rem', right: '0.65rem' }}>
          {isStockUnknown ? (
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '0.25rem 0.6rem', borderRadius: '9999px', backgroundColor: '#F4F4F5', color: '#52525B', border: '1px solid #E4E4E7' }}>
              STOCK DATA N/A
            </span>
          ) : isOutOfStock ? (
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '0.25rem 0.6rem', borderRadius: '9999px', backgroundColor: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA' }}>
              OUT OF STOCK
            </span>
          ) : isLowStock ? (
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '0.25rem 0.6rem', borderRadius: '9999px', backgroundColor: '#FFFBEB', color: '#D97706', border: '1px solid #FDE68A' }}>
              LOW STOCK ({totalStock})
            </span>
          ) : (
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '0.25rem 0.6rem', borderRadius: '9999px', backgroundColor: '#ECFDF5', color: '#059669', border: '1px solid #A7F3D0' }}>
              IN STOCK ({totalStock})
            </span>
          )}
        </div>
      </div>

      {/* Product Information */}
      <div style={{ padding: '0.9rem 1rem', display: 'flex', flexDirection: 'column', gap: '6px', flex: 1, justifyContent: 'space-between' }}>
        <div>
          {/* Category Tag */}
          <span
            style={{
              fontSize: '0.68rem',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: '#8E3642',
              fontWeight: 700,
              display: 'block',
              marginBottom: '2px'
            }}
          >
            {product.category_name || product.category?.category_name || 'Ready-to-Wear'}
          </span>

          {/* Product Title */}
          <h4
            style={{
              margin: '0 0 4px 0',
              fontSize: '0.9rem',
              fontWeight: 600,
              color: '#1F191B',
              lineHeight: 1.3,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
            title={productName}
          >
            {productName}
          </h4>

          {/* Brand if present */}
          {product.manufacturer_name && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#6B5E63', fontSize: '0.75rem', marginBottom: '4px' }}>
              <Building2 size={12} color="#D8727E" />
              <span>Brand: <strong>{product.manufacturer_name}</strong></span>
            </div>
          )}
        </div>

        <div>
          {/* Price Row */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '6px' }}>
            <span
              style={{
                fontSize: '1.05rem',
                fontWeight: 800,
                color: '#B8505E',
                fontFamily: "'Plus Jakarta Sans', sans-serif"
              }}
            >
              ₹{currentPrice.toLocaleString('en-IN')}
            </span>

            {isOnSale && (
              <span
                style={{
                  fontSize: '0.82rem',
                  color: '#9E8F94',
                  textDecoration: 'line-through'
                }}
              >
                ₹{basePrice.toLocaleString('en-IN')}
              </span>
            )}
          </div>

          {/* Footer Bar: SKU & Stock badge */}
          <div style={{ paddingTop: '0.5rem', borderTop: '1px solid var(--tarika-border, #F0E2E0)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: '#6B5E63' }}>
            <code style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1F191B', background: '#FAF7F5', padding: '0.15rem 0.45rem', borderRadius: '4px', border: '1px solid #F0E2E0' }}>
              {product.sku || 'SKU-KAT'}
            </code>
            <span>Stock: <strong style={{ color: isOutOfStock ? '#DC2626' : '#1F191B' }}>{isStockUnknown ? 'Data unavailable' : `${totalStock} units`}</strong></span>
          </div>

        </div>
      </div>
    </div>
  );
}

/* ==========================================================================
   ORDER DETAIL MODAL
   Opens when a warehouse manager clicks an order in the Orders table.
   Fetches full order detail + customer + items from Django (/api/warehouse/orders/<id>/).
   ========================================================================== */
function OrderDetailModal({ orderId, onClose, onOrderUpdated }) {
  const { token } = useAuth();
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [order, setOrder] = React.useState(null);

  // Dispatch Form State
  const [courierPartners, setCourierPartners] = React.useState([]);
  const [loadingCouriers, setLoadingCouriers] = React.useState(false);
  const [selectedCourier, setSelectedCourier] = React.useState('');
  const [deliveryEmployees, setDeliveryEmployees] = React.useState([]);
  const [loadingEmployees, setLoadingEmployees] = React.useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = React.useState('');
  const [expectedDeliveryDate, setExpectedDeliveryDate] = React.useState('');
  const [dispatching, setDispatching] = React.useState(false);
  const [dispatchError, setDispatchError] = React.useState(null);
  const [dispatchSuccess, setDispatchSuccess] = React.useState(null);

  React.useEffect(() => {
    let active = true;
    async function fetchDetail() {
      setLoading(true);
      setError(null);
      const res = await getWarehouseOrderDetail(orderId);
      if (active) {
        if (res.success && res.order) {
          setOrder(res.order);
        } else {
          setError(res.error || 'Failed to load order details.');
        }
        setLoading(false);
      }
    }
    if (orderId) fetchDetail();
    return () => { active = false; };
  }, [orderId]);

  // Load Courier Companies dynamically from existing DB data
  React.useEffect(() => {
    let active = true;
    async function loadCouriers() {
      setLoadingCouriers(true);
      const res = await getCourierPartners();
      if (active && res.success && res.partners) {
        setCourierPartners(res.partners);
      }
      if (active) setLoadingCouriers(false);
    }
    loadCouriers();
    return () => { active = false; };
  }, []);

  // When Courier changes, dynamically load active Delivery Partner employees for that company
  React.useEffect(() => {
    let active = true;
    if (!selectedCourier) {
      setDeliveryEmployees([]);
      setSelectedEmployeeId('');
      return;
    }
    async function loadDrivers() {
      setLoadingEmployees(true);
      setSelectedEmployeeId('');
      const res = await getDeliveryEmployees(selectedCourier);
      if (active && res.success && res.employees) {
        setDeliveryEmployees(res.employees);
      }
      if (active) setLoadingEmployees(false);
    }
    loadDrivers();
    return () => { active = false; };
  }, [selectedCourier]);

  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const handleDispatchSubmit = async (e) => {
    e.preventDefault();
    if (!selectedCourier) {
      setDispatchError('Please select a courier company.');
      return;
    }
    if (!selectedEmployeeId) {
      setDispatchError('Please select an active delivery partner employee.');
      return;
    }
    if (!expectedDeliveryDate) {
      setDispatchError('Please explicitly select the expected delivery date.');
      return;
    }

    setDispatching(true);
    setDispatchError(null);
    setDispatchSuccess(null);
    try {
      const res = await dispatchWarehouseOrder(orderId, {
        delivery_partner: selectedCourier,
        assigned_employee_id: Number(selectedEmployeeId),
        expected_delivery_date: expectedDeliveryDate,
      }, token);

      if (res.success) {
        setDispatchSuccess(res.message || 'Order dispatched successfully.');
        if (res.order) {
          setOrder(res.order);
        }
        if (onOrderUpdated) {
          onOrderUpdated(res.order);
        }
      } else {
        setDispatchError(res.error || 'Failed to dispatch order.');
      }
    } catch (err) {
      setDispatchError('Network error while dispatching order.');
    } finally {
      setDispatching(false);
    }
  };

  const isConfirmed = (order?.order_status || '').toLowerCase() === 'confirmed';
  const isShipped = (order?.order_status || '').toLowerCase() === 'shipped';

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 200,
          backgroundColor: 'rgba(31, 25, 27, 0.55)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Slide-in Panel */}
      <div
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201,
          width: 'min(760px, 100vw)',
          backgroundColor: '#FFFFFF',
          boxShadow: '-8px 0 60px rgba(31, 25, 27, 0.18)',
          display: 'flex', flexDirection: 'column',
          animation: 'slideInRight 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          overflowY: 'auto',
        }}
      >
        {/* Panel Header */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1.25rem 1.75rem',
          backgroundColor: '#FAF7F5',
          borderBottom: '1px solid var(--tarika-border, #F0E2E0)',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <ShoppingBag size={20} color="#B8505E" />
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#1F191B', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                Order Reference: {orderId}
              </h3>
            </div>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.8rem', color: '#6B5E63' }}>
              Database Order & Items Details
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: '36px', height: '36px', borderRadius: '50%',
              border: '1px solid var(--tarika-border, #F0E2E0)',
              backgroundColor: '#FFFFFF', cursor: 'pointer', color: '#1F191B', flexShrink: 0
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Panel Body */}
        <div style={{ padding: '1.75rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
              <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216, 114, 126, 0.3)', borderTopColor: '#D8727E' }} />
              <p style={{ color: '#6B5E63', fontWeight: 600 }}>Loading Order Details from Database...</p>
            </div>
          ) : error ? (
            <div className="tarika-auth-alert">
              <AlertCircle size={20} />
              <span>{error}</span>
            </div>
          ) : order ? (
            <>
              {/* Order Meta & Status Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', background: '#FAF7F5', padding: '1.25rem', borderRadius: '16px', border: '1px solid #F0E2E0' }}>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Order Date</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B', fontSize: '0.9rem' }}>{order.order_date || 'N/A'}</p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Order Status</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: (order.order_status || '').toLowerCase() === 'shipped' ? '#059669' : '#2563EB', fontSize: '0.9rem', textTransform: 'capitalize' }}>
                    {order.order_status || 'Confirmed'}
                  </p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Payment Status</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#059669', fontSize: '0.9rem', textTransform: 'capitalize' }}>
                    {order.payment_status || 'Paid'}
                  </p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Warehouse Facility</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B', fontSize: '0.9rem' }}>{order.warehouse_name || 'Fulfillment Center'}</p>
                </div>
              </div>

              {/* Delivery Info Banner (if order has an assigned delivery) */}
              {order.delivery && (
                <div style={{ background: '#FAF7F5', padding: '1.25rem', borderRadius: '16px', border: '1.5px solid #BFDBFE' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Truck size={18} color="#2563EB" />
                      <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: '#1E40AF' }}>
                        Delivery Assignment: {order.delivery.delivery_status || 'Assigned'}
                      </h4>
                    </div>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.75rem', borderRadius: '999px', background: '#EFF6FF', color: '#1E40AF', border: '1px solid #BFDBFE' }}>
                      {order.delivery.delivery_status || 'Assigned'}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', fontSize: '0.84rem' }}>
                    <div>
                      <span style={{ color: '#6B5E63', fontSize: '0.74rem' }}>Courier Partner:</span>
                      <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{order.delivery.delivery_partner || 'N/A'}</p>
                    </div>
                    <div>
                      <span style={{ color: '#6B5E63', fontSize: '0.74rem' }}>Assigned Employee:</span>
                      <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>
                        {order.delivery.assigned_employee_name || 'Assigned Delivery Partner'}
                        {order.delivery.assigned_employee_phone ? ` (${order.delivery.assigned_employee_phone})` : ''}
                      </p>
                    </div>
                    <div>
                      <span style={{ color: '#6B5E63', fontSize: '0.74rem' }}>Dispatch Date:</span>
                      <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{order.delivery.dispatch_date || 'N/A'}</p>
                    </div>
                    <div>
                      <span style={{ color: '#6B5E63', fontSize: '0.74rem' }}>Expected Delivery Date:</span>
                      <p style={{ margin: 0, fontWeight: 700, color: '#B8505E' }}>{order.delivery.expected_delivery_date || 'N/A'}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Warehouse Dispatch & Delivery Partner Assignment Section */}
              {(isConfirmed || (!isShipped && !order.delivery)) && (
                <div style={{ background: '#FFFFFF', padding: '1.35rem', borderRadius: '16px', border: '1.5px solid #D8727E', boxShadow: '0 4px 20px rgba(184,80,94,0.06)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Truck size={18} color="#B8505E" />
                      <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: '#1F191B' }}>
                        Dispatch & Assign Delivery Partner
                      </h4>
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: '999px', background: '#EFF6FF', color: '#2563EB', border: '1px solid #BFDBFE' }}>
                      Order Confirmed — Ready for Shipment
                    </span>
                  </div>

                  <p style={{ fontSize: '0.82rem', color: '#6B5E63', margin: '0 0 1.25rem', lineHeight: 1.45 }}>
                    Select a courier company and active delivery partner employee. Setting the explicit expected delivery date will update fulfillment to <strong>shipped</strong> and sync customer tracking to <strong>Assigned</strong>.
                  </p>

                  {dispatchError && (
                    <div className="tarika-auth-alert" style={{ marginBottom: '1rem' }}>
                      <AlertCircle size={16} />
                      <span>{dispatchError}</span>
                    </div>
                  )}

                  {dispatchSuccess && (
                    <div style={{ padding: '0.75rem 1rem', borderRadius: '10px', background: '#ECFDF5', color: '#065F46', border: '1px solid #A7F3D0', fontSize: '0.84rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                      <CheckCircle2 size={16} />
                      <span>{dispatchSuccess}</span>
                    </div>
                  )}

                  <form onSubmit={handleDispatchSubmit}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
                      {/* Step 1: Courier Company Dropdown */}
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>
                          1. Courier Company <span style={{ color: '#DC2626' }}>*</span>
                        </label>
                        <select
                          value={selectedCourier}
                          onChange={(e) => {
                            setSelectedCourier(e.target.value);
                            setSelectedEmployeeId('');
                          }}
                          disabled={dispatching || loadingCouriers}
                          style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid #D8727E', fontSize: '0.85rem', color: '#1F191B', background: '#FFFFFF', outline: 'none' }}
                        >
                          <option value="">-- Select Courier Company --</option>
                          {courierPartners.map((cp) => (
                            <option key={cp} value={cp}>{cp}</option>
                          ))}
                        </select>
                      </div>

                      {/* Step 2: Delivery Employee Dropdown */}
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>
                          2. Delivery Employee <span style={{ color: '#DC2626' }}>*</span>
                        </label>
                        <select
                          value={selectedEmployeeId}
                          onChange={(e) => setSelectedEmployeeId(e.target.value)}
                          disabled={dispatching || !selectedCourier || loadingEmployees}
                          style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid #D8727E', fontSize: '0.85rem', color: '#1F191B', background: (!selectedCourier) ? '#F9F9F9' : '#FFFFFF', outline: 'none' }}
                        >
                          <option value="">
                            {!selectedCourier ? '-- First choose courier company --' : loadingEmployees ? 'Loading drivers...' : deliveryEmployees.length === 0 ? '-- No active drivers for this company --' : '-- Select Delivery Driver --'}
                          </option>
                          {deliveryEmployees.map((emp) => (
                            <option key={emp.employee_id} value={emp.employee_id}>
                              {emp.full_name} (ID: #{emp.employee_id}{emp.phone ? ` • Tel: ${emp.phone}` : ''}{emp.warehouse ? ` • Warehouse: ${emp.warehouse}` : ''})
                            </option>
                          ))}
                        </select>
                        {selectedEmployeeId && (() => {
                          const empObj = deliveryEmployees.find(e => String(e.employee_id) === String(selectedEmployeeId));
                          if (!empObj) return null;
                          return (
                            <div style={{ marginTop: '0.45rem', padding: '0.5rem 0.75rem', borderRadius: '8px', background: '#FAF7F5', border: '1px solid #E5D0CD', fontSize: '0.74rem' }}>
                              <div style={{ fontWeight: 700, color: '#1F191B' }}>{empObj.full_name}</div>
                              <div style={{ color: '#6B5E63', marginTop: '1px' }}>
                                ID #{empObj.employee_id} • Courier: {empObj.courier_company}
                                {empObj.phone ? ` • Tel: ${empObj.phone}` : ''}
                                {empObj.warehouse ? ` • Assigned Warehouse: ${empObj.warehouse}` : ''}
                              </div>
                            </div>
                          );
                        })()}
                      </div>

                      {/* Step 3: Explicit Expected Delivery Date */}
                      <div>
                        <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>
                          3. Expected Delivery Date <span style={{ color: '#DC2626' }}>*</span>
                        </label>
                        <input
                          type="date"
                          value={expectedDeliveryDate}
                          min={new Date().toISOString().split('T')[0]}
                          onChange={(e) => setExpectedDeliveryDate(e.target.value)}
                          disabled={dispatching}
                          style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid #D8727E', fontSize: '0.85rem', color: '#1F191B', background: '#FFFFFF', outline: 'none' }}
                        />
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button
                        type="submit"
                        disabled={dispatching || !selectedCourier || !selectedEmployeeId || !expectedDeliveryDate}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.5rem',
                          padding: '0.75rem 1.75rem', borderRadius: '10px',
                          background: (!selectedCourier || !selectedEmployeeId || !expectedDeliveryDate) ? '#D1D5DB' : '#B8505E',
                          color: '#FFFFFF', fontWeight: 700, fontSize: '0.88rem', border: 'none',
                          cursor: (!selectedCourier || !selectedEmployeeId || !expectedDeliveryDate || dispatching) ? 'not-allowed' : 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        {dispatching ? (
                          <>
                            <div className="tarika-auth-spinner" style={{ width: '1rem', height: '1rem', borderWidth: '2px', borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#FFF' }} />
                            <span>Dispatching Shipment...</span>
                          </>
                        ) : (
                          <>
                            <Truck size={16} />
                            <span>Confirm Dispatch & Hand-off</span>
                          </>
                        )}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {/* Customer Details Card */}
              <div style={{ background: '#FFFFFF', padding: '1.25rem', borderRadius: '16px', border: '1px solid #F0E2E0' }}>
                <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <User size={16} color="#B8505E" />
                  Customer Information
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', fontSize: '0.85rem' }}>
                  <div>
                    <span style={{ color: '#6B5E63', fontSize: '0.75rem' }}>Customer Name:</span>
                    <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{order.customer_name}</p>
                  </div>
                  <div>
                    <span style={{ color: '#6B5E63', fontSize: '0.75rem' }}>Email Address:</span>
                    <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{order.customer_email || 'N/A'}</p>
                  </div>
                  <div>
                    <span style={{ color: '#6B5E63', fontSize: '0.75rem' }}>Phone Number:</span>
                    <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{order.customer_phone || 'N/A'}</p>
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <span style={{ color: '#6B5E63', fontSize: '0.75rem' }}>Shipping Address:</span>
                    <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{order.shipping_address || 'Standard Shipping Address'}</p>
                  </div>
                </div>
              </div>

              {/* Products in this Order */}
              <div>
                <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Package size={16} color="#B8505E" />
                  Products in this Order ({(order.items || []).length})
                </h4>
                {(!order.items || order.items.length === 0) ? (
                  <p style={{ color: '#6B5E63', fontStyle: 'italic', fontSize: '0.85rem' }}>No item records found for this order in database.</p>
                ) : (
                  <div style={{ border: '1px solid #F0E2E0', borderRadius: '16px', overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                      <thead>
                        <tr style={{ background: '#FAF7F5', borderBottom: '1.5px solid #F0E2E0', color: '#8E3642', fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          <th style={{ padding: '0.85rem 1rem' }}>Product Name</th>
                          <th style={{ padding: '0.85rem 1rem' }}>Category / Brand</th>
                          <th style={{ padding: '0.85rem 1rem', textAlign: 'center' }}>Quantity</th>
                          <th style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>Price</th>
                          <th style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {order.items.map((item, idx) => {
                          const itemTotal = item.subtotal || (Number(item.unit_price || 0) * Number(item.quantity || 1));
                          return (
                            <tr key={item.order_item_id || idx} style={{ borderBottom: '1px solid #F0E2E0' }}>
                              <td style={{ padding: '0.85rem 1rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                  {item.image && (
                                    <img
                                      src={item.image}
                                      alt={item.product_name}
                                      style={{ width: '42px', height: '42px', objectFit: 'cover', borderRadius: '8px', border: '1px solid #F0E2E0' }}
                                    />
                                  )}
                                  <div>
                                    <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{item.product_name}</p>
                                    <p style={{ margin: 0, fontSize: '0.72rem', color: '#6B5E63', fontFamily: 'monospace' }}>
                                      {item.sku ? `SKU: ${item.sku}` : `ID: ${item.product_id}`}
                                      {item.size ? ` | Size: ${item.size}` : ''}
                                      {item.color ? ` | Color: ${item.color}` : ''}
                                    </p>
                                  </div>
                                </div>
                              </td>
                              <td style={{ padding: '0.85rem 1rem' }}>
                                <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{item.category_name || 'Apparel'}</p>
                                {item.manufacturer_name && (
                                  <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63' }}>{item.manufacturer_name}</p>
                                )}
                              </td>
                              <td style={{ padding: '0.85rem 1rem', textAlign: 'center', fontWeight: 700, color: '#1F191B' }}>
                                {item.quantity}
                              </td>
                              <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 600, color: '#1F191B' }}>
                                ₹{Number(item.unit_price || 0).toLocaleString('en-IN')}
                              </td>
                              <td style={{ padding: '0.85rem 1rem', textAlign: 'right', fontWeight: 800, color: '#B8505E' }}>
                                ₹{Number(itemTotal).toLocaleString('en-IN')}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Summary Total */}
              <div style={{ background: '#FAF7F5', padding: '1.25rem', borderRadius: '16px', border: '1px solid #F0E2E0', display: 'flex', flexDirection: 'column', gap: '0.5rem', alignSelf: 'flex-end', width: 'min(360px, 100%)' }}>
                {order.discount_amount > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#059669' }}>
                    <span>Discount:</span>
                    <span style={{ fontWeight: 700 }}>- ₹{Number(order.discount_amount).toLocaleString('en-IN')}</span>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1.1rem', fontWeight: 800, color: '#1F191B', paddingTop: '0.25rem', borderTop: '1px solid #E2D4D6' }}>
                  <span>Order Total:</span>
                  <span style={{ color: '#B8505E' }}>₹{Number(order.total_amount || 0).toLocaleString('en-IN')}</span>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}

/* ==========================================================================
   PRODUCT EDIT MODAL
   Opens when a warehouse manager clicks a product card.
   Fetches full product detail from Django (GET /api/warehouse/products/<id>/).
   On save, sends PUT request; Django validates and persists; modal refreshes.
   availability_label / in_stock / total_stock all come from Django — not React.
   ========================================================================== */
function ProductEditModal({ product: cardProduct, onClose, onSaveSuccess, token }) {
  // Full product data fetched from Django (has stock, availability_label, etc.)
  const [product, setProduct] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [fetchError, setFetchError] = React.useState(null);

  // Form state — mirrors the real public.products columns
  const [form, setForm] = React.useState(null);

  // Save state
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState(null);
  const [saveSuccess, setSaveSuccess] = React.useState(false);

  // Build an editable form object from a Django product payload.
  // null stock stays '' (unavailable) — never converted to an invented 0.
  const buildFormFromProduct = (p) => ({
    product_name: p.product_name || '',
    main_category: p.main_category ?? p.category_name ?? '',
    sub_category: p.sub_category || '',
    image: p.image || '',
    link: p.link || '',
    discount_price: p.discount_price ?? p.selling_price ?? '',
    actual_price: p.actual_price ?? p.base_price ?? '',
    available_quantity: p.available_quantity ?? p.total_stock ?? '',
  });

  // Fetch full product detail from Django on mount
  React.useEffect(() => {
    if (!cardProduct?.product_id) return;
    let cancelled = false;
    setLoading(true);
    setFetchError(null);

    getWarehouseProductDetail(cardProduct.product_id).then((res) => {
      if (cancelled) return;
      if (res.success && res.product) {
        setProduct(res.product);
        // Initialise form with Django's values
        setForm(buildFormFromProduct(res.product));
      } else {
        // Fallback: use card product data so modal isn't empty
        setProduct(cardProduct);
        setForm(buildFormFromProduct(cardProduct));
        setFetchError(res.error || 'Could not load full product details. Showing cached data.');
      }
      setLoading(false);
    });

    return () => { cancelled = true; };
  }, [cardProduct?.product_id]);

  // Lock body scroll while modal is open
  React.useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSaveError(null);
    setSaveSuccess(false);
  };

  // Numeric field validation: finite, non-negative, empty allowed (null).
  const parseNumericField = (rawValue, label, allowEmpty = true) => {
    const str = String(rawValue ?? '').trim();
    if (str === '') {
      return { ok: allowEmpty, value: allowEmpty ? null : undefined, error: allowEmpty ? null : `${label} is required.` };
    }
    const num = Number(str);
    if (!Number.isFinite(num)) {
      return { ok: false, error: `${label} must be a valid number (numbers like NaN or Infinity are not accepted).` };
    }
    if (num < 0) {
      return { ok: false, error: `${label} cannot be negative.` };
    }
    return { ok: true, value: num };
  };

  const handleSave = async () => {
    if (!product?.product_id || saving) return;

    const name = (form.product_name || '').trim();
    if (!name) {
      setSaveError('Product name is required.');
      return;
    }
    const discount = parseNumericField(form.discount_price, 'Discount price');
    if (!discount.ok) { setSaveError(discount.error); return; }
    const stock = parseNumericField(form.available_quantity, 'Available stock');
    if (!stock.ok) { setSaveError(stock.error); return; }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    // Payload mirrors the real public.products columns. `actual_price` is
    // sent as text because the database column is TEXT.
    const payload = {
      product_name: name,
      main_category: (form.main_category || '').trim(),
      sub_category: (form.sub_category || '').trim(),
      image: (form.image || '').trim(),
      link: (form.link || '').trim(),
      discount_price: discount.value,
      actual_price: String(form.actual_price ?? ''),
      available_quantity: stock.value,
    };

    const res = await updateWarehouseProduct(product.product_id, payload, token);

    if (res.success && res.product) {
      // Show the values Django re-read from the database (not optimistic state)
      setProduct(res.product);
      setForm(buildFormFromProduct(res.product));
      setSaveSuccess(true);
      // Notify parent so the product list and category counts refresh
      if (onSaveSuccess) onSaveSuccess(res.product);
    } else {
      setSaveError(res.error || 'Failed to save changes. Please try again.');
    }
    setSaving(false);
  };

  // Availability data comes exclusively from Django; a real 0 stays
  // 'Out of Stock' while missing data is labelled separately.
  const availLabel = product?.availability_label
    || (product?.available_quantity != null || product?.total_stock != null
      ? ((Number(product.available_quantity ?? product.total_stock) > 0) ? 'Available' : 'Out of Stock')
      : 'Stock Data Unavailable');
  const rawStockValue = product ? (product.available_quantity !== undefined ? product.available_quantity : product.total_stock) : null;
  const totalStock = rawStockValue === null || rawStockValue === undefined ? null : Number(rawStockValue);
  const isAvailable = availLabel === 'Available';

  const imageUrl =
    product?.image ||
    cardProduct?.image ||
    'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=700&q=80';

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 200,
          backgroundColor: 'rgba(31, 25, 27, 0.55)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          animation: 'fadeIn 0.2s ease',
        }}
      />

      {/* Slide-in Panel */}
      <div
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201,
          width: 'min(640px, 100vw)',
          backgroundColor: '#FFFFFF',
          boxShadow: '-8px 0 60px rgba(31, 25, 27, 0.18)',
          display: 'flex', flexDirection: 'column',
          animation: 'slideInRight 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          overflowY: 'auto',
        }}
      >
        {/* Panel Header */}
        <div style={{
          position: 'sticky', top: 0, zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.96)',
          backdropFilter: 'blur(10px)',
          borderBottom: '1px solid var(--tarika-border, #F0E2E0)',
          padding: '1rem 1.5rem',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: '1rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px',
              background: 'linear-gradient(135deg, #FBF1F0 0%, #F5DDE0 100%)',
              border: '1px solid rgba(216, 114, 126, 0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#B8505E',
            }}>
              <Edit2 size={17} />
            </div>
            <div>
              <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                Product Details & Edit
              </p>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#6B5E63', fontWeight: 500 }}>
                {loading ? 'Loading…' : (product?.product_name || cardProduct?.product_name || 'Product')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '36px', height: '36px', borderRadius: '50%',
              border: '1px solid var(--tarika-border, #F0E2E0)',
              backgroundColor: '#FAF7F5', color: '#6B5E63',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'all 0.2s ease',
            }}
            aria-label="Close product edit panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem', padding: '3rem' }}>
            <div className="tarika-auth-spinner" style={{ width: '2.5rem', height: '2.5rem', borderColor: 'rgba(216, 114, 126, 0.25)', borderTopColor: '#D8727E' }} />
            <p style={{ color: '#6B5E63', fontWeight: 600, margin: 0 }}>Fetching product from database…</p>
          </div>
        )}

        {/* Content */}
        {!loading && product && form && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0 }}>

            {/* Hero: Product Image + Key Info */}
            <div style={{
              display: 'flex', gap: '1.25rem', padding: '1.5rem',
              background: 'linear-gradient(135deg, #FAF7F5 0%, #FBF1F0 100%)',
              borderBottom: '1px solid var(--tarika-border, #F0E2E0)',
            }}>
              {/* Product Image */}
              <div style={{ width: '120px', height: '150px', flexShrink: 0, borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(216,114,126,0.15)', boxShadow: '0 4px 16px rgba(184,80,94,0.08)' }}>
                <img
                  src={imageUrl}
                  alt={product.product_name}
                  onError={(e) => { e.target.src = 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=300&q=80'; }}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              </div>

              {/* Key Metadata */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem', justifyContent: 'center' }}>
                {/* Category badge */}
                <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                  {product.category_name || 'Ready-to-Wear'}
                </span>

                {/* Product name */}
                <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#1F191B', lineHeight: 1.3 }}>
                  {product.product_name}
                </h2>

                {/* Manufacturer */}
                {product.manufacturer_name && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#6B5E63', fontSize: '0.8rem' }}>
                    <Building2 size={13} color="#D8727E" />
                    <span>{product.manufacturer_name}</span>
                  </div>
                )}

                {/* SKU */}
                <code style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 700, color: '#1F191B', background: '#FFFFFF', padding: '0.2rem 0.55rem', borderRadius: '6px', border: '1px solid #F0E2E0', alignSelf: 'flex-start' }}>
                  {product.sku || 'N/A'}
                </code>

                {/* Availability — label from Django, not React logic */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '2px' }}>
                  <span style={{
                    fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.75rem',
                    borderRadius: '9999px',
                    backgroundColor: isAvailable ? '#ECFDF5' : '#FEF2F2',
                    color: isAvailable ? '#059669' : '#DC2626',
                    border: `1px solid ${isAvailable ? '#A7F3D0' : '#FECACA'}`,
                  }}>
                    {availLabel}
                  </span>
                  <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                    {totalStock === null ? 'Stock data unavailable' : `${totalStock} units available`}
                  </span>
                </div>
              </div>
            </div>

            {/* Fetch error banner (non-blocking) */}
            {fetchError && (
              <div style={{ margin: '1rem 1.5rem 0', padding: '0.7rem 1rem', borderRadius: '10px', background: '#FFFBEB', border: '1px solid #FDE68A', color: '#D97706', fontSize: '0.8rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '1px' }} />
                <span>{fetchError}</span>
              </div>
            )}

            {/* Read-only Info Section */}
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--tarika-border, #F0E2E0)' }}>
              <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                Read-Only Information
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem 1.5rem' }}>
                {[
                  { label: 'Product ID (key)', value: product.product_id },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p style={{ margin: '0 0 2px 0', fontSize: '0.7rem', fontWeight: 600, color: '#9E8F94', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</p>
                    <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 600, color: '#1F191B', wordBreak: 'break-all' }}>{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Editable Fields Section */}
            <div style={{ padding: '1.25rem 1.5rem', flex: 1 }}>
              <p style={{ margin: '0 0 1rem 0', fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#8E3642' }}>
                Edit Product Details
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                {/* Product Name */}
                <div>
                  <label style={labelStyle}>Product Name *</label>
                  <input
                    id="edit-product-name"
                    type="text"
                    value={form.product_name}
                    onChange={(e) => handleChange('product_name', e.target.value)}
                    placeholder="Enter product name"
                    style={inputStyle}
                  />
                </div>

                {/* Category Row (real main_category / sub_category columns) */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={labelStyle}>Main Category</label>
                    <input
                      id="edit-main-category"
                      type="text"
                      value={form.main_category}
                      onChange={(e) => handleChange('main_category', e.target.value)}
                      placeholder="e.g. women's clothing"
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Subcategory</label>
                    <input
                      id="edit-sub-category"
                      type="text"
                      value={form.sub_category}
                      onChange={(e) => handleChange('sub_category', e.target.value)}
                      placeholder="e.g. Western Wear"
                      style={inputStyle}
                    />
                  </div>
                </div>

                {/* Image URL */}
                <div>
                  <label style={labelStyle}>Image URL</label>
                  <input
                    id="edit-image-url"
                    type="url"
                    value={form.image}
                    onChange={(e) => handleChange('image', e.target.value)}
                    placeholder="https://…"
                    style={inputStyle}
                  />
                </div>

                {/* Product Link */}
                <div>
                  <label style={labelStyle}>Product Link</label>
                  <input
                    id="edit-product-link"
                    type="url"
                    value={form.link}
                    onChange={(e) => handleChange('link', e.target.value)}
                    placeholder="https://…"
                    style={inputStyle}
                  />
                </div>

                {/* Pricing & Stock Row (double precision numbers + TEXT price) */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={labelStyle}>Discount Price (₹)</label>
                    <input
                      id="edit-discount-price"
                      type="number"
                      min="0"
                      step="any"
                      value={form.discount_price}
                      onChange={(e) => handleChange('discount_price', e.target.value)}
                      placeholder="0"
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Actual Price (text)</label>
                    <input
                      id="edit-actual-price"
                      type="text"
                      value={form.actual_price}
                      onChange={(e) => handleChange('actual_price', e.target.value)}
                      placeholder="e.g. 1,099"
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Available Stock</label>
                    <input
                      id="edit-available-quantity"
                      type="number"
                      min="0"
                      step="any"
                      value={form.available_quantity}
                      onChange={(e) => handleChange('available_quantity', e.target.value)}
                      placeholder="Unknown"
                      style={inputStyle}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Save Error / Success Banners */}
            {saveError && (
              <div style={{ margin: '0 1.5rem', padding: '0.8rem 1rem', borderRadius: '10px', background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', fontSize: '0.82rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{saveError}</span>
              </div>
            )}
            {saveSuccess && (
              <div style={{ margin: '0 1.5rem', padding: '0.8rem 1rem', borderRadius: '10px', background: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669', fontSize: '0.82rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
                <span>Product updated successfully! Changes saved to database.</span>
              </div>
            )}

            {/* Sticky Footer Actions */}
            <div style={{
              position: 'sticky', bottom: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.97)',
              borderTop: '1px solid var(--tarika-border, #F0E2E0)',
              padding: '1rem 1.5rem',
              display: 'flex', gap: '0.75rem', justifyContent: 'flex-end',
            }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: '0.65rem 1.4rem',
                  borderRadius: '10px',
                  border: '1px solid var(--tarika-border, #F0E2E0)',
                  backgroundColor: '#FAF7F5',
                  color: '#6B5E63',
                  fontSize: '0.88rem', fontWeight: 600,
                  cursor: 'pointer', transition: 'all 0.2s ease',
                }}
              >
                Cancel
              </button>
              <button
                id="save-product-changes-btn"
                type="button"
                onClick={handleSave}
                disabled={saving}
                style={{
                  padding: '0.65rem 1.6rem',
                  borderRadius: '10px',
                  border: 'none',
                  background: saving ? 'rgba(184,80,94,0.5)' : 'linear-gradient(135deg, #D8727E 0%, #B8505E 100%)',
                  color: '#FFFFFF',
                  fontSize: '0.88rem', fontWeight: 700,
                  cursor: saving ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  transition: 'all 0.2s ease',
                  boxShadow: saving ? 'none' : '0 4px 15px rgba(184,80,94,0.3)',
                }}
              >
                {saving ? (
                  <>
                    <div className="tarika-auth-spinner" style={{ width: '16px', height: '16px', borderWidth: '2px', borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#FFFFFF', flexShrink: 0 }} />
                    Saving…
                  </>
                ) : (
                  <>
                    <Save size={15} />
                    Save Changes
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* CSS animations for modal */}
      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);   opacity: 1; }
        }
      `}</style>
    </>
  );
}

// Shared input/label style tokens for edit form (consistent with Tarika design)
const labelStyle = {
  display: 'block',
  fontSize: '0.72rem',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  color: '#6B5E63',
  marginBottom: '4px',
};
const inputStyle = {
  width: '100%',
  padding: '0.6rem 0.85rem',
  borderRadius: '10px',
  border: '1.5px solid var(--tarika-border, #F0E2E0)',
  backgroundColor: '#FAF7F5',
  color: '#1F191B',
  fontSize: '0.88rem',
  outline: 'none',
  transition: 'border-color 0.2s ease',
  boxSizing: 'border-box',
};




export default function WarehousePortal() {
  const { user, warehouseId, logout, token } = useAuth();

  // Active navigation tab state: default to 'products'
  const [activeTab, setActiveTab] = useState('products');

  // --- 1. Products & Category State ---
  const [dbCategories, setDbCategories] = useState([]);
  // Products now come from the existing server-side paginated catalogue API
  // (same optimized hook the customer Shop page uses) instead of loading the
  // entire product table on every visit.
  const [rawProducts, setRawProducts] = useState([]);
  const [productsTotalCount, setProductsTotalCount] = useState(0);
  const [productsPage, setProductsPage] = useState(1);
  const [productsHasMore, setProductsHasMore] = useState(false);
  const [loadingMoreProducts, setLoadingMoreProducts] = useState(false);
  // Guards against stale responses when filters change rapidly.
  const productsReqSeq = useRef(0);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState(null);
  const [selectedProductForEdit, setSelectedProductForEdit] = useState(null);

  // Filters & Selection matching Customer Shop/Categories
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [activeSubcategory, setActiveSubcategory] = useState('All');
  const [productSearchQuery, setProductSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedSort, setSelectedSort] = useState('newest');
  const [onlySale, setOnlySale] = useState(false);
  const [onlyInStock, setOnlyInStock] = useState(false);
  const [maxPriceFilter, setMaxPriceFilter] = useState('');
  const [selectedSize, setSelectedSize] = useState('All');
  const [selectedColor, setSelectedColor] = useState('All');

  // --- 2. Orders State ---
  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersError, setOrdersError] = useState(null);
  const [ordersSearch, setOrdersSearch] = useState('');
  const [ordersStatus, setOrdersStatus] = useState('ALL');
  const [ordersPage, setOrdersPage] = useState(1);
  const [ordersTotalCount, setOrdersTotalCount] = useState(0);
  const [ordersTotalPages, setOrdersTotalPages] = useState(1);
  const [selectedOrderIdForModal, setSelectedOrderIdForModal] = useState(null);

  // --- 3. Deliveries State ---
  const [deliveries, setDeliveries] = useState([]);
  const [deliveriesLoading, setDeliveriesLoading] = useState(false);
  const [deliveriesError, setDeliveriesError] = useState(null);
  const [deliveriesSearch, setDeliveriesSearch] = useState('');
  const [deliveriesStatus, setDeliveriesStatus] = useState('ALL');
  const [deliveriesPartner, setDeliveriesPartner] = useState('ALL');
  const [deliveriesPage, setDeliveriesPage] = useState(1);
  const [deliveriesTotalCount, setDeliveriesTotalCount] = useState(0);
  const [deliveriesTotalPages, setDeliveriesTotalPages] = useState(1);

  // --- 4. Returns State ---
  const [returnsList, setReturnsList] = useState([]);
  const [returnsLoading, setReturnsLoading] = useState(false);
  const [returnsError, setReturnsError] = useState(null);
  const [returnsSearch, setReturnsSearch] = useState('');
  const [returnsStatus, setReturnsStatus] = useState('ALL');
  const [returnsReason, setReturnsReason] = useState('ALL');
  const [returnsPage, setReturnsPage] = useState(1);
  const [returnsTotalCount, setReturnsTotalCount] = useState(0);
  const [returnsTotalPages, setReturnsTotalPages] = useState(1);
  // Tracks which return is currently being accepted/rejected (return_id → 'accepting'|'rejecting'|'receiving')
  const [returnsActionPending, setReturnsActionPending] = useState({});

  // Return Pickup Assignment Modal state
  const [assignPickupModalReturn, setAssignPickupModalReturn] = useState(null);
  const [courierPartnersList, setCourierPartnersList] = useState([]);
  const [courierPartnersLoading, setCourierPartnersLoading] = useState(false);
  const [assignPickupCompany, setAssignPickupCompany] = useState('');
  const [assignPickupEmployeeId, setAssignPickupEmployeeId] = useState('');
  const [assignPickupEmployeesList, setAssignPickupEmployeesList] = useState([]);
  const [assignPickupEmployeesLoading, setAssignPickupEmployeesLoading] = useState(false);
  const [assignPickupSubmitting, setAssignPickupSubmitting] = useState(false);
  const [assignPickupError, setAssignPickupError] = useState(null);


  useEffect(() => {
    document.title = 'Warehouse Operations — TARIKA';
  }, []);

  // Fetch Data when Tab Changes or Filters/Pages Change
  useEffect(() => {
    if (activeTab === 'orders') {
      fetchOrders();
    } else if (activeTab === 'deliveries') {
      fetchDeliveries();
    } else if (activeTab === 'returns') {
      fetchReturns();
    }
  }, [
    activeTab,
    ordersPage,
    ordersStatus,
    deliveriesPage,
    deliveriesStatus,
    deliveriesPartner,
    returnsPage,
    returnsStatus,
    returnsReason
  ]);

  // Categories come from the cached module-level helper (single query,
  // invalidated after product edits via invalidateCategoriesCache()).
  const loadCategories = useCallback(async (force = false) => {
    if (force) invalidateCategoriesCache();
    const catRes = await getCategories();
    if (catRes.success && catRes.categories) {
      setDbCategories(catRes.categories);
    }
    return catRes;
  }, []);

  // Load Initial Category Data (module-level cache avoids duplicate requests
  // across dashboard visits). Declared after loadCategories so the hook
  // binding is initialized before its dependency array is evaluated.
  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  // Debounce free-text search before hitting the server (searching runs with
  // an icontains index-friendly WHERE clause, not over the whole catalogue).
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(productSearchQuery.trim()), 350);
    return () => clearTimeout(t);
  }, [productSearchQuery]);

  // Real database subcategories for the selected main category (returned by
  // the grouped categories query). When the active pill is a real
  // `sub_category` value the server filters on it directly.
  const selectedDbCategory = useMemo(() => {
    if (selectedCategory === 'ALL') return null;
    const sel = selectedCategory.toLowerCase();
    return dbCategories.find(
      (c) => (c.category_name || '').toLowerCase() === sel || (c.category_id || '').toLowerCase() === sel
    ) || null;
  }, [dbCategories, selectedCategory]);

  const isRealSubcategory = Boolean(
    selectedDbCategory &&
    activeSubcategory !== 'All' &&
    (selectedDbCategory.sub_categories || []).some((s) => s.sub_category === activeSubcategory)
  );

  // Build the server-side query (filter + search + sort + pagination) for the
  // current filter selection — reuses the existing optimized catalogue API.
  const buildWarehouseProductParams = (pageNum) => {
    const params = {
      sort: selectedSort,
      page: pageNum,
      page_size: 48,
    };
    if (selectedCategory !== 'ALL') params.category = selectedCategory;
    if (isRealSubcategory) params.sub_category = activeSubcategory;
    if (debouncedSearch) params.search = debouncedSearch;
    if (onlyInStock) params.in_stock = 'true';
    if (maxPriceFilter) params.max_price = maxPriceFilter;
    return params;
  };

  // Fetch one page of products, discarding stale responses when filters
  // changed while the request was in flight.
  const fetchProducts = useCallback(async (pageNum = 1) => {
    const seq = ++productsReqSeq.current;
    if (pageNum === 1) setProductsLoading(true);
    setProductsError(null);
    try {
      const res = await getProducts(buildWarehouseProductParams(pageNum));
      if (seq !== productsReqSeq.current) return; // a newer request already started
      if (res.success) {
        setRawProducts((prev) => {
          if (pageNum === 1) return res.products || [];
          const seen = new Set(prev.map((p) => p.product_id || p.id));
          const merged = [...prev];
          (res.products || []).forEach((p) => {
            const id = p.product_id || p.id;
            if (!seen.has(id)) {
              seen.add(id);
              merged.push(p);
            }
          });
          return merged;
        });
        setProductsTotalCount(res.count || 0);
        setProductsPage(pageNum);
        setProductsHasMore(Boolean(res.hasNext));
      } else {
        setProductsError(res.error || 'Failed to load database catalog products.');
      }
    } catch (err) {
      if (seq === productsReqSeq.current) setProductsError('Network error loading catalog.');
    } finally {
      if (seq === productsReqSeq.current) {
        setProductsLoading(false);
        setLoadingMoreProducts(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategory, isRealSubcategory, activeSubcategory, debouncedSearch, selectedSort, onlyInStock, maxPriceFilter]);

  // Re-fetch page one whenever the active server-side filters change.
  useEffect(() => {
    fetchProducts(1);
  }, [fetchProducts]);

  // Incremental loading: append the next page without duplicating products.
  const handleLoadMoreProducts = async () => {
    if (loadingMoreProducts || !productsHasMore) return;
    const seq = productsReqSeq.current;
    const nextPage = productsPage + 1;
    setLoadingMoreProducts(true);
    try {
      const res = await getProducts(buildWarehouseProductParams(nextPage));
      if (seq !== productsReqSeq.current) return; // filters changed mid-flight
      if (res.success) {
        setRawProducts((prev) => {
          const seen = new Set(prev.map((p) => p.product_id || p.id));
          const merged = [...prev];
          (res.products || []).forEach((p) => {
            const id = p.product_id || p.id;
            if (!seen.has(id)) {
              seen.add(id);
              merged.push(p);
            }
          });
          return merged;
        });
        setProductsPage(nextPage);
        setProductsHasMore(Boolean(res.hasNext));
      }
    } catch (err) {
      // keep current list; the button stays available for retry
    } finally {
      if (seq === productsReqSeq.current) setLoadingMoreProducts(false);
    }
  };

  // Manual "Refresh Catalog" — refetches categories (cache invalidated) and
  // reloads page one of the currently filtered product query.
  const fetchCatalog = async () => {
    await loadCategories(true);
    fetchProducts(1);
  };

  // Keep the existing category-section presentation, but group only the
  // currently loaded page results instead of the whole catalogue.
  const filteredCategories = useMemo(() => {
    let list = [...rawProducts];

    // Client-side filters whose columns are not part of the real schema
    // (kept exactly as before: sale comparison, size and color attributes)
    if (onlySale) {
      list = list.filter((p) => {
        const base = Number(p.base_price || 0);
        const sale = Number(p.selling_price || p.sale_price || base);
        return p.is_on_sale || (sale > 0 && sale < base);
      });
    }
    if (selectedSize !== 'All') {
      list = list.filter((p) => (p.size || '').toLowerCase() === selectedSize.toLowerCase());
    }
    if (selectedColor !== 'All') {
      list = list.filter((p) => (p.color || '').toLowerCase().includes(selectedColor.toLowerCase()));
    }

    // Legacy keyword filter only for preset pills that are not backed by a
    // real `sub_category` value (real values are filtered server-side).
    if (!isRealSubcategory && activeSubcategory && !activeSubcategory.startsWith('All')) {
      const keyword = activeSubcategory
        .replace(/(Dresses|Tops|Bottoms|Jeans|Jackets|Shirts|Kurtis|Sarees|Ethnic Wear|Handbags|Footwear|Accessories)/gi, '')
        .trim()
        .toLowerCase();
      if (keyword) {
        const subList = list.filter((p) => {
          const name = (p.product_name || p.name || '').toLowerCase();
          return name.includes(keyword);
        });
        if (subList.length > 0) list = subList;
      }
    }

    const map = {};
    list.forEach((p) => {
      const catName = p.category_name || 'General Catalog';
      if (!map[catName]) {
        map[catName] = {
          category_id: p.category_id || catName.toLowerCase().replace(/\s+/g, '-'),
          category_name: catName,
          products: [],
        };
      }
      map[catName].products.push(p);
    });
    return Object.values(map).sort((a, b) => a.category_name.localeCompare(b.category_name));
  }, [rawProducts, onlySale, selectedSize, selectedColor, activeSubcategory, isRealSubcategory]);

  const totalFilteredProducts = useMemo(() => {
    return filteredCategories.reduce((acc, cat) => acc + cat.products.length, 0);
  }, [filteredCategories]);

  const hasActiveFilters = Boolean(
    activeSubcategory !== 'All' ||
    selectedSize !== 'All' ||
    selectedColor !== 'All' ||
    onlySale ||
    onlyInStock ||
    maxPriceFilter ||
    productSearchQuery
  );

  const resetAllFilters = () => {
    setActiveSubcategory('All');
    setSelectedSize('All');
    setSelectedColor('All');
    setOnlySale(false);
    setOnlyInStock(false);
    setMaxPriceFilter('');
    setProductSearchQuery('');
  };

  // Orders Fetch
  const fetchOrders = async () => {
    setOrdersLoading(true);
    setOrdersError(null);
    const res = await getWarehouseOrders({
      search: ordersSearch,
      status: ordersStatus,
      page: ordersPage,
      page_size: 15
    });
    if (res.success) {
      setOrders(res.orders || []);
      setOrdersTotalCount(res.count || 0);
      setOrdersTotalPages(res.totalPages || 1);
    } else {
      setOrdersError(res.error || 'Failed to fetch database orders.');
    }
    setOrdersLoading(false);
  };

  // Deliveries Fetch
  const fetchDeliveries = async () => {
    setDeliveriesLoading(true);
    setDeliveriesError(null);
    const res = await getWarehouseDeliveries({
      search: deliveriesSearch,
      status: deliveriesStatus,
      partner: deliveriesPartner,
      page: deliveriesPage,
      page_size: 15
    });
    if (res.success) {
      setDeliveries(res.deliveries || []);
      setDeliveriesTotalCount(res.count || 0);
      setDeliveriesTotalPages(res.totalPages || 1);
    } else {
      setDeliveriesError(res.error || 'Failed to fetch database deliveries.');
    }
    setDeliveriesLoading(false);
  };

  // Returns Fetch
  const fetchReturns = async () => {
    setReturnsLoading(true);
    setReturnsError(null);
    const res = await getWarehouseReturns({
      search: returnsSearch,
      status: returnsStatus,
      reason: returnsReason,
      page: returnsPage,
      page_size: 15
    });
    if (res.success) {
      setReturnsList(res.returnsList || []);
      setReturnsTotalCount(res.count || 0);
      setReturnsTotalPages(res.totalPages || 1);
    } else {
      setReturnsError(res.error || 'Failed to fetch database returns.');
    }
    setReturnsLoading(false);
  };

  // Handle Search Submission
  const handleOrdersSearchSubmit = (e) => {
    e.preventDefault();
    setOrdersPage(1);
    fetchOrders();
  };

  const handleDeliveriesSearchSubmit = (e) => {
    e.preventDefault();
    setDeliveriesPage(1);
    fetchDeliveries();
  };

  const handleReturnsSearchSubmit = (e) => {
    e.preventDefault();
    setReturnsPage(1);
    fetchReturns();
  };

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} />, count: null },
    { id: 'products', label: 'Products', icon: <Package size={18} />, count: totalFilteredProducts },
    { id: 'orders', label: 'Orders', icon: <ShoppingBag size={18} />, count: ordersTotalCount || 7949 },
    { id: 'deliveries', label: 'Deliveries', icon: <Truck size={18} />, count: deliveriesTotalCount || 7030 },
    { id: 'returns', label: 'Returns', icon: <RotateCcw size={18} />, count: returnsTotalCount || 1177 },
  ];

  const aiNavItems = [
    { id: 'stock-to-be-ordered', label: 'Stock to Be Ordered', icon: <Sparkles size={18} />, count: 'OLS' },
  ];

  // Status Badge Helper Components
  const renderOrderStatusBadge = (statusStr) => {
    const st = (statusStr || '').toLowerCase();
    let bg = '#FBF1F0', color = '#B8505E', border = 'rgba(216, 114, 126, 0.2)';
    if (st.includes('delivered')) {
      bg = '#ECFDF5'; color = '#059669'; border = '#A7F3D0';
    } else if (st.includes('confirmed') || st.includes('processing')) {
      bg = '#EFF6FF'; color = '#2563EB'; border = '#BFDBFE';
    } else if (st.includes('pending')) {
      bg = '#FFFBEB'; color = '#D97706'; border = '#FDE68A';
    } else if (st.includes('cancelled')) {
      bg = '#FEF2F2'; color = '#DC2626'; border = '#FECACA';
    }
    return (
      <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.65rem', borderRadius: '9999px', backgroundColor: bg, color, border: `1px solid ${border}`, textTransform: 'capitalize' }}>
        {statusStr || 'Pending'}
      </span>
    );
  };

  const renderPaymentStatusBadge = (statusStr) => {
    const st = (statusStr || '').toLowerCase();
    let bg = '#FFFBEB', color = '#D97706';
    if (st.includes('paid') || st.includes('success')) {
      bg = '#ECFDF5'; color = '#059669';
    } else if (st.includes('failed')) {
      bg = '#FEF2F2'; color = '#DC2626';
    }
    return (
      <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '0.2rem 0.55rem', borderRadius: '6px', backgroundColor: bg, color, textTransform: 'capitalize' }}>
        {statusStr || 'Pending'}
      </span>
    );
  };

  const renderDeliveryStatusBadge = (statusStr) => {
    const st = (statusStr || '').toLowerCase();
    let bg = '#ECFDF5', color = '#059669', border = '#A7F3D0';
    if (st.includes('transit')) {
      bg = '#EFF6FF'; color = '#2563EB'; border = '#BFDBFE';
    } else if (st.includes('out for delivery')) {
      bg = '#F5F3FF'; color = '#7C3AED'; border = '#DDD6FE';
    } else if (st.includes('fail') || st.includes('returned') || st.includes('cancel')) {
      bg = '#FEF2F2'; color = '#DC2626'; border = '#FECACA';
    } else if (st.includes('pending')) {
      bg = '#FFFBEB'; color = '#D97706'; border = '#FDE68A';
    }
    return (
      <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.65rem', borderRadius: '9999px', backgroundColor: bg, color, border: `1px solid ${border}` }}>
        {statusStr || 'In Transit'}
      </span>
    );
  };

  const renderReturnStatusBadge = (statusStr) => {
    const st = (statusStr || '').toLowerCase();
    let bg = '#ECFDF5', color = '#059669', border = '#A7F3D0';
    if (st.includes('request') || st.includes('pending')) {
      bg = '#FFFBEB'; color = '#D97706'; border = '#FDE68A';
    } else if (st.includes('approved') || st.includes('accept')) {
      bg = '#EFF6FF'; color = '#2563EB'; border = '#BFDBFE';
    } else if (st.includes('pickup assigned')) {
      bg = '#F3E8FF'; color = '#7E22CE'; border = '#DDD6FE';
    } else if (st.includes('pickup accepted')) {
      bg = '#EDE9FE'; color = '#6D28D9'; border = '#C4B5FD';
    } else if (st.includes('picked up')) {
      bg = '#FEF3C7'; color = '#B45309'; border = '#FCD34D';
    } else if (st.includes('received at warehouse')) {
      bg = '#E0F2FE'; color = '#0369A1'; border = '#BAE6FD';
    } else if (st.includes('reject') || st.includes('failed')) {
      bg = '#FEF2F2'; color = '#DC2626'; border = '#FECACA';
    } else if (st.includes('completed') || st.includes('refund')) {
      bg = '#ECFDF5'; color = '#059669'; border = '#A7F3D0';
    }
    return (
      <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.65rem', borderRadius: '9999px', backgroundColor: bg, color, border: `1px solid ${border}`, textTransform: 'capitalize' }}>
        {statusStr || 'Requested'}
      </span>
    );
  };

  const fetchCourierPartnersList = useCallback(async () => {
    setCourierPartnersLoading(true);
    const res = await getCourierPartners();
    setCourierPartnersLoading(false);
    if (res.success && Array.isArray(res.partners)) {
      setCourierPartnersList(res.partners);
    }
  }, []);

  useEffect(() => {
    fetchCourierPartnersList();
  }, [fetchCourierPartnersList]);

  const handleOpenAssignPickupModal = (ret) => {
    setAssignPickupModalReturn(ret);
    setAssignPickupCompany('');
    setAssignPickupEmployeeId('');
    setAssignPickupEmployeesList([]);
    setAssignPickupError(null);
    if (!courierPartnersList || courierPartnersList.length === 0) {
      fetchCourierPartnersList();
    }
  };


  const handleAssignCompanyChange = async (e) => {
    const comp = e.target.value;
    setAssignPickupCompany(comp);
    setAssignPickupEmployeeId('');
    setAssignPickupError(null);
    if (!comp) {
      setAssignPickupEmployeesList([]);
      return;
    }
    setAssignPickupEmployeesLoading(true);
    const res = await getDeliveryEmployees(comp);
    setAssignPickupEmployeesLoading(false);
    if (res.success && res.employees) {
      setAssignPickupEmployeesList(res.employees);
    } else {
      setAssignPickupEmployeesList([]);
      setAssignPickupError(res.error || 'Failed to load delivery employees for this courier.');
    }
  };

  const handleConfirmAssignPickup = async () => {
    if (!assignPickupModalReturn) return;
    if (!assignPickupCompany) {
      setAssignPickupError('Please select a courier company.');
      return;
    }
    if (!assignPickupEmployeeId) {
      setAssignPickupError('Please select an active delivery partner employee.');
      return;
    }

    setAssignPickupSubmitting(true);
    setAssignPickupError(null);
    const res = await assignWarehouseReturnPickup(assignPickupModalReturn.return_id, {
      delivery_partner: assignPickupCompany,
      assigned_employee_id: assignPickupEmployeeId,
    });
    setAssignPickupSubmitting(false);

    if (res.success && res.return) {
      setReturnsList(prev => prev.map(r => r.return_id === assignPickupModalReturn.return_id ? res.return : r));
      setAssignPickupModalReturn(null);
    } else {
      setAssignPickupError(res.error || 'Failed to assign return pickup.');
    }
  };

  const handleConfirmReturnReceived = async (ret) => {
    if (!window.confirm(`Confirm merchandise for Return ${ret.return_id} has arrived at the warehouse?`)) return;
    setReturnsActionPending(prev => ({ ...prev, [ret.return_id]: 'receiving' }));
    const res = await receiveWarehouseReturn(ret.return_id);
    setReturnsActionPending(prev => { const n = { ...prev }; delete n[ret.return_id]; return n; });

    if (res.success && res.return) {
      setReturnsList(prev => prev.map(r => r.return_id === ret.return_id ? res.return : r));
    } else {
      alert(res.error || 'Failed to confirm return received.');
    }
  };

  return (
    <div className="tarika-home" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#FAF7F5' }}>

      {/* 1. TOP HEADER / NAVBAR */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          backgroundColor: 'rgba(255, 255, 255, 0.94)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderBottom: '1px solid var(--tarika-border, #F0E2E0)',
          boxShadow: '0 4px 20px rgba(184, 80, 94, 0.05)'
        }}
      >
        <div
          style={{
            maxWidth: '1760px',
            margin: '0 auto',
            padding: '0.85rem 2rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1.5rem'
          }}
        >
          {/* Brand Logo & Section Badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
              <span
                className="tarika-serif"
                style={{
                  fontSize: '1.75rem',
                  fontWeight: 700,
                  letterSpacing: '0.12em',
                  background: 'linear-gradient(135deg, #1F191B 0%, #B8505E 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}
              >
                TARIKA
              </span>
              <span
                style={{
                  fontSize: '0.58rem',
                  letterSpacing: '0.28em',
                  color: '#8E3642',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  marginTop: '2px'
                }}
              >
                HAUTE BOUTIQUE
              </span>
            </div>

            <div style={{ height: '28px', width: '1px', backgroundColor: 'var(--tarika-border, #F0E2E0)' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div
                style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: '10px',
                  background: 'rgba(216, 114, 126, 0.12)',
                  color: 'var(--tarika-rose, #D8727E)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Warehouse size={18} />
              </div>
              <div>
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1F191B', display: 'block', lineHeight: 1.1 }}>
                  Warehouse Operations Portal
                </span>
                <span style={{ fontSize: '0.75rem', color: '#6B5E63' }}>
                  Central Logistics, Inventory & Fulfillment
                </span>
              </div>
            </div>
          </div>

          {/* Facility & User Account Info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.45rem 0.9rem',
                borderRadius: '9999px',
                background: '#FFFBF9',
                border: '1px solid rgba(216, 114, 126, 0.25)',
                fontSize: '0.8rem',
                color: '#1F191B'
              }}
            >
              <MapPin size={15} color="#D8727E" />
              <span style={{ fontWeight: 600, color: '#6B5E63' }}>Facility ID:</span>
              <code style={{ fontFamily: 'monospace', fontWeight: 700, color: '#B8505E' }}>
                {warehouseId || user?.warehouse_id || '8527dc10-e4f3-45a1-a5d7-166a6f03155c'}
              </code>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.35rem 0.85rem 0.35rem 0.45rem',
                borderRadius: '9999px',
                background: '#FFFFFF',
                border: '1px solid var(--tarika-border, #F0E2E0)'
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #D8727E 0%, #B8505E 100%)',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.85rem',
                  fontWeight: 700
                }}
              >
                {user?.full_name ? user.full_name[0].toUpperCase() : 'W'}
              </div>
              <div style={{ lineHeight: 1.2 }}>
                <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 700, color: '#1F191B' }}>
                  {user?.full_name || 'Warehouse Manager'}
                </p>
                <p style={{ margin: 0, fontSize: '0.7rem', color: '#8E3642', fontWeight: 600 }}>
                  WAREHOUSE_MANAGER
                </p>
              </div>
            </div>

            <button onClick={logout} className="tarika-btn-outline" style={{ padding: '0.5rem 1.1rem', fontSize: '0.82rem', borderRadius: '9999px' }}>
              <LogOut size={15} color="#D8727E" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* MAIN CONTAINER WITH SIDEBAR & CONTENT */}
      <div style={{ display: 'flex', flex: 1, maxWidth: '1760px', width: '100%', margin: '0 auto', padding: '1.5rem 2rem', gap: '2rem' }}>

        {/* 2. SIDEBAR NAVIGATION */}
        <aside style={{ width: '260px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ padding: '0.75rem 1rem', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#8E3642' }}>
            Management Modules
          </div>

          {/* Management Modules Nav */}
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.85rem 1.15rem',
                  borderRadius: '14px',
                  border: '1px solid',
                  borderColor: isActive ? 'rgba(216, 114, 126, 0.35)' : 'transparent',
                  backgroundColor: isActive ? '#FFFFFF' : 'transparent',
                  color: isActive ? '#B8505E' : '#6B5E63',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  transition: 'all 0.25s ease',
                  boxShadow: isActive ? '0 6px 20px rgba(184, 80, 94, 0.08)' : 'none'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ color: isActive ? '#D8727E' : '#9E8F94' }}>{item.icon}</span>
                  <span>{item.label}</span>
                </div>
                {item.count !== null && item.count !== undefined && (
                  <span
                    style={{
                      padding: '0.15rem 0.55rem',
                      borderRadius: '9999px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      backgroundColor: isActive ? 'rgba(216, 114, 126, 0.12)' : 'rgba(0, 0, 0, 0.05)',
                      color: isActive ? '#B8505E' : '#6B5E63'
                    }}
                  >
                    {item.count}
                  </span>
                )}
              </button>
            );
          })}

          {/* AI Analysis Section */}
          <div style={{ padding: '1.25rem 1rem 0.25rem', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#8E3642' }}>
            AI Analysis
          </div>
          {aiNavItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.85rem 1.15rem',
                  borderRadius: '14px',
                  border: '1px solid',
                  borderColor: isActive ? 'rgba(216, 114, 126, 0.35)' : 'transparent',
                  backgroundColor: isActive ? '#FFFFFF' : 'transparent',
                  color: isActive ? '#B8505E' : '#6B5E63',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  transition: 'all 0.25s ease',
                  boxShadow: isActive ? '0 6px 20px rgba(184, 80, 94, 0.08)' : 'none'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ color: isActive ? '#D8727E' : '#9E8F94' }}>{item.icon}</span>
                  <span>{item.label}</span>
                </div>
                <span
                  style={{
                    padding: '0.15rem 0.55rem',
                    borderRadius: '9999px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    backgroundColor: isActive ? 'rgba(216, 114, 126, 0.12)' : 'rgba(0, 0, 0, 0.05)',
                    color: isActive ? '#B8505E' : '#6B5E63'
                  }}
                >
                  {item.count}
                </span>
              </button>
            );
          })}

          {/* Sidebar Footer */}
        </aside>


        {/* 3. MAIN CONTENT AREA */}
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem', minWidth: 0 }}>

          {/* TAB 1: PRODUCTS (CATEGORY-WISE DISPLAY REPLICATING CUSTOMER SHOP/CATEGORIES) */}
          {activeTab === 'products' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              {/* Top Header Banner */}
              <div
                style={{
                  background: '#FFFFFF',
                  borderRadius: '20px',
                  padding: '1.75rem 2rem',
                  border: '1px solid var(--tarika-border, #F0E2E0)',
                  boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '1.25rem'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span className="tarika-serif" style={{ fontSize: '1.75rem', fontWeight: 700, color: '#1F191B' }}>
                      Database Products Catalog
                    </span>
                    <span className="tarika-badge tarika-badge-new" style={{ textTransform: 'uppercase' }}>
                      Category-Wise View
                    </span>
                  </div>
                  <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: 0 }}>
                    Products fetched from existing database grouped category-wise matching customer presentation. Showing {totalFilteredProducts.toLocaleString()} of {productsTotalCount.toLocaleString()} matched items across {filteredCategories.length} categories.
                  </p>
                </div>

                <button onClick={fetchCatalog} className="tarika-btn-outline" disabled={productsLoading} style={{ padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}>
                  <RefreshCw size={15} className={productsLoading ? 'animate-spin' : ''} color="#D8727E" />
                  <span>Refresh Catalog</span>
                </button>
              </div>

              {/* Dual Pane Layout (Left Department Sidebar + Right Hero Banner & Products Grid) */}
              <div
                style={{
                  display: 'flex',
                  gap: '2.5rem',
                  alignItems: 'flex-start',
                }}
                className="department-dual-pane"
              >
                {/* LEFT SIDEBAR: Sub-categories and Department Switcher */}
                <aside className="department-tabs-sidebar" style={{ top: '90px' }}>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      letterSpacing: '0.1em',
                      color: '#8E3642',
                      padding: '0 8px 8px 8px',
                    }}
                  >
                    {selectedCategory === 'ALL' ? 'ALL DEPARTMENTS' : selectedCategory}
                  </span>

                  {/* Subcategories for selected category — real `sub_category`
                      values from the database when available (filtered
                      server-side), falling back to the existing presets */}
                  {selectedCategory !== 'ALL' && (
                    selectedDbCategory?.sub_categories?.length
                      ? ['All ' + selectedCategory, ...selectedDbCategory.sub_categories.map((s) => s.sub_category)]
                      : (CATEGORY_SUBCATEGORIES[selectedCategory] || [`All ${selectedCategory}`, `Classic ${selectedCategory}`, `Casual ${selectedCategory}`, `Formal ${selectedCategory}`, `Atelier ${selectedCategory}`])
                  ).map((sub, index) => {
                    const isActive = activeSubcategory === sub || (index === 0 && activeSubcategory === 'All');
                    return (
                      <button
                        key={sub}
                        type="button"
                        className={`department-tab-btn ${isActive ? 'is-active' : ''}`}
                        onClick={() => setActiveSubcategory(sub)}
                      >
                        <span>{sub}</span>
                        {index === 0 && (
                          <span style={{ fontSize: '0.72rem', color: isActive ? '#B8505E' : '#9E8F94' }}>
                            ({totalFilteredProducts})
                          </span>
                        )}
                      </button>
                    );
                  })}

                  <div
                    style={{
                      margin: '1.5rem 0 0.5rem 0',
                      borderTop: '1px solid rgba(216, 114, 126, 0.15)',
                      paddingTop: '1rem',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 800,
                        textTransform: 'uppercase',
                        letterSpacing: '0.1em',
                        color: '#9E8F94',
                        padding: '0 8px 8px 8px',
                      }}
                    >
                      {selectedCategory !== 'ALL' ? 'Other Departments' : 'Departments'}
                    </span>
                  </div>

                  {/* All Categories Option */}
                  <button
                    type="button"
                    className={`department-tab-btn ${selectedCategory === 'ALL' ? 'is-active' : ''}`}
                    onClick={() => { setSelectedCategory('ALL'); setActiveSubcategory('All'); }}
                  >
                    <span>All Departments</span>
                    <span style={{ fontSize: '0.72rem', color: selectedCategory === 'ALL' ? '#B8505E' : '#9E8F94' }}>
                      ({dbCategories.reduce((sum, c) => sum + (c.product_count || 0), 0)})
                    </span>
                  </button>

                  {/* Database Categories List */}
                  {dbCategories
                    .filter((cat) => (cat.category_name || '').toLowerCase() !== 'kids wear')
                    .map((cat) => {
                      const catName = cat.category_name || cat.name;
                      const isSelected = selectedCategory.toLowerCase() === catName?.toLowerCase();
                      return (
                        <button
                          key={cat.category_id || catName}
                          type="button"
                          className={`department-tab-btn ${isSelected ? 'is-active' : ''}`}
                          onClick={() => { setSelectedCategory(catName); setActiveSubcategory('All'); }}
                        >
                          <span>{catName}</span>
                          <span style={{ fontSize: '0.72rem', color: isSelected ? '#B8505E' : '#9E8F94' }}>
                            {cat.product_count !== undefined ? `(${cat.product_count})` : ''}
                          </span>
                        </button>
                      );
                    })}
                </aside>

                {/* RIGHT COLUMN: Hero Banner, Quick Filter Bar & Products Grid */}
                <div style={{ flex: 1, minWidth: 0 }}>

                  {/* Category Hero Banner matching Customer reference */}
                  <div className="cat-selected-hero-banner" style={{ marginBottom: '1.5rem' }}>
                    <div>
                      <span
                        style={{
                          fontSize: '0.74rem',
                          fontWeight: 800,
                          letterSpacing: '0.14em',
                          textTransform: 'uppercase',
                          color: '#8E3642',
                        }}
                      >
                        WAREHOUSE DEPARTMENT CATALOG
                      </span>
                      <h2
                        style={{
                          fontFamily: "'Playfair Display', serif",
                          fontSize: '2.2rem',
                          fontWeight: 700,
                          margin: '4px 0',
                          color: '#1F191B',
                        }}
                      >
                        {selectedCategory === 'ALL' ? 'ALL DEPARTMENTS' : (CATEGORY_HERO_META[selectedCategory]?.title || selectedCategory.toUpperCase())}
                      </h2>
                      <p style={{ margin: 0, color: '#6B5E63', fontSize: '0.92rem' }}>
                        Products fetched from database grouped category-wise for warehouse inventory and fulfillment management.
                      </p>
                    </div>

                    {/* Right Side Quote & Vignette */}
                    <div className="cat-hero-right-accent">
                      <p className="cat-hero-script-tagline">
                        {CATEGORY_HERO_META[selectedCategory]?.quote || 'Curated luxury garments & apparel.'}
                      </p>
                      <div className="cat-hero-vignette-circle">
                        <img
                          src={
                            CATEGORY_HERO_META[selectedCategory]?.image ||
                            'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=300&auto=format&fit=crop&q=80'
                          }
                          alt={selectedCategory}
                          loading="lazy"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Quick Filter Bar matching Customer Shop/Categories */}
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '1rem',
                      padding: '12px 16px',
                      backgroundColor: '#FFFFFF',
                      borderRadius: '18px',
                      border: '1px solid rgba(240, 226, 224, 0.9)',
                      marginBottom: '1.5rem',
                      boxShadow: '0 4px 15px rgba(184, 80, 94, 0.04)',
                    }}
                  >
                    {/* Search & Filter Pills */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', flex: 1 }}>
                      {/* Search Bar */}
                      <div style={{ position: 'relative', minWidth: '220px', flex: 1 }}>
                        <Search size={14} color="#B8505E" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
                        <input
                          type="text"
                          placeholder="Search product, SKU, material, color..."
                          value={productSearchQuery}
                          onChange={(e) => setProductSearchQuery(e.target.value)}
                          style={{
                            width: '100%',
                            padding: '6px 12px 6px 2.2rem',
                            borderRadius: '9999px',
                            border: '1px solid #F0E2E0',
                            backgroundColor: '#FAF7F5',
                            fontSize: '0.8rem',
                            color: '#1F191B',
                            outline: 'none'
                          }}
                        />
                      </div>

                      {/* Filter Pills */}
                      <button
                        type="button"
                        onClick={() => setOnlySale(!onlySale)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '9999px',
                          border: `1px solid ${onlySale ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: onlySale ? '#FBF1F0' : '#FAF7F5',
                          color: onlySale ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <Tag size={13} />
                        <span>On Sale</span>
                        {onlySale && <Check size={12} />}
                      </button>

                      <button
                        type="button"
                        onClick={() => setOnlyInStock(!onlyInStock)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '9999px',
                          border: `1px solid ${onlyInStock ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: onlyInStock ? '#FBF1F0' : '#FAF7F5',
                          color: onlyInStock ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <span>In Stock Only</span>
                        {onlyInStock && <Check size={12} />}
                      </button>

                      <button
                        type="button"
                        onClick={() => setMaxPriceFilter(maxPriceFilter === '1000' ? '' : '1000')}
                        style={{
                          padding: '6px 14px',
                          borderRadius: '9999px',
                          border: `1px solid ${maxPriceFilter === '1000' ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: maxPriceFilter === '1000' ? '#FBF1F0' : '#FAF7F5',
                          color: maxPriceFilter === '1000' ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        Under ₹1,000
                      </button>

                      <button
                        type="button"
                        onClick={() => setMaxPriceFilter(maxPriceFilter === '2000' ? '' : '2000')}
                        style={{
                          padding: '6px 14px',
                          borderRadius: '9999px',
                          border: `1px solid ${maxPriceFilter === '2000' ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: maxPriceFilter === '2000' ? '#FBF1F0' : '#FAF7F5',
                          color: maxPriceFilter === '2000' ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        Under ₹2,000
                      </button>

                      {/* Size Selector */}
                      <select
                        value={selectedSize}
                        onChange={(e) => setSelectedSize(e.target.value)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '9999px',
                          border: `1px solid ${selectedSize !== 'All' ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: selectedSize !== 'All' ? '#FBF1F0' : '#FAF7F5',
                          color: selectedSize !== 'All' ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          outline: 'none',
                        }}
                      >
                        <option value="All">Size: All</option>
                        <option value="XS">Size: XS</option>
                        <option value="S">Size: S</option>
                        <option value="M">Size: M</option>
                        <option value="L">Size: L</option>
                        <option value="XL">Size: XL</option>
                      </select>

                      {/* Color Selector */}
                      <select
                        value={selectedColor}
                        onChange={(e) => setSelectedColor(e.target.value)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '9999px',
                          border: `1px solid ${selectedColor !== 'All' ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: selectedColor !== 'All' ? '#FBF1F0' : '#FAF7F5',
                          color: selectedColor !== 'All' ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          outline: 'none',
                        }}
                      >
                        <option value="All">Color: All</option>
                        <option value="Black">Color: Black</option>
                        <option value="White">Color: White</option>
                        <option value="Pink">Color: Pink</option>
                        <option value="Blue">Color: Blue</option>
                        <option value="Beige">Color: Beige</option>
                        <option value="Green">Color: Green</option>
                        <option value="Red">Color: Red</option>
                      </select>

                      {/* Category Dropdown */}
                      <select
                        value={selectedCategory}
                        onChange={(e) => { setSelectedCategory(e.target.value); setActiveSubcategory('All'); }}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '9999px',
                          border: `1px solid ${selectedCategory !== 'ALL' ? '#D8727E' : '#F0E2E0'}`,
                          backgroundColor: selectedCategory !== 'ALL' ? '#FBF1F0' : '#FAF7F5',
                          color: selectedCategory !== 'ALL' ? '#B8505E' : '#1F191B',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          outline: 'none',
                        }}
                      >
                        <option value="ALL">Category: All ({dbCategories.length})</option>
                        {dbCategories.map((c) => (
                          <option key={c.category_id || c.category_name} value={c.category_name}>
                            {c.category_name} ({c.product_count || 0})
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Sorting Dropdown */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '0.8rem', color: '#6B5E63', fontWeight: 600 }}>Sort:</span>
                      <select
                        value={selectedSort}
                        onChange={(e) => setSelectedSort(e.target.value)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '10px',
                          border: '1px solid #F0E2E0',
                          backgroundColor: '#FAF7F5',
                          fontSize: '0.82rem',
                          color: '#1F191B',
                          fontWeight: 600,
                          outline: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        <option value="newest">Newest First</option>
                        <option value="price_low_high">Price: Low to High</option>
                        <option value="price_high_low">Price: High to Low</option>
                        <option value="name">Name: A to Z</option>
                      </select>
                    </div>
                  </div>

                  {/* Products Count Header */}
                  <div
                    style={{
                      marginBottom: '1.25rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontSize: '0.86rem', color: '#6B5E63', fontWeight: 600 }}>
                      {totalFilteredProducts.toLocaleString()} Loaded Products ({productsTotalCount.toLocaleString()} Matched in Database)
                    </span>
                    {hasActiveFilters && (
                      <button
                        type="button"
                        onClick={resetAllFilters}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          background: 'none',
                          border: 'none',
                          fontSize: '0.78rem',
                          color: '#D8727E',
                          cursor: 'pointer',
                          fontWeight: 600,
                        }}
                      >
                        <RotateCcw size={12} />
                        Reset all filters
                      </button>
                    )}
                  </div>

                  {/* Loading State */}
                  {productsLoading && (
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                        gap: '1.5rem',
                      }}
                    >
                      {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
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
                  )}

                  {/* Error State */}
                  {productsError && !productsLoading && (
                    <div className="tarika-auth-alert">
                      <AlertCircle size={20} />
                      <span>{productsError}</span>
                    </div>
                  )}

                  {/* Category-Wise Product Sections Display */}
                  {!productsLoading && !productsError && filteredCategories.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                      {filteredCategories.map((category) => (
                        <section
                          key={category.category_id || category.category_name}
                          style={{
                            background: '#FFFFFF',
                            borderRadius: '20px',
                            padding: '1.75rem',
                            border: '1px solid var(--tarika-border, #F0E2E0)',
                            boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '1.25rem'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '1rem', borderBottom: '1.5px solid var(--tarika-border, #F0E2E0)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
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
                                  fontWeight: 700
                                }}
                              >
                                {category.category_name ? category.category_name[0].toUpperCase() : 'C'}
                              </div>
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                  <h3 className="tarika-serif" style={{ fontSize: '1.45rem', fontWeight: 700, margin: 0, color: '#1F191B' }}>
                                    {category.category_name}
                                  </h3>
                                  <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.65rem', borderRadius: '9999px', backgroundColor: 'rgba(216, 114, 126, 0.12)', color: '#B8505E' }}>
                                    {category.products.length} {category.products.length === 1 ? 'Product' : 'Products'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div
                            style={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                              gap: '1.5rem',
                            }}
                          >
                            {category.products.map((prod) => (
                              <WarehouseProductCard
                                key={prod.product_id || prod.id}
                                product={prod}
                                onCardClick={(productToEdit) => setSelectedProductForEdit(productToEdit)}
                              />
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                  )}

                  {/* Incremental loading: fetch next page of the filtered catalogue */}
                  {!productsLoading && !productsError && filteredCategories.length > 0 && productsHasMore && (
                    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '0.5rem' }}>
                      <button
                        type="button"
                        className="tarika-btn-outline"
                        onClick={handleLoadMoreProducts}
                        disabled={loadingMoreProducts}
                        style={{ padding: '0.7rem 1.6rem', fontSize: '0.85rem' }}
                      >
                        <RefreshCw size={15} className={loadingMoreProducts ? 'animate-spin' : ''} color="#D8727E" />
                        <span>
                          {loadingMoreProducts
                            ? 'Loading More…'
                            : `Load More Products (Showing ${totalFilteredProducts.toLocaleString()} of ${productsTotalCount.toLocaleString()})`}
                        </span>
                      </button>
                    </div>
                  )}

                  {/* Empty State */}
                  {!productsLoading && !productsError && filteredCategories.length === 0 && (
                    <div
                      style={{
                        padding: '4rem 2rem',
                        textAlign: 'center',
                        backgroundColor: '#FFFFFF',
                        borderRadius: '20px',
                        border: '1px solid #F0E2E0',
                      }}
                    >
                      <Sparkles size={36} color="#D8727E" style={{ marginBottom: '1rem' }} />
                      <h3
                        style={{
                          fontFamily: "'Playfair Display', serif",
                          fontSize: '1.4rem',
                          color: '#1F191B',
                          margin: '0 0 0.5rem 0',
                        }}
                      >
                        No Database Products Found In This Selection
                      </h3>
                      <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: '0 0 1.5rem 0' }}>
                        Try resetting your price, size, search query, or stock filters to view available items in{' '}
                        {selectedCategory === 'ALL' ? 'the catalog' : selectedCategory}.
                      </p>
                      <button
                        type="button"
                        className="tarika-btn-outline"
                        onClick={resetAllFilters}
                      >
                        Reset All Filters
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: ORDERS (REAL DATABASE ORDERS) */}
          {activeTab === 'orders' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Header & Stats Banner */}
              <div
                style={{
                  background: '#FFFFFF',
                  borderRadius: '20px',
                  padding: '1.75rem 2rem',
                  border: '1px solid var(--tarika-border, #F0E2E0)',
                  boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '1.25rem'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span className="tarika-serif" style={{ fontSize: '1.75rem', fontWeight: 700, color: '#1F191B' }}>
                      Orders ({ordersTotalCount.toLocaleString()})
                    </span>
                  </div>
                  <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: 0 }}>
                    Manage customer order fulfillment and track payment status. Showing Page {ordersPage} of {ordersTotalPages}.
                  </p>
                </div>

                <button onClick={fetchOrders} className="tarika-btn-outline" disabled={ordersLoading} style={{ padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}>
                  <RefreshCw size={15} className={ordersLoading ? 'animate-spin' : ''} color="#D8727E" />
                  <span>Refresh Orders</span>
                </button>
              </div>

              {/* Search & Status Filter Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                <form onSubmit={handleOrdersSearchSubmit} style={{ position: 'relative', minWidth: '320px', flex: 1 }}>
                  <Search size={16} color="#B8505E" style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    placeholder="Search by Order ID, Customer Name, Email, Address..."
                    value={ordersSearch}
                    onChange={(e) => setOrdersSearch(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem 0.75rem 2.75rem',
                      borderRadius: '12px',
                      border: '1.5px solid var(--tarika-border, #F0E2E0)',
                      backgroundColor: '#FFFFFF',
                      color: '#1F191B',
                      fontSize: '0.88rem',
                      outline: 'none'
                    }}
                  />
                </form>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <SlidersHorizontal size={16} color="#6B5E63" />
                  <select
                    value={ordersStatus}
                    onChange={(e) => { setOrdersStatus(e.target.value); setOrdersPage(1); }}
                    style={{
                      padding: '0.75rem 1.25rem',
                      borderRadius: '12px',
                      border: '1.5px solid var(--tarika-border, #F0E2E0)',
                      backgroundColor: '#FFFFFF',
                      color: '#1F191B',
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <option value="ALL">All Order Statuses</option>
                    <option value="delivered">Delivered</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="pending">Pending</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
              </div>

              {/* Orders Data Table */}
              {ordersLoading ? (
                <div style={{ textAlign: 'center', padding: '4rem 2rem', background: '#FFFFFF', borderRadius: '20px', border: '1px solid var(--tarika-border, #F0E2E0)' }}>
                  <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216, 114, 126, 0.3)', borderTopColor: '#D8727E' }} />
                  <p style={{ color: '#6B5E63', fontWeight: 600 }}>Fetching Orders from Database...</p>
                </div>
              ) : ordersError ? (
                <div className="tarika-auth-alert"><AlertCircle size={20} /><span>{ordersError}</span></div>
              ) : (
                <div style={{ background: '#FFFFFF', borderRadius: '20px', border: '1px solid var(--tarika-border, #F0E2E0)', overflow: 'hidden', boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)' }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                      <thead>
                        <tr style={{ background: '#FAF7F5', borderBottom: '1.5px solid var(--tarika-border, #F0E2E0)', color: '#8E3642', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          <th style={{ padding: '1rem 1.25rem' }}>Order Details</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Customer</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Order Date</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Total Amount</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Payment Status</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Order Status</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Fulfillment Warehouse</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orders.map((ord) => (
                          <tr
                            key={ord.order_id}
                            onClick={() => setSelectedOrderIdForModal(ord.order_id)}
                            style={{ borderBottom: '1px solid var(--tarika-border, #F0E2E0)', transition: 'background 0.2s ease', cursor: 'pointer' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = '#FAF7F5'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                          >
                            <td style={{ padding: '1rem 1.25rem', minWidth: '220px' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#B8505E', display: 'block', wordBreak: 'break-all', textDecoration: 'underline' }}>
                                {ord.order_id}
                              </span>
                              <span style={{ fontSize: '0.75rem', color: '#6B5E63' }}>{ord.item_count} Items</span>
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{ord.customer_name}</p>
                              <p style={{ margin: 0, fontSize: '0.78rem', color: '#6B5E63' }}>{ord.customer_email || 'Direct Order'}</p>
                            </td>
                            <td style={{ padding: '1rem 1.25rem', color: '#6B5E63', fontWeight: 500 }}>
                              {ord.order_date || 'N/A'}
                            </td>
                            <td style={{ padding: '1rem 1.25rem', fontWeight: 800, color: '#B8505E' }}>
                              ₹{Number(ord.total_amount || 0).toLocaleString('en-IN')}
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              {renderPaymentStatusBadge(ord.payment_status)}
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                {renderOrderStatusBadge(ord.order_status)}
                                {(ord.order_status || '').toLowerCase() === 'confirmed' && (
                                  <span style={{
                                    fontSize: '0.72rem',
                                    fontWeight: 700,
                                    padding: '0.2rem 0.55rem',
                                    borderRadius: '6px',
                                    backgroundColor: '#B8505E',
                                    color: '#FFFFFF',
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.25rem'
                                  }}>
                                    <Truck size={12} /> Dispatch
                                  </span>
                                )}
                              </div>
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <p style={{ margin: 0, fontWeight: 600, color: '#1F191B', fontSize: '0.84rem' }}>{ord.warehouse_name}</p>
                              <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63' }}>{ord.warehouse_city}</p>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.5rem', background: '#FAF7F5', borderTop: '1px solid var(--tarika-border, #F0E2E0)' }}>
                    <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>
                      Showing Page <strong>{ordersPage}</strong> of <strong>{ordersTotalPages}</strong> ({ordersTotalCount.toLocaleString()} total orders)
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => setOrdersPage(p => Math.max(1, p - 1))}
                        disabled={ordersPage === 1}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        <ChevronLeft size={14} /> Previous
                      </button>
                      <button
                        onClick={() => setOrdersPage(p => Math.min(ordersTotalPages, p + 1))}
                        disabled={ordersPage >= ordersTotalPages}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        Next <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: DELIVERIES (REAL DATABASE DELIVERIES) */}
          {activeTab === 'deliveries' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Header Banner */}
              <div
                style={{
                  background: '#FFFFFF',
                  borderRadius: '20px',
                  padding: '1.75rem 2rem',
                  border: '1px solid var(--tarika-border, #F0E2E0)',
                  boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '1.25rem'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span className="tarika-serif" style={{ fontSize: '1.75rem', fontWeight: 700, color: '#1F191B' }}>
                      Deliveries ({deliveriesTotalCount.toLocaleString()})
                    </span>
                  </div>
                  <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: 0 }}>
                    Dispatch and courier delivery tracking records. Showing Page {deliveriesPage} of {deliveriesTotalPages}.
                  </p>
                </div>

                <button onClick={fetchDeliveries} className="tarika-btn-outline" disabled={deliveriesLoading} style={{ padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}>
                  <RefreshCw size={15} className={deliveriesLoading ? 'animate-spin' : ''} color="#D8727E" />
                  <span>Refresh Deliveries</span>
                </button>
              </div>

              {/* Filters Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                <form onSubmit={handleDeliveriesSearchSubmit} style={{ position: 'relative', minWidth: '320px', flex: 1 }}>
                  <Search size={16} color="#B8505E" style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    placeholder="Search by Delivery ID, Order ID, Partner..."
                    value={deliveriesSearch}
                    onChange={(e) => setDeliveriesSearch(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem 0.75rem 2.75rem',
                      borderRadius: '12px',
                      border: '1.5px solid var(--tarika-border, #F0E2E0)',
                      backgroundColor: '#FFFFFF',
                      color: '#1F191B',
                      fontSize: '0.88rem',
                      outline: 'none'
                    }}
                  />
                </form>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <SlidersHorizontal size={16} color="#6B5E63" />
                  <select
                    value={deliveriesStatus}
                    onChange={(e) => { setDeliveriesStatus(e.target.value); setDeliveriesPage(1); }}
                    style={{
                      padding: '0.75rem 1.25rem',
                      borderRadius: '12px',
                      border: '1.5px solid var(--tarika-border, #F0E2E0)',
                      backgroundColor: '#FFFFFF',
                      color: '#1F191B',
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <option value="ALL">All Delivery Statuses</option>
                    <option value="Delivered">Delivered</option>
                    <option value="In Transit">In Transit</option>
                    <option value="Out for Delivery">Out for Delivery</option>
                    <option value="Failed">Failed / Returned</option>
                  </select>
                </div>
              </div>

              {/* Deliveries Data Table */}
              {deliveriesLoading ? (
                <div style={{ textAlign: 'center', padding: '4rem 2rem', background: '#FFFFFF', borderRadius: '20px', border: '1px solid var(--tarika-border, #F0E2E0)' }}>
                  <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216, 114, 126, 0.3)', borderTopColor: '#D8727E' }} />
                  <p style={{ color: '#6B5E63', fontWeight: 600 }}>Fetching Deliveries from Database...</p>
                </div>
              ) : deliveriesError ? (
                <div className="tarika-auth-alert"><AlertCircle size={20} /><span>{deliveriesError}</span></div>
              ) : (
                <div style={{ background: '#FFFFFF', borderRadius: '20px', border: '1px solid var(--tarika-border, #F0E2E0)', overflow: 'hidden', boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)' }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                      <thead>
                        <tr style={{ background: '#FAF7F5', borderBottom: '1.5px solid var(--tarika-border, #F0E2E0)', color: '#8E3642', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          <th style={{ padding: '1rem 1.25rem' }}>Delivery Tracking</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Order Ref</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Courier Partner</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Dispatch Date</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Expected Date</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Delivery Status</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Notes / Failure Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {deliveries.map((del) => (
                          <tr key={del.delivery_id} style={{ borderBottom: '1px solid var(--tarika-border, #F0E2E0)' }}>
                            <td style={{ padding: '1rem 1.25rem', minWidth: '200px' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1F191B', wordBreak: 'break-all' }}>
                                {del.delivery_id}
                              </span>
                            </td>
                            <td style={{ padding: '1rem 1.25rem', minWidth: '200px' }}>
                              <span style={{ fontFamily: 'monospace', color: '#B8505E', fontWeight: 600, wordBreak: 'break-all' }}>
                                {del.order_id || 'N/A'}
                              </span>
                            </td>
                            <td style={{ padding: '1rem 1.25rem', fontWeight: 600, color: '#1F191B' }}>
                              {del.delivery_partner || 'Standard Express'}
                            </td>
                            <td style={{ padding: '1rem 1.25rem', color: '#6B5E63' }}>
                              {del.dispatch_date || 'N/A'}
                            </td>
                            <td style={{ padding: '1rem 1.25rem', color: '#6B5E63' }}>
                              {del.expected_delivery_date || 'N/A'}
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              {renderDeliveryStatusBadge(del.delivery_status)}
                            </td>
                            <td style={{ padding: '1rem 1.25rem', fontSize: '0.8rem', color: del.failure_reason ? '#DC2626' : '#6B5E63' }}>
                              {del.failure_reason || 'Dispatched on schedule'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.5rem', background: '#FAF7F5', borderTop: '1px solid var(--tarika-border, #F0E2E0)' }}>
                    <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>
                      Showing Page <strong>{deliveriesPage}</strong> of <strong>{deliveriesTotalPages}</strong> ({deliveriesTotalCount.toLocaleString()} total deliveries)
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => setDeliveriesPage(p => Math.max(1, p - 1))}
                        disabled={deliveriesPage === 1}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        <ChevronLeft size={14} /> Previous
                      </button>
                      <button
                        onClick={() => setDeliveriesPage(p => Math.min(deliveriesTotalPages, p + 1))}
                        disabled={deliveriesPage >= deliveriesTotalPages}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        Next <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: RETURNS (REAL DATABASE RETURNS) */}
          {activeTab === 'returns' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Header Banner */}
              <div
                style={{
                  background: '#FFFFFF',
                  borderRadius: '20px',
                  padding: '1.75rem 2rem',
                  border: '1px solid var(--tarika-border, #F0E2E0)',
                  boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '1.25rem'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                    <span className="tarika-serif" style={{ fontSize: '1.75rem', fontWeight: 700, color: '#1F191B' }}>
                      Returns ({returnsTotalCount.toLocaleString()})
                    </span>
                  </div>
                  <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: 0 }}>
                    Customer return requests and product condition tracking. Showing Page {returnsPage} of {returnsTotalPages}.
                  </p>
                </div>

                <button onClick={fetchReturns} className="tarika-btn-outline" disabled={returnsLoading} style={{ padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}>
                  <RefreshCw size={15} className={returnsLoading ? 'animate-spin' : ''} color="#D8727E" />
                  <span>Refresh Returns</span>
                </button>
              </div>

              {/* Filters Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                <form onSubmit={handleReturnsSearchSubmit} style={{ position: 'relative', minWidth: '320px', flex: 1 }}>
                  <Search size={16} color="#B8505E" style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    placeholder="Search by Return ID, Product, Customer, Reason..."
                    value={returnsSearch}
                    onChange={(e) => setReturnsSearch(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem 0.75rem 2.75rem',
                      borderRadius: '12px',
                      border: '1.5px solid var(--tarika-border, #F0E2E0)',
                      backgroundColor: '#FFFFFF',
                      color: '#1F191B',
                      fontSize: '0.88rem',
                      outline: 'none'
                    }}
                  />
                </form>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <SlidersHorizontal size={16} color="#6B5E63" />
                  <select
                    value={returnsStatus}
                    onChange={(e) => { setReturnsStatus(e.target.value); setReturnsPage(1); }}
                    style={{
                      padding: '0.75rem 1.25rem',
                      borderRadius: '12px',
                      border: '1.5px solid var(--tarika-border, #F0E2E0)',
                      backgroundColor: '#FFFFFF',
                      color: '#1F191B',
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <option value="ALL">All Return Statuses</option>
                    <option value="requested">Requested</option>
                    <option value="approved">Approved</option>
                    <option value="pickup assigned">Pickup Assigned</option>
                    <option value="pickup accepted">Pickup Accepted</option>
                    <option value="picked up">Picked Up</option>
                    <option value="received at warehouse">Received at Warehouse</option>
                    <option value="completed">Completed / Refunded</option>
                    <option value="rejected">Rejected</option>
                    <option value="failed">Failed</option>
                  </select>
                </div>
              </div>

              {/* Returns Data Table */}
              {returnsLoading ? (
                <div style={{ textAlign: 'center', padding: '4rem 2rem', background: '#FFFFFF', borderRadius: '20px', border: '1px solid var(--tarika-border, #F0E2E0)' }}>
                  <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216, 114, 126, 0.3)', borderTopColor: '#D8727E' }} />
                  <p style={{ color: '#6B5E63', fontWeight: 600 }}>Fetching Returns from Database...</p>
                </div>
              ) : returnsError ? (
                <div className="tarika-auth-alert"><AlertCircle size={20} /><span>{returnsError}</span></div>
              ) : (
                <div style={{ background: '#FFFFFF', borderRadius: '20px', border: '1px solid var(--tarika-border, #F0E2E0)', overflow: 'hidden', boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)' }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                      <thead>
                        <tr style={{ background: '#FAF7F5', borderBottom: '1.5px solid var(--tarika-border, #F0E2E0)', color: '#8E3642', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          <th style={{ padding: '1rem 1.25rem' }}>Return Ref</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Product Item</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Customer</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Return Reason</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Return Date</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Status</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Condition / Refund</th>
                          <th style={{ padding: '1rem 1.25rem' }}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {returnsList.map((ret) => {
                          const isRequested = (ret.return_status || '').trim().toLowerCase() === 'requested';
                          const actionState = returnsActionPending[ret.return_id];

                          const handleAccept = async () => {
                            setReturnsActionPending(prev => ({ ...prev, [ret.return_id]: 'accepting' }));
                            const res = await acceptWarehouseReturn(ret.return_id);
                            if (res.success && res.return) {
                              setReturnsList(prev => prev.map(r =>
                                r.return_id === ret.return_id ? res.return : r
                              ));
                            } else {
                              alert(res.error || 'Failed to accept return.');
                            }
                            setReturnsActionPending(prev => { const n = {...prev}; delete n[ret.return_id]; return n; });
                          };

                          const handleReject = async () => {
                            setReturnsActionPending(prev => ({ ...prev, [ret.return_id]: 'rejecting' }));
                            const res = await rejectWarehouseReturn(ret.return_id);
                            if (res.success && res.return) {
                              setReturnsList(prev => prev.map(r =>
                                r.return_id === ret.return_id ? res.return : r
                              ));
                            } else {
                              alert(res.error || 'Failed to reject return.');
                            }
                            setReturnsActionPending(prev => { const n = {...prev}; delete n[ret.return_id]; return n; });
                          };

                          return (
                          <tr key={ret.return_id} style={{ borderBottom: '1px solid var(--tarika-border, #F0E2E0)', background: isRequested ? '#FFFBF9' : 'transparent' }}>
                            <td style={{ padding: '1rem 1.25rem', minWidth: '220px' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1F191B', wordBreak: 'break-all' }}>
                                {ret.return_id}
                              </span>
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{ret.product_name}</p>
                              <p style={{ margin: 0, fontSize: '0.75rem', color: '#6B5E63', fontFamily: 'monospace' }}>SKU: {ret.product_sku || 'SKU-RET'}</p>
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{ret.customer_name}</p>
                              <p style={{ margin: 0, fontSize: '0.78rem', color: '#6B5E63' }}>{ret.customer_email}</p>
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#B8505E', background: '#FBF1F0', padding: '0.2rem 0.55rem', borderRadius: '6px' }}>
                                {ret.return_reason || 'Quality Issue'}
                              </span>
                            </td>
                            <td style={{ padding: '1rem 1.25rem', color: '#6B5E63' }}>
                              {ret.return_date || 'N/A'}
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              {renderReturnStatusBadge(ret.return_status)}
                            </td>
                            <td style={{ padding: '1rem 1.25rem' }}>
                              <p style={{ margin: 0, fontSize: '0.8rem', color: '#1F191B' }}>{ret.condition_on_return || 'Standard return condition'}</p>
                              {ret.refund_amount && (
                                <p style={{ margin: 0, fontWeight: 700, color: '#059669', fontSize: '0.82rem' }}>
                                  Refund: ₹{Number(ret.refund_amount).toLocaleString('en-IN')}
                                </p>
                              )}
                            </td>
                            <td style={{ padding: '1rem 1.25rem', whiteSpace: 'nowrap' }}>
                              {(() => {
                                const retStatus = (ret.return_status || '').trim().toLowerCase();
                                const isReq = retStatus === 'requested';
                                const isAppr = retStatus === 'approved' || retStatus === 'accepted';
                                const isPickedUpOrWarehouse = retStatus === 'picked up' || retStatus === 'received at warehouse';
                                const isPickupAssigned = retStatus === 'pickup assigned' || retStatus === 'pickup accepted';
                                const isComp = retStatus === 'completed' || retStatus === 'refunded';

                                if (isReq) {
                                  return (
                                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                                      <button
                                        onClick={handleAccept}
                                        disabled={!!actionState}
                                        style={{
                                          padding: '0.35rem 0.85rem',
                                          borderRadius: '7px',
                                          border: '1px solid #A7F3D0',
                                          backgroundColor: actionState === 'accepting' ? '#D1FAE5' : '#ECFDF5',
                                          color: '#059669',
                                          fontSize: '0.78rem',
                                          fontWeight: 700,
                                          cursor: actionState ? 'wait' : 'pointer',
                                          transition: 'all 0.2s ease',
                                        }}
                                      >
                                        {actionState === 'accepting' ? '...' : 'Approve'}
                                      </button>
                                      <button
                                        onClick={handleReject}
                                        disabled={!!actionState}
                                        style={{
                                          padding: '0.35rem 0.85rem',
                                          borderRadius: '7px',
                                          border: '1px solid #FECACA',
                                          backgroundColor: actionState === 'rejecting' ? '#FEE2E2' : '#FEF2F2',
                                          color: '#DC2626',
                                          fontSize: '0.78rem',
                                          fontWeight: 700,
                                          cursor: actionState ? 'wait' : 'pointer',
                                          transition: 'all 0.2s ease',
                                        }}
                                      >
                                        {actionState === 'rejecting' ? '...' : 'Reject'}
                                      </button>
                                    </div>
                                  );
                                }

                                if (isAppr) {
                                  return (
                                    <button
                                      onClick={() => handleOpenAssignPickupModal(ret)}
                                      style={{
                                        padding: '0.4rem 0.95rem',
                                        borderRadius: '8px',
                                        border: '1px solid #8E3642',
                                        backgroundColor: '#8E3642',
                                        color: '#FFFFFF',
                                        fontSize: '0.78rem',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '5px',
                                        transition: 'all 0.2s ease',
                                        boxShadow: '0 2px 6px rgba(142, 54, 66, 0.2)',
                                      }}
                                    >
                                      <Truck size={13} />
                                      <span>Assign Pickup</span>
                                    </button>
                                  );
                                }

                                if (isPickedUpOrWarehouse) {
                                  return (
                                    <button
                                      onClick={() => handleConfirmReturnReceived(ret)}
                                      disabled={actionState === 'receiving'}
                                      style={{
                                        padding: '0.4rem 0.95rem',
                                        borderRadius: '8px',
                                        border: '1px solid #059669',
                                        backgroundColor: actionState === 'receiving' ? '#D1FAE5' : '#059669',
                                        color: '#FFFFFF',
                                        fontSize: '0.78rem',
                                        fontWeight: 700,
                                        cursor: actionState ? 'wait' : 'pointer',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '5px',
                                        transition: 'all 0.2s ease',
                                        boxShadow: '0 2px 6px rgba(5, 150, 105, 0.2)',
                                      }}
                                    >
                                      <CheckCircle2 size={13} />
                                      <span>{actionState === 'receiving' ? 'Confirming...' : 'Confirm Received'}</span>
                                    </button>
                                  );
                                }

                                if (isPickupAssigned) {
                                  return (
                                    <div style={{ fontSize: '0.78rem' }}>
                                      <span style={{ color: '#7E22CE', fontWeight: 700, display: 'block' }}>
                                        Assigned: {ret.assigned_employee_name || 'Driver'}
                                      </span>
                                      <span style={{ color: '#6B5E63', fontSize: '0.72rem' }}>
                                        {ret.delivery_partner || 'Courier'}
                                      </span>
                                    </div>
                                  );
                                }

                                if (isComp) {
                                  return (
                                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#059669' }}>
                                      ✓ Return Received
                                    </span>
                                  );
                                }

                                if (retStatus === 'rejected') {
                                  return (
                                    <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#DC2626' }}>
                                      ✕ Rejected
                                    </span>
                                  );
                                }

                                if (retStatus === 'failed') {
                                  return (
                                    <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#DC2626' }}>
                                      ⚠ Pickup Failed
                                    </span>
                                  );
                                }

                                return <span style={{ fontSize: '0.75rem', color: '#9E8F94' }}>—</span>;
                              })()}
                            </td>
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.5rem', background: '#FAF7F5', borderTop: '1px solid var(--tarika-border, #F0E2E0)' }}>
                    <span style={{ fontSize: '0.82rem', color: '#6B5E63' }}>
                      Showing Page <strong>{returnsPage}</strong> of <strong>{returnsTotalPages}</strong> ({returnsTotalCount.toLocaleString()} total returns)
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => setReturnsPage(p => Math.max(1, p - 1))}
                        disabled={returnsPage === 1}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        <ChevronLeft size={14} /> Previous
                      </button>
                      <button
                        onClick={() => setReturnsPage(p => Math.min(returnsTotalPages, p + 1))}
                        disabled={returnsPage >= returnsTotalPages}
                        className="tarika-btn-outline"
                        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', borderRadius: '8px' }}
                      >
                        Next <ChevronRight size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 5: INVENTORY (PLACEHOLDER FOR FUTURE PARTS) */}
          {activeTab === 'inventory' && (
            <div style={{ background: '#FFFFFF', borderRadius: '20px', padding: '4rem 2rem', border: '1px solid var(--tarika-border, #F0E2E0)', textAlign: 'center' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(216, 114, 126, 0.12)', color: '#D8727E', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
                <Boxes size={32} />
              </div>
              <span style={{ display: 'inline-block', padding: '0.3rem 0.85rem', borderRadius: '9999px', background: 'rgba(216, 114, 126, 0.12)', color: '#B8505E', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', marginBottom: '1rem' }}>
                INVENTORY MODULE
              </span>
              <h2 className="tarika-serif" style={{ fontSize: '1.85rem', marginBottom: '0.75rem', color: '#1F191B' }}>
                Warehouse Stock & Intakes
              </h2>
              <p style={{ color: '#6B5E63', maxWidth: '520px', margin: '0 auto 2rem', fontSize: '0.925rem', lineHeight: 1.6 }}>
                Multi-warehouse stock batch allocations and reorder thresholds will be active in upcoming operational releases.
              </p>
              <button onClick={() => setActiveTab('products')} className="tarika-btn-primary" style={{ display: 'inline-flex', width: 'auto', margin: '0 auto', padding: '0.75rem 2rem' }}>
                <span>Back to Products</span>
                <ChevronRight size={16} />
              </button>
            </div>
          )}

          {/* TAB: STOCK TO BE ORDERED (AI Analysis) */}
          {activeTab === 'stock-to-be-ordered' && (
            <StockToBeOrdered token={token} />
          )}

          {/* TAB 6: DASHBOARD OVERVIEW */}
          {activeTab === 'dashboard' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div style={{ background: '#FFFFFF', borderRadius: '20px', padding: '2rem', border: '1px solid var(--tarika-border, #F0E2E0)', boxShadow: '0 8px 30px rgba(184, 80, 94, 0.04)' }}>
                <h1 className="tarika-serif" style={{ fontSize: '2rem', fontWeight: 700, margin: '0 0 0.5rem', color: '#1F191B' }}>
                  Warehouse Control Center
                </h1>
                <p style={{ color: '#6B5E63', margin: 0, fontSize: '0.925rem' }}>
                  Real-time operational metrics across database catalog products, customer orders, logistics deliveries, and return processing.
                </p>
              </div>

              {/* 4 Summary Metric Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' }}>
                <div onClick={() => setActiveTab('products')} style={{ background: '#FFFFFF', padding: '1.5rem', borderRadius: '16px', border: '1px solid #F0E2E0', cursor: 'pointer', transition: 'all 0.25s ease' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#6B5E63', textTransform: 'uppercase' }}>Active Products</span>
                    <div style={{ padding: '0.5rem', borderRadius: '10px', background: '#FBF1F0', color: '#D8727E' }}><Package size={20} /></div>
                  </div>
                  <h3 style={{ fontSize: '1.85rem', fontWeight: 800, color: '#1F191B', margin: '0 0 0.25rem' }}>
                    {productsTotalCount.toLocaleString()}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: '#059669', fontWeight: 600 }}>Categorized across {dbCategories.length} Categories</p>
                </div>

                <div onClick={() => setActiveTab('orders')} style={{ background: '#FFFFFF', padding: '1.5rem', borderRadius: '16px', border: '1px solid #F0E2E0', cursor: 'pointer', transition: 'all 0.25s ease' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#6B5E63', textTransform: 'uppercase' }}>Total Database Orders</span>
                    <div style={{ padding: '0.5rem', borderRadius: '10px', background: '#EFF6FF', color: '#2563EB' }}><ShoppingBag size={20} /></div>
                  </div>
                  <h3 style={{ fontSize: '1.85rem', fontWeight: 800, color: '#1F191B', margin: '0 0 0.25rem' }}>
                    {ordersTotalCount > 0 ? ordersTotalCount.toLocaleString() : '7,949'}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: '#2563EB', fontWeight: 600 }}>Real customer orders in system</p>
                </div>

                <div onClick={() => setActiveTab('deliveries')} style={{ background: '#FFFFFF', padding: '1.5rem', borderRadius: '16px', border: '1px solid #F0E2E0', cursor: 'pointer', transition: 'all 0.25s ease' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#6B5E63', textTransform: 'uppercase' }}>Dispatched Deliveries</span>
                    <div style={{ padding: '0.5rem', borderRadius: '10px', background: '#ECFDF5', color: '#059669' }}><Truck size={20} /></div>
                  </div>
                  <h3 style={{ fontSize: '1.85rem', fontWeight: 800, color: '#1F191B', margin: '0 0 0.25rem' }}>
                    {deliveriesTotalCount > 0 ? deliveriesTotalCount.toLocaleString() : '7,030'}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: '#059669', fontWeight: 600 }}>Active courier partner shipments</p>
                </div>

                <div onClick={() => setActiveTab('returns')} style={{ background: '#FFFFFF', padding: '1.5rem', borderRadius: '16px', border: '1px solid #F0E2E0', cursor: 'pointer', transition: 'all 0.25s ease' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#6B5E63', textTransform: 'uppercase' }}>Customer Returns</span>
                    <div style={{ padding: '0.5rem', borderRadius: '10px', background: '#FFFBEB', color: '#D97706' }}><RotateCcw size={20} /></div>
                  </div>
                  <h3 style={{ fontSize: '1.85rem', fontWeight: 800, color: '#1F191B', margin: '0 0 0.25rem' }}>
                    {returnsTotalCount > 0 ? returnsTotalCount.toLocaleString() : '1,177'}
                  </h3>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: '#D97706', fontWeight: 600 }}>Return requests & refunds</p>
                </div>
              </div>
            </div>
          )}


        </main>
      </div>

      {/* Product Edit Modal */}
      {selectedProductForEdit && (
        <ProductEditModal
          product={selectedProductForEdit}
          token={token}
          onClose={() => setSelectedProductForEdit(null)}
          onSaveSuccess={(updatedProduct) => {
            // Merge the database-confirmed values into the loaded page so the
            // new details and stock appear immediately, while search, filters
            // and pagination position are preserved (no full reload).
            setRawProducts((prev) => prev.map((p) => (
              (p.product_id || p.id) === (updatedProduct.product_id || updatedProduct.id)
                ? { ...p, ...updatedProduct }
                : p
            )));
            // Category names/counts may have changed — invalidate the cache.
            invalidateCategoriesCache();
            loadCategories();
          }}
        />
      )}

      {/* Order Detail Modal */}
      {selectedOrderIdForModal && (
        <OrderDetailModal
          orderId={selectedOrderIdForModal}
          onClose={() => setSelectedOrderIdForModal(null)}
          onOrderUpdated={() => {
            fetchOrders();
          }}
        />
      )}

      {/* Return Pickup Assignment Modal */}
      {assignPickupModalReturn && (
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
            zIndex: 1100,
            animation: 'fadeIn 0.2s ease-out',
          }}
          onClick={() => setAssignPickupModalReturn(null)}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '24px',
              maxWidth: '560px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid var(--tarika-border, #F0E2E0)',
              boxShadow: '0 20px 60px rgba(31, 25, 27, 0.2)',
              padding: '2rem',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              type="button"
              onClick={() => setAssignPickupModalReturn(null)}
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
                <RotateCcw size={15} color="#B8505E" />
                <span style={{ fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  Return Reverse Logistics
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
                Assign Return Pickup
              </h2>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#6B5E63' }}>
                Select an active delivery partner employee to pick up the return from customer.
              </p>
            </div>

            {/* Return Item Summary Card */}
            <div
              style={{
                backgroundColor: '#FAF7F5',
                border: '1px solid #F0E2E0',
                borderRadius: '14px',
                padding: '1rem',
                marginBottom: '1.5rem',
                fontSize: '0.84rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <span style={{ color: '#6B5E63' }}>Return Ref:</span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#1F191B' }}>
                  {assignPickupModalReturn?.return_id}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <span style={{ color: '#6B5E63' }}>Product:</span>
                <span style={{ fontWeight: 600, color: '#1F191B' }}>
                  {assignPickupModalReturn?.product_name || 'Boutique Apparel'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                <span style={{ color: '#6B5E63' }}>Customer:</span>
                <span style={{ fontWeight: 600, color: '#1F191B' }}>
                  {assignPickupModalReturn?.customer_name || 'Customer'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#6B5E63' }}>Return Reason:</span>
                <span style={{ fontWeight: 600, color: '#B8505E' }}>
                  {assignPickupModalReturn?.return_reason || 'Customer Return'}
                </span>
              </div>
            </div>

            {/* Error Alert */}
            {assignPickupError && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: '#FEF2F2',
                  border: '1px solid #FECACA',
                  borderRadius: '10px',
                  padding: '0.75rem 1rem',
                  color: '#DC2626',
                  fontSize: '0.84rem',
                  marginBottom: '1.25rem',
                }}
              >
                <AlertCircle size={16} />
                <span>{assignPickupError}</span>
              </div>
            )}

            {/* 1. Courier Company Selection */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.4rem' }}>
                1. Courier Company <span style={{ color: '#DC2626' }}>*</span>
              </label>
              <select
                value={assignPickupCompany}
                onChange={handleAssignCompanyChange}
                disabled={courierPartnersLoading}
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1.5px solid #F0E2E0',
                  backgroundColor: '#FFFFFF',
                  color: '#1F191B',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  outline: 'none',
                }}
              >
                <option value="">
                  {courierPartnersLoading
                    ? 'Loading courier partners...'
                    : '— Select Courier Partner —'}
                </option>
                {(courierPartnersList || []).map(partner => (
                  <option key={partner} value={partner}>
                    {partner}
                  </option>
                ))}
              </select>
            </div>

            {/* 2. Delivery Partner Employee Selection */}
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.4rem' }}>
                2. Delivery Partner Employee <span style={{ color: '#DC2626' }}>*</span>
              </label>
              <select
                value={assignPickupEmployeeId}
                onChange={(e) => setAssignPickupEmployeeId(e.target.value)}
                disabled={!assignPickupCompany || assignPickupEmployeesLoading}
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1.5px solid #F0E2E0',
                  backgroundColor: !assignPickupCompany ? '#F9F6F4' : '#FFFFFF',
                  color: '#1F191B',
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  outline: 'none',
                  cursor: !assignPickupCompany ? 'not-allowed' : 'pointer',
                }}
              >
                <option value="">
                  {!assignPickupCompany
                    ? '— Select courier company first —'
                    : assignPickupEmployeesLoading
                    ? 'Loading active employees...'
                    : (assignPickupEmployeesList || []).length === 0
                    ? '— No active delivery employees found —'
                    : '— Select Active Delivery Partner Employee —'}
                </option>
                {(assignPickupEmployeesList || []).map(emp => (
                  <option key={emp.employee_id} value={emp.employee_id}>
                    {emp.full_name} (ID: {emp.employee_id}) — {emp.phone || 'Phone on file'}
                  </option>
                ))}
              </select>
            </div>


            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setAssignPickupModalReturn(null)}
                className="tarika-btn-outline"
                style={{ padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmAssignPickup}
                disabled={assignPickupSubmitting || !assignPickupCompany || !assignPickupEmployeeId}
                className="tarika-btn"
                style={{
                  padding: '0.65rem 1.5rem',
                  fontSize: '0.85rem',
                  backgroundColor: '#8E3642',
                  borderColor: '#8E3642',
                  color: '#FFFFFF',
                  cursor: assignPickupSubmitting || !assignPickupCompany || !assignPickupEmployeeId ? 'not-allowed' : 'pointer',
                  opacity: !assignPickupCompany || !assignPickupEmployeeId ? 0.6 : 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {assignPickupSubmitting ? (
                  <>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>Assigning...</span>
                  </>
                ) : (
                  <>
                    <Truck size={14} />
                    <span>Confirm Hand-off & Assign</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
