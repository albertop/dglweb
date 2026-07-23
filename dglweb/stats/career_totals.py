"""Build the materialized career totals from the season tables (in-house, all seasons).

Generic over the group: sum the counting columns over `season_totals()` / `position_totals()`,
recompute the rate columns via `career_rate` (exact where the formula is known, else a playing-time
weighted average). Career includes **every** season (Negro Leagues too). `ip`/`innings` are not
stored; derive them from `outs`/`innings_outs` at display. The proxy's career endpoint is the
reference `parity_career` checks this against — here we compute, we do not fetch.
"""

from collections.abc import Callable
from typing import Any

from django.db import models, transaction

from dglweb.stats import career_rate
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    Fielding,
    FieldingCareer,
    Pitching,
    PitchingCareer,
)

# group -> (career model, season model)
_GROUPS: dict[str, tuple[type[models.Model], type[models.Model]]] = {
    "batting": (BattingCareer, Batting),
    "pitching": (PitchingCareer, Pitching),
    "fielding": (FieldingCareer, Fielding),
}
_KEY_FIELDS = {"player", "pos", "player_id"}


def _stat_fields(career_model: type[models.Model]) -> tuple[list[str], list[str]]:
    """(counting columns, rate columns) of a career model — the FloatFields are rates, ints counts."""
    counting, rates = [], []
    for field in career_model._meta.fields:
        if field.name in _KEY_FIELDS or field.is_relation:
            continue
        if isinstance(field, models.FloatField):
            rates.append(field.name)
        elif isinstance(field, models.IntegerField):
            counting.append(field.name)
    return counting, rates


def build_career_totals(note: Callable[[str], None] = lambda _: None) -> dict[str, int]:
    """Rebuild every career table from scratch. Returns {written}."""
    written = 0
    with transaction.atomic():
        for group, (career_model, season_model) in _GROUPS.items():
            counting, rates = _stat_fields(career_model)
            weight_col = career_rate.WEIGHT[group]
            is_fielding = group == "fielding"

            base = season_model._default_manager.all()
            totals = base.position_totals() if is_fielding else base.season_totals()  # type: ignore[attr-defined]
            columns = list(dict.fromkeys(["player_id", *(["pos"] if is_fielding else []), *counting, *rates]))

            # Accumulate per key: counting sums, and (Σ rate·weight, Σ weight) for proration.
            acc: dict[tuple[Any, Any], dict[str, Any]] = {}
            for row in totals.values(*columns):
                pos = row["pos"] if is_fielding else None
                bucket = acc.setdefault(
                    (row["player_id"], pos),
                    {
                        "player_id": row["player_id"],
                        "pos": pos,
                        "sums": dict.fromkeys(counting),
                        "weighted": dict.fromkeys(rates, 0.0),
                        "weight": 0.0,
                    },
                )
                for column in counting:
                    value = row[column]
                    if value is not None:
                        bucket["sums"][column] = (bucket["sums"][column] or 0) + value
                weight = row[weight_col]
                if weight:
                    bucket["weight"] += weight
                    for rate in rates:
                        rate_value = row[rate]
                        if rate_value is not None:
                            bucket["weighted"][rate] += rate_value * weight

            objects = []
            for bucket in acc.values():
                fields: dict[str, Any] = dict(bucket["sums"])
                for rate in rates:
                    if career_rate.has_exact(group, rate):
                        fields[rate] = career_rate.exact_value(group, rate, bucket["sums"])
                    else:
                        fields[rate] = bucket["weighted"][rate] / bucket["weight"] if bucket["weight"] else None
                if is_fielding:
                    fields["pos"] = bucket["pos"]
                objects.append(career_model(player_id=bucket["player_id"], **fields))

            career_model._default_manager.all().delete()
            career_model._default_manager.bulk_create(objects, batch_size=500)
            written += len(objects)
            note(f"{group}: {len(objects)} carreras")
    return {"written": written}
