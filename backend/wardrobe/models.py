from django.db import models

class WardrobeItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer_id = models.TextField()  # Exact text UUID string matching customer.customer_id
    item_name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True, null=True)
    primary_color = models.CharField(max_length=100)
    secondary_color = models.CharField(max_length=100, blank=True, null=True)
    style_tag = models.CharField(max_length=100, default='Casual')
    occasion = models.CharField(max_length=100, default='Casual')
    season = models.CharField(max_length=100, default='All Season')
    material = models.CharField(max_length=100, blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wardrobe_items'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.item_name} ({self.category}, Customer {self.customer_id})"
