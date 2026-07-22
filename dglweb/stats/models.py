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

from datetime import timedelta
from typing import TypeVar

from django.db import models
from django.db.models import Exists, OuterRef, Q

from dglweb.players.models import Player

_M = TypeVar("_M", bound=models.Model)


class SeasonTotalsQuerySet(models.QuerySet[_M]):
    """Rows that are a season total, never a per-team breakdown — the base for leaders.

    A traded player's season is stored as one row per team **plus** a `team="XXX"` total. Summing
    every row would double-count him (Manny, Soto, Cruz…), so leaders must start here: keep the
    `XXX` row when it exists, and the single row when it does not.
    """

    def season_totals(self) -> "SeasonTotalsQuerySet[_M]":
        combined = self.model._default_manager.filter(player=OuterRef("player"), season=OuterRef("season"), team="XXX")
        return self.filter(Q(team="XXX") | ~Exists(combined))


class FieldingTotalsQuerySet(models.QuerySet[_M]):
    """Like `SeasonTotalsQuerySet` but per position: fielding's total is per (player, season, pos)."""

    def position_totals(self) -> "FieldingTotalsQuerySet[_M]":
        combined = self.model._default_manager.filter(
            player=OuterRef("player"), season=OuterRef("season"), pos=OuterRef("pos"), team="XXX"
        )
        return self.filter(Q(team="XXX") | ~Exists(combined))


class Batting(models.Model):
    """One batting line: a player's season with one team, or his combined season total."""

    objects = SeasonTotalsQuerySet.as_manager()

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

    # --- extra fields the proxy offers beyond the source table (raw, not derivable) ----------
    age = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Edad")
    roe = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="EmbErr")  # reached on error
    gidp_opp = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="OportDP")

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


class IngestRun(models.Model):
    """One execution of a scraper command — the pipeline's flight recorder.

    Generic on purpose: batting is the first user, but pitching, fielding and the roster scrapers
    write the same rows. Without this, a command that has been failing every night for weeks looks
    exactly like one that is working. A row is written on entry (RUNNING) so a hung run is visible
    too, and `record_run` (dglweb/stats/runlog.py) closes it out.
    """

    class Status(models.TextChoices):
        RUNNING = "running", "En curso"
        SUCCESS = "success", "Éxito"
        PARTIAL = "partial", "Parcial"
        FAILED = "failed", "Falló"

    command = models.CharField(max_length=50, verbose_name="Comando")
    scope = models.CharField(max_length=100, blank=True, verbose_name="Alcance")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING, verbose_name="Estado")
    started_at = models.DateTimeField(verbose_name="Inicio")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Fin")
    rows_affected = models.PositiveIntegerField(default=0, verbose_name="Filas")
    detail = models.TextField(blank=True, verbose_name="Detalle")

    class Meta:
        db_table = "ingest_run"
        ordering = ["-started_at"]
        verbose_name = "ejecución"
        verbose_name_plural = "ejecuciones"
        # A flight recorder is written by the scrapers, never by hand: only "view" exists, so no
        # add/edit/delete permission is created and the backoffice shows it read-only.
        default_permissions = ("view",)

    def __str__(self) -> str:
        return f"{self.command} [{self.scope}] {self.status}"

    @property
    def duration(self) -> timedelta | None:
        if self.finished_at is None:
            return None
        return self.finished_at - self.started_at


class Pitching(models.Model):
    """One pitching line: a player's season with one team, or his combined season total.

    Same shape and rules as `Batting` (source `dbo.mlbPitching`, 101 columns, natural key
    (player, season, stint), the `XXX` combined-row sentinel, NULL-over-0 for eras MLB never
    recorded). One thing differs and it is verified against the source: **stints are numbered as
    the proxy lists them — stint 1 is the oldest team**, the opposite of batting, because the
    owner's pitching script numbers them ascending while the batting one reverses.

    Columns are standard pitching abbreviations, so unlike `Batting` (which has an admin CRUD)
    this table carries no per-field Spanish labels — it is written by the scraper and read on
    pages, never edited by hand.
    """

    objects = SeasonTotalsQuerySet.as_manager()

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="pitching_seasons", db_column="player_id")
    season = models.PositiveSmallIntegerField()
    stint = models.PositiveSmallIntegerField()

    team = models.CharField(max_length=3, null=True, blank=True)
    league = models.CharField(max_length=2, null=True, blank=True)
    pos = models.CharField(max_length=2, null=True, blank=True)

    # --- record / appearances ----------------------------------------------------
    w = models.PositiveSmallIntegerField(null=True, blank=True)
    l = models.PositiveSmallIntegerField(null=True, blank=True)  # noqa: E741 (source column name)
    g = models.PositiveSmallIntegerField(null=True, blank=True)
    gp = models.PositiveSmallIntegerField(null=True, blank=True)
    gs = models.PositiveSmallIntegerField(null=True, blank=True)
    gf = models.PositiveSmallIntegerField(null=True, blank=True)
    cg = models.PositiveSmallIntegerField(null=True, blank=True)
    sho = models.PositiveSmallIntegerField(null=True, blank=True)
    sv = models.PositiveSmallIntegerField(null=True, blank=True)
    bsv = models.PositiveSmallIntegerField(null=True, blank=True)
    hld = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- runs allowed / basics ---------------------------------------------------
    # `ip` is baseball notation (46.2 = 46⅔) — display/parity only, NEVER aggregate it. For any
    # sum or rate use `outs` (below), the proxy's canonical out count: innings = outs / 3.
    ip = models.FloatField(null=True, blank=True, help_text="Entradas en notación de béisbol (46.2 = 46⅔).")
    h = models.PositiveSmallIntegerField(null=True, blank=True)
    r = models.PositiveSmallIntegerField(null=True, blank=True)
    hr = models.PositiveSmallIntegerField(null=True, blank=True)
    er = models.PositiveSmallIntegerField(null=True, blank=True)
    era = models.FloatField(null=True, blank=True)
    bb = models.PositiveSmallIntegerField(null=True, blank=True)
    ibb = models.PositiveSmallIntegerField(null=True, blank=True)
    so = models.PositiveSmallIntegerField(null=True, blank=True)
    hbp = models.PositiveSmallIntegerField(null=True, blank=True)
    wp = models.PositiveSmallIntegerField(null=True, blank=True)
    bk = models.PositiveSmallIntegerField(null=True, blank=True)
    bf = models.PositiveSmallIntegerField(null=True, blank=True)
    x2b = models.PositiveSmallIntegerField(null=True, blank=True)
    x3b = models.PositiveSmallIntegerField(null=True, blank=True)
    x1b = models.PositiveSmallIntegerField(null=True, blank=True)
    nibb = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- opponent rate lines (direct from the proxy) -----------------------------
    avg = models.FloatField(null=True, blank=True)
    obp = models.FloatField(null=True, blank=True)
    slg = models.FloatField(null=True, blank=True)
    ops = models.FloatField(null=True, blank=True)
    cs = models.PositiveSmallIntegerField(null=True, blank=True)
    sb = models.PositiveSmallIntegerField(null=True, blank=True)
    sb_pct = models.FloatField(null=True, blank=True)
    gidp = models.PositiveSmallIntegerField(null=True, blank=True)
    pitches = models.PositiveSmallIntegerField(null=True, blank=True)
    save_opp = models.PositiveSmallIntegerField(null=True, blank=True)
    outs = models.PositiveSmallIntegerField(null=True, blank=True)
    ground_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    air_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    strikes = models.PositiveSmallIntegerField(null=True, blank=True)
    strike_pct = models.FloatField(null=True, blank=True)
    inherit_runners = models.PositiveSmallIntegerField(null=True, blank=True)
    inherit_runners_scored = models.PositiveSmallIntegerField(null=True, blank=True)
    sh = models.PositiveSmallIntegerField(null=True, blank=True)
    sf = models.PositiveSmallIntegerField(null=True, blank=True)
    pickoffs = models.PositiveSmallIntegerField(null=True, blank=True)
    tb = models.PositiveSmallIntegerField(null=True, blank=True)
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True)
    baa = models.FloatField(null=True, blank=True, help_text="Promedio de bateo en contra (fórmula mlbstats).")
    whip = models.FloatField(null=True, blank=True)
    win_pct = models.FloatField(null=True, blank=True)
    r_per9 = models.FloatField(null=True, blank=True)

    # --- advanced ----------------------------------------------------------------
    runs_scored_per9 = models.FloatField(null=True, blank=True)
    babip = models.FloatField(null=True, blank=True)
    so_per9 = models.FloatField(null=True, blank=True)
    bb_per9 = models.FloatField(null=True, blank=True)
    hr_per9 = models.FloatField(null=True, blank=True)
    h_per9 = models.FloatField(null=True, blank=True)
    so_to_bb = models.FloatField(null=True, blank=True)
    bequeathed_runners = models.PositiveSmallIntegerField(null=True, blank=True)
    bequeathed_runners_scored = models.PositiveSmallIntegerField(null=True, blank=True)
    quality_starts = models.PositiveSmallIntegerField(null=True, blank=True)
    gidp_opp = models.PositiveSmallIntegerField(null=True, blank=True)
    total_swings = models.PositiveSmallIntegerField(null=True, blank=True)
    swing_and_misses = models.PositiveSmallIntegerField(null=True, blank=True)
    balls_in_play = models.PositiveSmallIntegerField(null=True, blank=True)
    run_support = models.PositiveSmallIntegerField(null=True, blank=True)
    pitches_per_inning = models.FloatField(null=True, blank=True)
    pitches_per_pa = models.FloatField(null=True, blank=True)
    walks_per_pa = models.FloatField(null=True, blank=True)
    so_per_pa = models.FloatField(null=True, blank=True)
    bb_per_so = models.FloatField(null=True, blank=True)
    iso = models.FloatField(null=True, blank=True)
    fly_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    line_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    fly_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    line_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    ground_hits = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- sabermetrics ------------------------------------------------------------
    fip = models.FloatField(null=True, blank=True)
    xfip = models.FloatField(null=True, blank=True)
    fip_minus = models.FloatField(null=True, blank=True)
    ra9_war = models.FloatField(null=True, blank=True)
    rar = models.FloatField(null=True, blank=True)
    war = models.FloatField(null=True, blank=True)
    sd = models.PositiveSmallIntegerField(null=True, blank=True)
    md = models.PositiveSmallIntegerField(null=True, blank=True)
    p_li = models.FloatField(null=True, blank=True)
    in_li = models.FloatField(null=True, blank=True)
    gm_li = models.FloatField(null=True, blank=True)
    ex_li = models.FloatField(null=True, blank=True)
    era_minus = models.FloatField(null=True, blank=True)

    # --- extra fields the proxy offers beyond the source table (raw, not derivable) ----------
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    ab = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Turnos al bate en contra.")
    sh_fail = models.PositiveSmallIntegerField(null=True, blank=True)
    sh_missed = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mlb_pitching"
        ordering = ["player", "season", "stint"]
        verbose_name = "línea de pitcheo"
        verbose_name_plural = "líneas de pitcheo"
        constraints = [models.UniqueConstraint(fields=["player", "season", "stint"], name="unique_pitching_line")]
        indexes = [models.Index(fields=["season"], name="mlb_pitching_season_idx")]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.team or ''}".strip()


class Fielding(models.Model):
    """One fielding line: a player's season at one position, with one team or combined (XXX).

    Fielding is per **position**, not per team, so the natural key is
    **(player, season, team, pos)** — not the (player, season, stint) of batting/pitching. The
    owner's source table keys on a fragile `stint` counter that also carries ~178 exact-duplicate
    rows; we drop the counter and key on what actually identifies a line (owner's decision). For a
    player who was traded, each position has one row per team plus a combined row with `team=XXX`
    (the season total at that position), exactly as the proxy returns it.

    Source `dbo.mlbFielding`. No mlbstats formulas here — every value comes straight from the
    proxy (fielding % included); `UZR` comes from the fielding sabermetrics and lands only on the
    season-total row of each position. Same NULL-over-0 rule as the other tables.
    """

    objects = FieldingTotalsQuerySet.as_manager()

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="fielding_seasons", db_column="player_id")
    season = models.PositiveSmallIntegerField()
    team = models.CharField(max_length=3, help_text="Código del equipo, o XXX para el total de la posición.")
    league = models.CharField(max_length=2, null=True, blank=True)
    pos = models.CharField(max_length=2, verbose_name="Posición")

    gp = models.PositiveSmallIntegerField(null=True, blank=True)
    gs = models.PositiveSmallIntegerField(null=True, blank=True)
    a = models.PositiveSmallIntegerField(null=True, blank=True)
    po = models.PositiveSmallIntegerField(null=True, blank=True)
    e = models.PositiveSmallIntegerField(null=True, blank=True)
    chances = models.PositiveSmallIntegerField(null=True, blank=True)
    fld_pct = models.FloatField(null=True, blank=True)
    rf_per_g = models.FloatField(null=True, blank=True)
    rf_per9 = models.FloatField(null=True, blank=True)
    innings = models.FloatField(null=True, blank=True, help_text="Entradas en notación de béisbol (111.1 = 111⅓).")
    # Canonical, additive form of `innings`. NEVER aggregate `innings` (baseball notation: .1/.2
    # are OUTS, not decimals, so 0.2 + 0.2 != 0.4); sum `innings_outs` and divide by 3 for display.
    innings_outs = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Entradas en outs (sumable).")
    double_plays = models.PositiveSmallIntegerField(null=True, blank=True)
    triple_plays = models.PositiveSmallIntegerField(null=True, blank=True)
    throwing_errors = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- catcher-only ------------------------------------------------------------
    passed_balls = models.PositiveSmallIntegerField(null=True, blank=True)
    catcher_era = models.FloatField(null=True, blank=True)
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True)
    wild_pitches = models.PositiveSmallIntegerField(null=True, blank=True)
    pickoffs = models.PositiveSmallIntegerField(null=True, blank=True)
    stolen_bases = models.PositiveSmallIntegerField(null=True, blank=True)
    caught_stealing = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- sabermetrics (season total per position only) ---------------------------
    uzr = models.FloatField(null=True, blank=True, verbose_name="UZR")

    # --- extra the proxy offers beyond the source table --------------------------
    age = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mlb_fielding"
        ordering = ["player", "season", "pos", "team"]
        verbose_name = "línea de fildeo"
        verbose_name_plural = "líneas de fildeo"
        constraints = [models.UniqueConstraint(fields=["player", "season", "team", "pos"], name="unique_fielding_line")]
        indexes = [models.Index(fields=["season"], name="mlb_fielding_season_idx")]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.pos} {self.team}".strip()


class BattingPost(models.Model):
    """One postseason batting line: a player's stats in one round of one season.

    Source `dbo.mlbBattingPost` (59 columns). Keyed by **round**, not stint:
    **(player, season, round)** with round in {DS, WC, LCS, WS}. A player is on one team per round,
    so there is no `XXX` combined row and no per-team stints (the whole traded-player machinery of
    `Batting` is absent here). The owner's post script uses only `season` + `seasonAdvanced`, so
    there is **no sabermetrics block** — the columns are the counts, the derived rates (the same
    15 `mlbstats` formulas as regular batting) and the batted-ball stats. Same NULL-over-0 rule.
    """

    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="batting_post_seasons", db_column="player_id"
    )
    season = models.PositiveSmallIntegerField()
    round = models.CharField(max_length=3, help_text="DS, WC, LCS o WS.")

    team = models.CharField(max_length=3, null=True, blank=True)
    league = models.CharField(max_length=2, null=True, blank=True)
    pos = models.CharField(max_length=2, null=True, blank=True)

    # --- counting stats ----------------------------------------------------------
    g = models.PositiveSmallIntegerField(null=True, blank=True)
    pa = models.PositiveSmallIntegerField(null=True, blank=True)
    ab = models.PositiveSmallIntegerField(null=True, blank=True)
    r = models.PositiveSmallIntegerField(null=True, blank=True)
    h = models.PositiveSmallIntegerField(null=True, blank=True)
    x1b = models.PositiveSmallIntegerField(null=True, blank=True)
    x2b = models.PositiveSmallIntegerField(null=True, blank=True)
    x3b = models.PositiveSmallIntegerField(null=True, blank=True)
    hr = models.PositiveSmallIntegerField(null=True, blank=True)
    xbh = models.PositiveSmallIntegerField(null=True, blank=True)
    rbi = models.PositiveSmallIntegerField(null=True, blank=True)
    sb = models.PositiveSmallIntegerField(null=True, blank=True)
    cs = models.PositiveSmallIntegerField(null=True, blank=True)
    bb = models.PositiveSmallIntegerField(null=True, blank=True)
    so = models.PositiveSmallIntegerField(null=True, blank=True)
    ibb = models.PositiveSmallIntegerField(null=True, blank=True)
    nibb = models.PositiveSmallIntegerField(null=True, blank=True)
    hbp = models.PositiveSmallIntegerField(null=True, blank=True)
    sh = models.PositiveSmallIntegerField(null=True, blank=True)
    sf = models.PositiveSmallIntegerField(null=True, blank=True)
    gidp = models.PositiveSmallIntegerField(null=True, blank=True)
    pitches = models.PositiveSmallIntegerField(null=True, blank=True)
    tb = models.PositiveSmallIntegerField(null=True, blank=True)
    lob = models.PositiveSmallIntegerField(null=True, blank=True)
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True)

    # --- derived rates (same mlbstats formulas as regular batting) ----------------
    avg = models.FloatField(null=True, blank=True)
    obp = models.FloatField(null=True, blank=True)
    slg = models.FloatField(null=True, blank=True)
    ops = models.FloatField(null=True, blank=True)
    ab_per_hr = models.FloatField(null=True, blank=True)
    babip = models.FloatField(null=True, blank=True)
    bb_per_so = models.FloatField(null=True, blank=True)
    bsr = models.FloatField(null=True, blank=True)
    eq_avg = models.FloatField(null=True, blank=True)
    gross_prod_avg = models.FloatField(null=True, blank=True)
    iso = models.FloatField(null=True, blank=True)
    pa_per_so = models.FloatField(null=True, blank=True)
    rc = models.FloatField(null=True, blank=True)
    runs_produced = models.PositiveSmallIntegerField(null=True, blank=True)
    total_avg = models.FloatField(null=True, blank=True)

    # --- batted ball --------------------------------------------------------------
    air_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    ground_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    fly_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    line_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    fly_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    line_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    ground_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    total_swings = models.PositiveSmallIntegerField(null=True, blank=True)
    swing_and_misses = models.PositiveSmallIntegerField(null=True, blank=True)
    balls_in_play = models.PositiveSmallIntegerField(null=True, blank=True)
    walk_offs = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mlb_batting_post"
        ordering = ["player", "season", "round"]
        verbose_name = "línea de bateo (postemporada)"
        verbose_name_plural = "líneas de bateo (postemporada)"
        constraints = [models.UniqueConstraint(fields=["player", "season", "round"], name="unique_batting_post_line")]
        indexes = [models.Index(fields=["season"], name="mlb_batting_post_season_idx")]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.round} {self.team or ''}".strip()


class PitchingPost(models.Model):
    """One postseason pitching line: a player's stats in one round of one season.

    Source `dbo.mlbPitchingPost` (88 columns). Keyed by round like `BattingPost`; the regular +
    advanced pitching columns, **no sabermetrics** (the FIP/WAR block the post script does not
    fetch) and no extras (age/ab/sh_*). `BAA` is the one mlbstats formula, reused from regular
    pitching. `ip` is baseball notation (display/parity only) — aggregate `outs` instead.
    """

    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="pitching_post_seasons", db_column="player_id"
    )
    season = models.PositiveSmallIntegerField()
    round = models.CharField(max_length=3, help_text="DS, WC, LCS o WS.")

    team = models.CharField(max_length=3, null=True, blank=True)
    league = models.CharField(max_length=2, null=True, blank=True)
    pos = models.CharField(max_length=2, null=True, blank=True)

    w = models.PositiveSmallIntegerField(null=True, blank=True)
    l = models.PositiveSmallIntegerField(null=True, blank=True)  # noqa: E741
    g = models.PositiveSmallIntegerField(null=True, blank=True)
    gp = models.PositiveSmallIntegerField(null=True, blank=True)
    gs = models.PositiveSmallIntegerField(null=True, blank=True)
    gf = models.PositiveSmallIntegerField(null=True, blank=True)
    cg = models.PositiveSmallIntegerField(null=True, blank=True)
    sho = models.PositiveSmallIntegerField(null=True, blank=True)
    sv = models.PositiveSmallIntegerField(null=True, blank=True)
    bsv = models.PositiveSmallIntegerField(null=True, blank=True)
    hld = models.PositiveSmallIntegerField(null=True, blank=True)
    ip = models.FloatField(null=True, blank=True, help_text="Entradas en notación de béisbol; usar outs para sumar.")
    h = models.PositiveSmallIntegerField(null=True, blank=True)
    r = models.PositiveSmallIntegerField(null=True, blank=True)
    hr = models.PositiveSmallIntegerField(null=True, blank=True)
    er = models.PositiveSmallIntegerField(null=True, blank=True)
    era = models.FloatField(null=True, blank=True)
    bb = models.PositiveSmallIntegerField(null=True, blank=True)
    ibb = models.PositiveSmallIntegerField(null=True, blank=True)
    so = models.PositiveSmallIntegerField(null=True, blank=True)
    hbp = models.PositiveSmallIntegerField(null=True, blank=True)
    wp = models.PositiveSmallIntegerField(null=True, blank=True)
    bk = models.PositiveSmallIntegerField(null=True, blank=True)
    bf = models.PositiveSmallIntegerField(null=True, blank=True)
    x2b = models.PositiveSmallIntegerField(null=True, blank=True)
    x3b = models.PositiveSmallIntegerField(null=True, blank=True)
    x1b = models.PositiveSmallIntegerField(null=True, blank=True)
    nibb = models.PositiveSmallIntegerField(null=True, blank=True)
    avg = models.FloatField(null=True, blank=True)
    obp = models.FloatField(null=True, blank=True)
    slg = models.FloatField(null=True, blank=True)
    ops = models.FloatField(null=True, blank=True)
    cs = models.PositiveSmallIntegerField(null=True, blank=True)
    sb = models.PositiveSmallIntegerField(null=True, blank=True)
    sb_pct = models.FloatField(null=True, blank=True)
    gidp = models.PositiveSmallIntegerField(null=True, blank=True)
    pitches = models.PositiveSmallIntegerField(null=True, blank=True)
    save_opp = models.PositiveSmallIntegerField(null=True, blank=True)
    outs = models.PositiveSmallIntegerField(null=True, blank=True)
    ground_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    air_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    strikes = models.PositiveSmallIntegerField(null=True, blank=True)
    strike_pct = models.FloatField(null=True, blank=True)
    inherit_runners = models.PositiveSmallIntegerField(null=True, blank=True)
    inherit_runners_scored = models.PositiveSmallIntegerField(null=True, blank=True)
    sh = models.PositiveSmallIntegerField(null=True, blank=True)
    sf = models.PositiveSmallIntegerField(null=True, blank=True)
    pickoffs = models.PositiveSmallIntegerField(null=True, blank=True)
    tb = models.PositiveSmallIntegerField(null=True, blank=True)
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True)
    baa = models.FloatField(null=True, blank=True)
    whip = models.FloatField(null=True, blank=True)
    win_pct = models.FloatField(null=True, blank=True)
    r_per9 = models.FloatField(null=True, blank=True)

    runs_scored_per9 = models.FloatField(null=True, blank=True)
    babip = models.FloatField(null=True, blank=True)
    so_per9 = models.FloatField(null=True, blank=True)
    bb_per9 = models.FloatField(null=True, blank=True)
    hr_per9 = models.FloatField(null=True, blank=True)
    h_per9 = models.FloatField(null=True, blank=True)
    so_to_bb = models.FloatField(null=True, blank=True)
    bequeathed_runners = models.PositiveSmallIntegerField(null=True, blank=True)
    bequeathed_runners_scored = models.PositiveSmallIntegerField(null=True, blank=True)
    quality_starts = models.PositiveSmallIntegerField(null=True, blank=True)
    gidp_opp = models.PositiveSmallIntegerField(null=True, blank=True)
    total_swings = models.PositiveSmallIntegerField(null=True, blank=True)
    swing_and_misses = models.PositiveSmallIntegerField(null=True, blank=True)
    balls_in_play = models.PositiveSmallIntegerField(null=True, blank=True)
    run_support = models.PositiveSmallIntegerField(null=True, blank=True)
    pitches_per_inning = models.FloatField(null=True, blank=True)
    pitches_per_pa = models.FloatField(null=True, blank=True)
    walks_per_pa = models.FloatField(null=True, blank=True)
    so_per_pa = models.FloatField(null=True, blank=True)
    bb_per_so = models.FloatField(null=True, blank=True)
    iso = models.FloatField(null=True, blank=True)
    fly_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    line_outs = models.PositiveSmallIntegerField(null=True, blank=True)
    fly_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    pop_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    line_hits = models.PositiveSmallIntegerField(null=True, blank=True)
    ground_hits = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mlb_pitching_post"
        ordering = ["player", "season", "round"]
        verbose_name = "línea de pitcheo (postemporada)"
        verbose_name_plural = "líneas de pitcheo (postemporada)"
        constraints = [models.UniqueConstraint(fields=["player", "season", "round"], name="unique_pitching_post_line")]
        indexes = [models.Index(fields=["season"], name="mlb_pitching_post_season_idx")]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.round} {self.team or ''}".strip()
