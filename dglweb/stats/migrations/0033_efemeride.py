"""Efemérides dominicanas: la tabla y su fila en el registro de datos de apoyo.

La tabla la llena el CSV que produce `static_data/efemerides/exportar_efemerides.ps1`, una vez al
año después de que Retrosheet publica. El diseño completo está en `docs/EFEMERIDES.md`.

El `RunPython` siembra la fila de `StaticDataset` en la misma migración que crea el modelo, como en
`0016_domplayer`, `0017_domsalary` y `0018_seasondates`: sin ella la tabla existe pero no aparece en
«Datos de apoyo» y no hay forma de cargarla desde el Backoffice.
"""

from django.db import migrations, models


def _registrar_dataset(apps, schema_editor):
    StaticDataset = apps.get_model("stats", "StaticDataset")
    StaticDataset.objects.get_or_create(
        table="dgl_efemerides",
        defaults={
            "powershell": "efemerides/exportar_efemerides.ps1",
            "csv": "dgl_efemerides.csv",
            "mode": "truncate",
            "natural_key": "tipo,game_id,mlb_id,event_id",
            "comment": (
                "Lo que pasó «un día como hoy» en Grandes Ligas protagonizado por dominicanos. "
                "Sale de 96 detectores contra SQL Server (Retrosheet + Statcast) y trae el texto ya "
                "redactado: el sitio filtra por mes y día, ordena por puntaje y pinta. Se genera una "
                "vez al año, en la offseason, después de que Retrosheet publica — entre publicación y "
                "publicación el pasado no cambia. Se reemplaza entera: no hay nada que reconciliar."
            ),
        },
    )


def _borrar_dataset(apps, schema_editor):
    apps.get_model("stats", "StaticDataset").objects.filter(table="dgl_efemerides").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("stats", "0032_vaciar_window_standout"),
    ]

    operations = [
        migrations.CreateModel(
            name="Efemeride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(max_length=40, verbose_name="Tipo")),
                ("gesta", models.CharField(max_length=120, verbose_name="Gesta")),
                ("etiquetas", models.CharField(blank=True, max_length=200, verbose_name="Etiquetas")),
                ("rol", models.CharField(max_length=12, verbose_name="Rol")),
                ("signo", models.SmallIntegerField(verbose_name="Signo")),
                ("cobertura", models.CharField(max_length=10, verbose_name="Cobertura")),
                ("mlb_id", models.PositiveIntegerField(db_index=True, verbose_name="MLB ID")),
                ("nombre", models.CharField(max_length=60, verbose_name="Jugador")),
                ("fecha", models.DateField(verbose_name="Fecha")),
                ("mes", models.PositiveSmallIntegerField(verbose_name="Mes")),
                ("dia", models.PositiveSmallIntegerField(verbose_name="Día")),
                ("temporada", models.PositiveSmallIntegerField(verbose_name="Temporada")),
                ("anos", models.PositiveSmallIntegerField(verbose_name="Años transcurridos")),
                ("game_id", models.CharField(blank=True, max_length=20, verbose_name="Juego")),
                ("event_id", models.PositiveIntegerField(default=0, verbose_name="Evento")),
                ("game_type", models.CharField(max_length=1, verbose_name="Tipo de juego")),
                ("equipo", models.CharField(blank=True, max_length=5, verbose_name="Equipo")),
                ("equipo_nombre", models.CharField(blank=True, max_length=40, verbose_name="Nombre del equipo")),
                ("rival", models.CharField(blank=True, max_length=5, verbose_name="Rival")),
                ("rival_nombre", models.CharField(blank=True, max_length=40, verbose_name="Nombre del rival")),
                ("en_casa", models.SmallIntegerField(verbose_name="En casa")),
                ("oponente", models.CharField(blank=True, max_length=60, verbose_name="Oponente")),
                ("magnitud", models.FloatField(verbose_name="Magnitud")),
                ("wpa_jugador", models.FloatField(blank=True, null=True, verbose_name="WPA")),
                ("li_max", models.FloatField(blank=True, null=True, verbose_name="Leverage máximo")),
                ("detalle", models.CharField(blank=True, max_length=200, verbose_name="Detalle")),
                ("veces_total", models.PositiveIntegerField(blank=True, null=True, verbose_name="Veces en total")),
                (
                    "jugadores_total",
                    models.PositiveIntegerField(blank=True, null=True, verbose_name="Jugadores distintos"),
                ),
                ("orden", models.PositiveIntegerField(verbose_name="Orden cronológico")),
                ("veces_jugador", models.PositiveIntegerField(verbose_name="Veces de este jugador")),
                ("orden_jugador", models.PositiveIntegerField(verbose_name="Cuál de las suyas")),
                ("rareza", models.FloatField(verbose_name="Rareza")),
                ("puntaje", models.PositiveSmallIntegerField(verbose_name="Puntaje")),
                ("titular", models.TextField(verbose_name="Titular")),
                ("situacion", models.TextField(blank=True, verbose_name="Situación")),
            ],
            options={
                "verbose_name": "efeméride",
                "verbose_name_plural": "efemérides",
                "db_table": "dgl_efemerides",
                "ordering": ["mes", "dia", "-puntaje", "fecha"],
            },
        ),
        migrations.AddConstraint(
            model_name="efemeride",
            constraint=models.UniqueConstraint(
                fields=("tipo", "game_id", "mlb_id", "event_id"), name="uniq_efemeride"
            ),
        ),
        migrations.AddIndex(
            model_name="efemeride",
            index=models.Index(fields=["mes", "dia", "-puntaje"], name="idx_efemeride_dia"),
        ),
        migrations.AddIndex(
            model_name="efemeride",
            index=models.Index(fields=["tipo"], name="idx_efemeride_tipo"),
        ),
        migrations.RunPython(_registrar_dataset, _borrar_dataset),
    ]
