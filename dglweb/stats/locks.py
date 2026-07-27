"""El candado de los rebuilds derivados.

QUÉ PROTEGE
-----------
`build_career_totals` y `build_leaders` no son consultas: **borran su tabla entera y la reescriben**.
Dos procesos haciendo eso a la vez intercalan borrados e inserciones, y lo que queda no es ninguno de
los dos resultados.

Y son una CADENA: los liderazgos de por vida leen los totales de carrera. Aunque cada comando fuera
atómico por separado, dos cadenas entrelazadas dejan liderazgos calculados sobre unos totales que ya
no existen — `A:carrera`, `B:carrera`, `A:líderes` publica líderes de la foto de B.

Dejó de ser teórico cuando cargar datos de apoyo pasó a disparar los rebuilds: desde entonces el
Backoffice y el refresco diario pueden reconstruir a la vez.

CÓMO
----
Una sola clave, tomada en dos niveles:

* **De sesión** (`cadena_derivada`) por quien corre la cadena completa — el orquestador y el hilo del
  Backoffice. Cubre los dos comandos y no se suelta entre uno y otro.
* **De transacción** (`tomar_en_transaccion`) dentro de cada comando, para cuando alguien lo corre
  suelto desde `manage.py`.

Los dos niveles usan la MISMA clave a propósito. Los advisory locks de Postgres son reentrantes
dentro de una sesión: el comando vuelve a pedir la clave que su propia cadena ya tiene y sigue de
largo, mientras que otra sesión espera. Con dos claves distintas habría que razonar sobre el orden en
que se toman, que es de donde salen los abrazos mortales.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection

# Arbitraria pero estable. No se cambia sin mirar quién más la usa: dos claves distintas es lo mismo
# que no tener candado.
CLAVE_DERIVADOS = 8412025


def tomar_en_transaccion(clave: int = CLAVE_DERIVADOS) -> None:
    """Toma la clave hasta que la transacción actual termine. Debe llamarse DENTRO de un `atomic()`.

    Se suelta sola al hacer commit o rollback, que es justo lo que se quiere en un comando: si
    revienta a mitad, nadie hereda un candado colgado.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [clave])


@contextmanager
def cadena_derivada(clave: int = CLAVE_DERIVADOS) -> Iterator[None]:
    """Toma la clave para toda la cadena y la suelta al salir, pase lo que pase.

    De sesión y no de transacción porque tiene que sobrevivir a los `atomic()` de los dos comandos:
    uno hace commit y suelta lo suyo, y la cadena sigue protegida hasta que termina el segundo.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [clave])
    try:
        yield
    finally:
        # En el `finally` sin excepción posible: un candado de sesión que no se suelta se queda
        # tomado mientras viva la conexión, y la siguiente cadena esperaría para siempre.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [clave])
