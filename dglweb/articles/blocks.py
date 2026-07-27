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

from decimal import Decimal
from typing import Any, ClassVar

from wagtail import blocks
from wagtail.contrib.table_block.blocks import TableBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtail.snippets.blocks import SnippetChooserBlock

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
        return Decimal(0), max(valores) if any(valores) else Decimal(1)

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
    fuente = blocks.CharBlock(
        max_length=160,
        required=False,
        label="Fuente",
        help_text="De dónde sale el dato. Un gráfico sin fuente no se puede comprobar.",
    )

    class Meta:
        label = "Gráfico"
        icon = "table"
        template = "articles/blocks/_grafico.html"

    def get_context(
        self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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

        barras = []
        for indice, (punto, valor) in enumerate(zip(puntos, valores, strict=True)):
            proporcion = float((valor - piso) / rango)
            centro = MARGEN_IZQUIERDA + paso * (indice + 0.5)
            alto = util_alto * proporcion
            barras.append(
                {
                    "etiqueta": punto["etiqueta"],
                    "valor": cifra(valor),
                    "centro": round(centro, 2),
                    "x": round(centro - (paso * GROSOR_BARRA) / 2, 2),
                    "ancho": round(paso * GROSOR_BARRA, 2),
                    "y": round(MARGEN_ARRIBA + util_alto - alto, 2),
                    "alto": round(alto, 2),
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
        # Para quien no ve el dibujo: el gráfico entero en una frase, que es lo que lee el lector de
        # pantalla. Sin esto el SVG es un hueco silencioso en mitad del artículo.
        contexto["resumen"] = "; ".join(f"{b['etiqueta']}: {b['valor']}" for b in barras)
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

    def get_context(
        self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Añade el enlace y el retrato, que el modelo `Player` no sabe dar por su cuenta.

        `Player` es la fila del maestro y no conoce las URLs del sitio ni dónde viven las fotos;
        resolverlo acá evita meterle al modelo dos cosas que solo le importan a la parte pública.
        """
        from django.urls import reverse

        from dglweb.players import mugshots

        contexto = super().get_context(value, parent_context)
        jugador = value.get("jugador")
        if jugador is not None:
            contexto["enlace"] = reverse("player_detail", args=[jugador.slug])
            # Vacío si el archivo no está —un tercio del maestro— y la plantilla no dibuja nada.
            contexto["foto"] = (
                mugshots.url(jugador.player_id, mugshots.CHICO)
                if mugshots.existe(jugador.player_id, mugshots.CHICO)
                else ""
            )
        return contexto


class CuerpoStreamBlock(blocks.StreamBlock):
    """Lo que puede llevar un artículo. El orden es el del menú del editor: lo común primero."""

    parrafo = blocks.RichTextBlock(
        label="Párrafo",
        icon="pilcrow",
        # Deliberadamente corto. Los títulos, las imágenes y las tablas tienen su propio bloque, así
        # que dejarlos también acá dentro daría dos maneras de hacer lo mismo con distinto estilo.
        features=["bold", "italic", "link", "ol", "ul"],
        template="articles/blocks/_parrafo.html",
    )
    titulo = blocks.CharBlock(
        max_length=120, label="Subtítulo", icon="title", template="articles/blocks/_titulo.html"
    )
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
    grafico = GraficoBlock()
    jugador = JugadorBlock()

    class Meta:
        # `ClassVar` porque es configuración del bloque, no un valor por instancia — Wagtail lo lee
        # de la clase. Sin la anotación, ruff lo ve como un diccionario mutable compartido.
        block_counts: ClassVar[dict[str, dict[str, int]]] = {"titulo": {"max_num": 20}}
