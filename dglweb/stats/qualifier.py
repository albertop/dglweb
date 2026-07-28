"""Resolve and evaluate the qualifier for a rate leaderboard (the 3-level cascade).

Resolution (most specific wins):
  * season boards -> season override (group, season) -> metric's own -> group default
  * career boards -> metric's own -> group default

Evaluation is a *safe* parse of a simple formula ``FIELD OP NUMBER`` (e.g. ``PA>=502``) — never
``eval``. The field names the qualifier column per group (batting PA, pitching IP, fielding G); IP
is derived from the canonical ``outs`` (never the baseball-notation ``ip``).
"""

import logging
import operator
from collections.abc import Callable, Mapping
from typing import Any

from dglweb.stats.formula import QUALIFIER_RE
from dglweb.stats.models import Metric

logger = logging.getLogger(__name__)

_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}

# Lookups the engine preloads once and passes in, to avoid a query per row.
Defaults = Mapping[str, tuple[str, str]]  # group -> (season formula, career formula)
Overrides = Mapping[tuple[str, int], str]  # (group, season) -> season formula


# EL UMBRAL POR JUEGO DE CADA OFICIO. `(campo, cuánto por juego)`.
#
# No son números elegidos: son los umbrales de temporada completa divididos entre 162, y los tres se
# comprobaron contra los overrides que el dueño venía poniendo a mano temporada por temporada.
#
#   bateo    3.1 PA/juego   →  3.1 x 162 = 502, el umbral fijo de siempre. Sus overrides de 1958
#                              (477), 1981 (332), 1994 (353) y 2020 (186) dan 154, 107, 114 y 60
#                              juegos: la mediana de cada una de esas temporadas, clavada.
#   pitcheo  1.0 IP/juego   →  162 IP. Igual: sus overrides de 1960, 1981, 1994 y 2020 son 154,
#                              107, 114 y 60.
#   fildeo   0.617 G/juego  →  100/162. Sus overrides dan 95/154, 66/108 y 37/60 = 0.617.
#
# O sea que la regla no se inventó acá: se leyó de lo que el dueño ya hacía a mano.
TEMPORADA_COMPLETA = 162

POR_JUEGO: dict[str, tuple[str, float]] = {
    "batting": ("PA", 502 / TEMPORADA_COMPLETA),
    "pitching": ("IP", TEMPORADA_COMPLETA / TEMPORADA_COMPLETA),
    "fielding": ("G", 100 / TEMPORADA_COMPLETA),
}


def escalar(formula: str, games: int) -> str:
    """El mismo umbral, medido contra una temporada de `games` juegos en vez de una completa.

    PARA QUÉ, Y QUÉ DESTAPÓ QUE HICIERA FALTA
    ------------------------------------------
    Los coeficientes de batazos no filtran por apariciones sino por bolas en juego o por swings:
    `BALLS_IN_PLAY>=300`, `TOTAL_SWINGS>=750`. Son cifras de UNA TEMPORADA COMPLETA, escritas a mano
    en la métrica, y no se prorrateaban — así que en una temporada corta no las alcanzaba nadie y sus
    tableros salían vacíos.

    Estuvo escondido durante años porque los overrides del dueño ganaban por estar más arriba en la
    cascada y rescataban a esos coeficientes de rebote. Al borrar los overrides (2026-07-28) el
    agujero salió: 251 puestos de 2020 desaparecieron de golpe. Y en las temporadas cortas SIN
    override —1972, 1995— llevaban vacíos desde siempre sin que nada lo dijera.

    Se escala el NÚMERO y se respeta el campo y el operador: no hay que saber qué mide `BALLS_IN_PLAY`
    para saber que 300 en 162 juegos son 111 en 60. Una fórmula que no se pueda leer se devuelve tal
    cual — el motor prefiere un umbral estricto a uno inventado.
    """
    match = QUALIFIER_RE.match(formula)
    if not match or games <= 0:
        return formula
    campo, operador, valor = match.group(1), match.group(2), float(match.group(3))
    return f"{campo}{operador}{round(valor * games / TEMPORADA_COMPLETA)}"


def prorated(group: str, games: int) -> str:
    """El umbral de un oficio para una temporada de `games` juegos. Vacío si el oficio no se conoce.

    Se redondea al entero más cercano porque un umbral con decimales no se puede explicar en el pie
    de una tabla: «PA ≥ 331,7» invita a preguntar de dónde sale el 0,7.
    """
    regla = POR_JUEGO.get(group)
    if not regla or games <= 0:
        return ""
    campo, por_juego = regla
    return f"{campo}>={round(games * por_juego)}"


def resolve_season(
    metric: Metric, season: int, defaults: Defaults, overrides: Overrides, games: int | None = None
) -> str:
    """El umbral de temporada, de lo más específico a lo más general.

    EL ESCALÓN NUEVO ES `games` (2026-07-28)
    ----------------------------------------
    Antes el último escalón era un número fijo —`PA>=502`— y eso mentía en cuanto la temporada no
    llegaba a 162 juegos. Medido: con 107 juegos jugados, 2026 publicaba CERO líderes de AVG, OBP,
    OPS, wOBA, wRC+, ERA y WHIP porque nadie llegaba a 502 apariciones. Y en silencio pasaba lo
    mismo con 1995, una temporada de 145 juegos que nadie había corregido a mano.

    `games` va DEBAJO del override del dueño y del umbral propio de la métrica, y ARRIBA del fijo:

        override del dueño  →  el de la métrica  →  3.1 x juegos  →  el fijo del oficio
             (manda)            (métricas raras)      (la regla)         (la red)

    El fijo no se retira: es lo que queda si no sabemos los juegos de esa temporada —el proxy caído,
    un año que la fuente no cubra— y publicar sin umbral sería peor que publicar con uno estricto.

    QUIÉN DECIDE CUÁNTOS JUEGOS. Esta función no lo sabe y no debe saberlo: recibe el número ya
    resuelto. Quien llama es quien tiene el dato —los juegos del equipo del jugador, o el máximo de
    su liga si lo cambiaron a mitad de temporada— y esa decisión vive junto a esos datos.
    """
    override = overrides.get((metric.stat_group, season))
    if override:
        return override
    if metric.qualifier_season:
        # También se prorratea. Su cifra está escrita para una temporada completa —300 bolas en
        # juego, 750 swings— y dejarla fija vacía el tablero en los años cortos. Ver `escalar`.
        return escalar(metric.qualifier_season, games) if games else metric.qualifier_season
    if games:
        prorrateado = prorated(metric.stat_group, games)
        if prorrateado:
            return prorrateado
    return defaults.get(metric.stat_group, ("", ""))[0]


def resolve_career(metric: Metric, defaults: Defaults) -> str:
    if metric.qualifier_career:
        return metric.qualifier_career
    return defaults.get(metric.stat_group, ("", ""))[1]


def _column(group: str, field: str) -> str:
    """The row column a qualifier field reads. Anything unmapped is the column of the same name."""
    if group == "pitching" and field == "IP":
        return "outs"  # IP is derived from the canonical outs
    return {"PA": "pa", "G": "gp" if group == "fielding" else "g"}.get(field, field.lower())


def field_column(group: str, formula: str) -> str | None:
    """The column a formula needs, so the caller can be sure it selected it.

    A threshold on a column the caller did not fetch reads as missing and fails **closed** — the
    board comes out empty instead of unfiltered. Metrics with their own qualifier (the batted-ball
    coefficients gate on `BALLS_IN_PLAY`, not `PA`) depend on this.
    """
    match = QUALIFIER_RE.match(formula or "")
    return None if match is None else _column(group, match.group(1))


def _field_value(group: str, field: str, row: Mapping[str, Any]) -> float | None:
    """The qualifier field's value for a totals row (IP = outs / 3; G = games at the position)."""
    if group == "pitching" and field == "IP":
        outs = row.get("outs")
        return None if outs is None else outs / 3
    value = row.get(_column(group, field))
    return None if value is None else float(value)


def qualifies(formula: str, group: str, row: Mapping[str, Any]) -> bool:
    """True if the row clears the threshold.

    A **blank** formula means *no threshold* (everyone qualifies). A non-blank but **unparseable**
    formula is fail-**closed**: it qualifies no one, so a typo publishes an empty board rather than an
    unfiltered one. (Forms reject invalid formulas via `validate_qualifier_formula`; this is defense
    in depth for anything that reaches the builder anyway.)
    """
    if not formula.strip():
        return True
    match = QUALIFIER_RE.match(formula)
    if match is None:
        logger.warning("Fórmula de umbral inválida %r: no califica a nadie (fail-closed).", formula)
        return False
    field, op, threshold = match.group(1), match.group(2), float(match.group(3))
    value = _field_value(group, field, row)
    if value is None:
        return False
    return _OPS[op](value, threshold)
