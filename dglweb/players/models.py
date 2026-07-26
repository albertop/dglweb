"""The master table of Dominican players who reached MLB.

Source: DGL SQL Server `dbo.dglMaster` (migrated per the owner's mapping query).
Schema derived from the real source columns/types — nothing assumed.

**Authority rule:** being in this table is what makes a player "a Dominican MLB player".
`birth_country_code` is informational input from the source, NOT the rule.

**ETL rule — the source uses 0 as a "no value" sentinel; these are converted to NULL:**
`statsID`→`yahoo_id`, `fanGraphID`→`fangraphs_id`, `signYear`→`sign_year`,
`yearDomHof`→`dom_hof_year`. That is why `sign_year` is nullable even though the
source column is NOT NULL.

Not to be confused with `dom_players` (a separate, broader table of Dominicans in MLB *and*
the minors, refreshed once or twice per season, used to detect debuts and roster moves).
"""

from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    from dglweb.stats.models import Batting


class VisiblePlayerManager(models.Manager["Player"]):
    """El manager por defecto: solo los jugadores visibles.

    Que el DEFAULT sea el seguro es la decisión de fondo. Un flag que hay que acordarse de filtrar en
    cada consulta nueva se va a olvidar, y el requisito es que un jugador dado de baja sea «como si
    no existiese» — eso solo se cumple si ver a los ocultos hay que PEDIRLO (`Player.todos`).

    Ojo: no alcanza para la data derivada. `build_leaders` y `build_career_totals` no pasan por acá:
    leen las tablas de stats y agrupan por `player_id`. Ver `dglweb.players.visibility`.
    """

    def get_queryset(self) -> models.QuerySet["Player"]:
        return super().get_queryset().filter(hidden=False)


class Player(models.Model):
    # Reverse accessors are created at runtime by the related models, so django-stubs cannot
    # see them; declaring them here is what makes `player.batting_seasons` type-check.
    if TYPE_CHECKING:
        batting_seasons: models.Manager["Batting"]

    # --- identity / external ids -------------------------------------------------
    player_id = models.PositiveIntegerField(primary_key=True, verbose_name="MLB ID")
    dgl_id = models.CharField(max_length=10, unique=True, verbose_name="DGL ID")
    bbref_id = models.CharField(max_length=10, unique=True, null=True, blank=True, verbose_name="Baseball-Reference")
    bbref_minor_id = models.CharField(
        max_length=15, unique=True, null=True, blank=True, verbose_name="Baseball-Reference (menores)"
    )
    retro_id = models.CharField(max_length=10, unique=True, null=True, blank=True, verbose_name="Retrosheet")
    yahoo_id = models.PositiveIntegerField(unique=True, null=True, blank=True, verbose_name="Yahoo")
    fangraphs_id = models.PositiveIntegerField(unique=True, null=True, blank=True, verbose_name="FanGraphs")
    register_id = models.CharField(max_length=10, unique=True, null=True, blank=True, verbose_name="Register")

    # --- names -------------------------------------------------------------------
    lastname_1 = models.CharField(max_length=30, verbose_name="Primer apellido")
    lastname_2 = models.CharField(max_length=30, null=True, blank=True, verbose_name="Segundo apellido")
    firstname = models.CharField(max_length=30, verbose_name="Nombre")
    secondname = models.CharField(max_length=30, null=True, blank=True, verbose_name="Segundo nombre")
    nickname = models.CharField(max_length=20, null=True, blank=True, verbose_name="Apodo")
    full_name = models.CharField(max_length=50, verbose_name="Nombre completo")

    # --- birth -------------------------------------------------------------------
    birth_date = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    birth_place = models.CharField(max_length=60, null=True, blank=True, verbose_name="Lugar de nacimiento")
    birth_province = models.CharField(max_length=60, null=True, blank=True, verbose_name="Provincia")
    birth_country_code = models.CharField(max_length=2, null=True, blank=True, verbose_name="País (código)")

    # --- physical / playing ------------------------------------------------------
    bats = models.CharField(max_length=1, null=True, blank=True, verbose_name="Batea")
    throws = models.CharField(max_length=1, null=True, blank=True, verbose_name="Lanza")
    height = models.CharField(
        max_length=4, null=True, blank=True, verbose_name="Estatura", help_text="Pies-pulgadas, ej. 5-10"
    )
    weight = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Peso (lb)")
    pos = models.CharField(max_length=2, null=True, blank=True, verbose_name="Posición")

    # --- career milestones -------------------------------------------------------
    debut_date = models.DateField(null=True, blank=True, verbose_name="Fecha de debut")
    death_date = models.DateField(null=True, blank=True, verbose_name="Fecha de fallecimiento")
    # Nullable because the ETL converts the source's 0 sentinel to NULL (see module docstring).
    sign_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Año de firma")
    sign_date = models.DateField(null=True, blank=True, verbose_name="Fecha de firma")
    dom_hof_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="Año Salón de la Fama RD")
    # Cooperstown (MLB Hall of Fame) induction year. Not in the SQL Server extract — the admin
    # fills it by hand in the backoffice, so it is not part of `import_dgl_master`'s columns.
    hof_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="Año Salón de la Fama (Cooperstown)")

    # La baja de un inscrito. No se borra la fila —el borrado es irreversible y se lleva por CASCADE
    # todas sus estadísticas— sino que se oculta: para el sitio deja de existir, para la tubería
    # sigue existiendo y se le sigue actualizando el dato, así que reactivarlo es instantáneo y no
    # exige un backfill. Tampoco es del extract de SQL Server: se prende y se apaga en el Backoffice.
    hidden = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Deshabilitado",
        help_text="El jugador desaparece del sitio: perfil, búsqueda y liderazgos. Es reversible.",
    )
    disabled_reason = models.TextField(
        blank=True,
        verbose_name="Motivo de la baja",
        help_text="Obligatorio al deshabilitar. Dentro de un año es lo único que va a explicar por "
        "qué falta este jugador, y si puede volver.",
    )

    # `objects` —el que se usa sin pensar en el código de la aplicación— es el filtrado. `todos` es
    # el que hay que pedir a propósito, y además es el `_default_manager` de Django, que NO es lo
    # mismo: esa es la plomería interna que usan el Backoffice y la validación de unicidad de los
    # formularios, y las dos tienen que ver a todo el mundo. Con el filtrado ahí, la pantalla de
    # edición daba 404 sobre un jugador oculto —o sea, no había forma de reactivarlo— y un `dgl_id`
    # ocupado por un oculto pasaba desapercibido al dar de alta a otro.
    todos = models.Manager["Player"]()
    objects = VisiblePlayerManager()

    class Meta:
        db_table = "dgl_master"
        ordering = ["full_name"]
        verbose_name = "jugador"
        verbose_name_plural = "jugadores"
        default_manager_name = "todos"  # ver el comentario de los managers: es la plomería del admin

    def __str__(self) -> str:
        return self.full_name

    def clean(self) -> None:
        """Deshabilitar exige decir por qué. Un booleano solo dice «está apagado»."""
        from django.core.exceptions import ValidationError

        if self.hidden and not self.disabled_reason.strip():
            raise ValidationError(
                {"disabled_reason": "Al deshabilitar un jugador hay que explicar por qué se da de baja."}
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Si cambió la visibilidad, rehace lo derivado — sin que nadie tenga que acordarse.

        Los liderazgos están materializados con el puesto ya escrito, así que ocultar a alguien no es
        solo sacarlo: los rangos de los que venían detrás tienen que cerrarse. Filtrarlo al leer
        dejaría la lista numerada 1, 2, 4.

        La lectura previa cuesta una consulta por `save()`, y no se paga donde importaría: el import
        del maestro escribe con `bulk_create`, que no pasa por acá.
        """
        previo = None
        if not self._state.adding:
            previo = Player.todos.filter(pk=self.pk).values_list("hidden", flat=True).first()
        super().save(*args, **kwargs)
        if previo is None or previo == self.hidden:
            return

        from django.db import transaction

        from dglweb.stats import rebuilds

        # Al COMMIT, no acá: si el guardado se revierte no hay nada que reconstruir, y arrancar un
        # hilo que lee la base desde adentro de la transacción lo dejaría viendo el estado viejo.
        transaction.on_commit(lambda: rebuilds.run_in_background(rebuilds.DERIVED))

    @property
    def slug(self) -> str:
        """SEO slug for the public page; always ends in the MLB id so it never collides."""
        from django.utils.text import slugify

        return f"{slugify(self.full_name)}-{self.player_id}"
