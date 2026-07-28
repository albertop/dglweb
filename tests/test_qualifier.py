"""La cascada de umbrales: quién califica para un tablero de tasas, y con qué mínimo.

Por qué merece pruebas propias, aunque el motor de líderes ya tenga paridad comprobada contra la
base real: la paridad demuestra que el resultado CUADRA, no que la regla se resuelva por el camino
correcto. Son cosas distintas. Hoy los tres niveles dan lo mismo en casi todas las métricas —de ahí
que la paridad pase— y el día que alguien ponga un override de temporada en el Backoffice, el nivel
equivocado devolvería un número igual de plausible y nadie lo notaría.

El orden manda de lo más específico a lo más general:

    temporada  →  override de (oficio, temporada)  →  el de la métrica  →  el del oficio
    carrera    →  el de la métrica                 →  el del oficio

Estas pruebas fijan ese orden y, sobre todo, que cada nivel TAPE al siguiente.
"""

import pytest

from dglweb.stats import qualifier
from dglweb.stats.models import Metric

DEFECTOS = {"batting": ("PA>=502", "PA>=3000"), "pitching": ("IP>=162", "IP>=1000")}


def _metrica(**campos: object) -> Metric:
    """Una métrica sin guardar: la cascada solo lee atributos, no consulta la base."""
    base = {"stat_group": "batting", "column": "avg", "qualifier_season": "", "qualifier_career": ""}
    return Metric(**{**base, **campos})


# ── Temporada: los tres niveles ─────────────────────────────────────────────────────────────────


def test_el_override_de_temporada_le_gana_a_todo() -> None:
    """El nivel que existe para las temporadas cortas: 1994, 2020, la pandemia.

    Si no ganara, un año de 60 juegos se mediría con el umbral de uno de 162 y el tablero saldría
    vacío — que es peor que salir con pocos, porque parece que no hubo temporada.
    """
    metrica = _metrica(qualifier_season="PA>=400")

    resuelto = qualifier.resolve_season(metrica, 2020, DEFECTOS, {("batting", 2020): "PA>=186"})

    assert resuelto == "PA>=186"


def test_sin_override_manda_el_de_la_metrica() -> None:
    """El de la métrica tapa al del oficio: hay tasas que piden su propio mínimo."""
    metrica = _metrica(qualifier_season="PA>=400")

    assert qualifier.resolve_season(metrica, 2020, DEFECTOS, {}) == "PA>=400"


def test_sin_override_ni_metrica_manda_el_del_oficio() -> None:
    assert qualifier.resolve_season(_metrica(), 2020, DEFECTOS, {}) == "PA>=502"


def test_un_override_de_otra_temporada_no_se_aplica() -> None:
    """La clave del override es (oficio, temporada), y las dos mitades importan.

    Sin esta prueba, un error de dedo que ignorara la temporada dejaría el umbral de 2020 —el año
    corto— gobernando todos los demás, y el tablero de cada año publicaría gente que no califica.
    """
    con_override = {("batting", 2020): "PA>=186"}

    assert qualifier.resolve_season(_metrica(), 2019, DEFECTOS, con_override) == "PA>=502"


def test_un_override_de_otro_oficio_no_se_aplica() -> None:
    con_override = {("pitching", 2020): "IP>=60"}

    assert qualifier.resolve_season(_metrica(), 2020, DEFECTOS, con_override) == "PA>=502"


# ── Carrera: dos niveles, sin override ──────────────────────────────────────────────────────────


def test_la_carrera_no_mira_los_overrides_de_temporada() -> None:
    """Y no es un olvido: un mínimo de carrera no puede depender de un año concreto."""
    metrica = _metrica(qualifier_career="PA>=2000")

    assert qualifier.resolve_career(metrica, DEFECTOS) == "PA>=2000"


def test_la_carrera_cae_al_del_oficio() -> None:
    assert qualifier.resolve_career(_metrica(), DEFECTOS) == "PA>=3000"


def test_un_oficio_sin_defecto_devuelve_vacio_en_vez_de_reventar() -> None:
    """Vacío significa «sin umbral», y el motor lo entiende como que todos califican.

    Es la respuesta correcta para un oficio recién añadido al que nadie le ha puesto mínimos:
    publicar el tablero completo se ve y se corrige; una excepción tumba la página entera.
    """
    assert qualifier.resolve_season(_metrica(stat_group="fielding"), 2020, DEFECTOS, {}) == ""
    assert qualifier.resolve_career(_metrica(stat_group="fielding"), DEFECTOS) == ""


# ── Evaluación ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("formula", "pa", "califica"),
    [("PA>=502", 502, True), ("PA>=502", 501, False), ("PA>502", 502, False), ("PA<100", 99, True)],
)
def test_la_formula_se_evalua_sin_eval(formula: str, pa: int, califica: bool) -> None:
    """El parseo es `CAMPO OP NÚMERO` y nada más. La fórmula la escribe un humano en el Backoffice,
    así que `eval` sería ejecución de código arbitrario a un formulario de distancia."""
    assert qualifier.qualifies(formula, "batting", {"pa": pa}) is califica


def test_una_fila_sin_el_dato_no_califica() -> None:
    """Sin el conteo no se puede afirmar que llegó al mínimo, y ante la duda no entra: un tablero de
    tasas con alguien que quizá no calificaba es peor que uno con una fila menos."""
    assert qualifier.qualifies("PA>=502", "batting", {"pa": None}) is False


def test_sin_formula_califican_todos() -> None:
    assert qualifier.qualifies("", "batting", {"pa": 1}) is True


# ── El prorrateo por juegos (2026-07-28) ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("grupo", "juegos", "esperado"),
    [
        # 162 juegos reproduce EXACTAMENTE los umbrales fijos de toda la vida. Es la prueba de que
        # 502 nunca fue un número mágico: es 3,1 x 162, y el fijo era la regla aplicada a una
        # temporada completa.
        ("batting", 162, "PA>=502"),
        ("pitching", 162, "IP>=162"),
        ("fielding", 162, "G>=100"),
        # Y estos reproducen, uno a uno, los overrides que el dueño venía poniendo A MANO.
        ("batting", 60, "PA>=186"),  # 2020, pandemia
        ("batting", 107, "PA>=332"),  # 1981, huelga
        ("batting", 114, "PA>=353"),  # 1994, huelga
        ("batting", 154, "PA>=477"),  # 1958-60, calendario de 154 juegos
        ("pitching", 107, "IP>=107"),
        ("pitching", 60, "IP>=60"),
    ],
)
def test_la_regla_reproduce_los_umbrales_escritos_a_mano(grupo: str, juegos: int, esperado: str) -> None:
    """La regla no se inventó: se leyó de lo que el dueño ya hacía.

    Si alguna de estas cambia, la regla dejó de coincidir con su criterio — y eso es una decisión
    suya, no un detalle de implementación.
    """
    assert qualifier.prorated(grupo, juegos) == esperado


def test_sin_juegos_no_hay_prorrateo() -> None:
    """Cero o negativo no es «umbral cero»: es «no se sabe», y ahí manda el fijo."""
    assert qualifier.prorated("batting", 0) == ""
    assert qualifier.prorated("bateo_inventado", 162) == ""


def test_el_prorrateo_va_debajo_del_override_del_dueno() -> None:
    """Su decisión no la pisa una regla, por buena que sea la regla."""
    metrica = _metrica()
    con_override = {("batting", 2020): "PA>=200"}

    assert qualifier.resolve_season(metrica, 2020, DEFECTOS, con_override, games=60) == "PA>=200"


def test_el_prorrateo_va_debajo_del_umbral_propio_de_la_metrica() -> None:
    """Los coeficientes de batazos filtran por bolas en juego, no por apariciones: su propio umbral
    tiene que seguir ganando o el tablero mediría otra cosa."""
    metrica = _metrica(qualifier_season="BALLS_IN_PLAY>=200")

    assert qualifier.resolve_season(metrica, 2026, DEFECTOS, {}, games=107) == "BALLS_IN_PLAY>=200"


def test_el_prorrateo_va_encima_del_fijo_del_oficio() -> None:
    """El caso que motivó todo: 107 juegos pedían 502 y dejaban el tablero de 2026 VACÍO."""
    assert qualifier.resolve_season(_metrica(), 2026, DEFECTOS, {}, games=107) == "PA>=332"


def test_sin_juegos_conocidos_se_cae_al_fijo_y_no_al_vacio() -> None:
    """La red. Un año que la fuente no cubra, o el proxy caído, no puede dejar el tablero SIN umbral:
    publicar tasas sin mínimo corona a quien jugó tres partidos."""
    assert qualifier.resolve_season(_metrica(), 2026, DEFECTOS, {}, games=None) == "PA>=502"
