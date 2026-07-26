"""Los videos de MLB donde un dominicano hizo algo: qué se guarda y qué se descarta.

De dónde sale: `/api/v1/game/{gamePk}/content`, una llamada por juego. En una jornada de 15 juegos
son 551 highlights, de los que quedan unas 16. Todo lo que sigue es el filtro que va de 551 a 16, y
está medido contra la jornada del 25 de julio de 2026.

**Quién sale no se adivina.** Cada item trae `keywordsAll` con el `player_id` del protagonista.
Cruzado contra `dgl_master` la atribución es exacta — 41 items de 551 tenían dominicano. Leer el
título para descubrir de quién es el video sería reemplazar un dato duro por una conjetura, y además
`docs/AUTORIDAD.md` no lo permitiría: el país no lo decide ni el nombre ni la API.

**Pero la etiqueta sola no alcanza.** De esos 41, nueve eran clips donde el dominicano es el OTRO de
la jugada o una revisión de árbitro: «Ball 4 confirmed after an ABS challenge» con Randy Vásquez
etiquetado, «Blue Jays score five runs in the 3rd inning» con Vladimir Guerrero. Por eso se exige
además que su apellido aparezca en el título: si el video no lo nombra, no es su video.

**Y la jugada se distingue de lo demás por taxonomía, no por maña.** El propio item viene marcado
`in-game-highlight` cuando es una jugada e `interview` cuando es una entrevista. No hace falta medir
duraciones ni buscar «reacts to» en el título. Eso deja fuera las entrevistas y también un par de
montajes promocionales que no traen taxonomía ninguna.
"""

import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

from dglweb.mlb.client import MlbProxyClient, MlbProxyError

# La marca que distingue una jugada de una entrevista o un montaje. La pone MLB en el item.
JUGADA = "in-game-highlight"

# Cómo se lee la taxonomía del item para saber de qué es la jugada. El orden importa: un jonrón
# también viene marcado `hitting`, y lo que se quiere decir es que fue un jonrón.
_TIPOS = (("home-run", "hr"), ("defense", "defensa"), ("pitching", "pitcheo"), ("hitting", "bateo"))


@dataclass(frozen=True)
class Video:
    """Un video ya juzgado: se sabe de quién es y que es una jugada suya."""

    guid: str
    player_id: int
    game_pk: int
    titulo: str
    descripcion: str
    segundos: int
    tipo: str
    video_url: str
    imagen_url: str


def sin_tildes(texto: str) -> str:
    """Para comparar «Durán» con «Duran»: MLB escribe los títulos sin acentos."""
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def _segundos(duracion: str) -> int:
    """«00:01:25» -> 85. Lo que no se pueda leer vale cero, que solo afecta al orden."""
    partes = duracion.split(":")
    try:
        return sum(int(parte) * factor for parte, factor in zip(reversed(partes), (1, 60, 3600), strict=False))
    except ValueError:
        return 0


def _taxonomias(item: dict[str, Any]) -> set[str]:
    return {str(k.get("value")) for k in item.get("keywordsAll") or [] if k.get("type") == "taxonomy"}


def _protagonistas(item: dict[str, Any]) -> set[int]:
    """Los `player_id` que MLB etiquetó en la jugada."""
    return {
        int(k["value"])
        for k in item.get("keywordsAll") or []
        if k.get("type") == "player_id" and str(k.get("value", "")).isdigit()
    }


def _tipo(taxonomias: set[str]) -> str:
    for marca, tipo in _TIPOS:
        if marca in taxonomias:
            return tipo
    return "otro"


def _mp4(item: dict[str, Any]) -> str:
    """El mp4 que se puede meter en un `<video>`.

    Se prefiere `mp4Avc` (1280x720, 4 Mbps) sobre `highBit`, que es el mismo cuadro a 16 Mbps: cuatro
    veces el peso para un clip de treinta segundos en una ventana emergente. Los `hlsCloud` son
    streaming y necesitarían un reproductor aparte.
    """
    reproducciones = {pb.get("name"): pb.get("url") for pb in item.get("playbacks") or []}
    return str(reproducciones.get("mp4Avc") or reproducciones.get("highBit") or "")


def _portada(item: dict[str, Any]) -> str:
    """La imagen más chica que siga siendo decente: es una miniatura, no un fondo de pantalla."""
    cortes = [c for c in ((item.get("image") or {}).get("cuts") or []) if c.get("src") and c.get("width")]
    if not cortes:
        return ""
    grandes = [c for c in cortes if c["width"] >= 640] or cortes
    return str(min(grandes, key=lambda c: c["width"])["src"])


def _es_suyo(item: dict[str, Any], apellido: str) -> bool:
    """Si el video lo nombra a él, y no lo etiqueta de paso por estar en la jugada del otro."""
    return sin_tildes(apellido) in sin_tildes(f"{item.get('title') or ''} {item.get('blurb') or ''}")


def de_un_juego(
    client: MlbProxyClient, game_pk: int, universo: set[int], apellidos: dict[int, str]
) -> list[Video]:
    """Los videos de jugadas dominicanas de un juego. Un juego sin highlights devuelve lista vacía."""
    payload = client.get(f"/api/v1/game/{game_pk}/content")
    items = (((payload.get("highlights") or {}).get("highlights") or {}).get("items")) or []

    salida = []
    for item in items:
        taxonomias = _taxonomias(item)
        if JUGADA not in taxonomias:
            continue
        enlace = _mp4(item)
        if not enlace:
            continue
        for player_id in _protagonistas(item) & universo:
            if not _es_suyo(item, apellidos.get(player_id, "")):
                continue
            salida.append(
                Video(
                    guid=str(item.get("guid") or ""),
                    player_id=player_id,
                    game_pk=game_pk,
                    titulo=str(item.get("title") or "")[:200],
                    descripcion=str(item.get("description") or item.get("blurb") or ""),
                    segundos=_segundos(str(item.get("duration") or "")),
                    tipo=_tipo(taxonomias),
                    video_url=enlace,
                    imagen_url=_portada(item),
                )
            )
    return salida


def de_la_jornada(client: MlbProxyClient, dia: date) -> list[Video]:
    """Todos los videos dominicanos de un día. Una llamada por juego, más la del calendario."""
    from dglweb.players import universe
    from dglweb.players.models import Player

    universo = universe.debuted()
    apellidos = dict(Player.todos.values_list("player_id", "lastname_1"))

    calendario = client.get("/api/v1/schedule", {"sportId": 1, "date": dia.isoformat()})
    juegos = [g for f in calendario.get("dates") or [] for g in f.get("games") or []]

    salida = []
    for juego in juegos:
        if (pk := juego.get("gamePk")) is None:
            continue
        try:
            salida.extend(de_un_juego(client, pk, universo, apellidos))
        except MlbProxyError:
            # Un juego sin contenido no puede costar los otros catorce. La próxima corrida del día
            # lo vuelve a intentar, porque guardar reemplaza la jornada entera.
            continue
    return salida


def guardar(dia: date, videos: list[Video]) -> int:
    """Reemplaza los videos de esa jornada. Devuelve cuántas filas quedaron.

    Se borra y reescribe el día como en los destacados: reprocesar una jornada tiene que dar el mismo
    resultado que procesarla por primera vez, y con upsert fila por fila un video que MLB haya
    retirado se quedaría para siempre.
    """
    from django.db import transaction

    from dglweb.players.models import Player
    from dglweb.stats.models import GameVideo

    conocidos = set(Player.todos.values_list("player_id", flat=True))
    # Por (guid, jugador), que es la clave única: MLB a veces repite el mismo item en dos secciones
    # del contenido, y `bulk_create` no perdona un duplicado dentro del mismo lote.
    filas = {
        (video.guid, video.player_id): GameVideo(
            guid=video.guid,
            player_id=video.player_id,
            fecha=dia,
            game_pk=video.game_pk,
            titulo=video.titulo,
            descripcion=video.descripcion,
            segundos=video.segundos,
            tipo=video.tipo,
            video_url=video.video_url,
            imagen_url=video.imagen_url,
        )
        for video in videos
        if video.player_id in conocidos and video.guid
    }
    with transaction.atomic():
        GameVideo.objects.filter(fecha=dia).delete()
        GameVideo.objects.bulk_create(filas.values())
    return len(filas)


@dataclass(frozen=True)
class Clip:
    """Lo mínimo que una plantilla necesita para abrir el video. Va aparte del modelo porque la
    pizarra se guarda en caché, y meter filas de la base en la caché es cargar con lo que no se usa.
    """

    titulo: str
    url: str
    portada: str


_ORDEN = {"hr": 0, "defensa": 1, "pitcheo": 2, "bateo": 3, "otro": 4}


def por_jugador(dia: date, player_ids: set[int]) -> dict[int, tuple[Clip, ...]]:
    """`player_id -> sus clips de ese día`, el mejor primero.

    El orden: primero el jonrón, y a igualdad de tipo el clip más largo. No es capricho — cuando un
    jugador tiene dos videos el mismo día hay que elegir cuál va al lado de su línea, y sin `playId`
    no existe forma de saber cuál corresponde a qué número. El jonrón es lo que el lector espera.
    """
    from dglweb.stats.models import GameVideo

    filas: dict[int, list[Any]] = {}
    for video in GameVideo.objects.filter(fecha=dia, player_id__in=player_ids):
        filas.setdefault(video.player_id, []).append(video)

    agrupados = {}
    for player_id, propios in filas.items():
        propios.sort(key=lambda v: (_ORDEN.get(v.tipo, 9), -v.segundos))
        agrupados[player_id] = tuple(Clip(v.titulo, v.video_url, v.imagen_url) for v in propios)
    return agrupados
