from django.db import models


class ProductRecommendation(models.Model):
    """
    Model representing directional association rules discovered from delivered customer orders.
    Maps to the existing 'product_recommendations' table in Supabase/PostgreSQL.
    """
    id = models.BigAutoField(primary_key=True)
    product = models.TextField(
        help_text="Antecedent product name"
    )
    frequently_bought_with = models.TextField(
        help_text="Consequent recommended product name"
    )
    support = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Fraction of total transactions containing both items"
    )
    confidence = models.DecimalField(
        max_digits=10,
        decimal_places=5,
        null=True,
        blank=True,
        help_text="Likelihood of purchasing 'frequently_bought_with' given 'product'"
    )
    lift = models.DecimalField(
        max_digits=16,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Strength of rule over random co-occurrence"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'product_recommendations'
        managed = False
        ordering = ['-lift', '-confidence']

    def __str__(self):
        return f"{self.product} -> {self.frequently_bought_with} (lift: {self.lift})"
