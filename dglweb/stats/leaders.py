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

from django.db import connection, models, transaction

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

# Product decision, not a bug: leaderboards start in 1956 and EXCLUDE the Negro Leagues. Those
# players ARE shown on their player pages (with a coverage note), but they do not participate in
# comparative leaders — the Negro Leagues' partial coverage would make historical rankings unfair.
# Do not "fix" this to 1920 without revisiting that decision. See docs/FASE4_PLAN.md.
FIRST_SEASON = 1956
_MODEL: dict[str, type[models.Model]] = {"batting": Batting, "pitching": Pitching, "fielding": Fielding}

# (board value, metric flag attribute, is-best, scope)
_BOARDS: list[tuple[str, str, bool, str]] = [
    (Leader.Board.BEST_SEASON, "best_season", True, "season"),
    (Leader.Board.WORST_SEASON, "worst_season", False, "season"),
    (Leader.Board.BEST_CAREER, "best_career", True, "career"),
    (Leader.Board.WORST_CAREER, "worst_career", False, "career"),
]
_BATCH = 2000
_LOCK_KEY = 8412025  # arbitrary but stable key for the build_leaders advisory lock
# Columns stored as outs but ranked/displayed as innings: the value is outs/3 (IP = outs/3).
_INNINGS_COLUMNS = frozenset({"outs", "innings_outs"})


def _precision(metric: Metric) -> int:
    """Decimals to round a rate to — from its display format (`#.000` -> 3), default 3."""
    fmt = metric.fmt or ""
    return len(fmt.rsplit(".", 1)[-1]) if "." in fmt else 3


def _leader_value(metric: Metric, raw: float) -> float:
    """The published value: innings (not raw outs) for innings metrics; rates rounded to their
    displayed precision so two players who show `.300` tie instead of splitting on a 1e-15 float diff.
    """
    if metric.column in _INNINGS_COLUMNS:
        return raw / 3
    if metric.kind == Metric.Kind.RATE:
        return round(raw, _precision(metric))
    return raw


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


def _first_season(metric: Metric) -> int:
    """The metric's own floor. `available_from` marks the first season the column has real data —
    the Statcast counts and coefficients start in 1989 (see `derive.FIRST_STATCAST_SEASON`), and
    ranking earlier seasons would publish boards built on a numerator that was never recorded."""
    return max(FIRST_SEASON, metric.available_from or 0)


def _totals(metric: Metric, pos: str | None) -> list[dict[str, Any]]:
    """Season-total rows for the metric (Dominican tables, 1956+), with the value and qualifier cols."""
    model = _MODEL[metric.stat_group]
    base = model._default_manager.filter(season__gte=_first_season(metric))
    if metric.stat_group == "fielding":
        rows = base.position_totals().filter(pos=pos)  # type: ignore[attr-defined]
        qualifier_col = "gp"
    else:
        rows = base.season_totals()  # type: ignore[attr-defined]
        qualifier_col = "outs" if metric.stat_group == "pitching" else "pa"
    # A metric may gate on a column other than the group's own (the coefficients use BALLS_IN_PLAY).
    # It has to be selected here or `qualifies` reads None and fails closed, emptying the board.
    own = [
        qualifier.field_column(metric.stat_group, formula)
        for formula in (metric.qualifier_season, metric.qualifier_career)
    ]
    columns = list(dict.fromkeys(["player_id", "season", metric.column, qualifier_col, *filter(None, own)]))
    return list(rows.values(*columns))


def _descending(metric: Metric, is_best: bool) -> bool:
    higher_is_better = metric.direction == Metric.Direction.HIGHER
    return higher_is_better if is_best else not higher_is_better


def _needs_qualifier(metric: Metric) -> bool:
    """Whether a threshold must gate this metric's board.

    A rate is distorted by a small sample in either direction. And so is the MINIMUM of a count:
    "fewest walks" without a threshold crowns whoever pitched one inning — the board for BB used to
    open with a position player who threw 1.0 IP and walked nobody. A count ranked "most first"
    needs nothing: you cannot accumulate a league-leading total in a cup of coffee.
    """
    return metric.kind == Metric.Kind.RATE or metric.direction == Metric.Direction.LOWER


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
        if _needs_qualifier(metric):
            formula = qualifier.resolve_season(metric, row["season"], defaults, overrides)
            if not qualifier.qualifies(formula, metric.stat_group, row):
                continue
        by_season.setdefault(row["season"], []).append((row["player_id"], _leader_value(metric, float(value))))

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
    metric: Metric,
    board: str,
    pos: str | None,
    rows: Iterable[dict[str, Any]],
    descending: bool,
    defaults: qualifier.Defaults,
) -> list[Leader]:
    totals: dict[int, float] = {}
    played: dict[int, dict[str, float]] = {}  # career sums of whatever the qualifier reads
    formula = qualifier.resolve_career(metric, defaults) if _needs_qualifier(metric) else ""
    threshold_column = qualifier.field_column(metric.stat_group, formula) if formula else None
    for row in rows:
        value = row[metric.column]
        if value is None:
            continue
        totals[row["player_id"]] = totals.get(row["player_id"], 0.0) + float(value)
        if threshold_column is not None:
            carried = row.get(threshold_column) or 0
            bucket = played.setdefault(row["player_id"], {threshold_column: 0.0})
            bucket[threshold_column] += float(carried)
    pairs = [
        (pid, _leader_value(metric, v))
        for pid, v in totals.items()
        if not (metric.exclude_zeros and v == 0)
        # A career minimum needs the same gate as a season one, or "fewest career walks" is won by
        # whoever threw a single inning.
        and (not formula or qualifier.qualifies(formula, metric.stat_group, played.get(pid, {})))
    ]

    return [
        Leader(metric=metric, board=board, season=None, fielding_pos=pos, player_id=pid, value=value, rank=rank)
        for pid, value, rank in _dense_rank(pairs, descending)
    ]


def _career_sums(group: str, pos: str | None, first_season: int = FIRST_SEASON) -> dict[int, dict[str, Any]]:
    """Per player, the career sum of the group's counting components (None where never recorded).

    `first_season` is the metric's floor: a career coefficient must sum only the seasons whose data
    exists, or a player spanning 1985-1995 would average a decade that was never classified.
    """
    components = career_rate.COMPONENTS[group]
    base = _MODEL[group]._default_manager.filter(season__gte=first_season)
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
        pairs.append((player_id, _leader_value(metric, value)))
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
        pairs.append((player_id, _leader_value(metric, weighted_sum / total_weight)))
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

    sums_cache: dict[tuple[str, str | None, int], dict[int, dict[str, Any]]] = {}  # per (group, pos, floor)
    written = prorated = 0
    with transaction.atomic():
        # A transaction-scoped advisory lock: a second concurrent build_leaders blocks here until the
        # first commits, instead of interleaving delete+insert and duplicating rows.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK_KEY])
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
                            # The floor is part of the key: metrics with different floors must not
                            # share a cached sum.
                            key = (metric.stat_group, pos, _first_season(metric))
                            if key not in sums_cache:
                                sums_cache[key] = _career_sums(metric.stat_group, pos, _first_season(metric))
                            buffer += _exact_career_rate_leaders(
                                metric, board, pos, descending, sums_cache[key], formula
                            )
                        else:
                            buffer += _prorated_career_rate_leaders(metric, board, pos, descending, rows, formula)
                            prorated += 1
                    elif scope == "season":
                        buffer += _season_leaders(metric, board, pos, rows, descending, defaults, overrides)
                    else:
                        buffer += _career_leaders(metric, board, pos, rows, descending, defaults)
                    if len(buffer) >= _BATCH:
                        Leader.objects.bulk_create(buffer)
                        written += len(buffer)
                        buffer = []
        if buffer:
            Leader.objects.bulk_create(buffer)
            written += len(buffer)

    note(f"{written} filas escritas; {prorated} tableros de tasa-carrera prorrateados.")
    return {"written": written, "prorated_rate_career": prorated}
