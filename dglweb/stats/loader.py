"""Persist batting rows — the shared upsert used by both loader commands.

`import_batting` (historical backfill) and `update_batting` (the scheduled current-season
refresh) both write through here, so the idempotent upsert lives in one place. Upserting on the
natural key `(player, season, stint)` is what makes re-running after a failed night safe: it
corrects the data instead of duplicating it.
"""

from typing import Any

from django.db import transaction

from dglweb.stats.models import Batting

# Every column except the natural key gets refreshed on conflict.
_UPDATE_FIELDS = [field.name for field in Batting._meta.fields if field.name not in {"id", "player", "season", "stint"}]


def save_batting_rows(rows: list[dict[str, Any]]) -> int:
    """Upsert the rows on (player, season, stint); returns how many were written."""
    if not rows:
        return 0

    with transaction.atomic():
        Batting.objects.bulk_create(
            [Batting(**row) for row in rows],
            update_conflicts=True,
            unique_fields=["player", "season", "stint"],
            update_fields=_UPDATE_FIELDS,
            batch_size=500,
        )
    return len(rows)
