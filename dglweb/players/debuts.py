"""Detectar debuts: quién de los que todavía no habían llegado aparece con estadísticas.

La detección no necesita heurísticas porque la estructura de los datos ya la contesta. `dom_players`
son los dominicanos SIN debut y `dgl_master` los que SÍ debutaron, y las dos tablas son disjuntas por
construcción. Entonces **un debut es exactamente un `player_id` que estaba en la primera y aparece
con estadísticas de Grandes Ligas.** Un cruce de conjuntos, no una inferencia.

Lo que NO se hace acá, y conviene que quede dicho: mirar el país de nacimiento de la API para
descubrir dominicanos nuevos. La regla de autoridad lo prohíbe y además no serviría — de los 1.324
jugadores con estadísticas de una temporada, unos 1.200 están fuera del universo, o sea el resto del
mundo. La cobertura de esta detección es, exactamente, la cobertura de `dom_players`.

Es un WORKLIST, no un aviso de una sola vez: mientras el debutante siga sin estar en `dgl_master`
vuelve a salir todos los días. Deja de salir cuando el dueño lo carga, porque entonces la resta de
`universe.not_debuted()` ya no lo incluye. Cargarlo ES el acuse de recibo.
"""

from dataclasses import dataclass
from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.players import universe

# Los dos oficios alcanzan: para tener estadísticas hay que batear o lanzar. Un jugador que solo
# apareciera en fildeo tendría que haber entrado a un juego sin batear ni lanzar, lo que en la
# práctica no ocurre — y si ocurriera, lo pescaría el barrido del día siguiente.
_GRUPOS = ("hitting", "pitching")
_LIMITE = 8000  # la liga entera entra de sobra; el mismo tope que usa el descargador de stats


@dataclass(frozen=True)
class Debut:
    """Un debutante detectado. `debut_date` viene de la API y puede faltar si aún no la publicó."""

    player_id: int
    full_name: str
    debut_date: str | None

    def __str__(self) -> str:
        return f"{self.player_id} {self.full_name} (debut {self.debut_date or 'sin fecha'})"


def players_with_stats(client: MlbProxyClient, season: int) -> set[int]:
    """Todos los `player_id` con estadísticas de la temporada, de toda la liga.

    Dos llamadas bulk, una por oficio. Es el mismo tipo de consulta que ya hace el refresco diario
    —trae la liga y se filtra en memoria— así que el costo no depende de cuántos dominicanos haya.
    """
    con_stats: set[int] = set()
    for grupo in _GRUPOS:
        payload = client.get(
            "/api/v1/stats",
            {"stats": "season", "group": grupo, "season": season, "playerPool": "All", "limit": _LIMITE},
        )
        for bloque in payload.get("stats") or []:
            for split in bloque.get("splits") or []:
                player_id = (split.get("player") or {}).get("id")
                if player_id is not None:
                    con_stats.add(int(player_id))
    return con_stats


def _detail(client: MlbProxyClient, player_id: int) -> Debut:
    """Nombre y fecha de debut, de la API. Una llamada por candidato — son un puñado al año.

    Si la llamada falla, el debut igual se reporta: lo que importa es que el dueño se entere de que
    hay alguien que cargar, y el nombre lo puede buscar. Perder el aviso por un timeout sería mucho
    peor que reportarlo sin adornos.
    """
    try:
        persona: dict[str, Any] = (client.get(f"/api/v1/people/{player_id}", {}).get("people") or [{}])[0]
    except Exception:  # cualquier fallo de red degrada el detalle, nunca el aviso
        return Debut(player_id=player_id, full_name="(no se pudo consultar)", debut_date=None)
    return Debut(
        player_id=player_id,
        full_name=persona.get("fullName") or "(sin nombre)",
        debut_date=persona.get("mlbDebutDate"),
    )


def detect(client: MlbProxyClient, season: int) -> list[Debut]:
    """Los dominicanos sin debut que ya tienen estadísticas de `season`, ordenados por nombre."""
    candidatos = universe.not_debuted() & players_with_stats(client, season)
    return sorted((_detail(client, player_id) for player_id in candidatos), key=lambda d: d.full_name)
