"""Delete ingest-log rows older than the retention window.

    manage.py prune_ingest_log            # uses settings.INGEST_LOG_RETENTION_DAYS (default 30)
    manage.py prune_ingest_log --days 7

`IngestRun` is a rolling operational log, not permanent data, so it must not grow forever. This
runs daily in the scheduler; keeping the window in a setting means ops can change it without code.
"""

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.stats.models import IngestRun


class Command(BaseCommand):
    help = "Borra las ejecuciones de la bitácora más viejas que la ventana de retención."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Días de retención (default: settings.INGEST_LOG_RETENTION_DAYS).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = options["days"] if options["days"] is not None else settings.INGEST_LOG_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)

        deleted, _ = IngestRun.objects.filter(started_at__lt=cutoff).delete()

        self.stdout.write(self.style.SUCCESS(f"{deleted} ejecuciones borradas (> {days} días)."))
