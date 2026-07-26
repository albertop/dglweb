"""`dom_salaries`: la tabla y su fila en el registro de datos de apoyo.

Tabla nueva —a diferencia de `dom_players`, no existía en Postgres— así que acá no hay nada que
dropear. La fila del registro va en la migración por lo mismo que la anterior: sin ella la tabla
existe pero no hay por dónde subirle el CSV.
"""

from django.db import migrations, models


def _registrar_dataset(apps, schema_editor):
    StaticDataset = apps.get_model("stats", "StaticDataset")
    StaticDataset.objects.get_or_create(
        table="dom_salaries",
        defaults={
            "powershell": "export_dom_salaries.ps1",
            "csv": "dom_salaries.csv",
            "mode": "truncate",
            # El equipo forma parte de la clave: un pelotero traspasado a mitad de año cobra de dos
            # organizaciones, así que su temporada son dos filas. Sin `team_id` en la clave, la
            # validación de duplicados las trataría como un error y bloquearía la carga.
            "natural_key": "player_id,season,team_id",
            "comment": (
                "Salarios por jugador, temporada y equipo. Sale de la vista v_dglweb_salaries "
                "(SQL Server). Se reemplaza entera: no se reconcilia con lo que había."
            ),
        },
    )


def _borrar_dataset(apps, schema_editor):
    apps.get_model("stats", "StaticDataset").objects.filter(table="dom_salaries").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0016_domplayer'),
    ]

    operations = [
        migrations.CreateModel(
            name='DomSalary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('player_id', models.PositiveIntegerField(db_index=True, verbose_name='MLB ID')),
                ('season', models.PositiveSmallIntegerField(verbose_name='Temporada')),
                ('team_id', models.CharField(max_length=3, verbose_name='Equipo (código DGL)')),
                ('league_id', models.CharField(blank=True, max_length=2, verbose_name='Liga (código DGL)')),
                ('age', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Edad')),
                ('salary', models.PositiveBigIntegerField(blank=True, null=True, verbose_name='Salario (USD)')),
            ],
            options={
                'verbose_name': 'salario',
                'verbose_name_plural': 'salarios',
                'db_table': 'dom_salaries',
                'ordering': ['player_id', 'season', 'team_id'],
                'constraints': [models.UniqueConstraint(fields=('player_id', 'season', 'team_id'), name='unique_dom_salary')],
            },
        ),
        migrations.RunPython(_registrar_dataset, _borrar_dataset),
    ]
