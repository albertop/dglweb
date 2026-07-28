"""Qué posición juega hoy cada pelotero, según sus propias estadísticas.

POR QUÉ ESTA COLUMNA NECESITA MANTENIMIENTO Y LAS OTRAS NO
----------------------------------------------------------
La fecha de nacimiento de un pelotero no cambia; su posición sí, y varias veces. Un campocorto se
muda a segunda a los treinta, un jardinero central pasa a la esquina cuando pierde piernas, un
abridor termina de cerrador. `dgl_master.pos` se llenó una vez y envejece sola.

Medido el 2026-07-27: de 981 jugadores del maestro, 100 tienen una posición que ya no corresponde a
lo que dicen sus estadísticas — Tatis en el jardín derecho y no en el campocorto, Soto en el derecho
y no en el izquierdo, Polanco en segunda.

CÓMO SE DECIDE
--------------
1. **La posición con más ENTRADAS**, no con más juegos: un cambio defensivo de una entrada cuenta un
   juego igual que una novena completa.
2. **Solo las últimas temporadas** (`VENTANA`). Con la carrera entera, un campocorto que lleva tres
   años en segunda seguiría diciendo SS durante años — y la pregunta que esta columna responde es
   qué juega HOY, no qué jugó más veces. Para quien ya no juega no hay ventana que valga: ahí se mira
   la carrera, que además ya no va a cambiar.
3. **Si es lanzador, el `GS/G` decide** entre abridor y relevista. Ahí NO se exige un mínimo de
   entradas: un relevista novato con cinco entradas es un relevista, y la proporción de aperturas ya
   lo dice. El mínimo es para los jugadores de posición, donde ocho entradas en el jardín derecho no
   convierten a nadie en jardinero derecho.

LO QUE NO SE TOCA
-----------------
`PH`, `PR`, `DH` y `OF` no son posiciones de fildeo: son roles, y alguien los puso a propósito. El
bateador emergente de carrera con veinte entradas en el jardín no es un jardinero. Son 71 jugadores
del maestro y se respetan siempre — decisión del dueño.
"""

from dataclasses import dataclass

from django.db.models import Max, Sum

from dglweb.players.models import Player
from dglweb.stats.models import Fielding, Pitching

# CÓMO SE ESCRIBEN LOS LANZADORES EN PANTALLA. Decisión del dueño (2026-07-28).
#
# `SP` y `RP` son las siglas de MLB y no dicen nada en español. El sitio ya traduce las posiciones de
# lanzador en la ficha del jugador; esto lo saca de ahí para que el índice y cualquier otra pantalla
# usen la MISMA nomenclatura, en vez de que cada plantilla decida.
#
# `P` a secas se queda igual: es el lanzador del que todavía no se sabe si abre o releva —le faltan
# juegos para decidirlo— y «P» dice exactamente eso.
#
# Ojo con no extender esto a las ESTADÍSTICAS: ahí las siglas van en inglés por regla del sitio
# (RBI, ER, AB, AVG…), y está escrito en `docs/AUTORIDAD.md`. Esto son posiciones, no métricas.
EN_ESPANOL: dict[str, str] = {"SP": "P-ABR", "RP": "P-REL"}


# El nombre COMPLETO, para cuando hay sitio para escribirlo: la descripción que sale bajo el titular
# en Google, por ejemplo. «Juan Soto, rf dominicano» se lee mal y no dice nada a quien no siga el
# juego; «jardinero derecho» sí. Las siglas de arriba son para las tablas, donde el espacio manda.
NOMBRE_COMPLETO: dict[str, str] = {
    "P": "lanzador",
    "SP": "lanzador abridor",
    "RP": "lanzador relevista",
    "C": "receptor",
    "1B": "primera base",
    "2B": "segunda base",
    "3B": "tercera base",
    "SS": "campocorto",
    "LF": "jardinero izquierdo",
    "CF": "jardinero central",
    "RF": "jardinero derecho",
    "OF": "jardinero",
    "DH": "bateador designado",
    "PH": "bateador emergente",
    "PR": "corredor emergente",
}


def nombre_largo(posicion: str | None) -> str:
    """`RF` -> `jardinero derecho`. Vacío si no se conoce, para que quien llama omita la frase entera
    en vez de escribir una sigla suelta en medio de una oración."""
    return NOMBRE_COMPLETO.get(posicion or "", "")


def como_se_lee(posicion: str | None) -> str:
    """`RP` -> `P-REL`. Lo que no esté en la tabla sale tal cual: `SS` y `3B` se entienden solos."""
    return EN_ESPANOL.get(posicion or "", posicion or "")


# Cuántas temporadas mira para decidir «qué juega hoy».
VENTANA = 3

# Entradas mínimas en la posición para mover a un jugador de posición. Elegido midiendo: con 20 se
# descartan cuatro casos de ocho y nueve entradas, y no toca ninguno legítimo. No aplica a lanzadores.
MIN_ENTRADAS = 20

# Roles, no posiciones. Ver la cabecera.
ROLES = frozenset({"PH", "PR", "DH", "OF"})

# `DH` aparece como fila de fildeo aunque no lo sea — 1.077 filas. Si entrara al conteo, un designado
# con muchas apariciones «jugaría» de DH.
_NO_ES_POSICION = "DH"


@dataclass(frozen=True)
class Discrepancia:
    """Un jugador cuya posición en el maestro no coincide con lo que dicen sus estadísticas."""

    player_id: int
    full_name: str
    actual: str
    sugerida: str
    entradas: float
    fuente: str  # "reciente" o "carrera"
    detalle: str = ""  # las aperturas sobre juegos, cuando es lanzador

    def __str__(self) -> str:
        aparte = f" · {self.detalle}" if self.detalle else ""
        return f"{self.player_id} {self.full_name}: {self.actual} → {self.sugerida} ({self.entradas:.0f} IP{aparte})"


def _mas_entradas(desde: int | None) -> dict[int, tuple[str, float]]:
    """`player_id` → (posición con más entradas, entradas). `desde=None` mira la carrera entera."""
    consulta = Fielding.objects.exclude(pos=_NO_ES_POSICION)
    if desde is not None:
        consulta = consulta.filter(season__gte=desde)

    mejor: dict[int, tuple[str, float]] = {}
    for fila in consulta.values("player_id", "pos").annotate(outs=Sum("innings_outs")).order_by("player_id", "-outs"):
        if fila["player_id"] not in mejor and fila["outs"]:
            mejor[fila["player_id"]] = (fila["pos"], fila["outs"] / 3)
    return mejor


def _abridor_o_relevista(ids: list[int], desde: int | None) -> dict[int, tuple[str, str]]:
    """`player_id` → (SP o RP, «12/30 aperturas»). Más de la mitad de sus juegos abiertos es abridor."""
    consulta = Pitching.objects.filter(player_id__in=ids)
    if desde is not None:
        consulta = consulta.filter(season__gte=desde)

    salida: dict[int, tuple[str, str]] = {}
    for fila in consulta.values("player_id").annotate(g=Sum("g"), gs=Sum("gs")):
        juegos, aperturas = fila["g"] or 0, fila["gs"] or 0
        if not juegos:
            continue
        salida[fila["player_id"]] = (
            "SP" if aperturas / juegos > 0.5 else "RP",
            f"{aperturas}/{juegos} aperturas",
        )
    return salida


def discrepancias(ventana: int = VENTANA, min_entradas: float = MIN_ENTRADAS) -> list[Discrepancia]:
    """Los jugadores cuya `pos` no coincide con sus estadísticas, ordenados por nombre."""
    ultima = Fielding.objects.aggregate(m=Max("season"))["m"]
    if ultima is None:
        return []
    desde = ultima - ventana + 1

    reciente, carrera = _mas_entradas(desde), _mas_entradas(None)
    # El reciente manda; quien no jugó en la ventana —retirado— se juzga por su carrera, que ya no
    # va a cambiar.
    propuesta = {
        pid: (*reciente.get(pid, datos), "reciente" if pid in reciente else "carrera") for pid, datos in carrera.items()
    }

    lanzadores = [pid for pid, (pos, _, _) in propuesta.items() if pos == "P"]
    por_reciente = _abridor_o_relevista(lanzadores, desde)
    por_carrera = _abridor_o_relevista(lanzadores, None)

    actual = dict(Player.todos.values_list("player_id", "pos"))
    nombres = dict(Player.todos.values_list("player_id", "full_name"))

    salida = []
    for pid, (pos, entradas, fuente) in propuesta.items():
        vieja = actual.get(pid)
        if vieja is None or vieja in ROLES:
            continue

        detalle = ""
        if pos == "P":
            decision = por_reciente.get(pid) or por_carrera.get(pid)
            if decision is None:
                continue  # lanzador sin juegos registrados: no hay con qué decidir
            pos, detalle = decision
        # El mínimo de entradas es solo para los de posición: al lanzador ya lo decidió su `GS/G`.
        elif entradas < min_entradas:
            continue

        if pos != vieja:
            salida.append(Discrepancia(pid, nombres[pid], vieja, pos, entradas, fuente, detalle))

    return sorted(salida, key=lambda d: d.full_name)


def aplicar(cambios: list[Discrepancia]) -> int:
    """Escribe las posiciones sugeridas en el maestro. Devuelve cuántas filas cambió.

    Una por una y no en masa a propósito: son cien filas como mucho, una vez por semana, y así el
    `player_id` de cada escritura queda a la vista si algo sale mal.
    """
    for cambio in cambios:
        Player.todos.filter(player_id=cambio.player_id).update(pos=cambio.sugerida)
    return len(cambios)
