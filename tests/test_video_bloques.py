"""El bloque de video de YouTube: qué enlaces acepta y qué URL acaba en el HTML.

Lo que se protege acá es una promesa de privacidad, no una funcionalidad. El sitio declara en su
aviso que incrusta desde `youtube-nocookie.com`, y esa afirmación solo vale mientras la única URL que
pueda salir al HTML la escriba nuestra propia plantilla.
"""

import pytest
from django.core.exceptions import ValidationError

from dglweb.articles.blocks import VideoBlock, VideoMlbBlock, id_de_youtube, ruta_de_streamable
from dglweb.core import csp

ONCE = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={ONCE}",
        f"https://youtube.com/watch?v={ONCE}",
        f"https://www.youtube.com/watch?t=42&v={ONCE}",
        f"https://youtu.be/{ONCE}",
        f"https://www.youtube.com/shorts/{ONCE}",
        f"  https://youtu.be/{ONCE}  ",
    ],
)
def test_las_tres_formas_en_que_youtube_reparte_un_enlace(url: str) -> None:
    """El editor va a pegar la que le dé la página en la que esté, no la que nos convenga."""
    assert id_de_youtube(url) == ONCE


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://vimeo.com/123456789",
        "https://www.youtube.com/watch?v=corto",
        "https://www.youtube.com/",
        "https://evil.example.com/watch?v=dQw4w9WgXcQ",
        f"https://www.youtube.com.evil.test/watch?v={ONCE}",
    ],
)
def test_lo_que_no_es_youtube_no_pasa(url: str) -> None:
    """El caso que importa es el penúltimo y el último: un dominio que CONTIENE «youtube.com» pero no
    lo es. Con un `in` en vez de una expresión anclada, los dos habrían pasado."""
    assert id_de_youtube(url) == ""


def test_el_bloque_rechaza_al_guardar_y_no_al_pintar() -> None:
    """Con el editor delante y pudiendo corregirlo. Dejarlo pasar dejaría un marco vacío en el
    artículo publicado, o un `iframe` a un dominio que la CSP no permite — un hueco blanco sin
    explicación para el lector."""
    with pytest.raises(ValidationError):
        VideoBlock().clean(VideoBlock().to_python({"url": "https://vimeo.com/123", "pie": ""}))


def test_el_bloque_acepta_uno_bueno() -> None:
    limpio = VideoBlock().clean(VideoBlock().to_python({"url": f"https://youtu.be/{ONCE}", "pie": "Un jonrón"}))

    assert limpio["url"].endswith(ONCE)


def test_la_csp_deja_entrar_al_dominio_sin_cookies_y_solo_a_ese() -> None:
    """La promesa del aviso de privacidad, comprobada donde de verdad se cumple o se rompe.

    Si algún día alguien «simplifica» esto a `https://*.youtube.com`, el dominio CON cookies pasaría a
    estar permitido y la elección quedaría en manos de quien escriba una plantilla. Por eso se
    comprueba lo que NO está, además de lo que está.
    """
    politica = csp.publica()

    assert "https://www.youtube-nocookie.com" in politica
    assert "youtube.com/" not in politica.replace("youtube-nocookie.com", "")
    assert "*.youtube" not in politica


def test_youtube_va_en_frame_src_y_no_en_script_src() -> None:
    """La distinción que sostiene todo el montaje: `frame-src` deja incrustar un documento ajeno;
    `script-src` dejaría ejecutar código ajeno DENTRO del nuestro. Es la misma razón por la que el
    servidor de anuncios entra por un `iframe` y no por su etiqueta de JavaScript."""
    politica = csp.publica()
    marcos = next(d for d in politica.split("; ") if d.startswith("frame-src"))
    scripts = next(d for d in politica.split("; ") if d.startswith("script-src"))

    assert "youtube-nocookie" in marcos
    assert "youtube" not in scripts


def test_el_anuncio_y_el_video_conviven_en_frame_src() -> None:
    """En desarrollo no hay servidor de anuncios y el video tiene que salir igual; en producción están
    los dos. Antes `frame-src` era una lista de uno y el código lo daba por hecho."""
    solo_video = csp.publica()
    con_anuncio = csp.publica(anuncios="https://promo.example.com")

    marcos = next(d for d in solo_video.split("; ") if d.startswith("frame-src"))
    assert marcos == f"frame-src {csp.VIDEO_YOUTUBE} {csp.VIDEO_MLB_INCRUSTADO}", "sin anuncios, solo los videos"
    assert "promo.example.com" in con_anuncio and "youtube-nocookie" in con_anuncio


# ── El video de MLB, que llega por streamable.com ───────────────────────────────────────────────

MLB_REAL = "https://streamable.com/m/statcast-mazara-s-505-ft-blast?partnerId=web_video-playback-page_video-share"


@pytest.mark.parametrize(
    "url",
    [
        MLB_REAL,
        "https://streamable.com/abc123",
        "https://www.streamable.com/m/algo",
        f"  {MLB_REAL}  ",
    ],
)
def test_el_enlace_que_da_mlb_al_compartir_se_acepta(url: str) -> None:
    """MLB reparte sus clips incrustables por Streamable. El de la primera línea lo copió el dueño de
    mlb.com tal cual, con su `partnerId` y todo."""
    assert ruta_de_streamable(url) != ""


def test_del_enlace_solo_sobrevive_la_ruta() -> None:
    """El dominio lo escribe la plantilla, así que el `src` publicado no puede apuntar a otro sitio
    por mucho que el editor pegue algo raro. La consulta SÍ se conserva: el `partnerId` es de MLB y
    quitarlo sería adivinar que no hace falta."""
    ruta = ruta_de_streamable(MLB_REAL)

    assert ruta.startswith("m/statcast-mazara")
    assert "partnerId=web_video-playback-page_video-share" in ruta
    assert "streamable.com" not in ruta


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://vimeo.com/123456789",
        "https://streamable.com.evil.test/m/algo",
        "http://streamable.com/m/algo",
        "https://evil.test/https://streamable.com/m/algo",
    ],
)
def test_lo_que_no_es_streamable_no_pasa(url: str) -> None:
    """El tercero y el cuarto son los que importan: un dominio que CONTIENE el nombre, y el mismo
    dominio por HTTP sin cifrar — que la CSP rechazaría dejando un marco en blanco."""
    assert ruta_de_streamable(url) == ""


def test_el_bloque_de_mlb_rechaza_lo_que_no_es_suyo() -> None:
    with pytest.raises(ValidationError):
        VideoMlbBlock().clean(VideoMlbBlock().to_python({"url": "https://youtu.be/dQw4w9WgXcQ", "pie": ""}))


def test_los_dos_bloques_no_se_aceptan_el_enlace_del_otro() -> None:
    """Son dos bloques y no uno con dos ramas, así que cada uno tiene que rechazar lo del otro. Si no,
    el editor elige el equivocado y descubre el fallo con el artículo publicado."""
    assert id_de_youtube(MLB_REAL) == ""
    assert ruta_de_streamable("https://youtu.be/dQw4w9WgXcQ") == ""


def test_la_csp_deja_entrar_a_streamable() -> None:
    """Sin esto el marco sale en blanco y el navegador no deja un error que se entienda."""
    marcos = next(d for d in csp.publica().split("; ") if d.startswith("frame-src"))

    assert csp.VIDEO_MLB_INCRUSTADO in marcos
    assert "streamable" not in next(d for d in csp.publica().split("; ") if d.startswith("script-src"))
