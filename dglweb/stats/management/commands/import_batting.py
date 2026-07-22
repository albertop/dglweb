"""Load batting seasons for the Dominican subset (historical backfill).

    manage.py import_batting --season 2025
    manage.py import_batting --from 1876 --to 2025

Idempotent (upsert on the natural key) and resilient (a failed season is recorded and skipped,
the run marked PARTIAL, the command still exits non-zero). The shared flow lives in
`dglweb/stats/ingest.py`.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dglweb.stats.batting_source import fetch_season
from dglweb.stats.ingest import backfill
from dglweb.stats.loader import save_batting_rows


class Command(BaseCommand):
    help = "Descarga y carga las temporadas de bateo de los jugadores de dgl_master."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--season", type=int, help="Una sola temporada.")
        parser.add_argument("--from", type=int, dest="season_from", help="Temporada inicial.")
        parser.add_argument("--to", type=int, dest="season_to", help="Temporada final.")

    def handle(self, *args: Any, **options: Any) -> None:
        seasons = _seasons(options)
        loaded, failed = backfill(
            "import_batting",
            seasons,
            fetch_season,
            save_batting_rows,
            note=self.stdout.write,
            warn=self.stderr.write,
        )
        self.stdout.write(self.style.SUCCESS(f"{loaded} filas cargadas."))
        if failed:
            raise CommandError("hubo temporadas sin cargar (ver la bitácora de ejecuciones).")


def _seasons(options: dict[str, Any]) -> range:
    if options["season"]:
        return range(options["season"], options["season"] + 1)

    first, last = options["season_from"], options["season_to"]
    if not first or not last:
        raise CommandError("indica --season, o bien --from y --to.")
    if first > last:
        raise CommandError("--from no puede ser mayor que --to.")
    return range(first, last + 1)
