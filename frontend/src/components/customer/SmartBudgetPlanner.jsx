import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  ShoppingBag,
  Sliders,
  Check,
  Tag,
  ArrowRight,
  TrendingUp,
  Heart,
  ShieldCheck,
  BookmarkPlus,
} from 'lucide-react';
import { getSmartBudgetOutfits, addWardrobeItem } from '../../services/api';
import { useCustomer } from '../../context/CustomerContext';
import { useAuth } from '../../auth/AuthContext';

const BUDGET_PRESETS = [1500, 2500, 3500, 5000];
const OCCASIONS = [
  { id: 'casual', label: 'Casual' },
  { id: 'formal', label: 'Formal / Work' },
  { id: 'party', label: 'Party / Evening' },
  { id: 'ethnic', label: 'Ethnic / Festive' },
];

export default function SmartBudgetPlanner() {
  const { addToBag, openProductDetail } = useCustomer();
  const { user, token } = useAuth();

  // Detect customer's gender from profile
  const userGenderRaw = (user?.gender || '').toLowerCase();
  const initialGender = userGenderRaw.includes('female') || userGenderRaw.includes('women') ? 'women' : 'men';

  const [budget, setBudget] = useState(2500);
  const [gender, setGender] = useState(initialGender);
  const [occasion, setOccasion] = useState('casual');

  const [loading, setLoading] = useState(false);
  const [outfitsData, setOutfitsData] = useState(null);
  const [error, setError] = useState('');
  const [addedOutfitIndex, setAddedOutfitIndex] = useState(null);
  const [savedOutfitIndex, setSavedOutfitIndex] = useState(null);

  const fetchOutfits = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await getSmartBudgetOutfits({
      budget,
      gender,
      occasion,
    });
    setLoading(false);
    if (res.success) {
      setOutfitsData(res);
    } else {
      setError(res.error || 'Failed to curate outfits for this budget.');
    }
  }, [budget, gender, occasion]);

  useEffect(() => {
    fetchOutfits();
  }, [fetchOutfits]);

  const handleAddFullOutfitToBag = (outfit, index) => {
    if (outfit.topwear) addToBag(outfit.topwear, 1);
    if (outfit.bottomwear) addToBag(outfit.bottomwear, 1);
    if (outfit.footwear) addToBag(outfit.footwear, 1);
    if (outfit.accessory) addToBag(outfit.accessory, 1);

    setAddedOutfitIndex(index);
    setTimeout(() => setAddedOutfitIndex(null), 2500);
  };

  const handleSaveToWardrobe = async (outfit, index) => {
    if (!token) return;
    setSavedOutfitIndex(index);

    if (outfit.topwear) {
      await addWardrobeItem(token, {
        item_name: outfit.topwear.product_name || outfit.topwear.name,
        category: 'Tops',
        primary_color: outfit.top_color || 'Neutral',
        occasion: occasion.charAt(0).toUpperCase() + occasion.slice(1),
        image_url: outfit.topwear.image,
      });
    }

    if (outfit.bottomwear) {
      await addWardrobeItem(token, {
        item_name: outfit.bottomwear.product_name || outfit.bottomwear.name,
        category: 'Bottoms',
        primary_color: outfit.bot_color || 'Neutral',
        occasion: occasion.charAt(0).toUpperCase() + occasion.slice(1),
        image_url: outfit.bottomwear.image,
      });
    }

    setTimeout(() => setSavedOutfitIndex(null), 2500);
  };

  return (
    <section
      className="smart-budget-planner-section"
      style={{
        margin: '3rem 0',
        backgroundColor: '#FFFFFF',
        borderRadius: '24px',
        border: '1px solid #EADBDA',
        overflow: 'hidden',
        boxShadow: '0 8px 30px rgba(156, 65, 70, 0.05)',
      }}
    >
      {/* Header Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, #1F191B 0%, #36282B 100%)',
          color: '#FFFFFF',
          padding: '2.5rem 2rem',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1.5rem',
        }}
      >
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: '#D8727E',
              fontSize: '0.82rem',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '1.2px',
              marginBottom: '0.5rem',
            }}
          >
            <Sparkles size={14} /> AI Stylist & Color Theory Engine
          </div>
          <h2
            style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: '2rem',
              margin: '0 0 0.5rem 0',
              fontWeight: 600,
            }}
          >
            Smart Budget Outfit Builder
          </h2>
          <p style={{ color: '#E2D3D2', fontSize: '0.92rem', margin: 0, maxWidth: '650px', lineHeight: 1.5 }}>
            Outfits built with <strong>genuine fashion compatibility</strong> — not just price math.
            Evaluated using Color Theory contrasts, Occasion Harmony, and Apriori Basket Mining.
          </p>
        </div>

        {/* Gender Toggle */}
        <div
          style={{
            display: 'inline-flex',
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            padding: '4px',
            borderRadius: '999px',
            border: '1px solid rgba(255, 255, 255, 0.15)',
          }}
        >
          <button
            onClick={() => setGender('men')}
            style={{
              padding: '8px 20px',
              borderRadius: '999px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.88rem',
              fontWeight: gender === 'men' ? 600 : 400,
              backgroundColor: gender === 'men' ? '#D8727E' : 'transparent',
              color: '#FFFFFF',
              transition: 'all 0.2s',
            }}
          >
            Men's Looks
          </button>
          <button
            onClick={() => setGender('women')}
            style={{
              padding: '8px 20px',
              borderRadius: '999px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.88rem',
              fontWeight: gender === 'women' ? 600 : 400,
              backgroundColor: gender === 'women' ? '#D8727E' : 'transparent',
              color: '#FFFFFF',
              transition: 'all 0.2s',
            }}
          >
            Women's Looks
          </button>
        </div>
      </div>

      {/* Control Panel: Budget Slider & Occasions */}
      <div
        style={{
          padding: '1.75rem 2rem',
          backgroundColor: '#FAF7F5',
          borderBottom: '1px solid #F0E2E0',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1.5rem',
        }}
      >
        {/* Budget Controller */}
        <div style={{ flex: '1 1 340px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.86rem', fontWeight: 600, color: '#3A2E32' }}>
              Maximum Total Budget:
            </span>
            <span
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '1.3rem',
                fontWeight: 700,
                color: '#9C4146',
              }}
            >
              ₹{budget.toLocaleString()}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <input
              type="range"
              min="1000"
              max="7000"
              step="250"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              style={{
                flex: 1,
                accentColor: '#9C4146',
                cursor: 'pointer',
              }}
            />
          </div>

          {/* Preset Buttons */}
          <div style={{ display: 'flex', gap: '6px', marginTop: '10px' }}>
            {BUDGET_PRESETS.map((val) => (
              <button
                key={val}
                onClick={() => setBudget(val)}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: budget === val ? '1px solid #9C4146' : '1px solid #D6C7C5',
                  backgroundColor: budget === val ? '#FAF5F4' : '#FFFFFF',
                  color: budget === val ? '#9C4146' : '#6B5E63',
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                ₹{val}
              </button>
            ))}
          </div>
        </div>

        {/* Occasion Filter */}
        <div style={{ flex: '1 1 300px' }}>
          <span style={{ display: 'block', fontSize: '0.86rem', fontWeight: 600, color: '#3A2E32', marginBottom: '8px' }}>
            Select Occasion:
          </span>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {OCCASIONS.map((occ) => (
              <button
                key={occ.id}
                onClick={() => setOccasion(occ.id)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '999px',
                  border: occasion === occ.id ? '1px solid #9C4146' : '1px solid #EADBDA',
                  backgroundColor: occasion === occ.id ? '#9C4146' : '#FFFFFF',
                  color: occasion === occ.id ? '#FFFFFF' : '#4A3E42',
                  fontSize: '0.82rem',
                  fontWeight: occasion === occ.id ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {occ.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Outfits Showcase */}
      <div style={{ padding: '2rem' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem 0', color: '#6B5E63' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                border: '3px solid #EADBDA',
                borderTopColor: '#9C4146',
                animation: 'spin 0.8s linear infinite',
                margin: '0 auto 1rem',
              }}
            />
            <p style={{ margin: 0 }}>Matching silhouettes, analyzing color harmony & optimizing budget...</p>
          </div>
        ) : error || !outfitsData?.outfits?.length ? (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#6B5E63' }}>
            <p>{error || 'No outfits matched this specific budget. Try raising the slider or switching occasion.'}</p>
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
              gap: '1.75rem',
            }}
          >
            {outfitsData.outfits.map((outfit, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: '#FFFFFF',
                  borderRadius: '20px',
                  border: idx === 0 ? '2px solid #9C4146' : '1px solid #EADBDA',
                  boxShadow: idx === 0 ? '0 10px 30px rgba(156, 65, 70, 0.12)' : '0 4px 16px rgba(0,0,0,0.04)',
                  padding: '1.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                }}
              >
                {/* Tier Badge */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <span
                    style={{
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.8px',
                      padding: '4px 12px',
                      borderRadius: '999px',
                      backgroundColor: idx === 0 ? '#9C4146' : '#FAF7F5',
                      color: idx === 0 ? '#FFFFFF' : '#4A3E42',
                      border: idx === 0 ? 'none' : '1px solid #EADBDA',
                    }}
                  >
                    {outfit.tier}
                  </span>

                  {/* Harmony Score Pill */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      backgroundColor: '#E6FCF5',
                      color: '#0CA678',
                      padding: '4px 10px',
                      borderRadius: '999px',
                      fontSize: '0.78rem',
                      fontWeight: 700,
                    }}
                  >
                    <ShieldCheck size={14} />
                    <span>{outfit.styling_score}% Harmony</span>
                  </div>
                </div>

                {/* Garments Showcase Layout — Click to view single product */}
                <div style={{ display: 'grid', gridTemplateColumns: outfit.bottomwear || outfit.footwear || outfit.accessory ? '1fr 1fr' : '1fr', gap: '1rem', marginBottom: '1.25rem' }}>
                  {/* Primary Garment: Topwear or Jumpsuit / Dress */}
                  <div
                    onClick={() => outfit.topwear && openProductDetail(outfit.topwear)}
                    title={`Click to view & shop: ${outfit.topwear?.product_name || outfit.topwear?.name}`}
                    style={{
                      backgroundColor: '#FAF7F5',
                      borderRadius: '12px',
                      padding: '0.75rem',
                      border: '1px solid #F0E2E0',
                      display: 'flex',
                      flexDirection: 'column',
                      cursor: 'pointer',
                      transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.06)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                  >
                    <div style={{ height: '140px', borderRadius: '8px', overflow: 'hidden', marginBottom: '0.5rem' }}>
                      <img
                        src={outfit.topwear?.image}
                        alt={outfit.topwear?.product_name}
                        onError={(e) => {
                          e.currentTarget.onerror = null;
                          e.currentTarget.src = 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=600&q=80';
                        }}
                        style={{ width: '100%', height: '100%', objectFit: 'contain', padding: '4px' }}
                      />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.68rem', color: '#9C4146', fontWeight: 600, textTransform: 'uppercase' }}>
                        {outfit.is_dress ? (outfit.garment_type || 'One-Piece') : 'Topwear'}
                      </span>
                      <span style={{ fontSize: '0.64rem', color: '#9C4146', fontWeight: 700 }}>Shop ↗</span>
                    </div>
                    <h4
                      style={{
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        color: '#1F191B',
                        margin: '2px 0 6px',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        height: '2.4em',
                        lineHeight: 1.2,
                      }}
                    >
                      {outfit.topwear?.product_name || outfit.topwear?.name}
                    </h4>
                    <span style={{ marginTop: 'auto', fontSize: '0.88rem', fontWeight: 700, color: '#1F191B' }}>
                      ₹{Math.round(outfit.topwear?.discount_price || outfit.topwear?.selling_price || 0)}
                    </span>
                  </div>

                  {/* Secondary Garment: Bottomwear OR Footwear/Accessory for Standalone */}
                  {(outfit.bottomwear || outfit.footwear || outfit.accessory) && (
                    <div
                      onClick={() => {
                        const sec = outfit.bottomwear || outfit.footwear || outfit.accessory;
                        if (sec) openProductDetail(sec);
                      }}
                      title="Click to view & shop individually"
                      style={{
                        backgroundColor: '#FAF7F5',
                        borderRadius: '12px',
                        padding: '0.75rem',
                        border: '1px solid #F0E2E0',
                        display: 'flex',
                        flexDirection: 'column',
                        cursor: 'pointer',
                        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 6px 16px rgba(0,0,0,0.06)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                    >
                      {(() => {
                        const sec = outfit.bottomwear || outfit.footwear || outfit.accessory;
                        const label = outfit.bottomwear ? 'Bottomwear' : (outfit.footwear ? 'Footwear' : 'Accessory');
                        return (
                          <>
                            <div style={{ height: '140px', borderRadius: '8px', overflow: 'hidden', marginBottom: '0.5rem' }}>
                              <img
                                src={sec?.image}
                                alt={sec?.product_name}
                                onError={(e) => {
                                  e.currentTarget.onerror = null;
                                  e.currentTarget.src = 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=600&q=80';
                                }}
                                style={{ width: '100%', height: '100%', objectFit: 'contain', padding: '4px' }}
                              />
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.68rem', color: '#9C4146', fontWeight: 600, textTransform: 'uppercase' }}>
                                {label}
                              </span>
                              <span style={{ fontSize: '0.64rem', color: '#9C4146', fontWeight: 700 }}>Shop ↗</span>
                            </div>
                            <h4
                              style={{
                                fontSize: '0.82rem',
                                fontWeight: 600,
                                color: '#1F191B',
                                margin: '2px 0 6px',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                height: '2.4em',
                                lineHeight: 1.2,
                              }}
                            >
                              {sec?.product_name || sec?.name}
                            </h4>
                            <span style={{ marginTop: 'auto', fontSize: '0.88rem', fontWeight: 700, color: '#1F191B' }}>
                              ₹{Math.round(sec?.discount_price || sec?.selling_price || 0)}
                            </span>
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>

                {/* Coins Remaining Badge */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    backgroundColor: '#FFFBEB',
                    border: '1px solid #FDE68A',
                    borderRadius: '10px',
                    padding: '6px 10px',
                    fontSize: '0.74rem',
                    color: '#92400E',
                    fontWeight: 600,
                    marginBottom: '0.85rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>🪙</span>
                    <span>
                      ₹{(outfit.coins_remaining !== undefined ? outfit.coins_remaining : outfit.savings).toLocaleString()} Coins Remaining from ₹{budget.toLocaleString()}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.68rem', backgroundColor: '#FEF3C7', padding: '2px 6px', borderRadius: '999px', fontWeight: 700 }}>
                    Saved
                  </span>
                </div>

                {/* Fashion Verdict Explanation */}
                <div
                  style={{
                    backgroundColor: '#FAF5F4',
                    borderRadius: '10px',
                    padding: '8px 12px',
                    fontSize: '0.78rem',
                    color: '#6B5E63',
                    marginBottom: '1.25rem',
                    borderLeft: '3px solid #9C4146',
                    lineHeight: 1.4,
                  }}
                >
                  <strong>Stylist Note:</strong> {outfit.style_verdict}
                </div>

                {/* Price & Savings Summary */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    marginBottom: '1rem',
                    borderTop: '1px solid #FAF0EE',
                    paddingTop: '0.75rem',
                  }}
                >
                  <div>
                    <span style={{ fontSize: '0.75rem', color: '#8A7A7F', display: 'block' }}>Outfit Total:</span>
                    <span
                      style={{
                        fontFamily: "'Playfair Display', serif",
                        fontSize: '1.35rem',
                        fontWeight: 700,
                        color: '#1F191B',
                      }}
                    >
                      ₹{outfit.total_price.toLocaleString()}
                    </span>
                  </div>

                  <span
                    style={{
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      color: '#0CA678',
                      backgroundColor: '#E6FCF5',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    Save ₹{outfit.coins_remaining !== undefined ? outfit.coins_remaining : outfit.savings} under budget
                  </span>
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '8px', marginTop: 'auto' }}>
                  <button
                    onClick={() => handleAddFullOutfitToBag(outfit, idx)}
                    className="tarika-btn-primary"
                    style={{
                      padding: '10px 14px',
                      fontSize: '0.84rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                    }}
                  >
                    {addedOutfitIndex === idx ? (
                      <>
                        <Check size={16} /> Look In Bag!
                      </>
                    ) : (
                      <>
                        <ShoppingBag size={16} /> Add Look to Bag
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => handleSaveToWardrobe(outfit, idx)}
                    title="Save entire look to your private wardrobe"
                    style={{
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid #D6C7C5',
                      backgroundColor: savedOutfitIndex === idx ? '#E6FCF5' : '#FFFFFF',
                      color: savedOutfitIndex === idx ? '#0CA678' : '#4A3E42',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {savedOutfitIndex === idx ? <Check size={16} /> : <BookmarkPlus size={16} />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
