"""Production settings. All secrets/hosts come from the environment (fail loud)."""

from .base import *

# ALLOWED_HOSTS is required in prod — fail loud at startup if it's missing,
# instead of booting and returning DisallowedHost at runtime.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# Hardening (behind Cloudflare + reverse proxy TLS — see docs/CONCEPT.md).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# HSTS on the apex domain only. includeSubDomains/preload is deferred until every
# subdomain (staging, etc.) is guaranteed HTTPS — enabling it early can lock out a
# non-TLS subdomain for a year.
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=31536000)
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Static files: hashed + compressed manifest (run `collectstatic` at build/deploy).
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"
