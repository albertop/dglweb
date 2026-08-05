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
from dglweb.profiles.metric_layout import (
    DESCRIPTIVE_COLUMNS,
    divisions_for,
    pretty_qualifier,
    qualifier_lookups,
)
from dglweb.stats import qualifier, season_window
from dglweb.stats.leaders import _POST_QUALIFIER
from dglweb.stats.models import Batting, Fielding, Leader, Metric, Pitching

_GROUPS: list[tuple[str, str]] = [("batting", "Bateo"), ("pitching", "Pitcheo"), ("fielding", "Fildeo")]
# Las nueve posiciones defensivas, en el orden del scorebook. `Fielding.pos` ya guarda "P" —el SP/RP
# vive en `Player.pos`, que es otra cosa— así que no hay nada que agrupar. El bateador designado no
# está: no defiende, y el motor de líderes ya lo excluye.
_POSITIONS: list[str] = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
# La división de receptor solo tiene sentido en C: passed balls y cERA no existen en las otras ocho.
_CATCHER_DIVISION = "Receptor"
# Octubre es su propio pill: otro tablero, no otra división de columnas.
_POSTSEASON_DIVISION = "Postemporada"
_SCOPES: list[tuple[str, str]] = [("carrera", "De por vida"), ("temporada", "Por temporada")]
# El valor de `?season=` que pide TODAS las temporadas a la vez en vez de una sola: las mejores
# temporadas individuales de la historia, no las mejores de 2026. Es una palabra y no un año vacío
# porque `season=` sin valor ya significa otra cosa —`_link` borra las claves vacías— y porque en la
# URL se lee solo.
TODAS = "todas"

# LAS TEMPORADAS RECORTADAS, QUE NO ENTRAN EN «Todas» (dueño, 2026-08-04). No se borran del sitio:
# las tres siguen siendo opciones del desplegable y su tablero se lee entero. Lo que no se puede es
# MEZCLARLAS con las demás.
#
# Los juegos que llegó a jugar un equipo, contra los 162 de una temporada normal:
#
#     1981   111   la huelga de mitad de temporada
#     1994   117   la huelga que se llevó la Serie Mundial
#     2020    60   la pandemia
#
# El problema es que la cascada de umbrales ESCALA el mínimo a los juegos disputados, que dentro de
# su propia temporada es lo correcto y entre temporadas es un disparate. En 2020 el mínimo bajó a
# 186 turnos donde una temporada normal pide 502, y así los Últimos de carreras empujadas de todos
# los tiempos tenían SEIS de sus ocho primeras filas en 2020 —con 189, 195 y 206 turnos—, y en
# jonrones encabezaba Raimel Tapia con 1 en 206. 1981 colaba a Rafael Ramírez con 342 turnos y a
# Alfredo Griffin con 414; 1994, a Félix Fermín con 411.
#
# Tampoco es solo el extremo malo: el .351 de Juan Soto en 196 turnos aparecía entre los mejores
# promedios de la historia, al lado del .366 de Rico Carty en 560. Por eso la temporada se descarta
# ENTERA y no solo de una punta.
#
# 1995 NO ESTÁ, y se miró: son 145 juegos de 162, que mueve el umbral de 502 a unos 449. Es un
# recorte de otro orden — no cambia quién califica de verdad.
#
# NO ES LA MISMA LISTA QUE LA DE `seed_qualifier_overrides`, y conviene no confundirlas. Aquella
# cubre OCHO temporadas cortas —1956-1960 además de estas tres— porque su trabajo es escalar el
# umbral, y para eso hasta un recorte pequeño cuenta. Esta es más corta a propósito: escalar el
# umbral es correcto siempre, y MEZCLAR años solo se rompe cuando el recorte es brutal.
_FUERA_DE_TODAS: frozenset[int] = frozenset({1981, 1994, 2020})

# LAS QUE NO LLEVAN TABLA DE «Últimos» EN «Todas» (dueño, 2026-08-04), por `(oficio, columna)`.
#
# Son conteos donde UNO es un número perfectamente normal en una temporada completa y calificada, y
# juntando setenta años el primer puesto se llena. Medido antes de esta lista:
#
#     3B    610 filas — 143 empatadas en 1        CS    556 filas —  83 empatadas
#     HBP   634 filas —  88 empatadas             IBB   545 filas — 107 empatadas
#     SB    368 filas —  54 empatadas             SH    333 filas —  77 empatadas
#     SF    261 filas —  50 empatadas             HR    203 filas —  20 empatadas
#
# El problema no es solo que «el que menos triples pegó» no sea una marca: es que el corte va HASTA
# EL PUESTO y un empate entra completo, así que 143 empatados en el primero arrastran la tabla
# entera. Seiscientas filas debajo de un tablero de diez.
#
# EN PITCHEO PASA LO MISMO CON TRES (dueño, 2026-08-04), y por el mismo motivo:
#
#     IBB   157 filas — 37 empatadas en 1        WP    167 filas — 10 empatadas
#     HBP   153 filas —  9 empatadas
#
# LA LISTA ES POR `(oficio, columna)` Y NO POR COLUMNA SUELTA, y `hr` es justo el caso que lo
# explica: existe en los dos oficios y solo se descarta en uno. En un lanzador el jonrón es algo que
# RECIBE, así que la métrica va al revés y su tabla de Últimos no es «menos» sino MÁS jonrones
# permitidos —48, 40, 39— que es una lista corta y con sentido. `ibb` y `hbp`, en cambio, se
# descartan en los dos: los reparte el lanzador, pero uno solo en toda una temporada es igual de
# corriente lo mires desde donde lo mires.
#
# Y no toca la temporada suelta: en 1998 los menos triples SON el dato de 1998, y son diez filas.
_SIN_ULTIMOS_EN_TODAS: frozenset[tuple[str, str]] = frozenset(
    {
        ("batting", "x3b"),  # Triples
        ("batting", "hr"),  # Jonrones
        ("batting", "sb"),  # Bases robadas
        ("batting", "cs"),  # Atrapados robando
        ("batting", "ibb"),  # Bases por bolas intencionales
        ("batting", "hbp"),  # Golpeado por lanzamiento
        ("batting", "sh"),  # Toques de sacrificio
        ("batting", "sf"),  # Elevados de sacrificio
        ("pitching", "ibb"),  # Boletos intencionales
        ("pitching", "hbp"),  # Golpeados
        ("pitching", "wp"),  # Lanzamientos descontrolados
    }
)
# Hasta qué PUESTO llega cada tabla (no cuántas filas): un empate en el último entra completo, así que
# un top-15 con tres empatados en el 15 muestra 17 filas. Vale para las dos puntas de un mismo
# tablero. De por vida da para más (es el registro histórico); una temporada suelta se corta antes.
# Los rótulos ("Primeros 15", "Los 10 más altos") se escriben desde acá, y los tests lo leen en vez
# de repetir el número.
_TOP_RANK: dict[str, int] = {"carrera": 15, "temporada": 10}
# Octubre se corta antes en las dos puntas: una postemporada entera son unos pocos juegos, así
# que el tablero es corto y quince puestos ya raspan el fondo de su propia población.
_POST_TOP_RANK = 10


def _top_rank(scope: str, october: bool) -> int:
    return _POST_TOP_RANK if october else _TOP_RANK[scope]


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
    # Fildeo faltaba: sin formato registrado `_format` cae al default "num", que redondea a entero, y
    # un fildeo de .980 se publicaba como "1" (lo mismo RF/G, RF/9, UZR, CS% y cERA).
    "fielding": (columns.FIELDING_STANDARD, columns.FIELDING_ADVANCED, columns.FIELDING_CATCHER),
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
    # Un dropdown no puede ofrecer una métrica sin tablero. El flag `postseason` dice qué QUIERE
    # tablero de octubre, no qué lo tiene: el motor omite a propósito los conteos que apuntan hacia
    # abajo (un "menos ponches" en octubre lo gana quien tuvo dos turnos) y solo acepta unas pocas
    # tasas, así que ocho métricas se ofrecían con la tabla vacía. Vale también para fildeo, donde una
    # métrica puede tener filas en una posición y no en otra.
    # `order_by()` NO es decorativo: sin él el Meta.ordering del modelo se cuela en el SELECT, el
    # DISTINCT pasa a operar sobre seis columnas —dos de ellas de `dgl_metric`, que entra por JOIN— y
    # la consulta salta de milisegundos a casi cuatro segundos sobre 400k filas. Mismo tropiezo que
    # documenta `_positions()` en el motor.
    # `rank=1` no es un filtro más: es lo que hace barata la pregunta. "Tiene tablero" equivale a
    # "tiene un puesto 1", así que en vez de recorrer las 400k filas para deduplicar metric_id, se
    # miran solo las cabezas de tablero — de un scan secuencial de 300k filas a unos pocos miles.
    ranked = {
        post: set(
            Leader.objects.filter(metric__in=active.values(), postseason=post, fielding_pos=pos, rank=1)
            .order_by()
            .values_list("metric_id", flat=True)
            .distinct()
        )
        for post in (False, True)
    }
    layout = divisions_for(group)
    catcher = [cols for label, cols in layout if label == _CATCHER_DIVISION]
    extra = catcher[0] if catcher and pos == "C" else []
    divisions: list[tuple[str, list[Metric]]] = []
    for label, cols in layout:
        if label == _CATCHER_DIVISION:
            continue
        wanted = [*cols, *(extra if label == "Avanzado" else [])]
        metrics = [active[col] for col in wanted if col in active and active[col].pk in ranked[False]]
        if metrics:
            divisions.append((label, metrics))
    # Octubre es su propio pill, como en el perfil. No es una división de columnas sino otro tablero:
    # solo las métricas marcadas para postemporada, en el mismo orden de las tablas. Fildeo no tiene
    # (las muestras de octubre por posición son muy pequeñas), así que ahí el pill no aparece.
    in_order = [col for _, cols in layout for col in cols]
    october = [active[col] for col in in_order if col in active and active[col].pk in ranked[True]]
    if october:
        divisions.append((_POSTSEASON_DIVISION, october))
    return divisions


def _direction_label(metric: Metric) -> str:
    higher = metric.direction == Metric.Direction.HIGHER
    if metric.column in DESCRIPTIVE_COLUMNS:  # SAB-02: descriptive stats have no "better", only más alto/bajo
        return "Más alto" if higher else "Más bajo"
    return "Más es mejor" if higher else "Menos es mejor"


def _juegos_de_la_temporada(season: int) -> int | None:
    """El calendario más largo de esa temporada, para explicar el umbral en el pie.

    Es el MÁXIMO de todos los equipos, no el de uno: el pie de la tabla habla del tablero entero y no
    de un jugador, y cada uno se midió contra los juegos de SU equipo. Poner el máximo dice de dónde
    sale el orden de magnitud sin fingir una precisión que la frase no puede tener.
    """
    from dglweb.stats.models import TeamSeasonGames

    maximo: int | None = TeamSeasonGames.objects.filter(season=season).aggregate(mx=Max("games"))["mx"]
    return maximo


def _excluded_note(*, todas: bool) -> str:
    """Qué temporadas se dejaron fuera de «Todas», y por qué. Vacía cuando no se dejó ninguna.

    Se dice en la página. Una tabla que descarta una temporada entera sin avisar deja a quien la lee
    buscando por qué no aparece la suya, y de paso oculta la única razón por la que el tablero es
    comparable.

    Normalmente esta frase va PEGADA a la del umbral, que es donde el dueño la pidió: «cada temporada
    se midió contra su propio mínimo» a secas se lee como que están todas. Sale sola cuando esa otra
    no existe — una métrica sin umbral y sin tablero de Últimos la deja vacía, y entonces el aviso
    se quedaría sin sitio. Lo decide `leaders_context`.
    """
    if not todas or not _FUERA_DE_TODAS:
        return ""
    orden = sorted(_FUERA_DE_TODAS)
    # «1981, 1994 y 2020», con la «y» final, que es como se escribe una lista en español.
    anios = str(orden[0]) if len(orden) == 1 else ", ".join(str(a) for a in orden[:-1]) + f" y {orden[-1]}"
    verbo = "no está considerada" if len(orden) == 1 else "no están consideradas"
    return f"{anios} {verbo}: son temporadas recortadas y no se comparan con una completa."


def _scope_label(scope: str, season: int | None, *, todas: bool) -> str:
    """Cómo se llama lo que se está mirando, para el encabezado del tablero."""
    if scope == "carrera":
        return "de por vida"
    return "todas las temporadas" if todas else f"temporada {season}"


def _qualifier_note(
    metric: Metric,
    scope: str,
    *,
    has_worst: bool,
    october: bool = False,
    season: int | None = None,
    todas: bool = False,
) -> str:
    """La frase del pie que explica el umbral. Vacía cuando no hay ninguno.

    Cuál de las dos tablas filtra depende del tipo de métrica, y por eso la frase cambia:
      * Una tasa se distorsiona en muestras chicas por los dos lados, así que el umbral vale para las
        dos tablas.
      * Un conteo solo lo necesita en Últimos: "más jonrones" no se logra en veinte turnos, pero
        "menos jonrones" sin piso lo gana el que apenas jugó. Decirle "mínimo para calificar" a secas
        haría pensar que también recorta a los líderes, y no es así.

    Octubre no pasa por la cascada: sus tasas usan el piso fijo del motor (docs/UMBRALES_POSTEMPORADA),
    mucho más bajo porque una postemporada entera son unos pocos juegos.
    """
    is_rate = metric.kind == Metric.Kind.RATE
    if not is_rate and not has_worst:
        return ""
    # CON «TODAS» NO HAY UN NÚMERO QUE ESCRIBIR, y poner uno sería mentir. El umbral se recalcula
    # cada año a partir de los juegos que se jugaron —en 2026 pide 332 turnos y en 2025 pedía 502, y
    # en 2020 muchísimo menos— así que las filas de esta tabla no pasaron todas por la misma vara.
    # Cada una calificó contra la de SU temporada, que es lo correcto y lo que dice la frase.
    #
    # Y LA SALVEDAD DE 2020 VA EN LA MISMA FRASE (dueño, 2026-08-04). «Cada temporada se midió contra
    # su propio mínimo» a secas se lee como que están TODAS, y justamente hay una que no está.
    if todas:
        cual = "calificar" if is_rate else "entrar en Últimos"
        return f"Cada temporada se midió contra su propio mínimo para {cual}. {_excluded_note(todas=True)}".strip()
    if october:
        season_floor, career_floor = _POST_QUALIFIER.get(metric.stat_group, ("", ""))
        formula = career_floor if scope == "carrera" else season_floor
        return f"Mínimo para calificar: {pretty_qualifier(formula)}." if formula else ""
    defaults, overrides = qualifier_lookups()
    juegos = _juegos_de_la_temporada(season) if scope != "carrera" and season else None
    formula = (
        qualifier.resolve_career(metric, defaults)
        if scope == "carrera"
        else qualifier.resolve_season(metric, season or 0, defaults, overrides, juegos)
    )
    if not formula:
        return ""
    pretty = pretty_qualifier(formula)
    # De dónde sale el número, cuando sale de los juegos. Un umbral que cambia de una temporada a
    # otra sin explicarse invita a pensar que está mal: en 2026 pide 332 y en 2025 pedía 502, y sin
    # esta coletilla no hay forma de saber que es la misma regla con menos juegos.
    origen = ""
    if juegos and not overrides.get((metric.stat_group, season or 0)) and not metric.qualifier_season:
        origen = f" ({juegos} juegos)"
    if is_rate:
        return f"Mínimo para calificar: {pretty}{origen}."
    return f"Mínimo para entrar en Últimos: {pretty}{origen}."


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
    metric: Metric, scope: str, season: int | None, player_ids: list[int], pos: str | None, *, october: bool
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
        metric=metric, board=_board_flag(scope), postseason=october, fielding_pos=pos, player_id__in=player_ids
    )
    if scope == "temporada" and season is not None:
        board = board.filter(season=season)
    return dict(board.values_list("player_id", "rank"))


def _de_todos_los_tiempos(
    candidatos: list[Leader], metric: Metric, tope: int, *, best: bool
) -> list[tuple[Leader, int]]:
    """Vuelve a rankear temporadas de años distintos entre sí, y corta en el puesto `tope`.

    EL `rank` GUARDADO ES DE SU PROPIA TEMPORADA y acá no sirve para nada: los 66 jonrones de Sosa en
    1998 y los 24 de alguien en 1972 son los dos un `rank = 1`. Para «Todas» hay que comparar los
    VALORES, que es lo que hace esto.

    FILTRAR ANTES POR EL TOP DE CADA TEMPORADA NO PIERDE A NADIE, y esa es la razón de que esto sea
    barato. Si alguien no está entre los diez de su propio año es porque diez lo superaron ESE MISMO
    año, y esos diez están todos guardados — así que tampoco puede estar entre los diez de la
    historia. La punta histórica siempre es un subconjunto de la unión de las puntas anuales. Sin
    eso habría que rankear cada temporada de cada jugador de todos los tiempos, y `dgl_leader` ni
    siquiera las guarda: llega hasta el puesto 29.

    HACIA DÓNDE SE ORDENA sale de la dirección de la métrica combinada con la punta que se pide. En
    jonrones la mejor es la más alta y la peor la más baja; en efectividad es al revés, y por eso no
    se puede asumir `reverse=True` para «mejores».

    Empates a la manera del motor (`stats/leaders._dense_rank`): comparten puesto y el siguiente es
    el que sigue, sin saltos. Y el corte es HASTA EL PUESTO, no a las N filas, igual que el
    `rank__lte` de todos los demás tableros: tres empatados en el décimo entran los tres.
    """
    # EL DESEMPATE LLEVA EL AÑO DENTRO, y hace falta. Con solo (valor, nombre), las dos temporadas de
    # un MISMO jugador que valen lo mismo —Alex Rodríguez con 54 en 2007 y en 2010— tienen la clave
    # idéntica: `sorted` es estable, así que el orden lo acababa decidiendo la base de datos. Y como
    # «Todas» PINTA el año, esa inestabilidad se veía en pantalla y se colaba en cualquier caché o
    # comparación de pruebas (QA-01 del review v21).
    #
    # La más vieja primero, que es el criterio del sitio para un empate: la marca es de quien llegó
    # antes. `player_id` cierra la clave por si dos homónimos empatan el mismo año.
    descendente = (metric.direction == Metric.Direction.HIGHER) == best
    ordenados = sorted(
        candidatos,
        key=lambda row: (
            -row.value if descendente else row.value,
            row.season or 0,
            row.player.full_name,
            row.player_id,
        ),
    )

    puestos: list[tuple[Leader, int]] = []
    rank = 0
    anterior: float | None = None
    for row in ordenados:
        if row.value != anterior:
            rank += 1
            anterior = row.value
        if rank > tope:
            break
        puestos.append((row, rank))
    return puestos


def _board_rows(
    metric: Metric,
    scope: str,
    season: int | None,
    pos: str | None,
    *,
    best: bool = True,
    october: bool = False,
    todas: bool = False,
) -> list[dict[str, Any]]:
    """Un extremo del tablero: los `_TOP_RANK` puestos de una punta.

    `rank` sale acá tal cual lo guarda `dgl_leader`. Para la tabla de abajo eso es su propio puesto 1
    en el extremo —que escrito así se leería como un liderato, "1º en menos jonrones"— y lo reemplaza
    `_best_and_worst` por el puesto real del ranking.

    Con `todas` el puesto NO es el guardado sino uno nuevo, calculado entre todas las temporadas de
    todos los años. Ver `_de_todos_los_tiempos`.
    """
    flag = _board_flag(scope, best=best)
    board = Leader.objects.filter(metric=metric, board=flag, postseason=october, fielding_pos=pos)
    if scope == "temporada" and season is not None:
        board = board.filter(season=season)
    # La temporada corta no se compara con una completa. Solo estorba acá, al mezclar años; elegida
    # a mano se lee entera. Ver `_FUERA_DE_TODAS`.
    if todas:
        board = board.exclude(season__in=_FUERA_DE_TODAS)
    # Y LA TEMPORADA EN CURSO SE CAE DE ÚLTIMOS, PERO NO DE PRIMEROS (dueño, 2026-08-04). La asimetría
    # no es un descuido: un total a medio jugar solo puede quedarse CORTO. Los 30 jonrones que alguien
    # lleva en agosto son 30 de verdad y no desmerecen nada en la tabla de arriba; en la de abajo, en
    # cambio, ganarían el primer puesto de «menos jonrones de la historia» por no haber terminado de
    # jugar. El umbral tampoco protege: la cascada lo escala a los juegos disputados, así que en
    # agosto pide 332 turnos donde en octubre pedirá 502.
    if todas and not best:
        board = board.exclude(season__in=season_window.temporadas_sin_terminar())
    tope = _top_rank(scope, october)
    candidatos = list(
        board.filter(rank__lte=tope).order_by("rank", "player__full_name").select_related("player")
    )
    # Con un año elegido el puesto guardado ES el puesto; con «Todas» hay que rehacerlo.
    puestos = (
        _de_todos_los_tiempos(candidatos, metric, tope, best=best)
        if todas
        else [(row, row.rank) for row in candidatos]
    )
    leaders = [row for row, _ in puestos]
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
            "rank": rank,
            "name": row.player.full_name,
            "slug": row.player.slug,
            "player_id": row.player_id,
            # EN QUÉ AÑO FUE. Solo lo pinta «Todas», donde cada fila es de una temporada distinta y
            # sin el año la tabla no se entiende; con un año elegido es el mismo para todas y el
            # rótulo del tablero ya lo dice.
            "season": row.season,
            "active": row.player_id in active,  # jugó la última temporada registrada
            "seasons": span.get(row.player_id, (0, 0))[0],
            "partial": bool(since) and span.get(row.player_id, (0, since or 0))[1] < (since or 0),
            "value": _format(metric.stat_group, metric.column, row.value),
        }
        for row, rank in puestos
    ]


def _column_labels(metric: Metric, scope: str, october: bool) -> tuple[str, str]:
    """Cómo se llaman las dos tablas.

    Sin el número: cuántos entran depende del alcance (15 de por vida, 10 por temporada) y del
    empate del último puesto, así que un "Primeros 15" sobre una tabla de 17 filas se contradecía
    solo. El número sigue en `_TOP_RANK`, que es donde importa.

    En una métrica normal son los primeros y los últimos. En una descriptiva no: ahí la segunda tabla
    no es la de los peores sino la del extremo OPUESTO del mismo perfil — un GB% bajo no es un mal
    GB%, es un lanzador de elevados en vez de uno de rodados. Se rotulan por altura, sin juzgar.
    El orden sale de la dirección, no se asume, para que el rótulo siga al tablero si alguien la
    cambia en el Backoffice.
    """
    if metric.column not in DESCRIPTIVE_COLUMNS:
        return "Primeros", "Últimos"
    alto, bajo = "Los más altos", "Los más bajos"
    return (alto, bajo) if metric.direction == Metric.Direction.HIGHER else (bajo, alto)


def _best_and_worst(
    metric: Metric, scope: str, season: int | None, pos: str | None, *, october: bool = False, todas: bool = False
) -> list[dict[str, Any]]:
    """Las dos tablas paralelas: el tablero descendente a la izquierda y el ascendente a la derecha.

    Cuando hay pocos calificados las dos puntas se solapan y un mismo jugador sale en las dos. Ahí
    manda la primera: el repetido se quita de la segunda. Si con eso la segunda se vacía —o la
    métrica no tiene ese tablero, como G/PA/AB— queda una sola columna.
    """
    best = _write_rank_once(_board_rows(metric, scope, season, pos, best=True, october=october, todas=todas))
    # Hay conteos cuyo extremo bajo, juntando setenta años, no es una marca sino un empate de
    # centenares. Se van sin consultar la otra punta siquiera. Ver `_SIN_ULTIMOS_EN_TODAS`.
    if todas and (metric.stat_group, metric.column) in _SIN_ULTIMOS_EN_TODAS:
        return _columnas(metric, scope, october, best, [])
    # QUÉ ES «EL MISMO» CAMBIA CON «TODAS». En un tablero normal la fila es un jugador y basta con su
    # id. En «Todas» la fila es un JUGADOR-TEMPORADA: Sammy Sosa sale tres veces en las mejores de
    # jonrones, por 1998, 1999 y 2001. Deduplicar solo por jugador le borraría de la otra punta una
    # temporada distinta que sí merece estar ahí.
    def cual(row: dict[str, Any]) -> tuple[int, int | None]:
        return (row["player_id"], row["season"] if todas else None)

    honored = {cual(row) for row in best}
    tail = [
        row
        for row in _board_rows(metric, scope, season, pos, best=False, october=october, todas=todas)
        if cual(row) not in honored
    ]
    if todas:
        # ACÁ LA COLA SE QUEDA CON SU PROPIO PUESTO, y no es por descuido. El renumerado de abajo
        # busca el puesto del jugador en el ranking DESCENDENTE, y el descendente de todos los
        # tiempos no existe: `dgl_leader` solo guarda la punta de cada temporada (hasta el 29), así
        # que la peor efectividad de la historia no tiene un puesto que buscar — habría que rankear
        # todas las temporadas de todos los lanzadores de siempre, y esas filas no están.
        #
        # No deja el número ambiguo: la tabla se titula «Últimos» y el 1 se lee como «el primero de
        # los últimos», que es lo que es.
        return _columnas(metric, scope, october, best, _write_rank_once(tail))
    # La cola se publica con el puesto del ranking de arriba, no con el del tablero ascendente, y se
    # ordena por él: así el extremo queda de último y ningún número significa dos cosas distintas.
    real = _real_ranks(metric, scope, season, [row["player_id"] for row in tail], pos, october=october)
    for row in tail:
        row["rank"] = real.get(row["player_id"], row["rank"])
    tail.sort(key=lambda row: (row["rank"], row["name"]))
    return _columnas(metric, scope, october, best, _write_rank_once(tail))


def _columnas(
    metric: Metric, scope: str, october: bool, best: list[dict[str, Any]], worst: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Las dos tablas rotuladas, o una sola si la segunda quedó vacía tras el dedup."""
    top_label, bottom_label = _column_labels(metric, scope, october)
    columns = [{"label": top_label, "rows": best}]
    if worst:
        columns.append({"label": bottom_label, "rows": worst})
    return columns


def _empty_context(group: str, scope: str, pos: str | None) -> dict[str, Any]:
    """El mismo contrato que `leaders_context`, con todo vacío: la página se dibuja y explica.

    Las claves están TODAS aunque no haya datos. Un contexto al que le faltan llaves no falla acá
    sino en el template, que es más lejos del problema y más difícil de leer.
    """
    state = {"g": group, "scope": scope, "pos": pos or ""}
    return {
        "groups": [
            {"label": label, "active": key == group, "url": _link(state, g=key, d=None, m=None, season=None)}
            for key, label in _GROUPS
        ],
        "divisions": [],
        "scopes": [{"label": label, "active": key == scope, "url": _link(state, scope=key)} for key, label in _SCOPES],
        "positions": [
            {"label": p, "active": p == pos, "url": _link(state, pos=p, d=None, m=None)}
            for p in (_POSITIONS if group == "fielding" else [])
        ],
        "metrics": [],
        "seasons": [],
        "board": {
            "name": "",
            "abbr": "",
            "direction": "",
            "qualifier": "",
            "excluded": "",
            "available_from": None,
            "scope_label": "",
            "columns": [],
            "shows_active": False,
            "shows_partial": False,
            "shows_seasons": False,
            "shows_season": False,
        },
        "group_label": dict(_GROUPS)[group],
        "scope_key": scope,
        "empty": True,
    }


# Con qué métrica se abre cada oficio cuando nadie pidió una. Sin esto se abría con la primera del
# catálogo —Juegos en bateo, Victorias en pitcheo— que está ordenada para leer una tabla completa, no
# para ser la portada de la sección: nadie llega a Líderes preguntándose quién jugó más partidos.
#
# Es una decisión editorial y por eso vive acá, escrita, y no en el `sort_order` del catálogo: mover
# HR al principio del orden cambiaría también todas las tablas donde ese orden sí importa.
#
# Un oficio que no esté acá abre con la primera de su división, que es el comportamiento de siempre.
METRICA_INICIAL: dict[str, str] = {"batting": "hr"}


def _por_defecto(group: str, metricas: list[Metric]) -> Metric:
    """La métrica con la que abre el oficio, o la primera si no hay una elegida (o si se desactivó)."""
    preferida = METRICA_INICIAL.get(group)
    return next((m for m in metricas if m.column == preferida), metricas[0])


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
    if not divisions:
        # Sin métricas activas no hay nada que rankear, y antes esto reventaba con IndexError —
        # una página pública caída, no un caso de borde: pasa en una base recién migrada, en staging
        # limpio, o si alguien desactiva las métricas de un grupo desde el Backoffice.
        return _empty_context(group, scope, chosen_pos)
    division_labels = [label for label, _ in divisions]
    if tab not in division_labels:
        tab = division_labels[0]
    tab_metrics = next(metrics for label, metrics in divisions if label == tab)

    metric = next((m for m in tab_metrics if m.column == metric_col), _por_defecto(group, tab_metrics))
    october = tab == _POSTSEASON_DIVISION

    # Seasons this metric was ranked in (some start in 1989), newest first; the picked one is validated.
    season_years: list[int] = []
    if scope == "temporada":
        years = Leader.objects.filter(
            metric=metric, board=Leader.Board.BEST_SEASON, postseason=october, fielding_pos=chosen_pos
        ).values_list("season", flat=True)
        season_years = sorted({year for year in years if year is not None}, reverse=True)
    # «TODAS» ES UNA ELECCIÓN MÁS DE ESTE MISMO DESPLEGABLE, no otro alcance. Pide las mejores
    # temporadas INDIVIDUALES de la historia —las 66 de Sosa en 1998 compitiendo contra las 54 de
    # Ortiz en 2006— y por eso vive acá y no al lado de «De por vida», que suma la carrera entera.
    #
    # `chosen_season = None` con `todas = True` es lo que apaga el filtro por año; el puesto lo
    # rehace `_de_todos_los_tiempos`, porque el guardado es de su propia temporada.
    # Y ES LO QUE SALE POR DEFECTO (dueño, 2026-08-04). Antes abría en la temporada más reciente, y
    # eso convertía «Por temporada» en «los líderes de 2026» — una foto de un año a medio jugar,
    # cuando lo que la sección promete son las mejores temporadas que se han visto. Quien quiera un
    # año concreto lo elige; el que no, ve la historia.
    #
    # Por eso el año solo gana si es uno de los que existen: vacío, «todas» o cualquier basura caen
    # todos acá. Un `?season=1899` ya no aterriza en 2026 sin explicación.
    todas = False
    chosen_season = None
    if season_years:
        if season.isdigit() and int(season) in season_years:
            chosen_season = int(season)
        else:
            todas = True

    state = {
        "g": group,
        "d": tab,
        "scope": scope,
        "m": metric.column,
        "season": TODAS if todas else str(chosen_season or ""),
        "pos": chosen_pos or "",
    }
    columns = _best_and_worst(metric, scope, chosen_season, chosen_pos, october=october, todas=todas)
    # La salvedad de 2020 va DENTRO de la frase del umbral, que es donde se pidió. Sola solo cuando
    # esa frase no existe —una métrica sin umbral y sin tablero de Últimos la deja vacía— para que el
    # aviso no se quede sin sitio. Ver `_excluded_note`.
    nota = _qualifier_note(
        metric, scope, has_worst=len(columns) > 1, october=october, season=chosen_season, todas=todas
    )

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
        # «Todas» LA PRIMERA (dueño, 2026-08-04), y solo si hay años que juntar. La lista se sigue
        # llamando `seasons` y cada entrada trae su `label`, para que la plantilla no tenga que saber
        # que la primera es especial.
        "seasons": [
            {"year": TODAS, "label": "Todas", "active": todas, "url": _link(state, season=TODAS)},
            *(
                {
                    "year": year,
                    "label": str(year),
                    "active": year == chosen_season,
                    "url": _link(state, season=str(year)),
                }
                for year in season_years
            ),
        ]
        if season_years
        else [],
        "board": {
            "name": metric.name_es or metric.abbrev,
            "abbr": metric.abbrev,
            "direction": _direction_label(metric),
            "qualifier": nota,
            "excluded": "" if nota else _excluded_note(todas=todas),
            "available_from": metric.available_from,  # "disponible desde YYYY" cuando aplica (Statcast)
            "scope_label": _scope_label(scope, chosen_season, todas=todas),
            "columns": columns,  # Mejores y (si existe y no quedó vacía tras el dedup) Peores
            # La leyenda del verde solo tiene sentido si alguna fila está marcada (no la hay en el
            # board de la última temporada, ni en uno viejo donde ya todos se retiraron).
            "shows_active": any(row["active"] for column in columns for row in column["rows"]),
            "shows_partial": any(row["partial"] for column in columns for row in column["rows"]),
            # La columna Temporadas es una lectura de carrera. En un tablero de temporada todos
            # jugaron ese año y punto: el dato no dice nada del puesto que se está mirando.
            "shows_seasons": scope == "carrera",
            # Y EL AÑO SOLO EN «TODAS», que es el único tablero donde cada fila es de un año distinto
            # y sin él la tabla no se entiende: «66» a secas no dice que fue 1998. Las dos columnas
            # son excluyentes por construcción —una es de carrera y la otra de temporada— así que
            # nunca aparecen «Temporadas» y «Temporada» juntas, que se leerían como un error.
            "shows_season": todas,
        },
        "group_label": dict(_GROUPS)[group],
        "scope_key": scope,
    }


def leaders_index(request: HttpRequest) -> HttpResponse:
    from dglweb.stats import mlb_leaders

    context = leaders_context(
        group=request.GET.get("g", "batting"),
        tab=request.GET.get("d", ""),
        scope=request.GET.get("scope", "carrera"),
        metric_col=request.GET.get("m", ""),
        season=request.GET.get("season", ""),
        pos=request.GET.get("pos", ""),
    )
    # El mismo widget de la portada. Acá dice algo que esta página no puede: sus tableros ordenan a
    # los nuestros ENTRE NOSOTROS, y el widget dice cuáles están en el top de las mayores. Verlos
    # juntos es lo que hace evidente que son dos preguntas distintas.
    context["lideres"] = mlb_leaders.portada()
    return render(request, "profiles/leaders.html", context)
