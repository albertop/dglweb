"""El universo dominicano: quién cuenta como dominicano, y quién todavía no ha debutado.

**REGLA DE AUTORIDAD.** Un jugador es dominicano si y solo si está en `dgl_master` o en
`dom_players`. Ningún campo de país decide — ni el nuestro ni, sobre todo, el `birthCountry` que
devuelve la API de MLB, que no es confiable. Ver el docstring de `players.models.Player`.

Las dos tablas son **disjuntas por construcción**: `dom_players` sale de la vista
`v_dglweb_master_no_debuts`, o sea el maestro SIN los que ya debutaron. De ahí que la resta de este
módulo sea la definición de "todavía no debutó" y no un apaño.

Por qué la resta y no un proceso de limpieza: entre que un pelotero debuta y que el dueño lo carga en
`dgl_master` pasan días, y entre eso y la próxima carga de `dom_players` pueden pasar meses. Durante
esa ventana está en las dos tablas. Un janitor que lo borrara sería una pieza móvil que puede no
correr, correr tarde, o pelearse con la carga por truncate; la resta no puede fallar porque no es un
proceso, es la pregunta bien hecha.
"""


def universe() -> set[int]:
    """Todos los `player_id` dominicanos conocidos: los que debutaron y los que no."""
    return debuted() | not_debuted()


def debuted() -> set[int]:
    """Los que ya llegaron a Grandes Ligas — `dgl_master`.

    `todos` y no `objects`: un jugador dado de baja sigue siendo dominicano y se le sigue
    actualizando el dato, para que reactivarlo sea instantáneo. Con el manager filtrado, esa decisión
    se rompería sin que nada avise.
    """
    from dglweb.players.models import Player

    return set(Player.todos.values_list("player_id", flat=True))


def not_debuted() -> set[int]:
    """Los que todavía no debutaron — `dom_players` MENOS `dgl_master`.

    La resta es lo que hace que cargar a un debutante en el Backoffice sea, además, el acuse de
    recibo: deja de ser candidato en el momento en que entra al maestro, sin flag de "ya lo vi" ni
    pantalla de descartar. No hay ventana y no hay nada que agendar.
    """
    from dglweb.stats.models import DomPlayer

    return set(DomPlayer.objects.values_list("player_id", flat=True)) - debuted()
