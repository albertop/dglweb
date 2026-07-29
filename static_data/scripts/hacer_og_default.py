"""La imagen que sale al compartir un enlace del sitio sin foto propia (`static/img/og-default.png`).

QUÉ ES Y DÓNDE SE VE
--------------------
Es la lámina de Open Graph: lo que dibuja WhatsApp, Telegram, Facebook o X cuando alguien pega un
enlace de un artículo que no tiene imagen. Sin ella el enlace sale como una línea de texto pelada, y
un enlace sin lámina se comparte muchísimo menos.

SOLO EL LOGOTIPO, POR DECISIÓN DEL DUEÑO (2026-07-28)
------------------------------------------------------
La versión anterior llevaba además la bajada del sitio en dos líneas y una barra roja al pie. Al
verla en el previsualizador de Telegram el dueño la encontró recargada, y tenía razón: **la lámina se
ve a un tercio de su tamaño, dentro de una tarjeta que YA repite el título, la descripción y el
dominio en texto**. Todo lo que la lámina escriba compite con eso o lo duplica.

Con el logotipo solo, la tarjeta reparte el trabajo: la imagen dice de quién es, y el texto de al lado
dice qué es. Es la misma lógica que las bandas de las tarjetas de artículo — lo que se repite en cada
pieza tiene que ser fondo, no cartel.

POR QUÉ SE RECORTA EN VEZ DE DIBUJARSE
---------------------------------------
El logotipo lleva tipografía, y las fuentes del sitio están vendorizadas en `woff2`, que Pillow no
sabe leer. Redibujarlo pediría convertir las fuentes o instalar otras, y **otras no serían las del
sitio**: el logotipo saldría parecido pero distinto, que es peor que no tocarlo.

Así que se recorta el bloque de la lámina anterior y se recentra. La tipografía queda EXACTAMENTE la
misma porque son los mismos píxeles.

La contrapartida, dicha para que nadie se lleve una sorpresa: **esto depende de la lámina anterior**.
Si algún día cambia el logotipo, este script no sirve — hay que rehacer la lámina desde el diseño y
volver a fijar las coordenadas de abajo. No es un generador, es una edición reproducible.
"""

from pathlib import Path

from PIL import Image

# La lámina COMPLETA se guarda aparte y es la fuente; la servida es la salida. Separados a propósito:
# con origen y destino en el mismo archivo, correr esto dos veces recortaría lo ya recortado y el
# logotipo se iría comiendo a sí mismo sin que ningún error lo dijera.
ORIGEN = Path("/app/static_data/graficos/og-lamina-original.png")
DESTINO = Path("/app/static/img/og-default.png")

# El recuadro del logotipo dentro de la lámina anterior, medido sobre los píxeles y no a ojo: es el
# rectángulo mínimo que contiene todo lo que no es fondo entre las filas 100 y 380.
LOGOTIPO = (110, 165, 768, 335)

MEDIDA = (1200, 630)  # lo que piden Open Graph y Twitter; también es la proporción 1.91:1 de WhatsApp
NAVY = (11, 31, 58)  # --dgl-navy, el mismo de la cabecera y el pie

# Cuánto del ancho ocupa el logotipo. A 0.62 queda holgado sin perderse: por debajo de la mitad se lee
# pequeño en el previsualizador de WhatsApp, que es donde más se va a ver, y por encima de 0.7 empieza
# a parecer que no cupo.
PROPORCION = 0.62


def main() -> None:
    original = Image.open(ORIGEN).convert("RGB")
    logotipo = original.crop(LOGOTIPO)

    # Se escala por ANCHO y el alto sale solo, para no deformarlo. `LANCZOS` porque acá se AMPLÍA, y
    # ampliar con el remuestreo por defecto deja los bordes de las letras dentados.
    ancho = int(MEDIDA[0] * PROPORCION)
    alto = round(logotipo.height * ancho / logotipo.width)
    logotipo = logotipo.resize((ancho, alto), Image.Resampling.LANCZOS)

    lienzo = Image.new("RGB", MEDIDA, NAVY)
    lienzo.paste(logotipo, ((MEDIDA[0] - ancho) // 2, (MEDIDA[1] - alto) // 2))
    lienzo.save(DESTINO, "PNG", optimize=True)
    print(f"{DESTINO.name}: {MEDIDA[0]}x{MEDIDA[1]}  ({DESTINO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
