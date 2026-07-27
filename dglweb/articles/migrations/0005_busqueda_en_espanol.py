"""Una configuración de búsqueda de Postgres que entiende español Y no exige tildes.

EL PROBLEMA, MEDIDO
-------------------
Con la configuración por defecto, buscar «gráfico» devolvía dos artículos y buscar «grafico»
devolvía cero. En un sitio en español eso es inaceptable: casi nadie teclea tildes en un buscador, y
menos desde un teléfono. Es exactamente el mismo problema que ya resolvió el buscador de jugadores
—«nunez» no encontraba a Núñez— y se resuelve con la misma pieza, la extensión `unaccent`.

QUÉ HACE ESTA CONFIGURACIÓN
---------------------------
Copia la de español —que trae el stemmer, o sea que «novatos» encuentra «novato»— y le antepone
`unaccent` al diccionario. Así «grafico», «gráfico», «GRÁFICO» y «graficos» caen todas en la misma
raíz.

Se aplica a la INDEXACIÓN y a la CONSULTA a la vez, que es lo que hace que funcione: si solo se
normalizara la consulta, el índice seguiría guardando «gráfico» con tilde y no habría coincidencia.

POR QUÉ NO SE BORRA AL DESHACER
-------------------------------
Al revertir se deja la configuración creada. Borrarla mientras `WAGTAILSEARCH_BACKENDS` la nombra
dejaría el buscador lanzando errores en cada consulta; una configuración de más no molesta a nadie.
"""

from django.db import migrations

NOMBRE = "espanol_sin_tildes"

CREAR = f"""
    CREATE TEXT SEARCH CONFIGURATION {NOMBRE} (COPY = spanish);
    ALTER TEXT SEARCH CONFIGURATION {NOMBRE}
        ALTER MAPPING FOR hword, hword_part, word
        WITH unaccent, spanish_stem;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0004_fuente_obligatoria"),
        # `unaccent` la instala el maestro de jugadores. Se declara la dependencia para que el orden
        # no dependa de la suerte: sin la extensión, el `ALTER MAPPING` de acá falla.
        ("players", "0005_unaccent"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREAR,
            # `IF EXISTS` para que revertir dos veces no reviente. Ver la cabecera: en la práctica no
            # se borra, esto es solo por si alguien desmonta la app entera.
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
