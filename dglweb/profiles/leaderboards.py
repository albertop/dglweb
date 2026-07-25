"""The public leaders pages (`/lideres/`): boards re-ranked for the Dominican subset from `dgl_leader`.

Unlike the per-player overlay, this is the global view: pick a metric and see who leads. It reuses the
player page's visual language and the Puestos division layout, so a metric sits under the same
division (Estándar/Avanzado/Sabermetría/Coeficientes) in both. MVP: Bateo and Pitcheo, regular season,
De por vida (career) and Por temporada (a chosen season). Postemporada and Fildeo (per position) come
next — the board queries already carry the `postseason`/`fielding_pos` dimensions for that.
"""

from itertools import groupby
from typing import Any
from urllib.parse import urlencode

from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from dglweb.profiles import columns
from dglweb.profiles.tabs import _DESCRIPTIVE_COLUMNS, _pretty_qualifier, _puestos_layout, _qualifier_context
from dglweb.stats import qualifier
from dglweb.stats.models import Batting, Fielding, Leader, Metric, Pitching

_GROUPS: list[tuple[str, str]] = [("batting", "Bateo"), ("pitching", "Pitcheo")]
_SCOPES: list[tuple[str, str]] = [("carrera", "De por vida"), ("temporada", "Por temporada")]
# Hasta qué PUESTO llega cada tablero (no cuántas filas): un empate en el último puesto entra
# completo, así que un top-25 con tres jugadores empatados en el 25 muestra 27 filas. De por vida da
# para 25 (es el registro histórico); una temporada suelta se corta en 10.
_TOP_RANK: dict[str, int] = {"carrera": 25, "temporada": 10}
# A partir de cuántas filas el tablero se parte en dos columnas paralelas. Por debajo de esto, dos
# columnas quedarían ridículamente cortas y se ve mejor una sola.
_SPLIT_FROM = 12
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


def _latest_season() -> int | None:
    """The most recent season anywhere in our tables — the yardstick for "still active"."""
    seasons = [model.objects.aggregate(m=Max("season"))["m"] for model in (Batting, Pitching, Fielding)]
    return max((s for s in seasons if s is not None), default=None)


def _active_players(player_ids: list[int], latest: int | None) -> set[int]:
    """Of `player_ids`, those with a batting, pitching or fielding line in the latest season — active."""
    if not player_ids or latest is None:
        return set()
    active: set[int] = set()
    for model in (Batting, Pitching, Fielding):
        active |= set(model.objects.filter(season=latest, player_id__in=player_ids).values_list("player_id", flat=True))
    return active


def _split_in_columns(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Parte el tablero en dos columnas paralelas para que no quede una lista larga y estrecha.

    El corte NO puede caer dentro de un empate: las filas repetidas de un empate van sin puesto ni
    valor (los escribe la primera), así que abrir una columna con una de ellas dejaría un nombre
    suelto sin número. Por eso el corte se corre hasta la próxima fila que abre puesto (`leads`).
    """
    if len(rows) < _SPLIT_FROM:
        return [rows]
    cut = (len(rows) + 1) // 2
    while cut < len(rows) and not rows[cut]["leads"]:
        cut += 1
    if cut >= len(rows):  # un empate gigante al final: mejor una sola columna que una vacía
        return [rows]
    return [rows[:cut], rows[cut:]]


def _board_rows(metric: Metric, scope: str, season: int | None) -> list[dict[str, Any]]:
    board = Leader.objects.filter(metric=metric, board=_board_flag(scope), postseason=False, fielding_pos=None)
    if scope == "temporada" and season is not None:
        board = board.filter(season=season)
    board = board.filter(rank__lte=_TOP_RANK[scope])
    leaders = list(board.order_by("rank", "player__full_name").select_related("player"))
    latest = _latest_season()
    # En el board de la ÚLTIMA temporada, todo el que aparece jugó ese año por definición: pintar
    # todas las filas de verde no distingue a nadie. Ahí no se marca a nadie como activo.
    every_row_is_active = scope == "temporada" and season is not None and season == latest
    active = set() if every_row_is_active else _active_players([row.player_id for row in leaders], latest)
    # Una fila por jugador, pero en un empate el puesto y el valor se escriben UNA sola vez: solo la
    # primera fila del grupo los lleva (`leads`), las demás dejan esas celdas vacías. `leaders` ya
    # viene ordenado por rank, que es lo que groupby necesita.
    rows: list[dict[str, Any]] = []
    for _, group in groupby(leaders, key=lambda row: row.rank):
        tied = list(group)
        for position, row in enumerate(tied):
            rows.append(
                {
                    "rank": row.rank,
                    "tie": len(tied) > 1,
                    "leads": position == 0,  # ¿abre el empate (escribe puesto y valor) o lo repite?
                    "name": row.player.full_name,
                    "slug": row.player.slug,
                    "active": row.player_id in active,  # jugó la última temporada registrada
                    "value": _format(metric.stat_group, metric.column, row.value),
                }
            )
    return rows


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
    rows = _board_rows(metric, scope, chosen_season)

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
            {
                "name": m.name_es or m.abbrev,
                "abbr": m.abbrev,
                "active": m.column == metric.column,
                "url": _link(state, m=m.column),
            }
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
            "available_from": metric.available_from,  # "disponible desde YYYY" cuando aplica (Statcast)
            "scope_label": f"temporada {chosen_season}" if scope == "temporada" else "de por vida",
            "rows": rows,
            "columns": _split_in_columns(rows),  # una o dos columnas paralelas, según el largo
            # La leyenda del verde solo tiene sentido si alguna fila está marcada (no la hay en el
            # board de la última temporada, ni en uno viejo donde ya todos se retiraron).
            "shows_active": any(row["active"] for row in rows),
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
