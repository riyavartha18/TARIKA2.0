import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import AdminSidebar, { ADMIN_NAV_ITEMS } from './AdminSidebar';
import AdminHeader from './AdminHeader';
import AdminDashboardView from './AdminDashboardView';
import AdminStaffView from './AdminStaffView';
import AdminWarehouseView from './AdminWarehouseView';
import AdminProductView from './AdminProductView';
import AdminAnalyticsView from './AdminAnalyticsView';
import AdminSectionPlaceholder from './AdminSectionPlaceholder';
import '../../styles/tarika.css';
import '../../styles/admin-portal.css';

export default function AdminPortal() {
  const location = useLocation();
  const navigate = useNavigate();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  useEffect(() => {
    document.title = 'TARIKA — Admin Portal';
  }, []);

  // Determine active section from current URL (e.g. /admin/staff -> 'staff')
  const pathSegments = location.pathname.split('/').filter(Boolean);
  const currentSubPath = pathSegments[1] || 'dashboard';
  const activeSection = ADMIN_NAV_ITEMS.some((item) => item.id === currentSubPath)
    ? currentSubPath
    : 'dashboard';

  // Find metadata for current active nav item
  const currentNavItem = ADMIN_NAV_ITEMS.find((item) => item.id === activeSection) || ADMIN_NAV_ITEMS[0];

  const handleSelectSection = (sectionId) => {
    if (sectionId === 'dashboard') {
      navigate('/admin');
    } else {
      navigate(`/admin/${sectionId}`);
    }
  };

  const handleToggleMobileMenu = () => {
    setIsMobileOpen((prev) => !prev);
  };

  const handleCloseMobileMenu = () => {
    setIsMobileOpen(false);
  };

  return (
    <div className="admin-portal-layout">
      {/* Mobile Drawer Backdrop */}
      <div
        className={`admin-mobile-backdrop ${isMobileOpen ? 'mobile-open' : ''}`}
        onClick={handleCloseMobileMenu}
      />

      {/* Left Sidebar Navigation */}
      <AdminSidebar
        activeSection={activeSection}
        onSelectSection={handleSelectSection}
        isMobileOpen={isMobileOpen}
        onCloseMobile={handleCloseMobileMenu}
      />

      {/* Main Content Wrapper */}
      <div className="admin-main-wrapper">
        {/* Top Header */}
        <AdminHeader
          activeNavLabel={currentNavItem.label}
          onToggleMobileMenu={handleToggleMobileMenu}
        />

        {/* Main Section Content */}
        <main className="admin-main-content">
          <Routes>
            <Route index element={<AdminDashboardView />} />
            <Route path="dashboard" element={<AdminDashboardView />} />
            <Route path="staff" element={<AdminStaffView />} />
            <Route path="warehouses" element={<AdminWarehouseView />} />
            <Route path="products" element={<AdminProductView />} />
            <Route path="analytics" element={<AdminAnalyticsView />} />
            <Route path="analysis" element={<AdminAnalyticsView />} />
            {ADMIN_NAV_ITEMS.filter(
              (item) => !['dashboard', 'staff', 'warehouses', 'products', 'analytics', 'analysis'].includes(item.id)
            ).map((item) => (
              <Route
                key={item.id}
                path={item.id}
                element={
                  <AdminSectionPlaceholder
                    title={item.label}
                    icon={item.icon}
                  />
                }
              />
            ))}
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

