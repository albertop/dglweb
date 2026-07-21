"""Historical MLB statistics for the Dominican subset.

Source of truth: `dbo.mlbBatting` in the owner's SQL Server, produced by his R pipeline from
the MLB stats API. Column names, types and nullability were read from that table — nothing
assumed. Only players present in `dgl_master` are stored here: the website is about Dominicans,
so the master table is the filter, enforced by the foreign key.

**The `stint` rule (verified against all 120 929 source rows, zero exceptions):** a season that
was split between teams gets one row per team *plus* a combined row carrying the sentinel team
`XXX` / league `XX`. The combined row is always the **highest `stint`** of that
`(player, season)`. So:

* the row with the highest `stint` in a season **is that season's total** (for a player who
  never moved, that is simply his only row), and
* summing every row would count split seasons twice.

**Nulls vs zeros.** The source zero-fills what MLB never recorded (`total_swings` only exists
from 1971, `pitches` from 1891). Loading those as 0 would make old players look like they
never swung and would wreck any rate or "fewest" ranking, so they arrive here as NULL. Genuine
zeros stay zero. Same lesson as the `0 -> NULL` sentinels in `dgl_master`.
"""

from django.db import models

from dglweb.players.models import Player


class Batting(models.Model):
    """One batting line: a player's season with one team, or his combined season total."""

    # --- natural key -------------------------------------------------------------
    # A surrogate `id` plus a unique constraint, rather than a composite primary key: it is the
    # boring option every Django tool (admin, snippets, fixtures) already understands.
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="batting_seasons",
        db_column="player_id",
        verbose_name="Jugador",
    )
    season = models.PositiveSmallIntegerField(verbose_name="Temporada")
    stint = models.PositiveSmallIntegerField(
        verbose_name="Etapa",
        help_text="1..n por equipo; la más alta de la temporada es el total combinado (XXX).",
    )

    # --- context -----------------------------------------------------------------
    team = models.CharField(max_length=3, null=True, blank=True, verbose_name="Equipo")
    league = models.CharField(max_length=2, null=True, blank=True, verbose_name="Liga")
    pos = models.CharField(max_length=2, null=True, blank=True, verbose_name="Posición")

    # --- counting stats ----------------------------------------------------------
    g = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="J")
    pa = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="AP")
    ab = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="VB")
    r = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="C")
    h = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="H")
    x1b = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="1B")
    x2b = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="2B")
    x3b = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="3B")
    hr = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HR")
    xbh = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="XBH")
    rbi = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="CI")
    sb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="BR")
    cs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="AR")
    bb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="BB")
    so = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="P")
    ibb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="BBI")
    nibb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="BBNI")
    hbp = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="GP")
    sh = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="TS")
    sf = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="ES")
    gidp = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="DP")
    pitches = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Lanzamientos")
    tb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="TB")
    lob = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="DEB")
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="ICat")

    # --- rate stats --------------------------------------------------------------
    avg = models.FloatField(null=True, blank=True, verbose_name="AVE")
    obp = models.FloatField(null=True, blank=True, verbose_name="OBP")
    slg = models.FloatField(null=True, blank=True, verbose_name="SLG")
    ops = models.FloatField(null=True, blank=True, verbose_name="OPS")
    ab_per_hr = models.FloatField(null=True, blank=True, verbose_name="VB/HR")
    babip = models.FloatField(null=True, blank=True, verbose_name="BABIP")
    bb_per_so = models.FloatField(null=True, blank=True, verbose_name="BB/P")
    bsr = models.FloatField(null=True, blank=True, verbose_name="BsR")
    eq_avg = models.FloatField(null=True, blank=True, verbose_name="EqA")
    gross_prod_avg = models.FloatField(null=True, blank=True, verbose_name="GPA")
    iso = models.FloatField(null=True, blank=True, verbose_name="ISO")
    pa_per_so = models.FloatField(null=True, blank=True, verbose_name="AP/P")
    rc = models.FloatField(null=True, blank=True, verbose_name="RC")
    runs_produced = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="CP")
    total_avg = models.FloatField(null=True, blank=True, verbose_name="TA")

    # --- batted ball / plate discipline (only recorded in the modern era) ---------
    air_outs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="OutsAire")
    ground_outs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="OutsTierra")
    fly_outs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Elevados")
    pop_outs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Palomitas")
    line_outs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="LíneasOut")
    fly_hits = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HitsElevado")
    pop_hits = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HitsPalomita")
    line_hits = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HitsLínea")
    ground_hits = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HitsRodado")
    total_swings = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Swings")
    swing_and_misses = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Fallados")
    balls_in_play = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="EnJuego")
    walk_offs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="WalkOffs")

    # --- sabermetrics ------------------------------------------------------------
    woba = models.FloatField(null=True, blank=True, verbose_name="wOBA")
    w_raa = models.FloatField(null=True, blank=True, verbose_name="wRAA")
    w_rc = models.FloatField(null=True, blank=True, verbose_name="wRC")
    w_rc_plus = models.FloatField(null=True, blank=True, verbose_name="wRC+")
    rar = models.FloatField(null=True, blank=True, verbose_name="RAR")
    war = models.FloatField(null=True, blank=True, verbose_name="WAR")
    ubr = models.FloatField(null=True, blank=True, verbose_name="UBR")
    w_gdp = models.FloatField(null=True, blank=True, verbose_name="wGDP")
    w_sb = models.FloatField(null=True, blank=True, verbose_name="wSB")
    spd = models.FloatField(null=True, blank=True, verbose_name="SPD")
    positional_adj = models.FloatField(null=True, blank=True, verbose_name="Ajuste posicional")
    w_league = models.FloatField(null=True, blank=True, verbose_name="wLiga")
    batting = models.FloatField(null=True, blank=True, verbose_name="Bateo")
    fielding = models.FloatField(null=True, blank=True, verbose_name="Defensa")
    base_running = models.FloatField(null=True, blank=True, verbose_name="Corrido")
    replacement = models.FloatField(null=True, blank=True, verbose_name="Reemplazo")

    class Meta:
        db_table = "mlb_batting"
        ordering = ["player", "season", "stint"]
        verbose_name = "línea de bateo"
        verbose_name_plural = "líneas de bateo"
        constraints = [
            models.UniqueConstraint(
                fields=["player", "season", "stint"],
                name="unique_batting_line",
            )
        ]
        indexes = [
            # Season leaderboards and "who played in year X" scan by season.
            models.Index(fields=["season"], name="mlb_batting_season_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.team or ''}".strip()
