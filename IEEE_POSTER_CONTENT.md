# IEEE Poster Content

## 1. Title

**TARIKA: A Role-Based Fashion Retail Platform with RFM Customer Analytics and
Demand-Informed Inventory Operations**

## 2. Authors and Affiliations

**Authors:** [Author 1], [Author 2], [Author 3]  
**Affiliation:** [Department, Institution, City, Country]  
**Corresponding author:** [Name and email]

## 3. Abstract

TARIKA is a web-based fashion retail application integrating customer
shopping, staff operations, and data-driven decision support. A React/Vite
frontend communicates with a Django REST API and PostgreSQL data store.
Implemented workflows include product browsing, cart and wishlist
management, checkout, order history, warehouse operations, and delivery
updates. Analytical modules calculate delivered-order Recency, Frequency, and
Monetary (RFM) metrics; assign percentile-based business segments; separately
cluster standardized RFM vectors using K-Means++; estimate customer value
using monthly cohort survival; and mine product associations with Apriori.
Demand tiers are currently assigned from terciles of observed units sold.
Although a manual ID3 tree is computed from wishlist and cart counts, the
source explicitly does not use it to classify products because the features
lack useful predictive signal in the present data. Replenishment compares
observed sales with current stock. Repository evidence does not include
holdout metrics, reproducible live-data results, or measured business impact.
TARIKA is therefore presented as an implemented retail decision-support
platform; predictive accuracy and operational effectiveness remain to be
validated.

## 4. Introduction

Retail operations span storefront transactions, inventory, fulfillment, and
customer retention. TARIKA places customer and staff workflows in one
application and surfaces historical customer and product analytics to support
retail decisions. Its research contribution is the integration of these
workflows and transparent analytics mechanisms; effectiveness has not yet
been established experimentally.

## 5. Problem Statement

Implement a role-based fashion retail system that connects online commerce and
fulfillment with interpretable summaries of customer purchasing behavior,
product associations, and stock requirements.

**Baseline limitation:** No prior system or comparative baseline is documented
in the repository. Claims about shortcomings of existing products are
therefore outside the evidence available.

## 6. Objectives

- Deliver customer catalog, cart, wishlist, checkout, and order workflows.
- Separate admin, warehouse, and delivery-partner operations by role.
- Summarize customer purchase behavior using RFM metrics and segments.
- Provide additional K-Means++ clusters, cohort-based CLV, and product
  association rules.
- Display historical demand tiers and stock gaps for operational review.
- Clearly distinguish descriptive outputs from validated future predictions.

## 7. Proposed Methodology

1. **Commerce data capture:** Customer-facing requests use Django APIs;
   checkout recalculates prices and validates stock server-side.
2. **RFM pipeline:** Filter eligible delivered orders; aggregate days since
   last purchase, distinct order count, and paid revenue; calculate tied
   average-rank percentiles; map percentiles to score bands and ordered
   business segments.
3. **Customer clusters:** Standardize stored RFM values, apply four-cluster
   K-Means++ (`n_init=10`, fixed random seed), profile clusters in original
   units, then map profiles to descriptive categories.
4. **Customer value:** Compute historical revenue and value tiers; derive
   monthly cohort survival; calculate future CLV only when the observed
   retention history is sufficient.
5. **Product associations:** Encode delivered customer/date product baskets,
   mine frequent itemsets with Apriori, and retain directional one-product
   rules with support, confidence, and lift.
6. **Stock review:** Assign Low/Medium/High historical sales terciles and
   calculate `max(0, round(units_sold) - available_quantity)`.

**Methodological caveat:** The source does not show a train/test split or
forecast horizon. Demand classes are historical sales buckets, not verified
forecasts.

## 8. System Architecture

```text
React/Vite portals
  Customer | Admin | Warehouse | Delivery
                 |
                 | JSON API + Bearer token
                 v
        Django REST API
  Authentication / Permissions / Views
     Commerce | Operations | Analytics
                 |
          ORM and SQL queries
                 v
        PostgreSQL tables
                 |
       Django cache (optional Redis)
```

The backend reads existing PostgreSQL retail tables and persists selected
analytics/campaign records. Active authentication depends on
Supabase-oriented code; the Neon setup documentation does not by itself
provide Supabase Auth.

**Suggested figure:** Draw the four role portals above Django APIs, group
backend services into Commerce, Fulfillment, and Analytics, then show
PostgreSQL and cache below. Mark the Supabase identity boundary explicitly.
Use arrows from orders to RFM/CLV/Apriori and from product sales/stock to
replenishment.

## 9. Implementation

| Component | Implementation |
|---|---|
| Frontend | React role routes in `frontend/src/App.jsx`; API client in `frontend/src/services/api.js` |
| Backend | Django REST views, serializers, services, and permissions in `backend/` |
| RFM | `backend/rfm_analysis/rfm_calculator.py`, `rfm_scoring.py`, `segmentation.py`, `engine.py` |
| Clustering | `backend/rfm_analysis/clustering.py` using scikit-learn K-Means++ / StandardScaler and SciPy assignment |
| CLV | `backend/clv/calc.py` and `backend/clv/service.py` |
| Recommendations | `backend/recommendations/services.py` using mlxtend Apriori and association rules |
| Demand / stock | `backend/demand_prediction/engine.py` and `backend/stock_to_be_ordered/services/` |
| Persistence | PostgreSQL configured through `DATABASE_URL`; Redis is optional |

## 10. Results and Discussion

- Source code implements the workflows and analytic calculations summarized
  above.
- No empirical model-quality metrics, benchmark comparisons, or measured
  business outcomes were found.
- The demand endpoint serves sales-tercile labels; the tree is computed for
  analysis but not used as the current product label.
- No backend tests ran during this analysis because Django was unavailable in
  the selected Python environment.

**Poster reporting rule:** Do not insert accuracy, latency, transaction counts,
or recommendation counts unless they are measured from a dated, reproducible
experiment. Label any later results with dataset period, sample size, split,
metric definition, and test environment.

## 11. Conclusion

TARIKA integrates fashion commerce and staff workflows with RFM, K-Means++,
cohort CLV, association mining, and stock decision support. Its source makes
the analytical methods inspectable, but current demand tiers describe
historical sales rather than validated future demand. The platform is an
implemented prototype; predictive quality and operational value remain open
evaluation questions.

## 12. Future Scope

- Define and validate a time-based demand forecast with a specified horizon
  and baseline models.
- Incorporate supplier lead times, safety stock, and inventory cost/service
  measures into replenishment evaluation.
- Use verified order/basket identifiers and evaluate association
  recommendations out of time.
- Measure cluster stability and compare campaign/retention outcomes.
- Validate cohort-based CLV against later realized revenue.
- Reconcile schema and identity-provider assumptions; add dependency pins and
  integration tests.

## 13. References

**Implementation evidence:** TARIKA source modules listed in Section 9;
frontend dependencies in `frontend/package.json`; module documentation in
`backend/README.md` and selected app READMEs.

**Technical documentation:** Django 5.2
([docs.djangoproject.com/en/5.2](https://docs.djangoproject.com/en/5.2/));
Django REST Framework
([django-rest-framework.org](https://www.django-rest-framework.org/));
React ([react.dev](https://react.dev/)); Vite
([vite.dev](https://vite.dev/)); scikit-learn K-Means and StandardScaler
([K-Means](https://scikit-learn.org/stable/modules/clustering.html#k-means),
[StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html));
SciPy linear assignment
([linear_sum_assignment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html));
mlxtend Apriori
([Apriori](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/apriori/),
[association_rules](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/)).

No academic papers or external dataset citations are present in the
repository. Add verified primary research citations before submission.

## Poster Layout and Visual Guidance

### Recommended three-column layout

| Column 1: Context | Column 2: Methods | Column 3: Evidence and implications |
|---|---|---|
| Title/authors, abstract, introduction, problem statement, objectives | Proposed methodology, system architecture, key implementation details | Results and discussion, conclusion, future scope, references |

### Suggested visuals

1. **System architecture diagram:** role portals -> Django REST API -> domain
   services -> PostgreSQL/cache; show the Supabase authentication boundary.
2. **Workflow flowchart:** customer checkout and order creation, with a
   separate orders-to-RFM/CLV/recommendation path and
   sales-plus-stock-to-replenishment path.
3. **RFM figure:** compact equation/score-band graphic, with rule-based
   segments visually distinguished from K-Means++ categories.
4. **Cohort method schematic:** cohort month, observed ages, survival curve,
   and the point at which future CLV becomes unavailable. Use real values only
   after a verified run.
5. **Product map:** median-split units/revenue quadrants from a documented
   live snapshot. If no verified data run is available, show an explicitly
   labeled schematic, not fabricated observations.
6. **Evidence table:** implemented modules, verified artifacts, and
   evaluation status; list predictive metrics as unavailable rather than
   filling in hypothetical values.

### Visual emphasis

- Lead with the system integration and modular analytics contribution.
- Make the difference between *historical sales terciles* and *future demand
  prediction* visually unmistakable.
- Distinguish rule-based RFM segments from unsupervised K-Means++ clusters.
- Use a prominent “No model-performance metrics available in repository”
  callout until validation is completed.
- Avoid decorative charts containing unsupported counts or performance
  values.
