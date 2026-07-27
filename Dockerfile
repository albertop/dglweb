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

# Punto de entrega de los CSV de datos de apoyo (Fase 4e). Existe en la imagen para que en el VPS
# haya una ruta conocida donde dejar el archivo: `docker cp` o `scp` al volumen montado acá, y desde
# el Backoffice se sube. Sin esto, en el servidor no hay dónde poner el CSV.
# Va fuera de /app/static_data (que está en .dockerignore, y es de los PowerShell) a propósito: eso
# es código y esto es dato de operación.
RUN mkdir -p /app/uploads

# Lo que sube el editor desde el CMS (`MEDIA_ROOT`). La carpeta tiene que existir EN LA IMAGEN aunque
# encima vaya un volumen: Docker copia el contenido y los permisos de la carpeta de la imagen al
# crear un volumen vacío, así que si acá no existe, el volumen nace de root y el proceso —que corre
# como `appuser`— no puede escribir. Se ve como un «Permission denied» al guardar la primera imagen,
# lejísimos de su causa.
RUN mkdir -p /app/media

# App code
COPY . .

# Non-root user
RUN useradd -r -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Dev server by default (this is a dev/CI image). Compose overrides the command anyway.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
