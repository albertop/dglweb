from datetime import timedelta

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone


def home(request: HttpRequest) -> HttpResponse:
    """La portada. La franja de arriba son widgets: los destacados de la jornada y la pizarra."""
    from dglweb.stats import daily, scoreboard

    return render(request, "home.html", {"destacados": daily.portada(), "pizarra": scoreboard.del_dia()})


def pizarra(request: HttpRequest) -> HttpResponse:
    """Solo el widget de la pizarra, para que el navegador lo refresque sin recargar la página.

    Existe porque «en vivo» que solo se actualiza al recargar no está en vivo. Devuelve el mismo
    fragmento que la portada incrusta, así hay una sola plantilla y no dos que se van separando.
    """
    from dglweb.stats import scoreboard

    return render(request, "widgets/_pizarra.html", {"pizarra": scoreboard.del_dia()})


def health(request: HttpRequest) -> JsonResponse:
    """Liveness probe: is this process up? Does NOT touch the DB (used by the container
    healthcheck, so an upstream/DB blip can't mark a healthy web process as unhealthy)."""
    return JsonResponse({"status": "ok"})


def pipeline_health(request: HttpRequest) -> JsonResponse:
    """¿El refresco diario está sano? 200 si sí, 503 si no. Pensado para un monitor EXTERNO.

    Existe por una razón muy concreta: el scheduler estuvo días sin correr y nadie se enteró. Un job
    que revisara «¿corrió el pipeline?» habría corrido en el mismo scheduler roto — por eso la
    vigilancia tiene que vivir afuera, y lo único que necesita de nosotros es un semáforo HTTP.

    Cubre los DOS modos de fallo con una sola respuesta:

    * **Corrió y algo falló** → la última fila no es `success` → 503.
    * **No corrió** → no hay fila reciente → 503. Este es el que ninguna alerta interna puede
      detectar, porque una ausencia no deja rastro que consultar.

    Fuera de temporada devuelve 200: no hay nada que refrescar, y un 503 diario durante el invierno
    enseñaría a ignorar la alerta, que es la peor manera de tener una.

    A diferencia de `/health`, este SÍ toca la base — es su trabajo. `/health` sigue siendo el
    liveness del contenedor y no debe depender de Postgres.
    """
    from django.conf import settings

    from dglweb.stats import season_window
    from dglweb.stats.models import IngestRun

    ventana_horas = settings.PIPELINE_STALE_HOURS
    ventana = season_window.evaluate()

    if not ventana.corre:
        return JsonResponse({"status": "ok", "detalle": f"Fuera de temporada — {ventana.motivo}"})

    desde = timezone.now() - timedelta(hours=ventana_horas)
    ultima = IngestRun.objects.filter(command="refresh_daily", started_at__gte=desde).order_by("-started_at").first()

    if ultima is None:
        return JsonResponse(
            {
                "status": "error",
                "detalle": f"Sin refresco en las últimas {ventana_horas} horas. El scheduler puede estar caído.",
            },
            status=503,
        )
    if ultima.status not in (IngestRun.Status.SUCCESS, IngestRun.Status.SKIPPED):
        return JsonResponse(
            {
                "status": "error",
                "detalle": f"El refresco de {ultima.scope} terminó en «{ultima.status}».",
                "pasos": (ultima.detail or "").splitlines(),
            },
            status=503,
        )
    return JsonResponse(
        {
            "status": "ok",
            "detalle": f"Refresco de {ultima.scope}: {ultima.status}.",
            "filas": ultima.rows_affected,
            "hace_horas": round((timezone.now() - ultima.started_at).total_seconds() / 3600, 1),
        }
    )
