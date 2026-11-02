"""Run K-Means++ (k=4) clustering over the RFM results already in the database.

Reuses the persisted Recency / Frequency / Monetary values (it never recomputes
RFM), standardizes them, runs the actual K-Means++ algorithm, maps the four
clusters to business categories from their unscaled profiles, and writes the
cluster id + category back onto each buyer's existing row. The original RFM
values, the rule-based segment and every CLV dependency are left untouched, and
re-running updates the same rows instead of creating duplicates.

Usage:
    python manage.py run_kmeans_segmentation [--dry-run]

`--dry-run` computes and prints the clustering (profiles, mapping, counts) but
does not persist anything.
"""

import json

from django.core.management.base import BaseCommand

from rfm_analysis import clustering


class Command(BaseCommand):
    help = 'Cluster persisted RFM buyers into 4 K-Means++ groups and map them.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compute and print the result without writing it to the DB.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        result = clustering.run_clustering(save=not dry_run)

        if not result.get('available'):
            self.stdout.write(self.style.WARNING(
                result.get('message') or 'Nothing to cluster.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Clustered {result['clustered']} buyers into "
            f"{result['effective_clusters']} of {result['requested_clusters']} "
            f"requested K-Means++ groups"
            + (' (dry run, nothing saved)' if dry_run else '') + '.'))

        for cluster in result['clusters']:
            self.stdout.write(
                f"  Cluster {cluster['cluster_id']} -> {cluster['category']} "
                f"[{cluster['confidence']} confidence] "
                f"({cluster['customer_count']} buyers, "
                f"R~{cluster['avg_recency']} F~{cluster['avg_frequency']} "
                f"M~{cluster['avg_monetary']})")

        if result['unsupported_categories']:
            self.stdout.write(self.style.WARNING(
                'Categories the data did not support: '
                + ', '.join(result['unsupported_categories'])))

        if options.get('verbosity', 1) > 1:
            self.stdout.write(json.dumps(result, indent=2))
