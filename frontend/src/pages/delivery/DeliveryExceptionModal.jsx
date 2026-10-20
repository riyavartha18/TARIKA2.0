import React, { useState } from 'react';
import { X, AlertTriangle, AlertCircle, Clock, XCircle } from 'lucide-react';

const COMMON_REASONS = [
  'Customer unreachable via phone / door unattended',
  'Customer requested delivery reschedule',
  'Incorrect or incomplete shipping address',
  'Premises access restricted / gate locked',
  'Severe weather / traffic obstruction',
  'Customer refused delivery / payment issue',
];

export default function DeliveryExceptionModal({
  delivery,
  onClose,
  onSubmitException,
  isSubmitting,
}) {
  const [selectedType, setSelectedType] = useState('Delayed');
  const [reasonPreset, setReasonPreset] = useState(COMMON_REASONS[0]);
  const [customNote, setCustomNote] = useState('');
  const [validationError, setValidationError] = useState('');

  if (!delivery) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    const finalReason = customNote.trim()
      ? `${reasonPreset} — ${customNote.trim()}`
      : reasonPreset;

    if (!finalReason.trim()) {
      setValidationError('Please select or specify a reason.');
      return;
    }

    onSubmitException(delivery.delivery_id, selectedType, finalReason);
  };

  return (
    <div className="delivery-modal-backdrop" onClick={onClose}>
      <div className="delivery-modal-window" style={{ maxWidth: '540px' }} onClick={(e) => e.stopPropagation()}>
        <button className="delivery-modal-close" onClick={onClose} aria-label="Close modal">
          <X size={20} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.75rem', color: '#BE123C' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: '#FFE4E6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <AlertTriangle size={20} color="#BE123C" />
          </div>
          <div>
            <h2 style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: '1.35rem',
              fontWeight: 700,
              margin: 0,
              color: '#1F191B',
            }}>
              Report Delivery Exception
            </h2>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#9E8F94' }}>
              Package: <strong>{delivery.delivery_id}</strong>
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Status Option Toggle: Delayed vs Failed */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
              Select Exception Status
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => setSelectedType('Delayed')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '12px',
                  border: selectedType === 'Delayed' ? '2px solid #D97706' : '1px solid #E5D0CD',
                  background: selectedType === 'Delayed' ? '#FFFBEB' : '#FFFFFF',
                  color: selectedType === 'Delayed' ? '#92400E' : '#6B5E63',
                  fontWeight: 700,
                  fontSize: '0.84rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <Clock size={16} />
                <span>Mark as Delayed</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedType('Failed')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '12px',
                  border: selectedType === 'Failed' ? '2px solid #DC2626' : '1px solid #E5D0CD',
                  background: selectedType === 'Failed' ? '#FEF2F2' : '#FFFFFF',
                  color: selectedType === 'Failed' ? '#991B1B' : '#6B5E63',
                  fontWeight: 700,
                  fontSize: '0.84rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <XCircle size={16} />
                <span>Mark as Failed</span>
              </button>
            </div>
            <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.74rem', color: '#9E8F94' }}>
              {selectedType === 'Delayed'
                ? 'Delivery will remain queued for re-attempt upon resolution.'
                : 'Delivery will be closed as unsuccessful and warehouse notified.'}
            </p>
          </div>

          {/* Reason Presets */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
              Primary Reason
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {COMMON_REASONS.map((r) => (
                <label
                  key={r}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.55rem',
                    padding: '0.55rem 0.85rem',
                    borderRadius: '8px',
                    border: reasonPreset === r ? '1px solid #D8727E' : '1px solid #F0E2E0',
                    background: reasonPreset === r ? '#FBF1F0' : '#FAF7F5',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    color: reasonPreset === r ? '#8E3642' : '#1F191B',
                    fontWeight: reasonPreset === r ? 600 : 400,
                  }}
                >
                  <input
                    type="radio"
                    name="reasonPreset"
                    checked={reasonPreset === r}
                    onChange={() => {
                      setReasonPreset(r);
                      setValidationError('');
                    }}
                    style={{ accentColor: '#8E3642' }}
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Custom Note */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#6B5E63', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
              Additional Dispatch Notes (Optional)
            </label>
            <textarea
              value={customNote}
              onChange={(e) => setCustomNote(e.target.value)}
              placeholder="e.g. Called customer 3 times, neighbor confirmed they are out of town until tomorrow..."
              rows={3}
              style={{
                width: '100%',
                padding: '0.75rem',
                borderRadius: '10px',
                border: '1px solid #E5D0CD',
                fontSize: '0.84rem',
                outline: 'none',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
                resize: 'vertical',
              }}
            />
          </div>

          {validationError && (
            <div style={{ color: '#DC2626', fontSize: '0.8rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <AlertCircle size={15} />
              <span>{validationError}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.75rem' }}>
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
              style={{
                background: selectedType === 'Delayed' ? '#D97706' : '#DC2626',
                width: 'auto',
                padding: '0.65rem 1.5rem',
              }}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Recording...' : `Confirm ${selectedType}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
