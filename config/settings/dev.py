"""Development settings. Sensible insecure defaults so `docker compose up` just works."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-insecure-key-do-not-use-in-prod")
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,web")
os.environ.setdefault("DATABASE_URL", "postgres://dglweb:dglweb@db:5432/dglweb")

from .base import *
