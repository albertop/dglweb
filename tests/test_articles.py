"""Los artículos: el índice, el detalle y los bloques del cuerpo.

Lo que se protege acá no es que Wagtail funcione —eso es su problema— sino las decisiones que
tomamos encima: que un borrador no se publique solo, que el filtro por categoría sea excluyente, que
el gráfico salga con coordenadas válidas y que la escala no mienta.

EL GRÁFICO SE PRUEBA POR EL SVG QUE SALE, no por los números que calcula. Dos fallos reales de este
módulo —las coordenadas con coma decimal por el locale español, y la escala de cero que aplastaba las
líneas— no se veían en el contexto: se veían en la lámina. Un test que solo mirara `get_context` los
habría dejado pasar los dos.
"""

import datetime
import re

import pytest
from django.test import Client, RequestFactory
from wagtail.models import Page, Site

from dglweb.articles.blocks import cifra
from dglweb.articles.models import ArticleIndexPage, ArticlePage, Categoria

HOY = datetime.date(2026, 7, 27)


def _indice_de_articulos() -> ArticleIndexPage:
    """El índice donde cuelgan los artículos, creándolo si hiciera falta.

    Normalmente ya está: lo crea la migración `0002`, y la base de test nace de las migraciones. El
    respaldo existe para que un test no dependa de eso — y de paso comprueba que el árbol se puede
    armar desde cero, que es lo que pasa en una instalación nueva.

    Función y no solo `fixture` porque la usa también `test_smoke`, que prueba la portada.
    """
    existente: ArticleIndexPage | None = ArticleIndexPage.objects.first()
    if existente:
        return existente
    raiz = Page.objects.get(pk=Site.objects.get(is_default_site=True).root_page_id)
    pagina = ArticleIndexPage(title="Artículos", slug="articulos")
    raiz.add_child(instance=pagina)
    return pagina


@pytest.fixture
def indice(db: None) -> ArticleIndexPage:
    return _indice_de_articulos()


def _articulo(indice: ArticleIndexPage, titulo: str, **campos: object) -> ArticlePage:
    campos.setdefault("entradilla", "Una entradilla cualquiera.")
    campos.setdefault("fecha", HOY)
    # La categoría es obligatoria desde el 2026-07-27, así que el ayudante pone una por defecto: sin
    # esto, cada test que solo quiere comprobar otra cosa tendría que acordarse de la regla. Los
    # tests que SÍ prueban la categoría la pasan explícita y esta línea no los toca.
    campos.setdefault("categoria", Categoria.objects.order_by("orden").first())
    articulo = ArticlePage(title=titulo, slug=titulo.lower().replace(" ", "-"), **campos)
    indice.add_child(instance=articulo)
    return articulo


def _reticula(cliente: Client, url: str) -> str:
    """Solo la columna de tarjetas, sin el panel de la derecha.

    Hace falta porque «Lo más reciente» NO se filtra a propósito: si siguiera a la retícula estaría
    repitiendo exactamente lo mismo dos veces en la misma pantalla. Mirar la página entera haría que
    un test del filtro fallara por culpa de ese panel, que está haciendo lo que debe.
    """
    return cliente.get(url).content.decode().split("<aside")[0]


# ── Lo publicado y lo que no ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_draft_never_reaches_the_index(indice: ArticleIndexPage) -> None:
    """Es la manera más fácil de publicar sin querer algo a medio escribir."""
    _articulo(indice, "Publicado")
    borrador = _articulo(indice, "Borrador")
    borrador.live = False
    borrador.save()

    reticula = _reticula(Client(), indice.url)

    assert "Publicado" in reticula
    assert "Borrador" not in reticula


@pytest.mark.django_db
def test_a_draft_is_not_on_the_homepage_either(indice: ArticleIndexPage) -> None:
    """La portada tiene su propia consulta, así que el filtro hay que probarlo también acá."""
    borrador = _articulo(indice, "Borrador de portada")
    borrador.live = False
    borrador.save()

    assert b"Borrador de portada" not in Client().get("/").content


@pytest.mark.django_db
def test_the_newest_article_leads(indice: ArticleIndexPage) -> None:
    """El destacado del índice es el primero de la lista, así que el orden no es cosmético."""
    _articulo(indice, "Viejo", fecha=datetime.date(2026, 1, 1))
    _articulo(indice, "Nuevo", fecha=datetime.date(2026, 7, 1))

    assert [a.title for a in indice.articulos()] == ["Nuevo", "Viejo"]


@pytest.mark.django_db
def test_two_articles_from_the_same_day_still_have_an_order(indice: ArticleIndexPage) -> None:
    """Sin desempate, el orden lo decidiría Postgres y la portada cambiaría sola entre recargas."""
    primero = _articulo(indice, "Uno")
    segundo = _articulo(indice, "Dos")

    assert [a.pk for a in indice.articulos()] == [segundo.pk, primero.pk]


# ── La categoría, que es única y excluyente ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_index_starts_with_the_seeded_categories(indice: ArticleIndexPage) -> None:
    """Las siembra la migración para que el editor no empiece en blanco, y salen en su orden."""
    contenido = Client().get(indice.url).content.decode()

    assert Categoria.objects.count() == 7
    assert contenido.index("Sabermetría") < contenido.index("Cosas raras")


@pytest.mark.django_db
def test_the_category_filter_leaves_the_others_out(indice: ArticleIndexPage) -> None:
    defensa = Categoria.objects.get(slug="defensa")  # sembrada por la migración
    _articulo(indice, "De defensa", categoria=defensa)
    _articulo(indice, "De otra cosa")

    reticula = _reticula(Client(), f"{indice.url}?categoria=defensa")

    assert "De defensa" in reticula
    assert "De otra cosa" not in reticula


@pytest.mark.django_db
def test_the_side_panel_ignores_the_filter_on_purpose(indice: ArticleIndexPage) -> None:
    """La otra mitad de la decisión anterior, escrita como test para que nadie la «arregle».

    Si el panel siguiera al filtro, con «Defensa» elegida mostraría los mismos títulos que la
    retícula que tiene al lado — la misma lista dos veces en la misma pantalla.
    """
    _articulo(indice, "De defensa", categoria=Categoria.objects.get(slug="defensa"))
    _articulo(indice, "De otra cosa")

    contenido = Client().get(f"{indice.url}?categoria=defensa").content.decode()

    assert "De otra cosa" in contenido.split("<aside")[1]


@pytest.mark.django_db
def test_an_empty_category_says_so_instead_of_showing_a_blank_page(indice: ArticleIndexPage) -> None:
    """Un hueco blanco bajo las pestañas es indistinguible de una página rota."""
    _articulo(indice, "De otra cosa")  # y ninguno en «historia», que sí existe como categoría

    contenido = Client().get(f"{indice.url}?categoria=historia").content.decode()

    assert "Todavía no hay artículos en esta categoría" in contenido


@pytest.mark.django_db
def test_an_unknown_category_is_an_empty_list_and_not_a_crash(indice: ArticleIndexPage) -> None:
    """La categoría viene de la URL, así que cualquiera puede escribir lo que quiera ahí."""
    _articulo(indice, "Uno")

    assert Client().get(f"{indice.url}?categoria=no-existe").status_code == 200


# ── El detalle ──────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_article_lives_under_the_index(indice: ArticleIndexPage) -> None:
    """`/articulos/<slug>/` sin que nadie escriba una ruta: es lo que da el árbol de Wagtail."""
    articulo = _articulo(indice, "Un titular")

    assert articulo.url == "/articulos/un-titular/"
    assert Client().get(articulo.url).status_code == 200


@pytest.mark.django_db
def test_the_summary_goes_in_the_meta_description(indice: ArticleIndexPage) -> None:
    """Es lo que sale bajo el titular en Google y en el recuadro de WhatsApp al pegar el enlace."""
    articulo = _articulo(indice, "Un titular", entradilla="Lo que cuenta este artículo.")

    contenido = Client().get(articulo.url).content.decode()

    assert '<meta name="description" content="Lo que cuenta este artículo.">' in contenido


@pytest.mark.django_db
def test_reading_time_is_computed_and_never_says_zero(indice: ArticleIndexPage) -> None:
    """Nadie acierta el tiempo de lectura a ojo, y «0 min» se lee como un error."""
    corto = _articulo(indice, "Corto", entradilla="Tres palabras nada más.")
    largo = _articulo(indice, "Largo", entradilla="palabra " * 600)

    assert corto.minutos == 1
    assert largo.minutos == 3


# ── El gráfico: lo que se mira es la lámina ─────────────────────────────────────────────────────


def _grafico(tipo: str, puntos: list[tuple[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "type": "grafico",
            "value": {
                "titulo": "Un gráfico",
                "tipo": tipo,
                "puntos": [{"etiqueta": e, "valor": v} for e, v in puntos],
            },
        }
    ]


def _svg(cliente: Client, articulo: ArticlePage) -> str:
    return cliente.get(articulo.url).content.decode()


@pytest.mark.django_db
def test_the_chart_coordinates_never_carry_a_decimal_comma(indice: ArticleIndexPage) -> None:
    """El fallo que se comió la primera versión del bloque.

    El sitio está en español, así que Django formatea `83.06` como `83,06`. Como coordenada SVG eso
    no es válido: el navegador no da error, simplemente dibuja mal —barras a cero y etiquetas
    amontonadas en una esquina—. Se arregla con `{% localize off %}` y se comprueba acá porque a
    ojo, en una lámina, «está mal» y «está mal por esto» no se distinguen.
    """
    articulo = _articulo(indice, "Con gráfico", cuerpo=_grafico("barras", [("2024", "27.5"), ("2025", "43.25")]))

    svg = _svg(Client(), articulo)

    assert 'class="barra"' in svg
    for atributo in re.findall(r'(?:x|y|width|height|cx|cy)="([^"]+)"', svg):
        assert "," not in atributo, f"coordenada con coma decimal: {atributo}"


@pytest.mark.django_db
def test_a_bar_chart_always_starts_at_zero(indice: ArticleIndexPage) -> None:
    """Lo que compara una barra es su LARGO. Cortar el eje por abajo hace ver 41 contra 43 como el
    doble, y eso en un sitio de estadísticas no es un adorno, es una mentira."""
    articulo = _articulo(indice, "Barras", cuerpo=_grafico("barras", [("2024", "41"), ("2025", "43")]))

    svg = _svg(Client(), articulo)

    # La referencia de más abajo es el cero, así que la etiqueta «0» tiene que estar en el eje.
    assert ">0</text>" in svg


@pytest.mark.django_db
def test_a_line_chart_does_not_flatten_the_series_against_the_top(indice: ArticleIndexPage) -> None:
    """En una línea el dato es la pendiente, no la distancia al suelo.

    Con base en cero, cinco temporadas de wOBA entre .372 y .419 salían como una raya recta con dos
    tercios de la lámina en blanco debajo: el gráfico no contaba nada. Se comprueba que los puntos
    usan de verdad el alto disponible.
    """
    articulo = _articulo(
        indice,
        "Linea",
        cuerpo=_grafico("linea", [("2023", "0.372"), ("2024", "0.419"), ("2025", "0.396")]),
    )

    svg = _svg(Client(), articulo)
    alturas = [float(y) for y in re.findall(r'<circle class="punto" cx="[\d.]+" cy="([\d.]+)"', svg)]

    assert len(alturas) == 3
    # Del punto más alto al más bajo hay más de la mitad del lienzo: la serie respira.
    assert max(alturas) - min(alturas) > 100


@pytest.mark.django_db
def test_a_flat_line_does_not_divide_by_zero(indice: ArticleIndexPage) -> None:
    """Tres temporadas con el mismo valor. Sin margen inventado, el rango sería cero."""
    articulo = _articulo(indice, "Plana", cuerpo=_grafico("linea", [("a", "1"), ("b", "1"), ("c", "1")]))

    assert Client().get(articulo.url).status_code == 200


@pytest.mark.django_db
def test_the_chart_says_out_loud_what_it_draws(indice: ArticleIndexPage) -> None:
    """Un SVG sin descripción es un hueco silencioso en mitad del artículo para quien no lo ve."""
    articulo = _articulo(indice, "Descrito", cuerpo=_grafico("barras", [("2024", "27"), ("2025", "43")]))

    svg = _svg(Client(), articulo)

    assert 'role="img"' in svg
    assert "2024: 27; 2025: 43" in svg


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("0.282", ".282"), ("-0.5", "-.5"), ("41", "41"), ("41.50", "41.5"), ("0", "0")],
)
def test_numbers_are_written_the_way_the_site_writes_them(valor: str, esperado: str) -> None:
    """Sin el cero de la izquierda, que es la convención del béisbol y la del resto del sitio."""
    from decimal import Decimal

    assert cifra(Decimal(valor)) == esperado


# ── El resto de los bloques ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_player_mention_links_to_his_profile(indice: ArticleIndexPage) -> None:
    """Es lo que conecta el artículo con el resto del sitio; sin el enlace es texto suelto."""
    from dglweb.players.models import Player
    from tests.test_players import _other_player

    jugador = Player.objects.create(**_other_player(player_id=901, dgl_id="a01", full_name="Un Jugador", pos="LF"))
    articulo = _articulo(
        indice,
        "Con jugador",
        cuerpo=[{"type": "jugador", "value": {"jugador": jugador.pk, "nota": "El caso del artículo."}}],
    )

    contenido = Client().get(articulo.url).content.decode()

    assert f'href="/jugador/{jugador.slug}/"' in contenido
    assert "El caso del artículo." in contenido


@pytest.mark.django_db
def test_the_table_marks_its_headers_so_a_screen_reader_can_narrate_it(indice: ArticleIndexPage) -> None:
    """Sin `<th scope>`, una tabla de estadísticas se lee como una lista de números sin dueño."""
    articulo = _articulo(
        indice,
        "Con tabla",
        cuerpo=[
            {
                "type": "tabla",
                "value": {
                    "first_row_is_table_header": True,
                    "first_col_is_header": True,
                    "data": [["Jugador", "HR"], ["Un Jugador", "41"]],
                },
            }
        ],
    )

    contenido = Client().get(articulo.url).content.decode()

    assert '<th scope="col">Jugador</th>' in contenido
    assert '<th scope="row">Un Jugador</th>' in contenido


# ── El enlace del menú ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_menu_link_follows_the_page_instead_of_a_fixed_route(indice: ArticleIndexPage) -> None:
    """El editor puede mover o renombrar la página; el menú tiene que seguirla."""
    from django.core.cache import cache

    cache.clear()
    assert f'href="{indice.url}"' in Client().get("/").content.decode()


# ── El reparto del índice ───────────────────────────────────────────────────────────────────────
#
# Nueve huecos con nombre —destacado, retícula, lateral y fila— y el resto escondido detrás del
# botón. Se prueba acá y no a ojo porque son cortes de una lista: equivocarse en un índice deja un
# artículo repetido en dos sitios o desaparecido, y las dos cosas se ven igual de bien en la pantalla.


@pytest.mark.django_db
def test_the_index_fills_its_nine_slots_in_order_without_repeating(indice: ArticleIndexPage) -> None:
    from dglweb.articles import models

    for numero in range(models.INICIALES):
        _articulo(indice, f"Articulo {numero:02d}", fecha=datetime.date(2026, 7, 27) - datetime.timedelta(days=numero))

    contexto = indice.get_context(RequestFactory().get(indice.url))
    colocados = [
        contexto["destacado"].title,
        *[a.title for a in contexto["reticula"]],
        *[a.title for a in contexto["lateral"]],
    ]

    # En orden, sin huecos y sin repetir: es exactamente la lista, troceada.
    assert colocados == [f"Articulo {numero:02d}" for numero in range(models.INICIALES)]
    assert contexto["mas"] == []


@pytest.mark.django_db
def test_beyond_the_nine_the_rest_is_drawn_hidden(indice: ArticleIndexPage) -> None:
    """Vienen en el HTML pero con `hidden`: el botón los descubre sin ir al servidor."""
    from dglweb.articles import models

    for numero in range(models.INICIALES + 3):
        _articulo(indice, f"Articulo {numero:02d}", fecha=datetime.date(2026, 7, 27) - datetime.timedelta(days=numero))

    contenido = Client().get(indice.url).content.decode()

    assert len(indice.get_context(RequestFactory().get(indice.url))["mas"]) == 3
    assert contenido.count('dgl-oculto" hidden') == 3
    assert "Articulo 07" in contenido  # está dibujado, aunque escondido


@pytest.mark.django_db
def test_the_index_stops_drawing_at_the_cap(indice: ArticleIndexPage) -> None:
    """El tope existe para que el día que haya trescientos artículos la página no pese trescientos."""
    from dglweb.articles import models

    tope = models.INICIALES + models.POR_TANDA * models.TANDAS
    for numero in range(tope + 5):
        _articulo(indice, f"Articulo {numero:03d}", fecha=datetime.date(2026, 7, 27) - datetime.timedelta(days=numero))

    contexto = indice.get_context(RequestFactory().get(indice.url))

    assert len(contexto["mas"]) == tope - models.INICIALES
    assert f"Articulo {tope:03d}" not in Client().get(indice.url).content.decode()


@pytest.mark.django_db
def test_the_button_is_left_out_when_there_is_nothing_to_reveal(indice: ArticleIndexPage) -> None:
    """Un botón que promete más artículos y no los tiene es peor que no tenerlo."""
    _articulo(indice, "El unico")

    assert 'id="dgl-ver-mas"' not in Client().get(indice.url).content.decode()


# ── SAB-01: métricas negativas ──────────────────────────────────────────────────────────────────
#
# En béisbol son de todos los días: OAA, DRS, run value, WPA, RE24 y el WAR en muestras cortas. Antes
# del arreglo el gráfico no se equivocaba un poco, se rompía — y en silencio, que es lo peor: con
# `[5, -3]` el alto del `<rect>` salía negativo y el navegador no lo dibujaba ni se quejaba, y con
# `[-8, -2]` el rango salía negativo y la barra medía cuatro veces el lienzo.


def _grafico_barras(puntos: list[tuple[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "type": "grafico",
            "value": {
                "titulo": "Un gráfico",
                "tipo": "barras",
                "puntos": [{"etiqueta": e, "valor": v} for e, v in puntos],
            },
        }
    ]


@pytest.mark.parametrize(
    ("puntos", "descripcion"),
    [
        ([("A", "5"), ("B", "-3")], "signos mezclados"),
        ([("A", "-8"), ("B", "-2")], "todos negativos"),
        ([("A", "4"), ("B", "7")], "todos positivos"),
        ([("A", "0"), ("B", "0")], "todos cero"),
    ],
)
@pytest.mark.django_db
def test_no_bar_is_ever_drawn_outside_the_canvas(
    indice: ArticleIndexPage, puntos: list[tuple[str, str]], descripcion: str
) -> None:
    """Ninguna barra con alto negativo ni más alta que la lámina, pase lo que pase con los signos."""
    from dglweb.articles.blocks import ALTO

    articulo = _articulo(indice, f"Barras {descripcion}", cuerpo=_grafico_barras(puntos))

    svg = Client().get(articulo.url).content.decode()
    patron = r'<rect class="barra[^"]*" x="[\d.-]+" y="([\d.-]+)"\s+width="[\d.-]+" height="([\d.-]+)"'
    rects = re.findall(patron, svg)

    assert len(rects) == len(puntos), f"faltan barras en el caso «{descripcion}»"
    for y, alto in rects:
        assert float(alto) >= 0, f"alto negativo: el navegador no dibuja ese rect y no avisa ({descripcion})"
        assert float(y) >= 0, f"barra por encima del lienzo ({descripcion})"
        assert float(y) + float(alto) <= ALTO, f"barra por debajo del lienzo ({descripcion})"


@pytest.mark.django_db
def test_a_negative_bar_hangs_from_zero_and_a_positive_one_stands_on_it(indice: ArticleIndexPage) -> None:
    """Es lo que hace honesta la comparación: las dos se miden contra la MISMA línea."""
    articulo = _articulo(indice, "Mezcla", cuerpo=_grafico_barras([("A", "5"), ("B", "-5")]))

    svg = Client().get(articulo.url).content.decode()
    encaje = re.search(r'<line class="ref cero"[^>]*y1="([\d.]+)"', svg)
    assert encaje is not None, "con signos mezclados, la línea del cero tiene que dibujarse"
    cero = float(encaje.group(1))
    patron = r'<rect class="barra[^"]*"[^>]*y="([\d.-]+)"\s+width="[\d.-]+" height="([\d.-]+)"'
    rects = [(float(y), float(alto)) for y, alto in re.findall(patron, svg)]

    (y_positiva, alto_positiva), (y_negativa, alto_negativa) = rects
    # La positiva termina en el cero; la negativa empieza ahí.
    assert y_positiva + alto_positiva == pytest.approx(cero, abs=0.5)
    assert y_negativa == pytest.approx(cero, abs=0.5)
    # Y con valores simétricos, miden lo mismo.
    assert alto_positiva == pytest.approx(alto_negativa, abs=0.5)


@pytest.mark.django_db
def test_the_zero_line_is_not_drawn_when_it_falls_outside_the_chart(indice: ArticleIndexPage) -> None:
    """En una línea de wOBA entre .372 y .419 el cero ni entra en la lámina; dibujarlo obligaría a
    aplastar la serie contra el borde, que es justo lo que la escala de líneas evita."""
    articulo = _articulo(
        indice,
        "Linea sin cero",
        cuerpo=[
            {
                "type": "grafico",
                "value": {
                    "titulo": "wOBA",
                    "tipo": "linea",
                    "puntos": [{"etiqueta": "2024", "valor": "0.372"}, {"etiqueta": "2025", "valor": "0.419"}],
                },
            }
        ],
    )

    assert 'class="ref cero"' not in Client().get(articulo.url).content.decode()


# ── SEC-03: el texto enriquecido, congelado ─────────────────────────────────────────────────────
#
# Hoy el comportamiento es seguro, y estos tests existen para que SIGA siéndolo. `RichTextBlock` está
# limitado a `bold/italic/link/ol/ul` y las plantillas escapan; el riesgo no es hoy sino el día que
# alguien amplíe `features` para poder poner una imagen y se lleve por delante el filtro sin notarlo.
# Un test que falla ruidosamente es lo que convierte ese descuido en una decisión.


@pytest.mark.django_db
def test_a_javascript_link_does_not_survive_the_rich_text(indice: ArticleIndexPage) -> None:
    """`javascript:` en un href es el XSS almacenado de manual."""
    articulo = _articulo(
        indice,
        "Con enlace raro",
        cuerpo=[{"type": "parrafo", "value": '<p><a href="javascript:alert(1)">pincha</a></p>'}],
    )

    contenido = Client().get(articulo.url).content.decode()

    assert "javascript:alert" not in contenido


@pytest.mark.django_db
def test_html_in_a_table_cell_is_escaped_not_executed(indice: ArticleIndexPage) -> None:
    """Las celdas las teclea una persona y salen tal cual en la página."""
    articulo = _articulo(
        indice,
        "Con tabla rara",
        cuerpo=[
            {
                "type": "tabla",
                "value": {
                    "first_row_is_table_header": True,
                    "first_col_is_header": False,
                    "data": [["Jugador"], ["<script>alert(1)</script>"]],
                },
            }
        ],
    )

    contenido = Client().get(articulo.url).content.decode()

    assert "<script>alert(1)</script>" not in contenido
    assert "&lt;script&gt;" in contenido


@pytest.mark.django_db
def test_html_in_the_summary_is_escaped(indice: ArticleIndexPage) -> None:
    """La entradilla sale en la tarjeta, en el artículo Y en la `meta description`: tres sitios."""
    articulo = _articulo(indice, "Con entradilla rara", entradilla="<script>alert(1)</script> y más")

    contenido = Client().get(articulo.url).content.decode()

    assert "<script>alert(1)</script>" not in contenido
    assert "&lt;script&gt;" in contenido


@pytest.mark.django_db
def test_the_rich_text_features_stay_narrow(indice: ArticleIndexPage) -> None:
    """El filtro de arriba solo vale mientras la lista de `features` siga siendo corta.

    Este test es el que hace ruido el día que alguien la amplíe: no dice que ampliarla esté mal, dice
    que hay que volver a mirar los tres tests anteriores antes de hacerlo.
    """
    from dglweb.articles.blocks import CuerpoStreamBlock

    parrafo = CuerpoStreamBlock().child_blocks["parrafo"]

    assert set(parrafo.features) == {"bold", "italic", "link", "ol", "ul"}


# ── SEC-02: la política de documentos del CMS ───────────────────────────────────────────────────


def test_cms_documents_are_public_on_purpose() -> None:
    """Decisión del dueño (2026-07-27): los documentos del CMS SON PÚBLICOS.

    Se sirven en `/documents/<id>/<archivo>` sin pedir permisos, y se quedan así porque hacen falta
    para lo que viene —«descarga los datos de este gráfico»—. El riesgo no era técnico sino de
    expectativa: un editor subiendo algo interno creyendo que es privado.

    Este test no comprueba una implementación, congela una DECISIÓN. Si algún día alguien monta una
    vista con permisos, va a fallar y va a obligar a actualizar lo que se le dice a quien escribe.
    """
    from django.conf import settings
    from django.urls import get_resolver

    assert "wagtail.documents" in settings.INSTALLED_APPS
    rutas = {str(p.pattern) for p in get_resolver().url_patterns}
    assert "documents/" in rutas, "la ruta pública de documentos es parte de la decisión"


# ── Las dos reglas editoriales que el dueño hizo obligatorias (2026-07-27) ──────────────────────


@pytest.mark.django_db
def test_an_article_cannot_be_saved_without_a_category(indice: ArticleIndexPage) -> None:
    """Sin categoría el artículo no sale bajo ningún filtro del índice: se publica y se pierde.

    La regla vive en el MODELO y no solo en el formulario del CMS. Un `full_clean()` la ve, y también
    la ve un import o un script — que es por donde se cuelan los datos que nadie revisó.
    """
    from django.core.exceptions import ValidationError

    articulo = ArticlePage(
        title="Sin categoria", slug="sin-categoria", entradilla="Algo.", fecha=HOY, categoria=None
    )

    with pytest.raises(ValidationError) as fallo:
        articulo.full_clean()

    assert "categoria" in fallo.value.error_dict


@pytest.mark.django_db
def test_a_category_with_articles_cannot_be_deleted_by_accident(indice: ArticleIndexPage) -> None:
    """`PROTECT`, no `SET_NULL`. Borrar una categoría con artículos dentro tiene que fallar y obligar
    a reasignarlos; dejarlos huérfanos en silencio es exactamente lo que la regla vino a evitar."""
    from django.db.models import ProtectedError

    defensa = Categoria.objects.get(slug="defensa")
    _articulo(indice, "De defensa", categoria=defensa)

    with pytest.raises(ProtectedError):
        defensa.delete()


@pytest.mark.django_db
def test_a_chart_without_a_source_is_rejected(indice: ArticleIndexPage) -> None:
    """Un gráfico sin fuente no se puede comprobar, y el texto de ayuda ya lo decía antes de que el
    modelo lo hiciera cumplir. Sin fuente, una comparación de WAR deja de ser un dato y pasa a ser
    una afirmación: el lector no sabe si viene de MLB, de Savant, de FanGraphs o de nuestro cálculo.
    """
    from wagtail.blocks import StreamBlockValidationError

    from dglweb.articles.blocks import CuerpoStreamBlock

    bloque = CuerpoStreamBlock()
    sin_fuente = bloque.to_python(
        [
            {
                "type": "grafico",
                "value": {
                    "titulo": "Un gráfico",
                    "tipo": "barras",
                    "puntos": [{"etiqueta": "A", "valor": "1"}, {"etiqueta": "B", "valor": "2"}],
                    "fuente": "",
                },
            }
        ]
    )

    with pytest.raises(StreamBlockValidationError):
        bloque.clean(sin_fuente)


def test_the_source_arrives_pre_filled_for_our_own_data() -> None:
    """La regla no puede obligar a inventarse una fuente externa cuando el dato sale de acá.

    El valor por defecto llega escrito en el formulario y quien escribe lo cambia si toca. Sin él, la
    salida fácil sería teclear cualquier cosa con tal de poder guardar, que es peor que no exigirlo.
    """
    from dglweb.articles.blocks import GraficoBlock

    assert GraficoBlock().child_blocks["fuente"].get_default() == "Cálculo propio sobre datos de dglweb"
