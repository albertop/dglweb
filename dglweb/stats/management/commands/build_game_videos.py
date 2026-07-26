"""Guardar los videos de MLB donde un dominicano protagonizó la jugada.

    manage.py build_game_videos                  # ayer
    manage.py build_game_videos --fecha 2026-07-25
    manage.py build_game_videos --force          # aunque estemos fuera de temporada

Corre de mañana junto al resto del refresco, y por eso mira a AYER: los videos de un juego aparecen
al ratito de terminar, y a las seis de la mañana la jornada anterior ya está completa.

Cuesta una llamada por juego —quince en una jornada normal— porque el contenido es por juego y no
hay endpoint que devuelva el de toda la liga de una vez.
"""

from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.mlb.client import build_client
from dglweb.stats import season_window, videos
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Guarda los videos de jugadas dominicanas de una jornada."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--fecha", type=date.fromisoformat, default=None, help="Jornada (default: ayer).")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Corre aunque estemos fuera de temporada. Para reprocesar en invierno tras un arreglo.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if season_window.skip("build_game_videos", note=self.stdout.write, force=options["force"]):
            return

        dia = options["fecha"] or timezone.localdate() - timedelta(days=1)

        with record_run("build_game_videos", dia.isoformat()) as run:
            encontrados = videos.de_la_jornada(build_client(), dia)
            guardados = videos.guardar(dia, encontrados)
            run.add_rows(guardados)
            run.note(f"{guardados} videos de {len({v.player_id for v in encontrados})} jugadores.")

        if not guardados:
            # No es un fallo: pasa en un día libre y en cualquier jornada sin dominicanos destacados.
            self.stdout.write(f"{dia}: ningún video dominicano.")
            return
        self.stdout.write(self.style.SUCCESS(f"{dia}: {guardados} videos guardados."))
        for video in encontrados[:5]:
            self.stdout.write(f"  ▶ {video.titulo}")
