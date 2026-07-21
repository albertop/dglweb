"""Tests for the MLB proxy client (Fase 3).

The client is the single door to the proxy: every scraper goes through it, so its failure
behaviour is what keeps a bad night from corrupting a table or hanging a page.
"""

from typing import Any

import httpx
import pytest

from dglweb.mlb.client import MlbProxyClient, MlbProxyError, build_client

PATH = "/api/v1/people/134181"


def _client(handler: object, **kwargs: object) -> MlbProxyClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return MlbProxyClient(
        base_url="http://proxy.test",
        api_key="test-key",
        retry_backoff=0,  # no real sleeping in tests
        transport=transport,
        **kwargs,  # type: ignore[arg-type]
    )


def test_sends_the_api_key_and_requested_path() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"people": []})

    _client(handler).get(PATH, {"hydrate": "stats(group=[hitting])"})

    assert seen["key"] == "test-key"
    # httpx percent-encodes the hydrate syntax (parentheses and brackets); the proxy accepts it.
    assert seen["url"] == ("http://proxy.test/api/v1/people/134181?hydrate=stats%28group%3D%5Bhitting%5D%29")


def test_returns_the_decoded_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"people": [{"id": 134181}]})

    assert _client(handler).get(PATH) == {"people": [{"id": 134181}]}


def test_retries_a_server_error_and_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    assert _client(handler).get(PATH) == {"ok": True}
    assert attempts["n"] == 3


def test_gives_up_after_the_last_attempt() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(500)

    with pytest.raises(MlbProxyError, match="500"):
        _client(handler, max_attempts=2).get(PATH)

    assert attempts["n"] == 2


def test_does_not_retry_a_client_error() -> None:
    """A 404 is a bug in our request; retrying it just wastes the upstream's patience."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(404)

    with pytest.raises(MlbProxyError, match="404"):
        _client(handler).get(PATH)

    assert attempts["n"] == 1


def test_a_timeout_is_retried_and_then_raises_our_error() -> None:
    """Callers must never see a raw httpx exception — they catch one type and degrade."""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectTimeout("too slow")

    with pytest.raises(MlbProxyError, match="conectar"):
        _client(handler, max_attempts=2).get(PATH)

    assert attempts["n"] == 2


def test_invalid_json_is_reported_as_a_proxy_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(MlbProxyError, match="JSON"):
        _client(handler).get(PATH)


def test_a_connection_error_is_also_wrapped() -> None:
    """Proxy down (not just slow): same single exception type for the caller."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(MlbProxyError, match="conectar"):
        _client(handler, max_attempts=1).get(PATH)


def test_works_as_a_context_manager_and_closes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    with _client(handler) as client:
        assert client.get(PATH) == {"ok": True}

    with pytest.raises(RuntimeError):
        client.get(PATH)


def test_build_client_reads_the_settings(settings: Any) -> None:
    settings.MLB_PROXY_URL = "http://proxy.test/"
    settings.MLB_PROXY_API_KEY = "from-settings"
    settings.MLB_PROXY_TIMEOUT = 7.5

    client = build_client()

    assert client._client.base_url == "http://proxy.test"
    assert client._client.headers["x-api-key"] == "from-settings"
    assert client._client.timeout.read == 7.5


def test_a_json_array_is_rejected() -> None:
    """A shape change upstream must fail here, not surface as a weird parser bug later."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    with pytest.raises(MlbProxyError, match="objeto JSON"):
        _client(handler).get(PATH)
