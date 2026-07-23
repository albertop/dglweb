"""The player-page tab registry — the extensibility seam.

A tab is a small object: what it is (`key`, `label`, `template`), whether a given player has data
for it (`applies_to`), where it sits in the tab bar for that player (`order_for` — pitchers lead
with Pitcheo), and the data its partial renders (`context`). Adding a new tab (Splits, Premios,
Game Logs…) is a new subclass + a template partial + one line in `REGISTRY`; the page shell, the
URL and the other tabs are untouched.
"""

from typing import Any

from dglweb.players.models import Player
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    BattingPost,
    CareerLevel,
    Fielding,
    FieldingCareer,
    Pitching,
    PitchingCareer,
)

_PITCHER_POSITIONS = {"P", "RP", "SP"}  # the master's pitcher codes (starter / reliever / generic)


def is_pitcher(player: Player) -> bool:
    return player.pos in _PITCHER_POSITIONS


class PlayerTab:
    """Base tab. Subclasses set the class attrs and implement `applies_to`/`context`."""

    key: str = ""
    label: str = ""
    template: str = ""
    base_order: int = 0

    def applies_to(self, player: Player) -> bool:
        raise NotImplementedError

    def order_for(self, player: Player) -> int:
        return self.base_order

    def context(self, player: Player) -> dict[str, Any]:
        return {}


class BattingTab(PlayerTab):
    key = "batting"
    label = "Bateo"
    template = "profiles/tabs/batting.html"
    base_order = 10

    def applies_to(self, player: Player) -> bool:
        return BattingCareer.objects.filter(player=player).exists()

    def order_for(self, player: Player) -> int:
        return 20 if is_pitcher(player) else 10  # pitchers push Bateo below Pitcheo

    def context(self, player: Player) -> dict[str, Any]:
        career = list(BattingCareer.objects.filter(player=player).order_by("sort_order"))
        return {
            "seasons": list(Batting.objects.filter(player=player).season_totals().order_by("season")),
            "total": next((row for row in career if row.level == CareerLevel.TOTAL), None),
            "teams": [row for row in career if row.level == CareerLevel.TEAM],
            "leagues": [row for row in career if row.level == CareerLevel.LEAGUE],
            "post": list(BattingPost.objects.filter(player=player).order_by("season", "round")),
        }


class PitchingTab(PlayerTab):
    key = "pitching"
    label = "Pitcheo"
    template = "profiles/tabs/_soon.html"  # placeholder until built (same shell, no page rework)
    base_order = 20

    def applies_to(self, player: Player) -> bool:
        return PitchingCareer.objects.filter(player=player).exists()

    def order_for(self, player: Player) -> int:
        return 10 if is_pitcher(player) else 20

    def context(self, player: Player) -> dict[str, Any]:
        return {"has_data": Pitching.objects.filter(player=player).exists()}


class FieldingTab(PlayerTab):
    key = "fielding"
    label = "Fildeo"
    template = "profiles/tabs/_soon.html"
    base_order = 30

    def applies_to(self, player: Player) -> bool:
        return FieldingCareer.objects.filter(player=player).exists()

    def context(self, player: Player) -> dict[str, Any]:
        return {"has_data": Fielding.objects.filter(player=player).exists()}


REGISTRY: list[PlayerTab] = [BattingTab(), PitchingTab(), FieldingTab()]  # append new tabs here


def tabs_for(player: Player) -> list[PlayerTab]:
    """The tabs that apply to a player, in that player's display order (pitchers lead with Pitcheo)."""
    return sorted((tab for tab in REGISTRY if tab.applies_to(player)), key=lambda tab: tab.order_for(player))
