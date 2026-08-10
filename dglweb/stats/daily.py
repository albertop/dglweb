"""La actuación del día: quién de los nuestros hizo algo digno de contarse ayer.

Alimenta el widget «Destacados de la jornada» de la portada, en **una sola lista** con los dos
oficios mezclados (decisión del dueño, 2026-07-27).

Acá decía que iban en dos listas separadas «porque comparar un 3-4 con siete entradas de una carrera
exige una escala común que no existe». Se quedó viejo dos veces: el widget las mezcla desde julio, y
desde el 2026-07-29 la escala común **sí existe** — los dos oficios se puntúan con la misma matriz de
pesos lineales, el bateador sumando lo que produjo y el lanzador restando lo que permitió. Ver
`valor_de_pitcheo`.

Un encabezado así no es ruido: es el que hace que alguien «arregle» lo que funciona.

CÓMO SE SACA EL DATO
--------------------
`stats=byDateRange` con la misma fecha de inicio y fin da las estadísticas de ESE día para toda la
liga en una sola llamada por oficio. Dos llamadas, menos de un segundo, y el recorte dominicano es
una intersección en memoria — el mismo patrón que el refresco diario. Un día sin juegos devuelve
cero splits sin error, así que no hay que preguntarle al calendario si hubo pelota.

CÓMO SE ORDENA
--------------
**Bateo: pesos lineales.** Cada evento vale lo que vale en carreras, según la matriz 2024-2025 del
dueño (columna `average`). Sumar la jornada da el valor en carreras que el pelotero produjo — la
misma lógica que hay detrás del wOBA, aplicada a un juego. Se prefiere a ordenar por remolcadas o
anotadas porque esas dependen de quién estaba en base: premian la oportunidad, no la actuación.

**Pitcheo: LA MISMA MATRIZ, leída desde el otro lado.** El lanzador resta lo que permitió y suma lo
que retiró, con los mismos pesos. Así la lista mezclada se ordena sin traducir nada.

Los dos oficios comparten **la misma heurística de pesos lineales, con distinta cobertura de eventos**
— y esa segunda mitad hace falta. Se escribió «misma unidad **por construcción**», y era decir de más:
compartir los coeficientes no basta si cada lado los multiplica por cantidades distintas. Los outs del
bateo salen de `AB - H - K + SF + SH`, que solo cuenta los suyos; los del pitcheo salen de
`outsPitched`, que incluye el segundo out de un doble play y los corredores sorprendidos fuera de
base. **Medido**: 13,3% de las salidas traen un doble play, el lanzador se lleva 0,271 carreras de más
en la mediana, y 8 de 216 salidas publicables cruzaron el piso solo por ese crédito. Está detallado en
`valor_de_pitcheo`.

Hasta el 2026-07-29 el pitcheo se puntuaba con **Game Score v2 de Tango** y se traducía a carreras
con `(GS - 50) / 3`. Esa traducción metía a los lanzadores en una escala del doble —un relevista con
un inning perfecto salía en -1,0 carreras— y por eso se quitó. `game_score()` se eliminó con ella: se
quedó sin ningún consumidor, y una función que solo llaman sus propias pruebas es código que envejece
sin que nadie lo note. Está en el historial si algún día se quiere ENSEÑAR el Game Score, que es otra
cosa que ordenar con él.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.utils.formats import date_format

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats import scoreboard, season_window
from dglweb.stats._download import fetch_team_codes

logger = logging.getLogger(__name__)

_LIMITE = 8000

# EL PISO PARA LLAMARSE DESTACADO. Decisión del dueño (2026-07-27), medida sobre 14 jornadas reales.
#
# Antes no había piso: se publicaba el top-3 y el top-2 pasara lo que pasara. Medido, eso ya
# coronaba actuaciones que no lo son — el tercer bateador publicado bajaba hasta **0,25** en las
# jornadas flojas (un 1-4 con sencillo) y el segundo lanzador hasta **46**, que en la escala de Tango
# está por DEBAJO del promedio. Llamarle destacado a eso contradice la propia métrica.
#
# CADA UNO ES EL PERCENTIL 80 DE SU OFICIO EN TODA LA MLB (calibrado el 2026-07-29, decisión del
# dueño). O sea: para salir en el widget hay que estar entre el **20% mejor de las mayores** ese día,
# no entre lo mejor que hicieron los dominicanos.
#
# Se calcula sobre TODA la liga a propósito. Con el universo dominicano la muestra son 331 y 119
# actuaciones en catorce días; con la liga entera son **3.141 y 1.307**. Y se comprobó antes de
# hacerlo que los dos grupos son la misma distribución —media de bateo -0,025 en MLB contra +0,005 en
# dominicanos, desviación 0,833 contra 0,811— así que el corte de la liga cae donde debe. Si fueran
# grupos distintos, calibrar con MLB estaría midiendo otra cosa.
#
# POR QUÉ DOS NÚMEROS DISTINTOS SI LA UNIDAD ES LA MISMA
# ------------------------------------------------------
# Parece contradecir todo el trabajo de poner los dos oficios en carreras, y no lo contradice: son
# dos preguntas distintas.
#
#   - **El ORDEN** usa el valor crudo. Ahí «una carrera es una carrera», y eso queda intacto.
#   - **El PISO** pregunta otra cosa: ¿fue esto NOTABLE? Y notable es relativo a lo normal en tu
#     oficio.
#
# Las dos distribuciones no tienen la misma forma. Mediana de bateo -0,14 contra +0,33 en pitcheo;
# desviación 0,83 contra 1,31. Un lanzador suma +0,27 por cada out, así que acumula valor por durar;
# un bateador solo tiene cuatro turnos.
#
# Con un solo número eso se rompe: un corte único de 0,70 publicaría bateadores del p84 y **lanzadores
# del p68**, que es un inning limpio con un ponche — el día normal de un relevista, no un destacado.
#
# LOS NÚMEROS, Y LO QUE LLENAN
# -----------------------------
# Al p80 salen **6,3 dominicanos al día**, que es justo lo que enseña el widget (`VISIBLES`). Con el
# piso anterior —1,0 para los dos— salían 3,8: la portada mostraba cuatro de seis huecos.
#
# LA MESETA DEL PITCHEO, Y POR QUÉ 0,82 NO ES UN REDONDEO DESCUIDADO DE 0,8163
# -----------------------------------------------------------------------------
# El p80 del pitcheo cae ENCIMA de una pila de empates, porque el inning limpio de relevo tiene tres
# valores exactos y se repite muchísimo. Contado sobre 2.828 salidas de 28 días:
#
#     0,8120   1.0 IP, 0 K     x113
#     0,8141   1.0 IP, 1 K     x173
#     0,8163   1.0 IP, 2 K      x96
#
# Son 382 salidas —el 13,5%— apiladas en tres valores, justo en el corte. La consecuencia es que **el
# 20% no se puede alcanzar**: los cortes que existen de verdad publican el 17,3% (dejando entrar el
# inning limpio con dos ponches) o el 26,8% (dejando entrar también el de uno). No hay nada en medio.
#
# 0,82 está DELIBERADAMENTE por encima de los tres, y publica el 16,6%. Es más estricto que el 20%
# nominal a propósito: por debajo de 0,8163 la portada se llena de relevistas que retiraron el inning
# en orden, que es el día normal de su oficio y no un destacado — exactamente lo que dice el bloque de
# arriba sobre el corte único de 0,70.
#
# ASÍ QUE NO SE «CORRIJA» A 0,8163 PARA QUE CUADRE CON EL PERCENTIL. Cuadraría, y metería 96
# innings limpios cada cuatro semanas. Hay una prueba que lo impide.
#
# El bateo no tiene este problema: publica el 19,2% y el 19,8% en dos ventanas sin solape, que es lo
# que se buscaba.
#
# ESTOS NÚMEROS CADUCAN. Salen de catorce días de julio de 2026. Sirven para arrancar, pero antes de
# dar por buena una temporada conviene recalcularlos con el año completo — el entorno de carreras
# cambia, y con él los percentiles.
#
# El piso se aplica al MOSTRAR, no al guardar. La tabla es el registro de la jornada y se queda con
# todos los que jugaron — cambiar el umbral no puede exigir volver a pedirle nada al proxy.
PISO_BATEO = 0.58
PISO_PITCHEO = 0.82

# LA ESCALA COMÚN, para poder ordenar las dos listas juntas (decisión del dueño, 2026-07-27).
#
# Durante mucho tiempo acá NO se comparaban: dos listas separadas, porque un 3-4 y siete entradas de
# una carrera no están en la misma unidad. El dueño decidió mezclarlas, y para eso hay que traducir.
#
# YA NO HAY NINGUNA TRADUCCIÓN, y ese es el arreglo (SAB-02 del review v12, 2026-07-29). Los dos
# oficios se puntúan con **la misma matriz de pesos lineales**, leída desde cada lado: el bateador
# suma lo que produjo, el lanzador resta lo que permitió.
#
# LO QUE ESO SÍ ARREGLA es la escala, que era lo roto: ya no hay una constante inventada metiendo a
# los lanzadores en una unidad del doble. LO QUE NO ARREGLA, y se escribió como si sí (SAB-01 del
# review v13), es el INVENTARIO DE EVENTOS: los dos lados no cuentan las mismas jugadas, así que la
# unidad es la misma pero la atribución no es simétrica. El detalle y los números, en
# `valor_de_pitcheo`.
#
# LO QUE HABÍA ANTES, ANOTADO PARA NO REPETIRLO. Se traducía el Game Score con `(GS - 50) / 3`,
# razonando que el término `-3R` fija el precio de una carrera en tres puntos y que 50 es la salida
# promedio. No funcionaba, y se pudo enseñar con números:
#
#   - Game Score tiene SEIS términos, y dividir el total entre tres los divide todos. Cada uno
#     heredaba una escala para la que no fue calibrado: un out salía a +0,67 carreras cuando la
#     matriz dice +0,27; un jonrón a -3,00 cuando la matriz dice -1,39. **Al doble en casi todo.**
#   - Un relevista que retiraba el inning en orden con un ponche valía **-1,0 carreras**, como si le
#     hubiera costado una a su equipo. Porque 50 es el promedio de un ABRIDOR, y un relevista no
#     puede acercarse: entra con la resta puesta por no lanzar siete entradas.
#   - Un juego sin hits con 12 ponches daba **+18,7 carreras**. Las mejores actuaciones de una
#     temporada rondan las +4.
#
# En la portada eso significaba que un 5-5 con tres jonrones (+5,1) perdía contra una apertura buena
# pero corriente (+9,0). El comentario que había acá lo notó y lo defendió —«evitar carreras rinde
# más que producirlas»— pero eso no era la métrica descubriendo nada: era la escala al doble.


# Cómo se puntúa y cómo se describe una jornada. Van tipados en vez de `Any` para que agregar un
# oficio nuevo falle en mypy si la firma no encaja, en vez de a mitad de una corrida.
Calculo = Callable[[dict[str, Any]], float]
Descripcion = Callable[[dict[str, Any]], str]

# Adónde va lo que hay que dejar escrito en la fila de `IngestRun`. En la práctica es `run.note`; se
# recibe como parámetro para que este módulo no tenga que saber nada del registro de corridas.
Aviso = Callable[[str], None] | None

# Valor en carreras de cada evento — matriz de pesos lineales **2024-2025**, columna `average`,
# provista por el dueño (`2024_2025_Linear_Weights.json`, 2026-08-07). Se copian tal cual, con todos
# sus decimales: redondearlos acá sería introducir un criterio propio en un número que ya viene
# decidido.
#
# SUSTITUYE A LA MATRIZ 2022-2025 y el cambio es pequeño en todo salvo en un sitio: el triple pasó de
# 1,0354 a 1,0218 y el sencillo subió de 0,4671 a 0,4720. El resto se mueve en la tercera cifra. No
# reordena a nadie por sí solo, pero los valores publicados cambian, así que las pruebas que fijan un
# número exacto van contra `PESOS[...]` y no contra la constante escrita a mano — que es como hay que
# escribirlas para que la próxima matriz no las rompa.
PESOS: dict[str, float] = {
    "out": -0.2700940433967196,  # out en juego (incluye elevados de sacrificio y toques)
    "k": -0.27339562613568386,
    "bb": 0.33066612165670933,
    "ibb": 0.22013392872280546,  # el intencional vale menos: no lo ganó el bateador
    "hbp": 0.3564065127331991,
    "1b": 0.47199779257268093,
    "2b": 0.7624346214376665,
    "3b": 1.021805683830989,
    "hr": 1.3895390412296236,
    "sb": 0.16979018811854363,
    "cs": -0.42326268796063693,
    # Estos dos solo los usa el pitcheo. Son del mismo archivo y de la misma columna, y entran porque
    # son cosa EXCLUSIVA del lanzador: nadie más lanza un wild pitch ni comete un balk.
    #
    # No se incluye el «Passed ball» (+0,2470), que se le parece y también está en la matriz: ese es
    # del receptor. Ni el «Error» (+0,4478), que es de la defensa. Cargárselos al lanzador sería
    # cobrarle el trabajo de otro.
    "wp": 0.2559670601209641,
    "bk": 0.25601677444834,
}


@dataclass(frozen=True)
class Actuacion:
    """Una línea del widget. `valor` ordena; `linea` es lo que se lee."""

    player_id: int
    nombre: str
    equipo: str
    valor: float
    linea: str


def _numero(stat: dict[str, Any], clave: str) -> float:
    """La API mezcla enteros con cadenas («1.000», «7.0»). Lo que no se pueda leer vale cero."""
    try:
        return float(stat.get(clave) or 0)
    except (TypeError, ValueError):
        return 0.0


def por_que_no_cuadra(stat: dict[str, Any], grupo: str = "hitting") -> str:
    """Por qué esta línea es imposible, o cadena vacía si cuadra. DEV-01 del review v13.

    QUÉ PROBLEMA RESUELVE, CON NÚMEROS
    ----------------------------------
    `_numero()` convierte lo ausente y lo ilegible en cero, y los componentes se sacan RESTANDO: los
    sencillos son `H - 2B - 3B - HR`, los boletos ganados `BB - IBB`. Si el proxy omite `H` pero manda
    un doble, el código inventa **-1 sencillos** y devuelve un `float` perfectamente válido.

    En pitcheo eso puede PREMIAR al lanzador, porque toda la suma va negada. Medido:

        6 IP, 6 K, 4 H limpio          +3,016
        IBB=2 con BB=0 (imposible)     +3,244   premia
        H ausente y 2 dobles           +4,286   premia  ← +1,27 carreras de regalo

    Y +1,27 basta para mover a un lanzador varios puestos en la lista mezclada de la portada.

    POR QUÉ SE EXCLUYE LA FILA Y NO SE ARREGLA CON `max()`
    -----------------------------------------------------
    Un `max(0, ...)` en cada resta haría desaparecer el negativo y dejaría un número plausible
    construido con componentes imposibles — o sea, un destacado falso que nadie puede detectar mirando.
    Es peor que no publicar la fila: la credibilidad de la portada depende de que lo que sale sea
    cierto, no de que salga completo.

    LO QUE SE COMPRUEBA, y todo es aritmética de definición, no un criterio nuestro:

    * `2B + 3B + HR <= H`  — un extrabase ES un hit; no puede haber más extrabases que hits.
    * `IBB <= BB`          — los intencionales son un subconjunto de los boletos.
    * `H + K <= AB`        — un hit y un ponche son turnos al bate, y son excluyentes entre sí.

    EL TERCERO ESTUVO CONDICIONADO A `if AB`, Y ESO ABRÍA UN HUECO. Lo puse temiendo descartar la
    línea de puro boleto, que trae `AB=0` legítimamente — pero esa línea tiene `H + K = 0 <= 0` y pasa
    igual. El guardia no protegía nada y dejaba entrar justo el caso que la regla existe para atrapar:

        {"AB": 0, "H": 1}   ->  cuadraba, y valía +0,7378

    Un hit sin turno al bate. Y no es que el error se colara con un valor pequeño: `AB - H` da **-1
    outs**, así que el out negativo SUMA +0,273 y el sencillo otros +0,465 — los dos componentes tiran
    para arriba. Medido sobre 3.141 líneas de bateo, la regla sin guardia no rechaza ninguna fila real,
    y las 150 líneas de puro boleto pasan.

    `AB` ausente se trata igual que `AB=0`: si el proxy no manda los turnos pero sí los hits,
    `valor_de_bateo` deduce los mismos outs negativos. La fila no es puntuable, venga el cero de la API
    o de que el campo no llegó.

    Y LA REGLA DE `AB` ES SOLO DE BATEO, que es el `grupo`
    ------------------------------------------------------
    Cada oficio se valida contra los campos que SU fórmula consume. `valor_de_pitcheo` no mira `AB` en
    ningún momento —sus outs salen de `outsPitched`—, así que descartar una salida por una
    inconsistencia en `AB` sería tirar una fila perfectamente puntuable por un campo que no participa.

    NO HAY UNA REGLA EQUIVALENTE DEL LADO DEL PITCHEO, y se comprobó antes de darla por buena. La
    candidata natural era `K + CS <= outsPitched`, y es FALSA: en un tercer strike no atrapado el
    ponche se acredita y no hay out. Dos casos reales en dos semanas —una salida de 2 outs con 3
    ponches, y otra de 1 out con 1 ponche y 1 atrapado robando—, así que exigirlo habría descartado
    jugadas legítimas. Es también lo que justifica el `max(..., 0)` de `valor_de_pitcheo`: ahí no está
    tapando un dato malo, está tratando una jugada que existe.
    """
    hits = _numero(stat, "H")
    extrabases = _numero(stat, "X2B") + _numero(stat, "X3B") + _numero(stat, "HR")
    if extrabases > hits:
        return f"{extrabases:.0f} extrabases con {hits:.0f} hits"

    boletos, intencionales = _numero(stat, "BB"), _numero(stat, "IBB")
    if intencionales > boletos:
        return f"{intencionales:.0f} boletos intencionales con {boletos:.0f} boletos"

    turnos = _numero(stat, "AB")
    if grupo == "hitting" and hits + _numero(stat, "K") > turnos:
        return f"{hits:.0f} hits y {_numero(stat, 'K'):.0f} ponches en {turnos:.0f} turnos"

    return ""


def valor_de_bateo(stat: dict[str, Any]) -> float:
    """El valor en carreras de la jornada del bateador, por pesos lineales.

    Los sencillos se deducen restando extrabases a los hits, porque la API no los manda aparte. Y los
    outs se parten en dos: los ponches tienen su propio peso, y el resto —outs en juego, elevados de
    sacrificio y toques— van al peso genérico. `AB` no incluye boletos ni sacrificios, de ahí que
    estos se sumen aparte en vez de salir de la resta.
    """
    hits = _numero(stat, "H")
    dobles, triples, jonrones = _numero(stat, "X2B"), _numero(stat, "X3B"), _numero(stat, "HR")
    sencillos = hits - dobles - triples - jonrones
    boletos, intencionales = _numero(stat, "BB"), _numero(stat, "IBB")
    ponches = _numero(stat, "K")
    outs_en_juego = _numero(stat, "AB") - hits - ponches + _numero(stat, "SF") + _numero(stat, "SH")

    return (
        sencillos * PESOS["1b"]
        + dobles * PESOS["2b"]
        + triples * PESOS["3b"]
        + jonrones * PESOS["hr"]
        + (boletos - intencionales) * PESOS["bb"]
        + intencionales * PESOS["ibb"]
        + _numero(stat, "HBP") * PESOS["hbp"]
        + ponches * PESOS["k"]
        + outs_en_juego * PESOS["out"]
        + _numero(stat, "SB") * PESOS["sb"]
        + _numero(stat, "CS") * PESOS["cs"]
    )


def valor_de_pitcheo(stat: dict[str, Any]) -> float:
    """El valor en carreras de la jornada del lanzador — **la misma matriz que el bateo, negada**.

    POR QUÉ ASÍ Y NO CON GAME SCORE (SAB-02 del review v12)
    --------------------------------------------------------
    La portada mezcla bateadores y lanzadores en una sola lista, así que hay que ponerlos en la misma
    unidad. Hasta el 2026-07-29 eso se hacía traduciendo Game Score con `(GS - 50) / 3`, apoyándose en
    que el término `-3R` dice que una carrera cuesta tres puntos.

    **No funcionaba, y se puede enseñar con números.** Game Score tiene seis términos y dividir el
    total entre tres los divide todos, así que cada uno hereda una escala para la que no fue
    calibrado. Comparado con esta misma matriz:

        un out        la conversión decía +0,67 carreras · la matriz dice +0,27
        un boleto                        -0,67                            -0,33
        un jonrón                        -3,00                            -1,39

    Al doble en casi todo. Y con dos consecuencias visibles: un relevista que retiraba el inning en
    orden con un ponche salía valorado en **-1,0 carreras** —como si le hubiera costado una a su
    equipo— porque 50 es el promedio de un ABRIDOR y un relevista nunca puede acercarse. Y un juego
    sin hits con 12 ponches daba **+18,7 carreras**, cuando las mejores actuaciones de una temporada
    rondan las +4.

    En la portada eso se traducía en que un 5-5 con tres jonrones (+5,1) perdía contra una apertura
    buena pero corriente (+9,0).

    Acá no hay ninguna traducción ni ninguna constante: se usa **la misma matriz de pesos lineales**,
    leída desde el otro lado. El valor del lanzador es el valor de bateo de lo que permitió, con el
    signo cambiado — por eso el `-(...)` envuelve toda la suma en vez de repartirse término a término.

    HASTA DÓNDE LLEGA ESA SIMETRÍA, QUE NO ES HASTA DONDE DECÍA ACÁ
    ---------------------------------------------------------------
    Esto decía «los dos oficios están en la misma unidad **por construcción**, no por una afirmación»,
    y era decir de más (SAB-01 del review v13). Compartir los coeficientes no produce simetría si cada
    lado los multiplica por cantidades distintas, y es justo lo que pasa con los outs:

        bateo      `AB - H - K + SF + SH`  — solo los outs del propio bateador
        pitcheo    `outsPitched`           — TODOS los de la entrada

    Así que el segundo out de un doble play le suma al lanzador como out genérico y **no aparece como
    nada en la línea de nadie**: el bateador que bateó para doble play registra un solo out, el suyo.
    Un corredor sorprendido fuera de base, igual.

    LOS NÚMEROS, porque «una aproximación» sin magnitud no se puede juzgar. Medido sobre 1.307 salidas
    de dos semanas, usando el `GIDP` que el propio split de pitcheo trae:

        13,3% de las salidas traen al menos un doble play
        0,271 carreras de crédito de más en la mediana (un out a +0,273, negado)
        0,812 en el peor caso
        8 de 216 salidas publicables cruzaron el piso SOLO por ese crédito  (3,7%)

    Ese 3,7% es el tamaño real del problema en la portada: ocho apariciones en dos semanas que se
    ganaron con un out que el modelo no le cobra a ningún bateador. No es ruido, y tampoco es lo que
    decide la lista.

    LO CORRECTO DE VERDAD SERÍA RE24 sobre jugada a jugada, donde el cambio de estado de bases y outs
    reparte el valor sin inventarle un peso a nada. Eso es otro proyecto: pide una fuente de eventos
    que hoy no se pide. Mientras tanto la frase honesta es **misma heurística de pesos lineales, con
    distinta cobertura de eventos** — y por eso el orden de la lista mezclada no se presenta como una
    comparación sabermétrica exacta.

    LOS OUTS SALEN DE `outsPitched` y no de `AB - H - K` **a sabiendas de lo anterior**: el dato
    autoritativo existe de este lado, y recoge outs que no son turnos al bate —un corredor eliminado
    robando, un pisa y corre— que la resta perdería. Deducirlos como hace el bateo cambiaría un sesgo
    por otro: perdería outs que el lanzador sí provocó.

    EL JUEGO DE CORREDORES SÍ ENTRA, y la primera versión de esto decía lo contrario. Yo había
    escrito que las bases robadas y los atrapados robando se omitían «para no cobrarle al lanzador el
    brazo del receptor». **El código no hacía eso**, y el review v12 lo destapó: `outsPitched` cuenta
    TODOS los outs de la entrada, así que el atrapado robando ya entraba —disfrazado de out
    cualquiera, a +0,27 en vez de a +0,42—. La documentación afirmaba una cosa y el código hacía otra.

    De las tres salidas posibles —omitirlos, dejarlos como out genérico, o darles su peso— se eligió
    la tercera, y no por la magnitud (medido: cambia el 15,9% de las salidas, mediana 0,173 carreras,
    y solo 7 de 1.307 cruzan el piso). Se eligió porque **es la que acerca los dos inventarios**: el
    bateo cuenta SB y CS, así que si el pitcheo no los contara, los dos oficios estarían mirando menos
    eventos en común todavía. Acerca; no iguala — de eso trata el bloque de arriba.

    LO QUE SIGUE FUERA: el passed ball, que es del receptor, y el error, que es de la defensa. Los dos
    están en la matriz y los dos se dejan a propósito.

    POR QUÉ EL DOBLE PLAY NO SE ARREGLA CON UN PESO PROPIO, que es lo primero que uno piensa: **la
    matriz no trae uno** —ni de este lado ni del otro—, y el split tampoco manda los pickoffs.
    Inventarle un número al doble play sería sustituir un sesgo medido y declarado por uno que nadie
    puede auditar. Se prefiere la aproximación conocida.

    LO QUE TAMBIÉN FALTABA: el **wild pitch** y el **balk**. Los dejé fuera escribiendo que no estaban
    en la matriz, y era falso — están los dos, en la misma columna `average` del mismo archivo.
    """
    hits = _numero(stat, "H")
    dobles, triples, jonrones = _numero(stat, "X2B"), _numero(stat, "X3B"), _numero(stat, "HR")
    sencillos = hits - dobles - triples - jonrones
    boletos, intencionales = _numero(stat, "BB"), _numero(stat, "IBB")
    ponches = _numero(stat, "K")
    atrapados = _numero(stat, "CS")
    outs = _numero(stat, "outsPitched") or _numero(stat, "Outs")
    # `outsPitched` CUENTA TODOS LOS OUTS DE LA ENTRADA, no solo los de bateadores: comprobado contra
    # el proxy, una salida de 1.0 IP con un atrapado robando trae `outsPitched=3` habiendo retirado a
    # dos bateadores. Así que el atrapado se saca de acá y entra abajo con SU peso, que es +0,42 para
    # la defensa y no los +0,27 de un out cualquiera.
    #
    # Los ponches también salen, porque ya van con el suyo. Nunca negativo: un dato raro de la API no
    # puede regalar carreras.
    outs_en_juego = max(outs - ponches - atrapados, 0.0)

    return -(
        sencillos * PESOS["1b"]
        + dobles * PESOS["2b"]
        + triples * PESOS["3b"]
        + jonrones * PESOS["hr"]
        + (boletos - intencionales) * PESOS["bb"]
        + intencionales * PESOS["ibb"]
        + _numero(stat, "HBP") * PESOS["hbp"]
        + _numero(stat, "WP") * PESOS["wp"]
        + _numero(stat, "BK") * PESOS["bk"]
        # El juego de corredores, con los mismos pesos que usa el bateo. Ver el docstring: incluirlos
        # es lo que hace CIERTA la afirmación de que los dos oficios miran los mismos eventos.
        + _numero(stat, "SB") * PESOS["sb"]
        + atrapados * PESOS["cs"]
        + ponches * PESOS["k"]
        + outs_en_juego * PESOS["out"]
    )


def linea_de_bateo(stat: dict[str, Any]) -> str:
    """«3-4, 2B, HR, 4 RBI» — lo que un dominicano lee de un vistazo.

    Las siglas van en inglés, que es como se leen en el béisbol dominicano: RBI y no CI, R y no CA.
    Es regla del sitio, no preferencia de esta función — ver `docs/AUTORIDAD.md`.

    Solo se nombra lo que ocurrió: un cero no se escribe. Una línea con «0 HR, 0 RBI» ocupa el mismo
    espacio y no dice nada.
    """
    partes = [f"{int(_numero(stat, 'H'))}-{int(_numero(stat, 'AB'))}"]
    for clave, etiqueta in (("X2B", "2B"), ("X3B", "3B"), ("HR", "HR")):
        cantidad = int(_numero(stat, clave))
        if cantidad:
            partes.append(etiqueta if cantidad == 1 else f"{cantidad} {etiqueta}")
    for clave in ("RBI", "R", "BB", "SB"):
        cantidad = int(_numero(stat, clave))
        if cantidad:
            partes.append(f"{cantidad} {clave}")
    return ", ".join(partes)


def linea_de_pitcheo(stat: dict[str, Any]) -> str:
    """«7.0 IP, 0 ER, 9 K, 1 BB (W)» — las entradas primero, que es lo que sitúa la actuación.

    LOS BOLETOS ENTRARON EL 2026-07-31, a pedido del dueño, y el orden pasó a IP, ER, K, BB. Faltaban
    desde siempre y el motivo para ponerlos no es de gusto: **el valor sí los cuenta** —pesan -0,326
    carreras cada uno, la misma matriz que castiga al bateador que los recibe— así que sin ellos la
    línea no explicaba su propio número. La misma razón por la que la del bateador lleva el promedio.

    El orden lo comparte con `ventana.linea_de_pitcheo`: los tres paneles de la franja están uno
    debajo del otro y leerse distinto los haría parecer cosas distintas. Lo único que no comparten es
    la decisión, que allá se quita porque en catorce días es de un juego suelto.

    Las filas ya guardadas conservan el formato viejo hasta que se reprocese su jornada con
    `build_daily_standouts --fecha`. No se reescriben en masa: son texto de lectura, y una jornada de
    mayo sin boletos no dice nada falso — dice menos.
    """
    partes = [
        f"{stat.get('IP', '0.0')} IP",
        f"{int(_numero(stat, 'ER'))} ER",
        f"{int(_numero(stat, 'K'))} K",
        f"{int(_numero(stat, 'BB'))} BB",
    ]
    for clave in ("W", "SV", "HLD"):
        if _numero(stat, clave):
            partes.append(f"({'H' if clave == 'HLD' else clave})")
            break
    return ", ".join(partes)


def splits(client: MlbProxyClient, grupo: str, dia: date) -> list[dict[str, Any]]:
    """Toda la liga en ese día, en una llamada. Sin juegos devuelve lista vacía, no error.

    Pública porque la pizarra la usa para saber quién vio acción: es la misma pregunta y no tiene
    sentido que existan dos formas distintas de hacerla.
    """
    payload = client.get(
        "/api/v1/stats",
        {
            "stats": "byDateRange",
            "group": grupo,
            "season": dia.year,
            "startDate": dia.isoformat(),
            "endDate": dia.isoformat(),
            "playerPool": "All",
            "limit": _LIMITE,
        },
    )
    return [split for bloque in (payload.get("stats") or []) for split in (bloque.get("splits") or [])]


def _actuaciones(
    client: MlbProxyClient,
    grupo: str,
    dia: date,
    universo: set[int],
    codigos: dict[int, str],
    puntuar: Calculo,
    describir: Descripcion,
    avisar: Aviso = None,
) -> list[Actuacion]:
    salida = []
    descartadas: list[str] = []
    for split in splits(client, grupo, dia):
        jugador = split.get("player") or {}
        if jugador.get("id") not in universo:
            continue
        stat = split.get("stat") or {}

        # UNA LÍNEA IMPOSIBLE NO SE PUNTÚA (DEV-01 del review v13). Ver `por_que_no_cuadra`: los
        # componentes se sacan restando, así que un campo ausente inventa cantidades negativas y en
        # pitcheo eso PREMIA al lanzador. Se descarta la fila y se deja dicho en el log, en vez de
        # publicar un número plausible construido con componentes que no pueden existir.
        if motivo := por_que_no_cuadra(stat, grupo):
            quien = jugador.get("fullName") or jugador.get("id")
            logger.warning("daily: línea imposible descartada — %s (%s, %s, %s): %s", quien, grupo, dia, motivo, stat)
            descartadas.append(f"{quien}: {motivo}")
            continue

        salida.append(
            Actuacion(
                player_id=jugador["id"],
                nombre=jugador.get("fullName") or "",
                equipo=codigos.get((split.get("team") or {}).get("id") or 0, ""),
                valor=puntuar(stat),
                linea=describir(stat),
            )
        )
    # EL DESCARTE TAMBIÉN VA A `IngestRun`, no solo al log del contenedor (review del 2026-07-30). El
    # log de Docker se rota y hay que entrar al servidor a leerlo; `IngestRun` es lo que se mira desde
    # el backoffice cuando el widget enseña menos gente de la esperada. Un descarte que solo existe en
    # un log que nadie abre es, en la práctica, un descarte silencioso.
    #
    # UN AVISO POR GRUPO Y NO UNO POR FILA: si el proxy se degrada de verdad, esto podrían ser cientos
    # de líneas metidas en una columna de texto. Se dan las tres primeras y el total, que es lo que
    # permite decidir si mirar el log completo.
    if descartadas and avisar is not None:
        muestra = "; ".join(descartadas[:3])
        resto = f" (y {len(descartadas) - 3} más)" if len(descartadas) > 3 else ""
        avisar(f"{len(descartadas)} líneas imposibles descartadas en {grupo} — {muestra}{resto}.")

    # Por valor, y el id desempata para que dos actuaciones idénticas no bailen entre corridas.
    return sorted(salida, key=lambda a: (-a.valor, a.player_id))


def destacados(
    client: MlbProxyClient, dia: date, universo: set[int], avisar: Aviso = None
) -> dict[str, list[Actuacion]]:
    """Las dos listas del día, ya ordenadas. El recorte a los primeros N lo decide quien muestre.

    `avisar` recibe lo que hay que dejar escrito en la fila de `IngestRun` — hoy, las líneas que se
    descartaron por imposibles. Es opcional para que la función se pueda llamar desde un shell sin
    montar un registro de corrida.
    """
    # El split solo trae el id y el nombre largo del equipo («San Diego Padres»); el código de tres
    # letras sale de `/teams`, que es la misma traducción que ya hace el descargador de temporadas.
    codigos = fetch_team_codes(client, dia.year)
    return {
        "bateo": _actuaciones(client, "hitting", dia, universo, codigos, valor_de_bateo, linea_de_bateo, avisar),
        "pitcheo": _actuaciones(client, "pitching", dia, universo, codigos, valor_de_pitcheo, linea_de_pitcheo, avisar),
    }


def guardar(dia: date, listas: dict[str, list[Actuacion]]) -> int:
    """Reemplaza la jornada en la tabla. Devuelve cuántas filas quedaron.

    Se borra y se reescribe el día entero en vez de hacer upsert fila por fila: una jornada es una
    unidad —o se tiene completa o no se tiene— y así una segunda corrida del mismo día no puede dejar
    mezclados los resultados de dos consultas al proxy.
    """
    from django.db import transaction

    from dglweb.players.models import Player
    from dglweb.stats.models import DailyStandout

    conocidos = set(Player.todos.values_list("player_id", flat=True))
    filas = [
        DailyStandout(
            fecha=dia,
            grupo=grupo,
            player_id=actuacion.player_id,
            team=actuacion.equipo,
            linea=actuacion.linea,
            valor=actuacion.valor,
        )
        for grupo, actuaciones in listas.items()
        for actuacion in actuaciones
        # El universo con el que se filtró viene de fuera; esto es la red por si trae a alguien que
        # no está en el maestro, porque la FK reventaría al escribir.
        if actuacion.player_id in conocidos
    ]
    with transaction.atomic():
        DailyStandout.objects.filter(fecha=dia).delete()
        DailyStandout.objects.bulk_create(filas)
    return len(filas)


@dataclass(frozen=True)
class Destacado:
    """Una fila del widget, ya con su video al lado.

    Envuelve a la fila de la tabla en vez de colgarle atributos encima: `clips` no es una columna y
    fingir que lo es deja al modelo mintiendo sobre lo que guarda. La plantilla lee lo mismo.
    """

    player: Any  # `players.models.Player`
    team: str
    linea: str
    clips: tuple[Any, ...]  # `videos.Clip`
    # `grupo` y `valor` NO se muestran: están para poder ordenar la lista mezclada. Sin ellos habría
    # que llevar dos listas paralelas —una para pintar y otra para ordenar— y basta con que se
    # desincronicen una vez para publicar un orden falso.
    #
    # Acá decía «en una misma unidad (`en_carreras`)». Esa función ya no existe: desde el 2026-07-29
    # los dos oficios se calculan con la misma matriz, así que `valor` YA está en carreras venga de
    # donde venga y no hay nada que convertir. `grupo` sigue haciendo falta para el piso, que sí es
    # distinto en cada oficio — ver `PISO_BATEO` y `PISO_PITCHEO`.
    grupo: str = "bateo"
    valor: float = 0.0
    fecha: date | None = None
    # Lo que se dibuja al lado del nombre cuando la fila NO es de la jornada de arriba: «Ayer», o la
    # fecha corta si el hueco es mayor. Vacío para las de la jornada de referencia — etiquetarlas
    # todas sería repetir en seis filas lo que ya dice el título.
    etiqueta: str = ""

    @property
    def foto(self) -> str:
        """La ruta del retrato, armada acá y no con `{% static %}` en la plantilla. Ver `mugshots`."""
        from dglweb.players import mugshots

        return mugshots.url(self.player.player_id, mugshots.CHICO)

    @property
    def logo(self) -> str:
        """Ruta relativa a `static/`, para `{% static %}`.

        Los treinta SVG de los equipos SÍ viven en la imagen. Se devuelve la ruta completa —y no un
        prefijo que la plantilla complete— porque el manifiesto de producción resuelve archivos, no
        pedazos de ruta.
        """
        return f"img/equipos/{self.team}.svg" if self.team else ""

    @property
    def nombre(self) -> str:
        """Abreviado como en el widget de líderes, para que las dos mitades de la franja rimen."""
        from dglweb.stats.mlb_leaders import nombre_corto

        return nombre_corto(self.player.full_name)


# EL PLIEGUE DEL MÓVIL, y solo del móvil (decisión del dueño, 2026-07-31). Ver el mismo bloque en
# `stats/ventana.py`, que gobierna los otros dos paneles de la franja.
#
# En escritorio la rejilla arma dos columnas y las diez cajas entran en las cinco filas del marco, sin
# botón. En un teléfono arma UNA columna —diez filas de scroll— así que el marco se recorta a cuatro y
# vuelve el «Ver N más». Este número es ese pliegue: lo que queda detrás del botón.
#
# Eran seis, en tres filas, hasta el 2026-07-31.
#
# Las pestañas por oficio que había acá se retiraron antes (dueño, 2026-07-27). Nunca llegaron a
# dibujarse: se activaban pasados los 6 destacados y la portada pedía como mucho 5.
VISIBLES = 4

# El tope de lo que se manda al navegador: la capacidad del marco en escritorio, 2 columnas x 5 filas.
# Medido sobre 14 jornadas con el piso puesto, la mejor dio 11 destacados — o sea que se pierde uno en
# el día más generoso del mes, a cambio de que lo que se manda sea exactamente lo que cabe.
MAXIMO = 10


def _pasan_el_piso() -> Any:  # noqa: ANN401 — es un `Q` de Django, tipado como Any para no importarlo arriba
    """El filtro «esto sí es una actuación destacada», con el piso de cada oficio.

    Va en un solo sitio porque lo usan dos consultas —cuál es la última jornada con destacados, y
    cuáles son— y que se separaran daría el peor fallo posible: una fecha elegida por un criterio y
    unas filas por otro, o sea un widget con el título de hoy y el contenido vacío.
    """
    from django.db.models import Q

    from dglweb.stats.models import DailyStandout

    return Q(grupo=DailyStandout.Grupo.BATEO, valor__gte=PISO_BATEO) | Q(
        grupo=DailyStandout.Grupo.PITCHEO, valor__gte=PISO_PITCHEO
    )


def _publicables() -> Any:  # noqa: ANN401 — un `QuerySet[DailyStandout]`, sin importarlo arriba
    """Los destacados que PUEDEN salir al público: pasan el piso **y** su jugador no está oculto.

    Por qué las dos condiciones juntas y no la visibilidad suelta en cada consulta: por lo mismo que
    dice `_pasan_el_piso()`, y acá muerde igual de fuerte. Las tres consultas de `portada()` tienen
    que estar de acuerdo sobre qué existe. Si la fecha de referencia se eligiera contando a un
    jugador oculto y las filas lo excluyeran, el resultado sería **un widget con el título de una
    jornada y el cuerpo vacío** — que es exactamente el fallo contra el que se escribió aquel
    comentario.

    Y va acá al leer, no al construir, a propósito: el dato crudo tiene que seguir entrando —así
    reactivar a un jugador es instantáneo y no exige recalcular nada— y lo que obedece al contrato de
    «deshabilitado» es la publicación. Es la misma regla de `players/visibility.py`.
    """
    from dglweb.players.visibility import only_visible
    from dglweb.stats.models import DailyStandout

    return only_visible(DailyStandout.objects.filter(_pasan_el_piso()))


def equipos_terminados(pizarra: Any, dia: date) -> set[str]:  # noqa: ANN401 — `scoreboard.Pizarra`
    """Los equipos cuyos juegos de `dia` están TODOS terminados.

    Es lo que hace honesta la carga horaria. `byDateRange` no distingue juego terminado de juego en
    curso: devuelve lo acumulado hasta ese instante. Sin este filtro, el widget publicaría «1.0 IP,
    1 K» de alguien que sigue en el montículo, y ese número cambiaría solo bajo los ojos del lector
    — peor que estar desactualizado. Medido el 27-07 a media tarde: entre los mejores del día
    aparecía un lanzador de SEA con el juego en marcha.

    «TODOS» y no «alguno» por las dobles tandas: con el primer juego final y el segundo en curso, las
    cifras del día siguen moviéndose para ese equipo.
    """
    jugando: set[str] = set()
    terminados: set[str] = set()
    for jornada in getattr(pizarra, "jornadas", ()):
        if jornada.dia != dia:
            continue
        for juego in jornada.juegos:
            for lado in juego.lados:
                (terminados if juego.estado == scoreboard.FINAL else jugando).add(lado.codigo)
    return terminados - jugando


def portada() -> dict[str, Any] | None:
    """Los destacados de la portada: las dos jornadas más recientes, en un solo flujo.

    NO es «la última jornada» y esa es la diferencia que se ve. Antes el widget era una foto de ayer
    que no se movía en 24 horas, y la portada parecía muerta durante todo el día. Ahora, según van
    terminando los juegos de hoy, sus destacados entran POR ARRIBA y empujan a los de ayer hacia
    abajo; el widget nunca está hueco porque los de ayer siguen ahí llenando lo que falte.

    El orden es fecha descendente y, dentro de cada fecha, valor en carreras descendente. Las dos
    claves importan: sin la fecha, una jornada de ayer excepcional taparía el primer destacado de hoy
    —que es la noticia—; sin el valor, el orden dentro del día sería arbitrario.

    Devuelve `None` cuando no hay nada que pase el piso, para que la plantilla no dibuje el panel
    hueco. Un widget vacío se lee como un sitio roto.
    """

    # LA ÚLTIMA JORNADA CON DESTACADOS, Y LA DE ANTES DE ELLA. Decisión del dueño (2026-07-27): el
    # «hoy» del widget es la fecha más alta que tengamos de un juego terminado, y el «ayer» es esa
    # fecha menos uno. No el calendario.
    #
    # La diferencia importa dos veces al día. A las 10 de la mañana el calendario dice 27 y no hay
    # nada del 27: con la regla del calendario el widget enseñaría solo el 26 y perdería el contexto
    # del 25. Y al revés, la primera versión de esto pedía «las dos fechas más recientes que tengan
    # datos», que con un hueco de por medio metía anteayer disfrazado de ayer.
    #
    # Anclando en la referencia, «Ayer» significa siempre lo mismo: el día anterior a la jornada que
    # se está enseñando. Es la única lectura que no obliga al lector a saber qué día es hoy.
    # FUERA DE TEMPORADA NO SE DIBUJA (dueño, 2026-08-01). Este widget no tenía ninguna regla de
    # fechas: enseñaba la jornada más reciente que hubiera guardada, viniera de donde viniera.
    #
    # En noviembre eso significa un titular que dice «Destacados **ayer y hoy**» encima de un 3-4 del
    # 28 de octubre. Y no se limpiaba solo: las filas viejas las borra `podar()`, que llama este mismo
    # comando, que está saltando por estar fuera de temporada. O sea cinco meses afirmando que la
    # Serie Mundial fue hoy.
    #
    # Sin rampa, al revés que las dos rachas: a este widget le basta UNA jornada, y el día de apertura
    # por la mañana todavía no hay filas — devuelve `None` y no se dibuja solo. El caso vacío ya lo
    # cubre, así que pedirle días de más sería esconderlo cuando sí tiene algo que decir.
    if not season_window.se_publica():
        return None

    referencia = _publicables().order_by("-fecha").values_list("fecha", flat=True).first()
    if referencia is None:
        return None

    anterior = referencia - timedelta(days=1)
    fechas = [referencia]
    if _publicables().filter(fecha=anterior).exists():
        fechas.append(anterior)

    from dglweb.stats import videos

    elegidas = _publicables().filter(fecha__in=fechas).select_related("player").order_by("-fecha")

    # El video se resuelve acá y no en la plantilla: una sola consulta por fecha, y así la plantilla
    # no tiene que saber que existe una tabla de videos.
    por_fecha: dict[date, set[int]] = {}
    for fila in elegidas:
        por_fecha.setdefault(fila.fecha, set()).add(fila.player_id)
    clips = {fecha: videos.por_jugador(fecha, ids) for fecha, ids in por_fecha.items()}

    # La jornada de arriba no lleva etiqueta —es la de referencia y su fecha ya está en el título—;
    # las de abajo van con la SUYA.
    #
    # Decía «Ayer» y se cambió por la fecha (dueño, 2026-07-28). Es más corto de leer pero obliga a
    # hacer una cuenta: para saber de qué día habla hay que saber primero de qué día es la jornada de
    # arriba, que está en la otra punta del panel. La fecha se lee sola.
    #
    # `date_format` y no una tabla de meses propia: da «26 Jul», que es exactamente lo que usa el
    # título del widget, así que las dos fechas del panel se escriben igual. El CSS las pasa a
    # mayúsculas.
    lista = sorted(
        (
            Destacado(
                player=fila.player,
                team=fila.team,
                linea=fila.linea,
                clips=clips.get(fila.fecha, {}).get(fila.player_id, ()),
                grupo=fila.grupo,
                valor=fila.valor,
                fecha=fila.fecha,
                etiqueta="" if fila.fecha == referencia else date_format(fila.fecha, "j M"),
            )
            for fila in elegidas
        ),
        # `valor` a secas, sin traducir. Desde el 2026-07-29 los dos oficios se puntúan con la misma
        # matriz de pesos lineales, así que ya vienen en carreras los dos — ver `valor_de_pitcheo`.
        # Antes acá había un `en_carreras(grupo, valor)` que convertía el Game Score, y esa conversión
        # era el problema: metía a los lanzadores en una escala del doble que la de los bateadores.
        key=lambda d: (d.fecha.toordinal() if d.fecha else 0, d.valor),
        reverse=True,
    )[:MAXIMO]

    return {
        "dia": referencia,
        "destacados": lista,
        # Los que caben sin desplegar y los que quedan detrás del botón. El corte se decide ACÁ y no
        # midiendo en el navegador —como sí hace el widget de líderes, cuya rejilla cambia de columnas
        # con el ancho— porque esta es fija: 2 por 3. Un número que ya se sabe no hay que medirlo.
        "visibles": lista[:VISIBLES],
        "de_mas": lista[VISIBLES:],
    }


def podar(temporada_activa: int | None) -> int:
    """Borra las jornadas que no son de la temporada en curso. Devuelve cuántas se fueron.

    Sin temporada activa NO se borra nada. Es el caso de que nadie marcó la nueva en el Backoffice, y
    ahí lo prudente es no tocar: una tabla con datos viejos es un problema menor que una vacía por un
    despiste de configuración.
    """
    from dglweb.stats.models import DailyStandout

    if temporada_activa is None:
        return 0
    borradas, _ = DailyStandout.objects.exclude(fecha__year=temporada_activa).delete()
    return int(borradas)
