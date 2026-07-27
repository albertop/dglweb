"""Los tres roles del CMS, montados de fábrica.

Wagtail crea de arranque `Editors` y `Moderators` con el reparto correcto: el primero NO tiene
`publish_page`, así que ya está obligado a mandar a revisión, y la tarea de aprobación apunta al
segundo. Lo que hace esta migración es terminar el trabajo, y son cuatro cosas:

1. **Los nombres, en español.** Se ven en la pantalla de un CMS entero en español que van a usar
   periodistas. Ver `core/roles.py` para la equivalencia con los nombres de Wagtail — no es
   literal a propósito.
2. **Un tercer rol, `Administradores`.** No existía, y sin embargo la guarda de las cargas de datos
   de apoyo ya lo buscaba por nombre: en la práctica solo pasaban los superusuarios. Funcionaba,
   pero por accidente.
3. **Los permisos, acotados a la sección de artículos.** Venían sobre `Root`, o sea sobre el árbol
   entero. Un redactor no tiene por qué poder tocar la raíz del sitio.
4. **La página raíz, con nombre.** Seguía llamándose «Welcome to your new Wagtail site!». No se ve
   en el sitio público —la portada la sirve una vista de Django— pero en el CMS es el primer cartel
   que ve quien entra a escribir, y esconde la sección de artículos detrás de un nombre que no
   significa nada.

Es una migración y no un comando a mano porque un sitio recién levantado tiene que quedar con sus
roles puestos. Que la seguridad dependa de que alguien se acuerde de correr algo es no tenerla.
"""

from typing import Any

from django.db import migrations

from dglweb.core.roles import ADMINISTRADORES, EDITORES, REDACTORES

# Cómo se llamaban en Wagtail. Se buscan por el nombre viejo para renombrarlos en vez de crear otros
# —si no, quedarían cinco grupos y los permisos repartidos entre ellos.
VIEJO_REDACTORES = "Editors"
VIEJO_EDITORES = "Moderators"

NOMBRE_DEL_SITIO = "Dominicanos en Grandes Ligas"

# Lo que un administrador puede hacer sobre las páginas: todo.
PERMISOS_DE_PAGINA = ("add_page", "change_page", "publish_page", "lock_page", "unlock_page")

# Las apps cuyos modelos vive en el Backoffice. Un administrador los gestiona enteros; a un redactor
# no le aparece siquiera el menú, porque Wagtail esconde lo que no se puede tocar.
APPS_DEL_BACKOFFICE = ("players", "stats", "articles")


def _asegurar_permisos(apps: Any) -> None:
    """Crea los permisos de los modelos si todavía no existen.

    Hace falta y no es paranoia. Django NO crea las filas de `auth_permission` durante las
    migraciones: las crea una señal `post_migrate` que corre CUANDO TODAS TERMINARON. Así que una
    migración de datos que reparte permisos por nombre, en una base recién creada, no encuentra
    ninguno y deja el grupo vacío — sin fallar, que es lo peor.

    En la base de desarrollo no se notaba: los permisos llevaban semanas ahí de migraciones
    anteriores. Se vio en la de tests, que nace de cero en cada corrida, y de ahí a producción —que
    también nace de cero— había un paso.
    """
    from django.apps import apps as registro
    from django.contrib.auth.management import create_permissions

    for etiqueta in APPS_DEL_BACKOFFICE:
        configuracion = registro.get_app_config(etiqueta)
        configuracion.models_module = configuracion.models_module or True
        create_permissions(configuracion, apps=apps, verbosity=0)


def montar(apps: Any, schema_editor: Any) -> None:
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Page = apps.get_model("wagtailcore", "Page")
    GroupPagePermission = apps.get_model("wagtailcore", "GroupPagePermission")

    _asegurar_permisos(apps)

    # --- 1 y 2: los nombres ---
    for viejo, nuevo in ((VIEJO_REDACTORES, REDACTORES), (VIEJO_EDITORES, EDITORES)):
        grupo = Group.objects.filter(name=viejo).first()
        if grupo and not Group.objects.filter(name=nuevo).exists():
            grupo.name = nuevo
            grupo.save(update_fields=["name"])

    admins, _ = Group.objects.get_or_create(name=ADMINISTRADORES)
    admins.permissions.set(
        Permission.objects.filter(content_type__app_label__in=(*APPS_DEL_BACKOFFICE, "wagtailimages", "wagtaildocs"))
        | Permission.objects.filter(codename="access_admin")
    )

    # --- 3: los permisos de página, acotados a la sección de artículos ---
    articulos = Page.objects.filter(slug="articulos", depth=3).first()
    raiz = Page.objects.filter(depth=2).order_by("path").first()
    if articulos is None or raiz is None:
        return  # base a medio armar; la migración de `articles` crea el índice

    reparto = {
        REDACTORES: (articulos, ("add_page", "change_page")),
        EDITORES: (articulos, PERMISOS_DE_PAGINA),
        ADMINISTRADORES: (raiz, PERMISOS_DE_PAGINA),
    }
    for nombre, (pagina, codigos) in reparto.items():
        grupo = Group.objects.filter(name=nombre).first()
        if grupo is None:
            continue
        GroupPagePermission.objects.filter(group=grupo).delete()
        for codigo in codigos:
            permiso = Permission.objects.filter(codename=codigo, content_type__app_label="wagtailcore").first()
            if permiso:
                GroupPagePermission.objects.create(group=grupo, page=pagina, permission=permiso)

    # --- 4: la raíz, con nombre ---
    if raiz.title.startswith("Welcome to your new Wagtail site"):
        raiz.title = NOMBRE_DEL_SITIO
        raiz.draft_title = NOMBRE_DEL_SITIO
        raiz.save(update_fields=["title", "draft_title"])


def desmontar(apps: Any, schema_editor: Any) -> None:
    """Devuelve los nombres de Wagtail. Los permisos NO se restauran: se quedan como estén, porque
    adivinar un reparto anterior es peor que dejar el actual a la vista."""
    Group = apps.get_model("auth", "Group")
    for nuevo, viejo in ((REDACTORES, VIEJO_REDACTORES), (EDITORES, VIEJO_EDITORES)):
        grupo = Group.objects.filter(name=nuevo).first()
        if grupo:
            grupo.name = viejo
            grupo.save(update_fields=["name"])


class Migration(migrations.Migration):
    initial = True

    # `players` y `stats` están acá aunque esta migración no toque sus tablas. `create_permissions`
    # busca la app en el registro HISTÓRICO —el que refleja las migraciones ya aplicadas en este
    # punto— y si no la encuentra se rinde en silencio, sin crear nada y sin avisar. Sin estas dos
    # líneas el grupo de administradores nacía sin un solo permiso sobre el Backoffice.
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("articles", "0002_indice_y_categorias"),
        ("players", "0006_alter_player_options_alter_player_managers"),
        ("stats", "0026_siglas_en_ingles_modelos"),
        ("wagtailcore", "0097_baselogentry_uuid_action_timestamp_indexes"),
    ]

    operations = [migrations.RunPython(montar, desmontar)]
