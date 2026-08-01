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


def test_the_team_games_come_from_what_was_actually_played() -> None:
    """Catorce días no son catorce juegos: hay días libres, dobles carteleras y el receso.

    Un número escrito a mano quedaría largo en julio y corto en septiembre sin que nada lo dijera.
    """
    splits = [{"stat": {"G": str(j)}} for j in [4, 6, 8, 10, 11, 11, 12, 12, 12, 12, 12, 13]]

    assert ventana.juegos_del_equipo(splits) == 12


def test_the_denominator_is_the_p90_and_not_the_maximum() -> None:
    """El máximo lo pone un solo jugador: una doble cartelera subiría el listón a los treinta.

    Y no es la mediana, que la baja el que estuvo lesionado media ventana — que es justo a quien el
    umbral tiene que dejar fuera.
    """
    normales = [{"stat": {"G": "10"}} for _ in range(20)]
    uno_que_jugo_de_mas = [{"stat": {"G": "20"}}]

    assert ventana.juegos_del_equipo(normales + uno_que_jugo_de_mas) == 10


def test_an_empty_window_does_not_divide_by_anything() -> None:
    """En pretemporada no hay splits, y eso no puede ser una excepción sin atrapar."""
    assert ventana.juegos_del_equipo([]) == 0


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
def test_the_two_ends_come_from_the_same_cut(temporada: object) -> None:
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
def test_nobody_reaching_either_cut_draws_nothing(temporada: object) -> None:
    """Una tanda entera del montón no llena ninguna de las dos puntas, y un panel hueco se lee como
    un sitio roto. Pasa de verdad en el receso."""
    _guardar([(0.5, "bateo"), (1.0, "bateo"), (-1.0, "pitcheo"), (0.0, "bateo")])

    assert ventana.portada() is None


@pytest.mark.django_db
def test_nothing_stored_draws_nothing(temporada: object) -> None:
    """En pretemporada la tabla está vacía y la portada no puede dibujar un panel hueco."""
    assert ventana.portada() is None


@pytest.mark.django_db
def test_the_cut_is_the_fixed_league_one_and_not_one_derived_from_the_table(temporada: object) -> None:
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
    assert all(f.valor >= ventana.CORTES["bateo"][0] for f in foto["quemando"]["lista"])


@pytest.mark.django_db
def test_each_office_is_judged_against_its_own_distribution(temporada: object) -> None:
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
                "abridor": False,
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
                "abridor": False,
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


# ── El contrato del umbral (SAB-01 del review v15) ──────────────────────────────────────────────


def test_the_innings_are_real_innings_and_not_baseball_notation() -> None:
    """«6.2 IP» son seis entradas y DOS TERCIOS: 6,667, no 6,2.

    Pasarlo por `float()` inventa una cifra que no existe, y estaba pasando en 219 de 400 lanzadores
    de una ventana normal. `oportunidades` se guarda para poder comprobar después por qué alguien
    entró o quedó fuera; un dato de auditoría que miente no sirve.
    """
    assert ventana._oportunidades({"IP": "6.2", "outsPitched": "20"}, "IP") == pytest.approx(6.667, abs=0.001)
    assert ventana._oportunidades({"IP": "4.1", "outsPitched": "13"}, "IP") == pytest.approx(4.333, abs=0.001)
    # El bateador no tiene notación rara: sus PA son un entero.
    assert ventana._oportunidades({"PA": "45"}, "PA") == 45


def test_the_starter_qualifies_by_the_official_rule() -> None:
    """1 IP por juego del EQUIPO, que es la regla real — y para el abridor sí funciona."""
    con_13 = {"GS": "2", "G": "2", "outsPitched": "39"}  # 13.0 IP en 2 aperturas
    con_12 = {"GS": "2", "G": "2", "outsPitched": "36"}  # 12.0

    assert ventana._califica(con_13, "pitching", juegos=13) == "abridor"
    assert ventana._califica(con_12, "pitching", juegos=13) == ""


def test_the_reliever_qualifies_by_appearances_because_the_rule_would_erase_him() -> None:
    """SAB-01 del review v15, y el número que lo decide.

    La regla de 1 IP por juego del equipo NO es la de calificación de los lanzadores: es la del título
    de efectividad, que es de abridores — en una temporada completa tampoco califica un cerrador.
    Medido en la ventana del 18 al 31 de julio, con el equipo jugando 13: a 13 IP calificaban 54
    lanzadores en toda la MLB, los 54 abridores, y **cero de 288 relevistas**. El que más lanzó en
    toda la liga llegó a 10,7.

    Con esa regla «Quemando la liga» no podría premiar nunca a un cerrador dominante, que es justo la
    clase de racha que el widget existe para contar.
    """
    cerrador = {"GS": "0", "G": "6", "outsPitched": "18"}  # 6 IP en 6 apariciones
    el_que_subio_dos_veces = {"GS": "0", "G": "2", "outsPitched": "6"}

    assert ventana._califica(cerrador, "pitching", juegos=13) == "relevista"
    assert ventana._califica(el_que_subio_dos_veces, "pitching", juegos=13) == ""


def test_the_batter_qualifies_by_plate_appearances_per_team_game() -> None:
    assert ventana._califica({"PA": "45"}, "hitting", juegos=13) == "bateo"
    assert ventana._califica({"PA": "30"}, "hitting", juegos=13) == ""


@pytest.mark.django_db
def test_each_pitching_role_is_judged_against_its_own_cut(temporada: object) -> None:
    """Un abridor y un relevista no son la misma población: medido sobre nueve ventanas, el p85 del
    abridor es +5,7 carreras y el del relevista +2,4, porque uno acumula durante seis entradas y el
    otro durante una.

    Con el corte único que hubo antes pasaba lo contrario de lo que uno supondría: a los abridores
    les sobraba —entraban por debajo de su propio p85— y a los relevistas les faltaba.
    """
    hoy = HOY
    for pid, abre, valor in ((3001, True, 4.0), (3002, False, 4.0)):
        WindowStandout.objects.create(
            player=_jugador(pid, "Juan", f"Rol{pid}"), desde=hoy - timedelta(days=13), hasta=hoy,
            grupo=WindowStandout.Grupo.PITCHEO, abridor=abre, team="SDN",
            linea="x", valor=valor, juegos=5, oportunidades=10,
        )  # fmt: skip

    foto = ventana.portada()

    assert foto is not None
    # El mismo +4,0: al relevista le basta (su corte es 2,4) y al abridor no (5,7).
    assert [f.player.player_id for f in foto["quemando"]["lista"]] == [3002]


# ── Cuándo tienen derecho a existir (decisión del dueño, 2026-08-01) ────────────────────────────


@pytest.fixture
def temporada(db: None) -> object:
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    return SeasonDates.objects.create(
        season=2026, sports_id=MLB,
        season_start_date=date(2026, 3, 26), season_end_date=date(2026, 9, 28), is_active=True,
    )  # fmt: skip


@pytest.mark.django_db
def test_los_widgets_no_salen_en_los_primeros_catorce_dias(temporada: object) -> None:
    """La ventana estaría a medias: el día 3 son tres días de juegos, no catorce, y los cortes se
    midieron sobre ventanas llenas de una liga en marcha."""
    assert ventana.se_puede_publicar(date(2026, 3, 26)) is False, "el día de la apertura"
    assert ventana.se_puede_publicar(date(2026, 4, 8)) is False, "el día 14, con la ventana aún corta"


@pytest.mark.django_db
def test_los_widgets_aparecen_el_dia_quince(temporada: object) -> None:
    """«El día 15 a partir del start season» — palabras del dueño."""
    assert ventana.se_puede_publicar(date(2026, 4, 9)) is True


@pytest.mark.django_db
def test_los_widgets_desaparecen_al_terminar_la_temporada(temporada: object) -> None:
    """«Últimos 14 días» en enero es una afirmación falsa: no ha habido catorce días de pelota.

    Con UN día de holgura (dueño, 2026-08-01): la Serie Mundial termina de noche y sin él los widgets
    se iban de madrugada, justo cuando alguien entra a ver cómo les fue a los nuestros en el último
    juego del año.
    """
    assert ventana.se_puede_publicar(date(2026, 9, 28)) is True, "el último día todavía cuenta"
    assert ventana.se_puede_publicar(date(2026, 9, 29)) is True, "el día siguiente, por la holgura"
    assert ventana.se_puede_publicar(date(2026, 9, 30)) is False, "al segundo día ya no"
    assert ventana.se_puede_publicar(date(2027, 1, 15)) is False


@pytest.mark.django_db
def test_sin_temporada_marcada_no_se_publica() -> None:
    """Mismo criterio que `season_window`: callar es mejor que afirmar sobre una ventana que nadie
    definió."""
    assert ventana.se_puede_publicar(date(2026, 7, 31)) is False


@pytest.mark.django_db
def test_quitar_la_marca_de_temporada_en_curso_apaga_los_widgets(temporada: object) -> None:
    """Es la palanca del Backoffice: el administrador desmarca «Temporada en curso» y los dos widgets
    se van de la portada en la siguiente petición, sin tocar código ni esperar a un job."""
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    assert ventana.se_puede_publicar(date(2026, 7, 31)) is True

    SeasonDates.objects.filter(sports_id=MLB).update(is_active=False)

    assert ventana.se_puede_publicar(date(2026, 7, 31)) is False


@pytest.mark.django_db
def test_una_temporada_de_otro_deporte_no_habilita_los_widgets(temporada: object) -> None:
    """La condición es `sports_id = 1`. Si algún día entra otro deporte en la tabla, su temporada
    activa no puede encender un widget que solo habla de las Grandes Ligas."""
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    SeasonDates.objects.filter(sports_id=MLB).update(is_active=False)
    SeasonDates.objects.create(
        season=2026, sports_id=MLB + 1, is_active=True,
        season_start_date=date(2026, 3, 26), season_end_date=date(2026, 9, 28),
    )  # fmt: skip

    assert ventana.se_puede_publicar(date(2026, 7, 31)) is False


@pytest.mark.django_db
def test_la_portada_calla_en_la_primera_quincena() -> None:
    """Con datos de sobra en la tabla, el widget no sale igual: la fecha manda.

    Es la prueba que importa de las cinco: las otras comprueban el cálculo de la fecha, esta
    comprueba que `portada()` de verdad lo obedece.
    """
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    # Una temporada que arrancó hace cinco días: estamos dentro de la primera quincena.
    SeasonDates.objects.create(
        season=2026, sports_id=MLB, is_active=True,
        season_start_date=HOY - timedelta(days=5), season_end_date=HOY + timedelta(days=150),
    )  # fmt: skip
    _guardar([(9.0, "bateo"), (-9.0, "bateo")])

    assert ventana.portada() is None


# ── Los bordes que encontró el review v16 ───────────────────────────────────────────────────────


def test_sin_denominador_no_califica_nadie() -> None:
    """DEV-01. `juegos` en cero no es «el equipo no jugó»: es «la consulta de bateo vino vacía».

    Sin el guard, `0 >= 3,1 x 0` es cierto y califica TODO EL MUNDO — un bateador sin turnos y un
    lanzador sin outs. Y como la foto se reemplaza entera, una respuesta parcial del proxy en plena
    temporada publicaría una lista de gente que no pasó ningún umbral.
    """
    assert ventana._califica({"PA": "0"}, "hitting", juegos=0) == ""
    assert ventana._califica({"PA": "600"}, "hitting", juegos=0) == ""
    assert ventana._califica({"GS": "1", "outsPitched": "0", "G": "9"}, "pitching", juegos=0) == ""


def test_el_que_abrio_una_vez_pero_relevó_el_resto_entra_como_relevista() -> None:
    """SAB-01 del v16. El opener, el bullpen game y el relevista largo que abrió una vez.

    Antes quedaban atrapados: no llegaban a las entradas del abridor y tampoco se les dejaba intentar
    por apariciones, así que desaparecían por una apertura administrativa. Medido: 15 lanzadores en
    toda la MLB caían en ese hueco, 3 dominicanos.
    """
    opener = {"GS": "1", "G": "8", "outsPitched": "24"}  # 8 IP en 8 salidas, abrió una

    assert ventana._califica(opener, "pitching", juegos=13) == "relevista"


def test_un_abridor_con_dos_aperturas_malas_no_entra_por_la_puerta_de_atras() -> None:
    """El respaldo no puede convertirse en un colador: dos aperturas son dos apariciones, y el
    umbral de relevo pide cuatro."""
    abridor_flojo = {"GS": "2", "G": "2", "outsPitched": "21"}  # 7 IP en 2 aperturas

    assert ventana._califica(abridor_flojo, "pitching", juegos=13) == ""


def test_la_linea_mas_larga_posible_cabe_en_la_columna() -> None:
    """DEV-02. El `[:160]` de `calcular()` es el largo de la columna, no una decisión de contenido.

    Esta prueba fija que no se llega a activar: si algún día la línea creciera —otra estadística, otro
    formato— se pone roja antes de que el truncado silencioso empiece a comerse datos de verdad.
    """
    maxima = ventana.linea_de_bateo(
        {
            "AVG": ".444",
            "H": "40",
            "AB": "90",
            "X2B": "12",
            "X3B": "11",
            "HR": "15",
            "RBI": "44",
            "R": "38",
            "BB": "27",
            "SB": "19",
        }
    )
    tope = WindowStandout._meta.get_field("linea").max_length
    assert tope is not None
    assert len(maxima) < tope
    assert len(ventana.linea_de_pitcheo({"IP": "100.2", "ER": "40", "K": "120", "BB": "55"})) < 160


# ── Los bordes que encontró el review v17 ───────────────────────────────────────────────────────


def test_el_swingman_no_entra_por_la_puerta_del_relevo() -> None:
    """SAB-01 del v17. El respaldo pide que el relevo haya sido su USO PRINCIPAL, no solo que tenga
    cuatro salidas.

    Con `G >= 4` a secas, un lanzador con dos aperturas de cuatro salidas —uso mitad y mitad— se medía
    contra el corte de relevista, que es el más permisivo de los dos (+2,4 contra +5,7). Medido en la
    ventana del 18 al 31 de julio, eran 5 de los 15 que caían al respaldo.
    """
    swingman = {"GS": "2", "G": "4", "outsPitched": "20"}  # 6.2 IP, mitad aperturas

    assert ventana._califica(swingman, "pitching", juegos=13) == ""


def test_el_opener_de_verdad_sigue_entrando() -> None:
    """Y la mitad buena del arreglo no se pierde: una apertura en ocho salidas ES relevo."""
    assert ventana._califica({"GS": "1", "G": "8", "outsPitched": "24"}, "pitching", juegos=13) == "relevista"
    # Justo en el filo: una apertura de cuatro salidas son tres de relevo, o sea más de la mitad.
    assert ventana._califica({"GS": "1", "G": "4", "outsPitched": "18"}, "pitching", juegos=13) == "relevista"


def test_el_relevista_puro_no_se_ve_afectado() -> None:
    """`GS = 0` nunca puede fallar la comprobación de rol dominante."""
    assert ventana._califica({"GS": "0", "G": "4", "outsPitched": "12"}, "pitching", juegos=13) == "relevista"


@pytest.mark.django_db
def test_la_muestra_del_comando_usa_la_fecha_de_la_ventana(temporada: object) -> None:
    """QA-01 del v17. `--hasta` reproduce una foto vieja, y la muestra decidía con la fecha de HOY.

    Con una ventana de la primera quincena, `portada()` sin fecha diría que sí se publica —porque hoy
    estamos en julio— y con la fecha de la ventana dice que no. El comando existe para depurar: una
    señal falsa ahí manda a mirar donde no es.
    """
    _guardar([(9.0, "bateo"), (-9.0, "bateo")])
    en_la_primera_quincena = date(2026, 4, 2)

    assert ventana.portada() is not None, "hoy sí se publica"
    assert ventana.portada(en_la_primera_quincena) is None, "el 2 de abril no, y la muestra tiene que decirlo"


# ── La regla del widget de líderes ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_los_lideres_sobreviven_al_invierno() -> None:
    """«Forever los mejores de la última temporada que se jugó» — palabras del dueño.

    Es la diferencia con los otros cuatro paneles: en febrero «los mejores de la liga» sigue siendo
    cierto sobre la temporada recién terminada, y «los destacados de ayer y hoy» no lo sería.
    """
    from dglweb.stats import season_window
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    SeasonDates.objects.create(
        season=2026, sports_id=MLB, is_active=False,
        season_start_date=date(2026, 3, 25), season_end_date=date(2026, 10, 31),
    )  # fmt: skip

    assert season_window.hay_temporada_empezada(date(2027, 2, 14)) is True, "en febrero siguen valiendo"
    assert season_window.se_publica(date(2027, 2, 14)) is False, "los otros widgets sí se apagan"


@pytest.mark.django_db
def test_una_temporada_futura_no_apaga_los_lideres() -> None:
    """LA TRAMPA, y cae en el peor día del año.

    El administrador carga la fila de la temporada nueva **la noche anterior al primer lanzamiento**.
    Con «la temporada más reciente» a secas, esa noche la más reciente sería 2027, su inicio no habría
    llegado, y el widget se apagaría — esa víspera y el día de apertura, que son justo cuando vuelve
    el que estuvo cinco meses sin pelota.

    Con «la más reciente que YA EMPEZÓ», esos dos días siguen enseñando los líderes del año anterior,
    que es lo correcto: la temporada nueva todavía no tiene ninguno.
    """
    from dglweb.stats import season_window
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    for temporada_, inicio, fin in ((2026, date(2026, 3, 25), date(2026, 10, 31)),
                                    (2027, date(2027, 3, 25), date(2027, 10, 31))):
        SeasonDates.objects.create(
            season=temporada_, sports_id=MLB, is_active=False,
            season_start_date=inicio, season_end_date=fin,
        )  # fmt: skip

    assert season_window.hay_temporada_empezada(date(2027, 3, 24)) is True, "la víspera"
    assert season_window.hay_temporada_empezada(date(2027, 3, 25)) is True, "el día de apertura"


@pytest.mark.django_db
def test_antes_de_la_primera_temporada_no_hay_nada_que_ensenar() -> None:
    """Un calendario cargado pero sin ninguna jornada jugada todavía: el widget no se dibuja."""
    from dglweb.stats import season_window
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    SeasonDates.objects.create(
        season=2027, sports_id=MLB, is_active=True,
        season_start_date=date(2027, 3, 25), season_end_date=date(2027, 10, 31),
    )  # fmt: skip

    assert season_window.hay_temporada_empezada(date(2027, 1, 10)) is False


@pytest.mark.django_db
def test_el_titulo_del_top_10_nombra_el_año_cuando_la_temporada_termina() -> None:
    """En curso dice «de la liga»; terminada, «del 2026». Sin eso, en febrero «la liga» se lee como
    la de ahora y el widget afirma algo falso durante cinco meses.

    Se pregunta por la temporada DE LOS DATOS y no por la fecha suelta: el día de apertura de 2027 la
    tabla todavía tiene los líderes de 2026 —el refresco horario no ha corrido— y el título tiene que
    seguir diciendo «del 2026» hasta que esos datos cambien.
    """
    from dglweb.stats import season_window
    from dglweb.stats.models import SeasonDates
    from dglweb.stats.season_window import MLB

    SeasonDates.objects.create(
        season=2026, sports_id=MLB, is_active=True,
        season_start_date=date(2026, 3, 25), season_end_date=date(2026, 10, 31),
    )  # fmt: skip

    assert season_window.temporada_terminada(2026, date(2026, 8, 1)) is False, "en plena temporada"
    assert season_window.temporada_terminada(2026, date(2026, 11, 1)) is False, "el día de holgura"
    assert season_window.temporada_terminada(2026, date(2026, 11, 2)) is True
    assert season_window.temporada_terminada(2026, date(2027, 3, 25)) is True, "el día de apertura del año nuevo"


@pytest.mark.django_db
def test_sin_calendario_de_esa_temporada_no_se_afirma_que_termino() -> None:
    """Callar el año es mejor que afirmar que terminó algo de lo que no se sabe la fecha."""
    from dglweb.stats import season_window

    assert season_window.temporada_terminada(1998, date(2026, 8, 1)) is False
