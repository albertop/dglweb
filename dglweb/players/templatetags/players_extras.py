"""Filtros de las pantallas de jugadores."""

from django import template

from dglweb.players import positions

register = template.Library()


@register.filter
def posicion(valor: str | None) -> str:
    """`RP` -> `P-REL`, `SP` -> `P-ABR`. El resto sale tal cual.

    Filtro y no algo que arme la vista porque el índice pinta cientos de jugadores en un bucle y la
    plantilla es quien decide cómo se ven. La tabla vive en `players/positions.py`, junto al código
    que decide la posición — así no hay dos sitios que puedan discrepar.
    """
    return positions.como_se_lee(valor)
