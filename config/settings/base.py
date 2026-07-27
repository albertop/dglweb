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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database (from DATABASE_URL) ---
DATABASES = {"default": env.db("DATABASE_URL")}

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

# --- Wagtail ---
WAGTAIL_SITE_NAME = "Dominicanos en Grandes Ligas"

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
