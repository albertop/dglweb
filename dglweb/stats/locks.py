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

# El candado del REFRESCO COMPLETO, distinto del de los derivados. Ver `refresco_exclusivo`.
CLAVE_REFRESCO = 8412026

# EL MOTIVO DEL SALTO, y vive acá y no en el comando porque lo miran TRES sitios: el comando que lo
# escribe, el log, y `/health/pipeline`, que necesita reconocer esas filas para no confundirlas con
# una corrida de verdad. Estaba en el comando, y que el semáforo tuviera que importar de
# `management/commands/` para hacer su trabajo era la señal de que estaba en el sitio equivocado.
MOTIVO_OCUPADO = "ya hay un refresco corriendo; este se omite para no mezclar los dos"


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


@contextmanager
def refresco_exclusivo(clave: int = CLAVE_REFRESCO) -> Iterator[bool]:
    """Intenta tomar el candado del refresco completo. NO espera: devuelve `False` si ya hay uno.

    QA-01 DEL REVIEW v13, Y EL FALLO ERA REAL
    -----------------------------------------
    `_estado_de()` busca «la fila más reciente de este comando desde que empecé», no SU fila. Con dos
    refrescos solapados —el scheduler corriendo cuando alguien lanza un retry a mano, o una corrida que
    se pasa de su ventana— los dos ejecutan `update_batting` y el primero puede leer la fila del
    segundo.

    Comprobado escribiendo las dos filas a mano: la corrida A dejó `PARTIAL — faltaron 3 equipos` y
    `_estado_de` le contestó `SUCCESS — completo`, que era de B. Un `PARTIAL` leído como `SUCCESS`
    hace que una corrida publique derivados con un insumo incompleto.

    POR QUÉ `try` Y NO ESPERAR. Un candado que espera convertiría el retry manual en una segunda
    corrida completa encolada, que arrancaría justo cuando la primera acabó de publicar — trabajo
    duplicado sobre datos que ya están. Y con el scheduler cada hora, una corrida lenta iría acumulando
    cola hasta solaparse igual. Rechazar y decirlo es lo correcto: el refresco de mañana lo arregla.

    LO QUE ESTO NO CUBRE, y queda anotado en `docs/TODO.md`: el candado impide dos refrescos, pero no
    que alguien corra `manage.py update_batting` suelto mientras el refresco va. En ese caso
    `_estado_de` puede seguir leyendo la fila ajena. El arreglo de fondo es que cada `IngestRun` lleve
    el identificador de su corrida padre y que `_estado_de` resuelva por esa identidad y no por una
    ventana temporal — el tiempo aproxima causalidad, pero no la representa. Eso pide una migración y
    tocar cómo cada comando registra su fila, así que va aparte.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [clave])
        fila = cursor.fetchone()
        tomado = bool(fila and fila[0])
    try:
        yield tomado
    finally:
        # Solo se suelta si se tomó: soltar un candado que no se tiene deja un aviso en el log de
        # Postgres y, peor, sueltaría el de la corrida que sí lo tiene.
        if tomado:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [clave])
