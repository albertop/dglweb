"""Las dos pantallas de la carga: subir y confirmar.

Están separadas a propósito. Subir NO escribe: deja el CSV en sesión y muestra la comparación contra
lo que ya hay. Recién el POST de confirmar toca la tabla, y lo hace en una transacción.

Un truncate a ciegas es irreversible y silencioso — si el CSV vino corto, la tabla queda corta y
nadie se entera hasta que alguien mira una página meses después. Ver `docs/DATOS_DE_APOYO.md`.
"""

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from dglweb.stats.models import StaticDataset
from dglweb.stats.staticdata import engine

_SESSION = "staticdata_upload"


def _is_admin(user: AbstractBaseUser | AnonymousUser) -> bool:
    """Solo administradores. El Backoffice es de staff, pero esto reemplaza tablas enteras."""
    if not user.is_authenticated:
        return False
    grupos = getattr(user, "groups", None)
    es_grupo = bool(grupos and grupos.filter(name="Administrators").exists())
    return bool(getattr(user, "is_superuser", False) or es_grupo)


@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def upload(request: HttpRequest, pk: int) -> HttpResponse:
    """Recibe el CSV y muestra la comparación. No escribe nada."""
    dataset = StaticDataset.objects.get(pk=pk)
    loader = engine.REGISTRY.get(dataset.table)
    if loader is None:
        return render(
            request,
            "staticdata/upload.html",
            {"dataset": dataset, "sin_loader": True},
        )

    if request.method == "GET" or "archivo" not in request.FILES:
        return render(request, "staticdata/upload.html", {"dataset": dataset})

    # `.get()` devuelve un solo archivo tipado; `request.FILES[...]` puede ser una lista para mypy.
    subido = request.FILES.get("archivo")
    if subido is None:
        return render(request, "staticdata/upload.html", {"dataset": dataset})
    # El nombre esperado ataja el error obvio: cargar el CSV de salarios sobre la tabla de
    # transacciones es un error de una sola vez y de consecuencias largas.
    aviso_nombre = (
        None if subido.name == dataset.csv else f"El archivo se llama «{subido.name}» y se esperaba «{dataset.csv}»."
    )

    raw = subido.read()
    truncating = dataset.mode == StaticDataset.Mode.TRUNCATE
    rows, problems = engine.validate(loader, engine.read(raw), dataset.key_columns)
    comparison = engine.compare(loader, rows, dataset.key_columns, problems, truncating=truncating)

    # El CSV queda en sesión, no en la base: es un borrador de un solo uso y no hay que limpiarlo.
    request.session[_SESSION] = {"pk": pk, "csv": raw.decode("utf-8-sig")}
    return render(
        request,
        "staticdata/compare.html",
        {"dataset": dataset, "c": comparison, "aviso_nombre": aviso_nombre},
    )


@user_passes_test(_is_admin)
@require_http_methods(["POST"])
def confirm(request: HttpRequest, pk: int) -> HttpResponse:
    """Escribe. Revalida antes: la sesión pudo quedar vieja y nadie escribe sobre un `can_apply` viejo."""
    dataset = StaticDataset.objects.get(pk=pk)
    guardado = request.session.get(_SESSION)
    loader = engine.REGISTRY.get(dataset.table)
    if loader is None or not guardado or guardado.get("pk") != pk:
        return redirect("staticdata_upload", pk=pk)

    rows, problems = engine.validate(loader, engine.read(guardado["csv"].encode("utf-8")), dataset.key_columns)
    if problems:  # se revalida: confirmar no es una firma en blanco sobre lo que se vio antes
        truncating = dataset.mode == StaticDataset.Mode.TRUNCATE
        comparison = engine.compare(loader, rows, dataset.key_columns, problems, truncating=truncating)
        return render(request, "staticdata/compare.html", {"dataset": dataset, "c": comparison})

    escritas = engine.apply(loader, rows, dataset.key_columns, truncating=dataset.mode == StaticDataset.Mode.TRUNCATE)
    StaticDataset.objects.filter(pk=pk).update(
        last_update=timezone.now(), last_rows=escritas, last_user=request.user.get_username()
    )
    request.session.pop(_SESSION, None)
    return render(request, "staticdata/done.html", {"dataset": dataset, "rows": escritas})
