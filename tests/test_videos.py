"""Los videos de jugadas: qué entra, qué se descarta y por qué.

Casi todo acá es el filtro que va de 551 highlights a unos 16, y cada caso descartado es uno real de
la jornada del 25 de julio de 2026. Un video atribuido al jugador equivocado es peor que ningún
video: pondría el jonrón de otro al lado del nombre de un dominicano.
"""

from datetime import date
from typing import Any, cast

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats import videos
from dglweb.stats.models import GameVideo, IngestRun, SeasonDates
from dglweb.stats.season_window import MLB
from tests.test_players import _other_player

AYER = date(2026, 7, 25)


def _item(
    *,
    titulo: str = "Rafael Devers' three-run homer (22)",
    blurb: str = "",
    jugadores: tuple[int, ...] = (1,),
    taxonomias: tuple[str, ...] = (videos.JUGADA, "hitting"),
    guid: str = "abc-123",
    duracion: str = "00:00:30",
    con_mp4: bool = True,
) -> dict[str, Any]:
    llaves = [{"type": "player_id", "value": str(pid)} for pid in jugadores]
    llaves += [{"type": "taxonomy", "value": t} for t in taxonomias]
    playbacks = [{"name": "hlsCloud", "url": "https://mlb/x.m3u8"}]
    if con_mp4:
        playbacks.append({"name": "mp4Avc", "url": "https://mlb/x_1280x720.mp4"})
    return {
        "guid": guid,
        "title": titulo,
        "blurb": blurb,
        "description": "",
        "duration": duracion,
        "keywordsAll": llaves,
        "playbacks": playbacks,
        "image": {"cuts": [{"width": 1920, "src": "https://img/grande.jpg"}, {"width": 640, "src": "https://img/x.jpg"}]},
    }


class _Proxy:
    def __init__(self, items: list[dict[str, Any]], juegos: list[int] | None = None) -> None:
        self.items = items
        self.juegos = juegos if juegos is not None else [700001]
        self.llamadas: list[str] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.llamadas.append(path)
        if path == "/api/v1/schedule":
            return {"dates": [{"games": [{"gamePk": pk} for pk in self.juegos]}]}
        return {"highlights": {"highlights": {"items": self.items}}}


def _devers() -> Player:
    return Player.todos.create(
        **_other_player(player_id=1, dgl_id="j1", full_name="Rafael Devers", firstname="Rafael", lastname_1="Devers")
    )


def _buscar(items: list[dict[str, Any]], universo: set[int] | None = None) -> list[videos.Video]:
    return videos.de_un_juego(cast("Any", _Proxy(items)), 700001, universo or {1}, {1: "Devers"})


# ── De quién es el video ────────────────────────────────────────────────────────────────────────


def test_the_player_comes_from_the_tag_not_from_the_title() -> None:
    """MLB etiqueta el `player_id` del protagonista. Deducirlo del título sería cambiar un dato duro
    por una conjetura, y además el país no lo decide ni el nombre ni la API — ver docs/AUTORIDAD.md.
    """
    encontrados = _buscar([_item(jugadores=(1,))])

    assert [v.player_id for v in encontrados] == [1]


def test_a_player_outside_the_master_is_not_dominican_no_matter_what() -> None:
    """La autoridad es `dgl_master`. Nadie entra por salir en el mismo video."""
    assert _buscar([_item(jugadores=(1, 999))], universo={1}) == _buscar([_item(jugadores=(1,))], universo={1})


def test_a_clip_that_does_not_name_him_is_not_his() -> None:
    """Caso real: «Ball 4 confirmed after an ABS challenge» venía etiquetado con Randy Vásquez.

    Está en la jugada, pero el video no es suyo: es una revisión de árbitro. Nueve de los 41 videos
    con dominicano del 25 de julio eran de este tipo.
    """
    assert _buscar([_item(titulo="Ball 4 confirmed after an ABS challenge")]) == []


def test_the_accents_of_our_master_do_not_block_the_match() -> None:
    """Nuestro maestro escribe «Durán»; MLB escribe «Duran». Sin normalizar, no coincidiría ninguno."""
    encontrados = videos.de_un_juego(
        cast("Any", _Proxy([_item(titulo="Jhoan Duran strikes out the side in the 9th")])), 700001, {1}, {1: "Durán"}
    )

    assert len(encontrados) == 1


def test_the_name_may_come_from_the_blurb() -> None:
    """El título a veces es genérico y el blurb es el que nombra la jugada."""
    encontrados = _buscar([_item(titulo="A great catch in the 8th", blurb="Rafael Devers' diving stop")])

    assert len(encontrados) == 1


# ── Qué cuenta como jugada ──────────────────────────────────────────────────────────────────────


def test_an_interview_is_not_a_play() -> None:
    """«Junior Caminero on Rays' win», 1:49. La taxonomía del propio item los separa: `interview`
    contra `in-game-highlight`. No hace falta medir duraciones ni buscar «reacts to» en el título.
    """
    assert _buscar([_item(titulo="Rafael Devers on the win", taxonomias=("interview",))]) == []


def test_a_clip_with_no_taxonomy_at_all_is_left_out() -> None:
    """Caso real: dos montajes promocionales de Eury Pérez que no traían taxonomía ninguna."""
    assert _buscar([_item(taxonomias=())]) == []


def test_a_clip_without_a_downloadable_mp4_is_useless() -> None:
    """Solo con `hlsCloud` haría falta un reproductor de streaming; la ventana emergente usa `<video>`."""
    assert _buscar([_item(con_mp4=False)]) == []


def test_the_home_run_wins_over_the_generic_hitting_tag() -> None:
    """Un jonrón viene marcado `home-run` Y `hitting`; lo que hay que decir es que fue un jonrón."""
    encontrados = _buscar([_item(taxonomias=(videos.JUGADA, "hitting", "home-run"))])

    assert encontrados[0].tipo == "hr"


# ── Lo que se guarda ────────────────────────────────────────────────────────────────────────────


def test_the_lighter_mp4_is_preferred() -> None:
    """`highBit` es el mismo cuadro a cuatro veces el peso, para un clip de treinta segundos."""
    item = _item()
    item["playbacks"].append({"name": "highBit", "url": "https://mlb/x_16000K.mp4"})

    assert _buscar([item])[0].video_url.endswith("_1280x720.mp4")


def test_the_thumbnail_is_not_the_full_size_image() -> None:
    """1920 de ancho para una miniatura al lado de una línea de estadísticas es peso regalado."""
    assert _buscar([_item()])[0].imagen_url == "https://img/x.jpg"


def test_the_duration_is_stored_in_seconds() -> None:
    assert _buscar([_item(duracion="00:01:25")])[0].segundos == 85


@pytest.mark.django_db
def test_reprocessing_a_day_does_not_duplicate_it(db: None) -> None:
    """Se borra y reescribe la jornada: reprocesar tiene que dar lo mismo que procesar de cero."""
    _devers()
    encontrados = _buscar([_item()])

    videos.guardar(AYER, encontrados)
    videos.guardar(AYER, encontrados)

    assert GameVideo.objects.filter(fecha=AYER).count() == 1


@pytest.mark.django_db
def test_the_same_item_repeated_in_the_feed_is_stored_once(db: None) -> None:
    """MLB a veces repite un item en dos secciones, y `bulk_create` no perdona un duplicado."""
    _devers()

    assert videos.guardar(AYER, _buscar([_item(), _item()])) == 1


@pytest.mark.django_db
def test_the_same_play_can_belong_to_two_dominicans(db: None) -> None:
    """El que lanzó y el que bateó: si el video nombra a los dos, a los dos les toca."""
    _devers()
    Player.todos.create(
        **_other_player(player_id=2, dgl_id="j2", full_name="Eury Pérez", firstname="Eury", lastname_1="Pérez")
    )
    encontrados = videos.de_un_juego(
        cast("Any", _Proxy([_item(titulo="Eury Perez strikes out Rafael Devers", jugadores=(1, 2))])),
        700001,
        {1, 2},
        {1: "Devers", 2: "Pérez"},
    )

    assert videos.guardar(AYER, encontrados) == 2


# ── Cuál se muestra al lado de la línea ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_home_run_is_the_one_shown_first(db: None) -> None:
    """Sin `playId` no hay forma de saber qué video corresponde a qué número de la línea, así que
    cuando hay varios se elige. El jonrón es lo que el lector espera ver.
    """
    jugador = _devers()
    for guid, tipo, segundos in (("a", "bateo", 40), ("b", "hr", 20)):
        GameVideo.objects.create(
            guid=guid, player=jugador, fecha=AYER, game_pk=1, titulo=tipo, tipo=tipo, segundos=segundos, video_url="u"
        )

    assert videos.por_jugador(AYER, {1})[1][0].titulo == "hr"


# ── El comando ──────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


@pytest.mark.django_db
def test_the_command_stores_the_day_and_records_it(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    _devers()
    proxy = _Proxy([_item()])
    monkeypatch.setattr("dglweb.stats.management.commands.build_game_videos.build_client", lambda: proxy)

    call_command("build_game_videos", "--fecha", "2026-07-25")

    assert GameVideo.objects.filter(fecha=AYER).count() == 1
    assert IngestRun.objects.get(command="build_game_videos").status == IngestRun.Status.SUCCESS


@pytest.mark.django_db
def test_a_game_whose_content_fails_does_not_lose_the_others(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quince llamadas separadas: que una falle no puede costar las otras catorce."""
    from dglweb.mlb.client import MlbProxyError

    _devers()

    class _Roto(_Proxy):
        def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if path.endswith("/700002/content"):
                raise MlbProxyError("ese juego no contesta")
            return super().get(path, params)

    monkeypatch.setattr(
        "dglweb.stats.management.commands.build_game_videos.build_client",
        lambda: _Roto([_item()], juegos=[700001, 700002]),
    )

    call_command("build_game_videos", "--fecha", "2026-07-25")

    assert GameVideo.objects.filter(fecha=AYER).count() == 1
