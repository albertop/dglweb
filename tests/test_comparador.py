"""El cálculo del comparador. Ver `docs/COMPARADOR.md`.

Se prueban las tres modalidades, el ranking histórico y las reglas que se decidieron a mano: el
universo desde 1956, el rango de 1 a 7 temporadas con descenso automático, y qué métricas no se
rankean.

Los datos se montan a mano y pequeños. La tentación es probar contra la base real —«Pujols tiene 703
jonrones»— y eso ata la prueba a una carga concreta: el día que se actualice la temporada, falla sin
que nadie haya roto nada.
"""

from typing import Any

import pytest

from dglweb.players.models import Player
from dglweb.stats import comparador
from dglweb.stats.models import Batting, Metric, Pitching
from tests.test_players import _other_player


def _jugador(pid: int, nombre: str, debut: str = "1990-04-05") -> Player:
    return Player.objects.create(
        **_other_player(player_id=pid, dgl_id=f"c{pid}", full_name=nombre, debut_date=debut)
    )


def _bateo(jugador: Player, season: int, **stats: Any) -> Batting:
    base = {
        "player": jugador, "season": season, "stint": 1, "team": "SDN", "league": "NL",
        "g": 150, "ab": 500, "pa": 600, "h": 150, "x1b": 100, "x2b": 30, "x3b": 5, "hr": 15,
        "rbi": 70, "r": 80, "bb": 60, "so": 100, "sb": 10, "cs": 3, "hbp": 5, "sf": 4,
        "war": 3.0, "avg": 0.300, "obp": 0.380, "slg": 0.450, "ops": 0.830,
        "woba": 0.360, "w_rc_plus": 120.0,
    }  # fmt: skip
    return Batting.objects.create(**(base | stats))


def _pitcheo(jugador: Player, season: int, **stats: Any) -> Pitching:
    base = {
        "player": jugador, "season": season, "stint": 1, "team": "SDN", "league": "NL",
        "g": 32, "gs": 32, "outs": 600, "w": 15, "l": 8, "so": 200, "bb": 50, "h": 180,
        "er": 70, "hr": 20, "r": 75, "ab": 750, "war": 4.0, "era": 3.15, "era_minus": 85.0,
        "fip": 3.40, "fip_minus": 88.0, "so_per9": 9.0, "bb_per9": 2.25,
    }  # fmt: skip
    return Pitching.objects.create(**(base | stats))



# ── El universo ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_los_de_ligas_negras_quedan_fuera() -> None:
    """El corte no es por fecha sino por fuente: sus estadísticas no son comparables y no tienen WAR.

    Tetelo Vargas figura con debut el 1 de enero de 1927 porque se conoce el año y no el día. Por eso
    el corte mira el AÑO — si mirara la fecha completa, seguiría funcionando por casualidad hoy y
    dejaría de hacerlo el día que alguien lo moviera a mitad de año.
    """
    moderno = _jugador(1, "Moderno", debut="1990-04-05")
    tetelo = _jugador(2, "Tetelo Vargas", debut="1927-01-01")
    justo = _jugador(3, "El del 56", debut="1956-09-23")

    dentro = comparador.universo("batting")

    assert moderno.player_id in dentro
    assert justo.player_id in dentro, "1956 es el primer año que entra, no el primero que sale"
    assert tetelo.player_id not in dentro


@pytest.mark.django_db
def test_un_jugador_deshabilitado_no_entra_ni_al_ranking() -> None:
    """`Player.hidden` promete que desaparece del sitio, y el ranking es parte del sitio."""
    _jugador(1, "Visible")
    oculto = _jugador(2, "Dado de baja")
    Player.objects.filter(pk=oculto.pk).update(hidden=True, disabled_reason="prueba")

    assert oculto.player_id not in comparador.universo("batting")


# ── Las tres modalidades ────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_carrera_suma_los_acumulables_y_recalcula_las_tasas(catalogo: None) -> None:
    """La tasa se recalcula desde los componentes sumados, no se promedia.

    Dos temporadas de .300 y .200 con turnos muy distintos NO dan .250: dan lo que salga de sumar los
    hits y los turnos. Es la diferencia que un promedio de promedios se come.
    """
    uno = _jugador(1, "Uno")
    _bateo(uno, 2020, h=150, ab=500, hr=20, avg=0.300)
    _bateo(uno, 2021, h=20, ab=100, hr=5, avg=0.200)
    _jugador(2, "Otro")

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_CARRERA)
    celdas = foto["izquierda"]["celdas"]

    assert celdas["hr"].valor == 25  # acumulable: se suma
    assert celdas["avg"].valor == pytest.approx(170 / 600)  # 0.283, no 0.250
    assert celdas["avg"].valor != pytest.approx(0.250)


@pytest.mark.django_db
def test_temporada_toma_solo_ese_ano_y_no_tienen_que_coincidir(catalogo: None) -> None:
    """«Soto 2024 vs. Guerrero 2021» es justo lo que nadie más publica."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020, hr=40)
    _bateo(uno, 2021, hr=10)
    _bateo(otro, 2021, hr=25)

    foto = comparador.comparar("batting", (1, 2020), (2, 2021), comparador.MODO_TEMPORADA)

    assert foto["izquierda"]["celdas"]["hr"].valor == 40
    assert foto["derecha"]["celdas"]["hr"].valor == 25
    assert foto["izquierda"]["temporadas"] == (2020,)
    assert foto["derecha"]["temporadas"] == (2021,)


@pytest.mark.django_db
def test_mejores_toma_las_de_mas_war_y_no_las_ultimas(catalogo: None) -> None:
    uno = _jugador(1, "Uno")
    _bateo(uno, 2018, war=1.0, hr=5)
    _bateo(uno, 2019, war=8.0, hr=40)
    _bateo(uno, 2020, war=6.0, hr=30)
    _bateo(uno, 2021, war=7.0, hr=35)
    otro = _jugador(2, "Otro")
    for anio in (2018, 2019, 2020, 2021):
        _bateo(otro, anio, war=2.0, hr=10)

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=3)

    assert foto["izquierda"]["temporadas"] == (2019, 2020, 2021), "la de WAR 1.0 se queda fuera"
    assert foto["izquierda"]["celdas"]["hr"].valor == 105


@pytest.mark.django_db
def test_el_que_no_llega_a_las_pedidas_da_error_con_su_maximo(catalogo: None) -> None:
    """Se avisa en vez de bajar en silencio (dueño, al montar el generador).

    El principio no cambia: nunca se enfrentan 5 temporadas contra 3, porque cinco acumulan más de
    todo y el de carrera larga ganaría por construcción. Lo que cambia es cómo se evita — antes
    igualando por abajo, ahora negándose y diciendo con cuántas sí se puede.

    El error lleva los DATOS y no la frase: nombrar al pelotero exige consultar `Player`, y eso es
    trabajo de la vista."""
    largo = _jugador(1, "Carrera larga")
    for anio in range(2015, 2023):
        _bateo(largo, anio, war=5.0, hr=30)
    corto = _jugador(2, "Carrera corta")
    for anio in range(2020, 2023):
        _bateo(corto, anio, war=5.0, hr=30)

    with pytest.raises(comparador.TemporadasInsuficientesError) as fallo:
        comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=5)

    assert fallo.value.player_id == 2, "acusa al que se queda corto, no al otro"
    assert (fallo.value.tiene, fallo.value.pedidas) == (3, 5)


@pytest.mark.django_db
@pytest.mark.parametrize("pedidas", [1, 2, 3, 5, 7])
def test_mejores_acepta_de_una_a_siete_temporadas(catalogo: None, pedidas: int) -> None:
    """El rango se abrió de 1 a 7 (dueño). Con X=1 la pregunta es «su mejor año contra su mejor año»,
    que NO es el modo temporada: allí el año lo elige quien compara y acá lo elige el WAR."""
    for pid in (1, 2):
        jugador = _jugador(pid, f"Jugador {pid}")
        for anio in range(2015, 2025):
            _bateo(jugador, anio, war=float(anio - 2014), hr=anio - 2014)

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=pedidas)

    assert foto["cuantas"] == pedidas
    assert len(foto["izquierda"]["temporadas"]) == pedidas


@pytest.mark.django_db
@pytest.mark.parametrize("fuera", [0, 8, 12])
def test_pedir_fuera_del_rango_es_un_error_y_no_se_recorta(catalogo: None, fuera: int) -> None:
    """Un 12 en la URL es un error de quien la escribió; devolver «las 7 mejores» lo escondería.

    El descenso automático es para quien NO TIENE temporadas suficientes, que es otra cosa: ahí no
    hay error de nadie y por eso sí se baja en silencio, con el rótulo diciendo el número real.
    """
    for pid in (1, 2):
        jugador = _jugador(pid, f"Jugador {pid}")
        for anio in range(2015, 2025):
            _bateo(jugador, anio)

    with pytest.raises(ValueError, match="entre 1 y 7 temporadas"):
        comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=fuera)


@pytest.mark.django_db
def test_sin_ninguna_temporada_con_war_no_hay_nada_que_agregar(catalogo: None) -> None:
    largo = _jugador(1, "Largo")
    for anio in range(2015, 2023):
        _bateo(largo, anio)
    _bateo(_jugador(2, "Sin WAR"), 2022, war=None)

    with pytest.raises(comparador.TemporadasInsuficientesError):
        comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES)


# ── El ranking histórico ────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_en_modo_temporada_se_rankea_contra_todas_las_temporadas(catalogo: None) -> None:
    """El histórico compara temporadas sueltas contra las 5.185 de la historia, no contra 870 carreras.

    Un mismo pelotero aporta UNA por cada año que jugó: sus buenos años compiten con los ajenos y
    también entre sí.
    """
    estrella = _jugador(1, "Estrella")
    _bateo(estrella, 2019, hr=50)
    _bateo(estrella, 2020, hr=45)
    _bateo(estrella, 2021, hr=30)
    otro = _jugador(2, "Otro")
    _bateo(otro, 2019, hr=48)

    foto = comparador.comparar("batting", (1, 2021), (2, 2019), comparador.MODO_TEMPORADA)

    # 50, 48 y 45 superan a los 30 de 2021 -> 4º de cuatro temporadas en la población.
    assert foto["izquierda"]["celdas"]["hr"].rank == 4
    assert foto["izquierda"]["celdas"]["hr"].de == 4
    # Los 48 solo los supera el 50 -> 2º.
    assert foto["derecha"]["celdas"]["hr"].rank == 2


@pytest.mark.django_db
def test_el_ranking_de_carrera_compara_carreras(catalogo: None) -> None:
    """Y no temporadas: en carrera cada jugador aporta UNA entrada a la población."""
    uno = _jugador(1, "Uno")
    _bateo(uno, 2019, hr=30)
    _bateo(uno, 2020, hr=30)  # 60 de carrera
    otro = _jugador(2, "Otro")
    _bateo(otro, 2019, hr=50)  # 50 de carrera

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_CARRERA)

    assert foto["izquierda"]["celdas"]["hr"].rank == 1
    assert foto["derecha"]["celdas"]["hr"].rank == 2
    assert foto["izquierda"]["celdas"]["hr"].de == 2, "dos carreras, no tres temporadas"


@pytest.mark.django_db
def test_una_metrica_de_menos_es_mejor_se_rankea_al_reves(catalogo: None) -> None:
    """En efectividad gana el más bajo. La dirección la declara el catálogo, no se asume."""
    bueno, malo = _jugador(1, "Bueno"), _jugador(2, "Malo")
    _pitcheo(bueno, 2020, er=50, outs=600)
    _pitcheo(malo, 2020, er=120, outs=600)

    foto = comparador.comparar("pitching", (1, 2020), (2, 2020), comparador.MODO_TEMPORADA)

    assert foto["izquierda"]["celdas"]["era"].valor < foto["derecha"]["celdas"]["era"].valor
    assert foto["izquierda"]["celdas"]["era"].rank == 1


@pytest.mark.django_db
def test_las_derrotas_se_pintan_pero_no_se_rankean(catalogo: None) -> None:
    """«5º dominicano en derrotas» es un dato raro de presumir. Ver `SIN_RANKING`."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _pitcheo(uno, 2020, w=20, l=3)
    _pitcheo(otro, 2020, w=8, l=15)

    foto = comparador.comparar("pitching", (1, 2020), (2, 2020), comparador.MODO_TEMPORADA)

    assert foto["izquierda"]["celdas"]["l"].valor == 3
    assert foto["izquierda"]["celdas"]["l"].rank is None
    assert foto["izquierda"]["celdas"]["w"].rank == 1, "las victorias sí se rankean"


# ── Las tasas aproximadas ───────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_las_indexadas_se_marcan_como_aproximadas(catalogo: None) -> None:
    """wOBA, wRC+, ERA- y FIP- llevan coeficientes que cambian cada año, así que no se pueden
    reconstruir sumando componentes: se ponderan. La imagen tiene que marcarlo."""
    uno = _jugador(1, "Uno")
    _bateo(uno, 2019, pa=600, woba=0.400)
    _bateo(uno, 2020, pa=200, woba=0.300)
    _jugador(2, "Otro")

    celdas = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_CARRERA)["izquierda"]["celdas"]

    assert celdas["woba"].aproximada is True
    assert celdas["avg"].aproximada is False, "el promedio sí sale exacto de los componentes"
    # Ponderado por apariciones: (0.400*600 + 0.300*200) / 800
    assert celdas["woba"].valor == pytest.approx(0.375)


@pytest.mark.django_db
def test_una_temporada_sin_war_no_entra_en_las_mejores(catalogo: None) -> None:
    """Un año sin dato no es un año malo: se deja fuera en vez de contarlo como cero."""
    uno = _jugador(1, "Uno")
    _bateo(uno, 2018, war=None, hr=60)
    for anio in (2019, 2020, 2021):
        _bateo(uno, anio, war=4.0, hr=10)
    otro = _jugador(2, "Otro")
    for anio in (2019, 2020, 2021):
        _bateo(otro, anio, war=4.0, hr=10)

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=3)

    assert 2018 not in foto["izquierda"]["temporadas"]
    assert foto["izquierda"]["celdas"]["hr"].valor == 30, "los 60 de la temporada sin WAR no entran"


@pytest.mark.django_db
def test_una_temporada_de_cafe_no_cuenta_como_temporada(catalogo: None) -> None:
    """Un año de veinte turnos no es una temporada, aunque tenga WAR. Ver `MINIMO_TEMPORADA`.

    ES DISTINTO DE NO TENER WAR: acá el dato existe y vale casi cero, así que sin umbral entraría en
    la bolsa de quien tenga justo las pedidas y le hundiría el agregado. Y no basta con excluirlo del
    valor: tampoco puede contar para decidir si el jugador LLEGA a las temporadas pedidas.
    """
    uno = _jugador(1, "Uno")
    _bateo(uno, 2018, pa=20, ab=18, war=0.1, hr=0)
    for anio in (2019, 2020, 2021):
        _bateo(uno, anio, war=4.0, hr=10)
    otro = _jugador(2, "Otro")
    for anio in (2019, 2020, 2021):
        _bateo(otro, anio, war=4.0, hr=10)

    with pytest.raises(comparador.TemporadasInsuficientesError) as fallo:
        comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=4)
    assert fallo.value.tiene == 3, "las tres de verdad, no las cuatro que hay en la tabla"

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=3)
    assert 2018 not in foto["izquierda"]["temporadas"]
    assert foto["minimo"] == 100, "el umbral viaja con el resultado para escribirlo al pie"


@pytest.mark.django_db
def test_la_carrera_no_descarta_las_temporadas_cortas(catalogo: None) -> None:
    """El umbral es de «mejores X» y de nadie más: los jonrones de una carrera son todos."""
    uno = _jugador(1, "Uno")
    _bateo(uno, 2018, pa=20, ab=18, war=0.1, hr=3)
    _bateo(uno, 2019, war=4.0, hr=10)

    foto = comparador.comparar("batting", (1, None), (1, None), comparador.MODO_CARRERA)

    assert foto["izquierda"]["celdas"]["hr"].valor == 13, "los 3 del año corto también cuentan"


@pytest.mark.django_db
def test_en_mejores_x_el_umbral_de_las_tasas_escala_con_las_temporadas(catalogo: None) -> None:
    """Las tasas de «mejores X» NO se miden contra el umbral de carrera. Ver `_formula`.

    EL FALLO QUE ESTO CAZA, encontrado por el dueño con Vladimir Guerrero padre e hijo: a una bolsa
    de tres temporadas se le exigía PA>=3000 —el umbral de CARRERA— que ninguna bolsa de tres puede
    alcanzar. La población quedaba vacía y los dos peloteros salían «1º» en promedio, OBP, SLG, OPS,
    wOBA y wRC+ a la vez. Sale en la tarjeta como un dato, no como un error, y es de las peores
    formas de fallar: nadie duda de un número.

    Se ve solo mirando `de`, que es cuántos había en la población. Por eso se comprueba `de` y no
    solo `rank`: con la población vacía el puesto SIEMPRE es 1, así que un `rank == 1` no distingue
    al mejor de la historia de un cálculo roto.
    """
    for pid in range(1, 6):
        jugador = _jugador(pid, f"J{pid}")
        for anio in (2019, 2020, 2021):
            _bateo(jugador, anio, war=float(pid), avg=0.250 + pid / 100, h=125 + pid)

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=3)

    assert foto["izquierda"]["celdas"]["avg"].de == 5, "los cinco compiten; ninguno tiene 3.000 PA"
    assert foto["izquierda"]["celdas"]["avg"].de == foto["izquierda"]["celdas"]["h"].de, (
        "una tasa y un acumulado de la misma bolsa se miden contra la misma gente"
    )


@pytest.mark.django_db
def test_una_bolsa_floja_no_entra_en_el_ranking_de_tasas(catalogo: None) -> None:
    """Escalar el umbral no es quitarlo: quien no jugó lo suficiente sigue fuera de las tasas.

    Es lo que impide que un .400 de 300 turnos en tres años desplace a quien lo hizo jugando entero.
    """
    titular, suplente = _jugador(1, "Titular"), _jugador(2, "Suplente")
    for anio in (2019, 2020, 2021):
        _bateo(titular, anio, avg=0.300)
        _bateo(suplente, anio, pa=120, ab=110, avg=0.400)

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_MEJORES, cuantas=3)

    assert foto["izquierda"]["celdas"]["avg"].de == 1, "solo el titular llega al umbral de tres temporadas"
    assert foto["derecha"]["celdas"]["avg"].rank is None, "sin umbral no hay puesto que dar"


@pytest.mark.django_db
def test_el_resaltado_de_la_tarjeta_sigue_al_numero_que_se_ve(catalogo: None) -> None:
    """Dos cifras iguales en la imagen se resaltan las dos. Ver `tarjeta.dibujar`.

    EL CASO QUE LO OBLIGA, visto por el dueño en wRC+: Alex Rodríguez y Pujols salían los dos con 141
    y solo uno aparecía resaltado, porque por dentro difieren en decimales que la tarjeta redondea.
    Quien mira la imagen ve dos números idénticos y uno pintado como mejor, sin nada que lo explique.

    Se comprueba el TEXTO y no el resaltado en píxeles a propósito: lo que se protege es la regla
    —empate en pantalla, empate en el resaltado— y esa vive en cómo se escribe el número.
    """
    from dglweb.stats import tarjeta

    metrica = Metric.objects.get(stat_group="batting", column="w_rc_plus")

    assert tarjeta._texto("w_rc_plus", 141.4, metrica) == tarjeta._texto("w_rc_plus", 140.6, metrica)
    assert tarjeta._texto("w_rc_plus", 141.4, metrica) != tarjeta._texto("w_rc_plus", 139.4, metrica)


@pytest.mark.django_db
def test_un_relevista_se_rankea_entre_relevistas(catalogo: None) -> None:
    """Abridores y relevistas son poblaciones distintas y umbrales distintos (dueño, 2026-08-13).

    EL CASO QUE LO OBLIGA, visto por el dueño en la tarjeta de José Mesa contra Rafael Soriano: a
    Soriano le faltaban los puestos de TODAS las tasas. El umbral de carrera del catálogo es IP>=1000,
    que es de abridor; un cerrador no se acerca nunca. Medido: de 440 relevistas dominicanos, siete
    llegan a mil entradas, y son los que abrieron parte de su carrera.
    """
    relevista = _jugador(1, "Cerrador")
    relevista.pos = "RP"
    relevista.save(update_fields=["pos"])
    for anio in (2018, 2019, 2020, 2021, 2022):
        # 90 IP al año, 450 de carrera: por encima del umbral del relevista (400) y muy por debajo
        # del de abridor (1.000). Es justo la franja donde vive un cerrador de carrera larga.
        _pitcheo(relevista, anio, outs=270, er=25)

    sin_oficio = comparador.comparar("pitching", (1, None), (1, None), comparador.MODO_CARRERA)
    con_oficio = comparador.comparar(
        "pitching", (1, None), (1, None), comparador.MODO_CARRERA, oficio=comparador.OFICIO_RELEVISTA
    )

    assert sin_oficio["izquierda"]["celdas"]["era"].rank is None, "con el umbral de abridor no califica"
    assert con_oficio["izquierda"]["celdas"]["era"].rank == 1, "con el suyo, sí"
    assert con_oficio["oficio"] == comparador.OFICIO_RELEVISTA, "y viaja para que la tarjeta lo escriba"


@pytest.mark.django_db
def test_la_poblacion_del_ranking_no_mezcla_oficios(catalogo: None) -> None:
    """Bajarle el umbral al relevista sin separar la población lo metería a competir contra abridores.

    Es la mitad que de verdad hace que el número signifique algo: «1º en efectividad» tiene que querer
    decir «entre relevistas», no «entre lanzadores de 200 entradas al año y cerradores mezclados».
    """
    for pid, pos in ((1, "RP"), (2, "SP")):
        jugador = _jugador(pid, f"J{pid}")
        jugador.pos = pos
        jugador.save(update_fields=["pos"])
        for anio in (2018, 2019, 2020, 2021, 2022):
            _pitcheo(jugador, anio, outs=270 if pos == "RP" else 620, er=25)

    foto = comparador.comparar(
        "pitching", (1, None), (1, None), comparador.MODO_CARRERA, oficio=comparador.OFICIO_RELEVISTA
    )

    assert foto["izquierda"]["celdas"]["era"].de == 1, "el abridor no entra en la población del relevista"


@pytest.mark.django_db
def test_el_comparador_no_mira_nunca_la_postemporada(catalogo: None) -> None:
    """La comparación es de temporada regular, siempre (dueño, 2026-08-13).

    POR QUÉ HAY QUE FIJARLO. Los dos mundos conviven en la misma base y se distinguen por una columna
    —`Leader.postseason`, y tablas `BattingPost`/`PitchingPost` aparte—, así que mezclarlos no rompe
    nada: produce números correctos que responden a otra pregunta. Un 1.000 de porcentaje de victorias
    es cierto si son las de octubre, y en una tarjeta que circula sola nadie puede saberlo.

    Se comprueba que el módulo del cálculo NO NOMBRE la postemporada, en vez de comparar cifras: es la
    forma de que la prueba siga valiendo cuando se añadan métricas.
    """
    import inspect

    fuente = inspect.getsource(comparador)

    for prohibido in ("BattingPost", "PitchingPost", "_POST_MODEL", "postseason"):
        assert prohibido not in fuente, f"el comparador no puede saber de {prohibido}"

    # Y las tablas que lee son las de temporada regular, no un alias que apunte a otra cosa.
    from dglweb.stats.leaders import _MODEL

    assert {_MODEL["batting"].__name__, _MODEL["pitching"].__name__} == {"Batting", "Pitching"}


@pytest.mark.django_db
def test_octubre_y_temporada_regular_son_dos_tableros(catalogo: None) -> None:
    """`dgl_leader` guarda los dos en la misma tabla y los separa `postseason`. Nunca se mezclan.

    ES LA LECCIÓN CARA DE ESTA SESIÓN. El issue del W-L del TODO nació de contar filas sin ese
    discriminador: salían «duplicados» que no existían y un 1.000 que era el récord de octubre de
    Fernando Rodney —1-0— leído como si fuera su carrera. Consultar `Leader` sin `postseason` es tan
    incorrecto como consultarlo sin `metric`.
    """
    from dglweb.stats.models import Leader

    campos = {f.name for f in Leader._meta.get_fields()}
    assert "postseason" in campos, "sin este campo los dos tableros serían indistinguibles"

    # La clave que identifica UNA fila de tablero. Si alguien añade una dimensión y no la mete acá,
    # esta prueba no lo caza — pero el comentario le dirá dónde mirar.
    clave = {"metric", "board", "season", "fielding_pos", "player", "postseason"}
    assert clave <= campos


@pytest.mark.django_db
def test_el_ranking_del_card_ignora_la_postemporada(catalogo: None) -> None:
    """Los puestos que salen entre paréntesis son de temporada regular (dueño, 2026-08-13).

    SE PRUEBA CON DATOS y no leyendo el código: se le cuelga al pelotero una línea de octubre enorme
    —treinta jonrones— y se comprueba que ni su cifra ni su puesto se mueven. Un test que solo mira
    los imports deja de valer en cuanto alguien añade una consulta nueva.

    OCTUBRE NO SE SUMA A NADA. El valor de la tarjeta es de temporada regular y el ranking se calcula
    sobre la misma población, así que las dos mitades del paréntesis hablan del mismo universo. Mezclar
    no rompería nada: daría cifras correctas que responden a otra pregunta, y en una imagen que circula
    sola nadie podría notarlo.
    """
    from dglweb.stats.models import BattingPost

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020, hr=10)
    _bateo(otro, 2020, hr=20)

    antes = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_CARRERA)

    BattingPost.objects.create(
        player=uno, season=2020, round="WS", team="SDN", league="NL", g=7, pa=30, ab=28, hr=30, h=15
    )
    despues = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_CARRERA)

    izq_antes, izq_despues = antes["izquierda"]["celdas"]["hr"], despues["izquierda"]["celdas"]["hr"]
    assert izq_despues.valor == izq_antes.valor == 10, "los 30 de octubre no se suman"
    assert izq_despues.rank == izq_antes.rank, "ni cambian el puesto"
    assert izq_despues.de == izq_antes.de, "ni la población contra la que se rankea"


@pytest.mark.django_db
def test_el_porcentaje_de_victorias_solo_se_rankea_en_abridores(catalogo: None) -> None:
    """PCT lleva puesto si son abridores y no si son relevistas (dueño, 2026-08-13).

    POR QUÉ LA DISTINCIÓN. En un relevista el W-L es casi ruido: sus victorias suelen venir de
    salvamentos volados —entra perdiendo, el equipo remonta y se le apunta a él— así que ordenar
    cerradores por porcentaje premia una carambola. En un abridor sí mide algo, y por eso Pedro
    Martínez es 1º con .687 y Marichal 2º con .631.

    EL VALOR SE PINTA EN LOS DOS CASOS. Lo que desaparece en relevistas es el puesto, no la cifra: es
    suya y es cierta, simplemente no encabeza ninguna lista que valga la pena publicar.
    """
    for pid, pos, outs in ((1, "SP", 3200), (2, "RP", 1400)):
        jugador = _jugador(pid, f"J{pid}")
        jugador.pos = pos
        jugador.save(update_fields=["pos"])
        for anio in range(2010, 2020):
            _pitcheo(jugador, anio, outs=outs // 10, w=15, l=8, er=60)

    abridor = comparador.comparar(
        "pitching", (1, None), (1, None), comparador.MODO_CARRERA, oficio=comparador.OFICIO_ABRIDOR
    )
    relevista = comparador.comparar(
        "pitching", (2, None), (2, None), comparador.MODO_CARRERA, oficio=comparador.OFICIO_RELEVISTA
    )

    assert abridor["izquierda"]["celdas"]["win_pct"].rank == 1, "el abridor sí compite"
    celda = relevista["izquierda"]["celdas"]["win_pct"]
    assert celda.rank is None, "el relevista no"
    assert celda.valor is not None, "pero su cifra se sigue pintando"

    # Y las derrotas no llevan puesto en ninguno de los dos: quien quiera saber quién ganó más de lo
    # que perdió lo lee en PCT, que es la métrica que responde a eso.
    assert abridor["izquierda"]["celdas"]["l"].rank is None


@pytest.mark.django_db
def test_la_linea_de_temporadas_no_abrevia(catalogo: None) -> None:
    """«16 temporadas», no «16 temp.» — y en singular, «1 temporada» (dueño, 2026-08-13).

    En esa línea sobra sitio, así que la abreviatura solo hacía que la tarjeta pareciera apretada donde
    no lo está. El singular se escribe entero por lo mismo que el rótulo de «mejor temporada»: no basta
    con quitarle la ese, cambia la palabra.
    """
    from dglweb.stats import tarjeta

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    for anio in (2018, 2019, 2020):
        _bateo(otro, anio)

    foto = comparador.comparar("batting", (1, None), (2, None), comparador.MODO_CARRERA)
    imagen = tarjeta.png(foto)  # que dibuje sin reventar con las dos formas

    assert imagen[:4] == b"\x89PNG"
    assert foto["izquierda"]["temporadas"] == (2020,), "una sola -> «2020 · 1 temporada»"
    assert foto["derecha"]["temporadas"] == (2018, 2019, 2020), "tres -> el rango con la palabra entera"


@pytest.mark.django_db
def test_cada_temporada_se_mide_con_el_umbral_de_su_ano(catalogo: None) -> None:
    """En modo temporada, el umbral sale del año de CADA bolsa. Es el finding DEV-01 del review v23.

    EL FALLO: se resolvía una sola fórmula para todo, sacada del año que viniera primero en la ruta.
    Comparando 2020 contra 2021, la población entera se medía con el umbral de uno de los dos. Si
    mandaba 2020 —temporada de 60 juegos, umbral prorrateado— entraban a competir temporadas normales
    que no calificaban; si mandaba 2021, quedaban fuera temporadas de 2020 que sí.

    NI ROMPÍA LA PÁGINA NI SE VEÍA RARO. Solo cambiaba quién compite por el puesto, y un ranking
    plausible pero mal calificado es peor que un error visible: nadie lo va a dudar.

    Importa por 1981, 1994 y 2020, que son las temporadas cortas de la historia.
    """
    corta, larga = _jugador(1, "Corta"), _jugador(2, "Larga")
    _bateo(corta, 2020, pa=250, ab=230, avg=0.350)  # media temporada del confinamiento
    _bateo(larga, 2021, avg=0.300)

    # El orden de los años en la ruta no puede cambiar el resultado: son la misma comparación.
    uno = comparador.comparar("batting", (1, 2020), (2, 2021), comparador.MODO_TEMPORADA)
    otro = comparador.comparar("batting", (2, 2021), (1, 2020), comparador.MODO_TEMPORADA)

    assert uno["izquierda"]["celdas"]["avg"].rank == otro["derecha"]["celdas"]["avg"].rank
    assert uno["derecha"]["celdas"]["avg"].rank == otro["izquierda"]["celdas"]["avg"].rank
    assert uno["izquierda"]["celdas"]["avg"].de == otro["izquierda"]["celdas"]["avg"].de, (
        "y la población contra la que se rankea tampoco depende del orden"
    )
