"""Ajustes que valen para toda la suite."""

from typing import Any

import pytest

from dglweb.mlb.client import MlbProxyError


@pytest.fixture(autouse=True)
def sin_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ningún test sale a la red por su cuenta.

    La portada le pide la pizarra al proxy en vivo, así que cualquier test que renderice `/` lo
    llamaría de verdad: lento, dependiente de que el proxy esté arriba, y capaz de colgar la suite en
    CI. Acá el cliente falla de entrada, que es un camino que el código ya tiene que manejar bien —la
    portada carga sin pizarra— y los tests de la pizarra ponen el suyo encima.
    """
    from dglweb.stats import scoreboard

    class _Nada:
        def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise MlbProxyError("en los tests no se sale a la red")

        def __enter__(self) -> "_Nada":
            return self

        def __exit__(self, *exc: object) -> None:
            pass

    monkeypatch.setattr(scoreboard, "_cliente", lambda: _Nada())


@pytest.fixture(autouse=True)
def cache_limpio() -> Any:
    """La pizarra se cachea; sin limpiar, un test vería la que dejó otro."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
