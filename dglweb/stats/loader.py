"""Persist stat rows — the shared idempotent upsert used by every loader command.

Upserting on the natural key `(player, season, stint)` is what makes re-running after a failed
night safe: it corrects the data instead of duplicating it. Generic over the model so batting,
pitching (and later fielding) all write through the same tested path.
"""

from typing import Any

from django.db import models, transaction

from dglweb.stats.models import Batting, Pitching


def _update_fields(model: type[models.Model]) -> list[str]:
    """Every column except the natural key gets refreshed on conflict."""
    return [f.name for f in model._meta.fields if f.name not in {"id", "player", "season", "stint"}]


def _upsert(model: type[models.Model], rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with transaction.atomic():
        # `_default_manager` (not `.objects`) so this stays typed over a generic `type[Model]`.
        model._default_manager.bulk_create(
            [model(**row) for row in rows],
            update_conflicts=True,
            unique_fields=["player", "season", "stint"],
            update_fields=_update_fields(model),
            batch_size=500,
        )
    return len(rows)


def save_batting_rows(rows: list[dict[str, Any]]) -> int:
    """Upsert batting rows on (player, season, stint); returns how many were written."""
    return _upsert(Batting, rows)


def save_pitching_rows(rows: list[dict[str, Any]]) -> int:
    """Upsert pitching rows on (player, season, stint); returns how many were written."""
    return _upsert(Pitching, rows)
