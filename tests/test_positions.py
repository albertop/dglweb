"""La posición del maestro contra la que dicen las estadísticas.

`pos` es la única columna del maestro que envejece sola: la fecha de nacimiento no cambia y la
posición sí, varias veces por carrera. Lo que se prueba acá es sobre todo lo que NO debe pasar —
mover a alguien por ocho entradas, o pisar un rol que el dueño puso a mano.
"""

import pytest
from django.core.management import call_command

from dglweb.players import positions
from dglweb.players.models import Player
from dglweb.stats.models import Fielding, Pitching
from tests.test_players import _other_player

HOY = 2026  # la última temporada con fildeo en los datos de cada test


def _jugador(pid: int, nombre: str, pos: str) -> Player:
    return Player.todos.create(**_other_player(player_id=pid, dgl_id=f"p{pid}", full_name=nombre, pos=pos))


def _fildeo(jugador: Player, season: int, pos: str, entradas: float) -> None:
    Fielding.objects.create(player=jugador, season=season, team="BOS", pos=pos, innings_outs=int(entradas * 3))


def _pitcheo(jugador: Player, season: int, juegos: int, aperturas: int) -> None:
    Pitching.objects.create(player=jugador, season=season, stint=1, team="BOS", g=juegos, gs=aperturas)


# ── Qué juega hoy ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_position_with_the_most_innings_wins_not_the_most_games() -> None:
    """Un cambio defensivo de una entrada cuenta un juego igual que una novena completa.

    Por eso se miden entradas: si se contaran juegos, veinte apariciones de un inning en el jardín
    pesarían más que diez partidos enteros en el campocorto.
    """
    jugador = _jugador(1, "Un Jugador", "LF")
    _fildeo(jugador, HOY, "SS", 90)
    _fildeo(jugador, HOY, "LF", 20)

    assert [(d.actual, d.sugerida) for d in positions.discrepancias()] == [("LF", "SS")]


@pytest.mark.django_db
def test_the_recent_seasons_beat_the_whole_career() -> None:
    """La pregunta es qué juega HOY, no qué jugó más veces.

    Caso real de la base: Jorge Polanco tiene más entradas de campocorto en su carrera y lleva tres
    años en segunda. Con el total de carrera seguiría diciendo SS durante años.
    """
    jugador = _jugador(2, "Jorge Polanco", "SS")
    _fildeo(jugador, 2019, "SS", 2000)  # fuera de la ventana
    _fildeo(jugador, HOY, "2B", 400)

    assert [d.sugerida for d in positions.discrepancias()] == ["2B"]


@pytest.mark.django_db
def test_a_retired_player_is_judged_by_his_whole_career() -> None:
    """Quien no jugó en la ventana no tiene «hoy». Su carrera ya no va a cambiar."""
    jugador = _jugador(3, "Un Retirado", "1B")
    _fildeo(jugador, 2005, "RF", 3000)  # y nada después: no tiene «hoy»

    # Otro jugador en activo, solo para que la ventana no se calcule sobre 2005.
    _fildeo(_jugador(4, "En Activo", "SS"), HOY, "SS", 500)

    cambio = next(d for d in positions.discrepancias() if d.player_id == 3)
    assert cambio.sugerida == "RF"
    assert cambio.fuente == "carrera"


# ── Los lanzadores ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_more_than_half_his_games_started_makes_him_a_starter() -> None:
    jugador = _jugador(5, "Un Abridor", "P")
    _fildeo(jugador, HOY, "P", 180)
    _pitcheo(jugador, HOY, juegos=30, aperturas=28)

    cambio = positions.discrepancias()[0]
    assert cambio.sugerida == "SP"
    assert "28/30" in cambio.detalle


@pytest.mark.django_db
def test_exactly_half_is_not_enough_to_be_a_starter() -> None:
    """El corte es «más de la mitad». Un abridor-relevista a partes iguales cuenta como relevista."""
    jugador = _jugador(6, "Un Híbrido", "P")
    _fildeo(jugador, HOY, "P", 100)
    _pitcheo(jugador, HOY, juegos=20, aperturas=10)

    assert positions.discrepancias()[0].sugerida == "RP"


@pytest.mark.django_db
def test_a_pitcher_is_never_dropped_for_pitching_too_few_innings() -> None:
    """El mínimo de entradas es para los de posición, no para los lanzadores.

    Un relevista novato con cinco entradas ES un relevista, y su `GS/G` ya lo dice. Aplicarle el
    umbral lo dejaría con la posición genérica «P» para siempre — que es justo lo que hay que curar:
    son 30 casos en la base real.
    """
    jugador = _jugador(7, "Un Novato", "P")
    _fildeo(jugador, HOY, "P", 5)
    _pitcheo(jugador, HOY, juegos=4, aperturas=0)

    assert positions.discrepancias()[0].sugerida == "RP"


# ── Lo que no se toca ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rol", sorted(positions.ROLES))
@pytest.mark.django_db
def test_a_role_is_never_overwritten_by_a_fielding_position(rol: str) -> None:
    """`PH`, `PR`, `DH` y `OF` no son posiciones: son roles, y alguien los puso a propósito.

    Un bateador emergente de carrera con entradas sueltas en el jardín no es un jardinero. Son 71
    jugadores del maestro y la decisión de respetarlos es del dueño.
    """
    jugador = _jugador(8, "Con Rol", rol)
    _fildeo(jugador, HOY, "LF", 500)

    assert positions.discrepancias() == []


@pytest.mark.django_db
def test_a_thin_sample_does_not_move_a_position_player() -> None:
    """Ocho entradas en el jardín derecho no convierten a nadie en jardinero derecho."""
    jugador = _jugador(9, "Poco Fildeo", "LF")
    _fildeo(jugador, HOY, "RF", 8)

    assert positions.discrepancias() == []
    assert positions.discrepancias(min_entradas=5)[0].sugerida == "RF"  # con otro umbral, sí


@pytest.mark.django_db
def test_the_designated_hitter_row_is_not_a_position() -> None:
    """`DH` viene como fila de fildeo —1.077 en la base— y contarla haría «jugar de DH» a alguien."""
    jugador = _jugador(10, "Un Designado", "1B")
    _fildeo(jugador, HOY, "DH", 900)
    _fildeo(jugador, HOY, "LF", 100)

    assert positions.discrepancias()[0].sugerida == "LF"


@pytest.mark.django_db
def test_a_player_already_in_the_right_position_is_not_reported() -> None:
    """El reporte es una lista de trabajo: lo que ya está bien no aparece."""
    jugador = _jugador(11, "Correcto", "SS")
    _fildeo(jugador, HOY, "SS", 900)

    assert positions.discrepancias() == []


# ── El comando ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_command_reports_without_touching_the_master() -> None:
    """`dgl_master` es la tabla del dueño: no se escribe sin que lo pida.

    Un proceso semanal que sobrescriba por su cuenta puede pisar una corrección hecha a mano, y el
    dueño se entera cuando el dato ya se perdió.
    """
    jugador = _jugador(12, "Un Jugador", "LF")
    _fildeo(jugador, HOY, "SS", 900)

    call_command("check_positions")

    assert Player.todos.get(player_id=12).pos == "LF"


@pytest.mark.django_db
def test_applying_writes_the_suggested_position() -> None:
    jugador = _jugador(13, "Un Jugador", "LF")
    _fildeo(jugador, HOY, "SS", 900)

    call_command("check_positions", "--aplicar")

    assert Player.todos.get(player_id=13).pos == "SS"


@pytest.mark.django_db
def test_the_run_leaves_every_change_in_the_log() -> None:
    """El aviso de Telegram lleva la cuenta; el detalle tiene que estar en algún sitio consultable."""
    from dglweb.stats.models import IngestRun

    jugador = _jugador(14, "Un Jugador", "LF")
    _fildeo(jugador, HOY, "SS", 900)

    call_command("check_positions")

    fila = IngestRun.objects.get(command="check_positions")
    assert fila.rows_affected == 1
    assert "LF → SS" in fila.detail
