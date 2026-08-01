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
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from dglweb.stats.models import SeasonDates

MLB = 1

# Margen después del cierre. Sin esto se perdería el último día de la temporada: los juegos del
# domingo se raspan el LUNES por la mañana, y si el domingo era `season_end_date` el job ya estaría
# fuera de la ventana. Dos días porque uno solo no deja margen para un job que se atrasa o falla y
# se reintenta al día siguiente — el costo de dos corridas de más es cero, el de perder el último
# juego de la Serie Mundial no.
GRACIA_FINAL = timedelta(days=2)

# La misma idea, pero PARA PUBLICAR, y por eso es un día y no dos (dueño, 2026-08-01).
#
# Los dos días de arriba son margen para un job que se atrasa o se reintenta — un coste de cero. Acá
# no hay reintentos: es cuánto tiempo después del último juego un widget puede seguir hablando de «la
# jornada» o de «los últimos 14 días» sin mentir.
#
# Uno, porque la Serie Mundial termina de noche y con el corte pegado a `season_end_date` los widgets
# se irían de madrugada, justo cuando alguien entra a ver cómo les fue a los nuestros en el último
# juego del año. Al segundo día ya no es noticia.
HOLGURA_AL_PUBLICAR = timedelta(days=1)


def se_publica(hoy: date | None = None, *, rampa: int = 0, sports_id: int = MLB) -> bool:
    """Si HOY un widget de temporada tiene derecho a dibujarse.

    Es la pregunta del que PINTA, no la del que calcula, y por eso no es `evaluate()`:

    * La holgura del final es distinta —un día contra dos— porque responden a cosas distintas. Ver
      `HOLGURA_AL_PUBLICAR`.
    * No deja fila en el log de ingesta. Un widget que no se dibuja porque estamos en enero no es un
      job que no corrió; anotarlo llenaría el log de ruido cada vez que alguien abre la portada.

    `rampa` son los días que el widget necesita ANTES de poder afirmar lo suyo. «Destacados ayer y
    hoy» no necesita ninguno: le basta una jornada, y mientras no haya filas no se dibuja solo. Las
    dos rachas piden catorce, porque prometen «los últimos 14 días» y el día 3 esa frase es falsa.

    Y ES LA MISMA PALANCA QUE LOS JOBS: exige una temporada marcada como en curso para `sports_id`.
    El administrador desmarca «Temporada en curso» en el Backoffice y los widgets desaparecen de la
    portada en la siguiente petición, sin tocar código ni esperar a ningún job.
    """
    from dglweb.stats.models import SeasonDates

    dia = hoy or timezone.localdate()
    temporada = SeasonDates.objects.filter(sports_id=sports_id, is_active=True).order_by("-season").first()
    if temporada is None:
        # Callar es mejor que afirmar sobre una ventana que nadie definió. Mismo criterio que
        # `evaluate()`, que para el caso de los jobs sí lo grita en el log.
        return False

    return (
        temporada.season_start_date + timedelta(days=rampa)
        <= dia
        <= temporada.season_end_date + HOLGURA_AL_PUBLICAR
    )


@dataclass(frozen=True)
class Ventana:
    """Si hoy hay que trabajar, y por qué. El motivo va al log: un salto mudo no se puede diagnosticar."""

    corre: bool
    motivo: str


def _apertura(temporada: "SeasonDates", *, postseason: bool) -> tuple[date, str]:
    """Desde cuándo hay trabajo, y cómo se llama esa fecha (el nombre va al motivo del salto).

    Los jobs de octubre no tienen nada que hacer en junio, así que arrancan en
    `post_season_start_date`. Pero esa fecha puede faltar —MLB la publica tarde, y en 1994 no hubo
    postemporada— y ahí la regla es **degradar hacia correr, nunca hacia callar**: primero el fin de
    la serie regular (la postemporada empieza justo después), y si tampoco está, la apertura de la
    temporada, que es el comportamiento de siempre.

    El sesgo es deliberado. Una llamada de más al proxy no cuesta nada; que a nadie se le ocurra
    llenar la fecha y la Serie Mundial no se raspe nunca, sí. Y el motivo del salto dice qué fecha se
    usó, así que si se cae al respaldo se ve en el log en vez de adivinarse.
    """
    if not postseason:
        return temporada.season_start_date, "la temporada"
    if temporada.post_season_start_date:
        return temporada.post_season_start_date, "la postemporada"
    if temporada.reg_season_end_date:
        return temporada.reg_season_end_date, "la postemporada (sin fecha propia: se usa el fin de la regular)"
    return temporada.season_start_date, "la postemporada (sin fecha propia ni fin de regular: se usa la apertura)"


def evaluate(*, sports_id: int = MLB, on: date | None = None, postseason: bool = False) -> Ventana:
    """La decisión, sin efectos. `on` es para los tests; en producción es hoy.

    `postseason=True` es para los tres jobs de octubre: misma temporada, ventana más corta.
    """
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

    apertura, que = _apertura(temporada, postseason=postseason)
    cierre = temporada.season_end_date + GRACIA_FINAL
    if hoy < apertura:
        return Ventana(corre=False, motivo=f"{temporada.season}: {que} empieza el {apertura}.")
    if hoy > cierre:
        return Ventana(corre=False, motivo=f"La temporada {temporada.season} terminó el {temporada.season_end_date}.")
    return Ventana(corre=True, motivo=f"{temporada.season}: {que} está en curso.")


def skip(
    command: str, *, note: object = None, sports_id: int = MLB, force: bool = False, postseason: bool = False
) -> bool:
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

    ventana = evaluate(sports_id=sports_id, postseason=postseason)
    if ventana.corre:
        return False

    record_skip(command, f"sports:{sports_id}", ventana.motivo)
    if callable(note):
        note(f"Sin correr — {ventana.motivo}")
    return True
