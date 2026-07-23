"""The player-page tab registry — the extensibility seam.

A tab is a small object: what it is (`key`, `label`, `template`), whether a given player has data
for it (`applies_to`), where it sits in the tab bar for that player (`order_for` — pitchers lead
with Pitcheo), and the data its partial renders (`context`). Adding a new tab (Splits, Premios,
Game Logs…) is a new subclass + a template partial + one line in `REGISTRY`; the page shell, the
URL and the other tabs are untouched.
"""

from typing import Any

from django.db import models

from dglweb.players.models import Player
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    BattingPost,
    CareerLevel,
    Fielding,
    FieldingCareer,
    Leader,
    Pitching,
    PitchingCareer,
)

_PITCHER_POSITIONS = {"P", "RP", "SP"}  # the master's pitcher codes (starter / reliever / generic)


def is_pitcher(player: Player) -> bool:
    return player.pos in _PITCHER_POSITIONS


def _leaderships(player: Player, group: str) -> tuple[set[tuple[int, str]], set[str]]:
    """Where this player is the #1 leader: {(season, column)} for the season and {column} for career.

    Batting/pitching are position-agnostic (their leaders carry `fielding_pos=NULL`) — position is
    only a fielding dimension. Drives the in-table highlight (wine = season leader, blue = career).
    """
    marks = Leader.objects.filter(player=player, rank=1, metric__stat_group=group).select_related("metric")
    season = {
        (row.season, row.metric.column)
        for row in marks
        if row.board == Leader.Board.BEST_SEASON and row.season is not None
    }
    career = {row.metric.column for row in marks if row.board == Leader.Board.BEST_CAREER}
    return season, career


_NOT_A_STAT = {"season", "stint", "age"}


def _personal_bests(model: type[models.Model], seasons: list[Any]) -> set[tuple[int, str]]:
    """Per numeric column, the season(s) holding the player's own career-high (his `más alto`)."""
    columns = [
        field.name
        for field in model._meta.fields
        if isinstance(field, models.IntegerField | models.FloatField) and field.name not in _NOT_A_STAT
    ]
    best: set[tuple[int, str]] = set()
    for column in columns:
        values = [(row.season, getattr(row, column)) for row in seasons if getattr(row, column) is not None]
        if values:
            top = max(value for _, value in values)
            best |= {(season, column) for season, value in values if value == top}
    return best


def _season_highlights(
    model: type[models.Model], seasons: list[Any], season_leads: set[tuple[int, str]]
) -> list[tuple[Any, dict[str, str]]]:
    """(row, {column: css class}). Priority: season leader (wine) > personal career-high (black bold)."""
    best = _personal_bests(model, seasons)
    rows = []
    for row in seasons:
        classes: dict[str, str] = {}
        for season, column in season_leads:
            if season == row.season:
                classes[column] = "lead-season"
        for season, column in best:
            if season == row.season and column not in classes:
                classes[column] = "lead-best"
        rows.append((row, classes))
    return rows


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
        seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
        season_leads, career_leads = _leaderships(player, "batting")
        career = list(BattingCareer.objects.filter(player=player).order_by("sort_order"))
        return {
            # (row, {column: css class}): season leader (wine) > personal career-high (black).
            "rows": _season_highlights(Batting, seasons, season_leads),
            "total": next((row for row in career if row.level == CareerLevel.TOTAL), None),
            "total_leads": {col: "lead-career" for col in career_leads},  # blue on the career row
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
