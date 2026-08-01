"""Qué jobs vigila el semáforo, y qué se considera «sano» en cada uno.

POR QUÉ ESTE MÓDULO EXISTE
--------------------------
La lista vivía en `core/views.py` y el calendario en `ofelia/config.ini`, y las dos crecían por su
cuenta. Cuando entró el job horario de destacados, el calendario pasó a tener tres jobs por hora y la
lista vigilada se quedó con dos — y ninguna prueba lo vio, porque las pruebas se parametrizaban desde
la misma lista incompleta que usaba producción. Un módulo vivo de la portada podía romperse durante
horas con el monitor en verde (DEV-01/QA-01 del review v10).

`tests/test_pipeline_health.py` lee ahora `ofelia/config.ini` de verdad y exige que todo job horario
esté acá o en `SIN_VIGILAR`. Esa prueba es la mitad importante de este archivo: sin ella esto no es
una fuente única de verdad, es una segunda lista.

Y POR QUÉ NO ES SOLO UNA TUPLA DE NOMBRES
------------------------------------------
Porque «sano» no significa lo mismo en los tres. Añadir `build_daily_standouts` a la lista vieja
—que exigía `SUCCESS`— habría puesto el semáforo **en rojo de las 4 de la mañana a las 5 de la tarde,
todos los días**: ese job anota `SKIPPED` legítimamente mientras no haya cerrado ningún juego, que en
horario dominicano es casi todo el día. Un monitor que grita a diario es un monitor que se apaga.

El módulo no vive en `core/views.py` ni en el comando: lo leen los dos, y ponerlo en cualquiera de
ellos obligaría al otro a importar de un sitio que no le toca. No importa nada de Django a propósito,
así que se puede leer desde donde sea sin arrastrar la app entera.
"""

from typing import NamedTuple

# El sufijo que marca una corrida del job HORARIO en el `scope` del log de ingesta.
#
# Hace falta porque `build_daily_standouts` corre en dos modos con el mismo nombre de comando: el
# refresco de las 4:30 guarda la jornada de ayer, y el job horario va guardando la de hoy según
# terminan los juegos. Sin distinguirlos, el éxito del refresco diario taparía tres horas de fallos
# del horario cada mañana — el job vigilado parecería fresco por el trabajo de otro (ARCH-01 del v10).
ALCANCE_EN_CURSO = "en curso"


class Vigilado(NamedTuple):
    """Un job horario y el contrato con el que se le mira.

    `alcance` es un sufijo del `scope`; vacío significa «cualquier corrida de ese comando».
    `sanos` son los estados de `IngestRun.Status` que cuentan como una corrida buena — van como texto
    para que este módulo no tenga que importar los modelos, y `test_pipeline_health` comprueba que
    todos existan de verdad.
    """

    comando: str
    alcance: str = ""
    sanos: tuple[str, ...] = ("success",)


HORARIOS = (
    Vigilado("build_mlb_leaders"),
    Vigilado("update_roster_moves"),
    # `SKIPPED` cuenta como sano acá y en ningún otro: «ningún juego ha terminado todavía» es la
    # respuesta CORRECTA a media mañana, no una avería. Lo que sí es avería —no poder preguntarle a
    # la pizarra qué terminó— el comando lo registra como fallo justamente para que este renglón no
    # se lo trague. Ver `build_daily_standouts`.
    Vigilado("build_daily_standouts", alcance=ALCANCE_EN_CURSO, sanos=("success", "skipped")),
    # Exige `SUCCESS` a secas, al revés que el de arriba. Este no tiene un caso legítimo de salto
    # dentro de temporada: pregunta por una ventana de catorce días, así que siempre hay algo que
    # contestar aunque hoy no se haya jugado. Un `skipped` acá sí es una avería.
    Vigilado("build_window_standouts"),
)

# Los jobs horarios que a propósito NO se vigilan, con el motivo. Existe para que la prueba que lee
# el calendario pueda distinguir «se decidió no vigilarlo» de «se olvidó», que es la diferencia que
# hizo falta desde el principio.
SIN_VIGILAR: dict[str, str] = {}
