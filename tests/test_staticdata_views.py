"""Las pantallas de carga: permisos y los tres portazos que dan antes de tocar la tabla.

Es la pieza que reemplaza tablas enteras, así que lo que se prueba acá no es que funcione el camino
feliz sino que los caminos infelices NO terminen en 500 ni en una carga aplicada por error.
"""

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from dglweb.stats.models import StaticDataset

if TYPE_CHECKING:  # solo existe en los stubs de django-stubs, no en runtime
    from django.test.client import _MonkeyPatchedWSGIResponse

CSV_BUENO = (
    b"mlb_id,season,stat_group,ground_hits,fly_hits,line_hits,pop_hits,h_typed,h_all\n1,2000,batting,5,3,2,1,11,11\n"
)


@pytest.fixture
def dataset(db: None) -> StaticDataset:
    return StaticDataset.objects.create(
        table="dgl_batted_ball_hits",
        powershell="export_batted_ball_hits.ps1",
        csv="batted_ball_hits.csv",
        mode=StaticDataset.Mode.TRUNCATE,
        natural_key="player_id,season,stat_group",
    )


def _admin_client() -> Client:
    user = get_user_model().objects.create_superuser("jefa", "jefa@dgl.do", "x")
    client = Client()
    client.force_login(user)
    return client


def _confirmar(client: Any, dataset: StaticDataset) -> Any:
    """Confirma como lo hace el navegador: devolviendo la huella del borrador que está en sesión.

    Existe desde que `confirm` exige esa huella (2026-07-28). Sin ella, la vista devuelve a la
    comparación en vez de escribir — que es justo lo que protege del caso de las dos pestañas.
    """
    huella = client.session["staticdata_upload"]["huella"]
    return client.post(reverse("staticdata_confirm", args=[dataset.pk]), {"huella": huella})


def _subir(
    client: Client, dataset: StaticDataset, contenido: bytes, nombre: str = "batted_ball_hits.csv"
) -> "_MonkeyPatchedWSGIResponse":
    return client.post(
        reverse("staticdata_upload", args=[dataset.pk]),
        {"archivo": SimpleUploadedFile(nombre, contenido, content_type="text/csv")},
    )


@pytest.mark.django_db
def test_an_anonymous_visitor_is_sent_to_the_login_not_to_a_404(dataset: StaticDataset) -> None:
    """El redirect apuntaba a /accounts/login/, que no existe en este proyecto: daba 404 seco."""
    response = Client().get(reverse("staticdata_upload", args=[dataset.pk]))

    assert response.status_code == 302
    assert "/cms/login/" in response["Location"]


@pytest.mark.django_db
def test_a_logged_in_non_admin_cannot_reach_it(dataset: StaticDataset) -> None:
    """El Backoffice es de staff, pero esto reemplaza tablas enteras: solo administradores."""
    user = get_user_model().objects.create_user("becario", "b@dgl.do", "x", is_staff=True)
    client = Client()
    client.force_login(user)

    assert client.get(reverse("staticdata_upload", args=[dataset.pk])).status_code == 302


@pytest.mark.django_db
def test_a_dataset_that_does_not_exist_is_a_404_not_a_500() -> None:
    assert _admin_client().get(reverse("staticdata_upload", args=[9999])).status_code == 404


@pytest.mark.django_db
def test_the_wrong_file_name_blocks_instead_of_warning(dataset: StaticDataset) -> None:
    """Cargar el CSV de salarios sobre la tabla de transacciones no se ataja con un aviso."""
    response = _subir(_admin_client(), dataset, CSV_BUENO, nombre="salarios.csv")

    assert response.status_code == 200
    assert b"este dataset espera" in response.content
    assert b"Confirmar y reemplazar" not in response.content  # sin botón: no se puede aplicar


@pytest.mark.django_db
def test_a_binary_file_is_a_message_not_a_crash(dataset: StaticDataset) -> None:
    """Subir el archivo equivocado es un error de dedo y merece una explicación, no un 500."""
    response = _subir(_admin_client(), dataset, b"\x89PNG\r\n\x1a\n\x00\xff\xfe")

    assert response.status_code == 200
    assert b"no es texto UTF-8" in response.content
    assert b"Confirmar y reemplazar" not in response.content


@pytest.mark.django_db
def test_an_oversized_file_is_rejected_before_being_read(dataset: StaticDataset) -> None:
    """No se decodifica en memoria algo que de todos modos no se va a aplicar."""
    from dglweb.stats.staticdata import engine

    gigante = b"x" * (engine.MAX_UPLOAD_BYTES + 1)
    response = _subir(_admin_client(), dataset, gigante)

    assert response.status_code == 200
    assert b"el tope es" in response.content


@pytest.mark.django_db
def test_confirming_without_a_pending_upload_goes_back_instead_of_writing(dataset: StaticDataset) -> None:
    response = _admin_client().post(reverse("staticdata_confirm", args=[dataset.pk]))

    assert response.status_code == 302
    assert str(dataset.pk) in response["Location"]


@pytest.mark.django_db
def test_a_load_rebuilds_what_is_derived_from_it_without_being_asked(
    dataset: StaticDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El paso que antes era manual y por eso se olvidaba.

    Cargados los hits, los coeficientes de temporada quedan al día (`post_apply`) pero los totales de
    carrera y los liderazgos siguen siendo los viejos: el sitio servía números vencidos hasta que
    alguien corría `build_leaders` a mano. Se verifica el ORDEN, además, porque los líderes de por
    vida leen los totales de carrera.
    """
    from dglweb.stats.staticdata import engine

    corridos: list[str] = []
    monkeypatch.setattr("django.core.management.call_command", lambda nombre, **_: corridos.append(nombre))

    engine.rebuild(engine.REGISTRY[dataset.table])

    assert corridos == ["build_career_totals", "build_leaders"]


@pytest.mark.django_db
def test_a_dataset_that_derives_nothing_starts_no_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    """No todo dataset alimenta un cálculo: los salarios no mueven ningún ranking."""
    from dglweb.stats.staticdata import engine

    monkeypatch.setattr("threading.Thread", lambda **_: pytest.fail("no debería lanzarse un hilo sin nada que rehacer"))

    assert engine.rebuild_in_background(engine.Loader()) == ""


@pytest.mark.django_db
def test_confirming_launches_the_rebuild_and_says_so(dataset: StaticDataset, monkeypatch: pytest.MonkeyPatch) -> None:
    """El cableado: que la vista lo dispare sola. El olvido estaba acá, no en el motor."""
    from dglweb.players.models import Player
    from dglweb.stats.staticdata import engine
    from tests.test_players import _other_player

    Player.objects.create(**_other_player(player_id=1, dgl_id="x01", full_name="Uno U", pos="1B"))
    lanzados: list[str] = []

    def espiar(loader: engine.Loader) -> str:
        lanzados.append(loader.table)
        return ""

    monkeypatch.setattr(engine, "rebuild_in_background", espiar)

    client = _admin_client()
    _subir(client, dataset, CSV_BUENO)  # deja el CSV validado en sesión
    response = _confirmar(client, dataset)

    assert response.status_code == 200
    assert lanzados == ["dgl_batted_ball_hits"]
