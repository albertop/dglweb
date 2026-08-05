"""P/IP no se puede rankear antes de 1989: el conteo de lanzamientos está incompleto.

EL SÍNTOMA. La tabla publicaba a Joaquín Andújar liderando 1976 con 6,67 lanzamientos por entrada, y
a Nino Espinosa con 6,05 en 1977. Es un número imposible — no se sacan tres outs con seis
lanzamientos, y la liga de hoy anda por dieciséis.

LA CAUSA. `Pitching.pitches` tiene filas desde 1974, pero hasta 1989 solo trae los juegos que alguien
llegó a anotar; las entradas, en cambio, están completas. El cociente divide un numerador parcial
entre un denominador entero, y sale la mitad de lo que debería. Un dato que falta se nota al mirar la
tabla; uno a medias se publica.

EL ARREGLO. `available_from = 1989`, que es lo que `build_leaders` lee para no rankear nada por
debajo (`_first_season`). La misma llave que ya usan los batazos y los coeficientes.

POR QUÉ HACE FALTA ESTA MIGRACIÓN Y NO BASTA CON EL SEED. `seed_metrics` va por `get_or_create`
justamente para no pisar lo que el dueño ajuste en el Backoffice, así que en una base ya sembrada
—dev, staging y producción— el campo se quedaría en `None` para siempre. Acá se rellena SOLO donde
está vacío, con el mismo criterio: si alguien ya puso un año a mano, ese manda.

Después de aplicarla hay que reconstruir los liderazgos (`build_leaders`); esta migración no los
toca, porque borrar y rehacer 400.000 filas dentro de una migración deja el despliegue colgado.
"""

from django.db import migrations

# `pitches_per_inning` es la única activa hoy. Las otras tres van igual: si mañana se activan desde el
# Backoffice, ya nacen con el piso puesto en vez de repetir este mismo susto.
COLUMNAS = ("pitches", "strikes", "pitches_per_inning", "pitches_per_pa")
DESDE = 1989


def poner_piso(apps, schema_editor):
    Metric = apps.get_model("stats", "Metric")
    Metric.objects.filter(stat_group="pitching", column__in=COLUMNAS, available_from__isnull=True).update(
        available_from=DESDE
    )


def quitar_piso(apps, schema_editor):
    """Solo deshace lo que esta migración pudo haber puesto, no un año escrito a mano."""
    Metric = apps.get_model("stats", "Metric")
    Metric.objects.filter(stat_group="pitching", column__in=COLUMNAS, available_from=DESDE).update(available_from=None)


class Migration(migrations.Migration):
    dependencies = [("stats", "0034_efemeride_participantes")]

    operations = [migrations.RunPython(poner_piso, quitar_piso)]
