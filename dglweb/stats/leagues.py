"""League and team codes, ported from the owner's R pipeline.

The two-letter league codes are a straight port of the `CASE` in his script (the mapping that
feeds `mlbTeams`/`mlbLeagues`), so the loaded rows match `dbo.mlbBatting` exactly. Unknown
leagues become `??` there, and they do here — silently dropping the row would hide a real gap.

MLB returns the short name ("NL") for modern leagues and the full name ("Negro National League
(II)") for historical ones, so both spellings map to the same code.
"""

# Combined-season sentinels: a season split across teams gets one extra row carrying the totals.
COMBINED_TEAM = "XXX"
COMBINED_LEAGUE = "XX"

UNKNOWN_LEAGUE = "??"

_LEAGUE_CODES = {
    "American Association": "AA",
    "American League": "AL",
    "American Negro League": "AN",
    "Eastern Colored League": "EN",
    "Federal League": "FL",
    "National League": "NL",
    "Negro American League": "NA",
    "Negro East West League": "EW",
    "Negro National League (I)": "N1",
    "Negro National League (II)": "N2",
    "Negro Southern League": "SL",
    "Players League": "PL",
    "Union Association": "UA",
}

# MLB sends "AL"/"NL" directly in modern season splits.
_LEAGUE_CODES.update({code: code for code in _LEAGUE_CODES.values()})


def league_code(name: str | None) -> str:
    """Two-letter code for a league name, or `??` when we do not recognise it."""
    if not name:
        return UNKNOWN_LEAGUE
    return _LEAGUE_CODES.get(name.strip(), UNKNOWN_LEAGUE)


def team_code(code: str | None) -> str | None:
    """MLB's `teamCode` ("kca") is stored uppercase ("KCA"), as in the source table."""
    return code.strip().upper() if code else None
