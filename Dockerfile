# syntax=docker/dockerfile:1
# Dev/CI image for the dglweb website (Django + Wagtail) on Python 3.13.
# (Prod hardening — slim image without dev deps — comes in Fase 8.)
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

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
