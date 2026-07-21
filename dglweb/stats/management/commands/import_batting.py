"""Load batting seasons for the Dominican subset.

    manage.py import_batting --season 2025
    manage.py import_batting --from 1876 --to 2025

Two properties matter more than speed here, because this runs unattended:

* **Idempotent.** Rows are upserted on `(player, season, stint)`, so re-running after a failure
  fixes the data instead of duplicating it. That is what makes a retry safe at 3am.
* **One bad season does not sink the run.** A season that fails is reported and skipped; the
  rest still load, and the command exits non-zero so the scheduler notices. Aborting the whole
  backfill because 1943 timed out would be the fragile choice.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from dglweb.mlb.client import MlbProxyError, build_client
from dglweb.players.models import Player
from dglweb.stats.batting_source import fetch_season
from dglweb.stats.models import Batting

# Every column except the natural key gets refreshed on conflict.
_UPDATE_FIELDS = [field.name for field in Batting._meta.fields if field.name not in {"id", "player", "season", "stint"}]


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

        loaded = 0
        failed: list[int] = []
        with build_client() as client:
            for season in seasons:
                try:
                    rows = fetch_season(client, season, player_ids)
                except MlbProxyError as exc:
                    failed.append(season)
                    self.stderr.write(f"{season}: falló la descarga — {exc}")
                    continue

                loaded += self._save(rows)
                self.stdout.write(f"{season}: {len(rows)} filas")

        self.stdout.write(self.style.SUCCESS(f"{loaded} filas cargadas."))
        if failed:
            raise CommandError(f"temporadas sin cargar: {', '.join(str(s) for s in failed)}")

    def _seasons(self, options: dict[str, Any]) -> range:
        if options["season"]:
            return range(options["season"], options["season"] + 1)

        first, last = options["season_from"], options["season_to"]
        if not first or not last:
            raise CommandError("indica --season, o bien --from y --to.")
        if first > last:
            raise CommandError("--from no puede ser mayor que --to.")
        return range(first, last + 1)

    def _save(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        with transaction.atomic():
            Batting.objects.bulk_create(
                [Batting(**row) for row in rows],
                update_conflicts=True,
                unique_fields=["player", "season", "stint"],
                update_fields=_UPDATE_FIELDS,
                batch_size=500,
            )
        return len(rows)
