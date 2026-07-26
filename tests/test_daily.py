"""La actuación de la jornada: cómo se puntúa, cómo se guarda y qué se poda.

Lo que más importa acá es que el ORDEN sea defendible. Un widget que dice «destacados» y pone arriba
al que menos hizo no es un bug de programación, es una afirmación falsa en la portada — así que la
mayoría de estos tests comparan dos jornadas y exigen que gane la que cualquiera diría que es mejor.
"""

from datetime import date
from typing import Any

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats import daily
from dglweb.stats.models import DailyStandout, IngestRun, SeasonDates
from dglweb.stats.season_window import MLB
from tests.test_players import _other_player

AYER = date(2026, 7, 25)


def _bateo(**stat: Any) -> dict[str, Any]:
    base = {"AB": 0, "H": 0, "X2B": 0, "X3B": 0, "HR": 0, "BB": 0, "IBB": 0, "HBP": 0, "K": 0, "SB": 0, "CS": 0}
    return base | stat


def _pitcheo(**stat: Any) -> dict[str, Any]:
    return {"outsPitched": 0, "K": 0, "H": 0, "R": 0, "HR": 0, "ER": 0, "IP": "0.0"} | stat


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


# ── El orden de los bateadores ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_homer_beats_a_single(db: None) -> None:
    """Lo mínimo que la fórmula tiene que respetar, y lo que un orden por hits no respetaría."""
    jonron = daily.valor_de_bateo(_bateo(AB=4, H=1, HR=1))
    sencillo = daily.valor_de_bateo(_bateo(AB=4, H=1))

    assert jonron > sencillo


@pytest.mark.django_db
def test_three_singles_beat_one_homer_in_four_at_bats(db: None) -> None:
    """No es obvio, y es justo lo que los pesos lineales resuelven bien.

    Tres sencillos valen 1,40 carreras contra 1,39 del jonrón: casi empate, con ventaja mínima para
    quien llegó tres veces a base. Ordenar por jonrones o por total de bases diría otra cosa.
    """
    tres_sencillos = daily.valor_de_bateo(_bateo(AB=4, H=3))
    un_jonron = daily.valor_de_bateo(_bateo(AB=4, H=1, HR=1))

    assert tres_sencillos > un_jonron


@pytest.mark.django_db
def test_a_walk_counts_and_an_out_hurts(db: None) -> None:
    """Un 1-3 con boleto vale más que un 1-4, aunque la línea de hits sea la misma.

    Es lo que separa esta fórmula de ordenar por promedio: el boleto es una vez que no falló.
    """
    con_boleto = daily.valor_de_bateo(_bateo(AB=3, H=1, BB=1))
    sin_boleto = daily.valor_de_bateo(_bateo(AB=4, H=1))

    assert con_boleto > sin_boleto


@pytest.mark.django_db
def test_an_intentional_walk_is_worth_less_than_an_earned_one(db: None) -> None:
    """La matriz los distingue y el cálculo también: el intencional no lo ganó el bateador."""
    ganado = daily.valor_de_bateo(_bateo(BB=1))
    regalado = daily.valor_de_bateo(_bateo(BB=1, IBB=1))

    assert ganado > regalado


@pytest.mark.django_db
def test_an_oh_for_four_is_negative(db: None) -> None:
    """Una mala jornada tiene que hundir, no quedar en cero: así el orden separa de verdad."""
    assert daily.valor_de_bateo(_bateo(AB=4, K=2)) < 0


@pytest.mark.django_db
def test_a_sacrifice_counts_as_an_out_even_though_it_is_not_an_at_bat(db: None) -> None:
    """`AB` no incluye sacrificios, así que si no se suman aparte el out desaparece del cálculo."""
    con_sacrificio = daily.valor_de_bateo(_bateo(AB=3, H=1, SF=1))
    sin_nada = daily.valor_de_bateo(_bateo(AB=3, H=1))

    assert con_sacrificio < sin_nada


# ── El orden de los lanzadores ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_seven_inning_start_beats_a_clean_inning_of_relief(db: None) -> None:
    """El problema que Game Score resuelve solo: los outs pesan.

    Siete entradas de una carrera (74) contra un inning perfecto con un ponche (47). Ordenar por
    efectividad del día pondría al relevista arriba con su 0.00.
    """
    apertura = daily.game_score(_pitcheo(outsPitched=21, K=6, H=4, R=1))
    relevo = daily.game_score(_pitcheo(outsPitched=3, K=1, H=0, R=0))

    assert apertura > relevo


@pytest.mark.django_db
def test_a_home_run_costs_more_than_a_hit(db: None) -> None:
    con_jonron = daily.game_score(_pitcheo(outsPitched=18, H=3, R=1, HR=1))
    sin_jonron = daily.game_score(_pitcheo(outsPitched=18, H=3, R=1))

    assert con_jonron < sin_jonron


# ── Cómo se lee ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_line_only_names_what_happened(db: None) -> None:
    """«3-4, 2B, HR, 4 CI» y no «3-4, 0 3B, 1 HR, 0 SB»: un cero ocupa lugar y no dice nada."""
    linea = daily.linea_de_bateo(_bateo(AB=4, H=3, X2B=1, HR=1, RBI=4, R=2))

    assert linea == "3-4, 2B, HR, 4 CI, 2 CA"


@pytest.mark.django_db
def test_two_of_the_same_are_counted(db: None) -> None:
    assert "2 HR" in daily.linea_de_bateo(_bateo(AB=4, H=2, HR=2))


@pytest.mark.django_db
def test_the_pitching_line_leads_with_innings_and_flags_the_decision(db: None) -> None:
    """Las entradas primero porque son lo que sitúa la actuación; la decisión al final."""
    assert daily.linea_de_pitcheo(_pitcheo(IP="7.0", K=9, ER=0, W=1)) == "7.0 IP, 9 K, 0 CL, (G)"
    assert "(S)" in daily.linea_de_pitcheo(_pitcheo(IP="1.0", SV=1))


# ── La tabla ────────────────────────────────────────────────────────────────────────────────────


def _jugador(pid: int) -> Player:
    return Player.todos.create(**_other_player(player_id=pid, dgl_id=f"j{pid}", full_name=f"Jugador {pid}"))


@pytest.mark.django_db
def test_saving_a_day_twice_does_not_duplicate_it(temporada: SeasonDates) -> None:
    """Se borra y reescribe la jornada entera: o se tiene completa o no se tiene.

    Con upsert fila por fila, una segunda corrida podría dejar mezclados los resultados de dos
    consultas distintas al proxy — y media jornada de cada una no es ninguna jornada.
    """
    _jugador(1)
    listas = {"bateo": [daily.Actuacion(1, "Jugador 1", "SDN", 2.0, "3-4")], "pitcheo": []}

    daily.guardar(AYER, listas)
    daily.guardar(AYER, listas)

    assert DailyStandout.objects.filter(fecha=AYER).count() == 1


@pytest.mark.django_db
def test_a_player_outside_the_master_is_skipped_instead_of_breaking_the_write(temporada: SeasonDates) -> None:
    """La FK reventaría, y una jornada no puede perderse por un id que no reconocemos."""
    _jugador(1)
    listas = {
        "bateo": [
            daily.Actuacion(1, "Conocido", "SDN", 2.0, "3-4"),
            daily.Actuacion(999, "Desconocido", "NYA", 3.0, "4-4"),
        ],
        "pitcheo": [],
    }

    assert daily.guardar(AYER, listas) == 1


@pytest.mark.django_db
def test_pruning_keeps_the_current_season_whole_and_drops_the_rest(temporada: SeasonDates) -> None:
    """Por temporada y no por antigüedad: así el receso del Juego de Estrellas nunca deja la tabla vacía."""
    jugador = _jugador(1)
    for fecha in (date(2025, 9, 1), date(2026, 4, 1), date(2026, 7, 25)):
        DailyStandout.objects.create(
            fecha=fecha, grupo=DailyStandout.Grupo.BATEO, player=jugador, linea="1-4", valor=0.1
        )

    borradas = daily.podar(2026)

    assert borradas == 1
    assert set(DailyStandout.objects.values_list("fecha", flat=True)) == {date(2026, 4, 1), date(2026, 7, 25)}


@pytest.mark.django_db
def test_without_an_active_season_nothing_is_pruned(temporada: SeasonDates) -> None:
    """Una tabla con datos viejos es un problema menor que una vacía por un despiste de configuración."""
    jugador = _jugador(1)
    DailyStandout.objects.create(
        fecha=date(2020, 5, 5), grupo=DailyStandout.Grupo.BATEO, player=jugador, linea="1-4", valor=0.1
    )

    assert daily.podar(None) == 0
    assert DailyStandout.objects.count() == 1


# ── El comando ──────────────────────────────────────────────────────────────────────────────────


class _ProxyFalso:
    """Devuelve una jornada con un bateador y un lanzador, más los códigos de equipo."""

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if path == "/api/v1/teams":
            return {"teams": [{"id": 135, "teamCode": "sdn"}]}
        bateando = (params or {}).get("group") == "hitting"
        stat = _bateo(AB=4, H=3, X2B=1, HR=1, RBI=4) if bateando else _pitcheo(outsPitched=21, K=9, IP="7.0")
        return {
            "stats": [
                {"splits": [{"player": {"id": 1, "fullName": "Jugador 1"}, "team": {"id": 135}, "stat": stat}]}
            ]
        }


@pytest.mark.django_db
def test_the_command_stores_the_day_and_records_it(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    _jugador(1)
    monkeypatch.setattr(
        "dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _ProxyFalso()
    )

    call_command("build_daily_standouts", "--fecha", "2026-07-25")

    assert DailyStandout.objects.filter(fecha=AYER).count() == 2  # uno de bateo, uno de pitcheo
    fila = IngestRun.objects.get(command="build_daily_standouts")
    assert fila.status == IngestRun.Status.SUCCESS
    assert "1 bateadores, 1 lanzadores" in fila.detail


@pytest.mark.django_db
def test_a_day_without_games_is_not_a_failure(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """El receso del Juego de Estrellas y cualquier día libre: cero filas, y todo en orden."""

    class _Vacio:
        def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {"teams": []} if path == "/api/v1/teams" else {"stats": [{"splits": []}]}

    monkeypatch.setattr(
        "dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _Vacio()
    )

    call_command("build_daily_standouts", "--fecha", "2026-07-14")

    assert IngestRun.objects.get(command="build_daily_standouts").status == IngestRun.Status.SUCCESS
