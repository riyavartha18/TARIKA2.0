import { useMemo } from 'react';
import { useCustomer } from '../context/CustomerContext';

// Every customer surface reads the same already-validated offer list from the
// customer context: the navbar badge, the home page feature, the Your Offers
// page and Member Privileges. The server decides eligibility (authenticated
// identity, latest completed RFM segment, published status, validity dates and
// coupon conditions), so nothing here filters or copies campaigns, and no
// surface can drift from another. `offers` arrives newest campaign first.
export default function usePersonalizedOffers() {
  const { offers, offersLoading, offersSyncing, refreshOffers } = useCustomer();

  // The server already returns usable offers before Used/Expired ones, newest
  // first. A redeemed or lapsed offer is never featured as if it were new.
  // Memoized on the list itself, so re-renders of the surrounding page (bag
  // updates, toasts) never recompute or re-create these values.
  const { featuredOffer, availableCount, usedCount } = useMemo(() => {
    const featured = offers.find(
      (offer) => (offer.status || 'AVAILABLE') === 'AVAILABLE',
    ) || null;
    const available = offers.filter(
      (offer) => (offer.status || 'AVAILABLE') === 'AVAILABLE',
    ).length;
    return {
      featuredOffer: featured,
      availableCount: available,
      usedCount: offers.length - available,
    };
  }, [offers]);

  return {
    loading: offersLoading,
    // No completed analysis in the server process yet: offers are being worked
    // out, which is different from "this customer has no offers".
    syncing: offersSyncing,
    offers,
    featuredOffer,
    availableCount,
    usedCount,
    refreshOffers,
  };
}
