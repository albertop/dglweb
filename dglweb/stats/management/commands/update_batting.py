"""Refresh the current season's batting — the job the scheduler runs daily.

    manage.py update_batting

Season-aware but simple: it reloads the current calendar year through the same idempotent path
as the backfill (`fetch_season` + `save_batting_rows`), so running it every morning keeps the
in-season numbers current and running it twice changes nothing. The historical backfill stays a
manual `import_batting --from --to`; this only touches the year in progress.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dglweb.mlb.client import MlbProxyError, build_client
from dglweb.players.models import Player
from dglweb.stats.batting_source import fetch_season
from dglweb.stats.loader import save_batting_rows
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Refresca el bateo de la temporada actual (para correr en schedule)."

    def handle(self, *args: Any, **options: Any) -> None:
        season = timezone.now().year

        player_ids = set(Player.objects.values_list("player_id", flat=True))
        if not player_ids:
            raise CommandError("dgl_master está vacía: carga la tabla maestra primero.")

        with record_run("update_batting", f"temporada actual ({season})") as run, build_client() as client:
            try:
                rows = fetch_season(client, season, player_ids)
            except MlbProxyError as exc:
                # A single-season refresh that can't reach the proxy is a full failure; the raise
                # marks the run FAILED (with the error) and lets the scheduler notice.
                self.stderr.write(f"{season}: falló la descarga — {exc}")
                raise CommandError(f"no se pudo refrescar {season} (ver la bitácora).") from exc

            run.add_rows(save_batting_rows(rows))
            run.note(f"{season}: {len(rows)} filas")
            self.stdout.write(self.style.SUCCESS(f"{season}: {len(rows)} filas refrescadas."))
