"""Shared body of the loader commands — backfill and current-season refresh.

Both properties that matter for an unattended job live here once: every run is recorded to the
ingest log (`record_run`), and a season that fails is skipped without sinking the rest (backfill)
while still surfacing loudly. Parameterised by the sport's `fetch_season` and `save_rows`, so
batting, pitching and fielding reuse the same tested flow.
"""

from collections.abc import Callable
from typing import Any

from django.core.management.base import CommandError

from dglweb.mlb.client import MlbProxyClient, MlbProxyError, build_client
from dglweb.players.models import Player
from dglweb.stats.runlog import record_run

FetchSeason = Callable[[MlbProxyClient, int, set[int]], list[dict[str, Any]]]
SaveRows = Callable[[list[dict[str, Any]]], int]
Write = Callable[[str], Any]


def _player_ids() -> set[int]:
    ids = set(Player.objects.values_list("player_id", flat=True))
    if not ids:
        raise CommandError("dgl_master está vacía: carga la tabla maestra primero.")
    return ids


def backfill(
    command: str, seasons: range, fetch_season: FetchSeason, save_rows: SaveRows, *, note: Write, warn: Write
) -> tuple[int, bool]:
    """Load a range of seasons. Returns (rows loaded, whether any season failed)."""
    player_ids = _player_ids()
    scope = f"{seasons.start}-{seasons.stop - 1}" if len(seasons) > 1 else str(seasons.start)

    with record_run(command, scope) as run, build_client() as client:
        for season in seasons:
            try:
                rows = fetch_season(client, season, player_ids)
            except MlbProxyError as exc:
                run.fail(str(season))
                warn(f"{season}: falló la descarga — {exc}")
                continue

            run.add_rows(save_rows(rows))
            run.note(f"{season}: {len(rows)} filas")
            note(f"{season}: {len(rows)} filas")

        return run.rows, run.failed_any


def refresh_current(command: str, season: int, fetch_season: FetchSeason, save_rows: SaveRows, *, warn: Write) -> int:
    """Reload a single (current) season. A proxy failure fails the whole run."""
    player_ids = _player_ids()

    with record_run(command, f"temporada actual ({season})") as run, build_client() as client:
        try:
            rows = fetch_season(client, season, player_ids)
        except MlbProxyError as exc:
            warn(f"{season}: falló la descarga — {exc}")
            raise CommandError(f"no se pudo refrescar {season} (ver la bitácora).") from exc

        run.add_rows(save_rows(rows))
        run.note(f"{season}: {len(rows)} filas")
        return len(rows)
