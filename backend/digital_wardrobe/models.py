from django.db import models
from django.utils import timezone


class WardrobeItem(models.Model):
    SOURCE_CHOICES = (
        ('upload', 'Customer Upload'),
        ('order_import', 'Order History Import'),
    )

    SLOT_CHOICES = (
        ('top', 'Topwear'),
        ('bottom', 'Bottomwear'),
        ('one_piece', 'One Piece / Dress / Saree'),
        ('footwear', 'Footwear'),
        ('bag', 'Bag / Clutch / Potli'),
        ('accessory', 'Accessory / Jewellery'),
    )

    id = models.BigAutoField(primary_key=True)
    customer_id = models.TextField(db_index=True)

    # Images
    image_url = models.TextField(blank=True, null=True, help_text="Transparent cutout WebP/PNG")
    flat_image_url = models.TextField(blank=True, null=True, help_text="Flattened on #FFFFFF with subtle soft shadow")
    thumb_url = models.TextField(blank=True, null=True, help_text="400x400 square thumbnail")
    original_image_url = models.TextField(blank=True, null=True, help_text="Private original upload")

    # Source & Linking
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default='upload', db_index=True)
    product_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    item_name = models.CharField(max_length=255, default='Wardrobe Piece')

    # Standardized Attribute Schema (reusing Smart Budget Stylist)
    slot_type = models.CharField(max_length=32, choices=SLOT_CHOICES, default='top', db_index=True)
    subtype = models.CharField(max_length=64, blank=True, default='other', db_index=True)
    formality = models.IntegerField(default=3)  # 1 to 5
    pattern = models.CharField(max_length=64, default='solid')
    dominant_colours = models.JSONField(default=list, help_text="List of detected lowercase colors")
    style_family = models.CharField(max_length=64, default='western', db_index=True)
    season = models.CharField(max_length=64, default='all_season')
    sleeve_type = models.CharField(max_length=64, blank=True, null=True, db_index=True, help_text="sleeveless, short, 3/4, full")
    length = models.CharField(max_length=32, blank=True, null=True, db_index=True, help_text="mini, midi, maxi")

    # Specific subcategory attributes
    footwear_type = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    accessory_type = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    metal_tone = models.CharField(max_length=32, blank=True, null=True)
    includes_blouse = models.BooleanField(default=False)
    includes_dupatta = models.BooleanField(default=False)

    # Confidence and Review Workflow
    confidence = models.FloatField(default=1.0)
    needs_review = models.BooleanField(default=False, db_index=True)
    user_verified = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    category = models.CharField(max_length=64, default='top', db_column='category')
    retake_prompt = models.TextField(blank=True, null=True)

    # Studio render and original-photo display mode
    render_status = models.CharField(
        max_length=32,
        default='completed',
        db_index=True,
        help_text="'pending', 'processing', 'completed', 'failed'"
    )
    display_mode = models.CharField(
        max_length=32,
        default='render',
        db_index=True,
        help_text="'render' (studio render) or 'original' (raw photo)"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wardrobe_items'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.category:
            self.category = self.slot_type or 'top'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} [{self.slot_type}/{self.subtype}] (Cust: {self.customer_id})"


class WardrobeMatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.TextField(db_index=True)
    product_key = models.TextField(db_index=True)
    wardrobe_item = models.ForeignKey(WardrobeItem, on_delete=models.CASCADE, related_name='product_matches')
    score = models.FloatField(default=0.0)
    reasons = models.JSONField(default=list)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wardrobe_matches'
        indexes = [
            models.Index(fields=['customer_id', 'product_key']),
        ]
        unique_together = ('customer_id', 'product_key', 'wardrobe_item')

    def __str__(self):
        return f"Match: Cust {self.customer_id} - Prod {self.product_key} - Item {self.wardrobe_item_id} (Score {self.score})"


class WardrobeOutfit(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.TextField(db_index=True)
    name = models.CharField(max_length=128, default='Curated Look')
    item_ids = models.JSONField(default=list)
    is_valid = models.BooleanField(default=True)
    validation_notes = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'wardrobe_outfits'
        ordering = ['-created_at']


class WardrobeCollection(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.TextField(db_index=True)
    name = models.CharField(max_length=128)
    items = models.ManyToManyField(WardrobeItem, related_name='collections', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'wardrobe_collections'
        ordering = ['-created_at']


class WardrobeNotificationLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.TextField(db_index=True)
    product_key = models.TextField()
    score = models.FloatField(default=0.0)
    matches_count = models.IntegerField(default=0)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'wardrobe_notification_logs'
        ordering = ['-sent_at']
