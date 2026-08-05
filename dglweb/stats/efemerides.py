"""«Un día como hoy»: las efemérides del calendario, listas para el widget de portada.

Acá no se redacta nada. El texto viene YA ESCRITO en `dgl_efemerides`, que produce una vez al año
`static_data/efemerides/exportar_efemerides.ps1`; el diseño completo está en `docs/EFEMERIDES.md`.
Este módulo solo elige cuáles del día caben en pantalla, las empareja y calcula cuánto tiempo se
queda cada par a la vista.

POR QUÉ LOS CUMPLEAÑOS ENTRAN ACÁ Y NO EN EL PERFIL. En el tab del jugador se excluyen a propósito
—«Cumple 70 años» es una afirmación sobre HOY y en una lista cronológica quedaría fechada en el año
de nacimiento, contradiciéndose sola. En la portada es al revés: el widget ES el día de hoy, y sin
ellos la mitad del año se queda en blanco. Medido sobre las 5.802 filas:

    con cumpleaños     358 días con algo, mediana 17 por día
    sin cumpleaños     228 días con algo — o sea 137 días del año con el widget vacío

El 25 de diciembre hay exactamente tres efemérides y las tres son cumpleaños. El invierno lo cargan
ellos enteros.

NO HAY CACHÉ, Y ES DELIBERADO. La pizarra sí la tiene porque cada visita suya se convertía en una
llamada al proxy de MLB; esto son dos consultas locales que devuelven ocho filas por el índice
`idx_efemeride_dia` (`mes`, `dia`, `-puntaje`). Cachearlo no ahorraría nada medible y añadiría el
problema de que el dueño recargue el CSV y la portada siga enseñando lo de antes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.utils import timezone

from dglweb.players.models import Player
from dglweb.stats.models import Efemeride

# CUÁNTAS SE ENSEÑAN AL DÍA. Decisión del dueño (2026-08-04): dieciséis. Con mediana de 17 al día,
# eso es casi todo lo que hay un día normal — y con las flechas de «Anterior» y «Próximo» ya no hace
# falta que quepan en una vuelta, porque quien quiera verlas todas las adelanta.
#
# EN ESCRITORIO SON OCHO PANTALLAS Y EN MÓVIL DIECISÉIS, porque el ancho manda: dos tarjetas caben
# en el `.container` y en un teléfono solo cabe una. Una vuelta entera anda por los dos minutos y
# medio en escritorio y por los cuatro en móvil; nadie la ve completa, y esa es justamente la razón
# de que los controles existan.
TOPE = 16

# Cuántas se piden a la base antes de descartar a los deshabilitados. El margen es para que un
# jugador dado de baja en el Backoffice no deje el widget corto.
_MARGEN = 3

# EL RITMO DE LA ROTACIÓN, en caracteres por segundo. ESTOS TRES NÚMEROS SON EL WIDGET: si rota
# rápido no se lee, y si rota lento parece colgado.
#
# Empezó en 28 c/s pensando en velocidad de OJEADA y el dueño lo paró en seco: «está rotando muy
# rápido, no hay forma de leerlo». El error fue contar como si hubiera un texto; hay DOS tarjetas y
# entre una y otra el ojo tiene que saltar y volver a agarrar el hilo. Con la mediana de 105
# caracteres por tarjeta, aquello daba 8,6 segundos para leer dos efemérides completas.
#
# 12 c/s es paso de lectura de verdad, con el salto entre tarjetas ya pagado. Sobre el archivo real:
#
#     una tarjeta de la mediana (unos 120 caracteres)     el suelo, 10 s
#     dos tarjetas de la mediana (unos 240)               20 s
#     dos del percentil 90 (unos 420)                     el techo, 24 s
#
# CADA TARJETA LLEVA SU CUENTA CRUDA Y SIN TOPAR, porque cuántas se ven a la vez no lo sabe el
# servidor: en escritorio son dos y en un teléfono una. Quien suma las visibles y aplica el suelo y
# el techo es `dia_como_hoy.js`, que sí sabe el ancho — y los dos topes viajan en el HTML para que
# el número siga viviendo acá, donde se puede probar.
_RITMO = 12.0
_MINIMO = 10.0
_MAXIMO = 24.0


@dataclass(frozen=True)
class Tarjeta:
    """Una efeméride lista para pintar. Solo lo que la plantilla necesita, nada más."""

    player: Player
    # De `dglMaster.nameList`, que es la autoridad de nombres del sitio (ver `docs/AUTORIDAD.md`).
    # NO se usa `player.full_name`: el archivo ya trae el nombre con el que hay que nombrarlo.
    nombre: str
    anio: int
    titular: str
    situacion: str
    # `signo < 0`. La deshonra se marca para que el CSS la distinga sin que la plantilla tenga que
    # saber qué tipos son deshonras.
    negativa: bool
    # Lo que cuesta leer ESTA tarjeta, en milisegundos y SIN topar. El suelo y el techo se aplican a
    # lo que se ve a la vez, que son dos tarjetas o una según el ancho — y eso el servidor no lo
    # sabe. Ver `_ms()`.
    ms: int


def del_dia(hoy: date | None = None) -> dict[str, Any] | None:
    """Las tarjetas del día, o `None` si no hay ninguna.

    `None` y no una lista vacía: la plantilla esconde el widget entero. Ocho días del año no tienen
    nada —el 29 de febrero y siete de invierno— y un panel con el título puesto y el cuerpo hueco se
    lee como un sitio roto.

    `hoy` es para las pruebas y para poder mirar un día concreto; en producción no se pasa.
    """
    dia = hoy or timezone.localdate()

    filas = list(
        Efemeride.objects.filter(mes=dia.month, dia=dia.day).order_by("-puntaje")[: TOPE + _MARGEN]
    )
    if not filas:
        return None

    # LOS DESHABILITADOS NO SALEN, y hay que quitarlos acá y no en la plantilla. `Player.objects`
    # ya filtra `hidden=False` (ver `players/models.py`), así que al que está de baja no se le
    # encuentra el perfil — y una tarjeta que lo nombra sin poder enlazarlo lo publica igual.
    # Es la regla que cubre `tests/test_visibilidad_widgets.py` para los otros widgets.
    perfiles = Player.objects.in_bulk([fila.mlb_id for fila in filas], field_name="player_id")

    tarjetas = [
        Tarjeta(
            player=perfiles[fila.mlb_id],
            nombre=fila.nombre,
            anio=fila.temporada,
            titular=fila.titular,
            situacion=fila.situacion,
            negativa=fila.signo < 0,
            ms=_ms(fila),
        )
        for fila in filas
        if fila.mlb_id in perfiles
    ][:TOPE]

    if not tarjetas:
        return None

    return {
        "fecha": dia,
        "tarjetas": tarjetas,
        # Los topes de la ventana, para que el JavaScript los aplique después de sumar lo que se ve.
        # Viajan en el HTML en vez de estar escritos en el `.js` para que el número siga viviendo en
        # este módulo, que es donde hay pruebas que lo miran.
        "minimo_ms": round(_MINIMO * 1000),
        "maximo_ms": round(_MAXIMO * 1000),
    }


def _ms(fila: Efemeride) -> int:
    """Lo que cuesta leer esta tarjeta, en milisegundos y sin topar.

    Un tiempo fijo trata igual «Cumple 70 años.» —quince caracteres— y una entrada de doscientos
    cincuenta: o el corto se eterniza o el largo se va antes de terminarlo.

    SIN SUELO NI TECHO ACÁ, y esa es la parte que cambió al meter el móvil. El suelo y el techo son
    de la VENTANA —lo que se ve de una vez— y la ventana mide dos tarjetas en escritorio y una en un
    teléfono. Toparlas una por una haría que dos cumpleaños seguidos costaran veinte segundos en
    escritorio, cuando entre los dos no llegan a cuarenta caracteres.

    EN MILISEGUNDOS ENTEROS Y NO EN SEGUNDOS CON DECIMAL. Django localiza los números al pintarlos y
    en español el decimal es una coma, así que el atributo salía `data-ms="8,6"` — y
    `parseFloat("8,6")` en JavaScript devuelve **8**, recortando en silencio.
    """
    letras = len(fila.titular) + len(fila.situacion) + len(fila.nombre)
    return round(letras / _RITMO * 1000)
