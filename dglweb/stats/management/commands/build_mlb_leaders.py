"""Refrescar qué dominicanos están entre los diez primeros de las mayores.

    manage.py build_mlb_leaders                 # la temporada en curso
    manage.py build_mlb_leaders --temporada 2025
    manage.py build_mlb_leaders --force         # aunque estemos fuera de temporada

Pensado para correr cada hora. Son dos llamadas al proxy —bateo y pitcheo— de poco más de medio
segundo en total; la alternativa era consultarle a MLB en cada visita a la portada.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from dglweb.mlb.client import build_client
from dglweb.players import universe
from dglweb.stats import mlb_leaders, season_window
from dglweb.stats._download import fetch_team_codes
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Guarda los dominicanos que están en el top de las mayores en la temporada en curso."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--temporada", type=int, default=None, help="Por defecto, la que esté en curso.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada. Para reprocesar en invierno tras un arreglo.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("build_mlb_leaders", note=self.stdout.write, force=options["force"]):
            return

        temporada = options["temporada"] or _temporada_activa()
        if temporada is None:
            # Sin temporada marcada no hay foto que tomar, y adivinar el año del reloj podría
            # reemplazar una tabla buena por una vacía.
            self.stdout.write(self.style.WARNING("No hay temporada en curso marcada; no se hace nada."))
            return

        with record_run("build_mlb_leaders", str(temporada)) as run:
            client = build_client()
            puestos = mlb_leaders.traer(client, temporada, universe.debuted())
            guardadas = mlb_leaders.guardar(temporada, puestos, fetch_team_codes(client, temporada))
            run.add_rows(guardadas)
            run.note(f"{guardadas} puestos en {len({p.categoria for p in puestos})} categorías.")

        self.stdout.write(self.style.SUCCESS(f"{temporada}: {guardadas} dominicanos en el top {mlb_leaders.PUESTOS}."))


def _temporada_activa() -> int | None:
    from dglweb.stats.models import SeasonDates

    fila = SeasonDates.objects.filter(sports_id=season_window.MLB, is_active=True).order_by("-season").first()
    return fila.season if fila else None
