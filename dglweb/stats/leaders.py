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

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from django.db import connection, models, transaction

from dglweb.stats import career_rate, qualifier
from dglweb.stats.models import (
    Batting,
    BattingPost,
    Fielding,
    Leader,
    Metric,
    Pitching,
    PitchingPost,
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


def _needs_qualifier(metric: Metric, descending: bool) -> bool:
    """Whether a threshold must gate this board.

    A rate is distorted by a small sample in either direction. And so is the MINIMUM of a count:
    "fewest walks" without a threshold crowns whoever pitched one inning — the board for BB used to
    open with a position player who threw 1.0 IP and walked nobody. A count ranked "most first"
    needs nothing: you cannot accumulate a league-leading total in a cup of coffee.

    Which end a board looks at is `descending`, NOT the metric's direction — that distinction is the
    whole point. HR points up, so its *best* board (most, descending) needs no gate, but its *worst*
    board (fewest, ascending) does: unqualified it was 384 players tied at one homer, among them a
    pitcher with 33 plate appearances. Reading `direction` instead of the board left every "fewest"
    board of a +metric ungated, and needlessly gated every "most" board of a -metric.
    """
    return metric.kind == Metric.Kind.RATE or not descending


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
        if _needs_qualifier(metric, descending):
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
    formula = qualifier.resolve_career(metric, defaults) if _needs_qualifier(metric, descending) else ""
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
        # `exclude_zeros` también acá: los otros dos caminos ya lo miraban y este no, así que una tasa
        # marcada para excluirlos igual publicaba sus ceros en el tablero de carrera.
        if value is None or (metric.exclude_zeros and value == 0):
            continue
        if not qualifier.qualifies(formula, metric.stat_group, counts):
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
        value = weighted_sum / total_weight
        if metric.exclude_zeros and value == 0:  # ver `_exact_career_rate_leaders`
            continue
        pairs.append((player_id, _leader_value(metric, value)))
    return [
        Leader(metric=metric, board=board, season=None, fielding_pos=pos, player_id=pid, value=value, rank=rank)
        for pid, value, rank in _dense_rank(pairs, descending)
    ]


_POST_MODEL: dict[str, type[models.Model]] = {"batting": BattingPost, "pitching": PitchingPost}


def _wants_postseason(metric: Metric) -> bool:
    """Los conteos marcados para octubre llevan tablero; `_postseason_leaders` decide el umbral.

    Uno que apunta hacia ARRIBA no lo necesita: no se puede liderar en jonrones de octubre sin
    batearlos. Uno que apunta hacia abajo sí, y lo lleva — antes se quedaban afuera porque "menos
    ponches en 2 turnos es ruido", pero el ruido lo quita el piso fijo de octubre, que es justo lo
    que existe para eso: con PA>=50 de por vida, "menos ponches" pasa a ser una marca real.

    Las clásicas de tasa tienen su propio camino (`_wants_postseason_rate`). Fildeo no lleva tablero
    de octubre. Los flags `best_season`/`best_career` mandan también acá (review v4 DEV-03): una
    métrica sin ninguno de los dos no quiere tablero.
    """
    return (
        metric.postseason
        and metric.stat_group in _POST_MODEL
        and metric.kind == Metric.Kind.CUMULATIVE
        and (metric.best_season or metric.best_career)
    )


# The only rates that get a postseason board (owner decision): the classic slash line and ERA. Other
# rates (BABIP, ISO, the coefficients…) are left out — noisy on their own and not asked for.
_POST_RATE: dict[str, frozenset[str]] = {
    "batting": frozenset({"avg", "obp", "slg", "ops"}),
    # Las cuatro por-9 y el porcentaje de victorias entran junto a ERA: todas tienen fórmula exacta,
    # así que el valor de octubre se recalcula desde los componentes sumados (H/9 = 27·ΣH/Σouts,
    # PCT = ΣW/(ΣW+ΣL)) y no es un promedio de promedios por ronda. Sin esto se ofrecían en el
    # dropdown de Postemporada con la tabla vacía.
    "pitching": frozenset({"era", "h_per9", "bb_per9", "so_per9", "win_pct"}),
}

# October has no official qualifier: not even a full deep run (max ~89 PA / ~29 IP) reaches a
# regular-season cut. These are FIXED floors, chosen by a statistical study of the real Dominican
# postseason distribution so each board admits ~1/3 of its population — a real field, not a 3-for-4
# wild-card cameo. The full exercise (distributions, why these numbers) is in
# docs/UMBRALES_POSTEMPORADA.md. They deliberately bypass the regular qualifier cascade (502 PA…).
_POST_QUALIFIER: dict[str, tuple[str, str]] = {  # group -> (season floor, career floor)
    "batting": ("PA>=25", "PA>=50"),
    "pitching": ("IP>=8", "IP>=15"),
}


def _wants_postseason_rate(metric: Metric) -> bool:
    """The classic slash-line/ERA rates get a postseason board, gated by the fixed October floor —
    and by `best_season`/`best_career` like every other board (review v4 DEV-03)."""
    return (
        metric.postseason
        and metric.kind == Metric.Kind.RATE
        and metric.column in _POST_RATE.get(metric.stat_group, frozenset())
        and (metric.best_season or metric.best_career)
    )


def _postseason_leaders(metric: Metric) -> list[Leader]:
    """Leaders of a count over the postseason, aggregating each player's whole October: per (player,
    season) for the season board, per player for the career board. Never per round.

    Un conteo que apunta hacia ARRIBA se rankea sin umbral: no se puede liderar en jonrones de
    octubre sin batearlos. Uno que apunta hacia abajo sí lo necesita, y es el mismo piso fijo que usan
    las tasas — "menos ponches" sin él lo gana quien tuvo dos turnos, pero con PA>=50 de por vida
    pasa a ser una marca real. Es la misma regla que la serie regular: el umbral lo pide el extremo
    que mira el tablero, no la dirección de la métrica.
    """
    model = _POST_MODEL[metric.stat_group]
    descending = _descending(metric, is_best=True)
    floor_column = qualifier.field_column(metric.stat_group, _POST_QUALIFIER[metric.stat_group][0]) or ""
    fields = {f.name for f in model._meta.get_fields()}
    tracks_floor = not descending and floor_column in fields
    columns_ = ["player_id", "season", metric.column, *([floor_column] if tracks_floor else [])]

    by_season: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    by_career: dict[int, float] = defaultdict(float)
    floor_season: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    floor_career: dict[int, float] = defaultdict(float)
    for row in model._default_manager.filter(season__gte=FIRST_SEASON).values(*columns_):
        value = row[metric.column]
        if value is None:
            continue
        by_season[row["season"]][row["player_id"]] += value
        by_career[row["player_id"]] += value
        if tracks_floor:
            carried = row.get(floor_column) or 0
            floor_season[row["season"]][row["player_id"]] += carried
            floor_career[row["player_id"]] += carried

    def board(
        scope: str, season: int | None, totals: dict[int, float], played: dict[int, float], gate: str
    ) -> list[Leader]:
        pairs: list[tuple[int, float]] = []
        for pid, total in totals.items():
            # value > 0: you are not a "postseason leader" in a count you never recorded. Salvo en un
            # tablero de "menos", donde el cero ES la marca (nunca lo poncharon en 50 turnos).
            if total <= 0 and descending:
                continue
            if tracks_floor and not qualifier.qualifies(gate, metric.stat_group, {floor_column: played.get(pid, 0)}):
                continue
            pairs.append((pid, _leader_value(metric, total)))
        return [
            Leader(metric=metric, board=scope, season=season, player_id=pid, value=value, rank=rank, postseason=True)
            for pid, value, rank in _dense_rank(pairs, descending)
        ]

    season_floor, career_floor = _POST_QUALIFIER[metric.stat_group]
    leaders: list[Leader] = (
        board(Leader.Board.BEST_CAREER, None, by_career, floor_career, career_floor) if metric.best_career else []
    )
    if metric.best_season:
        for season, totals in by_season.items():
            leaders += board(Leader.Board.BEST_SEASON, season, totals, floor_season[season], season_floor)
    return leaders


def _postseason_rate_leaders(metric: Metric) -> list[Leader]:
    """Rate leaders over the postseason. The value is RECOMPUTED from the summed components (AVG =
    ΣH/ΣAB, ERA = 27·ΣER/Σouts…), never an average of the per-round rates — aggregating each player's
    whole October per (player, season) and per player, exactly as the counting boards do. Gated by
    the fixed October floor (`_POST_QUALIFIER`), not the regular qualifier cascade."""
    model = _POST_MODEL[metric.stat_group]
    fields = {f.name for f in model._meta.get_fields()}
    components = [c for c in career_rate.COMPONENTS[metric.stat_group] if c in fields]
    season_floor, career_floor = _POST_QUALIFIER[metric.stat_group]
    descending = _descending(metric, is_best=True)  # postseason has only "best" boards (option A)

    by_season: dict[int, dict[int, dict[str, float]]] = defaultdict(dict)
    by_career: dict[int, dict[str, float]] = {}
    for row in model._default_manager.filter(season__gte=FIRST_SEASON).values("player_id", "season", *components):
        season_bucket = by_season[row["season"]].setdefault(row["player_id"], dict.fromkeys(components, 0.0))
        career_bucket = by_career.setdefault(row["player_id"], dict.fromkeys(components, 0.0))
        for component in components:
            value = row[component]
            if value is not None:
                season_bucket[component] += value
                career_bucket[component] += value

    def board(scope: str, season: int | None, sums: dict[int, dict[str, float]], floor: str) -> list[Leader]:
        pairs: list[tuple[int, float]] = []
        for player_id, counts in sums.items():
            value = career_rate.exact_value(metric.stat_group, metric.column, counts)
            if value is None or not qualifier.qualifies(floor, metric.stat_group, counts):
                continue
            pairs.append((player_id, _leader_value(metric, value)))
        return [
            Leader(metric=metric, board=scope, season=season, player_id=pid, value=value, rank=rank, postseason=True)
            for pid, value, rank in _dense_rank(pairs, descending)
        ]

    leaders: list[Leader] = board(Leader.Board.BEST_CAREER, None, by_career, career_floor) if metric.best_career else []
    if metric.best_season:
        for season, sums in by_season.items():
            leaders += board(Leader.Board.BEST_SEASON, season, sums, season_floor)
    return leaders


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
            # Postseason boards are once per metric (no position dimension): counts where more is
            # better (unqualified) and the classic rates (floored). Never both for the same metric.
            if _wants_postseason(metric):
                buffer += _postseason_leaders(metric)
            elif _wants_postseason_rate(metric):
                buffer += _postseason_rate_leaders(metric)
            if len(buffer) >= _BATCH:
                Leader.objects.bulk_create(buffer)
                written += len(buffer)
                buffer = []
        if buffer:
            Leader.objects.bulk_create(buffer)
            written += len(buffer)

    note(f"{written} filas escritas; {prorated} tableros de tasa-carrera prorrateados.")
    return {"written": written, "prorated_rate_career": prorated}
