import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Sparkles,
  ShoppingBag,
  Check,
  ArrowRight,
  Heart,
  ShieldCheck,
  Calendar,
  Layers,
  Store,
  ChevronDown,
} from 'lucide-react';
import { getSmartBudgetOutfits, getWardrobeItems, getCustomerCoins, redeemCoinsForOutfit } from '../../services/api';
import { useCustomer } from '../../context/CustomerContext';
import { useAuth } from '../../auth/AuthContext';

const COLOR_PALETTE = [
  { id: 'black', label: 'Black', hex: '#1F191B', border: '#1F191B' },
  { id: 'white', label: 'White', hex: '#FFFFFF', border: '#D1C5C7' },
  { id: 'beige', label: 'Beige', hex: '#EADBCA', border: '#D6C7B5' },
  { id: 'pink', label: 'Pink', hex: '#E57388', border: '#D65970' },
  { id: 'maroon', label: 'Maroon', hex: '#8B1E2F', border: '#701524' },
  { id: 'navy', label: 'Navy Blue', hex: '#23395B', border: '#1B2C47' },
  { id: 'green', label: 'Emerald Green', hex: '#2F6F4E', border: '#24593E' },
  { id: 'yellow', label: 'Mustard', hex: '#EAB308', border: '#CA8A04' },
  { id: 'purple', label: 'Purple', hex: '#6B46C1', border: '#553C9A' },
  { id: 'brown', label: 'Brown', hex: '#5C3D2E', border: '#462E22' },
];

const BUDGET_PRESETS = [500, 799, 1000, 1499, 1999, 2100, 5000];

const FASHION_DIRECTIONS = [
  { id: 'all', title: 'Surprise Me', subtitle: 'All Compatible Outfits' },
  { id: 'western', title: 'Western Wear', subtitle: 'Tops, Jeans, Skirts & Co-ords' },
  { id: 'ethnic', title: 'Ethnic', subtitle: 'Kurtas, Sarees & Palazzos' },
  { id: 'indo-western', title: 'Indo-Western', subtitle: 'Kurti + Denim Fusion' },
];

const BASE_FILTERS = [
  { id: 'all', label: 'All Looks' },
  { id: 'two_piece', label: 'Tops & Bottoms' },
  { id: 'one_piece', label: 'Dresses & Jumpsuits' },
  { id: 'saree_lehenga', label: 'Sarees & Lehengas' },
];

// Clean neutral SVG placeholder
export const NEUTRAL_PLACEHOLDER_IMAGE = "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='500' viewBox='0 0 400 500' fill='none'%3E%3Crect width='400' height='500' fill='%23FAF7F5'/%3E%3Cpath d='M160 190C160 167.909 177.909 150 200 150C222.091 150 240 167.909 240 190V205H160V190Z' stroke='%23C7B9BA' stroke-width='2' stroke-linecap='round'/%3E%3Cpath d='M135 205C129.477 205 125 209.477 125 215V325C125 330.523 129.477 335 135 335H265C270.523 335 275 330.523 275 325V215C275 209.477 270.523 205 265 205H135Z' stroke='%23C7B9BA' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3Cpath d='M175 205V335M225 205V335' stroke='%23E8DFDB' stroke-width='1.5' stroke-dasharray='4 4'/%3E%3Ctext x='50%25' y='375' text-anchor='middle' font-family='sans-serif' font-size='12' font-weight='600' letter-spacing='0.5' fill='%239C8C91'%3EIMAGE UNAVAILABLE%3C/text%3E%3C/svg%3E";

export function cleanProductImageUrl(url) {
  if (!url || typeof url !== 'string') return '';
  const trimmed = url.trim();
  if (!trimmed) return '';
  return trimmed.replace(/\/images\/W\/[^/]+\/images\/I\//, '/images/I/');
}

export default function SmartBudgetStylistPage() {
  const { addToBag, toggleWishlist, isWishlisted, openProductDetail } = useCustomer();
  const { user, token } = useAuth();
  const creatorRef = useRef(null);
  const resultsRef = useRef(null);

  // Filters State — Default budget 500, direction 'all' (Surprise Me)
  const [budget, setBudget] = useState(500);
  const [selectedColor, setSelectedColor] = useState('all');
  const [fashionDirection, setFashionDirection] = useState('all');
  const [sortBy, setSortBy] = useState('best');
  const [selectedBaseFilter, setSelectedBaseFilter] = useState('all');
  const [visibleCount, setVisibleCount] = useState(24);

  // TARIKA Coins & Loyalty State
  const [userCoins, setUserCoins] = useState(null);
  const [redeemedOutfits, setRedeemedOutfits] = useState({});
  const [redeemingOutfitId, setRedeemingOutfitId] = useState(null);
  const [coinActionMessage, setCoinActionMessage] = useState({});

  // Outfit Favourites
  const [favouritedOutfits, setFavouritedOutfits] = useState({});

  // Digital Wardrobe pieces locked into the styling loop
  const [wardrobeItems, setWardrobeItems] = useState([]);
  const [selectedWardrobeItemIds, setSelectedWardrobeItemIds] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const w = params.get('wardrobe_items');
      return w ? w.split(',').filter(Boolean) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    getWardrobeItems(token).then((res) => {
      if (res && res.success) {
        setWardrobeItems(res.results || []);
      }
    });
  }, [token]);

  // Fetch real customer coins on auth change
  useEffect(() => {
    const customerId = user?.customer_id || user?.id || user?.auth_user_id || null;
    if (customerId) {
      getCustomerCoins(customerId, token).then((res) => {
        if (res && res.success && res.coins) {
          setUserCoins(res.coins);
        }
      });
    }
  }, [user, token]);

  // Loading & Results
  const [loading, setLoading] = useState(false);
  const [outfitsData, setOutfitsData] = useState(null);
  const [error, setError] = useState('');
  const [addedOutfitIndex, setAddedOutfitIndex] = useState(null);

  const getOutfitKey = (outfit, idx) => {
    const topId = outfit.topwear?.product_id || outfit.topwear?.id || 'top';
    const botId = outfit.bottomwear?.product_id || outfit.bottomwear?.id || 'bot';
    return outfit.id || `${topId}_${botId}_${idx}`;
  };

  const isOutfitFavourited = (outfit, idx) => {
    const key = getOutfitKey(outfit, idx);
    if (favouritedOutfits[key] !== undefined) {
      return favouritedOutfits[key];
    }
    if (outfit.topwear?.product_id) {
      return isWishlisted(outfit.topwear.product_id);
    }
    return false;
  };

  const handleToggleFavouriteOutfit = (outfit, idx) => {
    const key = getOutfitKey(outfit, idx);
    const currentlyFav = isOutfitFavourited(outfit, idx);
    setFavouritedOutfits(prev => ({
      ...prev,
      [key]: !currentlyFav
    }));
    if (outfit.topwear) {
      toggleWishlist(outfit.topwear);
    }
  };

  // Secure coin redemption on outfit
  const handleRedeemCoins = async (outfit) => {
    const customerId = user?.customer_id || user?.id || user?.auth_user_id;
    if (!customerId) {
      setCoinActionMessage(prev => ({
        ...prev,
        [outfit.id]: { type: 'error', text: 'Please log in to redeem TARIKA coins.' }
      }));
      return;
    }

    const available = userCoins?.available_coins || 0;
    const eligible = outfit.eligible_coins || Math.min(available, Math.floor((outfit.subtotal_price || outfit.total_price) * 0.15));
    if (eligible <= 0) {
      setCoinActionMessage(prev => ({
        ...prev,
        [outfit.id]: { type: 'error', text: 'No coins available or eligible for this look.' }
      }));
      return;
    }

    setRedeemingOutfitId(outfit.id);
    const res = await redeemCoinsForOutfit({
      customerId,
      outfitId: outfit.id,
      coins: eligible,
      token
    });
    setRedeemingOutfitId(null);

    if (res.success) {
      setRedeemedOutfits(prev => ({
        ...prev,
        [outfit.id]: {
          redeemed: true,
          coinsRedeemed: res.redeemed_coins,
          discountAmount: res.discount_amount,
        }
      }));
      setUserCoins(prev => ({
        ...prev,
        available_coins: res.new_available_coins
      }));
      setCoinActionMessage(prev => ({
        ...prev,
        [outfit.id]: { type: 'success', text: `₹${res.discount_amount} coin discount applied successfully!` }
      }));
    } else {
      setCoinActionMessage(prev => ({
        ...prev,
        [outfit.id]: { type: 'error', text: res.error || 'Failed to redeem coins.' }
      }));
    }
  };

  const fetchOutfits = useCallback(async (isInitial = false, overrideParams = {}) => {
    setLoading(true);
    setError('');
    setVisibleCount(24);
    setSelectedBaseFilter('all');
    const targetBudget = overrideParams.budget !== undefined ? overrideParams.budget : budget;
    const targetColor = overrideParams.color !== undefined ? overrideParams.color : selectedColor;
    const targetDirection = overrideParams.direction !== undefined ? overrideParams.direction : fashionDirection;
    const targetSort = overrideParams.sort !== undefined ? overrideParams.sort : sortBy;
    const targetWardrobeIds = overrideParams.wardrobe_item_ids !== undefined ? overrideParams.wardrobe_item_ids : selectedWardrobeItemIds;

    const customerId = user?.customer_id || user?.id || user?.auth_user_id || null;

    const res = await getSmartBudgetOutfits({
      budget: targetBudget,
      gender: 'women',
      color: targetColor === 'all' ? null : targetColor,
      category_direction: targetDirection,
      sort: targetSort,
      wardrobe_item_ids: targetWardrobeIds,
      customer_id: customerId,
      personalise: true, // Auto-personalised using preference signals
      token: token,
    });
    setLoading(false);
    if (res.success && res.outfits && res.outfits.length > 0) {
      setOutfitsData(res);
      if (res.user_coins) {
        setUserCoins(res.user_coins);
      }
      if (!isInitial && resultsRef.current) {
        resultsRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      setOutfitsData(null);
      setError(res.error || res.message || `No outfit combinations found under ₹${targetBudget.toLocaleString()}. Try increasing your budget.`);
    }
  }, [budget, selectedColor, fashionDirection, sortBy, selectedWardrobeItemIds, user, token]);

  useEffect(() => {
    fetchOutfits(true);
  }, []);

  // Compute sorted outfits based on current sortBy state
  const displayedOutfits = React.useMemo(() => {
    if (!outfitsData?.outfits) return [];
    let list = [...outfitsData.outfits];
    if (sortBy === 'price_low') {
      list.sort((a, b) => a.total_price - b.total_price);
    } else if (sortBy === 'price_high') {
      list.sort((a, b) => b.total_price - a.total_price);
    } else if (sortBy === 'score') {
      list.sort((a, b) => (b.styling_score || 0) - (a.styling_score || 0));
    }
    return list;
  }, [outfitsData, sortBy]);

  // Filter by base type
  const baseFilteredOutfits = React.useMemo(() => {
    if (selectedBaseFilter === 'all') return displayedOutfits;
    return displayedOutfits.filter(o => o.base_type === selectedBaseFilter);
  }, [displayedOutfits, selectedBaseFilter]);

  // Counts per base
  const baseCounts = React.useMemo(() => {
    const counts = { all: displayedOutfits.length, two_piece: 0, one_piece: 0, saree_lehenga: 0 };
    displayedOutfits.forEach(o => {
      if (counts[o.base_type] !== undefined) counts[o.base_type]++;
    });
    return counts;
  }, [displayedOutfits]);

  const handleScrollToCreator = () => {
    if (creatorRef.current) {
      creatorRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleAddFullOutfitToBag = (outfit, index) => {
    if (outfit.topwear) addToBag(outfit.topwear, 1);
    if (outfit.bottomwear) addToBag(outfit.bottomwear, 1);
    if (outfit.blouse) addToBag(outfit.blouse, 1);
    if (outfit.footwear) addToBag(outfit.footwear, 1);
    if (outfit.bag) addToBag(outfit.bag, 1);
    if (outfit.accessory) addToBag(outfit.accessory, 1);
    if (outfit.accessories && Array.isArray(outfit.accessories)) {
      outfit.accessories.forEach((acc) => {
        if (acc) addToBag(acc, 1);
      });
    }

    setAddedOutfitIndex(index);
    setTimeout(() => setAddedOutfitIndex(null), 2500);
  };

  const getItemBadgeLabel = (item, fallbackRole) => {
    if (!item) return fallbackRole || 'Item ↗';
    if (item.subtype === 'saree') return 'Saree ↗';
    if (item.subtype === 'choli' || item.role?.includes('Blouse') || item.subtype === 'saree_blouse') return 'Blouse ↗';
    if (item.slot_type === 'bottom' || item.role?.includes('Bottom') || item.subtype === 'palazzo' || item.subtype === 'lehenga_skirt') return 'Bottom ↗';
    if (item.slot_type === 'footwear' || item.footwear_type) return 'Footwear ↗';
    if (item.slot_type === 'bag' || item.subtype === 'potli' || item.subtype === 'clutch') return 'Bag ↗';
    if (item.slot_type === 'accessory' || item.accessory_type) return 'Jewellery ↗';
    return fallbackRole || 'View ↗';
  };

  return (
    <div className="smart-budget-stylist-page" style={{ maxWidth: '1440px', margin: '0 auto', paddingBottom: '4rem' }}>
      {/* 1. HERO BANNER */}
      <section
        style={{
          background: 'linear-gradient(135deg, #FAF7F5 0%, #F5ECE9 60%, #EADBDA 100%)',
          borderRadius: '28px',
          padding: '3.5rem 3rem',
          margin: '1rem 0 3rem',
          border: '1px solid #EADBDA',
          display: 'grid',
          gridTemplateColumns: '1.2fr 0.9fr',
          gap: '2.5rem',
          alignItems: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Left Content */}
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#FFFFFF',
              border: '1px solid #EADBDA',
              borderRadius: '999px',
              padding: '6px 14px',
              fontSize: '0.78rem',
              fontWeight: 700,
              color: '#9C4146',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              marginBottom: '1.25rem',
              boxShadow: '0 2px 8px rgba(156,65,70,0.06)',
            }}
          >
            <Sparkles size={13} color="#9C4146" />
            <span>Smart AI Fashion Atelier</span>
          </div>

          <h1
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '3.2rem',
              lineHeight: 1.15,
              color: '#1F191B',
              margin: '0 0 1rem 0',
              fontWeight: 700,
              letterSpacing: '-0.5px',
            }}
          >
            Your Budget. Your Style. <br />
            <span style={{ fontStyle: 'italic', fontWeight: 400, color: '#B8505E' }}>
              Your Perfect Look.
            </span>
          </h1>

          <p
            style={{
              color: '#6B5E63',
              fontSize: '1rem',
              lineHeight: 1.6,
              maxWidth: '560px',
              margin: '0 0 2rem 0',
            }}
          >
            Discover complete outfits curated around your budget and favourite fashion mode.
            Real catalogue pieces, genuine colour harmony, and effortless 1-click shopping.
          </p>

          {/* 4 Feature Badges in a Row */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '0.75rem',
              marginBottom: '2.25rem',
            }}
          >
            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.75)',
                border: '1px solid #EADBDA',
                borderRadius: '12px',
                padding: '10px 12px',
              }}
            >
              <Sparkles size={16} color="#9C4146" style={{ marginBottom: '4px' }} />
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1F191B' }}>Multiple looks</div>
              <div style={{ fontSize: '0.72rem', color: '#8A7A7F' }}>One budget</div>
            </div>

            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.75)',
                border: '1px solid #EADBDA',
                borderRadius: '12px',
                padding: '10px 12px',
              }}
            >
              <Calendar size={16} color="#9C4146" style={{ marginBottom: '4px' }} />
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1F191B' }}>4 Fashion Modes</div>
              <div style={{ fontSize: '0.72rem', color: '#8A7A7F' }}>Western & Ethnic</div>
            </div>

            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.75)',
                border: '1px solid #EADBDA',
                borderRadius: '12px',
                padding: '10px 12px',
              }}
            >
              <Layers size={16} color="#9C4146" style={{ marginBottom: '4px' }} />
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1F191B' }}>Real products</div>
              <div style={{ fontSize: '0.72rem', color: '#8A7A7F' }}>Full catalogue</div>
            </div>

            <div
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.75)',
                border: '1px solid #EADBDA',
                borderRadius: '12px',
                padding: '10px 12px',
              }}
            >
              <Store size={16} color="#9C4146" style={{ marginBottom: '4px' }} />
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1F191B' }}>Ready to shop</div>
              <div style={{ fontSize: '0.72rem', color: '#8A7A7F' }}>in one click</div>
            </div>
          </div>

          {/* CTA Button */}
          <button
            onClick={handleScrollToCreator}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: '#9C4146',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '999px',
              padding: '0.9rem 2rem',
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 24px rgba(156, 65, 70, 0.25)',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = '0 12px 28px rgba(156, 65, 70, 0.35)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = '0 8px 24px rgba(156, 65, 70, 0.25)';
            }}
          >
            <Sparkles size={16} />
            <span>Style My Outfits</span>
            <ArrowRight size={16} />
          </button>
        </div>

        {/* Right Showcase Card with Model */}
        <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
          <div
            style={{
              position: 'relative',
              borderRadius: '24px',
              overflow: 'hidden',
              boxShadow: '0 16px 40px rgba(0,0,0,0.15)',
              width: '100%',
              maxWidth: '380px',
              height: '460px',
              background: '#900C3F',
            }}
          >
            <img
              src="https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=700&q=80"
              alt="Curated look"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />

            {/* Bottom Card Overlay */}
            <div
              style={{
                position: 'absolute',
                bottom: '16px',
                left: '16px',
                right: '16px',
                backgroundColor: 'rgba(255, 255, 255, 0.94)',
                backdropFilter: 'blur(10px)',
                borderRadius: '16px',
                padding: '12px 16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
              }}
            >
              <div>
                <div style={{ fontSize: '0.74rem', color: '#8A7A7F', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Smart Look
                </div>
                <div style={{ fontSize: '0.96rem', fontWeight: 700, color: '#1F191B' }}>
                  Complete Saree Look
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.72rem', color: '#8A7A7F' }}>Within</div>
                <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#9C4146' }}>₹1,499</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. "LET'S FIND YOUR LOOK" CARD — Streamlined 3-Column Luxury Layout */}
      <section
        ref={creatorRef}
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '24px',
          border: '1px solid #EADBDA',
          padding: '2.5rem',
          marginBottom: '3.5rem',
          boxShadow: '0 8px 30px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ marginBottom: '2rem' }}>
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '2rem',
              color: '#1F191B',
              margin: '0 0 0.5rem 0',
              fontWeight: 700,
            }}
          >
            Let's Find Your Look
          </h2>
          <p style={{ color: '#6B5E63', fontSize: '0.92rem', margin: '0 0 1.25rem 0' }}>
            Set your budget, select an outfit mode and optional colour palette to curate beautiful complete looks.
          </p>

          {/* TARIKA Coins Loyalty Rewards Banner (Automated Personalization) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: '#FFF9F5',
              borderRadius: '16px',
              padding: '14px 20px',
              border: '1.5px solid #F5E2D0',
              flexWrap: 'wrap',
              gap: '12px',
              boxShadow: '0 2px 10px rgba(222, 155, 38, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #FFD56B 0%, #DE9B26 100%)',
                  boxShadow: '0 2px 6px rgba(222, 155, 38, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '20px',
                  flexShrink: 0,
                }}
              >
                🪙
              </div>
              <div>
                <div style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>TARIKA Rewards Balance</span>
                  <span
                    style={{
                      fontSize: '0.78rem',
                      fontWeight: 800,
                      backgroundColor: '#FEF3D6',
                      color: '#9E6500',
                      padding: '2px 10px',
                      borderRadius: '999px',
                      border: '1px solid #F6D884',
                    }}
                  >
                    {userCoins?.available_coins != null ? `${userCoins.available_coins} Coins Available` : (user ? 'Loading Coins...' : '150 Welcome Coins Available')}
                  </span>
                </div>
                <div style={{ fontSize: '0.76rem', color: '#6B5E63', marginTop: '2px' }}>
                  {user ? (
                    <>Save up to <strong>{userCoins?.max_redeem_percent || 15}%</strong> off on curated outfits (1 Coin = ₹1 discount) · Earn 5% back on every outfit purchase</>
                  ) : (
                    <>Log in to access your <strong>150 Welcome Coins</strong> and redeem discounts up to 15% on any look.</>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  color: '#2F6F4E',
                  backgroundColor: '#EBF7EE',
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: '1px solid #CFEBD5',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Sparkles size={14} color="#2F6F4E" />
                <span>Auto-Personalised from Your Wishlist & History</span>
              </span>
            </div>
          </div>
        </div>

        {/* 3 Preferences Columns: Budget, Outfit Mode, Colour Palette */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '2.5rem',
            paddingBottom: '2.5rem',
            borderBottom: '1px solid #F0E2E0',
          }}
        >
          {/* Column 1: Your Budget (₹) */}
          <div>
            <span style={{ display: 'block', fontSize: '0.86rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.75rem' }}>
              1. Your Budget (₹)
            </span>

            {/* Dynamic Counter */}
            <div
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '2.2rem',
                fontWeight: 700,
                color: '#9C4146',
                marginBottom: '1rem',
              }}
            >
              ₹ {budget.toLocaleString()}
            </div>

            {/* Range Slider */}
            <input
              type="range"
              min="500"
              max="5000"
              step="50"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              style={{
                width: '100%',
                accentColor: '#9C4146',
                cursor: 'pointer',
                marginBottom: '0.5rem',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#8A7A7F', marginBottom: '1.25rem' }}>
              <span>₹500</span>
              <span>₹5,000</span>
            </div>

            {/* Preset Chips */}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {BUDGET_PRESETS.map((val) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setBudget(val)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '8px',
                    border: budget === val ? '1.5px solid #9C4146' : '1px solid #EADBDA',
                    backgroundColor: budget === val ? '#FAF5F4' : '#FFFFFF',
                    color: budget === val ? '#9C4146' : '#6B5E63',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  ₹{val}
                </button>
              ))}
            </div>
          </div>

          {/* Column 2: Outfit Mode (4 Distinct Modes) */}
          <div>
            <span style={{ display: 'block', fontSize: '0.86rem', fontWeight: 700, color: '#1F191B', marginBottom: '0.75rem' }}>
              2. Outfit Mode
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {FASHION_DIRECTIONS.map((dir) => {
                const isSelected = fashionDirection === dir.id;
                return (
                  <button
                    key={dir.id}
                    type="button"
                    onClick={() => setFashionDirection(dir.id)}
                    style={{
                      padding: '12px 14px',
                      borderRadius: '14px',
                      border: isSelected ? '1.5px solid #9C4146' : '1px solid #EADBDA',
                      backgroundColor: isSelected ? '#FAF5F4' : '#FFFFFF',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'center',
                    }}
                  >
                    <div style={{ fontSize: '0.86rem', fontWeight: 700, color: isSelected ? '#9C4146' : '#1F191B', marginBottom: '3px' }}>
                      {dir.title}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#8A7A7F', lineHeight: 1.3 }}>
                      {dir.subtitle}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Column 3: Preferred Colours (Optional) */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#1F191B' }}>
                3. Preferred Palette
              </span>
              <button
                type="button"
                onClick={() => setSelectedColor('all')}
                style={{
                  fontSize: '0.74rem',
                  color: selectedColor === 'all' ? '#9C4146' : '#8A7A7F',
                  fontWeight: 600,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  textDecoration: selectedColor === 'all' ? 'underline' : 'none',
                }}
              >
                All Colours
              </button>
            </div>

            {/* 10 Circular Swatches */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px', marginBottom: '12px' }}>
              {COLOR_PALETTE.map((c) => {
                const isSelected = selectedColor === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedColor(isSelected ? 'all' : c.id)}
                    title={c.label}
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '50%',
                      backgroundColor: c.hex,
                      border: `2px solid ${isSelected ? '#9C4146' : c.border}`,
                      boxShadow: isSelected ? '0 0 0 2px #FAF5F4, 0 2px 6px rgba(0,0,0,0.15)' : 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: c.id === 'white' || c.id === 'beige' || c.id === 'yellow' ? '#1F191B' : '#FFFFFF',
                      transition: 'transform 0.15s',
                    }}
                  >
                    {isSelected && <Check size={16} strokeWidth={3} />}
                  </button>
                );
              })}
            </div>

            <div style={{ fontSize: '0.8rem', color: '#6B5E63' }}>
              Selected: <strong style={{ color: '#9C4146' }}>{selectedColor && selectedColor !== 'all' ? selectedColor.charAt(0).toUpperCase() + selectedColor.slice(1) : 'All Palettes'}</strong>
            </div>
          </div>
        </div>

        {/* 4. Use Pieces from My Wardrobe Selector */}
        {wardrobeItems && wardrobeItems.length > 0 && (
          <div
            style={{
              marginTop: '1.5rem',
              padding: '1.25rem 1.5rem',
              backgroundColor: '#FAF5F4',
              borderRadius: '16px',
              border: '1px solid #EADBDA',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div>
                <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1F191B', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Sparkles size={16} color="#9C4146" /> Use Pieces from My Private Wardrobe (Locked at ₹0)
                </span>
                <p style={{ margin: '3px 0 0', fontSize: '0.76rem', color: '#6B5E63' }}>
                  Selected pieces cost ₹0 in your outfit. Your ₹{budget.toLocaleString()} budget is spent exclusively on missing store pieces.
                </p>
              </div>
              {selectedWardrobeItemIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedWardrobeItemIds([])}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#9C4146',
                    fontSize: '0.76rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Clear Selection
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '6px' }}>
              {wardrobeItems.map((item) => {
                const isSelected = selectedWardrobeItemIds.includes(String(item.id));
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      setSelectedWardrobeItemIds((prev) =>
                        isSelected ? prev.filter((id) => id !== String(item.id)) : [...prev, String(item.id)]
                      );
                    }}
                    style={{
                      flexShrink: 0,
                      width: '110px',
                      borderRadius: '12px',
                      backgroundColor: '#FFFFFF',
                      border: isSelected ? '2px solid #9C4146' : '1px solid #E0D2D0',
                      padding: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      cursor: 'pointer',
                      position: 'relative',
                      boxShadow: isSelected ? '0 4px 12px rgba(156,65,70,0.15)' : 'none',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div
                      style={{
                        width: '64px',
                        height: '64px',
                        borderRadius: '8px',
                        overflow: 'hidden',
                        backgroundColor: '#FAF9F8',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '6px',
                      }}
                    >
                      <img
                        src={item.thumb_url || item.image_url}
                        alt={item.item_name}
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                    </div>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        color: '#1F191B',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        width: '100%',
                        textAlign: 'center',
                      }}
                    >
                      {item.item_name}
                    </span>
                    <span
                      style={{
                        fontSize: '0.66rem',
                        fontWeight: 700,
                        color: isSelected ? '#9C4146' : '#059669',
                        marginTop: '2px',
                      }}
                    >
                      {isSelected ? '✓ Locked (₹0)' : '+ Lock Piece'}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Submit Button */}
        <div style={{ textAlign: 'center', paddingTop: '2rem' }}>
          <button
            onClick={() => fetchOutfits(false)}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: '#9C4146',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '999px',
              padding: '0.95rem 2.75rem',
              fontSize: '1rem',
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 8px 24px rgba(156, 65, 70, 0.25)',
              transition: 'transform 0.2s ease, box-shadow 0.2s ease',
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 12px 28px rgba(156, 65, 70, 0.35)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading) {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 8px 24px rgba(156, 65, 70, 0.25)';
              }
            }}
          >
            <Sparkles size={17} />
            <span>{loading ? 'Curating Looks...' : 'Create My Looks'}</span>
            <ArrowRight size={17} />
          </button>
        </div>
      </section>

      {/* 3. "LOOKS CURATED FOR YOU" RESULTS */}
      <section ref={resultsRef} style={{ marginTop: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '2.2rem',
                color: '#1F191B',
                margin: '0 0 0.5rem 0',
                fontWeight: 700,
              }}
            >
              Looks Curated for You
            </h2>
            <p style={{ color: '#6B5E63', fontSize: '0.92rem', margin: 0 }}>
              {outfitsData?.outfits?.length ? (
                <>
                  We found <strong>{outfitsData.outfits.length} looks</strong> that genuinely suit your <strong>₹{budget.toLocaleString()}</strong> budget in{' '}
                  <strong>{FASHION_DIRECTIONS.find(d => d.id === fashionDirection)?.title || 'Surprise Me'}</strong>.
                </>
              ) : outfitsData?.message ? (
                outfitsData.message
              ) : (
                <>
                  Discover genuine outfit combinations within your <strong>₹{budget.toLocaleString()}</strong> budget.
                </>
              )}
            </p>
          </div>

          {/* Sort By Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.84rem', color: '#6B5E63' }}>Sort by</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                border: '1px solid #D6C7C5',
                backgroundColor: '#FFFFFF',
                fontSize: '0.84rem',
                fontWeight: 600,
                color: '#1F191B',
                cursor: 'pointer',
              }}
            >
              <option value="best">Best Match</option>
              <option value="price_low">Price: Low to High</option>
              <option value="price_high">Price: High to Low</option>
              <option value="score">Styling Harmony Score</option>
            </select>
          </div>
        </div>

        {/* Base Filter Chips Row */}
        {!loading && displayedOutfits?.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#6B5E63', marginRight: '4px' }}>Base Category:</span>
            {BASE_FILTERS.map((bf) => {
              const isSelected = selectedBaseFilter === bf.id;
              const count = baseCounts[bf.id] || 0;
              return (
                <button
                  key={bf.id}
                  type="button"
                  onClick={() => {
                    setSelectedBaseFilter(bf.id);
                    setVisibleCount(24);
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '6px 14px',
                    borderRadius: '999px',
                    border: isSelected ? '1.5px solid #9C4146' : '1px solid #EADBDA',
                    backgroundColor: isSelected ? '#9C4146' : '#FFFFFF',
                    color: isSelected ? '#FFFFFF' : '#4A3E42',
                    fontSize: '0.8rem',
                    fontWeight: isSelected ? 700 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>{bf.label}</span>
                  <span
                    style={{
                      backgroundColor: isSelected ? 'rgba(255, 255, 255, 0.25)' : '#FAF5F4',
                      color: isSelected ? '#FFFFFF' : '#9C4146',
                      borderRadius: '999px',
                      padding: '1px 6px',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                    }}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* Outfits Cards Grid */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem 0', color: '#6B5E63' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                border: '3px solid #EADBDA',
                borderTopColor: '#9C4146',
                animation: 'spin 0.8s linear infinite',
                margin: '0 auto 1rem',
              }}
            />
            <p style={{ fontSize: '0.95rem' }}>Evaluating colour harmony and assembling matching catalogue outfits...</p>
          </div>
        ) : error || !displayedOutfits?.length ? (
          <div
            style={{
              textAlign: 'center',
              padding: '4rem 2rem',
              backgroundColor: '#FFFFFF',
              borderRadius: '20px',
              border: '1px dashed #E2D3D2',
            }}
          >
            <p style={{ color: '#1F191B', fontWeight: 700, fontSize: '1.1rem', marginBottom: '0.5rem' }}>
              No complete outfit combinations found under ₹{budget.toLocaleString()}
            </p>
            <p style={{ color: '#6B5E63', marginBottom: '1.5rem', fontSize: '0.88rem', maxWidth: '480px', margin: '0 auto 1.5rem' }}>
              {error || 'Try increasing your budget slider, selecting "Surprise Me", or clearing the colour filter.'}
            </p>
            <button
              onClick={() => {
                setBudget(1999);
                setSelectedColor('all');
                setFashionDirection('all');
                fetchOutfits(false, { budget: 1999, color: 'all', direction: 'all' });
              }}
              className="tarika-btn-primary"
              style={{ padding: '0.75rem 1.75rem', fontSize: '0.88rem' }}
            >
              Adjust to Recommended Budget (₹1,999)
            </button>
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
              gap: '2rem',
            }}
          >
            {baseFilteredOutfits.slice(0, visibleCount).map((outfit, idx) => {
              const subtotal = outfit.subtotal_price || outfit.total_price || 0;
              const isRedeemed = Boolean(redeemedOutfits[outfit.id]?.redeemed);
              const appliedCoinDiscount = isRedeemed
                ? (redeemedOutfits[outfit.id].discountAmount || outfit.coin_discount || 0)
                : 0;
              const finalPayable = Math.max(0, subtotal - appliedCoinDiscount);
              const remainingBudget = Math.max(0, budget - finalPayable);
              const eligibleCoins = outfit.eligible_coins || (userCoins?.available_coins ? Math.min(userCoins.available_coins, Math.floor(subtotal * 0.15)) : 0);
              const currentTotal = finalPayable;
              const coinsLeft = remainingBudget;

              // Secondary pieces for collage right column:
              const secondaryItems = [
                outfit.bottomwear,
                outfit.blouse,
                outfit.footwear,
                outfit.bag,
                outfit.accessory,
                ...(outfit.accessories || [])
              ].filter(Boolean);

              let rightTopItem = null;
              let rightBottomItem = null;

              if (outfit.bottomwear || outfit.blouse) {
                rightTopItem = outfit.bottomwear || outfit.blouse;
                rightBottomItem = outfit.footwear || outfit.bag || outfit.accessory || (outfit.accessories && outfit.accessories[0]);
              } else {
                rightTopItem = secondaryItems[0] || null;
                rightBottomItem = secondaryItems[1] || null;
              }

              const hasRightSide = Boolean(rightTopItem || rightBottomItem);

              // Determine category pill label matching screenshot ("Ethnic", "Indo-Western", "Western")
              let categoryLabel = 'Western';
              if (
                outfit.topwear?.subtype === 'saree' ||
                outfit.base_type === 'saree_lehenga' ||
                (outfit.topwear?.subtype === 'kurta' && !outfit.bottomwear?.subtype?.includes('jean'))
              ) {
                categoryLabel = 'Ethnic';
              } else if (
                outfit.base_type === 'indo-western' ||
                (outfit.topwear?.subtype === 'kurta' && outfit.bottomwear?.subtype?.includes('jean'))
              ) {
                categoryLabel = 'Indo-Western';
              } else if (outfit.base_type === 'one_piece') {
                categoryLabel = 'Western';
              } else {
                categoryLabel = 'Western';
              }

              const isMostPopular = idx === 0 || idx === 1 || (outfit.styling_score && outfit.styling_score >= 95);

              return (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '24px',
                    border: '1px solid #ECE3E1',
                    padding: '14px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.04)',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'box-shadow 0.25s ease, transform 0.25s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.boxShadow = '0 16px 36px rgba(156,65,70,0.12)';
                    e.currentTarget.style.transform = 'translateY(-3px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.04)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  {/* TALL COLLAGE LAYOUT — Height increased to 450px as requested ("length meh bada hoga thodaa and thoda ache se organized") */}
                  <div
                    style={{
                      height: '450px',
                      minHeight: '450px',
                      maxHeight: '450px',
                      display: 'grid',
                      gridTemplateColumns: hasRightSide ? '1.18fr 1fr' : '1fr',
                      gap: '10px',
                      marginBottom: '14px',
                      position: 'relative',
                    }}
                  >
                    {/* Left: Primary Garment (Saree, Dress, Jumpsuit, Top, or Kurti) */}
                    <div
                      onClick={() => outfit.topwear && openProductDetail(outfit.topwear)}
                      title={`Click to view details: ${outfit.topwear?.product_name || outfit.topwear?.name}`}
                      style={{
                        height: '100%',
                        position: 'relative',
                        overflow: 'hidden',
                        borderRadius: '18px',
                        backgroundColor: '#FAF7F5',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '10px',
                        cursor: 'pointer',
                      }}
                    >
                      <img
                        src={cleanProductImageUrl(outfit.topwear?.image) || NEUTRAL_PLACEHOLDER_IMAGE}
                        alt={outfit.topwear?.product_name || 'Main Garment'}
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          e.currentTarget.onerror = null;
                          e.currentTarget.src = NEUTRAL_PLACEHOLDER_IMAGE;
                        }}
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'contain',
                          display: 'block',
                          transition: 'transform 0.3s ease',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.02)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
                      />

                      {/* Top-Left Badge (Matching Screenshot 2: "Most Popular") */}
                      {isMostPopular && (
                        <div
                          style={{
                            position: 'absolute',
                            top: '12px',
                            left: '12px',
                            background: 'linear-gradient(135deg, #DE5A69 0%, #C74554 100%)',
                            color: '#FFFFFF',
                            padding: '5px 12px',
                            borderRadius: '999px',
                            fontSize: '0.74rem',
                            fontWeight: 700,
                            letterSpacing: '0.2px',
                            boxShadow: '0 2px 8px rgba(199, 69, 84, 0.35)',
                            pointerEvents: 'none',
                            zIndex: 2,
                          }}
                        >
                          Most Popular
                        </div>
                      )}

                      {/* Category Pill Floating on Main Garment (Matching Screenshot 1 & 2: "Ethnic" / "Indo-Western") */}
                      <div
                        style={{
                          position: 'absolute',
                          bottom: '14px',
                          left: '14px',
                          backgroundColor: '#FFFFFF',
                          color: '#1F191B',
                          padding: '6px 14px',
                          borderRadius: '999px',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                          boxShadow: '0 3px 10px rgba(0,0,0,0.12)',
                          pointerEvents: 'none',
                          zIndex: 2,
                        }}
                      >
                        {categoryLabel}
                      </div>
                    </div>

                    {/* Right Column: Stacked Secondary Pieces */}
                    {hasRightSide && (
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateRows: rightBottomItem ? '1fr 1fr' : '1fr',
                          gap: '10px',
                          height: '100%',
                          minHeight: 0,
                        }}
                      >
                        {/* Upper Right Item (Bottomwear, Blouse, or Footwear) */}
                        {rightTopItem && (
                          <div
                            onClick={() => openProductDetail(rightTopItem)}
                            title={`Click to view details: ${rightTopItem.product_name || rightTopItem.name}`}
                            style={{
                              position: 'relative',
                              overflow: 'hidden',
                              borderRadius: '18px',
                              backgroundColor: '#FAF7F5',
                              height: '100%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              padding: '8px',
                              cursor: 'pointer',
                            }}
                          >
                            <img
                              src={cleanProductImageUrl(rightTopItem.image) || NEUTRAL_PLACEHOLDER_IMAGE}
                              alt={rightTopItem.product_name || 'Item'}
                              referrerPolicy="no-referrer"
                              onError={(e) => {
                                e.currentTarget.onerror = null;
                                e.currentTarget.src = NEUTRAL_PLACEHOLDER_IMAGE;
                              }}
                              style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'contain',
                                display: 'block',
                                transition: 'transform 0.3s ease',
                              }}
                              onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.02)'; }}
                              onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
                            />

                            {/* Floating Heart Button (Matching Screenshot 2) */}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleWishlist(rightTopItem);
                              }}
                              title="Add to wishlist"
                              style={{
                                position: 'absolute',
                                top: '10px',
                                right: '10px',
                                width: '34px',
                                height: '34px',
                                borderRadius: '50%',
                                backgroundColor: '#FFFFFF',
                                boxShadow: '0 2px 8px rgba(0,0,0,0.14)',
                                border: 'none',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                cursor: 'pointer',
                                zIndex: 2,
                                transition: 'transform 0.15s ease',
                              }}
                              onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.08)'; }}
                              onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
                            >
                              <Heart
                                size={17}
                                fill={isWishlisted(rightTopItem?.product_id) ? '#9C4146' : 'none'}
                                color="#9C4146"
                              />
                            </button>
                          </div>
                        )}

                        {/* Lower Right Item (Shoes, Earrings, Jewellery, or Bag) */}
                        {rightBottomItem && (
                          <div
                            onClick={() => openProductDetail(rightBottomItem)}
                            title={`Click to view details: ${rightBottomItem.product_name || rightBottomItem.name}`}
                            style={{
                              position: 'relative',
                              overflow: 'hidden',
                              borderRadius: '18px',
                              backgroundColor: '#FAF7F5',
                              height: '100%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              padding: '8px',
                              cursor: 'pointer',
                            }}
                          >
                            <img
                              src={cleanProductImageUrl(rightBottomItem.image) || NEUTRAL_PLACEHOLDER_IMAGE}
                              alt={rightBottomItem.product_name || 'Item'}
                              referrerPolicy="no-referrer"
                              onError={(e) => {
                                e.currentTarget.onerror = null;
                                e.currentTarget.src = NEUTRAL_PLACEHOLDER_IMAGE;
                              }}
                              style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'contain',
                                display: 'block',
                                transition: 'transform 0.3s ease',
                              }}
                              onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.02)'; }}
                              onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Personalisation Reason Tag (if curated for logged-in user) */}
                  {outfit.is_personalised && outfit.personalisation_reason && (
                    <div
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        backgroundColor: '#FAF5F4',
                        border: '1px solid #EADBDA',
                        borderRadius: '8px',
                        padding: '4px 10px',
                        marginBottom: '8px',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        color: '#9C4146',
                        alignSelf: 'flex-start',
                      }}
                    >
                      <Sparkles size={13} color="#9C4146" />
                      <span>{outfit.personalisation_reason}</span>
                    </div>
                  )}

                  {/* Clean Look Title & Total Price Row */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'baseline',
                      padding: '0 4px',
                      marginBottom: '8px',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.94rem', fontWeight: 700, color: '#1F191B' }}>
                        {outfit.topwear?.subtype === 'saree' ? 'Complete Saree Ensemble' :
                         outfit.base_type === 'indo-western' ? 'Indo-Western Co-ord' :
                         outfit.is_dress ? 'Classic One-Piece Look' :
                         'Curated Two-Piece Look'}
                      </div>
                      <div style={{ fontSize: '0.74rem', color: '#8A7A7F', marginTop: '2px' }}>
                        {outfit.style_verdict || 'Perfect styling harmony across pieces'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#9C4146' }}>
                        ₹{currentTotal.toLocaleString()}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#8A7A7F', fontWeight: 500 }}>
                        Outfit Total
                      </div>
                    </div>
                  </div>

                  {/* COINS REMAINING BADGE */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '8px',
                      padding: '10px 18px',
                      backgroundColor: '#FAF7F5',
                      border: '1px solid #ECE3E1',
                      borderRadius: '999px',
                      margin: '12px 0 16px 0',
                      fontSize: '0.88rem',
                      fontWeight: 600,
                      color: '#4A3E42',
                    }}
                  >
                    <span style={{ fontSize: '1rem' }}>🪙</span>
                    <span>{coinsLeft.toLocaleString()} coins remaining</span>
                  </div>

                  {/* BOTTOM ACTION BUTTONS (Matching Screenshot 1 Pixel-Perfect) */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1.35fr',
                      gap: '10px',
                      marginTop: 'auto',
                    }}
                  >
                    {/* View Details Button (Outline Pill) */}
                    <button
                      type="button"
                      onClick={() => outfit.topwear && openProductDetail(outfit.topwear)}
                      style={{
                        padding: '11px 18px',
                        borderRadius: '999px',
                        border: '1.5px solid #9C4146',
                        backgroundColor: '#FFFFFF',
                        color: '#9C4146',
                        fontSize: '0.9rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        textAlign: 'center',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#FAF5F4';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#FFFFFF';
                      }}
                    >
                      View Details
                    </button>

                    {/* Add Outfit to Bag Button (Rose/Burgundy Solid Pill) */}
                    <button
                      type="button"
                      onClick={() => handleAddFullOutfitToBag(outfit, idx)}
                      style={{
                        padding: '11px 20px',
                        borderRadius: '999px',
                        border: 'none',
                        backgroundColor: addedOutfitIndex === idx ? '#10B981' : '#B44A59',
                        color: '#FFFFFF',
                        fontSize: '0.9rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        boxShadow: '0 4px 14px rgba(180, 74, 89, 0.28)',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (addedOutfitIndex !== idx) {
                          e.currentTarget.style.backgroundColor = '#9F3E4C';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (addedOutfitIndex !== idx) {
                          e.currentTarget.style.backgroundColor = '#B44A59';
                        }
                      }}
                    >
                      {addedOutfitIndex === idx ? (
                        <>
                          <Check size={17} /> Added to Bag!
                        </>
                      ) : (
                        <>
                          <ShoppingBag size={17} /> Add Outfit to Bag
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Show More Looks Pagination Button */}
        {!loading && baseFilteredOutfits.length > visibleCount && (
          <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
            <button
              onClick={() => setVisibleCount((prev) => prev + 24)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#FFFFFF',
                color: '#9C4146',
                border: '1.5px solid #9C4146',
                borderRadius: '999px',
                padding: '0.85rem 2.25rem',
                fontSize: '0.92rem',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 4px 16px rgba(156, 65, 70, 0.12)',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#FAF5F4';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#FFFFFF';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
            >
              <span>Show More Looks (+24)</span>
              <span style={{ fontSize: '0.8rem', color: '#8A7A7F' }}>
                (Showing {Math.min(visibleCount, baseFilteredOutfits.length)} of {baseFilteredOutfits.length})
              </span>
              <ChevronDown size={16} />
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
