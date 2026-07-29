"""Las conexiones persistentes a Postgres, y sobre todo que se curen solas.

POR QUÉ EXISTE ESTE ARCHIVO
---------------------------
Medido en producción el 2026-07-29: abrir una conexión a Postgres cuesta **32,9 ms**, de los cuales
solo 2 son red (0,8 resolver el nombre + 1,2 abrir el socket). El resto es `scram-sha-256` derivando
la clave con 4.096 iteraciones a los dos lados y Postgres bifurcando un proceso nuevo por conexión.
Con el valor de fábrica —`CONN_MAX_AGE = 0`— eso se pagaba en CADA petición.

`CONN_MAX_AGE` sin `CONN_HEALTH_CHECKS` cambia un problema de velocidad por uno de caídas: la
conexión guardada sobrevive en Django pero no en Postgres —un reinicio de la base, un despliegue del
stack— y el visitante se lleva un 500 cuando alguien la usa.

Y el ajuste que lo evita **es por base de datos, no global**. Escrito suelto en el módulo de
settings, Django lo ignora EN SILENCIO: no hay aviso, no hay error de configuración, y
`settings.CONN_HEALTH_CHECKS` devuelve `True` tan tranquilo. Así estuvo escrito primero, y solo se
descubrió matando una conexión a propósito desde el servidor.

POR QUÉ SE MIRA `config.settings.base` Y NO `django.conf.settings`
------------------------------------------------------------------
`config/settings/test.py` REEMPLAZA `DATABASES` con un diccionario literal —a propósito, para que la
suite no pueda apuntar sin querer a la base real— así que en los tests `settings.DATABASES` son los
de la suite, no los de producción. Un assert contra `django.conf.settings` no estaría comprobando lo
que se despliega.

El módulo `config.settings.base` sí conserva su propio diccionario, con los valores que van a
producción. Ahí es donde hay que mirar.

Y la suite NO usa conexiones persistentes, ni debe: `pytest-django` crea y destruye una base
`test_…` en cada corrida, y una conexión viva de más es lo que hace que un `DROP DATABASE` falle con
«is being accessed by other users». La tercera prueba activa el comportamiento solo para ella y lo
deja como estaba.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from django.conf import settings
from django.db import close_old_connections, connection

from config.settings import base

PRODUCCION = base.DATABASES["default"]


def test_las_conexiones_se_guardan_entre_peticiones() -> None:
    """`CONN_MAX_AGE` tiene que ser > 0, o se pagan 33 ms por petición."""
    assert PRODUCCION.get("CONN_MAX_AGE"), (
        "CONN_MAX_AGE está en 0 o falta: cada petición vuelve a presentarse ante una base que está "
        "en el mismo servidor, y eso son 33 ms medidos en producción."
    )


def test_la_comprobacion_de_salud_esta_dentro_de_databases() -> None:
    """Es la prueba que atrapa el fallo real, y por eso mira DENTRO del diccionario.

    Un `CONN_HEALTH_CHECKS = True` a nivel de módulo deja `settings.CONN_HEALTH_CHECKS` valiendo
    `True` mientras Django usa su defecto, que es `False`. Se ve bien, no se queja nadie, y el fallo
    aparece el día que Postgres se reinicie.
    """
    assert PRODUCCION.get("CONN_HEALTH_CHECKS"), (
        "CONN_HEALTH_CHECKS no está dentro de DATABASES['default']. Con conexiones persistentes y "
        "sin esto, el primer visitante después de un reinicio de Postgres se lleva un 500."
    )
    assert not hasattr(base, "CONN_HEALTH_CHECKS"), (
        "hay un CONN_HEALTH_CHECKS suelto en el módulo. Django NO lo lee de ahí: lo ignora en "
        "silencio y deja creer que la protección está puesta."
    )


@pytest.fixture
def con_conexiones_persistentes() -> Iterator[None]:
    """Enciende el comportamiento de producción solo durante una prueba.

    No vale con `override_settings`: lo que Django consulta es el `settings_dict` de la conexión ya
    construida. Y hay que reconectar DESPUÉS de cambiarlo, porque el momento de caducidad se calcula
    al abrir — una conexión nacida con `CONN_MAX_AGE = 0` ya nace caducada y `close_old_connections`
    la cerraría por vieja, no por rota, que es justo lo que la prueba no quiere medir.
    """
    antes = {clave: connection.settings_dict.get(clave) for clave in ("CONN_MAX_AGE", "CONN_HEALTH_CHECKS")}
    connection.settings_dict["CONN_MAX_AGE"] = 60
    connection.settings_dict["CONN_HEALTH_CHECKS"] = True
    connection.close()
    try:
        yield
    finally:
        connection.close()
        connection.settings_dict.update(antes)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("con_conexiones_persistentes")
def test_se_reconecta_sola_si_postgres_corta_la_conexion() -> None:
    """La prueba que importa: matar la conexión desde el SERVIDOR y pedir otra vez.

    Simula un reinicio de Postgres, que es cuando esto pasa de verdad. Sin la comprobación de salud
    la segunda consulta revienta con `OperationalError: terminating connection due to administrator
    command` — comprobado de verdad antes de arreglarlo, no supuesto.

    `transaction=True` porque hace falta una conexión real y no una envuelta en la transacción que
    `pytest-django` deshace: cerrar esa conexión a mitad dejaría el test inservible.
    """
    with connection.cursor() as cur:
        cur.execute("select pg_backend_pid()")
        fila = cur.fetchone()
        assert fila is not None
        pid_viejo = fila[0]

    # Entre peticiones Django llama a esto. Con CONN_MAX_AGE > 0 la conexión NO se cierra.
    close_old_connections()
    assert connection.connection is not None, "la conexión debería haber sobrevivido a la petición"

    # Postgres la mata desde fuera. Hace falta una segunda conexión: no se puede terminar el proceso
    # que estás usando para dar la orden.
    ajustes = settings.DATABASES["default"]
    verdugo = psycopg.connect(
        host=ajustes["HOST"],
        port=ajustes["PORT"] or 5432,
        dbname=connection.settings_dict["NAME"],
        user=ajustes["USER"],
        password=ajustes["PASSWORD"],
        autocommit=True,
    )
    try:
        verdugo.execute("select pg_terminate_backend(%s)", (pid_viejo,))
    finally:
        verdugo.close()

    # Y llega la siguiente petición. Esto es lo que decide entre servir la página y devolver un 500.
    close_old_connections()
    with connection.cursor() as cur:
        cur.execute("select pg_backend_pid()")
        fila = cur.fetchone()
        assert fila is not None
        pid_nuevo = fila[0]

    assert pid_nuevo != pid_viejo, (
        "el proceso debería ser otro: si es el mismo, la conexión no se recicló y la prueba no probó nada"
    )
