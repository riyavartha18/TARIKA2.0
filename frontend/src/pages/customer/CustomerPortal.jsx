import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { CustomerProvider } from '../../context/CustomerContext';
import CustomerNavbar from '../../components/customer/CustomerNavbar';
import ProductDetailModal from '../../components/customer/ProductDetailModal';
import CustomerToast from '../../components/customer/CustomerToast';

// Subviews
import CustomerHome from './CustomerHome';
import ShopCategories from './ShopCategories';
import ProductListingPage from './ProductListingPage';
import WishlistPage from './WishlistPage';
import BagPage from './BagPage';
import CheckoutPage from './CheckoutPage';
import OrderConfirmationPage from './OrderConfirmationPage';
import MyOrdersPage from './MyOrdersPage';
import ProfilePage from './ProfilePage';

// Portal CSS
import '../../styles/tarika.css';
import '../../styles/customer-portal.css';

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
          <Routes>
            <Route index element={<CustomerHome />} />
            <Route path="shop" element={<ShopCategories />} />
            <Route path="new-in" element={<ProductListingPage type="new-in" />} />
            <Route path="trending" element={<ProductListingPage type="trending" />} />
            <Route path="sale" element={<ProductListingPage type="sale" />} />
            <Route path="wishlist" element={<WishlistPage />} />
            <Route path="bag" element={<BagPage />} />
            <Route path="checkout" element={<CheckoutPage />} />
            <Route path="order-confirmation/:orderId" element={<OrderConfirmationPage />} />
            <Route path="orders" element={<MyOrdersPage />} />
            <Route path="profile" element={<ProfilePage />} />
            {/* Fallback to customer home */}
            <Route path="*" element={<Navigate to="/customer" replace />} />
          </Routes>
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
