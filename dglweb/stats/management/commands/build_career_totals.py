"""Rebuild the materialized career totals (mlb_*_career) from the season tables."""

from typing import Any

from django.core.management.base import BaseCommand

from dglweb.stats.career_totals import build_career_totals
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Reconstruye los totales de carrera por jugador desde nuestras tablas de temporada."

    def handle(self, *args: Any, **options: Any) -> None:
        with record_run("build_career_totals", "all") as run:
            result = build_career_totals(note=self.stdout.write)
            run.add_rows(result["written"])
        self.stdout.write(self.style.SUCCESS(f"Totales de carrera: {result['written']} filas."))
