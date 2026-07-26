"""`seasons_dates`: la tabla, su restricción de unicidad y su fila en el registro.

Es el primer dataset de apoyo que se carga por UPSERT y no por truncate, y el primero que además se
edita a mano en el Backoffice. Las dos cosas van juntas: reemplazar la tabla entera borraría
cualquier corrección hecha a mano, así que el modo tiene que respetar lo que ya está.
"""

from django.db import migrations, models


def _registrar_dataset(apps, schema_editor):
    StaticDataset = apps.get_model("stats", "StaticDataset")
    StaticDataset.objects.get_or_create(
        table="seasons_dates",
        defaults={
            "powershell": "export_seasons_dates.ps1",
            "csv": "seasons_dates.csv",
            # Upsert y no truncate: esta tabla se edita a mano en el Backoffice, y truncarla en cada
            # carga borraría esas correcciones. El upsert respeta lo que no viene en el CSV.
            "mode": "upsert",
            "natural_key": "season,sports_id",
            "comment": (
                "Calendario de cada temporada (inicio, fin de serie regular, Juego de Estrellas, "
                "postemporada, fin). Sale de la vista v_dglweb_season_dates (SQL Server). Se carga "
                "por upsert porque también se edita a mano desde el Backoffice."
            ),
        },
    )


def _borrar_dataset(apps, schema_editor):
    apps.get_model("stats", "StaticDataset").objects.filter(table="seasons_dates").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0017_domsalary'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeasonDates',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('season', models.PositiveSmallIntegerField(verbose_name='Temporada')),
                ('sports_id', models.PositiveSmallIntegerField(default=1, help_text='1 = MLB.', verbose_name='Deporte')),
                ('season_start_date', models.DateField(verbose_name='Inicio de temporada')),
                ('reg_season_end_date', models.DateField(blank=True, null=True, verbose_name='Fin de serie regular')),
                ('all_star_game_date', models.DateField(blank=True, null=True, verbose_name='Juego de Estrellas')),
                ('post_season_start_date', models.DateField(blank=True, null=True, verbose_name='Inicio de postemporada')),
                ('season_end_date', models.DateField(verbose_name='Fin de temporada')),
                ('is_active', models.BooleanField(default=False, verbose_name='Temporada en curso')),
            ],
            options={
                'verbose_name': 'calendario de temporada',
                'verbose_name_plural': 'calendarios de temporada',
                'db_table': 'seasons_dates',
                'ordering': ['-season', 'sports_id'],
                'constraints': [models.UniqueConstraint(fields=('season', 'sports_id'), name='unique_season_dates')],
            },
        ),
        migrations.RunPython(_registrar_dataset, _borrar_dataset),
    ]
