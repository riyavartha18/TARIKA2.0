import React from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, ChevronRight } from 'lucide-react';
import FeaturedOffer from './FeaturedOffer';
import PersonalizedOffers from './PersonalizedOffers';
import usePersonalizedOffers from '../../hooks/usePersonalizedOffers';
import { useCustomer } from '../../context/CustomerContext';

// "Exclusive Offers For You" on the customer home page: the newest campaign
// this customer is eligible for is featured prominently, with the rest of their
// eligible campaigns below as identical cards. The list is the one the backend
// computed from the latest completed RFM analysis + published campaigns, so it
// is exactly what the Your Offers page and Member Privileges show.
export default function CustomerOffers() {
  const { loading, syncing, offers, featuredOffer } = usePersonalizedOffers();
  const { addToast } = useCustomer();

  if (loading || syncing) return null;
  if (!offers.length) return null;

  const remaining = offers.filter(
    (offer) => !featuredOffer || offer.campaign_id !== featuredOffer.campaign_id,
  );

  return (
    <section aria-label="Exclusive offers for you" style={{ marginBottom: '2.25rem' }}>
      <div className="section-head">
        <div>
          <div className="section-eyebrow section-eyebrow--inline">
            <Sparkles size={14} />
            <span>Picked for you</span>
          </div>
          <h2 className="section-title">Exclusive Offers For You</h2>
        </div>
        <Link to="/customer/offers" className="section-link">
          <span>View All Offers</span>
          <ChevronRight size={16} />
        </Link>
      </div>

      <FeaturedOffer
        offer={featuredOffer}
        onCopyNote={(code) => addToast(`Coupon ${code} copied`, 'info')}
      />

      {remaining.length > 0 && <PersonalizedOffers offers={remaining} />}
    </section>
  );
}
