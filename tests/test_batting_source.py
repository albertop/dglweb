"""Tests for the per-season batting download (Fase 3).

The payload shapes below are trimmed copies of real proxy responses: the traded-player case
is Randal Grichuk's 2025 (Kansas City then Arizona), which is also the row the owner's table
stores as stint 1 / stint 2 / XXX.
"""

from typing import Any

from dglweb.stats.batting_source import fetch_season, fetch_team_codes

TEAMS = {
    "teams": [
        {"id": 118, "teamCode": "kca", "name": "Kansas City Royals"},
        {"id": 109, "teamCode": "ari", "name": "Arizona Diamondbacks"},
        {"id": 119, "teamCode": "lan", "name": "Los Angeles Dodgers"},
    ]
}

NL = {"id": 104, "name": "NL"}
AL = {"id": 103, "name": "AL"}


def _split(**kwargs: Any) -> dict[str, Any]:
    return {"season": "2025", **kwargs}


def _bulk(*splits: dict[str, Any]) -> dict[str, Any]:
    return {"stats": [{"splits": list(splits)}]}


def _person(*splits: dict[str, Any]) -> dict[str, Any]:
    return {"people": [{"stats": [{"splits": list(splits)}]}]}


class FakeClient:
    """Answers like the proxy, and records what was asked."""

    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        # Bulk calls are keyed by their stat type; per-player calls by the hydrate's type.
        key = str(params.get("stats") or "")
        if not key and "hydrate" in params:
            key = str(params["hydrate"]).split("type=[")[1].split("]")[0]
        self.calls.append((path, key))
        return self._responses.get((path, key), {})


# --- a plain, one-team season ---------------------------------------------------------

SINGLE = {
    ("/api/v1/teams", ""): TEAMS,
    ("/api/v1/stats", "season"): _bulk(
        _split(
            stat={"G": 156, "AB": 598, "H": 200, "X2B": 32, "X3B": 0, "HR": 48, "BB": 53, "IBB": 3},
            team={"id": 119},
            league=NL,
            player={"id": 134181},
            position={"abbreviation": "3B"},
            numTeams=1,
        )
    ),
    ("/api/v1/stats", "seasonAdvanced"): _bulk(_split(stat={"Swings": 2400, "SwingMiss": 300}, player={"id": 134181})),
    ("/api/v1/stats", "sabermetrics"): _bulk(_split(stat={"WAR": 9.67698, "wRCPlus": 161.043}, player={"id": 134181})),
}


def test_a_one_team_season_becomes_a_single_row() -> None:
    client = FakeClient(SINGLE)

    rows = fetch_season(client, 2025, {134181})  # type: ignore[arg-type]

    assert len(rows) == 1
    row = rows[0]
    assert (row["player_id"], row["season"], row["stint"]) == (134181, 2025, 1)
    assert (row["team"], row["league"], row["pos"]) == ("LAN", "NL", "3B")


def test_the_three_stat_families_land_in_one_row() -> None:
    rows = fetch_season(FakeClient(SINGLE), 2025, {134181})  # type: ignore[arg-type]

    assert rows[0]["hr"] == 48  # season
    assert rows[0]["total_swings"] == 2400  # seasonAdvanced
    assert rows[0]["war"] == 9.67698  # sabermetrics
    assert rows[0]["x1b"] == 200 - 32 - 0 - 48  # derived


def test_players_outside_the_master_table_are_ignored() -> None:
    """The website is only about Dominicans; the bulk call returns all of MLB."""
    rows = fetch_season(FakeClient(SINGLE), 2025, {999999})  # type: ignore[arg-type]

    assert rows == []


def test_a_one_team_season_costs_no_extra_calls() -> None:
    client = FakeClient(SINGLE)

    fetch_season(client, 2025, {134181})  # type: ignore[arg-type]

    assert [path for path, _ in client.calls] == ["/api/v1/teams"] + ["/api/v1/stats"] * 3


# --- a traded player ------------------------------------------------------------------

KC = _split(stat={"G": 43, "AB": 97, "H": 20, "HR": 2}, team={"id": 118}, league=AL)
ARI = _split(stat={"G": 70, "AB": 175, "H": 42, "HR": 7}, team={"id": 109}, league=NL)
COMBINED = _split(stat={"G": 113, "AB": 272, "H": 62, "HR": 9})  # no team: the season total

TRADED = {
    ("/api/v1/teams", ""): TEAMS,
    ("/api/v1/stats", "season"): _bulk(
        _split(
            stat={"G": 113, "AB": 272, "H": 62, "HR": 9},
            team={"id": 109},
            league=NL,
            player={"id": 545341},
            position={"abbreviation": "RF"},
            numTeams=2,
        )
    ),
    ("/api/v1/stats", "seasonAdvanced"): _bulk(_split(stat={"Swings": 1000}, player={"id": 545341})),
    ("/api/v1/stats", "sabermetrics"): _bulk(_split(stat={"WAR": 1.5}, player={"id": 545341})),
    # Per-player calls: newest first, combined row first, exactly as the proxy answers.
    ("/api/v1/people/545341", "season"): _person(COMBINED, ARI, KC),
    ("/api/v1/people/545341", "seasonAdvanced"): _person(
        _split(stat={"Swings": 400}, team={"id": 109}),
        _split(stat={"Swings": 600}, team={"id": 118}),
    ),
    ("/api/v1/people/545341", "sabermetrics"): _person(
        _split(stat={"WAR": 1.1}, team={"id": 109}),
        _split(stat={"WAR": 0.4}, team={"id": 118}),
    ),
}


def test_a_traded_player_gets_one_row_per_team_plus_the_combined_row() -> None:
    rows = fetch_season(FakeClient(TRADED), 2025, {545341})  # type: ignore[arg-type]

    assert [(r["stint"], r["team"], r["g"]) for r in rows] == [
        (1, "KCA", 43),
        (2, "ARI", 70),
        (3, "XXX", 113),
    ]


def test_the_stints_are_chronological_not_as_the_proxy_returns_them() -> None:
    """The proxy answers newest first; the source table numbers them oldest first."""
    rows = fetch_season(FakeClient(TRADED), 2025, {545341})  # type: ignore[arg-type]

    assert rows[0]["league"] == "AL"  # Kansas City came first
    assert rows[1]["league"] == "NL"


def test_the_combined_row_is_the_highest_stint_and_carries_the_sentinels() -> None:
    """The rule the Líderes will depend on: highest stint = that season's total."""
    rows = fetch_season(FakeClient(TRADED), 2025, {545341})  # type: ignore[arg-type]

    total = max(rows, key=lambda r: r["stint"])
    assert (total["team"], total["league"]) == ("XXX", "XX")
    assert total["g"] == sum(r["g"] for r in rows if r["team"] != "XXX")


def test_each_stint_keeps_its_own_advanced_and_sabermetric_numbers() -> None:
    rows = fetch_season(FakeClient(TRADED), 2025, {545341})  # type: ignore[arg-type]

    assert [r["total_swings"] for r in rows] == [600, 400, 1000]
    assert [r["war"] for r in rows] == [0.4, 1.1, 1.5]


# --- teams and degradation -------------------------------------------------------------


def test_team_codes_are_uppercased_by_id() -> None:
    codes = fetch_team_codes(FakeClient({("/api/v1/teams", ""): TEAMS}), 2025)  # type: ignore[arg-type]

    assert codes == {118: "KCA", 109: "ARI", 119: "LAN"}


def test_an_empty_season_returns_nothing_instead_of_crashing() -> None:
    """A season the upstream has no data for must be a no-op, not an exception."""
    rows = fetch_season(FakeClient({}), 1876, {134181})  # type: ignore[arg-type]

    assert rows == []
