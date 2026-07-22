"""Tests for the postseason pitching table (Fase 3).

Schema from `dbo.mlbPitchingPost` (88 columns). Keyed by round like batting post; the regular +
advanced pitching columns, no sabermetrics (FIP/WAR block absent), no extras (age/ab/sh_*). One
mlbstats formula: BAA, reused from regular pitching.
"""

import pytest
from django.db import IntegrityError, models

from dglweb.players.models import Player
from dglweb.stats.models import PitchingPost
from tests.test_players import RECORD

EXPECTED_FIELDS = (
    "player",
    "season",
    "round",
    "team",
    "league",
    "pos",
    "w",
    "l",
    "g",
    "gp",
    "gs",
    "gf",
    "cg",
    "sho",
    "sv",
    "bsv",
    "hld",
    "ip",
    "h",
    "r",
    "hr",
    "er",
    "era",
    "bb",
    "ibb",
    "so",
    "hbp",
    "wp",
    "bk",
    "bf",
    "x2b",
    "x3b",
    "x1b",
    "nibb",
    "avg",
    "obp",
    "slg",
    "ops",
    "cs",
    "sb",
    "sb_pct",
    "gidp",
    "pitches",
    "save_opp",
    "outs",
    "ground_outs",
    "air_outs",
    "strikes",
    "strike_pct",
    "inherit_runners",
    "inherit_runners_scored",
    "sh",
    "sf",
    "pickoffs",
    "tb",
    "catcher_int",
    "baa",
    "whip",
    "win_pct",
    "r_per9",
    "runs_scored_per9",
    "babip",
    "so_per9",
    "bb_per9",
    "hr_per9",
    "h_per9",
    "so_to_bb",
    "bequeathed_runners",
    "bequeathed_runners_scored",
    "quality_starts",
    "gidp_opp",
    "total_swings",
    "swing_and_misses",
    "balls_in_play",
    "run_support",
    "pitches_per_inning",
    "pitches_per_pa",
    "walks_per_pa",
    "so_per_pa",
    "bb_per_so",
    "iso",
    "fly_outs",
    "pop_outs",
    "line_outs",
    "fly_hits",
    "pop_hits",
    "line_hits",
    "ground_hits",
)

ROW: dict[str, object] = {"season": 2013, "round": "WS", "team": "BOS", "league": "AL", "ip": 6.0, "so": 5}


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


def test_has_every_source_column_in_order() -> None:
    ours = tuple(f.name for f in PitchingPost._meta.get_fields() if f.name not in {"id", "pk"})

    assert ours == EXPECTED_FIELDS


def test_uses_the_agreed_table_name() -> None:
    assert PitchingPost._meta.db_table == "mlb_pitching_post"


@pytest.mark.django_db
def test_a_player_can_pitch_in_several_rounds(player: Player) -> None:
    PitchingPost.objects.create(player=player, **{**ROW, "round": "DS"})
    PitchingPost.objects.create(player=player, **{**ROW, "round": "WS"})

    assert player.pitching_post_seasons.count() == 2


@pytest.mark.django_db
def test_the_same_player_season_and_round_cannot_repeat(player: Player) -> None:
    PitchingPost.objects.create(player=player, **ROW)

    with pytest.raises(IntegrityError):
        PitchingPost.objects.create(player=player, **ROW)


def test_only_the_natural_key_is_required() -> None:
    required = {
        f.name
        for f in PitchingPost._meta.get_fields()
        if isinstance(f, models.Field) and not f.null and f.name not in {"id", "pk"}
    }

    assert required == {"player", "season", "round"}
