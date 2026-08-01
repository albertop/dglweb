"""La ventana de catorce días: umbral, percentiles y el reparto entre oficios.

Las reglas que se comprueban acá son decisiones del dueño, no criterio del código: catorce días
naturales, el corte del 15% **de la liga entera** por oficio, y diez como mucho repartidos cinco y
cinco. Cada una tiene su prueba porque cada una se puede romper sin que la página se caiga.
"""

from datetime import date, timedelta

import pytest

from dglweb.players.models import Player
from dglweb.stats import ventana
from dglweb.stats.models import WindowStandout
from tests.test_players import _other_player

HOY = date(2026, 7, 31)


def _jugador(pid: int, nombre: str, apellido: str) -> Player:
    return Player.todos.create(
        **_other_player(
            player_id=pid, dgl_id=f"v{pid}", full_name=f"{nombre} {apellido}", firstname=nombre, lastname_1=apellido
        )
    )


def _fila(valor: float, grupo: str = "bateo") -> ventana.Fila:
    """Una fila del widget con lo justo para que `repartir` la pueda ordenar y elegir."""
    return ventana.Fila(player=None, team="SDN", linea="", valor=valor, juegos=10, grupo=grupo)


# ── El umbral ───────────────────────────────────────────────────────────────────────────────────


def test_the_threshold_comes_from_what_was_actually_played() -> None:
    """Catorce días no son catorce juegos: hay días libres, dobles carteleras y el receso.

    Un número escrito a mano quedaría largo en julio y corto en septiembre sin que nada lo dijera.
    """
    splits = [{"stat": {"G": str(j)}} for j in [4, 6, 8, 10, 11, 11, 12, 12, 12, 12, 12, 13]]

    assert ventana._umbral(splits, ventana.PA_POR_JUEGO) == pytest.approx(3.1 * 12)


def test_the_denominator_is_the_p90_and_not_the_maximum() -> None:
    """El máximo lo pone un solo jugador: una doble cartelera subiría el listón a los treinta.

    Y no es la mediana, que la baja el que estuvo lesionado media ventana — que es justo a quien el
    umbral tiene que dejar fuera.
    """
    normales = [{"stat": {"G": "10"}} for _ in range(20)]
    uno_que_jugo_de_mas = [{"stat": {"G": "20"}}]

    assert ventana._umbral(normales + uno_que_jugo_de_mas, 1.0) == pytest.approx(10.0)


def test_an_empty_window_does_not_divide_by_anything() -> None:
    """En pretemporada no hay splits, y eso no puede ser una excepción sin atrapar."""
    assert ventana._umbral([], 3.1) == 0.0


# ── El reparto entre oficios ────────────────────────────────────────────────────────────────────


def test_ten_at_most_five_of_each() -> None:
    """Decisión del dueño: cinco bateadores y cinco lanzadores."""
    filas = [_fila(9 - i, "bateo" if i % 2 == 0 else "pitcheo") for i in range(20)]

    elegidos = ventana.repartir(filas)

    assert len(elegidos) == 10
    assert sum(1 for f in elegidos if f.grupo == "bateo") == 5
    assert sum(1 for f in elegidos if f.grupo == "pitcheo") == 5


def test_a_short_office_is_filled_by_the_other() -> None:
    """«Si hay solo 3 lanzadores, entonces completar con 7 bateadores» — palabras del dueño."""
    filas = [_fila(20 - i, "pitcheo") for i in range(3)] + [_fila(10 - i, "bateo") for i in range(9)]

    elegidos = ventana.repartir(filas)

    assert len(elegidos) == 10
    assert sum(1 for f in elegidos if f.grupo == "pitcheo") == 3
    assert sum(1 for f in elegidos if f.grupo == "bateo") == 7


def test_the_order_of_merit_survives_the_split() -> None:
    """La lista se lee por mérito. Agrupada por oficio habría que leer las diez para saber quién manda."""
    filas = [_fila(9 - i, "bateo" if i % 3 else "pitcheo") for i in range(12)]

    valores = [f.valor for f in ventana.repartir(filas)]

    assert valores == sorted(valores, reverse=True)


def test_fewer_than_ten_are_all_kept() -> None:
    """Con seis candidatos no hay nada que repartir: entran los seis."""
    filas = [_fila(5 - i, "bateo") for i in range(6)]

    assert len(ventana.repartir(filas)) == 6


def test_the_filling_takes_the_next_best_and_not_the_first_it_finds() -> None:
    """Los que entran por cupo sobrante son los siguientes MEJORES, no los que aparezcan antes."""
    filas = [_fila(100 - i, "bateo") for i in range(9)] + [_fila(1, "pitcheo")]

    elegidos = ventana.repartir(filas)

    assert len(elegidos) == 10
    # El lanzador entra por su oficio y los nueve bateadores caben, así que están todos.
    assert min(f.valor for f in elegidos if f.grupo == "bateo") == 92


# ── Los dos widgets, de punta a punta ───────────────────────────────────────────────────────────


def _guardar(valores: list[tuple[float, str]]) -> None:
    for indice, (valor, grupo) in enumerate(valores):
        jugador = _jugador(1000 + indice, "Juan", f"Prueba{indice}")
        WindowStandout.objects.create(
            desde=HOY - timedelta(days=13), hasta=HOY, grupo=grupo, player=jugador,
            team="SDN", linea=f"linea {indice}", valor=valor, juegos=10, oportunidades=40,
        )  # fmt: skip


@pytest.mark.django_db
def test_the_two_ends_come_from_the_same_cut() -> None:
    """Son las dos puntas de UNA distribución, no dos preguntas: se calculan a la vez."""
    _guardar([(float(v), "bateo") for v in range(-10, 11)])

    foto = ventana.portada()

    assert foto is not None
    assert foto["quemando"]["lista"][0].valor > foto["pasando"]["lista"][0].valor
    # El de arriba encabeza con el mejor y el de abajo con el PEOR: los dos se leen igual, de más a
    # menos extremo. Al revés habría que explicarle al lector que uno va al derecho y otro al revés.
    assert foto["quemando"]["lista"][0].valor == max(w.valor for w in WindowStandout.objects.all())
    assert foto["pasando"]["lista"][0].valor == min(w.valor for w in WindowStandout.objects.all())


@pytest.mark.django_db
def test_nobody_reaching_either_cut_draws_nothing() -> None:
    """Una tanda entera del montón no llena ninguna de las dos puntas, y un panel hueco se lee como
    un sitio roto. Pasa de verdad en el receso."""
    _guardar([(0.5, "bateo"), (1.0, "bateo"), (-1.0, "pitcheo"), (0.0, "bateo")])

    assert ventana.portada() is None


@pytest.mark.django_db
def test_nothing_stored_draws_nothing() -> None:
    """En pretemporada la tabla está vacía y la portada no puede dibujar un panel hueco."""
    assert ventana.portada() is None


@pytest.mark.django_db
def test_the_cut_is_the_fixed_league_one_and_not_one_derived_from_the_table() -> None:
    """LA REGRESIÓN que importa. La tabla solo tiene dominicanos, así que un percentil sacado de ella
    sería la vara de cuarenta personas: medido, se movía de +3,02 a +3,54 en quince días.

    Con los cortes fijos, quién entra no depende de con quién le tocó compartir la tabla.
    """
    _guardar([(1.0, "bateo"), (1.5, "bateo"), (2.1, "bateo"), (3.5, "bateo"), (5.0, "pitcheo")])

    foto = ventana.portada()

    assert foto is not None
    # Solo los que pasan su propio corte: +3,5 en bateo y +3,7 en pitcheo. Un percentil sobre estos
    # cinco habría dejado entrar al de 2,1, que no llega al listón de la liga.
    assert [f.valor for f in foto["quemando"]["lista"]] == [5.0, 3.5]
    assert all(f.valor >= ventana.CORTES[f.grupo][0] for f in foto["quemando"]["lista"])


@pytest.mark.django_db
def test_each_office_is_judged_against_its_own_distribution() -> None:
    """Lo vio el dueño mirando el widget: en «Pasando trabajo» los lanzadores estaban hundidos y los
    bateadores solo flojos. Medido, las dos distribuciones no se parecen — el p15 del bateo es -3,0 y
    el del pitcheo -2,0— así que un corte único exigía cosas distintas a cada oficio.
    """
    _guardar([(-2.0, "bateo"), (-2.0, "pitcheo")])

    foto = ventana.portada()

    assert foto is not None
    # El mismo valor: al lanzador le basta para estar mal (su corte es -1,3) y al bateador no (-2,6).
    assert [f.grupo for f in foto["pasando"]["lista"]] == ["pitcheo"]


# ── Lo que se guarda ────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_saving_replaces_the_whole_snapshot() -> None:
    """Una ventana móvil no tiene historia: la de ayer ya no es cierta y guardarla haría creer que sí."""
    _guardar([(3.0, "bateo")])
    viejo = _jugador(2001, "Pedro", "Viejo")
    nuevo = _jugador(2002, "Ana", "Nueva")
    WindowStandout.objects.all().delete()
    WindowStandout.objects.create(
        desde=HOY, hasta=HOY, grupo="bateo", player=viejo, team="SDN", linea="vieja", valor=1, juegos=1
    )

    ventana.guardar(
        [
            {
                "player_id": nuevo.player_id,
                "team": "MIA",
                "grupo": "bateo",
                "linea": "nueva",
                "valor": 2.0,
                "juegos": 10,
                "oportunidades": 40,
                "desde": HOY,
                "hasta": HOY,
            }
        ]
    )

    assert [w.linea for w in WindowStandout.objects.all()] == ["nueva"]


@pytest.mark.django_db
def test_a_player_the_master_does_not_know_is_skipped() -> None:
    """El universo dice quién es dominicano, pero la fila del maestro puede no estar: un
    `bulk_create` con una clave ajena rota tumbaría la corrida entera."""
    guardadas = ventana.guardar(
        [
            {
                "player_id": 999999,
                "team": "MIA",
                "grupo": "bateo",
                "linea": "x",
                "valor": 1.0,
                "juegos": 1,
                "oportunidades": 1,
                "desde": HOY,
                "hasta": HOY,
            }
        ]
    )

    assert guardadas == 0


def test_the_window_is_fourteen_days() -> None:
    """Decisión del dueño. Se descartó «los últimos 10 juegos» —que el proxy sí sabe responder—
    porque es por JUGADOR: el que vuelve de lesión trae diez juegos repartidos en seis semanas."""
    assert ventana.DIAS == 14


# ── Cómo se escriben las líneas de la ventana ───────────────────────────────────────────────────


def test_the_batting_line_drops_the_at_bats() -> None:
    """«17-43» obliga a dividir, y el promedio de catorce días dice más del azar que del bateador.

    Decisión del dueño, 2026-07-31.
    """
    linea = ventana.linea_de_bateo({"H": "17", "AB": "43", "AVG": ".395", "X2B": "1", "HR": "6", "RBI": "9", "R": "13"})

    assert linea == ".395, 2B, 6 HR, 9 RBI, 13 R"
    assert "-43" not in linea


def test_the_pitching_line_drops_the_decision() -> None:
    """La decisión es de UN juego de los que caben en la ventana.

    Salía «6.1 IP, 4 K, 8 ER, (W)» en «Pasando trabajo»: una victoria al lado de un acumulado que la
    contradice. Decisión del dueño, 2026-07-31.
    """
    linea = ventana.linea_de_pitcheo({"IP": "6.1", "K": "4", "BB": "2", "ER": "8", "W": "1"})

    assert linea == "6.1 IP, 8 ER, 4 K, 2 BB"
    assert "(W)" not in linea


def test_neither_line_writes_a_zero() -> None:
    """Mismo criterio que la de la jornada: «0 HR, 0 RBI» ocupa sitio y no dice nada."""
    assert ventana.linea_de_bateo({"H": "3", "AB": "12", "AVG": ".250", "HR": "0", "RBI": "0"}) == ".250"


def test_a_long_line_is_not_trimmed() -> None:
    """NO SE RECORTA EN EL SERVIDOR (dueño, 2026-07-31). Hubo un tope de cinco cifras porque la línea
    larga no cabía; se quitó porque quien sabe si cabe es el navegador.

    El tope era peor por los dos lados: en pantalla ancha sobraba sitio y se había tirado dato igual,
    y en una estrecha seguía sin caber. Ahora va entera, el CSS la corta y `site.js` pone el tooltip.
    """
    linea = ventana.linea_de_bateo(
        {
            "H": "13",
            "AB": "50",
            "AVG": ".260",
            "X2B": "3",
            "X3B": "2",
            "HR": "2",
            "RBI": "3",
            "R": "10",
            "BB": "10",
            "SB": "6",
        }
    )

    assert linea == ".260, 3 2B, 2 3B, 2 HR, 3 RBI, 10 R, 6 SB, 10 BB"


def test_the_walk_goes_last_so_it_is_the_first_the_browser_cuts() -> None:
    """El navegador corta por la DERECHA, así que el orden decide qué se pierde primero.

    El boleto de último y RBI temprano: lo que sostiene la afirmación de la tarjeta es lo producido.
    """
    linea = ventana.linea_de_bateo(
        {"H": "9", "AB": "40", "AVG": ".225", "HR": "2", "RBI": "5", "R": "7", "BB": "9", "SB": "3"}
    )

    assert linea == ".225, 2 HR, 5 RBI, 7 R, 3 SB, 9 BB"
    assert linea.endswith("9 BB")


def test_a_short_line_is_not_padded() -> None:
    """Solo se nombra lo que ocurrió: una línea de tres cosas se queda con tres."""
    assert ventana.linea_de_bateo({"H": "4", "AB": "16", "AVG": ".250", "HR": "1", "RBI": "2"}) == ".250, HR, 2 RBI"


def test_the_pitching_line_names_the_walks() -> None:
    """Lo notó el dueño: ninguna línea de lanzador tenía BB, y el valor SÍ los cuenta —pesan -0,326
    carreras cada uno—. Sin ellos la tarjeta juzga y esconde parte del argumento.
    """
    linea = ventana.linea_de_pitcheo({"IP": "7.0", "K": "8", "BB": "5", "ER": "3"})

    assert linea == "7.0 IP, 3 ER, 8 K, 5 BB"


def test_a_pitcher_with_no_walks_says_so() -> None:
    """«0 BB» es una afirmación, no un hueco: en un lanzador, no regalar nada es parte del mérito."""
    assert ventana.linea_de_pitcheo({"IP": "7.0", "K": "8", "ER": "0"}) == "7.0 IP, 0 ER, 8 K, 0 BB"
