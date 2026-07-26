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
# Piso de cobertura POR TEMPORADA (no por fila — ver `checks`).
#
# Medido: los años 2000 en adelante van de 97 a 100%, pero los primeros bajan porque la fuente
# clasificaba menos — 1990 da 89,6%, y `derive.FIRST_STATCAST_SEASON` documenta que la cobertura de
# NUESTRA fuente en ese mismo año ronda el 90%. O sea que ~90% es el suelo histórico legítimo, no un
# síntoma.
#
# Por eso el piso va en 80%: deja pasar la realidad de los primeros años y sigue atajando lo que esta
# prueba busca, que no es una temporada floja sino una vacía. Para calibrar: cuando la API de MLB
# entregó 2000 incompleto, dio 1,8%.
_COBERTURA_MINIMA = 0.80


@register
class BattedBallHitsLoader(Loader):
    """Hits por tipo de batazo, desde Retrosheet.

    Por qué existe: a la API de MLB le faltan hits por tipo en diez temporadas (1989-90, 1993-97,
    2000-02) y en 2000-2001 entrega menos del 2%. Retrosheet los tiene con ~97% de cobertura.

    El CSV lo produce `static_data/scripts/export_batted_ball_hits.ps1`. Viene por `mlb_id` —la misma
    llave con la que trabaja el sitio— así que acá solo se traduce a la FK; el retroID se queda del
    lado de SQL Server, que es donde sirve para unir con los eventos de Retrosheet.

    Arranca en 1989, igual que `derive.FIRST_STATCAST_SEASON`: antes del 88 la clasificación de
    batazos de Retrosheet tampoco está completa, así que los dos cortes coinciden.
    """

    table = "dgl_batted_ball_hits"
    model = BattedBallHits
    # `post_apply` deja los coeficientes de la fila de temporada al día, pero de ahí para arriba todo
    # sigue viejo: los totales de carrera los suman y los liderazgos los rankean. Van en este orden
    # porque los líderes de por vida leen los totales de carrera.
    rebuilds: ClassVar[tuple[str, ...]] = ("build_career_totals", "build_leaders")
    columns: ClassVar[dict[str, str]] = {
        "mlb_id": "player",
        "season": "season",
        "stat_group": "stat_group",
        "ground_hits": "ground_hits",
        "fly_hits": "fly_hits",
        "line_hits": "line_hits",
        "pop_hits": "pop_hits",
        # Solo para la prueba de aceptación, no se guardan. `h_typed` son los hits CON trayectoria
        # y `h_all` todos: a Retrosheet le falta la trayectoria en ~2,5%, así que no coinciden.
        "h_typed": "__h_typed",
        "h_all": "__h_all",
    }

    def __init__(self) -> None:
        self._by_mlb: dict[int, int] = {}  # lo llena `prepare`
        self._huerfanas: list[dict[str, Any]] = []  # ídem

    def prepare(self) -> None:
        # Una sola consulta para todo el CSV. Sin esto, `resolve` haría una por línea.
        self._by_mlb = dict(Player.todos.values_list("player_id", "pk"))
        self._huerfanas = []  # filas cuyo mlb_id no está en el maestro; se reportan en `checks`

    def resolve(self, row: dict[str, str]) -> dict[str, Any] | None:
        crudo = (row.get("mlb_id") or "").strip()
        if not crudo:
            return None  # una fila de dglMaster sin mlbID: no la podemos casar
        player_id = self._by_mlb.get(int(crudo))
        if player_id is None:
            # NO se descarta en silencio. El maestro es la autoridad del subconjunto dominicano, así
            # que un mlb_id que no está ahí significa que falta cargar un jugador — y si se ignora,
            # sus hits desaparecen del dataset Y del cálculo de cobertura, con lo cual el CSV parece
            # MÁS sano de lo que está. La validación se autoengañaba.
            self._huerfanas.append(
                {
                    "mlb_id": crudo,
                    "season": int(row["season"]),
                    "h_typed": int(row["h_typed"] or 0),
                    "h_all": int(row["h_all"] or 0),
                }
            )
            return None
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
            "__h_typed": int(row["h_typed"] or 0),
            "__h_all": int(row["h_all"] or 0),
        }

    def checks(self, rows: list[dict[str, Any]]) -> list[Problem]:
        """Dos pruebas, cada una en su grano.

        1) Por fila, EXACTA: los cuatro tipos tienen que sumar `h_typed`, que son justamente los
           hits que se repartieron entre ellos. Cualquier diferencia es un error de armado del CSV.

        2) Por TEMPORADA, no por fila: qué fracción de los hits trae trayectoria. Medirlo por fila
           era un error — con 7 hits, uno solo sin tipificar da 57% y eso es ruido de muestra chica,
           no un export malo. Un export incompleto se manifiesta como una temporada entera caída,
           que es lo que esta prueba tiene que cazar. Referencia medida: 1999 al 100%, 2000-2002
           entre 97 y 98%.
        """
        rotas = []
        # Por (temporada, OFICIO), no solo por temporada: bateo y pitcheo son universos distintos, y
        # promediarlos deja pasar un oficio roto escondido tras el otro completo.
        cobertura: dict[tuple[int, str], list[int]] = {}
        for row in rows:
            tipos = row["ground_hits"] + row["fly_hits"] + row["line_hits"] + row["pop_hits"]
            if tipos != row["__h_typed"]:
                quien = f"jugador {row['player_id']} {row['season']} ({row['stat_group']})"
                rotas.append(f"{quien}: {tipos} ≠ {row['__h_typed']} tipificados")
            acumulado = cobertura.setdefault((row["season"], row["stat_group"]), [0, 0])
            acumulado[0] += row["__h_typed"]
            acumulado[1] += row["__h_all"]

        problems = []
        if rotas:
            problems.append(
                Problem(f"Los cuatro tipos no suman los hits tipificados en {len(rotas)} fila(s).", rotas[:10])
            )
        if self._huerfanas:
            perdidos = sum(h["h_all"] for h in self._huerfanas)
            ids = sorted({h["mlb_id"] for h in self._huerfanas})
            problems.append(
                Problem(
                    f"{len(ids)} jugador(es) del CSV no están en el maestro, y se perderían "
                    f"{perdidos:,} hits. Cargá el maestro antes que el dato de apoyo: si no, esos "
                    "jugadores quedan fuera de los rankings sin que nada lo diga.",
                    [f"mlb_id {i}" for i in ids[:10]],
                )
            )
        flojas = [
            f"{season} ({group}): {tip:,} de {todos:,} hits con trayectoria ({100 * tip / todos:.1f}%)"
            for (season, group), (tip, todos) in sorted(cobertura.items())
            if todos and tip / todos < _COBERTURA_MINIMA
        ]
        if flojas:
            problems.append(
                Problem(
                    f"{len(flojas)} temporada(s)/oficio por debajo del {_COBERTURA_MINIMA:.0%} de hits "
                    "tipificados. Lo normal es 97-100%; muy por debajo suele ser un export incompleto.",
                    flojas,
                )
            )
        return problems

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
                # Solo se pisa el dato del proxy cuando el de Retrosheet tipifica MÁS. Sin esta
                # guarda, cargar el CSV completo degradaba las temporadas sanas: el proxy tipifica el
                # 100% desde 2004 y Retrosheet ~97,5%, así que sobrescribir a ciegas cambiaba dato
                # bueno por dato peor. El CSV trae todo el rango a propósito —no hay que mantener una
                # lista de años rotos— y es acá donde se decide fila por fila cuál fuente gana.
                actual = sum(
                    getattr(linea, campo) or 0 for campo in ("ground_hits", "fly_hits", "line_hits", "pop_hits")
                )
                entrante = sum(nuevo[campo] for campo in ("ground_hits", "fly_hits", "line_hits", "pop_hits"))
                if entrante <= actual:
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
