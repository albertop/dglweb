"""Fetch one season of pitching from the proxy and shape it into `Pitching` rows.

Uses the shared download machinery (`dglweb/stats/_download.py`); the pitching specifics are the
`pitching` group, **oldest-first stint numbering** (unlike batting — verified against a traded
pitcher in the source), and how the columns are built: the rate lines come straight from the
proxy (parsed to float), with only `X1B`, `NIBB` and `BAA` derived.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import SportConfig
from dglweb.stats._download import fetch_season as _fetch_season
from dglweb.stats._download import fetch_team_codes as fetch_team_codes  # re-exported
from dglweb.stats.pitching_mapping import (
    derive_pitching,
    map_advanced,
    map_regular,
    map_sabermetrics,
)


def _build_stats(regular: dict[str, Any], advanced: dict[str, Any], sabermetrics: dict[str, Any]) -> dict[str, Any]:
    counts = {**map_regular(regular), **map_advanced(advanced)}
    return {**counts, **derive_pitching(counts), **map_sabermetrics(sabermetrics)}


CONFIG = SportConfig(group="pitching", reverse_stints=False, build_stats=_build_stats)


def fetch_season(client: MlbProxyClient, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
    """Every pitching row of `season` for the given players, ready for `Pitching(**row)`."""
    return _fetch_season(client, season, player_ids, CONFIG)
