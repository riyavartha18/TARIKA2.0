import React from 'react';

/**
 * Lightweight skeleton primitives used to reserve layout space while the
 * customer landing page and code-split routes load. Prevents blank screens
 * and reduces cumulative layout shift (CLS) versus popping content in.
 */

export function SkeletonBox({ width = '100%', height = '1rem', radius = '10px', style = {} }) {
  return (
    <div
      className="tarika-skeleton"
      style={{ width, height, borderRadius: radius, ...style }}
      aria-hidden="true"
    />
  );
}

export function SkeletonProductCard() {
  return (
    <div className="tarika-skeleton-card">
      <SkeletonBox height='0px' radius="14px" style={{ aspectRatio: '3 / 4', height: 'auto' }} />
      <div style={{ padding: '0.9rem 1rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SkeletonBox width="40%" height="0.6rem" />
        <SkeletonBox width="90%" height="0.85rem" />
        <SkeletonBox width="55%" height="0.9rem" />
      </div>
    </div>
  );
}

export function SkeletonProductRow({ count = 5 }) {
  return (
    <div className="tarika-skeleton-row">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonProductCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonProductGrid({ count = 8 }) {
  return (
    <div className="tarika-skeleton-grid">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonProductCard key={i} />
      ))}
    </div>
  );
}

export function SkeletonCategoryPills({ count = 8 }) {
  return (
    <div className="tarika-skeleton-row">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="tarika-skeleton-card" style={{ width: '140px', padding: '1rem' }}>
          <SkeletonBox width="54px" height="54px" radius="50%" style={{ margin: '0 auto 10px' }} />
          <SkeletonBox width="80%" height="0.7rem" style={{ margin: '0 auto' }} />
        </div>
      ))}
    </div>
  );
}
