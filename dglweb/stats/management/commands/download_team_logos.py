"""Bajar los logos de los 30 equipos a `static/img/equipos/`.

    manage.py download_team_logos
    manage.py download_team_logos --season 2027   # cuando entre un equipo nuevo o alguno cambie

Un comando y no un script suelto porque esto se vuelve a correr: los equipos rediseñan su logo cada
tantos años, y cuando pase hay que poder repetir la operación sin recordar de dónde salieron.

Se guardan con NUESTRO código de tres letras (`SDN.svg`) y no con el id de MLB: es el mismo código
que el sitio usa en todas las tablas, así la plantilla arma la ruta sin consultar nada.

Se sirven desde el sitio en vez de enlazarlos donde están: así el banner no depende de que un tercero
esté arriba, y treinta SVG pesan menos que una foto.
"""

from pathlib import Path
from typing import Any

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.mlb.client import build_client
from dglweb.stats._download import fetch_team_codes

FUENTE = "https://www.mlbstatic.com/team-logos/{}.svg"
CARPETA = Path("img") / "equipos"


class Command(BaseCommand):
    help = "Baja los logos de los equipos a static/img/equipos/."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--season", type=int, default=None, help="Temporada (default: la actual).")

    def handle(self, *args: Any, **options: Any) -> None:
        temporada = options["season"] or timezone.localdate().year
        destino = Path(settings.BASE_DIR) / "static" / CARPETA
        destino.mkdir(parents=True, exist_ok=True)

        codigos = fetch_team_codes(build_client(), temporada)
        bajados, fallados = 0, []
        with httpx.Client(timeout=15.0) as http:
            for equipo_id, codigo in sorted(codigos.items(), key=lambda par: par[1]):
                try:
                    respuesta = http.get(FUENTE.format(equipo_id))
                    respuesta.raise_for_status()
                except httpx.HTTPError as error:
                    # Un logo que falta no vale abortar los otros veintinueve: la plantilla se las
                    # arregla sin él y el comando dice cuáles hay que reintentar.
                    fallados.append(f"{codigo} ({error.__class__.__name__})")
                    continue
                (destino / f"{codigo}.svg").write_bytes(respuesta.content)
                bajados += 1

        self.stdout.write(self.style.SUCCESS(f"{bajados} logos en {destino}."))
        if fallados:
            self.stdout.write(self.style.WARNING(f"No se pudieron bajar: {', '.join(fallados)}."))
