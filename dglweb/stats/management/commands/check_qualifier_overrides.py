"""¿Qué overrides de umbral ya los produce la regla del prorrateo? No escribe nada.

    manage.py check_qualifier_overrides

POR QUÉ EXISTE
--------------
Hasta el 2026-07-28 el dueño corregía a mano el umbral de cada temporada corta: una fila por
(temporada, oficio) en `dgl_qualifier_season_override`. Desde entonces el motor lo calcula —`3,1 x
juegos` en bateo, `1,0` en pitcheo, `0,617` en fildeo— y esas filas pasaron a ser, en su mayoría,
la misma cuenta escrita a mano.

Este comando dice cuáles. **No borra ninguna**, y eso es deliberado: son decisiones del dueño y una
regla no las pisa. Lo que hace es quitarle el trabajo de comprobar treinta filas a ojo para saber
cuáles ya sobran.

Y sirve para lo contrario, que importa más: **si la regla NO reproduce un override, hay que mirarlo.**
O el dueño sabía algo que la fórmula no —y entonces ese override es justo la razón por la que el
escalón manual existe— o la regla se apartó de su criterio y hay que revisarla.
"""

from typing import Any

from django.core.management.base import BaseCommand

from dglweb.stats import qualifier
from dglweb.stats.models import QualifierSeasonOverride, TeamSeasonGames


# Cuántos juegos representa una temporada, para prorratear. La MEDIANA y no el máximo: es el
# calendario programado, y es donde caen los seis overrides que el dueño escribió a mano —154 en
# 1958-60, 108 en 1981, 114 en 1994, 60 en 2020—. El máximo incluye desempates y dobles tandas
# reprogramadas, que no alargan el calendario de nadie más.
def _juegos_tipicos(temporada: int) -> int | None:
    juegos = sorted(TeamSeasonGames.objects.filter(season=temporada).values_list("games", flat=True))
    return juegos[len(juegos) // 2] if juegos else None


class Command(BaseCommand):
    help = "Dice qué overrides de umbral ya reproduce la regla del prorrateo. No borra nada."

    def handle(self, *args: Any, **options: Any) -> None:
        filas = QualifierSeasonOverride.objects.order_by("season", "stat_group")
        if not filas.exists():
            self.stdout.write("No hay overrides.")
            return

        redundantes: list[str] = []
        distintos: list[str] = []
        sin_juegos: list[str] = []

        for fila in filas:
            juegos = _juegos_tipicos(fila.season)
            if juegos is None:
                sin_juegos.append(f"{fila.season} {fila.stat_group}: {fila.qualifier_season}")
                continue
            calculado = qualifier.prorated(fila.stat_group, juegos)
            linea = (
                f"{fila.season} {fila.stat_group:9} tuyo={fila.qualifier_season:14} "
                f"regla={calculado:14} ({juegos} juegos)"
            )
            (redundantes if calculado == fila.qualifier_season else distintos).append(linea)

        self.stdout.write(f"{filas.count()} override(s) en total.\n")

        if redundantes:
            self.stdout.write(self.style.SUCCESS(f"\nLa regla ya produce estos {len(redundantes)} — se pueden borrar:"))
            for linea in redundantes:
                self.stdout.write(f"  {linea}")

        if distintos:
            self.stdout.write(self.style.WARNING(f"\nEstos {len(distintos)} NO coinciden — mirarlos:"))
            for linea in distintos:
                self.stdout.write(f"  {linea}")
            self.stdout.write(
                "  O sabías algo que la fórmula no —y entonces el override es justo para eso—\n"
                "  o la regla se apartó de tu criterio y hay que revisarla."
            )

        if sin_juegos:
            self.stdout.write(self.style.WARNING(f"\nEstos {len(sin_juegos)} no tienen juegos cargados:"))
            for linea in sin_juegos:
                self.stdout.write(f"  {linea}")
            self.stdout.write("  Corré `manage.py build_team_games --temporada AÑO`.")
