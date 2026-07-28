"""El `stderr` limpio, y por qué eso es una prueba y no una manía.

`refresh_daily` avisa de sus fallos por `stderr`. Ese canal solo sirve si lo que sale por ahí es
excepcional: cuando cada corrida escribe cuatro líneas de aviso que no significan nada, nadie las
lee, y el día que aparezca un error de verdad va a estar mezclado con el ruido en el mismo bloque
del log. Ya nos pasó con las alertas de Telegram.

De ahí `SILENCED_SYSTEM_CHECKS` en los ajustes, con su explicación al lado. Esta prueba es la otra
mitad: vigila que el canal siga limpio, así que se cae cuando aparezca un aviso NUEVO —de Django, de
Wagtail o nuestro—, que es exactamente cuando alguien tiene que mirarlo y decidir.
"""

import io
import re

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_los_chequeos_del_sistema_no_escriben_avisos() -> None:
    """Si esto se cae, hay un aviso nuevo. La respuesta correcta NO es añadirlo a la lista de
    silenciados sin más: es leerlo, decidir si es nuestro —entonces se arregla— o de una librería
    —entonces se silencia CON su porqué y con qué se está aplazando, como el de treebeard."""
    salida = io.StringIO()
    call_command("check", stdout=salida, stderr=salida)

    # El resumen final se quita con expresión regular y no con un `replace` de la frase exacta: lleva
    # dentro cuántos avisos se silenciaron —«(4 silenced)»— y ese número cambia solo. Clavarlo haría
    # que la prueba se cayera por una razón que no tiene nada que ver con lo que vigila.
    limpio = re.sub(r"System check identified no issues \(\d+ silenced\)\.", "", salida.getvalue()).strip()
    assert not limpio, f"chequeos del sistema con avisos:\n{limpio}"
