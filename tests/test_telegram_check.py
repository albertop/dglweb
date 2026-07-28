"""El comando que diagnostica el canal de avisos, sobre todo cuando el canal está roto.

`telegram_check` es la herramienta a la que uno acude JUSTAMENTE cuando los avisos ya fallaron, así
que sus caminos de error son los que tienen que estar bien: un token que no sirve, un Telegram que no
contesta y un `--buscar` que no encuentra nada son los tres estados en los que el comando se usa de
verdad. El camino feliz —token válido, chat configurado— se prueba también, pero es el menos
interesante: si todo funciona, nadie corre esto.

Cada llamada a la red está simulada. Nunca sale una petición: ver `test_no_avisar_en_tests`, y el
marcador `telegram` del `pyproject.toml` para la única comprobación que sí habla de verdad.
"""

from io import StringIO
from typing import Any

import httpx
import pytest
from django.core.management import call_command
from django.test import override_settings

TOKEN = "123456:token-de-mentira"
CHAT = "-1001234567890"


def _respuesta(payload: dict[str, Any]) -> Any:
    """Un doble de `httpx.Response` con lo único que el comando le pide: `.json()`."""

    class _Falsa:
        def json(self) -> dict[str, Any]:
            return payload

    return _Falsa()


def _correr(monkeypatch: pytest.MonkeyPatch, respuestas: dict[str, Any], **opciones: Any) -> tuple[str, str]:
    """Corre el comando con `httpx.get` simulado. Devuelve (stdout, stderr).

    `respuestas` va por método de la API —`getMe`, `getUpdates`—; un valor que sea excepción se lanza,
    que es como se simula un Telegram caído.
    """

    def falso_get(url: str, **kwargs: Any) -> Any:
        metodo = url.rsplit("/", 1)[-1]
        valor = respuestas[metodo]
        if isinstance(valor, Exception):
            raise valor
        return _respuesta(valor)

    monkeypatch.setattr(httpx, "get", falso_get)
    salida, errores = StringIO(), StringIO()
    call_command("telegram_check", stdout=salida, stderr=errores, **opciones)
    return salida.getvalue(), errores.getvalue()


# ── Los tres caminos de error, que son la razón de ser del comando ──────────────────────────────


def test_without_a_token_it_says_where_to_get_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Es el estado de partida de cualquiera que conecte el bot por primera vez.

    Y no basta con decir «falta el token»: hay que decir que se pide a @BotFather, que es el paso que
    no se adivina.
    """
    salida, errores = _correr(monkeypatch, {})

    assert "Falta TELEGRAM_BOT_TOKEN" in errores
    assert "BotFather" in errores
    assert salida == ""


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
def test_a_telegram_that_does_not_answer_is_a_message_not_a_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una traza de `httpx` en la consola no le dice a nadie qué hacer con eso."""
    salida, errores = _correr(monkeypatch, {"getMe": httpx.ConnectError("sin ruta al host")})

    assert "No se pudo hablar con Telegram" in errores
    assert "sin ruta al host" in errores  # el motivo, no solo que hubo uno
    assert salida == ""


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN)
def test_a_token_that_does_not_work_is_told_apart_from_a_network_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Telegram contesta, pero dice que no. Son dos problemas distintos y se arreglan distinto:
    uno es rotar el token y el otro es mirar la red."""
    salida, errores = _correr(monkeypatch, {"getMe": {"ok": False, "description": "Unauthorized"}})

    assert "El token no sirve" in errores
    assert "Unauthorized" in errores
    assert salida == ""


# ── El chat id, que es el paso que confunde a todo el mundo ─────────────────────────────────────


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_CHAT_ID="")
def test_with_a_valid_token_and_no_chat_it_points_at_the_next_step(monkeypatch: pytest.MonkeyPatch) -> None:
    salida, _ = _correr(monkeypatch, {"getMe": {"ok": True, "result": {"username": "dglweb_bot"}}})

    assert "Token válido" in salida and "dglweb_bot" in salida
    assert "--buscar" in salida  # qué hacer ahora, no solo qué falta


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_CHAT_ID="")
def test_searching_with_no_messages_explains_that_a_bot_cannot_write_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El malentendido central del comando: `getUpdates` viene vacío hasta que vos le escribís.

    Sin esta explicación, la lista vacía se lee como «el bot está roto».
    """
    salida, _ = _correr(
        monkeypatch,
        {"getMe": {"ok": True, "result": {"username": "dglweb_bot"}}, "getUpdates": {"result": []}},
        buscar=True,
    )

    assert "Ningún mensaje recibido todavía" in salida
    assert "no puede escribir primero" in salida


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_CHAT_ID="")
def test_searching_prints_the_chat_id_ready_to_paste_into_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """En la forma exacta que hay que pegar en el `.env`, no como un número suelto que hay que
    envolver a mano. Y con el nombre al lado, que es lo que permite reconocer cuál es cuál."""
    salida, _ = _correr(
        monkeypatch,
        {
            "getMe": {"ok": True, "result": {"username": "dglweb_bot"}},
            "getUpdates": {"result": [{"message": {"chat": {"id": int(CHAT), "title": "Avisos DGL"}}}]},
        },
        buscar=True,
    )

    assert f"TELEGRAM_CHAT_ID={CHAT}" in salida
    assert "Avisos DGL" in salida


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_CHAT_ID="")
def test_a_chat_that_only_added_the_bot_is_found_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Meter el bot a un grupo no manda un `message`, manda un `my_chat_member`.

    Es el caso normal para un grupo de avisos —nadie le escribe al bot, se lo agrega— y mirar solo
    `message` dejaría la lista vacía justo en el escenario para el que existe el comando.
    """
    salida, _ = _correr(
        monkeypatch,
        {
            "getMe": {"ok": True, "result": {"username": "dglweb_bot"}},
            "getUpdates": {"result": [{"my_chat_member": {"chat": {"id": -99, "title": "Grupo nuevo"}}}]},
        },
        buscar=True,
    )

    assert "TELEGRAM_CHAT_ID=-99" in salida


# ── El mensaje de prueba ────────────────────────────────────────────────────────────────────────


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_CHAT_ID=CHAT)
def test_the_test_message_reports_whether_it_actually_went_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """`notify.enviar` devuelve si salió; el comando tiene que decirlo y no dar por hecho que sí."""
    # Por la ruta del módulo de origen: el comando hace `from dglweb.core import notify`, así que es
    # el mismo objeto, y así el parche no depende de qué nombres reexporta el comando.
    monkeypatch.setattr("dglweb.core.notify.enviar", lambda texto: False)

    salida, _ = _correr(monkeypatch, {"getMe": {"ok": True, "result": {"username": "dglweb_bot"}}}, probar=True)

    assert "No se pudo enviar" in salida
    assert "Mensaje de prueba enviado" not in salida


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_CHAT_ID=CHAT)
def test_nothing_is_sent_unless_it_is_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin `--probar` el comando diagnostica y no manda nada. Un diagnóstico que despierta el
    teléfono del dueño cada vez que se corre no se corre nunca."""

    def prohibido(texto: str) -> bool:
        raise AssertionError("mandó un mensaje sin que se lo pidieran")

    monkeypatch.setattr("dglweb.core.notify.enviar", prohibido)

    salida, _ = _correr(monkeypatch, {"getMe": {"ok": True, "result": {"username": "dglweb_bot"}}})

    assert f"Chat configurado: {CHAT}" in salida
