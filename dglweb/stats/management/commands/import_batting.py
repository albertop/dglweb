"""Load batting seasons for the Dominican subset (historical backfill).

    manage.py import_batting --season 2025
    manage.py import_batting --from 1876 --to 2025

Two properties matter more than speed here, because this can run unattended:

* **Idempotent.** Rows are upserted on `(player, season, stint)` via `save_batting_rows`, so
  re-running after a failure fixes the data instead of duplicating it.
* **One bad season does not sink the run.** A season that fails is recorded and skipped; the rest
  still load, the run is marked PARTIAL in the ingest log, and the command still exits non-zero so
  a scheduler notices.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dglweb.mlb.client import MlbProxyError, build_client
from dglweb.players.models import Player
from dglweb.stats.batting_source import fetch_season
from dglweb.stats.loader import save_batting_rows
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Descarga y carga las temporadas de bateo de los jugadores de dgl_master."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--season", type=int, help="Una sola temporada.")
        parser.add_argument("--from", type=int, dest="season_from", help="Temporada inicial.")
        parser.add_argument("--to", type=int, dest="season_to", help="Temporada final.")

    def handle(self, *args: Any, **options: Any) -> None:
        seasons = self._seasons(options)

        player_ids = set(Player.objects.values_list("player_id", flat=True))
        if not player_ids:
            raise CommandError("dgl_master está vacía: carga la tabla maestra primero.")

        self.stdout.write(f"{len(player_ids)} jugadores en la tabla maestra.")

        scope = f"{seasons.start}-{seasons.stop - 1}" if len(seasons) > 1 else str(seasons.start)
        with record_run("import_batting", scope) as run, build_client() as client:
            for season in seasons:
                try:
                    rows = fetch_season(client, season, player_ids)
                except MlbProxyError as exc:
                    run.fail(str(season))
                    self.stderr.write(f"{season}: falló la descarga — {exc}")
                    continue

                run.add_rows(save_batting_rows(rows))
                run.note(f"{season}: {len(rows)} filas")
                self.stdout.write(f"{season}: {len(rows)} filas")

            self.stdout.write(self.style.SUCCESS(f"{run.rows} filas cargadas."))
            failed = run.failed_any

        if failed:
            raise CommandError("hubo temporadas sin cargar (ver la bitácora de ejecuciones).")

    def _seasons(self, options: dict[str, Any]) -> range:
        if options["season"]:
            return range(options["season"], options["season"] + 1)

        first, last = options["season_from"], options["season_to"]
        if not first or not last:
            raise CommandError("indica --season, o bien --from y --to.")
        if first > last:
            raise CommandError("--from no puede ser mayor que --to.")
        return range(first, last + 1)
