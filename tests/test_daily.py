"""La actuación de la jornada: cómo se puntúa, cómo se guarda y qué se poda.

Lo que más importa acá es que el ORDEN sea defendible. Un widget que dice «destacados» y pone arriba
al que menos hizo no es un bug de programación, es una afirmación falsa en la portada — así que la
mayoría de estos tests comparan dos jornadas y exigen que gane la que cualquiera diría que es mejor.
"""

from datetime import date, timedelta
from typing import Any, cast

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.formats import date_format

from dglweb.players.models import Player
from dglweb.stats import daily, jobs
from dglweb.stats.models import DailyStandout, IngestRun, SeasonDates
from dglweb.stats.season_window import MLB
from tests.test_players import _other_player

AYER = date(2026, 7, 25)


def _bateo(**stat: Any) -> dict[str, Any]:
    base = {"AB": 0, "H": 0, "X2B": 0, "X3B": 0, "HR": 0, "BB": 0, "IBB": 0, "HBP": 0, "K": 0, "SB": 0, "CS": 0}
    return base | stat


def _pitcheo(**stat: Any) -> dict[str, Any]:
    return {"outsPitched": 0, "K": 0, "H": 0, "R": 0, "HR": 0, "ER": 0, "IP": "0.0"} | stat


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


# ── El orden de los bateadores ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_homer_beats_a_single(db: None) -> None:
    """Lo mínimo que la fórmula tiene que respetar, y lo que un orden por hits no respetaría."""
    jonron = daily.valor_de_bateo(_bateo(AB=4, H=1, HR=1))
    sencillo = daily.valor_de_bateo(_bateo(AB=4, H=1))

    assert jonron > sencillo


@pytest.mark.django_db
def test_three_singles_beat_one_homer_in_four_at_bats(db: None) -> None:
    """No es obvio, y es justo lo que los pesos lineales resuelven bien.

    Tres sencillos valen 1,40 carreras contra 1,39 del jonrón: casi empate, con ventaja mínima para
    quien llegó tres veces a base. Ordenar por jonrones o por total de bases diría otra cosa.
    """
    tres_sencillos = daily.valor_de_bateo(_bateo(AB=4, H=3))
    un_jonron = daily.valor_de_bateo(_bateo(AB=4, H=1, HR=1))

    assert tres_sencillos > un_jonron


@pytest.mark.django_db
def test_a_walk_counts_and_an_out_hurts(db: None) -> None:
    """Un 1-3 con boleto vale más que un 1-4, aunque la línea de hits sea la misma.

    Es lo que separa esta fórmula de ordenar por promedio: el boleto es una vez que no falló.
    """
    con_boleto = daily.valor_de_bateo(_bateo(AB=3, H=1, BB=1))
    sin_boleto = daily.valor_de_bateo(_bateo(AB=4, H=1))

    assert con_boleto > sin_boleto


@pytest.mark.django_db
def test_an_intentional_walk_is_worth_less_than_an_earned_one(db: None) -> None:
    """La matriz los distingue y el cálculo también: el intencional no lo ganó el bateador."""
    ganado = daily.valor_de_bateo(_bateo(BB=1))
    regalado = daily.valor_de_bateo(_bateo(BB=1, IBB=1))

    assert ganado > regalado


@pytest.mark.django_db
def test_an_oh_for_four_is_negative(db: None) -> None:
    """Una mala jornada tiene que hundir, no quedar en cero: así el orden separa de verdad."""
    assert daily.valor_de_bateo(_bateo(AB=4, K=2)) < 0


@pytest.mark.django_db
def test_a_sacrifice_counts_as_an_out_even_though_it_is_not_an_at_bat(db: None) -> None:
    """`AB` no incluye sacrificios, así que si no se suman aparte el out desaparece del cálculo."""
    con_sacrificio = daily.valor_de_bateo(_bateo(AB=3, H=1, SF=1))
    sin_nada = daily.valor_de_bateo(_bateo(AB=3, H=1))

    assert con_sacrificio < sin_nada


# ── El orden de los lanzadores ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_seven_inning_start_beats_a_clean_inning_of_relief(db: None) -> None:
    """Que los outs pesen es lo que impide que un relevista desplace a un abridor.

    Ordenar por efectividad del día pondría al relevista arriba con su 0.00. Acá siete entradas de
    una carrera valen +3,8 y un inning perfecto +0,8, porque cada out suma lo que vale un out.

    Antes esto probaba `game_score()`. Se conserva la comparación —es la propiedad que hay que
    proteger— pero contra la función que ordena de verdad.
    """
    apertura = daily.valor_de_pitcheo(_pitcheo(outsPitched=21, K=6, H=4, R=1))
    relevo = daily.valor_de_pitcheo(_pitcheo(outsPitched=3, K=1, H=0, R=0))

    assert apertura > relevo


@pytest.mark.django_db
def test_un_boleto_le_cuesta_al_lanzador_lo_que_dice_la_matriz(db: None) -> None:
    """El equivalente de la prueba de arriba, pero en el modelo que SÍ ordena la portada.

    Desde el 2026-07-29 el pitcheo no se puntúa con Game Score sino con la misma matriz de pesos
    lineales que el bateo (SAB-02). Acá se comprueba que el boleto le cuesta al lanzador exactamente
    lo que la matriz le regala al bateador — ni más ni menos, que es lo que hace que las dos listas
    se puedan comparar.
    """
    limpio = daily.valor_de_pitcheo(_pitcheo(outsPitched=18))
    con_uno = daily.valor_de_pitcheo(_pitcheo(outsPitched=18, BB=1))

    assert limpio - con_uno == pytest.approx(daily.PESOS["bb"])


@pytest.mark.django_db
def test_un_inning_perfecto_vale_positivo(db: None) -> None:
    """LA PRUEBA QUE FIJA EL FALLO DE SAB-02, y la más fácil de contarle a alguien.

    Con la conversión vieja —`(GS - 50) / 3`— un relevista que retiraba el inning en orden con un
    ponche salía valorado en **-1,0 carreras**: el sitio afirmaba que le había COSTADO una carrera a
    su equipo por lanzar un inning perfecto.

    Pasaba porque 50 es el promedio de un ABRIDOR, y un relevista no puede acercarse: entra con la
    resta ya puesta por no lanzar siete entradas. Con la matriz de pesos lineales no hay ningún ancla
    que suponga un rol — cada out suma lo que vale un out.
    """
    assert daily.valor_de_pitcheo(_pitcheo(outsPitched=3, K=1)) > 0


@pytest.mark.django_db
def test_el_mejor_dia_de_un_bateador_le_gana_a_una_apertura_buena(db: None) -> None:
    """La consecuencia que se veía en la portada, y el motivo de todo el cambio.

    Con la escala vieja, una apertura de 7 entradas y una carrera valía +9,0 y un 5-5 con tres
    jonrones +5,1: el día de la vida de un bateador perdía contra una apertura buena pero corriente.
    No era la métrica descubriendo nada — era que la escala del pitcheo estaba al doble.

    Con la matriz esa misma apertura vale +3,8 y el bateador sigue en +5,1.
    """
    apertura = daily.valor_de_pitcheo(_pitcheo(outsPitched=21, K=6, H=4, R=1))
    bateador = daily.valor_de_bateo(_bateo(AB=5, H=5, HR=3))

    assert bateador > apertura


@pytest.mark.django_db
def test_la_escala_del_pitcheo_no_se_dispara(db: None) -> None:
    """Un techo de cordura. Con la conversión vieja un juego sin hits y 12 ponches daba **+18,7
    carreras**, cuando las mejores actuaciones de una temporada entera rondan las +4 o +5.

    No se fija un valor exacto para no atar la prueba a los decimales de la matriz —que el dueño
    puede actualizar—, sino el orden de magnitud, que es lo que estaba mal.
    """
    joya = daily.valor_de_pitcheo(_pitcheo(outsPitched=27, K=12))

    assert 5 < joya < 10


@pytest.mark.django_db
def test_el_wild_pitch_y_el_balk_le_cuestan_al_lanzador(db: None) -> None:
    """Los dos estaban en la matriz y yo los había dejado fuera diciendo que no estaban.

    Son las únicas jugadas del listado que son cosa EXCLUSIVA del lanzador. El passed ball, que se
    les parece y también está en la matriz, es del receptor y por eso no entra.
    """
    limpio = daily.valor_de_pitcheo(_pitcheo(outsPitched=9))

    assert daily.valor_de_pitcheo(_pitcheo(outsPitched=9, WP=1)) < limpio
    assert daily.valor_de_pitcheo(_pitcheo(outsPitched=9, BK=1)) < limpio


@pytest.mark.django_db
def test_una_apertura_desastrosa_es_negativa(db: None) -> None:
    """El otro extremo: cuatro entradas con nueve hits y dos jonrones tiene que hundir.

    Con Game Score también lo hacía, pero conviene fijarlo en el modelo nuevo: si los outs pesaran
    demasiado, una salida larga y mala podría acabar en positivo solo por durar.
    """
    assert daily.valor_de_pitcheo(_pitcheo(outsPitched=12, K=2, H=9, R=6, HR=2)) < 0


@pytest.mark.django_db
def test_los_dos_pisos_son_distintos_y_el_de_pitcheo_es_mas_alto(db: None) -> None:
    """PARECE UNA INCONSISTENCIA Y NO LO ES. Esta prueba existe para que nadie la «arregle».

    Los dos oficios están en la misma unidad —carreras— así que la tentación es ponerles el mismo
    piso. Sería un error, y se puede enseñar con números: las dos distribuciones no tienen la misma
    forma. Mediana de bateo -0,14 contra +0,33 en pitcheo, desviación 0,83 contra 1,31, porque un
    lanzador suma valor con cada out y un bateador solo tiene cuatro turnos.

    Con un corte único de 0,70 entrarían bateadores del percentil 84 y lanzadores del **68**, que es
    un inning limpio con un ponche: el día normal de un relevista.

    Cada piso es el percentil 80 de SU oficio en toda la MLB. El orden sigue usando el valor crudo
    —ahí una carrera es una carrera— pero «notable» es relativo a lo normal en cada puesto.
    """
    assert daily.PISO_PITCHEO > daily.PISO_BATEO, (
        "el piso de pitcheo tiene que ser MÁS ALTO: su distribución está corrida hacia arriba porque "
        "cada out suma. Igualarlos publicaría relevistas con un inning corriente."
    )


@pytest.mark.django_db
def test_un_inning_limpio_de_relevo_no_alcanza_para_publicarse(db: None) -> None:
    """La consecuencia concreta del piso de pitcheo, y lo que se rompería al bajarlo.

    Un relevista que retira el inning en orden con un ponche vale +0,81 — positivo, como debe ser
    desde que se quitó la conversión de Game Score, pero **por debajo del piso**. Es el día normal de
    un relevista, no un destacado.
    """
    inning_limpio = daily.valor_de_pitcheo(_pitcheo(outsPitched=3, K=1))

    assert inning_limpio > 0, "un inning perfecto nunca puede valer negativo"
    assert inning_limpio < daily.PISO_PITCHEO, "pero tampoco alcanza para llamarse destacado"


@pytest.mark.django_db
def test_un_atrapado_robando_no_es_un_out_cualquiera(db: None) -> None:
    """`outsPitched` CUENTA LOS OUTS DE CORREDORES, y eso rompía la documentación.

    Comprobado contra el proxy: una salida de 1.0 IP con un atrapado robando trae `outsPitched=3`
    habiendo retirado a DOS bateadores. Así que el atrapado ya entraba al cálculo disfrazado de out
    cualquiera, a +0,27, mientras el docstring afirmaba que se omitía para no cobrarle al lanzador el
    brazo del receptor.

    Ahora entra con su peso de la matriz, +0,42, que es más que un out normal — y tiene sentido:
    borrar a un corredor de segunda vale más que retirar a un bateador.
    """
    con_atrapado = daily.valor_de_pitcheo(_pitcheo(outsPitched=3, K=0, CS=1))
    tres_outs_normales = daily.valor_de_pitcheo(_pitcheo(outsPitched=3, K=0))

    assert con_atrapado > tres_outs_normales
    # El valor exacto: dos outs de bateador más el atrapado con SU peso.
    esperado = 2 * -daily.PESOS["out"] + -daily.PESOS["cs"]
    assert con_atrapado == pytest.approx(esperado)


@pytest.mark.django_db
def test_una_base_robada_le_cuesta_al_lanzador(db: None) -> None:
    """El otro lado del juego de corredores, y el que hace honesta la simetría.

    Contar solo los atrapados sería quedarse con la mitad buena: el lanzador cobraría por sacar
    corredores y no pagaría por dejarlos correr. El bateo cuenta las dos, así que el pitcheo también.
    """
    con_robo = daily.valor_de_pitcheo(_pitcheo(outsPitched=9, SB=2))
    sin_robo = daily.valor_de_pitcheo(_pitcheo(outsPitched=9))

    assert con_robo < sin_robo
    assert sin_robo - con_robo == pytest.approx(2 * daily.PESOS["sb"])


@pytest.mark.django_db
def test_el_doble_play_cuenta_como_dos_outs_y_queda_declarado(db: None) -> None:
    """UNA APROXIMACIÓN A PROPÓSITO, fijada para que se sepa que lo es.

    Un doble play vale más que dos outs sueltos, pero **la matriz no trae un peso para él** —ni de
    este lado ni del otro— y el split tampoco manda los pickoffs. Inventarles un número rompería lo
    que hace comparables a las dos listas, así que el segundo out entra como out genérico.

    Si algún día la matriz trae el peso del doble play, esta prueba es la que hay que cambiar.
    """
    con_doble_play = daily.valor_de_pitcheo(_pitcheo(outsPitched=2, K=0, GIDP=1))
    dos_outs_sueltos = daily.valor_de_pitcheo(_pitcheo(outsPitched=2, K=0))

    assert con_doble_play == dos_outs_sueltos


@pytest.mark.django_db
def test_a_home_run_costs_more_than_a_hit(db: None) -> None:
    con_jonron = daily.valor_de_pitcheo(_pitcheo(outsPitched=18, H=3, HR=1))
    sin_jonron = daily.valor_de_pitcheo(_pitcheo(outsPitched=18, H=3))

    assert con_jonron < sin_jonron


@pytest.mark.django_db
def test_el_boleto_intencional_le_cuesta_menos_al_lanzador(db: None) -> None:
    """LA AFIRMACIÓN SE INVIRTIÓ al cambiar de modelo, y por eso conviene fijarla.

    Con Game Score los dos boletos valían igual: la fórmula de Tango dice «walks» a secas. Con pesos
    lineales el intencional vale menos —0,21 contra 0,33— porque no lo ganó el bateador, lo regaló el
    manager. Es el mismo trato que ya le daba `valor_de_bateo()`, que es justo lo que se busca: los
    dos oficios leyendo la misma matriz.
    """
    ganado = daily.valor_de_pitcheo(_pitcheo(outsPitched=9, BB=1))
    regalado = daily.valor_de_pitcheo(_pitcheo(outsPitched=9, BB=1, IBB=1))

    assert regalado > ganado


# ── Cómo se lee ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_line_only_names_what_happened(db: None) -> None:
    """«3-4, 2B, HR, 4 RBI» y no «3-4, 0 3B, 1 HR, 0 SB»: un cero ocupa lugar y no dice nada."""
    linea = daily.linea_de_bateo(_bateo(AB=4, H=3, X2B=1, HR=1, RBI=4, R=2))

    assert linea == "3-4, 2B, HR, 4 RBI, 2 R"


@pytest.mark.django_db
def test_two_of_the_same_are_counted(db: None) -> None:
    assert "2 HR" in daily.linea_de_bateo(_bateo(AB=4, H=2, HR=2))


@pytest.mark.django_db
def test_the_pitching_line_leads_with_innings_and_flags_the_decision(db: None) -> None:
    """Las entradas primero porque son lo que sitúa la actuación; la decisión al final."""
    assert daily.linea_de_pitcheo(_pitcheo(IP="7.0", K=9, ER=0, W=1)) == "7.0 IP, 9 K, 0 ER, (W)"
    assert "(SV)" in daily.linea_de_pitcheo(_pitcheo(IP="1.0", SV=1))


# ── La tabla ────────────────────────────────────────────────────────────────────────────────────


def _jugador(pid: int) -> Player:
    return Player.todos.create(**_other_player(player_id=pid, dgl_id=f"j{pid}", full_name=f"Jugador {pid}"))


@pytest.mark.django_db
def test_saving_a_day_twice_does_not_duplicate_it(temporada: SeasonDates) -> None:
    """Se borra y reescribe la jornada entera: o se tiene completa o no se tiene.

    Con upsert fila por fila, una segunda corrida podría dejar mezclados los resultados de dos
    consultas distintas al proxy — y media jornada de cada una no es ninguna jornada.
    """
    _jugador(1)
    listas = {"bateo": [daily.Actuacion(1, "Jugador 1", "SDN", 2.0, "3-4")], "pitcheo": []}

    daily.guardar(AYER, listas)
    daily.guardar(AYER, listas)

    assert DailyStandout.objects.filter(fecha=AYER).count() == 1


@pytest.mark.django_db
def test_a_player_outside_the_master_is_skipped_instead_of_breaking_the_write(temporada: SeasonDates) -> None:
    """La FK reventaría, y una jornada no puede perderse por un id que no reconocemos."""
    _jugador(1)
    listas = {
        "bateo": [
            daily.Actuacion(1, "Conocido", "SDN", 2.0, "3-4"),
            daily.Actuacion(999, "Desconocido", "NYA", 3.0, "4-4"),
        ],
        "pitcheo": [],
    }

    assert daily.guardar(AYER, listas) == 1


@pytest.mark.django_db
def test_pruning_keeps_the_current_season_whole_and_drops_the_rest(temporada: SeasonDates) -> None:
    """Por temporada y no por antigüedad: así el receso del Juego de Estrellas nunca deja la tabla vacía."""
    jugador = _jugador(1)
    for fecha in (date(2025, 9, 1), date(2026, 4, 1), date(2026, 7, 25)):
        DailyStandout.objects.create(
            fecha=fecha, grupo=DailyStandout.Grupo.BATEO, player=jugador, linea="1-4", valor=0.1
        )

    borradas = daily.podar(2026)

    assert borradas == 1
    assert set(DailyStandout.objects.values_list("fecha", flat=True)) == {date(2026, 4, 1), date(2026, 7, 25)}


@pytest.mark.django_db
def test_without_an_active_season_nothing_is_pruned(temporada: SeasonDates) -> None:
    """Una tabla con datos viejos es un problema menor que una vacía por un despiste de configuración."""
    jugador = _jugador(1)
    DailyStandout.objects.create(
        fecha=date(2020, 5, 5), grupo=DailyStandout.Grupo.BATEO, player=jugador, linea="1-4", valor=0.1
    )

    assert daily.podar(None) == 0
    assert DailyStandout.objects.count() == 1


# ── Lo que ve la portada ────────────────────────────────────────────────────────────────────────


def _guardar_jornada(bateadores: int, lanzadores: int) -> None:
    """Una jornada donde TODOS pasan el piso, para probar el recorte y no el filtro.

    Los valores bajan de uno en uno para que el orden sea predecible, pero se quedan siempre por
    encima del piso de su oficio: si no, estas pruebas medirían cuántos filtra el umbral en vez de
    cuántos caben en el panel, y se caerían el día que el dueño mueva un piso.
    """
    for n in range(bateadores + lanzadores):
        es_bateo = n < bateadores
        DailyStandout.objects.create(
            fecha=AYER,
            grupo=DailyStandout.Grupo.BATEO if es_bateo else DailyStandout.Grupo.PITCHEO,
            player=_jugador(100 + n),
            linea="1-4",
            valor=(daily.PISO_BATEO + 5 - n / 100) if es_bateo else (daily.PISO_PITCHEO + 20 - n / 100),
        )


@pytest.mark.django_db
def test_una_jornada_corta_cabe_entera_sin_boton(temporada: SeasonDates) -> None:
    """Seis es la capacidad del marco —2 columnas por 3 filas—, así que hasta ahí no hay nada que
    desplegar y el botón no debe aparecer."""
    _guardar_jornada(bateadores=3, lanzadores=2)

    datos = daily.portada()

    assert datos is not None
    assert len(datos["visibles"]) == 5
    assert datos["de_mas"] == []


@pytest.mark.django_db
def test_pasados_los_seis_el_resto_queda_detras_del_boton(temporada: SeasonDates) -> None:
    """Las pestañas por oficio se retiraron: una sola lista y un «ver más». Ver `_destacados.html`."""
    _guardar_jornada(bateadores=6, lanzadores=4)

    datos = daily.portada()

    assert datos is not None
    assert len(datos["destacados"]) == 10
    assert len(datos["visibles"]) == daily.VISIBLES
    assert len(datos["de_mas"]) == 4


@pytest.mark.django_db
def test_la_lista_no_crece_sin_fin(temporada: SeasonDates) -> None:
    """`MAXIMO` está para que una jornada excepcional no arme una lista infinita, no para elegir."""
    _guardar_jornada(bateadores=20, lanzadores=10)

    datos = daily.portada()

    assert datos is not None
    assert len(datos["destacados"]) == daily.MAXIMO


@pytest.mark.django_db
def test_los_dos_oficios_se_ordenan_en_una_misma_unidad(temporada: SeasonDates) -> None:
    """El sitio llevaba dos listas separadas porque un 3-4 y siete entradas no se comparan. El dueño
    decidió mezclarlas (2026-07-27), y hasta el 2026-07-29 eso se hacía TRADUCIENDO Game Score.

    Ya no hay traducción: los dos oficios se puntúan con la misma matriz, así que `valor` se compara
    tal cual. Esta prueba fija justo eso — que nadie vuelva a meter una conversión en el medio.
    """
    bateador = _jugador(400)
    lanzador = _jugador(401)
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.BATEO, player=bateador, linea="3-4, HR", valor=2.0
    )
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.PITCHEO, player=lanzador, linea="7.0 IP, 0 ER", valor=3.8
    )

    datos = daily.portada()

    assert datos is not None
    assert [d.player.player_id for d in datos["destacados"]] == [401, 400]


@pytest.mark.django_db
def test_un_bateador_le_gana_a_un_lanzador_que_valio_menos(temporada: SeasonDates) -> None:
    """El reverso, que es el que prueba que manda el valor y no el oficio."""
    bateador = _jugador(402)
    lanzador = _jugador(403)
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.BATEO, player=bateador, linea="3-4, 2 HR", valor=2.5
    )
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.PITCHEO, player=lanzador, linea="5.0 IP, 2 ER", valor=1.4
    )

    datos = daily.portada()

    assert datos is not None
    assert [d.player.player_id for d in datos["destacados"]] == [402, 403]


@pytest.mark.django_db
def test_solo_entran_los_que_pasan_el_piso(temporada: SeasonDates) -> None:
    """El piso es lo que hace que «destacado» signifique algo.

    Sin él, el top-N tenía que llenar sus huecos pasara lo que pasara, y en las jornadas flojas
    coronaba un 1-4 con sencillo. Medido sobre 14 jornadas reales, el tercer bateador publicado
    bajaba hasta 0,25 y el segundo lanzador hasta 46 — por debajo del promedio de su propia escala.
    """
    bueno = _jugador(200)
    flojo = _jugador(201)
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.BATEO, player=bueno, linea="2-4, HR", valor=daily.PISO_BATEO
    )
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.BATEO, player=flojo, linea="1-4", valor=daily.PISO_BATEO - 0.01
    )

    datos = daily.portada()

    assert datos is not None
    assert [d.player.player_id for d in datos["destacados"]] == [200]


@pytest.mark.django_db
def test_una_jornada_sin_nadie_destacado_no_desplaza_a_la_anterior(temporada: SeasonDates) -> None:
    """La regla del dueño: hoy se enseña en cuanto haya UN destacado; mientras no lo haya, ayer.

    Es lo que hace que la carga horaria no vacíe el widget. «Hoy» empieza a existir a media tarde con
    cero destacados, y elegir la última jornada GUARDADA lo habría dejado hueco hasta la noche.
    """
    ayer_bueno = _jugador(300)
    hoy_flojo = _jugador(301)
    DailyStandout.objects.create(
        fecha=AYER, grupo=DailyStandout.Grupo.BATEO, player=ayer_bueno, linea="3-4, HR", valor=2.0
    )
    DailyStandout.objects.create(
        fecha=AYER + timedelta(days=1), grupo=DailyStandout.Grupo.BATEO, player=hoy_flojo, linea="1-4", valor=0.1
    )

    datos = daily.portada()

    assert datos is not None
    assert datos["dia"] == AYER
    assert [d.player.player_id for d in datos["destacados"]] == [300]


# ── El comando ──────────────────────────────────────────────────────────────────────────────────


def _pizarra_falsa(*jornadas: tuple[date, set[str], set[str]]) -> Any:
    """Una pizarra con lo mínimo que mira `equipos_terminados`: día, juegos, estado y códigos.

    Se arma a mano en vez de pedirla al proxy porque en los tests no se sale a la red. Ojo con la
    tentación de devolver `None` para «no hay nada»: eso significa «no se pudo preguntar», que desde
    el review v10 es un fallo y no un día tranquilo.
    """
    from types import SimpleNamespace

    from dglweb.stats import scoreboard

    def juego(codigo: str, estado: str) -> Any:
        return SimpleNamespace(estado=estado, lados=[SimpleNamespace(codigo=codigo)])

    return SimpleNamespace(
        jornadas=[
            SimpleNamespace(
                dia=dia,
                juegos=[juego(c, scoreboard.FINAL) for c in terminados] + [juego(c, scoreboard.VIVO) for c in jugando],
            )
            for dia, terminados, jugando in jornadas
        ]
    )


class _ProxyFalso:
    """Devuelve una jornada con un bateador y un lanzador, más los códigos de equipo."""

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if path == "/api/v1/teams":
            return {"teams": [{"id": 135, "teamCode": "sdn"}]}
        bateando = (params or {}).get("group") == "hitting"
        stat = _bateo(AB=4, H=3, X2B=1, HR=1, RBI=4) if bateando else _pitcheo(outsPitched=21, K=9, IP="7.0")
        return {
            "stats": [{"splits": [{"player": {"id": 1, "fullName": "Jugador 1"}, "team": {"id": 135}, "stat": stat}]}]
        }


@pytest.mark.django_db
def test_the_command_stores_the_day_and_records_it(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    _jugador(1)
    monkeypatch.setattr("dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _ProxyFalso())

    call_command("build_daily_standouts", "--fecha", "2026-07-25")

    assert DailyStandout.objects.filter(fecha=AYER).count() == 2  # uno de bateo, uno de pitcheo
    fila = IngestRun.objects.get(command="build_daily_standouts")
    assert fila.status == IngestRun.Status.SUCCESS
    assert "1 bateadores, 1 lanzadores" in fila.detail


@pytest.mark.django_db
def test_a_day_still_being_played_is_not_stored(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """El widget presenta lo guardado como la actuación del día, y con juegos a medias eso es falso.

    Quien va de 0-2 a las nueve de la noche puede terminar de 2-4, y nada en la portada diría que la
    cifra todavía va a cambiar. Se anota como salto y no como fallo: el comando hizo lo correcto.
    """
    from dglweb.stats import scoreboard

    _jugador(1)
    monkeypatch.setattr("dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _ProxyFalso())
    # La pizarra SÍ responde y dice que el juego sigue vivo. Antes este test pasaba sin pizarra
    # ninguna, o sea por el motivo equivocado: ver `test_una_pizarra_que_no_responde_es_un_fallo`.
    hoy = timezone.localdate()
    monkeypatch.setattr(scoreboard, "del_dia", lambda: _pizarra_falsa((hoy, set(), {"MIA"})))

    call_command("build_daily_standouts", "--fecha", hoy.isoformat())

    assert not DailyStandout.objects.exists()
    assert IngestRun.objects.get(command="build_daily_standouts").status == IngestRun.Status.SKIPPED


@pytest.mark.django_db
def test_forcing_stores_an_unfinished_day_anyway(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """La puerta se abre a mano cuando alguien sabe lo que hace; sola, nunca."""
    _jugador(1)
    monkeypatch.setattr("dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _ProxyFalso())

    call_command("build_daily_standouts", "--fecha", timezone.localdate().isoformat(), "--force")

    assert DailyStandout.objects.exists()


@pytest.mark.django_db
def test_a_day_without_games_is_not_a_failure(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """El receso del Juego de Estrellas y cualquier día libre: cero filas, y todo en orden."""

    class _Vacio:
        def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {"teams": []} if path == "/api/v1/teams" else {"stats": [{"splits": []}]}

    monkeypatch.setattr("dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _Vacio())

    call_command("build_daily_standouts", "--fecha", "2026-07-14")

    assert IngestRun.objects.get(command="build_daily_standouts").status == IngestRun.Status.SUCCESS


@pytest.mark.django_db
def test_la_ventana_son_dos_dias_consecutivos(temporada: SeasonDates) -> None:
    """El «hoy» del widget es la jornada más reciente que haya, y el «ayer» es esa fecha menos uno.

    Regla del dueño (2026-07-27), y no es lo mismo que «las dos fechas con datos»: acá hay un hueco
    —falta la de hace tres días— y la de hace cuatro NO puede colarse a rellenar. Si lo hiciera,
    saldría etiquetada «Ayer» siendo de otra semana, que es mentir en la única palabra que el lector
    no puede verificar.
    """
    hoy = timezone.localdate()
    for dias, pid in ((1, 500), (2, 501), (4, 502)):
        DailyStandout.objects.create(
            fecha=hoy - timedelta(days=dias),
            grupo=DailyStandout.Grupo.BATEO,
            player=_jugador(pid),
            linea="3-4, HR",
            valor=2.0,
        )

    datos = daily.portada()

    assert datos is not None
    assert datos["dia"] == hoy - timedelta(days=1)
    assert [d.player.player_id for d in datos["destacados"]] == [500, 501]
    assert [d.etiqueta for d in datos["destacados"]] == ["", date_format(hoy - timedelta(days=2), "j M")]


@pytest.mark.django_db
def test_en_el_receso_se_cae_a_la_ultima_jornada_que_hubo(temporada: SeasonDates) -> None:
    """La red para el Juego de Estrellas: cuatro días sin pelota dejan hoy y ayer vacíos.

    Sin esta rama el widget desaparecería de la portada durante el receso, que es justo cuando menos
    hay que enseñar. Se cae a la última jornada real —una sola— y la fecha del título avisa.
    """
    hoy = timezone.localdate()
    DailyStandout.objects.create(
        fecha=hoy - timedelta(days=4),
        grupo=DailyStandout.Grupo.BATEO,
        player=_jugador(600),
        linea="3-4, HR",
        valor=2.0,
    )

    datos = daily.portada()

    assert datos is not None
    assert datos["dia"] == hoy - timedelta(days=4)
    assert [d.player.player_id for d in datos["destacados"]] == [600]


@pytest.mark.django_db
def test_la_jornada_en_curso_solo_guarda_los_equipos_que_terminaron(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lo que hace honesta la carga horaria.

    `byDateRange` no distingue juego terminado de juego en curso: devuelve lo acumulado hasta ese
    instante. Sin filtrar, el widget publicaría «1.0 IP, 1 K» de alguien que sigue en el montículo, y
    ese número cambiaría solo bajo los ojos del lector — peor que estar desactualizado.

    Medido el 27-07 a media tarde: entre los mejores del día aparecía un lanzador de SEA con el juego
    en marcha.
    """
    from dglweb.stats import scoreboard

    acabo = daily.Actuacion(player_id=1, nombre="Terminado", equipo="MIA", valor=2.0, linea="3-4, HR")
    jugando = daily.Actuacion(player_id=2, nombre="En curso", equipo="SEA", valor=2.0, linea="2-2, HR")

    monkeypatch.setattr(daily, "destacados", lambda *_: {"bateo": [acabo, jugando], "pitcheo": []})
    hoy = timezone.localdate()
    monkeypatch.setattr(scoreboard, "del_dia", lambda: _pizarra_falsa((hoy, {"MIA"}, {"SEA"})))
    guardadas: dict[str, list[daily.Actuacion]] = {}
    monkeypatch.setattr(daily, "guardar", lambda _dia, listas: guardadas.update(listas) or len(listas["bateo"]))
    monkeypatch.setattr(daily, "podar", lambda _temporada: 0)

    call_command("build_daily_standouts", "--fecha-hoy")

    assert [a.equipo for a in guardadas["bateo"]] == ["MIA"], "el equipo que sigue jugando no puede entrar"


# ── El job horario: qué jornadas cubre y qué cuenta como sano (review v10) ──────────────────────


@pytest.fixture
def _sin_escribir(monkeypatch: pytest.MonkeyPatch) -> list[date]:
    """Neutraliza la escritura y devuelve la lista de jornadas que el comando llegó a procesar.

    Interesa QUÉ DÍAS toca, no qué guarda en cada uno — eso ya lo cubren los tests de arriba.
    """
    procesadas: list[date] = []

    def _destacados(_cliente: Any, dia: date, _universo: Any) -> dict[str, list[Any]]:
        procesadas.append(dia)
        return {
            "bateo": [daily.Actuacion(player_id=1, nombre="X", equipo="MIA", valor=2.0, linea="3-4")],
            "pitcheo": [],
        }

    monkeypatch.setattr(daily, "destacados", _destacados)
    monkeypatch.setattr(daily, "guardar", lambda _dia, listas: len(listas["bateo"]))
    monkeypatch.setattr(daily, "podar", lambda _temporada: 0)
    monkeypatch.setattr("dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: None)
    return procesadas


@pytest.mark.django_db
def test_una_pizarra_que_no_responde_es_un_fallo_y_no_un_dia_tranquilo(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El agujero que abría aceptar el salto como sano, y que no estaba en el review v10.

    Con el proxy caído, `del_dia()` devuelve `None`, de ahí salía un conjunto vacío de equipos
    terminados, y el comando lo anotaba como «ningún juego ha terminado todavía» — el MISMO salto que
    a las diez de la mañana. Como el semáforo acepta ese salto en este job, el monitor se habría
    quedado en verde mientras el widget se congelaba: justo lo contrario de lo que se pedía.

    «Nadie ha terminado» tiene que significar eso, y no «no pude preguntar».
    """
    from dglweb.stats import scoreboard

    monkeypatch.setattr(scoreboard, "del_dia", lambda: None)

    with pytest.raises(CommandError, match="pizarra"):
        call_command("build_daily_standouts", "--fecha-hoy")

    assert not IngestRun.objects.filter(status=IngestRun.Status.SKIPPED).exists(), (
        "un proxy caído no puede dejar la misma huella que una mañana sin juegos"
    )


@pytest.mark.django_db
def test_el_job_horario_cubre_el_juego_del_pacifico_que_cruzo_la_medianoche(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch, _sin_escribir: list[date]
) -> None:
    """En béisbol la jornada no termina a medianoche (QA-02/SAB-01 del review v10).

    Un juego de la costa oeste empieza el 28 y termina a la 1:15 de la madrugada dominicana del 29,
    pero sigue siendo del 28. Preguntando solo por `localdate()`, a esa hora el job miraba el 29
    —donde no ha empezado nada— y la actuación no aparecía hasta el refresco de las 4:30.
    """
    from dglweb.stats import scoreboard

    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    # De madrugada: lo de ayer acaba de cerrar, lo de hoy ni ha empezado.
    monkeypatch.setattr(scoreboard, "del_dia", lambda: _pizarra_falsa((ayer, {"SEA"}, set()), (hoy, set(), set())))

    call_command("build_daily_standouts", "--fecha-hoy")

    assert _sin_escribir == [ayer]


@pytest.mark.django_db
def test_el_job_horario_suelta_ayer_en_cuanto_lo_toma_el_refresco_diario(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch, _sin_escribir: list[date]
) -> None:
    """El corte NO es una hora inventada: es el momento en que otro proceso se hace cargo.

    Poner «antes de las 5 de la mañana todavía cuenta como ayer» habría sido un número a mantener el
    día que el refresco cambie de hora. Así el traspaso se apaga solo, y son cuatro corridas de más.
    """
    from dglweb.stats import scoreboard

    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    monkeypatch.setattr(scoreboard, "del_dia", lambda: _pizarra_falsa((ayer, {"SEA"}, set()), (hoy, {"MIA"}, set())))
    # La huella que deja el refresco de las 4:30 al guardar la jornada completa de ayer.
    IngestRun.objects.create(
        command="build_daily_standouts",
        scope=ayer.isoformat(),
        status=IngestRun.Status.SUCCESS,
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )

    call_command("build_daily_standouts", "--fecha-hoy")

    assert _sin_escribir == [hoy], "ayer ya lo guardó el refresco; volver a procesarlo es trabajo de más"


@pytest.mark.django_db
def test_las_corridas_del_job_horario_se_distinguen_de_las_del_refresco(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch, _sin_escribir: list[date]
) -> None:
    """Lo que impide que el éxito del refresco diario tape tres horas de fallos del horario.

    Los dos modos escriben `command="build_daily_standouts"`, así que sin este sufijo en el `scope`
    el semáforo no puede saber cuál de los dos corrió. Ver `stats/jobs.py`.
    """
    from dglweb.stats import scoreboard

    hoy = timezone.localdate()
    monkeypatch.setattr(scoreboard, "del_dia", lambda: _pizarra_falsa((hoy, {"MIA"}, set())))

    call_command("build_daily_standouts", "--fecha-hoy")

    assert IngestRun.objects.get().scope == f"{hoy.isoformat()} {jobs.ALCANCE_EN_CURSO}"


@pytest.mark.django_db
def test_una_manana_sin_juegos_cerrados_deja_un_salto_con_el_alcance_puesto(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El salto sano tiene que llevar el alcance igual que la corrida buena.

    Si no, el semáforo no lo encontraría —filtra por el sufijo— y se pondría rojo a media mañana
    todos los días, que es la alarma que se aprende a ignorar.
    """
    from dglweb.stats import scoreboard

    hoy = timezone.localdate()
    monkeypatch.setattr(scoreboard, "del_dia", lambda: _pizarra_falsa((hoy, set(), {"MIA"})))

    call_command("build_daily_standouts", "--fecha-hoy")

    fila = IngestRun.objects.get()
    assert fila.status == IngestRun.Status.SKIPPED
    assert fila.scope.endswith(jobs.ALCANCE_EN_CURSO)


@pytest.mark.django_db
def test_el_refresco_diario_no_lleva_alcance(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """La otra mitad: la corrida de ayer tiene que quedar SIN sufijo.

    Es lo que mira `_ya_la_tomo_el_refresco` para soltar la jornada, así que un sufijo de más acá
    dejaría al job horario reprocesando ayer para siempre.
    """
    _jugador(1)
    monkeypatch.setattr("dglweb.stats.management.commands.build_daily_standouts.build_client", lambda: _ProxyFalso())

    call_command("build_daily_standouts", "--fecha", "2026-07-25")

    assert IngestRun.objects.get().scope == "2026-07-25"


# ── DEV-01 del review v13: una línea imposible no se puntúa ──────────────────────────────────────
#
# Los componentes se sacan RESTANDO —los sencillos son `H - 2B - 3B - HR`, los boletos ganados
# `BB - IBB`— y `_numero()` convierte lo ausente en cero. Si el proxy omite `H` pero manda un doble, el
# código inventa -1 sencillos y devuelve un float perfectamente válido.
#
# Medido antes de arreglarlo, sobre 6 IP con 6 K y 4 H:
#
#     limpio                        +3,016
#     IBB=2 con BB=0 (imposible)    +3,244   PREMIA
#     H ausente y 2 dobles          +4,286   PREMIA  ← +1,27 carreras de regalo
#
# En pitcheo premia porque toda la suma va negada, y +1,27 mueve a un lanzador varios puestos.


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("caso", "stat"),
    [
        ("más extrabases que hits", {"H": 0, "X2B": 1}),
        ("un jonrón sin hit", {"H": 0, "HR": 1}),
        ("más intencionales que boletos", {"BB": 0, "IBB": 2}),
        ("hits y ponches de más para los turnos", {"AB": 3, "H": 2, "K": 2}),
    ],
)
def test_una_linea_imposible_se_reconoce(caso: str, stat: dict[str, Any]) -> None:
    """Cada una es aritmética de definición, no un criterio nuestro: un extrabase ES un hit, un
    intencional ES un boleto, y un hit y un ponche son turnos al bate excluyentes entre sí."""
    assert daily.por_que_no_cuadra(stat), caso


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("caso", "stat"),
    [
        ("una jornada normal", {"AB": 4, "H": 2, "X2B": 1, "K": 1}),
        ("solo boletos, sin turnos", {"AB": 0, "BB": 2, "IBB": 1}),
        ("un ponche y nada más", {"AB": 3, "K": 1}),
        ("todo en cero", {}),
        ("una salida de pitcheo limpia", {"outsPitched": 18, "K": 6, "H": 4}),
    ],
)
def test_una_linea_buena_no_se_descarta(caso: str, stat: dict[str, Any]) -> None:
    """El otro lado, que es el que un validador demasiado estricto rompe sin que nadie lo note.

    El caso de «solo boletos» es el que obliga a mirar `AB` solo cuando hay: una línea de puro boleto
    trae `AB=0` legítimamente, y exigir `H + K <= AB` ahí descartaría filas buenas.
    """
    assert daily.por_que_no_cuadra(stat) == "", caso


@pytest.mark.django_db
def test_el_motivo_dice_los_numeros_y_no_solo_que_esta_mal() -> None:
    """Va a un log que alguien lee a las seis de la mañana. «línea inválida» no se puede depurar."""
    motivo = daily.por_que_no_cuadra({"H": 1, "X2B": 2, "HR": 1})

    assert "3" in motivo and "1" in motivo, motivo


@pytest.mark.django_db
def test_una_linea_imposible_no_llega_a_la_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    """LA PRUEBA QUE IMPORTA: que la fila no se puntúe, no solo que se sepa que está mal."""
    bueno = {"player": {"id": 1, "fullName": "Bueno"}, "team": {"id": 0}, "stat": {"AB": 4, "H": 3}}
    imposible = {"player": {"id": 2, "fullName": "Imposible"}, "team": {"id": 0}, "stat": {"H": 0, "X2B": 2}}

    monkeypatch.setattr(daily, "splits", lambda *a, **k: [bueno, imposible])

    # El cliente no se toca: `splits` está sustituido y es lo único que lo usaría. El `cast` es para
    # mypy, que corre sobre los tests y no puede saberlo.
    salida = daily._actuaciones(
        cast("Any", None), "hitting", AYER, {1, 2}, {}, daily.valor_de_bateo, daily.linea_de_bateo
    )

    assert [a.player_id for a in salida] == [1], "la línea imposible se colgó en la lista"
