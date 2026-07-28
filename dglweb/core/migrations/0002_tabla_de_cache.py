"""La tabla de la caché compartida.

Va en una migración y no en un paso manual del despliegue a propósito: `createcachetable` es de esas
cosas que se corren una vez, se olvidan, y al desplegar en una máquina nueva el sitio arranca y
revienta en la primera petición que toque la caché — o sea, la primera.

Como migración, la corre el mismo `migrate` que todo lo demás, y si faltara `/ready` lo diría con un
503 ANTES de que el balanceador le mande tráfico.

El porqué de cachear en la base y no en memoria está en `config/settings/base.py`, junto a `CACHES`.
"""

from django.core.management import call_command
from django.db import migrations


def crear(apps, schema_editor):  # noqa: ANN001, ANN201 — la firma es la de Django
    """`createcachetable` sabe qué columnas e índices necesita el backend; no se escriben a mano.

    `database=` para que en la suite —y en cualquier configuración multi-base— la tabla nazca en la
    misma conexión que está migrando y no en la que Django tenga por defecto.
    """
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


def borrar(apps, schema_editor):  # noqa: ANN001, ANN201
    schema_editor.execute("DROP TABLE IF EXISTS dgl_cache")


class Migration(migrations.Migration):
    dependencies = [("core", "0001_roles_editoriales")]

    operations = [migrations.RunPython(crear, borrar)]
