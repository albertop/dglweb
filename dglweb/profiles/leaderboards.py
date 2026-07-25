"""The public leaders pages (`/lideres/`): boards re-ranked for the Dominican subset from `dgl_leader`.

Unlike the per-player overlay, this is the global view: pick a metric and see who leads. It reuses the
player page's visual language and the Puestos division layout, so a metric sits under the same
division (Estándar/Avanzado/Sabermetría/Coeficientes) in both. MVP: Bateo and Pitcheo, regular season,
De por vida (career) and Por temporada (a chosen season). Postemporada and Fildeo (per position) come
next — the board queries already carry the `postseason`/`fielding_pos` dimensions for that.
"""

from collections import Counter
from typing import Any
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from dglweb.profiles import columns
from dglweb.profiles.tabs import _DESCRIPTIVE_COLUMNS, _pretty_qualifier, _puestos_layout, _qualifier_context
from dglweb.stats import qualifier
from dglweb.stats.models import Leader, Metric

_GROUPS: list[tuple[str, str]] = [("batting", "Bateo"), ("pitching", "Pitcheo")]
_SCOPES: list[tuple[str, str]] = [("carrera", "De por vida"), ("temporada", "Por temporada")]
_TOP_N = 25
# Display format per (group, column), read from the same column lists the profile tables use, so a
# leader value is written exactly like it is on a player page (ERA 2.93, AVG .318, HR 703).
_COLUMN_FMT: dict[tuple[str, str], str] = {}
for _group, _lists in {
    "batting": (columns.BATTING_STANDARD, columns.BATTING_ADVANCED, columns.BATTING_STATCAST, columns.BATTING_RATIOS),
    "pitching": (
        columns.PITCHING_STANDARD,
        columns.PITCHING_ADVANCED,
        columns.PITCHING_STATCAST,
        columns.PITCHING_RATIOS,
    ),
}.items():
    for _list in _lists:
        for _col in _list:
            _COLUMN_FMT.setdefault((_group, _col.attr), _col.fmt)


def _format(group: str, column: str, value: float) -> str:
    """A leader value written like on the player page. IP is stored as innings (outs/3), so its
    baseball notation is rebuilt here instead of running the `innings` filter, which expects outs."""
    fmt = _COLUMN_FMT.get((group, column), "num")
    if fmt == "innings":
        whole = int(value)
        return f"{whole:,}.{round((value - whole) * 3)}"
    if fmt == "num":  # counts come off Leader.value as floats (703.0) — write them as integers
        return columns._FORMATS["num"](round(value))
    return columns._FORMATS[fmt](value)


def _board_flag(scope: str) -> str:
    return Leader.Board.BEST_CAREER if scope == "carrera" else Leader.Board.BEST_SEASON


def _division_metrics(group: str, scope: str) -> list[tuple[str, list[Metric]]]:
    """The divisions and their metrics for this scope, in table order — only metrics that actually
    feed the board (career or season), and only divisions that end up with at least one."""
    flag = "best_career" if scope == "carrera" else "best_season"
    active = {m.column: m for m in Metric.objects.filter(is_active=True, stat_group=group, **{flag: True})}
    divisions: list[tuple[str, list[Metric]]] = []
    for label, cols in _puestos_layout(group):
        metrics = [active[col] for col in cols if col in active]
        if metrics:
            divisions.append((label, metrics))
    return divisions


def _direction_label(metric: Metric) -> str:
    higher = metric.direction == Metric.Direction.HIGHER
    if metric.column in _DESCRIPTIVE_COLUMNS:  # SAB-02: descriptive stats have no "better", only más alto/bajo
        return "Más alto" if higher else "Más bajo"
    return "Más es mejor" if higher else "Menos es mejor"


def _qualifier_note(metric: Metric, scope: str) -> str:
    """The minimum to qualify, for rate boards (counts carry none). Blank when there is no threshold."""
    if metric.kind != Metric.Kind.RATE and metric.direction != Metric.Direction.LOWER:
        return ""
    defaults, _ = _qualifier_context()
    formula = (
        qualifier.resolve_career(metric, defaults)
        if scope == "carrera"
        else qualifier.resolve_season(metric, 0, defaults, {})
    )
    return _pretty_qualifier(formula) if formula else ""


def _link(state: dict[str, str], **changes: str | None) -> str:
    """A `?g=…&d=…` query string: current state with `changes` applied (a None drops the key)."""
    merged = dict(state)
    for key, value in changes.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    order = ["g", "d", "scope", "m", "season"]
    return "?" + urlencode({key: merged[key] for key in order if merged.get(key)})


def _board_rows(metric: Metric, scope: str, season: int | None) -> list[dict[str, Any]]:
    board = Leader.objects.filter(metric=metric, board=_board_flag(scope), postseason=False, fielding_pos=None)
    if scope == "temporada" and season is not None:
        board = board.filter(season=season)
    leaders = list(board.order_by("rank", "player__full_name").select_related("player")[:_TOP_N])
    shared = {rank for rank, count in Counter(row.rank for row in leaders).items() if count > 1}
    return [
        {
            "rank": row.rank,
            "tie": row.rank in shared,
            "name": row.player.full_name,
            "slug": row.player.slug,
            "value": _format(metric.stat_group, metric.column, row.value),
        }
        for row in leaders
    ]


def leaders_context(*, group: str, tab: str, scope: str, metric_col: str, season: str) -> dict[str, Any]:
    """Everything the leaders page needs, with every selection validated and a sensible fallback."""
    if group not in dict(_GROUPS):
        group = "batting"
    if scope not in dict(_SCOPES):
        scope = "carrera"

    divisions = _division_metrics(group, scope)
    division_labels = [label for label, _ in divisions]
    if tab not in division_labels:
        tab = division_labels[0]
    tab_metrics = next(metrics for label, metrics in divisions if label == tab)

    metric = next((m for m in tab_metrics if m.column == metric_col), tab_metrics[0])

    # Seasons this metric was ranked in (some start in 1989), newest first; the picked one is validated.
    season_years: list[int] = []
    if scope == "temporada":
        years = Leader.objects.filter(metric=metric, board=Leader.Board.BEST_SEASON, postseason=False).values_list(
            "season", flat=True
        )
        season_years = sorted({year for year in years if year is not None}, reverse=True)
    chosen_season = None
    if season_years:
        chosen_season = int(season) if season.isdigit() and int(season) in season_years else season_years[0]

    state = {"g": group, "d": tab, "scope": scope, "m": metric.column, "season": str(chosen_season or "")}

    return {
        "groups": [
            {"label": label, "active": key == group, "url": _link(state, g=key, d=None, m=None, season=None)}
            for key, label in _GROUPS
        ],
        "divisions": [
            {"label": label, "active": label == tab, "url": _link(state, d=label, m=None)} for label in division_labels
        ],
        "scopes": [
            {"label": label, "active": key == scope, "url": _link(state, scope=key, m=None)} for key, label in _SCOPES
        ],
        "metrics": [
            {"name": m.name_es or m.abbrev, "active": m.column == metric.column, "url": _link(state, m=m.column)}
            for m in tab_metrics
        ],
        "seasons": [
            {"year": year, "active": year == chosen_season, "url": _link(state, season=str(year))}
            for year in season_years
        ],
        "board": {
            "name": metric.name_es or metric.abbrev,
            "abbr": metric.abbrev,
            "direction": _direction_label(metric),
            "qualifier": _qualifier_note(metric, scope),
            "scope_label": f"temporada {chosen_season}" if scope == "temporada" else "de por vida",
            "rows": _board_rows(metric, scope, chosen_season),
        },
        "group_label": dict(_GROUPS)[group],
        "scope_key": scope,
    }


def leaders_index(request: HttpRequest) -> HttpResponse:
    context = leaders_context(
        group=request.GET.get("g", "batting"),
        tab=request.GET.get("d", ""),
        scope=request.GET.get("scope", "carrera"),
        metric_col=request.GET.get("m", ""),
        season=request.GET.get("season", ""),
    )
    return render(request, "profiles/leaders.html", context)
