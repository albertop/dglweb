"""La suite no habla con Telegram. Con ninguno, ni con el de verdad ni con otro.

Pasó: `settings.test` heredaba el `.env` real, y los tests del orquestador hacen fallar pasos a
propósito para comprobar que el fallo se avisa. Cada corrida de la suite mandaba mensajes al grupo
del dueño —«update_fielding: failed (10 filas)», «Debut de Jugador 2»— indistinguibles a primera
vista de una alerta de verdad.

Eso es peor que ruido: un canal de alertas donde la mitad son falsas deja de leerse, y entonces la
alerta real llega igual y nadie la mira. El arreglo no es marcarlas con «TEST» —seguirían saliendo, y
seguirían metiendo la red en la suite— sino que no salgan.
"""

import pytest
from django.conf import settings

from dglweb.core import notify


def test_the_suite_has_no_telegram_credentials() -> None:
    """La red de seguridad está en la configuración, no en que cada test se acuerde de parchear."""
    assert settings.TELEGRAM_BOT_TOKEN == "", "la suite tiene un token de Telegram: mandaría mensajes de verdad"
    assert settings.TELEGRAM_CHAT_ID == ""


def test_the_notifier_is_a_no_op_under_the_test_settings() -> None:
    """Lo que de verdad importa: que llamar a `enviar` no toque la red.

    Se comprueba el comportamiento y no solo la configuración, porque es el comportamiento lo que
    llega al teléfono del dueño.
    """
    assert notify.configurado() is False
    assert notify.enviar("esto no puede salir de la suite") is False


def test_sending_does_not_reach_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Y que ni siquiera lo intente: sin esto, un fallo de red podría estar tapando un envío real."""

    def prohibido(*args: object, **kwargs: object) -> object:
        raise AssertionError("la suite intentó hablar con Telegram")

    monkeypatch.setattr("httpx.post", prohibido)

    assert notify.enviar("tampoco así") is False
