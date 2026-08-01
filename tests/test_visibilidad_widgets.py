"""Un jugador deshabilitado no puede salir en los widgets de la portada — QA-01 del review v11.

QUÉ SE ROMPÍA
-------------
`tests/test_player_visibility.py` ya cubría perfiles, buscador, listados, leaderboards y totales de
carrera. Faltaban las tres superficies que leen de **tablas derivadas** —destacados del día, líderes
MLB y cintillo de movimientos— y en las tres salía el jugador oculto. Comprobado ejecutando, antes de
arreglarlo.

Y no se curaba solo: ni `build_daily_standouts`, ni `build_mlb_leaders`, ni `update_roster_moves`
mencionaban `hidden` por ninguna parte, así que el siguiente refresco horario volvía a dejarlo ahí.

POR QUÉ IMPORTA MÁS DE LO QUE PARECE
-------------------------------------
El `help_text` del campo le promete al dueño «El jugador desaparece del sitio: perfil, búsqueda y
liderazgos». Un jugador se deshabilita por algo —una petición legal, un problema personal— y que
siguiera apareciendo en la portada es exactamente el fallo que esa función existe para evitar.

DÓNDE SE ARREGLÓ, Y POR QUÉ AHÍ
--------------------------------
Al **publicar**, no al ingerir. El dato crudo sigue entrando, así reactivar a un jugador es
instantáneo y no exige recalcular nada. Es la regla que ya estaba escrita en `players/visibility.py`.

Y en `daily.py` y `roster_moves.py` el filtro va sobre la consulta **compartida**, la que también
elige la FECHA de referencia. Filtrar solo las filas habría cambiado un fallo por otro: la fecha se
elegiría contando al jugador oculto y el widget saldría con el título de una jornada y el cuerpo
vacío.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.utils import timezone

from dglweb.players.models import Player
from dglweb.stats.models import DailyStandout, Metric, MlbLeader, RosterMove, WindowStandout


def _jugador(pid: int, *, oculto: bool) -> Player:
    """Se crea con `todos` y no con `objects`: el manager por defecto ya filtra a los ocultos."""
    return Player.todos.create(dgl_id=pid, player_id=pid, firstname="Prueba", lastname_1=str(pid), hidden=oculto)


def _destacado(jugador: Player, fecha: date | None = None) -> DailyStandout:
    return DailyStandout.objects.create(
        player=jugador,
        fecha=fecha or timezone.localdate(),
        grupo=DailyStandout.Grupo.BATEO,
        linea="4-4, 3 HR, 6 RBI",
        # Muy por encima del piso: la prueba tiene que fallar por la visibilidad, nunca por el umbral.
        valor=99,
        team="NYA",
    )


def _movimiento(jugador: Player, transaction_id: int) -> RosterMove:
    return RosterMove.objects.create(
        player=jugador,
        mlb_id=jugador.player_id,
        transaction_id=transaction_id,
        nombre=f"Prueba {jugador.player_id}",
        fecha=timezone.localdate(),
        type_code="TR",
        type_desc="Trade",
        descripcion="traded",
        texto=f"Prueba {jugador.player_id} fue cambiado a los Yankees",
    )


def _ids(estructura: object, hondo: int = 0) -> set[int]:
    """Todos los `player_id` que aparecen en la estructura, por hondo que estén.

    Recorrer en vez de mirar el `repr`: el `__repr__` de `Player` sale vacío y buscar el número en el
    texto daría un falso negativo — o sea, una prueba que pasa con el fallo puesto.
    """
    encontrados: set[int] = set()
    if hondo > 8:
        return encontrados
    pid = getattr(estructura, "player_id", None)
    if isinstance(pid, int):
        encontrados.add(pid)
    if isinstance(estructura, dict):
        for valor in estructura.values():
            encontrados |= _ids(valor, hondo + 1)
    elif isinstance(estructura, (list, tuple, set)):
        for valor in estructura:
            encontrados |= _ids(valor, hondo + 1)
    elif hasattr(estructura, "__dict__"):
        for valor in vars(estructura).values():
            encontrados |= _ids(valor, hondo + 1)
    return encontrados


@pytest.mark.django_db
def test_los_destacados_del_dia_no_ensenan_a_un_oculto() -> None:
    from dglweb.stats import daily

    visible = _jugador(910001, oculto=False)
    oculto = _jugador(910002, oculto=True)
    _destacado(visible)
    _destacado(oculto)

    salida = daily.portada()
    assert salida is not None, "con un jugador visible el widget tiene que salir"
    vistos = _ids(salida)
    assert 910001 in vistos, "el jugador visible tiene que seguir saliendo"
    assert 910002 not in vistos, "SALE UN JUGADOR DESHABILITADO en los destacados del día"


@pytest.mark.django_db
def test_si_el_unico_destacado_esta_oculto_el_widget_no_sale() -> None:
    """El caso que habría roto un arreglo a medias, y por eso tiene prueba propia.

    Si la fecha de referencia se eligiera contando al jugador oculto pero las filas lo excluyeran, el
    widget saldría con el título de una jornada y el cuerpo VACÍO. Tiene que no salir del todo.
    """
    from dglweb.stats import daily

    _destacado(_jugador(910003, oculto=True))

    assert daily.portada() is None, "la fecha se eligió contando a un oculto: widget con título y sin contenido"


@pytest.mark.django_db
def test_los_lideres_mlb_no_ensenan_a_un_oculto() -> None:
    from dglweb.stats import mlb_leaders

    metrica = Metric.objects.filter(visible_en_widget_lideres=True).first() or Metric.objects.create(
        stat_group="batting",
        column="hr",
        kind="ACU",
        abbrev="HR",
        name_es="Jonrones",
        sort_order=1,
        is_active=True,
        visible_en_widget_lideres=True,
    )
    visible = _jugador(910004, oculto=False)
    oculto = _jugador(910005, oculto=True)
    MlbLeader.objects.create(player=visible, metric=metrica, season=2026, rank=2, valor="30", team="NYA")
    MlbLeader.objects.create(player=oculto, metric=metrica, season=2026, rank=5, valor="27", team="BOS")

    vistos = _ids(mlb_leaders.portada())
    assert 910004 in vistos, "el jugador visible tiene que seguir saliendo"
    assert 910005 not in vistos, "SALE UN JUGADOR DESHABILITADO en los líderes de MLB"


@pytest.mark.django_db
def test_el_cintillo_no_ensena_a_un_oculto() -> None:
    from dglweb.stats import roster_moves

    visible = _jugador(910006, oculto=False)
    oculto = _jugador(910007, oculto=True)
    _movimiento(visible, transaction_id=910006)
    _movimiento(oculto, transaction_id=910007)

    salida = roster_moves.portada()
    vistos = _ids(salida)
    assert 910006 in vistos, "el jugador visible tiene que seguir saliendo"
    assert 910007 not in vistos, "SALE UN JUGADOR DESHABILITADO en el cintillo de movimientos"


@pytest.mark.django_db
def test_reactivar_a_un_jugador_lo_devuelve_sin_reconstruir_nada() -> None:
    """La otra mitad del contrato, y la razón de filtrar al leer y no al construir.

    Si el filtro estuviera en los constructores, volver a habilitar a alguien exigiría esperar al
    siguiente refresco horario. Filtrando al publicar, vuelve en la siguiente petición.
    """
    from dglweb.stats import roster_moves

    jugador = _jugador(910008, oculto=True)
    _movimiento(jugador, transaction_id=910008)
    assert 910008 not in _ids(roster_moves.portada())

    jugador.hidden = False
    jugador.save(update_fields=["hidden"])

    assert 910008 in _ids(roster_moves.portada()), "reactivar tiene que devolverlo de inmediato"


def _en_la_ventana(jugador: Player, valor: float = 99) -> WindowStandout:
    """Muy por encima del corte: la prueba tiene que fallar por la visibilidad, nunca por el umbral."""
    hoy = timezone.localdate()
    return WindowStandout.objects.create(
        player=jugador,
        desde=hoy - timedelta(days=13),
        hasta=hoy,
        grupo=WindowStandout.Grupo.BATEO,
        linea=".400, 6 HR, 14 RBI",
        valor=valor,
        juegos=12,
        oportunidades=45,
        team="NYA",
    )


@pytest.mark.django_db
def test_las_rachas_no_ensenan_a_un_oculto() -> None:
    """QA-01 del review v15. La ventana de catorce días es una superficie pública más, y se escribió
    copiando el patrón de `daily` sin copiar su filtro de visibilidad."""
    from dglweb.stats import ventana

    visible = _jugador(910101, oculto=False)
    oculto = _jugador(910102, oculto=True)
    _en_la_ventana(visible)
    _en_la_ventana(oculto)

    salida = ventana.portada()
    assert salida is not None, "con un jugador visible el widget tiene que salir"
    vistos = _ids(salida)
    assert 910101 in vistos, "el jugador visible tiene que seguir saliendo"
    assert 910102 not in vistos, "SALE UN JUGADOR DESHABILITADO en «Quemando la liga»"


@pytest.mark.django_db
def test_si_el_unico_de_la_racha_esta_oculto_el_widget_no_sale() -> None:
    """El panel entero desaparece, no queda con el título y el cuerpo vacío."""
    from dglweb.stats import ventana

    _en_la_ventana(_jugador(910103, oculto=True))

    assert ventana.portada() is None, "widget con título y sin contenido"


@pytest.mark.django_db
def test_el_oculto_tampoco_sale_por_la_punta_de_abajo() -> None:
    """«Pasando trabajo» lee la MISMA consulta, pero por el otro extremo. Un arreglo que solo mirara
    el orden descendente dejaría al oculto saliendo en el panel de abajo."""
    from dglweb.stats import ventana

    visible = _jugador(910104, oculto=False)
    oculto = _jugador(910105, oculto=True)
    _en_la_ventana(visible, valor=-99)
    _en_la_ventana(oculto, valor=-99)

    salida = ventana.portada()
    assert salida is not None
    vistos = _ids(salida["pasando"])
    assert 910104 in vistos
    assert 910105 not in vistos, "SALE UN JUGADOR DESHABILITADO en «Pasando trabajo»"
