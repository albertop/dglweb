"""Refresh the current season's postseason fielding — the job the scheduler runs daily.

    manage.py update_fielding_post

Idempotent; outside October/November the rounds simply return nothing.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from dglweb.stats.fielding_post_source import fetch_season
from dglweb.stats.ingest import refresh_current
from dglweb.stats.loader import save_fielding_post_rows


class Command(BaseCommand):
    help = "Refresca la postemporada de fildeo de la temporada actual (para correr en schedule)."

    def handle(self, *args: Any, **options: Any) -> None:
        season = timezone.now().year
        loaded = refresh_current(
            "update_fielding_post", season, fetch_season, save_fielding_post_rows, warn=self.stderr.write
        )
        self.stdout.write(self.style.SUCCESS(f"{season}: {loaded} filas refrescadas."))
