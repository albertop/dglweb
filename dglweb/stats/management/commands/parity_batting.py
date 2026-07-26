"""Check the batting port against an extract of the source table.

    manage.py parity_batting --expected extract.json

`extract.json` is a dump of `dbo.mlbBatting` for the Dominican subset (produced on the host with
sqlcmd, where the ODBC connection lives — the container cannot reach SQL Server). The command
fetches the same seasons from the proxy, compares them with `compare_batting`, prints the
report, and exits non-zero if anything is off. It writes nothing to the database: it is a check,
not a load.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dglweb.mlb.client import build_client
from dglweb.players.models import Player
from dglweb.stats.batting_source import fetch_season
from dglweb.stats.parity import compare_batting

# Column names in the sqlcmd extract map straight onto ours except the few we renamed.
_SOURCE_RENAMES = {
    "ABpHR": "ab_per_hr",
    "BBpSO": "bb_per_so",
    "PApSO": "pa_per_so",
    "GrossProdAvg": "gross_prod_avg",
    "EqAVG": "eq_avg",
    "wRCPlus": "w_rc_plus",
    "CatcherInt": "catcher_int",
    "RunsProduced": "runs_produced",
    "TotalAVG": "total_avg",
    "BSR": "bsr",
    "RC": "rc",
}


class Command(BaseCommand):
    help = "Compara el port de bateo contra un extracto de dbo.mlbBatting."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--expected", required=True, help="JSON extraído de dbo.mlbBatting.")
        parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerancia sabermétrica.")

    def handle(self, *args: Any, **options: Any) -> None:
        expected = self._load_expected(Path(options["expected"]))
        seasons = sorted({row["season"] for row in expected})
        player_ids = set(Player.todos.values_list("player_id", flat=True))
        if not player_ids:
            raise CommandError("dgl_master está vacía: carga la tabla maestra primero.")

        self.stdout.write(f"{len(expected)} filas esperadas, temporadas {seasons[0]}-{seasons[-1]}.")

        actual: list[dict[str, Any]] = []
        with build_client() as client:
            for season in seasons:
                actual.extend(fetch_season(client, season, player_ids))

        report = compare_batting(expected, actual, tolerance=options["tolerance"])
        self.stdout.write(report.summary())
        self._print_details(report)

        if report.ok:
            self.stdout.write(self.style.SUCCESS("Paridad OK."))
        else:
            raise CommandError("Paridad con diferencias (ver arriba).")

    def _load_expected(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise CommandError(f"no existe el extracto: {path}")
        raw = path.read_text(encoding="utf-8-sig").replace("\r", "").replace("\n", "")
        rows = json.loads(raw)
        return [self._normalise(row) for row in rows]

    def _normalise(self, row: dict[str, Any]) -> dict[str, Any]:
        """Lowercase the source columns and apply the handful of renames."""
        out: dict[str, Any] = {}
        for key, value in row.items():
            out[_SOURCE_RENAMES.get(key, key.lower())] = value
        return out

    def _print_details(self, report: Any, limit: int = 20) -> None:
        for m in report.mismatches[:limit]:
            self.stderr.write(f"  {m.key} {m.column}: origen={m.expected} cargado={m.actual}")
        if len(report.mismatches) > limit:
            self.stderr.write(f"  … y {len(report.mismatches) - limit} más")
        for key in report.missing_rows[:limit]:
            self.stderr.write(f"  falta en el port: {key}")
