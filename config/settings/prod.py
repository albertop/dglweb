"""Production settings. All secrets/hosts come from the environment (fail loud)."""

from .base import *

# Hardening (behind Cloudflare + reverse proxy TLS — see docs/CONCEPT.md).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Static files: hashed + compressed manifest (run `collectstatic` at build/deploy).
STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"
