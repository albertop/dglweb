import logging
import secrets
from datetime import timedelta
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from dglweb.core import legal

logger = logging.getLogger(__name__)

# Cuántos artículos entran en la portada: uno grande arriba y tres en la fila de abajo, que es la
# retícula que ya estaba dibujada. El corte vive acá y no en la plantilla para que el HTML no tenga
# que contar posiciones del bucle.
PORTADA_DESTACADO = 1
PORTADA_RESTO = 3

# Los jobs que corren cada hora y alimentan módulos que el visitante VE. Se vigilan aparte del
# refresco diario porque fallan distinto: el diario se nota al día siguiente, y estos dejan la
# portada enseñando dato viejo con cara de fresco. Ver `_horarios_atrasados()`.
HORARIOS = ("build_mlb_leaders", "update_roster_moves")

# Cuánto se cachea la respuesta ANÓNIMA de `/health/pipeline`. Medio minuto: un monitor externo que
# pregunta cada minuto sigue detectando un fallo en el siguiente sondeo, y mientras tanto ninguna
# petición pública toca la base. La respuesta detallada no se cachea — ver la vista.
SEGUNDOS_SEMAFORO = 30
CLAVE_SEMAFORO = "health:pipeline"


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


def documento_legal(request: HttpRequest, documento: str) -> HttpResponse:
    """Las tres páginas legales: privacidad, términos y cookies.

    Son plantillas del repositorio y no páginas del CMS, a diferencia de los artículos, y la razón
    no es pereza:

    - **No pueden desaparecer.** Una página del CMS se despublica con un clic, y quedarse sin aviso
      de privacidad publicado es un incumplimiento, no un fallo de maquetación.
    - **El historial tiene que ser un diff.** Ante un reclamo, lo que importa es qué decía el texto
      tal día. `git log` responde eso mejor que las revisiones del CMS, y con quién lo cambió.
    - **La URL es una promesa.** Se enlaza desde el pie de todas las páginas y —cuando lleguen— en
      el alta de los anunciantes. Que un editor pueda moverla sin querer es un riesgo sin ninguna
      ventaja a cambio.
    """
    if documento not in legal.PAGINAS:
        raise Http404(documento)
    return render(
        request,
        f"legal/{documento}.html",
        {"titulo": legal.PAGINAS[documento], "legal": legal, "documento": documento},
    )


def contacto(request: HttpRequest) -> HttpResponse:
    """La página de contacto.

    Es una dirección de correo y no un formulario, y es una decisión, no una etapa intermedia. Un
    formulario exige un servidor de salida configurado, defensa contra robots y un sitio donde
    guardar lo que llega; mientras alguna de las tres cosas falle, el formulario acepta el mensaje,
    dice «gracias» y lo tira — que es el peor fallo posible en una página de contacto, porque quien
    escribe se queda esperando una respuesta que nunca se pidió.

    Un `mailto` no puede fallar en silencio: o se abre el correo del visitante, o ve la dirección y
    la copia.
    """
    return render(request, "contacto.html", {"legal": legal})


def health(request: HttpRequest) -> JsonResponse:
    """Liveness probe: is this process up? Does NOT touch the DB (used by the container
    healthcheck, so an upstream/DB blip can't mark a healthy web process as unhealthy)."""
    return JsonResponse({"status": "ok"})


def ready(request: HttpRequest) -> JsonResponse:
    """Readiness: ¿este proceso puede ATENDER, o solo está encendido? 200 si sí, 503 si no.

    LA DIFERENCIA CON `/health`, QUE ES TODA LA GRACIA
    --------------------------------------------------
    `/health` responde «el proceso vive» y **no toca la base a propósito**: es lo que mira el
    healthcheck del contenedor, y si consultara la base, un parpadeo de Postgres reiniciaría un
    proceso web perfectamente sano. Empeorar una caída de la base tirando además la aplicación es el
    fallo clásico de mezclar las dos preguntas en un endpoint.

    Esto responde la otra: si le mandara tráfico ahora mismo, ¿lo serviría? Y ahí sí hay que tocar la
    base, porque un proceso arriba con la base caída devuelve 500 en todas las páginas.

    QUÉ COMPRUEBA, Y POR QUÉ ESAS DOS COSAS
    ---------------------------------------
    1. **Que la base contesta.** Un `SELECT 1`, que es la comprobación más barata que existe.
    2. **Que no faltan migraciones.** Este es el que de verdad se gana el endpoint: es el fallo del
       despliegue —imagen nueva, `migrate` que no corrió— y no se ve desde fuera. La base contesta,
       el proceso arranca, la portada carga… y revienta la primera página que toque la columna nueva.
       Un `SELECT 1` diría que todo está bien.

    NO SE CACHEA, y es deliberado: la respuesta cacheada de un readiness es una foto vieja, o sea
    exactamente lo contrario de lo que se le pregunta.
    """
    from django.db import DEFAULT_DB_ALIAS, connections
    from django.db.migrations.executor import MigrationExecutor

    try:
        conexion = connections[DEFAULT_DB_ALIAS]
        with conexion.cursor() as cursor:
            cursor.execute("SELECT 1")
        # `migration_plan` con los objetivos del grafo devuelve lo que FALTARÍA por aplicar. Vacío es
        # estar al día; cualquier cosa dentro es una migración que este proceso necesita y no tiene.
        ejecutor = MigrationExecutor(conexion)
        pendientes = ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes())
    # Se atrapa `Exception` a secas: acá cualquier fallo significa «no listo», sin matices.
    except Exception as error:
        # El DETALLE solo para quien puede verlo. El mensaje de un fallo de conexión trae host,
        # puerto, usuario y nombre de base — o sea el mapa de la infraestructura, servido a quien
        # golpee la URL justo durante una caída, que es cuando menos se está mirando.
        #
        # El mismo guardia que `/health/pipeline`, y que existía desde el 2026-07-27: este endpoint
        # nació al día siguiente y no lo aplicó. Lo destapó el review v9 (SEC-01).
        logger.error("readiness: %s: %s", type(error).__name__, error)
        cuerpo: dict[str, Any] = {"status": "error"}
        if _puede_ver_el_detalle(request):
            cuerpo["detalle"] = f"{type(error).__name__}: {error}"
        return JsonResponse(cuerpo, status=503)

    if pendientes:
        # Los NOMBRES también son detalle: dicen qué apps corren dentro y a qué ritmo se despliega.
        # El número va público porque es el semáforo —un monitor necesita saber que falta algo— y no
        # dice nada que la propia respuesta 503 no diga ya.
        faltan: list[str] = [f"{migracion.app_label}.{migracion.name}" for migracion, _ in pendientes]
        logger.error("readiness: %d migración(es) pendiente(s): %s", len(faltan), ", ".join(faltan[:20]))
        detalle: dict[str, Any] = {"status": "migraciones pendientes", "pendientes": len(faltan)}
        if _puede_ver_el_detalle(request):
            detalle["faltan"] = faltan[:20]
        return JsonResponse(detalle, status=503)

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
    from django.core.cache import cache

    from dglweb.stats import season_window
    from dglweb.stats.models import IngestRun

    ventana_horas = settings.PIPELINE_STALE_HOURS
    detallado = _puede_ver_el_detalle(request)

    # El semáforo anónimo se cachea; el detallado NO. Son dos lectores distintos: el monitor externo
    # pregunta cada minuto y le sirve una respuesta de hace treinta segundos, mientras que quien pide
    # el detalle es una persona mirando qué se rompió y necesita el estado de AHORA.
    #
    # Cachear el anónimo es lo que quita el trabajo de verdad: sin esto, cada petición pública evalúa
    # la ventana de temporada y consulta `IngestRun` tres veces, y el endpoint es público a propósito
    # (SEC-01 del v8). El rate limit NO va acá — un limitador dentro de Django gasta el proceso que
    # quiere proteger, así que vive en el proxy inverso, que es Fase 8.
    if not detallado:
        cacheada = cache.get(CLAVE_SEMAFORO)
        if cacheada is not None:
            estado, codigo = cacheada
            return JsonResponse({"status": estado}, status=codigo)

    ventana = season_window.evaluate()

    def respuesta(estado: str, codigo: int = 200, **detalle: object) -> JsonResponse:
        """El estado siempre; lo demás solo para quien puede verlo."""
        if not detallado:
            cache.set(CLAVE_SEMAFORO, (estado, codigo), SEGUNDOS_SEMAFORO)
        return JsonResponse({"status": estado, **(detalle if detallado else {})}, status=codigo)

    if not ventana.corre:
        return respuesta("ok", detalle=f"Fuera de temporada — {ventana.motivo}")

    desde = timezone.now() - timedelta(hours=ventana_horas)
    ultima = IngestRun.objects.filter(command="refresh_daily", started_at__gte=desde).order_by("-started_at").first()

    # Los jobs HORARIOS, con su propio umbral. El semáforo miraba solo el refresco diario, así que
    # `build_mlb_leaders` y `update_roster_moves` podían llevar seis horas fallando —líderes viejos en
    # la portada, cintillo congelado— con el monitor en verde. Un fallo user-facing que ninguna
    # alerta veía es exactamente el agujero que este endpoint vino a tapar (QA-01/ARCH-01 del v8).
    #
    # Umbral distinto a propósito: un día para lo diario y tres horas para lo horario. Con el mismo
    # umbral, o el diario da falsas alarmas o lo horario tarda un día en avisar.
    if ultima is not None and ultima.status in (IngestRun.Status.SUCCESS, IngestRun.Status.SKIPPED):
        atrasados = _horarios_atrasados()
        if atrasados:
            return respuesta("error", 503, detalle="; ".join(atrasados))

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


def _horarios_atrasados() -> list[str]:
    """Los jobs horarios que llevan demasiado sin una corrida buena.

    Se miran aparte del refresco diario porque fallan distinto y avisan distinto: el diario se nota
    al día siguiente, y estos dejan la portada enseñando dato viejo con cara de fresco. Un cintillo
    congelado no parece roto, parece que no pasó nada — que es peor.
    """
    from django.conf import settings

    from dglweb.stats.models import IngestRun

    desde = timezone.now() - timedelta(hours=settings.PIPELINE_HOURLY_STALE_HOURS)
    atrasados = []
    for comando in HORARIOS:
        ultima = (
            IngestRun.objects.filter(command=comando, started_at__gte=desde, status=IngestRun.Status.SUCCESS)
            .order_by("-started_at")
            .first()
        )
        if ultima is None:
            atrasados.append(f"{comando} sin corrida buena en {settings.PIPELINE_HOURLY_STALE_HOURS}h")
    return atrasados


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
