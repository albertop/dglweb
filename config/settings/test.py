"""Ajustes para la suite. Existe por una razón concreta y vale la pena leerla.

`DATABASE_URL` sale del entorno para que el contenedor que sirve el sitio pueda apuntar a la base
real. Pero la suite NO puede heredar eso: `pytest-django` crea y destruye una base `test_…`, y contra
la base de producción eso es —en el mejor caso— un permiso denegado, y en el peor exactamente lo que
suena. Pasó: al mover `DATABASE_URL` a `.env`, el gate empezó a fallar con «permission denied to
create database» contra 10.0.0.39.

Así que la base de pruebas se fija acá y no se negocia: nombre, usuario y clave son los del Postgres
descartable, y `DATABASE_URL` no se mira. Que el gate dependa de esa variable era el problema.

LO ÚNICO QUE VARÍA ES DÓNDE ESTÁ ESE POSTGRES
---------------------------------------------
La suite corre en dos sitios y el Postgres descartable no se llama igual en los dos:

* En el compose es el servicio `db`, un nombre que solo existe dentro de la red de Docker.
* En GitHub Actions es un `service` con el puerto publicado en el propio runner: `localhost`.

Clavar `db` dejó el CI en rojo doce pushes seguidos —558 errores por corrida, todos «failed to
resolve host 'db'»— sin que nadie lo notara, porque el gate local seguía en verde. De ahí que el
host salga de `DGLWEB_TEST_DB_HOST`, que es una variable SOLO de la suite: no la pone nadie más, no
la hereda el contenedor y no puede apuntar sin querer a la base real, que es lo que había que evitar.
"""

import os

from config.settings.dev import *  # el módulo de test hereda todo dev a propósito

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "dglweb",
        "USER": "dglweb",
        "PASSWORD": "dglweb",
        # Por defecto el del compose, que es donde corre el gate a diario. Ver la cabecera.
        "HOST": os.environ.get("DGLWEB_TEST_DB_HOST", "db"),
        "PORT": os.environ.get("DGLWEB_TEST_DB_PORT", "5432"),
    }
}

# La suite NO habla con Telegram. Vaciar las credenciales basta: `notify.configurado()` da falso y
# `notify.enviar()` se vuelve un no-op sin tocar la red — que es el comportamiento que el módulo ya
# tiene previsto para «no configurado».
#
# Hacía falta porque `.env` es real y `settings.test` lo heredaba. Los tests del orquestador hacen
# fallar pasos a propósito para comprobar que el fallo se avisa, así que cada corrida de la suite
# mandaba mensajes de verdad al grupo del dueño — indistinguibles de una alerta real, que es
# exactamente lo que vuelve inútil un canal de alertas.
#
# No se resuelve con un prefijo «TEST» en el texto: eso seguiría mandando mensajes y seguiría
# metiendo la red en la suite. Para probar el canal a mano está `manage.py telegram_check --probar`.
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
