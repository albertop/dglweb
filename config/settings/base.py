"""Base settings shared by all environments.

Secrets and environment-specific values come from the environment (see docs/
library-guidelines.md). Reads a `.env` file if present. `dev`/`prod` import from here.
"""

from pathlib import Path

import environ

# apps/dglweb/  (three parents up: base.py -> settings -> config -> project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# --- Core (fail loud if a required secret is missing) ---
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# --- Applications ---
INSTALLED_APPS = [
    "dglweb.core",
    "dglweb.players",
    "dglweb.stats",
    "dglweb.backoffice",
    "dglweb.profiles",
    "dglweb.articles",
    # Wagtail
    "wagtail.contrib.forms",
    # El bloque de tabla del cuerpo de los artículos: el editor la llena como una hoja de cálculo.
    "wagtail.contrib.table_block",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    # Las notas al pie del editor. Ver `requirements.txt` para por qué es dependencia y no código propio.
    "wagtail_footnotes",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # El mapa del sitio. Son DOS: Django cubre lo que sirven nuestras vistas —las ~970 fichas de
    # jugador, líderes, legales— y Wagtail lo suyo, que es el árbol de artículos y solo él sabe qué
    # está publicado. Sin ellos, Google tiene que descubrir mil páginas siguiendo enlaces.
    "django.contrib.sitemaps",
    "wagtail.contrib.sitemaps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # La CSP va ARRIBA del todo, junto a la otra de seguridad: así la cabecera sale también en las
    # respuestas que se cortan antes de llegar a una vista —un 404, un redirect de Wagtail—, que son
    # HTML igual y por lo tanto se pueden atacar igual. Ver `core/csp.py`.
    "dglweb.core.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # `indice_articulos`, que usan el menú y el pie en todas las páginas. Ver el módulo:
                # la ruta la decide el editor desde que la página la sirve Wagtail.
                "dglweb.articles.context_processors.indice",
                # `movimientos`, el cintillo de la cabecera. También en todas las páginas, así que
                # tampoco puede depender de que cada vista se acuerde de ponerlo.
                "dglweb.core.context_processors.cintillo",
                # `legal_paginas`, la columna «Legal» del pie. Constante del código: ni consulta ni
                # caché, solo evita que el pie y la vista lleven dos listas que se van separando.
                "dglweb.core.context_processors.paginas_legales",
                # `analitica`, el script de Umami. Vacío en desarrollo, así que en dev no se dibuja.
                "dglweb.core.context_processors.analitica",
                # `X_USUARIO`, la cuenta del sitio en X: la usan el pie y el `twitter:site` de la
                # tarjeta social, así que tampoco puede depender de cada vista.
                "dglweb.core.context_processors.redes",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database (from DATABASE_URL) ---
DATABASES = {"default": env.db("DATABASE_URL")}

# CONEXIONES PERSISTENTES. Sale de una medición en producción del 2026-07-29, no de una costumbre:
#
#   resolver el nombre  ...   0,8 ms
#   abrir el socket TCP ...   1,2 ms
#   la conexión ENTERA  ...  32,9 ms
#
# O sea que 31 de esos 33 ms no son red. Se descartó el TLS —Postgres tiene `ssl` apagado, y conectar
# con `sslmode=disable` da lo mismo (30,1 contra 30,9 ms)—. Lo que queda son las dos cosas que no se
# pueden quitar: `scram-sha-256` derivando la clave con 4.096 iteraciones a los dos lados, y Postgres
# BIFURCANDO UN PROCESO NUEVO por cada conexión.
#
# Con el valor de fábrica —0— eso se pagaba en CADA petición: 33 ms sobre los 274 de la portada, un
# 12% del tiempo, gastado en volver a presentarse ante una base que está en el mismo servidor.
#
# 60 segundos y no `None` (para siempre): así una conexión que se quedó rara se recicla sola cada
# minuto sin que nadie tenga que darse cuenta.
#
# LAS CUENTAS DE POSTGRES, que es lo que haría que esto fuera peligroso: con 4 workers y 4 hilos son
# como mucho 16 conexiones vivas —Django guarda una POR HILO—, contra las 100 de `max_connections`.
# Hoy se usan 9 en todo el servidor, contando pgAdmin y Revive. Sobra sitio.
DATABASES["default"]["CONN_MAX_AGE"] = 60

# EL COMPAÑERO OBLIGATORIO DEL DE ARRIBA. Sin esto, una conexión guardada que la base cerró por su
# cuenta —un reinicio de Postgres, un despliegue del stack— se descubre rota cuando alguien la usa, y
# el visitante se lleva un 500. Con esto Django la comprueba al empezar cada petición y, si está
# muerta, abre otra sin que nadie se entere.
#
# Cuesta una consulta trivial por petición: ~2 ms medidos en producción, contra los 33 que ahorra.
# Es exactamente el principio #0 del proyecto —resiliencia sobre features— cobrando su precio, y es
# barato.
#
# VA DENTRO DE `DATABASES`, no suelto en el módulo. Es POR BASE DE DATOS: Django lo lee de
# `settings_dict["CONN_HEALTH_CHECKS"]` y un `CONN_HEALTH_CHECKS = True` a nivel de módulo lo IGNORA
# en silencio —sin aviso, sin error de configuración, y con `settings.CONN_HEALTH_CHECKS` devolviendo
# `True` tan tranquilo—. Así estuvo escrito primero acá, y solo se descubrió matando una conexión a
# propósito desde el servidor. Lo cubre `test_conexiones_persistentes.py`.
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# --- Password validation ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / TZ (Spanish, DR audience) ---
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santo_Domingo"
USE_I18N = True
USE_TZ = True

# --- Medios: lo que sube el editor desde el CMS ---
# Distinto de los estáticos y por eso va aparte. Los estáticos los escribe un programador, entran a
# la imagen de Docker y se recogen con `collectstatic`; esto lo escribe una PERSONA desde el
# navegador mientras el sitio corre, así que vive en un volumen y sobrevive a un despliegue.
#
# Sin esto, Wagtail no puede aceptar una imagen: `MEDIA_ROOT` vacío deja los archivos tirados en la
# raíz del proyecto y `MEDIA_URL` vacío hace que ninguna se pueda pedir. En dev las sirve Django (ver
# `config/urls.py`); en producción tiene que servirlas el proxy — anotado en el TODO.
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# --- Caché: DOS, y cada una donde tiene sentido ---
#
# La primera versión de esto puso TODO en la base y salió peor: `/articulos/` pasó de 18 consultas a
# 133. El culpable estaba medido — Wagtail lee su caché constantemente: 23 veces por petición la
# clave `wagtail_site_root_paths` (una por cada URL de página que resuelve) y 4 por cada recorte de
# imagen. Eso es exactamente para lo que existe una caché en memoria, y mandarlo a la base convierte
# cada lectura en una consulta.
#
# Así que van dos.
#
# `default` — EN MEMORIA, por proceso. La usa Wagtail para sus lecturas diminutas y constantes. Que
# cada worker tenga la suya no molesta: las raíces del sitio cambian una vez en la vida, y un recorte
# de imagen cacheado de más solo significa volver a mirarlo, no un dato viejo publicado.
#
# `compartida` — EN LA BASE, la ven TODOS los workers. Solo para lo que se invalida por SEÑAL, que es
# donde `LocMemCache` deja de ser una optimización y pasa a ser un fallo:
#
#   El dueño cambia un umbral en el Backoffice. La señal que tira la caché
#   (`profiles.metric_layout._olvidar`) corre EN EL WORKER que atendió ese guardado. Los demás
#   seguirían sirviendo el valor viejo hasta que expire — y su TTL es de 24 HORAS.
#
# Lo mismo con la URL del índice de artículos. Las que dependen de un TTL corto —la pizarra, el
# cintillo, el semáforo del pipeline— se curan solas y se quedan en memoria.
#
# POR QUÉ LA BASE Y NO REDIS. Redis sería más rápido, pero suma un servicio que mantener, vigilar y
# reiniciar, y el principio #0 del proyecto es resiliencia sobre features. Lo que va a la compartida
# son 34 KB medidos, leídos un puñado de veces por petición.
#
# La tabla la crea `core.0002`, así que no hay un paso manual que olvidar al desplegar — y si
# faltara, `/ready` lo diría con un 503 antes de recibir tráfico.
COMPARTIDA = "compartida"

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    COMPARTIDA: {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "dgl_cache",
        # 300 es el defecto y se queda corto en cuanto entren más entradas compartidas. Mil de este
        # tamaño son unos pocos megas en una tabla que se limpia sola.
        "OPTIONS": {"MAX_ENTRIES": 1000},
    },
}

# --- Static files (served by WhiteNoise in prod) ---
# Leading slash so assets resolve from the site root on nested paths (e.g. /cms/login/).
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # prod swaps this for WhiteNoise's hashed+compressed manifest storage.
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- MLB proxy (the only upstream data source; see dglweb/mlb/client.py) ---
MLB_PROXY_URL = env("MLB_PROXY_URL", default="http://localhost:3002")
MLB_PROXY_API_KEY = env("MLB_PROXY_API_KEY", default="")
MLB_PROXY_TIMEOUT = env.float("MLB_PROXY_TIMEOUT", default=20.0)

# --- Ingest log ---
# The IngestRun rows are a rolling operational log, not permanent data; prune anything older than
# this so the table cannot grow without bound. `prune_ingest_log` runs daily in the scheduler.
INGEST_LOG_RETENTION_DAYS = env.int("INGEST_LOG_RETENTION_DAYS", default=30)

# Cuánto silencio del refresco diario es «algo anda mal», para `/health/pipeline`.
# Treinta y no veinticuatro: un refresco que se atrasa unas horas no es una emergencia, y una
# alerta que salta por eso enseña a ignorarla. Con 30 hay un día entero de margen.
PIPELINE_STALE_HOURS = env.int("PIPELINE_STALE_HOURS", default=30)
# Y el de los jobs HORARIOS, que es otro problema. Tres horas y no treinta: con el umbral del diario,
# un cintillo congelado tardaría más de un día en encender el semáforo, y para entonces la portada
# lleva un día entero enseñando dato viejo. Tres deja margen para un par de corridas fallidas
# seguidas sin gritar por una sola.
PIPELINE_HOURLY_STALE_HOURS = env.int("PIPELINE_HOURLY_STALE_HOURS", default=3)

# Quién puede ver el DETALLE del fallo en `/health/pipeline`. El semáforo —200 o 503— es público a
# propósito, porque quien lo lee es un monitor de uptime externo y pedirle credenciales a un servicio
# gratuito es cambiar una fuga menor por un monitor que nadie configura.
#
# Lo que no es para cualquiera es el detalle: nombres de comandos y el texto del error. Con este
# token puesto, quien lo mande en `X-Monitor-Token` recibe la respuesta completa. Vacío = nadie
# anónimo ve detalle, que es el default seguro. El personal del Backoffice lo ve por su sesión.
PIPELINE_HEALTH_TOKEN = env.str("PIPELINE_HEALTH_TOKEN", default="")

# Avisos por Telegram. Vacíos por defecto: sin token no se manda nada y no se protesta, que es
# lo que corresponde en desarrollo. El token es un secreto y sale de `.env`, nunca de acá.
TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env.str("TELEGRAM_CHAT_ID", default="")

# --- Analítica de visitas (Umami) ---
#
# Se elige Umami y no Google Analytics por decisión del dueño (2026-07-28). Lo que importa acá arriba
# es que son DOS variables y ninguna es un secreto: el identificador viaja en el HTML de todas las
# páginas, así que cualquiera lo ve. No van en `.env` por confidencialidad, van por ENTORNO — que es
# lo que evita que las visitas de desarrollo ensucien las estadísticas del sitio real.
#
# VACÍAS POR DEFECTO, y eso es el interruptor: sin las dos puestas no se dibuja ningún script y el
# sitio no le pide nada a nadie. Un default que apaga es lo correcto acá porque el fallo silencioso
# sería al revés — medir a escondidas cuando nadie lo configuró.
#
# `ANALITICA_URL` es el ORIGEN, sin `/script.js`: la ruta la pone la plantilla. Así el mismo ajuste
# sirve para la nube (`https://cloud.umami.is`) y para una instancia propia, que es la salida
# prevista. Y hay que declararlo también en la CSP — ver `core/csp.py`, que lo lee de acá.
ANALITICA_URL = env.str("ANALITICA_URL", default="").rstrip("/")
ANALITICA_ID = env.str("ANALITICA_ID", default="")


# ADÓNDE MANDA LOS EVENTOS ESE SCRIPT, que NO tiene por qué ser de donde se bajó.
#
# Umami Cloud sirve `script.js` desde `cloud.umami.is` y recolecta en `gateway.umami.is`. El
# 2026-07-30 esa segunda parte cambió, la CSP dejó de cubrirla, y el sitio estuvo días sin contar una
# sola visita sin que nada fallara: el script cargaba, el `POST` lo bloqueaba el navegador y el único
# rastro era una línea en la consola de quien mirara. Se descubrió en la factura de eventos —2 en todo
# el mes— y no en ninguna alerta.
#
# POR DEFECTO VA CON COMODÍN, `https://*.umami.is`, para que el próximo cambio de host del proveedor
# no vuelva a apagar la medición. Solo entra en `connect-src`, nunca en `script-src`: el primero
# decide adónde puede mandar datos un script ya autorizado, el segundo qué código puede ejecutarse.
# Ver `core/csp.py`, que lo explica entero.
#
# Vacío con una instancia propia: `csp.publica()` cae de vuelta en `ANALITICA_URL`, porque ahí el
# script y la recolección sí comparten host.
#
# Y es una variable de entorno para que el día que esto vuelva a cambiar se arregle editando el stack
# y reiniciando, sin reconstruir la imagen.
def _envio_por_defecto(analitica_url: str) -> str:
    """Adónde recolecta el proveedor, deducido de dónde sirve el script.

    Es una función y no una expresión suelta para poder PROBAR la regla: en desarrollo la analítica va
    vacía a propósito, así que una prueba contra `settings.ANALITICA_ENVIO_URL` no comprobaría nada de
    lo que corre en producción.
    """
    return "https://*.umami.is" if "umami.is" in analitica_url else ""


ANALITICA_ENVIO_URL = env.str("ANALITICA_ENVIO_URL", default=_envio_por_defecto(ANALITICA_URL)).rstrip("/")

# --- Servidor de anuncios (Revive, autoalojado) ---
#
# El ORIGEN del servidor, sin barra final. Vacío = los huecos siguen mostrando el recuadro rayado de
# maqueta, que es lo que corresponde en desarrollo: nadie quiere contar impresiones de sí mismo
# recargando la portada.
#
# Va como variable y no escrito en las plantillas por el mismo motivo que la analítica, y además por
# uno propio: el día que se cambie de servidor de anuncios, esto es una línea y no trece plantillas.
#
# Hay que declararlo también en la CSP — `core/csp.py` lo lee de acá — y en `frame-src`, no en
# `script-src`: el anuncio va en un `iframe` y el servidor NUNCA ejecuta código en nuestras páginas.
# Ver `docs/ADSERVER.md`.
ADSERVER_URL = env.str("ADSERVER_URL", default="").rstrip("/")

# La cuenta del sitio en X. Va como ajuste y no escrita a mano porque la usan TRES sitios —el pie, el
# `twitter:site` de la tarjeta social y el `via=` del botón de compartir— y un usuario que cambia en
# dos de los tres es un enlace roto que nadie mira.
#
# Sin barra ni arroba: cada sitio le pone lo que necesita. `@` para leerlo, `via=` sin él.
#
# Y es del SITIO, no del dueño (decisión del 2026-07-30). Publicar desde su cuenta personal ataría
# esto a su nombre en cada tuit que compartiera un lector, y él no trabaja en el ambiente deportivo.
# Los seguidores además se acumulan en el activo: si algún día entra alguien más a escribir, o el sitio
# cambia de manos, la audiencia se queda con el sitio.
X_USUARIO = env.str("X_USUARIO", default="dglmlb")

# --- Wagtail ---
WAGTAIL_SITE_NAME = "Dominicanos en Grandes Ligas"

# treebeard.E001: cuatro líneas de aviso en CADA corrida de CADA job del scheduler.
#
# QUÉ DICE. Que los managers de `Page` y `Collection` no heredan de `MP_NodeManager`, y que eso será
# un error en treebeard 6.
#
# POR QUÉ SE SILENCIA Y NO SE ARREGLA. **No es código nuestro.** Esos managers los define Wagtail
# 7.4.2, y la incompatibilidad es suya con django-treebeard 5.3.0. No hay nada que podamos cambiar de
# este lado; lo tiene que resolver Wagtail en su código.
#
# POR QUÉ MOLESTA LO SUFICIENTE. Sale por `stderr` decenas de veces al día y **entierra el `stderr`
# de verdad**, que es justamente el canal por el que `refresh_daily` avisa cuando algo falla. Un canal
# de errores donde casi todo es ruido deja de leerse — el mismo problema que ya tuvimos con las
# alertas de Telegram.
#
# ⚠️ QUÉ SE ESTÁ APLAZANDO. Nada se rompe hoy, pero en treebeard 6 esto pasa de aviso a ERROR, y ahí
# la aplicación no arranca. **Al subir de versión, lo primero es quitar esta línea y ver qué queda.**
# La política del proyecto es quedarse en LTS, así que no urge — pero un `SILENCED_SYSTEM_CHECKS` sin
# fecha de revisión es una trampa para quien venga después.
SILENCED_SYSTEM_CHECKS = ["treebeard.E001"]

# El panel del CMS llama a `releases.wagtail.org` en cada carga para avisar si hay versión nueva. Se
# apaga por tres razones, y la CSP fue solo la que lo destapó:
#
# 1. La CSP lo bloquea (`connect-src 'self'`), y dejaba un error rojo permanente en la consola del
#    CMS. Un error que siempre está es un error que nadie mira, y entierra a los de verdad.
# 2. Le anuncia a un tercero que esta instalación existe y qué versión corre — justo lo que dice la
#    política de privacidad que no hacemos.
# 3. No aporta nada: de subir Wagtail se entera quien lea el `requirements`, no quien publique un
#    artículo, y este es un LTS elegido a propósito.
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
        # Una configuración propia de Postgres: español CON stemmer y SIN exigir tildes. La crea
        # `articles/0005_busqueda_en_espanol`, y el porqué está ahí — medido, «grafico» sin tilde
        # devolvía cero resultados y «gráfico» devolvía dos.
        "SEARCH_CONFIG": "espanol_sin_tildes",
    },
}
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL", default="http://localhost:8000")
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "pdf", "xlsx"]
