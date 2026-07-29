#!/bin/bash
# Saca los estáticos del contenedor para que los sirva nginx.
#
# POR QUÉ, CON NÚMEROS
# --------------------
# Medido el 2026-07-29: la portada referencia **210 recursos estáticos y 164 los servía gunicorn**,
# vía WhiteNoise. Gunicorn corre con workers SÍNCRONOS: cada uno atiende una petición a la vez, así
# que una sola visita eran 164 peticiones peleándose por tres huecos.
#
# No es un problema de velocidad —un archivo se sirve rápido de cualquier forma— sino de
# CONCURRENCIA: mientras un worker manda un SVG de 2 KB, no está generando HTML para nadie. Con
# tráfico de lanzamiento, eso es lo que tumba el sitio.
#
# Pasándolos a nginx, gunicorn se queda solo con lo único que solo él puede hacer.
#
# NO SE BORRA NADA, Y ESA ES LA DECISIÓN QUE EVITA UN SITIO SIN ESTILOS
# ---------------------------------------------------------------------
# WhiteNoise nombra cada archivo con un hash de su contenido (`site.b6c97e5b013a.css`), así que dos
# versiones del sitio conviven sin pisarse. Si esto borrara lo viejo antes de copiar lo nuevo, habría
# una ventana —y peor: los navegadores que ya tienen cargada la página anterior seguirían pidiendo
# los archivos de esa versión durante minutos, y recibirían 404.
#
# Copiar encima sin borrar significa que el HTML viejo y el nuevo encuentran lo suyo, siempre. El
# precio es que la carpeta crece unos megas por despliegue. Se limpia a mano, en frío, cuando moleste.
#
# ORDEN: DESPUÉS de recrear el contenedor
# ----------------------------------------
# Al revés, se copiarían los estáticos de la versión anterior y el HTML nuevo pediría hashes que no
# existen — el sitio sale sin hojas de estilo y sin JavaScript, y en la consola solo hay 404.

set -euo pipefail

CONTENEDOR="${CONTENEDOR:-dglweb-web-live}"
DESTINO="${DESTINO:-/srv/dglweb-datos/static}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
    echo "Error: el contenedor $CONTENEDOR no está corriendo."
    exit 1
fi

# La versión que se está copiando, para que el registro diga qué se desplegó y no solo cuándo.
VERSION=$(docker exec "$CONTENEDOR" python -c \
    "import tomllib,pathlib;print(tomllib.loads(pathlib.Path('/app/pyproject.toml').read_text())['project']['version'])" \
    2>/dev/null || echo "?")

mkdir -p "$DESTINO"
docker cp "$CONTENEDOR:/app/staticfiles/." "$DESTINO/"

# Los archivos salen del contenedor con SU dueño, y en este VPS Docker remapea usuarios: acaban
# perteneciendo a un uid alto que nginx —que corre como `www-data`— no es. Lo que hace que funcione
# no es el dueño sino los permisos de lectura para todos.
#
# `a+rX` con X mayúscula: da ejecución solo a los DIRECTORIOS, que es lo que hace falta para
# atravesarlos. Con `x` minúscula marcaría como ejecutable cada CSS y cada imagen.
chmod -R a+rX "$DESTINO"

ARCHIVOS=$(find "$DESTINO" -type f | wc -l)
PESO=$(du -sh "$DESTINO" | cut -f1)
echo "$(date '+%F %T')  estáticos de la $VERSION en $DESTINO — $ARCHIVOS archivos, $PESO"

# La comprobación que importa: que el CSS que pide el HTML de AHORA esté en disco. Si esto falla, el
# sitio va a salir sin estilos y conviene enterarse acá y no por una captura de pantalla.
CSS=$(docker exec "$CONTENEDOR" sh -c 'ls /app/staticfiles/css/site.*.css 2>/dev/null | head -1' || true)
if [ -n "$CSS" ] && [ ! -f "$DESTINO/${CSS#/app/staticfiles/}" ]; then
    echo "AVISO: no se copió $CSS — el sitio se va a ver sin estilos."
    exit 1
fi
echo "Comprobado: el CSS con hash está en disco."
