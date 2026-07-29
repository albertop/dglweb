"""Las dos bandas de relleno para las tarjetas de artículo.

PARA QUÉ SON
------------
La tarjeta dibuja una banda apaisada encima del titular cuando el artículo tiene imagen. Una pieza
sin foto se queda sin ella, y en una retícula donde las demás sí la tienen se lee como un hueco. Esto
son dos bandas neutras para esos casos, con la identidad del sitio, para que el editor tenga algo que
poner sin salir a buscar una foto.

DOS Y NO UNA, y no es capricho: la tarjeta grande pide `fill-1200x140` y la chica `fill-640x130`. Son
proporciones distintas —8,6:1 contra 4,9:1— así que una sola imagen serviría bien para una y saldría
recortada en la otra. Se dibujan a **el doble** de esas medidas: Wagtail las reduce, y reducir se ve
nítido mientras que ampliar no. El doble EXACTO, para que el `fill` no recorte nada: si la proporción
de origen no coincide con la de la rendición, Wagtail corta antes de que nadie lo vea.

CUIDADO CON LOS BORDES: SE PIERDEN
-----------------------------------
La rendición no es lo que se ve. El CSS le pone a la banda un alto fijo —65px, 70 en la destacada— y
`object-fit: cover`, así que hay un SEGUNDO recorte encima del de Wagtail. Medido en pantalla el
2026-07-28, no calculado:

    chica    rendición 640x130   caja 358x65   -> se pierde el 11% del alto
    ancha    rendición 1200x140  caja 736x70   -> se pierde el 18% del alto

Ese recorte es simétrico: se va la mitad por arriba y la mitad por abajo. La primera versión de este
archivo llevaba una línea roja pegada al borde inferior y **en la tarjeta ancha se habría perdido
entera** — la clase de detalle que no se descubre hasta verlo publicado.

De ahí `SEGURO`: nada que importe se dibuja fuera de esa franja central. Los bordes son sangrado, y
lo que se ponga ahí hay que darlo por perdido.

CÓMO ESTÁ DIBUJADO
------------------
Con Pillow y geometría, igual que `hacer_favicon.py`, y por el mismo motivo: no hace falta rasterizar
ningún SVG ni cargar tipografías. Y **sin texto**, que es la otra decisión heredada del favicon — la
silueta del plato se reconoce y no depende de qué fuentes tenga instaladas la máquina que lo genere.

Todo se dibuja al cuádruple y se reduce al final. Es lo que da bordes limpios en las diagonales del
plato y en las curvas de la costura; sin eso salen como una escalera.

LO QUE ROMPE LA MONOTONÍA, que es lo que pidió el dueño:

1. El fondo NO es un azul plano sino el degradado de la marca, del `--dgl-navy` de la cabecera al
   `--dgl-navy-2`, con un halo del azul de acento arriba a la derecha.
2. Unas **franjas diagonales** que cruzan la banda y le dan ritmo. Muy tenues a propósito.
3. La **insignia roja** con el plato blanco: el mismo bloque del monograma de la cabecera. Es el único
   color fuerte, y ahí está toda la personalidad de la banda.

LO QUE SE QUITÓ, Y POR QUÉ IMPORTA MÁS QUE LO QUE SE PUSO
----------------------------------------------------------
Hubo una versión con un par de franjas rojo y blanco cruzando la derecha, en referencia a la cruz de
la bandera. Suelta se veía bien. El dueño la tumbó con el argumento correcto: **esta banda va encima
de CADA artículo**, así que se repite cuatro veces en la misma pantalla y otra vez en cada página.

Una imagen que se ve bien sola y se repite veinte veces no es la misma imagen. Lo que como pieza única
es carácter, repetido es ruido — y encima compite con el titular, que está a un centímetro debajo y es
lo que la persona vino a leer. La banda tiene que ser FONDO.

Por eso quedó tan sobria: degradado, una trama que casi no se ve, y la insignia. Si alguna vez parece
que le falta algo, la pregunta no es «¿se ve bien?» sino «¿se ve bien cuatro veces seguidas?».

SE DISEÑA PARA 70 PÍXELES DE ALTO, NO PARA 280
-----------------------------------------------
Y esa es la lección de la primera versión, que se tiró entera. Llevaba una costura de pelota con sus
puntadas y el plato de marca de agua: a tamaño completo se entendía, y en la tarjeta —736x70 la ancha,
358x65 la chica— la costura se leía como un cable colgando, las puntadas como las marcas de una regla
y el plato como una mancha.

A ese tamaño el detalle fino no existe: solo sobreviven las formas grandes y el contraste. Todo lo que
hay acá se comprueba mirándolo AL TAMAÑO DE LA TARJETA, no al del archivo.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

DESTINO = Path("/app/static_data/banners")

# Los colores del sitio, escritos literales porque un script suelto no ve las variables del CSS.
NAVY = (11, 31, 58)  # --dgl-navy, la barra de arriba y el pie
NAVY_2 = (18, 41, 75)  # --dgl-navy-2
AZUL = (31, 78, 155)  # --dgl-blue, el acento
ROJO = (206, 17, 38)  # --dgl-red, el de la bandera
BLANCO = (255, 255, 255)

ESCALA = 4

# La fracción del alto que sobrevive al recorte del CSS, con margen. Medido: 82% en la ancha y 89% en
# la chica; se usa 0.78 para las dos, que es lo más estrecho de los dos casos y aún deja aire.
SEGURO = 0.78

# Las dos medidas finales, al doble de lo que pide la tarjeta para que la reducción salga nítida.
MEDIDAS = {
    "banner-ancho": (2400, 280),  # tarjeta destacada: `fill-1200x140`
    "banner-chico": (1280, 260),  # retícula y lateral: `fill-640x130`
}


def _degradado(ancho: int, alto: int) -> Image.Image:
    """El fondo: navy arriba a la izquierda, navy-2 abajo a la derecha.

    En diagonal y no en vertical porque una banda tan baja y tan ancha con degradado vertical se lee
    como una franja plana: el ojo no llega a ver el cambio en 280 píxeles de alto.
    """
    base = Image.new("RGB", (ancho, alto))
    pincel = ImageDraw.Draw(base)
    total = ancho + alto
    for x in range(ancho):
        # Una sola pasada por columnas, metiendo el alto en la cuenta para que la diagonal se note.
        t = (x + alto * 0.5) / total
        color = tuple(int(a + (b - a) * t) for a, b in zip(NAVY, NAVY_2, strict=True))
        pincel.line([(x, 0), (x, alto)], fill=color)
    return base


def _halo(lienzo: Image.Image, cx: float, cy: float, radio: float) -> None:
    """Un resplandor del azul de acento, para que el fondo no quede muerto.

    Se dibuja en su propia capa y se difumina: un círculo con borde duro sobre el degradado se ve
    como una mancha pegada, no como luz.
    """
    ancho, alto = lienzo.size
    capa = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(capa).ellipse([cx - radio, cy - radio, cx + radio, cy + radio], fill=90)
    capa = capa.filter(ImageFilter.GaussianBlur(radio * 0.45))
    lienzo.paste(Image.new("RGB", (ancho, alto), AZUL), (0, 0), capa)


def _plato(pincel: ImageDraw.ImageDraw, x: float, y: float, lado: float, color: tuple[int, ...]) -> None:
    """El plato de home, con las mismas proporciones que el `path` del favicon.

    `x`, `y` son la esquina superior izquierda de su caja y `lado` el ancho de esa caja.
    """
    pincel.polygon(
        [
            (x + lado * 0.000, y + lado * 0.000),
            (x + lado * 1.000, y + lado * 0.000),
            (x + lado * 1.000, y + lado * 0.647),
            (x + lado * 0.500, y + lado * 1.117),
            (x + lado * 0.000, y + lado * 0.647),
        ],
        fill=color,
    )


def _franja(pincel: ImageDraw.ImageDraw, centro: float, grosor: float, alto: int, color: object) -> None:
    """Una franja diagonal de arriba abajo, inclinada hacia la derecha.

    El desplazamiento es proporcional al alto, así que la inclinación es la misma en las dos bandas
    aunque midan distinto. Se dibuja de sobra por arriba y por abajo para que corte limpio en el borde.
    """
    sesgo = alto * 0.42
    pincel.polygon(
        [
            (centro - grosor / 2 + sesgo, -1),
            (centro + grosor / 2 + sesgo, -1),
            (centro + grosor / 2 - sesgo, alto + 1),
            (centro - grosor / 2 - sesgo, alto + 1),
        ],
        fill=color,  # type: ignore[arg-type]
    )


def _insignia(lienzo: Image.Image, x: int, y: int, lado: int) -> None:
    """El bloque rojo con el plato blanco: el mismo de la cabecera del sitio.

    Va en su propia capa con transparencia para que las esquinas redondeadas queden suaves sobre el
    degradado. Pegar el rectángulo directo deja los cuatro cantos dentados.
    """
    capa = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    pincel = ImageDraw.Draw(capa)
    pincel.rounded_rectangle([0, 0, lado - 1, lado - 1], radius=lado * 0.1875, fill=(*ROJO, 255))
    _plato(pincel, lado * 0.22, lado * 0.245, lado * 0.56, (*BLANCO, 255))
    lienzo.paste(capa, (x, y), capa)


def banner(ancho: int, alto: int, *, insignia: float) -> Image.Image:
    """Una banda completa, dibujada al cuádruple y reducida al final.

    `insignia` es el lado del bloque rojo como fracción de la franja segura.
    """
    a, h = ancho * ESCALA, alto * ESCALA
    lienzo = _degradado(a, h)
    _halo(lienzo, a * 0.86, -h * 0.1, h * 1.5)

    # Las diagonales tenues. Van en una máscara y se pegan de blanco: así el mismo trazo aclara el
    # degradado sin inventarse un color nuevo, y la banda sigue siendo del azul del sitio.
    # Las diagonales, MUY tenues (alfa 7 sobre 255) y anchas. Antes eran el doble de marcadas y con
    # una segunda serie fina entremedio: a tamaño de tarjeta eso ya era una textura inquieta debajo
    # del titular. Así apenas se adivinan, que es justo lo que se busca — que la banda no sea plana
    # sin que nadie note por qué.
    trama = Image.new("L", (a, h), 0)
    pincel = ImageDraw.Draw(trama)
    paso = h * 1.6
    x = a * 0.34  # la izquierda se deja limpia: ahí va la insignia y necesita aire
    while x < a + h:
        _franja(pincel, x, h * 0.5, h, 7)
        x += paso
    lienzo.paste(Image.new("RGB", (a, h), BLANCO), (0, 0), trama)

    lado = int(h * SEGURO * insignia)
    _insignia(lienzo, int(h * 0.34), (h - lado) // 2, lado)

    return lienzo.resize((ancho, alto), Image.Resampling.LANCZOS)


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    # La chica lleva la costura más abierta y la marca de agua más al centro: tiene la mitad de ancho
    # para la misma altura, así que la composición de la ancha, escalada, saldría apretada.
    # La chica tiene la mitad de ancho para casi el mismo alto, así que la insignia pesa más.
    ajustes = {"banner-ancho": {"insignia": 0.56}, "banner-chico": {"insignia": 0.60}}
    for nombre, (ancho, alto) in MEDIDAS.items():
        imagen = banner(ancho, alto, **ajustes[nombre])
        ruta = DESTINO / f"{nombre}.png"
        imagen.save(ruta, "PNG", optimize=True)
        print(f"{ruta.name}: {ancho}x{alto}  ({ruta.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
