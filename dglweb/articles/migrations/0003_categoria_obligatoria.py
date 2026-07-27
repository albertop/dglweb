"""La categoría del artículo pasa a ser obligatoria.

Decisión del dueño (2026-07-27), y la razón no es de forma: un artículo sin categoría **no aparece
bajo ningún filtro del índice**, así que se publica y se pierde. Lo destapó el review v8 (DEV-03).

VAN DOS PASOS Y EN ESTE ORDEN
-----------------------------
Primero se rellenan los que están sin categoría, después se prohíbe el nulo. Al revés, Postgres
rechaza la columna en el mismo instante en que hay una fila con nulo y la migración muere a la mitad
— con el esquema medio cambiado, que es el peor sitio donde quedarse.

A LOS QUE NO TIENEN, SE LES ASIGNA; NO SE BORRAN
------------------------------------------------
El dueño dio permiso para cualquiera de las dos porque acá son artículos de prueba. Se asigna, y no
por pereza: una migración que BORRA filas es una que, el día que alguien la corra sobre otra base
—una copia, un entorno nuevo, el respaldo de producción— se lleva por delante trabajo de verdad sin
preguntar. Asignar es reversible mirando el CMS; borrar no.

La categoría que se pone es la primera por `orden`, que hoy es «Sabermetría». No es una elección
editorial: es un valor de arranque para que el artículo sea visible, y quien escriba lo corrige en un
clic. Medido acá al escribir esto: son cuatro artículos de 31.
"""

from typing import Any

from django.db import migrations, models
import django.db.models.deletion


def poner_categoria(apps: Any, schema_editor: Any) -> None:
    """Rellena los que están sin categoría. Ver la cabecera para el porqué de asignar y no borrar."""
    ArticlePage = apps.get_model("articles", "ArticlePage")
    Categoria = apps.get_model("articles", "Categoria")

    respaldo = Categoria.objects.order_by("orden", "nombre").first()
    if respaldo is None:
        # Sin categorías no hay nada que asignar. Pasa solo en una base a medio armar: las siembra la
        # migración 0002. Se sale sin tocar nada para que el fallo se vea en el paso siguiente —al
        # prohibir el nulo— y no disfrazado de otra cosa acá.
        return
    ArticlePage.objects.filter(categoria__isnull=True).update(categoria=respaldo)


def deshacer(apps: Any, schema_editor: Any) -> None:
    """No se puede deshacer: no hay forma de saber cuáles tenían categoría antes y cuáles no.

    Se deja explícito en vez de dejar que Django asuma que es reversible, para que quien haga
    `migrate` hacia atrás sepa que la asignación se queda puesta.
    """


class Migration(migrations.Migration):
    dependencies = [("articles", "0002_indice_y_categorias")]

    operations = [
        migrations.RunPython(poner_categoria, deshacer),
        migrations.AlterField(
            model_name="articlepage",
            name="categoria",
            field=models.ForeignKey(
                # `PROTECT` y no `SET_NULL`, que era lo que había: sin nulos, `SET_NULL` ni siquiera
                # es legal. Y la semántica correcta es esta — borrar una categoría con artículos
                # dentro tiene que fallar y obligar a reasignarlos, no dejarlos huérfanos.
                on_delete=django.db.models.deletion.PROTECT,
                related_name="articulos",
                to="articles.categoria",
                verbose_name="categoría",
            ),
        ),
    ]
