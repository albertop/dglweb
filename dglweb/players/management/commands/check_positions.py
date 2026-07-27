"""Revisar —y opcionalmente corregir— la posición de cada pelotero en el maestro.

    manage.py check_positions                    # solo informa
    manage.py check_positions --aplicar          # además escribe
    manage.py check_positions --min-ip 50        # más exigente con los de posición
    manage.py check_positions --ventana 5

**Informa por defecto y escribe solo si se lo piden.** `dgl_master` es la tabla del dueño: un proceso
semanal que sobrescriba por su cuenta puede pisar una corrección hecha a mano sin que nadie se
entere. Con `--aplicar` la decisión es explícita, y el log deja qué cambió.

El criterio vive en `players/positions.py`, con el porqué de cada regla.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from dglweb.core import notify
from dglweb.players import positions
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Compara la posición del maestro con la que dicen las estadísticas. Con --aplicar, la corrige."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--aplicar", action="store_true", help="Escribe las posiciones sugeridas en el maestro.")
        parser.add_argument(
            "--ventana", type=int, default=positions.VENTANA, help="Temporadas hacia atrás que definen «hoy»."
        )
        parser.add_argument(
            "--min-ip",
            type=float,
            default=positions.MIN_ENTRADAS,
            help="Entradas mínimas para mover a un jugador de posición (no aplica a lanzadores).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # Sin puerta de temporada: lee nuestras propias tablas, no el proxy, y una posición
        # recalculada en invierno es la misma que en agosto.
        with record_run("check_positions", "dgl_master") as run:
            cambios = positions.discrepancias(ventana=options["ventana"], min_entradas=options["min_ip"])
            run.add_rows(len(cambios))
            for cambio in cambios:
                run.note(str(cambio))

            if options["aplicar"] and cambios:
                positions.aplicar(cambios)
                run.note(f"APLICADO: {len(cambios)} posiciones corregidas en dgl_master.")

        self._informar(cambios, aplicado=options["aplicar"])
        self._avisar(cambios, aplicado=options["aplicar"])

    def _informar(self, cambios: list[positions.Discrepancia], *, aplicado: bool) -> None:
        if not cambios:
            self.stdout.write("Las posiciones del maestro coinciden con las estadísticas.")
            return

        verbo = "corregidas" if aplicado else "por revisar"
        self.stdout.write(self.style.WARNING(f"{len(cambios)} posiciones {verbo}:"))
        for cambio in cambios:
            self.stdout.write(f"  {cambio}")
        if not aplicado:
            self.stdout.write("\nPara escribirlas: manage.py check_positions --aplicar")

    def _avisar(self, cambios: list[positions.Discrepancia], *, aplicado: bool) -> None:
        """Telegram solo cuando hay algo que hacer, y con la cuenta y no la lista.

        Cien nombres en el teléfono no se leen. Lo que el aviso tiene que lograr es que el dueño abra
        el Backoffice; el detalle completo ya está en el log de esa corrida.
        """
        if not cambios:
            return
        if aplicado:
            texto = f"✅ {len(cambios)} posiciones corregidas en dgl_master.\n\nEl detalle está en el log de ingesta."
        else:
            texto = (
                f"📋 {len(cambios)} posiciones del maestro no coinciden con las estadísticas.\n\n"
                "El detalle está en el log de ingesta (check_positions).\n"
                "Para aplicarlas: manage.py check_positions --aplicar"
            )
        notify.enviar(texto)
