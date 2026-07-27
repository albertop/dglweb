"""El flujo editorial: borrador → revisión → publicado, y quién puede hacer cada paso.

Es el «Done when» de la Fase 5 y la regla que lo sostiene es una sola: **el que escribe no puede
publicarse solo**. Si pudiera, la revisión sería voluntaria, y una revisión voluntaria es ninguna.

Se prueba a nivel de permisos y de estado del workflow, no clicando el CMS. Lo que puede romperse
acá no es que Wagtail dibuje bien un botón —eso es problema suyo— sino que alguien, arreglando otra
cosa, le dé `publish_page` al grupo equivocado o mueva los permisos de sitio. Eso no se ve en la
pantalla hasta que un artículo a medio escribir aparece publicado.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, Group
from wagtail.models import Page, Workflow, WorkflowState

from dglweb.articles.models import ArticlePage
from dglweb.core.roles import ADMINISTRADORES, EDITORES, REDACTORES
from tests.test_articles import _articulo, _indice_de_articulos

# El modelo de usuario en tiempo de ejecución, para crear gente de prueba. Las anotaciones usan
# `AbstractBaseUser` porque `get_user_model()` devuelve una variable y mypy no la acepta como tipo.
Usuario = get_user_model()


def _usuario(nombre: str, grupo: str) -> AbstractBaseUser:
    persona = Usuario.objects.create_user(username=nombre, password="da-igual")
    persona.groups.add(Group.objects.get(name=grupo))
    return persona


@pytest.fixture
def redactor(db: None) -> AbstractBaseUser:
    return _usuario("un-redactor", REDACTORES)


@pytest.fixture
def editor(db: None) -> AbstractBaseUser:
    return _usuario("un-editor", EDITORES)


def _enviar_a_revision(articulo: ArticlePage, quien: AbstractBaseUser) -> tuple[ArticlePage, WorkflowState]:
    """Deja el artículo sin publicar y arranca el workflow, como hace el botón del CMS.

    La revisión se guarda ANTES y la página se relee de la base: el workflow cuelga su tarea de la
    última revisión, y el objeto que tenemos en memoria no la conoce hasta releerlo. Sin eso, arranca
    con `revision_id` en nulo y Postgres lo rechaza — que es exactamente lo que pasó al escribir
    estos tests.
    """
    articulo.live = False
    articulo.save()
    articulo.save_revision(user=quien)
    fresco = ArticlePage.objects.get(pk=articulo.pk)
    return fresco, Workflow.objects.first().start(fresco, quien)


# ── Los tres roles existen y no son lo mismo ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_three_roles_exist_out_of_the_box() -> None:
    """Montados por migración y no a mano: un sitio recién levantado tiene que traerlos puestos.

    Que la seguridad dependa de que alguien se acuerde de correr algo es no tenerla.
    """
    assert set(Group.objects.values_list("name", flat=True)) >= {REDACTORES, EDITORES, ADMINISTRADORES}


@pytest.mark.django_db
def test_a_writer_cannot_publish(redactor: AbstractBaseUser) -> None:
    """La regla que sostiene todo lo demás."""
    indice = _indice_de_articulos()
    articulo = _articulo(indice, "Un borrador")

    permisos = articulo.permissions_for_user(redactor)

    assert permisos.can_edit() is True
    assert permisos.can_publish() is False


@pytest.mark.django_db
def test_an_editor_can_publish(editor: AbstractBaseUser) -> None:
    indice = _indice_de_articulos()
    articulo = _articulo(indice, "Un borrador")

    assert articulo.permissions_for_user(editor).can_publish() is True


@pytest.mark.django_db
def test_nobody_writes_outside_the_articles_section(redactor: AbstractBaseUser, editor: AbstractBaseUser) -> None:
    """Los permisos cuelgan de «Artículos», no de la raíz.

    Venían sobre la raíz del árbol, o sea sobre el sitio entero. Un redactor no tiene por qué poder
    renombrar la página que contiene todo lo demás.
    """
    raiz = Page.objects.get(depth=2)

    assert raiz.permissions_for_user(redactor).can_edit() is False
    assert raiz.permissions_for_user(editor).can_edit() is False


# ── El flujo ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_submitting_leaves_the_article_unpublished_and_waiting(redactor: AbstractBaseUser) -> None:
    """Enviar a revisión NO publica. Suena obvio y es exactamente lo que hay que garantizar."""
    indice = _indice_de_articulos()
    articulo = _articulo(indice, "A revision")

    articulo, _ = _enviar_a_revision(articulo, redactor)

    estado = WorkflowState.objects.get(object_id=str(articulo.pk))
    assert estado.status == WorkflowState.STATUS_IN_PROGRESS
    assert Page.objects.get(pk=articulo.pk).live is False


@pytest.mark.django_db
def test_the_approval_task_is_addressed_to_the_editors(redactor: AbstractBaseUser) -> None:
    """Cuando un redactor envía, le tiene que llegar a alguien. Sin esta atadura el artículo se
    queda esperando a un grupo vacío y nadie se entera de que hay algo por revisar."""
    from wagtail.models import GroupApprovalTask

    indice = _indice_de_articulos()
    articulo = _articulo(indice, "Esperando")
    _enviar_a_revision(articulo, redactor)

    tarea = GroupApprovalTask.objects.get()
    assert list(tarea.groups.values_list("name", flat=True)) == [EDITORES]


@pytest.mark.django_db
def test_an_editor_approving_publishes_it(redactor: AbstractBaseUser, editor: AbstractBaseUser) -> None:
    """El final del camino: aprobado por quien puede, el artículo sale."""
    indice = _indice_de_articulos()
    articulo = _articulo(indice, "Por aprobar")

    articulo, estado = _enviar_a_revision(articulo, redactor)
    estado.current_task_state.approve(user=editor)

    assert Page.objects.get(pk=articulo.pk).live is True
    assert WorkflowState.objects.get(pk=estado.pk).status == WorkflowState.STATUS_APPROVED


# ── El Backoffice no es para escribir ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_only_administrators_reach_the_support_data_upload(
    redactor: AbstractBaseUser, editor: AbstractBaseUser
) -> None:
    """Reemplaza tablas enteras: un truncate a ciegas es irreversible y silencioso.

    La comprobación buscaba un grupo «Administrators» que no existía, así que en la práctica solo
    pasaban los superusuarios: no fallaba, simplemente no dejaba pasar a nadie. Ahora el nombre sale
    de `core.roles` y el grupo existe de verdad, que es lo que hace la prueba significativa.
    """
    from dglweb.stats.staticdata.views import _is_admin

    admin = _usuario("un-admin", ADMINISTRADORES)

    assert _is_admin(redactor) is False
    assert _is_admin(editor) is False
    assert _is_admin(admin) is True


@pytest.mark.django_db
def test_a_writer_does_not_even_see_the_backoffice_menu(redactor: AbstractBaseUser) -> None:
    """No basta con que la carga esté cerrada: el menú entero tiene que no estar para un redactor.

    Se le pregunta al menú de Wagtail, que es quien decide qué se dibuja, y no se busca la palabra
    en el HTML: la barra lateral la monta React con sus datos en un bloque aparte, así que un
    `"Backoffice" not in html` da verdadero también cuando la petición falló — que es como pasó la
    primera versión de este test, por la razón equivocada.

    Que el menú no salga es consecuencia de los permisos, no una regla suelta: los roles editoriales
    no tienen ninguno sobre los modelos del Backoffice, y Wagtail esconde lo que no se puede tocar.
    """
    from django.test import RequestFactory
    from wagtail.admin.menu import admin_menu

    admin = _usuario("otro-admin", ADMINISTRADORES)

    def menus(quien: AbstractBaseUser) -> list[str]:
        peticion = RequestFactory().get("/cms/")
        peticion.user = quien  # type: ignore[assignment]  # el request de prueba no lleva el tipo estrecho
        return [item.label for item in admin_menu.menu_items_for_request(peticion)]

    assert "Backoffice" not in menus(redactor)
    assert "Backoffice" in menus(admin)
