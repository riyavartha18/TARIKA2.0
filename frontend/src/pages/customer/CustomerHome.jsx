import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Tag,
  ArrowRight,
  ArrowDown,
  ChevronRight,
  Flower2,
  Shirt,
} from 'lucide-react';
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

      {/* 2. EXPLORE BY CATEGORY — editorial cards, data from the database */}
      <section className="cat-editorial-landing" aria-label="Product categories">
        {/* Editorial Masthead */}
        <div className="cat-editorial-masthead">
          <div className="cat-masthead-left">
            <div className="cat-masthead-eyebrow">EXPLORE BY STYLE</div>
            <h1 className="cat-masthead-main-title">CATEGORIES</h1>
            <p className="cat-masthead-script">Find your style. Tell your story..</p>
            <div className="cat-masthead-meta-tags">
              - CURATED LOOKS &nbsp;/&nbsp; TIMELESS TRENDS &nbsp;/&nbsp; MADE FOR YOU
            </div>
          </div>

          {/* Right Accent with Arched Floral Photo & Vertical Motto */}
          <div className="cat-masthead-right">
            <div className="cat-masthead-quote-wrap">
              <p className="cat-masthead-quote">
                More than just fashion,
                <br />
                it's a new chapter every day.
              </p>
              <div
                style={{
                  width: '32px',
                  height: '1.5px',
                  backgroundColor: '#D8727E',
                  margin: '4px 0',
                }}
              />
            </div>

            <div className="cat-masthead-arch-art">
              <img
                src="https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=400&auto=format&fit=crop&q=80"
                alt="Botanical floral silhouette"
                loading="lazy"
              />
            </div>

            <div className="cat-masthead-motto-stack">
              <span>WEAR</span>
              <span>EXPLORE</span>
              <span>EXPRESS</span>
              <span>REPEAT</span>
            </div>
          </div>
        </div>

        {/* Category cards rendered from the actual database categories */}
        {categoriesLoading ? (
          <SkeletonCategoryPills count={8} />
        ) : categories.length ? (
          <div className="cat-editorial-grid">
            {categories.map((cat, index) => {
              const catName = cat.category_name || cat.name;
              const countText =
                cat.product_count !== undefined
                  ? `${cat.product_count.toLocaleString('en-IN')} products in the collection`
                  : 'Explore the collection';

              return (
                <div
                  key={cat.category_id || cat.id || catName}
                  className="cat-card-interactive"
                  onClick={() => goToCategory(cat)}
                  style={{
                    animationDelay: `${index * 80}ms`,
                    borderColor: 'rgba(216, 114, 126, 0.2)',
                    boxShadow: '0 6px 25px rgba(184, 80, 94, 0.05)',
                  }}
                >
                  <div
                    className={`cat-split-layout ${
                      index % 2 === 0 ? 'is-media-right' : 'is-media-left'
                    }`}
                  >
                    {/* Media Wrapper */}
                    <div className="cat-split-media">
                      <img
                        src={cat.image || FALLBACK_CATEGORY_IMAGE}
                        alt={catName}
                        loading="lazy"
                      />
                    </div>

                    {/* Info Wrapper */}
                    <div className="cat-split-info">
                      <div className="cat-split-info-top">
                        <h3 className="cat-split-title">{catName.toUpperCase()}</h3>
                        <p className="cat-split-subtitle">{countText}</p>
                        <div className="cat-split-action">
                          <div className="cat-circle-arrow-btn">
                            <ArrowRight size={14} />
                          </div>
                        </div>
                      </div>
                      <span className="cat-split-bottom-tag">
                        {cat.product_count !== undefined
                          ? `${cat.product_count.toLocaleString('en-IN')}`
                          : 'EXPLORE'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="section-empty">Categories are unavailable right now.</p>
        )}

        {/* Affirmation Quality Strip */}
        <div className="cat-features-affirmation-strip">
          <div className="cat-affirmation-item">
            <Flower2 size={18} color="#D8727E" />
            <span>Every category. A new you.</span>
          </div>

          <div className="cat-affirmation-divider" />

          <div className="cat-affirmation-item">
            <Shirt size={18} color="#D8727E" />
            <span>Curated for your next favorite look.</span>
          </div>

          <div className="cat-affirmation-divider" />

          <div className="cat-affirmation-item">
            <Sparkles size={18} color="#D8727E" />
            <span>Fashion that feels like you.</span>
          </div>

          <div className="cat-affirmation-brand">
            TARIKA — <em>More than fashion</em>
          </div>
        </div>

        {/* Transition Indicator Badge */}
        <div className="cat-transition-indicator">
          <span>Smooth transition animation</span>
          <ArrowDown size={14} />
        </div>
      </section>

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
