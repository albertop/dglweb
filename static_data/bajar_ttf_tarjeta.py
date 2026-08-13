"""Trae en TTF las familias que usa el sitio, para que la tarjeta del comparador lleve su tipografía.

SE CORRE A MANO Y CASI NUNCA: los TTF están vendorizados en `dglweb/stats/fuentes/` y versionados con
el repo (~418 KB). Esto existe para poder rehacerlos si alguna vez cambian las familias del sitio, no
como paso de despliegue — el contenedor no baja nada de Google.

Google devuelve `woff2` a los navegadores modernos y `ttf` a los agentes viejos — lo dice
`static/vendor/vendorizar.py`, que hace lo contrario a propósito para la web. Pillow solo lee TTF.
"""

import re
import urllib.request
from pathlib import Path

VIEJO = "Mozilla/4.0"  # el que hace que Google mande TTF
DESTINO = Path(__file__).resolve().parent.parent / "dglweb" / "stats" / "fuentes"
DESTINO.mkdir(parents=True, exist_ok=True)

FAMILIAS = {
    "JetBrainsMono-Bold": "family=JetBrains+Mono:wght@700",
    "JetBrainsMono-Regular": "family=JetBrains+Mono:wght@400",
    "SourceSerif4-Regular": "family=Source+Serif+4:wght@400",
    # PARA LAS CIFRAS DE LA TARJETA (prueba B, 2026-08-13). Los dígitos de una monoespaciada se dibujan
    # estrechos para caber en un avance fijo, así que a igual altura se leen más finos que los de una
    # sans proporcional en negrita. Inter empareja bien con JetBrains Mono y trae cifras tabulares, que
    # es lo que mantiene las columnas alineadas sin ser monoespaciada.
    "Inter-Bold": "family=Inter:wght@700",
}

for nombre, consulta in FAMILIAS.items():
    css = urllib.request.urlopen(
        urllib.request.Request(f"https://fonts.googleapis.com/css2?{consulta}", headers={"User-Agent": VIEJO})
    ).read().decode()
    urls = re.findall(r"url\((https://[^)]+\.ttf)\)", css)
    if not urls:
        print(f"  {nombre}: sin TTF en la respuesta")
        continue
    datos = urllib.request.urlopen(urls[0]).read()
    (DESTINO / f"{nombre}.ttf").write_bytes(datos)
    print(f"  {nombre}.ttf  {len(datos) // 1024} KB")
