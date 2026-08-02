"""Los bloques con los que se arma el cuerpo de un artículo.

Un StreamField y no un campo de texto enriquecido gigante: lo que se escribe acá es periodismo de
datos, así que una tabla y un gráfico son tan parte del texto como un párrafo, y meterlos como HTML
pegado dentro de un editor los deja sin estilo propio y sin poder cambiarles la presentación después.

EL GRÁFICO SE DIBUJA EN EL SERVIDOR, EN SVG, SIN LIBRERÍA
--------------------------------------------------------
Es la decisión menos obvia del módulo, así que va explicada. Las alternativas eran una librería de
gráficos por CDN o que el editor suba una imagen.

* **Por CDN, no**: el sitio ya arrastra Bootstrap de un CDN sin `integrity` y eso está anotado como
  deuda a pagar en la Fase 8. Sumar otra dependencia externa ahora es ir en la dirección contraria de
  «resiliencia > features», que es el principio #0 del proyecto.
* **Una imagen subida, tampoco**: no se puede corregir un dato sin rehacer el archivo, no se puede
  leer con un lector de pantalla y se ve borrosa en pantalla densa.

Dibujarlo acá sale gratis en dependencias, funciona con JavaScript apagado, se imprime bien, escala
sin pixelarse y el dato queda EN la base — o sea que un número mal tecleado se arregla editando el
bloque, no rehaciendo una imagen.

Lo que NO hace: no lee de nuestras tablas. Los valores los teclea quien escribe. Un bloque que se
alimentara solo de `Batting` tendría que saber de temporadas, filtros y umbrales, y el primer
artículo que quisiera comparar otra cosa se quedaría sin bloque.
"""

import re
from decimal import Decimal
from typing import Any, ClassVar

from wagtail import blocks
from wagtail.contrib.table_block.blocks import TableBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock
from wagtail_footnotes.blocks import RichTextBlockWithFootnotes

# El lienzo del gráfico, en unidades del `viewBox`. No son píxeles: el SVG se estira al ancho de la
# columna y estas medidas solo fijan la proporción.
ANCHO = 720
# Más apaisado que un 4:3. La lámina se estira al ancho de la columna y el alto sale de esta
# proporción, así que ensanchar la columna sin achatar el gráfico habría hecho el artículo MÁS largo
# hacia abajo — lo contrario de lo que se buscaba al ensancharla.
ALTO = 250
# Deja sitio para las cifras del eje vertical (izquierda) y las etiquetas del horizontal (abajo).
MARGEN_ARRIBA, MARGEN_DERECHA, MARGEN_ABAJO, MARGEN_IZQUIERDA = 14, 14, 36, 52
# Cuánto del espacio de cada columna ocupa la barra. El resto es aire entre barras.
GROSOR_BARRA = 0.62
# Tres líneas de referencia (0, mitad, tope). Más se convierten en una rejilla que compite con el dato.
REFERENCIAS = 3


def cifra(valor: Decimal | float) -> str:
    """El número como lo escribe el sitio: sin ceros de relleno y sin el cero de la izquierda.

    `.282` y no `0.282`, que es la convención del béisbol y la que ya usan las tablas del perfil.
    """
    texto = f"{Decimal(str(valor)).normalize():f}"
    if texto.startswith("0.") or texto.startswith("-0."):
        texto = texto.replace("0.", ".", 1)
    return texto


def _escala(valores: list[Decimal], *, es_barra: bool) -> tuple[Decimal, Decimal]:
    """De dónde a dónde va el eje vertical. La regla NO es la misma para barras que para líneas.

    **Las barras empiezan en cero, siempre.** Lo que se compara en una barra es su LARGO, así que
    cortar el eje por abajo multiplica visualmente una diferencia que no existe: 41 jonrones contra
    43 se ven como el doble. En un sitio de estadísticas eso no es un adorno, es una mentira.

    **La línea no.** Ahí el dato es la posición del punto y lo que se lee es la PENDIENTE, no la
    distancia al suelo. Obligarla a empezar en cero aplasta la serie contra el borde de arriba: cinco
    temporadas de wOBA entre .372 y .419 salían como una raya recta con dos tercios de la lámina en
    blanco debajo, o sea el gráfico no contaba nada. Se le deja un respiro arriba y abajo para que la
    serie no toque los bordes, y las cifras del eje dicen dónde empieza de verdad.
    """
    if es_barra:
        # De `min(0, …)` a `max(0, …)`, y NO de cero al máximo. En béisbol hay métricas negativas
        # todos los días —OAA, DRS, run value, WPA, RE24, el WAR en muestras cortas— y con la escala
        # vieja el gráfico no se equivocaba un poco: se rompía. Comprobado antes de arreglarlo: con
        # `[-8, -2]` el tope salía -2, o sea RANGO NEGATIVO, y la proporción daba 4 — una barra
        # cuatro veces más alta que el lienzo. Con `[5, -3]` el alto salía negativo y el `<rect>`
        # sencillamente no se dibujaba: la barra desaparecía sin avisar.
        #
        # El cero sigue dentro del dominio siempre, que es lo que hace honesta la comparación de
        # largos; lo que cambia es que ahora puede no ser el suelo.
        piso, techo = min(Decimal(0), min(valores)), max(Decimal(0), max(valores))
        return (piso, techo) if piso != techo else (piso, techo + 1)

    piso, techo = min(valores), max(valores)
    # Una serie plana necesita un margen inventado: sin él el rango sería cero y no habría con qué
    # dividir. Con el margen queda una recta por el medio, que es justo lo que el dato dice.
    respiro = (techo - piso) / 5 if piso != techo else (abs(piso) / 10 or Decimal(1))
    return piso - respiro, techo + respiro


class PuntoBlock(blocks.StructBlock):
    """Un dato del gráfico: cómo se llama y cuánto vale."""

    etiqueta = blocks.CharBlock(max_length=20, label="Etiqueta", help_text="Lo que va debajo: 2024, SS, Soto…")
    valor = blocks.DecimalBlock(label="Valor", decimal_places=3)

    class Meta:
        label = "Dato"


class GraficoBlock(blocks.StructBlock):
    """Un gráfico de barras o de línea, dibujado como SVG en el servidor. Ver la cabecera del módulo."""

    titulo = blocks.CharBlock(max_length=120, label="Título")
    tipo = blocks.ChoiceBlock(
        choices=[("barras", "Barras"), ("linea", "Línea")],
        default="barras",
        label="Tipo",
        help_text="Barras para comparar cosas distintas; línea para una misma cosa a lo largo del tiempo.",
    )
    puntos = blocks.ListBlock(PuntoBlock(), label="Datos", min_num=2)
    # OBLIGATORIA desde el 2026-07-27, por decisión del dueño. El texto de ayuda ya decía la regla
    # —un gráfico sin fuente no se puede comprobar— y el modelo no la hacía cumplir: un lector podía
    # ver una comparación de WAR sin saber si salía de MLB, de Savant, de FanGraphs o de nuestro
    # cálculo, y eso convierte un dato en una afirmación.
    #
    # El `default` está puesto para que la regla no obligue a inventarse una fuente externa cuando el
    # dato sale de nuestras propias tablas: llega escrito y el redactor lo cambia si toca.
    fuente = blocks.CharBlock(
        max_length=160,
        required=True,
        default="Cálculo propio sobre datos de dglweb",
        label="Fuente",
        help_text="De dónde sale el dato. Un gráfico sin fuente no se puede comprobar.",
    )

    class Meta:
        label = "Gráfico"
        icon = "table"
        template = "articles/blocks/_grafico.html"

    def get_context(self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Convierte los datos en geometría. Toda la cuenta pasa acá; la plantilla solo pinta.

        La plantilla de Django no sabe restar ni dividir, así que si esto no se calculara en Python
        habría que meter filtros aritméticos —o peor, JavaScript— para dibujar una barra.
        """
        contexto = super().get_context(value, parent_context)
        puntos = list(value["puntos"])
        valores = [Decimal(str(p["valor"])) for p in puntos]
        piso, techo = _escala(valores, es_barra=value["tipo"] == "barras")

        util_ancho = ANCHO - MARGEN_IZQUIERDA - MARGEN_DERECHA
        util_alto = ALTO - MARGEN_ARRIBA - MARGEN_ABAJO
        paso = util_ancho / len(puntos)
        rango = techo - piso

        def altura_de(valor: Decimal) -> float:
            """La coordenada `y` que le toca a un valor. Arriba es menos, como en todo SVG."""
            return MARGEN_ARRIBA + util_alto * (1 - float((valor - piso) / rango))

        # La barra va DEL CERO AL VALOR, no del suelo al valor. Con todo positivo es lo mismo —el
        # cero es el suelo— y con negativos es la diferencia entre un gráfico correcto y uno roto.
        suelo = altura_de(Decimal(0)) if piso <= 0 <= techo else altura_de(piso)

        barras = []
        for indice, (punto, valor) in enumerate(zip(puntos, valores, strict=True)):
            centro = MARGEN_IZQUIERDA + paso * (indice + 0.5)
            alto_valor = altura_de(valor)
            barras.append(
                {
                    "etiqueta": punto["etiqueta"],
                    "valor": cifra(valor),
                    "centro": round(centro, 2),
                    "x": round(centro - (paso * GROSOR_BARRA) / 2, 2),
                    "ancho": round(paso * GROSOR_BARRA, 2),
                    # `y` es siempre el borde de ARRIBA del rectángulo y `alto` nunca es negativo:
                    # un `<rect>` con alto negativo es inválido y el navegador no lo dibuja ni se
                    # queja. Para una barra negativa, el borde de arriba es el cero.
                    "y": round(min(suelo, alto_valor), 2),
                    "alto": round(abs(alto_valor - suelo), 2),
                    # `baja` es solo para el color; la cifra va igual en las dos: encima del borde
                    # SUPERIOR del rectángulo, que en una barra positiva es su punta y en una
                    # negativa es la línea del cero.
                    #
                    # Primero la puse debajo de la barra negativa, que parece lo natural, y la
                    # barra más profunda —la que toca el suelo del lienzo— dejaba su cifra encima de
                    # la etiqueta del eje: se leía «-6» pisando «Santander». Encima del borde de
                    # arriba no choca nunca, porque ahí no hay nada dibujado.
                    "baja": valor < 0,
                }
            )

        # En la línea, la cifra de un valle va DEBAJO del punto. Encima la cruza el propio trazo —la
        # línea sube por los dos lados— y el número queda tachado por su propio gráfico. En una cima
        # o en una pendiente no pasa, así que solo se baja donde estorba.
        for indice, barra in enumerate(barras):
            vecinos = valores[max(indice - 1, 0) : indice + 2]
            barra["debajo"] = valores[indice] == min(vecinos) and len(set(vecinos)) > 1

        decimales = max(-exponente for v in valores if isinstance(exponente := v.as_tuple().exponent, int))
        contexto["barras"] = barras
        contexto["linea"] = " ".join(f"{b['centro']},{b['y']}" for b in barras)
        contexto["referencias"] = [
            {
                "y": round(MARGEN_ARRIBA + util_alto * (1 - indice / (REFERENCIAS - 1)), 2),
                # Redondeadas a los decimales que trae el dato: con una escala que no empieza en cero
                # el punto medio sale con cifras que nadie tecleó (.20950000) y ensucian el eje.
                "valor": cifra(round(piso + rango * indice / (REFERENCIAS - 1), min(decimales, 3))),
            }
            for indice in range(REFERENCIAS)
        ]
        contexto["lienzo"] = {"ancho": ANCHO, "alto": ALTO, "base": MARGEN_ARRIBA + util_alto}
        # La línea del cero, marcada aparte y solo cuando cae dentro del dibujo. Antes se daba por
        # supuesto que era la referencia de más abajo —y con barras siempre positivas lo era— pero
        # con negativos el cero queda a media altura y es justamente la línea contra la que se lee si
        # un valor está por encima o por debajo. En un gráfico de línea con rango acotado (wOBA entre
        # .372 y .419) el cero ni siquiera entra en la lámina, y ahí no se dibuja.
        contexto["cero"] = round(suelo, 2) if piso <= 0 <= techo else None
        # Para quien no ve el dibujo: el gráfico entero en una frase, que es lo que lee el lector de
        # pantalla. Sin esto el SVG es un hueco silencioso en mitad del artículo.
        contexto["resumen"] = "; ".join(f"{b['etiqueta']}: {b['valor']}" for b in barras)
        return contexto


# DE DÓNDE SE SACA EL IDENTIFICADOR. Las tres formas en que YouTube reparte un enlace, y ninguna más:
# el de la barra de direcciones, el de «Compartir», y el de un Short. Se aceptan las tres porque el
# editor va a pegar la que le dé la página en la que esté, no la que a nosotros nos convenga.
_YOUTUBE = (
    re.compile(r"^https?://(?:www\.)?youtube\.com/watch\?(?:.*&)?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"^https?://youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
)


def id_de_youtube(url: str) -> str:
    """Los once caracteres del video, o cadena vacía si eso no es un enlace de YouTube.

    Once exactos y con el alfabeto acotado: un identificador de YouTube siempre los tiene. Aceptar
    cualquier cosa dejaría que un error de copiar y pegar acabara en un `src` del HTML publicado.
    """
    for patron in _YOUTUBE:
        if encontrado := patron.match((url or "").strip()):
            return encontrado.group(1)
    return ""


class VideoBlock(blocks.StructBlock):
    """Un video de YouTube incrustado en el cuerpo del artículo.

    SE ARMA EL `iframe` A MANO Y NO SE USA `EmbedBlock`, que es la pieza que Wagtail trae para esto.
    El motivo es concreto: `EmbedBlock` resuelve el enlace por oEmbed y devuelve **lo que YouTube le
    dé**, que es un marco de `youtube.com`. Nosotros incrustamos desde `youtube-nocookie.com`, que es
    el dominio que YouTube publica justamente para no dejar cookies de seguimiento hasta que el
    visitante le da al play.

    Con `EmbedBlock` esa garantía dependería de que un tercero no cambie su respuesta. Armándolo acá,
    la única URL que puede salir al HTML es la que escribe esta clase.

    LO QUE ESTE BLOQUE ARRASTRA, y por eso no existía hasta hoy:

    * **La CSP.** `frame-src` tuvo que dejar entrar a `youtube-nocookie.com`. Era una lista de uno
      —el servidor de anuncios— y ahora son dos. Ver `core/csp.py`.
    * **El aviso de privacidad.** El sitio declaraba que la analítica era el único tercero que carga
      la parte pública. Ya no lo es, y eso está escrito en `legal/privacidad.html` y en la política de
      cookies.

    No es papeleo: al abrir un artículo con video, el navegador del lector se conecta a Google y le
    deja su IP, haya pulsado o no el play. Se elige `nocookie` para que al menos no le dejen también
    un identificador persistente.
    """

    url = blocks.URLBlock(
        label="Enlace de YouTube",
        help_text="Pega el enlace tal cual: el de la barra, el de «Compartir» o el de un Short.",
    )
    pie = blocks.CharBlock(max_length=200, required=False, label="Pie", help_text="Opcional: qué se ve.")

    class Meta:
        label = "Video de YouTube"
        icon = "media"
        template = "articles/blocks/_video.html"

    def clean(self, value: blocks.StructValue) -> blocks.StructValue:
        """Rechaza al guardar lo que no sea YouTube, y no al pintar.

        Un enlace de Vimeo o una dirección con una errata tienen que parar en el CMS, con el editor
        delante y pudiendo corregirlo. Dejarlo pasar significaría o un marco vacío en el artículo
        publicado, o —peor— un `iframe` a un dominio que la CSP no permite y que el lector ve como un
        hueco blanco sin explicación.
        """
        from django.core.exceptions import ValidationError

        limpio = super().clean(value)
        if not id_de_youtube(limpio.get("url") or ""):
            raise ValidationError(
                "Eso no parece un enlace de YouTube.",
                params={"url": ["Se aceptan youtube.com/watch, youtu.be y youtube.com/shorts."]},
            )
        return limpio

    def get_context(self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None) -> dict[str, Any]:
        contexto = super().get_context(value, parent_context)
        contexto["video_id"] = id_de_youtube(value.get("url") or "")
        return contexto


# EL HOST DE LOS VIDEOS DE MLB. `mlb.com` reparte sus clips para incrustar a través de Streamable: el
# botón de compartir de una página de video devuelve un `<iframe>` apuntando acá, con un `partnerId`
# suyo en la consulta. Comprobado por el dueño copiándolo de mlb.com.
#
# Se acepta con o sin `www.` porque las dos formas circulan, y NADA MÁS: el patrón está anclado al
# principio, así que `streamable.com.otro-sitio.test` no cuela.
_STREAMABLE = re.compile(r"^https://(?:www\.)?streamable\.com/([^\s\"'<>]+)$")


def ruta_de_streamable(url: str) -> str:
    """Lo que va después del dominio, o cadena vacía si eso no es un enlace de Streamable.

    Se conserva la ruta ENTERA, con su cadena de consulta. MLB reparte `/m/<slug>?partnerId=…` y ese
    `partnerId` es suyo; quitarlo sería adivinar que no hace falta. Lo que sí se garantiza es el
    dominio: la URL que sale al HTML la vuelve a armar esta función, así que por muy raro que sea lo
    que peguen, el `src` publicado empieza siempre por `https://streamable.com/`.
    """
    encontrado = _STREAMABLE.match((url or "").strip())
    return encontrado.group(1) if encontrado else ""


class VideoMlbBlock(blocks.StructBlock):
    """Un video de MLB incrustado en el cuerpo del artículo.

    EL ENLACE ES DE `streamable.com` Y ESO NO ES UN ERROR. MLB usa Streamable para repartir sus clips
    incrustables: el botón de compartir de una página de video de `mlb.com` devuelve un `<iframe>`
    apuntando ahí. Es el enlace que el dueño va a pegar, así que es el que este bloque acepta.

    NO ES LO MISMO QUE EL TELEVISORCITO de la pizarra y los destacados. Aquel sirve el `.mp4` directo
    desde `*.mlb.com` en un `<video>` nuestro, y solo tiene los clips que la API asocia a un dominicano
    en una jornada. Este acepta cualquier video de MLB que el redactor encuentre y quiera citar, al
    precio de incrustar un documento ajeno.

    Del enlace pegado solo sobrevive la RUTA: el dominio lo escribe la plantilla. Así, pegue lo que
    pegue el editor, el `src` publicado no puede apuntar a otro sitio.
    """

    url = blocks.URLBlock(
        label="Enlace del video de MLB",
        help_text="El que da mlb.com al compartir. Empieza por streamable.com — pégalo tal cual.",
    )
    pie = blocks.CharBlock(max_length=200, required=False, label="Pie", help_text="Opcional: qué se ve.")

    class Meta:
        label = "Video de MLB"
        icon = "media"
        template = "articles/blocks/_video_mlb.html"

    def clean(self, value: blocks.StructValue) -> blocks.StructValue:
        from django.core.exceptions import ValidationError

        limpio = super().clean(value)
        if not ruta_de_streamable(limpio.get("url") or ""):
            raise ValidationError(
                "Ese no es el enlace que da MLB.",
                params={
                    "url": ["Tiene que empezar por https://streamable.com/ — es lo que devuelve el botón de compartir."]
                },
            )
        return limpio

    def get_context(self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None) -> dict[str, Any]:
        contexto = super().get_context(value, parent_context)
        contexto["ruta"] = ruta_de_streamable(value.get("url") or "")
        return contexto


class JugadorBlock(blocks.StructBlock):
    """Una mención a un pelotero, enlazada a su ficha.

    Se elige de `dgl_master` y no se teclea el nombre: así el enlace no se rompe, la foto sale sola y
    —lo que importa— el artículo queda conectado al resto del sitio en vez de ser una isla de texto.
    """

    jugador = SnippetChooserBlock("players.Player", label="Jugador")
    nota = blocks.CharBlock(
        max_length=160,
        required=False,
        label="Apunte",
        help_text="Opcional: por qué viene a cuento acá.",
    )

    class Meta:
        label = "Mención de jugador"
        icon = "user"
        template = "articles/blocks/_jugador.html"

    def get_context(self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Añade el enlace y el retrato, que el modelo `Player` no sabe dar por su cuenta.

        `Player` es la fila del maestro y no conoce las URLs del sitio ni dónde viven las fotos;
        resolverlo acá evita meterle al modelo dos cosas que solo le importan a la parte pública.
        """
        from django.urls import reverse

        from dglweb.players import mugshots
        from dglweb.players.models import Player

        contexto = super().get_context(value, parent_context)
        jugador = value.get("jugador")
        if jugador is not None:
            # El enlace SOLO si el jugador es visible en el sitio. El selector del CMS ofrece a
            # todos —el modelo declara `default_manager_name = "todos"`, que incluye a los
            # deshabilitados— pero el perfil público usa `Player.objects`, que los excluye y devuelve
            # 404. Sin esta comprobación, un artículo publicado hoy queda con un enlace roto el día
            # que el dueño deshabilite a ese jugador (SAB-03 del v8). Sin enlace, el nombre sigue
            # saliendo: la mención es del artículo y no depende de que la ficha exista.
            visible = Player.objects.filter(pk=jugador.pk).exists()
            contexto["enlace"] = reverse("player_detail", args=[jugador.slug]) if visible else ""
            # Vacío si el archivo no está —un tercio del maestro— y la plantilla no dibuja nada.
            contexto["foto"] = (
                mugshots.url(jugador.player_id, mugshots.CHICO)
                if mugshots.existe(jugador.player_id, mugshots.CHICO)
                else ""
            )
        return contexto


class TablaHtmlBlock(blocks.TextBlock):
    """Una tabla pegada como HTML, filtrada por lista blanca. Ver `articles/tablas.py`.

    Convive con el bloque `tabla` en vez de sustituirlo, y no es indecisión: para cuatro filas por
    cinco columnas la cuadrícula del editor es más cómoda que pegar etiquetas. Este es para lo que
    aquella no puede — encabezados de dos niveles, notas al pie, y cientos de filas que salen de un
    script y nadie va a teclear a mano.

    SE GUARDA YA LIMPIO, Y ADEMÁS SE VUELVE A LIMPIAR AL PINTAR
    -----------------------------------------------------------
    `clean` devuelve el HTML filtrado, así que en la base queda la versión de 36 KB y no los 216 KB
    del archivo original — y el editor VE lo que sobrevivió, que es la mejor manera de enterarse de
    que algo se cayó.

    Y `get_context` lo filtra otra vez antes de pintar. Parece redundante y no lo es: lo primero
    depende de que el valor haya entrado por el formulario, y una importación, una migración de datos
    o un `StreamField` escrito a mano no pasan por ahí. Lo que se marca como seguro se acaba de
    revisar en esta misma petición, y eso no depende de la historia del registro.

    Que las dos pasadas usen la MISMA función obliga a que lo guardado se pueda volver a leer. La
    primera versión no cumplía eso —guardaba la tabla sin su `<table>`, que era justo lo que la
    función necesitaba para encontrarla— y el bloque quedaba imposible de reeditar. Ver `tablas.py`.
    """

    # Las del sitio, las mismas de la ficha del jugador. Van acá y no en el filtro: la presentación es
    # de esta capa, y al guardar se llama sin ellas para que en la base quede estructura pura.
    CLASES = "table table-sm table-striped dgl-stats-table mb-0"

    class Meta:
        label = "Tabla (HTML)"
        icon = "table"
        template = "articles/blocks/_tabla_html.html"
        help_text = (
            "Pega el HTML de la tabla. Se conservan colspan, rowspan, scope, <caption> y <tfoot>; "
            "se descarta el estilo, que lo pone el sitio. Para alinear, una vez por columna: "
            '<colgroup><col class="izq"><col class="der">…</colgroup> — izq, centro o der.'
        )

    def clean(self, value: str) -> str:
        from django.core.exceptions import ValidationError

        from dglweb.articles import tablas

        limpio = super().clean(value)
        try:
            return tablas.limpiar(limpio)
        except tablas.SinTablaError as error:
            raise ValidationError(str(error)) from error

    def get_context(self, value: str, parent_context: dict[str, Any] | None = None) -> dict[str, Any]:
        from django.utils.safestring import mark_safe

        from dglweb.articles import tablas

        contexto = super().get_context(value, parent_context)
        try:
            # `mark_safe` sobre la salida del filtro y no sobre lo pegado. Es la única forma de que un
            # `colspan` llegue al navegador, y es segura justo porque lo de la línea de arriba acaba
            # de decidir qué puede llegar.
            contexto["contenido"] = mark_safe(tablas.limpiar(value, clases=self.CLASES))
        except tablas.SinTablaError:
            # Un artículo publicado no se rompe por una tabla mala: se queda sin ella. El bloque no
            # debería poder llegar acá —`clean` no lo deja pasar— así que esto cubre lo que entró por
            # otra puerta.
            contexto["contenido"] = ""
        return contexto


class CuerpoStreamBlock(blocks.StreamBlock):
    """Lo que puede llevar un artículo. El orden es el del menú del editor: lo común primero."""

    # `RichTextBlockWithFootnotes` Y NO `RichTextBlock`, y no es intercambiable: es la clase que sabe
    # convertir el `<footnote id="…">` que guarda el editor en el numerito enlazado, y que va dejando
    # las notas encontradas en el objeto `page` para que la lista del final las pueda pintar en el
    # orden en que aparecen. Con el bloque normal, el editor deja poner la nota y el artículo publicado
    # no la enseña — ni el marcador ni el texto.
    parrafo = RichTextBlockWithFootnotes(
        label="Párrafo",
        icon="pilcrow",
        # Deliberadamente corto. Los títulos, las imágenes y las tablas tienen su propio bloque, así
        # que dejarlos también acá dentro daría dos maneras de hacer lo mismo con distinto estilo.
        #
        # `letra-chica` es nuestra y sale de `articles/wagtail_hooks.py`: guarda un `<small>` para
        # las salvedades, las fuentes y los créditos. Es la única excepción a la regla de arriba, y
        # se gana el sitio porque no duplica ningún bloque — no hay otra forma de achicar un trozo.
        #
        # `footnotes` la trae la dependencia. Cubre lo que `letra-chica` no puede: aquella achica un
        # trozo EN EL SITIO donde está, y una nota al pie saca la salvedad del renglón y la manda al
        # final, numerada y con enlace de vuelta. En un sitio que explica metodologías —«solo
        # bateadores con 1500 PA»— hacen falta las dos.
        features=["bold", "italic", "link", "ol", "ul", "letra-chica", "footnotes"],
        template="articles/blocks/_parrafo.html",
    )
    titulo = blocks.CharBlock(max_length=120, label="Subtítulo", icon="title", template="articles/blocks/_titulo.html")
    imagen = blocks.StructBlock(
        [
            ("imagen", ImageChooserBlock(label="Imagen")),
            ("pie", blocks.CharBlock(max_length=200, required=False, label="Pie de foto")),
        ],
        label="Imagen",
        icon="image",
        template="articles/blocks/_imagen.html",
    )
    cita = blocks.StructBlock(
        [
            ("texto", blocks.TextBlock(label="Cita")),
            ("quien", blocks.CharBlock(max_length=120, required=False, label="Quién lo dijo")),
        ],
        label="Cita",
        icon="openquote",
        template="articles/blocks/_cita.html",
    )
    tabla = TableBlock(label="Tabla", template="articles/blocks/_tabla.html")
    # Debajo de la cuadrícula porque es la excepción: la de arriba para lo del día a día, esta para la
    # tabla que sale de un script y no cabe en una cuadrícula.
    tabla_html = TablaHtmlBlock()
    grafico = GraficoBlock()
    jugador = JugadorBlock()
    video = VideoBlock()
    video_mlb = VideoMlbBlock()

    class Meta:
        # `ClassVar` porque es configuración del bloque, no un valor por instancia — Wagtail lo lee
        # de la clase. Sin la anotación, ruff lo ve como un diccionario mutable compartido.
        block_counts: ClassVar[dict[str, dict[str, int]]] = {"titulo": {"max_num": 20}}
