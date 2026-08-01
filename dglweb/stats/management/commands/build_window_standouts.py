"""Recalcular la ventana de los últimos catorce días.

    manage.py build_window_standouts
    manage.py build_window_standouts --hasta 2026-07-31   # para reproducir una foto vieja
    manage.py build_window_standouts --force              # aunque estemos fuera de temporada

Alimenta los widgets «Quemando la liga» y «Pasando trabajo». Reemplaza la tabla entera: una ventana
móvil no tiene historia que guardar, la de ayer ya no es cierta.

Corre cada hora. No es capricho: los juegos van terminando durante toda la tarde y la noche, y una
ventana que solo se recalculara de madrugada enseñaría por la noche una lista que ya no describe lo
que acaba de pasar. Son dos llamadas al proxy por corrida.
"""

from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.mlb.client import build_client
from dglweb.players import universe
from dglweb.stats import season_window, ventana
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Recalcula la ventana de catorce días que alimenta «Quemando la liga» y «Pasando trabajo»."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--hasta", type=date.fromisoformat, default=None, help="Último día (default: hoy).")
        parser.add_argument("--force", action="store_true", help="Corre aunque estemos fuera de temporada.")

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("build_window_standouts", note=self.stdout.write, force=options["force"]):
            return

        # La fecha la resuelve el proceso con SU zona horaria y no el shell del scheduler, por lo
        # mismo que en `build_daily_standouts`: con el contenedor en hora dominicana y el job
        # corriendo de madrugada, las dos no coinciden.
        hasta = options["hasta"] or timezone.localdate()

        with record_run("build_window_standouts", hasta.isoformat()) as run:
            filas = ventana.calcular(build_client(), universe.debuted(), hasta)
            guardadas = ventana.guardar(filas)
            run.add_rows(guardadas)
            # En la fila de ingesta y no solo en el log del contenedor: el log se rota y hay que
            # entrar al servidor a leerlo. Si un día los widgets salen vacíos, esta nota dice si fue
            # porque nadie calificó o porque el proxy no contestó.
            bateo = sum(1 for f in filas if f["grupo"] == "bateo")
            run.note(f"{bateo} bateadores y {len(filas) - bateo} lanzadores califican en la ventana.")

        if not guardadas:
            # No es un fallo: pasa en pretemporada y en el receso, cuando nadie llega al umbral.
            self.stdout.write("Nadie califica en la ventana; los widgets no se dibujan.")
            return

        self.stdout.write(self.style.SUCCESS(f"{guardadas} actuaciones guardadas, ventana hasta {hasta}."))
        foto = ventana.portada()
        if foto is None:
            self.stdout.write("  (menos de cinco: no alcanza para partir en quintos)")
            return
        for etiqueta, clave in (("🔥", "quemando"), ("🥶", "pasando")):
            for fila in foto[clave]["visibles"][:3]:
                self.stdout.write(f"  {etiqueta} {fila.nombre} ({fila.team}): {fila.linea}")
