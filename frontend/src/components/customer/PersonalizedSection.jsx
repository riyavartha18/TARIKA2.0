import React, { useState, useEffect } from 'react';
import { Sparkles, Heart, RefreshCw, ShoppingBag, ArrowRight } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { getPersonalizedRecommendations } from '../../services/api';
import ProductCard from './ProductCard';
import { Link } from 'react-router-dom';

export default function PersonalizedSection() {
  const { user, token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    if (token) {
      getPersonalizedRecommendations(token)
        .then((res) => {
          if (alive && res.success) {
            setData(res);
          }
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    } else {
      setLoading(false);
    }
    return () => {
      alive = false;
    };
  }, [token]);

  if (loading) {
    return (
      <div style={{ padding: '2rem 0', textAlign: 'center', color: '#6B5E63' }}>
        <p>Curating personalized collection for your profile...</p>
      </div>
    );
  }

  if (!data) return null;

  const hasHistory = data.has_order_history && data.because_you_bought?.length > 0;
  const trendingList = data.trending_for_you || [];

  return (
    <section className="personalized-recommendations-section" style={{ margin: '3.5rem 0' }}>
      {/* 1. If customer has past orders: "Because you bought X" */}
      {hasHistory && (
        <div style={{ marginBottom: '3.5rem' }}>
          <div className="section-head" style={{ marginBottom: '1.25rem' }}>
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: '#9C4146',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  marginBottom: '0.25rem',
                }}
              >
                <Sparkles size={13} /> Tailored to Your Purchase History
              </div>
              <h2
                style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: '1.8rem',
                  color: '#1F191B',
                  margin: 0,
                }}
              >
                Because You Ordered With Us
              </h2>
              <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: '4px 0 0' }}>
                Algorithmic pairings mined from real customer baskets containing your previously delivered pieces.
              </p>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: '1.5rem',
            }}
          >
            {data.because_you_bought.map((item, idx) => (
              <div key={idx} style={{ position: 'relative' }}>
                <div
                  style={{
                    backgroundColor: '#FAF5F4',
                    border: '1px solid #EADBDA',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.72rem',
                    color: '#9C4146',
                    fontWeight: 600,
                    marginBottom: '8px',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '160px' }}>
                    Matches: {item.source_product}
                  </span>
                  <span>{item.lift?.toFixed(1)}x Lift</span>
                </div>
                <ProductCard product={item.product} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 2. Gender Curated Collection (Men's / Women's Picks) */}
      <div>
        <div className="section-head" style={{ marginBottom: '1.25rem' }}>
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                color: '#9C4146',
                fontSize: '0.8rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '1px',
                marginBottom: '0.25rem',
              }}
            >
              <Sparkles size={13} /> {data.gender_label} Signature Edit
            </div>
            <h2
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.8rem',
                color: '#1F191B',
                margin: 0,
              }}
            >
              Curated For Your Profile ({data.gender_label})
            </h2>
            <p style={{ color: '#6B5E63', fontSize: '0.88rem', margin: '4px 0 0' }}>
              Hand-selected silhouettes personalized for your category preferences and seasonal trends.
            </p>
          </div>

          <Link
            to={`/customer/shop?category=${encodeURIComponent(data.gender === 'women' ? "women's clothing" : "men's clothing")}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.88rem',
              fontWeight: 600,
              color: '#9C4146',
              textDecoration: 'none',
            }}
          >
            <span>View All {data.gender_label}</span>
            <ArrowRight size={16} />
          </Link>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: '1.5rem',
          }}
        >
          {trendingList.slice(0, 8).map((prod) => (
            <ProductCard key={prod.product_id || prod.id} product={prod} />
          ))}
        </div>
      </div>
    </section>
  );
}
