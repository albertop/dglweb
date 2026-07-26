"""Detección de debuts: la resta del universo y el cruce contra quién tiene estadísticas.

Lo que estos tests fijan es sobre todo lo que NO se hace: no se mira el país de nacimiento de la API
—la regla de autoridad lo prohíbe— y no se escribe nada en ninguna de las dos tablas. El comando
avisa; promover al jugador es del dueño, y cargarlo en el maestro es lo que apaga el aviso.
"""

from datetime import date
from typing import Any

import pytest
from django.core.management import call_command

from dglweb.players import debuts, universe
from dglweb.players.models import Player
from dglweb.stats.models import DomPlayer, IngestRun, SeasonDates
from dglweb.stats.season_window import MLB
from tests.test_players import _other_player


class _ProxyFalso:
    """Devuelve estadísticas para `con_stats` y una ficha para cualquier persona que se le pida."""

    def __init__(self, con_stats: set[int], fichas: dict[int, dict[str, Any]] | None = None) -> None:
        self.con_stats = con_stats
        self.fichas = fichas or {}
        self.pedidos: list[str] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.pedidos.append(path)
        if path == "/api/v1/stats":
            splits = [{"player": {"id": pid}} for pid in sorted(self.con_stats)]
            return {"stats": [{"splits": splits if params and params.get("group") == "hitting" else []}]}
        player_id = int(path.rsplit("/", 1)[-1])
        return {"people": [self.fichas.get(player_id, {"fullName": f"Jugador {player_id}"})]}


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 3, 25),
        season_end_date=date(2026, 10, 31),
        is_active=True,
    )


def _maestro(player_id: int, nombre: str) -> Player:
    return Player.todos.create(**_other_player(player_id=player_id, dgl_id=f"m{player_id}", full_name=nombre))


def _prospecto(player_id: int, nombre: str) -> DomPlayer:
    return DomPlayer.objects.create(player_id=player_id, full_name=nombre)


# ── La resta ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_universe_is_both_tables_and_the_pending_ones_are_the_difference(db: None) -> None:
    _maestro(1, "Ya Debutó")
    _prospecto(2, "Todavía No")

    assert universe.universe() == {1, 2}
    assert universe.not_debuted() == {2}


@pytest.mark.django_db
def test_loading_him_into_the_master_is_what_stops_the_alert(db: None) -> None:
    """El corazón del diseño: no hay janitor ni flag de «ya lo vi».

    Mientras esté en las dos tablas la resta lo excluye igual, así que el overlap —que puede durar
    meses hasta la próxima carga de `dom_players`— es inofensivo por construcción.
    """
    _prospecto(2, "Debutante D")
    assert universe.not_debuted() == {2}

    _maestro(2, "Debutante D")  # el dueño lo carga en el Backoffice

    assert universe.not_debuted() == set()
    assert DomPlayer.objects.filter(player_id=2).exists()  # sigue en la otra tabla, y no molesta


@pytest.mark.django_db
def test_a_disabled_player_still_counts_as_debuted(db: None) -> None:
    """`hidden` es de cara al público. Si contara como no-debutado, saldría como debut cada día."""
    jugador = _maestro(1, "Dado de Baja")
    _prospecto(1, "Dado de Baja")
    jugador.hidden = True
    jugador.disabled_reason = "Inscrito por error."
    jugador.save()

    assert universe.not_debuted() == set()


# ── El cruce ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_prospect_with_stats_is_a_debut(db: None) -> None:
    _prospecto(2, "Debutante D")
    proxy = _ProxyFalso({2}, {2: {"fullName": "Debutante D", "mlbDebutDate": "2026-06-01"}})

    encontrados = debuts.detect(proxy, 2026)  # type: ignore[arg-type]

    assert [(d.player_id, d.full_name, d.debut_date) for d in encontrados] == [(2, "Debutante D", "2026-06-01")]


@pytest.mark.django_db
def test_a_prospect_without_stats_is_not_a_debut(db: None) -> None:
    """Estar en un roster no es debutar: hay que haber jugado."""
    _prospecto(2, "Sigue Esperando")

    assert debuts.detect(_ProxyFalso(set()), 2026) == []  # type: ignore[arg-type]


@pytest.mark.django_db
def test_someone_outside_the_universe_is_never_a_debut(db: None) -> None:
    """La regla de autoridad: no está en ninguna de las dos tablas, así que no es asunto nuestro.

    Y no se le mira el país para decidirlo — de los ~1.300 jugadores con estadísticas de una
    temporada, unos 1.200 están fuera del universo. No son candidatos: son el resto del mundo.
    """
    proxy = _ProxyFalso({999}, {999: {"fullName": "Un Extranjero", "birthCountry": "Dominican Republic"}})

    assert debuts.detect(proxy, 2026) == []  # type: ignore[arg-type]
    assert "/api/v1/people/999" not in proxy.pedidos  # ni se le pregunta


@pytest.mark.django_db
def test_an_already_loaded_player_with_stats_is_not_reported_again(db: None) -> None:
    """El caso de todos los días: 984 dominicanos con estadísticas, ninguno es novedad."""
    _maestro(1, "Veterano V")
    proxy = _ProxyFalso({1})

    assert debuts.detect(proxy, 2026) == []  # type: ignore[arg-type]


@pytest.mark.django_db
def test_a_failure_fetching_the_name_still_reports_the_debut(db: None) -> None:
    """Perder el aviso por un timeout sería mucho peor que darlo sin nombre."""

    class _ProxyRoto(_ProxyFalso):
        def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if path.startswith("/api/v1/people/"):
                raise RuntimeError("el proxy no responde")
            return super().get(path, params)

    _prospecto(2, "Debutante D")

    encontrados = debuts.detect(_ProxyRoto({2}), 2026)  # type: ignore[arg-type]

    assert [d.player_id for d in encontrados] == [2]


# ── El comando ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_command_records_the_finding_in_the_ingest_log(temporada: SeasonDates, monkeypatch: Any) -> None:
    """La cuenta va en `rows_affected` para que se vea en el listado sin abrir el detalle."""
    _prospecto(2, "Debutante D")
    proxy = _ProxyFalso({2}, {2: {"fullName": "Debutante D", "mlbDebutDate": "2026-06-01"}})
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: proxy)

    call_command("detect_debuts", "--season", "2026")

    fila = IngestRun.objects.get(command="detect_debuts")
    assert fila.status == IngestRun.Status.SUCCESS
    assert fila.rows_affected == 1
    assert "Debutante D" in fila.detail


@pytest.mark.django_db
def test_the_command_writes_to_neither_table(temporada: SeasonDates, monkeypatch: Any) -> None:
    """Detecta y avisa. La promoción ocurre en DGL, no acá."""
    _prospecto(2, "Debutante D")
    proxy = _ProxyFalso({2})
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: proxy)

    call_command("detect_debuts", "--season", "2026")

    assert DomPlayer.objects.filter(player_id=2).exists()
    assert not Player.todos.filter(player_id=2).exists()


@pytest.mark.django_db
def test_the_command_is_gated_by_the_season(temporada: SeasonDates, monkeypatch: Any) -> None:
    """Nadie debuta en enero, y salir al proxy para confirmarlo sería tirar llamadas."""
    monkeypatch.setattr(
        "dglweb.players.management.commands.detect_debuts.build_client",
        lambda: pytest.fail("no debería consultar el proxy fuera de temporada"),
    )
    SeasonDates.objects.update(is_active=False)

    call_command("detect_debuts")

    assert IngestRun.objects.get(command="detect_debuts").status == IngestRun.Status.SKIPPED
