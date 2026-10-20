import React, { useState, useEffect } from 'react';
import { 
  X, 
  MapPin, 
  Phone, 
  Calendar, 
  Package, 
  Truck, 
  CheckCircle, 
  AlertTriangle
} from 'lucide-react';
import { fetchDeliveryDetail } from './deliveryApi';

export default function DeliveryDetailsModal({ 
  deliveryId, 
  token, 
  onClose, 
  onStatusChange,
  onOpenIssueModal
}) {
  const [delivery, setDelivery] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function loadDetail() {
      setLoading(true);
      setError(null);
      const res = await fetchDeliveryDetail(token, deliveryId);
      if (isMounted) {
        if (res.success) {
          setDelivery(res.delivery);
        } else {
          setError(res.error || 'Failed to load delivery details.');
        }
        setLoading(false);
      }
    }
    loadDetail();
    return () => { isMounted = false; };
  }, [deliveryId, token]);

  const stages = ['Assigned', 'Picked Up', 'In Transit', 'Delivered'];
  const currentStatus = delivery?.delivery_status || '';
  const currentStageIndex = stages.findIndex(s => s.toLowerCase() === currentStatus.toLowerCase());

  return (
    <div className="delivery-modal-backdrop" onClick={onClose}>
      <div className="delivery-modal-window" onClick={(e) => e.stopPropagation()}>
        <button className="delivery-modal-close" onClick={onClose} aria-label="Close modal">
          <X size={20} />
        </button>

        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#8E3642' }}>
            <Package size={36} className="animate-spin" style={{ margin: '0 auto 1rem' }} />
            <p style={{ fontWeight: 600 }}>Loading package manifest...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#DC2626' }}>
            <AlertTriangle size={36} style={{ margin: '0 auto 1rem' }} />
            <p>{error}</p>
            <button className="delivery-btn-secondary" onClick={onClose} style={{ marginTop: '1rem' }}>
              Close
            </button>
          </div>
        ) : delivery && (
          <div>
            {/* Header info */}
            <div style={{ marginBottom: '1.5rem', paddingRight: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                <span className="delivery-id-title" style={{ fontSize: '1.25rem' }}>
                  {delivery.delivery_id}
                </span>
                <span className={`delivery-status-pill status-${delivery.delivery_status?.toLowerCase().replace(/\s+/g, '-')}`}>
                  {delivery.delivery_status}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#9E8F94' }}>
                Associated Order: <strong style={{ color: '#1F191B' }}>{delivery.order_id}</strong>
              </p>
            </div>

            {/* Exception Warning if Delayed/Failed */}
            {delivery.failure_reason && (
              <div className="delivery-exception-banner" style={{ marginBottom: '1.5rem' }}>
                <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <strong>Delivery Exception:</strong> {delivery.failure_reason}
                </div>
              </div>
            )}

            {/* Lifecycle Stages Step Bar */}
            <div style={{
              background: '#FAF7F5',
              border: '1px solid #F0E2E0',
              borderRadius: '14px',
              padding: '1.25rem',
              marginBottom: '1.75rem'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                position: 'relative'
              }}>
                {stages.map((st, idx) => {
                  const isDone = currentStageIndex >= idx;
                  const isCurrent = currentStageIndex === idx;
                  return (
                    <div key={st} style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      zIndex: 2,
                      width: '80px',
                      textAlign: 'center'
                    }}>
                      <div style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: isDone ? '#8E3642' : '#FFFFFF',
                        border: isDone ? '2px solid #8E3642' : '2px solid #E5D0CD',
                        color: isDone ? '#FFFFFF' : '#9E8F94',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.8rem',
                        fontWeight: 700,
                        marginBottom: '0.35rem',
                        boxShadow: isCurrent ? '0 0 10px rgba(216, 114, 126, 0.4)' : 'none'
                      }}>
                        {isDone ? <CheckCircle size={16} /> : idx + 1}
                      </div>
                      <span style={{
                        fontSize: '0.72rem',
                        fontWeight: isCurrent ? 700 : 500,
                        color: isCurrent ? '#8E3642' : '#6B5E63'
                      }}>
                        {st}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recipient / Shipping Details */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '1rem',
              marginBottom: '1.75rem'
            }}>
              <div style={{
                background: '#FFFFFF',
                border: '1px solid #F0E2E0',
                borderRadius: '12px',
                padding: '1rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#8E3642', marginBottom: '0.5rem' }}>
                  <MapPin size={16} />
                  <span style={{ fontSize: '0.76rem', fontWeight: 700, textTransform: 'uppercase' }}>Recipient Details</span>
                </div>
                <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1F191B', marginBottom: '0.25rem' }}>
                  {delivery.customer_name || 'Valued Customer'}
                </div>
                <div style={{ fontSize: '0.84rem', color: '#6B5E63', lineHeight: 1.4 }}>
                  {delivery.shipping_address || 'Address provided at checkout'}
                </div>
                <div style={{ fontSize: '0.82rem', color: '#9E8F94', marginTop: '0.25rem' }}>
                  {[delivery.customer_city, delivery.customer_state, delivery.customer_country].filter(Boolean).join(', ')}
                </div>
                {delivery.customer_phone && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <a href={`tel:${delivery.customer_phone}`} className="delivery-tel-link">
                      <Phone size={13} />
                      <span>{delivery.customer_phone}</span>
                    </a>
                  </div>
                )}
              </div>

              <div style={{
                background: '#FFFFFF',
                border: '1px solid #F0E2E0',
                borderRadius: '12px',
                padding: '1rem'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#8E3642', marginBottom: '0.5rem' }}>
                  <Calendar size={16} />
                  <span style={{ fontSize: '0.76rem', fontWeight: 700, textTransform: 'uppercase' }}>Fulfillment Timeline</span>
                </div>
                <div style={{ fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                  <span style={{ color: '#9E8F94' }}>Dispatched: </span>
                  <strong style={{ color: '#1F191B' }}>{delivery.dispatch_date || 'In warehouse prep'}</strong>
                </div>
                <div style={{ fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                  <span style={{ color: '#9E8F94' }}>Expected Delivery: </span>
                  <strong style={{ color: '#16A34A' }}>{delivery.expected_delivery_date || 'Standard schedule'}</strong>
                </div>
                {delivery.actual_delivery_date && (
                  <div style={{ fontSize: '0.82rem', marginBottom: '0.4rem' }}>
                    <span style={{ color: '#9E8F94' }}>Completed Delivery: </span>
                    <strong style={{ color: '#8E3642' }}>{delivery.actual_delivery_date}</strong>
                  </div>
                )}
                <div style={{ fontSize: '0.82rem', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid #F0E2E0' }}>
                  <span style={{ color: '#9E8F94' }}>Order Total: </span>
                  <strong style={{ color: '#1F191B', fontSize: '0.92rem' }}>₹{Number(delivery.total_amount || 0).toLocaleString()}</strong>
                  <span style={{ marginLeft: '0.5rem', fontSize: '0.76rem', color: '#16A34A', fontWeight: 600 }}>
                    ({delivery.payment_status || 'Paid'})
                  </span>
                </div>
              </div>
            </div>

            {/* Itemized Manifest */}
            <div style={{ marginBottom: '1.75rem' }}>
              <h3 style={{
                fontFamily: "'Playfair Display', Georgia, serif",
                fontSize: '1.15rem',
                margin: '0 0 0.5rem 0',
                color: '#1F191B'
              }}>
                Package Contents ({delivery.items?.length || 0} items)
              </h3>

              {delivery.items && delivery.items.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table className="delivery-items-table">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Details</th>
                        <th>Qty</th>
                        <th>Unit Price</th>
                        <th>Subtotal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {delivery.items.map((it) => (
                        <tr key={it.order_item_id}>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                              {it.image ? (
                                <img src={it.image} alt={it.product_name} className="delivery-item-thumb" />
                              ) : (
                                <div className="delivery-item-thumb" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <Package size={20} color="#D8727E" />
                                </div>
                              )}
                              <div>
                                <div style={{ fontWeight: 700, color: '#1F191B' }}>{it.product_name}</div>
                                <div style={{ fontSize: '0.72rem', color: '#9E8F94' }}>SKU: {it.sku || 'N/A'}</div>
                              </div>
                            </div>
                          </td>
                          <td>
                            <div style={{ fontSize: '0.78rem', color: '#6B5E63' }}>
                              {it.color && <span>Color: {it.color} • </span>}
                              {it.size && <span>Size: {it.size}</span>}
                              {it.material && <div>Mat: {it.material}</div>}
                            </div>
                          </td>
                          <td style={{ fontWeight: 600 }}>{it.quantity}</td>
                          <td>₹{Number(it.unit_price || 0).toLocaleString()}</td>
                          <td style={{ fontWeight: 700, color: '#8E3642' }}>
                            ₹{Number(it.subtotal || 0).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p style={{ color: '#9E8F94', fontSize: '0.84rem' }}>No individual item details available for this shipment.</p>
              )}
            </div>

            {/* Modal Bottom Actions */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.75rem',
              paddingTop: '1.25rem',
              borderTop: '1px solid #F0E2E0'
            }}>
              <button className="delivery-btn-secondary" onClick={onClose}>
                Close
              </button>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {currentStatus.toLowerCase() === 'assigned' && (
                  <button
                    className="delivery-btn-primary"
                    onClick={() => {
                      onStatusChange(delivery.delivery_id, 'Picked Up');
                      onClose();
                    }}
                  >
                    <Package size={15} />
                    <span>Confirm Pickup</span>
                  </button>
                )}

                {currentStatus.toLowerCase() === 'picked up' && (
                  <button
                    className="delivery-btn-primary"
                    onClick={() => {
                      onStatusChange(delivery.delivery_id, 'In Transit');
                      onClose();
                    }}
                  >
                    <Truck size={15} />
                    <span>Start Delivery</span>
                  </button>
                )}

                {currentStatus.toLowerCase() === 'in transit' && (
                  <>
                    <button
                      className="delivery-btn-issue"
                      onClick={() => {
                        onClose();
                        onOpenIssueModal(delivery);
                      }}
                    >
                      <AlertTriangle size={15} />
                      <span>Report Exception</span>
                    </button>
                    <button
                      className="delivery-btn-primary"
                      onClick={() => {
                        onStatusChange(delivery.delivery_id, 'Delivered');
                        onClose();
                      }}
                    >
                      <CheckCircle size={15} />
                      <span>Mark Delivered</span>
                    </button>
                  </>
                )}

                {['delayed', 'failed'].includes(currentStatus.toLowerCase()) && (
                  <button
                    className="delivery-btn-primary"
                    onClick={() => {
                      onStatusChange(delivery.delivery_id, 'In Transit');
                      onClose();
                    }}
                  >
                    <Truck size={15} />
                    <span>Resume Delivery</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
