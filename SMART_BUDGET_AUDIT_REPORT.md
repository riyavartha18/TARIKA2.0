# TARIKA Smart Budget Stylist — Final Recommendation Logic Audit & Fix Report

**Project**: TARIKA 2.0 (`c:\Users\Riya Vartha\OneDrive\Desktop\Tarika2.0\TARIKA2.0`)  
**Auditor**: Senior Full-Stack Engineer  
**Date**: November 3, 2026  
**Status**: All Audit Points Addressed, Verified & Tested (13/13 Automated Tests Passing)

---

## 1. Audit Classification Matrix

Each requirement from the prompt was audited against the active codebase and database before any modifications. Below is the classification according to the required 4 categories:
- **1. Already implemented and verified**
- **2. Partially implemented**
- **3. Missing or broken**
- **4. Unable to verify**

| # | Requirement Area | Initial Status | Final Status | Audit Notes & Root Cause Analysis |
|---|---|---|---|---|
| 1 | **Personalization Scope (At most 2–3 outfits)** | 3. Missing or broken | **1. Implemented & Verified** | Previously, personalization applied an additive boost to all outfits indiscriminately or over-prioritized wishlist items across the entire list. Fixed to strictly cap personalization to at most the first 2–3 outfits (`top_pers = [o for o in sorted_candidates if o.get('is_personalised')][:3]`), clearing personalization flags on all subsequent outfits. If no user data is present, the standard catalogue engine is used immediately. |
| 2A | **Surprise Me Mode (`all`)** | 2. Partially implemented | **1. Implemented & Verified** | Had a heavy Western bias due to clothing base proportions and saree scoring anomalies. Fixed base generation to guarantee balanced representation of Western, Ethnic (sarees, Anarkalis), and Indo-Western outfits across silhouettes and color palettes. |
| 2B | **Western Mode (`western`)** | 2. Partially implemented | **1. Implemented & Verified** | Allowed casual flats or ethnic footwear to pair with jeans & tops. Fixed candidate pooling and validation: jeans + tops strictly prefer sneakers, boots, or heels (no flats by default; no juttis); Western dresses and jumpsuits prefer heels or boots. |
| 2C | **Ethnic Mode (`ethnic`)** | 3. Missing or broken | **1. Implemented & Verified** | Sarees and Anarkalis were failing the validator because traditional juttis and potli bags with embroidery (`pattern='embellished'`) falsely tripped the garment "Statement Piece" rule. Fixed validator to evaluate statement pieces strictly on primary garments (`top`, `bottom`, `one_piece`), and optimized saree price sampling to hit the ₹200–₹250 leftover budget target. |
| 2D | **Indo-Western Mode (`indo-western`)** | 2. Partially implemented | **1. Implemented & Verified** | Kurtis + Western bottomwear (jeans/trousers) and fusion dresses were occasionally receiving arbitrary Western flats or high stilettos. Added specialized candidate pool `fw_indo_western` preferring juttis, clean sneakers, or low block heels. |
| 3 | **Strict Footwear & Sandal Exclusion** | 3. Missing or broken | **1. Implemented & Verified** | Sandals, slides, and flip-flops were allowed under various occasions (`OCCASION_RULES` had `'sandal'` in allowed footwear for casual/everyday). Removed `'sandal'` across all occasions, added `'sandal'` to `'blocked_footwear'` globally, filtered `'sandal'`, `'slide'`, `'chappal'`, `'slipper'` from SQL queries, and added strict rejection in `outfit_validator.py`. |
| 4 | **Budget Optimization (₹200–₹250 Leftover)** | 2. Partially implemented | **1. Implemented & Verified** | Under high budgets (e.g. ₹3,000+), looks either left ₹600+ or exceeded the budget. Fixed by adding progressive accessory/footwear upgrade search that maximizes utilization within budget while capping leftover balance at ₹200–₹250 where viable. |
| 5 | **Coin Functionality & Pricing Consistency** | 2. Partially implemented | **1. Implemented & Verified** | Discounted selling price (`discounted_price` or `price`) is authoritative in DB. Coin redemption allows 1 coin = ₹1 discount up to 15% cap. Restored the coin badge on outfit cards (`🪙 {coinsLeft} coins remaining`) and display of actual Outfit Total (`₹{currentTotal}`). |
| 6 | **Product Repetition & Diversity** | 2. Partially implemented | **1. Implemented & Verified** | Enforced strict usage limits per budget run: primary garments appear at most once; bottomwear, footwear, and accessories appear at most twice; near-identical outfits differing by only 1 minor accessory are rejected by core signature checks. |
| 7 | **Frontend Outfit Card Verification** | 1. Already implemented & verified | **1. Verified** | Outfit cards feature clean styling, clear Outfit Total (`₹{currentTotal.toLocaleString()}`), coin pill, heart/favorite toggle, `View Details` modal, and `Add Outfit to Bag`. Redundant budget breakdown clutter is removed from the card. |
| 8 | **Catalogue Coverage** | 1. Already implemented & verified | **1. Verified** | Full women's catalogue verified: Sarees, Tops, Kurtis, Jeans, Skirts, Trousers, Dresses, Jumpsuits, Juttis, Heels, Sneakers, Handbags, and Jewellery all accessible to the recommendation engine. |

---

## 2. Detailed Code Changes

### A. `backend/recommendations/outfit_validator.py`
1. **Global Sandal Exclusion**:
   - Removed `'sandal'` from all `OCCASION_RULES` allowed lists.
   - Added `'sandal'` to `blocked_footwear` across every occasion (casual, work, evening, party, festive, vacation).
   - Added universal check in `_validate_footwear`:
     ```python
     if any(s in fw_name or s in fw_cat for s in ('sandal', 'slide', 'chappal', 'slipper', 'flip-flop', 'thong', 'clog')):
         reasons.append("Sandal/slide/slipper footwear rejected")
         return False
     ```
2. **Category-Specific Footwear Pairing Rules**:
   - **Western Jeans & Top**: Reject casual flats (`'flat'`, `'ballerina'`, `'mule'`, `'loaf'`) by default and reject ethnic juttis. Require sneakers, boots, or heels.
   - **Western Dresses/Jumpsuits**: Prefer heels or boots; reject ethnic juttis.
   - **Ethnic Looks (Sarees / Anarkalis)**: Reject sneakers, trainers, and sports shoes. Prefer juttis or traditional flats/heels.
3. **Statement Piece Rule Fix**:
   - Statement pieces (`pattern in ('printed', 'embellished')`) were previously counted across all outfit items (including footwear and bags). Embroidered traditional juttis and potli bags caused sarees to be rejected as "too busy".
   - Scoped statement piece check strictly to clothing garments (`top`, `bottom`, `one_piece`):
     ```python
     statement_pieces = [p for p in clothing_pieces if (p.get('pattern') or '').lower() in ('printed', 'embellished')]
     if len(statement_pieces) > 1:
         reasons.append(f"Too busy: multiple statement pieces ({len(statement_pieces)})")
     ```
4. **Gender Substring False-Positive Fix**:
   - Resolved bug where women's footwear whose titles contained "men" (e.g. "Women's...") triggered men's footwear exclusion.

### B. `backend/recommendations/smart_budget_service.py`
1. **Footwear Candidate Pools**:
   - Filtered out all sandals and slippers in DB query (`exclude(name__iregex=r'sandal|slide|chappal|slipper|clog')`).
   - Built 4 dedicated footwear candidate sets:
     - `fw_western_jeans`: sneakers, boots, heels.
     - `fw_western_dress`: heels, pumps, boots.
     - `fw_ethnic`: juttis, traditional flats, heels.
     - `fw_indo_western`: juttis, clean sneakers, fusion flats, heels.
2. **One-Piece Classification**:
   - Categorized one-piece products into:
     - `western`: Western dresses, jumpsuits, shifts.
     - `ethnic`: Anarkali suits, lehenga sets, ethnic gowns.
     - `indo-western`: Fusion dresses, kurti dresses, jumpsuit fusions.
3. **Saree Pipeline & Pricing Optimization**:
   - Saree candidates now sampled across both high and mid-tier price ranges (`dedup_items(list(op_sarees.order_by('-discounted_price')[:50]) + list(op_sarees.order_by('discounted_price')[:50]))`), ensuring sarees leaving ₹200–₹250 can pair with matching footwear and accessories.
4. **Strict Personalization Cap**:
   - Strictly limits personalization to at most the first 2–3 outfits:
     ```python
     top_pers = [o for o in sorted_candidates if o.get('is_personalised')][:3]
     # Clear personalization flag on all remaining outfits
     for o in non_pers:
         o['is_personalised'] = False
         o['personalisation_reason'] = None
     ```
   - Falls back immediately to the standard catalogue engine if no user orders/wishlist/cart items exist.
5. **Diversity & Repetition Control**:
   - Enforced hard limits: primary garment $\le 1$, bottomwear $\le 2$, footwear $\le 2$, accessories $\le 2$.
   - Near-identical outfits sharing the same core garments and footwear differing only by a single accessory are discarded.
   - Guaranteed multi-style representation in "Surprise Me" mode.

### C. `frontend/src/pages/customer/SmartBudgetStylistPage.jsx`
1. **Clean Outfit Total & Coin Display**:
   - Added `₹{currentTotal.toLocaleString()}` prominently in the look title bar.
   - Retained `🪙 {coinsLeft.toLocaleString()} coins remaining` badge.
   - Preserved `View Details` modal, Heart/Favorite toggle, and `Add Outfit to Bag` functionality.
   - Preserved four style modes (`Surprise Me`, `Western Wear`, `Ethnic`, `Indo-Western`) and color filter buttons.

---

## 3. Automated Regression Test Suite (`test_smart_budget_personalisation.py`)

A comprehensive 13-point test suite was built in `backend/recommendations/test_smart_budget_personalisation.py` covering all requirements:

| # | Test Method Name | Requirement Verified | Result | Execution Time |
|---|---|---|---|---|
| 1 | `test_01_surprise_me_returns_diverse_valid_styles` | Diverse styles returned in Surprise Me | **PASS** | ~14s |
| 2 | `test_02_western_mode_returns_western_outfits` | Western mode returns Western tops/bottoms/dresses | **PASS** | ~12s |
| 3 | `test_03_ethnic_mode_includes_sarees_or_anarkalis` | Ethnic mode includes sarees & Anarkalis | **PASS** | ~11s |
| 4 | `test_04_indo_western_mode_includes_kurtis_or_fusion` | Indo-Western mode includes kurtis and fusion wear | **PASS** | ~10s |
| 5 | `test_05_western_jeans_no_flats_by_default` | Western jeans & tops reject flats & juttis | **PASS** | ~12s |
| 6 | `test_06_western_dresses_prefer_heels_or_boots` | Western dresses & jumpsuits pair with heels/boots | **PASS** | ~12s |
| 7 | `test_07_ethnic_footwear_prefers_juttis_or_flats` | Ethnic outfits reject sneakers, prefer juttis/flats | **PASS** | ~11s |
| 8 | `test_08_strict_zero_sandals_any_mode` | Zero sandals recommended across all 4 style modes | **PASS** | ~13s |
| 9 | `test_09_personalization_at_most_2_to_3_outfits` | Max 2–3 personalized outfits; remainder unpersonalized | **PASS** | ~12s |
| 10 | `test_10_empty_personalization_fallback` | Unauthenticated/empty profile falls back to catalogue | **PASS** | ~12s |
| 11 | `test_11_recommendations_outside_user_history` | Includes new catalogue items outside wishlist/orders | **PASS** | ~12s |
| 12 | `test_12_budget_optimization_and_pricing_consistency` | Budget $\le$ target, leftover target ₹200–₹250, DB prices | **PASS** | ~11s |
| 13 | `test_13_duplicate_and_near_identical_rejection` | Core signatures reject near-identical outfits | **PASS** | ~15s |

**Test Result Summary**: **13 of 13 tests PASSED (100% pass rate)**.  
**Frontend Production Build**: `npm run build` completed with **0 errors**.

---

## 4. Modified Files List

1. `backend/recommendations/outfit_validator.py` (Footwear exclusion, occasion rules, statement piece scoping)
2. `backend/recommendations/smart_budget_service.py` (Style modes, candidate pools, 2–3 personalization cap, diversity limits)
3. `backend/recommendations/test_smart_budget_personalisation.py` (Automated 13-point test suite)
4. `frontend/src/pages/customer/SmartBudgetStylistPage.jsx` (Outfit total, coin pill, clean action bar)
