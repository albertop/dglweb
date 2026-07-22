"""Tests for the per-season pitching download (Fase 3).

The traded-pitcher case is Dámaso Marte 2008 (Pittsburgh then the Yankees), which the source
stores as stint 1 = Pittsburgh (oldest) — the opposite of batting.
"""

from typing import Any

from dglweb.stats.pitching_source import fetch_season, fetch_team_codes

TEAMS = {
    "teams": [
        {"id": 134, "teamCode": "pit", "name": "Pittsburgh Pirates"},
        {"id": 147, "teamCode": "nya", "name": "New York Yankees"},
    ]
}

NL = {"id": 104, "name": "NL"}
AL = {"id": 103, "name": "AL"}


def _split(**kwargs: Any) -> dict[str, Any]:
    return {"season": "2008", **kwargs}


def _bulk(*splits: dict[str, Any]) -> dict[str, Any]:
    return {"stats": [{"splits": list(splits)}]}


def _person(*splits: dict[str, Any]) -> dict[str, Any]:
    return {"people": [{"stats": [{"splits": list(splits)}]}]}


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]) -> None:
        self._responses = responses

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        key = str(params.get("stats") or "")
        if not key and "hydrate" in params:
            key = str(params["hydrate"]).split("type=[")[1].split("]")[0]
        return self._responses.get((path, key), {})


SINGLE = {
    ("/api/v1/teams", ""): TEAMS,
    ("/api/v1/stats", "season"): _bulk(
        _split(
            stat={"G": 70, "IP": "65.0", "ERA": "2.45", "K": 60, "H": 50, "BB": 20, "BF": 260},
            team={"id": 134},
            league=NL,
            player={"id": 150122},
            position={"abbreviation": "P"},
            numTeams=1,
        )
    ),
    ("/api/v1/stats", "seasonAdvanced"): _bulk(_split(stat={"Kp9": "8.3", "Swings": 900}, player={"id": 150122})),
    ("/api/v1/stats", "sabermetrics"): _bulk(_split(stat={"FIP": "3.10", "WAR": "1.4"}, player={"id": 150122})),
}


def test_a_one_team_season_becomes_a_single_row() -> None:
    rows = fetch_season(FakeClient(SINGLE), 2008, {150122})  # type: ignore[arg-type]

    assert len(rows) == 1
    row = rows[0]
    assert (row["player_id"], row["stint"], row["team"], row["league"], row["pos"]) == (
        150122,
        1,
        "PIT",
        "NL",
        "P",
    )


def test_the_three_families_and_derived_land_in_one_row() -> None:
    row = fetch_season(FakeClient(SINGLE), 2008, {150122})[0]  # type: ignore[arg-type]

    assert row["era"] == 2.45  # season (parsed to float)
    assert row["so_per9"] == 8.3  # advanced
    assert row["fip"] == 3.10  # sabermetrics
    assert row["so"] == 60  # K -> so
    assert row["so_per9"] is not None


# --- a traded pitcher: Marte 2008, Pittsburgh (first) then Yankees ---------------------

PIT = _split(stat={"G": 47, "IP": "46.2", "K": 47, "H": 34, "BB": 21, "BF": 190}, team={"id": 134}, league=NL)
NYA = _split(stat={"G": 25, "IP": "18.1", "K": 24, "H": 20, "BB": 8, "BF": 80}, team={"id": 147}, league=AL)
COMBINED = _split(stat={"G": 72, "IP": "65.0", "K": 71, "H": 54, "BB": 29, "BF": 270})  # no team

TRADED = {
    ("/api/v1/teams", ""): TEAMS,
    ("/api/v1/stats", "season"): _bulk(
        _split(
            stat={"G": 72, "IP": "65.0", "K": 71},
            team={"id": 147},
            league=AL,
            player={"id": 150122},
            position={"abbreviation": "P"},
            numTeams=2,
        )
    ),
    ("/api/v1/stats", "seasonAdvanced"): _bulk(_split(stat={"Kp9": "9.8"}, player={"id": 150122})),
    ("/api/v1/stats", "sabermetrics"): _bulk(_split(stat={"WAR": "1.1"}, player={"id": 150122})),
    # Per-player calls: proxy lists oldest-first (Pittsburgh, then Yankees), combined first.
    ("/api/v1/people/150122", "season"): _person(COMBINED, PIT, NYA),
    ("/api/v1/people/150122", "seasonAdvanced"): _person(
        _split(stat={"Kp9": "9.1"}, team={"id": 134}),
        _split(stat={"Kp9": "11.9"}, team={"id": 147}),
    ),
    ("/api/v1/people/150122", "sabermetrics"): _person(
        _split(stat={"WAR": "1.0"}, team={"id": 134}),
        _split(stat={"WAR": "0.1"}, team={"id": 147}),
    ),
}


def test_a_traded_pitcher_keeps_the_proxy_order_oldest_first() -> None:
    """Pitching does NOT reverse: stint 1 is Pittsburgh (the first team), unlike batting."""
    rows = fetch_season(FakeClient(TRADED), 2008, {150122})  # type: ignore[arg-type]

    assert [(r["stint"], r["team"], r["league"]) for r in rows] == [
        (1, "PIT", "NL"),
        (2, "NYA", "AL"),
        (3, "XXX", "XX"),
    ]


def test_the_combined_row_is_the_highest_stint() -> None:
    rows = fetch_season(FakeClient(TRADED), 2008, {150122})  # type: ignore[arg-type]

    total = max(rows, key=lambda r: r["stint"])
    assert (total["team"], total["league"]) == ("XXX", "XX")


def test_each_stint_keeps_its_own_advanced_numbers() -> None:
    rows = fetch_season(FakeClient(TRADED), 2008, {150122})  # type: ignore[arg-type]

    # Oldest-first, so Pittsburgh's advanced numbers come first.
    assert [r["so_per9"] for r in rows] == [9.1, 11.9, 9.8]


def test_team_codes_are_uppercased() -> None:
    codes = fetch_team_codes(FakeClient({("/api/v1/teams", ""): TEAMS}), 2008)  # type: ignore[arg-type]

    assert codes == {134: "PIT", 147: "NYA"}


def test_an_empty_season_returns_nothing() -> None:
    assert fetch_season(FakeClient({}), 1901, {150122}) == []  # type: ignore[arg-type]
