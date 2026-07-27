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
from typing import Any, TypeVar

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
    g = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="G")
    pa = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="PA")
    ab = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="AB")
    r = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="R")
    h = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="H")
    x1b = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="1B")
    x2b = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="2B")
    x3b = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="3B")
    hr = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HR")
    xbh = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="XBH")
    rbi = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="RBI")
    sb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="SB")
    cs = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="CS")
    bb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="BB")
    so = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="SO")
    ibb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="IBB")
    nibb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="NIBB")
    hbp = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HBP")
    sh = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="SH")
    sf = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="SF")
    gidp = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="DP")
    pitches = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Lanzamientos")
    tb = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="TB")
    lob = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="LOB")
    catcher_int = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="ICat")

    # --- rate stats --------------------------------------------------------------
    avg = models.FloatField(null=True, blank=True, verbose_name="AVG")
    obp = models.FloatField(null=True, blank=True, verbose_name="OBP")
    slg = models.FloatField(null=True, blank=True, verbose_name="SLG")
    ops = models.FloatField(null=True, blank=True, verbose_name="OPS")
    ab_per_hr = models.FloatField(null=True, blank=True, verbose_name="AB/HR")
    babip = models.FloatField(null=True, blank=True, verbose_name="BABIP")
    bb_per_so = models.FloatField(null=True, blank=True, verbose_name="BB/SO")
    bsr = models.FloatField(null=True, blank=True, verbose_name="BsR")
    eq_avg = models.FloatField(null=True, blank=True, verbose_name="EqA")
    gross_prod_avg = models.FloatField(null=True, blank=True, verbose_name="GPA")
    iso = models.FloatField(null=True, blank=True, verbose_name="ISO")
    pa_per_so = models.FloatField(null=True, blank=True, verbose_name="PA/SO")
    rc = models.FloatField(null=True, blank=True, verbose_name="RC")
    runs_produced = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="RP")
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
        # No corrió, y a propósito: fuera de temporada. Es un estado y no una ausencia porque la
        # ausencia no se puede distinguir de un scheduler caído — ver `stats.season_window`.
        SKIPPED = "skipped", "Fuera de temporada"

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

    @property
    def cs_pct(self) -> float | None:
        """CS% = atrapados ÷ intentos (SB+CS); recomputa desde los conteos de esta fila (nunca
        promedia tasas). None si no hubo intentos: eso no es 0 %, es dato ausente."""
        caught = self.caught_stealing or 0
        attempts = (self.stolen_bases or 0) + caught
        return caught / attempts if attempts else None

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
    # `build_leaders` produces postseason boards (counts where more is better, and the classic rates
    # with fixed October floors — see `_postseason_leaders` / `_postseason_rate_leaders` and
    # docs/UMBRALES_POSTEMPORADA.md). `best_season`/`best_career` gate October too, like every board.
    postseason = models.BooleanField(default=False, verbose_name="Postemporada")

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
    # Enciende y apaga la métrica en el widget de la portada sin tocar código ni esperar el refresco:
    # el trabajo horario guarda TODAS las categorías que MLB publica —pedir veintitrés cuesta lo
    # mismo que pedir cinco, una llamada por oficio— y este flag decide cuáles se muestran.
    visible_en_widget_lideres = models.BooleanField(
        default=False,
        verbose_name="En el widget de líderes",
        help_text="Solo surte efecto en las métricas que MLB publica como ranking (ver stats.mlb_leaders).",
    )

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
            # El otro patrón de lectura: "qué métricas TIENEN tablero", que arma los dropdowns de
            # líderes. No arranca por `metric` —pregunta justamente por cuáles hay— así que el índice
            # de arriba no le sirve y caía en scan secuencial de 400k filas. Va por rank porque la
            # pregunta se responde mirando solo las cabezas de tablero (rank=1), y termina en metric
            # para que sea Index Only Scan: la respuesta sale del índice sin tocar la tabla.
            models.Index(
                fields=["postseason", "fielding_pos", "rank", "metric"],
                name="dgl_leader_avail_idx",
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

    @property
    def cs_pct(self) -> float | None:
        """CS% de la carrera: atrapados ÷ intentos sobre los conteos sumados de esta fila (por
        posición o total). None si no hubo intentos. Igual que la línea de temporada."""
        caught = self.caught_stealing or 0
        attempts = (self.stolen_bases or 0) + caught
        return caught / attempts if attempts else None

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


class StaticDataset(models.Model):
    """El registro de los datasets que se cargan a mano por CSV — Fase 4e.

    El sitio se alimenta del proxy de MLB, pero salarios, transacciones y los tipos de batazo solo
    existen en la base DGL (SQL Server). Son datos casi estáticos, de una o dos cargas al año, así
    que van por una vía manual: un PowerShell en `static_data/` los exporta a CSV y el Backoffice
    los sube. Esta tabla es la lista de qué se puede subir; agregar un dataset es crear una fila,
    no tocar código. Diseño completo en `docs/DATOS_DE_APOYO.md`.
    """

    class Mode(models.TextChoices):
        TRUNCATE = "truncate", "Truncar y reemplazar"
        UPSERT = "upsert", "Upsert idempotente"

    table = models.CharField(max_length=63, unique=True, verbose_name="Tabla destino")
    powershell = models.CharField(max_length=120, verbose_name="PowerShell")
    csv = models.CharField(max_length=120, verbose_name="Archivo CSV")
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.TRUNCATE, verbose_name="Modo de carga")
    # Obligatoria en los DOS modos, no solo en upsert: la pantalla de comparación la necesita para
    # decir qué desapareció, y la validación de unicidad corre siempre. Un duplicado con truncate no
    # se traga una fila con otra — inserta las dos y deja un registro fantasma.
    natural_key = models.CharField(
        max_length=200,
        verbose_name="Clave natural",
        help_text="Columnas que identifican una fila, separadas por coma. Casi siempre compuesta: "
        "player_id,season,stint",
    )
    comment = models.TextField(blank=True, verbose_name="Comentario")
    # El rastro de la última carga le da a la pantalla de comparación una línea base histórica: sin
    # esto se ve que un CSV trae menos filas que la tabla, pero no que viene encogiéndose carga tras
    # carga. En una operación semestral, además, importa quién la hizo.
    last_update = models.DateTimeField(null=True, blank=True, verbose_name="Última carga")
    last_rows = models.PositiveIntegerField(null=True, blank=True, verbose_name="Filas de la última carga")
    last_user = models.CharField(max_length=150, blank=True, verbose_name="Cargado por")

    class Meta:
        db_table = "dgl_static_dataset"
        ordering = ["table"]
        verbose_name = "dataset de apoyo"
        verbose_name_plural = "datasets de apoyo"

    def __str__(self) -> str:
        return self.table

    def cargar(self) -> str:
        """El enlace a la pantalla de carga, para que el listado del Backoffice lo ofrezca.

        Vive acá y no en el viewset porque Wagtail arma las columnas del listado leyendo atributos
        del modelo; una columna que solo existiera en el viewset no tendría de dónde salir.
        """
        from django.urls import reverse
        from django.utils.html import format_html

        return format_html(
            '<a href="{}" class="button button-small">Cargar CSV</a>', reverse("staticdata_upload", args=[self.pk])
        )

    cargar.short_description = "Carga"  # type: ignore[attr-defined]

    @property
    def key_columns(self) -> list[str]:
        """La clave natural como lista — el import y la comparación agrupan por TODAS estas columnas."""
        return [part.strip() for part in self.natural_key.split(",") if part.strip()]

    def clean(self) -> None:
        """Que la fila describa algo que el motor pueda cumplir de verdad.

        Agregar un dataset es crear una fila, no tocar código — pero eso significa que se puede
        escribir una configuración imposible sin que nada se queje hasta el día de la carga, que es
        el peor momento para enterarse: el CSV ya está hecho y hay alguien esperando. Los tres modos
        de fallo, todos silenciosos hasta acá: una tabla sin loader, una clave natural con columnas
        que no existen en el modelo, y un upsert sobre una tabla sin la restricción de unicidad que
        lo vuelve idempotente.
        """
        from django.core.exceptions import ValidationError

        from dglweb.stats.staticdata import REGISTRY

        loader = REGISTRY.get(self.table)
        if loader is None:
            conocidas = ", ".join(sorted(REGISTRY)) or "ninguna todavía"
            raise ValidationError(
                {
                    "table": f"No hay ningún loader registrado para «{self.table}». El motor no sabría "
                    f"cómo leer su CSV. Tablas con loader: {conocidas}."
                }
            )

        # Un alias por cada forma válida de nombrar una columna: la FK se declara `player` en el
        # modelo pero la columna es `player_id`, y en el CSV se escribe de las dos maneras.
        alias = {}
        for campo in loader.model._meta.concrete_fields:
            alias[campo.name] = campo.attname
            alias[campo.attname] = campo.attname

        errores: dict[str, str] = {}
        columnas = self.key_columns
        if not columnas:
            errores["natural_key"] = (
                "La clave natural no puede quedar vacía: la comparación y el chequeo de duplicados agrupan por ella."
            )
        elif desconocidas := [c for c in columnas if c not in alias]:
            errores["natural_key"] = (
                f"{loader.model.__name__} no tiene la(s) columna(s) {', '.join(desconocidas)}. "
                f"Columnas disponibles: {', '.join(sorted({c.attname for c in loader.model._meta.concrete_fields}))}."
            )

        # El upsert hace `update_or_create` por la clave natural. Sin una restricción de unicidad que
        # la respalde, dos filas iguales pueden convivir en la tabla y a la siguiente carga el
        # `update_or_create` revienta al encontrar dos: el modo se llama idempotente pero no lo es.
        if self.mode == self.Mode.UPSERT and "natural_key" not in errores:
            pedidas = {alias[c] for c in columnas}
            respaldada = any(
                {alias.get(f, f) for f in getattr(restriccion, "fields", ())} == pedidas
                for restriccion in loader.model._meta.constraints
            ) or any({alias.get(f, f) for f in juntas} == pedidas for juntas in loader.model._meta.unique_together)
            if not respaldada:
                errores["mode"] = (
                    f"El modo upsert necesita que {loader.model.__name__} tenga una restricción de "
                    f"unicidad sobre ({', '.join(columnas)}), y no la tiene. Agregala en el modelo "
                    "con su migración, o cargá esta tabla por truncate."
                )

        if errores:
            raise ValidationError(errores)


class BattedBallHits(models.Model):
    """Hits por tipo de batazo, traídos de Retrosheet — el primer dataset de la Fase 4e.

    Vive aparte de `mlb_batting`/`mlb_pitching` a propósito: esas tablas son del proxy, y truncarlas
    para cargar un CSV destruiría el backfill. Acá el dato tiene su propio dueño y su procedencia
    queda explícita; `derive` lo prefiere sobre el del proxy cuando existe.

    Por qué existe: a la API de MLB le faltan hits por tipo en diez temporadas (1989-90, 1993-97,
    2000-02), y en 2000-2001 entrega menos del 2%. Retrosheet los tiene con ~97% de cobertura, así
    que el hueco es de nuestra fuente y no del registro histórico. La prueba de aceptación es exacta:
    los cuatro tipos son una partición de los hits, así que deben sumar H.

    El grano es (jugador, temporada, oficio) y no incluye el stint: Retrosheet se agrega por evento y
    el reparto por equipo exigiría casar sus códigos con los nuestros. Los coeficientes se calculan
    sobre totales de temporada, así que este grano les alcanza.
    """

    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="batted_ball_hits", verbose_name="Jugador"
    )
    season = models.PositiveSmallIntegerField(verbose_name="Temporada")
    stat_group = models.CharField(max_length=8, verbose_name="Oficio")  # batting | pitching
    ground_hits = models.PositiveSmallIntegerField(default=0, verbose_name="Hits por roletazo")
    fly_hits = models.PositiveSmallIntegerField(default=0, verbose_name="Hits por elevado")
    line_hits = models.PositiveSmallIntegerField(default=0, verbose_name="Hits por línea")
    pop_hits = models.PositiveSmallIntegerField(default=0, verbose_name="Hits por palomita")

    class Meta:
        db_table = "dgl_batted_ball_hits"
        ordering = ["player", "season", "stat_group"]
        verbose_name = "hits por tipo de batazo"
        verbose_name_plural = "hits por tipo de batazo"
        constraints = [
            models.UniqueConstraint(fields=["player", "season", "stat_group"], name="unique_batted_ball_hits")
        ]

    def __str__(self) -> str:
        return f"{self.player} {self.season} ({self.stat_group})"


class DomPlayer(models.Model):
    """Dominicanos en el sistema profesional, con y sin debut en Grandes Ligas — Fase 4e.

    No confundir con `dgl_master`: ese es el maestro de los que SÍ llegaron a las mayores. Esta es más
    ancha —incluye ligas menores— y sirve para ver quién viene subiendo: detectar debuts y
    movimientos de roster.

    **Junto con `dgl_master` forma el "universo dominicano", y esa unión es la ÚNICA autoridad sobre
    quién es dominicano.** El `birthCountry` de la API de MLB no es confiable y no se usa nunca para
    decidirlo — ver la regla de autoridad en el docstring de `players.models.Player`.

    La tabla existía en Postgres desde antes, cargada por fuera de Django y con 27 columnas. Se
    rehízo con las trece que se usan, porque el dato viejo no servía: se reemplaza entero desde la
    vista `v_dglweb_master_no_debuts` de SQL Server, filtrada a los nacidos en los últimos 40 años
    (más los que no tienen fecha de nacimiento, que se conservan a propósito para no perderlos en
    silencio).

    Se declara como modelo Django para que el motor de carga pueda trabajar: `Loader` necesita
    `model` para contar filas, sumar columnas en la pantalla de comparación y escribir. **No tiene
    CRUD en el Backoffice** —igual que `BattedBallHits`— porque no se edita a mano: se reemplaza por
    CSV. Ver `docs/DATOS_DE_APOYO.md`.
    """

    # Sin `player` FK a `dgl_master`: la mayoría de estos jugadores nunca debutó, así que no está
    # en el maestro. El `player_id` es el de MLB y se usa tal cual como clave.
    player_id = models.PositiveIntegerField(primary_key=True, verbose_name="MLB ID")
    last_name = models.CharField(max_length=60, blank=True, verbose_name="Apellido")
    first_name = models.CharField(max_length=60, blank=True, verbose_name="Nombre")
    full_name = models.CharField(max_length=120, blank=True, verbose_name="Nombre completo")
    # `date` y no `datetime`: la tabla vieja guardaba timestamp y todas las filas traían las 19:00,
    # basura de zona horaria de la migración original.
    birth_date = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    birth_place = models.CharField(max_length=120, blank=True, verbose_name="Lugar de nacimiento")
    bats = models.CharField(max_length=1, blank=True, verbose_name="Batea")
    throws = models.CharField(max_length=1, blank=True, verbose_name="Lanza")
    height = models.CharField(max_length=8, blank=True, verbose_name="Estatura")
    weight = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Peso (lb)")
    # Booleanos y no el smallint 0/1 de la tabla vieja: en el origen son `bit`, y PowerShell los
    # exporta como True/False. Guardarlos como enteros obligaba a traducir en los dos extremos.
    is_active = models.BooleanField(null=True, verbose_name="Activo")
    is_player = models.BooleanField(null=True, verbose_name="Es jugador")
    is_verified = models.BooleanField(null=True, verbose_name="Verificado")

    class Meta:
        db_table = "dom_players"
        ordering = ["player_id"]
        verbose_name = "dominicano en el sistema"
        verbose_name_plural = "dominicanos en el sistema"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.player_id})"


class DomSalary(models.Model):
    """Salarios de dominicanos por temporada y equipo — Fase 4e.

    Sale de la vista `v_dglweb_salaries` de SQL Server; no existe en la API de MLB, que es de donde
    viene todo lo demás del sitio. Se reemplaza entera por CSV.

    El grano es (jugador, temporada, equipo) y el equipo forma parte de la clave a propósito: un
    pelotero traspasado a mitad de año cobra de dos organizaciones, así que su temporada son dos
    filas y no una. Sumarlas es la temporada completa.

    Como `DomPlayer`, se declara como modelo Django para que el motor de carga pueda contar, comparar
    y escribir — no para tener CRUD. Ver `docs/DATOS_DE_APOYO.md`.
    """

    # Sin FK a `dgl_master`: la referencia externa se guarda tal cual. Si un salario llega de alguien
    # que todavía no está en el maestro, la fila se conserva y el dato no se pierde — bloquear una
    # carga de miles de filas por un jugador faltante costaría más de lo que protege.
    player_id = models.PositiveIntegerField(db_index=True, verbose_name="MLB ID")
    season = models.PositiveSmallIntegerField(verbose_name="Temporada")
    # Códigos de DGL, no de MLB: `char(3)` y `char(2)` cuyos valores no se corresponden con nada de
    # la API. Se guardan tal cual y no se intentan casar con el `team`/`league` de las tablas del
    # proxy — son dos universos, y traducirlos exigiría un mapeo que hoy no existe.
    team_id = models.CharField(max_length=3, verbose_name="Equipo (código DGL)")
    league_id = models.CharField(max_length=2, blank=True, verbose_name="Liga (código DGL)")
    age = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Edad")
    # En dólares y entero: los salarios de MLB se publican en dólares completos. `BigInteger` porque
    # un contrato anual ya pasa los 40 millones y el techo de `Integer` no da margen para el futuro.
    salary = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="Salario (USD)")

    class Meta:
        db_table = "dom_salaries"
        ordering = ["player_id", "season", "team_id"]
        verbose_name = "salario"
        verbose_name_plural = "salarios"
        # La restricción existe aunque la carga sea por truncate: es la definición del grano, y deja
        # la tabla lista si algún día conviene pasarla a upsert.
        constraints = [models.UniqueConstraint(fields=["player_id", "season", "team_id"], name="unique_dom_salary")]

    def __str__(self) -> str:
        return f"{self.player_id} {self.season} ({self.team_id})"


class SeasonDates(models.Model):
    """El calendario de cada temporada: cuándo empieza, cuándo termina la regular y cuándo octubre.

    Sale de la vista `v_dglweb_season_dates` de SQL Server. A diferencia de los otros datasets de
    apoyo, este SÍ se edita a mano en el Backoffice: son pocas filas, cambian poco, y cuando MLB
    mueve una fecha conviene poder corregirla sin esperar un export. Por eso la carga es **upsert** y
    no truncate — reemplazar la tabla entera borraría cualquier ajuste hecho a mano.

    El grano es (temporada, deporte). `sports_id` está porque la fuente distingue ligas: 1 es MLB.
    Hoy solo se usa esa, pero la clave la respeta para no tener que migrarla si mañana entra otra.
    """

    MLB = 1  # el único `sports_id` que el sitio usa hoy

    season = models.PositiveSmallIntegerField(verbose_name="Temporada")
    sports_id = models.PositiveSmallIntegerField(default=MLB, verbose_name="Deporte", help_text="1 = MLB.")
    season_start_date = models.DateField(verbose_name="Inicio de temporada")
    # Nullable porque la fuente no dijo lo contrario. Si resulta que nunca viene vacía conviene
    # apretarlo, pero al revés —exigirla y que llegue nula— bloquearía la carga entera.
    reg_season_end_date = models.DateField(null=True, blank=True, verbose_name="Fin de serie regular")
    all_star_game_date = models.DateField(null=True, blank=True, verbose_name="Juego de Estrellas")
    post_season_start_date = models.DateField(null=True, blank=True, verbose_name="Inicio de postemporada")
    season_end_date = models.DateField(verbose_name="Fin de temporada")
    is_active = models.BooleanField(default=False, verbose_name="Temporada en curso")

    class Meta:
        db_table = "seasons_dates"
        ordering = ["-season", "sports_id"]
        verbose_name = "calendario de temporada"
        verbose_name_plural = "calendarios de temporada"
        constraints = [
            # Obligatoria, no opcional: el modo upsert hace `update_or_create` por esta clave, y sin
            # la restricción que la respalde dos filas iguales podrían convivir y reventar la carga
            # siguiente. `StaticDataset.clean()` lo exige (ARCH-04).
            models.UniqueConstraint(fields=["season", "sports_id"], name="unique_season_dates"),
            # UNA temporada en curso por deporte, garantizada por la base y no por quien escriba.
            #
            # Es una regla del dominio, no una validación de formulario: `season_window` la consulta
            # para decidir si el pipeline corre hoy, y con dos activas resolvía el empate con
            # `order_by("-season").first()`. Eso no rompe nada — hace algo peor, que es correr o
            # saltar según una temporada que nadie eligió, sin que nada lo diga.
            #
            # Parcial (`condition`) porque las inactivas son muchas y ahí no hay nada que restringir.
            models.UniqueConstraint(
                fields=["sports_id"],
                condition=models.Q(is_active=True),
                name="unique_temporada_activa_por_deporte",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.season}" if self.sports_id == self.MLB else f"{self.season} (deporte {self.sports_id})"

    def clean(self) -> None:
        """Las fechas en orden, y una sola temporada en curso. Vale para el CSV y para el Backoffice.

        Una fecha traspuesta no se ve mirando la fila —todas son plausibles— pero rompe en silencio a
        cualquiera que después pregunte "¿esta fecha cae en serie regular o en postemporada?".

        Lo de la temporada activa lo garantiza además una constraint de la base. Se comprueba también
        acá para que el error salga como un mensaje del formulario y no como un `IntegrityError`
        crudo: la base dice qué regla se rompió, no cuál es la fila que ya la ocupaba.
        """
        from django.core.exceptions import ValidationError

        problema = fechas_fuera_de_orden(
            {
                "season_start_date": self.season_start_date,
                "all_star_game_date": self.all_star_game_date,
                "reg_season_end_date": self.reg_season_end_date,
                "post_season_start_date": self.post_season_start_date,
                "season_end_date": self.season_end_date,
            }
        )
        if problema:
            raise ValidationError({problema[0]: problema[1]})

        if self.is_active:
            # `exclude(pk=...)` para que editar la fila que YA es la activa no choque consigo misma.
            otra = (
                SeasonDates.objects.filter(sports_id=self.sports_id, is_active=True)
                .exclude(pk=self.pk)
                .values_list("season", flat=True)
                .first()
            )
            if otra is not None:
                raise ValidationError(
                    {
                        "is_active": (
                            f"La temporada {otra} ya está marcada como en curso para este deporte. "
                            "Solo puede haber una: desmárcala antes de marcar esta."
                        )
                    }
                )


# El orden en que las fechas de una temporada tienen que ocurrir. El Juego de Estrellas va en medio
# de la serie regular, y la postemporada arranca después de que esta termina.
_ORDEN_FECHAS = (
    ("season_start_date", "el inicio de temporada"),
    ("all_star_game_date", "el Juego de Estrellas"),
    ("reg_season_end_date", "el fin de la serie regular"),
    ("post_season_start_date", "el inicio de la postemporada"),
    ("season_end_date", "el fin de temporada"),
)


def fechas_fuera_de_orden(fechas: dict[str, Any]) -> tuple[str, str] | None:
    """El primer par que rompe la cronología, o `None`. Las fechas ausentes se saltan."""
    previo_nombre, previo_valor = "", None
    for campo, nombre in _ORDEN_FECHAS:
        valor = fechas.get(campo)
        if valor is None:
            continue
        if previo_valor is not None and valor < previo_valor:
            return campo, f"{nombre.capitalize()} ({valor}) no puede ser antes que {previo_nombre} ({previo_valor})."
        previo_nombre, previo_valor = nombre, valor
    return None


class DailyStandout(models.Model):
    """La actuación de cada dominicano en una jornada — lo que alimenta el widget de la portada.

    Se guarda en vez de calcularse al mostrar porque el cálculo son dos llamadas al proxy: hacerlas
    en cada visita ataría la portada a que la API de MLB esté viva y rápida. El refresco de la mañana
    las hace una vez y acá queda el resultado.

    Se guardan TODOS los que jugaron, no solo los primeros, y **toda la temporada en curso**: unas 45
    filas por jornada, así que un año entero son ~8.000 — nada. A cambio se puede mostrar más, ordenar
    de otra forma o mirar una jornada de mayo sin volver a pedirle nada al proxy, que para un día
    viejo puede ya no devolver lo mismo.

    La poda va por TEMPORADA y no por antigüedad: cuando arranca una nueva, la anterior se borra
    entera. Eso resuelve solo el receso del Juego de Estrellas —cuatro días sin juegos en los que el
    widget sigue teniendo de dónde sacar la última jornada— que un tope de «los últimos N días»
    dejaría en blanco si N fuera corto.

    `valor` es lo que ordena y su escala depende del oficio: en bateo son carreras por pesos lineales
    (donde 0 es una jornada del montón) y en pitcheo es Game Score, que ronda 40-60. **No se comparan
    entre sí**, y por eso el widget muestra dos listas y no una. Ver `stats/daily.py`.
    """

    class Grupo(models.TextChoices):
        BATEO = "bateo", "Bateo"
        PITCHEO = "pitcheo", "Pitcheo"

    fecha = models.DateField(db_index=True, verbose_name="Jornada")
    grupo = models.CharField(max_length=8, choices=Grupo.choices, verbose_name="Oficio")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="jornadas", verbose_name="Jugador")
    team = models.CharField(max_length=4, blank=True, verbose_name="Equipo")
    # La línea ya escrita («3-4, 2B, HR, 4 RBI»). Se guarda armada y no en piezas: es texto de lectura,
    # no un dato del que se vaya a calcular nada, y rearmarla en la plantilla obligaría a llevar allá
    # las reglas de qué se nombra y qué se calla.
    linea = models.CharField(max_length=120, verbose_name="Línea")
    valor = models.FloatField(verbose_name="Valor")

    class Meta:
        db_table = "dgl_daily_standout"
        verbose_name = "actuación de la jornada"
        verbose_name_plural = "actuaciones de la jornada"
        constraints = [models.UniqueConstraint(fields=["fecha", "grupo", "player"], name="unique_daily_standout")]
        # El índice que sirve la portada: la jornada, su oficio, y el mejor primero.
        indexes = [models.Index(fields=["fecha", "grupo", "-valor"], name="dgl_standout_widget_idx")]

    def __str__(self) -> str:
        return f"{self.fecha} {self.player} ({self.linea})"


class MlbLeader(models.Model):
    """Un dominicano dentro de los diez primeros de las mayores, en una categoría de la temporada.

    NO ES LO MISMO QUE `Leader`
    ---------------------------
    `Leader` responde «quién es el mejor de entre los nuestros» y se calcula sobre nuestras propias
    tablas. Esta responde «cuáles de los nuestros están entre los mejores de las mayores», y sale del
    ranking que publica MLB. Ninguna de las dos se puede derivar de la otra: el motor propio no sabe
    contra quién más compiten, y el ranking de MLB solo enseña su top ~100 (ver `stats.mlb_leaders`).

    SOLO LA TEMPORADA EN CURSO
    --------------------------
    Es una foto, no un archivo: se borra entera y se reescribe en cada refresco. Quien salió del top
    diez tiene que desaparecer, y guardar el histórico haría creer que el puesto de una fila vieja
    sigue siendo cierto. Para lo de por vida está `Leader`.

    LA MÉTRICA NO SE NOMBRA ACÁ
    ---------------------------
    `metric` apunta al catálogo, que ya define la sigla y el nombre en español de cada estadística.
    Guardar acá una etiqueta propia terminaría diciendo «CI» donde el resto del sitio dice «RBI».
    """

    metric = models.ForeignKey(Metric, on_delete=models.CASCADE, related_name="mlb_leaders", verbose_name="Métrica")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="mlb_leaderships", verbose_name="Jugador")
    season = models.PositiveSmallIntegerField(verbose_name="Temporada")
    rank = models.PositiveSmallIntegerField(verbose_name="Puesto")
    # Texto y no número: el API manda «.328», «143.2» y «29», y cada estadística se escribe con sus
    # propios decimales. Pasarlo a float obligaría a reconstruir ese formato al mostrarlo.
    valor = models.CharField(max_length=12, verbose_name="Valor")
    team = models.CharField(max_length=4, blank=True, verbose_name="Equipo")

    class Meta:
        db_table = "dgl_mlb_leader"
        ordering = ["metric", "rank"]
        verbose_name = "dominicano en el top de MLB"
        verbose_name_plural = "dominicanos en el top de MLB"
        # Un jugador aparece una sola vez por métrica y temporada. Empatar en el décimo puesto es
        # normal —dos filas con `rank` 10— pero son jugadores distintos.
        #
        # La temporada entra en la clave aunque el janitor deje una sola: mientras se reprocesa una
        # vieja con `--temporada`, conviven dos, y sin ella la escritura reventaría.
        constraints = [models.UniqueConstraint(fields=["metric", "player", "season"], name="unique_mlb_leader")]
        indexes = [models.Index(fields=["season", "metric", "rank"], name="dgl_mlb_leader_widget_idx")]

    def __str__(self) -> str:
        return f"#{self.rank} {self.player} {self.metric.abbrev} {self.valor}"


class GameVideo(models.Model):
    """Un video de MLB donde un dominicano es el protagonista de la jugada.

    QUIÉN SALE EN EL VIDEO NO SE ADIVINA
    ------------------------------------
    `/api/v1/game/{pk}/content` etiqueta cada highlight con el `player_id` de quien protagoniza la
    jugada. Cruzado contra `dgl_master`, la atribución es exacta y no hay que leer títulos para
    saber de quién es — ver la regla de autoridad en `docs/AUTORIDAD.md`.

    NO HAY FORMA DE ATARLO A UN TURNO AL BATE
    -----------------------------------------
    El item no trae `playId` ni referencia a la jugada dentro del juego. Por eso el grano de esta
    tabla es **(jugador, fecha)** y no (jugador, turno): se puede decir «estos son los videos de
    Devers del 25 de julio», nunca «este video es de ese doble».

    POR QUÉ NO SE PODA
    ------------------
    A diferencia de `DailyStandout`, acá no hay janitor. Son unas 16 filas por día —menos de 3.000
    en una temporada— y borrarlas cerraría la puerta a un archivo por jugador, que es justo lo que
    esta tabla hace posible. Si algún día estorba, el criterio lo pone el dueño.
    """

    class Tipo(models.TextChoices):
        JONRON = "hr", "Jonrón"
        BATEO = "bateo", "Bateo"
        PITCHEO = "pitcheo", "Pitcheo"
        DEFENSA = "defensa", "Defensa"
        OTRO = "otro", "Otro"

    # El identificador estable del item en MLB. Es lo que hace que reprocesar un día no duplique.
    guid = models.CharField(max_length=40, verbose_name="GUID")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="videos", verbose_name="Jugador")
    fecha = models.DateField(db_index=True, verbose_name="Jornada")
    game_pk = models.PositiveIntegerField(verbose_name="Juego")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    segundos = models.PositiveSmallIntegerField(default=0, verbose_name="Duración (s)")
    # `tipo` sale de la taxonomía que trae el propio item, no de leer el título: sirve para elegir
    # cuál mostrar cuando un jugador tiene varios el mismo día — el jonrón antes que el sencillo.
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.OTRO, verbose_name="Tipo")
    video_url = models.URLField(max_length=400, verbose_name="Video (mp4)")
    imagen_url = models.URLField(max_length=400, blank=True, verbose_name="Portada")

    class Meta:
        db_table = "dgl_game_video"
        ordering = ["-fecha", "player"]
        verbose_name = "video de jugada"
        verbose_name_plural = "videos de jugadas"
        # Por (video, jugador) y no por video: una misma jugada puede etiquetar a dos dominicanos
        # —el que lanzó y el que bateó— y a los dos les toca.
        constraints = [models.UniqueConstraint(fields=["guid", "player"], name="unique_game_video")]
        indexes = [models.Index(fields=["fecha", "player"], name="dgl_video_jornada_idx")]

    def __str__(self) -> str:
        return f"{self.fecha} {self.player}: {self.titulo}"


class RosterMove(models.Model):
    """Un movimiento de roster de un dominicano: firmado, subido, bajado, cambiado, liberado.

    De dónde sale y por qué así está en `stats/roster_moves.py`. Lo que importa del modelo son tres
    decisiones.

    EL GRANO ES LA TRANSACCIÓN DE MLB, NO EL JUGADOR-DÍA
    ----------------------------------------------------
    Cada fila del feed trae un `id` propio y estable, y ese id es la clave única de acá. Es lo que
    permite que la corrida horaria pida SIEMPRE los últimos dos días y vuelva a guardar lo mismo sin
    duplicar: una corrida que falle no pierde nada, la siguiente la recupera. El horario del job pasa
    a ser una perilla de latencia y no de correctitud.

    EL JUGADOR NO ES UNA CLAVE FORÁNEA OBLIGATORIA
    ----------------------------------------------
    El universo dominicano es la unión de `dgl_master` y `dom_players`, y el segundo es mucho más grande: hay
    firmas de ligas menores de gente que todavía no llegó a las mayores y por lo tanto no tiene ficha.
    Medido sobre un mes: 117 movimientos de jugadores del maestro y 16 de los que solo están en
    `dom_players`, casi todos «Signed as Free Agent» a contrato de ligas menores.

    Por eso `player` admite nulo y siempre se guardan `mlb_id` y `nombre`. Con ficha, el cintillo
    enlaza; sin ficha, muestra el nombre y ya. Perder esas filas por no tener a quién apuntar sería
    tirar noticias que a un lector dominicano le importan.

    EL INGLÉS SE GUARDA, PERO NO SE MUESTRA
    ---------------------------------------
    `descripcion` es el texto tal como lo manda MLB. Se guarda porque es la materia prima de la
    traducción y porque, si un patrón deja de reconocerse, hace falta el original para arreglarlo.
    `texto` es la frase en español ya armada, y queda VACÍA cuando ningún patrón encajó — el sitio
    nunca enseña el inglés, así que una fila sin traducir simplemente no sale en el cintillo.
    """

    # El `id` de la transacción en MLB. Es lo que hace idempotente a la corrida horaria.
    transaction_id = models.BigIntegerField(unique=True, verbose_name="ID de la transacción")
    # El id de MLB de la persona. Se guarda suelto además de la FK porque la FK puede faltar.
    mlb_id = models.PositiveIntegerField(db_index=True, verbose_name="ID del jugador en MLB")
    player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movimientos",
        verbose_name="Jugador",
    )
    nombre = models.CharField(max_length=120, verbose_name="Nombre")
    fecha = models.DateField(db_index=True, verbose_name="Fecha")
    # El código corto de MLB (`SC`, `OPT`, `REL`…). Se guarda además del `type_desc` porque es el
    # identificador estable: la descripción legible la pueden reescribir, el código no.
    type_code = models.CharField(max_length=8, verbose_name="Código")
    type_desc = models.CharField(max_length=60, verbose_name="Tipo")
    desde = models.CharField(max_length=80, blank=True, verbose_name="Desde")
    hasta = models.CharField(max_length=80, blank=True, verbose_name="Hasta")
    descripcion = models.TextField(verbose_name="Texto original (inglés)")
    texto = models.TextField(blank=True, verbose_name="Texto en español")

    class Meta:
        db_table = "dgl_roster_move"
        ordering = ["-fecha", "-transaction_id"]
        verbose_name = "movimiento de roster"
        verbose_name_plural = "movimientos de roster"
        indexes = [models.Index(fields=["-fecha", "mlb_id"], name="dgl_roster_fecha_idx")]

    def __str__(self) -> str:
        return f"{self.fecha} {self.nombre}: {self.type_desc}"
