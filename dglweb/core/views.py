import secrets
from datetime import timedelta

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

# Cuántos artículos entran en la portada: uno grande arriba y tres en la fila de abajo, que es la
# retícula que ya estaba dibujada. El corte vive acá y no en la plantilla para que el HTML no tenga
# que contar posiciones del bucle.
PORTADA_DESTACADO = 1
PORTADA_RESTO = 3


def home(request: HttpRequest) -> HttpResponse:
    """La portada. La franja de arriba son widgets: la pizarra, los destacados y los líderes.

    Debajo van los artículos, que desde la Fase 5 son páginas de Wagtail de verdad y no las tarjetas
    de muestra que había escritas a mano. El primero se lleva el espacio grande y los tres siguientes
    la fila de abajo — cuántos van no lo decide la plantilla, lo decide este corte, para que no haya
    que contar `forloop` en el HTML.
    """
    from dglweb.articles.models import ArticlePage
    from dglweb.stats import daily, mlb_leaders, scoreboard

    cuantos = PORTADA_DESTACADO + PORTADA_RESTO
    articulos = list(ArticlePage.objects.live().select_related("categoria").order_by("-fecha", "-pk")[:cuantos])
    return render(
        request,
        "home.html",
        {
            "destacados": daily.portada(),
            "pizarra": scoreboard.del_dia(),
            "lideres": mlb_leaders.portada(),
            "articulo": articulos[0] if articulos else None,
            "articulos": articulos[PORTADA_DESTACADO:],
            "indice": _url_del_indice(),
        },
    )


def _url_del_indice() -> str:
    """La URL de `/articulos/`, preguntada al árbol y no escrita a mano.

    El editor puede renombrar la página o moverla; el enlace de «Ver más artículos» tiene que seguirla
    en vez de apuntar a una ruta que dejó de existir. Devuelve vacío si todavía no hay índice, y la
    plantilla esconde el enlace: mejor sin botón que con un botón a ninguna parte.
    """
    from dglweb.articles.models import ArticleIndexPage

    indice = ArticleIndexPage.objects.live().first()
    return indice.url if indice else ""


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

    EL SEMÁFORO ES PÚBLICO; EL DETALLE NO
    -------------------------------------
    El código —200 o 503— lo ve cualquiera, y así tiene que ser: quien lo lee es un monitor de uptime
    de afuera, y pedirle credenciales a un servicio gratuito es cambiar una fuga menor por un monitor
    que nadie llega a configurar.

    Lo que sí se recorta es el cuerpo. Un anónimo que consultara el endpoint cada minuto aprendía qué
    comandos existen, cuál falló y con qué texto de error — reconocimiento operativo gratis, y con
    el añadido de saber justo cuándo el sitio está sirviendo datos viejos. Ahora recibe el estado y
    nada más (SEC-01 del review v7).
    """
    from django.conf import settings

    from dglweb.stats import season_window
    from dglweb.stats.models import IngestRun

    ventana_horas = settings.PIPELINE_STALE_HOURS
    ventana = season_window.evaluate()
    detallado = _puede_ver_el_detalle(request)

    def respuesta(estado: str, codigo: int = 200, **detalle: object) -> JsonResponse:
        """El estado siempre; lo demás solo para quien puede verlo."""
        return JsonResponse({"status": estado, **(detalle if detallado else {})}, status=codigo)

    if not ventana.corre:
        return respuesta("ok", detalle=f"Fuera de temporada — {ventana.motivo}")

    desde = timezone.now() - timedelta(hours=ventana_horas)
    ultima = IngestRun.objects.filter(command="refresh_daily", started_at__gte=desde).order_by("-started_at").first()

    if ultima is None:
        return respuesta(
            "error",
            503,
            detalle=f"Sin refresco en las últimas {ventana_horas} horas. El scheduler puede estar caído.",
        )
    if ultima.status not in (IngestRun.Status.SUCCESS, IngestRun.Status.SKIPPED):
        return respuesta(
            "error",
            503,
            detalle=f"El refresco de {ultima.scope} terminó en «{ultima.status}».",
            pasos=(ultima.detail or "").splitlines(),
        )
    return respuesta(
        "ok",
        detalle=f"Refresco de {ultima.scope}: {ultima.status}.",
        filas=ultima.rows_affected,
        hace_horas=round((timezone.now() - ultima.started_at).total_seconds() / 3600, 1),
    )


def _puede_ver_el_detalle(request: HttpRequest) -> bool:
    """Quién recibe el cuerpo completo: el personal del Backoffice, y quien traiga el token.

    El token va en `X-Monitor-Token` y no en la URL a propósito: una query string acaba en los logs
    del servidor, en el historial del navegador y en el `Referer` de cualquier enlace que se pulse.

    `compare_digest` y no `==` porque comparar cadenas secretas byte a byte con salida temprana deja
    medir cuántos caracteres se acertaron. Acá el riesgo es remoto, pero el hábito no cuesta nada y
    la excepción es lo que se termina copiando a un sitio donde sí importa.
    """
    from django.conf import settings

    usuario = getattr(request, "user", None)
    if usuario is not None and getattr(usuario, "is_staff", False):
        return True

    esperado = settings.PIPELINE_HEALTH_TOKEN
    # Sin token configurado NADIE anónimo ve detalle: si no, un despiste de configuración lo dejaría
    # todo abierto, que es justo el fallo que este cambio viene a cerrar.
    if not esperado:
        return False
    return secrets.compare_digest(request.headers.get("X-Monitor-Token", ""), esperado)
