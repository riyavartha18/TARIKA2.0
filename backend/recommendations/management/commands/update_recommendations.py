from django.core.management.base import BaseCommand
from recommendations.services import RecommendationService


class Command(BaseCommand):
    help = (
        "Mines association rules from historical delivered orders using Apriori "
        "and updates the product_recommendations database table."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-support',
            type=float,
            default=RecommendationService.DEFAULT_MIN_SUPPORT,
            help=f"Minimum support threshold for Apriori (default: {RecommendationService.DEFAULT_MIN_SUPPORT})"
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=RecommendationService.DEFAULT_MIN_CONFIDENCE,
            help=f"Minimum confidence threshold for association rules (default: {RecommendationService.DEFAULT_MIN_CONFIDENCE})"
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Simulate the pipeline and print discovered rules without modifying the database."
        )

    def handle(self, *args, **options):
        min_support = options['min_support']
        min_confidence = options['min_confidence']
        dry_run = options['dry_run']

        self.stdout.write(self.style.NOTICE("Running Apriori Recommendation Pipeline..."))
        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode: Database will not be changed."))

        try:
            results = RecommendationService.update_recommendations(
                min_support=min_support,
                min_confidence=min_confidence,
                dry_run=dry_run
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR("\n=================================================="))
            self.stdout.write(self.style.ERROR("RECOMMENDATION ENGINE EXECUTION FAILED"))
            self.stdout.write(self.style.ERROR("=================================================="))
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            self.stdout.write(self.style.ERROR("=================================================="))
            return

        orders_count = results.get('delivered_orders_count', 0)
        products_count = results.get('products_count', 0)
        itemsets_count = results.get('frequent_itemsets_count', 0)
        rules_count = results.get('rules_count', 0)
        success = results.get('success', False)
        message = results.get('message', '')

        # Print concise summary
        self.stdout.write("\n==================================================")
        self.stdout.write("RECOMMENDATION ENGINE SUMMARY")
        self.stdout.write("==================================================")
        self.stdout.write(f"Delivered orders / transactions : {orders_count:,}")
        self.stdout.write(f"Unique catalog products         : {products_count:,}")
        self.stdout.write(f"Frequent itemsets mined         : {itemsets_count:,}")
        self.stdout.write(f"Recommendation rules produced   : {rules_count:,}")
        self.stdout.write("--------------------------------------------------")

        if success:
            self.stdout.write(self.style.SUCCESS(f"Status  : SUCCESS"))
            self.stdout.write(self.style.SUCCESS(f"Details : {message}"))
        else:
            self.stdout.write(self.style.WARNING(f"Status  : INCOMPLETE / SKIPPED"))
            self.stdout.write(self.style.WARNING(f"Details : {message}"))

        self.stdout.write("==================================================\n")
