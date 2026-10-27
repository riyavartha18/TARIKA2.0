import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ArrowDown, Flower2, Shirt, Sparkles } from 'lucide-react';
import {
  EDITORIAL_CATEGORIES,
  EDITORIAL_DEPARTMENTS,
} from '../../data/editorialCategories';

export default function CategoryEditorialSection({
  selectedCategory = '',
  onSelectCategory,
  showMasthead = true,
  defaultDepartment = 'all',
}) {
  const navigate = useNavigate();
  const [selectedDept, setSelectedDept] = useState(defaultDepartment);

  const handleCardClick = (targetCategory) => {
    if (onSelectCategory) {
      onSelectCategory(targetCategory);
    } else {
      navigate(`/customer/shop?category=${encodeURIComponent(targetCategory)}`);
    }
  };

  const filteredCategories =
    selectedDept === 'all'
      ? EDITORIAL_CATEGORIES
      : EDITORIAL_CATEGORIES.filter((c) => c.department === selectedDept);

  const isCategorySelected = (dbCategory) => {
    if (!selectedCategory) return false;
    const cleanCurrent = selectedCategory.trim().toLowerCase();
    const cleanTarget = dbCategory.trim().toLowerCase();
    return cleanCurrent === cleanTarget;
  };

  return (
    <section className="cat-editorial-landing" aria-label="Product categories">
      {/* 1. Editorial Masthead */}
      {showMasthead && (
        <div className="cat-editorial-masthead">
          <div className="cat-masthead-left">
            <div className="cat-masthead-eyebrow">EXPLORE BY STYLE</div>
            <h1 className="cat-masthead-main-title">CATEGORIES</h1>
            <p className="cat-masthead-script">Find your style. Tell your story..</p>
            <div className="cat-masthead-meta-tags">
              - CURATED LOOKS &nbsp;/&nbsp; TIMELESS TRENDS &nbsp;/&nbsp; MADE FOR YOU
            </div>
          </div>

          {/* Right Accent Card with Arched Floral Photo & Vertical Motto */}
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
                alt="Rose in vase silhouette"
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
      )}

      {/* 2. Department Selector Pills */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px',
          margin: '0 auto 2rem auto',
          flexWrap: 'wrap',
        }}
      >
        {EDITORIAL_DEPARTMENTS.map((dept) => {
          const isActive = selectedDept === dept.id;
          return (
            <button
              key={dept.id}
              type="button"
              onClick={() => setSelectedDept(dept.id)}
              style={{
                padding: '8px 18px',
                borderRadius: '9999px',
                border: `1.5px solid ${isActive ? '#D8727E' : 'rgba(216, 114, 126, 0.22)'}`,
                backgroundColor: isActive ? '#FAF0F0' : '#FFFFFF',
                color: isActive ? '#B8505E' : '#6B5E63',
                fontSize: '0.84rem',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                transition: 'all 0.25s ease',
                boxShadow: isActive ? '0 4px 14px rgba(216, 114, 126, 0.18)' : 'none',
              }}
            >
              {dept.label}
            </button>
          );
        })}
      </div>

      {/* 3. Editorial Category Cards Grid */}
      <div className="cat-editorial-grid">
        {filteredCategories.map((cat, index) => {
          if (cat.isMulti && cat.items) {
            // Multi-Item Card: ETHNIC EDIT
            const isAnySubSelected = cat.items.some((sub) =>
              isCategorySelected(sub.dbCategory)
            ) || isCategorySelected(cat.dbCategory);

            return (
              <div
                key={cat.id}
                className="cat-card-interactive"
                style={{
                  animationDelay: `${index * 60}ms`,
                  borderColor: isAnySubSelected ? '#D8727E' : 'rgba(216, 114, 126, 0.2)',
                  boxShadow: isAnySubSelected
                    ? '0 12px 30px rgba(216, 114, 126, 0.2)'
                    : '0 6px 25px rgba(184, 80, 94, 0.05)',
                  cursor: 'default',
                }}
              >
                <div className="cat-multi-card-layout">
                  {/* Header */}
                  <div className="cat-multi-card-header">
                    {cat.id === 'ethnic-edit' ? (
                      <svg
                        className="cat-multi-corner-accent"
                        viewBox="0 0 100 100"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M85 10C65 20 50 45 45 75M85 10C75 35 78 58 88 75M85 10C55 18 30 35 18 65"
                          stroke="#D8727E"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          opacity="0.4"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="cat-multi-corner-accent"
                        viewBox="0 0 100 100"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <circle cx="70" cy="30" r="24" stroke="#E2B755" strokeWidth="2.8" opacity="0.45" />
                        <circle cx="50" cy="52" r="14" stroke="#D8727E" strokeWidth="2" opacity="0.35" />
                      </svg>
                    )}

                    <h3 className="cat-multi-card-title">{cat.creativeTitle}</h3>
                    <p className="cat-multi-card-subtitle">{cat.subtitle}</p>
                  </div>

                  {/* 3 Sub-items in a Row */}
                  <div className="cat-multi-items-row">
                    {cat.items.map((sub) => {
                      const isSubSelected = isCategorySelected(sub.dbCategory);
                      return (
                        <button
                          key={sub.dbCategory}
                          type="button"
                          className="cat-multi-subitem-btn"
                          onClick={() => handleCardClick(sub.dbCategory)}
                          style={{
                            borderColor: isSubSelected
                              ? '#D8727E'
                              : 'rgba(216, 114, 126, 0.22)',
                            backgroundColor: isSubSelected ? '#FBF1F0' : '#FFFFFF',
                            boxShadow: isSubSelected
                              ? '0 4px 14px rgba(216, 114, 126, 0.22)'
                              : 'none',
                          }}
                        >
                          <div className="cat-multi-subitem-thumb">
                            <img src={sub.image} alt={sub.name} loading="lazy" />
                          </div>
                          <span
                            className="cat-multi-subitem-label"
                            style={{ color: isSubSelected ? '#B8505E' : '#1F191B' }}
                          >
                            {sub.name} <ArrowRight size={11} color="#D8727E" />
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          }

          // Single Split Card: THE DRESS STORY, TOP STORIES, BOTTOM LINE, etc.
          const isMediaLeft = cat.layout === 'media-left';
          const isSelected = isCategorySelected(cat.dbCategory);

          return (
            <div
              key={cat.id}
              className="cat-card-interactive"
              onClick={() => handleCardClick(cat.dbCategory)}
              style={{
                animationDelay: `${index * 60}ms`,
                borderColor: isSelected ? '#D8727E' : 'rgba(216, 114, 126, 0.2)',
                boxShadow: isSelected
                  ? '0 12px 30px rgba(216, 114, 126, 0.22)'
                  : '0 6px 25px rgba(184, 80, 94, 0.05)',
              }}
            >
              <div
                className={`cat-split-layout ${
                  isMediaLeft ? 'is-media-left' : 'is-media-right'
                }`}
              >
                {/* Media Wrapper */}
                <div className={`cat-split-media ${cat.isArch ? 'is-arch' : ''}`}>
                  <img src={cat.image} alt={cat.creativeTitle} loading="lazy" />
                  {cat.scriptOverlay && (
                    <span className="cat-split-media-script">{cat.scriptOverlay}</span>
                  )}
                </div>

                {/* Info Wrapper */}
                <div className="cat-split-info">
                  <div className="cat-split-info-top">
                    <h3 className="cat-split-title">{cat.creativeTitle}</h3>
                    <p className="cat-split-subtitle">{cat.subtitle}</p>
                    <div className="cat-split-action">
                      <div className="cat-circle-arrow-btn">
                        <ArrowRight size={14} />
                      </div>
                    </div>
                  </div>
                  <span className="cat-split-bottom-tag">{cat.tag}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 4. Affirmation Quality Strip */}
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

      {/* 5. Transition Indicator Badge */}
      <div className="cat-transition-indicator">
        <span>Smooth transition animation</span>
        <ArrowDown size={14} />
      </div>
    </section>
  );
}
