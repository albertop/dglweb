"""Lo que hace que el sitio se encuentre y que un enlace compartido se vea.

Se prueba porque **no se nota al mirarlo**: una etiqueta que falta no rompe ninguna página, no da
error y no sale en ninguna revisión visual. Se descubre semanas después, cuando alguien pregunta por
qué el sitio no aparece en Google o por qué los enlaces salen desnudos en WhatsApp.
"""

import json

import pytest
from django.test import Client
from django.urls import reverse

from dglweb.players.models import Player
from tests.test_players import _other_player


def _jugador() -> Player:
    return Player.objects.create(**_other_player(player_id=665742, dgl_id="s01", full_name="Juan Soto", pos="RF"))


@pytest.mark.django_db
def test_el_robots_apunta_al_mapa_y_cierra_lo_que_no_es_contenido() -> None:
    """El `Sitemap:` es la mitad que importa: es cómo Google se entera de que el mapa existe."""
    texto = Client().get("/robots.txt").content.decode()

    assert "Sitemap: http://testserver/sitemap.xml" in texto
    assert "Disallow: /cms/" in texto
    # La página de líderes CON parámetros: 146 métricas x 2 alcances x 72 temporadas son ~21.000
    # URLs de la misma página, y rastrearlas se come el presupuesto que necesitan las ~970 fichas.
    assert "Disallow: /lideres/?" in texto


@pytest.mark.django_db
def test_el_mapa_lista_las_fichas_y_no_las_combinaciones_de_lideres() -> None:
    jugador = _jugador()

    xml = Client().get("/sitemap.xml").content.decode()

    assert jugador.slug in xml
    assert "/lideres/" in xml  # la URL desnuda SÍ
    assert "/lideres/?" not in xml  # las ~21.000 combinaciones NO


@pytest.mark.django_db
def test_un_jugador_dado_de_baja_no_entra_al_mapa() -> None:
    """Anunciar una URL que devuelve 404 es la forma más rápida de que Google deje de fiarse del
    mapa entero — y las bajas siguen respondiendo 404 por diseño."""
    jugador = _jugador()
    jugador.hidden = True
    jugador.save()

    assert jugador.slug not in Client().get("/sitemap.xml").content.decode()


@pytest.mark.django_db
def test_cada_ficha_lleva_su_propia_descripcion() -> None:
    """Sin ella, Google recorta la primera frase de la página —la fila biográfica— y publica algo
    como «Posición: P-ABR · Batea: Derecho». Cierto, y no distingue una ficha de otras 970.
    """
    jugador = _jugador()

    html = Client().get(reverse("player_detail", args=[jugador.slug])).content.decode()

    assert "jardinero derecho dominicano" in html
    assert 'property="og:title" content="Juan Soto"' in html


@pytest.mark.django_db
def test_la_canonica_deja_fuera_la_cadena_de_consulta() -> None:
    """Es lo que impide que los filtros se indexen como páginas distintas."""
    html = Client().get("/lideres/?g=batting&scope=temporada&m=avg").content.decode()

    assert 'rel="canonical" href="http://testserver/lideres/"' in html


@pytest.mark.django_db
def test_los_datos_estructurados_del_jugador_son_json_valido() -> None:
    """Un JSON roto —una comilla en un nombre— hace que Google descarte la ficha entera sin avisar.

    Por eso cada valor va con `escapejs` y por eso esto se prueba parseando de verdad, no buscando
    una cadena.
    """
    jugador = _jugador()

    html = Client().get(reverse("player_detail", args=[jugador.slug])).content.decode()
    crudo = html.split('<script type="application/ld+json">')[1].split("</script>")[0]
    datos = json.loads(crudo)

    assert datos["@type"] == "Person"
    assert datos["name"] == "Juan Soto"
    assert datos["nationality"]["name"] == "República Dominicana"


@pytest.mark.django_db
def test_un_nombre_con_comillas_no_rompe_el_json() -> None:
    """El caso que `escapejs` existe para cubrir. Hay apodos con comillas en el maestro."""
    jugador = Player.objects.create(
        **_other_player(player_id=1, dgl_id="x01", full_name='Pedro "Tiburón" Guerrero', pos="1B")
    )

    html = Client().get(reverse("player_detail", args=[jugador.slug])).content.decode()
    crudo = html.split('<script type="application/ld+json">')[1].split("</script>")[0]

    assert json.loads(crudo)["name"] == 'Pedro "Tiburón" Guerrero'
