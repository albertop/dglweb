"""El hilo que rehace lo derivado — quién cierra las conexiones y quién no.

Lo que hace `run` ya está probado en otros sitios: que corre los comandos en orden, bajo un solo
candado, y sin la puerta de temporada (ver `test_season_window` y `test_locks`). Acá se prueba lo
otro, lo que no se ve mirando la salida: **el manejo de las conexiones a Postgres**.

Es una regla de dos caras y las dos hacen daño si se rompen:

* En un hilo propio HAY que cerrar. El hilo abre sus conexiones y nadie las va a cerrar por él, así
  que cada carga de datos dejaría una colgada. Con un pool chico, unas cuantas cargas y el sitio deja
  de poder abrir conexiones — un fallo que aparece lejos de su causa.
* En el hilo principal NO hay que cerrar. Ahí las conexiones son de otro —del request que llamó, o
  del test— y cerrarlas le rompe la transacción a quien nos llamó. Cerrar lo que uno no abrió nunca
  es correcto.

El `finally` que decide eso mira `threading.current_thread()`, y por eso los tests de acá tienen que
cruzar de hilo de verdad en vez de simularlo.
"""

import threading
from typing import Any

import pytest

from dglweb.stats import rebuilds


@pytest.fixture
def sin_trabajo_real(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Anula los comandos: acá no se prueba qué construyen, sino quién limpia detrás.

    Anula también el candado, que es de Postgres: los tests de este módulo corren en hilos ajenos a
    la transacción del test y pedirle un `advisory lock` a una conexión que no es la suya cuelga.
    Que el candado se toma de verdad ya lo prueba `test_locks`.
    """
    corridos: list[str] = []
    monkeypatch.setattr(rebuilds, "locks", _CandadoDeMentira())
    monkeypatch.setattr(
        "django.core.management.call_command",
        lambda nombre, *a, **k: corridos.append(nombre),
    )
    return corridos


class _CandadoDeMentira:
    """Con la misma forma que `locks`: un gestor de contexto que no hace nada."""

    class _Nada:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: Any) -> None:
            return None

    def cadena_derivada(self) -> "_CandadoDeMentira._Nada":
        return self._Nada()


def _cerradas_al_correr(en_hilo: bool, monkeypatch: pytest.MonkeyPatch) -> bool:
    """Corre `rebuilds.run` en el hilo pedido y dice si cerró las conexiones."""
    cerro: list[bool] = []
    # Por la ruta del módulo de origen y no por `rebuilds.connections`: es el mismo objeto —el import
    # de `rebuilds` es un alias— y así no se depende de qué nombres reexporta ese módulo.
    monkeypatch.setattr("django.db.connections.close_all", lambda: cerro.append(True))

    if en_hilo:
        hilo = threading.Thread(target=rebuilds.run, args=(["build_leaders"],))
        hilo.start()
        hilo.join(timeout=10)
        assert not hilo.is_alive(), "el hilo no terminó"
    else:
        rebuilds.run(["build_leaders"])

    return bool(cerro)


@pytest.mark.django_db
def test_a_rebuild_in_its_own_thread_closes_the_connections_it_opened(
    sin_trabajo_real: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin esto, cada carga de datos deja una conexión colgada en Postgres."""
    assert _cerradas_al_correr(en_hilo=True, monkeypatch=monkeypatch) is True


@pytest.mark.django_db
def test_a_rebuild_in_the_main_thread_leaves_someone_elses_connections_alone(
    sin_trabajo_real: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acá la conexión es del request que llamó, o del test. Cerrarla le rompe la transacción."""
    assert _cerradas_al_correr(en_hilo=False, monkeypatch=monkeypatch) is False


# El `filterwarnings` no esconde un problema: la excepción SALE del hilo a propósito, y salir es lo
# que la manda al log del servidor con su traza. Lo único que se silencia es que pytest la reporte
# como huérfana, cosa que acá es exactamente lo que el test provoca.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
@pytest.mark.django_db
def test_the_connections_are_closed_even_when_a_command_explodes(
    sin_trabajo_real: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Va en un `finally` y no al final del cuerpo, que es la diferencia que importa.

    Un comando que revienta es justo cuando MÁS caro sale dejar la conexión abierta: se reintenta, y
    cada reintento suma otra.
    """
    cerro: list[bool] = []
    # Por la ruta del módulo de origen y no por `rebuilds.connections`: es el mismo objeto —el import
    # de `rebuilds` es un alias— y así no se depende de qué nombres reexporta ese módulo.
    monkeypatch.setattr("django.db.connections.close_all", lambda: cerro.append(True))
    monkeypatch.setattr(
        "django.core.management.call_command",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("reventó a mitad")),
    )

    hilo = threading.Thread(target=rebuilds.run, args=(["build_leaders"],))
    hilo.start()
    hilo.join(timeout=10)

    assert not hilo.is_alive()
    assert cerro == [True]


# ── El lanzamiento en segundo plano ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_background_launch_returns_before_the_work_is_done(
    sin_trabajo_real: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Es la razón de ser del hilo: sin él, la respuesta HTTP espera el minuto y pico de
    `build_leaders` — el tipo de request que un proxy corta a los 30 segundos."""
    arrancó = threading.Event()
    soltar = threading.Event()

    def lento(nombres: Any) -> None:
        arrancó.set()
        soltar.wait(timeout=10)

    monkeypatch.setattr(rebuilds, "run", lento)

    devuelto = rebuilds.run_in_background(["build_career_totals", "build_leaders"])

    try:
        assert devuelto == "build_career_totals, build_leaders"  # lo que se le muestra al usuario
        assert arrancó.wait(timeout=10), "el hilo nunca arrancó"
    finally:
        soltar.set()  # que el hilo termine aunque el assert falle


@pytest.mark.django_db
def test_asking_for_nothing_starts_no_thread(sin_trabajo_real: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Una lista vacía es «no hay nada derivado de esto», no «reconstruí todo»."""
    monkeypatch.setattr("threading.Thread", lambda *a, **k: pytest.fail("no debería lanzar un hilo sin comandos"))

    assert rebuilds.run_in_background([]) == ""
