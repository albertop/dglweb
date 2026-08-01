"""Los últimos catorce días: quién está quemando la liga y quién está pasando trabajo.

DOS WIDGETS, UN SOLO CÁLCULO
----------------------------
«Quemando la liga» es el 15% de arriba y «Pasando trabajo» el 15% de abajo de la MISMA lista. Son las
dos puntas de una distribución, no dos preguntas: calcularlas por separado permitiría que dejaran de
cuadrar —dos umbrales, dos poblaciones, dos momentos— y no hay ninguna ventaja a cambio.

POR QUÉ NO SE DERIVA DE `DailyStandout`
---------------------------------------
Tentador: la tabla ya guarda el `valor` de cada dominicano en cada jornada de la temporada, y sumar
catorce filas daría el acumulado sin tocar el proxy. **No alcanza**: no guarda PA ni IP, así que no
hay con qué aplicar el umbral, y sin umbral el widget se llena de quien tuvo un buen día en tres
turnos. Se piden aparte: dos llamadas, una por oficio, ambas con `byDateRange`.

LA VENTANA ES DE DÍAS, NO DE JUEGOS (decisión del dueño, 2026-07-31)
--------------------------------------------------------------------
El proxy sabe responder «los últimos 10 juegos» (`lastXGames`, probado: 520 splits). Se descartó
porque es **por jugador**: el que vuelve de una lesión trae sus diez juegos repartidos en seis
semanas, así que su ventana no es la de los demás y las dos cifras dejan de ser comparables. Con
catorce días naturales todos miden lo mismo y el umbral se encarga del que apenas jugó.

TRES POBLACIONES Y NO DOS: BATEO, ABRIDOR Y RELEVISTA (SAB-01 del review v15)
-----------------------------------------------------------------------------
Cada una califica con su propia regla y se juzga contra su propio percentil. El abridor usa la regla
oficial —1 IP por juego del equipo— y el relevista NO puede usarla: aplicada a catorce días deja
fuera a los 288 relevistas de la liga, porque es la regla del título de efectividad y ese título es
de abridores. Está contestado entero, con los números, en `APARICIONES_RELEVO`.

EL CORTE ES EL DE LA LIGA, ES FIJO, Y ES POR CLASE (2026-07-31)
----------------------------------------------------------------
La tabla guarda solo dominicanos, pero el umbral **no se calcula con ellos**: son percentiles de las
mayores enteras, escritos como constantes. Ver `CORTES`, que lleva el estudio con números.

Se probaron las dos formas. El corte entre nuestros —cuarenta jugadores— se movió de +3,02 a +3,54 en
quince días; el de la liga —cuatrocientos— apenas se mueve. Con la vara chica, un jugador entrando o
saliendo mueve el listón de todos, y «está entre los mejores» deja de querer decir lo mismo de una
semana a la otra.

Así que el título dice la verdad: **quemando la liga es contra la liga.**
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import quantiles
from typing import Any

from django.utils import timezone

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats.models import WindowStandout

logger = logging.getLogger(__name__)

# Catorce días naturales. Es lo que el dueño pidió y lo que hace comparables a todos.
DIAS = 14

# EL PLIEGUE DEL MÓVIL, y solo del móvil (decisión del dueño, 2026-07-31).
#
# En escritorio se ven las diez: la rejilla arma dos columnas y el marco las enseña en cinco filas sin
# botón, porque no habría nada que desplegar.
#
# En un teléfono la rejilla arma UNA columna, así que esas diez cajas son diez filas de scroll dentro
# de un widget — y hay cuatro widgets seguidos. Ahí el marco se recorta a cuatro filas y vuelve el
# «Ver N más». Este número es ese pliegue: lo que queda detrás del botón, `de_mas`.
#
# Las cuatro cajas se mandan igual al navegador en los dos casos. Quién las esconde es el CSS, que es
# el único que sabe de qué ancho es la pantalla; el servidor no puede saberlo y adivinarlo por el
# `User-Agent` sería peor.
VISIBLES = 4

# EL CUPO Y EL REPARTO (decisión del dueño, 2026-07-31).
#
# Diez como mucho, repartidos **5 bateadores y 5 lanzadores**, y si un oficio no llega a cinco se
# completa con el otro: tres lanzadores dejan sitio a siete bateadores.
#
# El corte se aplica ANTES del reparto, y cada uno contra el de SU clase — ver `CORTES`. El reparto
# es solo de PRESENTACIÓN: decide a quién se le da sitio en pantalla, no quién califica. Sin él, el
# widget se llenaría del oficio que ese día haya tenido la ventana más generosa, y en una semana de
# abridores dominados no saldría un solo bateador.
#
# El reparto es por OFICIO —cinco bateadores y cinco lanzadores— y no por las tres clases del corte.
# Es deliberado: al lector le importa ver bateo y pitcheo, no que le repartan las cajas entre
# abridores y relevistas, que es un detalle de cómo se decide quién entra.
MAXIMO = 10
POR_OFICIO = 5

# EL UMBRAL, POR JUEGO DEL EQUIPO. No son números de acá: los fija `qualifier.py` como los umbrales
# de temporada completa divididos entre 162, y están comprobados contra los overrides que el dueño
# puso a mano para 1958, 1981, 1994 y 2020. Se reusan tal cual para no tener dos autoridades
# diciendo cuándo alguien «jugó lo suficiente».
PA_POR_JUEGO = 3.1
IP_POR_JUEGO = 1.0

# ═══════════════════════════════════════════════════════════════════════════════════════════════
# POR QUÉ EL RELEVISTA NO CALIFICA CON «1 IP POR JUEGO DEL EQUIPO»
# ═══════════════════════════════════════════════════════════════════════════════════════════════
#
# Es la pregunta obvia al leer esto —el abridor usa esa regla y el relevista no— así que va contestada
# entera. Corrige SAB-01 del review v15, y la pregunta la hizo el dueño con estas palabras: «si en un
# periodo hay 11 J, entonces los lanzadores que califican son esos con 11 o más IP».
#
# LA REGLA ES CIERTA, PERO NO ES LO QUE PARECE. «1 IP por juego del equipo» no es la regla de
# calificación de los lanzadores en general: es la del **título de efectividad**, y ese título es de
# abridores. No es una interpretación nuestra — en una temporada COMPLETA tampoco califica un
# relevista: Mariano Rivera no calificó para un título de ERA en toda su carrera, porque 70 entradas
# al año no llegan a 162. La regla no está excluyendo relevistas por accidente al prorratearla a dos
# semanas; los excluye por diseño, también en su escala original.
#
# QUÉ PASA SI SE APLICA IGUAL. Medido en la ventana del 18 al 31 de julio, con el equipo jugando 13:
#
#     con >= 13 IP    califican 54 lanzadores en TODA la MLB
#                     los 54 son abridores. CERO relevistas. 2 dominicanos.
#     el relevista que más lanzó de toda la liga en esos 14 días:  10,7 IP
#     relevistas que llegarían a 13 IP:  0 de 288
#
# No es que entren pocos: no entra ninguno, y no puede entrar ninguno. Un relevista bueno lanza entre
# 5 y 8 entradas en dos semanas porque ese es su oficio, no porque le esté yendo mal.
#
# Y ESO ROMPERÍA EL WIDGET, no lo haría más riguroso. «Quemando la liga» existe para contar rachas de
# dos semanas, y un cerrador con siete entradas sin carrera limpia ES una racha de dos semanas —
# Bryan Abreu y Ángel Chivilli están saliendo hoy justamente así. Con el umbral de 13 el panel se
# quedaría con dos abridores dominicanos y no podría volver a nombrar a un relevista nunca.
#
# LO QUE SE HACE EN SU LUGAR. El relevista califica por **apariciones**: cuatro en dos semanas. No es
# un umbral de rendimiento, es uno de presencia — «lo usaron con regularidad»— y deja fuera al que
# subió una vez y al que estuvo lesionado media ventana. Da 186 relevistas por ventana, contra los 64
# abridores.
#
# Y POR ESO TAMBIÉN TIENEN CORTES DISTINTOS. Si dos poblaciones califican con reglas distintas, no se
# pueden juzgar con el mismo percentil: el abridor acumula durante seis entradas y el relevista
# durante una, así que su p85 es +5,7 contra +2,5. Ver `CORTES`. Las dos decisiones son la misma
# decisión mirada dos veces.
APARICIONES_RELEVO = 4

# LOS CORTES, EN CARRERAS SOBRE EL PROMEDIO. Seis constantes: p85 y p15 de cada una de las TRES clases
# —bateo, abridor y relevista—, sacadas de LA LIGA ENTERA. Llegaron ahí en cuatro pasos, y los cuatro
# dejaron algo aprendido.
#
# 1. DE LA LIGA Y NO DE LOS NUESTROS. La tabla solo guarda dominicanos, así que lo natural era sacar
#    el percentil de ella. Medido: con cuarenta jugadores el corte de arriba se movió de +3,02 a +3,54
#    en quince días —lo mueve uno solo— mientras que con los cuatrocientos de la liga apenas cambia.
#    Una vara que se mueve sola no permite decir «está entre los mejores» dos semanas seguidas.
#
# 2. UNO POR OFICIO. Empezó siendo un corte único para los dos, y el dueño vio el problema mirando el
#    widget: en «Pasando trabajo» los lanzadores estaban hundidos y los bateadores solo flojos. Las
#    distribuciones no se parecen —el p15 del bateo es -3,0 y el del pitcheo rondaba -2,0— así que un
#    número común le pedía a cada uno una cosa distinta.
#
# 3. p85/p15 Y NO p80/p20. Con el 20% salían listas de nueve y diez: si uno de cada cinco «está
#    quemando la liga», la frase pierde fuerza. El 15% deja una punta de verdad.
#
# EL ESTUDIO ES DE LA TEMPORADA ENTERA, y eso resultó importar. Con solo tres ventanas el p85 del
# bateo salía 3,2; con las nueve de la temporada la mediana es 3,44 — las tres primeras habían caído
# justo en las dos ventanas más flojas del año. Una constante que va a estar cinco meses en la portada
# no se fija con quince días.
#
# NUEVE VENTANAS DE CATORCE DÍAS SIN SOLAPE, del 2026-03-28 al 2026-07-31:
#
#                        mediana   desv    rango            n medio   dominicanos
#     bateo      p15      -3,03    0,45   [-3,96, -2,40]      172         21,1
#     bateo      p85       3,44    0,37   [ 2,94,  4,03]
#     abridor    p15      -2,38    0,84   [-3,06, -0,49]       64          5,0
#     abridor    p85       5,70    0,46   [ 4,62,  6,23]
#     relevista  p15      -1,44    0,29   [-2,02, -1,21]      186         17,2
#     relevista  p85       2,46    0,25   [ 2,20,  2,86]
#
# Se toma la MEDIANA y no la media: abril y mayo dejaron dos colas de bateo muy largas —-3,55 y -3,96—
# que arrastran el promedio hacia un corte más permisivo que el de una quincena normal. Y se redondea
# a un decimal, que ya no cambia a casi nadie: son umbrales fijos, no un percentil que deba cuadrar.
#
# COMPROBADO CONTRA LAS NUEVE VENTANAS: «Quemando» va de 3 a 10 y «Pasando» de 6 a 11, y no hay una
# sola en que alguno de los dos baje de tres. Los paneles se sostienen todo el año, no solo en julio.
#
# RECALIBRADO EL 2026-08-01, después de que el arreglo del opener (review v16) cambiara la población:
# los relevistas pasaron de 173 a 186 por ventana. El p85 se movió de 2,42 a 2,46 y el p15 no se
# movió, así que los seis números siguen dentro del redondeo y no se tocó ninguno. Los trece nuevos
# son el 7% del grupo y se reparten por toda la distribución en vez de amontonarse en una punta.
#
# EL MENOS ESTABLE ES EL p15 DEL ABRIDOR: desviación **0,84**, contra 0,45 del bateo y 0,29 del
# relevista. Son solo 64 abridores por ventana y la cola de abajo la mueve una apertura desastrosa;
# el rango va de -3,06 a -0,49, que es medio punto y pico de recorrido. Si algún día «Pasando
# trabajo» se llena o se vacía de abridores sin motivo aparente, ese es el primer número a remedir.
#
# Y ESTOS NÚMEROS CADUCAN, igual que los pisos de `daily`: el entorno de carreras cambia de una
# temporada a otra. Antes de dar por buena la 2027 hay que rehacer el estudio.
# 4. UNO POR ROL DENTRO DEL PITCHEO (SAB-01 del review v15). Empezó con un solo corte para los dos, y
#    la medición sobre las nueve ventanas dice que son poblaciones incomparables:
#
#                    n medio   p15      p85
#        abridor        64    -2,38    +5,70
#        relevista     173    -1,44    +2,42
#
#    Un abridor necesita **+5,7** carreras para estar en su 15% mejor y un relevista **+2,4**, porque
#    el abridor acumula durante seis entradas y el relevista durante una. Con el corte único de +3,7
#    pasaba lo contrario de lo que uno supondría: a los abridores les sobraba —entraban con un valor
#    por debajo de su propio p85— y a los relevistas les faltaba. Lo mismo al revés en la punta baja.
CORTES = {
    "bateo": (3.5, -3.0),
    "abridor": (5.7, -2.4),
    "relevista": (2.4, -1.4),
}

# EN QUÉ ORDEN SE ESCRIBE LA LÍNEA DE BATEO. Es el de siempre salvo por el final: **el boleto va
# último**, detrás del robo (decisión del dueño, 2026-07-31).
#
# El orden importa porque la línea NO se recorta en el servidor: se manda entera y el navegador la
# corta por la derecha con puntos suspensivos cuando no cabe. O sea que este orden decide qué se
# pierde primero. El boleto de último y RBI temprano, que es lo que sostiene la afirmación de la
# tarjeta; lo que se corte, sea lo que sea, sigue estando en el tooltip.
ORDEN_LECTURA = ("X2B", "X3B", "HR", "RBI", "R", "SB", "BB")


@dataclass(frozen=True)
class Fila:
    """Una actuación de la ventana, con lo justo para pintarla y para ordenarla."""

    player: Any  # `players.models.Player`
    team: str
    linea: str
    valor: float
    juegos: int
    grupo: str

    # Las tres salen igual que en `daily.Destacado`, y a propósito: los tres paneles de la franja
    # comparten plantilla y CSS, así que si acá el nombre se abreviara de otra forma las cajas
    # dejarían de rimar. Cuando `Destacado` cambie, esto tiene que cambiar con él.
    @property
    def nombre(self) -> str:
        from dglweb.stats.mlb_leaders import nombre_corto

        return nombre_corto(self.player.full_name)

    @property
    def foto(self) -> str:
        from dglweb.players import mugshots

        return mugshots.url(self.player.player_id, mugshots.CHICO)

    @property
    def logo(self) -> str:
        return f"img/equipos/{self.team}.svg" if self.team else ""


def _numero(stat: dict[str, Any], clave: str) -> float:
    """Lo mismo que en `daily`, y a propósito: el proxy manda las cifras como texto."""
    try:
        return float(stat.get(clave) or 0)
    except (TypeError, ValueError):
        return 0.0


def linea_de_bateo(stat: dict[str, Any]) -> str:
    """«.395, 2B, 6 HR, 9 RBI, 13 R» — la de catorce días, que NO se escribe como la de un juego.

    ABRE CON EL PROMEDIO, y llegar ahí costó dos vueltas que vale la pena dejar escritas.

    `daily.linea_de_bateo` abre con «17-43», que es lo correcto en una jornada: «3-4» se lee de un
    vistazo porque los dos números caben en la cabeza. En catorce días, «17-43» obliga a dividir, así
    que se probó con «17 H» a secas — nombrar lo que ocurrió y soltar el denominador.

    **Y eso rompía el widget de abajo.** «9 H, 3B, 5 RBI, 4 R, 5 SB» parece una buena quincena; lo que
    hay detrás es 9-44, o sea .205 y 37 outs en 45 apariciones. El dueño lo vio en pantalla: Otto
    López en «Pasando trabajo» sin nada en la tarjeta que explicara por qué. Contar producción sin
    contar oportunidades acusa a alguien y esconde el argumento.

    El promedio lo dice en cuatro caracteres y es la cifra que el lector dominicano ya tiene en la
    cabeza. Viene del proxy —comprobado, lo manda como `.667`, ya sin el cero de la izquierda que es
    la convención del béisbol— así que ni se calcula ni se formatea acá.

    NO SE RECORTA (decisión del dueño, 2026-07-31). Hubo un rato en que esta función se quedaba con
    las cinco cosas más importantes porque la línea larga no cabía en la caja. Se quitó: **quien sabe
    si cabe es el navegador, no el servidor** — depende del ancho, de la fuente y de cuántas columnas
    armó la rejilla. Ahora va entera, el CSS la corta con puntos suspensivos donde haga falta y
    `site.js` le pone el tooltip SOLO cuando de verdad la cortó.

    El resto de la línea es idéntico a la de la jornada, y a propósito: mismas siglas en inglés
    —RBI y no CI, ver `docs/AUTORIDAD.md`— y el mismo criterio de no escribir un cero.
    """
    partes: dict[str, str] = {}
    for clave, etiqueta in (("X2B", "2B"), ("X3B", "3B"), ("HR", "HR")):
        cantidad = int(_numero(stat, clave))
        if cantidad:
            partes[clave] = etiqueta if cantidad == 1 else f"{cantidad} {etiqueta}"
    for clave in ("RBI", "R", "BB", "SB"):
        cantidad = int(_numero(stat, clave))
        if cantidad:
            partes[clave] = f"{cantidad} {clave}"

    # Sin turnos al bate no hay promedio que enseñar, y `.000` sería una afirmación falsa: el que solo
    # recibió boletos no bateó mal, no bateó. Con el umbral de PA puesto no llega a pasar, pero esta
    # función también se llama desde el shell y desde las pruebas.
    promedio = str(stat.get("AVG") or "") if _numero(stat, "AB") else ""
    encabeza = [promedio] if promedio else []
    return ", ".join(encabeza + [partes[clave] for clave in ORDEN_LECTURA if clave in partes])


def linea_de_pitcheo(stat: dict[str, Any]) -> str:
    """«19.0 IP, 4 ER, 17 K, 3 BB» — como la de la jornada, sin la decisión y CON los boletos.

    SIN LA DECISIÓN. `daily.linea_de_pitcheo` cierra con «(W)», «(SV)» o «(H)», y ahí está bien: en
    una jornada la decisión es parte de lo que pasó ese día. En catorce días es ruido que confunde —
    la decisión es de UN juego de los que hay dentro, así que «6.1 IP, 4 K, 8 ER, (W)» pone una
    victoria al lado de un acumulado que la contradice. Apareció literalmente así en «Pasando
    trabajo». Y el acumulado tiene varias: enseñar una sola es elegir cuál sin decir por qué.

    CON LOS BOLETOS, que la de la jornada tampoco lleva. Lo notó el dueño mirando el widget: ninguna
    línea de lanzador tenía BB. **El valor sí los cuenta** —pesan `-0,326` carreras cada uno, igual
    que para el bateador que lo recibe— así que sin ellos la línea no explica su propio número. Es el
    mismo problema que tenía el bateador cuando se le quitó el denominador: la tarjeta juzga a alguien
    y esconde parte del argumento.

    EL ORDEN ES IP, ER, K, BB (decisión del dueño, 2026-07-31), y sigue el mismo criterio que la línea
    del bateador: lo que más pesa primero, lo más prescindible al final. Las entradas sitúan la
    actuación, las carreras limpias son el juicio, y K y BB —la pareja que dice si dominó o regaló—
    cierran. Si un día la línea no cupiera, lo que se corta por la derecha es el boleto.

    El cero se escribe en las cuatro: «0 BB» es una afirmación y no un hueco, y en un lanzador no
    regalar nada es parte del mérito.
    """
    return (
        f"{stat.get('IP', '0.0')} IP, {int(_numero(stat, 'ER'))} ER, "
        f"{int(_numero(stat, 'K'))} K, {int(_numero(stat, 'BB'))} BB"
    )


def _splits(client: MlbProxyClient, grupo: str, desde: date, hasta: date) -> list[dict[str, Any]]:
    """Toda la liga acumulada en el rango, en una llamada.

    Es `daily.splits` con dos fechas distintas en vez de la misma dos veces. No se reusa aquella
    porque su firma pide un solo día y ensancharla obligaría a tocar a sus tres llamadores —la
    pizarra entre ellos— para un parámetro que solo necesita este módulo.
    """
    payload = client.get(
        "/api/v1/stats",
        {
            "stats": "byDateRange",
            "group": grupo,
            "season": hasta.year,
            "startDate": desde.isoformat(),
            "endDate": hasta.isoformat(),
            "playerPool": "All",
            "limit": 2000,
        },
    )
    return [split for bloque in (payload.get("stats") or []) for split in (bloque.get("splits") or [])]


def _oportunidades(stat: dict[str, Any], campo: str) -> float:
    """El denominador del umbral: PA para el bateador, entradas DE VERDAD para el lanzador.

    `IP` NO ES UN NÚMERO DECIMAL (SAB-01 del review v15). Es notación de béisbol: «6.2» son seis
    entradas y dos tercios, o sea 6,667 — no 6,2. Pasarlo por `float()` inventa una cifra que no
    existe, y estaba pasando en **219 de 400 lanzadores** de una ventana normal.

    En la comparación con el umbral el efecto es chico —el error máximo es de 0,47 entradas y hoy no
    mueve a nadie del corte de 6,0— pero `oportunidades` se guarda para poder comprobar después por
    qué alguien entró o quedó fuera, y un dato de auditoría que miente no sirve de nada.

    `outsPitched / 3` es la cifra real. El propio `models.py` ya lo advierte para las tablas de
    temporada: para sumar entradas se usan outs, nunca la notación.
    """
    if campo == "IP":
        return _numero(stat, "outsPitched") / 3
    return _numero(stat, campo)


def juegos_del_equipo(splits_de_bateo: list[dict[str, Any]]) -> int:
    """Cuántos juegos jugó un equipo en la ventana, deducido de los bateadores de toda la liga.

    Se deduce y no se pregunta al calendario porque ya está en la respuesta: `G` de un bateador son
    juegos disputados, y el que juega todos los días juega los del equipo. El p90 de esa columna es
    «los que jugaron casi todo», que es la referencia buena — el máximo lo pone uno solo y bastaría
    una doble cartelera para subirle el listón a los treinta, y la mediana la baja el que estuvo
    lesionado media ventana, que es justo a quien el umbral tiene que dejar fuera.

    NO SE SACA DE `G` EN PITCHEO, y ese fue el error que corrige SAB-01 del review v15: ahí `G` son
    APARICIONES del lanzador, otra cosa. Medido en la misma ventana: bateo mediana 10 y p90 13,
    pitcheo mediana 3 y p90 6, con el equipo jugando los mismos 13.

    Catorce días no son catorce juegos: hay días libres, dobles carteleras y el receso del Juego de
    Estrellas. Medido sobre las nueve ventanas de 2026, salió entre 10 y 13.
    """
    juegos = sorted(_numero(s.get("stat") or {}, "G") for s in splits_de_bateo)
    if not juegos:
        return 0
    p90 = quantiles(juegos, n=10)[8] if len(juegos) > 9 else juegos[-1]
    return int(p90)


def _califica(stat: dict[str, Any], grupo: str, juegos: int) -> str:
    """La clase a la que pertenece la actuación, o cadena vacía si no llega al umbral de la suya.

    Devuelve la clase y no un booleano porque las dos cosas se deciden con el mismo dato —si abrió o
    no— y separarlas invitaría a que el umbral y el corte del percentil dejaran de estar de acuerdo
    sobre a quién están mirando.

    Los tres umbrales, y por qué cada uno:

    * **bateo**: 3,1 PA por juego del equipo. El qualifier de temporada, prorrateado.
    * **abridor**: 1,0 IP por juego del equipo. El mismo qualifier, y acá sí es la regla oficial.
    * **relevista**: cuatro APARICIONES, no entradas. La regla de «1 IP por juego» es la del título
      de efectividad y ese título es de abridores: aplicada a catorce días deja fuera a **los 288
      relevistas de la liga**, no a algunos. El porqué completo, con los números, está en
      `APARICIONES_RELEVO`.
    """
    # SIN DENOMINADOR NO CALIFICA NADIE (DEV-01 del review v16). `juegos` en cero no significa «el
    # equipo no jugó»: significa que la consulta de bateo vino vacía y no sabemos cuánto se jugó.
    # Sin esta línea, `0 >= 3,1 x 0` es cierto y **califica todo el mundo** — un bateador sin turnos y
    # un lanzador sin outs incluidos. El caso peligroso no es la pretemporada limpia, es una respuesta
    # parcial del proxy en plena temporada: la foto se reemplaza entera, así que publicaría una lista
    # de gente que no pasó ningún umbral. Ante un dato incompleto se calla, no se publica.
    if juegos <= 0:
        return ""

    if grupo == "hitting":
        return "bateo" if _numero(stat, "PA") >= PA_POR_JUEGO * juegos else ""

    # EL QUE ABRIÓ PERO NO LLEGA AL LISTÓN DE ABRIDOR CAE AL DE RELEVISTA (SAB-01 del review v16).
    #
    # `GS > 0` no quiere decir «pertenece a la población de abridores» en el béisbol de hoy: está el
    # opener que lanza una entrada, el bullpen game y el relevista largo que abrió una vez. Con la
    # regla anterior ese lanzador quedaba atrapado — no llegaba a las 13 entradas del abridor y
    # tampoco se le dejaba intentar por apariciones, así que desaparecía del widget por una apertura
    # administrativa.
    #
    # Medido en la ventana del 18 al 31 de julio: **15 lanzadores en toda la MLB** caían en ese hueco,
    # 3 dominicanos. Ninguno de los tres habría entrado ese día por su valor, pero Mason Montgomery
    # —GS=1, 8 apariciones, +3,59— sí habría pasado el corte de relevista de haber sido nuestro.
    #
    # El orden importa: se prueba PRIMERO el listón de abridor. Un abridor de verdad lo cruza y se
    # mide contra los abridores.
    #
    # PERO EL RESPALDO PIDE QUE EL RELEVO HAYA SIDO SU USO PRINCIPAL (SAB-01 del review v17). La
    # primera versión solo miraba `G >= 4`, y eso metía en la población de relevistas a un lanzador
    # con dos aperturas de cuatro salidas: su uso fue mitad y mitad, pero se le medía con el corte de
    # relevista, que es el más permisivo de los dos (+2,4 contra +5,7).
    #
    # `GS * 2 < G` dice exactamente «más de la mitad de sus salidas fueron de relevo». Con eso, el
    # opener de una apertura en ocho salidas entra y el swingman de dos en cuatro no. Medido en la
    # ventana del 18 al 31 de julio: de los 15 que caían al respaldo, entran 10 y quedan fuera 5, los
    # cinco de dos aperturas. Ninguno de los cinco era dominicano.
    #
    # Y QUEDAR FUERA ES LA RESPUESTA CORRECTA para ese perfil, aunque suene a pérdida: un swingman
    # que no llega al listón de abridor no es comparable con ninguna de las dos poblaciones, así que
    # no enseñarlo es más honesto que enseñarlo medido con la vara que no le toca.
    if _numero(stat, "GS") > 0 and _oportunidades(stat, "IP") >= IP_POR_JUEGO * juegos:
        return "abridor"
    if _numero(stat, "GS") * 2 >= _numero(stat, "G"):
        return ""
    return "relevista" if _numero(stat, "G") >= APARICIONES_RELEVO else ""


def calcular(client: MlbProxyClient, universo: set[int], hasta: date) -> list[dict[str, Any]]:
    """Los dominicanos que califican en la ventana, con su línea y su valor en carreras.

    Devuelve diccionarios y no filas del modelo para que el comando decida cuándo escribir: así esta
    función se puede llamar desde una prueba o desde el shell sin tocar la base.
    """
    from dglweb.stats import daily
    from dglweb.stats._download import fetch_team_codes

    desde = hasta - timedelta(days=DIAS - 1)
    # El split trae del equipo solo `id`, `name` y `link` — comprobado, no viene la sigla. La misma
    # tabla que ya usa `daily.destacados`, así que las tres cajas de la franja escriben «SDN» igual.
    codigos = fetch_team_codes(client, hasta.year)

    # El bateo se pide primero porque de él sale el denominador de los TRES umbrales: los juegos que
    # jugó el equipo en la ventana.
    splits = {"hitting": _splits(client, "hitting", desde, hasta)}
    splits["pitching"] = _splits(client, "pitching", desde, hasta)
    juegos = juegos_del_equipo(splits["hitting"])
    logger.info(
        "Ventana %s..%s: %s bateadores y %s lanzadores en las mayores, el equipo jugó %s",
        desde, hasta, len(splits["hitting"]), len(splits["pitching"]), juegos,
    )  # fmt: skip

    salida: list[dict[str, Any]] = []
    for grupo, valorar, describir in (
        # La línea de bateo es la de ACÁ y no la de `daily`: abre con el promedio. Y la de pitcheo
        # también, que va sin la decisión. Ver las dos funciones.
        ("hitting", daily.valor_de_bateo, linea_de_bateo),
        ("pitching", daily.valor_de_pitcheo, linea_de_pitcheo),
    ):
        for split in splits[grupo]:
            jugador_id = (split.get("player") or {}).get("id")
            if jugador_id not in universo:
                continue
            stat = split.get("stat") or {}
            # LA MISMA GUARDA QUE `daily` (DEV-01 del review v13): los componentes se sacan restando,
            # así que un campo ausente inventa cantidades negativas — y en pitcheo eso PREMIA al
            # lanzador, que acá lo metería en el widget equivocado. Se descarta y se deja dicho.
            if motivo := daily.por_que_no_cuadra(stat, grupo):
                quien = (split.get("player") or {}).get("fullName") or jugador_id
                logger.warning("ventana: línea imposible descartada — %s (%s): %s", quien, grupo, motivo)
                continue
            clase = _califica(stat, grupo, juegos)
            if not clase:
                continue

            salida.append(
                {
                    "player_id": jugador_id,
                    "team": codigos.get((split.get("team") or {}).get("id") or 0, ""),
                    "grupo": WindowStandout.Grupo.BATEO if grupo == "hitting" else WindowStandout.Grupo.PITCHEO,
                    "abridor": clase == "abridor",
                    # ENTERA: no se recorta por criterio editorial. Quien decide si cabe en pantalla
                    # es el navegador, que la corta con puntos suspensivos, y `site.js` le pone el
                    # tooltip solo cuando la cortó de verdad.
                    #
                    # El `[:160]` es el largo de la COLUMNA y no una decisión de contenido (DEV-02
                    # del review v16). Es una red para que un dato absurdo del proxy no tumbe la
                    # corrida entera con un error de base: la línea más larga que se puede construir
                    # —promedio y las siete estadísticas con dos cifras cada una— ronda los 50
                    # caracteres, así que este corte no llega a activarse. Hay una prueba que lo fija.
                    "linea": describir(stat)[:160],
                    "valor": valorar(stat),
                    "juegos": int(_numero(stat, "G")),
                    # Lo que se comparó con el umbral de SU clase: PA, entradas o apariciones. Es el
                    # único dato que permite comprobar después por qué alguien entró o quedó fuera.
                    "oportunidades": _oportunidades(stat, "PA" if grupo == "hitting" else "IP")
                    if clase != "relevista"
                    else _numero(stat, "G"),
                    "desde": desde,
                    "hasta": hasta,
                }
            )

    return salida


def guardar(filas: list[dict[str, Any]]) -> int:
    """Reemplaza la foto entera. Devuelve cuántas quedaron.

    Se borra y se reescribe en una transacción: a mitad de camino la tabla diría que hay ocho
    quemando la liga y ninguno pasando trabajo, y la portada la lee en cada visita.
    """
    from django.db import transaction

    from dglweb.players.models import Player

    # La clave primaria de `Player` ES el id de MLB, así que no hay traducción que hacer. Se
    # comprueba igual que existan: el universo dice quién es dominicano, pero una fila del maestro
    # puede haberse borrado entre que se armó el conjunto y se escribe, y un `bulk_create` con una
    # clave ajena rota tumba la corrida entera.
    conocidos = set(
        Player.todos.filter(player_id__in=[f["player_id"] for f in filas]).values_list("player_id", flat=True)
    )

    objetos = [
        WindowStandout(
            desde=f["desde"],
            hasta=f["hasta"],
            grupo=f["grupo"],
            abridor=f["abridor"],
            player_id=f["player_id"],
            team=f["team"],
            linea=f["linea"],
            valor=f["valor"],
            juegos=f["juegos"],
            oportunidades=f["oportunidades"],
        )
        for f in filas
        if f["player_id"] in conocidos
    ]

    with transaction.atomic():
        WindowStandout.objects.all().delete()
        WindowStandout.objects.bulk_create(objetos)
    return len(objetos)


def repartir(filas: list[Fila]) -> list[Fila]:
    """Hasta diez, tratando de que sean cinco de cada oficio. Ver `MAXIMO` y `POR_OFICIO`.

    Las filas entran YA ORDENADAS por mérito —mejor primero en «Quemando», peor primero en
    «Pasando»— y esta función no reordena: solo elige. Así el mismo reparto sirve para los dos
    widgets sin tener que saber cuál de los dos está armando.

    El resultado sale en el orden original y no con los cinco de un oficio y luego los cinco del
    otro: la lista se lee por mérito, y agruparla por oficio obligaría a leer las diez cajas para
    saber quién encabeza.
    """
    elegidos: set[int] = set()
    for oficio in (WindowStandout.Grupo.BATEO, WindowStandout.Grupo.PITCHEO):
        del_oficio = [i for i, f in enumerate(filas) if f.grupo == oficio]
        elegidos.update(del_oficio[:POR_OFICIO])

    # Lo que sobró del cupo, para el oficio que sí tenga con qué llenarlo. Se recorre en el orden de
    # mérito, así que los que entran son los siguientes mejores y no los primeros que aparezcan.
    if len(elegidos) < MAXIMO:
        for i in range(len(filas)):
            if len(elegidos) >= MAXIMO:
                break
            elegidos.add(i)

    return [f for i, f in enumerate(filas) if i in elegidos][:MAXIMO]


def _publicables() -> Any:  # noqa: ANN401 — un `QuerySet[WindowStandout]`, sin importarlo arriba
    """Las filas que PUEDEN salir al público: las de un jugador que no esté oculto.

    `Player.hidden` promete que un jugador deshabilitado desaparece del sitio, y esta superficie no
    cumplía esa promesa: `portada()` leía la tabla entera (QA-01 del review v15). Se copió el patrón
    de `daily` sin copiar su filtro, que es la forma más fácil de romper un contrato — el widget
    nuevo se ve bien y la regla vieja deja de valer en un sitio donde nadie mira.

    VA AL LEER Y NO AL GUARDAR, igual que en `daily`. El dato crudo sigue entrando en la tabla, así
    que reactivar a un jugador lo devuelve a la portada en la siguiente petición en vez de tener que
    esperar al próximo recálculo de la ventana. Deshabilitar es reversible; ocultarlo al guardar lo
    haría irreversible hasta la hora siguiente.
    """
    from dglweb.players.visibility import only_visible

    return only_visible(WindowStandout.objects.all())


def se_puede_publicar(hoy: date | None = None) -> bool:
    """Si hoy los dos widgets tienen derecho a existir. Decisión del dueño, 2026-08-01.

    DOS PUNTAS, Y LAS DOS POR EL MISMO MOTIVO: el widget promete «los últimos 14 días» y solo puede
    prometerlo cuando esos catorce días existen de verdad.

    * **Los primeros catorce días de la temporada, no.** La ventana estaría a medias —el día 3 son
      tres días de juegos, no catorce— y los cortes de `CORTES` se midieron sobre ventanas llenas de
      una liga en marcha. Con media ventana, el valor acumulado de todos es más chico y el corte deja
      fuera a gente que sí está quemando la liga; y al revés, el umbral de PA y de IP tampoco se
      alcanza. Los widgets aparecen **el día 15**, contado desde `season_start_date`.
    * **Después del último día, tampoco** — pero con **un día de holgura** (dueño, 2026-08-01). La
      Serie Mundial termina de noche, y con el corte pegado a `season_end_date` los widgets
      desaparecían de madrugada, justo cuando alguien entra a ver cómo le fue a los nuestros en el
      último juego del año. El día siguiente todavía es noticia; el segundo ya no.

    La fecha sale de `SeasonDates`, que es la misma tabla que gobierna los jobs — no de una constante
    ni del calendario civil, para que una temporada que empiece antes o se alargue no obligue a tocar
    código.

    Y TIENE QUE HABER UNA TEMPORADA MARCADA COMO EN CURSO, para `sports_id = 1`. Es la condición que
    hace esto gobernable desde el Backoffice sin tocar código: el administrador quita la marca
    «Temporada en curso» y los dos widgets desaparecen de la portada en la siguiente petición.

    SE COMPRUEBA AL PUBLICAR Y NO AL CALCULAR, igual que la visibilidad de los jugadores. El job
    horario puede seguir corriendo en la primera quincena: escribe una foto que nadie lee y que se
    reemplaza sola, y el día 15 ya está lista sin esperar a la siguiente hora. Bloquearlo al calcular
    no ganaría nada y añadiría una segunda regla que mantener de acuerdo con esta.
    """
    from dglweb.stats import season_window

    # La regla vive en `season_window` y no acá: la comparten estos dos widgets y «Destacados ayer y
    # hoy», y tres copias de una condición sobre fechas de temporada son tres formas de que se
    # separen. Lo único propio de este widget es la rampa.
    return season_window.se_publica(hoy, rampa=DIAS)


def _clase(registro: WindowStandout) -> str:
    """Contra qué corte se mide esta fila: `bateo`, `abridor` o `relevista`. Ver `CORTES`.

    Una función y no una columna: el rol ya está guardado en `abridor`, y una tercera forma de decir
    lo mismo es una tercera forma de que se contradigan.
    """
    if registro.grupo == WindowStandout.Grupo.BATEO:
        return "bateo"
    return "abridor" if registro.abridor else "relevista"


def _fila(registro: WindowStandout) -> Fila:
    return Fila(
        player=registro.player,
        team=registro.team,
        linea=registro.linea,
        valor=registro.valor,
        juegos=registro.juegos,
        grupo=registro.grupo,
    )


def portada(hoy: date | None = None) -> dict[str, Any] | None:
    """Los dos widgets, o `None` si no hay con qué dibujarlos.

    Devuelve los dos juntos porque salen de la misma consulta y de los mismos cortes: pedirlos por
    separado abriría la puerta a que la portada enseñara un p85 de una corrida y un p15 de otra.

    LOS CORTES SON FIJOS, SALEN DE LA LIGA Y HAY UNO POR CLASE — ver `CORTES`. No se recalculan con
    lo que hay en la tabla, que son solo dominicanos: con cuarenta jugadores el percentil lo mueve uno
    solo, y está medido que así el corte de arriba se movía medio punto de una quincena a la otra.
    Una vara que cambia sola no permite decir «está entre los mejores» dos semanas seguidas.

    Devuelve `None` cuando no queda nadie en ninguna de las dos puntas. Puede pasar de verdad —en el
    receso, o el día que se recalcula la ventana en pretemporada— y un panel hueco se lee como un
    sitio roto.

    `hoy` es para reproducir: `build_window_standouts --hasta` calcula la ventana de otra fecha y
    tenía que poder enseñarla. Sin el parámetro, el comando guardaba la foto de abril y decidía si se
    podía publicar con la fecha de hoy, así que en invierno imprimía «no alcanza para partir en
    quintos» cuando la causa real era el calendario (QA-01 del review v17). En producción no se pasa:
    la portada siempre pregunta por hoy.
    """
    if not se_puede_publicar(hoy):
        return None

    registros = list(_publicables().select_related("player").order_by("-valor"))

    # EL CORTE PRIMERO Y EL REPARTO DESPUÉS. Cada uno se mide contra el corte de SU clase —bateo,
    # abridor o relevista— y solo entonces se decide a quién se le da sitio en pantalla. Al revés, el
    # reparto elegiría antes de saber quién califica de verdad.
    arriba = repartir([_fila(r) for r in registros if r.valor >= CORTES[_clase(r)][0]])
    # De peor a mejor: el que peor la está pasando encabeza, igual que el mejor encabeza el otro. Sin
    # esto el widget de abajo se leería al revés que el de arriba y habría que explicarlo.
    abajo = repartir([_fila(r) for r in reversed(registros) if r.valor <= CORTES[_clase(r)][1]])

    if not arriba and not abajo:
        return None

    return {
        "desde": registros[0].desde,
        "hasta": registros[0].hasta,
        "quemando": {"lista": arriba, "visibles": arriba[:VISIBLES], "de_mas": arriba[VISIBLES:]},
        "pasando": {"lista": abajo, "visibles": abajo[:VISIBLES], "de_mas": abajo[VISIBLES:]},
    }
