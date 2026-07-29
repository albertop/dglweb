"""Las cabeceras de seguridad que solo existen en producción.

POR QUÉ NO SE PRUEBAN CON `settings.` A SECAS
----------------------------------------------
La suite corre con `config.settings.test`, que hereda de `dev`. Ahí la HSTS está apagada a propósito
—encenderla en desarrollo dejaría `localhost` clavado en HTTPS en el navegador del que la corra— así
que un assert contra `django.conf.settings` estaría comprobando justo lo contrario de lo que se
despliega.

Por eso se importa `config.settings.prod` a mano, con las variables de entorno que exige. Es feo,
pero es la única forma de que estas pruebas hablen de producción.

QUÉ SE PROTEGE Y POR QUÉ ESTAS TRES
------------------------------------
`SECURE_HSTS_PRELOAD` es **el ajuste sin vuelta atrás del proyecto**. Encenderlo no cambia una
cabecera: es el requisito para inscribir el dominio en una lista que viene COMPILADA dentro de
Chrome, Firefox y Safari. Salir de ahí tarda meses y depende de que otros publiquen versiones nuevas
del navegador. Nadie debería encenderlo sin decidirlo a conciencia, y hoy nada lo impedía.

`SECURE_HSTS_INCLUDE_SUBDOMAINS` es lo contrario: cuesta encenderlo y no debería apagarse por
descuido, porque apagarlo no se nota — los navegadores que ya lo recibieron siguen exigiendo HTTPS
durante un año, así que el sitio parece funcionar igual mientras la protección desaparece para los
visitantes nuevos.
"""

from __future__ import annotations

import importlib
import os
from types import ModuleType
from unittest import mock

import pytest

# Lo mínimo que `prod.py` exige del entorno para poder importarse. Son valores de mentira: no se
# conecta a nada, solo se lee la configuración.
ENTORNO_FALSO = {
    "DJANGO_ALLOWED_HOSTS": "ejemplo.test",
    "MLB_PROXY_URL": "http://proxy.test",
    "MLB_PROXY_API_KEY": "no-se-usa",
    "DATABASE_URL": "postgres://u:p@h:5432/d",
    "DJANGO_SECRET_KEY": "x" * 50,
    "SECRET_KEY": "x" * 50,
}


@pytest.fixture(scope="module")
def prod() -> ModuleType:
    with mock.patch.dict(os.environ, ENTORNO_FALSO, clear=False):
        return importlib.import_module("config.settings.prod")


def test_la_hsts_cubre_los_subdominios(prod: ModuleType) -> None:
    """Sin esto, `promo.` queda sin la protección aunque el apex la tenga.

    Se comprobó antes de encenderlo que los dos subdominios que existen —`www` y `promo`— redirigen
    HTTP→HTTPS con un 301. Si algún día nace uno sin TLS, esta prueba NO lo va a detectar: lo que
    hace es impedir que la protección se caiga sola.
    """
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_SECONDS >= 31536000, "un año es el mínimo que vale para una HSTS"


def test_el_preload_sigue_apagado(prod: ModuleType) -> None:
    """LA PRUEBA QUE IMPORTA. `preload` es la decisión irreversible.

    Si alguna vez se enciende a conciencia, esta prueba tiene que cambiarse a mano — y ese es el
    punto: obligar a que sea una decisión y no un descuido de una línea.
    """
    assert prod.SECURE_HSTS_PRELOAD is False, (
        "SECURE_HSTS_PRELOAD encendido inscribe el dominio en una lista compilada dentro de los "
        "navegadores. Salir de ahí tarda meses. Si es a propósito, cambia esta prueba y explica por "
        "qué en el commit."
    )


def test_las_cookies_solo_viajan_por_https(prod: ModuleType) -> None:
    """Una cookie de sesión sin `Secure` viaja en claro si algo pide el sitio por HTTP."""
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
