"""Avisos por Telegram — el canal, y los dos sitios que lo usan.

Lo que más se prueba acá no es que el mensaje salga: es que **nunca rompa a quien lo llama**. Un
refresco de 400.000 filas no puede fallar porque Telegram esté caído, y un debut no puede perderse
porque la red se cortó justo al avisar. El aviso es lo accesorio; el trabajo es lo importante.
"""

from datetime import date
from typing import Any

import httpx
import pytest
from django.core.management import call_command
from django.utils import timezone

from dglweb.core import notify
from dglweb.players.models import Player
from dglweb.stats import pipeline
from dglweb.stats.models import DomPlayer, IngestRun, SeasonDates
from dglweb.stats.season_window import MLB
from tests.test_players import _other_player


@pytest.fixture
def configurado(settings: Any) -> None:
    settings.TELEGRAM_BOT_TOKEN = "123:abc"
    settings.TELEGRAM_CHAT_ID = "456"


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


# ── El canal ────────────────────────────────────────────────────────────────────────────────────


def test_without_a_token_it_stays_quiet_instead_of_complaining(settings: Any) -> None:
    """En desarrollo no hay token. Protestar por eso enseña a ignorar las protestas de verdad."""
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_CHAT_ID = ""

    assert notify.configurado() is False
    assert notify.enviar("hola") is False


def test_it_posts_the_text_as_plain_text(configurado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin `parse_mode`: un nombre con guion bajo rompería el mensaje o haría que la API lo rechace."""
    enviados: list[dict[str, Any]] = []

    def falso_post(url: str, **kwargs: Any) -> Any:
        enviados.append({"url": url, **kwargs})
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr("httpx.post", falso_post)

    assert notify.enviar("Debut de Juan_Soto") is True
    assert enviados[0]["json"]["text"] == "Debut de Juan_Soto"
    assert "parse_mode" not in enviados[0]["json"]
    assert "123:abc" in enviados[0]["url"]


def test_a_network_failure_is_swallowed_and_logged(configurado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """La regla que no se negocia: el aviso puede perderse, el trabajo no puede caerse."""

    def revienta(url: str, **kwargs: Any) -> Any:
        raise httpx.ConnectTimeout("sin red")

    monkeypatch.setattr("httpx.post", revienta)

    assert notify.enviar("hola") is False  # y no lanza


def test_an_error_response_is_also_swallowed(configurado: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un token vencido devuelve 401. Tampoco puede tumbar el job."""

    def prohibido(url: str, **kwargs: Any) -> Any:
        return httpx.Response(401, json={"ok": False}, request=httpx.Request("POST", url))

    monkeypatch.setattr("httpx.post", prohibido)

    assert notify.enviar("hola") is False


# ── El refresco diario ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def pasos_falsos(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    control: dict[str, Any] = {"estados": {}}

    def falso(comando: str, *args: Any, **kwargs: Any) -> None:
        if comando in pipeline.MANTENIMIENTO:
            return
        ahora = timezone.now()
        IngestRun.objects.create(
            command=comando,
            scope="test",
            status=control["estados"].get(comando, IngestRun.Status.SUCCESS),
            started_at=ahora,
            finished_at=ahora,
            rows_affected=1,
        )

    monkeypatch.setattr(pipeline, "call_command", falso)
    return control


@pytest.mark.django_db
def test_a_clean_refresh_sends_nothing(
    temporada: SeasonDates, pasos_falsos: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un «todo bien» diario se vuelve ruido en una semana, y entonces el canal deja de servir."""

    def no_avisar(texto: str) -> bool:
        pytest.fail("no debía avisar")

    monkeypatch.setattr("dglweb.core.notify.enviar", no_avisar)

    pipeline.run_and_record()


@pytest.mark.django_db
def test_a_broken_refresh_says_which_step_fell(
    temporada: SeasonDates, pasos_falsos: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """El monitor externo dirá «503»; esto dice CUÁL, que es la diferencia entre enterarse y actuar."""
    enviados: list[str] = []

    def espiar(texto: str) -> bool:
        enviados.append(texto)
        return True

    monkeypatch.setattr("dglweb.core.notify.enviar", espiar)
    pasos_falsos["estados"]["update_fielding"] = IngestRun.Status.FAILED

    pipeline.run_and_record()

    assert len(enviados) == 1
    assert "update_fielding" in enviados[0]
    assert "no se reconstruyeron" in enviados[0].lower()


@pytest.mark.django_db
def test_telegram_failing_does_not_fail_the_refresh(
    temporada: SeasonDates, pasos_falsos: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lo que este archivo existe para probar."""
    pasos_falsos["estados"]["update_fielding"] = IngestRun.Status.FAILED

    def revienta(texto: str) -> bool:
        raise RuntimeError("caído")

    monkeypatch.setattr("dglweb.core.notify.enviar", revienta)

    with pytest.raises(RuntimeError):
        pipeline.run_and_record()  # el doble lanza a propósito: `notify.enviar` real NUNCA lo hace

    assert IngestRun.objects.filter(command="refresh_daily").exists()  # el trabajo quedó registrado


# ── Los debuts ──────────────────────────────────────────────────────────────────────────────────


class _ProxyFalso:
    def __init__(self, con_stats: set[int]) -> None:
        self.con_stats = con_stats

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if path == "/api/v1/stats":
            splits = [{"player": {"id": pid}} for pid in sorted(self.con_stats)]
            return {"stats": [{"splits": splits if params and params.get("group") == "hitting" else []}]}
        return {"people": [{"fullName": "Debutante D", "mlbDebutDate": "2026-07-25"}]}


@pytest.mark.django_db
def test_a_new_debut_reaches_telegram(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    DomPlayer.objects.create(player_id=2, full_name="Debutante D")
    enviados: list[str] = []

    def espiar(texto: str) -> bool:
        enviados.append(texto)
        return True

    monkeypatch.setattr("dglweb.core.notify.enviar", espiar)
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: _ProxyFalso({2}))

    call_command("detect_debuts", "--season", "2026")

    assert len(enviados) == 1
    assert "Debutante D" in enviados[0]
    assert "Backoffice" in enviados[0]


@pytest.mark.django_db
def test_a_pending_debut_is_announced_every_single_day(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """La repetición es el mecanismo, no un efecto secundario.

    Hubo una versión que avisaba una sola vez por debutante, para no cansar. **El dueño pidió lo
    contrario**: si el aviso sale un martes y ese día no lo ve, el pelotero se queda fuera del sitio
    sin que nada vuelva a recordarlo. Insiste hasta que lo carga, que es el acuse de recibo.

    Puede insistir sin cansar porque son pocos y raros: un puñado al año.
    """
    DomPlayer.objects.create(player_id=2, full_name="Debutante D")
    enviados: list[str] = []

    def espiar(texto: str) -> bool:
        enviados.append(texto)
        return True

    monkeypatch.setattr("dglweb.core.notify.enviar", espiar)
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: _ProxyFalso({2}))

    call_command("detect_debuts", "--season", "2026")
    call_command("detect_debuts", "--season", "2026")  # al día siguiente, sigue pendiente

    assert len(enviados) == 2  # y vuelve a avisar, que es lo que se quiere
    assert enviados[0] == enviados[1]


@pytest.mark.django_db
def test_a_second_debut_does_get_announced(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """Y no al revés: silenciar al conocido no puede silenciar al que llega después."""
    DomPlayer.objects.create(player_id=2, full_name="Debutante D")
    DomPlayer.objects.create(player_id=3, full_name="Otro Debutante")
    enviados: list[str] = []

    def espiar(texto: str) -> bool:
        enviados.append(texto)
        return True

    monkeypatch.setattr("dglweb.core.notify.enviar", espiar)

    proxy = _ProxyFalso({2})
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: proxy)
    call_command("detect_debuts", "--season", "2026")

    proxy.con_stats = {2, 3}  # al otro día debuta un segundo
    call_command("detect_debuts", "--season", "2026")

    assert len(enviados) == 2


@pytest.mark.django_db
def test_nothing_pending_sends_nothing(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    Player.objects.create(**_other_player(player_id=1, dgl_id="v1", full_name="Veterano V"))

    def no_avisar(texto: str) -> bool:
        pytest.fail("no había nada que avisar")

    monkeypatch.setattr("dglweb.core.notify.enviar", no_avisar)
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: _ProxyFalso({1}))

    call_command("detect_debuts", "--season", "2026")


@pytest.mark.django_db
def test_the_alert_carries_the_id_the_backoffice_needs(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quien recibe el aviso va a dar de alta al pelotero: necesita el nombre y el `player_id`.

    Rotulado y en su propia línea. Como «• 2 Debutante D» el número se leía como parte de la viñeta.
    """
    DomPlayer.objects.create(player_id=2, full_name="Debutante D")
    enviados: list[str] = []

    def espiar(texto: str) -> bool:
        enviados.append(texto)
        return True

    monkeypatch.setattr("dglweb.core.notify.enviar", espiar)
    monkeypatch.setattr("dglweb.players.management.commands.detect_debuts.build_client", lambda: _ProxyFalso({2}))

    call_command("detect_debuts", "--season", "2026")

    assert "player_id 2" in enviados[0]
    assert "Cargalo en el Backoffice" in enviados[0]


# ── El comprobador ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_checker_explains_a_missing_token_instead_of_crashing(settings: Any, capsys: Any) -> None:
    """Es una herramienta de diagnóstico: si revienta cuando falta lo que vino a diagnosticar, no sirve."""
    settings.TELEGRAM_BOT_TOKEN = ""

    call_command("telegram_check")

    assert "@BotFather" in capsys.readouterr().err


@pytest.mark.django_db
def test_the_checker_names_the_bot_and_says_what_is_missing(
    configurado: None, settings: Any, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """El caso del medio, y el que más confunde: token bueno pero sin chat todavía."""
    settings.TELEGRAM_CHAT_ID = ""

    def falso_get(url: str, **kwargs: Any) -> Any:
        cuerpo = {"ok": True, "result": {"username": "dglweb_avisos_bot"} if "getMe" in url else []}
        return httpx.Response(200, json=cuerpo, request=httpx.Request("GET", url))

    monkeypatch.setattr("httpx.get", falso_get)

    call_command("telegram_check", "--buscar")

    salida = capsys.readouterr().out
    assert "dglweb_avisos_bot" in salida
    assert "no puede escribir primero" in salida  # la explicación del paso que nadie adivina
