"""Refresh the current season's postseason batting — the job the scheduler runs daily.

    manage.py update_batting_post

Idempotent; outside October/November the rounds simply return nothing.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from dglweb.stats.batting_post_source import fetch_season
from dglweb.stats.ingest import refresh_current
from dglweb.stats.loader import save_batting_post_rows


class Command(BaseCommand):
    help = "Refresca la postemporada de bateo de la temporada actual (para correr en schedule)."

    def handle(self, *args: Any, **options: Any) -> None:
        season = timezone.now().year
        loaded = refresh_current(
            "update_batting_post", season, fetch_season, save_batting_post_rows, warn=self.stderr.write
        )
        self.stdout.write(self.style.SUCCESS(f"{season}: {loaded} filas refrescadas."))
