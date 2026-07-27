"""Trae los movimientos de roster de los dominicanos.

    manage.py update_roster_moves            # lo que corre el scheduler, cada hora
    manage.py update_roster_moves --dias 30  # para rellenar hacia atrás

Una llamada al proxy por corrida, no una por equipo. La lógica vive en `stats/roster_moves.py`; acá
solo están los argumentos, la bitácora y la salida por consola.
"""

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats import roster_moves
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Trae los movimientos de roster de los dominicanos desde el proxy de MLB."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dias",
            type=int,
            default=roster_moves.DIAS,
            help="Cuántos días hacia atrás pedir. Por defecto dos, que es lo que necesita la corrida horaria.",
        )
        # `--force` no hace nada acá y existe a propósito: el orquestador llama a TODOS los pasos con
        # esa bandera porque la ventana de temporada ya la evaluó él. Sin aceptarla, el paso reventaría
        # dentro del refresco diario. Ver `stats/pipeline.py`.
        parser.add_argument("--force", action="store_true", help="Aceptada por compatibilidad con el pipeline.")

    def handle(self, *args: Any, **options: Any) -> None:
        hoy = timezone.localdate()
        dias = max(1, options["dias"])
        alcance = f"{hoy - timedelta(days=dias - 1)}..{hoy}"

        with record_run("update_roster_moves", alcance) as run:
            cliente = MlbProxyClient(settings.MLB_PROXY_URL, settings.MLB_PROXY_API_KEY)
            movimientos = roster_moves.traer(cliente, hoy, dias)
            run.add_rows(roster_moves.guardar(movimientos))

            # Cuántas quedaron sin traducir es el número que hay que vigilar: si MLB cambia una
            # plantilla, esto sube y el cintillo se queda callado sin que nadie se entere. Va a la
            # bitácora para que se vea en el Backoffice.
            sin_traducir = [m for m in movimientos if not m.texto]
            if sin_traducir:
                run.note(f"{len(sin_traducir)} sin traducir — falta un patrón en roster_moves.PATRONES")
                for movimiento in sin_traducir[:5]:
                    run.note(f"  {movimiento.descripcion[:120]}")

        self.stdout.write(
            self.style.SUCCESS(f"{len(movimientos)} movimientos ({len(movimientos) - len(sin_traducir)} en español)")
        )
