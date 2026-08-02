"""Las notas al pie del editor: numeración, enlaces de ida y vuelta, y el rótulo en español.

La lógica de convertir `<footnote id="…">` en anclas la pone `wagtail-footnotes` y no se prueba acá:
es su trabajo. Lo que se prueba es lo NUESTRO, que son cuatro cosas que se rompen en silencio.

1. **Las dos plantillas propias se usan de verdad.** Pisan a las del paquete por estar en
   `templates/`, y esa precedencia se pierde con solo mover un directorio en `TEMPLATES["DIRS"]`.
   Cuando se pierde no falla nada: vuelve a salir un rótulo en inglés a mitad del artículo.
2. **El `{% include %}` va DESPUÉS del cuerpo.** La lista se llena mientras cada párrafo se
   renderiza, así que puesto antes sale vacío — con los numeritos publicados y sin destino.
3. **El número sale del orden de APARICIÓN**, no del de creación en el editor.
4. **Los `id` de ida y vuelta se emparejan.** Son dos plantillas distintas escribiendo la mitad cada
   una; si una cambia el formato y la otra no, los enlaces siguen ahí y no llevan a ningún sitio.
"""

import json
import re
import uuid

import pytest
from django.test import Client
from wagtail.rich_text import features as registro_de_features
from wagtail_footnotes.models import Footnote

from dglweb.articles.models import ArticlePage
from tests.test_articles import _articulo, _indice_de_articulos


def _con_notas(cuerpo: str, notas: dict[str, str]) -> ArticlePage:
    """Un artículo publicado cuyo único párrafo es `cuerpo`, con `notas` colgadas de la página.

    Las claves de `notas` son marcadores —`{a}`, `{b}`— que se sustituyen por el UUID real: el test
    no puede escribir el UUID a mano porque lo necesita en dos sitios a la vez, el párrafo y la nota.
    """
    articulo = _articulo(_indice_de_articulos(), "Con notas")
    identificadores = {clave: uuid.uuid4() for clave in notas}
    for clave, texto in notas.items():
        Footnote.objects.create(page=articulo, uuid=identificadores[clave], text=f"<p>{texto}</p>")
    llamadas = {clave: f'<footnote id="{u}">x</footnote>' for clave, u in identificadores.items()}
    articulo.cuerpo = json.dumps([{"type": "parrafo", "value": cuerpo.format(**llamadas)}])
    articulo.save()
    articulo.save_revision().publish()
    return articulo


def _html(articulo: ArticlePage) -> str:
    return Client().get(articulo.url).content.decode()


@pytest.mark.django_db
def test_la_nota_se_numera_por_donde_aparece_y_no_por_cuando_se_creo() -> None:
    """Es lo que hace que reordenar dos párrafos no obligue a renumerar nada a mano.

    La nota `b` se crea segunda y se cita primera, así que tiene que salir como la [1].
    """
    articulo = _con_notas(
        "<p>Primero{b} y después{a}.</p>",
        {"a": "La creada primero.", "b": "La creada segunda."},
    )
    html = _html(articulo)
    assert re.search(r'href="#footnote-1"[^>]*><sup>\[1\]</sup>', html)
    # Y en la lista, el punto 1 es el texto de la que se citó primero.
    lista = html[html.index('class="dgl-notas-lista"') :]
    assert lista.index("La creada segunda.") < lista.index("La creada primero.")


@pytest.mark.django_db
def test_cada_llamada_lleva_a_su_nota_y_cada_nota_devuelve_a_su_llamada() -> None:
    """El par de `id` lo escriben DOS plantillas distintas. Este test es el que las ata."""
    html = _html(_con_notas("<p>Una{a} y otra{b}.</p>", {"a": "Primera.", "b": "Segunda."}))
    # De la llamada a la nota: el `href` de arriba tiene que existir como `id` abajo.
    for destino in re.findall(r'class="dgl-nota-llamada" href="#([\w-]+)"', html):
        assert f'id="{destino}"' in html, f"la llamada apunta a #{destino}, que no existe"
    # Y de vuelta.
    for origen in re.findall(r'class="dgl-nota-volver" href="#([\w-]+)"', html):
        assert f'id="{origen}"' in html, f"la nota vuelve a #{origen}, que no existe"


@pytest.mark.django_db
def test_la_misma_nota_citada_dos_veces_es_una_sola_con_dos_vueltas() -> None:
    """Repetir la fuente en dos frases no debe duplicar la nota al pie.

    Y las dos vueltas tienen que ser DISTINTAS: una sola flecha dejaría colgado a quien llegó desde
    la segunda cita.
    """
    html = _html(_con_notas("<p>Acá{a} y también acá{a}.</p>", {"a": "Una sola fuente."}))
    assert html.count("Una sola fuente.") == 1
    vueltas = re.findall(r'href="#(footnote-source-1-\d+)"', html)
    assert sorted(vueltas) == ["footnote-source-1-1", "footnote-source-1-2"]


@pytest.mark.django_db
def test_la_llamada_no_arrastra_un_espacio_antes_del_punto() -> None:
    """La plantilla de la llamada NO puede terminar en salto de línea.

    El bloque la renderiza aparte y mete el resultado dentro del párrafo, así que un `\\n` final sale
    como espacio en el navegador: «la primera[2] .». Es el fallo que nadie va a poner en un ticket y
    que se ve en todos los artículos.
    """
    assert "</sup></a>." in _html(_con_notas("<p>Al final{a}.</p>", {"a": "Una nota."}))


@pytest.mark.django_db
def test_el_rotulo_de_la_lista_esta_en_espanol() -> None:
    """El paquete solo trae inglés, francés y rumano — de ahí que la plantilla sea nuestra."""
    html = _html(_con_notas("<p>Con nota{a}.</p>", {"a": "Una nota."}))
    assert ">Notas</h2>" in html
    assert "Footnotes" not in html


@pytest.mark.django_db
def test_un_articulo_sin_notas_no_publica_el_bloque_vacio() -> None:
    """La inmensa mayoría de los artículos no llevan notas y no tienen por qué cargar con el título."""
    articulo = _articulo(_indice_de_articulos(), "Sin notas")
    articulo.cuerpo = json.dumps([{"type": "parrafo", "value": "<p>Texto pelado.</p>"}])
    articulo.save()
    articulo.save_revision().publish()
    html = _html(articulo)
    assert "dgl-notas" not in html
    assert ">Notas</h2>" not in html


def test_el_boton_del_editor_dice_nota_y_conserva_el_componente_del_paquete() -> None:
    """El rótulo es nuestro; el JavaScript que abre el diálogo, del paquete.

    Se registran los dos en el mismo sitio, así que es fácil cambiar el rótulo y llevarse por delante
    el `js` — y entonces el botón sigue en la barra y no hace nada al pulsarlo.
    """
    registro_de_features.get_default_features()
    boton = registro_de_features.get_editor_plugin("draftail", "footnotes")
    assert boton.data["label"] == "Nota"
    assert boton.data["description"] == "Nota al pie"
    assert "footnotes/js/footnotes.js" in boton.js


# ── SEC-03, la parte que le toca a las notas ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_un_javascript_en_el_href_de_una_nota_no_sobrevive() -> None:
    """El texto de la nota es texto enriquecido igual que el párrafo, así que corre el mismo riesgo.

    Hoy el campo del paquete viene con `bold/italic/link`, pero se ensancha con un ajuste
    —`WAGTAIL_FOOTNOTES_TEXT_FEATURES`— y ese día este test es el que avisa. Es el gemelo de
    `test_a_javascript_link_does_not_survive_the_rich_text`, para la otra mitad del artículo.
    """
    articulo = _con_notas("<p>Con nota{a}.</p>", {"a": '<a href="javascript:alert(1)">pincha</a>'})
    assert "javascript:alert" not in _html(articulo)


@pytest.mark.django_db
def test_un_id_de_nota_inventado_no_pinta_ancla_ni_rompe_la_pagina() -> None:
    """Lo que se guarda en el párrafo es un `id`, y un `id` se puede quedar huérfano.

    Pasa de verdad: se escribe la nota, se cita, y después se borra la nota desde el panel lateral.
    El artículo tiene que seguir publicándose — sin numerito y sin página de error.
    """
    articulo = _articulo(_indice_de_articulos(), "Con nota fantasma")
    articulo.cuerpo = json.dumps(
        [{"type": "parrafo", "value": f'<p>Texto<footnote id="{uuid.uuid4()}">x</footnote>.</p>'}]
    )
    articulo.save()
    articulo.save_revision().publish()

    html = _html(articulo)

    assert "Texto" in html
    assert "dgl-nota-llamada" not in html
    assert "dgl-notas" not in html
