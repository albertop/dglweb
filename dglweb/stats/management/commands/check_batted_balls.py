"""Audita los coeficientes de batazos ya guardados. No escribe nada.

    manage.py check_batted_balls
    manage.py check_batted_balls --desde 1999 --limite 50

La guarda de `BattedBallHitsLoader.post_apply` impide que ENTRE una fila imposible, pero solo mira
las filas que toca ese import. Esto mira las que ya están: las que se cargaron antes de que la guarda
existiera, y las que llegan por el camino normal del proxy sin pasar por ningún CSV.

Qué busca: filas donde los cuatro tipos de batazo —outs de MLB más hits de Retrosheet— no caben en
los `balls_in_play` que reportó el proxy. Cuando eso pasa, GB%+FB%+LD%+PU% pasa de 100%, que es
imposible y a simple vista no se nota: un GB% de 41 no tiene nada de raro por sí solo.

Sale con código 1 solo si encuentra algo FUERA de `ACEPTADAS`, para poder colgarlo de un job sin leer
la salida. Las anomalías ya decididas se listan pero no fallan — ver el comentario de esa lista.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from dglweb.stats.derive import batted_ball_excess
from dglweb.stats.models import Batting, Pitching

# Las anomalías que vienen de la fuente y se decidió NO tocar. Clave: (oficio, player_id, temporada).
#
# Esta lista existe para que la auditoría pueda salir en VERDE. Un comando que siempre termina en
# rojo es un comando que nadie corre —y entonces no sirve de nada haberlo construido—, así que lo
# conocido se lista aparte y no falla; cualquier fila nueva sí.
#
# Añadir algo acá es una decisión sobre los datos, no un atajo para callar el comando: cada entrada
# lleva por qué se acepta, y el detalle largo está en `docs/DATOS_DE_APOYO.md`.
ACEPTADAS: dict[tuple[str, int, int], str] = {
    ("pitcheo", 400089, 2010): (
        "Rafael Soriano: 165 batazos contra 164 BIP. Los hits son del propio proxy —2010 no se "
        "carga del CSV de Retrosheet—, así que es MLB inconsistente consigo mismo. Decisión del "
        "dueño (2026-07-27): se deja, corregirlo sería inventar un dato."
    ),
}

# Lo que `batted_ball_excess` necesita. Se piden con `values()` y no como objetos: son decenas de
# miles de filas y acá no hace falta nada más que estos números.
CAMPOS = (
    "player_id",
    "season",
    "ground_outs",
    "fly_outs",
    "line_outs",
    "pop_outs",
    "ground_hits",
    "fly_hits",
    "line_hits",
    "pop_hits",
    "balls_in_play",
)


class Command(BaseCommand):
    help = "Busca filas donde los cuatro tipos de batazo no caben en balls_in_play (SAB-02)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--desde", type=int, default=0, help="Temporada mínima a revisar.")
        parser.add_argument("--limite", type=int, default=20, help="Cuántas filas malas listar.")

    def handle(self, *args: Any, **options: Any) -> None:
        desde: int = options["desde"]
        limite: int = options["limite"]
        malas: list[str] = []
        conocidas: list[str] = []
        vistas: set[tuple[str, int, int]] = set()
        revisadas = medibles = 0

        for oficio, model in (("bateo", Batting), ("pitcheo", Pitching)):
            filas = model.objects.filter(season__gte=desde).values(*CAMPOS)
            for fila in filas.iterator(chunk_size=2000):
                revisadas += 1
                exceso = batted_ball_excess(dict(fila))
                if exceso is None:
                    continue  # sin BIP o sin tipificar: no hay nada que reconciliar
                medibles += 1
                if exceso <= 0:
                    continue
                clave = (oficio, fila["player_id"], fila["season"])
                linea = (
                    f"{oficio}: jugador {fila['player_id']} {fila['season']} — "
                    f"{exceso} batazo(s) por encima de {fila['balls_in_play']} BIP"
                )
                if clave in ACEPTADAS:
                    vistas.add(clave)
                    conocidas.append(linea)
                else:
                    malas.append(linea)

        # El total de medibles va SIEMPRE, aunque no haya nada malo. Un «0 problemas» sin decir sobre
        # cuántas filas se midió no distingue una base sana de un filtro que no encontró nada.
        self.stdout.write(f"Revisadas {revisadas:,} filas; {medibles:,} se pueden reconciliar.")
        # Las conocidas se enseñan igual, aunque no fallen: si algún día una desaparece —porque la
        # fuente la corrigió— hay que sacarla de `ACEPTADAS`, y eso solo se nota si se ven.
        for linea in conocidas:
            self.stdout.write(self.style.WARNING(f"  conocida · {linea}"))

        # Una entrada de `ACEPTADAS` que ya no dispara es basura: o la fuente corrigió el dato, o la
        # fila desapareció. Se avisa para que se borre — una lista de excepciones que crece y nunca
        # se poda termina tapando problemas nuevos con el nombre de problemas viejos.
        if desde == 0:  # solo tiene sentido con la base entera a la vista
            for clave in sorted(set(ACEPTADAS) - vistas):
                self.stdout.write(self.style.WARNING(f"  ACEPTADAS tiene {clave} y ya no falla: sacala de la lista."))

        if not malas:
            self.stdout.write(self.style.SUCCESS("Ningún coeficiente imposible fuera de lo conocido."))
            return

        self.stdout.write(self.style.ERROR(f"{len(malas)} fila(s) con coeficientes imposibles:"))
        for linea in malas[:limite]:
            self.stdout.write(f"  {linea}")
        if len(malas) > limite:
            self.stdout.write(f"  … y {len(malas) - limite} más.")
        raise SystemExit(1)
