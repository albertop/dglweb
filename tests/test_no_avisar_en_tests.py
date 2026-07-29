"""La suite no habla con Telegram. Con ninguno, ni con el de verdad ni con otro.

Pasó: `settings.test` heredaba el `.env` real, y los tests del orquestador hacen fallar pasos a
propósito para comprobar que el fallo se avisa. Cada corrida de la suite mandaba mensajes al grupo
del dueño —«update_fielding: failed (10 filas)», «Debut de Jugador 2»— indistinguibles a primera
vista de una alerta de verdad.

Eso es peor que ruido: un canal de alertas donde la mitad son falsas deja de leerse, y entonces la
alerta real llega igual y nadie la mira. El arreglo no es marcarlas con «TEST» —seguirían saliendo, y
seguirían metiendo la red en la suite— sino que no salgan.
"""

from typing import Any

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


# ── La comprobación de arranque del canal de avisos (2026-07-28) ────────────────────────────────


def _comprobar(monkeypatch: pytest.MonkeyPatch, *, entorno: str, token: str, chat: str) -> list[Any]:
    from django.test import override_settings

    from dglweb.core.checks import avisos_configurados

    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", f"config.settings.{entorno}")
    with override_settings(TELEGRAM_BOT_TOKEN=token, TELEGRAM_CHAT_ID=chat):
        return avisos_configurados(None)


def test_en_produccion_sin_credenciales_avisa(monkeypatch: pytest.MonkeyPatch) -> None:
    """El fallo real: producción llevaba muda desde siempre y nada lo decía.

    En dev las credenciales salen del `.env` que Django lee al arrancar; en producción ese archivo no
    existe —`.dockerignore` lo excluye— así que solo pueden venir del entorno del contenedor. Nadie
    las puso, `configurado()` devolvía falso, y `enviar()` se iba en silencio.
    """
    avisos = _comprobar(monkeypatch, entorno="prod", token="", chat="")

    assert [a.id for a in avisos] == ["core.W001"]


def test_es_aviso_y_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regla del dueño (2026-07-27): nunca bloquear un proceso por algo que no impide trabajar.

    Un `Error` de Django impide arrancar, y eso convertiría «no puedo avisar» en «no puedo servir el
    sitio» — cambiar un fallo silencioso por uno estruendoso y peor.
    """
    from django.core.checks import Warning as AvisoDjango

    avisos = _comprobar(monkeypatch, entorno="prod", token="", chat="")

    assert isinstance(avisos[0], AvisoDjango)


def test_con_las_dos_puestas_se_calla(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _comprobar(monkeypatch, entorno="prod", token="un-token", chat="-100123") == []


def test_a_medias_tambien_avisa(monkeypatch: pytest.MonkeyPatch) -> None:
    """`configurado()` exige las DOS. Un token sin chat no manda nada, y calla igual."""
    assert _comprobar(monkeypatch, entorno="prod", token="un-token", chat="") != []


def test_en_desarrollo_no_molesta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lo normal en dev es no tener el canal puesto, y un aviso que sale siempre no lo lee nadie."""
    assert _comprobar(monkeypatch, entorno="dev", token="", chat="") == []
