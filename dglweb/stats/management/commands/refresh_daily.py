"""El refresco diario completo, en un solo comando.

    manage.py refresh_daily                     # lo que corre el scheduler
    manage.py refresh_daily --publicar-parcial  # reconstruye aunque falte un insumo
    manage.py refresh_daily --force             # aunque estemos fuera de temporada

Reemplaza a los diez horarios que se encadenaban por reloj. La lógica vive en `stats/pipeline.py`;
acá solo están los argumentos y la salida por consola.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.stats import locks, pipeline, runlog
from dglweb.stats.locks import MOTIVO_OCUPADO

__all__ = ["MOTIVO_OCUPADO", "Command"]


class Command(BaseCommand):
    help = "Corre el refresco diario completo, con los derivados dependiendo de las entradas."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada.",
        )
        parser.add_argument(
            "--publicar-parcial",
            action="store_true",
            dest="publicar_parcial",
            help="Reconstruye los derivados aunque alguna entrada haya fallado. Por defecto NO se hace.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # UN REFRESCO A LA VEZ (QA-01 del review v13). Dos solapados pueden atribuirse mutuamente el
        # resultado de sus pasos: `_estado_de()` busca la fila más reciente del comando, no la suya.
        # Comprobado — un PARTIAL se leía como SUCCESS. Ver `locks.refresco_exclusivo`.
        with locks.refresco_exclusivo() as tomado:
            if not tomado:
                # Se registra el salto en vez de callarlo: un refresco que no dejó rastro se lee como
                # un scheduler que no corrió, y eso ya costó días de no darse cuenta una vez.
                runlog.record_skip("refresh_daily", str(timezone.localdate()), MOTIVO_OCUPADO)
                self.stdout.write(f"Sin correr — {MOTIVO_OCUPADO}")
                return

            resultado = pipeline.run_and_record(
                force=options["force"],
                publicar_parcial=options["publicar_parcial"],
                note=self.stdout.write,
            )

        if resultado.motivo_salto:
            self.stdout.write(f"Sin correr — {resultado.motivo_salto}")
            return

        fallidos = resultado.fallidos
        resumen = f"{len(resultado.pasos) - len(fallidos)}/{len(resultado.pasos)} pasos · {resultado.filas:,} filas"
        if fallidos:
            # Ruidoso a propósito: si el scheduler manda esto a un log, el fallo tiene que verse ahí
            # aunque nadie abra el Backoffice.
            self.stderr.write(self.style.ERROR(f"Refresco con fallos — {resumen}"))
            for paso in fallidos:
                self.stderr.write(f"  {paso}")
            return
        self.stdout.write(self.style.SUCCESS(f"Refresco completo — {resumen}"))
