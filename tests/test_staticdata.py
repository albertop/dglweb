"""El motor de datos de apoyo (Fase 4e): validación, comparación y escritura.

Se prueba con un loader de juguete, no con el de batazos: el punto del motor es que no sabe nada de
ningún dataset, y un test que dependa del dataset real no probaría eso.
"""

from typing import Any, ClassVar

import pytest
from django.urls import reverse

from dglweb.players.models import Player
from dglweb.stats.models import BattedBallHits
from dglweb.stats.staticdata import engine
from tests.test_players import _other_player


class _Juguete(engine.Loader):
    """Un dataset cualquiera. Lo único que declara son las tres cosas obligatorias."""

    table = "dgl_batted_ball_hits"
    model = BattedBallHits
    columns: ClassVar[dict[str, str]] = {
        "player": "player_id",
        "season": "season",
        "stat_group": "stat_group",
        "ground_hits": "ground_hits",
    }

    def resolve(self, row: dict[str, str]) -> dict[str, Any] | None:
        return {
            "player_id": int(row["player"]),
            "season": int(row["season"]),
            "stat_group": row["stat_group"],
            "ground_hits": int(row["ground_hits"]),
        }


KEY = ["player_id", "season", "stat_group"]


def _player(pid: int) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=f"d{pid}", full_name=f"Jugador {pid}"))


def _csv(*lines: str) -> list[dict[str, str]]:
    header = "player,season,stat_group,ground_hits\n"
    return engine.read((header + "\n".join(lines) + "\n").encode("utf-8"))


@pytest.mark.django_db
def test_a_repeated_natural_key_blocks_the_load() -> None:
    """Un duplicado en la clave es un export mal hecho, y con truncate inserta las dos filas."""
    p = _player(1)
    rows, problems = engine.validate(_Juguete(), _csv(f"{p.pk},2000,batting,10", f"{p.pk},2000,batting,20"), KEY)

    assert len(rows) == 2  # se leyeron bien: el problema no es de formato
    assert problems and "se repite" in problems[0].message
    assert not engine.compare(_Juguete(), rows, KEY, problems, truncating=True).can_apply


@pytest.mark.django_db
def test_the_comparison_lists_what_disappears_only_when_truncating() -> None:
    """Con truncate lo ausente se pierde; con upsert sobrevive, y eso cambia lo que hay que avisar."""
    viejo, nuevo = _player(1), _player(2)
    BattedBallHits.objects.create(player=viejo, season=1999, stat_group="batting", ground_hits=5)
    rows, problems = engine.validate(_Juguete(), _csv(f"{nuevo.pk},2000,batting,7"), KEY)

    truncando = engine.compare(_Juguete(), rows, KEY, problems, truncating=True)
    upsert = engine.compare(_Juguete(), rows, KEY, problems, truncating=False)

    assert truncando.vanishing == [f"{viejo.pk}|1999|batting"]  # se va: hay que verlo antes
    assert truncando.rows_before == 1 and truncando.rows_after == 1
    assert upsert.vanishing == []  # sobrevive
    assert upsert.rows_after == 2


@pytest.mark.django_db
def test_apply_truncates_or_upserts_and_never_leaves_it_half_done() -> None:
    p = _player(1)
    BattedBallHits.objects.create(player=p, season=1999, stat_group="batting", ground_hits=5)

    rows, _ = engine.validate(_Juguete(), _csv(f"{p.pk},2000,batting,7"), KEY)
    engine.apply(_Juguete(), rows, KEY, truncating=False)  # upsert: la de 1999 queda
    assert BattedBallHits.objects.count() == 2

    engine.apply(_Juguete(), rows, KEY, truncating=True)  # truncate: solo lo del CSV
    assert [(r.season, r.ground_hits) for r in BattedBallHits.objects.all()] == [(2000, 7)]


@pytest.mark.django_db
def test_upsert_updates_in_place_instead_of_duplicating() -> None:
    p = _player(1)
    BattedBallHits.objects.create(player=p, season=2000, stat_group="batting", ground_hits=5)

    rows, _ = engine.validate(_Juguete(), _csv(f"{p.pk},2000,batting,9"), KEY)
    engine.apply(_Juguete(), rows, KEY, truncating=False)

    assert BattedBallHits.objects.count() == 1
    assert BattedBallHits.objects.get().ground_hits == 9


@pytest.mark.django_db
def test_a_missing_column_stops_everything_before_reading_rows() -> None:
    sin_columna = engine.read(b"player,season,stat_group\n1,2000,batting\n")
    rows, problems = engine.validate(_Juguete(), sin_columna, KEY)

    assert rows == []
    assert problems and "faltan columnas" in problems[0].message


@pytest.mark.django_db
def test_the_real_loader_checks_the_four_types_and_the_season_coverage() -> None:
    """Exacta por fila; la cobertura, por TEMPORADA — medirla por fila confundía muestras chicas."""
    from dglweb.stats.staticdata.loaders import BattedBallHitsLoader

    def fila(**extra: int) -> dict[str, Any]:
        base = {
            "player_id": 1,
            "season": 2000,
            "stat_group": "batting",
            "ground_hits": 5,
            "fly_hits": 3,
            "line_hits": 2,
            "pop_hits": 1,
            "__h_typed": 11,
            "__h_all": 11,
        }
        return {**base, **extra}

    assert BattedBallHitsLoader().checks([fila()]) == []

    # Los cuatro no suman los tipificados: error de armado del CSV.
    rotas = BattedBallHitsLoader().checks([fila(__h_typed=99)])
    assert len(rotas) == 1 and "no suman los hits tipificados" in rotas[0].message

    # Una fila chica muy por debajo NO bloquea si la temporada está sana: es ruido de muestra, no un
    # export malo. Antes, midiendo por fila, esto reventaba con 203 filas legítimas.
    sana = [
        fila(player_id=1, __h_all=20),
        fila(player_id=2, __h_typed=1000, __h_all=1000, ground_hits=1000, fly_hits=0, line_hits=0, pop_hits=0),
    ]
    assert BattedBallHitsLoader().checks(sana) == []

    # Pero la temporada entera caída sí: aquí el agregado es 11 de 200.
    caida = [fila(player_id=n, __h_all=20) for n in range(10)]
    problems = BattedBallHitsLoader().checks(caida)
    assert len(problems) == 1
    assert "por debajo" in problems[0].message
    assert problems[0].rows[0].startswith("2000 (batting):")


@pytest.mark.django_db
def test_loading_the_hits_also_fixes_the_coefficients_they_feed() -> None:
    """Cargar los hits no sirve si GB%/FB%/LD%/PU% siguen calculados con los viejos.

    Reproduce el caso real: la fuente entregó los outs completos y casi ningún hit, así que los
    cuatro coeficientes no llegaban a sumar 100%. Tras la carga tienen que sumar 1.0.
    """
    from dglweb.stats.models import Batting
    from dglweb.stats.staticdata.loaders import BattedBallHitsLoader

    p = _player(1)
    # Como venía del proxy: 60 outs tipificados, 0 hits, 100 bolas en juego -> los coeficientes suman .60
    Batting.objects.create(
        player=p,
        season=2000,
        stint=1,
        team="XXX",
        h=40,
        balls_in_play=100,
        ground_outs=30,
        fly_outs=20,
        line_outs=8,
        pop_outs=2,
        ground_hits=0,
        fly_hits=0,
        line_hits=0,
        pop_hits=0,
    )
    filas = [
        {
            "player_id": p.pk,
            "season": 2000,
            "stat_group": "batting",
            "ground_hits": 20,
            "fly_hits": 12,
            "line_hits": 7,
            "pop_hits": 1,
            "__h": 40,
        }
    ]

    BattedBallHitsLoader().post_apply(filas)

    linea = Batting.objects.get(player=p, season=2000)
    assert (linea.ground_hits, linea.fly_hits, linea.line_hits, linea.pop_hits) == (20, 12, 7, 1)
    # (30+20) + (20+12) + (8+7) + (2+1) = 100 sobre 100 bolas en juego
    reparto = [linea.gb_pct, linea.fb_pct, linea.ld_pct, linea.pu_pct]
    assert None not in reparto
    assert round(sum(v for v in reparto if v is not None), 6) == 1.0
    assert linea.gb_pct == 0.5  # 50 roletazos de 100


@pytest.mark.django_db
def test_the_override_never_replaces_better_data_with_worse() -> None:
    """Retrosheet tipifica ~97,5% y el proxy 100% desde 2004: pisar a ciegas degradaba lo sano.

    El CSV trae todo el rango a propósito —así no hay que mantener una lista de años rotos— y la
    decisión de cuál fuente gana se toma fila por fila.
    """
    from dglweb.stats.models import Batting
    from dglweb.stats.staticdata.loaders import BattedBallHitsLoader

    p = _player(1)
    # Temporada sana: el proxy ya tipificó los 40 hits.
    Batting.objects.create(
        player=p,
        season=2010,
        stint=1,
        team="XXX",
        h=40,
        balls_in_play=100,
        ground_outs=30,
        fly_outs=20,
        line_outs=8,
        pop_outs=2,
        ground_hits=20,
        fly_hits=12,
        line_hits=7,
        pop_hits=1,
    )
    # Retrosheet trae menos (39 de 40): no debe pisar.
    BattedBallHitsLoader().post_apply(
        [
            {
                "player_id": p.pk,
                "season": 2010,
                "stat_group": "batting",
                "ground_hits": 20,
                "fly_hits": 12,
                "line_hits": 6,
                "pop_hits": 1,
                "__h_typed": 39,
                "__h_all": 40,
            }
        ]
    )

    linea = Batting.objects.get(player=p, season=2010)
    assert linea.line_hits == 7  # se queda el del proxy, que es mejor


@pytest.mark.django_db
def test_an_unknown_mlb_id_is_reported_not_swallowed() -> None:
    """El maestro es la autoridad: un jugador que no está ahí no puede desaparecer en silencio.

    Peor que perderse: sus hits tampoco entraban en el cálculo de cobertura, así que un maestro
    incompleto hacía que el CSV pareciera MÁS sano de lo que está (v5 QA-01 / SAB-04).
    """
    from dglweb.stats.staticdata.loaders import BattedBallHitsLoader

    conocido = _player(1)
    loader = BattedBallHitsLoader()
    csv = (
        "mlb_id,season,stat_group,ground_hits,fly_hits,line_hits,pop_hits,h_typed,h_all\n"
        f"{conocido.player_id},2000,batting,5,3,2,1,11,11\n"
        "9999999,2000,batting,4,3,2,1,10,10\n"  # este no existe en el maestro
    )
    filas = engine.read(csv.encode("utf-8"))
    rows, problems = engine.validate(loader, filas, ["player_id", "season", "stat_group"])

    assert len(rows) == 1  # el desconocido no entra a la tabla…
    assert any("no están en el maestro" in p.message for p in problems)  # …pero se reporta
    assert any("9999999" in r for p in problems for r in p.rows)


@pytest.mark.django_db
def test_coverage_is_measured_per_trade_not_just_per_season() -> None:
    """Bateo y pitcheo son universos distintos: promediarlos escondía un oficio roto (v5 SAB-01)."""
    from dglweb.stats.staticdata.loaders import BattedBallHitsLoader

    def fila(group: str, typed: int, todos: int) -> dict[str, Any]:
        return {
            "player_id": 1,
            "season": 2000,
            "stat_group": group,
            "ground_hits": typed,
            "fly_hits": 0,
            "line_hits": 0,
            "pop_hits": 0,
            "__h_typed": typed,
            "__h_all": todos,
        }

    # Bateo sano (1000/1000) y pitcheo roto (10/1000). Juntos dan 50%, pero por separado el roto
    # se ve solo. Antes, el promedio de los dos podía tapar al malo.
    problems = BattedBallHitsLoader().checks([fila("batting", 1000, 1000), fila("pitching", 10, 1000)])

    flojas = [p for p in problems if "por debajo" in p.message]
    assert len(flojas) == 1
    assert flojas[0].rows == ["2000 (pitching): 10 de 1,000 hits con trayectoria (1.0%)"]


@pytest.mark.django_db
def test_post_apply_avisa_de_los_batazos_imposibles_pero_nunca_corta(caplog: Any) -> None:
    """Regla del dueño (2026-07-27): ningún proceso se detiene porque MLB entregue data mala.

    MLB es la autoridad y nosotros consumidores. Si el dato viene descuadrado no hay nada que
    podamos corregir, así que se deja constancia y se sigue. La versión anterior levantaba
    `ValueError` acá dentro, o sea abortaba la transacción del import entero: un descuadre de UN
    batazo en la fuente se convertía en una carga que no entra y alguien depurando un CSV sano.

    Lo que se prueba es lo que NO pasa: que la carga termine y que la fila quede escrita.
    """
    import logging

    from dglweb.players.models import Player
    from dglweb.stats.models import Pitching
    from dglweb.stats.staticdata.loaders import BattedBallHitsLoader
    from tests.test_players import _other_player

    jugador = Player.objects.create(**_other_player(player_id=7, dgl_id="z01", full_name="Un Lanzador"))
    # 60 outs contra 61 BIP, y el CSV trae 5 hits: 65 batazos donde caben 61.
    Pitching.objects.create(
        player=jugador,
        season=2010,
        stint=1,
        balls_in_play=61,
        ground_outs=30,
        fly_outs=20,
        line_outs=5,
        pop_outs=5,
        ground_hits=0,
        fly_hits=0,
        line_hits=0,
        pop_hits=0,
    )
    fila = {
        "player_id": jugador.pk,
        "season": 2010,
        "stat_group": "pitching",
        "ground_hits": 2,
        "fly_hits": 2,
        "line_hits": 1,
        "pop_hits": 0,
    }

    with caplog.at_level(logging.WARNING):
        BattedBallHitsLoader().post_apply([fila])  # no levanta nada

    assert "por encima de BIP" in caplog.text
    assert Pitching.objects.get().ground_hits == 2, "la carga tiene que haber entrado igual"


# ── QA-02: el rebuild deja constancia ANTES de lanzarse ─────────────────────────────────────────


@pytest.mark.django_db
def test_el_rebuild_deja_constancia_antes_de_lanzar_el_hilo() -> None:
    """La ventana que el review v6 señaló: el hilo puede morir antes de registrar nada.

    Sin la fila padre, una carga aplicada cuyo rebuild murió al instante es INDISTINGUIBLE de una
    cuyo rebuild nunca se lanzó. Y no es teórico: con el scheduler pasó exactamente eso — 27 corridas
    fallidas y el log de ingesta limpio, porque ninguna llegó a arrancar.

    Se comprueba lo que importa: que la fila exista tras anotar y ANTES de que corra nada.
    """
    from dglweb.stats import rebuilds
    from dglweb.stats.models import IngestRun

    padre = rebuilds.anotar_lanzamiento(("build_career_totals", "build_leaders"))
    assert padre is not None

    fila = IngestRun.objects.get(pk=padre)
    assert fila.command == rebuilds.PADRE
    assert fila.status == IngestRun.Status.RUNNING
    assert fila.scope == "build_career_totals+build_leaders"
    assert fila.finished_at is None, "una corrida en RUNNING de hace horas es justo la señal buscada"


@pytest.mark.django_db
def test_sin_nada_que_reconstruir_no_se_anota_nada() -> None:
    """Un dataset sin derivados no ensucia el log con una fila que no representa trabajo."""
    from dglweb.stats import rebuilds
    from dglweb.stats.models import IngestRun

    assert rebuilds.anotar_lanzamiento(()) is None
    assert not IngestRun.objects.filter(command=rebuilds.PADRE).exists()


@pytest.mark.django_db
def test_la_fila_padre_se_cierra_al_terminar(monkeypatch: pytest.MonkeyPatch) -> None:
    from dglweb.stats import rebuilds
    from dglweb.stats.models import IngestRun

    padre = rebuilds.anotar_lanzamiento(("build_career_totals",))
    assert padre is not None
    monkeypatch.setattr("django.core.management.call_command", lambda *a, **k: None)

    rebuilds.run(("build_career_totals",), padre)

    fila = IngestRun.objects.get(pk=padre)
    assert fila.status == IngestRun.Status.SUCCESS
    assert fila.finished_at is not None


@pytest.mark.django_db
def test_si_el_rebuild_revienta_la_fila_padre_lo_dice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Que quede en FAILED y con el porqué: el rebuild corre en un hilo, así que esta fila es lo
    único que va a ver quien investigue mañana."""
    from dglweb.stats import rebuilds
    from dglweb.stats.models import IngestRun

    def revienta(*a: object, **k: object) -> None:
        raise RuntimeError("la base se cayó")

    padre = rebuilds.anotar_lanzamiento(("build_career_totals",))
    assert padre is not None
    monkeypatch.setattr("django.core.management.call_command", revienta)

    with pytest.raises(RuntimeError):
        rebuilds.run(("build_career_totals",), padre)

    fila = IngestRun.objects.get(pk=padre)
    assert fila.status == IngestRun.Status.FAILED
    assert "la base se cayó" in fila.detail


# ── El borrador y la pantalla tienen que ser el mismo archivo ────────────────────────────────────


@pytest.mark.django_db
def test_confirmar_desde_una_pantalla_vieja_no_escribe(admin_client: Any) -> None:
    """El caso de las dos pestañas, que NO necesita dos administradores.

    El borrador vive en una sola llave de sesión: subir un CSV nuevo pisa el anterior. Con el mismo
    dataset abierto dos veces —subes, ves algo raro, regeneras el archivo, subes de nuevo— la pestaña
    vieja sigue enseñando las cifras del primero. Confirmar ahí aplicaría el segundo mientras se
    miran los números del primero, que es exactamente lo que la pantalla de comparación existe para
    impedir.

    El escenario de DOS admins que levantaba el review quedó descartado por el dueño (2026-07-28): no
    va a haber un segundo administrador. Este no depende de eso.
    """
    from dglweb.stats.models import StaticDataset

    dataset = StaticDataset.objects.filter(table="seasons_dates").first()
    assert dataset is not None

    respuesta = admin_client.post(reverse("staticdata_confirm", args=[dataset.pk]), {"huella": "unaqueno-existe"})

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("staticdata_upload", args=[dataset.pk])
