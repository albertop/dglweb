"""Un loader por dataset. Esto es TODO lo que hay que escribir para sumar una tabla de apoyo.

El motor (`engine.py`) ya se encarga de leer el CSV, validar columnas, exigir que la clave natural
sea única, armar la comparación y aplicar en una transacción. Acá solo va lo que el motor no puede
adivinar: qué columna del CSV es qué campo, cómo se resuelve una referencia externa, y qué hace que
ESTE dataset esté sano.
"""

import logging
from datetime import date
from typing import Any, ClassVar

from dglweb.players.models import Player
from dglweb.stats.models import (
    BattedBallHits,
    Batting,
    DomPlayer,
    DomSalary,
    Efemeride,
    Pitching,
    SeasonDates,
    fechas_fuera_de_orden,
)
from dglweb.stats.staticdata.engine import Loader, Problem, register

logger = logging.getLogger(__name__)

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
        from dglweb.stats.derive import batted_ball_coefficients, batted_ball_excess

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
                # La reconciliación contra `balls_in_play` (SAB-02), medida ANTES y DESPUÉS de poner
                # los hits nuevos. Si los cuatro tipos no caben en los batazos que reportó el proxy,
                # las cuatro proporciones suman más de 100%: imposible.
                #
                # AVISA Y SIGUE. NUNCA CORTA. Regla del dueño (2026-07-27), y no es pereza:
                #
                #   «MLB es la máxima autoridad y nosotros simples consumidores. Si nos dan data
                #   mala, ¿qué podemos hacer? Hay que aceptarlo y seguir adelante.»
                #
                # La versión anterior levantaba `ValueError` acá dentro, o sea abortaba la
                # transacción del import entero. Eso convertía un descuadre de UN batazo en la fuente
                # —Soriano 2010, medido: 165 contra 164— en una carga que no entra, un job en rojo y
                # a alguien depurando un CSV que estaba bien. El precio de parar es enorme y el de
                # seguir es un porcentaje 0,6 puntos raro que nadie suma en pantalla.
                #
                # Se sigue midiendo antes y después para poder decir en el aviso si el descuadre lo
                # trajimos nosotros o ya venía; el recuento completo lo da `check_batted_balls`.
                antes = batted_ball_excess(_as_dict(linea))
                for campo in ("ground_hits", "fly_hits", "line_hits", "pop_hits"):
                    setattr(linea, campo, nuevo[campo])
                despues = batted_ball_excess(_as_dict(linea))
                if despues is not None and despues > 0:
                    origen = "ya venía así" if antes is not None and antes >= despues else "lo empeora este CSV"
                    logger.warning(
                        "Batazos por encima de BIP (%s): jugador %s %s (%s) — %s de más sobre %s "
                        "balls in play. Los coeficientes suman más de 100%%. Se carga igual; "
                        "auditar con `manage.py check_batted_balls`.",
                        origen,
                        linea.player_id,
                        linea.season,
                        group,
                        despues,
                        linea.balls_in_play,
                    )
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


@register
class DomPlayersLoader(Loader):
    """Dominicanos en el sistema profesional, con y sin debut en Grandes Ligas.

    El CSV lo produce `static_data/scripts/export_dom_players.ps1` desde la vista
    `v_dglweb_master_no_debuts` de SQL Server. Se reemplaza entera (truncate): el dato viejo de esta
    tabla no se conserva ni se reconcilia.

    La validación es a propósito flaca. La única columna que importa es `player_id` —tiene que venir
    y ser única, y de eso se encarga el motor— porque el resto es descriptivo: un prospecto recién
    cargado puede no tener ni fecha de nacimiento, y así y todo hay que poder listarlo.

    No declara `rebuilds`: no alimenta ningún cálculo. Los liderazgos salen de `dgl_master`, que es
    otra tabla y otra autoridad.
    """

    table = "dom_players"
    model = DomPlayer
    # El peso es un atributo del pelotero, no una medida acumulable: sumarlo daba 1.640.576 libras,
    # un número que no dice nada. Sin medidas que mostrar, la comparación se queda con las filas,
    # que acá es justamente lo único que importa.
    no_sum: ClassVar[tuple[str, ...]] = ("weight",)
    columns: ClassVar[dict[str, str]] = {
        "player_id": "player_id",
        "last_name": "last_name",
        "first_name": "first_name",
        "full_name": "full_name",
        "birth_date": "birth_date",
        "birth_place": "birth_place",
        "bats": "bats",
        "throws": "throws",
        "height": "height",
        "weight": "weight",
        "is_active": "is_active",
        "is_player": "is_player",
        "is_verified": "is_verified",
    }

    _TEXTO: ClassVar[tuple[str, ...]] = ("last_name", "first_name", "full_name", "birth_place", "bats", "throws")
    _BOOLEANOS: ClassVar[tuple[str, ...]] = ("is_active", "is_player", "is_verified")

    def resolve(self, row: dict[str, str]) -> dict[str, Any]:
        """Traduce los tres tipos que cambian de forma al cruzar la frontera.

        `player_id` sin valor levanta `ValueError`, que el motor convierte en un problema con el
        número de línea. NO se descarta en silencio: una fila sin identificador es un CSV mal armado,
        y tragársela dejaría un archivo que parece más sano de lo que está.
        """
        crudo = (row.get("player_id") or "").strip()
        if not crudo:
            raise ValueError("player_id vacío")

        resuelta: dict[str, Any] = {"player_id": int(crudo)}
        # Se recorta al largo del campo: un nombre de más no puede tumbar una carga de 9.000 filas.
        largos = {campo.name: campo.max_length for campo in DomPlayer._meta.fields}
        resuelta.update({campo: _texto(row.get(campo), largos[campo]) for campo in self._TEXTO})
        resuelta["height"] = _texto(row.get("height"), largos["height"])
        resuelta["birth_date"] = _fecha(row.get("birth_date"))
        resuelta["weight"] = _entero(row.get("weight"))
        resuelta.update({campo: _booleano(row.get(campo)) for campo in self._BOOLEANOS})
        return resuelta


@register
class EfemeridesLoader(Loader):
    """Efemérides dominicanas: lo que pasó «un día como hoy».

    El CSV lo produce `static_data/efemerides/exportar_efemerides.ps1`, que corre 96 detectores
    contra SQL Server y trae el texto YA REDACTADO. El diseño está en `docs/EFEMERIDES.md`.

    SE REEMPLAZA ENTERA. Retrosheet publica una vez al año y entre publicación y publicación el
    pasado no cambia, así que no hay nada que reconciliar: `truncate` y listo.

    NO DECLARA `rebuilds`. No alimenta ningún cálculo del sitio — es contenido terminado, no una
    fuente de la que se deriven otras tablas.

    POR QUÉ LA VALIDACIÓN NO MIRA EL CONTENIDO. El exportador ya trae sus propias autocomprobaciones
    —puntaje dentro de rango, ninguna fila sin titular, ningún marcador `{campo}` sin rellenar,
    ninguna clave repetida tras la fusión— y las corre sobre los datos completos, que es donde se
    pueden comprobar. Repetirlas acá sería duplicar la regla en dos lenguajes y arriesgarse a que se
    separen. Lo que sí se comprueba es lo que el CSV puede romper AL CRUZAR LA FRONTERA: tipos,
    fechas y campos obligatorios.
    """

    table = "dgl_efemerides"
    model = Efemeride
    # Ninguno de estos números es una medida acumulable, así que sumarlos no dice nada: `mes` y `dia`
    # son coordenadas, `signo` vale ±1, `magnitud` cambia de unidad según el tipo —jonrones en uno,
    # WPA en otro— y los conteos son atributos de la fila, no cantidades. Sin medidas que sumar, la
    # comparación se queda con las filas, que es lo que de verdad hay que mirar antes de reemplazar
    # el archivo entero.
    no_sum: ClassVar[tuple[str, ...]] = (
        "signo", "mes", "dia", "temporada", "anos", "event_id", "en_casa",
        "magnitud", "wpa_jugador", "li_max", "rareza", "puntaje",
        "veces_total", "jugadores_total", "orden", "veces_jugador", "orden_jugador",
    )
    columns: ClassVar[dict[str, str]] = {
        "tipo": "tipo",
        "gesta": "gesta",
        "etiquetas": "etiquetas",
        "rol": "rol",
        "signo": "signo",
        "cobertura": "cobertura",
        "mlb_id": "mlb_id",
        "nombre": "nombre",
        "fecha": "fecha",
        "mes": "mes",
        "dia": "dia",
        "temporada": "temporada",
        "anos": "anos",
        "game_id": "game_id",
        "event_id": "event_id",
        "game_type": "game_type",
        "equipo": "equipo",
        "equipo_nombre": "equipo_nombre",
        "rival": "rival",
        "rival_nombre": "rival_nombre",
        "en_casa": "en_casa",
        "oponente": "oponente",
        "magnitud": "magnitud",
        "wpa_jugador": "wpa_jugador",
        "li_max": "li_max",
        "detalle": "detalle",
        "veces_total": "veces_total",
        "jugadores_total": "jugadores_total",
        "orden": "orden",
        "veces_jugador": "veces_jugador",
        "orden_jugador": "orden_jugador",
        "rareza": "rareza",
        "puntaje": "puntaje",
        "titular": "titular",
        "situacion": "situacion",
        "participantes": "participantes",
    }

    # Los que no admiten vacío: sin ellos la fila no se puede ni pintar ni ordenar.
    _OBLIGATORIOS: ClassVar[tuple[str, ...]] = ("tipo", "mlb_id", "fecha", "titular")
    _TEXTO: ClassVar[tuple[str, ...]] = (
        "tipo", "gesta", "etiquetas", "rol", "cobertura", "nombre",
        "game_id", "game_type", "equipo", "equipo_nombre", "rival", "rival_nombre",
        "oponente", "detalle",
    )
    # `titular` y `situacion` son `TextField`, sin `max_length`: no se recortan.
    _LIBRE: ClassVar[tuple[str, ...]] = ("titular", "situacion")
    _ENTEROS: ClassVar[tuple[str, ...]] = (
        "signo", "mlb_id", "mes", "dia", "temporada", "anos", "event_id", "en_casa",
        "orden", "veces_jugador", "orden_jugador", "puntaje",
    )
    # Nulos legítimos: con cobertura parcial los totales van vacíos a propósito, y el WPA y el
    # leverage solo existen en las gestas que cuelgan de un turno.
    _ENTEROS_NULABLES: ClassVar[tuple[str, ...]] = ("veces_total", "jugadores_total")
    _DECIMALES: ClassVar[tuple[str, ...]] = ("magnitud", "rareza")
    _DECIMALES_NULABLES: ClassVar[tuple[str, ...]] = ("wpa_jugador", "li_max")

    def resolve(self, row: dict[str, str]) -> dict[str, Any]:
        """Traduce la fila del CSV a campos del modelo.

        Los obligatorios levantan `ValueError`, que el motor convierte en un problema con su número
        de línea. No se descartan en silencio: una fila sin titular es un archivo mal generado, y
        tragársela dejaría un CSV que parece más sano de lo que está.
        """
        for campo in self._OBLIGATORIOS:
            if not (row.get(campo) or "").strip():
                raise ValueError(f"{campo} vacío")

        largos = {campo.name: campo.max_length for campo in Efemeride._meta.fields}
        resuelta: dict[str, Any] = {
            campo: _texto(row.get(campo), largos[campo]) for campo in self._TEXTO
        }
        resuelta.update({campo: (row.get(campo) or "").strip() for campo in self._LIBRE})
        resuelta["fecha"] = _fecha(row.get("fecha"))
        resuelta.update({campo: _entero_exigido(row.get(campo), campo) for campo in self._ENTEROS})
        resuelta.update({campo: _entero(row.get(campo)) for campo in self._ENTEROS_NULABLES})
        resuelta.update({campo: _decimal_exigido(row.get(campo), campo) for campo in self._DECIMALES})
        resuelta.update({campo: _decimal(row.get(campo)) for campo in self._DECIMALES_NULABLES})
        resuelta["participantes"] = _participantes(row.get("participantes"))
        return resuelta

    def checks(self, rows: list[dict[str, Any]]) -> list[Problem]:
        """Lo único que el exportador no puede comprobar: que el CSV llegue completo.

        El resto de la salud del archivo ya la verifica el `.ps1` sobre los datos crudos. Acá se
        atajan dos formas de subir un archivo a medias que la comparación por sí sola no delata,
        porque un CSV recortado es un CSV válido.
        """
        problemas: list[Problem] = []

        # 1. El calendario. El archivo tiene que cubrir casi todo el año — con los cumpleaños solos
        #    ya pasan de 330 días. Si llegan pocos, se subió un archivo parcial o filtrado.
        dias = {(row["mes"], row["dia"]) for row in rows}
        if len(dias) < 300:
            problemas.append(
                Problem(
                    f"El archivo solo cubre {len(dias)} días del calendario. Un archivo completo pasa "
                    "de 350: con los cumpleaños solos ya son más de 330. Parece un CSV recortado.",
                )
            )

        # 2. La variedad de detectores. Si vienen cuatro tipos, alguien exportó con la carpeta de
        #    detectores a medias.
        tipos = {row["tipo"] for row in rows}
        if len(tipos) < 40:
            problemas.append(
                Problem(
                    f"El archivo trae {len(tipos)} tipos de efeméride distintos y el exportador corre "
                    "casi cien detectores. Revisá que la corrida no se haya cortado a la mitad.",
                    sorted(tipos)[:20],
                )
            )

        return problemas


def _texto(crudo: str | None, largo: int | None) -> str:
    return (crudo or "").strip()[:largo]


def _participantes(crudo: str | None) -> str:
    """Los otros dueños de una gesta colectiva, envueltos en espacios y con espacio entre cada uno.

    NO PASA POR `_texto` Y ESO ES EL PUNTO. El SQL emite `« 110188 110186 110187 »` con espacio al
    principio y al final a propósito: el perfil los busca con `participantes__contains=" 110186 "`, y
    esos dos espacios son lo único que impide que el 12345 se lleve las efemérides del 123456. Un
    `.strip()` —que es lo que hace `_texto`— deja al primero y al último de la lista sin su espacio y
    los vuelve invisibles en su propio perfil. Pasó: de los tres hermanos Alou en el jardín de 1963,
    la efeméride solo aparecía en el perfil de Felipe, que iba en el medio.

    Se reconstruye en vez de confiar en lo que venga: partir por espacios y volver a unir da el mismo
    resultado aunque el CSV llegue sin los extremos, con espacios de más o de un exportador futuro
    que use comas. Vacío se queda vacío — que es el caso de 5.409 de las 5.802 filas.
    """
    piezas = (crudo or "").replace(",", " ").split()
    return f" {' '.join(piezas)} " if piezas else ""


def _fecha(crudo: str | None) -> date | None:
    """Solo ISO (`1994-07-05`, con o sin hora). Cualquier otro formato es un error, no una conjetura.

    `Export-Csv` de PowerShell escribe las fechas con el formato regional de la máquina, así que un
    CSV puede llegar con «7/6/1987» — y eso es ambiguo: 7 de junio o 6 de julio según la
    configuración de quien lo corrió. Adivinar el orden corrompería en silencio la fecha de todo el
    que nació en día ≤ 12, que es el tipo de daño que no se descubre nunca. Por eso el SQL emite la
    fecha ya en ISO y esto la exige.

    Devuelve un `date` y no un texto a propósito: si la conversión se dejara para el `INSERT`, un
    formato raro reventaría al ESCRIBIR, después de que la pantalla de comparación dijo que todo
    estaba bien. Acá levanta `ValueError` y el motor lo convierte en un problema con su número de
    línea, que es donde el usuario puede hacer algo al respecto.
    """
    texto = (crudo or "").strip()
    if not texto:
        return None
    try:
        return date.fromisoformat(texto.split(" ")[0])
    except ValueError:
        raise ValueError(
            f"fecha «{texto}» no está en formato ISO (YYYY-MM-DD). El PowerShell tiene que emitirla "
            "con CONVERT(varchar(10), fecha, 23); volvé a correr el script."
        ) from None


def _entero(crudo: str | None) -> int | None:
    texto = (crudo or "").strip()
    return int(float(texto)) if texto else None  # `float` primero: el CSV puede traer «210.0»


def _entero_exigido(crudo: str | None, campo: str) -> int:
    """Como `_entero`, pero el vacío es un error con nombre y no un `None` que reviente al escribir.

    Sin esto, una columna numérica que llega vacía pasa la comparación —el motor no la mira— y
    explota en el `INSERT`, después de que la pantalla dijo que todo estaba bien. Acá levanta
    `ValueError` y el motor lo convierte en un problema con su número de línea, que es donde el
    usuario puede hacer algo.
    """
    valor = _entero(crudo)
    if valor is None:
        raise ValueError(f"{campo} vacío y es obligatorio")
    return valor


def _decimal(crudo: str | None) -> float | None:
    """Acepta notación científica, que es como PowerShell escribe los WPA muy chicos.

    Medido sobre el CSV de efemérides: hay valores como «7.82716988860389E-05». `float()` los parsea
    sin ayuda; lo que no hay que hacer es filtrarlos con una expresión regular de dígitos y punto,
    porque los daría por inválidos.
    """
    texto = (crudo or "").strip()
    return float(texto) if texto else None


def _decimal_exigido(crudo: str | None, campo: str) -> float:
    valor = _decimal(crudo)
    if valor is None:
        raise ValueError(f"{campo} vacío y es obligatorio")
    return valor


def _booleano(crudo: str | None) -> bool | None:
    """El `bit` de SQL Server sale de PowerShell como True/False, pero el 1/0 también es legítimo."""
    texto = (crudo or "").strip().lower()
    if texto in ("true", "1"):
        return True
    if texto in ("false", "0"):
        return False
    return None


@register
class DomSalariesLoader(Loader):
    """Salarios por jugador, temporada y equipo.

    El CSV lo produce `static_data/scripts/export_dom_salaries.ps1` desde la vista
    `v_dglweb_salaries`. Se reemplaza entera (truncate).

    La clave es (player_id, season, team_id) y las tres son obligatorias: sin el equipo, un traspaso
    a mitad de temporada colapsaría dos filas legítimas en una y se perdería la mitad del salario.

    No declara `rebuilds`: los salarios no alimentan ningún cálculo del sitio.
    """

    table = "dom_salaries"
    model = DomSalary
    # La edad es numérica pero no es una medida: la suma de las edades de mil peloteros no significa
    # nada. El salario SÍ se suma — el total es la nómina dominicana del período, y un salto raro ahí
    # es exactamente lo que la pantalla tiene que delatar.
    no_sum: ClassVar[tuple[str, ...]] = ("age",)
    columns: ClassVar[dict[str, str]] = {
        "player_id": "player_id",
        "season": "season",
        "team_id": "team_id",
        "league_id": "league_id",
        "age": "age",
        "salary": "salary",
    }

    def resolve(self, row: dict[str, str]) -> dict[str, Any]:
        """Las tres columnas de la clave son obligatorias; las otras tres pueden faltar.

        `team_id` es texto y no un número: es un código de DGL de tres caracteres, sin relación con
        los ids de MLB. Va en la clave, así que vacío es un error y no un dato ausente.
        """
        resuelta: dict[str, Any] = {
            "player_id": _entero(row.get("player_id")),
            "season": _entero(row.get("season")),
            "team_id": _texto(row.get("team_id"), 3),
            "league_id": _texto(row.get("league_id"), 2),
            "age": _entero(row.get("age")),
            "salary": _entero(row.get("salary")),
        }
        faltan = [campo for campo in ("player_id", "season", "team_id") if not resuelta[campo]]
        if faltan:
            raise ValueError(f"{', '.join(faltan)} vacío — es parte de la clave y no puede faltar")
        return resuelta

    def checks(self, rows: list[dict[str, Any]]) -> list[Problem]:
        """Un salario negativo no existe: es un error de la vista o del export, no un dato raro."""
        negativos = [
            f"jugador {row['player_id']} {row['season']} (equipo {row['team_id']}): {row['salary']:,}"
            for row in rows
            if row["salary"] is not None and row["salary"] < 0
        ]
        if not negativos:
            return []
        return [Problem(f"{len(negativos)} salario(s) negativo(s).", negativos[:10])]


@register
class SeasonDatesLoader(Loader):
    """Calendario de cada temporada. El primero que se carga por UPSERT y no por truncate.

    El motivo del modo: esta tabla también se edita a mano en el Backoffice —son pocas filas y cuando
    MLB mueve una fecha conviene corregirla sin esperar un export—. Truncar en cada carga borraría
    esas correcciones; el upsert pisa lo que el CSV trae y deja en paz lo demás.

    Eso cambia lo que hay que cuidar. Con truncate, una fila mala desaparece en la carga siguiente;
    con upsert **se queda para siempre**, porque nada la borra. Por eso `checks()` es más estricto acá
    que en los otros datasets: una temporada absurda o unas fechas traspuestas quedarían atornilladas.
    """

    table = "seasons_dates"
    model = SeasonDates
    columns: ClassVar[dict[str, str]] = {
        "season": "season",
        "sports_id": "sports_id",
        "season_start_date": "season_start_date",
        "reg_season_end_date": "reg_season_end_date",
        "all_star_game_date": "all_star_game_date",
        "post_season_start_date": "post_season_start_date",
        "season_end_date": "season_end_date",
        "is_active": "is_active",
    }

    _FECHAS: ClassVar[tuple[str, ...]] = (
        "season_start_date",
        "reg_season_end_date",
        "all_star_game_date",
        "post_season_start_date",
        "season_end_date",
    )
    # Las dos que la fuente declara obligatorias. Sin ellas la fila no dice nada útil: una temporada
    # es justamente el intervalo entre esas dos fechas.
    _FECHAS_OBLIGATORIAS: ClassVar[tuple[str, ...]] = ("season_start_date", "season_end_date")

    def resolve(self, row: dict[str, str]) -> dict[str, Any]:
        season = _entero(row.get("season"))
        if season is None:
            raise ValueError("season vacío — es parte de la clave y no puede faltar")

        resuelta: dict[str, Any] = {
            "season": season,
            # Por defecto MLB: la fuente distingue ligas pero hoy solo se carga esa, y una columna
            # vacía significa «la de siempre», no «ninguna».
            "sports_id": _entero(row.get("sports_id")) or SeasonDates.MLB,
            "is_active": _booleano(row.get("is_active")) or False,
        }
        resuelta.update({campo: _fecha(row.get(campo)) for campo in self._FECHAS})

        faltan = [campo for campo in self._FECHAS_OBLIGATORIAS if resuelta[campo] is None]
        if faltan:
            raise ValueError(f"{', '.join(faltan)} vacío — la fuente lo declara obligatorio")
        return resuelta

    def checks(self, rows: list[dict[str, Any]]) -> list[Problem]:
        """Dos pruebas, las dos pensadas para un modo que no borra nada.

        1) Las fechas en orden. Una traspuesta no se ve mirando la fila —todas son plausibles— pero
           rompe en silencio a cualquiera que después pregunte si una fecha cae en serie regular o en
           postemporada.

        2) Una sola temporada en curso. `is_active` marca la vigente; dos encendidas es un export a
           medias, y con upsert la vieja se quedaría encendida para siempre porque nada la apaga.
        """
        problems = []

        desordenadas = [
            f"{row['season']}: {problema[1]}" for row in rows if (problema := fechas_fuera_de_orden(row)) is not None
        ]
        if desordenadas:
            problems.append(
                Problem(f"{len(desordenadas)} temporada(s) con las fechas fuera de orden.", desordenadas[:10])
            )

        activas = sorted(str(row["season"]) for row in rows if row["is_active"])
        if len(activas) > 1:
            problems.append(
                Problem(
                    f"{len(activas)} temporadas marcadas como en curso, y solo puede haber una. "
                    "Con upsert la vieja no se apaga sola: hay que arreglarlo en la vista.",
                    activas,
                )
            )
        elif activas:
            problems.extend(self._choca_con_la_activa_guardada(rows, activas[0]))
        return problems

    def _choca_con_la_activa_guardada(self, rows: list[dict[str, Any]], entrante: str) -> list[Problem]:
        """La activa del CSV contra la que YA está en la base.

        Es la mitad que faltaba. Mirar solo el CSV alcanza con truncate, donde la carga reemplaza la
        tabla entera; con upsert la activa vieja **sobrevive si el CSV no la trae**, y entonces
        quedan dos encendidas: la que estaba y la que llega.

        No es hipotético — es lo que pasa con el export normal del año siguiente, que trae la
        temporada nueva y no vuelve a mencionar la anterior.

        Se avisa acá, en la pantalla de comparación, y no se deja para el `IntegrityError` de la
        constraint: la base diría que la regla se rompió, no cuál es la fila que hay que apagar.
        """
        llaves = {(row["season"], row["sports_id"]) for row in rows}
        chocan = [
            f"{fila.season} (deporte {fila.sports_id})"
            for fila in SeasonDates.objects.filter(is_active=True)
            # Las que el CSV sí trae no cuentan: esta carga las va a pisar con el valor que traiga.
            if (fila.season, fila.sports_id) not in llaves
        ]
        if not chocan:
            return []
        return [
            Problem(
                f"La temporada {entrante} llega marcada como en curso, pero en la base ya hay otra "
                "encendida que este CSV no incluye. Con upsert nadie la apaga y quedarían dos. "
                "Añádela al CSV con is_active en falso, o desmárcala en el Backoffice antes de cargar.",
                chocan,
            )
        ]
