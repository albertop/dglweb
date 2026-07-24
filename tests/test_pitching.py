"""Tests for the historical pitching table (Fase 3).

Schema derived column by column from `dbo.mlbPitching` (101 columns) — the table the owner's R
pipeline produces. Nothing invented; the field order mirrors the source.
"""

import pytest
from django.db import IntegrityError, models

from dglweb.players.models import Player
from dglweb.stats.models import Pitching
from tests.test_players import RECORD

# The 101 columns of dbo.mlbPitching, in source order, under the agreed naming convention.
EXPECTED_FIELDS = (
    "player",
    "season",
    "stint",
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
    # coeficientes de batazo (derive.batted_ball_coefficients) — mismos que bateo
    "gb_pct",
    "fb_pct",
    "ld_pct",
    "pu_pct",
    "gb_fb",
    "contact_pct",
    "whiff_pct",
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
    "fip",
    "xfip",
    "fip_minus",
    "ra9_war",
    "rar",
    "war",
    "sd",
    "md",
    "p_li",
    "in_li",
    "gm_li",
    "ex_li",
    "era_minus",
    # extra fields the proxy offers beyond the source table (raw)
    "age",
    "ab",
    "sh_fail",
    "sh_missed",
)

SEASON: dict[str, object] = {"season": 2008, "stint": 1, "team": "PIT", "league": "NL", "g": 47}


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


def test_has_every_expected_column_in_order() -> None:
    """The 101 source columns plus the extra raw fields the proxy offers."""
    ours = tuple(f.name for f in Pitching._meta.get_fields() if f.name not in {"id", "pk"})

    assert ours == EXPECTED_FIELDS


def test_uses_the_agreed_table_name() -> None:
    assert Pitching._meta.db_table == "mlb_pitching"


@pytest.mark.django_db
def test_a_season_belongs_to_a_player_in_the_master_table(player: Player) -> None:
    Pitching.objects.create(player=player, **SEASON)

    assert player.pitching_seasons.get().season == 2008


@pytest.mark.django_db
def test_the_same_player_season_and_stint_cannot_repeat(player: Player) -> None:
    Pitching.objects.create(player=player, **SEASON)

    with pytest.raises(IntegrityError):
        Pitching.objects.create(player=player, **SEASON)


@pytest.mark.django_db
def test_stints_are_not_reversed_here_unlike_batting(player: Player) -> None:
    """Pitching numbers stints as the proxy lists them: stint 1 is the oldest team."""
    Pitching.objects.create(player=player, **{**SEASON, "stint": 1, "team": "PIT"})
    Pitching.objects.create(player=player, **{**SEASON, "stint": 2, "team": "NYA"})
    Pitching.objects.create(player=player, **{**SEASON, "stint": 3, "team": "XXX", "league": "XX"})

    assert player.pitching_seasons.count() == 3


@pytest.mark.django_db
def test_stats_that_did_not_exist_in_an_era_are_null_not_zero(player: Player) -> None:
    row = Pitching.objects.create(player=player, season=1950, stint=1, g=30)

    assert row.total_swings is None
    assert row.fip is None


def test_only_the_natural_key_is_required() -> None:
    required = {
        f.name
        for f in Pitching._meta.get_fields()
        if isinstance(f, models.Field) and not f.null and f.name not in {"id", "pk"}
    }

    assert required == {"player", "season", "stint"}


@pytest.mark.django_db
def test_str_reads_like_a_stat_line(player: Player) -> None:
    row = Pitching.objects.create(player=player, **SEASON)

    assert str(row) == "Gibson Alba 2008 PIT"
