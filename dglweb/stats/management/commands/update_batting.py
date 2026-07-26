"""Refresh the current season's batting — the job the scheduler runs daily.

    manage.py update_batting

Reloads the current calendar year through the same idempotent path as the backfill, so running
it every morning keeps the in-season numbers current and running it twice changes nothing. The
historical backfill stays a manual `import_batting --from --to`.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.stats import season_window
from dglweb.stats.batting_source import fetch_season
from dglweb.stats.ingest import refresh_current
from dglweb.stats.loader import save_batting_rows


class Command(BaseCommand):
    help = "Refresca el bateo de la temporada actual (para correr en schedule)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada. Para reprocesar en invierno tras un arreglo.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("update_batting", note=self.stdout.write, force=options["force"]):
            return

        season = timezone.now().year
        loaded = refresh_current("update_batting", season, fetch_season, save_batting_rows, warn=self.stderr.write)
        self.stdout.write(self.style.SUCCESS(f"{season}: {loaded} filas refrescadas."))
