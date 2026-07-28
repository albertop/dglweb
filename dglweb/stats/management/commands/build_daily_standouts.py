"""Guardar la actuación de los dominicanos en la jornada de ayer.

    manage.py build_daily_standouts                  # ayer
    manage.py build_daily_standouts --fecha 2026-07-25
    manage.py build_daily_standouts --force          # aunque estemos fuera de temporada

Alimenta el widget «Destacados de la jornada» de la portada. Guarda a TODOS los que jugaron —no solo
los primeros— y de paso borra las jornadas que ya no son de la temporada en curso.

La poda vive acá y no en un job aparte a propósito: quien escribe la tabla es quien mejor sabe qué
sobra en ella, y un janitor separado es una pieza más que puede dejar de correr sin que nadie note
que dejó de correr.
"""

from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from dglweb.mlb.client import build_client
from dglweb.players import universe
from dglweb.stats import daily, jobs, season_window
from dglweb.stats.runlog import record_run, record_skip


class Command(BaseCommand):
    help = "Guarda la actuación de los dominicanos en una jornada y poda las temporadas viejas."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--fecha", type=date.fromisoformat, default=None, help="Jornada (default: ayer).")
        parser.add_argument(
            "--fecha-hoy",
            action="store_true",
            help="La jornada de HOY, guardando solo los equipos cuyo juego ya terminó. Lo usa el job horario.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Corre aunque estemos fuera de temporada, y guarda una jornada que no ha terminado. "
                "Para reprocesar en invierno tras un arreglo."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("build_daily_standouts", note=self.stdout.write, force=options["force"]):
            return

        # Ayer y no hoy: los juegos terminan de noche, y el refresco corre a las 6 de la mañana. Pedir
        # «hoy» a esa hora devolvería una jornada que todavía no empezó.
        # `--fecha-hoy` en vez de `--fecha $(date)`: la fecha la tiene que resolver el proceso con SU
        # zona horaria, no el shell del scheduler. Con el contenedor en hora dominicana y el job
        # corriendo a las 00:50, las dos no coinciden — y el fallo sería guardar la jornada de ayer
        # creyendo que es la de hoy, una hora al día, sin que nada lo dijera.
        dia = options["fecha"] or timezone.localdate() - (timedelta(0) if options["fecha_hoy"] else timedelta(days=1))

        if options["fecha_hoy"] and not options["force"]:
            self._al_dia()
            return

        # LOS EQUIPOS QUE YA TERMINARON, cuando la jornada es la de hoy.
        #
        # Antes una jornada en curso sencillamente no se guardaba, y por eso el widget era una foto de
        # ayer que no se movía en 24 horas. Ahora sí se guarda, pero SOLO lo de los equipos cuyo juego
        # acabó: `byDateRange` no distingue terminado de en curso —devuelve lo acumulado hasta ese
        # instante— y sin filtrar publicaríamos «1.0 IP, 1 K» de alguien que sigue en el montículo.
        # Ese número cambiaría solo bajo los ojos del lector, que es peor que estar desactualizado.
        #
        # Medido el 27-07 a media tarde: entre los mejores del día aparecía un lanzador de SEA con el
        # juego en marcha. Con `--force` no se filtra, que es lo que hace falta para reprocesar.
        terminados: set[str] | None = None
        if dia >= timezone.localdate() and not options["force"]:
            terminados = daily.equipos_terminados(self._pizarra(), dia)
            if not terminados:
                # Ni un juego cerrado todavía. No es un fallo —a media mañana es lo normal— y anotarlo
                # como salto evita una fila roja en el Backoffice buscando una avería que no existe.
                record_skip("build_daily_standouts", dia.isoformat(), "ningún juego ha terminado todavía")
                self.stdout.write(f"{dia}: ningún juego ha terminado todavía.")
                return

        self._guardar(dia, terminados)

    # ── El modo del job horario ─────────────────────────────────────────────────────────────────

    def _al_dia(self) -> None:
        """Lo que corre cada hora: las jornadas VIVAS, según lo que diga la pizarra.

        DOS JORNADAS Y NO UNA, y esa es la corrección del review v10 (QA-02/SAB-01). La fecha civil
        del servidor no es la jornada de MLB: un juego del Pacífico empieza el 28 y termina a la 1:15
        de la madrugada dominicana del 29, pero sigue siendo del 28. Con `localdate()` a secas, a esa
        hora el job ya estaba preguntando por el 29 —donde todavía no ha empezado nada— y esa
        actuación no aparecía hasta el refresco de las 4:30.

        Ayer se deja de mirar en cuanto el refresco diario lo toma, no a una hora fija. Así el corte
        no es un número inventado: es el momento exacto en que otro proceso se hace cargo. En la
        práctica son cuatro corridas de más al día, entre las 00:50 y las 4:50.

        La pizarra ya trae ayer y hoy, así que las dos jornadas salen de la misma consulta.
        """
        hoy = timezone.localdate()
        pizarra = self._pizarra()
        jornadas = [d for d in (hoy - timedelta(days=1), hoy) if d == hoy or not _ya_la_tomo_el_refresco(d)]

        hubo = False
        for dia in jornadas:
            terminados = daily.equipos_terminados(pizarra, dia)
            if terminados:
                self._guardar(dia, terminados, alcance=jobs.ALCANCE_EN_CURSO)
                hubo = True

        if not hubo:
            # Ni un juego cerrado todavía. No es un fallo —a media mañana es lo normal— y anotarlo
            # como salto evita una fila roja en el Backoffice buscando una avería que no existe. El
            # semáforo sabe que en ESTE job un salto cuenta como sano; ver `stats/jobs.py`.
            record_skip(
                "build_daily_standouts",
                f"{hoy.isoformat()} {jobs.ALCANCE_EN_CURSO}",
                "ningún juego ha terminado todavía",
            )
            self.stdout.write(f"{hoy}: ningún juego ha terminado todavía.")

    def _pizarra(self) -> Any:  # `scoreboard.Pizarra`, sin importarlo acá arriba
        """La pizarra, y un fallo de verdad si no se pudo armar.

        NO PUEDE SALIR VACÍA Y SEGUIR: sin esto, un proxy caído devolvía `None`, de ahí salía un
        conjunto vacío de equipos terminados, y el comando lo anotaba como «ningún juego ha terminado
        todavía» — el mismo salto sano que a las diez de la mañana. Con el semáforo aceptando ese
        salto como bueno, el monitor se quedaba en verde mientras el widget se congelaba.

        Es la línea que hace honesto el `SKIPPED` de este job: «nadie ha terminado» tiene que
        significar eso y no «no pude preguntar».
        """
        from dglweb.stats import scoreboard

        pizarra = scoreboard.del_dia()
        if pizarra is None:
            raise CommandError("No se pudo armar la pizarra: sin ella no se sabe qué juegos terminaron.")
        return pizarra

    def _guardar(self, dia: date, terminados: set[str] | None, alcance: str = "") -> None:
        """Una jornada, con su fila en el log de ingesta.

        `alcance` marca en el `scope` que la corrida es del job horario. Lo necesita el semáforo para
        no confundir los dos modos de este mismo comando — ver `stats/jobs.py`.
        """
        with record_run("build_daily_standouts", f"{dia.isoformat()} {alcance}".strip()) as run:
            listas = daily.destacados(build_client(), dia, universe.debuted())
            if terminados is not None:
                listas = {oficio: [a for a in lista if a.equipo in terminados] for oficio, lista in listas.items()}
                run.note(f"Jornada en curso: {len(terminados)} equipos con el juego terminado.")
            guardadas = daily.guardar(dia, listas)
            run.add_rows(guardadas)
            run.note(f"{len(listas['bateo'])} bateadores, {len(listas['pitcheo'])} lanzadores.")

            podadas = daily.podar(_temporada_activa())
            if podadas:
                run.note(f"Podadas {podadas} filas de temporadas anteriores.")

        if not guardadas:
            # No es un fallo: pasa en el receso del Juego de Estrellas y en cualquier día libre.
            self.stdout.write(f"{dia}: no hubo juegos (o ningún dominicano vio acción).")
            return
        self.stdout.write(self.style.SUCCESS(f"{dia}: {guardadas} actuaciones guardadas."))
        for actuacion in listas["bateo"][:3]:
            self.stdout.write(f"  🏏 {actuacion.nombre} ({actuacion.equipo}): {actuacion.linea}")
        for actuacion in listas["pitcheo"][:2]:
            self.stdout.write(f"  ⚾ {actuacion.nombre} ({actuacion.equipo}): {actuacion.linea}")


def _ya_la_tomo_el_refresco(dia: date) -> bool:
    """¿El refresco diario ya guardó esa jornada como cerrada?

    Se mira por el `scope` SIN el sufijo de «en curso»: eso es exactamente lo que escribe el refresco
    de las 4:30 (y una corrida manual con `--fecha`), y nunca el job horario. Es lo que le permite al
    horario soltar la jornada de ayer sin que nadie le diga a qué hora.
    """
    from dglweb.stats.models import IngestRun

    return IngestRun.objects.filter(
        command="build_daily_standouts", scope=dia.isoformat(), status=IngestRun.Status.SUCCESS
    ).exists()


def _temporada_activa() -> int | None:
    from dglweb.stats.models import SeasonDates

    fila = SeasonDates.objects.filter(sports_id=season_window.MLB, is_active=True).order_by("-season").first()
    return fila.season if fila else None
