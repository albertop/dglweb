"""Un loader por dataset. Esto es TODO lo que hay que escribir para sumar una tabla de apoyo.

El motor (`engine.py`) ya se encarga de leer el CSV, validar columnas, exigir que la clave natural
sea única, armar la comparación y aplicar en una transacción. Acá solo va lo que el motor no puede
adivinar: qué columna del CSV es qué campo, cómo se resuelve una referencia externa, y qué hace que
ESTE dataset esté sano.
"""

from typing import Any, ClassVar

from dglweb.players.models import Player
from dglweb.stats.models import BattedBallHits, Batting, Pitching
from dglweb.stats.staticdata.engine import Loader, Problem, register

_GROUPS = {"batting", "pitching"}


@register
class BattedBallHitsLoader(Loader):
    """Hits por tipo de batazo, desde Retrosheet.

    Por qué existe: a la API de MLB le faltan hits por tipo en diez temporadas (1989-90, 1993-97,
    2000-02) y en 2000-2001 entrega menos del 2%. Retrosheet los tiene con ~97% de cobertura.

    El CSV lo produce `static_data/export_batted_ball_hits.ps1` y viene por `retro_id` porque es la
    llave con la que Retrosheet identifica al jugador; acá se traduce a nuestra FK.
    """

    table = "dgl_batted_ball_hits"
    model = BattedBallHits
    columns: ClassVar[dict[str, str]] = {
        "retro_id": "player",
        "season": "season",
        "stat_group": "stat_group",
        "ground_hits": "ground_hits",
        "fly_hits": "fly_hits",
        "line_hits": "line_hits",
        "pop_hits": "pop_hits",
        # Solo para la prueba de aceptación: es el total de hits que el proxy ya tiene, y sirve para
        # comprobar que los cuatro tipos suman. No se guarda.
        "h": "__h",
    }

    def __init__(self) -> None:
        self._by_retro: dict[str, int] = {}  # lo llena `prepare`

    def prepare(self) -> None:
        # Una sola consulta para todo el CSV. Sin esto, `resolve` haría una por línea.
        pares = Player.objects.exclude(retro_id="").exclude(retro_id=None).values_list("retro_id", "pk")
        self._by_retro = {retro: pk for retro, pk in pares if retro}

    def resolve(self, row: dict[str, str]) -> dict[str, Any] | None:
        retro = (row.get("retro_id") or "").strip()
        if not retro:
            return None  # Retrosheet trae eventos de todos; sin retro_id no es de los nuestros
        player_id = self._by_retro.get(retro)
        if player_id is None:
            return None  # no está en nuestro maestro: no es dominicano, o es un alta que falta
        group = (row.get("stat_group") or "").strip()
        if group not in _GROUPS:
            raise ValueError(f"stat_group inválido: {group!r}")
        return {
            "player_id": player_id,
            "season": int(row["season"]),
            "stat_group": group,
            "ground_hits": int(row["ground_hits"] or 0),
            "fly_hits": int(row["fly_hits"] or 0),
            "line_hits": int(row["line_hits"] or 0),
            "pop_hits": int(row["pop_hits"] or 0),
            "__h": int(row["h"] or 0),
        }

    def checks(self, rows: list[dict[str, Any]]) -> list[Problem]:
        """Los cuatro tipos son una partición de los hits, así que TIENEN que sumar H.

        Es una prueba exacta, no un umbral: con datos sanos da clavado (1999 = 4.957 = 4.957). Es
        justo la prueba que le faltaba a nuestra fuente y que dejó pasar diez temporadas rotas.
        """
        malas = []
        for row in rows:
            tipos = row["ground_hits"] + row["fly_hits"] + row["line_hits"] + row["pop_hits"]
            if tipos != row["__h"]:
                quien = f"jugador {row['player_id']} {row['season']} ({row['stat_group']})"
                malas.append(f"{quien}: {tipos} ≠ {row['__h']}")
        if not malas:
            return []
        return [
            Problem(f"Los cuatro tipos no suman H en {len(malas)} fila(s).", malas[:10]),
        ]

    def post_apply(self, rows: list[dict[str, Any]]) -> None:
        """Reescribe los hits por tipo en la fila de temporada y recalcula sus coeficientes.

        Cargar los hits no sirve de nada si GB%/FB%/LD%/PU% —que salen de ellos— siguen calculados
        con los viejos. Corre dentro de la transacción del import: o queda todo consistente o nada.

        Se toca SOLO la fila de temporada (`season_totals`: la combinada `XXX`, o la única si no hubo
        cambio de equipo), porque el dato de Retrosheet viene por (jugador, temporada) y repartirlo
        entre los stints exigiría casar sus códigos de equipo con los nuestros. Las líneas por equipo
        de una temporada con traspaso conservan lo que dio el proxy; los líderes y los coeficientes
        del perfil leen el total, que es el que queda corregido.
        """
        from dglweb.stats.derive import batted_ball_coefficients

        por_oficio: dict[str, dict[tuple[int, int], dict[str, int]]] = {"batting": {}, "pitching": {}}
        for row in rows:
            por_oficio[row["stat_group"]][row["player_id"], row["season"]] = row

        for group, model in (("batting", Batting), ("pitching", Pitching)):
            objetivo = por_oficio[group]
            if not objetivo:
                continue
            temporadas = {season for _, season in objetivo}
            actualizadas: list[Any] = []
            for linea in model.objects.filter(season__in=temporadas).season_totals():
                nuevo = objetivo.get((linea.player_id, linea.season))
                if nuevo is None:
                    continue
                for campo in ("ground_hits", "fly_hits", "line_hits", "pop_hits"):
                    setattr(linea, campo, nuevo[campo])
                for campo, valor in batted_ball_coefficients(_as_dict(linea)).items():
                    setattr(linea, campo, valor)
                actualizadas.append(linea)
            if actualizadas:
                campos = ["ground_hits", "fly_hits", "line_hits", "pop_hits", *_COEFFICIENT_FIELDS]
                model._default_manager.bulk_update(actualizadas, campos)


_COEFFICIENT_FIELDS = ("gb_pct", "fb_pct", "ld_pct", "pu_pct", "gb_fb", "contact_pct", "whiff_pct")


def _as_dict(linea: Batting | Pitching) -> dict[str, Any]:
    """Los campos que `batted_ball_coefficients` lee, tomados de la fila ya modificada."""
    campos = (
        "ground_outs",
        "fly_outs",
        "pop_outs",
        "line_outs",
        "ground_hits",
        "fly_hits",
        "pop_hits",
        "line_hits",
        "balls_in_play",
        "total_swings",
        "swing_and_misses",
    )
    return {campo: getattr(linea, campo, None) for campo in campos}
