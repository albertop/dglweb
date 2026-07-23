"""The leaders engine: precompute `dgl_leader` from our stat tables for the Dominican subset.

For each active `Metric` and each board its calc flags enable, rank players and write `Leader` rows.
Fielding metrics are broken down **by position** (`fielding_pos`); batting/pitching are not. Only
seasons from 1956 on count (Negro Leagues are excluded from leaderboards). Ties get a dense rank.

Value:
  * counting (ACU): season = the season-total; career = the sum over seasons.
  * rate (PRO): season = the stored rate, gated by the qualifier cascade; career = a recompute from
    summed components where the formula is known (`career_rate.has_exact`), else a playing-time
    weighted average of the per-season values (`career_rate`).
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from django.db import models, transaction

from dglweb.stats import career_rate, qualifier
from dglweb.stats.models import (
    Batting,
    Fielding,
    Leader,
    Metric,
    Pitching,
    QualifierDefault,
    QualifierSeasonOverride,
)

FIRST_SEASON = 1956  # leaders exclude the Negro Leagues (pre-1956)
_MODEL: dict[str, type[models.Model]] = {"batting": Batting, "pitching": Pitching, "fielding": Fielding}

# (board value, metric flag attribute, is-best, scope)
_BOARDS: list[tuple[str, str, bool, str]] = [
    (Leader.Board.BEST_SEASON, "best_season", True, "season"),
    (Leader.Board.WORST_SEASON, "worst_season", False, "season"),
    (Leader.Board.BEST_CAREER, "best_career", True, "career"),
    (Leader.Board.WORST_CAREER, "worst_career", False, "career"),
]
_BATCH = 2000


def _dense_rank(pairs: Sequence[tuple[int, float]], descending: bool) -> list[tuple[int, float, int]]:
    """(player_id, value) -> (player_id, value, dense_rank). Ties share a rank; the next is +1."""
    ranked: list[tuple[int, float, int]] = []
    rank = 0
    previous: float | None = None
    for player_id, value in sorted(pairs, key=lambda pair: pair[1], reverse=descending):
        if value != previous:
            rank += 1
            previous = value
        ranked.append((player_id, value, rank))
    return ranked


def _positions() -> list[str]:
    # A plain `.distinct()` would be broken by Fielding's Meta.ordering (the ORDER BY columns leak
    # into the SELECT), so dedupe in Python. DH is not a fielding position.
    positions = Fielding.objects.filter(season__gte=FIRST_SEASON).values_list("pos", flat=True)
    return sorted({p for p in positions if p and p != "DH"})


def _totals(metric: Metric, pos: str | None) -> list[dict[str, Any]]:
    """Season-total rows for the metric (Dominican tables, 1956+), with the value and qualifier cols."""
    model = _MODEL[metric.stat_group]
    base = model._default_manager.filter(season__gte=FIRST_SEASON)
    if metric.stat_group == "fielding":
        rows = base.position_totals().filter(pos=pos)  # type: ignore[attr-defined]
        qualifier_col = "gp"
    else:
        rows = base.season_totals()  # type: ignore[attr-defined]
        qualifier_col = "outs" if metric.stat_group == "pitching" else "pa"
    columns = list(dict.fromkeys(["player_id", "season", metric.column, qualifier_col]))
    return list(rows.values(*columns))


def _descending(metric: Metric, is_best: bool) -> bool:
    higher_is_better = metric.direction == Metric.Direction.HIGHER
    return higher_is_better if is_best else not higher_is_better


def _season_leaders(
    metric: Metric,
    board: str,
    pos: str | None,
    rows: Iterable[dict[str, Any]],
    descending: bool,
    defaults: qualifier.Defaults,
    overrides: qualifier.Overrides,
) -> list[Leader]:
    by_season: dict[int, list[tuple[int, float]]] = {}
    for row in rows:
        value = row[metric.column]
        if value is None or (metric.exclude_zeros and value == 0):
            continue
        if metric.kind == Metric.Kind.RATE:
            formula = qualifier.resolve_season(metric, row["season"], defaults, overrides)
            if not qualifier.qualifies(formula, metric.stat_group, row):
                continue
        by_season.setdefault(row["season"], []).append((row["player_id"], float(value)))

    leaders: list[Leader] = []
    for season, pairs in by_season.items():
        for player_id, value, rank in _dense_rank(pairs, descending):
            leaders.append(
                Leader(
                    metric=metric,
                    board=board,
                    season=season,
                    fielding_pos=pos,
                    player_id=player_id,
                    value=value,
                    rank=rank,
                )
            )
    return leaders


def _career_leaders(
    metric: Metric, board: str, pos: str | None, rows: Iterable[dict[str, Any]], descending: bool
) -> list[Leader]:
    totals: dict[int, float] = {}
    for row in rows:
        value = row[metric.column]
        if value is None:
            continue
        totals[row["player_id"]] = totals.get(row["player_id"], 0.0) + float(value)
    pairs = [(pid, v) for pid, v in totals.items() if not (metric.exclude_zeros and v == 0)]

    return [
        Leader(metric=metric, board=board, season=None, fielding_pos=pos, player_id=pid, value=value, rank=rank)
        for pid, value, rank in _dense_rank(pairs, descending)
    ]


def _career_sums(group: str, pos: str | None) -> dict[int, dict[str, Any]]:
    """Per player, the career sum of the group's counting components (None where never recorded)."""
    components = career_rate.COMPONENTS[group]
    base = _MODEL[group]._default_manager.filter(season__gte=FIRST_SEASON)
    rows = base.position_totals().filter(pos=pos) if group == "fielding" else base.season_totals()  # type: ignore[attr-defined]
    sums: dict[int, dict[str, Any]] = {}
    for row in rows.values("player_id", *components):
        player = sums.setdefault(row["player_id"], dict.fromkeys(components))
        for component in components:
            value = row[component]
            if value is not None:
                player[component] = (player[component] or 0) + value
    return sums


def _exact_career_rate_leaders(
    metric: Metric, board: str, pos: str | None, descending: bool, sums: dict[int, dict[str, Any]], formula: str
) -> list[Leader]:
    """Career rate with a known formula: recompute from the summed components."""
    pairs: list[tuple[int, float]] = []
    for player_id, counts in sums.items():
        value = career_rate.exact_value(metric.stat_group, metric.column, counts)
        if value is None or not qualifier.qualifies(formula, metric.stat_group, counts):
            continue
        pairs.append((player_id, value))
    return [
        Leader(metric=metric, board=board, season=None, fielding_pos=pos, player_id=pid, value=value, rank=rank)
        for pid, value, rank in _dense_rank(pairs, descending)
    ]


def _prorated_career_rate_leaders(
    metric: Metric, board: str, pos: str | None, descending: bool, rows: Iterable[dict[str, Any]], formula: str
) -> list[Leader]:
    """Career rate with no known formula: a playing-time-weighted average of the per-season rate."""
    group = metric.stat_group
    weight_col = career_rate.WEIGHT[group]
    weighted: dict[int, list[float]] = {}  # player -> [sum(rate*weight), sum(weight)]
    for row in rows:
        rate, weight = row[metric.column], row[weight_col]
        if rate is None or not weight:
            continue
        accumulator = weighted.setdefault(row["player_id"], [0.0, 0.0])
        accumulator[0] += rate * weight
        accumulator[1] += weight

    pairs: list[tuple[int, float]] = []
    for player_id, (weighted_sum, total_weight) in weighted.items():
        if total_weight == 0 or not qualifier.qualifies(formula, group, {weight_col: total_weight}):
            continue
        pairs.append((player_id, weighted_sum / total_weight))
    return [
        Leader(metric=metric, board=board, season=None, fielding_pos=pos, player_id=pid, value=value, rank=rank)
        for pid, value, rank in _dense_rank(pairs, descending)
    ]


def build_leaders(note: Callable[[str], None] = lambda _: None) -> dict[str, int]:
    """Rebuild `dgl_leader` from scratch. Returns {written, prorated_rate_career}."""
    defaults: qualifier.Defaults = {
        d.stat_group: (d.qualifier_season, d.qualifier_career) for d in QualifierDefault.objects.all()
    }
    overrides: qualifier.Overrides = {
        (o.stat_group, o.season): o.qualifier_season for o in QualifierSeasonOverride.objects.all()
    }

    sums_cache: dict[tuple[str, str | None], dict[int, dict[str, Any]]] = {}  # career sums, per (group, pos)
    written = prorated = 0
    with transaction.atomic():
        Leader.objects.all().delete()
        buffer: list[Leader] = []
        for metric in Metric.objects.filter(is_active=True):
            positions: Sequence[str | None] = _positions() if metric.stat_group == "fielding" else [None]
            for pos in positions:
                rows = _totals(metric, pos)
                for board, flag, is_best, scope in _BOARDS:
                    if not getattr(metric, flag):
                        continue
                    descending = _descending(metric, is_best)
                    if metric.kind == Metric.Kind.RATE and scope == "career":
                        formula = qualifier.resolve_career(metric, defaults)
                        if career_rate.has_exact(metric.stat_group, metric.column):
                            key = (metric.stat_group, pos)
                            if key not in sums_cache:
                                sums_cache[key] = _career_sums(metric.stat_group, pos)
                            buffer += _exact_career_rate_leaders(
                                metric, board, pos, descending, sums_cache[key], formula
                            )
                        else:
                            buffer += _prorated_career_rate_leaders(metric, board, pos, descending, rows, formula)
                            prorated += 1
                    elif scope == "season":
                        buffer += _season_leaders(metric, board, pos, rows, descending, defaults, overrides)
                    else:
                        buffer += _career_leaders(metric, board, pos, rows, descending)
                    if len(buffer) >= _BATCH:
                        Leader.objects.bulk_create(buffer)
                        written += len(buffer)
                        buffer = []
        if buffer:
            Leader.objects.bulk_create(buffer)
            written += len(buffer)

    note(f"{written} filas escritas; {prorated} tableros de tasa-carrera prorrateados.")
    return {"written": written, "prorated_rate_career": prorated}
