"""«Letra chica»: un estilo de texto pequeño para dentro del párrafo.

PARA QUÉ
--------
Lo que un artículo de datos necesita decir sin robarle peso al texto: de dónde salió una cifra, qué
temporadas cubre, una salvedad metodológica, un crédito. Escrito al mismo tamaño que el cuerpo, eso
compite con lo que se está contando; en letra chica se lee igual pero no interrumpe.

POR QUÉ UN ESTILO EN LÍNEA Y NO UN BLOQUE NUEVO
-----------------------------------------------
Un bloque «Nota» solo sirve para párrafos enteros. Esto vale para las dos cosas: se selecciona media
frase y se achica, o se selecciona el párrafo completo y queda entero en chico. Un bloque aparte
habría que elegirlo del menú y no serviría para la aclaración de tres palabras a mitad de frase, que
es el caso más frecuente.

POR QUÉ `<small>` Y NO UN `<span>` CON CLASE
--------------------------------------------
`<small>` significa exactamente esto en HTML —letra pequeña, comentario al margen, letra legal— así
que un lector de pantalla y un buscador lo entienden sin que haya que explicarles una clase nuestra.
Y sobrevive a un cambio de diseño: si mañana se rehace el CSS, el texto sigue marcado como lo que es.

El tamaño real lo pone `site.css`; lo que se guarda en la base es la etiqueta, no un `font-size`
escrito a mano. Sin esa separación, cambiar el cuerpo del artículo obligaría a reeditar los artículos
viejos uno por uno.
"""

from typing import Any

from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import InlineStyleElementHandler
from wagtail.admin.rich_text.editors.draftail import features as draftail_features

NOMBRE = "letra-chica"
# El nombre interno del estilo dentro del editor. En mayúsculas por convención de Draft.js.
ESTILO = "SMALL"


# El decorador de Wagtail no está tipado y mypy contagia eso a la función entera. La alternativa
# —envolverlo— sería más código para tapar una carencia de la librería.
@hooks.register("register_rich_text_features")  # type: ignore[untyped-decorator]
def registrar_letra_chica(features: Any) -> None:  # noqa: ANN401 — la firma es la del hook de Wagtail
    """Suma el botón al editor y enseña a Wagtail a guardar y leer `<small>`.

    Las dos mitades son necesarias y se olvidan por separado: sin `register_editor_plugin` no hay
    botón, y sin `register_converter_rule` el botón existe pero Wagtail tira la etiqueta al guardar
    —su limpiador borra todo lo que no esté declarado— y el texto vuelve a tamaño normal solo, sin
    decir nada.
    """
    features.register_editor_plugin(
        "draftail",
        NOMBRE,
        draftail_features.InlineStyleFeature(
            {
                "type": ESTILO,
                "label": "aA",  # se ve en la barra del editor; dos tamaños, que es lo que hace
                "description": "Letra chica",
                # Solo para la VISTA PREVIA dentro del editor, que así se parece al resultado. Lo que
                # manda en la página publicada es `site.css`.
                "style": {"fontSize": "0.82em"},
            }
        ),
    )
    features.register_converter_rule(
        "contentstate",
        NOMBRE,
        {
            "from_database_format": {"small": InlineStyleElementHandler(ESTILO)},
            "to_database_format": {"style_map": {ESTILO: "small"}},
        },
    )
