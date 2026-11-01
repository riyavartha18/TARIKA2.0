import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShoppingBag,
  ArrowLeft,
  MapPin,
  CreditCard,
  Banknote,
  Lock,
  Truck,
  ShieldCheck,
  ChevronRight,
  AlertCircle,
  Sparkles,
  CheckCircle2,
  Loader2,
  Gift,
  ChevronDown,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { useCustomer } from '../../context/CustomerContext';
import CheckoutOfferCard from '../../components/customer/CheckoutOfferCard';
import { offerDisplayName } from '../../utils/offerNames';
import { createOrder, validateCheckoutCoupon } from '../../services/api';

export default function CheckoutPage() {
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const {
    bagItems,
    subtotal,
    total,
    bagLoading,
    addToast,
    clearCartLocal,
    refreshOffers,
    offers,
    offersLoading,
  } = useCustomer();

  // Form State
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [shippingAddress, setShippingAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('COD'); // 'COD' or 'ONLINE'

  // Coupon. The discount is validated and recomputed on the backend; the
  // frontend never decides the amount, it only reflects what the server returns.
  const [couponInput, setCouponInput] = useState('');
  const [appliedCoupon, setAppliedCoupon] = useState(null); // { code, name, discount, payable }
  const [couponMsg, setCouponMsg] = useState('');
  const [couponType, setCouponType] = useState(''); // 'success' | 'error'
  const [applyingCode, setApplyingCode] = useState(''); // code currently being validated
  // The offers list stays collapsed by default so the checkout summary keeps
  // reading cleanly; one row shows what is available (and what was applied).
  const [offersOpen, setOffersOpen] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    document.title = 'Checkout — TARIKA Luxury';
    if (user) {
      if (user.full_name) setFullName(user.full_name);
      else if (user.name) setFullName(user.name);
      if (user.phone) setPhone(user.phone);
      if (user.city) setCity(user.city);
      if (user.state) setState(user.state);
      if (user.postal_code) setPostalCode(user.postal_code);
      if (user.shipping_address) setShippingAddress(user.shipping_address);
      else if (user.address) setShippingAddress(user.address);
    }
  }, [user]);

  // Applies one code. Every amount comes back from the server, which rebuilds
  // the cart from the customer's own stored cart rows and re-checks the segment,
  // validity dates, minimum order and the one-use-per-customer rule.
  const applyCode = async (rawCode) => {
    const code = String(rawCode || '').trim().toUpperCase();
    setCouponMsg('');
    if (!code) {
      setCouponType('error');
      setCouponMsg('Enter a coupon code first.');
      return;
    }
    setApplyingCode(code);
    const res = await validateCheckoutCoupon(token, code, subtotal);
    setApplyingCode('');
    if (res.success && res.valid) {
      // The campaign name comes from the same offer list Your Offers shows, so
      // the summary names the applied offer instead of only its code.
      const offer = (offers || []).find(
        (item) => String(item.coupon_code).toUpperCase() === code,
      );
      setAppliedCoupon({
        code: res.coupon_code,
        name: offer ? offerDisplayName(offer.name) : res.offer_summary,
        discount: res.discount, payable: res.payable,
        // Extra benefits computed by the backend (Buy & Get / combined offers).
        cashback: res.cashback, freeShipping: res.free_shipping,
        gift: res.gift, summary: res.offer_summary,
      });
      setCouponInput(code);
      setCouponType('success');
      const savedPart = Number(res.discount) > 0
        ? `you saved \u20B9${Number(res.discount).toLocaleString('en-IN')}`
        : (res.offer_summary || 'benefit applied');
      setCouponMsg(`Applied successfully \u2014 ${savedPart}.`);
    } else {
      setAppliedCoupon(null);
      setCouponType('error');
      setCouponMsg(res.error || 'Coupon is not valid for this order.');
    }
  };

  const removeAppliedCoupon = () => {
    setAppliedCoupon(null);
    setCouponInput('');
    setCouponMsg('');
    setCouponType('');
  };

  // The same server-decided campaign list Your Offers, Customer Home and Member
  // Privileges render - no extra request, no duplicate campaign records. Used
  // and Expired entries stay listed with their badge, and the card disables
  // their Apply button exactly as the backend refuses them.
  const checkoutOffers = useMemo(() => offers || [], [offers]);
  const availableOfferCount = useMemo(
    () => checkoutOffers.filter((offer) => (offer.status || 'AVAILABLE') === 'AVAILABLE').length,
    [checkoutOffers],
  );
  // Generous measured height for the collapse animation: each card plus the
  // manual-code row and the message line.
  const offersPanelHeight = Math.max(260, checkoutOffers.length * 205 + 210);

  const handleSubmitOrder = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!shippingAddress.trim() || shippingAddress.trim().length < 5) {
      setFormError('Please enter a valid delivery address (at least 5 characters).');
      return;
    }

    if (!city.trim()) {
      setFormError('Please specify your city.');
      return;
    }

    if (!postalCode.trim()) {
      setFormError('Please specify your PIN / postal code.');
      return;
    }

    setSubmitting(true);

    try {
      const payload = {
        shipping_address: shippingAddress.trim(),
        city: city.trim(),
        state: state.trim(),
        postal_code: postalCode.trim(),
        payment_method: paymentMethod, // 'COD' or 'ONLINE'
        // Only a server-validated coupon is sent; the backend re-checks it
        // against the live cart total before applying any discount.
        coupon_code: appliedCoupon ? appliedCoupon.code : '',
      };

      const res = await createOrder(token, payload);

      if (res.success && res.order) {
        // The checkout transaction already removed the ordered rows from the
        // Neon cart, so empty the bag locally instead of refetching it.
        if (clearCartLocal) {
          clearCartLocal();
        }
        // The coupon was booked server-side as part of this confirmed order, so
        // My Profile / Member Privileges must show it as Used right away.
        if (appliedCoupon && refreshOffers) {
          refreshOffers();
        }
        if (addToast) {
          addToast('Your order has been placed successfully!', 'success');
        }
        navigate(`/customer/order-confirmation/${res.order.order_id}`, {
          state: { order: res.order },
          replace: true,
        });
      } else {
        const errMsg = res.error || 'Failed to place your order. Please check item availability.';
        setFormError(errMsg);
        if (addToast) {
          addToast(errMsg, 'error');
        }
      }
    } catch (err) {
      const errMsg = 'An unexpected error occurred during checkout. Please try again.';
      setFormError(errMsg);
      if (addToast) {
        addToast(errMsg, 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ paddingBottom: '4rem', maxWidth: '1440px', margin: '0 auto' }}>
      <style>{`
        @media (max-width: 960px) {
          .checkout-page-grid {
            grid-template-columns: 1fr !important;
          }
        }
        .tarika-input:focus {
          border-color: #B8505E !important;
          outline: none;
          box-shadow: 0 0 0 3px rgba(184, 80, 94, 0.12);
        }
        /* Offers & Coupons accordion */
        .checkout-offers-panel {
          overflow: hidden;
          transition: max-height 0.32s ease, opacity 0.24s ease;
        }
        .checkout-offers-chevron svg {
          transition: transform 0.25s ease;
        }
        .checkout-offers-chevron.open svg {
          transform: rotate(180deg);
        }
        .checkout-offers-toggle:hover {
          color: #B8505E;
        }
        @media (prefers-reduced-motion: reduce) {
          .checkout-offers-panel,
          .checkout-offers-chevron svg {
            transition: none;
          }
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
          to="/customer/bag"
          style={{
            color: '#8E3642',
            textDecoration: 'none',
            fontWeight: 600,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <ShoppingBag size={14} />
          <span>Shopping Bag</span>
        </Link>
        <ChevronRight size={14} />
        <span style={{ color: '#1F191B', fontWeight: 700 }}>Checkout</span>
      </nav>

      {/* Page Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: '1rem',
          marginBottom: '2rem',
          borderBottom: '1px solid rgba(216, 114, 126, 0.2)',
          paddingBottom: '1.25rem',
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
              Atelier Order Desk
            </span>
          </div>
          <h1
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '2.4rem',
              fontWeight: 700,
              color: '#1F191B',
              margin: 0,
              letterSpacing: '-0.01em',
            }}
          >
            Checkout
          </h1>
        </div>

        <Link
          to="/customer/bag"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: '#6B5E63',
            fontSize: '0.88rem',
            textDecoration: 'none',
            fontWeight: 600,
            padding: '0.4rem 0.8rem',
            borderRadius: '9999px',
            backgroundColor: '#FFFFFF',
            border: '1px solid rgba(216, 114, 126, 0.2)',
            transition: 'all 0.2s ease',
          }}
        >
          <ArrowLeft size={16} />
          <span>Return to Bag</span>
        </Link>
      </div>

      {bagLoading ? (
        <div style={{ padding: '4rem', textAlign: 'center', color: '#B8505E' }}>
          <Loader2 size={32} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
          <p style={{ marginTop: '1rem', fontWeight: 600 }}>Loading checkout details...</p>
        </div>
      ) : bagItems.length === 0 ? (
        /* Empty Cart State */
        <div
          style={{
            padding: '4.5rem 2rem',
            textAlign: 'center',
            backgroundColor: '#FFFFFF',
            borderRadius: '24px',
            border: '1px solid #F0E2E0',
            maxWidth: '540px',
            margin: '2rem auto',
            boxShadow: '0 8px 30px rgba(184, 80, 94, 0.05)',
          }}
        >
          <div
            style={{
              width: '68px',
              height: '68px',
              borderRadius: '50%',
              backgroundColor: '#FBF1F0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.25rem auto',
            }}
          >
            <ShoppingBag size={30} color="#B8505E" />
          </div>
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.65rem',
              fontWeight: 700,
              color: '#1F191B',
              marginBottom: '0.5rem',
            }}
          >
            Your Shopping Bag is Empty
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.94rem', marginBottom: '1.75rem', lineHeight: 1.5 }}>
            You don't have any pieces reserved in your bag to checkout. Explore our latest arrivals to build your wardrobe.
          </p>
          <Link
            to="/customer/shop"
            className="tarika-btn-primary"
            style={{ textDecoration: 'none', display: 'inline-flex', padding: '0.85rem 1.75rem' }}
          >
            <span>Explore Collections</span>
          </Link>
        </div>
      ) : (
        /* Main Checkout 2-Column Grid */
        <form onSubmit={handleSubmitOrder}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1.7fr) minmax(0, 1.15fr)',
              gap: '2.5rem',
              alignItems: 'start',
            }}
            className="checkout-page-grid"
          >
            {/* LEFT COLUMN: Delivery Address & Payment Method */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {/* Form Validation Error Banner */}
              {formError && (
                <div
                  style={{
                    backgroundColor: '#FEF2F2',
                    border: '1px solid #FCA5A5',
                    borderRadius: '16px',
                    padding: '1rem 1.25rem',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                  }}
                >
                  <AlertCircle size={20} color="#DC2626" style={{ flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <strong style={{ fontSize: '0.88rem', color: '#991B1B', display: 'block' }}>
                      Order Validation Notice
                    </strong>
                    <p style={{ margin: '2px 0 0 0', fontSize: '0.84rem', color: '#B91C1C', lineHeight: 1.5 }}>
                      {formError}
                    </p>
                  </div>
                </div>
              )}

              {/* SECTION 1: Delivery Address */}
              <section
                aria-label="Delivery Address"
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '24px',
                  border: '1px solid rgba(240, 226, 224, 0.95)',
                  boxShadow: '0 6px 24px rgba(184, 80, 94, 0.05)',
                  padding: '2rem',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '1.5rem',
                    borderBottom: '1px solid #FAF0EE',
                    paddingBottom: '1rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        backgroundColor: '#FBF1F0',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <MapPin size={20} color="#B8505E" />
                    </div>
                    <div>
                      <h2
                        style={{
                          fontFamily: "'Playfair Display', serif",
                          fontSize: '1.3rem',
                          fontWeight: 700,
                          margin: 0,
                          color: '#1F191B',
                        }}
                      >
                        Delivery Address
                      </h2>
                      <span style={{ fontSize: '0.78rem', color: '#9E8F94' }}>
                        Where should we dispatch your luxury wardrobe?
                      </span>
                    </div>
                  </div>

                  <span
                    style={{
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      backgroundColor: '#FBF1F0',
                      color: '#8E3642',
                      padding: '4px 10px',
                      borderRadius: '9999px',
                      border: '1px solid rgba(216, 114, 126, 0.2)',
                    }}
                  >
                    Step 1 of 2
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {/* Full Name & Phone */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#382E32', marginBottom: '6px' }}>
                        Recipient Full Name
                      </label>
                      <input
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="e.g. Tarika Singhania"
                        className="tarika-input"
                        style={{
                          width: '100%',
                          padding: '0.85rem 1rem',
                          borderRadius: '12px',
                          border: '1.5px solid #F0E2E0',
                          backgroundColor: '#FAF7F5',
                          color: '#1F191B',
                          fontSize: '0.9rem',
                          boxSizing: 'border-box',
                          transition: 'all 0.2s',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#382E32', marginBottom: '6px' }}>
                        Phone Number
                      </label>
                      <input
                        type="text"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="+91 98765 43210"
                        className="tarika-input"
                        style={{
                          width: '100%',
                          padding: '0.85rem 1rem',
                          borderRadius: '12px',
                          border: '1.5px solid #F0E2E0',
                          backgroundColor: '#FAF7F5',
                          color: '#1F191B',
                          fontSize: '0.9rem',
                          boxSizing: 'border-box',
                          transition: 'all 0.2s',
                        }}
                      />
                    </div>
                  </div>

                  {/* Street Address */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#382E32', marginBottom: '6px' }}>
                      Flat / House No. / Building / Street Address <span style={{ color: '#B8505E' }}>*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={shippingAddress}
                      onChange={(e) => setShippingAddress(e.target.value)}
                      placeholder="e.g. 14B, Royal Heritage Mansions, South Avenue"
                      className="tarika-input"
                      style={{
                        width: '100%',
                        padding: '0.85rem 1rem',
                        borderRadius: '12px',
                        border: '1.5px solid #F0E2E0',
                        backgroundColor: '#FAF7F5',
                        color: '#1F191B',
                        fontSize: '0.9rem',
                        boxSizing: 'border-box',
                        transition: 'all 0.2s',
                      }}
                    />
                  </div>

                  {/* City, State & PIN */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: '1.25rem' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#382E32', marginBottom: '6px' }}>
                        City <span style={{ color: '#B8505E' }}>*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        placeholder="e.g. Mumbai"
                        className="tarika-input"
                        style={{
                          width: '100%',
                          padding: '0.85rem 1rem',
                          borderRadius: '12px',
                          border: '1.5px solid #F0E2E0',
                          backgroundColor: '#FAF7F5',
                          color: '#1F191B',
                          fontSize: '0.9rem',
                          boxSizing: 'border-box',
                          transition: 'all 0.2s',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#382E32', marginBottom: '6px' }}>
                        State
                      </label>
                      <input
                        type="text"
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                        placeholder="e.g. Maharashtra"
                        className="tarika-input"
                        style={{
                          width: '100%',
                          padding: '0.85rem 1rem',
                          borderRadius: '12px',
                          border: '1.5px solid #F0E2E0',
                          backgroundColor: '#FAF7F5',
                          color: '#1F191B',
                          fontSize: '0.9rem',
                          boxSizing: 'border-box',
                          transition: 'all 0.2s',
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#382E32', marginBottom: '6px' }}>
                        PIN Code <span style={{ color: '#B8505E' }}>*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        placeholder="e.g. 400001"
                        className="tarika-input"
                        style={{
                          width: '100%',
                          padding: '0.85rem 1rem',
                          borderRadius: '12px',
                          border: '1.5px solid #F0E2E0',
                          backgroundColor: '#FAF7F5',
                          color: '#1F191B',
                          fontSize: '0.9rem',
                          boxSizing: 'border-box',
                          transition: 'all 0.2s',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </section>

              {/* SECTION 2: Payment Method */}
              <section
                aria-label="Payment Method"
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '24px',
                  border: '1px solid rgba(240, 226, 224, 0.95)',
                  boxShadow: '0 6px 24px rgba(184, 80, 94, 0.05)',
                  padding: '2rem',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '1.5rem',
                    borderBottom: '1px solid #FAF0EE',
                    paddingBottom: '1rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        backgroundColor: '#FBF1F0',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <CreditCard size={20} color="#B8505E" />
                    </div>
                    <div>
                      <h2
                        style={{
                          fontFamily: "'Playfair Display', serif",
                          fontSize: '1.3rem',
                          fontWeight: 700,
                          margin: 0,
                          color: '#1F191B',
                        }}
                      >
                        Payment Method
                      </h2>
                      <span style={{ fontSize: '0.78rem', color: '#9E8F94' }}>
                        Select your preferred payment channel
                      </span>
                    </div>
                  </div>

                  <span
                    style={{
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      backgroundColor: '#FBF1F0',
                      color: '#8E3642',
                      padding: '4px 10px',
                      borderRadius: '9999px',
                      border: '1px solid rgba(216, 114, 126, 0.2)',
                    }}
                  >
                    Step 2 of 2
                  </span>
                </div>

                {/* Payment Option Cards */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {/* Cash on Delivery option */}
                  <label
                    htmlFor="payment-cod"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1.25rem',
                      padding: '1.25rem',
                      borderRadius: '16px',
                      border: paymentMethod === 'COD' ? '2px solid #B8505E' : '1px solid #E5D7D5',
                      backgroundColor: paymentMethod === 'COD' ? '#FAF3F2' : '#FFFFFF',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <input
                      type="radio"
                      name="paymentMethod"
                      id="payment-cod"
                      value="COD"
                      checked={paymentMethod === 'COD'}
                      onChange={() => setPaymentMethod('COD')}
                      style={{ accentColor: '#B8505E', transform: 'scale(1.2)', cursor: 'pointer' }}
                    />
                    <div
                      style={{
                        width: '42px',
                        height: '42px',
                        borderRadius: '12px',
                        backgroundColor: '#FFFFFF',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '1px solid #F0E2E0',
                        flexShrink: 0,
                      }}
                    >
                      <Banknote size={22} color="#166534" />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.98rem', fontWeight: 700, color: '#1F191B' }}>
                          Cash on Delivery
                        </span>
                        <span
                          style={{
                            backgroundColor: '#DCFCE7',
                            color: '#166534',
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '9999px',
                          }}
                        >
                          Popular
                        </span>
                      </div>
                      <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: '#6B5E63' }}>
                        Pay comfortably at doorstep via cash or digital UPI / QR code upon delivery.
                      </p>
                    </div>
                  </label>

                  {/* UPI / Online Payment option (Disabled - Launching Soon) */}
                  <div
                    onClick={() => {
                      if (addToast) {
                        addToast(
                          'Online payment is launching soon. Please choose Cash on Delivery to place your order.',
                          'info',
                          4500
                        );
                      }
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1.25rem',
                      padding: '1.25rem',
                      borderRadius: '16px',
                      border: '1px dashed #D1C5C7',
                      backgroundColor: '#FAF7F5',
                      cursor: 'not-allowed',
                      opacity: 0.72,
                      transition: 'all 0.2s ease',
                      position: 'relative',
                    }}
                  >
                    <input
                      type="radio"
                      name="paymentMethod"
                      id="payment-online"
                      value="ONLINE"
                      disabled
                      checked={false}
                      readOnly
                      style={{ accentColor: '#B8505E', transform: 'scale(1.2)', cursor: 'not-allowed' }}
                    />
                    <div
                      style={{
                        width: '42px',
                        height: '42px',
                        borderRadius: '12px',
                        backgroundColor: '#FFFFFF',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '1px solid #EAD4D7',
                        flexShrink: 0,
                      }}
                    >
                      <CreditCard size={22} color="#9E8F94" />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.98rem', fontWeight: 600, color: '#6B5E63' }}>
                          UPI / Online Payment
                        </span>
                        <span
                          style={{
                            backgroundColor: '#FCE7F3',
                            color: '#9D174D',
                            fontSize: '0.68rem',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '9999px',
                            border: '1px solid rgba(157, 23, 77, 0.2)',
                            letterSpacing: '0.04em',
                          }}
                        >
                          Launching Soon
                        </span>
                      </div>
                      <p style={{ margin: '3px 0 0 0', fontSize: '0.8rem', color: '#9E8F94' }}>
                        Online payment will be enabled soon. Please choose Cash on Delivery for now.
                      </p>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            {/* RIGHT COLUMN: Order Summary Sidebar */}
            <aside
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '24px',
                border: '1px solid rgba(240, 226, 224, 0.95)',
                boxShadow: '0 8px 30px rgba(184, 80, 94, 0.06)',
                padding: '2rem',
                position: 'sticky',
                top: '2rem',
              }}
            >
              <h2
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.35rem',
                  fontWeight: 700,
                  margin: '0 0 1.25rem 0',
                  color: '#1F191B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span>Order Summary</span>
                <span
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    color: '#8E3642',
                    backgroundColor: '#FAF3F2',
                    padding: '2px 10px',
                    borderRadius: '9999px',
                  }}
                >
                  {bagItems.length} {bagItems.length === 1 ? 'item' : 'items'}
                </span>
              </h2>

              {/* Items List in Bag */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  maxHeight: '280px',
                  overflowY: 'auto',
                  marginBottom: '1.5rem',
                  paddingRight: '4px',
                }}
              >
                {bagItems.map((item) => {
                  const unitPrice = Number(item.product?.selling_price || item.selling_price || 0);
                  const lineTotal = unitPrice * (item.quantity || 1);
                  const imageUrl =
                    item.product?.primary_image ||
                    item.primary_image ||
                    'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=300&q=80';

                  return (
                    <div
                      key={item.id || item.product_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '10px 12px',
                        borderRadius: '14px',
                        backgroundColor: '#FAF7F5',
                        border: '1px solid rgba(240, 226, 224, 0.8)',
                      }}
                    >
                      {/* Product Image */}
                      <div
                        style={{
                          width: '52px',
                          height: '66px',
                          borderRadius: '10px',
                          overflow: 'hidden',
                          flexShrink: 0,
                          backgroundColor: '#FFFFFF',
                        }}
                      >
                        <img
                          src={imageUrl}
                          alt={item.product?.product_name || item.product_name || 'Product'}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      </div>

                      {/* Product Name, Quantity & Unit Price */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3
                          style={{
                            margin: 0,
                            fontSize: '0.86rem',
                            fontWeight: 600,
                            color: '#1F191B',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {item.product?.product_name || item.product_name}
                        </h3>
                        <p style={{ margin: '3px 0 0 0', fontSize: '0.78rem', color: '#6B5E63' }}>
                          Qty: <strong>{item.quantity}</strong> × ₹{unitPrice.toLocaleString('en-IN')}
                        </p>
                      </div>

                      {/* Line Price */}
                      <span
                        style={{
                          fontSize: '0.92rem',
                          fontWeight: 700,
                          color: '#B8505E',
                          fontFamily: "'Plus Jakarta Sans', sans-serif",
                        }}
                      >
                        ₹{lineTotal.toLocaleString('en-IN')}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Calculations Breakdown */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  marginBottom: '1.5rem',
                  borderTop: '1px solid #F0E2E0',
                  paddingTop: '1rem',
                }}
              >
                {/* Offers & Coupons - an accordion over the customer's own
                    eligible campaigns: the exact same list Your Offers, Customer
                    Home and Member Privileges render, from the same one
                    server-decided service. Collapsed by default so the summary
                    panel stays uncluttered. */}
                <div
                  style={{
                    border: '1px solid rgba(216,114,126,0.22)',
                    borderRadius: 14,
                    background: '#FFFFFF',
                    padding: '0.7rem 0.85rem',
                  }}
                >
                  <button
                    type="button"
                    className="checkout-offers-toggle"
                    aria-expanded={offersOpen}
                    aria-controls="checkout-offers-panel"
                    onClick={() => setOffersOpen((open) => !open)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between', gap: 10,
                      background: 'none', border: 'none', padding: 0,
                      cursor: 'pointer', textAlign: 'left', color: '#1F191B',
                      fontFamily: 'inherit',
                    }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                      <span
                        style={{
                          flexShrink: 0, width: 30, height: 30, borderRadius: 9,
                          background: 'rgba(216,114,126,0.12)',
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        }}
                      >
                        <Gift size={16} color="#B8505E" />
                      </span>
                      <span style={{ minWidth: 0 }}>
                        <span style={{ display: 'block', fontSize: '0.86rem', fontWeight: 800, lineHeight: 1.25 }}>
                          Offers &amp; Coupons
                        </span>
                        <span
                          style={{
                            display: 'block', fontSize: '0.72rem', color: '#6B5E63',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}
                        >
                          {appliedCoupon
                            ? `Applied: ${appliedCoupon.name || appliedCoupon.code} — you saved ₹${Number(appliedCoupon.discount).toLocaleString('en-IN')}`
                            : availableOfferCount
                              ? `${availableOfferCount} offer${availableOfferCount === 1 ? '' : 's'} available for your account`
                              : 'Offers available for your account'}
                        </span>
                      </span>
                    </span>
                    <span
                      className={offersOpen ? 'checkout-offers-chevron open' : 'checkout-offers-chevron'}
                      style={{
                        flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 5,
                        border: '1px solid rgba(184,80,94,0.35)', borderRadius: 9999,
                        padding: '4px 10px', fontSize: '0.72rem', fontWeight: 700,
                        color: '#B8505E', background: '#FFFFFF', whiteSpace: 'nowrap',
                      }}
                    >
                      <span>{offersOpen ? 'Hide Offers' : 'View Available Offers'}</span>
                      <ChevronDown size={13} />
                    </span>
                  </button>

                  <div
                    id="checkout-offers-panel"
                    className="checkout-offers-panel"
                    style={{
                      maxHeight: offersOpen ? `${offersPanelHeight}px` : 0,
                      opacity: offersOpen ? 1 : 0,
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: '0.7rem' }}>
                      {checkoutOffers.length > 0 ? (
                        checkoutOffers.map((offer) => (
                          <CheckoutOfferCard
                            key={offer.campaign_id}
                            offer={offer}
                            applied={!!appliedCoupon && appliedCoupon.code === offer.coupon_code}
                            applying={applyingCode === offer.coupon_code}
                            onApply={applyCode}
                            onRemove={removeAppliedCoupon}
                          />
                        ))
                      ) : (
                        <p style={{ margin: 0, fontSize: '0.76rem', color: '#9E8F94' }}>
                          {offersLoading
                            ? 'Loading your offers…'
                            : 'No personalized offers are active on your account right now. You can still try a coupon code below.'}
                        </p>
                      )}

                      {/* Manual code entry, for any other valid campaign code. */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 2 }}>
                        <label style={{ fontSize: '0.76rem', fontWeight: 700, color: '#1F191B' }}>
                          Have another coupon code?
                        </label>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <input
                            value={couponInput}
                            onChange={(e) => setCouponInput(e.target.value.toUpperCase())}
                            placeholder="Enter coupon code"
                            style={{
                              flex: 1, minWidth: 0, border: '1px solid #F0E2E0', borderRadius: 9,
                              padding: '0.5rem 0.65rem', fontSize: '0.85rem', letterSpacing: '0.04em',
                            }}
                          />
                          {appliedCoupon ? (
                            <button
                              type="button"
                              onClick={removeAppliedCoupon}
                              style={{ border: '1px solid #F0E2E0', background: '#fff', borderRadius: 9, padding: '0 0.8rem', cursor: 'pointer', fontSize: '0.78rem', color: '#6B5E63', whiteSpace: 'nowrap' }}
                            >
                              Remove
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => applyCode(couponInput)}
                              disabled={!!applyingCode}
                              style={{ border: 'none', background: '#B8505E', color: '#fff', borderRadius: 9, padding: '0 1rem', cursor: applyingCode ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.82rem', opacity: applyingCode ? 0.6 : 1, whiteSpace: 'nowrap' }}
                            >
                              {applyingCode ? 'Checking…' : 'Apply'}
                            </button>
                          )}
                        </div>
                      </div>

                      {couponMsg && (
                        <span
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 6,
                            fontSize: '0.76rem', fontWeight: 600,
                            color: couponType === 'success' ? '#15803D' : '#B3261E',
                            background: couponType === 'success' ? 'rgba(21,128,61,0.08)' : 'rgba(179,38,30,0.07)',
                            borderRadius: 8, padding: '6px 9px',
                          }}
                        >
                          {couponType === 'success' && <CheckCircle2 size={14} />}
                          {couponMsg}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Subtotal */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
                  <span>Subtotal</span>
                  <span style={{ fontWeight: 600, color: '#1F191B' }}>
                    ₹{Number(subtotal).toLocaleString('en-IN')}
                  </span>
                </div>

                {/* Delivery: Free */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
                  <span>Delivery</span>
                  <span style={{ fontWeight: 700, color: '#16A34A' }}>Free</span>
                </div>

                {/* Which campaign is applied - named, not just a code. */}
                {appliedCoupon && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: '0.9rem', color: '#6B5E63' }}>
                    <span>Applied Offer</span>
                    <span style={{ fontWeight: 700, color: '#B8505E', textAlign: 'right' }}>
                      {appliedCoupon.name || appliedCoupon.code}
                    </span>
                  </div>
                )}

                {/* Coupon discount (server-computed) */}
                {appliedCoupon && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: '#6B5E63' }}>
                    <span>Discount ({appliedCoupon.code})</span>
                    <span style={{ fontWeight: 700, color: '#16A34A' }}>
                      −₹{Number(appliedCoupon.discount).toLocaleString('en-IN')}
                    </span>
                  </div>
                )}

                {/* Extra server-validated benefits of segment offers */}
                {appliedCoupon?.freeShipping && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#6B5E63' }}>
                    <span>Shipping</span>
                    <span style={{ fontWeight: 700, color: '#16A34A' }}>Free ({appliedCoupon.code})</span>
                  </div>
                )}
                {appliedCoupon?.cashback > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#6B5E63' }}>
                    <span>Cashback</span>
                    <span style={{ fontWeight: 700, color: '#16A34A' }}>₹{Number(appliedCoupon.cashback).toLocaleString('en-IN')} after delivery</span>
                  </div>
                )}
                {appliedCoupon?.gift && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#6B5E63' }}>
                    <span>Free gift</span>
                    <span style={{ fontWeight: 700, color: '#16A34A' }}>{appliedCoupon.gift.name}</span>
                  </div>
                )}

                {/* Final Total */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    paddingTop: '1rem',
                    borderTop: '1px solid #F0E2E0',
                    marginTop: '4px',
                  }}
                >
                  <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1F191B' }}>
                    Total Amount
                  </span>
                  <span
                    style={{
                      fontSize: '1.65rem',
                      fontWeight: 800,
                      color: '#B8505E',
                      fontFamily: "'Plus Jakarta Sans', sans-serif",
                    }}
                  >
                    ₹{Number(appliedCoupon ? appliedCoupon.payable : total).toLocaleString('en-IN')}
                  </span>
                </div>
              </div>

              {/* Place Order Button */}
              <button
                type="submit"
                disabled={submitting}
                className="tarika-btn-primary"
                style={{
                  width: '100%',
                  padding: '1rem 1.5rem',
                  fontSize: '1rem',
                  marginBottom: '1rem',
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  opacity: submitting ? 0.75 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '10px',
                }}
              >
                {submitting ? (
                  <>
                    <Loader2 size={18} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                    <span>Processing Order...</span>
                  </>
                ) : (
                  <>
                    <Lock size={16} />
                    <span>Place Order • ₹{Number(appliedCoupon ? appliedCoupon.payable : total).toLocaleString('en-IN')}</span>
                  </>
                )}
              </button>

              {/* Atelier Perks */}
              <div
                style={{
                  marginTop: '1.25rem',
                  paddingTop: '1rem',
                  borderTop: '1px solid #F0E2E0',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Truck size={14} color="#8E3642" />
                  <span style={{ fontSize: '0.76rem', color: '#6B5E63' }}>
                    Complimentary Express Courier
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <ShieldCheck size={14} color="#8E3642" />
                  <span style={{ fontSize: '0.76rem', color: '#6B5E63' }}>
                    100% Genuine Luxury Guarantee
                  </span>
                </div>
              </div>
            </aside>
          </div>
        </form>
      )}
    </div>
  );
}
