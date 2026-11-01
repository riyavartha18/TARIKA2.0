"""Live audience size for a campaign's targeting, from the latest snapshot.

The count always comes from the most recently *completed* RFM analysis (the
snapshot cache), never from a stored assignment: when a fresh run moves a
customer out of Champions they stop counting towards Champions campaigns.
When a campaign only names primary segments the answer is a metadata sum (no
row scan); the Big Spender secondary tag needs the segment buckets, which the
cache already keeps grouped, so it stays cheap.
"""

from . import cache_manager, utils


def audience_count(segments, tags):
    """Eligible customer count for these targets, or None if no analysis yet."""
    meta = cache_manager.get_meta()
    if not meta:
        return None
    segments = [s for s in (segments or []) if s in utils.ALL_SEGMENTS]
    if not segments:
        return 0
    tags = [t for t in (tags or []) if t in utils.SECONDARY_TAGS]

    if not tags:
        counts = meta['segment_counts']
        return sum(int(counts.get(s, 0)) for s in segments)

    total = 0
    for segment in segments:
        rows, _version = cache_manager.get_segment_base(segment)
        if not rows:
            continue
        total += sum(1 for r in rows
                     if set(tags) & set(r.get('tags') or []))
    return total
