"""Las pantallas de carga: permisos y los tres portazos que dan antes de tocar la tabla.

Es la pieza que reemplaza tablas enteras, así que lo que se prueba acá no es que funcione el camino
feliz sino que los caminos infelices NO terminen en 500 ni en una carga aplicada por error.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import _MonkeyPatchedWSGIResponse
from django.test import Client
from django.urls import reverse

from dglweb.stats.models import StaticDataset

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
