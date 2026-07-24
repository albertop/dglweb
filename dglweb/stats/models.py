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
from dglweb.stats.formula import validate_qualifier_formula

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

    # --- natural key (also the primary key) --------------------------------------
    # The composite primary key IS the identity of a line: (player, season, stint). No surrogate
    # `id` — it would be a second, meaningless key, and nothing foreign-keys to these tables. The
    # three key columns lead the table by declaration order.
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
    pk = models.CompositePrimaryKey("player", "season", "stint")

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

    # --- batted-ball / swing coefficients (derived from the counts above; derive.py group 3) -----
    gb_pct = models.FloatField(null=True, blank=True, verbose_name="GB%")
    fb_pct = models.FloatField(null=True, blank=True, verbose_name="FB%")
    ld_pct = models.FloatField(null=True, blank=True, verbose_name="LD%")
    pu_pct = models.FloatField(null=True, blank=True, verbose_name="PU%")
    gb_fb = models.FloatField(null=True, blank=True, verbose_name="GB/FB")
    contact_pct = models.FloatField(null=True, blank=True, verbose_name="Contact%")
    whiff_pct = models.FloatField(null=True, blank=True, verbose_name="Whiff%")

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
        indexes = [
            # Season leaderboards and "who played in year X" scan by season (the PK index leads
            # with player_id, so a season-only scan needs its own index).
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
    pk = models.CompositePrimaryKey("player", "season", "stint")

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

    # --- batted-ball / swing coefficients (derive.batted_ball_coefficients) ------
    # The balls put in play AGAINST him: same arithmetic as batting, same column names.
    gb_pct = models.FloatField(null=True, blank=True)
    fb_pct = models.FloatField(null=True, blank=True)
    ld_pct = models.FloatField(null=True, blank=True)
    pu_pct = models.FloatField(null=True, blank=True)
    gb_fb = models.FloatField(null=True, blank=True)
    contact_pct = models.FloatField(null=True, blank=True)
    whiff_pct = models.FloatField(null=True, blank=True)

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
    pos = models.CharField(max_length=2, verbose_name="Posición")
    league = models.CharField(max_length=2, null=True, blank=True)
    pk = models.CompositePrimaryKey("player", "season", "team", "pos")

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
    pk = models.CompositePrimaryKey("player", "season", "round")

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

    # --- batted-ball / swing coefficients (derive.py group 3) ---------------------
    gb_pct = models.FloatField(null=True, blank=True)
    fb_pct = models.FloatField(null=True, blank=True)
    ld_pct = models.FloatField(null=True, blank=True)
    pu_pct = models.FloatField(null=True, blank=True)
    gb_fb = models.FloatField(null=True, blank=True)
    contact_pct = models.FloatField(null=True, blank=True)
    whiff_pct = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "mlb_batting_post"
        ordering = ["player", "season", "round"]
        verbose_name = "línea de bateo (postemporada)"
        verbose_name_plural = "líneas de bateo (postemporada)"
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
    pk = models.CompositePrimaryKey("player", "season", "round")

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

    # --- batted-ball / swing coefficients (derive.batted_ball_coefficients) ------
    # The balls put in play AGAINST him: same arithmetic as batting, same column names.
    gb_pct = models.FloatField(null=True, blank=True)
    fb_pct = models.FloatField(null=True, blank=True)
    ld_pct = models.FloatField(null=True, blank=True)
    pu_pct = models.FloatField(null=True, blank=True)
    gb_fb = models.FloatField(null=True, blank=True)
    contact_pct = models.FloatField(null=True, blank=True)
    whiff_pct = models.FloatField(null=True, blank=True)

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
        indexes = [models.Index(fields=["season"], name="mlb_pitching_post_season_idx")]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.round} {self.team or ''}".strip()


class FieldingPost(models.Model):
    """One postseason fielding line: a player's stats at one position in one round.

    Source `dbo.mlbFieldingPost` (24 columns) — the simplest table. Per position per round, keyed
    **(player, season, round, pos)**; no `XXX` (one team per round), no `UZR` (the post script
    fetches only `season`, not sabermetrics) and no stolen-bases/caught-stealing. No formulas.
    `innings` is baseball notation (display); aggregate `innings_outs`.
    """

    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="fielding_post_seasons", db_column="player_id"
    )
    season = models.PositiveSmallIntegerField()
    round = models.CharField(max_length=3, help_text="DS, WC, LCS o WS.")
    pos = models.CharField(max_length=2, verbose_name="Posición")
    pk = models.CompositePrimaryKey("player", "season", "round", "pos")
    team = models.CharField(max_length=3, null=True, blank=True)
    league = models.CharField(max_length=2, null=True, blank=True)

    gp = models.PositiveSmallIntegerField(null=True, blank=True)
    gs = models.PositiveSmallIntegerField(null=True, blank=True)
    a = models.PositiveSmallIntegerField(null=True, blank=True)
    po = models.PositiveSmallIntegerField(null=True, blank=True)
    e = models.PositiveSmallIntegerField(null=True, blank=True)
    chances = models.PositiveSmallIntegerField(null=True, blank=True)
    fld_pct = models.FloatField(null=True, blank=True)
    rf_per_g = models.FloatField(null=True, blank=True)
    rf_per9 = models.FloatField(null=True, blank=True)
    innings = models.FloatField(
        null=True, blank=True, help_text="Entradas en notación de béisbol; usar innings_outs para sumar."
    )
    innings_outs = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Entradas en outs (sumable).")
    double_plays = models.PositiveSmallIntegerField(null=True, blank=True)
    triple_plays = models.PositiveSmallIntegerField(null=True, blank=True)
    throwing_errors = models.PositiveSmallIntegerField(null=True, blank=True)

    passed_balls = models.PositiveSmallIntegerField(null=True, blank=True)
    catcher_era = models.FloatField(null=True, blank=True)
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True)
    wild_pitches = models.PositiveSmallIntegerField(null=True, blank=True)
    pickoffs = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "mlb_fielding_post"
        ordering = ["player", "season", "round", "pos"]
        verbose_name = "línea de fildeo (postemporada)"
        verbose_name_plural = "líneas de fildeo (postemporada)"
        indexes = [models.Index(fields=["season"], name="mlb_fielding_post_season_idx")]

    def __str__(self) -> str:
        return f"{self.player} {self.season} {self.round} {self.pos} {self.team or ''}".strip()


class Metric(models.Model):
    """A leaderboard metric: one stat column of our tables, plus how to rank it.

    The catalog is *generated from our own stat tables* (see `seed_metrics`), one row per rankable
    column; nothing is invented and nothing depends on the old site's SQL Server. What makes a
    column a *leader* — its direction, which boards it feeds, its qualifier — is configured here and
    edited in the Backoffice. The leaders engine (`build_leaders`) reads this table.

    Design borrowed from the original `dgl_stat` but cleaned up: identity is `(stat_group, column)`
    (no per-context duplication — one HR, the engine handles seasons/career/post), and the qualifier
    is a first-class configurable field instead of being hardcoded in SQL views.
    """

    class Group(models.TextChoices):
        BATTING = "batting", "Bateo"
        PITCHING = "pitching", "Pitcheo"
        FIELDING = "fielding", "Fildeo"  # catching stats live here too (Fielding, pos='C')

    class Kind(models.TextChoices):
        CUMULATIVE = "ACU", "Acumulada"  # a count: career value = sum over seasons
        RATE = "PRO", "Tasa"  # a rate: career value = recomputed from summed components

    class Direction(models.TextChoices):
        HIGHER = "+", "Mayor es mejor"
        LOWER = "-", "Menor es mejor"

    stat_group = models.CharField(max_length=10, choices=Group.choices, verbose_name="Grupo")
    column = models.CharField(max_length=40, verbose_name="Columna", help_text="Campo de la tabla de stats.")
    kind = models.CharField(max_length=3, choices=Kind.choices, verbose_name="Tipo")
    direction = models.CharField(
        max_length=1, choices=Direction.choices, default=Direction.HIGHER, verbose_name="Dirección"
    )

    # Which of the four leaderboards this metric feeds (the old `calc*` flags).
    best_season = models.BooleanField(default=False, verbose_name="Mejores temporadas")
    worst_season = models.BooleanField(default=False, verbose_name="Peores temporadas")
    best_career = models.BooleanField(default=False, verbose_name="Mejores carreras")
    worst_career = models.BooleanField(default=False, verbose_name="Peores carreras")

    exclude_zeros = models.BooleanField(default=False, verbose_name="Excluir ceros")
    # Reserved: `build_leaders` does not yet produce postseason boards (they will read the *_post
    # tables in a later phase). The flag is captured now from the source config; setting it has no
    # effect until that dimension exists. See docs/MEJORAS_FUTURAS.md.
    postseason = models.BooleanField(default=False, verbose_name="Postemporada (reservado)")

    # Qualifier cascade, level 2 (optional per-metric override). A simple formula on aggregated
    # columns, e.g. "PA>=502". Blank = inherit the group default (`QualifierDefault`, level 1);
    # a season may still override it (`QualifierSeasonOverride`, level 3). Counts need no threshold.
    qualifier_season = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Umbral propio (temporada)",
        help_text="Vacío = hereda el del grupo.",
        validators=[validate_qualifier_formula],
    )
    qualifier_career = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Umbral propio (carrera)",
        help_text="Vacío = hereda el del grupo.",
        validators=[validate_qualifier_formula],
    )

    available_from = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Disponible desde", help_text="Primer año con dato (métricas nuevas)."
    )

    abbrev = models.CharField(max_length=40, blank=True, verbose_name="Abreviatura")
    name_es = models.CharField(max_length=80, blank=True, verbose_name="Nombre")
    fmt = models.CharField(max_length=10, blank=True, verbose_name="Formato", help_text='Ej. "#.000", "0.00".')
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Orden", help_text="Orden de despliegue en la UI (menor primero)."
    )
    is_active = models.BooleanField(default=False, verbose_name="Activa")

    class Meta:
        db_table = "dgl_metric"
        ordering = ["stat_group", "sort_order", "column"]
        verbose_name = "métrica"
        verbose_name_plural = "métricas"
        constraints = [models.UniqueConstraint(fields=["stat_group", "column"], name="unique_metric")]

    def __str__(self) -> str:
        return f"{self.get_stat_group_display()} · {self.abbrev or self.column}"


class QualifierDefault(models.Model):
    """Qualifier cascade, level 1: the default threshold for a whole stat group.

    One row per group (batting -> PA, pitching -> IP, fielding -> G). Every rate metric of the group
    inherits this unless it sets its own (`Metric.qualifier_*`, level 2) or a season overrides it
    (`QualifierSeasonOverride`, level 3). So `PA>=502` is defined once and applies to avg/obp/slg/…
    """

    stat_group = models.CharField(max_length=10, choices=Metric.Group.choices, unique=True, verbose_name="Grupo")
    qualifier_season = models.CharField(
        max_length=100, blank=True, verbose_name="Umbral (temporada)", validators=[validate_qualifier_formula]
    )
    qualifier_career = models.CharField(
        max_length=100, blank=True, verbose_name="Umbral (carrera)", validators=[validate_qualifier_formula]
    )

    class Meta:
        db_table = "dgl_qualifier_default"
        ordering = ["stat_group"]
        verbose_name = "umbral por defecto"
        verbose_name_plural = "umbrales por defecto"

    def __str__(self) -> str:
        return f"{self.get_stat_group_display()}: {self.qualifier_season or '—'}"


class QualifierSeasonOverride(models.Model):
    """Qualifier cascade, level 3: overrides a group's season threshold for one short season.

    Per `(stat_group, season)`, so one row (e.g. batting/2020 -> PA>=186) applies to every rate
    metric of the group at once. Only the season threshold is overridden — career spans many seasons.
    """

    stat_group = models.CharField(max_length=10, choices=Metric.Group.choices, verbose_name="Grupo")
    season = models.PositiveSmallIntegerField(verbose_name="Temporada")
    qualifier_season = models.CharField(
        max_length=100, verbose_name="Umbral (temporada)", validators=[validate_qualifier_formula]
    )

    class Meta:
        db_table = "dgl_qualifier_season_override"
        ordering = ["-season", "stat_group"]
        verbose_name = "override de umbral por temporada"
        verbose_name_plural = "overrides de umbral por temporada"
        constraints = [models.UniqueConstraint(fields=["stat_group", "season"], name="unique_group_season_qualifier")]

    def __str__(self) -> str:
        return f"{self.get_stat_group_display()} {self.season}: {self.qualifier_season}"


class Leader(models.Model):
    """One precomputed leaderboard row. Rebuilt from scratch by `build_leaders`.

    A row belongs to a (metric, board, season?, fielding_pos?) leaderboard and gives a player's
    value and dense rank within it. Dimensions:
      * `board`   — best/worst x season/career (from the metric's calc flags).
      * `season`  — the season for a *season* board; NULL for a *career* board.
      * `fielding_pos` — the position for a fielding board (LF, CF, 1B…); NULL for batting/pitching.
      * `postseason` — regular season (False) vs postseason (True). Orthogonal to `board`: a
        postseason board aggregates a player's whole October per season (best_season) or over his
        career (best_career), never per round. Only counts get postseason boards.
    So "PutOuts leaders for LF in 2020" = (metric=po, board=best_season, season=2020, pos=LF).
    """

    class Board(models.TextChoices):
        BEST_SEASON = "best_season", "Mejores temporadas"
        WORST_SEASON = "worst_season", "Peores temporadas"
        BEST_CAREER = "best_career", "Mejores carreras"
        WORST_CAREER = "worst_career", "Peores carreras"

    metric = models.ForeignKey(Metric, on_delete=models.CASCADE, related_name="leaders", verbose_name="Métrica")
    board = models.CharField(max_length=12, choices=Board.choices, verbose_name="Tablero")
    season = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Temporada")
    fielding_pos = models.CharField(max_length=2, null=True, blank=True, verbose_name="Posición")
    postseason = models.BooleanField(default=False, verbose_name="Postemporada")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="leaderships", verbose_name="Jugador")
    value = models.FloatField(verbose_name="Valor")
    rank = models.PositiveIntegerField(verbose_name="Rango")

    class Meta:
        db_table = "dgl_leader"
        ordering = ["metric", "board", "season", "fielding_pos", "rank"]
        verbose_name = "líder"
        verbose_name_plural = "líderes"
        indexes = [
            # The read pattern is "one leaderboard": fix metric/board/season/pos/postseason, by rank.
            models.Index(
                fields=["metric", "board", "season", "fielding_pos", "postseason", "rank"],
                name="dgl_leader_board_idx",
            ),
        ]
        constraints = [
            # One row per player per board. `nulls_distinct=False` so career boards (season NULL) and
            # non-fielding boards (fielding_pos NULL) are still deduped. Backstop against a concurrent
            # rebuild (which also takes an advisory lock in build_leaders).
            models.UniqueConstraint(
                fields=["metric", "board", "season", "fielding_pos", "postseason", "player"],
                name="unique_leader",
                nulls_distinct=False,
            )
        ]

    def __str__(self) -> str:
        where = self.season if self.season else "carrera"
        pos = f" {self.fielding_pos}" if self.fielding_pos else ""
        return f"{self.metric.abbrev}{pos} {where} #{self.rank}: {self.player}"


# --- Career totals --------------------------------------------------------------------------------
# Materialized per-player career lines, rebuilt by `build_career_totals` from the season tables.
# In-house is the source of truth (career = the sum of the seasons we show), verified against the
# proxy's career endpoint by `parity_career`. These sum ALL seasons (Negro Leagues included, unlike
# leaders). `ip`/`innings` are not stored — derive them from `outs`/`innings_outs` at display.
#
# Each player has SEVERAL rows (subtotals): batting/pitching carry a row per team and per league
# plus the grand total; fielding a row per position plus the grand total. `level` says which, and
# `sort_order` (assigned at build time) is the display order the owner asked for: teams first (by
# PA), then leagues (by PA), then the total; for fielding, positions first (by G) then the total.
# A surrogate id, not a natural key: these are derived rows rebuilt wholesale, never upserted.


class CareerLevel(models.TextChoices):
    TEAM = "team", "Por equipo"
    LEAGUE = "league", "Por liga"
    POSITION = "pos", "Por posición"
    TOTAL = "total", "Total"


class BattingCareer(models.Model):
    """A player's career batting subtotals (per team, per league) and grand total."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, db_column="player_id", related_name="batting_career")
    level = models.CharField(max_length=6, choices=CareerLevel.choices)
    team = models.CharField(max_length=3, null=True, blank=True)
    league = models.CharField(max_length=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    g = models.PositiveIntegerField(null=True, blank=True)
    pa = models.PositiveIntegerField(null=True, blank=True)
    ab = models.PositiveIntegerField(null=True, blank=True)
    r = models.PositiveIntegerField(null=True, blank=True)
    h = models.PositiveIntegerField(null=True, blank=True)
    x1b = models.PositiveIntegerField(null=True, blank=True)
    x2b = models.PositiveIntegerField(null=True, blank=True)
    x3b = models.PositiveIntegerField(null=True, blank=True)
    hr = models.PositiveIntegerField(null=True, blank=True)
    xbh = models.PositiveIntegerField(null=True, blank=True)
    rbi = models.PositiveIntegerField(null=True, blank=True)
    sb = models.PositiveIntegerField(null=True, blank=True)
    cs = models.PositiveIntegerField(null=True, blank=True)
    bb = models.PositiveIntegerField(null=True, blank=True)
    so = models.PositiveIntegerField(null=True, blank=True)
    ibb = models.PositiveIntegerField(null=True, blank=True)
    nibb = models.PositiveIntegerField(null=True, blank=True)
    hbp = models.PositiveIntegerField(null=True, blank=True)
    sh = models.PositiveIntegerField(null=True, blank=True)
    sf = models.PositiveIntegerField(null=True, blank=True)
    gidp = models.PositiveIntegerField(null=True, blank=True)
    pitches = models.PositiveIntegerField(null=True, blank=True)
    tb = models.PositiveIntegerField(null=True, blank=True)
    lob = models.PositiveIntegerField(null=True, blank=True)
    catcher_int = models.PositiveIntegerField(null=True, blank=True)
    runs_produced = models.PositiveIntegerField(null=True, blank=True)
    air_outs = models.PositiveIntegerField(null=True, blank=True)
    ground_outs = models.PositiveIntegerField(null=True, blank=True)
    fly_outs = models.PositiveIntegerField(null=True, blank=True)
    pop_outs = models.PositiveIntegerField(null=True, blank=True)
    line_outs = models.PositiveIntegerField(null=True, blank=True)
    fly_hits = models.PositiveIntegerField(null=True, blank=True)
    pop_hits = models.PositiveIntegerField(null=True, blank=True)
    line_hits = models.PositiveIntegerField(null=True, blank=True)
    ground_hits = models.PositiveIntegerField(null=True, blank=True)
    total_swings = models.PositiveIntegerField(null=True, blank=True)
    swing_and_misses = models.PositiveIntegerField(null=True, blank=True)
    balls_in_play = models.PositiveIntegerField(null=True, blank=True)
    walk_offs = models.PositiveIntegerField(null=True, blank=True)

    # --- batted-ball / swing coefficients (derive.py group 3) ---------------------
    gb_pct = models.FloatField(null=True, blank=True)
    fb_pct = models.FloatField(null=True, blank=True)
    ld_pct = models.FloatField(null=True, blank=True)
    pu_pct = models.FloatField(null=True, blank=True)
    gb_fb = models.FloatField(null=True, blank=True)
    contact_pct = models.FloatField(null=True, blank=True)
    whiff_pct = models.FloatField(null=True, blank=True)

    roe = models.PositiveIntegerField(null=True, blank=True)
    gidp_opp = models.PositiveIntegerField(null=True, blank=True)

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
    total_avg = models.FloatField(null=True, blank=True)
    woba = models.FloatField(null=True, blank=True)
    w_raa = models.FloatField(null=True, blank=True)
    w_rc = models.FloatField(null=True, blank=True)
    w_rc_plus = models.FloatField(null=True, blank=True)
    rar = models.FloatField(null=True, blank=True)
    war = models.FloatField(null=True, blank=True)
    ubr = models.FloatField(null=True, blank=True)
    w_gdp = models.FloatField(null=True, blank=True)
    w_sb = models.FloatField(null=True, blank=True)
    spd = models.FloatField(null=True, blank=True)
    positional_adj = models.FloatField(null=True, blank=True)
    w_league = models.FloatField(null=True, blank=True)
    batting = models.FloatField(null=True, blank=True)
    fielding = models.FloatField(null=True, blank=True)
    base_running = models.FloatField(null=True, blank=True)
    replacement = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "mlb_batting_career"
        ordering = ["player", "sort_order"]
        indexes = [models.Index(fields=["player", "sort_order"], name="mlb_batting_career_idx")]
        verbose_name = "carrera de bateo"
        verbose_name_plural = "carreras de bateo"

    def __str__(self) -> str:
        return f"{self.player} bateo {self.team or self.league or 'total'}"


class PitchingCareer(models.Model):
    """A player's career pitching subtotals (per team, per league) and grand total.

    `ip` is derived from `outs` at display; subtotals are ordered by `bf` (the pitcher's PA).
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, db_column="player_id", related_name="pitching_career")
    level = models.CharField(max_length=6, choices=CareerLevel.choices)
    team = models.CharField(max_length=3, null=True, blank=True)
    league = models.CharField(max_length=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    w = models.PositiveIntegerField(null=True, blank=True)
    l = models.PositiveIntegerField(null=True, blank=True)  # noqa: E741
    g = models.PositiveIntegerField(null=True, blank=True)
    gp = models.PositiveIntegerField(null=True, blank=True)
    gs = models.PositiveIntegerField(null=True, blank=True)
    gf = models.PositiveIntegerField(null=True, blank=True)
    cg = models.PositiveIntegerField(null=True, blank=True)
    sho = models.PositiveIntegerField(null=True, blank=True)
    sv = models.PositiveIntegerField(null=True, blank=True)
    bsv = models.PositiveIntegerField(null=True, blank=True)
    hld = models.PositiveIntegerField(null=True, blank=True)
    h = models.PositiveIntegerField(null=True, blank=True)
    r = models.PositiveIntegerField(null=True, blank=True)
    hr = models.PositiveIntegerField(null=True, blank=True)
    er = models.PositiveIntegerField(null=True, blank=True)
    bb = models.PositiveIntegerField(null=True, blank=True)
    ibb = models.PositiveIntegerField(null=True, blank=True)
    so = models.PositiveIntegerField(null=True, blank=True)
    hbp = models.PositiveIntegerField(null=True, blank=True)
    wp = models.PositiveIntegerField(null=True, blank=True)
    bk = models.PositiveIntegerField(null=True, blank=True)
    bf = models.PositiveIntegerField(null=True, blank=True)
    x2b = models.PositiveIntegerField(null=True, blank=True)
    x3b = models.PositiveIntegerField(null=True, blank=True)
    x1b = models.PositiveIntegerField(null=True, blank=True)
    nibb = models.PositiveIntegerField(null=True, blank=True)
    cs = models.PositiveIntegerField(null=True, blank=True)
    sb = models.PositiveIntegerField(null=True, blank=True)
    gidp = models.PositiveIntegerField(null=True, blank=True)
    pitches = models.PositiveIntegerField(null=True, blank=True)
    save_opp = models.PositiveIntegerField(null=True, blank=True)
    outs = models.PositiveIntegerField(null=True, blank=True)
    ground_outs = models.PositiveIntegerField(null=True, blank=True)
    air_outs = models.PositiveIntegerField(null=True, blank=True)
    strikes = models.PositiveIntegerField(null=True, blank=True)
    inherit_runners = models.PositiveIntegerField(null=True, blank=True)
    inherit_runners_scored = models.PositiveIntegerField(null=True, blank=True)
    sh = models.PositiveIntegerField(null=True, blank=True)
    sf = models.PositiveIntegerField(null=True, blank=True)
    pickoffs = models.PositiveIntegerField(null=True, blank=True)
    tb = models.PositiveIntegerField(null=True, blank=True)
    catcher_int = models.PositiveIntegerField(null=True, blank=True)
    bequeathed_runners = models.PositiveIntegerField(null=True, blank=True)
    bequeathed_runners_scored = models.PositiveIntegerField(null=True, blank=True)
    quality_starts = models.PositiveIntegerField(null=True, blank=True)
    gidp_opp = models.PositiveIntegerField(null=True, blank=True)
    total_swings = models.PositiveIntegerField(null=True, blank=True)
    swing_and_misses = models.PositiveIntegerField(null=True, blank=True)
    balls_in_play = models.PositiveIntegerField(null=True, blank=True)

    # Batted-ball breakdown. The career table was missing these seven, so a career line could not
    # show the type split nor recompute the coefficients from its own sums.
    fly_outs = models.PositiveIntegerField(null=True, blank=True)
    pop_outs = models.PositiveIntegerField(null=True, blank=True)
    line_outs = models.PositiveIntegerField(null=True, blank=True)
    fly_hits = models.PositiveIntegerField(null=True, blank=True)
    pop_hits = models.PositiveIntegerField(null=True, blank=True)
    line_hits = models.PositiveIntegerField(null=True, blank=True)
    ground_hits = models.PositiveIntegerField(null=True, blank=True)

    # --- batted-ball / swing coefficients (derive.batted_ball_coefficients) ------
    gb_pct = models.FloatField(null=True, blank=True)
    fb_pct = models.FloatField(null=True, blank=True)
    ld_pct = models.FloatField(null=True, blank=True)
    pu_pct = models.FloatField(null=True, blank=True)
    gb_fb = models.FloatField(null=True, blank=True)
    contact_pct = models.FloatField(null=True, blank=True)
    whiff_pct = models.FloatField(null=True, blank=True)

    run_support = models.PositiveIntegerField(null=True, blank=True)
    sd = models.PositiveIntegerField(null=True, blank=True)
    md = models.PositiveIntegerField(null=True, blank=True)
    ab = models.PositiveIntegerField(null=True, blank=True)
    sh_fail = models.PositiveIntegerField(null=True, blank=True)
    sh_missed = models.PositiveIntegerField(null=True, blank=True)

    era = models.FloatField(null=True, blank=True)
    avg = models.FloatField(null=True, blank=True)
    obp = models.FloatField(null=True, blank=True)
    slg = models.FloatField(null=True, blank=True)
    ops = models.FloatField(null=True, blank=True)
    sb_pct = models.FloatField(null=True, blank=True)
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
    strike_pct = models.FloatField(null=True, blank=True)
    pitches_per_inning = models.FloatField(null=True, blank=True)
    pitches_per_pa = models.FloatField(null=True, blank=True)
    walks_per_pa = models.FloatField(null=True, blank=True)
    so_per_pa = models.FloatField(null=True, blank=True)
    bb_per_so = models.FloatField(null=True, blank=True)
    iso = models.FloatField(null=True, blank=True)
    fip = models.FloatField(null=True, blank=True)
    xfip = models.FloatField(null=True, blank=True)
    fip_minus = models.FloatField(null=True, blank=True)
    ra9_war = models.FloatField(null=True, blank=True)
    rar = models.FloatField(null=True, blank=True)
    war = models.FloatField(null=True, blank=True)
    p_li = models.FloatField(null=True, blank=True)
    in_li = models.FloatField(null=True, blank=True)
    gm_li = models.FloatField(null=True, blank=True)
    ex_li = models.FloatField(null=True, blank=True)
    era_minus = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "mlb_pitching_career"
        ordering = ["player", "sort_order"]
        indexes = [models.Index(fields=["player", "sort_order"], name="mlb_pitching_career_idx")]
        verbose_name = "carrera de pitcheo"
        verbose_name_plural = "carreras de pitcheo"

    def __str__(self) -> str:
        return f"{self.player} pitcheo {self.team or self.league or 'total'}"


class FieldingCareer(models.Model):
    """A player's career fielding subtotals per position and the grand total.

    Positions first (by G), then the total. `innings` is derived from `innings_outs` at display.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, db_column="player_id", related_name="fielding_career")
    level = models.CharField(max_length=6, choices=CareerLevel.choices)
    pos = models.CharField(max_length=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    gp = models.PositiveIntegerField(null=True, blank=True)
    gs = models.PositiveIntegerField(null=True, blank=True)
    a = models.PositiveIntegerField(null=True, blank=True)
    po = models.PositiveIntegerField(null=True, blank=True)
    e = models.PositiveIntegerField(null=True, blank=True)
    chances = models.PositiveIntegerField(null=True, blank=True)
    innings_outs = models.PositiveIntegerField(null=True, blank=True)
    double_plays = models.PositiveIntegerField(null=True, blank=True)
    triple_plays = models.PositiveIntegerField(null=True, blank=True)
    throwing_errors = models.PositiveIntegerField(null=True, blank=True)
    passed_balls = models.PositiveIntegerField(null=True, blank=True)
    catcher_int = models.PositiveIntegerField(null=True, blank=True)
    wild_pitches = models.PositiveIntegerField(null=True, blank=True)
    pickoffs = models.PositiveIntegerField(null=True, blank=True)
    stolen_bases = models.PositiveIntegerField(null=True, blank=True)
    caught_stealing = models.PositiveIntegerField(null=True, blank=True)

    fld_pct = models.FloatField(null=True, blank=True)
    rf_per_g = models.FloatField(null=True, blank=True)
    rf_per9 = models.FloatField(null=True, blank=True)
    catcher_era = models.FloatField(null=True, blank=True)
    uzr = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "mlb_fielding_career"
        ordering = ["player", "sort_order"]
        indexes = [models.Index(fields=["player", "sort_order"], name="mlb_fielding_career_idx")]
        verbose_name = "carrera de fildeo"
        verbose_name_plural = "carreras de fildeo"

    def __str__(self) -> str:
        return f"{self.player} fildeo {self.pos or 'total'}"


class CareerParityIssue(models.Model):
    """A career total that disagreed with the proxy's authoritative `career` — the parity marker.

    `parity_career` compares our in-house totals to the proxy and records the survivors here (option
    "b": it only flags and logs, never auto-writes data). The row IS the "known, unresolved" state:
    it is created on first disagreement, its `detail` refreshed while it persists, and **deleted when
    parity passes again** (a re-backfill fixed the season data). `attempts` is the loop guard for a
    future auto-remediation (option "a", see docs/MEJORAS_FUTURAS): it stays 0 here, and would cap
    remediation at one try so a persistent mismatch can never re-trigger it.
    """

    class Status(models.TextChoices):
        UNRESOLVED = "unresolved", "Sin resolver"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, db_column="player_id", verbose_name="Jugador")
    group = models.CharField(max_length=10, verbose_name="Grupo")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UNRESOLVED, verbose_name="Estado")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Intentos de remediación")
    detail = models.TextField(verbose_name="Diferencias")
    first_detected = models.DateTimeField(verbose_name="Detectado")
    last_checked = models.DateTimeField(verbose_name="Última revisión")

    class Meta:
        db_table = "dgl_career_parity_issue"
        ordering = ["-last_checked", "player"]
        verbose_name = "disparidad de carrera"
        verbose_name_plural = "disparidades de carrera"
        constraints = [models.UniqueConstraint(fields=["player", "group"], name="unique_career_parity_issue")]

    def __str__(self) -> str:
        return f"{self.player} ({self.group}): {self.detail}"
