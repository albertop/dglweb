"""Tests for the historical batting table (Fase 3).

Schema derived column by column from `dbo.mlbBatting` in SQL Server — the table the owner's
R pipeline produces. Nothing here is invented.
"""

import pytest
from django.db import IntegrityError, models

from dglweb.players.models import Player
from dglweb.stats.models import Batting
from tests.test_players import RECORD

# The 75 columns of dbo.mlbBatting, in source order, under the agreed naming convention.
EXPECTED_FIELDS = (
    "player",
    "season",
    "stint",
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
    # Not from the source: our batted-ball / swing coefficients (derive.py group 3).
    "gb_pct",
    "fb_pct",
    "ld_pct",
    "pu_pct",
    "gb_fb",
    "contact_pct",
    "whiff_pct",
    "woba",
    "w_raa",
    "w_rc",
    "w_rc_plus",
    "rar",
    "war",
    "ubr",
    "w_gdp",
    "w_sb",
    "spd",
    "positional_adj",
    "w_league",
    "batting",
    "fielding",
    "base_running",
    "replacement",
    # extra fields the proxy offers beyond the source table (raw)
    "age",
    "roe",
    "gidp_opp",
)

SEASON: dict[str, object] = {"season": 2004, "stint": 1, "team": "LAN", "league": "NL", "g": 156}


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


def test_has_every_expected_column_in_order() -> None:
    """The 75 source columns plus the extra raw fields the proxy offers; guards typos/drops."""
    ours = tuple(f.name for f in Batting._meta.get_fields() if f.name not in {"id", "pk"})

    assert ours == EXPECTED_FIELDS


def test_uses_the_agreed_table_name() -> None:
    assert Batting._meta.db_table == "mlb_batting"


@pytest.mark.django_db
def test_a_season_belongs_to_a_player_in_the_master_table(player: Player) -> None:
    Batting.objects.create(player=player, **SEASON)

    assert player.batting_seasons.count() == 1
    assert player.batting_seasons.get().season == 2004


@pytest.mark.django_db
def test_the_same_player_season_and_stint_cannot_repeat(player: Player) -> None:
    """The natural key: it is what makes re-running the loader safe."""
    Batting.objects.create(player=player, **SEASON)

    with pytest.raises(IntegrityError):
        Batting.objects.create(player=player, **SEASON)


@pytest.mark.django_db
def test_a_player_can_have_several_stints_in_one_season(player: Player) -> None:
    Batting.objects.create(player=player, **{**SEASON, "stint": 1, "team": "KCA"})
    Batting.objects.create(player=player, **{**SEASON, "stint": 2, "team": "ARI"})
    Batting.objects.create(player=player, **{**SEASON, "stint": 3, "team": "XXX", "league": "XX"})

    assert player.batting_seasons.count() == 3


@pytest.mark.django_db
def test_stats_that_did_not_exist_in_an_era_are_null_not_zero(player: Player) -> None:
    """A 1950 season has no swing data; 0 would read as "never swung and missed"."""
    row = Batting.objects.create(player=player, season=1950, stint=1, g=100, ab=350)

    assert row.total_swings is None
    assert row.war is None


def test_only_the_natural_key_is_required() -> None:
    """Everything else is nullable: eras differ in what MLB recorded."""
    required = {
        f.name
        for f in Batting._meta.get_fields()
        if isinstance(f, models.Field) and not f.null and f.name not in {"id", "pk"}
    }

    assert required == {"player", "season", "stint"}


@pytest.mark.django_db
def test_str_reads_like_a_stat_line(player: Player) -> None:
    row = Batting.objects.create(player=player, **SEASON)

    assert str(row) == "Gibson Alba 2004 LAN"
