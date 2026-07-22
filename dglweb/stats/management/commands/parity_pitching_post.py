"""Check the postseason pitching port against an extract of the source table.

    manage.py parity_pitching_post --expected extract.json

`extract.json` is a dump of `dbo.mlbPitchingPost` for the Dominican subset, its columns aliased to
our field names. Keyed by (player, season, round). Use a stable season.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dglweb.mlb.client import build_client
from dglweb.players.models import Player
from dglweb.stats.parity import compare_pitching_post
from dglweb.stats.pitching_post_source import fetch_season


class Command(BaseCommand):
    help = "Compara el port de postemporada de pitcheo contra un extracto de dbo.mlbPitchingPost."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--expected", required=True, help="JSON de dbo.mlbPitchingPost (alias a nuestros campos).")
        parser.add_argument("--tolerance", type=float, default=0.05, help="Tolerancia de tasas.")

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

        report = compare_pitching_post(expected, actual, tolerance=options["tolerance"])
        self.stdout.write(report.summary())
        for m in report.mismatches[:20]:
            self.stderr.write(f"  {m.key} {m.column}: origen={m.expected} cargado={m.actual}")
        for key in report.missing_rows[:20]:
            self.stderr.write(f"  falta en el port: {key}")
        for key in report.extra_rows[:20]:
            self.stderr.write(f"  sobra en el port: {key}")

        if report.ok:
            self.stdout.write(self.style.SUCCESS("Paridad OK."))
        else:
            raise CommandError("Paridad con diferencias (ver arriba).")

    def _load_expected(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise CommandError(f"no existe el extracto: {path}")
        raw = path.read_text(encoding="utf-8-sig").replace("\r", "").replace("\n", "")
        return list(json.loads(raw))
