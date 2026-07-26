"""La extensión `unaccent` de Postgres, que es lo que hace buscable a medio maestro.

De los 984 nombres, 488 llevan tilde o eñe. Sin esto, quien escribe «nunez» no encuentra a Núñez y
quien escribe «pena» no encuentra a Peña — y exigirle al visitante que sepa dónde va la tilde, o que
tenga eñe en el teclado, es exigirle demasiado.

`unaccent` mapea la eñe a n además de quitar tildes (verificado: `unaccent('Adrián Beltré Núñez')`
devuelve `Adrian Beltre Nunez`), así que las dos exigencias se cubren con la misma pieza.
"""

from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("players", "0004_alter_player_options_player_disabled_reason_and_more")]

    operations = [UnaccentExtension()]
