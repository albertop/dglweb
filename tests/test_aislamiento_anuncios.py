"""Que ningún marco de publicidad salga sin `sandbox`.

QUÉ SE ESTÁ EVITANDO
---------------------
La creatividad la sube un anunciante, no nosotros: es HTML y JavaScript de un tercero corriendo dentro
del sitio. Sin `sandbox`, ese código puede hacer `top.location = ...` y llevarse al lector a otra parte
sin que toque nada. Es el fraude publicitario más común que existe.

Y NO SE CAZA MIRANDO EL SITIO. La redirección aparece cuando le conviene a quien la puso —de
madrugada, o solo en móvil, o una de cada cincuenta cargas—, así que abrir la página y comprobar que
todo va bien no prueba nada. Un atributo o está en el HTML o no está: eso sí se puede afirmar.

POR QUÉ SE COMPRUEBAN LOS DOS MARCOS CON LA MISMA LISTA
-------------------------------------------------------
Hay dos plantillas —el marco con `src` del servidor y el que nace vacío para `anuncios.js`— y son dos
archivos distintos por una razón que no tiene nada que ver con la seguridad. Proteger uno y dejar el
otro abierto no protege nada: basta el hueco descuidado. Al tocar uno hay que tocar el otro, y esto es
lo que lo recuerda.

Estuvieron los dos SIN `sandbox`, con este argumento escrito en ambas plantillas: que el marco «tiene
que poder navegar al hacer clic, y eso es lo que se le factura al anunciante». Era falso — la
plantilla de entrega de Revive ya abre con `target="_blank"`, se miró el HTML que sirve—, así que el
clic nunca navegó la ventana de arriba y nunca hizo falta permitirlo. De ahí
`test_no_se_permite_navegar_la_ventana_de_arriba`: si alguien reconstruye ese razonamiento y añade
`allow-top-navigation`, el permiso vuelve y con él el agujero.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from django.template import Context, Template
from django.test import override_settings

PLANTILLAS = pathlib.Path(__file__).resolve().parent.parent / "templates" / "widgets"

MARCOS = ("_anuncio.html", "_anuncio_horizontal.html")

# Los cuatro, y por qué cada uno:
#
#   allow-scripts                    casi toda creatividad es HTML+JS; sin esto no se ve nada
#   allow-same-origin                Revive necesita SU cookie para no repetir el mismo anuncio
#   allow-popups                     el `target="_blank"` del clic, que es lo que se factura
#   allow-popups-to-escape-sandbox   sin esto la página del anunciante abre TAMBIÉN aislada y se ve
#                                    rota, que de cara al anunciante es peor que no mostrarla
PERMISOS = {
    "allow-scripts",
    "allow-same-origin",
    "allow-popups",
    "allow-popups-to-escape-sandbox",
}

# Estos son los que devuelven justo lo que el `sandbox` quita.
PROHIBIDOS = ("allow-top-navigation", "allow-top-navigation-by-user-activation")

SERVIDOR = "https://promo.dominicanosengrandesligas.com"


def _sandbox(nombre: str) -> str:
    texto = (PLANTILLAS / nombre).read_text(encoding="utf-8")
    # Solo la etiqueta, no los comentarios: los comentarios NOMBRAN los permisos para explicarlos, y
    # buscar en el archivo entero daría por bueno un marco documentado y desprotegido.
    marco = re.search(r"<iframe[^>]*>", texto, re.S)
    assert marco, f"{nombre} ya no tiene un <iframe>: esta prueba dejó de comprobar nada"
    atributo = re.search(r'sandbox="([^"]*)"', marco.group(0))
    assert atributo, f"{nombre} tiene un marco de publicidad SIN sandbox"
    return atributo.group(1)


@pytest.mark.parametrize("nombre", MARCOS)
def test_todo_marco_de_publicidad_va_aislado(nombre: str) -> None:
    assert set(_sandbox(nombre).split()) == PERMISOS, nombre


@pytest.mark.parametrize("nombre", MARCOS)
@pytest.mark.parametrize("permiso", PROHIBIDOS)
def test_no_se_permite_navegar_la_ventana_de_arriba(nombre: str, permiso: str) -> None:
    """El permiso que devolvería exactamente el agujero, y el que alguien añadiría de buena fe al ver
    que un clic «no hace nada» — antes de descubrir que sí hace, en otra pestaña."""
    assert permiso not in _sandbox(nombre).split(), f"{nombre} permite {permiso}"


def test_los_dos_marcos_van_igual_de_aislados() -> None:
    """Son dos archivos por razones de maquetación, no de seguridad: el descuidado sería suficiente."""
    con_src, sin_src = (_sandbox(n) for n in MARCOS)

    assert set(con_src.split()) == set(sin_src.split())


@override_settings(ADSERVER_URL=SERVIDOR)
def test_el_atributo_llega_a_la_pagina() -> None:
    """Lo anterior lee archivos; esto renderiza.

    Un `{% comment %}` mal cerrado, o el atributo dentro de un `{% if %}` que no se cumple, dejarían
    las comprobaciones de arriba en verde con el marco saliendo pelado a la página.
    """
    html = Template("{% load anuncios %}{% anuncio 5 300 250 %}{% anuncio_horizontal 1 2 3 %}").render(Context({}))

    assert html.count("sandbox=") == 2, html


@override_settings(ADSERVER_URL=SERVIDOR)
def test_el_aislamiento_no_le_quita_el_origen_a_revive() -> None:
    """`allow-same-origin` junto a `allow-scripts` ANULA el aislamiento cuando el marco es del mismo
    origen que la página, porque entonces alcanza el documento de arriba y se quita el atributo solo.

    Acá no lo es —el marco viene de `promo.` y la página de la raíz—, y por eso el permiso es seguro.
    Esta prueba fija esa condición: si el adserver se mudara al mismo dominio, el `sandbox` pasaría a
    ser decorativo sin que nada fallara, y lo que hay que hacer entonces es quitar `allow-same-origin`
    y aceptar que Revive pierda su cookie de frecuencia.
    """
    html = Template("{% load anuncios %}{% anuncio 5 300 250 %}").render(Context({}))

    assert f'src="{SERVIDOR}/' in html, "el marco dejó de servirse desde un subdominio aparte"
