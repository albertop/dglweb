"""`dom_players` pasa a ser una tabla de Django, con trece columnas en vez de veintisiete.

La tabla ya existía en Postgres, cargada por fuera de Django. Se DROPEA y se recrea en vez de
hacerle nueve `ALTER TABLE ... DROP COLUMN` porque el dato que tiene no sirve: se va a reemplazar
entero desde la vista de SQL Server, filtrada por edad. Dropear es además lo que deja el esquema
igual en una base existente y en una base nueva, sin depender de qué versión de la tabla había.
"""

from django.db import migrations, models


def _registrar_dataset(apps, schema_editor):
    """La fila del registro, para que la tabla aparezca en «Datos de apoyo» y se pueda cargar.

    Va en la migración y no a mano en cada base: si no, la tabla existe pero no hay por dónde
    subirle el CSV, y eso se descubre el día que hace falta.
    """
    StaticDataset = apps.get_model("stats", "StaticDataset")
    StaticDataset.objects.get_or_create(
        table="dom_players",
        defaults={
            "powershell": "export_dom_players.ps1",
            "csv": "dom_players.csv",
            "mode": "truncate",
            "natural_key": "player_id",
            "comment": (
                "Dominicanos en el sistema profesional, con y sin debut. Sale de la vista "
                "v_dglweb_master_no_debuts (SQL Server), limitada a los nacidos en los últimos 40 "
                "años más los que no tienen fecha de nacimiento. Se reemplaza entera: el dato viejo "
                "no se conserva."
            ),
        },
    )


def _borrar_dataset(apps, schema_editor):
    apps.get_model("stats", "StaticDataset").objects.filter(table="dom_players").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0015_staticdataset_battedballhits'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS dom_players;",
            # Sin marcha atrás: la tabla vieja tenía 27 columnas y un contenido que ya no sirve.
            # Revertir la crearía vacía y con el esquema nuevo, que es lo que hace `CreateModel`.
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='DomPlayer',
            fields=[
                ('player_id', models.PositiveIntegerField(primary_key=True, serialize=False, verbose_name='MLB ID')),
                ('last_name', models.CharField(blank=True, max_length=60, verbose_name='Apellido')),
                ('first_name', models.CharField(blank=True, max_length=60, verbose_name='Nombre')),
                ('full_name', models.CharField(blank=True, max_length=120, verbose_name='Nombre completo')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Fecha de nacimiento')),
                ('birth_place', models.CharField(blank=True, max_length=120, verbose_name='Lugar de nacimiento')),
                ('bats', models.CharField(blank=True, max_length=1, verbose_name='Batea')),
                ('throws', models.CharField(blank=True, max_length=1, verbose_name='Lanza')),
                ('height', models.CharField(blank=True, max_length=8, verbose_name='Estatura')),
                ('weight', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Peso (lb)')),
                ('is_active', models.BooleanField(null=True, verbose_name='Activo')),
                ('is_player', models.BooleanField(null=True, verbose_name='Es jugador')),
                ('is_verified', models.BooleanField(null=True, verbose_name='Verificado')),
            ],
            options={
                'verbose_name': 'dominicano en el sistema',
                'verbose_name_plural': 'dominicanos en el sistema',
                'db_table': 'dom_players',
                'ordering': ['player_id'],
            },
        ),
        migrations.RunPython(_registrar_dataset, _borrar_dataset),
    ]
