"""Los dominicanos que están en el top de las mayores.

Lo que se protege acá es sobre todo lo que NO debe pasar: que alguien entre por parecer dominicano en
vez de estarlo, que se quede pegado un puesto que ya no es cierto, y que el widget dependa de tocar
código para encender una métrica.
"""

from typing import Any

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats import mlb_leaders
from dglweb.stats.models import IngestRun, Metric, MlbLeader, SeasonDates
from dglweb.stats.season_window import MLB
from tests.test_players import _other_player


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    from datetime import date

    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


@pytest.fixture
def hr(db: None) -> Metric:
    return Metric.objects.create(
        stat_group="batting", column="hr", abbrev="HR", name_es="Jonrones", kind="ACU", visible_en_widget_lideres=True
    )


def _jugador(pid: int, nombre: str) -> Player:
    return Player.todos.create(**_other_player(player_id=pid, dgl_id=f"j{pid}", full_name=nombre))


class _Proxy:
    """Un ranking a la medida. `filas` es (categoría, [(rank, player_id, valor)])."""

    def __init__(self, *filas: tuple[str, list[tuple[int, int, str]]]) -> None:
        self.filas = filas
        self.llamadas: list[dict[str, Any]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if path == "/api/v1/teams":
            return {"teams": [{"id": 117, "teamCode": "hou"}]}
        self.llamadas.append(params or {})
        pedidas = str((params or {}).get("leaderCategories") or "").split(",")
        return {
            "leagueLeaders": [
                {
                    "leaderCategory": cat,
                    "leaders": [
                        {"rank": r, "value": v, "person": {"id": pid}, "team": {"id": 117}} for r, pid, v in hojas
                    ],
                }
                for cat, hojas in self.filas
                if cat in pedidas
            ]
        }


def _traer(proxy: _Proxy, universo: set[int]) -> list[mlb_leaders.Puesto]:
    return mlb_leaders.traer(proxy, 2026, universo)  # type: ignore[arg-type]


# ── Quién entra ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_only_the_master_decides_who_is_dominican(temporada: SeasonDates) -> None:
    """Regla de autoridad: manda `dgl_master`, nunca el país que devuelva la API."""
    proxy = _Proxy(("homeRuns", [(1, 111, "40"), (2, 999, "38")]))

    puestos = _traer(proxy, {111})

    assert [p.player_id for p in puestos] == [111]


@pytest.mark.django_db
def test_a_tie_for_tenth_keeps_both(temporada: SeasonDates, hr: Metric) -> None:
    """Pedir diez puede devolver trece: a los empatados en el décimo puesto les toca igual."""
    _jugador(111, "Uno")
    _jugador(222, "Dos")
    proxy = _Proxy(("homeRuns", [(10, 111, "25"), (10, 222, "25")]))

    mlb_leaders.guardar(2026, _traer(proxy, {111, 222}), {})

    assert list(MlbLeader.objects.values_list("rank", flat=True)) == [10, 10]


@pytest.mark.django_db
def test_a_category_the_catalog_does_not_know_is_dropped(temporada: SeasonDates) -> None:
    """El API normaliza nombres. Si alguno cambia, se ignora en vez de guardarse sin métrica."""
    proxy = _Proxy(("homeRuns", [(1, 111, "40")]), ("inventadaPorMlb", [(1, 111, "9")]))

    assert {p.categoria for p in _traer(proxy, {111})} == {"homeRuns"}


# ── Que no se quede pegado ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_dropping_out_of_the_top_removes_the_row(temporada: SeasonDates, hr: Metric) -> None:
    """Lo importante de esta tabla: es una foto, no un archivo.

    Con upsert, quien cayó del top diez se quedaría ahí para siempre luciendo un puesto que ya no
    tiene — y una portada que anuncia un liderazgo perdido es peor que una que no anuncia nada.
    """
    _jugador(111, "Se queda")
    _jugador(222, "Se cae")
    mlb_leaders.guardar(2026, _traer(_Proxy(("homeRuns", [(1, 111, "40"), (2, 222, "38")])), {111, 222}), {})

    mlb_leaders.guardar(2026, _traer(_Proxy(("homeRuns", [(1, 111, "41")])), {111, 222}), {})

    assert list(MlbLeader.objects.values_list("player_id", "valor")) == [(111, "41")]


@pytest.mark.django_db
def test_a_player_outside_the_master_never_reaches_the_write(temporada: SeasonDates, hr: Metric) -> None:
    """La FK reventaría, y un id desconocido no puede tumbar el refresco entero."""
    _jugador(111, "Conocido")
    puestos = _traer(_Proxy(("homeRuns", [(1, 111, "40"), (2, 999, "38")])), {111, 999})

    assert mlb_leaders.guardar(2026, puestos, {}) == 1


# ── El costo ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_whole_catalog_costs_two_calls(temporada: SeasonDates) -> None:
    """Una llamada por oficio, no una por categoría.

    Es lo que hace viable el refresco horario: pedir las veintitrés categorías cuesta lo mismo que
    pedir cinco. Si esto se rompiera, la hora pasaría a costar veintitrés llamadas.
    """
    proxy = _Proxy()

    _traer(proxy, set())

    assert len(proxy.llamadas) == 2
    assert {str(ll.get("statGroup")) for ll in proxy.llamadas} == {"hitting", "pitching"}


@pytest.mark.django_db
def test_the_stat_group_is_always_sent(temporada: SeasonDates) -> None:
    """Sin `statGroup`, cada categoría vuelve tres veces —una por oficio— con combinaciones absurdas
    como «battingAverage / pitching». Está medido contra el proxy."""
    proxy = _Proxy()

    _traer(proxy, set())

    assert all(ll.get("statGroup") for ll in proxy.llamadas)


@pytest.mark.django_db
def test_only_the_first_ten_are_asked_for(temporada: SeasonDates) -> None:
    """Estar entre los diez primeros de MLB es la noticia; el puesto 40 no lo es."""
    proxy = _Proxy()

    _traer(proxy, set())

    assert {ll.get("limit") for ll in proxy.llamadas} == {10}


@pytest.mark.django_db
def test_fielding_and_catching_never_enter(temporada: SeasonDates) -> None:
    """El widget es de bateo y pitcheo. Fildeo y receptoría quedan fuera por decisión del dueño.

    Se verifica en el catálogo y no en la respuesta porque es estructural: solo se piden esos dos
    oficios, así que una categoría de fildeo no tiene por dónde entrar aunque MLB la publique.
    """
    assert {grupo for grupo, _ in mlb_leaders.CATEGORIAS.values()} == {"batting", "pitching"}
    assert "catching" not in mlb_leaders._OFICIOS.values()


# ── El interruptor del Backoffice ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_turning_a_metric_off_does_not_require_refetching(temporada: SeasonDates, hr: Metric) -> None:
    """Se guardan TODAS las categorías y el flag decide cuáles se muestran.

    Por eso encender una métrica en el Backoffice la enseña al instante, en vez de esperar al
    refresco de la hora siguiente. Y cuesta lo mismo, porque el precio es por oficio.
    """
    _jugador(111, "Uno")
    mlb_leaders.guardar(2026, _traer(_Proxy(("homeRuns", [(1, 111, "40")])), {111}), {})

    Metric.objects.update(visible_en_widget_lideres=False)

    assert MlbLeader.objects.count() == 1  # la fila sigue ahí
    assert not MlbLeader.objects.filter(metric__visible_en_widget_lideres=True).exists()


# ── El comando ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_command_stores_the_snapshot_and_records_it(
    temporada: SeasonDates, hr: Metric, monkeypatch: pytest.MonkeyPatch
) -> None:
    _jugador(111, "Junior Caminero")
    proxy = _Proxy(("homeRuns", [(6, 111, "29")]))
    monkeypatch.setattr("dglweb.stats.management.commands.build_mlb_leaders.build_client", lambda: proxy)

    call_command("build_mlb_leaders")

    fila = MlbLeader.objects.get()
    assert (fila.rank, fila.valor, fila.team, fila.season) == (6, "29", "HOU", 2026)
    assert IngestRun.objects.get(command="build_mlb_leaders").status == IngestRun.Status.SUCCESS


@pytest.mark.django_db
def test_without_an_active_season_nothing_is_touched(
    temporada: SeasonDates, hr: Metric, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adivinar el año del reloj podría reemplazar una tabla buena por una vacía."""
    _jugador(111, "Uno")
    mlb_leaders.guardar(2026, _traer(_Proxy(("homeRuns", [(1, 111, "40")])), {111}), {})
    SeasonDates.objects.update(is_active=False)
    monkeypatch.setattr("dglweb.stats.management.commands.build_mlb_leaders.build_client", lambda: _Proxy())

    call_command("build_mlb_leaders", "--force")

    assert MlbLeader.objects.count() == 1
