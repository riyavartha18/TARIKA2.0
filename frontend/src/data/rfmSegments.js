// Plain-language descriptions and colors for each customer segment.
// Display-only: the numeric segmentation rules live on the backend and are
// never duplicated here. Labels are kept intentionally non-technical so the
// overview reads clearly without any prior RFM knowledge.

export const SEGMENT_META = {
  Champions: {
    blurb: 'Your most valuable and highly engaged customers.',
    color: '#B8505E',
    soft: 'rgba(184, 80, 94, 0.12)',
  },
  'Loyal Customers': {
    blurb: 'Customers who purchase frequently and reliably.',
    color: '#C0623F',
    soft: 'rgba(192, 98, 63, 0.12)',
  },
  'Potential Loyalists': {
    blurb: 'Recent shoppers with strong potential to become loyal.',
    color: '#B08A2E',
    soft: 'rgba(176, 138, 46, 0.12)',
  },
  'New Customers': {
    blurb: 'Customers in the new-customer classification.',
    color: '#3F8F6B',
    soft: 'rgba(63, 143, 107, 0.12)',
  },
  'At-Risk': {
    blurb: 'Previously valuable customers losing engagement.',
    color: '#3E7CB1',
    soft: 'rgba(62, 124, 177, 0.12)',
  },
  Hibernating: {
    blurb: 'Customers with very low recent activity.',
    color: '#6D6AA8',
    soft: 'rgba(109, 106, 168, 0.12)',
  },
  'Never Purchased': {
    blurb: 'Customers who have not completed an eligible purchase.',
    color: '#9E8F94',
    soft: 'rgba(158, 143, 148, 0.12)',
  },
};

export const BIG_SPENDER_META = {
  blurb: 'High spenders (top 10% by value).',
  color: '#8E3642',
  soft: 'rgba(142, 54, 66, 0.10)',
};
