import React from 'react';
import { CATEGORIES } from '../../data/tarikaData';

export default function CategoriesSection() {
  return (
    <section
      id="categories"
      style={{
        padding: '3.5rem 2.5rem',
        maxWidth: '1680px',
        margin: '0 auto'
      }}
    >
      {/* 10 Horizontal Circular Category Items */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(10, 1fr)',
          gap: '1.25rem',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          overflowX: 'auto',
          paddingBottom: '0.75rem'
        }}
      >
        {CATEGORIES.map((cat) => (
          <a
            key={cat.id}
            href={`#${cat.id}`}
            className="category-card"
            style={{ minWidth: '92px' }}
          >
            {/* Circular Image Container */}
            <div className="category-circle zoom-container">
              <img
                src={cat.image}
                alt={cat.name}
                loading="lazy"
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover'
                }}
              />
            </div>

            {/* Label */}
            <span className="category-label">
              {cat.name}
            </span>
          </a>
        ))}
      </div>
    </section>
  );
}
