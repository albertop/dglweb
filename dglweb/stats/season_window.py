"""¿Hay temporada hoy? La puerta que decide si un job del scheduler corre o se va a dormir.

El scheduler despierta todas las mañanas los doce meses del año, pero la pelota se juega en siete.
Fuera de temporada cada job era un viaje al proxy de MLB para traer lo mismo que ayer, y una
reconstrucción de 400.000 liderazgos que daba idénticos a los del día anterior.

La ventana la manda el dato, no el código: sale de `seasons_dates`, la temporada marcada como en
curso (`is_active`). Eso es a propósito — cuando MLB mueve una fecha se corrige en el Backoffice y
los jobs se enteran solos, sin tocar el compose ni desplegar.

`sports_id` es parámetro y no constante porque la fuente distingue ligas. Hoy todos los jobs son de
MLB (1); si mañana entra otra, sus jobs consultan su propia ventana sin tocar esto.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

MLB = 1

# Margen después del cierre. Sin esto se perdería el último día de la temporada: los juegos del
# domingo se raspan el LUNES por la mañana, y si el domingo era `season_end_date` el job ya estaría
# fuera de la ventana. Dos días porque uno solo no deja margen para un job que se atrasa o falla y
# se reintenta al día siguiente — el costo de dos corridas de más es cero, el de perder el último
# juego de la Serie Mundial no.
GRACIA_FINAL = timedelta(days=2)


@dataclass(frozen=True)
class Ventana:
    """Si hoy hay que trabajar, y por qué. El motivo va al log: un salto mudo no se puede diagnosticar."""

    corre: bool
    motivo: str


def evaluate(*, sports_id: int = MLB, on: date | None = None) -> Ventana:
    """La decisión, sin efectos. `on` es para los tests; en producción es hoy."""
    from dglweb.stats.models import SeasonDates

    hoy = on or timezone.localdate()
    temporada = SeasonDates.objects.filter(sports_id=sports_id, is_active=True).order_by("-season").first()

    if temporada is None:
        # El fallo que más caro sale, y por eso tiene su propio mensaje: si nadie marcó la temporada
        # nueva, el sitio deja de actualizarse en silencio y se descubre cuando alguien se queja.
        return Ventana(
            corre=False,
            motivo=(
                f"No hay ninguna temporada marcada como en curso (deporte {sports_id}). "
                "Marcala en el Backoffice: Calendario de temporadas."
            ),
        )

    cierre = temporada.season_end_date + GRACIA_FINAL
    if hoy < temporada.season_start_date:
        return Ventana(corre=False, motivo=f"La temporada {temporada.season} empieza el {temporada.season_start_date}.")
    if hoy > cierre:
        return Ventana(corre=False, motivo=f"La temporada {temporada.season} terminó el {temporada.season_end_date}.")
    return Ventana(corre=True, motivo=f"Temporada {temporada.season} en curso.")


def skip(command: str, *, note: object = None, sports_id: int = MLB, force: bool = False) -> bool:
    """`True` si el job NO debe correr hoy. Deja el salto anotado en el log de ingesta.

    Se registra a propósito, en vez de salir callado. El log de ingesta es la pantalla donde se mira
    "¿por qué no se actualizó esto?", y un job que no deja rastro obliga a contestar esa pregunta
    entrando al servidor a leer logs de contenedor. Con la fila, la respuesta está a la vista y dice
    si fue porque estamos fuera de temporada o porque nadie marcó la temporada nueva.

    Las filas de salto las poda `prune_ingest_log` con la misma retención que las demás.
    """
    from dglweb.stats.runlog import record_skip

    # `--force` existe para el día que hay que reprocesar algo en invierno: arreglar un bug de
    # cálculo en diciembre y tener que encender una temporada terminada para poder correr el
    # rebuild sería peor que un flag.
    if force:
        return False

    ventana = evaluate(sports_id=sports_id)
    if ventana.corre:
        return False

    record_skip(command, f"sports:{sports_id}", ventana.motivo)
    if callable(note):
        note(f"Sin correr — {ventana.motivo}")
    return True
