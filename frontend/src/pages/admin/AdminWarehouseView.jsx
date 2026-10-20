import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { getAdminWarehouseList } from '../../services/api';
import {
  Building2,
  Boxes,
  Layers,
  Percent,
  Search,
  RefreshCw,
  Eye,
  X,
  AlertCircle,
  MapPin,
  User,
  Phone,
  Mail,
  ShoppingBag,
  Package,
  Calendar,
  Sparkles,
  Info,
} from 'lucide-react';

export default function AdminWarehouseView() {
  const { token } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState({
    total_warehouses: 0,
    total_capacity: 0,
    total_inventory_units: 0,
    network_utilization_pct: 0,
  });
  const [warehouses, setWarehouses] = useState([]);
  const [search, setSearch] = useState('');
  const [selectedWarehouse, setSelectedWarehouse] = useState(null);

  const fetchWarehouses = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await getAdminWarehouseList(token, { search });
    if (res.success) {
      setSummary(res.summary);
      setWarehouses(res.warehouses);
    } else {
      setError(res.error || 'Failed to load warehouse management data.');
    }
    setLoading(false);
  }, [token, search]);

  useEffect(() => {
    fetchWarehouses();
  }, [fetchWarehouses]);

  return (
    <div>
      {/* 1. Header & Title Section */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: '0 0 0.35rem' }}>
            Warehouse Management
          </h1>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: 0 }}>
            Monitor fulfillment facilities, capacity allocation, assigned managers, and inventory levels across the TARIKA retail network.
          </p>
        </div>

        <button
          onClick={fetchWarehouses}
          className="tarika-btn-outline"
          style={{ padding: '0.65rem 1.25rem', fontSize: '0.85rem' }}
          title="Refresh Warehouse Data"
        >
          <RefreshCw size={15} />
          <span>Refresh Data</span>
        </button>
      </div>

      {/* 2. System-Wide Summary KPI Cards */}
      <div className="admin-metrics-grid" style={{ marginBottom: '1.75rem' }}>
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Building2 size={22} />
            </div>
            <span className="admin-metric-status">Network Hubs</span>
          </div>
          <div>
            <p className="admin-metric-title">Total Warehouses</p>
            <p className="admin-metric-val">{summary.total_warehouses || 0}</p>
            <p className="admin-metric-subtext">Active fulfillment centers</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Layers size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#EFF6FF', color: '#2563EB', borderColor: '#BFDBFE' }}>
              Allocated Space
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Total Network Capacity</p>
            <p className="admin-metric-val">{(summary.total_capacity || 0).toLocaleString('en-IN')}</p>
            <p className="admin-metric-subtext">Units storage limit</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Boxes size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#ECFDF5', color: '#059669', borderColor: '#A7F3D0' }}>
              Current Stock
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Total Inventory Units</p>
            <p className="admin-metric-val">{(summary.total_inventory_units || 0).toLocaleString('en-IN')}</p>
            <p className="admin-metric-subtext">Aggregate physical units in stock</p>
          </div>
        </div>

        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Percent size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#FFFBEB', color: '#D97706', borderColor: '#FDE68A' }}>
              Network Density
            </span>
          </div>
          <div>
            <p className="admin-metric-title">Capacity Utilization</p>
            <p className="admin-metric-val">{summary.network_utilization_pct || 0}%</p>
            <p className="admin-metric-subtext">Storage capacity occupancy rate</p>
          </div>
        </div>
      </div>

      {/* 3. Search Bar */}
      <div className="admin-card" style={{ marginBottom: '1.5rem', padding: '1.15rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 300px', position: 'relative' }}>
            <Search size={17} style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)', color: '#9E8F94' }} />
            <input
              type="text"
              placeholder="Search by facility name, city, state, or manager..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem 0.65rem 2.4rem',
                borderRadius: '10px',
                border: '1.5px solid var(--tarika-border, #F0E2E0)',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ fontSize: '0.8rem', color: '#6B5E63', fontWeight: 600 }}>
            Showing {warehouses.length} facility records
          </div>
        </div>
      </div>

      {/* 4. Warehouse Table & Cards */}
      <div className="admin-card">
        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
            <div className="tarika-auth-spinner" style={{ margin: '0 auto 1rem', width: '2rem', height: '2rem', borderColor: 'rgba(216, 114, 126, 0.25)', borderTopColor: '#D8727E' }} />
            <p style={{ color: '#6B5E63', fontWeight: 600 }}>Loading warehouse records from database...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#DC2626' }}>
            <AlertCircle size={28} style={{ margin: '0 auto 0.5rem' }} />
            <p style={{ margin: 0, fontWeight: 600 }}>{error}</p>
          </div>
        ) : warehouses.length === 0 ? (
          <div style={{ padding: '3rem 1rem', textAlign: 'center', color: '#6B5E63' }}>
            <Building2 size={36} color="#9E8F94" style={{ margin: '0 auto 0.75rem' }} />
            <h4 style={{ margin: '0 0 0.35rem', color: '#1F191B', fontFamily: 'var(--font-serif)' }}>No Warehouses Found</h4>
            <p style={{ margin: 0, fontSize: '0.85rem' }}>No warehouse facilities match your search query.</p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Warehouse Facility</th>
                  <th>Location</th>
                  <th>Assigned Manager</th>
                  <th>Capacity & Stock</th>
                  <th>Utilization</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {warehouses.map((wh) => {
                  const utilPct = wh.utilization_pct || 0;
                  let utilColor = '#059669'; // Green
                  if (utilPct > 85) utilColor = '#DC2626'; // High/Red
                  else if (utilPct > 65) utilColor = '#D97706'; // Amber

                  return (
                    <tr key={wh.warehouse_id}>
                      {/* Name & ID */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <div style={{
                            width: '38px', height: '38px', borderRadius: '10px',
                            background: 'linear-gradient(135deg, #FBF1F0 0%, #F5DDE0 100%)',
                            border: '1px solid rgba(216, 114, 126, 0.2)',
                            color: '#B8505E', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                          }}>
                            <Building2 size={18} />
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: '#1F191B' }}>{wh.warehouse_name}</div>
                            <code style={{ fontSize: '0.72rem', color: '#6B5E63', fontFamily: 'monospace' }}>
                              ID: {wh.warehouse_id}
                            </code>
                          </div>
                        </div>
                      </td>

                      {/* Location */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', color: '#1F191B', fontWeight: 600 }}>
                          <MapPin size={13} color="#D8727E" />
                          <span>{wh.city}{wh.state ? `, ${wh.state}` : ''}</span>
                        </div>
                        {wh.country && (
                          <div style={{ fontSize: '0.72rem', color: '#6B5E63', marginLeft: '1.1rem' }}>
                            {wh.country}
                          </div>
                        )}
                      </td>

                      {/* Manager */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 600, color: '#1F191B' }}>
                          <User size={13} color="#6B5E63" />
                          <span>{wh.manager_name}</span>
                        </div>
                        {wh.manager_email && (
                          <div style={{ fontSize: '0.72rem', color: '#6B5E63', marginLeft: '1.1rem' }}>
                            {wh.manager_email}
                          </div>
                        )}
                      </td>

                      {/* Capacity & Stock */}
                      <td>
                        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1F191B' }}>
                          {wh.stock_units.toLocaleString('en-IN')} / {wh.capacity > 0 ? wh.capacity.toLocaleString('en-IN') : 'N/A'} units
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#6B5E63' }}>
                          {wh.product_count} product titles
                        </div>
                      </td>

                      {/* Utilization */}
                      <td style={{ minWidth: '130px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                          <span style={{ color: utilColor }}>{utilPct}%</span>
                          <span style={{ color: '#9E8F94', fontSize: '0.7rem' }}>occupied</span>
                        </div>
                        <div className="admin-progress-track" style={{ height: '6px' }}>
                          <div className="admin-progress-fill" style={{ width: `${Math.min(utilPct, 100)}%`, backgroundColor: utilColor }} />
                        </div>
                      </td>

                      {/* Actions */}
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={() => setSelectedWarehouse(wh)}
                          style={{
                            padding: '0.45rem 0.85rem',
                            borderRadius: '8px',
                            border: '1px solid var(--tarika-border, #F0E2E0)',
                            backgroundColor: '#FFFFFF',
                            color: '#6B5E63',
                            fontSize: '0.78rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            transition: 'all 0.2s ease',
                          }}
                          title="Inspect Warehouse Details"
                        >
                          <Eye size={14} />
                          <span>Details</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ==========================================================================
         WAREHOUSE DETAIL INSPECTION MODAL
         ========================================================================== */}
      {selectedWarehouse && (
        <>
          <div
            onClick={() => setSelectedWarehouse(null)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              backgroundColor: 'rgba(31, 25, 27, 0.55)',
              backdropFilter: 'blur(4px)',
            }}
          />

          <div
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201,
              width: 'min(500px, 100vw)', backgroundColor: '#FFFFFF',
              boxShadow: '-8px 0 60px rgba(31, 25, 27, 0.18)',
              display: 'flex', flexDirection: 'column', overflowY: 'auto',
            }}
          >
            {/* Modal Header */}
            <div style={{ padding: '1.25rem 1.5rem', backgroundColor: '#FAF7F5', borderBottom: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Building2 size={20} color="#B8505E" />
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                  Warehouse Facility Overview
                </h3>
              </div>
              <button
                onClick={() => setSelectedWarehouse(null)}
                style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FFFFFF', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Hero Header Card */}
              <div style={{ background: 'linear-gradient(135deg, #FAF7F5 0%, #FBF1F0 100%)', padding: '1.25rem', borderRadius: '16px', border: '1px solid #F0E2E0' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: '0.2rem' }}>
                  Fulfillment Hub Reference #{selectedWarehouse.warehouse_id}
                </span>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '1.2rem', fontWeight: 800, color: '#1F191B' }}>
                  {selectedWarehouse.warehouse_name}
                </h4>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#6B5E63', fontSize: '0.85rem' }}>
                  <MapPin size={14} color="#D8727E" />
                  <span>{selectedWarehouse.city}{selectedWarehouse.state ? `, ${selectedWarehouse.state}` : ''} {selectedWarehouse.country ? `(${selectedWarehouse.country})` : ''}</span>
                </div>
              </div>

              {/* Storage Capacity & Utilization Card */}
              <div style={{ border: '1px solid #F0E2E0', borderRadius: '16px', padding: '1.25rem' }}>
                <h5 style={{ margin: '0 0 0.85rem', fontSize: '0.9rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Boxes size={16} color="#B8505E" />
                  Capacity & Inventory Storage
                </h5>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '1rem' }}>
                  <div style={{ background: '#FAF7F5', padding: '0.85rem', borderRadius: '12px', border: '1px solid #F0E2E0' }}>
                    <span style={{ fontSize: '0.7rem', color: '#6B5E63', fontWeight: 600 }}>Stated Capacity:</span>
                    <p style={{ margin: '0.2rem 0 0', fontWeight: 800, fontSize: '1.1rem', color: '#1F191B' }}>
                      {selectedWarehouse.capacity > 0 ? selectedWarehouse.capacity.toLocaleString('en-IN') : 'N/A'} <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>units</span>
                    </p>
                  </div>

                  <div style={{ background: '#FAF7F5', padding: '0.85rem', borderRadius: '12px', border: '1px solid #F0E2E0' }}>
                    <span style={{ fontSize: '0.7rem', color: '#6B5E63', fontWeight: 600 }}>Current Stock:</span>
                    <p style={{ margin: '0.2rem 0 0', fontWeight: 800, fontSize: '1.1rem', color: '#B8505E' }}>
                      {selectedWarehouse.stock_units.toLocaleString('en-IN')} <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>units</span>
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 700 }}>
                    <span>Occupancy Rate</span>
                    <span style={{ color: selectedWarehouse.utilization_pct > 85 ? '#DC2626' : '#059669' }}>
                      {selectedWarehouse.utilization_pct}% Occupied
                    </span>
                  </div>
                  <div className="admin-progress-track" style={{ height: '8px' }}>
                    <div
                      className="admin-progress-fill"
                      style={{
                        width: `${Math.min(selectedWarehouse.utilization_pct, 100)}%`,
                        backgroundColor: selectedWarehouse.utilization_pct > 85 ? '#DC2626' : '#059669',
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Assigned Manager & Contact */}
              <div style={{ border: '1px solid #F0E2E0', borderRadius: '16px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
                <h5 style={{ margin: '0 0 0.25rem', fontSize: '0.9rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <User size={16} color="#B8505E" />
                  Assigned Facility Manager
                </h5>

                <div>
                  <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Manager Name:</span>
                  <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{selectedWarehouse.manager_name}</p>
                </div>

                {selectedWarehouse.manager_email && (
                  <div>
                    <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Email Address:</span>
                    <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{selectedWarehouse.manager_email}</p>
                  </div>
                )}

                {selectedWarehouse.manager_phone && (
                  <div>
                    <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Contact Number:</span>
                    <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{selectedWarehouse.manager_phone}</p>
                  </div>
                )}
              </div>

              {/* Operational Metrics */}
              <div style={{ border: '1px solid #F0E2E0', borderRadius: '16px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
                <h5 style={{ margin: '0 0 0.25rem', fontSize: '0.9rem', fontWeight: 800, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <ShoppingBag size={16} color="#B8505E" />
                  Operational Fulfillment Metrics
                </h5>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Catalog Product Titles:</span>
                    <p style={{ margin: 0, fontWeight: 700, color: '#1F191B' }}>{selectedWarehouse.product_count} Titles</p>
                  </div>

                  <div>
                    <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Low-Stock Products:</span>
                    <p style={{ margin: 0, fontWeight: 700, color: selectedWarehouse.low_stock_count > 0 ? '#DC2626' : '#059669' }}>
                      {selectedWarehouse.low_stock_count} Items
                    </p>
                  </div>

                  <div>
                    <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Active Orders:</span>
                    <p style={{ margin: 0, fontWeight: 700, color: '#2563EB' }}>{selectedWarehouse.active_orders_count} Orders</p>
                  </div>

                  {selectedWarehouse.created_at && (
                    <div>
                      <span style={{ fontSize: '0.72rem', color: '#6B5E63' }}>Date Provisioned:</span>
                      <p style={{ margin: 0, fontWeight: 600, color: '#1F191B' }}>{selectedWarehouse.created_at}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
