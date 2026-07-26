"""Buscar peloteros por nombre, tolerando acentos.

**El requisito de fondo no es la velocidad: son los acentos.** De los 984 nombres del maestro, 488
llevan tilde o eñe. Quien escribe «nunez» tiene que encontrar a Núñez y quien escribe «beltre» a
Beltré — si no, la mitad del maestro es inalcanzable para cualquiera que no sepa dónde va la tilde.

Por qué esto es una consulta y no un índice en memoria: son 984 filas. Un trie daría respuestas en
microsegundos en vez de milisegundos, y a cambio habría que construirlo al arrancar, mantenerlo
sincronizado cuando el dueño edita un jugador en el Backoffice, y decidir qué pasa con los procesos
que no comparten memoria. Es una estructura para un problema de escala que no tenemos: la búsqueda ya
va contra un índice de Postgres y el cuello de botella es la red, no el algoritmo.

Del lado de Python tampoco hace falta módulo alguno: `unaccent` de Postgres normaliza la columna y
`unicodedata` de la biblioteca estándar normaliza lo que escribe el usuario. Nada de terceros.
"""

import unicodedata
from dataclasses import dataclass

from django.db.models import Case, Func, IntegerField, QuerySet, Value, When
from django.db.models.functions import Lower

from dglweb.players.models import Player

# Dos caracteres: con uno solo, «a» devuelve medio maestro y la lista deja de ser una sugerencia.
MIN_CARACTERES = 2
LIMITE_SUGERENCIAS = 10


@dataclass(frozen=True)
class Sugerencia:
    """Lo que ve quien busca. El rango de carrera no es decorativo — ver `_span`."""

    player_id: int
    name: str
    slug: str
    pos: str
    span: str

    def to_dict(self) -> dict[str, str | int]:
        return {"id": self.player_id, "name": self.name, "slug": self.slug, "pos": self.pos, "span": self.span}


def normalize(texto: str) -> str:
    """Lo que escribe el usuario, en la misma forma que la columna: sin acentos y en minúsculas.

    NFKD separa la letra de su tilde y el filtro se queda con lo que no es marca diacrítica, así que
    «Núñez» y «Nunez» colapsan a lo mismo. La eñe entra en el mismo saco a propósito: quien busca
    «Pena» espera encontrar a Peña, y exigirle la eñe sería exigirle saber cómo se escribe.
    """
    descompuesto = unicodedata.normalize("NFKD", texto.strip().casefold())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


class _Unaccent(Func):
    """`unaccent(...)` de Postgres. La extensión la instala la migración `0005`."""

    function = "unaccent"


def buscar(consulta: str, limite: int = LIMITE_SUGERENCIAS) -> list[Sugerencia]:
    """Los jugadores cuyo nombre contiene `consulta`, ordenados por qué tan bien encaja.

    El orden es el que espera quien escribe, y sale de una sola consulta:

    1. El nombre **empieza** con lo escrito — «sot» pone primero a Soto.
    2. Una **palabra** del nombre empieza con lo escrito — «beltre» encuentra a Adrián Beltré.
    3. El nombre lo **contiene** en cualquier parte, que es la red de seguridad.

    Con menos de `MIN_CARACTERES` devuelve vacío en vez de medio maestro.
    """
    aguja = normalize(consulta)
    if len(aguja) < MIN_CARACTERES:
        return []

    filas = _rankeado(aguja)[:limite]
    ids = [fila.player_id for fila in filas]
    tramos = _span(ids)
    return [
        Sugerencia(
            player_id=fila.player_id,
            name=fila.full_name,
            slug=fila.slug,
            pos=fila.pos or "",
            span=tramos.get(fila.player_id, ""),
        )
        for fila in filas
    ]


def _rankeado(aguja: str) -> QuerySet[Player]:
    """`Player.objects` y no `todos`: un jugador dado de baja no debe ser encontrable."""
    return (
        Player.objects.annotate(plano=_Unaccent(Lower("full_name")))
        .filter(plano__contains=aguja)
        .annotate(
            encaje=Case(
                When(plano__startswith=aguja, then=Value(0)),
                # El espacio delante es lo que distingue "empieza una palabra" de "está en el medio":
                # buscando «ram», Amed Rosario no debería ganarle a José Ramírez.
                When(plano__contains=f" {aguja}", then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        )
        .order_by("encaje", "full_name")
    )


def _span(player_ids: list[int]) -> dict[int, str]:
    """`2001-2012` por jugador. Desempata a los homónimos, que acá son un caso real.

    El maestro tiene «Abraham Núñez» y «Abraham O. Núñez»: sin el rango, la lista muestra dos
    entradas casi idénticas y quien busca no puede elegir. Se calcula sobre los ids ya recortados al
    límite, así que son tres agregados sobre un puñado de filas y no uno por jugador.
    """
    from django.db.models import Max, Min

    from dglweb.stats.models import Batting, Fielding, Pitching

    if not player_ids:
        return {}
    extremos: dict[int, list[int]] = {}
    for modelo in (Batting, Pitching, Fielding):
        filas = (
            modelo.objects.filter(player_id__in=player_ids)
            .values("player_id")
            .annotate(desde=Min("season"), hasta=Max("season"))
        )
        for fila in filas:
            tramo = extremos.setdefault(fila["player_id"], [fila["desde"], fila["hasta"]])
            tramo[0] = min(tramo[0], fila["desde"])
            tramo[1] = max(tramo[1], fila["hasta"])
    return {pid: (f"{d}-{h}" if d != h else str(d)) for pid, (d, h) in extremos.items()}
