"""Load the DGL master extract into the `dgl_master` table.

The extract is produced on Windows from SQL Server (`DGL.dbo.dglMaster`) with the owner's
mapping query, which already applies the `0 -> NULL` sentinel conversions
(`statsID`, `fanGraphID`, `signYear`, `yearDomHof`) and formats dates as ISO strings.

Usage:
    python manage.py import_dgl_master --file _dgl_extract.json [--replace]
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from dglweb.players.models import Player

# The 28 columns produced by the extract query, in model order.
EXPECTED_FIELDS = {
    "player_id",
    "dgl_id",
    "bbref_id",
    "bbref_minor_id",
    "retro_id",
    "yahoo_id",
    "fangraphs_id",
    "register_id",
    "lastname_1",
    "lastname_2",
    "firstname",
    "secondname",
    "nickname",
    "full_name",
    "birth_date",
    "birth_place",
    "birth_province",
    "birth_country_code",
    "bats",
    "throws",
    "height",
    "weight",
    "pos",
    "debut_date",
    "death_date",
    "sign_year",
    "sign_date",
    "dom_hof_year",
}


class Command(BaseCommand):
    help = "Load the DGL master JSON extract into dgl_master."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--file", required=True, help="Path to the JSON extract.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing rows before loading (otherwise a non-empty table aborts).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Extract file not found: {path}")

        # utf-8-sig strips the BOM that sqlcmd writes. sqlcmd also hard-wraps FOR JSON output
        # every 2033 chars, so raw newlines are formatting artifacts, not data (real newlines
        # inside values arrive escaped as \n) — joining the lines rebuilds the document.
        raw = path.read_text(encoding="utf-8-sig").replace("\r", "").replace("\n", "")
        records: list[dict[str, Any]] = json.loads(raw)
        if not records:
            raise CommandError("Extract is empty — nothing to load.")

        unexpected = set(records[0]) - EXPECTED_FIELDS
        missing = EXPECTED_FIELDS - set(records[0])
        if unexpected or missing:
            raise CommandError(f"Column mismatch. Unexpected: {unexpected}. Missing: {missing}.")

        existing = Player.objects.count()
        if existing and not options["replace"]:
            raise CommandError(f"dgl_master already has {existing} rows; pass --replace to reload.")

        with transaction.atomic():
            if options["replace"]:
                Player.objects.all().delete()
            Player.objects.bulk_create(
                [Player(**record) for record in records],
                batch_size=500,
            )

        self.stdout.write(self.style.SUCCESS(f"Loaded {Player.objects.count()} players."))
