"""Seed per-group season qualifier overrides for the short seasons (level 3 of the cascade).

The group defaults (`QualifierDefault`, level 1) assume a 162-game schedule, so a rate threshold
like ``PA>=502`` is unreachable in a shortened year. These are *exceptions* — a handful of seasons —
so we override them explicitly per `(group, season)`: one row (batting/2020 -> PA>=186) applies to
every rate metric of the group at once. Each group's default season threshold is prorated by
``games / 162``. Career thresholds are never overridden per season.

Idempotent: `get_or_create` on (stat_group, season). `--reset` clears these seasons first. The
1981/1994 game counts are approximate (teams played varying totals in the strike years); tune any
value in the Backoffice afterwards.
"""

import re
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from dglweb.stats.models import QualifierDefault, QualifierSeasonOverride

_FULL_SCHEDULE = 162

# Team games for each short season (stated explicitly; editable in the Backoffice).
_SHORT_SEASONS: dict[int, int] = {
    1956: 154,  # 154-game era (leaders start in 1956; 1961 was mixed by league -> games table, backlog)
    1957: 154,
    1958: 154,
    1959: 154,
    1960: 154,
    1981: 107,  # players' strike (approx.)
    1994: 114,  # players' strike (approx.)
    2020: 60,  # pandemic
}

_QUALIFIER = re.compile(r"^\s*([A-Za-z_]+)\s*(>=|<=|>|<|=)\s*(\d+)\s*$")


def _prorate(formula: str, games: int) -> str | None:
    """`PA>=502` at `games` team-games -> `PA>=<prorated>`; None if the formula is not a simple one."""
    match = _QUALIFIER.match(formula)
    if match is None:
        return None
    field, op, threshold = match.group(1), match.group(2), int(match.group(3))
    scaled = round(threshold * games / _FULL_SCHEDULE)
    return f"{field}{op}{scaled}"


class Command(BaseCommand):
    help = "Siembra los overrides de umbral por (grupo, temporada) para las temporadas cortas."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true", help="Borra los overrides de estas temporadas primero.")

    def handle(self, *args: Any, **options: Any) -> None:
        seasons = list(_SHORT_SEASONS)
        with transaction.atomic():
            if options["reset"]:
                QualifierSeasonOverride.objects.filter(season__in=seasons).delete()
            written = 0
            defaults = list(QualifierDefault.objects.exclude(qualifier_season=""))
            for default in defaults:
                for season, games in _SHORT_SEASONS.items():
                    formula = _prorate(default.qualifier_season, games)
                    if formula is None:
                        continue
                    _, created = QualifierSeasonOverride.objects.get_or_create(
                        stat_group=default.stat_group, season=season, defaults={"qualifier_season": formula}
                    )
                    written += created
        self.stdout.write(
            self.style.SUCCESS(f"{written} overrides creados ({len(defaults)} grupos x {len(seasons)} temporadas).")
        )
