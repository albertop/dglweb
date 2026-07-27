"""Baja Bootstrap y las fuentes al repositorio, una sola vez.

No es código de producción: es la herramienta con la que se hizo el vendorizado, y se guarda en el
scratchpad. Si algún día hay que subir de versión, se corre otra vez cambiando `VERSION`.

Las fuentes se piden con un User-Agent de navegador moderno a propósito: Google devuelve `woff2` solo
si cree que el cliente lo entiende, y con el agente de una librería HTTP manda `ttf`, que pesa el
triple.
"""

import pathlib
import re

import httpx

VERSION = "5.3.3"
BOOTSTRAP = f"https://cdn.jsdelivr.net/npm/bootstrap@{VERSION}/dist"
# El agente decide el formato que devuelve Google. Sin esto llegan `ttf` en vez de `woff2`.
MODERNO = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# Los mismos pesos que pedía el `<link>` que se está reemplazando, ni uno más: cada peso es un
# archivo, y bajar los nueve de una familia para usar cuatro es peso muerto en cada visita.
FAMILIAS = (
    "family=JetBrains+Mono:wght@400;500;700;800"
    "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400"
)

RAIZ = pathlib.Path("/app/static/vendor")
FUENTES = RAIZ / "fuentes"


def bajar(url: str, destino: pathlib.Path, headers: dict[str, str] | None = None) -> int:
    respuesta = httpx.get(url, timeout=30, follow_redirects=True, headers=headers or {})
    respuesta.raise_for_status()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(respuesta.content)
    return len(respuesta.content)


def main() -> None:
    total = 0
    for nombre in ("css/bootstrap.min.css", "js/bootstrap.bundle.min.js"):
        peso = bajar(f"{BOOTSTRAP}/{nombre}", RAIZ / pathlib.Path(nombre).name)
        print(f"  {pathlib.Path(nombre).name:28} {peso / 1024:6.0f} KB")
        total += peso

    # El CSS de Google trae las URLs de los `.woff2` y los rangos unicode. Se baja, se sacan las URLs,
    # se guardan los archivos y se reescribe el CSS apuntando a la copia local.
    hoja = httpx.get(
        f"https://fonts.googleapis.com/css2?{FAMILIAS}&display=swap", timeout=30, headers=MODERNO
    ).text
    urls = sorted(set(re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)", hoja)))
    print(f"  — {len(urls)} archivos de fuente")
    for url in urls:
        archivo = url.rsplit("/", 1)[-1]
        peso = bajar(url, FUENTES / archivo)
        hoja = hoja.replace(url, f"fuentes/{archivo}")
        total += peso

    (RAIZ / "fuentes.css").write_text(hoja, encoding="utf-8")
    print(f"  {'fuentes.css':28} {len(hoja) / 1024:6.0f} KB")
    print(f"\nTOTAL: {total / 1024:.0f} KB en {RAIZ}")


main()
