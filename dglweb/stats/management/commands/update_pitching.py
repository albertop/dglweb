"""Refresh the current season's pitching — the job the scheduler runs daily.

    manage.py update_pitching

Reloads the current calendar year through the same idempotent path as the backfill.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.stats import season_window
from dglweb.stats.ingest import refresh_current
from dglweb.stats.loader import save_pitching_rows
from dglweb.stats.pitching_source import fetch_season


class Command(BaseCommand):
    help = "Refresca el pitcheo de la temporada actual (para correr en schedule)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada. Para reprocesar en invierno tras un arreglo.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("update_pitching", note=self.stdout.write, force=options["force"]):
            return

        season = timezone.now().year
        loaded = refresh_current("update_pitching", season, fetch_season, save_pitching_rows, warn=self.stderr.write)
        self.stdout.write(self.style.SUCCESS(f"{season}: {loaded} filas refrescadas."))
