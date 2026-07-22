"""Fetch one season of batting from the proxy and shape it into `Batting` rows.

The download machinery is shared (`dglweb/stats/_download.py`); this module only supplies the
batting specifics: the `hitting` group, newest-first stint numbering (the batting R script
reverses, verified against a traded batter in the source), and how the three stat families become
columns — with the rate stats *computed* from the counts, not taken from the proxy's strings.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import SportConfig
from dglweb.stats._download import fetch_season as _fetch_season
from dglweb.stats._download import fetch_team_codes as fetch_team_codes  # re-exported
from dglweb.stats.derive import derived_rates
from dglweb.stats.mapping import map_advanced, map_regular, map_sabermetrics


def _build_stats(regular: dict[str, Any], advanced: dict[str, Any], sabermetrics: dict[str, Any]) -> dict[str, Any]:
    counts = {**map_regular(regular), **map_advanced(advanced)}
    return {**counts, **derived_rates(counts), **map_sabermetrics(sabermetrics)}


CONFIG = SportConfig(group="hitting", reverse_stints=True, build_stats=_build_stats)


def fetch_season(client: MlbProxyClient, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
    """Every batting row of `season` for the given players, ready for `Batting(**row)`."""
    return _fetch_season(client, season, player_ids, CONFIG)
