import React from 'react';
import OfferCard from './OfferCard';

// Responsive rail of identical offer cards. Used by My Profile, Member
// Privileges and the home page, so a customer sees the same eligible campaigns
// - styled exactly the same way - in every one of those places.
function PersonalizedOffers({ offers, minColumnWidth = 260 }) {
  if (!offers?.length) return null;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(auto-fill, minmax(${minColumnWidth}px, 1fr))`,
        gap: '1rem',
        alignItems: 'stretch',
      }}
    >
      {offers.map((offer) => (
        <OfferCard key={offer.campaign_id} offer={offer} />
      ))}
    </div>
  );
}

export default React.memo(PersonalizedOffers);
