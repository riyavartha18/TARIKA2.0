import React, { useEffect, lazy, Suspense, Component } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { CustomerProvider } from '../../context/CustomerContext';
import CustomerNavbar from '../../components/customer/CustomerNavbar';
import ProductDetailModal from '../../components/customer/ProductDetailModal';
import CustomerToast from '../../components/customer/CustomerToast';
import { SkeletonProductGrid } from '../../components/customer/Skeleton';

// Landing view stays eager so the first page after login paints immediately.
import CustomerHome from './CustomerHome';

// Everything below is reached only on navigation, so it is code-split out of
// the landing bundle (ShopCategories, CheckoutPage and MyOrdersPage alone are
// >3500 lines and were previously downloaded on first login).
const ShopCategories = lazy(() => import('./ShopCategories'));
const ProductListingPage = lazy(() => import('./ProductListingPage'));
const WishlistPage = lazy(() => import('./WishlistPage'));
const BagPage = lazy(() => import('./BagPage'));
const CheckoutPage = lazy(() => import('./CheckoutPage'));
const OrderConfirmationPage = lazy(() => import('./OrderConfirmationPage'));
const MyOrdersPage = lazy(() => import('./MyOrdersPage'));
const ProfilePage = lazy(() => import('./ProfilePage'));

// Portal CSS
import '../../styles/tarika.css';
import '../../styles/customer-portal.css';

function RouteFallback() {
  return (
    <div style={{ padding: '1rem 0' }}>
      <SkeletonProductGrid count={8} />
    </div>
  );
}

// A single uncaught render error otherwise unmounts the whole portal to a
// blank/black screen. This boundary keeps the navbar and page shell intact and
// shows a recoverable message instead, so a failing component or request never
// leaves the customer staring at an empty page after login.
class PortalErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('Customer portal render error:', error, info);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            padding: '4rem 2rem',
            textAlign: 'center',
            backgroundColor: '#FFFFFF',
            borderRadius: '20px',
            border: '1px solid #F0E2E0',
            maxWidth: '560px',
            margin: '2rem auto',
          }}
        >
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '1.5rem',
              color: '#1F191B',
              margin: '0 0 0.5rem 0',
            }}
          >
            Something went wrong
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: '0 0 1.5rem 0' }}>
            This part of the store could not be displayed. Your account and cart
            are safe — please try again.
          </p>
          <button type="button" className="tarika-btn-primary" onClick={this.handleRetry}>
            <span>Try Again</span>
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function CustomerPortal() {
  useEffect(() => {
    document.title = 'TARIKA — Customer Portal';
  }, []);

  return (
    <CustomerProvider>
      <div
        className="tarika-home"
        style={{
          minHeight: '100vh',
          backgroundColor: '#FAF7F5',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Customer Top Navigation & Marquee */}
        <CustomerNavbar />

        {/* Main Content Area */}
        <main
          style={{
            maxWidth: '1680px',
            width: '100%',
            margin: '0 auto',
            padding: '2rem 2.5rem',
            flex: 1,
            boxSizing: 'border-box',
          }}
        >
          <PortalErrorBoundary>
            <Routes>
            <Route index element={<CustomerHome />} />
            <Route
              path="shop"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <ShopCategories />
                </Suspense>
              }
            />
            <Route
              path="new-in"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <ProductListingPage type="new-in" />
                </Suspense>
              }
            />
            <Route
              path="trending"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <ProductListingPage type="trending" />
                </Suspense>
              }
            />
            <Route
              path="sale"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <ProductListingPage type="sale" />
                </Suspense>
              }
            />
            <Route
              path="wishlist"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <WishlistPage />
                </Suspense>
              }
            />
            <Route
              path="bag"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <BagPage />
                </Suspense>
              }
            />
            <Route
              path="checkout"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <CheckoutPage />
                </Suspense>
              }
            />
            <Route
              path="order-confirmation/:orderId"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <OrderConfirmationPage />
                </Suspense>
              }
            />
            <Route
              path="orders"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <MyOrdersPage />
                </Suspense>
              }
            />
            <Route
              path="profile"
              element={
                <Suspense fallback={<RouteFallback />}>
                  <ProfilePage />
                </Suspense>
              }
            />
            {/* Fallback to customer home */}
            <Route path="*" element={<Navigate to="/customer" replace />} />
          </Routes>
          </PortalErrorBoundary>
        </main>

        {/* Global Product Detail Modal */}
        <ProductDetailModal />

        {/* Micro-animated Customer Toasts */}
        <CustomerToast />

        {/* Subdued Boutique Footer */}
        <footer
          style={{
            borderTop: '1px solid rgba(216, 114, 126, 0.18)',
            backgroundColor: '#FFFFFF',
            padding: '2.5rem 2rem',
            marginTop: 'auto',
          }}
        >
          <div
            style={{
              maxWidth: '1680px',
              margin: '0 auto',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1.5rem',
            }}
          >
            <div>
              <span
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.3rem',
                  fontWeight: 700,
                  color: '#1F191B',
                  letterSpacing: '0.08em',
                }}
              >
                TARIKA
              </span>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem', color: '#9E8F94' }}>
                Handcrafted Luxury • National Express Dispatch • © 2026 TARIKA Retail Inc.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '2rem', fontSize: '0.82rem', color: '#6B5E63' }}>
              <span>Atelier Guarantee</span>
              <span>Complimentary Delivery</span>
              <span>VIP Privilege Circle</span>
            </div>
          </div>
        </footer>
      </div>
    </CustomerProvider>
  );
}
