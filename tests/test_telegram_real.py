"""La comprobación de que el canal de avisos funciona DE VERDAD.

    pytest -m telegram

Manda un mensaje real al grupo del dueño usando el token real. Por eso está **excluido de la suite
por defecto** (`addopts = -m 'not telegram'`): el resto de los tests no puede mandar nada, y esa regla
la fija `config/settings/test.py` vaciando las credenciales.

POR QUÉ EXISTE, SI LOS DEMÁS TESTS YA PRUEBAN `notify`
------------------------------------------------------
Los otros parchean `httpx.post`: comprueban que el mensaje se arma bien, que un 401 no tumba el job,
que no se usa `parse_mode`. Nada de eso toca la red, así que **ninguno se enteraría de que el token
está vencido, revocado o mal copiado en el `.env`**.

Y eso es exactamente lo que hay que saber antes de confiar en el canal: un aviso que no llega no
avisa de que no llegó. El token está además pendiente de rotarse antes de producción (ver
`docs/TODO.md`), y esta es la forma de confirmar que la llave nueva quedó bien puesta.

EL PREFIJO
----------
El mensaje empieza por «TEST» y dice de dónde salió. Es la única vez que el sitio manda un mensaje a
propósito desde los tests, y tiene que ser imposible confundirlo con una alerta real — ya pasó al
revés: la suite mandaba fallos falsos indistinguibles de los buenos.
"""

import os

import pytest

pytestmark = pytest.mark.telegram


def _credenciales() -> tuple[str, str]:
    """Del entorno y no de `settings`: `settings.test` las vacía a propósito."""
    return os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


def test_the_real_credentials_actually_deliver_a_message() -> None:
    """Manda un mensaje de verdad y exige que Telegram diga que lo aceptó.

    Se comprueba la respuesta y no solo que no reviente: `notify.enviar` se traga los fallos a
    propósito —la regla es que el aviso puede perderse pero el trabajo no puede caerse— así que un
    token muerto devolvería `False` en silencio. Acá ese silencio es justamente el fallo.
    """
    import httpx
    from django.test import override_settings

    from dglweb.core import notify

    token, chat = _credenciales()
    if not token or not chat:
        pytest.skip("sin TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID en el entorno: no hay llave que probar")

    texto = (
        "TEST · comprobación del canal de avisos\n\n"
        "Este mensaje lo manda `pytest -m telegram`. Si lo estás leyendo, el token y el chat id "
        "funcionan.\n\n"
        "No es una alerta: no hay nada que revisar ni que cargar."
    )

    with override_settings(TELEGRAM_BOT_TOKEN=token, TELEGRAM_CHAT_ID=chat):
        assert notify.configurado() is True, "las credenciales del entorno no llegaron a settings"
        entregado = notify.enviar(texto)

    if not entregado:
        # Se vuelve a preguntar sin el manto de `notify` para que el fallo diga QUÉ contestó Telegram.
        # «devolvió False» no sirve para arreglar nada; «401 Unauthorized» sí.
        respuesta = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": "TEST · diagnóstico"},
            timeout=10,
        )
        pytest.fail(f"Telegram no aceptó el mensaje: HTTP {respuesta.status_code} — {respuesta.text[:200]}")
