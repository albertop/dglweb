"""La tarjeta del comparador en PNG. Ver `docs/COMPARADOR.md`.

ES LA PÁGINA DE RESULTADO, no un extra (dueño, 2026-08-13). Se probó una tabla en HTML y se descartó:
lo que la gente comparte es una imagen, y una imagen que se genera aparte de lo que se ve en pantalla
acaba diciendo otra cosa. Acá hay UNA sola representación del resultado.

Formato Stathead: la métrica en la columna del CENTRO y los valores flanqueándola, con el ganador
resaltado.

ACÁ NO SE CALCULA NADA: `stats/comparador.py` entrega la foto hecha y esto la dibuja.
"""

from io import BytesIO
from pathlib import Path
from typing import IO, Any

from django.contrib.staticfiles import finders
from PIL import Image, ImageDraw, ImageFont

from dglweb.players.models import Player
from dglweb.stats import comparador
from dglweb.stats.models import Metric

# 1080x1350 ES 4:5 EXACTO, y la proporción manda más que el tamaño: es la vertical MÁXIMA que
# Instagram admite sin recortar, X la muestra entera, y WhatsApp aguanta de sobra. Se probó 980x1350
# —proporción 0,73— y se pasaba de alto en los dos sitios donde más se comparte: Instagram habría
# cortado la cabecera o el pie, que es justo donde van la marca y la URL.
#
# LO ESTRECHO NO LO DA EL LIENZO SINO LA COLUMNA DEL CENTRO, que pasó de 340px a 130: solo tiene que
# caber «wRC+», y todo lo que se llevaba de más separaba los dos valores que se vienen a comparar.
W, H = 1080, 1350
CENTRO = 130

# El alto del pie, fijo. Lleva cuatro textos en DOS líneas —arroba y fecha a la izquierda, leyenda del
# paréntesis y umbral a la derecha— y la tabla reparte lo que queda, así que las tres modalidades salen
# con las filas del mismo alto.
#
# BAJÓ DE 126 A 88 (dueño, 2026-08-13), en dos pasos y por dos motivos distintos:
#
#   126 → 112   recortar cromo. Medido contra Stathead en un teléfono, gastábamos 562px de 1350 en
#               cabecera, retratos y pie —el 42%— y ellos casi nada; por eso su tarjeta se leía mejor
#               con cifras MÁS pequeñas que las nuestras.
#   112 →  88   el pie pasó de tres líneas a dos al quitar la nota de la media ponderada.
#
# SE PROBÓ 95 CON TRES LÍNEAS Y NO CABÍA: la fecha se montaba sobre el arroba y las de la derecha se
# pisaban. Estos números están medidos, no estimados.
ALTO_PIE = 88

# LOS DOS EJES DE LA IMAGEN, calculados UNA vez. El retrato, el nombre y el valor de cada jugador
# cuelgan del mismo, o se desalinean: la primera versión sacaba el del retrato de `W // 4` y el del
# valor del ancho de la columna, y quedaban a 38 px uno de otro.
EJE_IZQ = (W - CENTRO) // 4
EJE_DER = W - EJE_IZQ
NAVY, AZUL, ROJO = (11, 31, 58), (31, 78, 155), (206, 17, 38)
TINTA, SUAVE, LINEA = (26, 29, 33), (107, 114, 128), (229, 231, 235)
GANA = (232, 240, 252)  # el azul del sitio en tono muy bajo, no el verde de Stathead

# EL PUESTO ENTRE PARÉNTESIS, UN PELÍN MÁS OSCURO QUE `SUAVE` (dueño, 2026-08-13). Tiene color propio
# y no comparte el de los años bajo el nombre: allí el gris claro está bien —es contexto— pero el
# ordinal ES parte de lo que se viene a leer, y a 25px en gris medio se caía de la fila.
#
# Sigue por debajo de la tinta del valor a propósito: acompaña a la cifra, no compite con ella.
PUESTO = (44, 50, 62)

# LAS TIPOGRAFÍAS VIVEN EN EL REPO, junto a este módulo, y no bajo `static/`: no las carga ningún
# navegador, las lee Pillow en el servidor. Están vendorizadas porque la imagen del contenedor solo
# trae fuentes de iconos. Se rehacen con `static_data/bajar_ttf_tarjeta.py`, que las pide con un
# agente viejo porque Google sirve TTF a esos y woff2 al resto — y Pillow solo lee TTF.
F = Path(__file__).resolve().parent / "fuentes"
def mono(t: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(F / "JetBrainsMono-Bold.ttf"), t)


def mono_n(t: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(F / "JetBrainsMono-Regular.ttf"), t)


def cifra(t: int) -> ImageFont.FreeTypeFont:
    """La sans proporcional en negrita de los NÚMEROS (prueba B, dueño 2026-08-13).

    Los dígitos de una monoespaciada se dibujan estrechos para caber en un avance fijo, así que a igual
    altura se leen más finos que los de una proporcional en negrita — medido contra la tarjeta de
    Stathead en un teléfono: las nuestras eran MÁS grandes y aun así se leían peor.

    Inter trae cifras tabulares, que es lo que mantiene las columnas alineadas sin ser monoespaciada.
    El resto de la tarjeta —métricas, marca, pie— sigue en JetBrains Mono: el cambio es solo donde
    están las cifras, que es donde el ojo se cansa.
    """
    return ImageFont.truetype(str(F / "Inter-Bold.ttf"), t)


def serif(t: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(F / "SourceSerif4-Regular.ttf"), t)

# CÓMO SE LLAMA CADA OFICIO EN LA TARJETA (dueño, 2026-08-13). Va bajo la modalidad y en TODAS las
# tarjetas: desde que abridores y relevistas se rankean por separado, un «17º» significa dos cosas
# distintas según quién salga en la imagen, y la imagen circula sola.
OFICIO_ROTULO = {
    comparador.OFICIO_BATEO: "Bateadores",
    comparador.OFICIO_ABRIDOR: "Lanzadores abridores",
    comparador.OFICIO_RELEVISTA: "Lanzadores relevistas",
}

ROTULO = {
    comparador.MODO_CARRERA: "Carrera completa",
    comparador.MODO_TEMPORADA: "Temporada",
    comparador.MODO_MEJORES: "Sus mejores temporadas",
}


# Lo que Pillow acepta como color: un nombre o una terna RGB. Las dos formas conviven en este módulo
# —«white» junto a `NAVY`— así que el alias las nombra en vez de caer en `Any`.
_Color = str | tuple[int, int, int]

# EL LOGO DE X, COPIADO DEL SVG QUE YA USA EL SITIO en `templates/widgets/_compartir.html`. Se
# transcribe y no se aproxima: su trazado son SOLO rectas —`M`, `h`, `l`, `H`, `L`, `Z`, ni una curva—
# así que dos polígonos lo reproducen exacto.
#
# El segundo es el HUECO de la diagonal, y va relleno del color del fondo. Pillow no tiene reglas de
# relleno con agujeros, así que se pinta encima; por eso `_equis` necesita saber sobre qué fondo cae.
#
# Coordenadas en el lienzo de 24x24 del original, para poder compararlas con el SVG de un vistazo.
_EQUIS_TRAZO = [
    (18.9, 1.15), (22.58, 1.15), (14.54, 10.34), (24, 22.85), (16.59, 22.85),
    (10.79, 15.27), (4.16, 22.85), (0.47, 22.85), (9.07, 13.02), (0, 1.15),
    (7.59, 1.15), (12.84, 8.08),
]  # fmt: skip
_EQUIS_HUECO = [(17.61, 20.64), (19.65, 20.64), (6.49, 3.24), (4.3, 3.24)]


def _equis(
    d: ImageDraw.ImageDraw, x: float, y: float, alto: float, color: _Color, fondo: _Color
) -> float:
    """Dibuja el logo de X con su centro vertical en `y`. Devuelve dónde termina, para poner el texto."""
    escala = alto / 24
    def punto(p: tuple[float, float]) -> tuple[float, float]:
        return (x + p[0] * escala, y - alto / 2 + p[1] * escala)

    d.polygon([punto(p) for p in _EQUIS_TRAZO], fill=color)
    d.polygon([punto(p) for p in _EQUIS_HUECO], fill=fondo)
    return x + 24 * escala


def _texto(columna: str, valor: float | None, metrica: Metric) -> str:
    if valor is None:
        return "—"
    # WAR VA CON UN DECIMAL, y hay que decirlo antes que nada porque el catálogo lo tiene marcado como
    # ACUMULABLE — que es correcto: se suma temporada a temporada, no se promedia. Pero «acumulable»
    # decide cómo se AGREGA, no cómo se ESCRIBE, y aquí se estaban confundiendo las dos cosas: el
    # quinquenio de Pujols salía como «43» cuando son 42,5.
    #
    # Es el único caso donde las dos reglas no coinciden. Todo el mundo publica WAR con un decimal.
    if columna == "war":
        return f"{valor:.1f}"
    # LOS MILES CON COMA (dueño). El resto del sitio escribe en español —donde el separador de miles
    # es el punto— pero acá manda otra cosa: las cifras del béisbol se leen en la convención
    # anglosajona en todas partes, y «1.256 hits» junto a un «.318» de promedio se lee mal.
    if columna == "outs":
        enteras = int(valor // 3)
        return f"{enteras:,}.{int(valor % 3)}"
    if metrica.kind == Metric.Kind.CUMULATIVE:
        return f"{round(valor):,}"
    if columna in ("avg", "obp", "slg", "ops", "woba", "win_pct"):
        return f"{valor:.3f}".lstrip("0")
    if columna in ("w_rc_plus", "era_minus", "fip_minus"):
        return f"{round(valor)}"
    return f"{valor:.2f}"


def dibujar(foto: dict[str, Any], destino: IO[bytes] | Path) -> None:
    grupo = foto["grupo"]
    metricas = {m.column: m for m in Metric.objects.filter(stat_group=grupo)}
    lienzo = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(lienzo)

    # ── cabecera ──────────────────────────────────────────────────────────────────────────────
    #
    # LA MARCA A LA IZQUIERDA Y LA MODALIDAD A LA DERECHA (dueño). La marca es la MISMA del sitio y
    # se dibuja, no se pega: en el sitio no es una imagen sino CSS —un cuadro rojo con «DGL» y el
    # nombre en dos líneas— así que no hay archivo que reusar. Replicarla acá la mantiene reconocible.
    d.rectangle([0, 0, W, 132], fill=NAVY)
    # La misma línea roja que cierra el pie, acá cerrando la cabecera: encuadra la tabla entre dos
    # filos del rojo de la bandera y las dos franjas azules dejan de leerse como piezas sueltas.
    d.rectangle([0, 132, W, 136], fill=ROJO)

    # LAS MEDIDAS SALEN DE `.dgl-marca` EN `site.css`, escaladas 1,6x — no del ojo. El sitio la define
    # a 1rem: monograma de 46px con radio 8, hueco de .55rem, «Dominicanos» a 1.4rem y la bajada a
    # .7rem con `letter-spacing: .16em`.
    esc = 1.6
    mono_lado, hueco = round(46 * esc), round(8.8 * esc)
    x0, y0 = 32, 66 - mono_lado // 2
    d.rounded_rectangle([x0, y0, x0 + mono_lado, y0 + mono_lado], radius=round(8 * esc), fill=ROJO)
    d.text((x0 + mono_lado // 2, y0 + mono_lado // 2), "DGL", font=mono(round(15.2 * esc)), fill="white", anchor="mm")

    texto_x = x0 + mono_lado + hueco
    # TRES LÍNEAS EN LA MISMA BANDA. El dominio se subió acá (dueño) porque es lo que convierte una
    # imagen prestada en una visita, y al pie competía con la leyenda de los paréntesis. Las tres se
    # reparten el alto del monograma —29 a 103— en vez de crecer la banda: la tabla necesita el sitio.
    d.text((texto_x, 48), "Dominicanos", font=mono(round(22.4 * esc)), fill="white", anchor="lm")
    # LA BAJADA VA EN BLANCO, y el CSS avisa de por qué: en gris azulado «se leía como un texto
    # secundario en vez de como parte del nombre». La jerarquía la dan el cuerpo y el espaciado.
    #
    # El interletrado Pillow no lo hace, así que se dibuja letra a letra con el avance de `.16em`.
    fuente_baja = mono_n(round(11.2 * esc))
    avance = 0.16 * round(11.2 * esc)
    x = float(texto_x)
    for letra in "EN GRANDES LIGAS":
        d.text((x, 78), letra, font=fuente_baja, fill="white", anchor="lm")
        x += d.textlength(letra, font=fuente_baja) + avance

    # El dominio, en el mismo gris azulado que el resto de las aclaraciones de la tarjeta: acompaña a
    # la marca sin competir con ella.
    d.text((texto_x, 106), "dominicanosengrandesligas.com", font=mono_n(20), fill=(150, 175, 215), anchor="lm")

    rotulo = ROTULO[foto["modo"]]
    if foto["modo"] == comparador.MODO_MEJORES:
        # POR WAR, dicho en el rótulo: es la regla que decide qué temporadas entraron, y sin ella
        # «sus 5 mejores» no dice mejores según qué.
        #
        # EL SINGULAR SE ESCRIBE ENTERO (dueño): «Mejor temporada por WAR», no «Mejores 1 temporadas».
        # No basta con quitarle la ese al plural — cambia también el adjetivo y sobra el número.
        rotulo = (
            "Mejor temporada por WAR"
            if foto["cuantas"] == 1
            else f"Mejores {foto['cuantas']} temporadas por WAR"
        )
    elif foto["modo"] == comparador.MODO_TEMPORADA:
        rotulo = f"Temporada {foto['izquierda']['temporadas'][0]}"
    # LA MODALIDAD ARRIBA Y EL OFICIO DEBAJO, los dos a la derecha. El oficio va en cuerpo menor y en
    # gris azulado porque es la aclaración, no el titular: quien mira la tarjeta quiere saber primero
    # qué se compara y después entre quiénes se rankea.
    oficio = OFICIO_ROTULO.get(foto.get("oficio") or "", "")
    if oficio:
        d.text((W - 32, 56), rotulo, font=mono(28), fill="white", anchor="rm")
        d.text((W - 32, 92), oficio, font=mono_n(20), fill=(150, 175, 215), anchor="rm")
    else:
        d.text((W - 32, 71), rotulo, font=mono(28), fill="white", anchor="rm")

    # ── los dos jugadores ─────────────────────────────────────────────────────────────────────
    for lado, cx in (("izquierda", EJE_IZQ), ("derecha", EJE_DER)):
        pid = foto[lado]["player_id"]
        jugador = Player.objects.filter(pk=pid).first()
        nombre = jugador.full_name if jugador else str(pid)

        # SI FALTA EL RETRATO SE DIBUJA UN SUSTITUTO DEL MISMO TAMAÑO, y no se deja el hueco.
        #
        # Pasa: los retratos se bajan aparte con `download_mugshots.ps1` y un debutante puede estar en
        # la base antes de que MLB publique el suyo. En la web esto lo resuelve `data-quitar-si-falta`,
        # que borra la imagen rota — pero acá no hay navegador que compense: un lado con foto y el
        # otro con un agujero deja la tarjeta coja, y es una imagen que se comparte.
        #
        # El sustituto son las iniciales sobre un círculo gris, ocupando los mismos 168px. Mantiene la
        # simetría y se lee como una decisión, no como un fallo de carga.
        # RETRATO CUADRADO Y SIN MÁSCARA REDONDA (2026-08-13). El círculo recortaba las esquinas y aun
        # así reservaba su cuadrado entero, o sea que gastaba alto para tapar píxeles. Rectangular
        # llena lo mismo ocupando menos, que es lo que hace Stathead.
        #
        # Se sube de 168 a 176 A LA VEZ QUE EL BLOQUE SE ACORTA: la foto crece y el bloque encoge,
        # porque lo que sobraba era el aire alrededor, no la imagen.
        lado_px = 176
        caja = (cx - lado_px // 2, 146)
        # Se pregunta a los buscadores de estáticos en vez de clavar `/app/static/…`: en producción
        # los retratos llegan por un volumen montado y la ruta no es la del repo.
        # `None` y no `Path("")`: la ruta vacía es `Path(".")`, que EXISTE —es un directorio— así que
        # el `exists()` daba verdadero y Pillow reventaba al abrirlo.
        hallado = finders.find(f"img/mugshots/360/{pid}.png")
        retrato = Path(hallado) if hallado else None
        if retrato is not None and retrato.is_file():
            foto_img = Image.open(retrato).convert("RGBA").resize((lado_px, lado_px))
            lienzo.paste(foto_img, caja, foto_img)
        else:
            d.ellipse([caja[0], caja[1], caja[0] + lado_px, caja[1] + lado_px], fill=(233, 236, 240))
            iniciales = "".join(p[0] for p in nombre.split()[:2]).upper() or "?"
            d.text((cx, caja[1] + lado_px // 2), iniciales, font=mono(58), fill=(160, 167, 178), anchor="mm")
        # 35 y no 31 (dueño): es el rótulo de quién es cada columna, y con las cifras en Inter Bold se
        # había quedado pequeño al lado de lo que rotula.
        d.text((cx, 352), nombre, font=mono(35), fill=TINTA, anchor="mm")
        # QUÉ AÑOS ENTRARON, Y EN «MEJORES X» SE ESCRIBEN UNO A UNO (dueño).
        #
        # Un rango miente ahí: las mejores cinco de alguien pueden ser 2019, 2021, 2022, 2023 y 2024,
        # y «2019-2024» da a entender seis años seguidos. En carrera sí es un rango de verdad —son
        # todas las que jugó, sin huecos que ocultar— así que ahí se deja.
        anios = foto[lado]["temporadas"]
        if anios:
            if foto["modo"] == comparador.MODO_MEJORES:
                pie = ", ".join(str(a) for a in anios)
            elif len(anios) == 1:
                # LA PALABRA ENTERA Y NO «temp.» (dueño): en esta línea sobra sitio, y una abreviatura
                # que nadie necesita solo hace que la tarjeta parezca apretada donde no lo está.
                pie = f"{anios[0]} · 1 temporada"
            else:
                # La raya larga del rango es tipografía deliberada y sale impresa en la tarjeta: no
                # es la misma que un guion corto. Se marca en vez de degradar la imagen.
                pie = f"{anios[0]}–{anios[-1]} · {len(anios)} temporadas"  # noqa: RUF001
            # En `PUESTO` y no en `SUAVE` (dueño): el gris claro venía de cuando esta línea era puro
            # relleno, pero dice CUÁNTAS temporadas entraron en la comparación — en «mejores X» es la
            # lista exacta de años. Eso no es contexto, es parte de lo que se compara.
            d.text((cx, 382), pie, font=mono_n(18), fill=PUESTO, anchor="mm")

    # ── la tabla ──────────────────────────────────────────────────────────────────────────────
    #
    # LA LEYENDA SE DICE UNA VEZ Y NO TREINTA (dueño). Cada celda llevaba «2º histórico», y con trece
    # filas por dos jugadores eso son 26 repeticiones de la misma palabra: el ojo la lee como ruido y
    # deja de ver el número, que es lo único que cambia. Enunciada arriba, en las celdas basta el
    # ordinal.
    #
    # Va pegada a la tabla y no en el pie porque es la clave para leerla: al pie llegaría cuando ya
    # se ha leído todo sin entenderlo.
    filas = [c for c in comparador.METRICAS[grupo] if c in foto["izquierda"]["celdas"]]
    leyenda = "( ) puesto histórico entre dominicanos"
    if foto["modo"] == comparador.MODO_MEJORES:
        # Acá el puesto no compara carreras sino quinquenios, y decirlo evita que «2º» se lea como
        # «2º de por vida», que es lo que uno supone por defecto.
        leyenda = f"( ) puesto entre los mejores {foto['cuantas']} años de cada dominicano"
    elif foto["modo"] == comparador.MODO_TEMPORADA:
        leyenda = "( ) puesto entre todas las temporadas dominicanas"

    # LA TABLA EMPIEZA 30px ANTES: el bloque de retratos pasó de 300 a 264. Ver el comentario de
    # `ALTO_PIE` para el porqué de recortar cromo.
    arriba = 406
    alto = (H - arriba - ALTO_PIE) // len(filas)
    for i, columna in enumerate(filas):
        y = arriba + i * alto
        metrica = metricas.get(columna)
        if metrica is None:  # una métrica desactivada en el Backoffice no tumba la tarjeta
            continue
        izq, der = foto["izquierda"]["celdas"][columna], foto["derecha"]["celdas"][columna]

        # EL GANADOR SE DECIDE CON EL VALOR TAL COMO SE ESCRIBE, no con el float de dentro.
        #
        # EL CASO QUE LO OBLIGA (lo vio el dueño en wRC+): Alex Rodríguez y Pujols salían los dos con
        # 141 y el resaltado iba a uno solo. Por dentro difieren en decimales que la tarjeta redondea,
        # así que la imagen se contradecía: dos cifras idénticas y una pintada como mejor. Quien la
        # mira no tiene forma de entender por qué, y el sitio no puede tomar decisiones que el usuario
        # no entienda.
        #
        # Empate en pantalla, empate en el resaltado. La diferencia real no se pierde: sigue estando
        # en los puestos entre paréntesis, que ahí sí salen distintos.
        mejor = None
        if izq.valor is not None and der.valor is not None:
            escrito_izq = _texto(columna, izq.valor, metrica)
            escrito_der = _texto(columna, der.valor, metrica)
            if escrito_izq == escrito_der:
                mejor = "ambos"
            else:
                mas_alto = metrica.direction == Metric.Direction.HIGHER
                mejor = "izquierda" if (izq.valor > der.valor) == mas_alto else "derecha"

        for lado, celda, x0, x1, cx in (
            ("izquierda", izq, 0, (W - CENTRO) // 2, EJE_IZQ),
            ("derecha", der, (W + CENTRO) // 2, W, EJE_DER),
        ):
            if mejor in (lado, "ambos"):
                d.rectangle([x0, y, x1, y + alto - 2], fill=GANA)
            # EL VALOR Y SU PUESTO EN LA MISMA LÍNEA (dueño): «42.5 (2º)» en vez de apilarlos. Se
            # dibujan como un bloque centrado en el eje —se miden los dos y se reparte— porque
            # centrar solo el valor dejaría el paréntesis colgando y las filas bailando entre sí.
            #
            # El paréntesis va en la fuente normal y algo menor que el valor: tiene que leerse sin
            # competir con la cifra, que es lo que la gente viene a mirar.
            # LAS CIFRAS SE ALINEAN POR LA DERECHA, en un eje fijo por columna. Centrar el bloque
            # entero —valor más paréntesis— parecía lo natural y era el error: el paréntesis cambia
            # de ancho en cada fila («(1º)» contra «(67º)»), así que el valor se desplazaba distinto
            # en cada una y las cifras bailaban. El dueño lo cazó trazando dos líneas verticales.
            #
            # En una tabla de números lo que tiene que caer en columna son los dígitos, no el
            # conjunto. Se fija el borde derecho del valor y el paréntesis cuelga detrás.
            f_valor, f_rank = cifra(40), mono_n(25)
            medio = y + alto // 2
            fin_valor = cx + 26
            d.text((fin_valor, medio), _texto(columna, celda.valor, metrica), font=f_valor, fill=TINTA, anchor="rm")
            if celda.rank:
                d.text((fin_valor + 10, medio + 1), f"({celda.rank}º)", font=f_rank, fill=PUESTO, anchor="lm")

        etiqueta = metrica.abbrev if metrica else columna
        d.text((W // 2, y + alto // 2), etiqueta, font=mono(31), fill=AZUL, anchor="mm")
        # SIN ASTERISCO EN wOBA NI wRC+ (dueño, 2026-08-13). Marcaba las medias ponderadas y remitía a
        # una nota al pie que se quitó al compactarlo a dos líneas — «no vale mucho», y tenía razón:
        # decía «este número es aproximado», que es una discusión que no cabe en una imagen.
        #
        # Se van los dos juntos a propósito. Un marcador sin leyenda es PEOR que ninguno: el lector ve
        # una llamada, la busca, no la encuentra y se queda pensando qué se le escapa.
        #
        # El dato no se pierde del todo: `Celda.aproximada` sigue viajando en la foto, y la página HTML
        # puede explicarlo con todo el sitio del mundo.
        d.line([(0, y + alto - 1), (W, y + alto - 1)], fill=LINEA)

    # LOS TRES FILOS DE LA TABLA (dueño, 2026-08-13): uno horizontal donde empieza y dos verticales
    # flanqueando la columna del centro.
    #
    # QUÉ HACEN. Los retratos y los nombres flotaban sobre un blanco continuo que seguía hasta la
    # primera fila, así que la tabla no empezaba en ninguna parte — empezaba donde el ojo decidiera. Y
    # las verticales convierten la columna de métricas en una columna de verdad: sin ellas los tres
    # bloques se leen como una sola parrilla de números con palabras sueltas en medio.
    #
    # VAN AL FINAL, encima de los fondos de fila: el resaltado del ganador llega hasta el borde de la
    # columna, y dibujadas antes las taparía a trozos.
    #
    # 2px y en el azul de la marca. Con el gris de las filas se perderían —es el mismo peso visual— y
    # más gruesas competirían con las cifras, que es lo que se viene a leer.
    abajo = H - ALTO_PIE
    d.line([(0, arriba), (W, arriba)], fill=AZUL, width=2)
    for x in ((W - CENTRO) // 2, (W + CENTRO) // 2):
        d.line([(x, arriba), (x, abajo)], fill=AZUL, width=2)

    # ── pie ───────────────────────────────────────────────────────────────────────────────────
    # LA NOTA DEL UMBRAL (dueño), y hay que redactarla con cuidado: **el mínimo solo se le exige a las
    # TASAS**. A un conteo no — «más jonrones» no se logra en 3.000 apariciones, la cantidad ya es su
    # propio piso, y pedírselo dejaría el ranking sobre una población casi vacía. Decir «los líderes
    # son de quienes superan X» a secas sería falso para ocho de las trece filas.
    #
    # El número sale del catálogo (`QualifierDefault`) y no escrito a mano: hoy son 3.000 apariciones
    # en bateo y 1.000 entradas en pitcheo, y el día que el dueño los cambie en el Backoffice esta
    # nota tiene que cambiar con ellos o pasa a mentir.
    nota = ""
    if foto["modo"] in (comparador.MODO_CARRERA, comparador.MODO_MEJORES):
        from dglweb.stats.models import QualifierDefault

        piso = QualifierDefault.objects.filter(stat_group=grupo).values_list("qualifier_career", flat=True).first()
        # EL RELEVISTA TIENE EL SUYO, y el pie tiene que decir el que se usó de verdad. Leyendo el
        # catálogo a secas la tarjeta de Soriano anunciaba 1.000 IP mientras su ranking se había hecho
        # con 400: una nota que contradice sus propios números es peor que no ponerla.
        if foto.get("oficio") == comparador.OFICIO_RELEVISTA:
            piso = comparador.UMBRAL_RELEVISTA_CARRERA
        if piso:
            campo, minimo = piso.replace(">=", " ").split()
            # LOS DOS PUNTOS PONEN EL ÁMBITO DELANTE (dueño). «Los rankings de promedios exigen…» se
            # leía como una regla del sitio que aplica a lo que tengas delante; así dice desde la
            # primera palabra a qué se refiere y, por omisión, a qué no — los acumulados no tienen
            # umbral. Y es más corta, que en ese renglón importa: comparte línea con la leyenda.
            nota = f"Puestos de promedios: mínimo {int(minimo):,} {campo}"

    # QUÉ CONTAMOS COMO TEMPORADA (dueño). Se escribe en la imagen y no solo en la página: la tarjeta
    # se reenvía suelta por WhatsApp, y «2º histórico» sin decir entre quiénes no lo puede comprobar
    # nadie. Sustituye a la nota del qualifier en «mejores X» porque comparten renglón y esta explica
    # algo que el lector no puede deducir —la otra habla de un umbral estándar del béisbol.
    if foto["modo"] == comparador.MODO_MEJORES:
        unidad = "IP" if grupo == "pitching" else "PA"
        nota = f"Cuenta como temporada la de {foto['minimo']}+ {unidad}"

    d.rectangle([0, H - ALTO_PIE + 4, W, H], fill=NAVY)
    d.rectangle([0, H - ALTO_PIE, W, H - ALTO_PIE + 4], fill=ROJO)

    # Las dos líneas de la izquierda y las tres de la derecha se reparten el pie. `base` es la
    # primera; las otras cuelgan de `H` para que el renglón de abajo no dependa de cuántas haya.
    base = H - ALTO_PIE + 28
    # LA CUENTA DE X AL PIE Y EL DOMINIO EN LA CABECERA (dueño, 2026-08-13). Antes el dominio estaba
    # acá abajo; se subió junto a la marca, que es donde el ojo lo busca, y este sitio queda para el
    # arroba — que es lo que alguien copia cuando quiere citar la fuente en la propia red.
    # El logo delante del arroba dice de QUÉ red es la cuenta sin gastar una palabra. A 20px queda un
    # pelo por debajo de la altura del texto, que es lo que hace que acompañe en vez de competir.
    fin = _equis(d, 28, base, 20, "white", NAVY)
    d.text((fin + 12, base), "@dglmlb", font=mono_n(23), fill="white", anchor="lm")
    # LA LEYENDA DEL PARÉNTESIS COMPARTE RENGLÓN CON EL ARROBA (dueño, 2026-08-13). El pie pasó de tres
    # líneas a DOS, y lo que salió fue la nota de la media ponderada — «no vale mucho», y es cierto:
    # explicaba un asterisco que solo decía «este número es aproximado», que es más de lo que cabe
    # discutir en una imagen. Con ella se fueron también los asteriscos de wOBA y wRC+, porque un
    # marcador sin leyenda es peor que ninguno.
    d.text((W - 28, base), leyenda, font=mono_n(19), fill=(150, 175, 215), anchor="rm")
    # LA SEGUNDA LÍNEA DEL PIE: la nota a la izquierda y la fecha a la derecha (dueño).
    #
    # EL SELLO DE FECHA NO ES DECORACIÓN. Estas imágenes se comparten y sobreviven al momento en que
    # se hicieron: una comparación de dos peloteros en activo cambia cada semana, y sin fecha alguien
    # puede estar mirando en octubre unos números de abril sin saberlo. Con ella, la imagen dice
    # cuándo fue cierta.
    #
    # Va en hora dominicana, que es la del sitio.
    from django.utils import timezone

    # LA FECHA EN ISO Y A LA IZQUIERDA (dueño). `YYYY-MM-DD` no se puede leer mal: «03/04/2026» es el
    # 3 de abril o el 4 de marzo según quién lo mire, y estas imágenes salen del país.
    cuando = timezone.localtime().strftime("%Y-%m-%d")
    d.text((28, H - 26), cuando, font=mono_n(19), fill=(150, 175, 215), anchor="lm")
    # LA LEYENDA DEL PARÉNTESIS BAJÓ AL PIE (dueño). Estaba sobre la tabla como clave de lectura, pero
    # con el ordinal ya metido en la línea del valor —«3,384 (2º)»— el paréntesis se explica casi
    # solo, y la leyenda arriba competía con los nombres de los jugadores.
    #
    # Se le antepone «( )» para que se sepa a qué se refiere sin repetir la palabra en cada celda,
    # que es de lo que veníamos huyendo.
    if nota:
        d.text((W - 28, H - 26), nota, font=mono_n(19), fill=(150, 175, 215), anchor="rm")

    # `format` explícito: el destino puede ser un buffer en memoria, y sin extensión de fichero Pillow
    # no tiene de dónde deducirlo.
    lienzo.save(destino, format="PNG", optimize=True)


def png(foto: dict[str, Any]) -> bytes:
    """La tarjeta, lista para servir o para descargar.

    Devuelve bytes y no escribe a disco: la vista la sirve tal cual y quien la comparte la recibe del
    mismo sitio que la ve. Un fichero intermedio solo añadiría una copia que puede quedar vieja.
    """
    memoria = BytesIO()
    dibujar(foto, memoria)
    return memoria.getvalue()


# LA PREVIA DE LAS REDES ES APAISADA, y no la tarjeta encogida por las bravas.
#
# EL PROBLEMA: X, WhatsApp y Facebook recortan la imagen de previsualización a ~1.91:1. La tarjeta es
# 4:5 —vertical— así que un recorte a ese ancho se lleva por delante la cabecera con la marca y el pie
# con la dirección del sitio, que son justo las dos cosas por las que se comparte.
#
# NINGUNA RED PERMITE ADJUNTAR LA IMAGEN por un enlace de compartir: el intent de X no tiene parámetro
# para media, y subirla exige la API con OAuth publicando en nombre del usuario. Así que la previa ES
# lo que la gente ve al pegar el enlace, y tiene que verse entera.
#
# La solución es encajarla completa sobre el azul de la marca. Sobra sitio a los lados y ahí no va
# nada: la tarjeta ya se explica sola, y meter texto duplicado competiría con el que la red pinta
# debajo con el título y la descripción.
PREVIA_W, PREVIA_H = 1200, 630


def previa(foto: dict[str, Any], base: bytes | None = None) -> bytes:
    """La tarjeta encajada en 1200x630 para la previsualización de las redes.

    `base` son los bytes de la tarjeta vertical si quien llama ya los tiene. Sin ellos hay que
    dibujarla entera otra vez —abrir tipografías, leer retratos, pintar quince filas— solo para
    reescalarla, que es el trabajo caro repetido por nada.
    """
    tarjeta_img = Image.open(BytesIO(base if base is not None else png(foto))).convert("RGB")
    lienzo = Image.new("RGB", (PREVIA_W, PREVIA_H), NAVY)

    escala = min(PREVIA_W / tarjeta_img.width, PREVIA_H / tarjeta_img.height)
    ancho, alto = round(tarjeta_img.width * escala), round(tarjeta_img.height * escala)
    lienzo.paste(
        tarjeta_img.resize((ancho, alto), Image.Resampling.LANCZOS),
        ((PREVIA_W - ancho) // 2, (PREVIA_H - alto) // 2),
    )

    memoria = BytesIO()
    lienzo.save(memoria, format="PNG", optimize=True)
    return memoria.getvalue()
