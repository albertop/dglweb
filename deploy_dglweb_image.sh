#!/bin/bash
# Construye la imagen de producción del sitio y la deja lista para el stack de Portainer.
#
# DIFERENCIA CON `deploy_mlb_api_proxy_image.sh`: aquel CARGA un `.tar` que se construyó en otra
# máquina; este CONSTRUYE desde el código. El sitio vive en un repositorio que el VPS ya clona, así
# que mover un tar de 470 MB por la red no aporta nada — y construir acá garantiza que la imagen
# corresponde exactamente al commit que está desplegado.

set -e

if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker no está corriendo."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "======================================"
echo "Despliegue de la imagen de dglweb"
echo "======================================"

# 1. Traer el código
echo ""
echo "Trayendo los últimos cambios…"
git pull --ff-only
COMMIT=$(git rev-parse --short HEAD)
echo "  commit: $COMMIT — $(git log -1 --format=%s | cut -c1-60)"

# 2. La versión sale del repositorio, no de lo que uno recuerde
VERSION=$(grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2)
if [ -z "$VERSION" ]; then
    echo "Error: no se pudo leer la versión de pyproject.toml"
    exit 1
fi
echo "  versión: $VERSION"

# 3. Avisar si esa versión ya existe. No se bloquea —reconstruir el mismo número es legítimo cuando
#    se corrige algo sin cambiar la versión— pero conviene saberlo antes y no después.
if docker images "dglweb:$VERSION" --format '{{.Tag}}' | grep -q "^${VERSION}$"; then
    echo ""
    echo "  ⚠ dglweb:$VERSION YA EXISTE y se va a reemplazar."
    read -p "  ¿Seguir? (s/N): " -n 1 -r; echo
    [[ $REPLY =~ ^[SsYy]$ ]] || { echo "Cancelado."; exit 0; }
fi

# 4. Construir
echo ""
echo "Construyendo (unos minutos la primera vez)…"
docker build -f Dockerfile.prod -t "dglweb:$VERSION" .

# `latest` como alias, para poder mirar la última sin recordar el número. El STACK debe apuntar
# siempre a la versión concreta: con `latest`, volver atrás es imposible porque el nombre ya se
# reasignó.
docker tag "dglweb:$VERSION" dglweb:latest

echo ""
echo "======================================"
echo "LISTO"
echo "======================================"
docker images "dglweb:$VERSION" --format "  dglweb:{{.Tag}}   {{.Size}}   creada {{.CreatedSince}}"
echo ""
echo "Siguiente paso, en Portainer:"
echo "  1. Stacks -> dglweb -> Editor"
echo "  2. Poner:  image: dglweb:$VERSION"
echo "  3. Update the stack (con «Re-pull image» DESACTIVADO: la imagen es local)"
echo ""
echo "Para volver atrás, apuntar el stack a la versión anterior:"
docker images dglweb --format "  {{.Tag}}   ({{.CreatedSince}})" | grep -v latest | head -5
echo "======================================"
