"""Los otros dueños de una efeméride colectiva.

Seis detectores narran gestas de varios a la vez —el jardín entero dominicano, el cuadro entero, los
cinco lanzadores en un juego— y de esas se publica UNA fila, atribuida al más reconocible del grupo.
Sin esta columna, el 15 de septiembre de 1963 aparecía en el perfil de Felipe Alou y no en el de
Mateo ni el de Jesús, que estaban en el mismo jardín.

La alternativa era emitir una fila por participante. Arreglaba el perfil y rompía el calendario: «un
día como hoy» habría repetido la misma frase tres veces seguidas.

393 filas la llevan; las otras 5.409 la tienen vacía.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("stats", "0033_efemeride")]

    operations = [
        migrations.AddField(
            model_name="efemeride",
            name="participantes",
            field=models.CharField(blank=True, max_length=200, verbose_name="Participantes"),
        ),
    ]
