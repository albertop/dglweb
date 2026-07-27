"""Los movimientos de roster de los dominicanos, en español.

DE DÓNDE SALE
-------------
De `/api/v1/transactions`, no de comparar rosters. La comparación fue la primera idea y se descartó
con números: pedir el roster de los 30 equipos son 30 llamadas por corrida, y aun así la diferencia
entre dos fotos solo dice que alguien dejó de estar — **no distingue** una bajada a ligas menores de
un cambio, de una cesión o de una liberación, que es justo lo que hace noticiable el movimiento.
Averiguarlo pediría más llamadas, no menos.

El feed acepta rangos de fechas: una sola llamada trae dos semanas. La corrida pide siempre los
últimos dos días y guarda por el `id` de la transacción, así que repetirla no duplica y una que falle
no pierde nada.

EL ESPAÑOL SE HACE CON REGLAS, NO CON UN MODELO DE LENGUAJE
-----------------------------------------------------------
Porque MLB no escribe prosa: rellena plantillas. Medido sobre un mes real (2.139 transacciones de
toda la MLB), sustituyendo nombres, equipos, posiciones y números por marcadores quedan 226
esqueletos distintos, pero **29 cubren el 90%**; entre los nuestros, 36 cubren el mes entero.

EL ATAJO QUE NO FUNCIONA, escrito para que nadie lo reintente: armar la frase solo con los campos
estructurados, ignorando el inglés. `typeDesc` es demasiado grueso — «Status Change» mete en la misma
bolsa *activado*, *lista de lesionados*, *paternidad*, *duelo*, *restringido* y *suspendido*. Saldría
«cambio de estatus» donde la noticia era la lesión.

Así que se reconoce la frase inglesa con un patrón y se rellena la plantilla española con los CAMPOS
DEL JSON —`person`, `fromTeam`, `toTeam`—, nunca con lo que se extraiga del texto. El texto solo se
usa para saber QUÉ pasó; el quién y el dónde vienen limpios del payload.

LO QUE NO SE RECONOCE NO SE MUESTRA
-----------------------------------
`traducir()` devuelve cadena vacía si ningún patrón encajó, y el cintillo salta esas filas. Una línea
en inglés dentro de una cintilla en español no se lee como un dato, se lee como un error. El inglés
original queda guardado para poder agregar el patrón que falte.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction

from dglweb.mlb.client import MlbProxyClient
from dglweb.players.models import Player
from dglweb.stats.models import DomPlayer, RosterMove

# Cuántos días pide cada corrida. Dos y no uno: la corrida de la medianoche tiene que alcanzar lo que
# pasó tarde el día anterior, y repetir lo ya guardado no cuesta nada porque se guarda por id.
DIAS = 2

# Las posiciones como las escribe MLB dentro de la frase. Se quitan del texto antes de comparar
# contra los patrones: son ruido para reconocer QUÉ pasó, y el sitio ya muestra la posición del
# jugador en su ficha.
_POSICIONES = r"(?:RHP|LHP|1B|2B|3B|SS|LF|CF|RF|OF|IF|DH|C|P)"

# El repertorio. Cada entrada es (qué reconocer, cómo decirlo en español).
#
# El orden IMPORTA: se prueba de arriba abajo y gana el primero que encaje, así que lo específico va
# antes que lo general — «activated from the 10-day injured list» antes que «activated».
#
# Los marcadores son los del payload y nunca texto sacado de la frase inglesa:
#
#   {jugador}          `person.fullName`
#   {desde} / {hasta}  `fromTeam` / `toTeam` — SOLO cuando la dirección es la noticia
#                      («enviado A», «llamado DESDE»)
#   {equipo}           el equipo que ACTÚA. Medido: `toTeam` viene en el 100% de las filas y
#                      `fromTeam` solo en la mitad, así que para «X designó a Y» hay que usar este y
#                      no `{desde}` — con `{desde}` salían frases decapitadas en el cintillo,
#                      « designó a Steward Berroa para asignación», sin sujeto.
#   {n} / {n2}         los números que capture el patrón
PATRONES: list[tuple[str, str]] = [
    # --- Subidas y bajadas ---
    (r"^.+ optioned .+ to .+\.$", "{jugador} fue enviado a {hasta}"),
    (r"^.+ recalled .+ from .+\.$", "{jugador} fue llamado desde {desde}"),
    (r"^.+ selected the contract of .+ from .+\.$", "{equipo} seleccionó el contrato de {jugador}"),
    (r"^.+ sent .+ outright to .+\.$", "{jugador} fue asignado a {hasta} sin pasar por waivers"),
    (r"^.+ designated .+ for assignment\.$", "{equipo} designó a {jugador} para asignación"),
    # --- Lesiones y listas especiales ---
    (r"^.+ placed .+ on the (\d+)-day injured list.*$", "{jugador} fue puesto en la lista de lesionados de {n} días"),
    (r"^.+ activated .+ from the (\d+)-day injured list\.$", "{jugador} volvió de la lista de lesionados"),
    # El traspaso entre listas es noticia de verdad —de 10 a 60 días es una lesión larga— así que va
    # con su propia plantilla y no cae en la genérica. El número que interesa es el SEGUNDO, el de la
    # lista a la que pasa; de ahí que el patrón capture los dos y la plantilla use `{n2}`.
    (
        r"^.+ transferred .+ from the (\d+)-day injured list to the (\d+)-day injured list.*$",
        "{jugador} pasó a la lista de lesionados de {n2} días",
    ),
    (r"^.+ sent .+ on a rehab assignment to .+\.$", "{jugador} salió a rehabilitación con {hasta}"),
    (r"^.+ placed .+ on the paternity list\.$", "{jugador} fue puesto en la lista de paternidad"),
    (r"^.+ activated .+ from the paternity list\.$", "{jugador} volvió de la lista de paternidad"),
    (r"^.+ placed .+ on the bereavement list\.$", "{jugador} fue puesto en la lista de duelo"),
    (r"^.+ activated .+ from the bereavement list\.$", "{jugador} volvió de la lista de duelo"),
    (r"^.+ placed .+ on the restricted list\.$", "{jugador} fue puesto en la lista de restringidos"),
    (r"^.+ activated .+ from the restricted list\.$", "{jugador} volvió de la lista de restringidos"),
    # --- Cambios, firmas y salidas ---
    (r"^.+ traded .+ to .+ for cash\.$", "{jugador} fue cambiado a {hasta} por dinero"),
    (r"^.+ traded .+ to .+\.$", "{jugador} fue cambiado a {hasta}"),
    (r"^.+ claimed .+ off waivers from .+\.$", "{equipo} reclamó a {jugador} en waivers"),
    (
        r"^.+ signed free agent .+ to a minor league contract\.$",
        "{equipo} firmó a {jugador} a contrato de ligas menores",
    ),
    (r"^.+ signed free agent .+\.$", "{equipo} firmó a {jugador} como agente libre"),
    (r"^.+ signed .+\.$", "{equipo} firmó a {jugador}"),
    (r"^.+ released .+\.$", "{equipo} dejó libre a {jugador}"),
    (r"^.+ acquired .+ from .+\.$", "{equipo} adquirió a {jugador}"),
    (r"^.+ obtain(?:ed)? .+ from .+\.$", "{equipo} adquirió a {jugador}"),
    (r"^.+ suspended\.?$", "{jugador} fue suspendido"),
    (r"^.+ (?:declared|elected) free agency\.$", "{jugador} se declaró agente libre"),
    # --- Lo genérico, al final ---
    (r"^.+ activated .+\.$", "{equipo} activó a {jugador}"),
    (r"^.+ assigned to .+\.$", "{jugador} fue asignado a {hasta}"),
    # MLB también es vago acá: «roster status changed» no dice a qué. Se traduce igual de vago en vez
    # de inventarle un motivo, porque la alternativa era dejarlo fuera del cintillo — y es el más
    # frecuente de los que ningún otro patrón reconoce.
    (r"^.+ roster status changed by .+\.$", "{equipo} cambió el estatus de {jugador} en el roster"),
]

_COMPILADOS = [(re.compile(patron, re.IGNORECASE), plantilla) for patron, plantilla in PATRONES]


@dataclass(frozen=True)
class Movimiento:
    """Una transacción ya cruzada contra el universo dominicano, lista para guardar."""

    transaction_id: int
    mlb_id: int
    nombre: str
    fecha: date
    type_code: str
    type_desc: str
    desde: str
    hasta: str
    descripcion: str
    texto: str


def universo() -> set[int]:
    """Quién es dominicano: la unión de `dgl_master` y `dom_players`, y NUNCA el `birthCountry` del feed.

    Es la regla de autoridad de todo el sitio — ver `docs/AUTORIDAD.md`.
    """
    return set(Player.todos.values_list("player_id", flat=True)) | set(
        DomPlayer.objects.values_list("player_id", flat=True)
    )


def traducir(fila: dict[str, Any]) -> str:
    """La frase en español, o cadena vacía si ningún patrón encajó. Ver la cabecera del módulo."""
    descripcion = (fila.get("description") or "").strip()
    if not descripcion:
        return ""

    # Se compara sin las posiciones: son ruido para reconocer QUÉ pasó y multiplicarían los patrones.
    limpia = re.sub(rf"\b{_POSICIONES}\b\s*", "", descripcion)
    for patron, plantilla in _COMPILADOS:
        encaje = patron.match(limpia)
        if encaje is None:
            continue
        numeros = encaje.groups()
        desde = (fila.get("fromTeam") or {}).get("name") or ""
        hasta = (fila.get("toTeam") or {}).get("name") or ""
        piezas = {
            "jugador": (fila.get("person") or {}).get("fullName") or "",
            "desde": desde,
            "hasta": hasta,
            # El que actúa. `toTeam` está siempre; `fromTeam` es el respaldo por si algún día no.
            "equipo": hasta or desde,
            "n": numeros[0] if numeros else "",
            "n2": numeros[1] if len(numeros) > 1 else "",
        }
        # Si a la plantilla le falta una pieza, NO se publica una frase coja. Es la red que faltaba:
        # el patrón de «designated for assignment» rellenaba con `fromTeam`, que en ese tipo no viene,
        # y el cintillo mostró « designó a Steward Berroa para asignación» — sin sujeto y empezando
        # por un espacio. Nadie lo habría visto hasta que un lector lo leyera.
        if any(f"{{{clave}}}" in plantilla and not valor for clave, valor in piezas.items()):
            return ""
        return plantilla.format(**piezas).strip()
    return ""


def _movimiento(fila: dict[str, Any]) -> Movimiento | None:
    """Convierte una fila del feed. `None` si le falta algo con lo que no se puede trabajar."""
    persona = fila.get("person") or {}
    identificador, mlb_id = fila.get("id"), persona.get("id")
    if not identificador or not mlb_id or not fila.get("date"):
        return None
    return Movimiento(
        transaction_id=int(identificador),
        mlb_id=int(mlb_id),
        nombre=str(persona.get("fullName") or ""),
        fecha=date.fromisoformat(str(fila["date"])),
        type_code=str(fila.get("typeCode") or "")[:8],
        type_desc=str(fila.get("typeDesc") or "")[:60],
        desde=str((fila.get("fromTeam") or {}).get("name") or "")[:80],
        hasta=str((fila.get("toTeam") or {}).get("name") or "")[:80],
        descripcion=str(fila.get("description") or ""),
        texto=traducir(fila),
    )


def traer(client: MlbProxyClient, hasta: date, dias: int = DIAS) -> list[Movimiento]:
    """Los movimientos de los nuestros en la ventana pedida. UNA llamada, no una por equipo."""
    desde = hasta - timedelta(days=dias - 1)
    payload = client.get(
        "/api/v1/transactions",
        {
            "sportId": 1,
            # MLB pide las fechas en mm/dd/aaaa. Con guiones devuelve vacío sin quejarse.
            "startDate": desde.strftime("%m/%d/%Y"),
            "endDate": hasta.strftime("%m/%d/%Y"),
        },
    )
    nuestros = universo()
    movimientos = []
    for fila in payload.get("transactions") or []:
        if (fila.get("person") or {}).get("id") not in nuestros:
            continue
        movimiento = _movimiento(fila)
        if movimiento is not None:
            movimientos.append(movimiento)
    return movimientos


# Cuántos movimientos entran en el cintillo y cuánto hacia atrás mira.
#
# TRES DÍAS, no una semana. Con la semana entraban noticias de seis días atrás —el dueño las vio— y
# un cintillo de movimientos que enseña lo de la semana pasada deja de ser noticia y pasa a ser
# archivo. Con unos cuatro o cinco movimientos nuestros por día, tres días dan una docena larga de
# entradas: suficiente para que la tira no dé vueltas cortas y todo lo que pasa es reciente.
#
# El tope de 25 casi nunca muerde con esa ventana; está para el día raro de muchos movimientos
# —cierre de cambios, primeros de temporada— en que la tira se haría interminable.
EN_CINTILLO = 25
VENTANA_CINTILLO = 3


def portada() -> list[RosterMove]:
    """Los movimientos para el cintillo. Dos filtros, y los dos son reglas del sitio.

    **Solo los que tienen ficha en `dgl_master`** — decisión del dueño (2026-07-27). Se guardan
    igual los de `dom_players` que aún no llegaron a las mayores, porque el dato es bueno y algún día
    puede servir, pero al cintillo no van: este sitio es de dominicanos en GRANDES LIGAS, y una firma
    de ligas menores de un muchacho de 17 años no es lo que viene a leer quien entra. Antes salían y
    se notaba — la cintilla se llenaba de «firmó a X a contrato de ligas menores».

    **Solo los que se pudieron traducir.** Lo que ningún patrón reconoció no sale: el sitio no enseña
    inglés.
    """
    from django.utils import timezone

    desde = timezone.localdate() - timedelta(days=VENTANA_CINTILLO)
    return list(
        RosterMove.objects.filter(fecha__gte=desde, player__isnull=False)
        .exclude(texto="")
        .select_related("player")
        .order_by("-fecha", "-transaction_id")[:EN_CINTILLO]
    )


def guardar(movimientos: list[Movimiento]) -> int:
    """Escribe por `transaction_id`. Devuelve cuántas filas tocó.

    Actualiza además de crear: MLB corrige descripciones a las horas de publicarlas, y la traducción
    de una fila vieja tiene que mejorar si mañana se agrega el patrón que le faltaba.
    """
    if not movimientos:
        return 0
    fichas = dict(Player.todos.values_list("player_id", "pk"))
    with transaction.atomic():
        for movimiento in movimientos:
            RosterMove.objects.update_or_create(
                transaction_id=movimiento.transaction_id,
                defaults={
                    "mlb_id": movimiento.mlb_id,
                    # Sin ficha en el maestro queda en nulo y el cintillo muestra el nombre sin
                    # enlace: son firmas de ligas menores de gente que aún no llegó a las mayores.
                    "player_id": fichas.get(movimiento.mlb_id),
                    "nombre": movimiento.nombre,
                    "fecha": movimiento.fecha,
                    "type_code": movimiento.type_code,
                    "type_desc": movimiento.type_desc,
                    "desde": movimiento.desde,
                    "hasta": movimiento.hasta,
                    "descripcion": movimiento.descripcion,
                    "texto": movimiento.texto,
                },
            )
    return len(movimientos)
