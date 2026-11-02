"""Single source of truth for category / subcategory normalization.

Product categories and subcategories live in free-text columns on the unmanaged
`public.products` table (and mirrored into `dim_product`), so the same logical
value can be stored with different capitalization or stray surrounding
whitespace - "Dress", "dress", " DRESS ". Grouping, DISTINCT lists, dropdown
filters and equality filters must treat those as ONE category, or charts,
filters and reports show case-only duplicates.

This module centralizes that rule so no feature re-implements it ad hoc:

* `normalize_category(value)`  - Python comparison/grouping key
  (strip + casefold + typographic-apostrophe folding).
* `canonical_display(value)`   - clean, consistent display name (trim only;
  never re-cases the real value).
* `sql_norm_expr(column)`      - the SQL-side normalization of a (possibly
  table-qualified) column, used for GROUP BY / DISTINCT / equality so the
  database merges variants server-side and no stored row is rewritten.

Only values that differ solely in case and/or surrounding whitespace merge;
genuinely different names stay separate. No production data is mutated -
normalization happens at read/aggregate/filter time, and new writes are trimmed
by the serializers, so a fresh "dress" groups with the existing "Dress".
"""


def normalize_category(value):
    """Comparison/grouping key: trimmed, casefolded, apostrophe-folded.

    Two names map to the same key exactly when they differ only by surrounding
    whitespace and/or letter case (plus curly vs straight apostrophes). Inner
    whitespace is left untouched so genuinely different names never merge.
    """
    if value is None:
        return ''
    return str(value).strip().replace('\u2019', "'").lower()


def canonical_display(value):
    """A clean display name: trims only, preserving the real casing."""
    return (str(value).strip() if value is not None else '')


def sql_norm_expr(column):
    """Normalize a (table-qualified) SQL column for grouping/matching.

    LOWER(TRIM(COALESCE(<column>, ''))) works on both PostgreSQL and SQLite, so
    the same expression drives production and the unit-test backend.
    """
    return f"LOWER(TRIM(COALESCE({column}, '')))"
