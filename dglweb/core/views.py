import logging
import secrets
from datetime import timedelta
from typing import Any, Protocol

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from dglweb.core import legal
from dglweb.stats import jobs  # no importa modelos: se puede traer acá arriba sin cargar la app

logger = logging.getLogger(__name__)

# Cuántos artículos entran en la portada: uno grande arriba y tres en la fila de abajo, que es la
# retícula que ya estaba dibujada. El corte vive acá y no en la plantilla para que el HTML no tenga
# que contar posiciones del bucle.
PORTADA_DESTACADO = 1
# DOS y no tres, y el motivo está en la plantilla: la fila de «Últimos artículos» son tres celdas en
# pantalla grande, y la tercera la ocupa un anuncio (zona 5). Con tres artículos, el anuncio empujaría
# al último a una segunda fila él solo — una tarjeta y dos huecos, que se lee como un error.
PORTADA_RESTO = 2

# Los jobs que corren cada hora y alimentan módulos que el visitante VE. Se vigilan aparte del
# refresco diario porque fallan distinto: el diario se nota al día siguiente, y estos dejan la
# portada enseñando dato viejo con cara de fresco. Ver `_horarios_atrasados()`.
#
# La lista se mudó a `stats/jobs.py` porque el comando horario también necesita parte de ella, y
# porque cada job trae ahora su propio contrato de qué cuenta como sano. El porqué está allá.
HORARIOS = jobs.HORARIOS

# Cuánto se cachea la respuesta ANÓNIMA de `/health/pipeline`. Medio minuto: un monitor externo que
# pregunta cada minuto sigue detectando un fallo en el siguiente sondeo, y mientras tanto ninguna
# petición pública toca la base. La respuesta detallada no se cachea — ver la vista.
SEGUNDOS_SEMAFORO = 30
CLAVE_SEMAFORO = "health:pipeline"
CLAVE_PROXY = "health:proxy"
CLAVE_ADSERVER = "health:adserver"


def home(request: HttpRequest) -> HttpResponse:
    """La portada. La franja de arriba son widgets: la pizarra, los destacados y los líderes.

    Debajo van los artículos, que desde la Fase 5 son páginas de Wagtail de verdad y no las tarjetas
    de muestra que había escritas a mano. El primero se lleva el espacio grande y los tres siguientes
    la fila de abajo — cuántos van no lo decide la plantilla, lo decide este corte, para que no haya
    que contar `forloop` en el HTML.
    """
    from dglweb.articles.models import ArticlePage, para_tarjetas
    from dglweb.stats import daily, mlb_leaders, scoreboard

    cuantos = PORTADA_DESTACADO + PORTADA_RESTO
    # `para_tarjetas` y no un `select_related` propio: la portada usa la misma plantilla de tarjeta
    # que el índice, así que tiene que traer lo mismo. Ver su docstring.
    # `-fijado` primero, igual que el índice: es lo que deja al dueño elegir qué encabeza la portada
    # sin tener que retocar la fecha del artículo. Ver `ArticlePage.fijado`.
    articulos = list(para_tarjetas(ArticlePage.objects.live()).order_by("-fijado", "-fecha", "-pk")[:cuantos])
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

    # `public()` y no solo `live()`: si el índice mismo quedara restringido, este enlace mandaría a
    # una pantalla de contraseña desde la portada pública. Ver `para_tarjetas`, que lleva la misma
    # política para los listados.
    indice = ArticleIndexPage.objects.live().public().first()
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


def robots(request: HttpRequest) -> HttpResponse:
    """`/robots.txt`. Le dice a los buscadores dónde está el mapa y qué NO mirar.

    Lo importante no es lo que prohíbe —nada de eso es secreto, y `robots.txt` no protege nada; lo
    que no quiere verse no se publica— sino que **evita gastar presupuesto de rastreo**. Google
    dedica un tiempo limitado a cada sitio, y este tiene ~970 fichas de jugador que sí importan.

    Lo que se cierra y por qué:
    * `/cms/` y `/django-admin/` — pantallas de acceso, no contenido.
    * `/jugadores/buscar/` — el endpoint del buscador; devuelve JSON, no una página.
    * `/lideres/` CON parámetros — 146 métricas x 2 alcances x 72 temporadas son ~21.000 URLs de la
      misma página. La URL desnuda sí se indexa, y va en el mapa.

    Se sirve desde una vista y no como archivo estático para que el dominio salga del propio
    request: en desarrollo apunta a localhost y en producción al dominio real, sin dos versiones que
    se puedan desincronizar.
    """
    lineas = [
        "User-agent: *",
        "Disallow: /cms/",
        "Disallow: /django-admin/",
        "Disallow: /jugadores/buscar/",
        "Disallow: /lideres/?",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lineas) + "\n", content_type="text/plain; charset=utf-8")


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


# Cuánto vive un cerrojo de sondeo. Más que el tope de 5 s de la petición saliente, para que no
# caduque con el sondeo todavía en marcha y entren dos a la vez. Y corto, para que un proceso que se
# muera a mitad no deje el semáforo congelado más de unos segundos.
SEGUNDOS_CERROJO = 10

# El ÚLTIMO estado conocido, para poder contestar sin sondear cuando otro ya está sondeando. Quince
# minutos: lo bastante para cubrir cualquier racha de peticiones, y lo bastante poco para que un dato
# viejo no sobreviva a una tarde entera.
SEGUNDOS_ULTIMO = 900


def _semaforo_cacheado(clave: str, detallado: bool) -> JsonResponse | None:
    """El estado guardado si sirve, o `None` si hay que salir a sondear.

    LO QUE ESTO ARREGLA, Y POR QUÉ NO BASTABA CON CACHEAR
    ------------------------------------------------------
    El patrón anterior era `cache.get` → petición saliente de hasta 5 s → `cache.set`. Entre el fallo
    de caché y el `set` no había nada: **todas las peticiones que llegaran durante esos 5 segundos
    veían el mismo hueco y abrían su propia conexión**. Y la caché era la `default`, que es
    `LocMemCache`, o sea **una por proceso**: los cuatro workers ni siquiera compartían el resultado.

    Con el upstream caído —que es justo cuando esto importa— cada sondeo tarda los 5 segundos
    enteros. Un cliente anónimo golpeando esta ruta podía dejar los 16 hilos de gunicorn esperando al
    servicio que se estaba intentando diagnosticar. Una caída parcial de la publicidad se convertía
    en una caída total del sitio. Lo destapó el review v12 (SEC-01).

    Medido antes de arreglarlo: 16 peticiones simultáneas con el upstream tardando 200 ms produjeron
    **3 llamadas salientes** —no las 16 que decía el review, pero tampoco la única que debería ser—.
    Y eso dentro de UN proceso: en producción hay cuatro, cada uno con su caché.

    LAS DOS MITADES, Y NINGUNA SIRVE SOLA
    --------------------------------------
    1. **La caché compartida** (en la base) hace que los cuatro workers vean el mismo estado. Por sí
       sola no arregla nada: la carrera seguiría, solo que entre procesos en vez de dentro de uno.
    2. **El cerrojo** (`add`, que es atómico) hace que sondee UNO. Por sí solo tampoco basta, porque
       sin caché compartida habría un cerrojo por proceso.

    Quien pierde el cerrojo no se queda esperando ni miente: devuelve **el último estado conocido**.
    Eso es lo correcto para un semáforo — la alternativa sería bloquear, que es el problema original.

    El que trae el token se salta todo esto: es una persona mirando qué se rompió y necesita el
    estado de AHORA, no el de hace medio minuto. Y al estar detrás de un token no puede provocar una
    avalancha.
    """
    if detallado:
        return None

    from django.conf import settings
    from django.core.cache import caches

    compartida = caches[settings.COMPARTIDA]

    guardado = compartida.get(clave)
    if guardado is not None:
        estado, codigo = guardado
        return JsonResponse({"status": estado}, status=codigo)

    # Nadie tiene un estado fresco. Que sondee uno solo.
    if compartida.add(f"{clave}:sondeando", 1, SEGUNDOS_CERROJO):
        return None

    ultimo = compartida.get(f"{clave}:ultimo")
    if ultimo is not None:
        estado, codigo = ultimo
        return JsonResponse({"status": estado}, status=codigo)

    # Ni fresco, ni cerrojo, ni último. Solo pasa en los primeros segundos después de un despliegue,
    # y con varias peticiones a la vez. Un 200 sería mentir en verde y un 503, dar una falsa alarma:
    # se dice lo que hay, y la siguiente consulta del monitor traerá la respuesta de verdad.
    return JsonResponse({"status": "sondeando"}, status=200)


class _Semaforo(Protocol):
    """La firma de `respuesta(...)`.

    Va como `Protocol` y no como `Callable`: hace falta expresar un argumento con valor por defecto y
    `**detalle`, y `Callable[...]` no sabe describir eso. Con `Any` mypy dejaba de comprobar el tipo
    de retorno de las dos vistas que lo usan — que es justo lo que uno quiere que vigile.
    """

    def __call__(self, estado: str, codigo: int = 200, **detalle: object) -> JsonResponse: ...


def _guardar_semaforo(clave: str, detallado: bool) -> _Semaforo:
    """Arma el `respuesta(...)` de cada semáforo: guarda el estado y suelta el cerrojo.

    El cerrojo se suelta SIEMPRE que se llega acá, incluso al devolver un error: si no, un upstream
    caído dejaría el cerrojo puesto sus diez segundos y las peticiones de ese rato contestarían con un
    estado más viejo del necesario.
    """
    from django.conf import settings
    from django.core.cache import caches

    def respuesta(estado: str, codigo: int = 200, **detalle: object) -> JsonResponse:
        if not detallado:
            compartida = caches[settings.COMPARTIDA]
            compartida.set(clave, (estado, codigo), SEGUNDOS_SEMAFORO)
            compartida.set(f"{clave}:ultimo", (estado, codigo), SEGUNDOS_ULTIMO)
            compartida.delete(f"{clave}:sondeando")
        return JsonResponse({"status": estado, **(detalle if detallado else {})}, status=codigo)

    return respuesta


def proxy_health(request: HttpRequest) -> HttpResponse:
    """¿Puede EL SITIO hablar con el proxy de MLB? Para un monitor externo.

    POR QUÉ ESTE ENDPOINT Y NO APUNTAR EL MONITOR AL PROXY
    -------------------------------------------------------
    En producción el proxy está atado a `127.0.0.1:3003`, así que desde fuera no se alcanza — y
    abrirlo para que lo vigilen sería publicar un servicio interno solo para poder mirarlo.

    Pero hay una razón mejor que la comodidad: **nginx y el sitio llegan al proxy por caminos
    distintos**. nginx lo alcanzaría por el `127.0.0.1` del anfitrión; el sitio, por la red de Docker
    y por nombre de contenedor. Un monitor que pasara por nginx diría que todo está bien mientras el
    sitio es incapaz de pedir un dato. Preguntándoselo al sitio se vigila **el camino que importa**,
    con la misma URL, la misma clave y la misma red que usa el pipeline de verdad.

    SE PREGUNTA POR `/live` Y NO POR `/health`, y la diferencia es cara: el `/health` del proxy va a
    la API de MLB en CADA llamada. Un monitor cada minuto son 1.440 peticiones diarias a MLB solo
    para comprobar que un contenedor está vivo. `/live` no sale a la red.

    Y además `/health` se pondría rojo cuando MLB tenga un corte — algo que ni podemos arreglar ni
    tiene que despertar a nadie, y que el proxy sigue sobreviviendo sirviendo desde su caché. Lo que
    esta alerta debe cazar es que el proxy no esté, que es lo que pasó el 2026-07-29.

    Mismo trato que `/health/pipeline`: el semáforo es público y el detalle solo con el token.
    """
    import httpx
    from django.conf import settings

    detallado = _puede_ver_el_detalle(request)
    fresco = _semaforo_cacheado(CLAVE_PROXY, detallado)
    if fresco is not None:
        return fresco

    respuesta = _guardar_semaforo(CLAVE_PROXY, detallado)

    url = f"{settings.MLB_PROXY_URL.rstrip('/')}/live"
    try:
        # Tope corto y propio: el del pipeline son 20 segundos, que para un monitor es una eternidad
        # —el sondeo se agota antes— y acá solo se pregunta si hay alguien al otro lado.
        con_que = httpx.get(url, timeout=5.0)
    except httpx.HTTPError as error:
        return respuesta("error", 503, detalle=f"No se pudo alcanzar el proxy: {error}", url=url)

    if con_que.status_code != 200:
        return respuesta("error", 503, detalle=f"El proxy respondió {con_que.status_code}.", url=url)

    # UN 200 NO BASTA, y por eso el cuerpo se lee acá dentro y no de pasada.
    #
    # Hasta el 2026-07-29 esto era `con_que.json().get("version", "")` a pelo, fuera de cualquier
    # protección. Un 200 cuyo cuerpo no fuera JSON —una página de error de nginx, el HTML de un portal
    # cautivo, un proxy intermedio contestando por su cuenta— reventaba con `ValueError` y el endpoint
    # devolvía **500**. O sea que el que existe para diagnosticar se convertía en el que hay que
    # diagnosticar, y encima rompía su contrato: un upstream enfermo tiene que dar 503, no 500.
    #
    # Lo destapó el review v12 (QA-01) y se reprodujo antes de arreglarlo.
    #
    # El `isinstance` no sobra: un JSON válido que sea una lista —`[]`— pasa el `json()` y revienta
    # después en el `.get()`. Es el mismo fallo un renglón más tarde.
    try:
        cuerpo = con_que.json()
    except ValueError as error:
        return respuesta("error", 503, detalle=f"El proxy respondió 200 pero no con JSON: {error}", url=url)
    if not isinstance(cuerpo, dict):
        return respuesta("error", 503, detalle=f"El proxy respondió 200 con un {type(cuerpo).__name__}.", url=url)

    # La versión es accesoria: si no viene, el proxy sigue estando vivo. Nunca puede decidir el
    # semáforo — ese fue precisamente el error.
    return respuesta("ok", detalle="El proxy responde.", version=cuerpo.get("version", ""))


def adserver_health(request: HttpRequest) -> HttpResponse:
    """¿Está sirviendo anuncios Revive? Para un monitor externo.

    POR QUÉ SE PREGUNTA POR LA URL PÚBLICA, Y NO POR LA RED INTERNA DE DOCKER
    --------------------------------------------------------------------------
    Va **al revés que `/health/proxy`**, y la diferencia no es un detalle: el proxy de MLB lo consume
    EL SITIO desde el servidor, así que ahí lo que importa es el camino interno. Revive lo consume
    **el navegador del visitante**, dentro de un `iframe`. Un monitor que preguntara por
    `http://revive/` por nombre de contenedor podría estar verde con el certificado caducado, el
    subdominio mal apuntado o nginx sin recargar — y ningún visitante vería un anuncio.

    Así que se pregunta por `ADSERVER_URL`, que es literalmente la dirección que el navegador va a
    pedir. Se recorre el mismo camino: DNS, TLS, nginx, contenedor.

    QUÉ DEMUESTRA UN 200, Y QUÉ NO
    -------------------------------
    Demuestra que Apache está arriba, que PHP ejecuta y que la ruta de entrega —renombrada para
    esquivar las listas de bloqueo— sigue existiendo. Ese último punto no es teórico: el healthcheck
    del contenedor apuntaba a `/adjs.php`, se renombró la carpeta, y Portainer marcó `unhealthy` un
    servicio que funcionaba perfectamente.

    **NO demuestra que haya una campaña activa**, y es a propósito. Revive responde 200 con un
    `var OX_… = ''` cuando no hay nada que entregar, y así debe ser: un hueco sin campaña vendida es
    el estado normal de un sitio que arranca, no una avería que tenga que sonar de madrugada.

    EL CASO QUE DE VERDAD SE QUIERE CAZAR
    -------------------------------------
    `ADSERVER_URL` vacío **en producción** da 503. Ese es el fallo silencioso de este montaje: la
    variable se declara en Portainer en dos sitios —la sustitución `${...}` y el bloque
    `environment:`— y si falta en el segundo, el contenedor arranca sin ella, la página carga
    perfecta, y los huecos salen vacíos sin un solo error en ningún registro. En desarrollo, en
    cambio, tenerlo apagado es lo normal y responde 200.

    Mismo trato que los otros semáforos: el estado es público y el detalle solo con el token.
    """
    import httpx
    from django.conf import settings

    from dglweb.core.notify import entorno

    detallado = _puede_ver_el_detalle(request)
    fresco = _semaforo_cacheado(CLAVE_ADSERVER, detallado)
    if fresco is not None:
        return fresco

    respuesta = _guardar_semaforo(CLAVE_ADSERVER, detallado)

    origen = (settings.ADSERVER_URL or "").rstrip("/")
    if not origen:
        if entorno() == "PROD":
            return respuesta(
                "error",
                503,
                detalle="ADSERVER_URL está vacío en producción: los huecos de anuncio salen en blanco.",
            )
        return respuesta("apagado", detalle="ADSERVER_URL vacío. Fuera de producción es lo normal.")

    # La misma zona que usa el healthcheck del contenedor. `cb` es el «cache buster» que Revive
    # espera; sin él podría devolver una respuesta guardada y la comprobación no probaría nada.
    url = f"{origen}/www/pauta/dgl-j.php?cb={secrets.token_hex(6)}&zoneid=1"
    try:
        # Cinco segundos, como el del proxy: acá solo se pregunta si hay alguien al otro lado, y un
        # monitor que espera más se agota antes de recibir la respuesta.
        con_que = httpx.get(url, timeout=5.0)
    except httpx.HTTPError as error:
        return respuesta("error", 503, detalle=f"No se pudo alcanzar el adserver: {error}", url=url)

    if con_que.status_code != 200:
        return respuesta("error", 503, detalle=f"El adserver respondió {con_que.status_code}.", url=url)

    # El cuerpo tiene que ser el JavaScript de entrega. Un 200 con una página de error de nginx, o
    # con el instalador de Revive pidiendo que se configure, también es un 200 — y esa es justo la
    # forma en que este montaje se ha roto antes.
    cuerpo = con_que.text
    if "OX_" not in cuerpo:
        return respuesta("error", 503, detalle="Respondió 200 pero el cuerpo no es la entrega de Revive.", url=url)

    return respuesta("ok", detalle="El adserver entrega.", bytes=len(cuerpo))


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
    for job in HORARIOS:
        corridas = IngestRun.objects.filter(command=job.comando, started_at__gte=desde, status__in=job.sanos)
        # El `alcance` separa dos modos que comparten nombre de comando: sin él, el éxito del refresco
        # diario de las 4:30 haría pasar por fresco al job horario durante tres horas cada mañana.
        if job.alcance:
            corridas = corridas.filter(scope__endswith=job.alcance)
        if not corridas.exists():
            atrasados.append(f"{job.comando} sin corrida buena en {settings.PIPELINE_HOURLY_STALE_HOURS}h")
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
