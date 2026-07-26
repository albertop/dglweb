"""Ajustes para la suite. Existe por una razón concreta y vale la pena leerla.

`DATABASE_URL` sale del entorno para que el contenedor que sirve el sitio pueda apuntar a la base
real. Pero la suite NO puede heredar eso: `pytest-django` crea y destruye una base `test_…`, y contra
la base de producción eso es —en el mejor caso— un permiso denegado, y en el peor exactamente lo que
suena. Pasó: al mover `DATABASE_URL` a `.env`, el gate empezó a fallar con «permission denied to
create database» contra 10.0.0.39.

Así que la base de pruebas se fija acá y no se negocia. Que el gate dependa de una variable de
entorno era el problema, no la solución.
"""

from config.settings.dev import *  # el módulo de test hereda todo dev a propósito

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "dglweb",
        "USER": "dglweb",
        "PASSWORD": "dglweb",
        # El Postgres del propio compose. Es descartable y local: justo lo que la suite necesita.
        "HOST": "db",
        "PORT": "5432",
    }
}
