"""Load postseason batting for the Dominican subset (historical backfill).

    manage.py import_batting_post --season 2025
    manage.py import_batting_post --from 1962 --to 2025

Same shared flow as the regular-season loaders (`dglweb/stats/ingest.py`); `fetch_season` loops
the four postseason rounds internally. Keyed by (player, season, round).
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dglweb.stats.batting_post_source import fetch_season
from dglweb.stats.ingest import backfill
from dglweb.stats.loader import save_batting_post_rows


class Command(BaseCommand):
    help = "Descarga y carga la postemporada de bateo de los jugadores de dgl_master."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--season", type=int, help="Una sola temporada.")
        parser.add_argument("--from", type=int, dest="season_from", help="Temporada inicial.")
        parser.add_argument("--to", type=int, dest="season_to", help="Temporada final.")

    def handle(self, *args: Any, **options: Any) -> None:
        seasons = _seasons(options)
        loaded, failed = backfill(
            "import_batting_post",
            seasons,
            fetch_season,
            save_batting_post_rows,
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
