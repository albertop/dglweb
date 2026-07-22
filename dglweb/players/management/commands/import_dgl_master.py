"""Load the DGL master extract into the `dgl_master` table.

The extract is produced on Windows from SQL Server (`DGL.dbo.dglMaster`) with the owner's
mapping query, which already applies the `0 -> NULL` sentinel conversions
(`statsID`, `fanGraphID`, `signYear`, `yearDomHof`) and formats dates as ISO strings.

Usage:
    python manage.py import_dgl_master --file _dgl_extract.json          # initial load
    python manage.py import_dgl_master --file _dgl_extract.json --upsert # insert/update, no deletes
    python manage.py import_dgl_master --file _dgl_extract.json --upsert --delete-missing [--force]

**Never deletes stats.** `dgl_master` is a living authority whose `player_id` is the parent of
`mlb_batting`/`mlb_pitching`/`mlb_fielding` via CASCADE. A blunt `delete()` here would wipe the
whole backfill, so the reload path is an **upsert on `player_id`**. Removing players that dropped
out of the extract is opt-in (`--delete-missing`) and refuses to touch anyone who has stats rows
unless `--force` is given.
"""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.db.models import Q

from dglweb.players.models import Player

# The 28 columns produced by the extract query.
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
_UPDATE_FIELDS = sorted(EXPECTED_FIELDS - {"player_id"})
# Columns the DB enforces as unique; a duplicate within the extract is a clearer error here.
_UNIQUE_FIELDS = ("dgl_id", "bbref_id", "bbref_minor_id", "retro_id", "yahoo_id", "fangraphs_id", "register_id")


class Command(BaseCommand):
    help = "Load the DGL master JSON extract into dgl_master (upsert; never deletes stats)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--file", required=True, help="Path to the JSON extract.")
        parser.add_argument(
            "--upsert",
            action="store_true",
            help="Insert new players and update existing ones by player_id. No rows are deleted. "
            "Required to modify a non-empty table.",
        )
        parser.add_argument(
            "--delete-missing",
            action="store_true",
            help="Also delete players absent from the extract. Aborts if any of them have stats, "
            "unless --force is given. Implies --upsert.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow --delete-missing to remove players that have stats rows (CASCADE).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        records = self._load(Path(options["file"]))
        self._validate(records)

        existing = Player.objects.count()
        if existing and not (options["upsert"] or options["delete_missing"]):
            raise CommandError(
                f"dgl_master already has {existing} rows; pass --upsert to insert/update (nothing is deleted)."
            )

        extract_ids = {record["player_id"] for record in records}
        with transaction.atomic():
            if options["delete_missing"]:
                self._delete_missing(extract_ids, force=options["force"])
            Player.objects.bulk_create(
                [Player(**record) for record in records],
                update_conflicts=True,
                unique_fields=["player_id"],
                update_fields=_UPDATE_FIELDS,
                batch_size=500,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Loaded/updated {len(records)} players ({Player.objects.count()} total).")
        )

    def _load(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise CommandError(f"Extract file not found: {path}")
        # utf-8-sig strips the BOM; sqlcmd hard-wraps FOR JSON every 2033 chars, so raw newlines
        # are formatting artifacts (real newlines inside values arrive escaped) — joining rebuilds it.
        raw = path.read_text(encoding="utf-8-sig").replace("\r", "").replace("\n", "")
        records: list[dict[str, Any]] = json.loads(raw)
        if not records:
            raise CommandError("Extract is empty — nothing to load.")
        return records

    def _validate(self, records: list[dict[str, Any]]) -> None:
        """Check every row's shape and every uniqueness constraint before touching the DB."""
        for index, record in enumerate(records):
            unexpected = set(record) - EXPECTED_FIELDS
            missing = EXPECTED_FIELDS - set(record)
            if unexpected or missing:
                raise CommandError(f"Row {index}: column mismatch. Unexpected: {unexpected}. Missing: {missing}.")

        self._reject_duplicates(records, "player_id")
        for field in _UNIQUE_FIELDS:
            self._reject_duplicates(records, field, skip_null=True)

    def _reject_duplicates(self, records: list[dict[str, Any]], field: str, *, skip_null: bool = False) -> None:
        seen: set[Any] = set()
        dupes: set[Any] = set()
        for record in records:
            value = record.get(field)
            if skip_null and value is None:
                continue
            if value in seen:
                dupes.add(value)
            seen.add(value)
        if dupes:
            raise CommandError(f"Duplicate {field} in extract: {sorted(dupes)}.")

    def _delete_missing(self, extract_ids: set[int], *, force: bool) -> None:
        missing = Player.objects.exclude(player_id__in=extract_ids)
        with_stats = missing.filter(
            Q(batting_seasons__isnull=False) | Q(pitching_seasons__isnull=False) | Q(fielding_seasons__isnull=False)
        ).distinct()
        if with_stats.exists() and not force:
            raise CommandError(
                f"{with_stats.count()} players to delete have stats rows; pass --force to delete them too."
            )
        missing.delete()
