"""Guardar la actuación de los dominicanos en la jornada de ayer.

    manage.py build_daily_standouts                  # ayer
    manage.py build_daily_standouts --fecha 2026-07-25
    manage.py build_daily_standouts --force          # aunque estemos fuera de temporada

Alimenta el widget «Destacados de la jornada» de la portada. Guarda a TODOS los que jugaron —no solo
los primeros— y de paso borra las jornadas que ya no son de la temporada en curso.

La poda vive acá y no en un job aparte a propósito: quien escribe la tabla es quien mejor sabe qué
sobra en ella, y un janitor separado es una pieza más que puede dejar de correr sin que nadie note
que dejó de correr.
"""

from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.mlb.client import build_client
from dglweb.players import universe
from dglweb.stats import daily, season_window
from dglweb.stats.runlog import record_run, record_skip


class Command(BaseCommand):
    help = "Guarda la actuación de los dominicanos en una jornada y poda las temporadas viejas."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--fecha", type=date.fromisoformat, default=None, help="Jornada (default: ayer).")
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Corre aunque estemos fuera de temporada, y guarda una jornada que no ha terminado. "
                "Para reprocesar en invierno tras un arreglo."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("build_daily_standouts", note=self.stdout.write, force=options["force"]):
            return

        # Ayer y no hoy: los juegos terminan de noche, y el refresco corre a las 6 de la mañana. Pedir
        # «hoy» a esa hora devolvería una jornada que todavía no empezó.
        dia = options["fecha"] or timezone.localdate() - timedelta(days=1)

        if dia >= timezone.localdate() and not options["force"]:
            # Una jornada en curso no se guarda. El widget presenta lo guardado como la actuación del
            # día, y con juegos a medias eso es sencillamente falso: quien va de 0-2 a las nueve de la
            # noche puede terminar de 2-4. Guardarla haría que la portada anunciara una cifra que aún
            # va a cambiar, y nada en la pantalla diría que está a medias.
            #
            # Se anota como salto, no como fallo: el comando hizo lo correcto al no correr, y una fila
            # roja en el Backoffice mandaría a buscar una avería que no existe.
            record_skip("build_daily_standouts", dia.isoformat(), "la jornada todavía no ha terminado")
            self.stdout.write(self.style.WARNING(f"{dia} no ha terminado; use --force para guardarla igual."))
            return

        with record_run("build_daily_standouts", dia.isoformat()) as run:
            listas = daily.destacados(build_client(), dia, universe.debuted())
            guardadas = daily.guardar(dia, listas)
            run.add_rows(guardadas)
            run.note(f"{len(listas['bateo'])} bateadores, {len(listas['pitcheo'])} lanzadores.")

            podadas = daily.podar(_temporada_activa())
            if podadas:
                run.note(f"Podadas {podadas} filas de temporadas anteriores.")

        if not guardadas:
            # No es un fallo: pasa en el receso del Juego de Estrellas y en cualquier día libre.
            self.stdout.write(f"{dia}: no hubo juegos (o ningún dominicano vio acción).")
            return
        self.stdout.write(self.style.SUCCESS(f"{dia}: {guardadas} actuaciones guardadas."))
        for actuacion in listas["bateo"][:3]:
            self.stdout.write(f"  🏏 {actuacion.nombre} ({actuacion.equipo}): {actuacion.linea}")
        for actuacion in listas["pitcheo"][:2]:
            self.stdout.write(f"  ⚾ {actuacion.nombre} ({actuacion.equipo}): {actuacion.linea}")


def _temporada_activa() -> int | None:
    from dglweb.stats.models import SeasonDates

    fila = SeasonDates.objects.filter(sports_id=season_window.MLB, is_active=True).order_by("-season").first()
    return fila.season if fila else None
