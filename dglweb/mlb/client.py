"""The single door to the MLB proxy.

Every scraper goes through this client, so all the network failure handling lives here and
nowhere else. It guarantees callers two things:

* **One exception type.** Timeouts, connection errors, HTTP errors and malformed bodies all
  surface as `MlbProxyError`, so a caller writes one `except` and degrades gracefully instead
  of leaking `httpx` internals into commands and views.
* **Retries only where they help.** Server errors and timeouts are transient, so they are
  retried with exponential backoff. A 4xx means *our* request is wrong — retrying it would
  just hammer the upstream without ever succeeding, so it fails immediately.

Note the proxy renames the upstream stat fields (`gamesPlayed` -> `G`, `strikeOuts` -> `K`,
`doubles` -> `X2B`, ...). Callers get the translated names; mapping them to our columns is the
job of the parsing layer, not of this client.
"""

import logging
import time
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def build_client() -> "MlbProxyClient":
    """The client every command should use: configured from the environment, one place."""
    return MlbProxyClient(
        base_url=settings.MLB_PROXY_URL,
        api_key=settings.MLB_PROXY_API_KEY,
        timeout=settings.MLB_PROXY_TIMEOUT,
    )


class MlbProxyError(RuntimeError):
    """The proxy could not be reached, refused the request, or answered with garbage."""


class MlbProxyClient:
    """Synchronous client for the MLB proxy.

    Sync on purpose: the scrapers are batch jobs where clarity beats concurrency, and the
    proxy already caches and coalesces upstream calls on its side.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 20.0,
        max_attempts: int = 3,
        retry_backoff: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._max_attempts = max_attempts
        self._retry_backoff = retry_backoff
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Fetch `path` and return the decoded JSON, or raise `MlbProxyError`."""
        last_error: str = ""

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.get(path, params=params)
            except httpx.TimeoutException as exc:
                last_error = f"no se pudo conectar al proxy ({exc.__class__.__name__})"
            except httpx.HTTPError as exc:
                last_error = f"no se pudo conectar al proxy ({exc.__class__.__name__})"
            else:
                if response.status_code < 400:
                    return self._decode(response)
                if response.status_code < 500:
                    # Our request is wrong; another identical try cannot fix it.
                    raise MlbProxyError(f"el proxy rechazó {path} con HTTP {response.status_code}")
                last_error = f"el proxy respondió HTTP {response.status_code} en {path}"

            if attempt < self._max_attempts:
                logger.warning("Intento %s/%s falló: %s", attempt, self._max_attempts, last_error)
                time.sleep(self._retry_backoff * 2 ** (attempt - 1))

        raise MlbProxyError(f"{last_error} (tras {self._max_attempts} intentos)")

    def _decode(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise MlbProxyError(f"el proxy devolvió algo que no es JSON: {exc}") from exc

        # Every statsapi endpoint we use answers with an object. Anything else means the shape
        # changed upstream, and silently returning it would push the surprise into the parsers.
        if not isinstance(payload, dict):
            raise MlbProxyError(f"se esperaba un objeto JSON y llegó {type(payload).__name__}")
        return payload

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MlbProxyClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
