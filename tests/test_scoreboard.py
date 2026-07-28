"""La pizarra: qué se muestra, a quién se marca y qué pasa cuando el proxy no contesta.

Dos cosas son las que de verdad importan acá. Una es que la portada nunca se rompa ni mienta —un
marcador inventado es peor que ninguno—, y la otra es que no se marque como dominicano a nadie que no
lo sea: la autoridad es `dgl_master`, nunca el país que devuelva la API.
"""

from datetime import date
from typing import Any

import pytest
from django.core.cache import cache

from dglweb.mlb.client import MlbProxyError
from dglweb.players.models import Player
from dglweb.stats import scoreboard
from tests.test_players import _other_player

HOY = date(2026, 7, 26)
AYER = date(2026, 7, 25)


@pytest.fixture(autouse=True)
def _hoy_fijo(monkeypatch: pytest.MonkeyPatch) -> None:
    """La tira es «ayer y hoy». Sin fijar el día, estos tests solo pasarían el 26 de julio de 2026."""
    from django.utils import timezone

    monkeypatch.setattr(timezone, "localdate", lambda: HOY)


def _juego(
    *,
    estado: str = "Final",
    detallado: str = "Final",
    visitante: tuple[int, str, int | None] = (135, "sdn", 7),
    local: tuple[int, str, int | None] = (146, "mia", 2),
    inning: int = 9,
    mitad: str = "Bottom",
    alineacion: dict[str, list[int]] | None = None,
    abridores: dict[str, int] | None = None,
    hora: str = "2026-07-26T23:10:00Z",
    pk: int = 800001,
    doble: str = "N",
) -> dict[str, Any]:
    def lado(datos: tuple[int, str, int | None], cual: str) -> dict[str, Any]:
        equipo_id, codigo, carreras = datos
        salida: dict[str, Any] = {
            "team": {"id": equipo_id, "teamCode": codigo, "teamName": codigo.upper()},
            "score": carreras,
        }
        if (abridores or {}).get(cual) is not None:
            salida["probablePitcher"] = {"id": abridores[cual]}  # type: ignore[index]
        return salida

    return {
        "gamePk": pk,
        "doubleHeader": doble,
        "gameDate": hora,
        "status": {"abstractGameState": estado, "detailedState": detallado},
        "linescore": {"currentInning": inning, "inningState": mitad},
        "teams": {"away": lado(visitante, "away"), "home": lado(local, "home")},
        "lineups": {
            "awayPlayers": [{"id": pid} for pid in (alineacion or {}).get("away", [])],
            "homePlayers": [{"id": pid} for pid in (alineacion or {}).get("home", [])],
        },
    }


class _Proxy:
    """Un calendario y unas estadísticas a la medida de cada test.

    `juegos` va por día porque el banner pide un rango —ayer y hoy— en una sola llamada; el que no se
    declara sencillamente no tuvo pelota.
    """

    def __init__(
        self,
        juegos: dict[date, list[dict[str, Any]]] | list[dict[str, Any]],
        accion: list[tuple[int, int, str, dict[str, Any]]] | None = None,
        boxscores: dict[int, dict[str, Any]] | None = None,
    ) -> None:
        self.juegos = juegos if isinstance(juegos, dict) else {HOY: juegos}
        self.accion = accion or []  # (player_id, team_id, grupo, stat)
        self.boxscores = boxscores or {}
        self.llamadas: list[str] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.llamadas.append(path)
        if path.endswith("/boxscore"):
            pk = int(path.split("/")[-2])
            if pk not in self.boxscores:
                raise MlbProxyError("el proxy no contesta por ese juego")
            return self.boxscores[pk]
        if path == "/api/v1/schedule":
            desde, hasta = (params or {}).get("startDate"), (params or {}).get("endDate")
            return {
                "dates": [
                    {"date": dia.isoformat(), "games": lista}
                    for dia, lista in sorted(self.juegos.items())
                    if lista and str(desde) <= dia.isoformat() <= str(hasta)
                ]
            }
        grupo = (params or {}).get("group")
        return {
            "stats": [
                {
                    "splits": [
                        {"player": {"id": pid}, "team": {"id": tid}, "stat": stat}
                        for pid, tid, g, stat in self.accion
                        if g == grupo
                    ]
                }
            ]
        }

    def close(self) -> None:
        pass

    def __enter__(self) -> "_Proxy":
        return self

    def __exit__(self, *exc: object) -> None:
        pass


def _armada() -> scoreboard.Pizarra:
    """`del_dia` devuelve None cuando el proxy falla; en estos tests siempre contesta."""
    pizarra = scoreboard.del_dia()
    assert pizarra is not None
    return pizarra


def _hoy(pizarra: scoreboard.Pizarra) -> scoreboard.Jornada:
    return next(j for j in pizarra.jornadas if j.es_hoy)


def _jugador(pid: int, nombre: str, apellido: str) -> Player:
    return Player.todos.create(
        **_other_player(
            player_id=pid, dgl_id=f"j{pid}", full_name=f"{nombre} {apellido}", firstname=nombre, lastname_1=apellido
        )
    )


def _instalar(monkeypatch: pytest.MonkeyPatch, proxy: _Proxy) -> None:
    monkeypatch.setattr(scoreboard, "_cliente", lambda: proxy)


# ── Quién es de los nuestros ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_only_the_master_decides_who_is_dominican(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regla de autoridad: `dgl_master` manda. Nadie más entra por jugar en el mismo juego."""
    _jugador(1, "Eury", "Pérez")
    proxy = _Proxy([_juego(alineacion={"away": [1, 999]})], accion=[(1, 135, "hitting", {}), (999, 135, "hitting", {})])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert [n.nombre for n in juego.visitante.nuestros] == ["E. Pérez"]


@pytest.mark.django_db
def test_the_announced_lineup_marks_a_player_before_the_first_pitch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin esto, un juego de las 8 no mostraría un dominicano hasta que alguno se embase."""
    _jugador(1, "Juan", "Soto")
    proxy = _Proxy([_juego(estado="Preview", detallado="Scheduled", alineacion={"away": [1]})], accion=[])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert [n.nombre for n in juego.visitante.nuestros] == ["J. Soto"]


@pytest.mark.django_db
def test_a_reliever_who_never_appeared_in_a_lineup_is_still_marked(monkeypatch: pytest.MonkeyPatch) -> None:
    """El relevista y el emergente no salen en ninguna alineación, y en un sitio dominicano cuentan."""
    _jugador(1, "Cristopher", "Sánchez")
    proxy = _Proxy([_juego(alineacion={})], accion=[(1, 146, "pitching", {})])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert [n.nombre for n in juego.local.nuestros] == ["C. Sánchez"]


@pytest.mark.django_db
def test_each_player_is_marked_on_his_own_side(monkeypatch: pytest.MonkeyPatch) -> None:
    """Marcarlos todos juntos al pie del juego obligaría a repetir el equipo en cada nombre."""
    _jugador(1, "Rafael", "Devers")
    _jugador(2, "Sandy", "Alcántara")
    proxy = _Proxy([_juego()], accion=[(1, 135, "hitting", {}), (2, 146, "pitching", {})])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert [n.nombre for n in juego.visitante.nuestros] == ["R. Devers"]
    assert [n.nombre for n in juego.local.nuestros] == ["S. Alcántara"]


@pytest.mark.django_db
def test_the_same_player_is_not_listed_twice_when_both_sources_have_him(monkeypatch: pytest.MonkeyPatch) -> None:
    """El abridor sale en la alineación Y en las estadísticas del día: es la unión, no la suma."""
    _jugador(1, "Eury", "Pérez")
    proxy = _Proxy([_juego(alineacion={"away": [1]})], accion=[(1, 135, "hitting", {}), (1, 135, "pitching", {})])
    _instalar(monkeypatch, proxy)

    assert len(_hoy(_armada()).juegos[0].visitante.nuestros) == 1


# ── Cómo se lee el juego ────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_game_that_has_not_started_shows_no_score(monkeypatch: pytest.MonkeyPatch) -> None:
    """El calendario manda 0. Anunciar 0-0 a las 3 de la tarde es publicar un marcador que no existe."""
    proxy = _Proxy([_juego(estado="Preview", detallado="Scheduled", visitante=(135, "sdn", 0), local=(146, "mia", 0))])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert juego.visitante.carreras is None
    assert juego.local.carreras is None


@pytest.mark.django_db
def test_a_live_game_says_which_half_of_which_inning(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = _Proxy([_juego(estado="Live", detallado="In Progress", inning=7, mitad="Bottom")])
    _instalar(monkeypatch, proxy)

    assert _hoy(_armada()).juegos[0].detalle == "Baja del 7"


@pytest.mark.django_db
def test_extra_innings_are_named_and_the_ordinary_nine_are_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """«Final (11)» dice algo; «Final (9)» es ruido en catorce filas de quince."""
    proxy = _Proxy([_juego(inning=11), _juego(inning=9)])
    _instalar(monkeypatch, proxy)

    juegos = _hoy(_armada()).juegos

    assert juegos[0].detalle == "Final (11)"
    assert juegos[1].detalle == "Final"


@pytest.mark.django_db
def test_a_postponed_game_says_so_instead_of_showing_a_start_time(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = _Proxy([_juego(estado="Other", detallado="Postponed")])
    _instalar(monkeypatch, proxy)

    assert _hoy(_armada()).juegos[0].detalle == "Pospuesto"


@pytest.mark.django_db
def test_games_come_in_start_time_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Es el orden en que ocurre la jornada, y el único que no cambia entre refrescos."""
    proxy = _Proxy(
        [
            _juego(visitante=(147, "nya", 3), hora="2026-07-26T23:15:00Z"),
            _juego(visitante=(135, "sdn", 7), hora="2026-07-26T17:10:00Z"),
        ]
    )
    _instalar(monkeypatch, proxy)

    assert [j.visitante.codigo for j in _hoy(_armada()).juegos] == ["SDN", "NYA"]


# ── El juego en curso ───────────────────────────────────────────────────────────────────────────


def _boxscore(
    visitantes: list[tuple[int, dict[str, Any]]] | None = None,
    locales: list[tuple[int, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    def lado(equipo_id: int, jugadores: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
        return {
            "team": {"id": equipo_id},
            "players": {f"ID{pid}": {"person": {"id": pid}, "stats": stats} for pid, stats in jugadores},
        }

    return {"teams": {"away": lado(135, visitantes or []), "home": lado(146, locales or [])}}


def _bateo(**stat: Any) -> dict[str, Any]:
    return {"batting": stat}


@pytest.mark.django_db
def test_a_game_in_progress_gets_its_lines_from_the_boxscore(monkeypatch: pytest.MonkeyPatch) -> None:
    """`byDateRange` no publica nada de un juego hasta que termina — está medido contra el proxy.

    Sin el boxscore, un juego en curso muestra los nombres y ninguna línea al lado.
    """
    _jugador(1, "Wilmer", "Adames")
    proxy = _Proxy(
        [_juego(estado="Live", detallado="In Progress")],
        accion=[],  # la consulta del día no trae a nadie de este juego, como en la realidad
        boxscores={800001: _boxscore([(1, _bateo(AB=2, H=1, X2B=1, R=1))])},
    )
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert [(n.nombre, n.linea) for n in juego.visitante.nuestros] == [("W. Adames", "1-2, 2B, 1 R")]


@pytest.mark.django_db
def test_a_player_on_the_bench_is_not_listed_as_having_played(monkeypatch: pytest.MonkeyPatch) -> None:
    """El boxscore trae la novena entera. Los bloques vacíos son la señal de quién no ha entrado."""
    _jugador(1, "Rafael", "Devers")
    vacio = _boxscore([(1, {"batting": {}, "pitching": {}})])
    proxy = _Proxy([_juego(estado="Live", detallado="In Progress")], boxscores={800001: vacio})
    _instalar(monkeypatch, proxy)

    assert _hoy(_armada()).juegos[0].visitante.nuestros == ()


@pytest.mark.django_db
def test_a_boxscore_that_fails_does_not_take_down_the_rest_of_the_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Catorce juegos no pueden perderse porque uno no contestó."""
    # Sin boxscore declarado el proxy falso revienta al pedirlo, como uno real que no contesta.
    proxy = _Proxy([_juego(estado="Live", detallado="In Progress", pk=1), _juego(pk=2)])
    _instalar(monkeypatch, proxy)

    assert len(_hoy(_armada()).juegos) == 2


@pytest.mark.django_db
def test_a_finished_game_costs_no_extra_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """El precio del detalle en vivo es una llamada POR JUEGO VIVO, y solo por juego vivo.

    Los terminados salen de la consulta del día, que es una sola para toda la liga. Si esto se
    rompiera, una jornada completa costaría quince llamadas por minuto en vez de tres.
    """
    proxy = _Proxy([_juego(), _juego(pk=2), _juego(pk=3)])
    _instalar(monkeypatch, proxy)

    _armada()

    assert not [ruta for ruta in proxy.llamadas if ruta.endswith("/boxscore")]


# ── La doble cartelera ──────────────────────────────────────────────────────────────────────────


def _doble(uno: dict[str, Any], dos: dict[str, Any]) -> _Proxy:
    """Dos juegos del mismo día entre los mismos dos equipos, cada uno con su boxscore."""
    return _Proxy(
        [_juego(pk=1, doble="S"), _juego(pk=2, doble="S")],
        # La consulta del día devuelve UN split por jugador con los dos juegos sumados: es
        # exactamente el dato que no sirve acá, y por eso se pide el boxscore de cada juego.
        accion=[(1, 135, "hitting", {"AB": 7, "H": 1, "X2B": 1, "RBI": 1, "R": 1})],
        boxscores={1: uno, 2: dos},
    )


@pytest.mark.django_db
def test_each_game_of_a_doubleheader_shows_its_own_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """El total del día son los dos juegos sumados, y ninguno de los dos fue eso.

    Verificado contra la doble cartelera real de LAN en NYA del 19 de julio: Teoscar Hernández fue
    de 1-4 con doble en el primero y de 0-3 en el segundo.
    """
    _jugador(1, "Teoscar", "Hernández")
    _instalar(
        monkeypatch,
        _doble(
            _boxscore([(1, _bateo(AB=4, H=1, X2B=1, RBI=1, R=1))]),
            _boxscore([(1, _bateo(AB=3, H=0))]),
        ),
    )

    juegos = _hoy(_armada()).juegos

    assert juegos[0].visitante.nuestros[0].linea == "1-4, 2B, 1 RBI, 1 R"
    assert juegos[1].visitante.nuestros[0].linea == "0-3"


@pytest.mark.django_db
def test_playing_only_the_nightcap_does_not_put_you_in_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con el total del día, el relevista del segundo juego aparecía también en el primero."""
    _jugador(2, "Camilo", "Doval")
    _instalar(monkeypatch, _doble(_boxscore([]), _boxscore([(2, _bateo(AB=1, H=1))])))

    juegos = _hoy(_armada()).juegos

    assert juegos[0].visitante.nuestros == ()
    assert [n.nombre for n in juegos[1].visitante.nuestros] == ["C. Doval"]


@pytest.mark.django_db
def test_only_the_doubleheader_pays_for_the_extra_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """El precio se paga donde está el problema: un día sin doble cartelera no cuesta ni una llamada."""
    proxy = _Proxy([_juego(pk=1, doble="S"), _juego(pk=2, doble="S"), _juego(pk=3), _juego(pk=4)])
    _instalar(monkeypatch, proxy)

    _armada()

    assert sorted(r for r in proxy.llamadas if r.endswith("/boxscore")) == [
        "/api/v1/game/1/boxscore",
        "/api/v1/game/2/boxscore",
    ]


@pytest.mark.django_db
def test_a_game_that_has_not_started_does_not_open_a_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se sabe quién está anunciado, pero un panel de nombres sin líneas promete un dato que no hay."""
    _jugador(1, "Juan", "Soto")
    proxy = _Proxy([_juego(estado="Preview", detallado="Scheduled", alineacion={"away": [1]})])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert juego.con_dominicanos is True
    assert juego.detallable is False


@pytest.mark.django_db
def test_a_dominican_probable_starter_opens_the_panel_before_first_pitch(monkeypatch: pytest.MonkeyPatch) -> None:
    """No hay líneas que enseñar, pero «hoy lanza uno de los nuestros» es noticia por sí sola."""
    _jugador(1, "Cristopher", "Sánchez")
    proxy = _Proxy([_juego(estado="Preview", detallado="Scheduled", abridores={"home": 1})])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert juego.detallable is True
    assert [(n.nombre, n.abridor) for n in juego.local.nuestros] == [("C. Sánchez", True)]


@pytest.mark.django_db
def test_the_starter_label_belongs_to_the_starter_and_to_nobody_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """El resto de la alineación anunciada sale sin etiqueta: no van a abrir, van a batear."""
    _jugador(1, "Cristopher", "Sánchez")
    _jugador(2, "Juan", "Soto")
    proxy = _Proxy([_juego(estado="Preview", detallado="Scheduled", alineacion={"home": [2]}, abridores={"home": 1})])
    _instalar(monkeypatch, proxy)

    juego = _hoy(_armada()).juegos[0]

    assert {(n.nombre, n.abridor) for n in juego.local.nuestros} == {("C. Sánchez", True), ("J. Soto", False)}


# ── Los dos días de la tira ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_strip_carries_yesterday_and_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quien entra de mañana quiere lo de anoche; quien entra de noche quiere lo de ahora."""
    _instalar(monkeypatch, _Proxy({AYER: [_juego()], HOY: [_juego(), _juego()]}))

    jornadas = _armada().jornadas

    assert [(j.dia, j.es_hoy, len(j.juegos)) for j in jornadas] == [(AYER, False, 1), (HOY, True, 2)]


@pytest.mark.django_db
def test_a_day_without_baseball_falls_out_of_the_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    """En el receso del Juego de Estrellas hoy no hubo nada: queda ayer, no un hueco con una fecha."""
    _instalar(monkeypatch, _Proxy({AYER: [_juego()]}))

    jornadas = _armada().jornadas

    assert [j.dia for j in jornadas] == [AYER]


@pytest.mark.django_db
def test_with_no_baseball_at_all_the_banner_is_not_drawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """En enero no hay ni hoy ni ayer. La plantilla no dibuja nada; no es un error."""
    _instalar(monkeypatch, _Proxy({}))

    assert _armada().hay_juegos is False


# ── Que la portada no se rompa ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_when_the_proxy_fails_the_last_good_board_is_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un marcador de hace unos minutos es un problema mucho menor que un hueco en la portada."""
    _instalar(monkeypatch, _Proxy([_juego()]))
    buena = scoreboard.del_dia()
    cache.delete("pizarra")  # vence la caché corta, sobrevive el respaldo

    class _Caido:
        def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise MlbProxyError("el proxy no contesta")

        def __enter__(self) -> "_Caido":
            return self

        def __exit__(self, *exc: object) -> None:
            pass

    monkeypatch.setattr(scoreboard, "_cliente", lambda: _Caido())

    assert scoreboard.del_dia() == buena


@pytest.mark.django_db
def test_with_no_board_ever_built_a_failure_returns_nothing_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Primera visita con el proxy caído: la portada carga sin la pizarra, no con un error 500."""

    class _Caido:
        def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise MlbProxyError("el proxy no contesta")

        def __enter__(self) -> "_Caido":
            return self

        def __exit__(self, *exc: object) -> None:
            pass

    monkeypatch.setattr(scoreboard, "_cliente", lambda: _Caido())

    assert scoreboard.del_dia() is None


@pytest.mark.django_db
def test_a_second_visit_within_the_minute_does_not_ask_the_proxy_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """La caché es por sitio, no por visita: si no, cada lector costaría tres llamadas."""
    proxy = _Proxy([_juego()])
    _instalar(monkeypatch, proxy)

    scoreboard.del_dia()
    llamadas = len(proxy.llamadas)
    scoreboard.del_dia()

    assert len(proxy.llamadas) == llamadas


@pytest.mark.django_db
def test_the_browser_stops_asking_once_every_game_is_over(monkeypatch: pytest.MonkeyPatch) -> None:
    """`hay_vivos` es lo que el JS mira. Con todo terminado no queda nada que pueda cambiar."""
    _instalar(monkeypatch, _Proxy([_juego(), _juego()]))
    assert _armada().hay_vivos is False

    cache.clear()
    _instalar(monkeypatch, _Proxy([_juego(), _juego(estado="Live", detallado="In Progress")]))
    assert _armada().hay_vivos is True
