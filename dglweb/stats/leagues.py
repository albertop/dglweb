"""League and team codes, ported from the owner's R pipeline.

The two-letter codes are a straight port of the `CASE` in his script (what feeds
`mlbTeams`/`mlbLeagues`), so loaded rows match `dbo.mlbBatting` exactly.

**Match on the league id, not the name.** MLB spells the same league three ways depending on
the endpoint: `/league` gives "Negro National League (II)", the stats splits give the
abbreviation "NN2", and none of those is the owner's "N2". The numeric id (431) is the one
stable identifier, so it is the primary key here and the text is only a fallback. This matters
concretely: seven Dominicans in the master table played in these leagues, and matching by name
would have filed all 22 of their seasons under "unknown".

An unrecognised league becomes `??` rather than NULL or a dropped row — a visible gap beats a
silent one.
"""

from typing import Any

# Combined-season sentinels: a season split across teams gets one extra row with the totals.
COMBINED_TEAM = "XXX"
COMBINED_LEAGUE = "XX"

UNKNOWN_LEAGUE = "??"

# MLB league id -> the owner's code. Ids read from /api/v1/league?sportId=1.
_CODE_BY_ID = {
    103: "AL",  # American League
    104: "NL",  # National League
    100: "AA",  # American Association
    101: "UA",  # Union Association
    105: "PL",  # Players League
    106: "FL",  # Federal League
    426: "AN",  # American Negro League
    427: "EN",  # Eastern Colored League
    428: "NA",  # Negro American League
    429: "EW",  # Negro East West League
    430: "N1",  # Negro National League (I)
    431: "N2",  # Negro National League (II)
    432: "SL",  # Negro Southern League
}

# Fallback for when a payload carries no id: full names, MLB abbreviations, and our own codes.
_CODE_BY_TEXT = {
    "American League": "AL",
    "AL": "AL",
    "National League": "NL",
    "NL": "NL",
    "American Association": "AA",
    "AA": "AA",
    "Union Association": "UA",
    "UA": "UA",
    "Players League": "PL",
    "PL": "PL",
    "Federal League": "FL",
    "FL": "FL",
    "American Negro League": "AN",
    "ANL": "AN",
    "AN": "AN",
    "Eastern Colored League": "EN",
    "ECL": "EN",
    "EN": "EN",
    "Negro American League": "NA",
    "NAL": "NA",
    "NA": "NA",
    "Negro East West League": "EW",
    "EWL": "EW",
    "EW": "EW",
    "Negro National League (I)": "N1",
    "NNL": "N1",
    "N1": "N1",
    "Negro National League (II)": "N2",
    "NN2": "N2",
    "N2": "N2",
    "Negro Southern League": "SL",
    "NSL": "SL",
    "SL": "SL",
}


def league_code(league: dict[str, Any] | None) -> str:
    """Two-letter code for a proxy `league` object, or `??` when unrecognised."""
    if not league:
        return UNKNOWN_LEAGUE

    league_id = league.get("id")
    if isinstance(league_id, int):
        by_id = _CODE_BY_ID.get(league_id)
        if by_id:
            return by_id

    text = (league.get("abbreviation") or league.get("name") or "").strip()
    return _CODE_BY_TEXT.get(text, UNKNOWN_LEAGUE)


def team_code(code: str | None) -> str | None:
    """MLB's `teamCode` ("kca") is stored uppercase ("KCA"), as in the source table."""
    return code.strip().upper() if code else None
