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

from django.db import models
from django.db.models import Case, Func, IntegerField, QuerySet, Value, When
from django.db.models.functions import Lower

from dglweb.players.models import Player

# Dos caracteres: con uno solo, «a» devuelve medio maestro y la lista deja de ser una sugerencia.
MIN_CARACTERES = 2
# El techo sale del propio modelo y no de un número inventado: `full_name` mide 50, así que una
# consulta más larga NO PUEDE estar contenida en ningún nombre. Devolverla vacía sin ir a la base no
# es una heurística de rendimiento — es el resultado correcto, calculado antes de gastar una consulta.
# De paso cierra SEC-04 en su parte barata: el endpoint es público y así nadie le manda un megabyte.
MAX_CARACTERES = Player._meta.get_field("full_name").max_length or 50
# Veinte y no diez. Con diez, buscar «carlos» —que tiene 22 coincidencias— dejaba fuera al segundo
# Carlos Martínez, que cae en el puesto 16: el usuario concluía que no estaba en la base. La lista
# tiene scroll, así que veinte no la alargan de más, y lo que de verdad arregla el problema es que
# `Resultados` diga cuántos quedaron fuera.
LIMITE_SUGERENCIAS = 20


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


@dataclass(frozen=True)
class Resultados:
    """Lo que encaja y CUÁNTOS encajan, que no es lo mismo.

    El total va aparte porque recortar en silencio es el peor fallo posible de un buscador: quien
    busca «jose» ve diez nombres de sesenta y ocho y concluye que los otros no existen. Con el total,
    la interfaz puede decir «y 58 más» y ofrecer la lista entera.
    """

    items: list[Sugerencia]
    total: int

    @property
    def ocultos(self) -> int:
        return max(0, self.total - len(self.items))


def buscar(
    consulta: str, limite: int | None = LIMITE_SUGERENCIAS, *, desde_1956: bool = False, oficio: str = ""
) -> Resultados:
    """Los jugadores cuyo nombre contiene `consulta`, ordenados por qué tan bien encaja.

    El orden sale de una sola consulta, y son dos escalones:

    1. Una **palabra** del nombre empieza con lo escrito — da igual si es el nombre de pila o el
       apellido, porque para quien busca las dos cosas encajan igual de bien.
    2. Lo escrito aparece **a mitad de palabra**, que es la red de seguridad y va al final.

    Dentro de cada escalón manda la **fecha de debut**: primero el más veterano.

    Con menos de `MIN_CARACTERES` devuelve vacío en vez de medio maestro, y con más de
    `MAX_CARACTERES` también: no cabe en ningún nombre. `limite=None` trae todo:
    lo usa la página de resultados, que es donde el desplegable manda a ver lo que no le cupo.
    """
    aguja = normalize(consulta)
    if not MIN_CARACTERES <= len(aguja) <= MAX_CARACTERES:
        return Resultados(items=[], total=0)

    encontrados = _rankeado(aguja)
    if desde_1956:
        # EL BUSCADOR DEL COMPARADOR NO OFRECE A LAS LIGAS NEGRAS (dueño, 2026-08-13). Sus números no
        # son comparables con los de Grandes Ligas y el WAR ni siquiera existe para ellos, así que
        # elegirlos solo lleva a un error. El corte es el mismo que usa `comparador.universo`.
        #
        # ES UNA OPCIÓN Y NO EL COMPORTAMIENTO NORMAL: la caja del encabezado, que está en todas las
        # páginas, TIENE que seguir encontrando a Tetelo Vargas y a Horacio Martínez. Son parte del
        # sitio; lo que no son es comparables.
        from dglweb.stats.leaders import FIRST_SEASON

        encontrados = encontrados.filter(debut_date__year__gte=FIRST_SEASON)

    # EL OFICIO LO PIDE EL PASO 1 DEL ASISTENTE, y es lo que hace que el buscador del paso 2 sea
    # «inteligente»: quien dijo «bateadores» no puede tropezarse con Pedro Martínez. `Player.pos` ya
    # distingue abridor de relevista (ver `players/positions.py`), así que no hace falta nada nuevo.
    #
    # Un oficio desconocido NO filtra, en vez de vaciar la lista: un parámetro con una errata dejaría
    # el buscador mudo sin decir por qué.
    if oficio == "batting":
        encontrados = encontrados.exclude(pos__in=["P", "SP", "RP"])
    elif oficio in ("SP", "RP"):
        encontrados = encontrados.filter(pos=oficio)
    # `count()` sobre el queryset ya filtrado: una consulta más, sin traer las filas. Es lo que
    # permite decir cuántos quedaron fuera en vez de recortar y callar.
    total = encontrados.count()
    filas = list(encontrados if limite is None else encontrados[:limite])
    tramos = _span([fila.player_id for fila in filas])
    return Resultados(
        items=[
            Sugerencia(
                player_id=fila.player_id,
                name=fila.full_name,
                slug=fila.slug,
                pos=fila.pos or "",
                span=tramos.get(fila.player_id, ""),
            )
            for fila in filas
        ],
        total=total,
    )


def _rankeado(aguja: str) -> QuerySet[Player]:
    """`Player.objects` y no `todos`: un jugador dado de baja no debe ser encontrable."""
    return (
        Player.objects.annotate(plano=_Unaccent(Lower("full_name")))
        .filter(plano__contains=aguja)
        .annotate(
            encaje=Case(
                # DOS niveles, no tres. Empezar el nombre y empezar un apellido cuentan igual: buscando
                # «so», separarlos ponía a Sócrates Brito (2015) por delante de Elías Sosa (1972) solo
                # por ser su nombre de pila, y para quien busca los dos encajan exactamente igual de
                # bien. Juntos, decide el debut, que es lo que el dueño quiere ver.
                When(plano__startswith=aguja, then=Value(0)),
                When(plano__contains=f" {aguja}", then=Value(0)),
                # El segundo nivel es el que sí hay que separar: lo escondido a mitad de palabra.
                # «AlfonSO Vargas» coincide con «so» sin que nadie lo estuviera buscando por eso, y
                # sin este escalón le ganaría a un Soto de verdad con solo haber debutado antes.
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        # Primero el encaje, y dentro de cada nivel por fecha de debut, del más veterano al más nuevo.
        #
        # El debut y no el apellido, por lo mismo que se descartó en la lista de activos: `lastname_1`
        # es el paterno, y en 44 de los 984 el pelotero se conoce por el materno — Felipe Alou está
        # bajo «Rojas» y Sammy Sosa bajo «Peralta».
        #
        # `player_id` cierra el orden para que los que comparten fecha no bailen entre búsquedas.
        .order_by("encaje", models.F("debut_date").asc(nulls_last=True), "player_id")
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
