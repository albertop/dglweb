"""La pizarra: el banner de juegos de ayer y de hoy, con los nuestros marcados.

Toda la liga y no solo los juegos con dominicanos: quien entra a la portada quiere ver la pelota del
día, y esconder doce juegos para mostrar tres no le ahorra nada. Lo dominicano se marca dentro de
cada juego, que es donde el lector lo busca.

DOS DÍAS, NO UNO
----------------
Ayer y hoy en la misma tira. Quien entra de mañana quiere ver cómo terminó lo de anoche, y quien
entra de noche quiere el juego en curso; con un solo día siempre hay una de las dos visitas que se
queda sin lo suyo. De paso resuelve el receso del Juego de Estrellas: si hoy no hubo pelota, ayer
sigue ahí y el banner no queda en blanco.

QUIÉNES SON LOS NUESTROS EN CADA JUEGO
--------------------------------------
La unión de dos fuentes, porque ninguna sola alcanza:

* **La alineación anunciada** (`lineups` y `probablePitcher`, que vienen en la misma llamada del
  calendario). Es lo único que existe antes del primer lanzamiento, y sin ella un juego que empieza
  a las 8 no mostraría un solo dominicano hasta que alguno se embase.
* **Quién vio acción**, del mismo `byDateRange` que alimenta los destacados. Recoge al relevista y al
  emergente, que no salen en ninguna alineación y que en un sitio dominicano importan tanto como el
  abridor.

Ambas se cruzan contra el universo dominicano —`dgl_master`, nunca el `birthCountry` de la API— antes
de marcar nada.

POR QUÉ ESTO NO ES UN JOB NOCTURNO
----------------------------------
Un marcador en vivo por definición no se puede escribir la noche anterior. Se pide al proxy desde la
página, con caché de un minuto: son tres llamadas por minuto para todo el sitio, no por visita.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_date

from dglweb.mlb.client import MlbProxyClient, MlbProxyError
from dglweb.stats.leagues import team_code

logger = logging.getLogger(__name__)

# La portada no puede quedarse esperando al proxy: el cliente de los scrapers reintenta tres veces con
# 20 segundos de espera, hasta un minuto colgado. En un job nocturno eso es prudencia; en una página
# es una página rota. Acá se pide una vez, corto, y si no llega se muestra lo último bueno.
_TIMEOUT = 4.0
_FRESCO = 60  # segundos que vale una pizarra antes de volver a preguntar
_RESPALDO = 6 * 60 * 60  # cuánto se guarda la última buena, por si el proxy se cae
_CLAVE = "pizarra"
_CLAVE_RESPALDO = "pizarra:respaldo"

# Los logos viven en el sitio, bajados por `manage.py download_team_logos`, y no enlazados donde
# están: así el banner no depende de que un tercero esté arriba.
_LOGOS = "img/equipos/"

PROGRAMADO, VIVO, FINAL = "programado", "vivo", "final"

# `abstractGameState` agrupa los muchos `detailedState` en cuatro. "Other" es lo raro —pospuesto,
# suspendido— y se trata como no jugado, que es lo que el lector necesita saber.
_ESTADOS = {"Preview": PROGRAMADO, "Live": VIVO, "Final": FINAL, "Other": PROGRAMADO}

# Los `detailedState` que cambian lo que hay que decir. El resto de los previos son «va a jugarse» y
# se muestran con la hora de inicio, que dice más que repetir «Programado».
_INCIDENCIAS = {
    "Postponed": "Pospuesto",
    "Suspended": "Suspendido",
    "Cancelled": "Cancelado",
    "Delayed": "Demorado",
    "Delayed Start": "Demorado",
}


@dataclass(frozen=True)
class Nuestro:
    """Un dominicano en ese juego, con lo que hizo. `slug` para enlazar al perfil.

    `linea` sale de las estadísticas del día, no del juego: para quien jugó una sola vez —la inmensa
    mayoría— son lo mismo. En una doble cartelera el número es el de las dos juntas; es el precio de
    no pedir un boxscore por juego, que serían quince llamadas más por refresco.

    Vacía cuando el jugador está anunciado en la alineación pero todavía no ha hecho nada.
    """

    nombre: str
    slug: str
    linea: str
    clips: tuple[Any, ...] = ()  # `videos.Clip`, sin importarlo para no atar los dos módulos
    # Abridor probable. Es lo único que se sabe de un juego que no ha empezado, y lo que hace que
    # valga la pena abrir su panel: «hoy lanza uno de los nuestros» es noticia por sí sola.
    abridor: bool = False


@dataclass(frozen=True)
class Lado:
    codigo: str
    nombre: str
    logo: str
    record: str  # "54-53", como en la pizarra de MLB
    carreras: int | None
    ganador: bool
    nuestros: tuple[Nuestro, ...]


@dataclass(frozen=True)
class Juego:
    estado: str
    detalle: str  # "Final", "Baja del 7", "8:10 p. m.", "Pospuesto"
    visitante: Lado
    local: Lado

    @property
    def lados(self) -> tuple[Lado, Lado]:
        """Para recorrerlos en la plantilla sin perder cuál es cuál: siempre visitante y local."""
        return (self.visitante, self.local)

    @property
    def con_dominicanos(self) -> bool:
        return bool(self.visitante.nuestros or self.local.nuestros)

    @property
    def abridor_nuestro(self) -> bool:
        """Si el abridor probable de alguno de los dos lados es dominicano."""
        return any(nuestro.abridor for lado in self.lados for nuestro in lado.nuestros)

    @property
    def detallable(self) -> bool:
        """Si vale la pena abrir el panel al pasar el mouse.

        Dos casos, y por motivos distintos:

        * **Terminado o en curso**, con alguien nuestro que haya hecho algo. Ahí el panel enseña qué
          hizo cada uno, que es el dato.
        * **Sin empezar, con un abridor probable dominicano.** Ahí no hay líneas que enseñar, pero
          «hoy lanza uno de los nuestros» es noticia por sí sola y merece poder mirarse.

        Un juego que no ha empezado y solo tiene bateadores anunciados queda fuera: abrir un panel
        con cinco nombres y ninguna línea al lado es prometer un dato que todavía no existe.
        """
        if self.estado == PROGRAMADO:
            return self.abridor_nuestro
        return self.estado in (FINAL, VIVO) and any(nuestro.linea for lado in self.lados for nuestro in lado.nuestros)


@dataclass(frozen=True)
class Jornada:
    """Un día de la tira. El banner los pinta seguidos, con su fecha al frente."""

    dia: date
    juegos: tuple[Juego, ...]
    es_hoy: bool


@dataclass(frozen=True)
class Pizarra:
    jornadas: tuple[Jornada, ...]

    @property
    def hay_juegos(self) -> bool:
        return any(jornada.juegos for jornada in self.jornadas)

    @property
    def hay_vivos(self) -> bool:
        """Si no hay nada en juego, el navegador deja de preguntar: no habría nada que cambiar."""
        return any(juego.estado == VIVO for jornada in self.jornadas for juego in jornada.juegos)


def _cliente() -> MlbProxyClient:
    return MlbProxyClient(
        base_url=settings.MLB_PROXY_URL,
        api_key=settings.MLB_PROXY_API_KEY,
        timeout=_TIMEOUT,
        max_attempts=1,
    )


def _calendario(client: MlbProxyClient, desde: date, hasta: date) -> dict[date, list[dict[str, Any]]]:
    """Los juegos de un rango, agrupados por día y ordenados por hora de inicio.

    El rango en una sola llamada y no una por día: el calendario ya sabe agrupar, y pedir dos veces
    lo mismo con un día de diferencia es trabajo de más para el proxy y para la página.
    """
    payload = client.get(
        "/api/v1/schedule",
        {
            "sportId": 1,
            "startDate": desde.isoformat(),
            "endDate": hasta.isoformat(),
            "hydrate": "linescore,team,lineups,probablePitcher",
        },
    )
    por_dia = {}
    for fecha in payload.get("dates") or []:
        dia = parse_date(str(fecha.get("date") or ""))
        if dia is not None:
            por_dia[dia] = sorted(fecha.get("games") or [], key=lambda j: str(j.get("gameDate") or ""))
    return por_dia


@dataclass(frozen=True)
class _Accion:
    """Quién jugó y qué hizo, en dos niveles de precisión.

    `por_equipo` y `lineas` son del DÍA: una sola consulta para toda la liga, y alcanzan mientras un
    jugador juegue una sola vez ese día, que es lo normal.

    `por_lado` es por JUEGO —`(gamePk, equipo)`— y solo existe para los juegos donde el día no basta:
    los que están en curso y los de doble cartelera. Cuando hay entrada acá, manda esta, porque el
    total del día mezclaría los dos juegos en uno.
    """

    por_equipo: dict[int, set[int]]
    lineas: dict[int, str]
    por_lado: dict[tuple[int, int], dict[int, str]]

    def jugadores_de(self, pk: Any, equipo_id: Any) -> set[int] | None:  # noqa: ANN401 — vienen del feed
        """Los de ese lado en ESE juego, o `None` si para este juego alcanza el total del día."""
        detalle = self.por_lado.get((pk, equipo_id))
        return set(detalle) if detalle is not None else None

    def linea_de(self, pk: Any, equipo_id: Any, jugador_id: int) -> str:  # noqa: ANN401 — vienen del feed
        detalle = self.por_lado.get((pk, equipo_id))
        return detalle.get(jugador_id, "") if detalle is not None else self.lineas.get(jugador_id, "")


def _linea_de(stats: dict[str, Any]) -> str:
    """La línea de un jugador a partir de sus dos bloques de estadísticas.

    Un lanzador que además bateó lleva las dos, separadas: son dos oficios y una sola línea que las
    mezclara no se podría leer. El bloque vacío —el del que no hizo ese oficio— no aporta nada.
    """
    from dglweb.stats import daily

    partes = []
    if bateo := stats.get("batting"):
        partes.append(daily.linea_de_bateo(bateo))
    if pitcheo := stats.get("pitching"):
        partes.append(daily.linea_de_pitcheo(pitcheo))
    return " · ".join(partes)


def _accion_del_dia(client: MlbProxyClient, dia: date, universo: set[int]) -> _Accion:
    """Los dominicanos que vieron acción, con su línea. Incluye al relevista y al emergente.

    Las mismas dos llamadas sirven para las dos cosas —marcar el equipo y escribir la línea— porque
    salen del mismo split. Y las líneas se arman con las funciones de `daily`, que son las que ya
    escriben los destacados: dos formas distintas de decir «3-4, 2B, HR» sería una de más.
    """
    from dglweb.stats import daily

    por_equipo: dict[int, set[int]] = {}
    lineas: dict[int, list[str]] = {}
    for grupo, describir in (("hitting", daily.linea_de_bateo), ("pitching", daily.linea_de_pitcheo)):
        for split in daily.splits(client, grupo, dia):
            jugador_id = (split.get("player") or {}).get("id")
            equipo_id = (split.get("team") or {}).get("id")
            if jugador_id not in universo or equipo_id is None:
                continue
            por_equipo.setdefault(equipo_id, set()).add(jugador_id)
            lineas.setdefault(jugador_id, []).append(describir(split.get("stat") or {}))

    return _Accion(
        por_equipo=por_equipo,
        lineas={pid: " · ".join(partes) for pid, partes in lineas.items()},
        por_lado={},
    )


def _pide_boxscore(juego: dict[str, Any]) -> bool:
    """Si a este juego no le alcanza el total del día y hay que preguntarle a él directamente.

    Dos casos, y solo dos, porque cada uno cuesta una llamada:

    * **En curso.** `byDateRange` no publica nada de un juego hasta que termina — está medido: con un
      juego vivo, sus dos equipos son los únicos de los treinta que no aparecen en la consulta del
      día. Sin esto, un juego en curso muestra los nombres y ninguna línea.
    * **Doble cartelera.** Los dos juegos son del mismo día y de los mismos dos equipos, así que el
      total del día son los dos sumados. Sin esto, quien jugó los dos aparece con las mismas cifras
      en ambos, y quien jugó solo el segundo aparece también en el primero.

    Un juego que no ha empezado no entra: su boxscore está vacío y sería una llamada regalada.
    """
    estado = _ESTADOS.get(str((juego.get("status") or {}).get("abstractGameState")), PROGRAMADO)
    if estado == VIVO:
        return True
    return estado == FINAL and str(juego.get("doubleHeader") or "N") != "N"


def _accion_por_juego(client: MlbProxyClient, crudos: list[dict[str, Any]], universo: set[int]) -> _Accion:
    """El detalle de los juegos que lo necesitan, uno por uno. Ver `_pide_boxscore` para cuáles.

    Se guarda por `(juego, equipo)` y no por jugador: en una doble cartelera el mismo jugador tiene
    dos líneas distintas el mismo día, y un diccionario por jugador solo podría quedarse con una.
    """
    por_lado: dict[tuple[int, int], dict[int, str]] = {}
    for juego in crudos:
        if not _pide_boxscore(juego) or (pk := juego.get("gamePk")) is None:
            continue
        try:
            payload = client.get(f"/api/v1/game/{pk}/boxscore")
        except MlbProxyError:
            # Un juego que no contesta no puede tumbar la tira entera: ese se queda con el total del
            # día y los otros catorce salen igual.
            logger.warning("No se pudo leer el boxscore del juego %s.", pk, exc_info=True)
            continue

        for lado in ("away", "home"):
            datos = (payload.get("teams") or {}).get(lado) or {}
            equipo_id = (datos.get("team") or {}).get("id")
            if equipo_id is None:
                continue
            # Se crea aunque quede vacío: la entrada es la que dice «para este juego mando yo», y sin
            # ella el lado volvería al total del día, que es justo lo que se quiere evitar.
            nuestros = por_lado.setdefault((pk, equipo_id), {})
            for jugador in (datos.get("players") or {}).values():
                jugador_id = (jugador.get("person") or {}).get("id")
                # El boxscore trae la novena entera, banca incluida. Los bloques de estadísticas del
                # que no ha entrado vienen vacíos, y esa es la señal de quién realmente jugó.
                linea = _linea_de(jugador.get("stats") or {})
                if jugador_id in universo and linea:
                    nuestros[jugador_id] = linea

    return _Accion(por_equipo={}, lineas={}, por_lado=por_lado)


def _abridor(juego: dict[str, Any], visitante: bool) -> int | None:
    """El abridor probable de un lado, si el calendario ya lo publicó."""
    lado = (juego.get("teams") or {}).get("away" if visitante else "home") or {}
    return (lado.get("probablePitcher") or {}).get("id")


def _anunciados(juego: dict[str, Any], visitante: bool) -> set[int]:
    """La alineación publicada de un lado, más su abridor. Vacía si todavía no la publican."""
    alineaciones = juego.get("lineups") or {}
    jugadores = alineaciones.get("awayPlayers" if visitante else "homePlayers") or []
    ids = {jugador["id"] for jugador in jugadores if jugador.get("id") is not None}

    abridor = _abridor(juego, visitante)
    if abridor is not None:
        ids.add(abridor)
    return ids


def _detalle(juego: dict[str, Any], estado: str) -> str:
    """La frase corta que sitúa el juego: el inning si está vivo, la hora si no ha empezado."""
    detallado = str((juego.get("status") or {}).get("detailedState") or "")
    if detallado in _INCIDENCIAS:
        return _INCIDENCIAS[detallado]

    pizarra = juego.get("linescore") or {}
    if estado == FINAL:
        # Solo se nombra el inning cuando la cuenta se salió de lo normal: «Final (11)» dice algo,
        # «Final (9)» es ruido en todas las filas menos una.
        entradas = pizarra.get("currentInning") or 9
        return f"Final ({entradas})" if entradas != 9 else "Final"
    if estado == VIVO:
        # `Middle` y `End` son los cambios de lado; se cuentan con la mitad que acaba de terminar.
        mitad = "Alta" if str(pizarra.get("inningState") or "") in ("Top", "Middle") else "Baja"
        return f"{mitad} del {pizarra.get('currentInning') or 1}"

    empieza = juego.get("gameDate")
    if not empieza:
        return "Por definir"
    from django.utils.dateparse import parse_datetime

    momento = parse_datetime(str(empieza))
    return _hora_corta(timezone.localtime(momento)) if momento else "Por definir"


def _hora_corta(momento: datetime) -> str:
    """«2:05 pm» — la hora sin el cero de delante, sin depender del sistema operativo.

    Decía `strftime("%-I:%M %p")`, y el `%-` es una extensión de glibc: en Windows levanta
    `ValueError: Invalid format string` (comprobado). Hoy no rompe nada porque el Python de este
    proyecto corre siempre en el contenedor —en el anfitrión ni siquiera está en el PATH— pero una
    dependencia del sistema operativo escondida en un formateador es una trampa para el día que
    alguien corra algo fuera. Del review v9 (DEV-02/QA-02).

    `lstrip("0")` y no un `replace`: solo hay que quitar el cero inicial de la hora, y a las 10, 11 y
    12 no hay ninguno que quitar.
    """
    return momento.strftime("%I:%M %p").lstrip("0").lower()


def _lado(
    juego: dict[str, Any],
    visitante: bool,
    estado: str,
    accion: _Accion,
    universo: set[int],
    nombres: dict[int, tuple[str, str]],
    clips: dict[int, tuple[Any, ...]],
) -> Lado:
    datos = (juego.get("teams") or {}).get("away" if visitante else "home") or {}
    equipo = datos.get("team") or {}
    pk, equipo_id = juego.get("gamePk"), equipo.get("id")

    del_juego = accion.jugadores_de(pk, equipo_id)
    ids = _anunciados(juego, visitante) & universo
    ids |= del_juego if del_juego is not None else accion.por_equipo.get(equipo_id or 0, set())

    abridor = _abridor(juego, visitante)
    # Por nombre y no por id: el orden de un conjunto cambia entre corridas, y una lista que se
    # reordena sola cada minuto en la pantalla se lee como un error.
    nuestros = sorted(
        (
            Nuestro(
                nombre=nombres[pid][0],
                slug=nombres[pid][1],
                linea=accion.linea_de(pk, equipo_id, pid),
                clips=clips.get(pid, ()),
                abridor=pid == abridor,
            )
            for pid in ids
            if pid in nombres
        ),
        key=lambda n: n.nombre,
    )
    marca = datos.get("leagueRecord") or {}

    return Lado(
        codigo=team_code(equipo.get("teamCode")) or str(equipo.get("abbreviation") or ""),
        nombre=str(equipo.get("teamName") or equipo.get("name") or ""),
        # Ruta relativa a `static/`, que es lo que `{% static %}` espera. Los baja
        # `manage.py download_team_logos`; si falta alguno, la plantilla lo omite y no se rompe.
        logo=f"{_LOGOS}{codigo}.svg" if (codigo := team_code(equipo.get("teamCode"))) else "",
        record=f"{marca['W']}-{marca['L']}" if "W" in marca and "L" in marca else "",
        # El calendario manda 0 en los juegos que no han empezado. Mostrarlo sería anunciar un
        # marcador que no existe: un juego de las 8 de la noche no va 0-0 a las 3 de la tarde.
        carreras=None if estado == PROGRAMADO else datos.get("score"),
        ganador=bool(datos.get("isWinner")),
        nuestros=tuple(nuestros),
    )


def _nombres(ids: set[int]) -> dict[int, tuple[str, str]]:
    """`player_id -> (nombre corto, slug)`, de nuestro maestro y no del feed.

    Sin la línea a propósito: en una doble cartelera el mismo jugador tiene dos líneas distintas el
    mismo día, así que la línea no puede vivir en un diccionario por jugador. La pone `_lado`, que sí
    sabe de qué juego está hablando.
    """
    from dglweb.players.models import Player

    nombres = {}
    for jugador in Player.objects.filter(player_id__in=ids):
        inicial = f"{jugador.firstname[:1]}. " if jugador.firstname else ""
        nombres[jugador.player_id] = (f"{inicial}{jugador.lastname_1}", jugador.slug)
    return nombres


def jornada(client: MlbProxyClient, dia: date, crudos: list[dict[str, Any]], universo: set[int]) -> tuple[Juego, ...]:
    """Los juegos de un día, con los dominicanos de cada lado ya resueltos."""
    if not crudos:
        return ()

    accion = _accion_del_dia(client, dia, universo)
    detalle = _accion_por_juego(client, crudos, universo)
    accion.por_lado.update(detalle.por_lado)

    candidatos = {pid for equipo in accion.por_equipo.values() for pid in equipo}
    candidatos |= {pid for lado in accion.por_lado.values() for pid in lado}
    for juego in crudos:
        candidatos |= (_anunciados(juego, visitante=True) | _anunciados(juego, visitante=False)) & universo
    nombres = _nombres(candidatos)

    from dglweb.stats import videos

    clips = videos.por_jugador(dia, candidatos)

    return tuple(
        Juego(
            estado=(estado := _ESTADOS.get(str((juego.get("status") or {}).get("abstractGameState")), PROGRAMADO)),
            detalle=_detalle(juego, estado),
            visitante=_lado(juego, True, estado, accion, universo, nombres, clips),
            local=_lado(juego, False, estado, accion, universo, nombres, clips),
        )
        for juego in crudos
    )


def _armar() -> Pizarra:
    from dglweb.players import universe

    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    universo = universe.debuted()
    with _cliente() as client:
        calendario = _calendario(client, ayer, hoy)
        # Los días sin pelota se caen de la tira en vez de dejar un hueco con la fecha y nada debajo.
        jornadas = tuple(
            Jornada(dia=dia, juegos=jornada(client, dia, calendario.get(dia) or [], universo), es_hoy=dia == hoy)
            for dia in (ayer, hoy)
            if calendario.get(dia)
        )
    return Pizarra(jornadas=jornadas)


def del_dia() -> Pizarra | None:
    """La pizarra que muestra la portada. `None` solo si nunca se pudo armar una.

    Dos cachés a propósito. La corta evita pedirle al proxy una vez por visita. La larga guarda la
    última que salió bien: si el proxy se cae, la portada muestra un marcador de hace unos minutos en
    vez de un hueco. Un marcador levemente viejo es un problema mucho menor que un widget en blanco.
    """
    fresca = cache.get(_CLAVE)
    if fresca is not None:
        return fresca  # type: ignore[no-any-return]

    try:
        pizarra = _armar()
    except MlbProxyError:
        logger.warning("No se pudo armar la pizarra; se muestra la última buena.", exc_info=True)
        return cache.get(_CLAVE_RESPALDO)  # type: ignore[no-any-return]

    cache.set(_CLAVE, pizarra, _FRESCO)
    cache.set(_CLAVE_RESPALDO, pizarra, _RESPALDO)
    return pizarra
