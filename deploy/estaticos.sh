#!/bin/bash
# Saca los estáticos para que los sirva nginx.
#
#   ./deploy/estaticos.sh 1.2026.12     ANTES de cambiar el stack  ← la forma buena
#   ./deploy/estaticos.sh              del contenedor que esté corriendo (deja una ventana, ver abajo)
#
#
# POR QUÉ, CON NÚMEROS
# --------------------
# Medido el 2026-07-29: la portada referencia 210 recursos estáticos y 164 los servía gunicorn vía
# WhiteNoise. Gunicorn atiende una petición por hilo, así que servir archivos le robaba capacidad a lo
# único que solo él puede hacer: generar HTML. Pasándolos a nginx se sirven desde disco y comprimidos.
#
#
# POR QUÉ SE COPIA DE LA IMAGEN Y NO DEL CONTENEDOR — LA CORRECCIÓN DEL 2026-07-29
# --------------------------------------------------------------------------------
# La primera versión copiaba del contenedor corriendo, así que HABÍA QUE HACERLO DESPUÉS de recrearlo.
# Eso abre una ventana de segundos en la que el contenedor nuevo ya sirve el HTML nuevo —con los nombres
# con hash nuevos— y los archivos todavía no están en disco. Quien entre ahí ve el sitio sin estilos.
#
# Ese día costó una avería de verdad: el bloque `/static/` de nginx llevaba `always` en su `add_header`,
# así que **el 404 salía con caché de un año y marcado como inmutable**. El navegador de quien entrara
# en la ventana no volvía a pedir el CSS jamás. Lo del `always` ya está arreglado, pero la ventana
# seguía ahí — y encima este paso era el fácil de olvidar, porque iba al final.
#
# `docker create` hace un contenedor SIN ARRANCARLO, y de ahí se copia igual. Así los archivos nuevos
# están en disco ANTES de que exista el HTML que los pide.
#
# Y copiar antes es seguro porque ESTE SCRIPT NUNCA BORRA: los nombres llevan un hash del contenido, así
# que las dos versiones conviven. El HTML viejo sigue encontrando lo suyo y el nuevo ya tiene lo suyo
# esperando. La carpeta crece unos megas por despliegue; se limpia a mano, en frío, cuando moleste.

set -euo pipefail

DESTINO="${DESTINO:-/srv/dglweb-datos/static}"
IMAGEN="${1:-}"
TEMPORAL=""
MANIFIESTO=$(mktemp)

limpiar() {
    [ -n "$TEMPORAL" ] && docker rm -f "$TEMPORAL" >/dev/null 2>&1 || true
    rm -f "$MANIFIESTO"
}
trap limpiar EXIT

if [ -n "$IMAGEN" ]; then
    # Se acepta «1.2026.12» y «dglweb:1.2026.12»: el prefijo se pone solo si falta.
    case "$IMAGEN" in *:*) ;; *) IMAGEN="dglweb:$IMAGEN" ;; esac
    if ! docker image inspect "$IMAGEN" >/dev/null 2>&1; then
        echo "Error: la imagen $IMAGEN no existe. Constrúyela primero con ./deploy_dglweb_image.sh"
        exit 1
    fi
    TEMPORAL="estaticos-$$"
    docker create --name "$TEMPORAL" "$IMAGEN" >/dev/null
    ORIGEN="$TEMPORAL"
    VERSION="${IMAGEN#*:}"
    echo "Copiando de la IMAGEN $IMAGEN, sin arrancarla."
else
    ORIGEN="${CONTENEDOR:-dglweb-web-live}"
    if ! docker ps --format '{{.Names}}' | grep -qx "$ORIGEN"; then
        echo "Error: el contenedor $ORIGEN no está corriendo y no se indicó una imagen."
        echo "Uso recomendado:  ./deploy/estaticos.sh <version>   (antes de cambiar el stack)"
        exit 1
    fi
    VERSION=$(docker exec "$ORIGEN" python -c \
        "import tomllib,pathlib;print(tomllib.loads(pathlib.Path('/app/pyproject.toml').read_text())['project']['version'])" \
        2>/dev/null || echo "?")
    echo "AVISO: se copia del contenedor corriendo. Si el stack ya se cambió, hubo una ventana en la que"
    echo "       el sitio se sirvió sin estilos. Para evitarla:  ./deploy/estaticos.sh <version>"
fi

# EL MANIFIESTO PRIMERO, y es lo que hace verificable todo lo demás. WhiteNoise deja en
# `staticfiles.json` el nombre con hash de cada archivo, o sea EXACTAMENTE lo que el HTML va a pedir.
# Sacándolo aparte se puede comprobar que la copia trajo los archivos de ESTA versión, en vez de dar por
# bueno que «hay un css» —que es lo que hacía la comprobación anterior, y que pasaba en verde con los
# archivos de la versión de antes en disco.
docker cp "$ORIGEN:/app/staticfiles/staticfiles.json" "$MANIFIESTO" >/dev/null

mkdir -p "$DESTINO"
docker cp "$ORIGEN:/app/staticfiles/." "$DESTINO/"

# Los archivos salen con SU dueño, y en este VPS Docker remapea usuarios: acaban perteneciendo a un uid
# alto que nginx —que corre como `www-data`— no es. Lo que hace que funcione no es el dueño sino los
# permisos de lectura para todos.
#
# `a+rX` con X mayúscula: da ejecución solo a los DIRECTORIOS, que es lo que hace falta para
# atravesarlos. Con `x` minúscula marcaría como ejecutable cada CSS y cada imagen.
chmod -R a+rX "$DESTINO"

ARCHIVOS=$(find "$DESTINO" -type f | wc -l)
PESO=$(du -sh "$DESTINO" | cut -f1)
echo "$(date '+%F %T')  estáticos de la $VERSION en $DESTINO — $ARCHIVOS archivos, $PESO"

# LA COMPROBACIÓN QUE IMPORTA: que lo que el HTML de ESTA versión va a pedir esté en disco. Se miran el
# CSS y los dos JavaScript sin los que el sitio no funciona — incluido `anuncios.js`, que es el que le
# pone el `src` a los huecos de publicidad: sin él no sale ni un banner horizontal.
FALTAN=0
for CLAVE in css/site.css js/site.js js/anuncios.js; do
    CON_HASH=$(python3 -c "
import json
print(json.load(open('$MANIFIESTO')).get('paths', {}).get('$CLAVE', ''))
" 2>/dev/null || true)
    if [ -z "$CON_HASH" ]; then
        echo "AVISO: $CLAVE no aparece en el manifiesto de la imagen."
        FALTAN=1
    elif [ ! -f "$DESTINO/$CON_HASH" ]; then
        echo "AVISO: no se copió $CON_HASH (de $CLAVE) — el sitio saldría roto."
        FALTAN=1
    else
        echo "  ok  $CLAVE -> $CON_HASH"
    fi
done
[ "$FALTAN" -eq 0 ] || exit 1
echo "Comprobado contra el manifiesto: lo que el HTML va a pedir está en disco."
