"""Rehacer la data derivada sin bloquear a quien disparó el cambio.

Hay dos tablas que no son datos sino RESULTADOS: los totales de carrera y los liderazgos. No se
consultan en vivo — se construyen enteras y el sitio solo las lee. Eso las hace rápidas y las vuelve
mentirosas en cuanto cambia algo debajo: cargar hits de apoyo, dar de baja a un jugador.

Este módulo es el punto único desde donde se vuelven a construir. Vive aparte de `staticdata.engine`
porque ya tiene dos clientes que no se conocen entre sí, y aparte de `players` porque importar el
motor de líderes desde el modelo de jugadores sería un ciclo.
"""

import threading
from collections.abc import Sequence

from django.db import connections

# Lo derivado, en orden de dependencia: los liderazgos de por vida leen los totales de carrera.
DERIVED = ("build_career_totals", "build_leaders")


def run(names: Sequence[str]) -> None:
    """Corre los comandos en orden. Cada uno se registra solo en `IngestRun` (vía `record_run`).

    Pensado para correr en un hilo, así que cierra sus conexiones al salir — pero solo las suyas: ver
    el `finally`.
    """
    from django.core.management import call_command

    try:
        for nombre in names:
            # `force=True` a propósito. Estos comandos tienen puerta de temporada porque como job
            # DIARIO no tienen nada que hacer en invierno, pero acá no los despierta el reloj: los
            # dispara una persona que acaba de cargar datos o de dar de baja a un jugador. Y el dato
            # histórico se carga justamente fuera de temporada, así que sin esto la carga entraría y
            # los liderazgos seguirían viejos hasta marzo — el bug que ARCH-01 vino a matar.
            call_command(nombre, force=True)  # lo que imprima va al log del servidor
    finally:
        # Solo si corremos en un hilo propio. El hilo abre sus conexiones y nadie las va a cerrar por
        # él, así que sin esto cada carga deja una colgada en Postgres. Pero en el hilo principal las
        # conexiones son de OTRO —del request, o del test— y cerrarlas le rompe la transacción a
        # quien nos llamó: cerrar lo que uno no abrió nunca es correcto.
        if threading.current_thread() is not threading.main_thread():
            connections.close_all()


def run_in_background(names: Sequence[str]) -> str:
    """Lanza `run` en un hilo y devuelve enseguida. El texto es lo que se le muestra al usuario.

    Sin hilo, la respuesta HTTP esperaría el minuto y pico que tarda `build_leaders` — justo el tipo
    de request que un proxy corta a los 30 segundos, y cortarla no detiene el trabajo, solo deja al
    usuario sin saber cómo terminó.

    Es un hilo suelto y no una cola: este proyecto no tiene worker, estos cambios los dispara una
    persona que está mirando, y si el proceso se reinicia a mitad la red de seguridad ya existe (el
    cron reconstruye todas las mañanas). Lo que no puede pasar —y era lo que pasaba— es que no se
    reconstruya nunca porque nadie se acordó.
    """
    if not names:
        return ""
    threading.Thread(target=run, args=(names,), name=f"rebuild:{'+'.join(names)}", daemon=True).start()
    return ", ".join(names)
