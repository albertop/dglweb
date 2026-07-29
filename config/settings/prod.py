"""Production settings. All secrets/hosts come from the environment (fail loud)."""

from .base import *

# ALLOWED_HOSTS is required in prod — fail loud at startup if it's missing,
# instead of booting and returning DisallowedHost at runtime.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# Hardening (behind Cloudflare + reverse proxy TLS — see docs/CONCEPT.md).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=31536000)

# Cubre también los subdominios (2026-07-29). Antes estaba apagado, y la razón que había escrita era
# buena: encenderlo con un subdominio sin TLS lo deja INACCESIBLE durante un año, porque el navegador
# se niega a hablarle por HTTP y ya no hay forma de decirle que sí.
#
# Así que se comprobó cuáles existen antes de tocarlo. Bajo `dominicanosengrandesligas.com` hay
# exactamente dos, y los dos redirigen HTTP→HTTPS con un 301:
#
#     www.dominicanosengrandesligas.com     el mismo sitio
#     promo.dominicanosengrandesligas.com   el panel de anuncios (Revive)
#
# Los otros dominios del servidor —`sabertables.com`, `baseballsixdegrees.com`, `prdm0.com`— NO son
# subdominios de este, así que esta cabecera no los toca.
#
# LO QUE ESTO OBLIGA DE AQUÍ EN ADELANTE: cualquier subdominio nuevo nace con TLS o no funciona. Un
# `staging.` levantado deprisa por HTTP se va a ver inaccesible desde cualquier navegador que haya
# entrado al sitio. No es un problema —Let's Encrypt es gratis y automático— pero hay que saberlo
# antes, no descubrirlo.
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# `preload` NO, y es a propósito. Es otra cosa: mete el dominio en una lista que viene COMPILADA
# dentro de Chrome, Firefox y Safari. Salir de ahí tarda meses y depende de que otros publiquen una
# versión nueva del navegador. Es una decisión sin vuelta atrás práctica, y no hace falta para lo que
# se quiere acá — con la cabecera basta para todo el que ya visitó el sitio.
SECURE_HSTS_PRELOAD = False
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# The proxy is the only upstream data source: require it in prod (base.py keeps dev-only defaults),
# so a missing URL/key fails loud at startup instead of at 6am when the first scraper runs.
MLB_PROXY_URL = env("MLB_PROXY_URL")
MLB_PROXY_API_KEY = env("MLB_PROXY_API_KEY")

# Static files: hashed + compressed manifest (run `collectstatic` at build/deploy).
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"
