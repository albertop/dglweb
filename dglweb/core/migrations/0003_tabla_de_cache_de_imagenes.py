"""La tabla de la caché de imágenes: las tarjetas del comparador.

VA APARTE DE LA COMPARTIDA POR TAMAÑO, no por orden. Una tarjeta pesa 200 KB —270 KB ya serializada—
contra los 34 KB que mide todo lo que guarda la otra junto. `MAX_ENTRIES` se aplica por tabla, así que
compartiéndola un puñado de PNGs expulsaría las entradas de la pizarra, que son baratas y se leen en
todas las páginas. El razonamiento entero está en `config/settings/base.py`, junto a `CACHES`.

Migración por lo mismo que la 0002: `createcachetable` es de esas cosas que se corren una vez, se
olvidan, y al desplegar en una máquina nueva el sitio arranca y revienta en la primera petición que
toque la caché.
"""

from django.core.management import call_command
from django.db import migrations


def crear(apps, schema_editor):  # noqa: ANN001, ANN201 — la firma es la de Django
    """Crea las tablas de TODOS los alias configurados; las que ya existan se dejan como están.

    `database=` para que en la suite —y en cualquier configuración multi-base— la tabla nazca en la
    misma conexión que está migrando y no en la que Django tenga por defecto.
    """
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


def borrar(apps, schema_editor):  # noqa: ANN001, ANN201
    schema_editor.execute("DROP TABLE IF EXISTS dgl_cache_imagenes")


class Migration(migrations.Migration):
    dependencies = [("core", "0002_tabla_de_cache")]

    operations = [migrations.RunPython(crear, borrar)]
