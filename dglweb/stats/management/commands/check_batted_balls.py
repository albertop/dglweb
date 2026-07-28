"""Audita los coeficientes de batazos ya guardados. No escribe nada.

    manage.py check_batted_balls
    manage.py check_batted_balls --desde 1999 --tolerancia 0

La guarda de `BattedBallHitsLoader.post_apply` impide que ENTRE una fila imposible, pero solo mira
las filas que toca ese import. Esto mira las que ya están: las que se cargaron antes de que la guarda
existiera, y las que llegan por el camino normal del proxy sin pasar por ningún CSV.

Qué busca: filas donde los cuatro tipos de batazo —outs de MLB más hits de Retrosheet— no caben en
los `balls_in_play` que reportó el proxy. Cuando eso pasa, GB%+FB%+LD%+PU% pasa de 100%, que es
imposible y a simple vista no se nota: un GB% de 41 no tiene nada de raro por sí solo.

**SALE SIEMPRE EN CERO salvo que se pida `--estricto`.** Regla del dueño (2026-07-27): ningún proceso
automático se detiene porque MLB entregue data mala. Ellos son la autoridad y nosotros consumidores;
si el dato viene descuadrado no hay nada que podamos hacer salvo dejar constancia y seguir. Este
comando informa — no es un portero.

`--estricto` existe para la auditoría a mano, cuando alguien quiere el código de salida para
encadenarlo con otra cosa. **No lo cuelgues de un job.**
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from dglweb.stats.derive import batted_ball_excess
from dglweb.stats.models import Batting, Pitching

# Cuántos batazos de más se dan por ruido de la fuente antes de gritar.
#
# EN BATAZOS ENTEROS Y NO EN PORCENTAJE, y no es un detalle de estilo: una tolerancia del 1% sale
# invertida respecto a lo que uno quiere. Medido sobre las 6.896 filas reconciliables de hoy —cuyo
# `balls_in_play` va de unas decenas a 922—, el 1% daría:
#
#     con  20 BIP → 0,2 batazos: NO perdona ni uno, justo donde el ruido es más esperable
#     con 164 BIP → 1,6 batazos
#     con 922 BIP → 9,2 batazos: deja pasar NUEVE imposibles sin decir nada, justo donde una
#                                carga mal armada se manifestaría
#
# O sea: estricta con las muestras chicas, donde una unidad no significa nada, y laxa con las
# grandes, que es donde un fallo sistemático se vería. En batazos enteros la regla es la misma para
# todas las filas, y coincide con el modo de fallo real: MLB descuadrado por uno consigo mismo.
#
# `--tolerancia 0` vuelve a la regla estricta, para auditar a fondo.
TOLERANCIA = 1

# Anomalías POR ENCIMA de la tolerancia que se decidió no tocar. Clave: (oficio, player_id, temporada).
#
# Hoy está vacía a propósito: la única que había —Soriano 2010, un batazo sobre 164— cae dentro de la
# tolerancia y ya no necesita mención aparte. Sigue documentada en `docs/DATOS_DE_APOYO.md`, que es
# donde tiene que estar el porqué.
#
# La lista existe para lo que la tolerancia no puede cubrir: un descuadre grande que se investigó y
# se aceptó. Añadir algo acá es una decisión sobre los datos, no un atajo para callar el comando —
# cada entrada lleva su explicación y hay una prueba que lo exige.
ACEPTADAS: dict[tuple[str, int, int], str] = {}

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
        parser.add_argument(
            "--tolerancia",
            type=int,
            default=TOLERANCIA,
            help=f"Batazos de más que se dan por ruido de la fuente (por defecto {TOLERANCIA}).",
        )
        parser.add_argument(
            "--estricto",
            action="store_true",
            help="Sale con código 1 si hay descuadres. Para auditar a mano, NO para un job.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        desde: int = options["desde"]
        limite: int = options["limite"]
        tolerancia: int = options["tolerancia"]
        malas: list[str] = []
        conocidas: list[str] = []
        vistas: set[tuple[str, int, int]] = set()
        revisadas = medibles = dentro_de_tolerancia = 0

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
                if exceso <= tolerancia:
                    dentro_de_tolerancia += 1
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

        # Las toleradas se CUENTAN aunque no se listen. Una a una no dicen nada, pero que el número
        # salte de 1 a 800 es justo la señal de un fallo sistemático que la tolerancia se comería en
        # silencio. Sin este renglón, la tolerancia sería una venda en vez de un umbral.
        if dentro_de_tolerancia:
            self.stdout.write(
                f"  {dentro_de_tolerancia:,} fila(s) se pasan por ≤{tolerancia} batazo(s): "
                "ruido de la fuente, dentro de tolerancia."
            )

        # Las conocidas se enseñan igual, aunque no fallen: si algún día una desaparece —porque la
        # fuente la corrigió— hay que sacarla de `ACEPTADAS`, y eso solo se nota si se ven.
        for linea in conocidas:
            self.stdout.write(self.style.WARNING(f"  conocida · {linea}"))

        # Una entrada de `ACEPTADAS` que ya no dispara es basura: o la fuente corrigió el dato, o la
        # fila desapareció. Se avisa para que se borre — una lista de excepciones que crece y nunca
        # se poda termina tapando problemas nuevos con el nombre de problemas viejos.
        if desde == 0 and tolerancia == TOLERANCIA:
            for clave in sorted(set(ACEPTADAS) - vistas):
                self.stdout.write(self.style.WARNING(f"  ACEPTADAS tiene {clave} y ya no falla: sacala de la lista."))

        if not malas:
            self.stdout.write(self.style.SUCCESS("Ningún coeficiente imposible fuera de lo esperado."))
            return

        self.stdout.write(self.style.WARNING(f"{len(malas)} fila(s) con coeficientes imposibles:"))
        for linea in malas[:limite]:
            self.stdout.write(f"  {linea}")
        if len(malas) > limite:
            self.stdout.write(f"  … y {len(malas) - limite} más.")
        self.stdout.write(
            "Es dato de la fuente y no hay nada que corregir de nuestro lado. Queda constancia."
        )
        # El código de salida solo con `--estricto`. Por defecto cero: ver la cabecera del módulo.
        if options["estricto"]:
            raise SystemExit(1)
