import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth, ROLE_ROUTES } from './auth/AuthContext';
import Home from './pages/Home';
import Login from './pages/Login';
import Signup from './pages/Signup';
import CustomerPortal from './pages/customer/CustomerPortal';
import AdminPortal from './pages/admin/AdminPortal';
import WarehousePortal from './pages/warehouse/WarehousePortal';
import DeliveryPortal from './pages/delivery/DeliveryPortal';

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
