"""La actuación del día: quién de los nuestros hizo algo digno de contarse ayer.

Alimenta el widget «Destacados de la jornada» de la portada. Dos listas separadas —bateadores y
lanzadores— porque comparar un 3-4 con siete entradas de una carrera exige una escala común que no
existe, y forzarla produciría un orden que nadie podría defender.

CÓMO SE SACA EL DATO
--------------------
`stats=byDateRange` con la misma fecha de inicio y fin da las estadísticas de ESE día para toda la
liga en una sola llamada por oficio. Dos llamadas, menos de un segundo, y el recorte dominicano es
una intersección en memoria — el mismo patrón que el refresco diario. Un día sin juegos devuelve
cero splits sin error, así que no hay que preguntarle al calendario si hubo pelota.

CÓMO SE ORDENA
--------------
**Bateo: pesos lineales.** Cada evento vale lo que vale en carreras, según la matriz 2022-2025 del
dueño (columna `average`). Sumar la jornada da el valor en carreras que el pelotero produjo — la
misma lógica que hay detrás del wOBA, aplicada a un juego. Se prefiere a ordenar por remolcadas o
anotadas porque esas dependen de quién estaba en base: premian la oportunidad, no la actuación.

**Pitcheo: Game Score v2 de Tango.** `40 + 2*outs + K - 2*H - 3*R - 6*HR`. Resuelve solo el problema
de que un relevista de un inning no desplace a un abridor de siete, porque los outs pesan.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.utils.formats import date_format

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats import scoreboard
from dglweb.stats._download import fetch_team_codes

_LIMITE = 8000

# EL PISO PARA LLAMARSE DESTACADO. Decisión del dueño (2026-07-27), medida sobre 14 jornadas reales.
#
# Antes no había piso: se publicaba el top-3 y el top-2 pasara lo que pasara. Medido, eso ya
# coronaba actuaciones que no lo son — el tercer bateador publicado bajaba hasta **0,25** en las
# jornadas flojas (un 1-4 con sencillo) y el segundo lanzador hasta **46**, que en la escala de Tango
# está por DEBAJO del promedio. Llamarle destacado a eso contradice la propia métrica.
#
# Los dos números son estándares, no inventos:
#
#   - **1,0 en bateo** es una carrera producida por encima de lo que habría dado un bateador
#     promedio en esas mismas apariciones. La unidad sale de la propia matriz de pesos lineales.
#     Deja fuera el 1-4 con sencillo y deja dentro el 2-4 con jonrón.
#   - **50 en pitcheo** es, por definición, la salida promedio en Game Score v2.
#
# Con estos pisos se llenan 1,9 de los 3 huecos de bateo y 1,0 de los 2 de pitcheo al día. Que a
# veces queden vacíos es la respuesta correcta: hubo jornadas en las que nadie destacó.
#
# El piso se aplica al MOSTRAR, no al guardar. La tabla es el registro de la jornada y se queda con
# todos los que jugaron — cambiar el umbral no puede exigir volver a pedirle nada al proxy.
PISO_BATEO = 1.0
PISO_PITCHEO = 50.0

# LA ESCALA COMÚN, para poder ordenar las dos listas juntas (decisión del dueño, 2026-07-27).
#
# Durante mucho tiempo acá NO se comparaban: dos listas separadas, porque un 3-4 y siete entradas de
# una carrera no están en la misma unidad. El dueño decidió mezclarlas, y para eso hay que traducir.
#
# La traducción NO necesita ninguna constante inventada: sale de la propia fórmula de Game Score v2.
#
#   - El término `-3R` dice que **una carrera cuesta 3 puntos**.
#   - **50 es, por definición, la salida promedio.**
#
# Luego `(GS - 50) / 3` son carreras por encima de una salida promedio — exactamente la unidad en la
# que ya está el bateo, que son carreras producidas por encima del bateador promedio.
#
# Lo que sale de ahí es defendible aunque sorprenda: en las jornadas con buen pitcheo, los lanzadores
# encabezan. Medido, una salida de 5.2 entradas sin carreras vale +6,7 y un juego de 2 jonrones
# +2,2. En valor de carreras eso es correcto: evitar carreras rinde más que producirlas, y esa es
# justamente la afirmación que hace la métrica.
GS_PROMEDIO = 50.0
PUNTOS_POR_CARRERA = 3.0


def en_carreras(grupo: str, valor: float) -> float:
    """El valor de una actuación en carreras sobre el promedio, venga del oficio que venga.

    Es lo único que permite ordenar las dos listas juntas sin inventarse una equivalencia. El bateo
    ya viene en esta unidad; el pitcheo se traduce desde Game Score — ver arriba.
    """
    return valor if grupo == "bateo" else (valor - GS_PROMEDIO) / PUNTOS_POR_CARRERA


# Cómo se puntúa y cómo se describe una jornada. Van tipados en vez de `Any` para que agregar un
# oficio nuevo falle en mypy si la firma no encaja, en vez de a mitad de una corrida.
Calculo = Callable[[dict[str, Any]], float]
Descripcion = Callable[[dict[str, Any]], str]

# Valor en carreras de cada evento — matriz de pesos lineales 2022-2025, columna `average`, provista
# por el dueño. Se copian tal cual, con todos sus decimales: redondearlos acá sería introducir un
# criterio propio en un número que ya viene decidido.
PESOS: dict[str, float] = {
    "out": -0.2706628521511171,  # out en juego (incluye elevados de sacrificio y toques)
    "k": -0.27279957184505116,
    "bb": 0.3260503399594458,
    "ibb": 0.2121959272993923,  # el intencional vale menos: no lo ganó el bateador
    "hbp": 0.3534316578542027,
    "1b": 0.46710077393962235,
    "2b": 0.766364884886978,
    "3b": 1.0354271039388732,
    "hr": 1.3890765661634175,
    "sb": 0.1730862402850167,
    "cs": -0.42172462878318934,
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


def game_score(stat: dict[str, Any]) -> float:
    """Game Score v2 de Tango: `40 + 2*outs + K - 2*H - 3*R - 6*HR`.

    Carreras totales y no limpias, como manda la fórmula: al lector le importa cuántas cruzaron el
    plato, y repartir la culpa con la defensa es otra discusión.
    """
    outs = _numero(stat, "outsPitched") or _numero(stat, "Outs")
    return (
        40 + 2 * outs + _numero(stat, "K") - 2 * _numero(stat, "H") - 3 * _numero(stat, "R") - 6 * _numero(stat, "HR")
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
    """«7.0 IP, 9 K, 0 ER (W)» — las entradas primero, que es lo que sitúa la actuación."""
    partes = [f"{stat.get('IP', '0.0')} IP", f"{int(_numero(stat, 'K'))} K", f"{int(_numero(stat, 'ER'))} ER"]
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
) -> list[Actuacion]:
    salida = []
    for split in splits(client, grupo, dia):
        jugador = split.get("player") or {}
        if jugador.get("id") not in universo:
            continue
        stat = split.get("stat") or {}
        salida.append(
            Actuacion(
                player_id=jugador["id"],
                nombre=jugador.get("fullName") or "",
                equipo=codigos.get((split.get("team") or {}).get("id") or 0, ""),
                valor=puntuar(stat),
                linea=describir(stat),
            )
        )
    # Por valor, y el id desempata para que dos actuaciones idénticas no bailen entre corridas.
    return sorted(salida, key=lambda a: (-a.valor, a.player_id))


def destacados(client: MlbProxyClient, dia: date, universo: set[int]) -> dict[str, list[Actuacion]]:
    """Las dos listas del día, ya ordenadas. El recorte a los primeros N lo decide quien muestre."""
    # El split solo trae el id y el nombre largo del equipo («San Diego Padres»); el código de tres
    # letras sale de `/teams`, que es la misma traducción que ya hace el descargador de temporadas.
    codigos = fetch_team_codes(client, dia.year)
    return {
        "bateo": _actuaciones(client, "hitting", dia, universo, codigos, valor_de_bateo, linea_de_bateo),
        "pitcheo": _actuaciones(client, "pitching", dia, universo, codigos, game_score, linea_de_pitcheo),
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
    # `grupo` y `valor` NO se muestran: están para poder ordenar la lista mezclada en una misma
    # unidad (`en_carreras`). Sin ellos habría que llevar dos listas paralelas —una para pintar y
    # otra para ordenar— y basta con que se desincronicen una vez para publicar un orden falso.
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


# Cuántos destacados caben en el panel sin desplegar. NO es un número de diseño elegido a ojo: el
# marco es una rejilla de 2 columnas por 3 filas con `overflow: hidden`, medida en el navegador, así
# que seis es exactamente su capacidad. Poner otro número dejaría un hueco o cortaría una caja.
#
# Las pestañas por oficio que había acá se retiraron (decisión del dueño, 2026-07-27). Nunca llegaron
# a dibujarse: se activaban pasados los 6 destacados y la portada pedía como mucho 5, así que la rama
# estuvo muerta desde que se escribió. Un botón de «ver más» hace el mismo trabajo sin esconder la
# mitad del contenido detrás de un clic.
VISIBLES = 6

# El tope de lo que se llega a mandar al navegador. Medido sobre 14 jornadas con el piso puesto: la
# mejor dio 11 destacados. Doce deja margen sin que una jornada excepcional arme una lista infinita.
MAXIMO = 12


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
        key=lambda d: (d.fecha.toordinal() if d.fecha else 0, en_carreras(d.grupo, d.valor)),
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
