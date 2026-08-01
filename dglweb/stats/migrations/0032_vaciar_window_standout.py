"""Vacía `WindowStandout` porque la migración anterior le cambió el contrato.

ARCH-01 del review v16. `0031` añadió `abridor` con `default=False`, así que **toda fila de pitcheo
anterior nace marcada como relevista**. Y desde ese mismo momento la portada mide a cada lanzador
contra el corte de su clase: +5,7 carreras el abridor, +2,4 el relevista.

El hueco es la ventana entre `migrate` y la siguiente corrida horaria de `build_window_standouts` —
hasta una hora. Ahí un abridor viejo con +4,0 no llegaría a su p85 real pero sí al de relevista, y
saldría en «Quemando la liga» por una comparación que no le toca.

SE BORRA EN VEZ DE ADIVINAR. `WindowStandout` es una foto, no un archivo: no hay nada que conservar,
y la fila no guarda `GS` ni nada de donde deducir si abrió. Un panel que no sale durante una hora es
un problema mucho menor que uno que sale con la gente equivocada — y el job lo rellena solo.

No hay marcha atrás simbólica: al revertir tampoco queda nada que restaurar, así que `reverse` es un
no-op explícito y no `RunPython.noop` a secas, para que se lea que es deliberado.
"""

from django.db import migrations


def vaciar(apps, schema_editor):  # noqa: ANN001, ANN201 — firma fija de Django
    apps.get_model("stats", "WindowStandout").objects.all().delete()


def nada_que_restaurar(apps, schema_editor):  # noqa: ANN001, ANN201 — firma fija de Django
    """Al revertir no se reconstruye nada: la foto la vuelve a escribir el job horario."""


class Migration(migrations.Migration):
    dependencies = [("stats", "0031_windowstandout_abridor_and_more")]

    operations = [migrations.RunPython(vaciar, nada_que_restaurar)]
