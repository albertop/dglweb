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

EL CORTE ES EL DE LA LIGA, ES FIJO, Y ES POR OFICIO (2026-07-31)
-----------------------------------------------------------------
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
# El corte del percentil se hace ANTES y sobre la lista entera, no por oficio. Es lo que pidió el
# dueño y además es lo correcto: partir primero por oficio daría dos percentiles distintos y un
# lanzador podría entrar en «Quemando la liga» con un valor que a un bateador no le alcanza.
#
# El reparto es solo de PRESENTACIÓN — decide a quién se le da sitio en pantalla, no quién califica.
# Sin él, el widget se llenaría del oficio que ese día haya tenido la ventana más generosa, y en una
# semana de abridores dominados no saldría un solo bateador.
MAXIMO = 10
POR_OFICIO = 5

# EL UMBRAL, POR JUEGO. No son números de acá: los fija `qualifier.py` como los umbrales de temporada
# completa divididos entre 162, y están comprobados contra los overrides que el dueño puso a mano
# para 1958, 1981, 1994 y 2020. Se reusan tal cual para no tener dos autoridades diciendo cuándo
# alguien «jugó lo suficiente».
PA_POR_JUEGO = 3.1
IP_POR_JUEGO = 1.0

# LOS CORTES, EN CARRERAS SOBRE EL PROMEDIO. Cuatro constantes: p85 y p15 de cada oficio, sacados de
# LA LIGA ENTERA. Llegaron ahí en tres pasos y los tres dejaron algo aprendido.
#
# 1. DE LA LIGA Y NO DE LOS NUESTROS. La tabla solo guarda dominicanos, así que lo natural era sacar
#    el percentil de ella. Medido: con cuarenta jugadores el corte de arriba se movió de +3,02 a +3,54
#    en quince días —lo mueve uno solo— mientras que con los cuatrocientos de la liga apenas cambia.
#    Una vara que se mueve sola no permite decir «está entre los mejores» dos semanas seguidas.
#
# 2. UNO POR OFICIO. Empezó siendo un corte único para los dos, y el dueño vio el problema mirando el
#    widget: en «Pasando trabajo» los lanzadores estaban hundidos y los bateadores solo flojos. Las
#    distribuciones no se parecen —el p15 del bateo es -3,0 y el del pitcheo -2,0— así que un número
#    común le pedía a cada uno una cosa distinta.
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
#                       media   mediana   desv    rango            n medio
#     bateo    p15      -3,08    -2,99    0,45   [-3,96, -2,40]      172
#     bateo    p85       3,47     3,44    0,37   [ 2,94,  4,03]
#     pitcheo  p15      -2,18    -1,98    0,39   [-2,79, -1,69]      223
#     pitcheo  p85       3,73     3,71    0,22   [ 3,49,  4,19]
#
# Se toma la MEDIANA y no la media: abril y mayo dejaron dos colas de bateo muy largas —-3,55 y -3,96—
# que arrastran el promedio hacia un corte más permisivo que el de una quincena normal. Y se redondea
# a un decimal, que ya no cambia a casi nadie: son umbrales fijos, no un percentil que deba cuadrar.
#
# COMPROBADO CONTRA LAS NUEVE VENTANAS: «Quemando» va de 3 a 10 y «Pasando» de 6 a 11, y no hay una
# sola en que alguno de los dos baje de tres. Los paneles se sostienen todo el año, no solo en julio.
#
# EL MENOS ESTABLE es el p15 del pitcheo (desviación 0,39 sobre una media de -2,18). Los relevistas
# entran y salen de la ventana según cuánto los usen, y eso mueve la cola de abajo. Si un día «Pasando
# trabajo» sale con demasiados lanzadores, ese es el primer número que hay que remedir.
#
# Y ESTOS NÚMEROS CADUCAN, igual que los pisos de `daily`: el entorno de carreras cambia de una
# temporada a otra. Antes de dar por buena la 2027 hay que rehacer el estudio.
CORTES = {
    "bateo": (3.5, -3.0),
    "pitcheo": (3.7, -2.0),
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


def _umbral(splits: list[dict[str, Any]], por_juego: float) -> float:
    """Cuántas PA (o IP) hay que tener para entrar, según lo que se jugó DE VERDAD en la ventana.

    Se calcula y no se fija: catorce días no son catorce juegos. Hay días libres, hay dobles
    carteleras y está el receso del Juego de Estrellas, así que un número escrito a mano quedaría
    largo en julio y corto en septiembre sin que nada lo dijera.

    El denominador es el **p90 de juegos disputados** y no el máximo ni la mediana. El máximo lo pone
    un solo jugador y bastaría una doble cartelera para subir el listón a todos; la mediana la baja
    el que estuvo lesionado la mitad de la ventana, que es justo a quien el umbral tiene que dejar
    fuera. El p90 es «los que jugaron casi todo», que es la referencia correcta.

    Medido el 2026-07-31 sobre catorce días: p90 de 12 juegos en bateo y 6 en pitcheo, o sea 37,2 PA
    y 6,0 IP. Dejaron 182 y 224 jugadores en las mayores, y 22 y 20 dominicanos.
    """
    juegos = sorted(_numero(s.get("stat") or {}, "G") for s in splits)
    if not juegos:
        return 0.0
    p90 = quantiles(juegos, n=10)[8] if len(juegos) > 9 else juegos[-1]
    return por_juego * int(p90)


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
    salida: list[dict[str, Any]] = []

    for grupo, campo, por_juego, valorar, describir in (
        # La línea de bateo es la de ACÁ y no la de `daily`: en catorce días «17-43» obliga a dividir
        # y el promedio de una muestra así dice más del azar que del bateador. Ver `linea_de_bateo`.
        ("hitting", "PA", PA_POR_JUEGO, daily.valor_de_bateo, linea_de_bateo),
        # También la de acá: la de `daily` cierra con la decisión, que en catorce días es de UN juego
        # de los que hay dentro. Ver `linea_de_pitcheo`.
        ("pitching", "IP", IP_POR_JUEGO, daily.valor_de_pitcheo, linea_de_pitcheo),
    ):
        splits = _splits(client, grupo, desde, hasta)
        corte = _umbral(splits, por_juego)
        logger.info(
            "Ventana %s..%s (%s): %s en las mayores, umbral %.1f %s",
            desde, hasta, grupo, len(splits), corte, campo,
        )  # fmt: skip

        for split in splits:
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
            oportunidades = _numero(stat, campo)
            if oportunidades < corte:
                continue

            # ENTERA. No se recorta acá: quien sabe si cabe es el navegador. El CSS la corta con
            # puntos suspensivos y `site.js` le pone el tooltip solo cuando de verdad la cortó.
            linea = describir(stat)

            salida.append(
                {
                    "player_id": jugador_id,
                    "team": codigos.get((split.get("team") or {}).get("id") or 0, ""),
                    "grupo": WindowStandout.Grupo.BATEO if grupo == "hitting" else WindowStandout.Grupo.PITCHEO,
                    "linea": linea[:160],
                    "valor": valorar(stat),
                    "juegos": int(_numero(stat, "G")),
                    "oportunidades": oportunidades,
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


def _fila(registro: WindowStandout) -> Fila:
    return Fila(
        player=registro.player,
        team=registro.team,
        linea=registro.linea,
        valor=registro.valor,
        juegos=registro.juegos,
        grupo=registro.grupo,
    )


def portada() -> dict[str, Any] | None:
    """Los dos widgets, o `None` si no hay con qué dibujarlos.

    Devuelve los dos juntos porque salen de la misma consulta y de los mismos dos cortes: pedirlos por
    separado abriría la puerta a que la portada enseñara un p80 de una corrida y un p20 de otra.

    LOS CORTES SON FIJOS Y SALEN DE LA LIGA — ver `P80` y `P20`. No se recalculan con lo que hay en la
    tabla, que son solo dominicanos: con cuarenta jugadores el percentil lo mueve uno solo, y está
    medido que así el corte de arriba se movía medio punto de una quincena a la otra. Una vara que
    cambia sola no permite decir «está entre el 20% mejor» dos semanas seguidas.

    Devuelve `None` cuando no queda nadie en ninguna de las dos puntas. Puede pasar de verdad —en el
    receso, o el día que se recalcula la ventana en pretemporada— y un panel hueco se lee como un
    sitio roto.
    """
    registros = list(WindowStandout.objects.select_related("player").order_by("-valor"))

    # EL CORTE PRIMERO Y EL REPARTO DESPUÉS. El umbral vale para los dos oficios juntos y solo
    # entonces se decide a quién se le da sitio en pantalla. Al revés darían dos varas distintas y un
    # lanzador entraría con un valor que a un bateador no le alcanza.
    arriba = repartir([_fila(r) for r in registros if r.valor >= CORTES[r.grupo][0]])
    # De peor a mejor: el que peor la está pasando encabeza, igual que el mejor encabeza el otro. Sin
    # esto el widget de abajo se leería al revés que el de arriba y habría que explicarlo.
    abajo = repartir([_fila(r) for r in reversed(registros) if r.valor <= CORTES[r.grupo][1]])

    if not arriba and not abajo:
        return None

    return {
        "desde": registros[0].desde,
        "hasta": registros[0].hasta,
        "quemando": {"lista": arriba, "visibles": arriba[:VISIBLES], "de_mas": arriba[VISIBLES:]},
        "pasando": {"lista": abajo, "visibles": abajo[:VISIBLES], "de_mas": abajo[VISIBLES:]},
    }
