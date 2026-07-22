"""Refresh the current season's pitching — the job the scheduler runs daily.

    manage.py update_pitching

Reloads the current calendar year through the same idempotent path as the backfill.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from dglweb.stats.ingest import refresh_current
from dglweb.stats.loader import save_pitching_rows
from dglweb.stats.pitching_source import fetch_season


class Command(BaseCommand):
    help = "Refresca el pitcheo de la temporada actual (para correr en schedule)."

    def handle(self, *args: Any, **options: Any) -> None:
        season = timezone.now().year
        loaded = refresh_current("update_pitching", season, fetch_season, save_pitching_rows, warn=self.stderr.write)
        self.stdout.write(self.style.SUCCESS(f"{season}: {loaded} filas refrescadas."))
