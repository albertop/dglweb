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
from datetime import date
from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import fetch_team_codes

_LIMITE = 8000

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


def portada(bateadores: int = 3, lanzadores: int = 2) -> dict[str, Any] | None:
    """Los destacados que muestra la portada, de la jornada más reciente que haya guardada.

    «La más reciente que haya» y no «ayer» a propósito: en el receso del Juego de Estrellas ayer no
    hubo pelota, y pedir literalmente ayer dejaría el widget vacío cuatro días. Se muestra la última
    jornada real, y la fecha va al lado para que nadie la confunda con la de hoy.

    Devuelve `None` cuando la tabla está vacía —sitio recién levantado, o el refresco nunca corrió—
    para que la plantilla pueda decidir no dibujar el panel en vez de dibujarlo hueco.
    """
    from dglweb.stats.models import DailyStandout

    ultima = DailyStandout.objects.order_by("-fecha").values_list("fecha", flat=True).first()
    if ultima is None:
        return None

    from dglweb.stats import videos

    del_dia = DailyStandout.objects.filter(fecha=ultima).select_related("player").order_by("-valor")
    filas = {
        "bateo": list(del_dia.filter(grupo=DailyStandout.Grupo.BATEO)[:bateadores]),
        "pitcheo": list(del_dia.filter(grupo=DailyStandout.Grupo.PITCHEO)[:lanzadores]),
    }

    # El video se resuelve acá y no en la plantilla: una sola consulta para los cinco, y así la
    # plantilla no tiene que saber que existe una tabla de videos.
    clips = videos.por_jugador(ultima, {fila.player_id for lista in filas.values() for fila in lista})
    return {
        "dia": ultima,
        **{
            oficio: [
                Destacado(
                    player=fila.player,
                    team=fila.team,
                    linea=fila.linea,
                    clips=clips.get(fila.player_id, ()),
                )
                for fila in lista
            ]
            for oficio, lista in filas.items()
        },
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
