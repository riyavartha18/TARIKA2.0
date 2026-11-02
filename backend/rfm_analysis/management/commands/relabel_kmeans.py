"""Re-derive the K-Means business labels for the persisted clustering run.

When the K-Means label vocabulary changes, a completed run still carries its OLD
label strings in `rfm_customer_segments.kmeans_category` and in the run-state
`mapping`, even though every buyer's numeric cluster assignment and each
cluster's unscaled RFM profile are exactly right. The business label is derived
purely from those stored profiles, so it can be recomputed from them here -
WITHOUT reloading the population and WITHOUT re-fitting K-Means.

This command never changes a buyer's `kmeans_cluster_id` (so no customer moves
between clusters, no customer is added or removed) and never recomputes RFM or
touches the rule-based segment or any CLV input: it only refreshes the
`kmeans_category` string mapped onto each existing cluster and the run-state
mapping, then bumps the clustering epoch so the dashboard rebuilds.

Usage:
    python manage.py relabel_kmeans [--check]

`--check` only reports whether the persisted labels are current, changing
nothing.
"""

from django.core.management.base import BaseCommand

from rfm_analysis import clustering


class Command(BaseCommand):
    help = 'Refresh persisted K-Means business labels from stored profiles.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check', action='store_true',
            help='Report whether the persisted labels are current; change nothing.')

    def handle(self, *args, **options):
        if options.get('check'):
            state = clustering.get_run_state()
            current = clustering.labels_are_current(state)
            self.stdout.write(self.style.SUCCESS(
                'Persisted K-Means labels are current.' if current
                else 'Persisted K-Means labels are legacy and need relabelling.'))
            return

        result = clustering.relabel_stored_run()
        if result is None:
            self.stdout.write(self.style.WARNING(
                'No completed clustering run to relabel (or it has no profiled '
                'clusters). Run clustering first.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Re-derived {len(result["clusters"])} cluster labels from the '
            f'stored profiles (K-Means was not re-run; cluster assignments are '
            f'unchanged).'))
        for cluster in result['clusters']:
            self.stdout.write(
                f"  Cluster {cluster['cluster_id']} -> {cluster['category']} "
                f"[{cluster['confidence']} confidence, "
                f"supported={cluster['supported']}] "
                f"({cluster['customer_count']} buyers, "
                f"R~{cluster['avg_recency']} F~{cluster['avg_frequency']} "
                f"M~{cluster['avg_monetary']})")

        if result['unsupported_categories']:
            self.stdout.write(self.style.WARNING(
                'Categories the data did not support: '
                + ', '.join(result['unsupported_categories'])))
        for text in result['ambiguities']:
            self.stdout.write(self.style.WARNING(f'  note: {text}'))
