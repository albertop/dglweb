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
