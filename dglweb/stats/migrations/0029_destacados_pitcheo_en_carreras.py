"""Borra los destacados de PITCHEO guardados con la unidad vieja.

POR QUÉ HACE FALTA UNA MIGRACIÓN Y NO BASTA UN COMANDO
------------------------------------------------------
Hasta el 2026-07-29 el `valor` de un destacado de pitcheo era un **Game Score** —números de 40 a 106—
y desde ese día son **carreras sobre el promedio**, como los de bateo (SAB-02 del review v12).

Las dos cosas viven en la misma columna y nada las distingue. Con el piso nuevo en 0,82 carreras,
**una fila vieja de 51 puntos lo pasa sin despeinarse y encabeza la lista**, porque 51 es mayor que
cualquier valor de bateo real. O sea: la portada saldría con todos los lanzadores viejos arriba, con
cara de dato bueno.

Se podría arreglar corriendo `build_daily_standouts --fecha` a mano después de desplegar. Pero eso es
justo la clase de paso que se olvida, y el fallo no avisa: la página carga perfecta y el orden está
mal. Una migración corre sola, en el despliegue, sin que nadie tenga que acordarse.

SOLO EL PITCHEO
---------------
El bateo NO se toca: su unidad no cambió —siempre fueron carreras por pesos lineales— y solo se movió
el piso, que se aplica al leer. Borrar esas filas sería tirar dato bueno.

QUÉ VE EL VISITANTE MIENTRAS TANTO
-----------------------------------
El widget sigue enseñando a los bateadores. Los lanzadores vuelven solos cuando corra el job horario
—`build_daily_standouts --fecha-hoy`, cada hora— y para recuperar jornadas anteriores basta con
`manage.py build_daily_standouts --fecha 2026-07-28 --force`.

Un hueco temporal es preferible a un orden equivocado: lo primero se nota y se arregla, lo segundo se
lee como si fuera cierto.

NO TIENE VUELTA ATRÁS, y es correcto que no la tenga: el dato de vuelta serían Game Scores metidos en
una columna que ahora significa carreras. `RunPython.noop` deja el `migrate --fake` limpio sin
prometer una reversión que no existe.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def borrar_pitcheo(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    DailyStandout = apps.get_model("stats", "DailyStandout")
    borradas, _ = DailyStandout.objects.filter(grupo="pitcheo").delete()
    if borradas:
        print(f"  destacados de pitcheo borrados (unidad vieja): {borradas}")


class Migration(migrations.Migration):
    dependencies = [("stats", "0028_juegos_por_equipo")]

    operations = [migrations.RunPython(borrar_pitcheo, migrations.RunPython.noop)]
