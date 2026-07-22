"""Check the pitching port against an extract of the source table.

    manage.py parity_pitching --expected extract.json

`extract.json` is a dump of `dbo.mlbPitching` for the Dominican subset, produced on the host with
sqlcmd, its columns aliased to our field names (so no rename map is needed here). Use an **old,
stable season**: the source's recent seasons are stale (the owner last ran the pitching script a
while ago), so 2024 would show differences that are staleness, not port bugs.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dglweb.mlb.client import build_client
from dglweb.players.models import Player
from dglweb.stats.parity import compare_pitching
from dglweb.stats.pitching_source import fetch_season


class Command(BaseCommand):
    help = "Compara el port de pitcheo contra un extracto de dbo.mlbPitching."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--expected", required=True, help="JSON de dbo.mlbPitching (alias a nuestros campos).")
        parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerancia sabermétrica.")

    def handle(self, *args: Any, **options: Any) -> None:
        expected = self._load_expected(Path(options["expected"]))
        seasons = sorted({row["season"] for row in expected})
        player_ids = set(Player.objects.values_list("player_id", flat=True))
        if not player_ids:
            raise CommandError("dgl_master está vacía: carga la tabla maestra primero.")

        self.stdout.write(f"{len(expected)} filas esperadas, temporadas {seasons[0]}-{seasons[-1]}.")

        actual: list[dict[str, Any]] = []
        with build_client() as client:
            for season in seasons:
                actual.extend(fetch_season(client, season, player_ids))

        report = compare_pitching(expected, actual, tolerance=options["tolerance"])
        self.stdout.write(report.summary())
        for m in report.mismatches[:20]:
            self.stderr.write(f"  {m.key} {m.column}: origen={m.expected} cargado={m.actual}")
        for key in report.missing_rows[:20]:
            self.stderr.write(f"  falta en el port: {key}")

        if report.ok:
            self.stdout.write(self.style.SUCCESS("Paridad OK."))
        else:
            raise CommandError("Paridad con diferencias (ver arriba).")

    def _load_expected(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise CommandError(f"no existe el extracto: {path}")
        raw = path.read_text(encoding="utf-8-sig").replace("\r", "").replace("\n", "")
        return list(json.loads(raw))
