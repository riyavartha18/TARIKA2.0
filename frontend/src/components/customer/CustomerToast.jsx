import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { useCustomer } from '../../context/CustomerContext';

export default function CustomerToast() {
  const { toasts, removeToast } = useCustomer();

  if (!toasts || toasts.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '380px',
        width: 'calc(100% - 48px)',
        pointerEvents: 'none',
      }}
    >
      {toasts.map((toast) => {
        let icon = <CheckCircle2 size={18} color="#D8727E" />;
        let borderColor = 'rgba(216, 114, 126, 0.3)';
        let badgeBg = 'rgba(251, 241, 240, 0.95)';

        if (toast.type === 'error') {
          icon = <AlertCircle size={18} color="#E04D60" />;
          borderColor = 'rgba(224, 77, 96, 0.35)';
          badgeBg = 'rgba(255, 241, 242, 0.98)';
        } else if (toast.type === 'info') {
          icon = <Info size={18} color="#8E3642" />;
          borderColor = 'rgba(142, 54, 66, 0.25)';
          badgeBg = 'rgba(255, 251, 249, 0.98)';
        }

        return (
          <div
            key={toast.id}
            style={{
              pointerEvents: 'auto',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '12px 16px',
              backgroundColor: badgeBg,
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              borderRadius: '14px',
              border: `1px solid ${borderColor}`,
              boxShadow: '0 12px 36px rgba(184, 80, 94, 0.16)',
              animation: 'toastSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
              fontFamily: "'Plus Jakarta Sans', sans-serif",
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
              <span style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>{icon}</span>
              <p
                style={{
                  margin: 0,
                  fontSize: '0.86rem',
                  fontWeight: 500,
                  color: '#1F191B',
                  lineHeight: 1.4,
                }}
              >
                {toast.message}
              </p>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '4px',
                color: '#9E8F94',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '6px',
                transition: 'color 0.2s ease',
              }}
              aria-label="Dismiss toast"
            >
              <X size={15} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
