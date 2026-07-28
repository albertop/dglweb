"""Rehacer la data derivada sin bloquear a quien disparó el cambio.

Hay dos tablas que no son datos sino RESULTADOS: los totales de carrera y los liderazgos. No se
consultan en vivo — se construyen enteras y el sitio solo las lee. Eso las hace rápidas y las vuelve
mentirosas en cuanto cambia algo debajo: cargar hits de apoyo, dar de baja a un jugador.

Este módulo es el punto único desde donde se vuelven a construir. Vive aparte de `staticdata.engine`
porque ya tiene dos clientes que no se conocen entre sí, y aparte de `players` porque importar el
motor de líderes desde el modelo de jugadores sería un ciclo.
"""

import logging
import threading
from collections.abc import Sequence

from django.db import connections
from django.utils import timezone

from dglweb.stats import locks

logger = logging.getLogger(__name__)

# Lo derivado, en orden de dependencia: los liderazgos de por vida leen los totales de carrera.
DERIVED = ("build_career_totals", "build_leaders")


PADRE = "rebuild_derivados"


def anotar_lanzamiento(names: Sequence[str]) -> int | None:
    """Deja constancia de que el rebuild se va a lanzar, ANTES de lanzarlo. Devuelve el id de la fila.

    QA-02 del review v6. El rebuild corre en un hilo suelto —no hay worker, y sostener la respuesta
    HTTP un minuto es pedirle al proxy que la corte— y cada comando se registra solo al arrancar. Eso
    deja una ventana de milisegundos con consecuencias feas: **si el hilo muere antes de que el
    primer comando cree su fila, la carga queda aplicada sin ninguna evidencia de su rebuild**, y eso
    es indistinguible de «nunca se lanzó».

    No es teórico en este proyecto: ya pasó con el scheduler, donde 27 corridas fallidas dejaron el
    log limpio porque ninguna llegó a arrancar. Un canal de auditoría que solo registra lo que
    empieza no sirve para investigar lo que no empezó.

    La fila padre se crea en el hilo de la petición, así que si se escribe, se escribió. La cierra
    `run` al terminar; si nadie la cierra, se queda en RUNNING — y una corrida en RUNNING de hace
    horas es exactamente la señal que faltaba.
    """
    from dglweb.stats.models import IngestRun

    if not names:
        return None
    fila = IngestRun.objects.create(
        command=PADRE,
        scope="+".join(names),
        status=IngestRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    return int(fila.pk)


def _cerrar_padre(padre: int | None, error: BaseException | None) -> None:
    """Cierra la fila de `anotar_lanzamiento`. Nunca levanta: es contabilidad, no el trabajo."""
    if padre is None:
        return
    from dglweb.stats.models import IngestRun

    try:
        IngestRun.objects.filter(pk=padre).update(
            status=IngestRun.Status.FAILED if error else IngestRun.Status.SUCCESS,
            detail=f"{type(error).__name__}: {error}"[:500] if error else "",
            finished_at=timezone.now(),
        )
    # Se atrapa todo: si falla el registro, el rebuild ya se hizo y eso importa más que la anotación.
    except Exception:
        logger.exception("No se pudo cerrar la fila padre del rebuild %s", padre)


def run(names: Sequence[str], padre: int | None = None) -> None:
    """Corre los comandos en orden. Cada uno se registra solo en `IngestRun` (vía `record_run`).

    Pensado para correr en un hilo, así que cierra sus conexiones al salir — pero solo las suyas: ver
    el `finally`.
    """
    from django.core.management import call_command

    fallo: BaseException | None = None
    try:
        # Toda la cadena bajo un candado, no cada comando por su cuenta: los liderazgos de por vida
        # leen los totales de carrera, así que dos cadenas entrelazadas publican líderes calculados
        # sobre unos totales que ya se reemplazaron. Ver `stats/locks.py`.
        with locks.cadena_derivada():
            for nombre in names:
                # `force=True` a propósito. Estos comandos tienen puerta de temporada porque como job
                # DIARIO no tienen nada que hacer en invierno, pero acá no los despierta el reloj:
                # los dispara una persona que acaba de cargar datos o de dar de baja a un jugador. Y
                # el dato histórico se carga justamente fuera de temporada, así que sin esto la carga
                # entraría y los liderazgos seguirían viejos hasta marzo — el bug que ARCH-01 vino a
                # matar.
                call_command(nombre, force=True)  # lo que imprima va al log del servidor
    except BaseException as error:
        fallo = error
        raise
    finally:
        _cerrar_padre(padre, fallo)
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
    # La constancia se deja ANTES de lanzar el hilo, en el hilo de la petición. Ver
    # `anotar_lanzamiento`: es lo que distingue «el rebuild murió» de «nadie lo lanzó».
    padre = anotar_lanzamiento(names)
    threading.Thread(target=run, args=(names, padre), name=f"rebuild:{'+'.join(names)}", daemon=True).start()
    return ", ".join(names)
