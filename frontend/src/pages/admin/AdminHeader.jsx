import React from 'react';
import { useAuth } from '../../auth/AuthContext';
import { Menu, LogOut, ShieldCheck, Sparkles } from 'lucide-react';

export default function AdminHeader({ activeNavLabel, onToggleMobileMenu }) {
  const { user, logout } = useAuth();

  // Extract display name and initial dynamically from authenticated user
  const firstName = user?.first_name?.trim() || '';
  const lastName = user?.last_name?.trim() || '';
  const fullName = (firstName || lastName)
    ? `${firstName} ${lastName}`.trim()
    : (user?.full_name?.trim() || user?.name?.trim() || 'Admin');
  const userInitial = (firstName?.[0] || user?.email?.[0] || 'A').toUpperCase();

  return (
    <header className="admin-top-header">
      {/* Left side: Mobile Toggle & Page Title */}
      <div className="admin-header-left">
        <button
          onClick={onToggleMobileMenu}
          className="admin-mobile-toggle"
          aria-label="Toggle navigation menu"
        >
          <Menu size={20} />
        </button>
        <div className="admin-page-title-wrap">
          <span className="admin-breadcrumb">TARIKA Admin / Module</span>
          <h2 className="admin-header-title">{activeNavLabel}</h2>
        </div>
      </div>

      {/* Right side: System status, User profile, Logout button */}
      <div className="admin-header-right">
        <div className="admin-system-badge">
          <span className="admin-system-dot" />
          <span>Admin Portal Active</span>
        </div>

        <div className="admin-user-profile">
          <div className="admin-user-avatar">
            {userInitial}
          </div>
          <div className="admin-user-info">
            <span className="admin-user-name">{fullName}</span>
            <span className="admin-user-role">{user?.email || 'ADMIN'}</span>
          </div>
        </div>

        <button onClick={logout} className="admin-logout-btn" title="Sign out of Admin Portal">
          <LogOut size={16} />
          <span>Logout</span>
        </button>
      </div>
    </header>
  );
}
