"""Avisar de dominicanos que debutaron y todavía no están en el maestro.

    manage.py detect_debuts                 # la temporada en curso
    manage.py detect_debuts --season 2025
    manage.py detect_debuts --force         # aunque estemos fuera de temporada

No escribe nada: `dom_players` se rellena por truncate desde una vista de DGL y `dgl_master` lo
mantiene el dueño, así que este comando **detecta y avisa**, nunca promueve. La promoción ocurre en
DGL y el jugador sale solo de la vista en el siguiente export.

El resultado va al log de ingesta —la misma pantalla donde se mira todo lo demás— con la cuenta en
`rows_affected` para que se vea de un vistazo en el listado, y los nombres en el detalle.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.core import notify
from dglweb.mlb.client import build_client
from dglweb.players import debuts
from dglweb.stats import season_window
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Detecta dominicanos sin debut que ya tienen estadísticas de la temporada."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--season", type=int, default=None, help="Temporada a revisar (default: la actual).")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada. Para reprocesar en invierno tras un arreglo.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("detect_debuts", note=self.stdout.write, force=options["force"]):
            return

        season = options["season"] or timezone.now().year

        with record_run("detect_debuts", str(season)) as run:
            encontrados = debuts.detect(build_client(), season)
            run.add_rows(len(encontrados))
            for debut in encontrados:
                run.note(str(debut))

        self._avisar(season, encontrados)

        if not encontrados:
            self.stdout.write(f"{season}: sin debuts pendientes de cargar.")
            return

        # Ruidoso a propósito: es un pendiente que exige una acción humana, y va a repetirse todos
        # los días hasta que el dueño cargue al jugador en el Backoffice — que es el acuse de recibo.
        self.stdout.write(self.style.WARNING(f"{season}: {len(encontrados)} debut(s) por cargar en dgl_master:"))
        for debut in encontrados:
            self.stdout.write(f"  {debut}")

    def _avisar(self, season: int, pendientes: list[debuts.Debut]) -> None:
        """Avisa de TODOS los que faltan por cargar, todos los días, hasta que dejen de faltar.

        Hubo una versión que avisaba una sola vez por debutante, para no repetirse. **El dueño pidió
        lo contrario, y tiene razón**: si el aviso sale un martes y ese día no lo ve, el pelotero se
        queda fuera del sitio sin que nada vuelva a recordarlo. La repetición no es ruido acá — es
        justamente el mecanismo, y para en cuanto carga al jugador, que es el acuse de recibo.

        Por eso son pocos y raros —un puñado al año— y por eso no hace falta protegerse de la
        insistencia: el canal no se satura con esto.
        """
        if not pendientes:
            return
        # `debut.aviso` y no `str(debut)`: el del log empieza por el id, y en el teléfono ese número
        # se leería como parte de la viñeta en vez de como un dato. Ver `debuts.Debut`.
        lineas = [f"⚾ Debut dominicano en Grandes Ligas ({season})", ""]
        lineas += [debut.aviso for debut in pendientes]
        lineas += ["", "Cargalo en el Backoffice para que aparezca en el sitio."]
        notify.enviar("\n".join(lineas))
