import React, { useState } from 'react';
import { X, AlertTriangle, XCircle, RotateCcw } from 'lucide-react';

const COMMON_RETURN_FAIL_REASONS = [
  'Customer unavailable / door locked at pickup address',
  'Product not packaged or not ready for handover',
  'Customer cancelled return request at doorstep',
  'Incorrect or mismatched product presented by customer',
  'Product damaged / tags missing / condition unacceptable',
  'Customer address inaccessible / restricted gate',
];

export default function ReturnExceptionModal({
  returnPickup,
  onClose,
  onSubmitException,
  isSubmitting,
}) {
  const [reasonPreset, setReasonPreset] = useState(COMMON_RETURN_FAIL_REASONS[0]);
  const [customNote, setCustomNote] = useState('');
  const [validationError, setValidationError] = useState('');

  if (!returnPickup) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    const finalReason = customNote.trim()
      ? `${reasonPreset} — ${customNote.trim()}`
      : reasonPreset;

    if (!finalReason.trim()) {
      setValidationError('Please select or specify a reason.');
      return;
    }

    onSubmitException(returnPickup.return_id, 'Failed', finalReason);
  };

  return (
    <div className="delivery-modal-backdrop" onClick={onClose}>
      <div className="delivery-modal-window" style={{ maxWidth: '540px' }} onClick={(e) => e.stopPropagation()}>
        <button className="delivery-modal-close" onClick={onClose} aria-label="Close modal">
          <X size={20} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.75rem', color: '#B45309' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            background: '#FEF3C7',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <RotateCcw size={20} color="#D97706" />
          </div>
          <div>
            <h2 style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: '1.35rem',
              fontWeight: 700,
              margin: 0,
              color: '#1F191B',
            }}>
              Report Return Pickup Exception
            </h2>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#9E8F94' }}>
              Return Request: <strong>{returnPickup.return_id}</strong> • Order #{returnPickup.order_id?.slice(0, 14)}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Reason preset selector */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
              Select Reason for Failed Pickup
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {COMMON_RETURN_FAIL_REASONS.map((reason) => (
                <label
                  key={reason}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.6rem',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '8px',
                    border: reasonPreset === reason ? '1px solid #D97706' : '1px solid #E5D0CD',
                    background: reasonPreset === reason ? '#FFFBEB' : '#FFFFFF',
                    cursor: 'pointer',
                    fontSize: '0.84rem',
                    color: '#1F191B',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <input
                    type="radio"
                    name="return_reason_preset"
                    checked={reasonPreset === reason}
                    onChange={() => {
                      setReasonPreset(reason);
                      setValidationError('');
                    }}
                    style={{ accentColor: '#D97706' }}
                  />
                  <span>{reason}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Custom Note */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
              Additional Field Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={customNote}
              onChange={(e) => setCustomNote(e.target.value)}
              placeholder="e.g. Spoke with customer on phone at 3:15 PM, requested pickup next Monday morning."
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: '8px',
                border: '1px solid #E5D0CD',
                fontFamily: 'inherit',
                fontSize: '0.85rem',
                outline: 'none',
                resize: 'vertical',
                boxSizing: 'border-box'
              }}
            />
          </div>

          {validationError && (
            <div style={{ color: '#BE123C', fontSize: '0.82rem', marginBottom: '1rem', fontWeight: 600 }}>
              {validationError}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              type="button"
              className="delivery-btn-secondary"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="delivery-btn-primary"
              style={{ background: '#DC2626', borderColor: '#DC2626' }}
              disabled={isSubmitting}
            >
              <XCircle size={16} />
              <span>{isSubmitting ? 'Recording...' : 'Record Pickup Exception'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
