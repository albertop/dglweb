"""Tests for the postseason batting table (Fase 3).

Schema derived from `dbo.mlbBattingPost` (59 columns). Postseason is keyed by round, not stint:
`(player, season, round)` with round in {DS, WC, LCS, WS}. No sabermetrics block (the owner's
post script uses only season + seasonAdvanced), no `XXX`, no per-team stints.
"""

import pytest
from django.db import IntegrityError, models

from dglweb.players.models import Player
from dglweb.stats.models import BattingPost
from tests.test_players import RECORD

EXPECTED_FIELDS = (
    "player",
    "season",
    "round",
    "team",
    "league",
    "pos",
    "g",
    "pa",
    "ab",
    "r",
    "h",
    "x1b",
    "x2b",
    "x3b",
    "hr",
    "xbh",
    "rbi",
    "sb",
    "cs",
    "bb",
    "so",
    "ibb",
    "nibb",
    "hbp",
    "sh",
    "sf",
    "gidp",
    "pitches",
    "tb",
    "lob",
    "catcher_int",
    "avg",
    "obp",
    "slg",
    "ops",
    "ab_per_hr",
    "babip",
    "bb_per_so",
    "bsr",
    "eq_avg",
    "gross_prod_avg",
    "iso",
    "pa_per_so",
    "rc",
    "runs_produced",
    "total_avg",
    "air_outs",
    "ground_outs",
    "fly_outs",
    "pop_outs",
    "line_outs",
    "fly_hits",
    "pop_hits",
    "line_hits",
    "ground_hits",
    "total_swings",
    "swing_and_misses",
    "balls_in_play",
    "walk_offs",
)

ROW: dict[str, object] = {"season": 2013, "round": "WS", "team": "BOS", "league": "AL", "ab": 16, "h": 11}


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


def test_has_every_source_column_in_order() -> None:
    ours = tuple(f.name for f in BattingPost._meta.get_fields() if f.name not in {"id", "pk"})

    assert ours == EXPECTED_FIELDS


def test_uses_the_agreed_table_name() -> None:
    assert BattingPost._meta.db_table == "mlb_batting_post"


@pytest.mark.django_db
def test_a_player_can_have_several_rounds_in_one_season(player: Player) -> None:
    BattingPost.objects.create(player=player, **{**ROW, "round": "DS"})
    BattingPost.objects.create(player=player, **{**ROW, "round": "LCS"})
    BattingPost.objects.create(player=player, **{**ROW, "round": "WS"})

    assert player.batting_post_seasons.count() == 3


@pytest.mark.django_db
def test_the_same_player_season_and_round_cannot_repeat(player: Player) -> None:
    BattingPost.objects.create(player=player, **ROW)

    with pytest.raises(IntegrityError):
        BattingPost.objects.create(player=player, **ROW)


def test_only_the_natural_key_is_required() -> None:
    required = {
        f.name
        for f in BattingPost._meta.get_fields()
        if isinstance(f, models.Field) and not f.null and f.name not in {"id", "pk"}
    }

    assert required == {"player", "season", "round"}


@pytest.mark.django_db
def test_str_reads_like_a_postseason_line(player: Player) -> None:
    row = BattingPost.objects.create(player=player, **ROW)

    assert str(row) == "Gibson Alba 2013 WS BOS"
