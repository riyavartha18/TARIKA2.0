# TARIKA: Repository-Based Project Analysis

## Scope and evidence standard

This report describes the repository as inspected, including the current
working-tree state. It is not a claim that the remote database, every API, or
the production deployment was independently exercised. Statements about
implemented behavior are grounded in source files; documented example counts
are not treated as fresh measurements. Where the source does not establish a
fact, this report says so.

The repository already had uncommitted changes when it was inspected. No
existing project source files were changed for this report. Two requested
documentation files are the only intended additions.

## 1. Project Title

**TARIKA: A Role-Based Fashion Retail Platform with RFM Customer Analytics and
Demand-Informed Inventory Operations**

- **Main research/engineering domain:** Retail information systems and applied
  data analytics.
- **Application area:** Fashion e-commerce operations, customer segmentation
  and value analysis, product association recommendations, and warehouse
  replenishment support.
- **Important qualification:** The source contains analytics and decision
  support, but does not demonstrate a validated predictive demand model or
  measured business impact.

## 2. Abstract

Fashion retailers coordinate customer-facing commerce with inventory,
fulfillment, and customer-retention decisions, yet the repository does not
document a comparative baseline or a formally evaluated prior system. TARIKA
implements a web-based retail workflow that combines a React customer
storefront and role-specific staff portals with a Django REST API and a
PostgreSQL data store. Its operational functions cover product browsing,
authentication, cart and wishlist management, checkout, orders, warehouse
operations, and delivery status updates. Analytics include delivered-order
RFM scoring and rule-based segments, a separate standardized K-Means++
clustering workflow, cohort-based customer lifetime value calculations,
Apriori product associations, and product- and stock-related dashboards.
Demand tiers are derived from data-based terciles of observed units sold; an
ID3 decision tree is also computed for explanation, but the code explicitly
does not use that tree as the per-product demand label because its engagement
features do not provide useful predictive signal in the current data. The
stock recommendation uses observed units sold and current stock to calculate a
reorder gap. Source code and unit tests are present, but this inspection found
no train/test evaluation, model-quality metrics, benchmark, reproducible
dataset, or verified live-system results. TARIKA is therefore best described
as an implemented retail and analytics decision-support prototype whose
predictive effectiveness and operational impact remain to be experimentally
validated.

## 3. Keywords

Fashion retail; e-commerce; customer analytics; RFM analysis; K-Means++;
association rule mining; cohort analysis; inventory replenishment.

## 4. Introduction

Retail software must support a lifecycle that extends from product discovery
and checkout to inventory handling, delivery, returns, and customer retention.
TARIKA brings those activities into one codebase. The React application
provides a public homepage and customer shopping experience alongside admin,
warehouse, and delivery-partner portals. Django REST endpoints connect these
interfaces to PostgreSQL-backed product, customer, order, and operational
records.

The analytics-oriented motivation visible in the implementation is to make
retail data usable in day-to-day decisions: segment buyers from purchase
history, summarize historical customer value, surface product associations,
and prioritize stock actions. These are implementation goals inferred from
the modules and UI; the repository contains no author statement, formal
business case, or study establishing a quantified need or impact.

The application is relevant to apparel and other product retailers that need
to connect storefront activity with fulfillment and historical-sales
analytics. In particular, role-based interfaces separate customer actions
from administrative, warehouse, and delivery workflows. Analytics are
presented through admin modules and customer-facing offers, rather than as an
offline research notebook.

## 5. Problem Statement

**Repository-grounded problem framing:** implement an integrated system for
fashion retail transactions and operations, and expose customer- and
product-level historical analytics that can support campaign and replenishment
decisions.

The code attempts to address fragmented workflow through:

1. A shared product catalog and customer cart/checkout/order flow.
2. Role-based admin, warehouse, and delivery functions.
3. RFM-derived customer groups, customer value summaries, and targeted
   campaigns.
4. Product co-purchase rules and sales/stock reporting.

**Existing-system gap:** Not found in the source code. There is no documented
competitor comparison, literature review, baseline implementation, or measured
description of limitations in a prior retail system. Accordingly, the report
does not claim that existing approaches lack particular features or that
TARIKA outperforms them.

**Research gap:** The repository provides implementation evidence, not
comparative research evidence. It does not show that the computed demand
classes forecast future outcomes, that recommendations improve conversion, or
that segmentation increases retention or revenue.

## 6. Objectives

### Primary objectives represented in the implementation

1. **Provide a customer shopping workflow.** Browse and filter active
   products, manage a wishlist and cart, apply eligible campaigns, check out,
   and view orders. Core code includes `frontend/src/pages/customer/`,
   `backend/catalog/`, `backend/cart/`, and `backend/orders/`.
2. **Support staff operations by role.** Separate admin, warehouse, and
   delivery workflows, with API permissions and portal routes. Relevant code
   includes `frontend/src/App.jsx`, `backend/accounts/permissions.py`,
   `backend/warehouse/`, and `backend/delivery/`.
3. **Summarize historical customer behavior.** Calculate RFM metrics and
   scores, assign rule-based segments, and separately cluster stored RFM
   vectors using K-Means++. Relevant modules are in `backend/rfm_analysis/`.
4. **Estimate customer value from observed orders and retention history.**
   Produce historical CLV, value tiers, cohort survival summaries, and
   conditional future CLV when the observed history supports it. See
   `backend/clv/calc.py` and `backend/clv/service.py`.
5. **Expose product and stock decision support.** Mine product associations,
   derive demand labels, show product performance groupings, and compute stock
   gaps. See `backend/recommendations/`,
   `backend/demand_prediction/`, `backend/admin/performance_map.py`, and
   `backend/stock_to_be_ordered/`.

### Secondary objectives and implementation mechanisms

- Keep customer actions scoped to the authenticated customer and staff actions
  constrained by role.
- Reuse database-side aggregation, pagination, and cache/version keys for
  large analytics and catalog reads.
- Preserve existing PostgreSQL tables using unmanaged Django models where
  specified, while maintaining separate app-owned analytics/campaign tables.
- Surface explainable rules, tree splits, status transitions, or data-derived
  summaries where present.

These objectives describe code paths. The source does not establish that each
objective is met in a live deployment or at a specific scale.

## 7. Existing System and Limitations

### Documented baseline

Not found in the source code. The root `README.md` gives a one-line product
description. The other README files describe selected modules and setup, not
an existing competing or predecessor system. No literature review, existing
system architecture, baseline measurements, or controlled comparison is
included.

### Existing repository limitations that can be evidenced

- **Demand prediction is not established as predictive.** The ID3 engine
  calculates a tree from wishlist/cart counts, but the source says that the
  tree has negligible information gain on the current data and is not used for
  per-product tiers. Those tiers are assigned from observed `units_sold`
  terciles. There is no holdout evaluation.
- **Replenishment uses observed units, not a forecast horizon.** The stock
  workflow sets `predicted_demand = round(units_sold)` and computes the gap
  against available stock. No future period or lead-time model is represented
  in that calculation.
- **Recommendation baskets are inferred from customer and purchase date.**
  `RecommendationService.fetch_delivered_order_items` creates a synthetic key
  from `(customer_id, purchase_date)` and includes groups with at least two
  distinct products. This does not necessarily mean a source order ID is a
  multi-item basket.
- **Schema descriptions disagree.** Current catalog and order code maps to a
  `products` table keyed by `product_key` and an `orders` table with `orderid`
  and product fields on each row. Some READMEs describe older `categories`,
  separate inventory, product counts, and order-item relationships. In
  addition, `warehouse.models.Order` maps a different field layout to the
  same `orders` table name as `orders.models.Order`. Schema reconciliation is
  required before assuming all modules can operate against one database
  schema. The backend setup README also says there are no CSV files in the
  repository, whereas the current tree contains price-correction preview and
  recovery CSV artifacts; those files are not documented training data.
- **Replenishment stock timing differs by operation.** The individual
  replenishment path applies ordered quantity to `available_quantity`
  immediately and marks the purchase order `stock_applied`; bulk order paths
  record purchase orders without applying stock until receipt. The
  `ReplenishmentOrder` model docstring describes receipt as the stock-increase
  point generally. This behavior and its operator-facing meaning should be
  reconciled.
- **Database/authentication configuration has a migration boundary.** The
  backend setup document discusses Neon PostgreSQL, while active REST
  authentication uses `SupabaseAuthService` and raw SQL against
  `public.app_users` / `public.customers`; a `NeonAuthService` module also
  exists but is not the service imported by `accounts.authentication` or the
  serializers. A Neon PostgreSQL URL alone does not provide Supabase Auth
  schema/services.
- **Analytics are integrated in the current admin UI, but are not
  experimentally validated.** `AdminAnalyticsView.jsx` requests demand,
  slow-inventory, RFM, CLV, and sales-history data;
  `AdminDashboardView.jsx` requests the product-performance API and renders
  `ProductPerformanceMap.jsx`. This is interface integration evidence, not
  proof of correct live-data results.
- **Project dependency reproducibility is incomplete.** A frontend lockfile
  exists. A backend dependency manifest was Not found in the source code.
- **Evaluation artifacts are absent.** Not found in the source code: a
  documented train/test split, model evaluation report, accuracy/precision/
  recall/F1, comparison baseline, or measured end-to-end performance results.

The code addresses some operational workflow needs with a single application,
but no evidence supports claims of superiority over external or pre-existing
systems.

## 8. Proposed System

TARIKA is a role-based web application whose core data services and analytics
are exposed through Django REST APIs.

### Major components

1. **React/Vite frontend:** `frontend/src/App.jsx` routes public, customer,
   admin, warehouse, and delivery pages. `AuthContext.jsx` stores session
   information in browser local storage and obtains data through
   `frontend/src/services/api.js`.
2. **Django REST backend:** `backend/config/urls.py` mounts app routes under
   `/api/`. API views validate requests, apply role permissions, and delegate
   business rules to service modules.
3. **PostgreSQL database:** `backend/config/settings.py` parses a
   `DATABASE_URL`, requires a PostgreSQL URL, and enforces SSL. The setup README
   describes Neon as the configured PostgreSQL host. Application code also
   assumes Supabase-originated public tables and authentication behavior.
4. **Commerce services:** catalog, cart/wishlist, order creation/history,
   warehouse operations, and delivery status/return workflows.
5. **Analytics and decision support:** RFM scoring and segments, distinct
   K-Means++ customer clusters, cohort-based CLV, Apriori association rules,
   a demand-analysis tree and sales terciles, and stock/replenishment logic.
6. **Persistence and cache:** many legacy/business tables are `managed=False`;
   RFM and campaign models define app-owned tables and migrations. Django cache
   uses Redis when `REDIS_URL` is provided, otherwise process-local
   `LocMemCache`.

### Module interaction

- Customer UI calls catalog endpoints; cart and checkout requests are
  authenticated and scoped to the user's customer profile.
- Checkout recalculates product prices and validates stock server-side, then
  writes order rows and clears the cart transactionally. Campaign coupons are
  validated against server-derived cart lines.
- Admin functions manage product/staff data and analytics. RFM-derived
  segment labels feed campaign audience and personalized-offer logic.
- Warehouse views combine product and stock data with demand tiers and
  replenishment orders. Delivery views constrain records and state changes to
  assigned delivery employees.
- CLV reads persisted RFM output and order history. Recommendation generation
  reads delivered orders and writes association rules to
  `product_recommendations`.

The exact deployment topology, network boundaries, database host instance,
and production secrets are Not found in the source code and are intentionally
not reproduced here.

## 9. Methodology

### 9.1 Commerce and fulfillment workflow

1. A customer registers or logs in through `/api/auth/`.
2. The frontend retrieves categories/products and submits cart or wishlist
   changes.
3. Cart and checkout logic resolve the customer from the authenticated
   identity; user-supplied customer IDs are not the authority.
4. Checkout reloads prices from database-backed product records, rechecks
   stock, validates an optional coupon, and writes orders within a transaction.
5. Warehouse staff can review product and order operations; delivery staff
   update assigned delivery states using allowed transitions.
6. Order and delivery history supports the analytical modules described below.

This sequence is represented across frontend pages and services; it was not
executed end-to-end during this repository analysis.

### 9.2 RFM analysis

The pipeline in `rfm_analysis/engine.py` calls `queries.fetch_buyer_metrics`,
normalizes records with `rfm_calculator.build_metrics`, scores with
`rfm_scoring.score_metrics`, and assigns rule-based labels with
`segmentation.apply_segments`.

- **Eligibility:** by default, delivered orders with non-null customer/date
  and non-negative `final_price` are used. The policy is configurable through
  environment variables in `rfm_analysis/utils.py`.
- **Recency (R):** days from latest eligible purchase to analysis date.
- **Frequency (F):** count of eligible order rows; source comments state one
  row is one order.
- **Monetary (M):** sum of eligible `final_price`.
- **Analysis date:** the greater of database current date and the latest
  eligible purchase date, preventing negative recency for future-dated rows.
- **Percentile score:** average ranks preserve ties. For N buyers and
  ascending average rank `rank(x)`:

  ```text
  R_pct = 100 * (N - rank(R)) / (N - 1)   # lower recency is better
  F_pct = 100 * (rank(F) - 1) / (N - 1)
  M_pct = 100 * (rank(M) - 1) / (N - 1)
  ```

  The percentiles are mapped to five bands with cut points 20, 40, 60, 80,
  and 100. The single-buyer case is handled separately.
- **Rule-based segments:** six primary labels are assigned in ordered rules:
  Champions, Loyal Customers, Potential Loyalists, New Customers, At-Risk,
  and Hibernating. Big Spender is an independent secondary tag at monetary
  percentile 90 or above. Never Purchased customers are handled separately.
- **Persistence:** analysis is performed as a snapshot/background run and
  customer-level results are persisted for downstream use. The API also
  guards overlapping background runs and records run status.

### 9.3 K-Means++ RFM clustering

`rfm_analysis/clustering.py` consumes stored RFM metrics, standardizes
recency/frequency/monetary values using `StandardScaler`, and calls
`KMeans(n_clusters=4, init='k-means++', n_init=10, random_state=42)`.
Profiles are interpreted in original units. A one-to-one mapping between
numeric clusters and four descriptive categories is selected using the
Hungarian assignment implementation (`scipy.optimize.linear_sum_assignment`).
Mapping support/cautions are exposed rather than silently forcing unsupported
labels. The result is stored separately from the rule-based segment, which
remains used by CLV and campaign logic.

### 9.4 CLV and cohort retention

`clv/calc.py` implements deterministic formulas, not an ML estimator:

```text
Historical CLV = eligible lifetime order revenue
AOV            = Historical CLV / eligible order count
Annual rate    = eligible order count / max(tenure in years, 30 days in years)
```

High/Medium/Low historical value tiers use P70/P30 population thresholds.
Monthly cohorts are formed from first purchase month; observed lifetime is
the month span between first and last eligible purchases. A pooled monthly
survival curve `S(k)` is calculated only for mature observation ages.
The expected-lifespan approximation is `1 + sum(S(k))` across mature ages.
Remaining lifespan conditions this curve on observed age; projected CLV is
`AOV * annual purchase rate * remaining lifespan in years`. Future CLV is
unavailable when the cohort history is insufficient or the buyer is older
than the observed horizon. See `clv/utils.py` for thresholds and
`clv/calc.py` for formulas.

### 9.5 Demand classification and replenishment

`demand_prediction/engine.py` implements a weighted manual ID3 classifier.
The target classes are Low, Medium, and High, defined by the 33.3rd and
66.7th percentiles of `units_sold`; the tree's input features are
`wishlist_count` and `cart_count`. It calculates Shannon entropy,
information gain, continuous split thresholds, recursively builds a tree
(maximum depth 3), and can explain a decision path.

**Critical distinction in the serving code:** `_build_model` states that the
engagement-feature tree has negligible predictive signal on the current data.
It assigns the actual units-sold target distribution to `predicted_distribution`,
and `demand_tier_sql` returns sales-derived terciles. Therefore the currently
served per-product tier is a descriptive bucket of observed sales, not a
holdout-validated ID3 prediction.

The stock workflow in `stock_to_be_ordered/services/forecasting.py` computes:

```text
observed_demand = round(units_sold)
need_to_order   = max(0, observed_demand - available_quantity)
```

No forecast horizon, supplier lead time, safety stock, or service-level
constraint appears in that formula. Priority is then based on demand tier,
stock, and the calculated gap. Replenishment-order creation and receipt are
handled in `services/replenishment.py`.

### 9.6 Product association and performance map

- **Apriori:** `recommendations/services.py` groups delivered rows by a
  synthetic `(customer_id, purchase_date)` key, uses `TransactionEncoder`,
  mines itemsets using `mlxtend.frequent_patterns.apriori`, derives rules
  using confidence, then retains one-product-to-one-product directions.
  Support, confidence, and lift are stored in the unmanaged
  `product_recommendations` table. Implementation defaults are minimum
  support `0.001` and confidence `0.0`; the module README says `0.002` for
  support, so the README and code are inconsistent.
- **Performance map:** `admin/performance_map.py` aggregates delivered
  quantity and revenue by active-product subcategory. Median sales and median
  revenue split the groups into four quadrants, with nonzero guards to prevent
  zero-sales categories being counted as high. It is exposed by the admin
  product-performance API. `ProductPerformanceMap.jsx` renders the API payload
  as an interactive SVG bubble chart with log-scaled axes, bubble area based
  on product count, median dividers, tooltips, and quadrant summaries.
  `AdminAnalyticsView.jsx` also integrates demand and slow-inventory views,
  plus RFM/CLV dashboards.

## 10. System Architecture

### Component responsibilities

| Layer | Components | Responsibilities |
|---|---|---|
| Presentation | React 19, React Router, Vite | Public homepage; customer, admin, warehouse, and delivery routes; interactive product performance map; API calls and portal state |
| API | Django and Django REST Framework | Authentication, role permissions, serializers, business services, analytics endpoints |
| Business services | `accounts`, `catalog`, `cart`, `orders`, `warehouse`, `delivery`, `rfm_analysis`, `clv`, `recommendations`, `demand_prediction`, `stock_to_be_ordered`, `admin` | Commerce operations, analytics, campaigns, and replenishment |
| Data | PostgreSQL via `DATABASE_URL` | Existing retail tables plus app-owned RFM/campaign/replenishment structures |
| Cache | Django cache; optional Redis | Catalog, RFM/CLV snapshots, run state, and feature caches |
| External identity dependency | Supabase-specific auth/database behavior in active auth service | JWT validation and profile/password queries; Neon-only hosting does not supply Supabase Auth |

### Data flow

```text
Browser (React portals)
        | JSON/HTTP, Bearer token
        v
Django REST API (views -> serializers/permissions -> services)
        | ORM + parameterized PostgreSQL SQL
        v
PostgreSQL application and imported retail tables
        |                         |
        | cache/version keys      +--> orders/products/customer histories
        v                                  |
Configured Django cache                    +--> RFM / CLV / Apriori / demand
                                           +--> warehouse and delivery actions
```

### Suggested architecture diagram

Draw five horizontal tiers. Put Customer/Admin/Warehouse/Delivery React portals
at the top; Django URL router and DRF views in the second tier; the domain
services in separate commerce, operations, and analytics groups in the third;
PostgreSQL tables plus Redis/LocMemCache in the fourth; and Supabase-origin
authentication dependency as a clearly marked external boundary. Add arrows
for API requests, ORM/SQL reads and writes, cache reads/invalidations, and
analytics flows from orders/products to customer/product outputs. Label
K-Means clustering and rule-based RFM segmentation as distinct paths.

## 11. Technologies and Tools Used

| Technology/tool | Version identifiable from repository | Purpose | Where used |
|---|---|---|---|
| Python | Exact supported/runtime version: Not found in the source code | Backend language | `backend/**/*.py` |
| Django | Settings header says generated with Django 5.2.17; no backend pin found | Backend framework, ORM, cache, management commands | `backend/config/`, all backend apps |
| Django REST Framework | Version: Not found in the source code | REST API views, serializers, permissions | Backend API apps |
| PostgreSQL | Backend setup specifies PostgreSQL; server version not found | Relational persistence and SQL aggregates | `backend/config/settings.py`, app SQL |
| Neon | Host/setup target named in backend setup documentation; project ID/plan not found | PostgreSQL hosting target described by the setup guide | `DATABASE_URL` configuration |
| Supabase Auth/schema | Exact version/service configuration: Not found in the source code | Existing auth token/schema assumptions and public-table access | `accounts/services/supabase_auth.py`, `accounts/authentication.py` |
| React | `^19.2.8` declared | Frontend component framework | `frontend/src/` |
| React Router DOM | `^7.18.3` declared | Browser routing and nested role portals | `frontend/src/App.jsx`, portal components |
| Vite | `^8.2.2` declared | Frontend dev server and production bundler | `frontend/vite.config.js`, `frontend/package.json` |
| `@vitejs/plugin-react` | `^6.1.0` declared | Vite React integration | `frontend/vite.config.js` |
| Lucide React | `^1.41.0` declared | UI icons | Frontend components |
| Oxlint | `^1.79.0` declared | Frontend lint script | `frontend/package.json` |
| NumPy | Version: Not found in the source code | RFM and clustering numeric arrays | `rfm_analysis/rfm_scoring.py`, `rfm_analysis/clustering.py` |
| pandas | Version: Not found in the source code | Percentile ranking, transaction/CLV calculations | `rfm_analysis/rfm_scoring.py`, `clv/calc.py`, `recommendations/services.py` |
| scikit-learn | Version: Not found in the source code | StandardScaler and K-Means++ | `rfm_analysis/clustering.py` |
| SciPy | Version: Not found in the source code | Hungarian cluster/category assignment | `rfm_analysis/clustering.py` |
| mlxtend | Version: Not found in the source code | Transaction encoding, Apriori, association rules | `recommendations/services.py` |
| PyJWT (`jwt`) | Version: Not found in the source code | JWT encoding/verification | `accounts/services/supabase_auth.py`, `accounts/services/neon_auth.py` |
| `python-dotenv` | Version: Not found in the source code | Load backend `.env` configuration | `backend/config/settings.py` |
| Redis / django-redis | Optional; versions: Not found in the source code | Shared cache if `REDIS_URL` is configured | `backend/config/settings.py` |

The frontend package manifest and lockfile are present. A Python requirements,
`pyproject.toml`, Pipfile, or equivalent backend dependency manifest was Not
found in the source code. Dependency versions for Python libraries must not be
assumed from imports.

## 12. Implementation Details

| Area | Important files and symbols | Responsibility |
|---|---|---|
| Frontend entry/routing | `frontend/src/main.jsx`, `frontend/src/App.jsx` | Mounts React app, lazy-loads portals, and enforces frontend role routing |
| Frontend identity/API | `frontend/src/auth/AuthContext.jsx`, `frontend/src/services/api.js` | Login/register, token/profile handling, and HTTP helpers |
| Customer commerce | `frontend/src/pages/customer/`, `frontend/src/context/CustomerContext.jsx` | Catalog, cart, checkout, order history, profile, wishlist, and offers |
| Staff portals | `frontend/src/pages/admin/`, `frontend/src/pages/warehouse/`, `frontend/src/pages/delivery/` | Staff UI; admin analytics and performance map are integrated; some sidebar pages remain placeholders |
| Backend configuration | `backend/config/settings.py`, `backend/config/urls.py` | Installed apps, PostgreSQL, cache, REST auth defaults, CORS, and API route mounting |
| Authentication | `accounts/authentication.py`, `accounts/permissions.py`, `accounts/services/supabase_auth.py` | Bearer-token authentication, database-resolved roles, and role permissions |
| Catalog | `catalog/models.py`, `catalog/views.py`, `catalog/services.py`, `catalog/pricing.py` | Legacy/current product mapping, filtering, pricing, catalog APIs |
| Cart and wishlist | `cart/services.py`, `cart/views.py`, `cart/models.py` | Customer isolation, stock validation, cart totals, and wishlist |
| Checkout/orders | `orders/services.py`, `orders/views.py`, `orders/models.py` | Server-side pricing, cart-to-order transaction, order reads, and return records |
| Warehouse/delivery | `warehouse/services.py`, `warehouse/views.py`, `delivery/services.py`, `delivery/views.py` | Warehouse inventory/order/return operations and assigned delivery lifecycle |
| Demand | `demand_prediction/engine.py`, `demand_prediction/views.py` | Manual weighted ID3 calculations, tier analytics, product lists, sales history |
| Replenishment | `stock_to_be_ordered/services/forecasting.py`, `services/replenishment.py`, `views.py` | Sales/stock gap, priority, purchase order lifecycle |
| RFM | `rfm_analysis/queries.py`, `rfm_calculator.py`, `rfm_scoring.py`, `segmentation.py`, `engine.py` | Eligible order aggregation, dynamic scoring, segment rules, and snapshot lifecycle |
| K-Means | `rfm_analysis/clustering.py` | Standardized RFM clustering, profile assignment, and label persistence |
| Campaigns | `rfm_analysis/models.py`, `campaign_audience.py`, `campaign_engine.py`, `coupon_validation.py`, `personalization.py` | Admin-authored offers, targeted audiences, coupon validation and personalized offers |
| CLV | `clv/calc.py`, `clv/queries.py`, `clv/service.py`, `clv/views.py` | Historical/future value calculations, cohort survival, cache, and API |
| Recommendations | `recommendations/services.py`, `recommendations/management/commands/update_recommendations.py` | Apriori mining, replacement persistence, and product-level retrieval |
| Product performance | `admin/performance_map.py`, `admin/views.py`, `frontend/src/pages/admin/ProductPerformanceMap.jsx`, `frontend/src/pages/admin/AdminDashboardView.jsx` | Delivered-sales subcategory aggregates, median quadrants, and interactive SVG presentation |
| Schema changes | `backend/rfm_analysis/migrations/`, `backend/orders/sql/` | Analytics/campaign migration history; price-correction SQL and generated CSV artifacts |

`backend/revenue_forecasting/` contains no Python implementation in the
repository scan (only bytecode cache entries), and it is not included in
`INSTALLED_APPS`. A revenue-forecasting algorithm or API is therefore Not
found in the source code.

## 13. Dataset and Data Processing

### Sources visible in the repository

- The application reads retail data from PostgreSQL tables such as
  `public.products`, `public.orders`, `public.customers`, and
  `fact_product_analysis`.
- `fact_product_analysis` is used by demand code with fields including
  `product_key`, `units_sold`, `total_sales`, `wishlist_count`, and
  `cart_count`.
- RFM and CLV read purchase date, delivery status, final price, customer, and
  product fields from orders.
- CSV files present under `backend/orders/sql/` are described by their names
  as price-correction previews or recovery exports. They are not documented
  as model-training datasets. Their row-level contents were not used as
  research evidence.

### Dataset facts and unknowns

| Item | Finding |
|---|---|
| Dataset origin | The code/docs describe a connected retail PostgreSQL dataset; its original public source, license, collection process, and citation are Not found in the source code. |
| Dataset files | No documented raw training dataset, notebook dataset, or test fixture data file was found in the final repository scan. The SQL-folder CSV artifacts are operational previews/exports, not documented benchmarks. |
| Dataset size | Current exact live row counts: Not found in the source code during this inspection. Source comments mention roughly 90k product records and roughly 100k buyers / large order tables, but those are not fresh measurements. An older catalog README lists 420 products, 909 inventory rows, and other counts; these conflict with current-schema comments and should be treated as stale or unresolved. |
| Input features: RFM | Delivered status, customer ID, purchase date, and final price; aggregates are recency, order count, and revenue. |
| Input features: demand | `wishlist_count` and `cart_count` for the diagnostic tree; `units_sold` defines the output terciles. `available_quantity` is stock evidence, not a tree feature. |
| Input features: K-Means | Stored recency, frequency, and monetary values; standardized before clustering. |
| Input features: recommendations | Product names grouped by synthetic customer-date basket, restricted to delivered purchases. |
| Cleaning | Code handles nulls, invalid/negative price policy for RFM, date parsing, text normalization, duplicate products within baskets, and missing numeric demand values. |
| Train/test split | Not found in the source code. |
| Data augmentation | Not found in the source code. |
| Dataset license / consent | Not found in the source code. |

Do not publish the older catalog README counts as the current dataset profile
without verifying them against a named database snapshot and date.

## 14. Experimental Results and Performance Evaluation

### Verified results

- **Model-quality metrics:** Not found in the source code. No accuracy,
  precision, recall, F1-score, ROC-AUC, or test-set metrics are recorded.
- **Demand model outcome:** Source comments explicitly state that the
  wishlist/cart ID3 tree is non-predictive on the current data and that the
  endpoint uses sales-derived terciles instead. This is a code-level
  implementation note, not an independently measured performance report.
- **Recommendation output:** `backend/recommendations/README.md` contains an
  example output with 5,756 transactions, 187 products, 159 frequent itemsets,
  and 8 rules. It is an illustrative README example, not verifiable current
  run output; it also documents a support default that differs from code.
- **Runtime/latency:** Source comments mention historical query timings and
  optimizations, but this inspection did not execute a connected live
  database. No reproducible benchmark environment/results were found.
- **Automated tests:** Test modules exist across the backend, including
  algorithm, API, serializer, and service tests. The attempted backend test
  command could not start because Django is not installed in the selected
  Python environment (`ModuleNotFoundError: No module named 'django'`).
  Therefore no backend tests passed or failed in this analysis.
- **Test environment in source:** `backend/test_settings.py` configures
  in-memory SQLite, intended for non-live tests. It does not validate the
  connected production schema or full database behavior.
- **Frontend evaluation:** No frontend test script or browser-based evaluation
  setup was identified in `frontend/package.json`.

### Evaluation limitations

No experiment establishes out-of-sample predictive performance, baseline
improvement, recommendation utility, customer retention effects, or inventory
cost/service-level effects. The target construction for demand tiers uses
observed sales and therefore must not be reported as a future forecast without
time-based evaluation. The system needs a dated dataset snapshot, leakage-safe
temporal split, explicit forecast horizon, baselines, repeated runs, and
uncertainty analysis before research claims can be made.

## 15. Advantages and Applications

### Implemented capabilities

- Customer, admin, warehouse, and delivery interfaces are routed separately.
- Backend customer requests are scoped to authenticated profiles; role
  permissions are centralized in `accounts/permissions.py`.
- Catalog filtering, pagination, product prices, stock checks, and checkout
  logic are server-side.
- RFM scores use population-relative percentiles and preserve ties; segment
  labels and a Big Spender overlay are computed from explicit rules.
- K-Means++ results are stored separately from the business-rule segments.
- CLV future estimates are omitted when cohort observations do not support
  them instead of inventing an estimate.
- Association rules carry support, confidence, and lift values.
- Stock workflow calculates a visible reorder gap and tracks pending purchase
  orders.
- Database aggregation, pagination, and caching are present in selected
  high-volume paths.

These are capabilities visible in source, not a claim of security certification,
scalability testing, or business benefit.

### Potential applications

The implemented modules could support apparel e-commerce, targeted campaign
planning, customer-value monitoring, product cross-sell discovery, and
warehouse stock review. Impact on conversion, retention, revenue, or stockout
rates is a future evaluation question, not a verified outcome.

## 16. Limitations

1. **Predictive validity:** no train/test split, temporal backtest, error
   metric, calibration check, or independent validation is present. Demand
   tiers currently describe historical sales quantiles.
2. **Replenishment semantics:** use of accumulated `units_sold` as a
   replenishment demand quantity lacks a defined forecast period, lead time,
   safety stock, and supplier constraints.
3. **Association basket definition:** customer-date grouping may combine
   separate same-day orders or otherwise fail to represent a true transaction.
   The one-product-per-order schema makes that decision particularly important.
4. **Replenishment stock timing:** individual and bulk order paths apply stock
   at different lifecycle points, while the model description is broader than
   the service behavior.
5. **Schema alignment:** differing legacy/current model assumptions for
   `orders`, inventory, customers, and catalog tables may make some paths
   incompatible with a single deployed schema. The backend README itself
   warns that schema migration requires review.
6. **Identity provider boundary:** configured database hosting and active
   authentication assumptions are not equivalent; Supabase Auth functionality
   must be retained or migrated deliberately.
7. **Data provenance and governance:** no dataset license, source citation,
   privacy/consent policy, or documented anonymization procedure was found.
8. **Reproducibility:** backend dependency versions and database snapshot
   definitions are missing. Analytics depend on live database contents and
   environment configuration.
9. **Operational verification:** tests could not run in the available
   environment; live DB/API behavior was not verified. Some admin portal
   sections still use the generic placeholder component.
10. **Deployment configuration:** the checked-in settings include development-
   oriented debug, host, and CORS configuration; production hardening is not
   demonstrated.
11. **External validity:** no evidence shows that segment labels or data-driven
   thresholds generalize beyond this database population or time window.

## 17. Future Scope

1. **Establish reproducible evaluation data.** Create a versioned, permissioned
   snapshot with a data dictionary, source/license statement, time boundaries,
   exclusions, and row-count reconciliation.
2. **Evaluate demand forecasting properly.** Define a forecast horizon and
   target such as next-period sales. Use time-ordered train/validation/test
   partitions, compare against seasonal-naive and moving-average baselines,
   and report MAE/RMSE or suitable count/ranking metrics with confidence
   intervals. Avoid leakage from post-outcome features.
3. **Redesign replenishment inputs.** Include supplier lead time, forecast
   demand over lead time, safety stock, pack sizes, costs, and service level;
   simulate stockouts and holding costs before operational release.
4. **Validate recommendation baskets.** Use a stable transaction/order-line
   identity, specify support/confidence/lift thresholds, evaluate temporal
   stability and ranking quality, and run a controlled online experiment
   before claiming conversion lift.
5. **Assess segmentation.** Report cluster size balance, silhouette or other
   internal diagnostics, stability under resampling/time shifts, and
   business-interpretability review. Keep rule-based and K-Means labels
   conceptually separate.
6. **Audit cohort CLV assumptions.** Test censoring assumptions, cohort
   completeness, temporal drift, and projection error against later observed
   outcomes; report intervals instead of point estimates alone.
7. **Resolve schema/auth architecture.** Document a canonical table schema and
   migrations, reconcile conflicting order/product/inventory mappings, and
   explicitly select Supabase Auth, Django Auth, or another supported
   identity provider.
8. **Strengthen UI and operational verification.** Add API/integration tests
   for the current admin analytics and performance-map interfaces, browser
   tests, and deployment smoke tests; complete any remaining placeholder
   portal sections.
9. **Improve reproducibility and governance.** Add a pinned backend dependency
   manifest, environment template without secrets, data dictionary,
   retention/access rules, and research references.

## 18. Conclusion

TARIKA is a broad retail application that combines a fashion storefront and
staff workflows with customer and product analytics. The repository
implements commerce and fulfillment services, percentile-based RFM scoring
and rule segments, a separate K-Means++ analysis, cohort-derived CLV
calculations, Apriori product association mining, and demand/stock dashboards.
The code is sufficiently explicit to describe its formulas and data paths, but
the implementation must not be overstated: the current demand labels are
sales-derived historical terciles, and replenishment compares those observed
sales values with current stock. No measured model metrics, live evaluation,
or business-impact outcomes were verified. In addition, dataset provenance,
dependency pinning, and alignment among current and legacy database schemas
remain unresolved. The project is a useful implemented decision-support
platform and a candidate for further study; predictive and operational claims
require reproducible, leakage-safe experiments.

## 19. References

### Repository evidence

The primary technical evidence is the implementation itself:

1. TARIKA repository, root `README.md` and `backend/README.md`.
2. Django settings and API routes: `backend/config/settings.py`,
   `backend/config/urls.py`.
3. RFM, CLV, demand, recommendation, and replenishment source files referenced
   throughout Sections 9 and 12.
4. Frontend dependency declarations: `frontend/package.json` and
   `frontend/package-lock.json`.
5. Module-specific documentation: `backend/catalog/README.md`,
   `backend/cart/README.md`, and `backend/recommendations/README.md`.

No peer-reviewed paper, external dataset citation, or project bibliography was
found in the repository. The README example statistics are not included here
as empirical results.

### Official technical documentation for the libraries present

The following links identify primary documentation for technologies imported
or declared by the project. They document the tools; they are not evidence of
the project's empirical performance.

1. Django Software Foundation, *Django documentation*, version 5.2.
   [https://docs.djangoproject.com/en/5.2/](https://docs.djangoproject.com/en/5.2/)
2. Encode OSS Ltd., *Django REST Framework documentation*.
   [https://www.django-rest-framework.org/](https://www.django-rest-framework.org/)
3. React, *React documentation*.
   [https://react.dev/](https://react.dev/)
4. Vite, *Vite documentation*.
   [https://vite.dev/](https://vite.dev/)
5. scikit-learn developers, *K-means clustering* and *StandardScaler*.
   [https://scikit-learn.org/stable/modules/clustering.html#k-means](https://scikit-learn.org/stable/modules/clustering.html#k-means);
   [https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html)
6. SciPy developers, *scipy.optimize.linear_sum_assignment*.
   [https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html)
7. mlxtend developers, *Apriori* and *Association rules*.
   [https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/apriori/](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/apriori/);
   [https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/)

For an IEEE paper submission, add primary academic citations for RFM
segmentation, K-Means++, Apriori/association rules, and cohort/survival methods
after selecting and verifying the precise works used. No such papers are cited
in the repository, so none are fabricated here.

## 20. Verified Technical Facts, Missing Information, and Validation Needs

### Verified technical facts

- React/Vite frontend and Django REST backend are present.
- Frontend routes implement public, customer, admin, warehouse, and delivery
  portals.
- Backend routes expose catalog, auth, cart/wishlist, orders, admin,
  warehouse, delivery, demand, replenishment, recommendation, RFM, and CLV
  module paths.
- PostgreSQL is required by runtime settings; Redis is optional.
- Active DRF authentication imports `SupabaseAuthentication`, which validates
  tokens through `SupabaseAuthService`.
- RFM uses delivered orders, nonnegative final prices by default, dynamic
  average-rank percentiles, five score bands, six rule-based segments, and a
  separate Big Spender tag.
- K-Means++ is a separate four-cluster analysis over standardized RFM values;
  cluster categories are mapped after clustering.
- CLV includes historical revenue/value tiers and monthly cohort retention;
  future estimates can be unavailable.
- The demand tree features are `wishlist_count` and `cart_count`, but served
  demand tiers are computed from `units_sold` terciles.
- Replenishment gap is `max(0, round(units_sold) - available_quantity)`.
- Apriori mines one-to-one directional rules from delivered products grouped
  by customer/date.
- Product performance groups delivered sales and revenue by active-product
  subcategory using median-based quadrants; current admin code requests this
  endpoint and renders the response in an interactive SVG component.
- Backend test files exist; the attempted test run did not start because Django
  is absent from the selected environment.

### Missing information

- Fresh database row counts and a dataset snapshot date.
- Original dataset source, citation, license, and collection methodology.
- Pinned Python/backend dependency versions.
- Production hosting topology and deployment configuration.
- A canonical, reconciled database schema for all modules.
- A documented existing-system baseline or literature review.
- Any train/validation/test split, benchmark, or ML evaluation metrics.
- Verified live API results, latency measurements, and user/business outcomes.
- Frontend automated test setup.
- Authors and institutional affiliations for the IEEE poster/paper.

### Claims that require experimental validation

- That the demand classifier predicts future product demand with useful
  accuracy.
- That the current stock rule reduces stockouts, holding costs, or over-ordering.
- That Apriori suggestions improve product discovery, basket size, or
  conversion.
- That K-Means clusters are stable, meaningful, or superior to rule-based RFM
  segments.
- That CLV projections accurately predict later realized customer value.
- That caching or SQL aggregation meets a defined performance/service target.
- That the application scales to the approximate data sizes mentioned in
  source comments.
- That the overall platform improves retention, revenue, operational
  efficiency, or customer experience.

## Suggested IEEE poster structure

Use the concise three-column poster in `IEEE_POSTER_CONTENT.md`. The most
important visual distinction is between **observed-data descriptions** and
**validated predictions**. Highlight the RFM-to-campaign and
orders-to-replenishment data flows, and mark evaluation results as unavailable
until tested. Suggested figures are a system architecture diagram, end-to-end
workflow, RFM/K-Means distinction, cohort survival schematic, and a sample
median-quadrant map generated from a verified data snapshot. Do not plot
fabricated values or the README's illustrative recommendation counts as
experimental findings.
