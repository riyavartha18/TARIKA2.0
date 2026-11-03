"""Persistent campaign configuration and order-level redemption audit.

Section 12 requires campaign definitions to persist somewhere durable: unlike
the RFM results (which stay in a short-lived snapshot cache), a campaign cannot
exist only in memory. The inspected Neon database had no campaign, coupon or
redemption table, so this is the smallest new schema that satisfies the feature
without duplicating anything that already exists:

* `rfm_campaigns` - the admin-authored campaigns and their targeting rules.
* `rfm_campaign_redemptions` - one row per order that used a coupon, giving
  order-level redemption auditing (usage limits, global limits, duplicate
  protection) without adding columns to the read-only `public.orders` table and
  without any permanent customer-coupon assignment table.
* `rfm_campaign_audience` - the coupon assignments of a K-Means campaign, i.e.
  the exact customers it was published to. Added when targeting moved from the
  rule-based segments to the four K-Means clusters: a segment campaign can be
  evaluated from the customer's current label, but a published cluster campaign
  must not move when clustering is re-run, so its members are recorded here.
* `rfm_kmeans_runs` - one append-only row per completed clustering run, so a
  campaign can name the run its audience came from.
* `rfm_customer_segments` + `rfm_analysis_state` - the segment label of the
  latest completed analysis per buyer, so a customer page reads one indexed row
  instead of rebuilding the cached snapshot (or recomputing the analysis).

Customer and order identity are stored as plain text keys (`customer_id`,
`order_id`) rather than foreign keys, because `public.orders`/`public.customers`
are unmanaged dataset tables; matching them by key avoids introducing FK
constraints Postgres could not validate against existing rows.
"""

from django.db import models


class UsageType(models.TextChoices):
    ONCE = 'ONCE', 'Once per customer'
    LIMITED = 'LIMITED', 'Limited uses per customer'
    UNLIMITED = 'UNLIMITED', 'Unlimited uses per customer'


class DiscountType(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage'
    FIXED = 'FIXED', 'Fixed amount'


class CampaignStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    PAUSED = 'PAUSED', 'Paused'
    EXPIRED = 'EXPIRED', 'Expired'


class OfferCategory(models.TextChoices):
    """Which of the two offer families a campaign carries.

    A campaign may hold a discount offer, a Buy & Get offer, or both at once
    (`COMBINED`). The category decides which of the JSON rule fields must be
    filled in; `benefits_combinable` then decides whether a COMBINED campaign
    stacks both benefits at checkout or only grants the better one.
    """
    DISCOUNT = 'DISCOUNT', 'Discount offer'
    BUY_GET = 'BUY_GET', 'Buy & Get offer'
    COMBINED = 'COMBINED', 'Combined offer'


class TargetingMode(models.TextChoices):
    """Which segmentation a campaign's audience was chosen from.

    Two vocabularies exist in this module's history and both must stay
    readable, so a campaign declares which one it uses instead of the code
    guessing from the stored labels:

    * `LEGACY_RFM` - the previous rule-based segments (`target_segments` /
      `target_tags`). The default, so every campaign row written before the
      K-Means switch keeps its original meaning and audience untouched.
    * `KMEANS` - one or more of the four K-Means++ clusters of a specific
      persisted clustering run (`target_cluster_ids` + `clustering_run`), with
      the buyers of those clusters materialized into `CampaignAudience` when
      the campaign is published.
    """
    LEGACY_RFM = 'LEGACY_RFM', 'Rule-based RFM segment (legacy)'
    KMEANS = 'KMEANS', 'K-Means cluster'


class Campaign(models.Model):
    campaign_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)
    coupon_code = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, default='')

    offer_category = models.CharField(max_length=20, choices=OfferCategory.choices,
                                      default=OfferCategory.DISCOUNT)

    # Structured offer rules (see benefits.py for the exact shape of each):
    # `discount_rule` holds the monetary offer, `buy_get_rule` the quantity/
    # product-based one, and `scope` the eligible product/category selection.
    # Empty dicts mean "no such benefit"; a COMBINED campaign fills both.
    discount_rule = models.JSONField(default=dict, blank=True)
    buy_get_rule = models.JSONField(default=dict, blank=True)
    scope = models.JSONField(default=dict, blank=True)
    # COMBINED only: can both benefits apply to the same checkout, or does
    # the customer get whichever benefit is better for them?
    benefits_combinable = models.BooleanField(default=False)

    # Legacy simple-discount fields, kept as the headline mirror of
    # `discount_rule` so older offers and API consumers keep working.
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices,
                                     default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2,
                                         default=0)
    max_discount = models.DecimalField(max_digits=12, decimal_places=2,
                                       null=True, blank=True)

    # Targeting: JSON lists of segment labels / secondary tags. Empty target
    # segment list means the campaign targets no one and is never shown.
    # These two are the LEGACY_RFM audience and are only ever read for a
    # campaign whose `targeting_mode` is LEGACY_RFM.
    target_segments = models.JSONField(default=list, blank=True)
    target_tags = models.JSONField(default=list, blank=True)

    # K-Means targeting (the current segmentation). `target_cluster_ids` are the
    # numeric clusters selected from `clustering_run`, and `target_cluster_labels`
    # is the business label each of those clusters carried *in that run* - stored
    # so a later re-cluster (which may map a different label onto the same id)
    # can never rename what an existing campaign was actually aimed at.
    targeting_mode = models.CharField(max_length=20, choices=TargetingMode.choices,
                                      default=TargetingMode.LEGACY_RFM)
    target_cluster_ids = models.JSONField(default=list, blank=True)
    target_cluster_labels = models.JSONField(default=list, blank=True)
    clustering_run = models.ForeignKey('ClusteringRun', null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='campaigns')

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                           default=0)
    usage_type = models.CharField(max_length=20, choices=UsageType.choices,
                                  default=UsageType.UNLIMITED)
    per_customer_limit = models.PositiveIntegerField(default=0)  # used with LIMITED
    global_usage_limit = models.PositiveIntegerField(default=0)  # 0 = unlimited
    stacking_allowed = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=CampaignStatus.choices,
                              default=CampaignStatus.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rfm_campaigns'
        ordering = ['-campaign_id']
        # Every customer offer read asks for "PUBLISHED rows whose validity
        # window covers now". Without this index PostgreSQL would scan the whole
        # table on each request; with it the live set is an index range scan.
        indexes = [
            models.Index(fields=['status', 'start_date', 'end_date'],
                         name='campaign_live_window'),
        ]

    @property
    def targets_clusters(self):
        """Is this campaign aimed at K-Means clusters rather than old segments?"""
        return self.targeting_mode == TargetingMode.KMEANS

    def __str__(self):
        return f"{self.name} ({self.coupon_code})"


class ClusteringRun(models.Model):
    """Append-only history of every successfully completed K-Means++ run.

    `KmeansRunState` is a singleton describing only the *latest* run, so a
    campaign that references it would silently change meaning as soon as
    clustering is re-run. This table keeps one row per completed run - the same
    mapping the run persisted, plus which RFM version it clustered and when -
    so a campaign's audience can always be traced to the exact run that produced
    it and an older run's interpretation is never rewritten.

    Rows are only ever added (by `clustering._store_run_state`); the one
    exception is `relabel_stored_run`, which refreshes the business labels of the
    newest row from its own stored profiles, exactly as it does for the
    singleton. Deleting a row cannot affect a campaign (`SET_NULL`) and never
    touches coupons or redemption history.
    """
    run_id = models.BigAutoField(primary_key=True)
    algorithm = models.CharField(max_length=64, default='KMeans(k-means++)')
    rfm_version = models.PositiveIntegerField(default=0)
    n_clusters = models.PositiveIntegerField(default=0)
    clustered = models.PositiveIntegerField(default=0)
    # [{'cluster_id', 'category', 'customer_count', 'confidence', ...profile}]
    mapping = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    class Meta:
        db_table = 'rfm_kmeans_runs'
        ordering = ['-run_id']

    def __str__(self):
        return f'Run #{self.run_id} on RFM v{self.rfm_version} ({self.clustered} buyers)'


class CampaignAudience(models.Model):
    """One row per (campaign, customer) coupon assignment.

    A K-Means campaign's audience is *materialized* when the campaign is
    published: every buyer in the selected clusters of the selected clustering
    run gets exactly one row here, which is the coupon issued to them. That is
    what freezes the audience - a future clustering run may move the buyer to
    another cluster, but the campaign keeps the members it was actually issued
    to, and the unique constraint makes a duplicate assignment impossible at the
    database level rather than by convention.

    Legacy (rule-based segment) campaigns never write here: their audience is
    still decided from the customer's current segment, so nothing about an
    already-published old campaign changes when this table is introduced.

    Customer identity is a plain text key (like `CampaignRedemption`) because
    `public.customers` is an unmanaged dataset table.
    """
    assignment_id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE,
                                 related_name='audience_assignments')
    customer_id = models.CharField(max_length=255)
    cluster_id = models.PositiveIntegerField()
    cluster_label = models.CharField(max_length=40, blank=True, default='')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rfm_campaign_audience'
        ordering = ['assignment_id']
        constraints = [
            # One coupon, one customer: publishing twice (or widening a live
            # campaign to a cluster that overlaps it) can never issue a second
            # coupon to the same buyer.
            models.UniqueConstraint(
                fields=['campaign', 'customer_id'],
                name='unique_coupon_assignment_per_customer',
            ),
        ]
        indexes = [
            # A customer's offer list asks "which published campaigns hold me"
            # in one query, for every campaign at once. The per-campaign count
            # (coupons issued) is served by the unique constraint's own index,
            # so only this reverse direction needs an index of its own.
            models.Index(fields=['customer_id', 'campaign'],
                         name='audience_customer_campaign'),
        ]

    def __str__(self):
        return f"{self.customer_id} in campaign {self.campaign_id}"


class CampaignRedemption(models.Model):
    redemption_id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE,
                                 related_name='redemptions')
    order_id = models.CharField(max_length=32)
    customer_id = models.CharField(max_length=255)
    discount_applied = models.DecimalField(max_digits=12, decimal_places=2)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rfm_campaign_redemptions'
        ordering = ['-redemption_id']
        # Duplicate-order protection: the same coupon cannot be booked twice
        # against the same order, whatever the usage limit is.
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'order_id'],
                name='unique_coupon_per_order',
            ),
            # One customer, one redemption per coupon - the business rule for
            # personalized segment offers. It is a database guarantee, not a
            # convention: two checkouts racing each other cannot both book it,
            # and it still lets a different customer use the same campaign.
            models.UniqueConstraint(
                fields=['campaign', 'customer_id'],
                name='unique_coupon_per_customer',
            ),
        ]
        indexes = [
            models.Index(fields=['campaign', 'customer_id'],
                         name='redemption_campaign_customer'),
            # The customer offer list asks "what has THIS buyer already
            # redeemed" in one query, for every campaign at once.
            models.Index(fields=['customer_id', 'campaign_id'],
                         name='redemption_customer_campaign'),
        ]

    def __str__(self):
        return f"{self.campaign_id} on {self.order_id} by {self.customer_id}"


class CustomerSegment(models.Model):
    """One row per buyer: the *latest* complete RFM result from a completed run.

    Originally this table carried only the segment label (so a customer page
    could read one indexed row instead of deserializing ~100k cached records or
    recomputing the whole analysis after a restart). It is now the dedicated,
    durable RFM *result* store the architecture calls for: every completed run
    synchronizes each buyer's full RFM state here - metrics, scores, segment,
    tags and the calculation version/timestamp - so the row for a customer is
    always their latest successfully calculated result, independent of the
    short-lived cache snapshot.

    CLV reads Monetary, Frequency and segment straight from these rows and
    never re-derives the RFM metrics from the 1M-row orders table; first/last
    purchase date and the lifetime order count are still computed on demand
    from `orders` by CLV (they are order facts, not stored here for CLV).

    Written only from a *successfully completed* run (see `segment_store`), and
    updated with an `ON CONFLICT ... DO UPDATE ... WHERE <changed>` upsert, so
    an unchanged customer is not rewritten (no `updated_at` churn) and an older
    calculation can never overwrite a newer one.

    Customer identity is a plain text key (`customer_id`), not a foreign key,
    because `public.customers`/`public.orders` are unmanaged dataset tables.
    """
    customer_id = models.CharField(max_length=255, primary_key=True)
    # RFM metrics (Recency in whole days, Frequency as the valid distinct order
    # count, Monetary as lifetime valid revenue - the same definition CLV uses).
    recency = models.IntegerField(null=True, blank=True)
    frequency = models.IntegerField(null=True, blank=True)
    monetary = models.DecimalField(max_digits=14, decimal_places=2,
                                   null=True, blank=True)
    # 1-5 percentile-band scores for each dimension plus a combined RFM score
    # (the R/F/M scores concatenated, e.g. "543"). The combined score is stored
    # for completeness/reporting; segmentation itself uses the percentiles.
    r_score = models.PositiveIntegerField(null=True, blank=True)
    f_score = models.PositiveIntegerField(null=True, blank=True)
    m_score = models.PositiveIntegerField(null=True, blank=True)
    rfm_score = models.CharField(max_length=3, blank=True, default='')
    # Latest segment label and secondary tags (e.g. Big Spender).
    segment = models.CharField(max_length=40)
    tags = models.JSONField(default=list, blank=True)
    # K-Means++ (k=4) clustering result over the *standardized* RFM features.
    # These two columns are completely independent of the rule-based `segment`
    # above: the cluster id is the raw numeric K-Means output (0-3, no business
    # meaning) and the category is the business label mapped from that cluster's
    # *unscaled* RFM profile. Both are nullable so a buyer that has not been
    # clustered yet (or has no eligible RFM metrics) simply carries no value, and
    # a clustering rerun overwrites the same row instead of adding a duplicate.
    # The original recency/frequency/monetary columns above are left exactly as
    # the RFM run wrote them - the standardized values used for clustering are
    # never stored. CLV still reads only the RFM columns; the cluster id is what
    # K-Means campaign targeting resolves a customer's group from (see
    # `cluster_targeting`), and publishing a campaign copies the assignment it
    # used into `rfm_campaign_audience` so the campaign's own audience is frozen.
    kmeans_cluster_id = models.PositiveIntegerField(null=True, blank=True)
    kmeans_category = models.CharField(max_length=40, blank=True, default='')
    # Purchase-date bookends kept alongside the metrics so the paginated RFM
    # results endpoint is fully served from this table (no order scan). CLV does
    # not consume these - it derives them from `orders` - so they are optional.
    first_purchase_date = models.DateField(null=True, blank=True)
    last_purchase_date = models.DateField(null=True, blank=True)
    # Version of the RFM calculation that last changed this row (monotonic run
    # id) - guards against an older run overwriting a newer result.
    version = models.PositiveIntegerField(default=0)
    # When this row's values were last calculated (per-customer) ...
    computed_at = models.DateTimeField()
    # ... and when a stored value actually changed (only moved on real change).
    # Nullable so adding the column to a populated table needs no back-fill
    # default; it is always set explicitly by the upsert write paths.
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'rfm_customer_segments'
        indexes = [
            # Audience counts by segment and the segment-filtered results list.
            models.Index(fields=['segment', 'customer_id'],
                         name='rfm_segment_by_label'),
            # The results endpoint sorts within a segment by Monetary (top
            # spenders); this keeps that filter+order an index scan.
            models.Index(fields=['segment', 'monetary'],
                         name='rfm_segment_by_monetary'),
            # K-Means cluster counts / profiles are aggregated by category and
            # cluster id whenever the dashboard, a rerun or a campaign audience
            # read them back. `kmeans_cluster_id` first, because every campaign
            # targeting query filters and groups by the cluster alone.
            models.Index(fields=['kmeans_category', 'kmeans_cluster_id'],
                         name='rfm_kmeans_by_category'),
            models.Index(fields=['kmeans_cluster_id', 'kmeans_category'],
                         name='rfm_kmeans_by_cluster'),
        ]

    def __str__(self):
        return f"{self.customer_id} -> {self.segment}"


class KmeansRunState(models.Model):
    """Single row describing the latest completed K-Means++ clustering run.

    The per-buyer labels live on `CustomerSegment` (one row per buyer, always the
    latest assignment). This row carries the *run* bookkeeping the page needs to
    explain those labels honestly and to know whether they are current:

    * `rfm_version` / `clustered` - which analysis version was clustered and how
      many buyers it covered, so a later RFM refresh (new buyers, moved metrics)
      can be reported as "clustering is out of date" instead of silently
      presenting stale groups.
    * `mapping` - cluster id -> business category with its unscaled RFM/tenure
      profile and the mapping confidence. Cluster ids carry no business meaning,
      so this is the audit trail of how the labels were derived.
    * `scaler` - the fitted StandardScaler mean/scale, proving the standardized
      space was used for clustering only and never stored per buyer.

    Keeping it in its own table (rather than columns on the singleton analysis
    state) means clustering can be re-run without touching any RFM run bookkeeping.
    """
    SINGLETON_ID = 1
    id = models.PositiveIntegerField(primary_key=True)
    algorithm = models.CharField(max_length=64, default='KMeans(k-means++)')
    # RFM analysis version whose persisted metrics this clustering consumed.
    rfm_version = models.PositiveIntegerField(default=0)
    # Effective cluster count (<= the requested four) and buyers assigned.
    n_clusters = models.PositiveIntegerField(default=0)
    clustered = models.PositiveIntegerField(default=0)
    # [{'cluster_id', 'category', 'confidence', 'customer_count', ...profile}]
    mapping = models.JSONField(default=list, blank=True)
    # Business categories the data could not support - reported, never forced.
    unsupported_categories = models.JSONField(default=list, blank=True)
    # Fitted scaler statistics {'mean': [...], 'scale': [...]} of the three
    # standardized features. Reporting only: never written to the RFM columns.
    scaler = models.JSONField(default=dict, blank=True)
    # The append-only history row written for this same run. Campaigns reference
    # that row (not this singleton), so a later clustering run can never change
    # what an existing campaign points at; this pointer only lets a read of the
    # latest run name the run it describes.
    run = models.ForeignKey('ClusteringRun', null=True, blank=True,
                            on_delete=models.SET_NULL, related_name='+')
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    class Meta:
        db_table = 'rfm_kmeans_run_state'

    def __str__(self):
        return f'K-Means on RFM v{self.rfm_version} ({self.clustered} buyers)'


class DashboardSnapshot(models.Model):
    """One row per analysis version: the assembled dashboard aggregate.

    The RFM page's first paint used to pay for a GROUPING SETS aggregation over
    ~100k persisted buyer rows plus a count of the `customers` table whenever
    the in-process cache was empty - which happens on every `runserver`
    restart, because LocMemCache dies with the process and a remote Neon query
    costs hundreds of milliseconds each. This row makes that expensive assembly
    durable: it stores exactly the payload the dashboard reads, keyed by the
    analysis version it was computed from and by the clustering run whose
    labels it contains. A reader that matches both numbers takes this row
    instead of re-running the aggregation; anything else (a new analysis, a
    re-clustering) recomputes and overwrites the row. The numbers are the same
    aggregates the live query would return, so caching never trades correctness
    for speed - a snapshot for a superseded version is simply never served.
    """
    version = models.PositiveIntegerField(primary_key=True)
    # The clustering run whose labels are baked into `payload`. A different (or
    # later) run means the stored cluster counts are no longer current.
    clustering_run_id = models.PositiveIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField()

    class Meta:
        db_table = 'rfm_dashboard_snapshot'
        ordering = ['-version']

    def __str__(self):
        return f'Dashboard bundle v{self.version} (run {self.clustering_run_id})'


class RfmAnalysisState(models.Model):
    """Single row recording which analysis version is currently stored.

    It tells the read path the difference between "this buyer simply has no
    eligible purchase (so: no personalized offers)" and "no analysis has ever
    completed here yet (so: one is needed)". Without it, a missing segment row
    would be indistinguishable from an uninitialised system.
    """
    SINGLETON_ID = 1
    id = models.PositiveIntegerField(primary_key=True)
    version = models.PositiveIntegerField(default=0)
    buyer_count = models.PositiveIntegerField(default=0)
    analysis_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField()
    # Cheap fingerprint of the eligible source data at the moment this version
    # completed (eligible order count | distinct buyers | max purchase date).
    # The incremental refresh compares the live fingerprint against this to
    # decide whether anything actually changed, without a dirty-customer queue.
    source_fingerprint = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        db_table = 'rfm_analysis_state'

    def __str__(self):
        return f'RFM v{self.version} ({self.buyer_count} buyers)'
