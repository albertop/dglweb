"""El vocabulario compartido entre el perfil y Líderes.

Estas reglas no son de una pantalla: son el acuerdo entre las dos. Si el perfil pone ISO en Avanzado
y Líderes en Estándar, el lector que salta de una a la otra cree que son métricas distintas. Por eso
el módulo es público y por eso estos tests viven aparte de los de cada página.
"""

import pytest

from dglweb.players.models import Player
from dglweb.profiles import metric_layout
from dglweb.profiles.leaderboards import leaders_context
from dglweb.stats.models import Leader, Metric
from tests.test_players import _other_player


@pytest.mark.parametrize("group", ["batting", "pitching", "fielding"])
def test_no_metric_is_listed_in_two_divisions(group: str) -> None:
    """Una columna repetida saldría dos veces en Puestos y en el dropdown de Líderes.

    Pasa fácil sin querer: OPS está en la tabla Estándar y también en Avanzado del perfil, y G/AB
    encabezan Statcast y Coeficientes como contexto. La primera división gana.
    """
    todas = [attr for _, attrs in metric_layout.divisions_for(group) for attr in attrs]

    assert len(todas) == len(set(todas))


def test_batting_slots_the_two_metrics_that_no_table_shows() -> None:
    """1B e IBB se rankean pero no están en ninguna tabla del perfil: entran en su lugar lógico."""
    estandar = dict(metric_layout.divisions_for("batting"))["Estándar"]

    assert estandar.index("h") < estandar.index("x1b") < estandar.index("x2b")
    assert estandar.index("bb") < estandar.index("ibb")


def test_fielding_has_no_batted_ball_divisions() -> None:
    """Los batazos son del bateador y del lanzador, no de la posición defensiva."""
    divisiones = [label for label, _ in metric_layout.divisions_for("fielding")]

    assert divisiones == ["Estándar", "Avanzado", "Receptor"]


@pytest.mark.parametrize(
    ("formula", "esperado"),
    [
        ("PA>=502", "PA ≥ 502"),
        ("BALLS_IN_PLAY>=400", "BIP ≥ 400"),
        ("TOTAL_SWINGS>=1000", "swings ≥ 1000"),
        ("", ""),
    ],
)
def test_a_threshold_reads_the_same_wherever_it_is_shown(formula: str, esperado: str) -> None:
    """El perfil y Líderes escriben el mismo umbral igual: es la misma regla, no dos."""
    assert metric_layout.pretty_qualifier(formula) == esperado


@pytest.mark.django_db
def test_the_leaders_page_groups_metrics_by_the_shared_layout() -> None:
    """La prueba de que el acuerdo se cumple de verdad, y no solo que el módulo existe.

    La página solo ofrece las divisiones que tienen tablero construido, así que hace falta un líder
    real: sin él el dropdown sale vacío y el test no probaría nada.
    """
    jugador = Player.objects.create(**_other_player(player_id=1, dgl_id="a01", full_name="Uno U"))
    metrica = Metric.objects.create(
        stat_group="batting",
        column="hr",
        abbrev="HR",
        name_es="Jonrones",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        best_career=True,
        is_active=True,
    )
    Leader.objects.create(
        metric=metrica, board=Leader.Board.BEST_CAREER, season=None, player=jugador, value=500.0, rank=1
    )

    contexto = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")

    assert "hr" in dict(metric_layout.divisions_for("batting"))["Estándar"]
    assert [division["label"] for division in contexto["divisions"]] == ["Estándar"]
