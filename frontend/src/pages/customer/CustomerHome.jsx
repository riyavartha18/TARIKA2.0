import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Tag,
  ArrowRight,
  ChevronRight,
} from 'lucide-react';
import ExclusiveOffersCarousel from '../../components/customer/ExclusiveOffersCarousel';
import TrendingFashionCarousel from '../../components/customer/TrendingFashionCarousel';
import SpinRewardsWheelSection from '../../components/customer/SpinRewardsWheelSection';
import CategoryEditorialSection from '../../components/customer/CategoryEditorialSection';
import ProductCard from '../../components/customer/ProductCard';
import PersonalizedSection from '../../components/customer/PersonalizedSection';
import {
  SkeletonProductRow,
  SkeletonProductGrid,
} from '../../components/customer/Skeleton';
import { useAuth } from '../../auth/AuthContext';
import { getNewArrivals, getSale } from '../../services/api';

export default function CustomerHome() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [newArrivals, setNewArrivals] = useState([]);
  const [newArrivalsLoading, setNewArrivalsLoading] = useState(true);
  const [saleItems, setSaleItems] = useState([]);
  const [saleLoading, setSaleLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    getNewArrivals(20)
      .then((res) => { if (alive && res.success) setNewArrivals(res.products || []); })
      .finally(() => { if (alive) setNewArrivalsLoading(false); });

    getSale(8)
      .then((res) => { if (alive && res.success) setSaleItems(res.products || []); })
      .catch(() => {})
      .finally(() => { if (alive) setSaleLoading(false); });

    return () => { alive = false; };
  }, []);

  const firstName = (user?.full_name || user?.customer_name || 'Riya').trim().split(' ')[0];

  return (
    <div className="customer-home">
      {/* 1. WELCOME HERO BANNER — with boutique clothing rack & lilies on the right */}
      <section className="welcome-band" style={{ marginBottom: '2.5rem' }}>
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

        {/* Right Boutique Clothing Rack Display */}
        <div className="welcome-band-media">
          <img
            src="/images/tarika_hero_rack.jpg"
            alt="Curated boutique wardrobe rack with gowns and lilies"
          />
        </div>
      </section>

      {/* 2. PERSONALIZED EXCLUSIVE OFFERS CAROUSEL */}
      <ExclusiveOffersCarousel />

      {/* 3. DYNAMIC FASHION PRODUCT CAROUSEL ("TRENDING IN TARIKA") WITH CATEGORY FILTERS */}
      <TrendingFashionCarousel />

      {/* 4. REWARDS WHEEL: CENTRED "SPIN & EARN COINS" SECTION */}
      <SpinRewardsWheelSection />

      {/* 5. EXPLORE BY CATEGORY — editorial cards */}
      <CategoryEditorialSection />

      {/* 6. PERSONALIZED RECOMMENDATIONS — Customer History */}
      <PersonalizedSection />

      {/* 7. NEW ARRIVALS — curated horizontal product rail */}
      <section aria-label="New arrivals" style={{ marginBottom: '2.75rem' }}>
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
            {newArrivals.slice(0, 10).map((prod) => (
              <div key={prod.product_id || prod.id} className="scroll-snap-card" style={{ width: '230px' }}>
                <ProductCard product={prod} />
              </div>
            ))}
          </div>
        ) : (
          <p className="section-empty">No new arrivals to show yet.</p>
        )}
      </section>

      {/* 8. ON SALE — Deals & Reductions */}
      <section aria-label="Sale products" style={{ marginBottom: '2.5rem' }}>
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
