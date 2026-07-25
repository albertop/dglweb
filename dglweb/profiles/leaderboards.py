"""The public leaders pages (`/lideres/`): boards re-ranked for the Dominican subset from `dgl_leader`.

Unlike the per-player overlay, this is the global view: pick a metric and see who leads. It reuses the
player page's visual language and the Puestos division layout, so a metric sits under the same
division (Estándar/Avanzado/Statcast/Coeficientes) in both. MVP: Bateo and Pitcheo, regular season,
De por vida (career) and Por temporada (a chosen season). Postemporada and Fildeo (per position) come
next — the board queries already carry the `postseason`/`fielding_pos` dimensions for that.
"""

from collections import Counter
from typing import Any
from urllib.parse import urlencode

from django.db.models import Count, Max, Min
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from dglweb.profiles import columns
from dglweb.profiles.tabs import _DESCRIPTIVE_COLUMNS, _pretty_qualifier, _puestos_layout, _qualifier_context
from dglweb.stats import qualifier
from dglweb.stats.models import Batting, Fielding, Leader, Metric, Pitching

_GROUPS: list[tuple[str, str]] = [("batting", "Bateo"), ("pitching", "Pitcheo"), ("fielding", "Fildeo")]
# Las nueve posiciones defensivas, en el orden del scorebook. `Fielding.pos` ya guarda "P" —el SP/RP
# vive en `Player.pos`, que es otra cosa— así que no hay nada que agrupar. El bateador designado no
# está: no defiende, y el motor de líderes ya lo excluye.
_POSITIONS: list[str] = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
# La división de receptor solo tiene sentido en C: passed balls y cERA no existen en las otras ocho.
_CATCHER_DIVISION = "Receptor"
_SCOPES: list[tuple[str, str]] = [("carrera", "De por vida"), ("temporada", "Por temporada")]
# Hasta qué PUESTO llega cada tabla (no cuántas filas): un empate en el último entra completo, así que
# un top-15 con tres empatados en el 15 muestra 17 filas. Vale para las dos puntas de un mismo
# tablero. De por vida da para más (es el registro histórico); una temporada suelta se corta antes.
# Los rótulos ("Primeros 15", "Los 10 más altos") se escriben desde acá, y los tests lo leen en vez
# de repetir el número.
_TOP_RANK: dict[str, int] = {"carrera": 15, "temporada": 10}
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


def _board_flag(scope: str, *, best: bool = True) -> str:
    if scope == "carrera":
        return Leader.Board.BEST_CAREER if best else Leader.Board.WORST_CAREER
    return Leader.Board.BEST_SEASON if best else Leader.Board.WORST_SEASON


def _division_metrics(group: str, scope: str, pos: str | None = None) -> list[tuple[str, list[Metric]]]:
    """The divisions and their metrics for this scope, in table order — only metrics that actually
    feed the board (career or season), and only divisions that end up with at least one.

    Las de receptor no abren un pill propio: se suman al dropdown de Avanzado cuando la posición
    elegida es C, y no existen en las otras ocho — un tablero de passed balls o cERA de un jardinero
    no significaría nada. Así fildeo mantiene los mismos pills que los otros oficios.
    """
    flag = "best_career" if scope == "carrera" else "best_season"
    active = {m.column: m for m in Metric.objects.filter(is_active=True, stat_group=group, **{flag: True})}
    catcher = [cols for label, cols in _puestos_layout(group) if label == _CATCHER_DIVISION]
    extra = catcher[0] if catcher and pos == "C" else []
    divisions: list[tuple[str, list[Metric]]] = []
    for label, cols in _puestos_layout(group):
        if label == _CATCHER_DIVISION:
            continue
        metrics = [active[col] for col in [*cols, *(extra if label == "Avanzado" else [])] if col in active]
        if metrics:
            divisions.append((label, metrics))
    return divisions


def _direction_label(metric: Metric) -> str:
    higher = metric.direction == Metric.Direction.HIGHER
    if metric.column in _DESCRIPTIVE_COLUMNS:  # SAB-02: descriptive stats have no "better", only más alto/bajo
        return "Más alto" if higher else "Más bajo"
    return "Más es mejor" if higher else "Menos es mejor"


def _qualifier_note(metric: Metric, scope: str, *, has_worst: bool) -> str:
    """La frase del pie que explica el umbral. Vacía cuando no hay ninguno.

    Cuál de las dos tablas filtra depende del tipo de métrica, y por eso la frase cambia:
      * Una tasa se distorsiona en muestras chicas por los dos lados, así que el umbral vale para las
        dos tablas.
      * Un conteo solo lo necesita en Últimos: "más jonrones" no se logra en veinte turnos, pero
        "menos jonrones" sin piso lo gana el que apenas jugó. Decirle "mínimo para calificar" a secas
        haría pensar que también recorta a los líderes, y no es así.
    """
    is_rate = metric.kind == Metric.Kind.RATE
    if not is_rate and not has_worst:
        return ""
    defaults, _ = _qualifier_context()
    formula = (
        qualifier.resolve_career(metric, defaults)
        if scope == "carrera"
        else qualifier.resolve_season(metric, 0, defaults, {})
    )
    if not formula:
        return ""
    pretty = _pretty_qualifier(formula)
    if is_rate:
        return f"Mínimo para calificar: {pretty}."
    return f"Mínimo para entrar en Últimos {_TOP_RANK[scope]}: {pretty}."


def _link(state: dict[str, str], **changes: str | None) -> str:
    """A `?g=…&d=…` query string: current state with `changes` applied (a None drops the key)."""
    merged = dict(state)
    for key, value in changes.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    order = ["g", "pos", "d", "scope", "m", "season"]
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


def _career_span(group: str, player_ids: list[int], pos: str | None = None) -> dict[int, tuple[int, int]]:
    """Por jugador: (cuántas temporadas jugó, en cuál debutó), en la tabla del oficio de la métrica.

    Las temporadas se cuentan DISTINTAS, no como la resta entre el último año y el primero: quien se
    perdió tres años por lesión jugó tres menos, y un año repartido entre dos equipos son varias filas
    pero una sola temporada. Es el mismo criterio del `season_count` del perfil, así que el número
    coincide con el que ve el usuario en la página del jugador.

    En fildeo se cuentan las temporadas EN ESA POSICIÓN, no las de su carrera: el tablero es por
    posición, y a un antesalista que pasó tres años en el jardín no se le cuentan esos tres.

    El debut sirve para otra cosa: marcar el total como incompleto cuando la métrica empezó a
    registrarse después de que el jugador ya estaba jugando.

    `order_by()` limpia el orden del modelo: si no, sus columnas se cuelan en el GROUP BY y el conteo
    deja de ser por jugador.
    """
    if not player_ids:
        return {}

    def tally(rows: Any) -> dict[int, tuple[int, int]]:  # noqa: ANN401 — tres querysets de modelos distintos
        grouped = rows.order_by().values("player_id").annotate(n=Count("season", distinct=True), debut=Min("season"))
        return {row["player_id"]: (row["n"], row["debut"]) for row in grouped}

    if group == "fielding":
        return tally(Fielding.objects.filter(player_id__in=player_ids, pos=pos)) if pos else {}
    if group == "batting":
        return tally(Batting.objects.filter(player_id__in=player_ids))
    return tally(Pitching.objects.filter(player_id__in=player_ids))


def _write_rank_once(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Marca qué fila escribe el puesto y el valor: la primera de cada empate, el resto los deja vacíos.

    Se aplica DESPUÉS de descartar a los repetidos entre las dos tablas, no antes: si el que abría un
    empate es justo el que se fue, el puesto tiene que pasar al que quedó o esa fila saldría huérfana.
    """
    shared = Counter(row["rank"] for row in rows)
    seen: set[int] = set()
    for row in rows:
        row["tie"] = shared[row["rank"]] > 1
        row["leads"] = row["rank"] not in seen
        seen.add(row["rank"])
    return rows


def _real_ranks(
    metric: Metric, scope: str, season: int | None, player_ids: list[int], pos: str | None
) -> dict[int, int]:
    """El puesto de cada jugador en el tablero DESCENDENTE — el ranking que muestra la tabla de arriba.

    Lo necesita la tabla de abajo, que sale del tablero ascendente. Los dos tableros no rankean a la
    misma gente: en un conteo el descendente no lleva umbral y el ascendente sí, así que en BB 2023
    son 68 jugadores contra 17. Numerar la tabla de abajo dentro de sus 17 producía un "10" que no era
    el mismo "10" de arriba — Julio Rodríguez y Manny Machado salían los dos de décimos. El puesto que
    se publica es siempre el del mismo ranking, y ahí Rodríguez es el 11, justo detrás de Machado.
    """
    if not player_ids:
        return {}
    board = Leader.objects.filter(
        metric=metric, board=_board_flag(scope), postseason=False, fielding_pos=pos, player_id__in=player_ids
    )
    if scope == "temporada" and season is not None:
        board = board.filter(season=season)
    return dict(board.values_list("player_id", "rank"))


def _board_rows(
    metric: Metric, scope: str, season: int | None, pos: str | None, *, best: bool = True
) -> list[dict[str, Any]]:
    """Un extremo del tablero: los `_TOP_RANK` puestos de una punta.

    `rank` sale acá tal cual lo guarda `dgl_leader`. Para la tabla de abajo eso es su propio puesto 1
    en el extremo —que escrito así se leería como un liderato, "1º en menos jonrones"— y lo reemplaza
    `_best_and_worst` por el puesto real del ranking.
    """
    flag = _board_flag(scope, best=best)
    board = Leader.objects.filter(metric=metric, board=flag, postseason=False, fielding_pos=pos)
    if scope == "temporada" and season is not None:
        board = board.filter(season=season)
    leaders = list(
        board.filter(rank__lte=_TOP_RANK[scope]).order_by("rank", "player__full_name").select_related("player")
    )
    # El verde solo va en los tableros de por vida, que es donde separa a quien sigue jugando de quien
    # ya es historia. En uno de temporada no distingue nada: en la última todos jugaron ese año por
    # definición, y en una reciente casi todos siguen activos, así que se pinta la tabla entera.
    active = _active_players([row.player_id for row in leaders], _latest_season()) if scope == "carrera" else set()
    span = _career_span(metric.stat_group, [row.player_id for row in leaders], pos)
    # Un total de por vida queda TRUNCADO si la métrica se empezó a registrar después de que el
    # jugador ya estaba jugando: los batazos y coeficientes arrancan en 1989, así que a quien debutó
    # en 1985 le faltan cuatro años de cuenta. Solo pasa de por vida — los tableros de temporada ya
    # arrancan en `available_from`, así que ahí cada valor está completo.
    since = metric.available_from if scope == "carrera" else None
    return [
        {
            "rank": row.rank,
            "name": row.player.full_name,
            "slug": row.player.slug,
            "player_id": row.player_id,
            "active": row.player_id in active,  # jugó la última temporada registrada
            "seasons": span.get(row.player_id, (0, 0))[0],
            "partial": bool(since) and span.get(row.player_id, (0, since or 0))[1] < (since or 0),
            "value": _format(metric.stat_group, metric.column, row.value),
        }
        for row in leaders
    ]


def _column_labels(metric: Metric, scope: str) -> tuple[str, str]:
    """Cómo se llaman las dos tablas. El número son PUESTOS, no filas: con empates entran más.

    En una métrica normal son los primeros y los últimos. En una descriptiva no: ahí la segunda tabla
    no es la de los peores sino la del extremo OPUESTO del mismo perfil — un GB% bajo no es un mal
    GB%, es un lanzador de elevados en vez de uno de rodados. Se rotulan por altura, sin juzgar.
    El orden sale de la dirección, no se asume, para que el rótulo siga al tablero si alguien la
    cambia en el Backoffice.
    """
    top = _TOP_RANK[scope]
    if metric.column not in _DESCRIPTIVE_COLUMNS:
        return f"Primeros {top}", f"Últimos {top}"
    alto, bajo = f"Los {top} más altos", f"Los {top} más bajos"
    return (alto, bajo) if metric.direction == Metric.Direction.HIGHER else (bajo, alto)


def _best_and_worst(metric: Metric, scope: str, season: int | None, pos: str | None) -> list[dict[str, Any]]:
    """Las dos tablas paralelas: el tablero descendente a la izquierda y el ascendente a la derecha.

    Cuando hay pocos calificados las dos puntas se solapan y un mismo jugador sale en las dos. Ahí
    manda la primera: el repetido se quita de la segunda. Si con eso la segunda se vacía —o la
    métrica no tiene ese tablero, como G/PA/AB— queda una sola columna.
    """
    best = _write_rank_once(_board_rows(metric, scope, season, pos, best=True))
    honored = {row["player_id"] for row in best}
    tail = [row for row in _board_rows(metric, scope, season, pos, best=False) if row["player_id"] not in honored]
    # La cola se publica con el puesto del ranking de arriba, no con el del tablero ascendente, y se
    # ordena por él: así el extremo queda de último y ningún número significa dos cosas distintas.
    real = _real_ranks(metric, scope, season, [row["player_id"] for row in tail], pos)
    for row in tail:
        row["rank"] = real.get(row["player_id"], row["rank"])
    tail.sort(key=lambda row: (row["rank"], row["name"]))
    worst = _write_rank_once(tail)
    top_label, bottom_label = _column_labels(metric, scope)
    columns = [{"label": top_label, "rows": best}]
    if worst:
        columns.append({"label": bottom_label, "rows": worst})
    return columns


def leaders_context(*, group: str, tab: str, scope: str, metric_col: str, season: str, pos: str = "") -> dict[str, Any]:
    """Everything the leaders page needs, with every selection validated and a sensible fallback."""
    if group not in dict(_GROUPS):
        group = "batting"
    if scope not in dict(_SCOPES):
        scope = "carrera"
    # Fildeo se rankea POR POSICIÓN — un jardinero y un antesalista no compiten por las mismas
    # asistencias— así que siempre hay una elegida. Bateo y pitcheo no la usan: ahí `fielding_pos` es
    # NULL en `dgl_leader` y filtrar por ella vaciaría el tablero.
    chosen_pos = None
    if group == "fielding":
        chosen_pos = pos if pos in _POSITIONS else _POSITIONS[0]

    divisions = _division_metrics(group, scope, chosen_pos)
    division_labels = [label for label, _ in divisions]
    if tab not in division_labels:
        tab = division_labels[0]
    tab_metrics = next(metrics for label, metrics in divisions if label == tab)

    metric = next((m for m in tab_metrics if m.column == metric_col), tab_metrics[0])

    # Seasons this metric was ranked in (some start in 1989), newest first; the picked one is validated.
    season_years: list[int] = []
    if scope == "temporada":
        years = Leader.objects.filter(
            metric=metric, board=Leader.Board.BEST_SEASON, postseason=False, fielding_pos=chosen_pos
        ).values_list("season", flat=True)
        season_years = sorted({year for year in years if year is not None}, reverse=True)
    chosen_season = None
    if season_years:
        chosen_season = int(season) if season.isdigit() and int(season) in season_years else season_years[0]

    state = {
        "g": group,
        "d": tab,
        "scope": scope,
        "m": metric.column,
        "season": str(chosen_season or ""),
        "pos": chosen_pos or "",
    }
    columns = _best_and_worst(metric, scope, chosen_season, chosen_pos)

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
        # Solo fildeo. Cambiar de posición suelta la métrica: las de receptor no existen en las otras
        # ocho, así que quedarse con cERA al pasar de C a SS daría un tablero vacío.
        "positions": [
            {"label": p, "active": p == chosen_pos, "url": _link(state, pos=p, d=None, m=None)}
            for p in (_POSITIONS if group == "fielding" else [])
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
            "qualifier": _qualifier_note(metric, scope, has_worst=len(columns) > 1),
            "available_from": metric.available_from,  # "disponible desde YYYY" cuando aplica (Statcast)
            "scope_label": f"temporada {chosen_season}" if scope == "temporada" else "de por vida",
            "columns": columns,  # Mejores y (si existe y no quedó vacía tras el dedup) Peores
            # La leyenda del verde solo tiene sentido si alguna fila está marcada (no la hay en el
            # board de la última temporada, ni en uno viejo donde ya todos se retiraron).
            "shows_active": any(row["active"] for column in columns for row in column["rows"]),
            "shows_partial": any(row["partial"] for column in columns for row in column["rows"]),
            # La columna Temporadas es una lectura de carrera. En un tablero de temporada todos
            # jugaron ese año y punto: el dato no dice nada del puesto que se está mirando.
            "shows_seasons": scope == "carrera",
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
        pos=request.GET.get("pos", ""),
    )
    return render(request, "profiles/leaders.html", context)
