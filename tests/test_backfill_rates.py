"""`backfill_batting_rates`: la herramienta que reescribe columnas derivadas en masa.

Es idempotente por diseño, pero también es escritura masiva sobre las tablas de stats. Una
herramienta de reparación tiene que ser más confiable que el bug que arregla, así que se prueba
qué escribe, qué NO escribe, y que no se coma el último lote.
"""

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats.derive import batted_ball_coefficients, derived_rates
from dglweb.stats.management.commands.backfill_batting_rates import _BATCH, backfill
from dglweb.stats.models import Batting, BattingPost, Pitching, PitchingPost
from tests.test_players import _other_player


def _player(pid: int = 1, dgl: str = "a01") -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl, full_name="Un Jugador"))


@pytest.mark.django_db
def test_recomputes_the_derived_columns_from_the_stored_counts() -> None:
    player = _player()
    # avg guardado a propósito mal: el backfill debe corregirlo desde h/ab.
    Batting.objects.create(player=player, season=2019, stint=1, h=90, ab=300, avg=0.999)

    assert backfill(Batting, derived_rates) == 1

    row = Batting.objects.get()
    assert row.avg == pytest.approx(0.300)


@pytest.mark.django_db
def test_leaves_the_counting_columns_untouched() -> None:
    """Solo reescribe lo derivado: si tocara los conteos, estaría inventando datos de origen."""
    player = _player()
    Batting.objects.create(player=player, season=2019, stint=1, h=90, ab=300, hr=12, pa=330)

    backfill(Batting, derived_rates)

    row = Batting.objects.get()
    assert (row.h, row.ab, row.hr, row.pa) == (90, 300, 12, 330)


@pytest.mark.django_db
def test_pitching_only_recomputes_the_batted_ball_coefficients() -> None:
    """ERA, WHIP y FIP vienen mapeados de la fuente. Correr las fórmulas de bateo sobre la línea de
    un lanzador las destruiría, así que pitcheo usa su propia función derivadora."""
    player = _player()
    Pitching.objects.create(
        player=player,
        season=2019,
        stint=1,
        era=2.50,
        whip=1.05,
        outs=600,
        ground_outs=100,
        ground_hits=20,
        fly_outs=50,
        fly_hits=10,
        balls_in_play=200,
    )

    backfill(Pitching, batted_ball_coefficients)

    row = Pitching.objects.get()
    assert row.era == 2.50 and row.whip == 1.05  # intactas
    assert row.gb_pct == pytest.approx(120 / 200)  # (100+20)/200


@pytest.mark.django_db
def test_empty_table_returns_zero() -> None:
    assert backfill(Batting, derived_rates) == 0


@pytest.mark.django_db
def test_persists_a_final_partial_batch() -> None:
    """El lote final es más chico que `_BATCH`: si se escribiera solo al llenarse, se perdería."""
    player = _player()
    rows = [Batting(player=player, season=1990 + n, stint=1, h=30, ab=100) for n in range(5)]
    Batting.objects.bulk_create(rows)
    assert len(rows) < _BATCH

    assert backfill(Batting, derived_rates) == 5
    assert Batting.objects.filter(avg__isnull=True).count() == 0


@pytest.mark.django_db
def test_only_flag_touches_a_single_table() -> None:
    player = _player()
    Batting.objects.create(player=player, season=2019, stint=1, h=90, ab=300, avg=0.999)
    BattingPost.objects.create(player=player, season=2019, round="WS", h=5, ab=20, avg=0.999)

    call_command("backfill_batting_rates", "--only", "batting")

    assert Batting.objects.get().avg == pytest.approx(0.300)
    assert BattingPost.objects.get().avg == 0.999  # sin tocar


@pytest.mark.django_db
def test_running_it_twice_changes_nothing() -> None:
    player = _player()
    Batting.objects.create(player=player, season=2019, stint=1, h=90, ab=300)
    backfill(Batting, derived_rates)
    first = Batting.objects.get().avg

    backfill(Batting, derived_rates)

    assert Batting.objects.get().avg == first


@pytest.mark.django_db
def test_command_covers_every_table_by_default() -> None:
    player = _player()
    Batting.objects.create(player=player, season=2019, stint=1, h=90, ab=300, avg=0.999)
    BattingPost.objects.create(player=player, season=2019, round="WS", h=5, ab=20, avg=0.999)
    # `ground_hits` explícito: sin él `_sum` propaga NULL y el coeficiente sale None, que es
    # justamente la regla NULL-sobre-0 del módulo.
    Pitching.objects.create(player=player, season=2019, stint=1, balls_in_play=200, ground_outs=120, ground_hits=0)
    PitchingPost.objects.create(player=player, season=2019, round="WS", balls_in_play=20, ground_outs=12, ground_hits=0)

    call_command("backfill_batting_rates")

    assert Batting.objects.get().avg == pytest.approx(0.300)
    assert BattingPost.objects.get().avg == pytest.approx(0.250)
    assert Pitching.objects.get().gb_pct == pytest.approx(0.6)
    assert PitchingPost.objects.get().gb_pct == pytest.approx(0.6)
