"""Rebuild the materialized career totals (mlb_*_career) from the season tables."""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from dglweb.stats import season_window
from dglweb.stats.career_totals import build_career_totals
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Reconstruye los totales de carrera por jugador desde nuestras tablas de temporada."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada. Para reprocesar en invierno tras un arreglo.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("build_career_totals", note=self.stdout.write, force=options["force"]):
            return

        with record_run("build_career_totals", "all") as run:
            result = build_career_totals(note=self.stdout.write)
            run.add_rows(result["written"])
        self.stdout.write(self.style.SUCCESS(f"Totales de carrera: {result['written']} filas."))
