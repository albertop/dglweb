"""El motor de carga de datos de apoyo — genérico, sin saber nada de ningún dataset.

Cuatro pasos, en este orden y siempre los cuatro:

    leer  ──▶  validar  ──▶  comparar  ──▶  aplicar
                  │              │              └─ trunca/upsert dentro de UNA transacción
                  │              └─ lo que verá el usuario antes de decidir
                  └─ si falla, no hay botón de confirmar

Lo que este archivo NO sabe: qué columnas tiene un CSV, cómo se llama un jugador, ni qué hace que un
dataset esté sano. Todo eso vive en el `Loader` de cada dataset (ver `loaders.py`), que es lo único
que hay que escribir para sumar una tabla nueva. Ver `docs/DATOS_DE_APOYO.md`.
"""

import csv
import io
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, ClassVar

from django.db import models, transaction


@dataclass
class Problem:
    """Algo que impide cargar. Si hay uno solo, la pantalla no ofrece confirmar."""

    message: str
    rows: list[str] = field(default_factory=list)  # una muestra de las filas culpables


@dataclass
class Comparison:
    """Lo que la pantalla muestra lado a lado antes de escribir nada."""

    problems: list[Problem]
    rows_before: int
    rows_after: int
    columns: list[dict[str, Any]]  # por columna numérica: suma antes, después y % de cambio
    vanishing: list[str]  # claves que están en la tabla y NO en el CSV
    sample: list[dict[str, str]]
    truncating: bool
    seasons_before: str = ""  # el rango cubierto, cuando el dataset tiene columna `season`
    seasons_after: str = ""

    @property
    def can_apply(self) -> bool:
        return not self.problems

    @property
    def rows_delta(self) -> int:
        return self.rows_after - self.rows_before


class Loader:
    """Lo que hay que escribir para sumar un dataset. Todo lo demás ya está hecho.

    Lo mínimo: `table`, `model` y `columns`. `resolve` y `checks` solo si el dataset los necesita.
    """

    table: str  # tiene que coincidir con StaticDataset.table
    model: type[models.Model]
    columns: ClassVar[dict[str, str]]  # columna del CSV -> campo del modelo

    def prepare(self) -> None:
        """Se corre UNA vez antes de leer las filas. Acá van los lookups que si no serían por fila.

        El caso típico: cargar {retro_id: player_id} en memoria. Sin este hook, un `resolve` que
        consulte la base hace una query por línea del CSV.
        """

    def resolve(self, row: dict[str, str]) -> dict[str, Any] | None:
        """Traduce una fila del CSV a kwargs del modelo. `None` descarta la fila.

        El caso típico de sobreescribirlo: el CSV trae un identificador externo (`retro_id`,
        `mlb_id`) y el modelo espera una FK. Por defecto solo mapea `columns` tal cual.
        """
        return {campo: row[col] for col, campo in self.columns.items()}

    def post_apply(self, rows: list[dict[str, Any]]) -> None:
        """Corre DESPUÉS de escribir y DENTRO de la misma transacción. Vacío = no hace falta.

        Para los datasets que corrigen un dato del que otros dependen: cargar los hits por tipo no
        sirve de nada si los coeficientes que salen de ellos siguen calculados con los viejos. Al ir
        dentro de la transacción, o queda todo consistente o no queda nada.
        """

    def checks(self, rows: list[dict[str, Any]]) -> list[Problem]:
        """La prueba de aceptación propia del dataset. Vacío = no tiene ninguna.

        Es donde va el conocimiento que solo aplica a estos datos: que los cuatro tipos de hit sumen
        H, que un salario no sea negativo, que las fechas caigan dentro de la temporada.
        """
        return []


REGISTRY: dict[str, Loader] = {}


def register(loader_cls: type[Loader]) -> type[Loader]:
    """Decorador de clase: instancia el loader y lo deja disponible por nombre de tabla."""
    REGISTRY[loader_cls.table] = loader_cls()
    return loader_cls


# Tope de subida. El CSV real de batazos pesa ~250 KB, así que 20 MB deja muchísimo margen y a la vez
# impide que un archivo enorme —o binario— se decodifique entero en memoria y se guarde en la sesión.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class UnreadableCSVError(ValueError):
    """El archivo no se puede leer siquiera. Se convierte en `Problem`, nunca en un 500."""


def read(raw: bytes) -> list[dict[str, str]]:
    """El CSV crudo a filas. UTF-8 con BOM porque es lo que escribe PowerShell por defecto.

    Un archivo que no sea texto UTF-8 levanta `UnreadableCSVError` en vez de reventar: subir el binario
    equivocado es un error de dedo, y merece un mensaje, no una pantalla de error.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise UnreadableCSVError(
            "El archivo no es texto UTF-8 — puede ser un binario, un Excel sin exportar, "
            f"o venir con otra codificación ({error.reason})."
        ) from error
    return list(csv.DictReader(io.StringIO(text)))


def _key_of(row: dict[str, Any], key_columns: list[str]) -> str:
    return "|".join(str(row.get(column, "")) for column in key_columns)


def validate(
    loader: Loader, raw_rows: list[dict[str, str]], key_columns: list[str]
) -> tuple[list[dict[str, Any]], list[Problem]]:
    """Las validaciones que valen para CUALQUIER dataset, más las propias del loader."""
    problems: list[Problem] = []
    if not raw_rows:
        return [], [Problem("El CSV no trae ninguna fila.")]

    faltantes = [col for col in loader.columns if col not in raw_rows[0]]
    if faltantes:
        return [], [Problem(f"Al CSV le faltan columnas: {', '.join(faltantes)}.")]

    loader.prepare()
    rows: list[dict[str, Any]] = []
    malas: list[str] = []
    for numero, raw in enumerate(raw_rows, start=2):  # 2 = la primera fila de datos, tras el encabezado
        try:
            resolved = loader.resolve(raw)
        except (KeyError, ValueError, TypeError) as error:
            malas.append(f"línea {numero}: {error}")
            continue
        if resolved is not None:
            rows.append(resolved)
    if malas:
        problems.append(Problem(f"{len(malas)} fila(s) no se pudieron leer.", malas[:10]))

    # Unicidad de la clave natural. Corre SIEMPRE, no solo en upsert: con truncate un duplicado no
    # pisa una fila con otra, inserta las dos y deja un registro fantasma que nadie pidió.
    if key_columns:
        repetidas = [k for k, n in Counter(_key_of(r, key_columns) for r in rows).items() if n > 1]
        if repetidas:
            problems.append(
                Problem(
                    f"La clave natural ({', '.join(key_columns)}) se repite en {len(repetidas)} caso(s).",
                    repetidas[:10],
                )
            )

    problems.extend(loader.checks(rows))
    return rows, problems


def compare(
    loader: Loader,
    rows: list[dict[str, Any]],
    key_columns: list[str],
    problems: list[Problem],
    *,
    truncating: bool,
) -> Comparison:
    """Los números lado a lado. No escribe nada. Recibe las filas y los problemas de `validate`."""
    existing = list(loader.model._default_manager.all().values())
    antes = len(existing)
    claves_actuales = {_key_of(e, key_columns) for e in existing} if key_columns else set()
    claves_entrantes = {_key_of(r, key_columns) for r in rows} if key_columns else set()

    # Qué desaparece: solo significa algo con truncate. Con upsert las filas ausentes sobreviven, y
    # callarlo haría leer "no se pierde nada" como si fuera una propiedad del CSV y no del modo.
    vanishing = sorted(claves_actuales - claves_entrantes) if truncating else []
    # Con upsert la tabla crece solo por las claves que no estaban; las repetidas actualizan en sitio.
    despues = len(rows) if truncating else antes + len(claves_entrantes - claves_actuales)

    # Las columnas de la clave natural quedan fuera: son identificadores, no medidas. Sumar `season`
    # daba 9.644.972 —la suma de todos los años— que no significa nada y ensuciaba la tabla.
    fuera = {"id", *key_columns}
    numericas = [
        f.name
        for f in loader.model._meta.fields
        if isinstance(f, models.IntegerField | models.FloatField) and f.name not in fuera
    ]
    columnas = []
    for nombre in numericas:
        suma_antes = sum(float(e.get(nombre) or 0) for e in existing)
        suma_despues = sum(float(r.get(nombre) or 0) for r in rows)
        columnas.append(
            {
                "name": nombre,
                "before": suma_antes,
                "after": suma_despues,
                # La diferencia absoluta va siempre; el porcentaje solo cuando hay contra qué
                # compararlo. Con la tabla vacía el % es división por cero, y mostrar "—" a secas
                # dejaba la fila sin decir nada.
                "delta": suma_despues - suma_antes,
                "change": (suma_despues - suma_antes) / suma_antes * 100 if suma_antes else None,
            }
        )

    def rango(filas: list[dict[str, Any]]) -> str:
        """Las temporadas cubiertas, de un vistazo: que falte un año entero se ve acá."""
        años = sorted({r["season"] for r in filas if r.get("season") is not None})
        if not años:
            return ""
        return f"{años[0]}-{años[-1]} ({len(años)})" if len(años) > 1 else str(años[0])

    return Comparison(
        problems=problems,
        rows_before=antes,
        rows_after=despues,
        columns=columnas,
        vanishing=vanishing,
        sample=[{k: str(v) for k, v in r.items()} for r in rows[:5]],
        truncating=truncating,
        seasons_before=rango(existing),
        seasons_after=rango(rows),
    )


@transaction.atomic
def apply(loader: Loader, rows: list[dict[str, Any]], key_columns: list[str], *, truncating: bool) -> int:
    """Escribe. Atómico: o queda la tabla nueva completa, o la vieja intacta — nunca a medias."""
    manager = loader.model._default_manager
    # Los campos con prefijo `__` son auxiliares de validación (el total contra el que se compara,
    # por ejemplo), no columnas del modelo. Se descartan antes de escribir.
    limpias = [{k: v for k, v in row.items() if not k.startswith("__")} for row in rows]
    if truncating:
        manager.all().delete()
        manager.bulk_create([loader.model(**row) for row in limpias])
    else:
        for row in limpias:
            clave = {column: row[column] for column in key_columns}
            manager.update_or_create(**clave, defaults={k: v for k, v in row.items() if k not in clave})
    loader.post_apply(rows)
    return len(limpias)
