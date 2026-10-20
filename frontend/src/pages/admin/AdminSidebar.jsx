import React from 'react';
import {
  LayoutDashboard,
  Users,
  Building2,
  Package,
  BarChart3,
  ShieldCheck,
  ChevronRight,
  Sparkles,
} from 'lucide-react';

export const ADMIN_NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'staff', label: 'Staff Management', icon: Users },
  { id: 'warehouses', label: 'Warehouses', icon: Building2 },
  { id: 'products', label: 'Products', icon: Package },
  { id: 'analytics', label: 'Admin Analysis', icon: BarChart3 },
];

export default function AdminSidebar({ activeSection, onSelectSection, isMobileOpen, onCloseMobile }) {
  return (
    <aside className={`admin-sidebar ${isMobileOpen ? 'mobile-open' : ''}`}>
      {/* Admin Brand Area */}
      <div className="admin-sidebar-brand">
        <div className="admin-brand-header">
          <div className="admin-brand-icon">
            <Sparkles size={20} />
          </div>
          <div>
            <h1 className="admin-brand-title">TARIKA</h1>
            <p className="admin-brand-subtitle">HAUTE RETAIL</p>
          </div>
        </div>
        <span className="admin-brand-badge">
          <ShieldCheck size={12} />
          Admin Portal
        </span>
      </div>

      {/* Navigation Menu */}
      <nav className="admin-sidebar-nav">
        <span className="admin-nav-section-label">Management Modules</span>
        {ADMIN_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeSection === item.id;
          return (
            <button
              key={item.id}
              onClick={() => {
                onSelectSection(item.id);
                if (onCloseMobile) onCloseMobile();
              }}
              className={`admin-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} className="admin-nav-icon" color={isActive ? '#B8505E' : '#6B5E63'} />
              <span className="admin-nav-label">{item.label}</span>
              <ChevronRight size={14} className="admin-nav-chevron" color="#B8505E" />
            </button>
          );
        })}
      </nav>

      {/* Sidebar Footer info */}
      <div className="admin-sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#9E8F94', fontSize: '0.72rem' }}>
          <ShieldCheck size={14} color="#D8727E" />
          <span>System Version v1.0 • Incremental</span>
        </div>
      </div>
    </aside>
  );
}
