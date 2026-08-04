"""El loader de `dgl_efemerides` — el quinto dataset de apoyo.

Este dataset es distinto de los otros cuatro: el CSV trae el TEXTO YA REDACTADO, y el exportador
(`static_data/efemerides/exportar_efemerides.ps1`) corre sus propias autocomprobaciones sobre los
datos completos antes de escribirlo. Repetir esas reglas acá sería tenerlas en dos lenguajes y
arriesgarse a que se separen.

Así que lo que se prueba es lo que el CSV puede romper AL CRUZAR LA FRONTERA —tipos, fechas, campos
obligatorios— más las dos formas de subir un archivo a medias que la pantalla de comparación no
delata por sí sola, porque un CSV recortado es un CSV perfectamente válido.
"""

from datetime import date
from typing import Any

import pytest

from dglweb.stats.models import Efemeride, StaticDataset
from dglweb.stats.staticdata import engine

TABLA = "dgl_efemerides"
CLAVE = ["tipo", "game_id", "mlb_id", "event_id"]


def _fila(**cambios: str) -> dict[str, str]:
    """Un ciclo de Rafael Devers: gesta de evento, con juego y con todos los números puestos."""
    base = {
        "tipo": "ciclo",
        "gesta": "un ciclo",
        "etiquetas": "hits5",
        "rol": "bateador",
        "signo": "1",
        "cobertura": "completa",
        "mlb_id": "646240",
        "nombre": "Rafael Devers",
        "fecha": "2019-04-05",
        "mes": "4",
        "dia": "5",
        "temporada": "2019",
        "anos": "7",
        "game_id": "PHI201904050",
        "event_id": "0",
        "game_type": "R",
        "equipo": "BOS",
        "equipo_nombre": "Boston Red Sox",
        "rival": "PHI",
        "rival_nombre": "Philadelphia Phillies",
        "en_casa": "0",
        "oponente": "",
        "magnitud": "4",
        "wpa_jugador": "0.32",
        "li_max": "1.85",
        "detalle": "5 hits y 1 empujada",
        "veces_total": "20",
        "jugadores_total": "16",
        "orden": "18",
        "veces_jugador": "1",
        "orden_jugador": "1",
        "rareza": "457.2",
        "puntaje": "715",
        "titular": "Bateó para el ciclo contra Philadelphia Phillies: 5 hits y 1 empujada.",
        "situacion": "Es uno de los 16 dominicanos con un ciclo.",
    }
    return base | cambios


def _persona(**cambios: str) -> dict[str, str]:
    """Un cumpleaños: sin juego, sin equipo y sin WPA. La otra forma que tiene una fila."""
    return _fila(
        tipo="cumpleanos",
        gesta="un cumpleaños",
        etiquetas="",
        rol="persona",
        game_id="",
        event_id="0",
        game_type="-",
        equipo="",
        equipo_nombre="",
        rival="",
        rival_nombre="",
        wpa_jugador="",
        li_max="",
        detalle="46 años",
        titular="Cumple 46 años.",
        situacion="",
        **cambios,
    )


def _relleno(cuantas: int) -> list[dict[str, str]]:
    """Filas suficientes para que las comprobaciones de archivo completo no salten.

    Se reparten por el calendario y por tipo a propósito: lo que se está probando en cada caso es
    otra cosa, y un `checks` disparando de fondo enturbiaría el resultado.
    """
    # El mes avanza cada 28 filas y el día cada una: así los pares (mes, día) no se repiten hasta la
    # 336. Con `i % 12` y `i % 28` a la vez irían acompasados y darían solo 84 días distintos, que es
    # justo lo que la comprobación del calendario ataja.
    return [
        _fila(
            tipo=f"tipo_{i % 60}",
            mlb_id=str(600000 + i),
            game_id=f"BOS2019{i:05d}",
            mes=str((i // 28) % 12 + 1),
            dia=str((i % 28) + 1),
        )
        for i in range(cuantas)
    ]


def _validar(*filas: dict[str, str]) -> tuple[list[dict[str, Any]], list[engine.Problem]]:
    return engine.validate(engine.REGISTRY[TABLA], list(filas), CLAVE)


@pytest.mark.django_db
def test_the_registry_row_ships_with_the_migration() -> None:
    """Sin la fila del registro la tabla existe pero no hay por dónde subirle el CSV."""
    dataset = StaticDataset.objects.get(table=TABLA)

    assert dataset.csv == "dgl_efemerides.csv"
    assert dataset.mode == StaticDataset.Mode.TRUNCATE
    assert dataset.natural_key == "tipo,game_id,mlb_id,event_id"
    dataset.full_clean()  # y describe algo que el motor puede cumplir


@pytest.mark.django_db
def test_a_complete_row_crosses_the_border_with_its_types_translated() -> None:
    rows, problems = _validar(*_relleno(400), _fila())

    assert problems == []
    ciclo = next(row for row in rows if row["tipo"] == "ciclo")
    assert ciclo["fecha"] == date(2019, 4, 5)
    assert ciclo["mlb_id"] == 646240
    assert ciclo["signo"] == 1
    assert ciclo["magnitud"] == pytest.approx(4.0)
    assert ciclo["wpa_jugador"] == pytest.approx(0.32)
    assert ciclo["puntaje"] == 715
    assert ciclo["titular"].startswith("Bateó para el ciclo")


@pytest.mark.django_db
def test_a_person_row_keeps_its_empties_as_empties_and_its_nulls_as_nulls() -> None:
    """Cumpleaños, debut y fallecimiento no cuelgan de ningún juego, y eso no es un defecto.

    La distinción importa: el texto vacío y el `None` no son lo mismo. `game_id` vacío significa
    «esta gesta no tiene juego»; `wpa_jugador` nulo significa «acá no hay WPA que medir».
    """
    rows, problems = _validar(*_relleno(400), _persona())

    assert problems == []
    cumple = next(row for row in rows if row["tipo"] == "cumpleanos")
    assert cumple["game_id"] == ""
    assert cumple["equipo"] == ""
    assert cumple["wpa_jugador"] is None
    assert cumple["li_max"] is None
    assert cumple["situacion"] == ""


@pytest.mark.django_db
def test_partial_coverage_leaves_the_totals_null_instead_of_zero() -> None:
    """Con cobertura parcial el exportador vacía los totales a propósito.

    Cero y ausencia no son lo mismo, y el sitio tiene que poder distinguirlas: cero dominicanos sería
    un dato, y lo que pasa es que no sabemos el número porque la fuente empieza en 2008.
    """
    rows, problems = _validar(
        *_relleno(400),
        _fila(tipo="inmaculado", cobertura="parcial", veces_total="", jugadores_total=""),
    )

    assert problems == []
    parcial = next(row for row in rows if row["tipo"] == "inmaculado")
    assert parcial["veces_total"] is None
    assert parcial["jugadores_total"] is None


@pytest.mark.django_db
def test_scientific_notation_survives_the_crossing() -> None:
    """PowerShell escribe los WPA muy chicos en notación científica.

    Medido sobre el archivo real: hay valores como «7.82716988860389E-05». Un parseo que filtre por
    dígitos y punto los daría por inválidos y tumbaría la carga.
    """
    rows, problems = _validar(*_relleno(400), _fila(wpa_jugador="7.82716988860389E-05"))

    assert problems == []
    fila = next(row for row in rows if row["tipo"] == "ciclo")
    assert fila["wpa_jugador"] == pytest.approx(7.82716988860389e-05)


@pytest.mark.django_db
@pytest.mark.parametrize("campo", ["tipo", "mlb_id", "fecha", "titular"])
def test_a_row_missing_something_essential_is_reported_with_its_line(campo: str) -> None:
    """No se descarta en silencio: una fila sin titular es un archivo mal generado.

    Tragársela dejaría un CSV que parece más sano de lo que está — y el titular es justamente lo que
    el sitio pinta, así que sin él la fila no sirve para nada.
    """
    _, problems = _validar(*_relleno(400), _fila(**{campo: ""}))

    assert problems, f"«{campo}» vacío tiene que dar problema"
    # El motor pone el resumen en `message` y el detalle —con el número de línea y el nombre del
    # campo— en `rows`, que es lo que la pantalla lista debajo. El nombre tiene que llegar ahí para
    # que el usuario sepa qué columna arreglar.
    assert any(campo in detalle for problem in problems for detalle in problem.rows)
    assert any("línea" in detalle for problem in problems for detalle in problem.rows)


@pytest.mark.django_db
def test_a_numeric_column_arriving_empty_fails_here_and_not_at_the_insert() -> None:
    """Si esto no se ataja, la comparación dice que todo está bien y revienta al escribir.

    Es el peor momento posible para enterarse: después de que el usuario apretó «Confirmar».
    """
    _, problems = _validar(*_relleno(400), _fila(puntaje=""))

    assert problems
    assert any("puntaje" in detalle for problem in problems for detalle in problem.rows)


@pytest.mark.django_db
def test_a_repeated_natural_key_is_caught() -> None:
    """El exportador ya fusiona por jugador-juego-evento, así que un repetido es señal de otra cosa.

    O el CSV se concatenó dos veces, o la fusión se rompió. En cualquier caso no se escribe.
    """
    _, problems = _validar(*_relleno(400), _fila(), _fila(nombre="Otro"))

    assert problems
    assert any("clave" in problem.message.lower() or "repet" in problem.message.lower() for problem in problems)


@pytest.mark.django_db
def test_a_file_covering_few_calendar_days_is_rejected() -> None:
    """Un archivo recortado es un CSV válido, así que la comparación sola no lo delata.

    Con los cumpleaños solos el archivo ya pasa de 330 días del calendario. Si llegan cincuenta, lo
    que se está por reemplazar entero es el archivo con un pedazo del archivo.
    """
    pocos = [
        _fila(tipo=f"tipo_{i % 60}", mlb_id=str(700000 + i), game_id=f"BOS2019{i:05d}", mes="4", dia=str((i % 20) + 1))
        for i in range(400)
    ]

    _, problems = _validar(*pocos)

    assert problems
    assert any("días del calendario" in problem.message for problem in problems)


@pytest.mark.django_db
def test_a_file_with_too_few_detector_types_is_rejected() -> None:
    """La otra forma de subir medio archivo: correr el exportador con la carpeta a medias."""
    # Con el calendario bien cubierto, para que el único problema que salte sea el de los tipos.
    monotematico = [
        _fila(mlb_id=str(700000 + i), game_id=f"BOS2019{i:05d}", mes=str((i // 28) % 12 + 1), dia=str((i % 28) + 1))
        for i in range(400)
    ]

    _, problems = _validar(*monotematico)

    assert problems
    assert any("tipos de efeméride" in problem.message for problem in problems)


@pytest.mark.django_db
def test_applying_replaces_the_whole_table() -> None:
    """El modo es truncate: el archivo del año pasado no se conserva ni se reconcilia."""
    Efemeride.objects.create(
        tipo="viejo", gesta="una gesta vieja", rol="bateador", signo=1, cobertura="completa",
        mlb_id=1, nombre="Alguien", fecha=date(1999, 1, 1), mes=1, dia=1, temporada=1999, anos=27,
        game_id="", event_id=0, game_type="-", en_casa=0, magnitud=1.0, orden=1,
        veces_jugador=1, orden_jugador=1, rareza=1.0, puntaje=1, titular="Algo viejo.",
    )
    rows, problems = _validar(*_relleno(400), _fila())
    assert problems == []

    engine.apply(engine.REGISTRY[TABLA], rows, CLAVE, truncating=True)

    assert not Efemeride.objects.filter(tipo="viejo").exists()
    assert Efemeride.objects.count() == 401
    guardada = Efemeride.objects.get(tipo="ciclo")
    assert guardada.titular.startswith("Bateó para el ciclo")
    assert guardada.mes == 4 and guardada.dia == 5
