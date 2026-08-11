"""`ANUNCIOS_VISIBLES=False`: los huecos no se dibujan y la portada se recompone.

QUÉ SE PROTEGE ACÁ. El dueño pidió esconder la publicidad mientras llegan los primeros anunciantes,
y pidió DOS veces que no se perdiera la integración con Revive. Así que estas pruebas vigilan las dos
mitades: que apagado no quede rastro de publicidad, y que apagar no haya roto nada de lo que hace
falta para volver a encenderla.

POR QUÉ NO SE APAGA VACIANDO `ADSERVER_URL`, que es lo que uno haría primero: ver
`config/settings/base.py`. Resumido — dispararía la alarma de `/health/adserver` en producción, sacaría
a Revive de la CSP hasta el próximo reinicio, y dibujaría el recuadro de maqueta en vez de nada.
"""

import pytest
from django.template import Context, Template
from django.test import Client, override_settings
from django.urls import reverse

from tests.test_articles import _articulo, _indice_de_articulos

REVIVE = "https://promo.dominicanosengrandesligas.com"
APAGADO = override_settings(ANUNCIOS_VISIBLES=False, ADSERVER_URL=REVIVE)
ENCENDIDO = override_settings(ANUNCIOS_VISIBLES=True, ADSERVER_URL=REVIVE)


def _pintar(plantilla: str) -> str:
    return Template("{% load anuncios %}" + plantilla).render(Context({}))


# ── Apagado: ni marco, ni maqueta, ni hueco ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "etiqueta",
    [
        "{% anuncio 1 728 90 %}",
        "{% anuncio_horizontal 1 16 17 %}",
        "{% anuncio_rango 3 300 600 minimo=992 %}",
    ],
)
def test_ningun_tag_dibuja_nada_con_la_publicidad_apagada(etiqueta: str) -> None:
    """Los tres tags, porque los tres son puertas distintas al mismo servidor."""
    with APAGADO:
        assert _pintar(etiqueta).strip() == ""


@pytest.mark.django_db
def test_la_portada_no_lleva_marcos_ni_recuadros_de_maqueta() -> None:
    """«Espacio publicitario» es el recuadro rayado de desarrollo, y también sobra.

    Es la mitad menos evidente del encargo: apagar mal habría cambiado un hueco en blanco por un
    recuadro que dice «acá va un anuncio», que es peor — anuncia que falta algo.
    """
    with APAGADO:
        cuerpo = Client().get("/").content.decode()

    assert "dgl-ad-marco" not in cuerpo
    assert "Espacio publicitario" not in cuerpo
    assert REVIVE not in cuerpo


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", ["/", "/articulos/", "/jugadores/", "/lideres/"])
def test_ninguna_pagina_publica_pide_un_anuncio(ruta: str) -> None:
    """El dueño lo pidió en TODOS los sitios, no solo en la portada."""
    with APAGADO:
        respuesta = Client().get(ruta)

    assert respuesta.status_code == 200
    assert "dgl-ad-marco" not in respuesta.content.decode()


# ── Apagado: la portada se recompone ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sin_carril_los_articulos_pasan_a_tres_columnas() -> None:
    """El hueco que deja el anuncio de 300x600 se llena con artículos, no con aire.

    Al quitar la columna del carril, la hermana `col-12 col-lg` se ensancha sola al contenedor
    entero; con `col-md-6` las tarjetas pasarían de ~300px a ~550px. `col-lg-4` las devuelve a su
    tamaño y mete una tercera por fila.
    """
    indice = _indice_de_articulos()
    for n in range(6):
        _articulo(indice, f"Articulo {n}")

    with APAGADO:
        cuerpo = Client().get("/").content.decode()

    assert "col-lg-4" in cuerpo
    assert "dgl-col-300" not in cuerpo  # la columna del carril, entera


@pytest.mark.django_db
def test_las_tres_tarjetas_escondidas_se_marcan_para_salir_en_escritorio() -> None:
    """Solo se escondían para no estirar la fila que sostenía el anuncio. Sin él, se publican.

    Lo decide el CSS con `.sin-anuncios`, y no quitando `dgl-art-de-mas` desde la plantilla: en móvil
    esa clase es el pliegue que hace útil al botón «Ver 3 más», y ahí nunca hubo carril que compensar.
    """
    indice = _indice_de_articulos()
    for n in range(6):
        _articulo(indice, f"Articulo {n}")

    with APAGADO:
        cuerpo = Client().get("/").content.decode()

    assert "sin-anuncios" in cuerpo
    # YA NO HAY «DE MÁS» SIN PUBLICIDAD, y esta prueba cambió con el layout del 2026-08-10: la vista
    # pide ocho artículos y TODOS entran en pantalla —dos destacados al 50 % arriba y seis en tres
    # columnas—, así que no queda nada detrás del botón del móvil. La clase solo se dibuja cuando hay
    # publicidad, que es cuando existe la restricción que la justificaba.
    assert "dgl-art-de-mas" not in cuerpo


@pytest.mark.django_db
def test_con_publicidad_la_portada_es_la_de_siempre() -> None:
    """La otra cara: encender no puede dejar restos del modo apagado."""
    indice = _indice_de_articulos()
    for n in range(6):
        _articulo(indice, f"Articulo {n}")

    with ENCENDIDO:
        cuerpo = Client().get("/").content.decode()

    assert "dgl-col-300" in cuerpo
    assert "sin-anuncios" not in cuerpo
    assert "dgl-ad-marco" in cuerpo


# ── Lo que NO se puede perder ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_contacto_no_ofrece_espacios_publicitarios_con_la_publicidad_apagada() -> None:
    """Ofrecer espacios donde no se ve ni un anuncio son dos mensajes que se contradicen.

    Es la mitad no visual del apagado: el visitante no ve publicidad y la página de contacto le dice
    a quién escribir para comprarla. Vuelve sola con la bandera, igual que los huecos.
    """
    with APAGADO:
        cuerpo = Client().get("/contacto/").content.decode()

    assert "<h2>Publicidad</h2>" not in cuerpo
    assert "Para espacios publicitarios" not in cuerpo
    # Y EL CRÉDITO DEL PIE TAMBIÉN (dueño). Adcio Media es la agencia de publicidad del sitio: con la
    # publicidad escondida, su crédito sería la única pista de que acá hay un negocio montado.
    assert "adciomediard" not in cuerpo

    with ENCENDIDO:
        cuerpo = Client().get("/contacto/").content.decode()

    assert "Para espacios publicitarios" in cuerpo
    assert "adciomediard" in cuerpo


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", ["/", "/contacto/", "/lideres/"])
def test_el_credito_de_la_agencia_desaparece_de_todo_el_sitio(ruta: str) -> None:
    """El pie va en `base.html`, o sea en TODAS las páginas. Se comprueban tres para no fiarse."""
    with APAGADO:
        assert "dgl-agencia" not in Client().get(ruta).content.decode()
    with ENCENDIDO:
        assert "dgl-agencia" in Client().get(ruta).content.decode()


@pytest.mark.django_db
def test_apagar_no_saca_a_revive_de_la_csp() -> None:
    """La condición que el dueño repitió: no perder la integración.

    La CSP se calcula UNA VEZ al arrancar el proceso a partir de `ADSERVER_URL`. Si el apagado
    hubiera pasado por vaciar ese ajuste, encender de nuevo exigiría reiniciar el contenedor — y
    mientras tanto los anuncios se bloquearían en silencio, que es el peor de los fallos.
    """
    with APAGADO:
        politica = Client().get("/").headers.get("Content-Security-Policy", "")

    assert REVIVE in politica


@pytest.mark.django_db
def test_apagar_no_dispara_el_semaforo_del_adserver() -> None:
    """`/health/adserver` vigila a Revive, no a la decisión editorial de enseñarlo.

    Vaciar `ADSERVER_URL` en producción devuelve 503 y despierta al monitor externo. Apagar la
    publicidad no es una avería y no puede sonar como una.
    """
    with APAGADO:
        respuesta = Client().get(reverse("adserver_health"))

    assert respuesta.status_code != 503


def test_los_tags_siguen_escritos_en_las_plantillas() -> None:
    """«NO QUIERO PERDER LA INTEGRACIÓN QUE EXISTE CON REVIVE», en mayúsculas y dos veces.

    Apagar es un ajuste, no un borrado: los dieciséis huecos siguen declarados con su zona en las seis
    plantillas. Esta prueba es la que impide que alguien «limpie» el HTML que hoy no dibuja nada.
    """
    import re
    from pathlib import Path

    # Las seis páginas que llevan publicidad. Las legales no, y está escrito en `legal/_base.html`.
    paginas = (
        "home.html",
        "articles/article_index_page.html",
        "articles/article_page.html",
        "profiles/players_index.html",
        "profiles/player_detail.html",
        "profiles/leaders.html",
    )
    # La invocación de verdad, no la palabra suelta: las plantillas de marco la nombran en sus
    # comentarios y contarlas ahí inflaba el número.
    tag = re.compile(r"\{%\s*anuncio(_horizontal|_rango)?\s+\d")

    plantillas = Path(__file__).resolve().parent.parent / "templates"
    encontrados = {p: len(tag.findall((plantillas / p).read_text(encoding="utf-8"))) for p in paginas}

    assert all(encontrados.values()), f"alguna página se quedó sin hueco: {encontrados}"
    # DIECISÉIS, y el número se midió acá. Los docstrings de `anuncios.py` y `docs/ADSERVER.md` decían
    # «trece» desde que se montó esto y se quedaron viejos: la portada y líderes tienen cuatro cada
    # una —dos horizontales y dos de rango— no dos. Corregidos al escribir esta prueba.
    #
    # Si el número cambia, que sea a propósito y no por una «limpieza» del HTML que hoy no dibuja nada.
    assert sum(encontrados.values()) == 16, encontrados


@pytest.mark.django_db
def test_encender_de_nuevo_devuelve_la_publicidad_sin_tocar_html() -> None:
    """La prueba que cierra el encargo: un ajuste la quita y el mismo ajuste la devuelve."""
    with APAGADO:
        apagada = Client().get("/").content.decode()
    with ENCENDIDO:
        encendida = Client().get("/").content.decode()

    assert "dgl-ad-marco" not in apagada
    assert encendida.count("dgl-ad-marco") >= 2  # cabecera y pie de la portada


def test_el_ajuste_viene_encendido_por_defecto() -> None:
    """Apagar es un acto explícito; el comportamiento de siempre no depende de acordarse de nada."""
    from django.conf import settings

    assert settings.ANUNCIOS_VISIBLES is True
