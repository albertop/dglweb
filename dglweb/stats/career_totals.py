"""Build the materialized career totals (with subtotals) from the season tables.

Each player gets several rows: batting/pitching a subtotal **per team** and **per league** plus the
**grand total**; fielding a subtotal **per position** plus the **grand total**. Counting columns are
summed; rate columns recomputed via `career_rate` (exact where the formula is known, else a
playing-time weighted average). Career includes every season (Negro Leagues too).

Aggregation levels, and how the seasons feed them:
  * grand total  — sum over `season_totals()` / `position_totals()` (the anti-double-count views).
  * team/league  — sum over the per-team rows (`team != XXX`), grouped by team / by league.
  * position     — the per-position `position_totals()`.
Σ team subtotals == Σ league subtotals == grand total (the per-team rows of a season sum to its XXX).

`sort_order` (the owner's display order): teams first by PA, then leagues by PA, then total; for
fielding, positions by G then total. `ip`/`innings` are not stored — derive from `outs` at display.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from django.db import models, transaction

from dglweb.players.visibility import only_visible
from dglweb.stats import career_rate
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    CareerLevel,
    Fielding,
    FieldingCareer,
    Pitching,
    PitchingCareer,
)

# fields that are not stats (never summed / recomputed)
_KEY_FIELDS = {"id", "player", "player_id", "level", "team", "league", "pos", "sort_order"}
# Same idea for a *line* model (a season or a postseason round): its keys differ from a career row's,
# and summing `season` or averaging `age` would be nonsense.
_LINE_KEY_FIELDS = {"season", "stint", "age"}
_SORT_BASE = {"team": 100, "league": 200, "position": 100, "total": 300}


def aggregate_lines(group: str, model: type[models.Model], rows: Sequence[models.Model]) -> dict[str, Any]:
    """Collapse stat lines into one set of fields, exactly as a career row is built: counting columns
    summed, rates recomputed **from those sums** where the formula is known (never an average of
    averages), else a playing-time weighted average.

    For subtotals that are not materialized — the postseason ones, computed per request. Returns a
    plain dict so the caller decides what to wrap it in.
    """
    counting: list[str] = []
    rates: list[str] = []
    for field in model._meta.fields:
        if field.is_relation or field.name in _LINE_KEY_FIELDS:
            continue
        if not isinstance(field, models.IntegerField | models.FloatField):
            continue
        is_rate = isinstance(field, models.FloatField) and (group, field.name) not in career_rate.CUMULATIVE_FLOATS
        (rates if is_rate else counting).append(field.name)

    weight_col = career_rate.WEIGHT[group]
    columns = list(dict.fromkeys([*counting, *rates, weight_col]))
    values = [{column: getattr(row, column, None) for column in columns} for row in rows]
    bucket = _accumulate(values, counting, rates, weight_col, lambda _: "all").get("all")
    return _stats(bucket, group, rates) if bucket else {}


def _stat_fields(group: str, career_model: type[models.Model]) -> tuple[list[str], list[str]]:
    """(counting columns, rate columns). Additive-float sabermetrics (WAR, UZR…) count, not prorate."""
    counting: list[str] = []
    rates: list[str] = []
    for field in career_model._meta.fields:
        if field.name in _KEY_FIELDS or field.is_relation:
            continue
        is_rate = isinstance(field, models.FloatField) and (group, field.name) not in career_rate.CUMULATIVE_FLOATS
        (rates if is_rate else counting).append(field.name)
    return counting, rates


def _accumulate(
    rows: list[dict[str, Any]],
    counting: list[str],
    rates: list[str],
    weight_col: str,
    key: Callable[[dict[str, Any]], Any],
) -> dict[Any, dict[str, Any]]:
    """Sum counting columns and (Σ rate·weight, Σ weight) per key. `key` returning None drops a row."""
    acc: dict[Any, dict[str, Any]] = {}
    for row in rows:
        bucket_key = key(row)
        if bucket_key is None:
            continue
        bucket = acc.setdefault(
            bucket_key, {"sums": dict.fromkeys(counting), "weighted": dict.fromkeys(rates, 0.0), "weight": 0.0}
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
    return acc


def _stats(bucket: dict[str, Any], group: str, rates: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = dict(bucket["sums"])
    for rate in rates:
        if career_rate.has_exact(group, rate):
            fields[rate] = career_rate.exact_value(group, rate, bucket["sums"])
        else:
            fields[rate] = bucket["weighted"][rate] / bucket["weight"] if bucket["weight"] else None
    return fields


def _build_batting_pitching(group: str, career_model: type[models.Model], season_model: type[models.Model]) -> int:
    counting, rates = _stat_fields(group, career_model)
    weight_col = career_rate.WEIGHT[group]
    order_col = "pa" if group == "batting" else "bf"  # the pitcher's PA is bf
    columns = list(dict.fromkeys(["player_id", "team", "league", *counting, *rates]))

    manager = only_visible(season_model._default_manager.all())
    season_rows = list(manager.season_totals().values(*columns))  # type: ignore[attr-defined]
    grand = _accumulate(season_rows, counting, rates, weight_col, lambda r: r["player_id"])
    per_team_rows = list(manager.exclude(team="XXX").values(*columns))
    teams = _accumulate(
        per_team_rows, counting, rates, weight_col, lambda r: (r["player_id"], r["team"]) if r["team"] else None
    )
    leagues = _accumulate(
        per_team_rows, counting, rates, weight_col, lambda r: (r["player_id"], r["league"]) if r["league"] else None
    )

    teams_by_player: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for (player_id, team), bucket in teams.items():
        teams_by_player[player_id].append((team, bucket))
    leagues_by_player: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for (player_id, league), bucket in leagues.items():
        leagues_by_player[player_id].append((league, bucket))

    def order(pair: tuple[str, dict[str, Any]]) -> int:
        return -(pair[1]["sums"].get(order_col) or 0)

    objects = []
    for player_id, total_bucket in grand.items():
        for index, (team, bucket) in enumerate(sorted(teams_by_player[player_id], key=order)):
            objects.append(
                career_model(
                    player_id=player_id,
                    level=CareerLevel.TEAM,
                    team=team,
                    sort_order=_SORT_BASE["team"] + index,
                    **_stats(bucket, group, rates),
                )
            )
        for index, (league, bucket) in enumerate(sorted(leagues_by_player[player_id], key=order)):
            objects.append(
                career_model(
                    player_id=player_id,
                    level=CareerLevel.LEAGUE,
                    league=league,
                    sort_order=_SORT_BASE["league"] + index,
                    **_stats(bucket, group, rates),
                )
            )
        objects.append(
            career_model(
                player_id=player_id,
                level=CareerLevel.TOTAL,
                sort_order=_SORT_BASE["total"],
                **_stats(total_bucket, group, rates),
            )
        )

    career_model._default_manager.all().delete()
    career_model._default_manager.bulk_create(objects, batch_size=500)
    return len(objects)


def _build_fielding() -> int:
    group = "fielding"
    counting, rates = _stat_fields(group, FieldingCareer)
    weight_col = career_rate.WEIGHT[group]
    columns = list(dict.fromkeys(["player_id", "pos", *counting, *rates]))

    rows = list(
        only_visible(Fielding.objects.position_totals()).exclude(pos="DH").values(*columns)
    )  # DH is not a position
    positions = _accumulate(rows, counting, rates, weight_col, lambda r: (r["player_id"], r["pos"]))
    grand = _accumulate(rows, counting, rates, weight_col, lambda r: r["player_id"])

    positions_by_player: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for (player_id, pos), bucket in positions.items():
        positions_by_player[player_id].append((pos, bucket))

    objects = []
    for player_id, total_bucket in grand.items():
        ordered = sorted(positions_by_player[player_id], key=lambda pair: -(pair[1]["sums"].get("gp") or 0))
        for index, (pos, bucket) in enumerate(ordered):
            objects.append(
                FieldingCareer(
                    player_id=player_id,
                    level=CareerLevel.POSITION,
                    pos=pos,
                    sort_order=_SORT_BASE["position"] + index,
                    **_stats(bucket, group, rates),
                )
            )
        objects.append(
            FieldingCareer(
                player_id=player_id,
                level=CareerLevel.TOTAL,
                sort_order=_SORT_BASE["total"],
                **_stats(total_bucket, group, rates),
            )
        )

    FieldingCareer._default_manager.all().delete()
    FieldingCareer._default_manager.bulk_create(objects, batch_size=500)
    return len(objects)


def build_career_totals(note: Callable[[str], None] = lambda _: None) -> dict[str, int]:
    """Rebuild every career table (with subtotals) from scratch. Returns {written}."""
    written = 0
    with transaction.atomic():
        for group, career_model, season_model in [
            ("batting", BattingCareer, Batting),
            ("pitching", PitchingCareer, Pitching),
        ]:
            count = _build_batting_pitching(group, career_model, season_model)
            written += count
            note(f"{group}: {count} filas")
        count = _build_fielding()
        written += count
        note(f"fielding: {count} filas")
    return {"written": written}
