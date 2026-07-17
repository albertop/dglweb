# syntax=docker/dockerfile:1
# DEV / CI image for the dglweb website (Django + Wagtail) on Python 3.13.
# It installs dev deps and defaults to dev settings + runserver — NOT for production.
# The prod image (runtime deps only, config.settings.prod, `collectstatic`, gunicorn,
# fail-loud on missing secrets) is built separately in Fase 8 (prod hardening).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.dev

WORKDIR /app

# Dependencies first (cached unless requirements change)
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip && pip install -r requirements-dev.txt

# App code
COPY . .

# Non-root user
RUN useradd -r -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Dev server by default (this is a dev/CI image). Compose overrides the command anyway.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
