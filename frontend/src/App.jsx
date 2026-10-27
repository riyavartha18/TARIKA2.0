import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth, ROLE_ROUTES } from './auth/AuthContext';
import Login from './pages/Login';
import Signup from './pages/Signup';

// Role portals are loaded on demand so the public landing page and the
// customer flow never download the admin / warehouse / delivery bundles.
const Home = lazy(() => import('./pages/Home'));
const CustomerPortal = lazy(() => import('./pages/customer/CustomerPortal'));
const AdminPortal = lazy(() => import('./pages/admin/AdminPortal'));
const WarehousePortal = lazy(() => import('./pages/warehouse/WarehousePortal'));
const DeliveryPortal = lazy(() => import('./pages/delivery/DeliveryPortal'));

function PortalFallback() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#FAF7F5',
      }}
    >
      <div
        style={{
          width: '34px',
          height: '34px',
          borderRadius: '50%',
          border: '3px solid rgba(216, 114, 126, 0.25)',
          borderTopColor: '#D8727E',
          animation: 'spin 0.8s linear infinite',
        }}
      />
    </div>
  );
}

function ProtectedRoute({ children, allowedRole }) {
  const { isAuthenticated, role } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRole && role !== allowedRole) {
    const defaultRoute = ROLE_ROUTES[role] || '/customer';
    return <Navigate to={defaultRoute} replace />;
  }

  return children;
}

function PublicAuthRoute({ children }) {
  const { isAuthenticated, role } = useAuth();

  if (isAuthenticated) {
    const defaultRoute = ROLE_ROUTES[role] || '/customer';
    return <Navigate to={defaultRoute} replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <Suspense fallback={<PortalFallback />}>
      <Routes>
        {/* TARIKA Customer-Facing Homepage */}
        <Route path="/" element={<Home />} />

        {/* Authentication Routes (Part 1 intact) */}
        <Route
          path="/login"
          element={
            <PublicAuthRoute>
              <Login />
            </PublicAuthRoute>
          }
        />
        <Route
          path="/signup"
          element={
            <PublicAuthRoute>
              <Signup />
            </PublicAuthRoute>
          }
        />

        {/* Role-Protected Portals */}
        <Route
          path="/customer/*"
          element={
            <ProtectedRoute allowedRole="CUSTOMER">
              <CustomerPortal />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/*"
          element={
            <ProtectedRoute allowedRole="ADMIN">
              <AdminPortal />
            </ProtectedRoute>
          }
        />
        <Route
          path="/warehouse/*"
          element={
            <ProtectedRoute allowedRole="WAREHOUSE_MANAGER">
              <WarehousePortal />
            </ProtectedRoute>
          }
        />
        <Route
          path="/delivery/*"
          element={
            <ProtectedRoute allowedRole="DELIVERY_PARTNER">
              <DeliveryPortal />
            </ProtectedRoute>
          }
        />

        {/* Catch-all fallback to Homepage */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
