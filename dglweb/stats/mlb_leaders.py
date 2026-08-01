"""Dónde está el dominicano en la carrera de las mayores.

Es lo contrario del motor de líderes del sitio. `build_leaders` responde «quién es el mejor de entre
los nuestros»; esto responde «cuáles de los nuestros están entre los mejores de las mayores». Son dos
preguntas distintas y ninguna de las dos se puede sacar de la otra.

QUÉ TRAE EL ENDPOINT, Y QUÉ NO
------------------------------
`/api/v1/stats/leaders` devuelve el ranking de las mayores por categoría. Medido contra el proxy:

* **`statGroup` es obligatorio.** Sin él, cada categoría vuelve TRES veces —una por oficio— e
  incluye combinaciones sin sentido como `battingAverage / pitching`.
* **El `limit` tiene techo.** Pedir 1000 devuelve ~100 filas de las 485 que existen en jonrones. Por
  eso este endpoint jamás podría producir «líderes dominicanos»: al dominicano del puesto 150 no lo
  ve. Acá no estorba, porque lo que se guarda son los primeros 10 y nada más.
* **El `rank` empata.** Pedir 10 puede devolver 13 filas si hay empates en el décimo puesto, y a los
  empatados les toca igual: los dos son décimos.
* **Los nombres de categoría se normalizan.** `baseOnBalls` vuelve como `walks` y `whip` como
  `walksAndHitsPerInningPitched`. Se piden por su nombre canónico para que la respuesta case.

DOS LLAMADAS Y YA
-----------------
Todas las categorías de un oficio caben en una sola llamada. Bateo y pitcheo juntos tardan poco más
de medio segundo, que es lo que hace viable refrescar esto cada hora en vez de pegarle al proxy en
cada visita.
"""

from dataclasses import dataclass
from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.players import mugshots

# Cuántos puestos del ranking de las mayores interesan. Diez porque es lo que el dueño pidió: estar
# entre los diez primeros de MLB es la noticia; el puesto 40 no lo es.
PUESTOS = 10

# Categoría de MLB -> (grupo, columna) del catálogo `Metric`.
#
# Se cruza contra `Metric` en vez de traer etiquetas propias: ese catálogo ya define cómo se llama y
# cómo se abrevia cada estadística en el sitio (ver docs/AUTORIDAD.md), y una segunda lista de
# nombres acabaría diciendo «CI» donde la otra dice «RBI».
#
# Faltan a propósito las que el catálogo no tiene: `inningsPitched` —nuestras tablas guardan outs— y
# las de MLB que no son columnas nuestras. Se añaden aquí el día que existan allá.
CATEGORIAS: dict[str, tuple[str, str]] = {
    # Bateo
    "homeRuns": ("batting", "hr"),
    "battingAverage": ("batting", "avg"),
    "runsBattedIn": ("batting", "rbi"),
    "hits": ("batting", "h"),
    "runs": ("batting", "r"),
    "stolenBases": ("batting", "sb"),
    "onBasePlusSlugging": ("batting", "ops"),
    "onBasePercentage": ("batting", "obp"),
    "sluggingPercentage": ("batting", "slg"),
    "doubles": ("batting", "x2b"),
    "triples": ("batting", "x3b"),
    "totalBases": ("batting", "tb"),
    "walks": ("batting", "bb"),
    "extraBaseHits": ("batting", "xbh"),
    # Pitcheo
    "wins": ("pitching", "w"),
    "earnedRunAverage": ("pitching", "era"),
    "strikeouts": ("pitching", "so"),
    "saves": ("pitching", "sv"),
    "walksAndHitsPerInningPitched": ("pitching", "whip"),
    "shutouts": ("pitching", "sho"),
    "holds": ("pitching", "hld"),
    "winPercentage": ("pitching", "win_pct"),
    "strikeoutsPer9Inn": ("pitching", "so_per9"),
}

# El endpoint habla de oficios («hitting», «pitching») y el catálogo de grupos («batting»,
# «pitching»). Una llamada por oficio.
_OFICIOS = {"batting": "hitting", "pitching": "pitching"}

# Los mismos treinta SVG que usa la pizarra, con los mismos nombres de archivo. Los baja
# `manage.py download_team_logos`.
_LOGOS = "img/equipos/"


@dataclass(frozen=True)
class Puesto:
    """Un dominicano dentro del top de las mayores en una categoría."""

    categoria: str
    player_id: int
    rank: int
    valor: str
    equipo_id: int | None


def _bloques(client: MlbProxyClient, oficio: str, categorias: list[str], temporada: int) -> list[dict[str, Any]]:
    payload = client.get(
        "/api/v1/stats/leaders",
        {
            "leaderCategories": ",".join(categorias),
            "statGroup": oficio,
            "season": temporada,
            "sportId": 1,
            "limit": PUESTOS,
        },
    )
    return list(payload.get("leagueLeaders") or [])


def traer(client: MlbProxyClient, temporada: int, universo: set[int]) -> list[Puesto]:
    """Los dominicanos que están entre los diez primeros de las mayores, categoría por categoría.

    `universo` es la autoridad de quién es dominicano —`dgl_master`— y no el país que devuelva la
    API. Es la regla de siempre: el `birthCountry` del feed no sirve para esto.
    """
    puestos = []
    for grupo, oficio in _OFICIOS.items():
        categorias = [cat for cat, (g, _) in CATEGORIAS.items() if g == grupo]
        for bloque in _bloques(client, oficio, categorias, temporada):
            categoria = str(bloque.get("leaderCategory") or "")
            if categoria not in CATEGORIAS:
                # El API normaliza algunos nombres; si alguno cambia, se ignora en vez de guardarse
                # sin métrica que lo explique.
                continue
            for hoja in bloque.get("leaders") or []:
                jugador_id = (hoja.get("person") or {}).get("id")
                if jugador_id not in universo:
                    continue
                puestos.append(
                    Puesto(
                        categoria=categoria,
                        player_id=jugador_id,
                        rank=int(hoja.get("rank") or 0),
                        # Tal cual lo manda el API: «.328», «143.2», «29». Convertirlo a número
                        # perdería los ceros y los decimales con que cada estadística se escribe.
                        valor=str(hoja.get("value") or ""),
                        equipo_id=(hoja.get("team") or {}).get("id"),
                    )
                )
    return puestos


def guardar(temporada: int, puestos: list[Puesto], codigos: dict[int, str]) -> int:
    """Reemplaza la foto de ESA temporada. Devuelve cuántas filas quedaron.

    Se borra y se reescribe, no se hace upsert: quien salió del top 10 desde el refresco anterior
    tiene que desaparecer, y un upsert lo dejaría ahí para siempre con su último puesto.

    El borrado va acotado a la temporada que se está escribiendo y no a la tabla entera, para que
    reprocesar una vieja con `--temporada` no tumbe la foto de la que está en curso. De las que
    sobren se encarga `podar`.
    """
    from django.db import transaction

    from dglweb.players.models import Player
    from dglweb.stats.models import Metric, MlbLeader

    conocidos = set(Player.todos.values_list("player_id", flat=True))
    metricas = {(m.stat_group, m.column): m.pk for m in Metric.objects.all()}

    filas = []
    for puesto in puestos:
        metrica = metricas.get(CATEGORIAS[puesto.categoria])
        if metrica is None or puesto.player_id not in conocidos:
            continue
        filas.append(
            MlbLeader(
                metric_id=metrica,
                player_id=puesto.player_id,
                season=temporada,
                rank=puesto.rank,
                valor=puesto.valor,
                team=codigos.get(puesto.equipo_id or 0, ""),
            )
        )

    with transaction.atomic():
        MlbLeader.objects.filter(season=temporada).delete()
        MlbLeader.objects.bulk_create(filas)
    return len(filas)


# Las cajas que caben sin desplegar: tres filas de dos columnas. Con esas o menos, separar los
# oficios en pestañas no ahorra espacio —ya estaban todas a la vista— y solo agrega un clic.
SIN_PESTANAS = 6


def nombre_corto(nombre: str) -> str:
    """«Fernando Tatis Jr.» → «F. Tatis Jr.», «Juan Soto» → «J. Soto».

    Todos por igual, quepan o no. Abreviar solo a los largos dejaba una columna despareja —unos con
    pila y otros con inicial— y esa irregularidad se nota más que el nombre completo que se pierde.

    Se sacrifica la pila y no el apellido porque es el apellido el que identifica al pelotero. Es
    también lo contrario de lo que haría dejar que el CSS lo recorte: los puntos suspensivos se
    comerían el final, que es la parte que importa.

    Un nombre de una sola palabra se deja como está: no hay pila que quitar, y dejarlo en una letra
    sería borrarlo.
    """
    pila, _, resto = nombre.partition(" ")
    return f"{pila[:1]}. {resto}" if resto else nombre


def portada(metricas: int = 5) -> dict[str, Any] | None:
    """Lo que muestra el widget: por oficio, una entrada por métrica con los nuestros que están ahí.

    `metricas` es cuántas se ven sin desplegar; el resto llega con «ver más». No se recorta en la
    consulta porque son treinta filas en total: traerlas todas y esconder unas cuantas con CSS cuesta
    menos que ir al servidor otra vez cuando el lector abre el panel.

    Devuelve `None` con la tabla vacía —temporada sin empezar, o el refresco horario nunca corrió—
    para que la plantilla no dibuje un panel hueco.

    ESTE WIDGET NO SE APAGA FUERA DE TEMPORADA, al revés que los otros cuatro (dueño, 2026-08-01).
    Solo pide que ALGUNA temporada haya empezado ya. El motivo es lo que cada uno afirma: en febrero,
    «los mejores de la liga» sigue siendo cierto sobre la temporada que se acaba de jugar, mientras
    que «los destacados de ayer y hoy» sería mentira. La tabla es una foto que se reescribe entera en
    cada refresco, así que fuera de temporada conserva sola la última buena. Ver
    `season_window.hay_temporada_empezada`.
    """
    from dglweb.players.visibility import only_visible
    from dglweb.stats import season_window
    from dglweb.stats.models import MlbLeader

    if not season_window.hay_temporada_empezada():
        return None

    # `only_visible` saca a los jugadores dados de baja. Va acá al leer y no al construir: el dato
    # crudo debe seguir entrando, así reactivar a alguien es instantáneo y no exige otro refresco.
    #
    # Y acá **no hay que renumerar nada**, al revés que en `dgl_leader`. Ese `rank` no lo calculamos
    # nosotros: viene del API de MLB y es el puesto absoluto en las mayores. Si el 5.º queda oculto,
    # el widget enseña «2.º y 7.º» y las dos cosas siguen siendo ciertas.
    filas = (
        only_visible(MlbLeader.objects.filter(metric__visible_en_widget_lideres=True))
        .select_related("metric", "player")
        .order_by("metric__stat_group", "metric__sort_order", "rank", "player__lastname_1")
    )

    oficios: dict[str, list[dict[str, Any]]] = {"batting": [], "pitching": []}
    temporada = None
    for fila in filas:
        grupo = oficios.get(fila.metric.stat_group)
        if grupo is None:
            continue
        temporada = fila.season
        # La ruta de la foto se arma acá y no con `{% static %}` en la plantilla. Ver `mugshots`.
        fila.foto = mugshots.url(fila.player_id, mugshots.CHICO)  # type: ignore[attr-defined]
        # El logo sí va por `{% static %}`, como en la pizarra: esos treinta SVG sí viven en la
        # imagen. Se arma la ruta completa —y no un prefijo más el código en la plantilla— porque el
        # manifiesto de producción resuelve archivos, no pedazos de ruta.
        fila.logo = f"{_LOGOS}{fila.team}.svg" if fila.team else ""  # type: ignore[attr-defined]
        fila.nombre = nombre_corto(fila.player.full_name)  # type: ignore[attr-defined]
        # Una entrada por métrica, con todos los nuestros que caen ahí. El primero de la lista es el
        # mejor rankeado, porque así vienen ordenadas.
        if grupo and grupo[-1]["metrica"] == fila.metric:
            grupo[-1]["puestos"].append(fila)
        else:
            grupo.append({"metrica": fila.metric, "puestos": [fila]})

    if temporada is None:
        return None

    # Si todo cabe en las filas que se ven, las pestañas no esconden nada: son un clic para llegar a
    # algo que ya estaba a la vista. Solo aparecen cuando de verdad hay que repartir el espacio.
    total = sum(len(grupo) for grupo in oficios.values())
    grupos = (
        (("bateo", "Bateo", oficios["batting"]), ("pitcheo", "Pitcheo", oficios["pitching"]))
        if total > SIN_PESTANAS
        # Bateo primero y pitcheo después, sin entremezclar las categorías: el orden dentro de cada
        # oficio lo pone el catálogo, y alternarlos rompería esa secuencia sin ganar nada.
        else (("todos", "", [*oficios["batting"], *oficios["pitching"]]),)
    )
    return {
        "oficios": grupos,
        "con_pestanas": len(grupos) > 1,
        "visibles": metricas,
        "temporada": temporada,
        # EL TÍTULO CAMBIA CUANDO LA TEMPORADA SE ACABA (dueño, 2026-08-01). En curso dice «En el top
        # 10 de la liga»; terminada, «En el top 10 del 2026». Es la única forma de que el widget siga
        # siendo cierto los cinco meses de invierno en que enseña la temporada anterior: sin el año,
        # «la liga» se lee como la de ahora.
        #
        # La decisión es de Python porque es una regla de fechas; las palabras son de la plantilla.
        "terminada": season_window.temporada_terminada(temporada),
    }


def podar(temporada_activa: int | None) -> int:
    """Borra las temporadas que ya no están en curso. Devuelve cuántas filas se fueron.

    El puesto en el ranking solo significa algo mientras la temporada corre: «#6 en jonrones» de una
    temporada cerrada no es una foto vieja, es una frase falsa —el ranking final quedó en otro sitio
    y esta tabla nunca guardó el cierre. Lo de por vida y lo histórico vive en `Leader`.

    Sin temporada activa NO se borra nada, igual que en `stats.daily`: es el caso de que nadie marcó
    la nueva en el Backoffice, y ahí una tabla con datos viejos es un problema menor que una vacía.
    """
    from dglweb.stats.models import MlbLeader

    if temporada_activa is None:
        return 0
    borradas, _ = MlbLeader.objects.exclude(season=temporada_activa).delete()
    return int(borradas)
