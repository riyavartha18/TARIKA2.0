import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Tag,
  ArrowRight,
  ChevronRight,
} from 'lucide-react';
import CategoryEditorialSection from '../../components/customer/CategoryEditorialSection';
import CustomerOffers from '../../components/customer/CustomerOffers';
import ProductCard from '../../components/customer/ProductCard';
import {
  SkeletonProductRow,
  SkeletonProductGrid,
  SkeletonCategoryPills,
} from '../../components/customer/Skeleton';
import { useAuth } from '../../auth/AuthContext';
import { getCategories, getNewArrivals, getSale } from '../../services/api';

// Fallback artwork when a database category carries no image of its own.
const FALLBACK_CATEGORY_IMAGE =
  'https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&auto=format&fit=crop&q=80';

export default function CustomerHome() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Each section owns its own loading flag so the page paints progressively:
  // a slow category/product request can no longer block the rest of the page.
  const [categories, setCategories] = useState([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [newArrivals, setNewArrivals] = useState([]);
  const [newArrivalsLoading, setNewArrivalsLoading] = useState(true);
  const [saleItems, setSaleItems] = useState([]);
  const [saleLoading, setSaleLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    // Fire each request independently and commit as it resolves instead of
    // awaiting Promise.all, so the first paint is not gated by the slowest call.
    getCategories()
      .then((res) => { if (alive && res.success) setCategories(res.categories || []); })
      .catch(() => {})
      .finally(() => { if (alive) setCategoriesLoading(false); });

    getNewArrivals(10)
      .then((res) => { if (alive && res.success) setNewArrivals(res.products || []); })
      .catch(() => {})
      .finally(() => { if (alive) setNewArrivalsLoading(false); });

    getSale(8)
      .then((res) => { if (alive && res.success) setSaleItems(res.products || []); })
      .catch(() => {})
      .finally(() => { if (alive) setSaleLoading(false); });

    return () => { alive = false; };
  }, []);

  const goToCategory = useCallback(
    (cat) => navigate(`/customer/shop?category=${encodeURIComponent(cat.slug || cat.name)}`),
    [navigate]
  );

  const firstName = (user?.full_name || user?.customer_name || '').trim().split(' ')[0];

  return (
    <div className="customer-home">
      {/* 1. PERSONALIZED WELCOME — compact, no external image (fast LCP) */}
      <section className="welcome-band">
        <div className="welcome-band-inner">
          <span className="welcome-eyebrow">
            <Sparkles size={13} /> Welcome back{firstName ? `, ${firstName}` : ''}
          </span>
          <h1 className="welcome-title">Your curated boutique wardrobe awaits.</h1>
          <p className="welcome-desc">
            Handcrafted gowns, structured co-ords and seasonal staples — picked to suit
            your story, with complimentary express delivery on every order.
          </p>
          <div className="welcome-actions">
            <Link to="/customer/shop" className="tarika-btn-primary">
              <span>Start Shopping</span>
              <ArrowRight size={16} />
            </Link>
            <Link to="/customer/new-in" className="tarika-btn-outline">
              Explore New In
            </Link>
          </div>
        </div>
      </section>

      {/* 2. PERSONALIZED OFFERS — from the latest RFM analysis + published campaigns */}
      <CustomerOffers />

      {/* 3. EXPLORE BY CATEGORY — editorial cards */}
      <CategoryEditorialSection />

      {/* 3. NEW ARRIVALS — single horizontal product rail */}
      <section aria-label="New arrivals">
        <div className="section-head">
          <div>
            <div className="section-eyebrow section-eyebrow--inline">
              <Sparkles size={14} />
              <span>Just arrived</span>
            </div>
            <h2 className="section-title">New In</h2>
          </div>
          <Link to="/customer/new-in" className="section-link">
            <span>View All</span>
            <ChevronRight size={16} />
          </Link>
        </div>

        {newArrivalsLoading ? (
          <SkeletonProductRow count={5} />
        ) : newArrivals.length ? (
          <div className="horizontal-scroll-row">
            {newArrivals.map((prod) => (
              <div key={prod.product_id || prod.id} className="scroll-snap-card" style={{ width: '230px' }}>
                <ProductCard product={prod} />
              </div>
            ))}
          </div>
        ) : (
          <p className="section-empty">No new arrivals to show yet.</p>
        )}
      </section>

      {/* 4. ON SALE — responsive product grid (distinct from New In) */}
      <section aria-label="Sale products">
        <div className="section-head">
          <div>
            <div className="section-eyebrow section-eyebrow--inline">
              <Tag size={14} />
              <span>Limited quantities</span>
            </div>
            <h2 className="section-title">Deals &amp; Reductions</h2>
          </div>
          <Link to="/customer/sale" className="section-link">
            <span>View All Sale</span>
            <ChevronRight size={16} />
          </Link>
        </div>

        {saleLoading ? (
          <SkeletonProductGrid count={8} />
        ) : saleItems.length ? (
          <div className="product-grid">
            {saleItems.map((prod) => (
              <ProductCard key={prod.product_id || prod.id} product={prod} />
            ))}
          </div>
        ) : (
          <p className="section-empty">No sale picks right now — check back soon.</p>
        )}
      </section>
    </div>
  );
}
