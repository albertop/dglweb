#!/bin/bash
# Genera el PDF de especificaciones que se le entrega a los anunciantes.
#
#   ./docs/generar_pdf_banners.sh
#
# La FUENTE es `docs/ESPECIFICACIONES_BANNERS.md`. El PDF se regenera desde ahí, así que las
# correcciones se hacen en el Markdown y nunca sobre el PDF — si no, la próxima vez que alguien lo
# regenere se pierden.
#
# Se hace en dos pasos y con dos contenedores porque ninguna herramienta hace bien las dos cosas:
#
#   pandoc      Markdown → HTML5
#   WeasyPrint  HTML + CSS → PDF
#
# WeasyPrint y no LaTeX: acá el documento es tipografía y tablas, no fórmulas, y con CSS se controla
# el diseño con lo que ya sabemos usar. LaTeX daría un resultado correcto tras pelear con paquetes de
# acentuación y márgenes.
#
# El diseño vive en `docs/_banners.css`. Los colores son los de la marca, para que el documento se
# reconozca como nuestro sin llevar el logotipo repetido.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

FUENTE="ESPECIFICACIONES_BANNERS.md"
SALIDA="Especificaciones-banners-DGL.pdf"

# `pwd -W` en Git Bash devuelve la ruta que entiende Docker en Windows; en Linux no existe y se usa
# `pwd` a secas. Sin esto, el montaje falla con «invalid working directory».
DIR="$(pwd -W 2>/dev/null || pwd)"

echo "1/2  Markdown → HTML…"
MSYS_NO_PATHCONV=1 docker run --rm -v "$DIR:/data" pandoc/core:latest \
    -f markdown -t html5 --standalone \
    --metadata title="Especificaciones para banners" \
    -c _banners.css -o _banners.html "$FUENTE"

echo "2/2  HTML → PDF…"
# El entrypoint de la imagen YA es `weasyprint`: pasar el nombre otra vez da «unrecognized arguments»
# y manda a buscar el problema en el archivo, que es donde no está.
MSYS_NO_PATHCONV=1 docker run --rm -v "$DIR:/data" -w //data \
    ghcr.io/weasyprint/weasyprint:latest _banners.html "$SALIDA"

rm -f _banners.html

echo
echo "Listo: docs/$SALIDA  ($(du -h "$SALIDA" | cut -f1))"
