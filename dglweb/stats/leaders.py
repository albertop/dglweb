"""The leaders engine: precompute `dgl_leader` from our stat tables for the Dominican subset.

For each active `Metric` and each board its calc flags enable, rank players and write `Leader` rows.
Fielding metrics are broken down **by position** (`fielding_pos`); batting/pitching are not. Only
seasons from 1956 on count (Negro Leagues are excluded from leaderboards). Ties get a dense rank.

Value:
  * counting (ACU): season = the season-total; career = the sum over seasons.
  * rate (PRO): season = the stored rate, gated by the qualifier cascade.
Rate *career* boards (career AVG/ERA — a recompute from summed components) are v2: they are counted
and reported, not written.
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from django.db import models, transaction

from dglweb.stats import qualifier
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


def build_leaders(note: Callable[[str], None] = lambda _: None) -> dict[str, int]:
    """Rebuild `dgl_leader` from scratch. Returns {written, deferred_rate_career}."""
    defaults: qualifier.Defaults = {
        d.stat_group: (d.qualifier_season, d.qualifier_career) for d in QualifierDefault.objects.all()
    }
    overrides: qualifier.Overrides = {
        (o.stat_group, o.season): o.qualifier_season for o in QualifierSeasonOverride.objects.all()
    }

    written = deferred = 0
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
                    if metric.kind == Metric.Kind.RATE and scope == "career":
                        deferred += 1  # career rate = recompute from summed components (v2)
                        continue
                    descending = _descending(metric, is_best)
                    if scope == "season":
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

    note(f"{written} filas escritas; {deferred} tableros de tasa-carrera diferidos (v2).")
    return {"written": written, "deferred_rate_career": deferred}
