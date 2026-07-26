"""Sacar a los jugadores dados de baja de la data que se CALCULA.

Existe porque el manager por defecto de `Player` no alcanza. `build_leaders` y `build_career_totals`
no consultan jugadores: leen `Batting`/`Pitching`/`Fielding` y agrupan por `player_id` crudo, así que
el filtro del manager nunca entra en juego y hay que excluirlos acá.

Y no basta con filtrarlos al mostrar. Los liderazgos están materializados con el puesto ya escrito:
esconder una fila al leer dejaría la lista numerada 1, 2, 4 y —peor— al que venía tercero en un
puesto que no le corresponde. La exclusión tiene que pasar cuando se construyen.

Regla para lo que venga: **si una consulta parte de `Player`, el manager ya te cubre; si parte de una
tabla de stats, tenés que pasarla por acá.**
"""

from django.db.models import QuerySet


def only_visible[QS: QuerySet](queryset: QS) -> QS:  # type: ignore[type-arg]
    """Quita las filas de jugadores ocultos. Para querysets que tengan FK `player`."""
    return queryset.exclude(player__hidden=True)
