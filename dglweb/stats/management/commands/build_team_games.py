"""Cuántos juegos jugó cada equipo en cada temporada — la base del umbral prorrateado.

    manage.py build_team_games                 # la temporada en curso
    manage.py build_team_games --desde 1956    # relleno histórico, una sola vez
    manage.py build_team_games --temporada 1981

POR QUÉ SE GUARDA EN VEZ DE PREGUNTARLO
---------------------------------------
Una temporada cerrada no cambia nunca, así que pedirla otra vez es gastar una llamada para recibir
lo mismo. El relleno de 1956-2025 son ~70 llamadas de 151 ms —once segundos, UNA vez— y a partir de
ahí solo la temporada en curso necesita refrescarse, dentro del refresco diario que ya corre.

QUÉ HACE CON LO QUE YA HABÍA
----------------------------
Upsert por (temporada, equipo). Las temporadas cerradas quedan idénticas al recargarlas, que es la
prueba de que el dato es estable; la en curso se actualiza sola cada día.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from dglweb.mlb.client import MlbProxyClient, build_client
from dglweb.stats._download import fetch_team_codes
from dglweb.stats.leagues import league_code
from dglweb.stats.models import SeasonDates, TeamSeasonGames
from dglweb.stats.runlog import record_run

# La primera temporada que publica el sitio: el debut de Ozzie Virgil.
PRIMERA = 1956

# Las dos ligas mayores. Se piden juntas en una sola llamada — el endpoint las acepta separadas por
# coma— para no gastar dos por temporada.
LIGAS = "103,104"


class Command(BaseCommand):
    help = "Guarda los juegos jugados por equipo y temporada (para el umbral prorrateado)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--temporada", type=int, default=None, help="Solo esta.")
        parser.add_argument(
            "--desde", type=int, default=None, help=f"Relleno desde este año hasta hoy (mín. {PRIMERA})."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        temporadas = self._elegir(options)
        cliente = build_client()
        with record_run("build_team_games", f"{temporadas[0]}-{temporadas[-1]}") as run:
            escritas = 0
            for temporada in temporadas:
                filas = self._traer(cliente, temporada)
                if not filas:
                    # Sin dato no se borra lo que hubiera: una respuesta vacía por un fallo de la
                    # fuente dejaría la temporada sin umbral, y el motor caería al fijo sin decirlo.
                    self.stdout.write(
                        self.style.WARNING(f"{temporada}: la fuente no devolvió juegos; se deja como estaba.")
                    )
                    continue
                escritas += self._guardar(temporada, filas)
            run.add_rows(escritas)
            run.note(f"{len(temporadas)} temporada(s).")
        self.stdout.write(self.style.SUCCESS(f"{escritas} filas escritas en {len(temporadas)} temporada(s)."))

    def _elegir(self, options: dict[str, Any]) -> list[int]:
        if options["temporada"]:
            return [options["temporada"]]
        if options["desde"]:
            return list(range(max(PRIMERA, options["desde"]), timezone.localdate().year + 1))
        activa = SeasonDates.objects.filter(sports_id=SeasonDates.MLB, is_active=True).order_by("-season").first()
        return [activa.season if activa else timezone.localdate().year]

    def _traer(self, cliente: MlbProxyClient, temporada: int) -> list[tuple[str, str, int]]:
        """(liga, equipo, juegos) de una temporada. Lista vacía si la fuente no sabe de ese año.

        Son DOS llamadas y no una: la tabla de posiciones identifica al equipo por id numérico —no
        trae el `teamCode`— y el sitio guarda el código de tres letras del dueño, que es el que
        llevan las filas de estadísticas. Sin la traducción no se podrían cruzar.
        """
        codigos = fetch_team_codes(cliente, temporada)
        datos = cliente.get("/api/v1/standings", {"leagueId": LIGAS, "season": str(temporada)})
        filas: list[tuple[str, str, int]] = []
        for grupo in datos.get("records", []):
            liga = league_code(grupo.get("league"))
            for registro in grupo.get("teamRecords", []):
                juegos = registro.get("G")
                identificador = (registro.get("team") or {}).get("id")
                codigo = codigos.get(identificador) if isinstance(identificador, int) else None
                if juegos and codigo:
                    filas.append((liga, codigo, int(juegos)))
        return filas

    def _guardar(self, temporada: int, filas: list[tuple[str, str, int]]) -> int:
        objetos = [
            TeamSeasonGames(season=temporada, league=liga, team=equipo, games=juegos) for liga, equipo, juegos in filas
        ]
        TeamSeasonGames.objects.bulk_create(
            objetos,
            update_conflicts=True,
            unique_fields=["season", "team"],
            update_fields=["league", "games", "updated_at"],
        )
        return len(objetos)
