"""El candado de los rebuilds derivados.

Lo que se protege no es una tabla: es que `build_career_totals` y `build_leaders` se corran como una
sola cosa. Son una cadena —los liderazgos de por vida leen los totales de carrera— y dos cadenas
entrelazadas publican líderes calculados sobre unos totales que ya se reemplazaron.

Estos tests hablan con Postgres de verdad, con dos conexiones. Un candado que solo se prueba en
memoria no prueba nada: lo que se está afirmando es que el motor bloquea.
"""

import threading
import time

import pytest
from django.db import connection, connections, transaction

from dglweb.stats import locks


def _tomado_por_otra_sesion(espera: float) -> tuple[list[float], threading.Thread]:
    """Lanza una segunda conexión que pide la clave y anota cuánto tardó en conseguirla."""
    esperas: list[float] = []

    def pedir() -> None:
        conexion = connections.create_connection("default")
        inicio = time.monotonic()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [locks.CLAVE_DERIVADOS])
                esperas.append(time.monotonic() - inicio)
                cursor.execute("SELECT pg_advisory_unlock(%s)", [locks.CLAVE_DERIVADOS])
        finally:
            conexion.close()

    hilo = threading.Thread(target=pedir, daemon=True)
    hilo.start()
    time.sleep(espera)
    return esperas, hilo


@pytest.mark.django_db(transaction=True)
def test_a_second_chain_waits_for_the_first() -> None:
    """Lo único que este candado tiene que hacer, y la razón de que exista."""
    with locks.cadena_derivada():
        esperas, hilo = _tomado_por_otra_sesion(0.4)
        assert esperas == [], "la segunda sesión entró mientras la primera reconstruía"

    hilo.join(timeout=5)
    assert len(esperas) == 1, "la segunda sesión no entró al soltarse el candado"


@pytest.mark.django_db(transaction=True)
def test_the_commands_do_not_deadlock_inside_their_own_chain() -> None:
    """La cadena toma la clave y luego cada comando la vuelve a pedir. Tiene que pasar de largo.

    Es lo que permite usar UNA sola clave para los dos niveles: los advisory locks de Postgres son
    reentrantes dentro de una sesión. Con dos claves distintas habría que razonar sobre el orden en
    que se toman, que es de donde salen los abrazos mortales.
    """
    with locks.cadena_derivada(), transaction.atomic():
        locks.tomar_en_transaccion()  # si no fuera reentrante, esto colgaría el test


@pytest.mark.django_db(transaction=True)
def test_a_crash_mid_rebuild_does_not_leave_the_lock_held() -> None:
    """Un candado de sesión que no se suelta se queda tomado mientras viva la conexión.

    Sin el `finally`, un rebuild que reviente dejaría a todos los siguientes esperando para siempre —
    y el síntoma sería «los líderes no se actualizan», que no apunta a un candado.
    """
    with pytest.raises(RuntimeError), locks.cadena_derivada():
        raise RuntimeError("algo explotó a mitad del rebuild")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = %s",
            [locks.CLAVE_DERIVADOS],
        )
        fila = cursor.fetchone()
    assert fila[0] == 0


def test_both_halves_of_the_chain_share_the_key() -> None:
    """Dos claves distintas es exactamente lo mismo que no tener candado.

    No hace falta base: se lee el código. Es una prueba contra el descuido de que alguien, algún día,
    le dé a uno de los dos su propia clave «para que no se estorben» — que es justo lo que hay que
    evitar.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    for modulo in ("career_totals.py", "leaders.py"):
        fuente = (raiz / "dglweb" / "stats" / modulo).read_text(encoding="utf-8")
        assert "locks.tomar_en_transaccion()" in fuente, f"{modulo} dejó de tomar el candado compartido"
        assert "pg_advisory" not in fuente, f"{modulo} toma un candado por su cuenta, fuera de stats/locks.py"
