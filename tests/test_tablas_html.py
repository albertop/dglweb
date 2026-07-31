"""El filtro de tablas pegadas: qué entra, qué se cae y qué no puede pasar nunca.

Las pruebas de seguridad no comprueban «que no explote»: comprueban que la etiqueta peligrosa NO
ESTÉ en la salida. Un filtro que deja pasar `<script>` sin ejecutarlo hoy lo ejecuta mañana, cuando
esa salida se pegue en otro sitio.
"""

import pytest

from dglweb.articles.blocks import TablaHtmlBlock
from dglweb.articles.tablas import SinTablaError, limpiar

# La forma que tiene una salida de `gt` de R: título y subtítulo como filas anchas, encabezado de dos
# niveles con `colspan`, y la hoja de estilos entera colgada de un id aleatorio.
COMO_GT = """
<div id="emvpzbznrf" style="padding-left:0px">
  <style>#emvpzbznrf table { font-family: Tahoma; }</style>
  <table class="gt_table" data-quarto-disable-processing="false">
    <thead>
      <tr><td colspan="7" class="gt_heading"><strong>Best &amp; Worst Players by WAR</strong></td></tr>
      <tr>
        <th colspan="1" rowspan="2" scope="col" class="gt_col_heading">Seasons</th>
        <th colspan="3" rowspan="1" scope="colgroup"><span><strong>Best Hitters</strong></span></th>
        <th colspan="3" rowspan="1" scope="colgroup">
          <span><strong>Worst Hitters</strong><span><sup>1</sup></span></span>
        </th>
      </tr>
      <tr>
        <th scope="col" class="gt_col_heading">Name</th><th scope="col">Age</th><th scope="col">WAR</th>
        <th scope="col">Name</th><th scope="col">Age</th><th scope="col">WAR</th>
      </tr>
    </thead>
    <tbody class="gt_table_body">
      <tr>
        <td class="gt_row gt_center">1876-1880</td>
        <td class="gt_row">Cap Anson</td><td class="gt_row">24-28</td><td class="gt_row">14.9</td>
        <td class="gt_row">Jack Burdock</td><td class="gt_row">24-28</td><td class="gt_row">6.6</td>
      </tr>
    </tbody>
    <tfoot><tr><td colspan="7">Only hitters with at least 1500 PA.</td></tr></tfoot>
  </table>
</div>
"""


# ── Lo que la cuadrícula del editor no sabe hacer ───────────────────────────────────────────────


def test_the_two_level_header_survives() -> None:
    """Es la razón de existir del bloque: «Best Hitters» abarcando Name/Age/WAR."""
    salida = limpiar(COMO_GT)

    assert 'colspan="3"' in salida
    assert 'rowspan="2"' in salida
    assert 'scope="colgroup"' in salida


def test_the_caption_and_the_footnotes_survive() -> None:
    """Sin la metodología —1500 PA— la tabla afirma algo que no es."""
    salida = limpiar(COMO_GT)

    assert "Only hitters with at least 1500 PA." in salida
    assert "<tfoot>" in salida
    assert "<sup>1</sup>" in salida


def test_the_whole_gt_file_can_be_pasted_as_is() -> None:
    """No hay que preparar nada en R: se pega el archivo y el estilo ajeno se cae solo."""
    salida = limpiar(COMO_GT)

    assert "Tahoma" not in salida
    assert "gt_table" not in salida
    assert "emvpzbznrf" not in salida
    assert "style=" not in salida
    assert "class=" not in salida
    # Y el dato, entero.
    assert "Cap Anson" in salida
    assert "1876-1880" in salida


def test_the_whole_table_comes_back_so_it_can_go_back_in() -> None:
    """LA REGRESIÓN. Lo que se guarda es esta salida, así que tiene que poder volver a entrar.

    La primera versión devolvía solo el interior —sin el `<table>`— y en la base quedaba un valor que
    esta misma función ya no sabía leer. Se veía como tres fallos distintos: al guardar desaparecía el
    `<table>`, el artículo publicado no enseñaba nada, y la página no se dejaba volver a guardar.
    """
    una = limpiar(COMO_GT)
    dos = limpiar(una)

    assert una.lstrip().startswith("<table")
    assert dos == una, "limpiar() no es idempotente: lo guardado no se puede releer"
    assert "Cap Anson" in dos


def test_the_classes_are_decided_by_who_calls_and_not_by_the_filter() -> None:
    """Al guardar, estructura pura; al pintar, las del sitio. Y la segunda pasada no las acumula."""
    guardada = limpiar(COMO_GT)
    pintada = limpiar(guardada, clases="table dgl-stats-table")

    assert "class=" not in guardada
    assert '<table class="table dgl-stats-table">' in pintada
    assert limpiar(pintada, clases="table dgl-stats-table") == pintada


def test_loose_rows_with_no_table_around_them_are_wrapped() -> None:
    """Pasa al copiar un trozo de una hoja de cálculo. Se sabe qué falta, así que se pone."""
    salida = limpiar("<tr><td>Cap Anson</td><td>14.9</td></tr>")

    assert salida.lstrip().startswith("<table")
    assert "Cap Anson" in salida


# ── La alineación por columna ───────────────────────────────────────────────────────────────────


CON_COLGROUP = """
<table>
  <colgroup>
    <col class="izq"><col class="izq"><col class="centro"><col class="der">
  </colgroup>
  <thead>
    <tr>
      <th rowspan="2">Seasons</th>
      <th colspan="3">Best Hitters</th>
    </tr>
    <tr><th>Name</th><th>Age</th><th>WAR</th></tr>
  </thead>
  <tbody>
    <tr><th scope="row">1876-1880</th><td>Cap Anson</td><td>24-28</td><td>14.9</td></tr>
  </tbody>
</table>
"""


def _clases(html: str, selector: str) -> list[object]:
    """Las clases de las celdas que casen, en orden. `select` para no ir encadenando opcionales."""
    from bs4 import BeautifulSoup

    return [celda.get("class") for celda in BeautifulSoup(html, "html.parser").select(selector)]


def test_the_column_alignment_reaches_every_cell() -> None:
    """CSS no puede alinear texto desde un `<col>`, así que la clase hay que bajarla a la celda."""
    assert _clases(limpiar(CON_COLGROUP), "tbody tr > *") == [["izq"], ["izq"], ["centro"], ["der"]]


def test_a_rowspan_above_does_not_shift_the_row_below() -> None:
    """LA TRAMPA. Contando una columna por celda, la segunda fila del encabezado sale corrida.

    `Seasons` lleva `rowspan="2"`, así que en la fila de abajo la columna 0 está ocupada y `Name`
    empieza en la 1. Sumando ingenuamente, `Name` recibiría la alineación de la columna 0.
    """
    assert _clases(limpiar(CON_COLGROUP), "thead tr:nth-child(2) > th") == [["izq"], ["centro"], ["der"]]


def test_a_cell_that_spans_columns_gets_no_alignment() -> None:
    """Un encabezado que cubre tres columnas no tiene una sola respuesta a cómo se alinea."""
    assert _clases(limpiar(CON_COLGROUP), 'thead th[colspan="3"]') == [None]


def test_an_alignment_written_on_the_cell_wins() -> None:
    """Es la excepción, y una excepción que la regla pisara no serviría de nada."""
    salida = limpiar('<table><colgroup><col class="der"></colgroup><tr><td class="izq">Soto</td></tr></table>')

    assert 'class="izq"' in salida


def test_the_alignment_vocabulary_is_closed() -> None:
    """La rendija de `class` no puede dejar entrar las clases de Bootstrap ni las de `gt`."""
    salida = limpiar('<table><tr><td class="gt_row gt_center bg-danger">3-4</td></tr></table>')

    assert "class=" not in salida
    assert "3-4" in salida


def test_alignment_survives_the_round_trip() -> None:
    """Se guarda con la alineación ya puesta, y volver a guardar no la duplica ni la pierde."""
    una = limpiar(CON_COLGROUP)
    dos = limpiar(una)

    assert dos == una
    assert una.count('class="izq"') == dos.count('class="izq"')


def test_a_comment_between_tags_does_not_break_the_round_trip() -> None:
    """Al quitar un comentario queda el espacio que lo rodeaba, y la pasada siguiente lo normaliza
    distinto. Guardar dos veces daba dos textos distintos, y con eso la ida y vuelta dejaba de ser
    exacta — se vio con el `<colgroup>` comentado del archivo de prueba: 5.508 bytes contra 5.505.
    """
    con_comentarios = (
        "<table>\n  <colgroup>\n"
        '    <col class="izq">   <!-- Seasons -->\n'
        '    <col class="der">   <!-- WAR -->\n'
        "  </colgroup>\n"
        "  <tbody>\n    <tr><td>1876</td><td>14.9</td></tr>\n  </tbody>\n</table>"
    )

    una = limpiar(con_comentarios)
    assert limpiar(una) == una
    assert _clases(una, "tbody tr > *") == [["izq"], ["der"]]


def test_the_space_inside_a_cell_is_not_touched() -> None:
    """Entre etiquetas el espacio no se pinta; entre palabras separa. Solo se tira el primero."""
    salida = limpiar("<table>\n  <tr>\n    <td>Cap Anson  Jr.</td>\n  </tr>\n</table>")

    assert "Cap Anson  Jr." in salida
    assert "<tr><td>" in salida


def test_a_broken_colspan_does_not_bring_the_article_down() -> None:
    """Lo pegado viene de fuera; un `colspan="tres"` no puede ser una excepción sin atrapar."""
    salida = limpiar('<table><colgroup><col class="der"></colgroup><tr><td colspan="tres">7</td></tr></table>')

    assert "7" in salida


# ── Lo que no puede pasar nunca ─────────────────────────────────────────────────────────────────


def test_a_script_is_destroyed_with_its_contents() -> None:
    """`unwrap` conservaría el código como texto visible. Tiene que morir entero."""
    salida = limpiar('<table><tr><td>ok<script>alert("x")</script></td></tr></table>')

    assert "<script" not in salida
    assert "alert" not in salida
    assert "ok" in salida


def test_an_event_handler_never_survives() -> None:
    salida = limpiar('<table><tr><td onclick="robar()" onmouseover="x()">3-4</td></tr></table>')

    assert "onclick" not in salida
    assert "onmouseover" not in salida
    assert "3-4" in salida


@pytest.mark.parametrize("destino", ["javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4=", "vbscript:x"])
def test_a_link_to_a_strange_scheme_loses_the_tag(destino: str) -> None:
    """Se va la etiqueta y no solo el atributo: un `<a>` sin `href` es texto subrayado que engaña."""
    salida = limpiar(f'<table><tr><td><a href="{destino}">clic</a></td></tr></table>')

    assert "<a" not in salida
    assert destino not in salida
    assert "clic" in salida


@pytest.mark.parametrize("destino", ["/jugador/juan-soto-665742/", "https://www.mlb.com/stats", "#nota-1"])
def test_a_link_to_a_normal_place_is_kept(destino: str) -> None:
    """El enlace a una ficha del propio sitio es justo lo que hace útil una tabla acá."""
    salida = limpiar(f'<table><tr><td><a href="{destino}">J. Soto</a></td></tr></table>')

    assert f'href="{destino}"' in salida


def test_a_comment_does_not_survive() -> None:
    """`find_all(True)` no los devuelve —no son etiquetas— y llegarían enteros al `str()`."""
    salida = limpiar("<table><tr><td>1<!-- [if IE]><script>x</script><![endif] --></td></tr></table>")

    assert "<!--" not in salida
    assert "script" not in salida


def test_a_style_block_inside_a_cell_dies_too() -> None:
    salida = limpiar("<table><tr><td><style>td{display:none}</style>dato</td></tr></table>")

    assert "display:none" not in salida
    assert "dato" in salida


def test_a_form_never_gets_through() -> None:
    """Un formulario dentro de un artículo solo puede servir para pedir algo que no le toca pedir."""
    salida = limpiar('<table><tr><td><form action="/x"><input name="clave"></form>dato</td></tr></table>')

    assert "<form" not in salida
    assert "<input" not in salida
    assert "dato" in salida


# ── Cuando lo pegado no sirve ───────────────────────────────────────────────────────────────────


def test_pasting_something_that_is_not_a_table_says_so() -> None:
    """Callar y devolver vacío dejaría un hueco en el artículo sin que nadie supiera por qué."""
    with pytest.raises(SinTablaError):
        limpiar("<p>Se me olvidó copiar la tabla.</p>")


def test_a_table_with_no_rows_is_not_a_table() -> None:
    with pytest.raises(SinTablaError):
        limpiar("<table><caption>Solo el título</caption></table>")


def test_the_editor_gets_an_error_instead_of_a_silent_hole() -> None:
    """El bloque traduce el fallo del filtro a un error de formulario de Wagtail."""
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        TablaHtmlBlock().clean("<p>no hay tabla</p>")


# ── Cómo lo guarda y lo pinta el bloque ─────────────────────────────────────────────────────────


def test_what_gets_stored_is_already_clean() -> None:
    """En la base queda la versión filtrada y no los 216 KB del archivo original."""
    guardado = TablaHtmlBlock().clean(COMO_GT)

    assert "Tahoma" not in guardado
    assert len(guardado) < len(COMO_GT)
    assert "Cap Anson" in guardado


def test_it_is_filtered_again_before_painting() -> None:
    """Lo primero depende de haber pasado por el formulario; una importación no pasa por ahí."""
    contexto = TablaHtmlBlock().get_context("<table><tr><td>x<script>alert(1)</script></td></tr></table>")

    assert "alert" not in str(contexto["contenido"])
    assert "<td>x</td>" in str(contexto["contenido"])


def test_a_broken_value_leaves_a_gap_and_not_a_500() -> None:
    """No debería poder llegar acá; si llega, el artículo se queda sin la tabla y no sin la página."""
    contexto = TablaHtmlBlock().get_context("<p>esto no es una tabla</p>")

    assert contexto["contenido"] == ""


def test_a_value_saved_by_the_broken_version_heals_itself() -> None:
    """Lo que quedó en la base mientras `limpiar` devolvía solo el interior.

    Son filas sin `<table>` alrededor, o sea justo el caso que ahora se envuelve. Importa porque hay
    un artículo guardado así: sin esto habría que volver a pegar la tabla a mano.
    """
    de_la_version_rota = (
        "<caption>Best &amp; Worst</caption><thead><tr><th>Seasons</th></tr></thead>"
        "<tbody><tr><td>Cap Anson</td></tr></tbody>"
    )

    salida = TablaHtmlBlock().clean(de_la_version_rota)

    assert salida.lstrip().startswith("<table")
    assert "Cap Anson" in salida
    assert "Cap Anson" in str(TablaHtmlBlock().get_context(salida)["contenido"])


def test_the_full_editor_round_trip() -> None:
    """Pegar → guardar → pintar → volver a editar → volver a guardar. El ciclo que estaba roto.

    Cada paso usa el valor que dejó el anterior, que es la única forma de que el fallo aparezca: por
    separado, las dos primeras llamadas funcionaban.
    """
    bloque = TablaHtmlBlock()

    pegado = bloque.clean(COMO_GT)  # el editor pega y guarda
    pintado = str(bloque.get_context(pegado)["contenido"])  # el lector abre el artículo
    reeditado = bloque.clean(pegado)  # el editor vuelve a entrar y guarda otra vez

    assert "Cap Anson" in pintado, "el artículo publicado se quedó sin tabla"
    assert "dgl-stats-table" in pintado
    assert 'colspan="3"' in pintado
    assert reeditado == pegado, "reeditar cambia el valor, y a la tercera se pierde algo"
    assert "Cap Anson" in str(bloque.get_context(reeditado)["contenido"])
