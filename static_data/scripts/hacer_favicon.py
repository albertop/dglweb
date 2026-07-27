"""Los mapas de bits del favicon, a partir de la misma figura del SVG.

Se dibujan con Pillow y no se convierte el SVG: Pillow no rasteriza SVG, y meter una dependencia
nueva para dos formas geométricas no se justifica. La figura son cuatro números, y están acá y en
`favicon.svg` — si un día cambia, cambia en los dos sitios.
"""

from pathlib import Path

from PIL import Image, ImageDraw

DESTINO = Path("/app/static/img")
ROJO = (206, 17, 38, 255)  # --dgl-red, el de la bandera y el del monograma
BLANCO = (255, 255, 255, 255)


def icono(lado: int) -> Image.Image:
    """El plato blanco sobre el cuadrado rojo, a la escala que se pida.

    Se dibuja al cuádruple y se reduce al final: es la forma barata de tener bordes suaves en las
    diagonales del plato, que a 16 píxeles y sin suavizar salen como una escalera.
    """
    escala = 4
    n = lado * escala
    lienzo = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    pincel = ImageDraw.Draw(lienzo)

    # El radio en proporción al lado, para que el redondeo se vea igual en 16 que en 512.
    pincel.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.1875, fill=ROJO)

    # Las mismas proporciones que el `path` del SVG, en fracciones del lado.
    def p(x: float, y: float) -> tuple[float, float]:
        return (n * x, n * y)

    pincel.polygon(
        [p(0.234, 0.219), p(0.766, 0.219), p(0.766, 0.563), p(0.5, 0.813), p(0.234, 0.563)],
        fill=BLANCO,
    )
    return lienzo.resize((lado, lado), Image.LANCZOS)


# El .ico lleva los tres tamaños que Windows y los navegadores viejos piden; los modernos usan el SVG.
icono(64).save(DESTINO / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

# iOS no entiende SVG en `apple-touch-icon` y lo pone sobre fondo blanco si tiene transparencia, así
# que este va opaco y sin canal alfa.
icono(180).convert("RGB").save(DESTINO / "apple-touch-icon.png")

for archivo in ("favicon.ico", "apple-touch-icon.png"):
    ruta = DESTINO / archivo
    print(f"{archivo:<24} {ruta.stat().st_size / 1024:5.1f} KB")
