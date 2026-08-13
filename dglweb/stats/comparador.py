"""El cálculo del comparador de peloteros. Ver `docs/COMPARADOR.md` para el diseño completo.

Acá NO se dibuja nada: se calculan los valores de cada jugador y su puesto histórico. La página y el
PNG salen de esto sin volver a tocar la base.

LA IDEA QUE SIMPLIFICA LAS TRES MODALIDADES
--------------------------------------------
Las tres son **la misma operación sobre bolsas de temporadas distintas**:

    temporada    la bolsa tiene UNA temporada
    carrera      la bolsa tiene TODAS
    mejores X    la bolsa tiene las X de más WAR

Una vez armada la bolsa, el valor de cada métrica se calcula igual en los tres casos, y el ranking
también: se arman las bolsas de los 981 dominicanos con el mismo criterio y se cuenta cuántos
superan. Sin ramas por modalidad y sin tres caminos que se van separando con el tiempo.

EL RANKING ES UNO Y ES EL HISTÓRICO
------------------------------------
Contra dominicanos, siempre — el sitio existe para ordenarlos entre ellos.

El de temporada se descartó: el universo dominicano de un año es pequeño y para las tasas se encoge
más, así que «1º en 2024» dice lo mismo que dijo en 2021, 2022 y 2023 para el mismo pelotero. Un
número que casi siempre sale igual no distingue nada. El histórico sí cuesta: compite contra las
5.185 temporadas dominicanas de la historia.

**El tablero `dgl_leader` NO sirve para esto**, y conviene saberlo antes de intentarlo: guarda las
puntas, no a todo el mundo. En jonrones de 2019 tiene 69 de los 142 que batearon. Acá se rankea al
vuelo sobre las tablas de temporada, que con 5.185 filas es instantáneo y nunca queda desfasado.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from dglweb.players.models import Player
from dglweb.players.visibility import only_visible
from dglweb.stats import career_rate, qualifier
from dglweb.stats.formula import QUALIFIER_RE
from dglweb.stats.leaders import _MODEL, FIRST_SEASON
from dglweb.stats.models import Metric

# LAS TRES MODALIDADES.
MODO_TEMPORADA = "temporada"
MODO_CARRERA = "carrera"
MODO_MEJORES = "mejores"

# DE 1 A 7 TEMPORADAS (dueño, 2026-08-11). El dueño lo llama el killer feature de los tres, así que
# se le abre el rango en vez de dejarlo clavado en cinco.
#
# EL SUELO DE TRES DESAPARECIÓ con esta decisión, y tiene sentido: existía porque «pico de carrera»
# no significaba nada por debajo de tres años. Pero con X=1 la pregunta cambia y vuelve a ser buena
# —«su mejor año contra su mejor año»— y NO es la misma que el modo temporada: allí el año lo elige
# quien compara, acá lo elige el WAR.
#
# EL SIETE ES EL TECHO porque más allá la modalidad se convierte en la de carrera para casi todos:
# solo 305 bateadores y 162 lanzadores llegan a seis temporadas, y de ahí para arriba la muestra se
# adelgaza rápido.
TEMPORADAS_MINIMAS, TEMPORADAS_MAXIMAS = 1, 7

# QUÉ CUENTA COMO TEMPORADA EN «MEJORES X». FIJO, no configurable (dueño, 2026-08-11).
#
# EL PROBLEMA QUE RESUELVE: un año de cinco turnos aporta un WAR cercano a cero, y si alguien tiene
# exactamente cinco temporadas y una es de café, pasa la validación y luego arrastra el agregado.
#
# LOS NÚMEROS SON BAJOS A PROPÓSITO. La primera propuesta fue 400 PA y 50 IP, y medido se llevaba el
# feature por delante: con PA>=400 quedan 84 bateadores capaces de hacer «mejores 5», de 366. El
# motivo es que 400 PA describe «una temporada de TITULAR», y lo que hay que excluir es «una
# temporada que no existió». Un año de 150 turnos es un suplente de verdad.
#
#     bateo      sin umbral 366 peloteros | >=100 PA 161 | >=200 PA 125 | >=400 PA 84
#     pitcheo    sin umbral 197 peloteros | >=30 IP  132 | >=60 IP   79 | >=150 IP 24
#
# SOLO APLICA A «MEJORES X». En carrera NO se filtra nada: los 703 jonrones de Pujols incluyen su
# última temporada, valga lo que valga.
#
# POR QUÉ NO LO ELIGE EL USUARIO. Se planteó como campo del formulario y se descartó: el umbral cambia
# también la POBLACIÓN DEL RANKING. Con uno pidiendo 100 PA y otro 400, el «2º histórico» de la misma
# tarjeta diría cosas distintas — dos verdades incompatibles circulando con la misma marca. Y de paso
# multiplicaría las URLs, porque cada umbral sería una página que cachear e indexar.
#
# Fijo y ESCRITO EN LA TARJETA, que es lo que lo hace interpretable: quien la mire sabe con qué se hizo.
# LOS TRES OFICIOS. Bateo es uno; pitcheo son DOS, y esa es la corrección de 2026-08-13.
OFICIO_BATEO, OFICIO_ABRIDOR, OFICIO_RELEVISTA = "batting", "SP", "RP"

MINIMO_TEMPORADA: dict[str, int] = {OFICIO_BATEO: 100, OFICIO_ABRIDOR: 30, OFICIO_RELEVISTA: 20}

# ABRIDORES Y RELEVISTAS NO SE MIDEN CON LA MISMA VARA (dueño, 2026-08-13).
#
# EL PROBLEMA, que se veía en la tarjeta de José Mesa contra Rafael Soriano: a Soriano le faltaban los
# puestos de TODAS las tasas —efectividad, WHIP, FIP, SO/9…— mientras Mesa los tenía. El umbral de
# carrera del catálogo es IP>=1000, que es de abridor. Soriano lanzó 636 entradas en catorce
# temporadas porque era cerrador, y ningún cerrador se acerca a mil.
#
# MEDIDO: solo 87 de los 527 lanzadores dominicanos son abridores. El umbral no estaba mal calibrado
# «para lanzadores» — estaba calibrado para el 17 % de ellos. De los 440 relevistas, SIETE llegan a
# 1.000 IP, y son los que fueron abridores parte de su carrera (Mesa, con 95 aperturas, es uno).
#
# LOS NÚMEROS SALEN DE IGUALAR LA PROPORCIÓN QUE COMPITE, no de igualar las entradas:
#
#                          abridores (87)        relevistas (440)
#     carrera    IP>=1000  → 29                  IP>=400 → 63
#     temporada  IP>=162   → 35 % de sus años    IP>=50  → 37 % de los suyos
#
# El 50 lo eligió el dueño sobre el 40, que habría dado 81 relevistas capaces de «mejores 5» en vez
# de 64: prefiere la población más selecta y simétrica con la de los abridores.
UMBRAL_RELEVISTA_TEMPORADA, UMBRAL_RELEVISTA_CARRERA = "IP>=50", "IP>=400"

# Mientras el oficio no llegue a todas las capas, el valor conservador para pitcheo es el de ABRIDOR:
# es el que estaba antes, así que quien no diga su oficio no ve cambiar nada bajo los pies.
_MINIMO_POR_GRUPO: dict[str, int] = {"batting": 100, "pitching": MINIMO_TEMPORADA[OFICIO_ABRIDOR]}


def minimo_de(grupo: str, oficio: str = "") -> int:
    """Qué cuenta como temporada, por oficio si se sabe y por grupo si no.

    EXISTE PORQUE EL OFICIO NO LLEGA A TODAS PARTES todavía: la tarjeta y el endpoint de años solo
    conocen el grupo de métricas. Se pasa el oficio donde se tiene y se cae al valor de abridor donde
    no, que es el que regía antes de separarlos.
    """
    if oficio in MINIMO_TEMPORADA:
        return MINIMO_TEMPORADA[oficio]
    return _MINIMO_POR_GRUPO[grupo]

# En qué columna se mide cada oficio. Pitcheo se guarda en OUTS, no en entradas, así que el umbral en
# IP hay que multiplicarlo por tres — es el error clásico de esta tabla.
_COLUMNA_UMBRAL: dict[str, tuple[str, int]] = {"batting": ("pa", 1), "pitching": ("outs", 3)}

# LO QUE PASA CON QUIEN NO LLEGA A LAS PEDIDAS: se baja hasta donde alcance el que menos tenga.
#
# Se toman tantas como tenga el más corto de los dos, y el rótulo de la imagen dice el número REAL —
# «Mejores 3 temporadas por WAR» aunque se hubieran pedido siete. Es lo que impide la comparación
# tramposa: cinco temporadas acumulan más de todo que tres, así que enfrentar 5 contra 3 le daría la
# victoria al de carrera larga POR CONSTRUCCIÓN, y un pie de foto no salva esa lectura.
#
# Medido, para saber cuánto se va a usar el descenso: el 58 % de los bateadores y el 65 % de los
# lanzadores no llegan a cinco temporadas.

# Las métricas de cada oficio, en el orden en que se pintan. Elegidas por el dueño (2026-08-11).
#
# `W` y `L` van seguidas porque la imagen las pinta en UNA celda —«18-7»— pero acá son dos métricas
# como cualquier otra. Lo que NO se hace es rankear el porcentaje de victorias: ver `SIN_RANKING`.
METRICAS: dict[str, tuple[str, ...]] = {
    "batting": ("war", "g", "pa", "h", "hr", "rbi", "sb", "avg", "obp", "slg", "ops", "woba", "w_rc_plus"),
    "pitching": (
        "war", "g", "gs", "outs", "w", "l", "win_pct",
        "era", "era_minus", "whip", "fip", "fip_minus",
        "so", "so_per9", "bb_per9", "hr_per9",
    ),
}

# LO QUE SE PINTA PERO NO SE RANKEA. Hoy solo las derrotas, que acompañan a las victorias en la misma
# celda: «5º dominicano en derrotas» es un dato raro de presumir, y el porcentaje de victorias —que
# sería lo natural— tiene un bug abierto sin diagnosticar. Ver `docs/TODO.md` y `docs/COMPARADOR.md`.
SIN_RANKING: frozenset[str] = frozenset({"l"})

# EL PORCENTAJE DE VICTORIAS SOLO SE RANKEA EN ABRIDORES (dueño, 2026-08-13).
#
# En un relevista el W-L es casi ruido: sus victorias suelen venir de salvamentos volados —entra
# perdiendo, el equipo remonta y se le apunta a él— así que ordenar cerradores por WPCT premia una
# carambola. En un abridor sí mide algo: ganó más de lo que perdió con la pelota en la mano.
#
# HASTA HOY NO SE RANKEABA PARA NADIE, y el motivo escrito era que el WPCT de carrera tenía «un bug
# abierto sin diagnosticar». Ese bug no existía: eran tres mediciones mal hechas. Ver `docs/TODO.md`.
SOLO_ABRIDORES: frozenset[str] = frozenset({"win_pct"})


class TemporadasInsuficientesError(ValueError):
    """Uno de los dos no llega a las temporadas pedidas.

    LLEVA LOS DATOS Y NO LA FRASE. El mensaje que ve el usuario nombra al pelotero —«Marichal no tiene
    7 temporadas, compara con 6 o menos»— y para eso hace falta consultar `Player`, que es trabajo de
    la vista. Acá se dice QUÉ pasó y con qué números; cómo se cuenta es de la capa de arriba.

    `tiene` puede ser 0: quien todavía no tiene el WAR calculado de su temporada de debut.
    """

    def __init__(self, player_id: int, *, tiene: int, pedidas: int) -> None:
        self.player_id, self.tiene, self.pedidas = player_id, tiene, pedidas
        super().__init__(f"el jugador {player_id} tiene {tiene} temporadas y se piden {pedidas}")


@dataclass(frozen=True)
class Registro:
    """Lo que un jugador aporta a la comparación: su bolsa de temporadas, ya resuelta.

    `temporadas` son los años que entraron, para poder rotular «Sus 4 mejores» con el número de
    verdad y no prometer cinco cuando fueron cuatro.
    """

    player_id: int
    temporadas: tuple[int, ...]
    componentes: dict[str, Any]


@dataclass(frozen=True)
class Celda:
    """Una métrica de un jugador: su valor, su puesto histórico y de cuántos."""

    metrica: str
    valor: float | None
    rank: int | None
    de: int
    # `True` cuando el valor es una media ponderada y no el número exacto — wOBA, wRC+, FIP, ERA- y
    # FIP- llevan coeficientes que cambian cada año, así que no se pueden reconstruir sumando
    # componentes. La imagen tiene que marcarlo con un asterisco.
    aproximada: bool


def universo(grupo: str, oficio: str = "") -> set[int]:
    """Los dominicanos que entran al comparador: debut desde 1956 y no deshabilitados.

    EL CORTE NO ES POR FECHA SINO POR FUENTE. Deja fuera a los siete de las Ligas Negras —Pedro San,
    Tetelo Vargas, Néstor Lambertus, Sijo Gómez, Horacio Martínez, Enrique Lantigua y Julio Báez—
    porque sus estadísticas no son comparables con las de Grandes Ligas y el WAR ni siquiera existe
    para ellas: de sus 27 temporadas en la base, ninguna lo tiene. Compararlos sería inventar una
    equivalencia que los datos no sostienen.

    Se aplica UNA vez, acá, y vale para el selector, el cálculo y el ranking. Ningún pelotero tiene la
    fecha de debut vacía, así que nadie queda en tierra de nadie por un nulo.

    CUIDADO SI ALGUIEN MUEVE EL CORTE: cinco de esos siete tienen debut el 1 de enero porque se conoce
    el año y no el día — Tetelo Vargas debutó en 1927, no el 1 de enero de 1927. Para un corte por AÑO
    da igual; para uno dentro del año, dejaría de funcionar.
    """
    del grupo  # el universo base es el mismo para los dos grupos de métricas
    peloteros = Player.objects.filter(debut_date__year__gte=FIRST_SEASON)
    # EL OFICIO PARTE LA POBLACIÓN DEL RANKING (dueño, 2026-08-13): un relevista se rankea contra
    # relevistas y un abridor contra abridores. Sin esto, bajarle el umbral a los relevistas los
    # metería a competir en efectividad contra abridores de 200 entradas al año, que es otra pregunta.
    #
    # Manda `Player.pos`, o sea el oficio de HOY. Un abridor reconvertido a cerrador aparece donde diga
    # su posición actual, y es lo correcto: es como se le conoce y como se le va a buscar.
    if oficio in (OFICIO_ABRIDOR, OFICIO_RELEVISTA):
        peloteros = peloteros.filter(pos=oficio)
    elif oficio == OFICIO_BATEO:
        peloteros = peloteros.exclude(pos__in=["P", OFICIO_ABRIDOR, OFICIO_RELEVISTA])
    return set(peloteros.values_list("player_id", flat=True))


def _filas(grupo: str) -> list[dict[str, Any]]:
    """Todas las temporadas dominicanas del oficio, con los componentes y las métricas que hacen falta.

    Se traen ENTERAS y una sola vez. Son 5.185 filas en bateo y 3.046 en pitcheo: cabe en memoria sin
    discusión, y tenerlas todas es lo que permite rankear al vuelo sin una tabla de puestos.

    `season_totals()` colapsa las temporadas repartidas entre equipos, que vienen con una fila por
    club MÁS la combinada. Sin eso, quien fue traspasado contaría doble — la suma cruda de Fernando
    Rodney da 61-88 y la colapsada 48-71, que es la buena.
    """
    modelo = _MODEL[grupo]
    componentes = career_rate.COMPONENTS[grupo]
    columnas = list(dict.fromkeys(["player_id", "season", "war", *METRICAS[grupo], *componentes]))
    base = only_visible(modelo._default_manager.filter(season__gte=FIRST_SEASON))
    return list(base.season_totals().values(*columnas))  # type: ignore[attr-defined]


def _por_jugador(filas: list[dict[str, Any]], dentro: set[int]) -> dict[int, list[dict[str, Any]]]:
    bolsas: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for fila in filas:
        if fila["player_id"] in dentro:
            bolsas[fila["player_id"]].append(fila)
    return bolsas


def inventario(grupo: str, *pids: int, oficio: str = "") -> dict[int, tuple[list[int], int]]:
    """Qué puede aportar cada pelotero: `(años comparables, cuántos son)`, de más reciente a más viejo.

    LO USA EL GENERADOR PARA HABLAR EN CASTELLANO. El formulario tiene que poder decir «Marichal no
    tiene 7 temporadas de al menos 30 IP, compara con 6 o menos» ANTES de mandar a nadie a una URL
    que no existe, y para llenar el desplegable de años necesita la lista.

    EL UMBRAL MANDA TAMBIÉN ACÁ, y en las tres modalidades (dueño, 2026-08-13). Hubo una versión que
    devolvía todos los años jugados con el argumento de que un año de veinte turnos es un año que
    jugó; se descartó porque el desplegable lo ofrecería, y ofrecer una comparación cuyo resultado no
    dice nada es peor que no ofrecerla. El número de la izquierda de la tupla y el de la derecha
    hablan del mismo conjunto: si se separan, el error y el desplegable se contradicen.
    """
    # EL OFICIO TIENE QUE LLEGAR HASTA ACÁ. Sin él, el asistente le exige 30 IP a un relevista —el
    # mínimo de abridor— mientras la tarjeta ya lo acepta con 20: la pantalla diría que no tiene
    # temporadas suficientes y la imagen las contaría. Dos capas contando distinto sobre el mismo
    # pelotero es la peor forma de equivocarse, porque ninguna de las dos parece rota.
    #
    # El universo NO se filtra por oficio acá: esto mira a un pelotero concreto, no arma un ranking.
    dentro = universo(grupo) & set(pids)
    bolsas = _por_jugador(_filas(grupo), dentro)
    minimo = minimo_de(grupo, oficio)
    salida: dict[int, tuple[list[int], int]] = {}
    for pid in pids:
        anios = sorted(
            {t["season"] for t in _mejores(bolsas.get(pid, []), 10**6, grupo, minimo)}, reverse=True
        )
        salida[pid] = (anios, len(anios))
    return salida


def _mejores(temporadas: list[dict[str, Any]], cuantas: int, grupo: str, minimo: int) -> list[dict[str, Any]]:
    """Las `cuantas` de más WAR entre las que cuentan como temporada. Ver `MINIMO_TEMPORADA`.

    Las temporadas sin WAR quedan fuera en vez de contar como cero: un año sin dato no es un año malo.

    Y las que no llegan al umbral tampoco, que es distinto: un año de cinco turnos SÍ tiene WAR —cerca
    de cero— así que sin este filtro entraría en la bolsa de quien tenga justo cinco temporadas y le
    hundiría el agregado.
    """
    columna, factor = _COLUMNA_UMBRAL[grupo]
    piso = minimo * factor
    cuentan = [t for t in temporadas if t.get("war") is not None and (t.get(columna) or 0) >= piso]
    return sorted(cuentan, key=lambda t: (-t["war"], t["season"]))[:cuantas]


def _sumar(temporadas: list[dict[str, Any]], claves: list[str]) -> dict[str, Any]:
    """Suma componente a componente. `None` si NINGUNA temporada lo tiene; los nulos sueltos no restan."""
    total: dict[str, Any] = dict.fromkeys(claves)
    for temporada in temporadas:
        for clave in claves:
            valor = temporada.get(clave)
            if valor is not None:
                total[clave] = (total[clave] or 0) + valor
    return total


def _valor(metrica: Metric, temporadas: list[dict[str, Any]], grupo: str) -> tuple[float | None, bool]:
    """El valor de la métrica sobre la bolsa, y si salió aproximado.

    TRES CAMINOS, y el motor de líderes ya los tenía — acá se reusan, no se reinventan:

    1. **Acumulables**: se suman. WAR, G, PA, H, HR, SO, IP…
    2. **Tasas con fórmula conocida**: se recalculan desde los componentes SUMADOS y se divide una
       vez. Para el promedio se suman hits y turnos de todas las temporadas, que no es lo mismo que
       promediar promedios — con volúmenes distintos la diferencia se ve en la tercera cifra.
    3. **Tasas ponderadas**: media de los valores por temporada, pesada por apariciones o entradas.

    EL TERCER CAMINO NO ES PEREZA. wOBA, wRC+, ERA- y FIP- llevan coeficientes que cambian cada
    temporada —y ajuste de parque— y FIP necesita su constante anual. Sumar cinco años de componentes
    y aplicarles un solo juego de pesos mezclaría la escala de 2015 con la de 2024. Comprobado:
    `derive.derived_rates` calcula veintidós tasas de bateo desde componentes y **wOBA no está entre
    ellas**.

    Con una sola temporada en la bolsa los tres caminos dan lo mismo, así que la modalidad de
    temporada no necesita rama propia.
    """
    if not temporadas:
        return None, False

    if metrica.kind == Metric.Kind.CUMULATIVE:
        return _sumar(temporadas, [metrica.column])[metrica.column], False

    if career_rate.has_exact(grupo, metrica.column):
        componentes = _sumar(temporadas, list(career_rate.COMPONENTS[grupo]))
        return career_rate.exact_value(grupo, metrica.column, componentes), False

    peso_col = career_rate.WEIGHT[grupo]
    numerador = denominador = 0.0
    for temporada in temporadas:
        valor, peso = temporada.get(metrica.column), temporada.get(peso_col)
        if valor is not None and peso:
            numerador += valor * peso
            denominador += peso
    return (numerador / denominador if denominador else None), True


def _cumple(metrica: Metric, componentes: dict[str, Any], formula: str) -> bool:
    """El umbral, y SOLO SE LE EXIGE A LAS TASAS.

    Sin él, el ranking de una tasa lo gana quien tuvo tres turnos: un 1.000 de promedio en un turno
    encabezaría la historia del béisbol dominicano.

    A UN CONTEO NO SE LE PIDE, y es la regla del sitio — la misma que usa la página de líderes. «Más
    jonrones» no se logra en veinte turnos, así que la cantidad ya es su propio umbral; exigirle el
    mínimo de apariciones de carrera dejaría fuera a cualquiera que no llegue a 3.000, que es casi
    todo el mundo. Se descubrió porque el ranking de jonrones de carrera salía sobre una población
    VACÍA.

    (El caso donde un conteo sí necesita piso es el extremo MALO —«menos jonrones» lo gana el que
    apenas jugó— y el comparador no tiene ese extremo: enseña a dos peloteros, no una cola.)
    """
    if metrica.kind != Metric.Kind.RATE:
        return True
    return qualifier.qualifies(formula, metrica.stat_group, componentes)




def _bolsa(
    temporadas: list[dict[str, Any]], modo: str, cuantas: int, anio: int | None, grupo: str, minimo: int
) -> list[dict[str, Any]]:
    """Qué temporadas entran, según la modalidad. Es lo ÚNICO que cambia entre las tres."""
    if modo == MODO_TEMPORADA:
        return [t for t in temporadas if t["season"] == anio]
    if modo == MODO_CARRERA:
        return temporadas
    return _mejores(temporadas, cuantas, grupo, minimo)


def _formula(
    metrica: Metric,
    modo: str,
    anio: int | None,
    cajas: tuple[qualifier.Defaults, qualifier.Overrides],
    oficio: str = "",
) -> str:
    """El umbral que se le exige a la métrica en esta modalidad.

    En temporada se resuelve el de ese año —que baja en las temporadas cortas, ver `qualifier`— y en
    carrera, el de carrera. Es el mismo reparto que hace la página de líderes. «Mejores X» no tiene
    umbral fijo, y la de temporada tampoco: dependen de qué años trae cada bolsa. Ver
    `_umbral_de_la_bolsa`.
    """
    defaults, overrides = cajas
    if modo == MODO_TEMPORADA and anio is not None:
        del_anio = qualifier.resolve_season(metrica, anio, defaults, overrides)
        return _relevista(metrica, del_anio, oficio, UMBRAL_RELEVISTA_TEMPORADA)
    return _relevista(metrica, qualifier.resolve_career(metrica, defaults), oficio, UMBRAL_RELEVISTA_CARRERA)


def _relevista(metrica: Metric, normal: str, oficio: str, suyo: str) -> str:
    """El umbral del relevista en vez del del catálogo, cuando toca.

    SOLO SE SUSTITUYE EL UMBRAL DE ENTRADAS. Hay métricas con umbral propio —los coeficientes de bola
    en juego se miden en `BALLS_IN_PLAY`, no en IP— y cambiárselo por uno de entradas las dejaría
    midiendo otra cosa. Por eso se comprueba que la fórmula que venía hablara de IP.
    """
    if oficio != OFICIO_RELEVISTA:
        return normal
    trozo = QUALIFIER_RE.match(normal or "")
    if trozo is None or trozo.group(1).upper() != "IP":
        return normal
    return suyo


def _umbral_de_la_bolsa(
    metrica: Metric,
    modo: str,
    bolsa: list[dict[str, Any]],
    cajas: tuple[qualifier.Defaults, qualifier.Overrides],
    fijo: str,
    oficio: str = "",
) -> str:
    """El umbral que le toca a ESTA bolsa. Fuera de «mejores X» es el de la modalidad, sin más.

    EL FALLO QUE ESTO ARREGLA (lo encontró el dueño con los dos Vladimir Guerrero, 2026-08-13): a una
    bolsa de tres temporadas se le exigía el umbral de CARRERA —PA>=3000—, que ninguna bolsa de tres
    puede alcanzar. La población se quedaba vacía y los dos peloteros salían «1º» en promedio, OBP,
    SLG, OPS, wOBA y wRC+ a la vez. En la tarjeta eso no parece un error, parece un dato.

    LA REGLA ES SUMAR EL UMBRAL DE CADA AÑO QUE TRAE LA BOLSA. Tres temporadas se miden contra tres
    temporadas de titular; cinco, contra cinco. No es multiplicar por X: se resuelve año por año
    porque el umbral BAJA en las temporadas cortas —1981, 1994, 2020— y pedirle 502 apariciones al
    año del confinamiento dejaría fuera a todo el que tuvo la mala suerte de que le tocara.

    Cada bolsa candidata trae sus propios años, así que cada una se mide contra su propia suma. Eso
    es lo correcto y no una aproximación: la pregunta es si ese pelotero fue titular en LOS AÑOS QUE
    ESTÁ APORTANDO.
    """
    # LA MODALIDAD DE TEMPORADA VA POR EL MISMO CAMINO, y esto lo arregló el review v23 (DEV-01).
    #
    # EL FALLO: se resolvía UNA fórmula para todo, sacada del año que viniera primero en la ruta. Con
    # «2020 contra 2021» la población entera se medía con el umbral de uno de los dos: si mandaba
    # 2020 —temporada de 60 juegos, umbral prorrateado— entraban a competir temporadas normales que no
    # calificaban; si mandaba 2021, quedaban fuera temporadas de 2020 que sí. Ni rompía la página ni
    # se veía raro: solo cambiaba quién compite por el puesto.
    #
    # Con la bolsa de una sola temporada, sumar «los umbrales de sus años» da exactamente el de ESE
    # año. El código ya servía; lo único que sobraba era la excepción.
    if modo == MODO_CARRERA:
        return fijo
    defaults, overrides = cajas
    total = 0.0
    campo = operador = ""
    for temporada in bolsa:
        pieza = _relevista(
            metrica, qualifier.resolve_season(metrica, temporada["season"], defaults, overrides),
            oficio, UMBRAL_RELEVISTA_TEMPORADA,
        )
        trozo = QUALIFIER_RE.match(pieza or "")
        if trozo is None:
            # Sin umbral en algún año —o con uno ilegible— no se puede sumar nada coherente, así que
            # la métrica se queda sin umbral. Es lo mismo que hace `qualifies` con una fórmula vacía.
            return ""
        campo, operador, valor = trozo.group(1), trozo.group(2), float(trozo.group(3))
        total += valor
    if not campo:
        return ""
    return f"{campo}{operador}{total:g}"


def comparar(
    grupo: str,
    izquierda: tuple[int, int | None],
    derecha: tuple[int, int | None],
    modo: str,
    cuantas: int = 5,
    oficio: str = "",
) -> dict[str, Any]:
    """Los dos lados de la comparación, con valor y puesto histórico por métrica.

    `izquierda` y `derecha` son `(player_id, temporada)`; la temporada solo se usa en modo temporada,
    y NO tiene que ser la misma en los dos — «Soto 2024 vs. Guerrero 2021» es justo lo que nadie más
    publica.

    EL RANKING SE CALCULA CONTRA LA MISMA MODALIDAD, y eso es lo que lo hace honesto: un agregado de
    cinco temporadas se compara con los mejores quinquenios de los demás, no con sus carreras. Por eso
    `cuantas` viaja en la URL — «sus 4 mejores» y «sus 5 mejores» son rankings distintos.

    Y CONTRA EL MISMO OFICIO: un relevista se rankea entre relevistas. Sin `oficio` la población es
    todo el universo y los umbrales son los de abridor, que es como se comportaba antes de separarlos.
    """
    from dglweb.profiles.metric_layout import qualifier_lookups

    filas = _filas(grupo)
    bolsas = _por_jugador(filas, universo(grupo, oficio))
    cajas = qualifier_lookups()
    minimo = minimo_de(grupo, oficio)

    # EL NÚMERO DE TEMPORADAS SE IGUALA POR ABAJO, con suelo. Se calcula ANTES de armar nada porque
    # decide la bolsa de los dos y también la del ranking: si se comparan cuatrienios, el resto del
    # mundo también se mide por cuatrienios.
    if modo == MODO_MEJORES:
        # LO PEDIDO SE VALIDA CONTRA EL RANGO, y no se recorta en silencio: un 12 escrito en la URL
        # es un error de quien la escribió, y devolver «las 7 mejores» sin decir nada esconde el
        # fallo. El descenso automático es para quien NO TIENE temporadas suficientes, que es otra
        # cosa — ahí no hay error de nadie.
        if not TEMPORADAS_MINIMAS <= cuantas <= TEMPORADAS_MAXIMAS:
            raise ValueError(
                f"se piden entre {TEMPORADAS_MINIMAS} y {TEMPORADAS_MAXIMAS} temporadas, no {cuantas}"
            )
        # SI ALGUNO NO LLEGA, SE AVISA Y NO SE COMPARA (dueño, 2026-08-11).
        #
        # Hubo una versión que bajaba en silencio hasta donde alcanzara el más corto, declarando el
        # número real en el rótulo. Se cambió al montar el generador: con un formulario delante, «pide
        # menos» es más claro que dar otra cosa sin avisar, y además deja la URL diciendo exactamente
        # lo que se pidió.
        #
        # Lo que NO cambia es el principio: nunca se enfrentan 7 temporadas contra 4. Cinco acumulan
        # más de todo que tres, así que el de carrera larga ganaría cualquier acumulado POR
        # CONSTRUCCIÓN. Antes eso se evitaba igualando; ahora, negándose.
        for pid, _ in (izquierda, derecha):
            tiene = len(_mejores(bolsas.get(pid, []), 10**6, grupo, minimo))
            if tiene < cuantas:
                raise TemporadasInsuficientesError(pid, tiene=tiene, pedidas=cuantas)

    metricas = {m.column: m for m in Metric.objects.filter(stat_group=grupo, column__in=METRICAS[grupo])}
    lados: dict[str, dict[str, Any]] = {}
    for nombre, (pid, anio) in (("izquierda", izquierda), ("derecha", derecha)):
        propias = _bolsa(bolsas.get(pid, []), modo, cuantas, anio, grupo, minimo)
        lados[nombre] = {
            "player_id": pid,
            "temporadas": tuple(sorted(t["season"] for t in propias)),
            "bolsa": propias,
            "celdas": {},
        }

    for columna in METRICAS[grupo]:
        metrica = metricas.get(columna)
        if metrica is None:  # una métrica desactivada en el Backoffice no tumba la comparación
            continue
        # En «mejores X» esto es solo el punto de partida: cada bolsa se mide contra la suma de los
        # umbrales de SUS años. Ver `_umbral_de_la_bolsa`.
        formula = _formula(metrica, modo, izquierda[1] or derecha[1], cajas, oficio)
        descendente = metrica.direction == Metric.Direction.HIGHER

        # La población del ranking: todos los dominicanos medidos con ESTA misma modalidad.
        poblacion: list[tuple[int, float]] = []
        if columna not in SIN_RANKING:
            for pid, suyas in bolsas.items():
                for candidata in _candidatas(suyas, modo, cuantas, grupo, minimo):
                    valor, _ = _valor(metrica, candidata, grupo)
                    if valor is None:
                        continue
                    suyo = _umbral_de_la_bolsa(metrica, modo, candidata, cajas, formula, oficio)
                    if not _cumple(metrica, _sumar(candidata, list(career_rate.COMPONENTS[grupo])), suyo):
                        continue
                    poblacion.append((pid, valor))

        for lado in lados.values():
            valor, aproximada = _valor(metrica, lado["bolsa"], grupo)
            rank = None
            # AL PROPIO TAMBIÉN SE LE EXIGE EL UMBRAL, y no es un detalle: la población ya está
            # filtrada, así que sin esto un .400 en 300 turnos saldría PRIMERO sobre gente que jugó
            # entero. El valor se sigue pintando —es suyo y es cierto— pero sin puesto: no compite en
            # la misma lista.
            suyo = _umbral_de_la_bolsa(metrica, modo, lado["bolsa"], cajas, formula, oficio)
            compite = _cumple(metrica, _sumar(lado["bolsa"], list(career_rate.COMPONENTS[grupo])), suyo)
            sin_puesto = columna in SIN_RANKING or (
                columna in SOLO_ABRIDORES and oficio != OFICIO_ABRIDOR
            )
            if valor is not None and compite and not sin_puesto:
                # Se busca el puesto de ESTE valor, no el del jugador: en modo temporada un pelotero
                # aporta muchas temporadas a la población y hay que rankear la que se está mirando.
                rank = 1 + sum(1 for _, otro in poblacion if (otro > valor if descendente else otro < valor))
            lado["celdas"][columna] = Celda(
                metrica=columna, valor=valor, rank=rank, de=len(poblacion), aproximada=aproximada
            )

    return {
        "grupo": grupo,
        "modo": modo,
        "cuantas": cuantas,
        # EL UMBRAL VIAJA CON EL RESULTADO para que la página y el PNG lo escriban al pie. Una tarjeta
        # que dice «2º histórico» sin decir entre quiénes es una cifra que no se puede verificar, y
        # estas imágenes circulan sueltas por WhatsApp, lejos de cualquier explicación.
        "minimo": minimo,
        "oficio": oficio,
        "izquierda": lados["izquierda"],
        "derecha": lados["derecha"],
    }


def _candidatas(
    temporadas: list[dict[str, Any]], modo: str, cuantas: int, grupo: str, minimo: int
) -> list[list[dict[str, Any]]]:
    """Las bolsas que ese jugador aporta a la POBLACIÓN del ranking.

    En carrera y en mejores X aporta UNA —su carrera, su mejor quinquenio—. En modo temporada aporta
    UNA POR CADA AÑO que jugó: el ranking histórico compara temporadas sueltas contra las 5.185 de la
    historia, no contra 870 carreras.
    """
    if modo == MODO_TEMPORADA:
        return [[t] for t in temporadas]
    if modo == MODO_CARRERA:
        return [temporadas]
    mejores = _mejores(temporadas, cuantas, grupo, minimo)
    return [mejores] if len(mejores) >= cuantas else []
