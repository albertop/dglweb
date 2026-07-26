"""Dar de baja a un jugador sin borrarlo — el flag `hidden` de `dgl_master`.

La baja es rara y reversible, así que no se borra la fila: se oculta. Para el sitio el jugador deja
de existir; para la tubería de datos sigue existiendo y sus estadísticas se siguen actualizando, de
modo que reactivarlo es instantáneo y no exige un backfill.

Lo que estos tests fijan es justamente lo que se olvida: que "no existe" alcance a la data DERIVADA
—liderazgos y totales de carrera— y no solo a las pantallas. Esos dos motores no pasan por el
manager de `Player`: leen las tablas de stats y agrupan por `player_id`, así que el filtro por
defecto no los cubre y hay que excluirlos a mano.
"""

from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from dglweb.players.models import Player
from dglweb.stats.career_totals import build_career_totals
from dglweb.stats.leaders import build_leaders
from dglweb.stats.models import Batting, BattingCareer, Leader, Metric
from tests.test_players import _other_player


def _player(pid: int, dgl: str, name: str, **extra: Any) -> Player:
    return Player.todos.create(**_other_player(player_id=pid, dgl_id=dgl, full_name=name, **extra))


@pytest.fixture
def trio(db: None) -> dict[str, Player]:
    """Tres bateadores con 30, 20 y 10 jonrones. El del medio es el que se da de baja."""
    jugadores = {
        "primero": _player(1, "a01", "Primero P"),
        "medio": _player(2, "b01", "Medio M"),
        "ultimo": _player(3, "c01", "Ultimo U"),
    }
    for jugador, hr in zip(jugadores.values(), (30, 20, 10), strict=True):
        Batting.objects.create(player=jugador, season=2020, stint=1, hr=hr, pa=600, ab=550, h=150)
    Metric.objects.create(
        stat_group="batting",
        column="hr",
        abbrev="HR",
        name_es="Jonrones",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        best_season=True,
        best_career=True,
        is_active=True,
    )
    return jugadores


def _ocultar(jugador: Player, motivo: str = "Inscrito por error: no es dominicano.") -> None:
    jugador.hidden = True
    jugador.disabled_reason = motivo
    jugador.save()


# ── Que desaparezca de las pantallas ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_hidden_player_is_gone_from_the_default_manager(trio: dict[str, Player]) -> None:
    """`Player.objects` es la puerta segura: lo que se escriba sin pensar ya sale filtrado."""
    _ocultar(trio["medio"])

    assert list(Player.objects.values_list("player_id", flat=True)) == [1, 3]


@pytest.mark.django_db
def test_the_pipeline_still_sees_him_through_the_explicit_manager(trio: dict[str, Player]) -> None:
    """`todos` es para la tubería: se le siguen bajando stats para que reactivarlo sea instantáneo."""
    _ocultar(trio["medio"])

    assert Player.todos.count() == 3


@pytest.mark.django_db
def test_his_profile_answers_404_and_not_a_page(trio: dict[str, Player]) -> None:
    """Sacarlo de las listas no alcanza: el enlace directo sobrevive en Google y en cualquier chat."""
    url = f"/jugador/{trio['medio'].slug}/"
    assert Client().get(url).status_code != 404  # antes de la baja sí existe

    _ocultar(trio["medio"])

    assert Client().get(url).status_code == 404


# ── Que desaparezca de lo que se CALCULA ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_leaderboards_close_the_gap_behind_him(trio: dict[str, Player]) -> None:
    """Lo que de verdad importa: los puestos de los DEMÁS quedan bien.

    Filtrarlo al leer dejaría la lista numerada 1, 3 y al tercero en un puesto que no le corresponde.
    Los liderazgos están materializados con el `rank` ya escrito, así que la exclusión tiene que
    pasar cuando se construyen.
    """
    build_leaders()
    antes = Leader.objects.filter(board="best_season", season=2020).order_by("rank")
    assert [(fila.player_id, fila.rank) for fila in antes] == [(1, 1), (2, 2), (3, 3)]

    _ocultar(trio["medio"])
    build_leaders()

    despues = Leader.objects.filter(board="best_season", season=2020).order_by("rank")
    assert [(fila.player_id, fila.rank) for fila in despues] == [(1, 1), (3, 2)]


@pytest.mark.django_db
def test_he_is_left_out_of_the_career_totals(trio: dict[str, Player]) -> None:
    """Los totales de carrera alimentan los liderazgos de por vida y el perfil."""
    _ocultar(trio["medio"])
    build_career_totals()

    assert set(BattingCareer.objects.values_list("player_id", flat=True)) == {1, 3}


@pytest.mark.django_db
def test_bringing_him_back_puts_him_back_in_the_rankings(trio: dict[str, Player]) -> None:
    """La baja es reversible por diseño: no se borró nada, así que volver es solo apagar el flag."""
    _ocultar(trio["medio"])
    build_leaders()

    trio["medio"].hidden = False
    trio["medio"].save()
    build_leaders()

    vuelto = Leader.objects.filter(board="best_season", season=2020).order_by("rank")
    assert [(fila.player_id, fila.rank) for fila in vuelto] == [(1, 1), (2, 2), (3, 3)]


# ── Las reglas de la propia baja ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_hiding_a_player_requires_saying_why(trio: dict[str, Player]) -> None:
    """Sin el motivo, en un año nadie va a saber por qué falta ese jugador — ni si puede volver."""
    trio["medio"].hidden = True

    with pytest.raises(ValidationError) as error:
        trio["medio"].full_clean()

    assert "disabled_reason" in error.value.message_dict


@pytest.mark.django_db
def test_a_visible_player_needs_no_reason(trio: dict[str, Player]) -> None:
    """El motivo es obligatorio solo cuando hay algo que explicar."""
    trio["medio"].full_clean()


@pytest.mark.django_db
def test_toggling_the_flag_rebuilds_what_is_derived(
    trio: dict[str, Player], monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """Que no haya que acordarse de correr nada: sin esto la baja no se nota hasta el otro día.

    Se dispara al COMMIT, no al `save()`: si el guardado se revierte no hay nada que reconstruir. Por
    eso hace falta el `capture` — en un test todo vive dentro de una transacción que nunca commitea.
    """
    from dglweb.stats import rebuilds

    lanzados: list[tuple[str, ...]] = []

    def espiar(nombres: tuple[str, ...]) -> str:
        lanzados.append(tuple(nombres))
        return ""

    monkeypatch.setattr(rebuilds, "run_in_background", espiar)

    with django_capture_on_commit_callbacks(execute=True):
        _ocultar(trio["medio"])

    assert lanzados == [rebuilds.DERIVED]


@pytest.mark.django_db
def test_saving_a_player_for_any_other_reason_rebuilds_nothing(
    trio: dict[str, Player], monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    """El import diario del maestro guarda miles de filas; reconstruir en cada una sería absurdo."""
    from dglweb.stats import rebuilds

    def reventar(nombres: tuple[str, ...]) -> str:
        pytest.fail("no cambió la visibilidad")

    monkeypatch.setattr(rebuilds, "run_in_background", reventar)

    with django_capture_on_commit_callbacks(execute=True):
        trio["medio"].nickname = "El Medio"
        trio["medio"].save()


@pytest.mark.django_db
def test_the_backoffice_can_still_edit_him_to_bring_him_back(trio: dict[str, Player]) -> None:
    """El bug que casi se cuela: sin esto la baja era irreversible desde la interfaz.

    Wagtail resuelve la pantalla de edición con el `_default_manager` de Django. Si ese es el
    filtrado, editar a un jugador oculto da 404 — o sea, no hay forma de volver a habilitarlo.
    """
    from django.contrib.auth import get_user_model

    _ocultar(trio["medio"])
    client = Client()
    client.force_login(get_user_model().objects.create_superuser("jefa", "jefa@dgl.do", "x"))

    url = f"/cms/snippets/players/player/edit/{trio['medio'].pk}/"
    assert client.get(url).status_code == 200
