"""Catalog cache keys + invalidation.

The customer-facing catalog caches a few server-side aggregates because the
~90k-row ``products`` table is expensive to scan on every request:

  * the category list (``catalog:categories``), and
  * the curated home rails (new arrivals / trending / sale), keyed by the exact
    query string.

A warehouse edit, delete or stock receipt changes those derived values, so every
cache must be refreshed at once. Deleting individual per-query-string keys is not
possible with the default cache backend, so the curated keys embed a monotonically
increasing *catalog version*. Bumping the version instantly orphans every cached
rail (the next request recomputes it) while the category key is removed directly.
"""

from django.core.cache import cache

VERSION_KEY = 'catalog:version'
CATEGORIES_KEY = 'catalog:categories:v1'


def get_catalog_version():
    version = cache.get(VERSION_KEY)
    if version is None:
        version = 1
        cache.set(VERSION_KEY, version, None)
    return version


def categories_cache_key():
    return CATEGORIES_KEY


def curated_cache_key(endpoint, query_key):
    return f'catalog:curated:v{get_catalog_version()}:{endpoint}:{query_key}'


def bump_catalog_version():
    """Call after any product mutation so stale caches are never served.

    Uses an atomic ``incr`` so a concurrent bump from another worker/process
    can never be lost (a plain get-then-set would race under a shared backend).
    ``cache.incr`` is atomic on Redis and on LocMemCache; when the key does not
    exist yet it is seeded, so the first request after a restart still works.
    """
    try:
        version = cache.incr(VERSION_KEY)
    except ValueError:
        cache.add(VERSION_KEY, 1, None)
        version = cache.incr(VERSION_KEY)
    cache.delete(CATEGORIES_KEY)
    return version
