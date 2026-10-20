import React, { createContext, useContext, useState, useEffect } from 'react';
import { loginUser, registerCustomer, logoutUser, getMe } from '../services/api';

const AuthContext = createContext(null);

export const ROLE_ROUTES = {
  CUSTOMER: '/customer',
  ADMIN: '/admin',
  WAREHOUSE_MANAGER: '/warehouse',
  DELIVERY_PARTNER: '/delivery',
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('iras_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [token, setToken] = useState(() => {
    return localStorage.getItem('iras_token') || null;
  });

  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (token && !user) {
      getMe(token).then((res) => {
        if (res.success) {
          setUser(res.user);
          localStorage.setItem('iras_user', JSON.stringify(res.user));
        } else if (res.error === 'Session expired') {
          logout();
        }
      });
    }
  }, [token]);

  const handleLogin = async (email, password) => {
    setIsLoading(true);
    const result = await loginUser(email, password);
    setIsLoading(false);

    if (result.success) {
      const accessToken = result.tokens?.access_token;
      setUser(result.user);
      setToken(accessToken);
      localStorage.setItem('iras_token', accessToken);
      localStorage.setItem('iras_user', JSON.stringify(result.user));

      const redirectPath = ROLE_ROUTES[result.role] || '/customer';
      return { success: true, redirectPath, role: result.role };
    }

    return { success: false, error: result.error };
  };

  const handleRegister = async (customerData) => {
    setIsLoading(true);
    const result = await registerCustomer(customerData);
    setIsLoading(false);

    if (result.success) {
      const accessToken = result.tokens?.access_token;
      setUser(result.user);
      setToken(accessToken);
      localStorage.setItem('iras_token', accessToken);
      localStorage.setItem('iras_user', JSON.stringify(result.user));

      return { success: true, redirectPath: '/customer', role: 'CUSTOMER' };
    }

    return { success: false, error: result.error };
  };

  const logout = async () => {
    if (token) {
      await logoutUser(token);
    }
    setUser(null);
    setToken(null);
    localStorage.removeItem('iras_token');
    localStorage.removeItem('iras_user');
  };

  const value = {
    user,
    token,
    role: user?.role || null,
    warehouseId: user?.warehouse_id || null,
    isAuthenticated: Boolean(token && user),
    isLoading,
    login: handleLogin,
    register: handleRegister,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
