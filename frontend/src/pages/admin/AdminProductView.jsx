import React, { useState, useEffect, useCallback } from 'react';
import {
  Package,
  Layers,
  CheckCircle2,
  AlertTriangle,
  Search,
  Filter,
  Plus,
  Eye,
  Edit,
  RefreshCw,
  X,
  Tag,
  Warehouse as WarehouseIcon,
  Check,
  TrendingDown,
  Sparkles,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { getAdminProductList, createAdminProduct, updateWarehouseProduct } from '../../services/api';

export default function AdminProductView() {
  const { token } = useAuth();

  // Database-backed catalog states
  const [metrics, setMetrics] = useState({
    total_products: 0,
    total_categories: 0,
    in_stock_products: 0,
    low_stock_products: 0,
  });
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [stockStatus, setStockStatus] = useState('ALL');

  // Active Modals
  const [selectedProduct, setSelectedProduct] = useState(null); // Detail Inspection Drawer
  const [editingProduct, setEditingProduct] = useState(null); // Edit Modal
  const [showCreateModal, setShowCreateModal] = useState(false); // Create Modal

  // Form feedback states
  const [actionSuccess, setActionSuccess] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit Form State
  const [editForm, setEditForm] = useState({
    product_name: '',
    description: '',
    base_price: '',
    selling_price: '',
    stock_quantity: '',
    color: '',
    size: '',
    material: '',
    gender: 'Unisex',
    is_active: true,
  });

  // Create Form State
  const [createForm, setCreateForm] = useState({
    product_name: '',
    category_id: '',
    sku: '',
    selling_price: '',
    base_price: '',
    cost_price: '',
    initial_stock: '10',
    description: '',
    gender: 'Women',
    color: '',
    size: '',
    material: '',
    is_active: true,
  });

  // Fetch REAL database product catalog data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const activeToken = token || localStorage.getItem('iras_token');
    const res = await getAdminProductList(activeToken, {
      search: searchTerm,
      category: selectedCategory,
      stock_status: stockStatus,
    });

    if (res.success) {
      setMetrics(res.metrics || {});
      setCategories(res.categories || []);
      setProducts(res.products || []);
    } else {
      setError(res.error || 'Failed to load product catalog data.');
    }
    setLoading(false);
  }, [token, searchTerm, selectedCategory, stockStatus]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Open Edit Modal
  const handleOpenEdit = (product) => {
    setEditingProduct(product);
    setEditForm({
      product_name: product.product_name || '',
      description: product.description || '',
      base_price: product.base_price || product.selling_price || 0,
      selling_price: product.selling_price || 0,
      stock_quantity: product.total_stock !== undefined ? product.total_stock : '',
      color: product.color || '',
      size: product.size || '',
      material: product.material || '',
      gender: product.gender || 'Unisex',
      is_active: product.is_active !== undefined ? product.is_active : true,
    });
    setActionError(null);
  };

  // Submit Edit Form
  const handleUpdateProduct = async (e) => {
    e.preventDefault();
    if (!editingProduct) return;
    setIsSubmitting(true);
    setActionError(null);

    const activeToken = token || localStorage.getItem('iras_token');
    const payload = {
      product_name: editForm.product_name,
      description: editForm.description,
      base_price: parseInt(editForm.base_price, 10) || 0,
      selling_price: parseInt(editForm.selling_price, 10) || 0,
      stock_quantity: editForm.stock_quantity !== '' ? parseInt(editForm.stock_quantity, 10) : undefined,
      color: editForm.color,
      size: editForm.size,
      material: editForm.material,
      gender: editForm.gender,
      is_active: editForm.is_active,
    };

    const res = await updateWarehouseProduct(editingProduct.product_id, payload, activeToken);

    if (res.success) {
      setActionSuccess(`Product "${editForm.product_name}" updated successfully.`);
      setEditingProduct(null);
      fetchData();
      setTimeout(() => setActionSuccess(null), 4000);
    } else {
      setActionError(res.error || 'Failed to update product.');
    }
    setIsSubmitting(false);
  };

  // Open Create Modal
  const handleOpenCreate = () => {
    setCreateForm({
      product_name: '',
      category_id: categories.length > 0 ? categories[0].category_id : '',
      sku: '',
      selling_price: '',
      base_price: '',
      cost_price: '',
      initial_stock: '10',
      description: '',
      gender: 'Women',
      color: '',
      size: '',
      material: '',
      is_active: true,
    });
    setActionError(null);
    setShowCreateModal(true);
  };

  // Submit Create Form
  const handleCreateProduct = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setActionError(null);

    const activeToken = token || localStorage.getItem('iras_token');
    const payload = {
      ...createForm,
      selling_price: parseFloat(createForm.selling_price),
      base_price: createForm.base_price ? parseFloat(createForm.base_price) : parseFloat(createForm.selling_price),
      cost_price: createForm.cost_price ? parseFloat(createForm.cost_price) : 0,
      initial_stock: parseInt(createForm.initial_stock, 10) || 0,
    };

    const res = await createAdminProduct(activeToken, payload);

    if (res.success) {
      setActionSuccess(`Product "${createForm.product_name}" created successfully.`);
      setShowCreateModal(false);
      fetchData();
      setTimeout(() => setActionSuccess(null), 4000);
    } else {
      setActionError(res.error || 'Failed to create product.');
    }
    setIsSubmitting(false);
  };

  // Currency formatting helper
  const formatCurrency = (val) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val || 0);
  };

  return (
    <div>
      {/* 1. Header Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.75rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span style={{ padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.72rem', fontWeight: 700, backgroundColor: '#FBF1F0', color: '#B8505E', border: '1px solid #F0CFCD' }}>
              Retail Catalog
            </span>
            <span style={{ fontSize: '0.78rem', color: '#9E8F94' }}>System-Wide Product Management</span>
          </div>
          <h1 style={{ fontFamily: "var(--font-serif, 'Playfair Display', serif)", fontSize: '1.85rem', fontWeight: 700, color: '#1F191B', margin: 0 }}>
            Product &amp; Catalog Management
          </h1>
          <p style={{ color: '#6B5E63', fontSize: '0.9rem', margin: '0.35rem 0 0' }}>
            Oversee retail products, database categories, real-time inventory levels, pricing, and product status across all channels.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={fetchData}
            disabled={loading}
            style={{
              padding: '0.65rem 1.1rem',
              borderRadius: '12px',
              border: '1px solid #F0E2E0',
              backgroundColor: '#FFFFFF',
              color: '#1F191B',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              opacity: loading ? 0.6 : 1,
            }}
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          <button
            onClick={handleOpenCreate}
            style={{
              padding: '0.65rem 1.25rem',
              borderRadius: '12px',
              border: 'none',
              backgroundColor: '#8E3642',
              color: '#FFFFFF',
              fontSize: '0.85rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 4px 14px rgba(142, 54, 66, 0.25)',
            }}
          >
            <Plus size={16} />
            <span>Add Product</span>
          </button>
        </div>
      </div>

      {/* Success Banner */}
      {actionSuccess && (
        <div style={{ padding: '0.9rem 1.25rem', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669', borderRadius: '14px', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyBetween: 'space-between', fontSize: '0.875rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircle2 size={18} color="#059669" />
            <span style={{ fontWeight: 600 }}>{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} style={{ background: 'none', border: 'none', color: '#059669', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div style={{ padding: '0.9rem 1.25rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', borderRadius: '14px', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyBetween: 'space-between', fontSize: '0.875rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={18} color="#DC2626" />
            <span style={{ fontWeight: 600 }}>{error}</span>
          </div>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: '#DC2626', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* 2. Real Database Summary KPI Cards */}
      <div className="admin-metrics-grid">
        {/* Total Products */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon">
              <Package size={22} />
            </div>
            <span className="admin-metric-status">Catalog</span>
          </div>
          <div className="admin-metric-title">Total Products</div>
          <div className="admin-metric-val">
            {loading ? '...' : metrics.total_products?.toLocaleString() || '0'}
          </div>
          <div className="admin-metric-subtext">Active Database Items</div>
        </div>

        {/* Total Categories */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon" style={{ backgroundColor: '#FFFBEB', color: '#D97706' }}>
              <Layers size={22} />
            </div>
            <span className="admin-metric-status">Taxonomy</span>
          </div>
          <div className="admin-metric-title">Total Categories</div>
          <div className="admin-metric-val">
            {loading ? '...' : metrics.total_categories?.toLocaleString() || '0'}
          </div>
          <div className="admin-metric-subtext">Database Categories</div>
        </div>

        {/* In Stock Products */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon" style={{ backgroundColor: '#ECFDF5', color: '#059669' }}>
              <CheckCircle2 size={22} />
            </div>
            <span className="admin-metric-status">Available</span>
          </div>
          <div className="admin-metric-title">In Stock Products</div>
          <div className="admin-metric-val" style={{ color: '#059669' }}>
            {loading ? '...' : metrics.in_stock_products?.toLocaleString() || '0'}
          </div>
          <div className="admin-metric-subtext">Total Stock &gt; 0 Units</div>
        </div>

        {/* Low Stock Products */}
        <div className="admin-metric-card">
          <div className="admin-metric-top">
            <div className="admin-metric-icon" style={{ backgroundColor: '#FEF2F2', color: '#DC2626' }}>
              <AlertTriangle size={22} />
            </div>
            <span className="admin-metric-status" style={{ backgroundColor: '#FEF2F2', color: '#DC2626', borderColor: '#FECACA' }}>
              Attention
            </span>
          </div>
          <div className="admin-metric-title">Low Stock Products</div>
          <div className="admin-metric-val" style={{ color: '#DC2626' }}>
            {loading ? '...' : metrics.low_stock_products?.toLocaleString() || '0'}
          </div>
          <div className="admin-metric-subtext">Stock &le; 5 Units</div>
        </div>
      </div>

      {/* 3. Search & Filter Bar */}
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between', marginBottom: '1.5rem', background: '#FFFFFF', padding: '1rem 1.25rem', borderRadius: '16px', border: '1px solid #F0E2E0', boxShadow: 'var(--shadow-soft)' }}>
        {/* Search */}
        <div style={{ position: 'relative', flex: '1', minWidth: '260px' }}>
          <Search size={16} color="#9E8F94" style={{ position: 'absolute', left: '0.85rem', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            placeholder="Search products by name, SKU, color, material..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '0.65rem 0.85rem 0.65rem 2.4rem',
              borderRadius: '10px',
              border: '1px solid #F0E2E0',
              backgroundColor: '#FFFFFF',
              fontSize: '0.875rem',
              color: '#1F191B',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#9E8F94', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Category Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Filter size={15} color="#9E8F94" />
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{
                padding: '0.65rem 0.85rem',
                borderRadius: '10px',
                border: '1px solid #F0E2E0',
                backgroundColor: '#FFFFFF',
                fontSize: '0.875rem',
                fontWeight: 600,
                color: '#1F191B',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Categories ({categories.length})</option>
              {categories.map((c) => (
                <option key={c.category_id} value={c.category_id}>
                  {c.category_name}
                </option>
              ))}
            </select>
          </div>

          {/* Stock Status Filter */}
          <select
            value={stockStatus}
            onChange={(e) => setStockStatus(e.target.value)}
            style={{
              padding: '0.65rem 0.85rem',
              borderRadius: '10px',
              border: '1px solid #F0E2E0',
              backgroundColor: '#FFFFFF',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: '#1F191B',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            <option value="ALL">All Stock Statuses</option>
            <option value="IN_STOCK">In Stock</option>
            <option value="LOW_STOCK">Low Stock (&le; 5)</option>
            <option value="OUT_OF_STOCK">Out of Stock</option>
          </select>
        </div>
      </div>

      {/* 4. Product Table */}
      <div className="admin-card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '3.5rem 1rem', textAlign: 'center' }}>
            <RefreshCw size={28} color="#8E3642" className="animate-spin" style={{ margin: '0 auto 0.75rem' }} />
            <p style={{ color: '#6B5E63', fontWeight: 600, margin: 0 }}>Loading retail product catalog...</p>
          </div>
        ) : products.length === 0 ? (
          <div style={{ padding: '3.5rem 1rem', textAlign: 'center', color: '#6B5E63' }}>
            <Package size={38} color="#9E8F94" style={{ margin: '0 auto 0.75rem' }} />
            <h4 style={{ margin: '0 0 0.35rem', color: '#1F191B', fontFamily: 'var(--font-serif)' }}>No Products Found</h4>
            <p style={{ margin: 0, fontSize: '0.85rem' }}>
              {searchTerm || selectedCategory !== 'ALL' || stockStatus !== 'ALL'
                ? 'Try adjusting your search criteria or category filters.'
                : 'No products are currently available in the database.'}
            </p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Product Item</th>
                  <th>Category</th>
                  <th>Price</th>
                  <th>System Stock</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((prod) => (
                  <tr key={prod.product_id}>
                    {/* Item & Image */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                        <div style={{ width: '42px', height: '42px', borderRadius: '10px', backgroundColor: '#FAF7F5', border: '1px solid #F0E2E0', overflow: 'hidden', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          {prod.image ? (
                            <img
                              src={prod.image}
                              alt={prod.product_name}
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              onError={(e) => { e.target.style.display = 'none'; }}
                            />
                          ) : (
                            <Package size={20} color="#9E8F94" />
                          )}
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, color: '#1F191B', lineHeight: '1.2' }}>
                            {prod.product_name}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.2rem', fontSize: '0.72rem', color: '#6B5E63' }}>
                            <code style={{ background: '#FAF7F5', padding: '0.1rem 0.35rem', borderRadius: '4px', border: '1px solid #F0E2E0', fontFamily: 'monospace' }}>
                              {prod.sku || 'NO-SKU'}
                            </code>
                            {prod.color && <span>• {prod.color}</span>}
                            {prod.size && <span>• Size {prod.size}</span>}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Category */}
                    <td>
                      <span style={{ padding: '0.25rem 0.65rem', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 600, backgroundColor: '#FAF7F5', color: '#1F191B', border: '1px solid #F0E2E0', display: 'inline-block' }}>
                        {prod.category_name}
                      </span>
                    </td>

                    {/* Price */}
                    <td>
                      <div style={{ fontWeight: 700, color: '#1F191B' }}>
                        {formatCurrency(prod.selling_price)}
                      </div>
                      {prod.base_price > prod.selling_price && (
                        <div style={{ fontSize: '0.72rem', color: '#9E8F94', textDecoration: 'line-through' }}>
                          {formatCurrency(prod.base_price)}
                        </div>
                      )}
                    </td>

                    {/* System Stock */}
                    <td>
                      {prod.total_stock === 0 ? (
                        <span className="admin-status-badge admin-status-cancelled">
                          Out of Stock (0)
                        </span>
                      ) : prod.is_low_stock ? (
                        <span className="admin-status-badge admin-status-pending" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <AlertTriangle size={12} color="#D97706" />
                          Low Stock ({prod.total_stock})
                        </span>
                      ) : (
                        <span className="admin-status-badge admin-status-delivered">
                          In Stock ({prod.total_stock})
                        </span>
                      )}
                    </td>

                    {/* Active Status */}
                    <td>
                      {prod.is_active ? (
                        <span className="admin-status-badge admin-status-delivered">
                          Active
                        </span>
                      ) : (
                        <span className="admin-status-badge" style={{ backgroundColor: '#F3F4F6', color: '#6B7280', border: '1px solid #E5E7EB' }}>
                          Inactive
                        </span>
                      )}
                    </td>

                    {/* Actions */}
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.4rem' }}>
                        <button
                          onClick={() => setSelectedProduct(prod)}
                          style={{ padding: '0.4rem 0.6rem', borderRadius: '8px', border: '1px solid #F0E2E0', backgroundColor: '#FFFFFF', color: '#6B5E63', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.78rem', fontWeight: 600 }}
                          title="View Product Details"
                        >
                          <Eye size={14} />
                          <span>Details</span>
                        </button>
                        <button
                          onClick={() => handleOpenEdit(prod)}
                          style={{ padding: '0.4rem 0.6rem', borderRadius: '8px', border: '1px solid #F0CFCD', backgroundColor: '#FBF1F0', color: '#B8505E', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.78rem', fontWeight: 700 }}
                          title="Edit Product"
                        >
                          <Edit size={14} />
                          <span>Edit</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Product Detail Inspection Drawer */}
      {selectedProduct && (
        <>
          <div
            onClick={() => setSelectedProduct(null)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              backgroundColor: 'rgba(31, 25, 27, 0.55)',
              backdropFilter: 'blur(4px)',
            }}
          />

          <div
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 201,
              width: 'min(520px, 100vw)', backgroundColor: '#FFFFFF',
              boxShadow: '-8px 0 60px rgba(31, 25, 27, 0.18)',
              display: 'flex', flexDirection: 'column', overflowY: 'auto',
            }}
          >
            <div style={{ padding: '1.25rem 1.5rem', backgroundColor: '#FAF7F5', borderBottom: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                Product Specifications
              </h3>
              <button
                onClick={() => setSelectedProduct(null)}
                style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FFFFFF', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Product Header & Image */}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', background: '#FBF1F0', padding: '1.25rem', borderRadius: '16px', border: '1px solid #F0CFCD' }}>
                <div style={{ width: '80px', height: '80px', borderRadius: '12px', backgroundColor: '#FFFFFF', border: '1px solid #F0E2E0', overflow: 'hidden', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {selectedProduct.image ? (
                    <img
                      src={selectedProduct.image}
                      alt={selectedProduct.product_name}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <Package size={32} color="#9E8F94" />
                  )}
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#B8505E', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {selectedProduct.category_name}
                  </span>
                  <h4 style={{ margin: '0.2rem 0', fontSize: '1.1rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                    {selectedProduct.product_name}
                  </h4>
                  <p style={{ margin: 0, fontSize: '0.78rem', color: '#6B5E63', fontFamily: 'monospace' }}>
                    SKU: {selectedProduct.sku}
                  </p>
                </div>
              </div>

              {/* Attributes Grid */}
              <div style={{ border: '1px solid #F0E2E0', borderRadius: '16px', padding: '1.25rem', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', fontSize: '0.85rem' }}>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Selling Price</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 800, color: '#1F191B', fontSize: '1.1rem' }}>{formatCurrency(selectedProduct.selling_price)}</p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Base Price (MRP)</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#6B5E63' }}>{formatCurrency(selectedProduct.base_price)}</p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Gender</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B' }}>{selectedProduct.gender || 'Unisex'}</p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Color</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B' }}>{selectedProduct.color || 'Standard'}</p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Size</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B' }}>{selectedProduct.size || 'Standard'}</p>
                </div>
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Material</span>
                  <p style={{ margin: '0.2rem 0 0', fontWeight: 700, color: '#1F191B' }}>{selectedProduct.material || 'Standard'}</p>
                </div>
              </div>

              {/* Description */}
              {selectedProduct.description && (
                <div>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Description</span>
                  <p style={{ margin: '0.35rem 0 0', padding: '0.85rem', backgroundColor: '#FAF7F5', borderRadius: '12px', border: '1px solid #F0E2E0', fontSize: '0.85rem', color: '#1F191B', lineHeight: '1.5' }}>
                    {selectedProduct.description}
                  </p>
                </div>
              )}

              {/* Warehouse Inventory Breakdown */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyBetween: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#8E3642', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Warehouse Inventory Breakdown
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#1F191B' }}>
                    Total: {selectedProduct.total_stock} units
                  </span>
                </div>

                {selectedProduct.warehouse_inventory && selectedProduct.warehouse_inventory.length > 0 ? (
                  <div style={{ border: '1px solid #F0E2E0', borderRadius: '12px', overflow: 'hidden' }}>
                    <table className="admin-table" style={{ fontSize: '0.8rem' }}>
                      <thead>
                        <tr>
                          <th>Warehouse Facility</th>
                          <th style={{ textAlign: 'right' }}>Stock Qty</th>
                          <th style={{ textAlign: 'right' }}>Reorder Level</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedProduct.warehouse_inventory.map((wh, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 700 }}>{wh.warehouse_name}</td>
                            <td style={{ textAlign: 'right', fontWeight: 800 }}>{wh.stock_quantity}</td>
                            <td style={{ textAlign: 'right', color: '#6B5E63' }}>{wh.reorder_level}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ margin: 0, padding: '0.85rem', backgroundColor: '#FAF7F5', borderRadius: '12px', border: '1px solid #F0E2E0', fontSize: '0.8rem', color: '#6B5E63', fontStyle: 'italic' }}>
                    No warehouse inventory allocation rows recorded for this product yet.
                  </p>
                )}
              </div>
            </div>

            <div style={{ padding: '1.25rem 1.5rem', backgroundColor: '#FAF7F5', borderTop: '1px solid #F0E2E0', display: 'flex', justifyBetween: 'space-between', gap: '0.75rem' }}>
              <button
                onClick={() => {
                  const p = selectedProduct;
                  setSelectedProduct(null);
                  handleOpenEdit(p);
                }}
                style={{ flex: 1, padding: '0.65rem', borderRadius: '10px', border: 'none', backgroundColor: '#8E3642', color: '#FFFFFF', fontWeight: 700, cursor: 'pointer', fontSize: '0.85rem' }}
              >
                Edit Product
              </button>
              <button
                onClick={() => setSelectedProduct(null)}
                style={{ padding: '0.65rem 1.25rem', borderRadius: '10px', border: '1px solid #F0E2E0', backgroundColor: '#FFFFFF', color: '#1F191B', fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem' }}
              >
                Close
              </button>
            </div>
          </div>
        </>
      )}

      {/* 6. Product Edit Modal */}
      {editingProduct && (
        <>
          <div
            onClick={() => setEditingProduct(null)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              backgroundColor: 'rgba(31, 25, 27, 0.55)',
              backdropFilter: 'blur(4px)',
            }}
          />

          <div
            style={{
              position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 201,
              width: 'min(580px, 92vw)', maxHeight: '88vh', backgroundColor: '#FFFFFF',
              borderRadius: '20px', boxShadow: '0 20px 60px rgba(31, 25, 27, 0.3)',
              display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}
          >
            <div style={{ padding: '1.25rem 1.5rem', backgroundColor: '#FAF7F5', borderBottom: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                  Edit Product Details
                </h3>
                <p style={{ margin: '0.15rem 0 0', fontSize: '0.78rem', color: '#6B5E63', fontFamily: 'monospace' }}>
                  SKU: {editingProduct.sku}
                </p>
              </div>
              <button
                onClick={() => setEditingProduct(null)}
                style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FFFFFF', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleUpdateProduct} style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.1rem', fontSize: '0.85rem' }}>
              {actionError && (
                <div style={{ padding: '0.75rem 1rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', borderRadius: '10px', fontWeight: 600 }}>
                  {actionError}
                </div>
              )}

              {/* Product Name */}
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Product Name *</label>
                <input
                  type="text"
                  required
                  value={editForm.product_name}
                  onChange={(e) => setEditForm({ ...editForm, product_name: e.target.value })}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                />
              </div>

              {/* Prices */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Selling Price (₹) *</label>
                  <input
                    type="number"
                    required
                    min="0"
                    value={editForm.selling_price}
                    onChange={(e) => setEditForm({ ...editForm, selling_price: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Base Price (MRP ₹)</label>
                  <input
                    type="number"
                    min="0"
                    value={editForm.base_price}
                    onChange={(e) => setEditForm({ ...editForm, base_price: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                  />
                </div>
              </div>

              {/* Stock & Gender */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>System Stock Quantity</label>
                  <input
                    type="number"
                    min="0"
                    value={editForm.stock_quantity}
                    onChange={(e) => setEditForm({ ...editForm, stock_quantity: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Gender</label>
                  <select
                    value={editForm.gender}
                    onChange={(e) => setEditForm({ ...editForm, gender: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem', background: '#FFF' }}
                  >
                    <option value="Women">Women</option>
                    <option value="Men">Men</option>
                    <option value="Unisex">Unisex</option>
                    <option value="Kids">Kids</option>
                  </select>
                </div>
              </div>

              {/* Color, Size, Material */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Color</label>
                  <input
                    type="text"
                    value={editForm.color}
                    onChange={(e) => setEditForm({ ...editForm, color: e.target.value })}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.8rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Size</label>
                  <input
                    type="text"
                    value={editForm.size}
                    onChange={(e) => setEditForm({ ...editForm, size: e.target.value })}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.8rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Material</label>
                  <input
                    type="text"
                    value={editForm.material}
                    onChange={(e) => setEditForm({ ...editForm, material: e.target.value })}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.8rem' }}
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Description</label>
                <textarea
                  rows="3"
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem', fontFamily: 'inherit' }}
                ></textarea>
              </div>

              {/* Active Toggle */}
              <div style={{ display: 'flex', alignItems: 'center', justifyBetween: 'space-between', padding: '0.85rem', backgroundColor: '#FAF7F5', borderRadius: '12px', border: '1px solid #F0E2E0' }}>
                <div>
                  <span style={{ fontWeight: 700, color: '#1F191B', display: 'block' }}>Active Catalog Status</span>
                  <span style={{ fontSize: '0.78rem', color: '#6B5E63' }}>Product visibility on customer shopping channels</span>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                    style={{ width: '18px', height: '18px', accentColor: '#8E3642' }}
                  />
                  <span style={{ fontWeight: 700, color: editForm.is_active ? '#059669' : '#6B5E63' }}>
                    {editForm.is_active ? 'Active' : 'Inactive'}
                  </span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyBetween: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setEditingProduct(null)}
                  style={{ padding: '0.65rem 1.25rem', borderRadius: '10px', border: '1px solid #F0E2E0', backgroundColor: '#FFFFFF', color: '#1F191B', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{ padding: '0.65rem 1.5rem', borderRadius: '10px', border: 'none', backgroundColor: '#8E3642', color: '#FFFFFF', fontWeight: 700, cursor: 'pointer', opacity: isSubmitting ? 0.6 : 1 }}
                >
                  {isSubmitting ? 'Saving Changes...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </>
      )}

      {/* 7. Product Creation Modal */}
      {showCreateModal && (
        <>
          <div
            onClick={() => setShowCreateModal(false)}
            style={{
              position: 'fixed', inset: 0, zIndex: 200,
              backgroundColor: 'rgba(31, 25, 27, 0.55)',
              backdropFilter: 'blur(4px)',
            }}
          />

          <div
            style={{
              position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 201,
              width: 'min(580px, 92vw)', maxHeight: '88vh', backgroundColor: '#FFFFFF',
              borderRadius: '20px', boxShadow: '0 20px 60px rgba(31, 25, 27, 0.3)',
              display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}
          >
            <div style={{ padding: '1.25rem 1.5rem', backgroundColor: '#FAF7F5', borderBottom: '1px solid #F0E2E0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: '#1F191B', fontFamily: 'var(--font-serif)' }}>
                  Add New Retail Product
                </h3>
                <p style={{ margin: '0.15rem 0 0', fontSize: '0.78rem', color: '#6B5E63' }}>
                  Create a new item in the TARIKA database catalog
                </p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid #F0E2E0', background: '#FFFFFF', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateProduct} style={{ padding: '1.5rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.1rem', fontSize: '0.85rem' }}>
              {actionError && (
                <div style={{ padding: '0.75rem 1rem', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626', borderRadius: '10px', fontWeight: 600 }}>
                  {actionError}
                </div>
              )}

              {/* Product Name */}
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Product Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Silk Embroidered Kurta"
                  value={createForm.product_name}
                  onChange={(e) => setCreateForm({ ...createForm, product_name: e.target.value })}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                />
              </div>

              {/* Category & SKU */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Category *</label>
                  <select
                    required
                    value={createForm.category_id}
                    onChange={(e) => setCreateForm({ ...createForm, category_id: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem', background: '#FFF' }}
                  >
                    <option value="" disabled>Select Category</option>
                    {categories.map((c) => (
                      <option key={c.category_id} value={c.category_id}>
                        {c.category_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>SKU (Identifier)</label>
                  <input
                    type="text"
                    placeholder="Auto-generated if left blank"
                    value={createForm.sku}
                    onChange={(e) => setCreateForm({ ...createForm, sku: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem', fontFamily: 'monospace' }}
                  />
                </div>
              </div>

              {/* Prices */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Selling Price (₹) *</label>
                  <input
                    type="number"
                    required
                    min="0"
                    placeholder="1499"
                    value={createForm.selling_price}
                    onChange={(e) => setCreateForm({ ...createForm, selling_price: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Base Price (MRP ₹)</label>
                  <input
                    type="number"
                    min="0"
                    placeholder="1999"
                    value={createForm.base_price}
                    onChange={(e) => setCreateForm({ ...createForm, base_price: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                  />
                </div>
              </div>

              {/* Stock & Gender */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Initial Stock Units</label>
                  <input
                    type="number"
                    min="0"
                    value={createForm.initial_stock}
                    onChange={(e) => setCreateForm({ ...createForm, initial_stock: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Gender</label>
                  <select
                    value={createForm.gender}
                    onChange={(e) => setCreateForm({ ...createForm, gender: e.target.value })}
                    style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem', background: '#FFF' }}
                  >
                    <option value="Women">Women</option>
                    <option value="Men">Men</option>
                    <option value="Unisex">Unisex</option>
                    <option value="Kids">Kids</option>
                  </select>
                </div>
              </div>

              {/* Color, Size, Material */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Color</label>
                  <input
                    type="text"
                    placeholder="Emerald Green"
                    value={createForm.color}
                    onChange={(e) => setCreateForm({ ...createForm, color: e.target.value })}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.8rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Size</label>
                  <input
                    type="text"
                    placeholder="M / L / XL"
                    value={createForm.size}
                    onChange={(e) => setCreateForm({ ...createForm, size: e.target.value })}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.8rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Material</label>
                  <input
                    type="text"
                    placeholder="Chanderi Silk"
                    value={createForm.material}
                    onChange={(e) => setCreateForm({ ...createForm, material: e.target.value })}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.8rem' }}
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#1F191B', marginBottom: '0.35rem' }}>Description</label>
                <textarea
                  rows="3"
                  placeholder="Enter detailed product description..."
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '10px', border: '1px solid #F0E2E0', outline: 'none', boxSizing: 'border-box', fontSize: '0.875rem', fontFamily: 'inherit' }}
                ></textarea>
              </div>

              <div style={{ display: 'flex', justifyBetween: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ padding: '0.65rem 1.25rem', borderRadius: '10px', border: '1px solid #F0E2E0', backgroundColor: '#FFFFFF', color: '#1F191B', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{ padding: '0.65rem 1.5rem', borderRadius: '10px', border: 'none', backgroundColor: '#8E3642', color: '#FFFFFF', fontWeight: 700, cursor: 'pointer', opacity: isSubmitting ? 0.6 : 1 }}
                >
                  {isSubmitting ? 'Creating Product...' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </>
      )}
    </div>
  );
}
