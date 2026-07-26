"""What each stat table shows, declared once.

Before this, every table repeated its column list three times — header, season row, total row — and
each pane repeated it again for the Totales and Postemporada versions. Adding LOB, TotAvg, BsR, G or
AB meant editing five or six blocks by hand, and a column present in the seasons but missing from
the totals only showed up by counting `<th>` against `<td>` in an ad-hoc script.

Here a table is a list of `Column(label, attr, fmt)`. The same list drives the header, the season
lines, the career total, the postseason and the per-team subtotals, so a column can no longer exist
in one of them and not the others.

`attr` doubles as the key for the highlight classes, which is why IP is declared over `outs`: that
is the canonical column, and `innings` renders it in baseball notation.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from dglweb.profiles.templatetags.stats_extras import dec, innings, num, pct, rate


@dataclass(frozen=True)
class Column:
    label: str
    attr: str
    fmt: str = "num"


# Every way a stat is written on this site. `index` is the whole-number scale of wRC+, ERA- and FIP-.
_FORMATS: dict[str, Callable[[Any], str]] = {
    "num": num,
    "rate": rate,
    "index": lambda value: rate(value, 0),
    "dec1": lambda value: dec(value, 1),
    "dec2": lambda value: dec(value, 2),
    "pct": pct,
    "innings": innings,
}


def cells(row: Any, columns: Sequence[Column], leads: Mapping[str, str] | None = None) -> list[dict[str, str]]:  # noqa: ANN401
    """One rendered cell per column: the text to print and the highlight class, if any."""
    marks = leads or {}
    return [
        {"text": _FORMATS[column.fmt](getattr(row, column.attr, None)), "css": marks.get(column.attr, "")}
        for column in columns
    ]


BATTING_STANDARD: list[Column] = [
    Column(label, attr)
    for label, attr in (
        ("G", "g"),
        ("PA", "pa"),
        ("AB", "ab"),
        ("R", "r"),
        ("H", "h"),
        ("2B", "x2b"),
        ("3B", "x3b"),
        ("HR", "hr"),
        ("RBI", "rbi"),
        ("SB", "sb"),
        ("CS", "cs"),
        ("BB", "bb"),
        ("SO", "so"),
        ("HBP", "hbp"),
        ("SH", "sh"),
        ("SF", "sf"),
        ("GIDP", "gidp"),
    )
] + [Column(label, attr, "rate") for label, attr in (("AVG", "avg"), ("OBP", "obp"), ("SLG", "slg"), ("OPS", "ops"))]

BATTING_ADVANCED: list[Column] = [
    Column("TB", "tb"),
    Column("XBH", "xbh"),
    Column("LOB", "lob"),
    Column("RP", "runs_produced"),
    Column("ISO", "iso", "rate"),
    Column("BABIP", "babip", "rate"),
    Column("TotAvg", "total_avg", "rate"),
    Column("EqA", "eq_avg", "rate"),
    Column("GPA", "gross_prod_avg", "rate"),
    Column("wOBA", "woba", "rate"),
    Column("wRC+", "w_rc_plus", "index"),
    Column("wRAA", "w_raa", "dec1"),
    Column("wRC", "w_rc", "dec1"),
    Column("wGDP", "w_gdp", "dec1"),
    Column("wSB", "w_sb", "dec1"),
    Column("UBR", "ubr", "dec1"),
    Column("SPD", "spd", "dec1"),
    Column("RAR", "rar", "dec1"),
    Column("RC", "rc", "dec1"),
    Column("BsR", "bsr", "dec1"),
    Column("WAR", "war", "dec1"),
]

# The batted-ball counts, shared by both groups: the same events, seen from each side of the plate.
_BATTED_BALL: list[Column] = [
    Column(label, attr)
    for label, attr in (
        ("AO", "air_outs"),
        ("GO", "ground_outs"),
        ("FO", "fly_outs"),
        ("PO", "pop_outs"),
        ("LO", "line_outs"),
        ("FH", "fly_hits"),
        ("PH", "pop_hits"),
        ("LH", "line_hits"),
        ("GH", "ground_hits"),
        ("Sw", "total_swings"),
        ("Miss", "swing_and_misses"),
        ("BIP", "balls_in_play"),
    )
]

_COEFFICIENTS: list[Column] = [
    Column("GB%", "gb_pct", "pct"),
    Column("FB%", "fb_pct", "pct"),
    Column("LD%", "ld_pct", "pct"),
    Column("PU%", "pu_pct", "pct"),
    Column("GB/FB", "gb_fb", "dec2"),
    Column("Contact%", "contact_pct", "pct"),
    Column("Whiff%", "whiff_pct", "pct"),
]

BATTING_STATCAST: list[Column] = [Column("G", "g"), Column("AB", "ab"), *_BATTED_BALL]
BATTING_RATIOS: list[Column] = [Column("G", "g"), Column("AB", "ab"), *_COEFFICIENTS]

PITCHING_STANDARD: list[Column] = [
    Column("W", "w"),
    Column("L", "l"),
    Column("W-L%", "win_pct", "rate"),
    Column("ERA", "era", "dec2"),
    Column("G", "g"),
    Column("GS", "gs"),
    Column("GF", "gf"),
    Column("CG", "cg"),
    Column("SHO", "sho"),
    Column("SV", "sv"),
    # El oficio del relevista. Sin estas tres, la temporada 2012 de Rodney se lee "SV=48" y se
    # pierde lo que la hace extraordinaria: 48 de 50 con solo 2 desperdiciados.
    Column("SVO", "save_opp"),
    Column("BSv", "bsv"),
    Column("HLD", "hld"),
    Column("IP", "outs", "innings"),
    Column("H", "h"),
    Column("R", "r"),
    Column("ER", "er"),
    Column("HR", "hr"),
    Column("BB", "bb"),
    Column("IBB", "ibb"),
    Column("SO", "so"),
    Column("HBP", "hbp"),
    Column("WP", "wp"),
    Column("BK", "bk"),
    Column("BF", "bf"),
    Column("WHIP", "whip", "dec2"),
]

PITCHING_ADVANCED: list[Column] = [
    Column("IP", "outs", "innings"),
    Column("BF", "bf"),
    Column("BAA", "baa", "rate"),
    Column("OBP", "obp", "rate"),
    Column("BABIP", "babip", "rate"),
    Column("WHIP", "whip", "dec2"),
    Column("SO/9", "so_per9", "dec2"),
    Column("BB/9", "bb_per9", "dec2"),
    Column("HR/9", "hr_per9", "dec2"),
    Column("H/9", "h_per9", "dec2"),
    Column("R/9", "r_per9", "dec2"),
    Column("SO/BB", "so_to_bb", "dec2"),
    Column("Strike%", "strike_pct", "pct"),
    Column("P/IP", "pitches_per_inning", "dec1"),
    Column("FIP", "fip", "dec2"),
    Column("xFIP", "xfip", "dec2"),
    Column("ERA-", "era_minus", "index"),
    Column("FIP-", "fip_minus", "index"),
    Column("RA9-WAR", "ra9_war", "dec1"),
    Column("RAR", "rar", "dec1"),
    Column("WAR", "war", "dec1"),
]

PITCHING_STATCAST: list[Column] = [Column("G", "g"), Column("IP", "outs", "innings"), *_BATTED_BALL]
PITCHING_RATIOS: list[Column] = [Column("G", "g"), Column("IP", "outs", "innings"), *_COEFFICIENTS]

# Fielding. `Inn` is the canonical `innings_outs` rendered as baseball notation (never the summable
# `innings` float). The position itself is the row prefix, not a stat column.
FIELDING_STANDARD: list[Column] = [
    Column("G", "gp"),
    Column("GS", "gs"),
    Column("Inn", "innings_outs", "innings"),
    Column("PO", "po"),
    Column("A", "a"),
    Column("E", "e"),
    Column("Ch", "chances"),
    Column("DP", "double_plays"),
    Column("Fld%", "fld_pct", "rate"),
    Column("RF/G", "rf_per_g", "dec2"),
]

FIELDING_ADVANCED: list[Column] = [
    Column("Inn", "innings_outs", "innings"),
    Column("Ch", "chances"),
    Column("DP", "double_plays"),
    Column("TP", "triple_plays"),
    Column("ErrT", "throwing_errors"),
    Column("RF/G", "rf_per_g", "dec2"),
    Column("RF/9", "rf_per9", "dec2"),
    Column("UZR", "uzr", "dec1"),
]

# Catcher-only line. Its own pill, shown only when the player caught, so a first baseman is never
# handed a row of dashes.
FIELDING_CATCHER: list[Column] = [
    Column("Inn", "innings_outs", "innings"),
    Column("SB", "stolen_bases"),
    Column("CS", "caught_stealing"),
    Column("CS%", "cs_pct", "pct"),  # atrapados ÷ intentos — el volumen (SB/CS) mezcla staff y turnos
    Column("PB", "passed_balls"),
    Column("WP", "wild_pitches"),
    Column("PkO", "pickoffs"),
    Column("cERA", "catcher_era", "dec2"),
]
