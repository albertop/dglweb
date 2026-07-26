"""Las dos pantallas de la carga: subir y confirmar.

Están separadas a propósito. Subir NO escribe: deja el CSV en sesión y muestra la comparación contra
lo que ya hay. Recién el POST de confirmar toca la tabla, y lo hace en una transacción.

Un truncate a ciegas es irreversible y silencioso — si el CSV vino corto, la tabla queda corta y
nadie se entera hasta que alguien mira una página meses después. Ver `docs/DATOS_DE_APOYO.md`.
"""

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from dglweb.stats.models import StaticDataset
from dglweb.stats.staticdata import engine

_SESSION = "staticdata_upload"


def _blocked(problems: list[engine.Problem], *, truncating: bool) -> engine.Comparison:
    """Una comparación que solo lleva problemas: el archivo ni se llegó a leer."""
    return engine.Comparison(
        problems=problems,
        rows_before=0,
        rows_after=0,
        columns=[],
        vanishing=[],
        sample=[],
        truncating=truncating,
    )


def _is_admin(user: AbstractBaseUser | AnonymousUser) -> bool:
    """Solo administradores. El Backoffice es de staff, pero esto reemplaza tablas enteras."""
    if not user.is_authenticated:
        return False
    grupos = getattr(user, "groups", None)
    es_grupo = bool(grupos and grupos.filter(name="Administrators").exists())
    return bool(getattr(user, "is_superuser", False) or es_grupo)


@user_passes_test(_is_admin, login_url="wagtailadmin_login")
@require_http_methods(["GET", "POST"])
def upload(request: HttpRequest, pk: int) -> HttpResponse:
    """Recibe el CSV y muestra la comparación. No escribe nada."""
    dataset = get_object_or_404(StaticDataset, pk=pk)
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
    truncating = dataset.mode == StaticDataset.Mode.TRUNCATE
    previos: list[engine.Problem] = []

    # El nombre BLOQUEA, no avisa. El control existe para atajar que el CSV de salarios se cargue
    # sobre la tabla de transacciones; si dos datasets tienen columnas parecidas, un aviso que deja
    # confirmar no ataja nada. Un archivo bien nombrado es trivial de conseguir; una tabla
    # reemplazada con el dataset equivocado, no.
    if subido.name != dataset.csv:
        previos.append(engine.Problem(f"El archivo se llama «{subido.name}» y este dataset espera «{dataset.csv}»."))
    if subido.size and subido.size > engine.MAX_UPLOAD_BYTES:
        previos.append(
            engine.Problem(
                f"El archivo pesa {subido.size / 1024 / 1024:.1f} MB y el tope es "
                f"{engine.MAX_UPLOAD_BYTES // 1024 // 1024} MB."
            )
        )
    if previos:  # ni se lee: no hay por qué decodificar en memoria algo que no se va a aplicar
        return render(
            request,
            "staticdata/compare.html",
            {"dataset": dataset, "c": _blocked(previos, truncating=truncating)},
        )

    raw = subido.read()
    try:
        crudas = engine.read(raw)
    except engine.UnreadableCSVError as error:
        return render(
            request,
            "staticdata/compare.html",
            {"dataset": dataset, "c": _blocked([engine.Problem(str(error))], truncating=truncating)},
        )
    rows, problems = engine.validate(loader, crudas, dataset.key_columns)
    comparison = engine.compare(loader, rows, dataset.key_columns, problems, truncating=truncating)

    # El CSV queda en sesión, no en la base: es un borrador de un solo uso y no hay que limpiarlo.
    request.session[_SESSION] = {"pk": pk, "csv": raw.decode("utf-8-sig")}
    return render(request, "staticdata/compare.html", {"dataset": dataset, "c": comparison})


@user_passes_test(_is_admin, login_url="wagtailadmin_login")
@require_http_methods(["POST"])
def confirm(request: HttpRequest, pk: int) -> HttpResponse:
    """Escribe. Revalida antes: la sesión pudo quedar vieja y nadie escribe sobre un `can_apply` viejo."""
    dataset = get_object_or_404(StaticDataset, pk=pk)
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

    # Y recién ahora, con la carga ya comprometida, se rehace lo que se calcula a partir de ella.
    # Antes esto era un paso manual y por lo tanto un paso olvidable: el dato entraba y el sitio
    # seguía sirviendo liderazgos viejos hasta que alguien corría `build_leaders` a mano.
    reconstruyendo = engine.rebuild_in_background(loader)
    return render(
        request,
        "staticdata/done.html",
        {"dataset": dataset, "rows": escritas, "rebuilds": reconstruyendo},
    )
