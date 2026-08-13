"""El generador de comparaciones: la pantalla donde se eligen los parámetros. Ver `docs/COMPARADOR.md`.

LO QUE SE PRUEBA ACÁ ES QUE NO DECIDA POR EL USUARIO. El cálculo tiene sus propias pruebas; esto
vigila la otra mitad del trato: que un parámetro imposible produzca una FRASE que diga qué pedir en
su lugar, y no un 404, ni una comparación distinta de la que se pidió. Es el requisito literal del
dueño —«no quiero que el site tome decisiones que el usuario luego no entienda qué pasó»— y es fácil
de romper sin darse cuenta, porque bajar el número en silencio siempre parece más amable.
"""

from datetime import date

import pytest
from django.urls import reverse

from dglweb.players.models import Player
from dglweb.stats import comparador
from tests.test_comparador import _bateo, _pitcheo
from tests.test_comparador import _jugador as _crudo


def _jugador(pid: int, nombre: str, pos: str = "OF") -> Player:
    """Un pelotero con posición declarada.

    HACE FALTA DECIRLA: el generador decide bateo o pitcheo mirando `pos`, y el molde de pruebas la
    deja en lanzador. Sin esto, un «bateador» de prueba recibe el error de las 30 IP y la prueba
    parece fallar por otra cosa.
    """
    pelotero = _crudo(pid, nombre)
    pelotero.pos = pos
    pelotero.save(update_fields=["pos"])
    return pelotero


def _errores(respuesta) -> list[str]:  # type: ignore[no-untyped-def]
    from django.utils.html import strip_tags

    cuerpo = respuesta.content.decode()
    # Se corta en el cierre de cada párrafo: sin eso, el último se lleva el pie de página entero.
    return [strip_tags(t.split("</p>")[0]).strip() for t in cuerpo.split('<p class="mb-0">')[1:]]


@pytest.mark.django_db
def test_comparar_salta_a_la_tarjeta(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El generador nunca pinta una comparación: redirige a la URL propia, que es la que se comparte."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    for anio in (2019, 2020, 2021):
        _bateo(uno, anio)
        _bateo(otro, anio)

    respuesta = client.get(
        reverse("comparador"), {"comparar": "1", "uno": uno.slug, "otro": otro.slug, "modo": "carrera"}
    )

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"/comparar/{uno.slug}/vs/{otro.slug}/carrera/"


@pytest.mark.django_db
def test_el_que_no_llega_se_nombra_y_se_dice_que_pedir(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El error del dueño, literal: quién, cuántas tiene y con cuántas comparar.

    NO SE BAJA EL NÚMERO EN SILENCIO. Hubo una versión que igualaba por abajo y lo declaraba en el
    rótulo de la imagen; con un formulario delante es peor, porque el usuario ve un 5 en la pantalla
    y recibe una tarjeta de 3.
    """
    corto, largo = _jugador(1, "Corto"), _jugador(2, "Largo")
    for anio in (2019, 2020):
        _bateo(corto, anio)
    for anio in (2017, 2018, 2019, 2020, 2021):
        _bateo(largo, anio)

    respuesta = client.get(
        reverse("comparador"),
        {"comparar": "1", "uno": corto.slug, "otro": largo.slug, "modo": "mejores", "cuantas": "5"},
    )

    assert respuesta.status_code == 200, "se queda en el formulario, no manda a un 404"
    assert _errores(respuesta) == ["Corto tiene 2 temporadas de al menos 100 PA, no 5. Compara con 2 o menos."]


@pytest.mark.django_db
def test_una_temporada_de_cafe_no_cuenta_para_el_error(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El mensaje habla de temporadas de verdad, que es lo que la comparación va a usar."""
    corto, largo = _jugador(1, "Corto"), _jugador(2, "Largo")
    _bateo(corto, 2018, pa=20, ab=18, war=0.1)
    for anio in (2019, 2020):
        _bateo(corto, anio)
    for anio in (2017, 2018, 2019, 2020, 2021):
        _bateo(largo, anio)

    respuesta = client.get(
        reverse("comparador"),
        {"comparar": "1", "uno": corto.slug, "otro": largo.slug, "modo": "mejores", "cuantas": "3"},
    )

    assert "tiene 2 temporadas de al menos 100 PA, no 3" in _errores(respuesta)[0], "las 3 de la tabla no valen"


@pytest.mark.django_db
def test_no_se_compara_un_bateador_con_un_lanzador(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """La tarjeta responde 404 —correcto para una URL escrita a mano— pero acá se puede decir por qué."""
    bate, lanza = _jugador(1, "Bate"), _jugador(2, "Lanza", pos="P")
    _bateo(bate, 2020)
    _pitcheo(lanza, 2020)

    respuesta = client.get(
        reverse("comparador"), {"comparar": "1", "uno": bate.slug, "otro": lanza.slug, "modo": "carrera"}
    )

    assert respuesta.status_code == 200
    assert "no comparten ninguna estadística" in _errores(respuesta)[0]


@pytest.mark.django_db
def test_un_ano_no_comparable_dice_entre_cuales_elegir(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Decir que no vale sin decir qué sí vale obliga a adivinar."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    for anio in (2019, 2020, 2021):
        _bateo(uno, anio)
        _bateo(otro, anio)

    respuesta = client.get(
        reverse("comparador"),
        {"comparar": "1", "uno": uno.slug, "otro": otro.slug, "modo": "temporadas",
         "anio_uno": "1999", "anio_otro": "2020"},
    )

    assert _errores(respuesta) == ["Uno no tiene una temporada comparable en 1999. Elige entre 2019 y 2021."]


@pytest.mark.django_db
def test_el_mismo_pelotero_dos_veces(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    uno = _jugador(1, "Uno")
    _bateo(uno, 2020)

    respuesta = client.get(
        reverse("comparador"), {"comparar": "1", "uno": uno.slug, "otro": uno.slug, "modo": "carrera"}
    )

    assert _errores(respuesta) == ["Son el mismo pelotero. Elige dos distintos."]


@pytest.mark.django_db
def test_fuera_de_rango_no_llega_a_la_tarjeta(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El tope es 7 (ver `TEMPORADAS_MAXIMAS`) y se explica, en vez de recortar sin avisar."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    for anio in range(2015, 2025):
        _bateo(uno, anio)
        _bateo(otro, anio)

    respuesta = client.get(
        reverse("comparador"),
        {"comparar": "1", "uno": uno.slug, "otro": otro.slug, "modo": "mejores", "cuantas": "12"},
    )

    assert str(comparador.TEMPORADAS_MAXIMAS) in _errores(respuesta)[0]


@pytest.mark.django_db
def test_los_anios_que_ofrece_el_desplegable(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El endpoint que llena el desplegable: solo años que cuentan como temporada (dueño).

    OFRECER UN AÑO DE VEINTE TURNOS SERÍA INVITAR A UNA COMPARACIÓN QUE NO DICE NADA, y el usuario no
    tiene forma de saberlo hasta que ve la tarjeta. Que el camino equivocado no esté disponible es
    mejor que explicarlo después.
    """
    uno = _jugador(1, "Uno")
    _bateo(uno, 2018, pa=20, ab=18, war=0.1)
    for anio in (2019, 2020, 2021):
        _bateo(uno, anio)

    datos = client.get(reverse("comparador_temporadas"), {"jugador": uno.slug}).json()

    assert datos["anios"] == [2021, 2020, 2019], "de más reciente a más antiguo, y sin el año de café"
    assert datos["minimo"] == 100


@pytest.mark.django_db
def test_el_desplegable_de_un_desconocido_viene_vacio(client) -> None:  # type: ignore[no-untyped-def]
    """Un slug inventado devuelve una lista vacía, no un 500: el JS no puede tumbar la página."""
    assert client.get(reverse("comparador_temporadas"), {"jugador": "no-existe-9999"}).json()["anios"] == []
    assert client.get(reverse("comparador_temporadas")).json()["anios"] == []


@pytest.mark.django_db
def test_una_temporada_de_cafe_no_se_puede_pedir_por_url(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El desplegable no la ofrece; esto es la red para quien escriba la dirección a mano."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2018, pa=20, ab=18, war=0.1)
    for anio in (2019, 2020):
        _bateo(uno, anio)
        _bateo(otro, anio)

    respuesta = client.get(
        reverse("comparador"),
        {"comparar": "1", "uno": uno.slug, "otro": otro.slug, "modo": "temporadas",
         "anio_uno": "2018", "anio_otro": "2019"},
    )

    assert _errores(respuesta) == ["Uno no tiene una temporada comparable en 2018. Elige entre 2019 y 2020."]


@pytest.mark.django_db
def test_los_errores_salen_debajo_del_boton(client) -> None:  # type: ignore[no-untyped-def]
    """Donde queda mirando quien acaba de pulsarlo (dueño), no arriba obligando a subir la vista."""
    cuerpo = client.get(reverse("comparador"), {"comparar": "1", "modo": "carrera"}).content.decode()

    assert cuerpo.index('name="comparar"') < cuerpo.index('id="errores"')


@pytest.mark.django_db
def test_el_buscador_del_comparador_no_ofrece_las_ligas_negras(client) -> None:  # type: ignore[no-untyped-def]
    """Con `universo=comparador` no salen los que debutaron antes de 1956 (dueño, 2026-08-13).

    Sus números no son comparables con los de Grandes Ligas —el WAR ni siquiera existe para ellos—
    así que elegirlos solo lleva a un error. Que no aparezcan es mejor que explicarlo después.
    """
    _jugador(1, "Tetelo Vargas", pos="OF")
    viejo = Player.objects.get(pk=1)
    viejo.debut_date = date(1927, 1, 1)
    viejo.save(update_fields=["debut_date"])
    _jugador(2, "Tetelo Moderno", pos="OF")  # debut de 1990, el del molde

    nombres = [
        s["name"]
        for s in client.get(reverse("players_suggest"), {"q": "tetelo", "universo": "comparador"}).json()["results"]
    ]

    assert nombres == ["Tetelo Moderno"]


@pytest.mark.django_db
def test_el_buscador_del_sitio_los_sigue_encontrando(client) -> None:  # type: ignore[no-untyped-def]
    """LA CAJA DEL ENCABEZADO ENCUENTRA A TODOS (dueño, en mayúsculas y con razón).

    Está en todas las páginas y es la puerta a los perfiles. Tetelo Vargas es parte del sitio; lo que
    no es, es comparable. Si esta prueba y la de arriba dejan de ser dos, el filtro se escapó de donde
    tenía que estar.
    """
    _jugador(1, "Tetelo Vargas", pos="OF")
    viejo = Player.objects.get(pk=1)
    viejo.debut_date = date(1927, 1, 1)
    viejo.save(update_fields=["debut_date"])
    _jugador(2, "Tetelo Moderno", pos="OF")

    nombres = [s["name"] for s in client.get(reverse("players_suggest"), {"q": "tetelo"}).json()["results"]]

    assert sorted(nombres) == ["Tetelo Moderno", "Tetelo Vargas"]


@pytest.mark.django_db
def test_una_sola_temporada_se_escribe_en_singular(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """«Mejor temporada por WAR», no «Mejores 1 temporadas» (dueño, 2026-08-13).

    No basta con quitarle la ese al plural: cambia el adjetivo y sobra el número. Por eso son dos
    frases y no una plantilla, y por eso se prueban las dos.
    """
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    for anio in (2019, 2020):
        _bateo(uno, anio)
        _bateo(otro, anio)

    def rotulo(cuantas: int) -> str:
        ruta = reverse("comparar", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": f"mejores-{cuantas}"})
        return str(client.get(ruta).context["rotulo"])

    assert rotulo(1) == "su mejor temporada por WAR"
    assert rotulo(2) == "sus mejores 2 temporadas por WAR"


@pytest.mark.django_db
def test_la_pagina_de_resultado_es_la_imagen(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Sin tabla en HTML (dueño, 2026-08-13): la página enseña el PNG y lo reparte.

    Dos representaciones del mismo resultado acaban divergiendo, y la que circula por WhatsApp es la
    que nadie puede corregir. Que la tabla no vuelva es lo que esta prueba vigila.
    """
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    ruta = reverse("comparar", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})
    cuerpo = client.get(ruta).content.decode()

    assert "dgl-cmp-tarjeta" in cuerpo, "la imagen es el contenido"
    assert "<table" not in cuerpo, "la tabla en HTML se quitó a propósito"
    # El `alt` cuenta la comparación con cifras: la imagen ES el contenido, no un adorno.
    assert "Uno contra Otro, carrera completa" in cuerpo


@pytest.mark.django_db
def test_el_png_se_sirve_desde_la_misma_ruta(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Compartir el enlace y compartir el fichero llevan al mismo sitio."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    respuesta = client.get(
        reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})
    )

    assert respuesta["Content-Type"] == "image/png"
    assert respuesta.content[:4] == b"\x89PNG"
    assert f"{uno.slug}-vs-{otro.slug}" in respuesta["Content-Disposition"]


@pytest.mark.django_db
def test_la_tarjeta_es_la_imagen_social_del_enlace(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Pegar el enlace en WhatsApp o X tiene que enseñar la tarjeta, no la miniatura genérica.

    Es la mitad del feature: sin esto se comparte el enlace y la comparación no se ve.
    """
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    ruta = reverse("comparar", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})
    cuerpo = client.get(ruta).content.decode()

    # La previa apaisada, no la tarjeta vertical: las redes recortan a ~1.91:1. Ver `tarjeta.previa`.
    assert "previa=1" in cuerpo.split('property="og:image"')[1].split(">")[0]
    assert 'content="1200"' in cuerpo and 'content="630"' in cuerpo


@pytest.mark.django_db
def test_la_previa_de_las_redes_es_apaisada(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """X, WhatsApp y Facebook recortan a ~1.91:1 y la tarjeta es 4:5. Ver `tarjeta.previa`.

    SIN ESTO el recorte se lleva la cabecera con la marca y el pie con la dirección del sitio, que son
    justo las dos cosas por las que se comparte. Ninguna red permite ADJUNTAR la imagen por un enlace
    —el intent de X no tiene parámetro para media— así que la previa es lo que la gente ve.
    """
    from io import BytesIO

    from PIL import Image

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)
    ruta = reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})

    previa = Image.open(BytesIO(client.get(ruta, {"previa": "1"}).content))
    tarjeta = Image.open(BytesIO(client.get(ruta).content))

    assert previa.size == (1200, 630), "la medida que esperan las redes"
    assert tarjeta.size == (1080, 1350), "la que se comparte como fichero sigue siendo vertical"

    ruta = reverse("comparar", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})
    cuerpo = client.get(ruta).content.decode()
    assert "previa=1" in cuerpo.split('property="og:image"')[1].split(">")[0]
    assert "tarjeta.png" in cuerpo.split('class="dgl-cmp-tarjeta"')[1].split(">")[0], "la página enseña la vertical"


# ── el asistente: seis pasos, una pregunta cada uno ─────────────────────────────────────────────
#
# LO QUE SE PROTEGE ES EL FLUJO, no el aspecto. Un asistente falla de tres formas que no se ven
# mirando una pantalla suelta: dejando avanzar sin contestar, perdiendo lo contestado al retroceder,
# y enseñando un paso que la modalidad elegida no necesita.


@pytest.mark.django_db
def test_el_asistente_empieza_preguntando_el_oficio(client) -> None:  # type: ignore[no-untyped-def]
    cuerpo = client.get(reverse("comparador")).content.decode()

    assert "¿Qué quieres comparar?" in cuerpo
    assert 'value="SP"' in cuerpo and 'value="RP"' in cuerpo, "abridores y relevistas van separados"
    assert not _errores(client.get(reverse("comparador"))), "entrar no es enviar"


@pytest.mark.django_db
def test_no_se_puede_saltar_a_un_paso_sin_contestar_los_anteriores(client) -> None:  # type: ignore[no-untyped-def]
    """Pasa al pegar una URL vieja o al retroceder y cambiar algo de arriba.

    Sin esto se enseñaría una pantalla que da por hecho algo que ya no es cierto — el paso 5 pidiendo
    temporadas de dos peloteros que nadie ha elegido.
    """
    respuesta = client.get(reverse("comparador"), {"paso": "5"})

    assert "¿Qué quieres comparar?" in respuesta.content.decode(), "se cae al primero que falta"


@pytest.mark.django_db
def test_el_buscador_del_paso_2_solo_ofrece_el_oficio_elegido(client) -> None:  # type: ignore[no-untyped-def]
    """Es lo que hace «inteligente» al desplegable: quien dijo bateadores no tropieza con un lanzador."""
    bate = _jugador(1, "Pedro Bateador", pos="OF")
    _jugador(2, "Pedro Abridor", pos="SP")

    nombres = [
        s["name"]
        for s in client.get(
            reverse("players_suggest"), {"q": "pedro", "universo": "comparador", "oficio": "batting"}
        ).json()["results"]
    ]

    assert nombres == [bate.full_name]


@pytest.mark.django_db
def test_la_carrera_completa_se_salta_el_paso_de_parametros(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """No pide nada más, así que el 5 no existe para ella.

    Enseñar una pantalla vacía con un botón de seguir es peor que no enseñarla: el usuario se queda
    buscando qué tenía que contestar.
    """
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)
    base = {"oficio": "batting", "uno": uno.slug, "otro": otro.slug, "modo": "carrera"}

    cuerpo = client.get(reverse("comparador"), {**base, "paso": "5"}).content.decode()

    assert "Esto es lo que vas a generar" in cuerpo
    assert "¿Qué temporada de cada uno?" not in cuerpo


@pytest.mark.django_db
def test_el_resumen_final_habla_en_castellano(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Última oportunidad de que alguien vea que pidió otra cosa, así que no va en jerga de parámetros."""
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    for anio in (2019, 2020):
        _bateo(uno, anio)
        _bateo(otro, anio)

    cuerpo = client.get(reverse("comparador"), {
        "paso": "6", "oficio": "batting", "uno": uno.slug, "otro": otro.slug,
        "modo": "mejores", "cuantas": "1",
    }).content.decode()

    assert "Bateadores" in cuerpo
    assert "Uno" in cuerpo and "Otro" in cuerpo
    assert "Su mejor temporada por WAR" in cuerpo, "el singular se escribe entero"


@pytest.mark.django_db
def test_lo_contestado_no_se_repite_como_oculto(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El campo del paso actual lo pinta el paso, no un oculto.

    Si se mandaran los dos, el navegador envía ambos y gana el primero: cambiar una respuesta al
    retroceder no tendría efecto y no habría forma de que el usuario entendiera por qué.
    """
    cuerpo = client.get(reverse("comparador"), {"paso": "1", "oficio": "batting"}).content.decode()

    assert 'type="hidden" name="oficio"' not in cuerpo
    assert 'name="oficio" id="of-batting"' in cuerpo


@pytest.mark.django_db
def test_generar_desde_el_ultimo_paso_salta_a_la_tarjeta(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    respuesta = client.get(reverse("comparador"), {
        "comparar": "1", "oficio": "batting", "uno": uno.slug, "otro": otro.slug, "modo": "carrera",
    })

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"/comparar/{uno.slug}/vs/{otro.slug}/carrera/"


@pytest.mark.django_db
def test_el_paso_de_temporadas_deja_al_js_encontrar_a_los_peloteros(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Los ocultos con el slug llevan `id`, y `comparador.js` los busca por ahí.

    EL FALLO QUE ESTO CAZA: al pasar el formulario a asistente, los campos ya contestados se pintaron
    con `name` pero sin `id`. `getElementById("uno")` devolvía nulo, así que los desplegables de
    temporada salían VACÍOS y no había nada en pantalla que explicara por qué — ni error, ni aviso,
    solo dos selectores muertos.

    Se comprueba el contrato entre plantilla y script —el `id` y el `data-elegido` que lo apunta— y no
    el contenido de los desplegables, que lo llena el navegador.
    """
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    for anio in (2019, 2020):
        _bateo(uno, anio)
        _bateo(otro, anio)

    cuerpo = client.get(reverse("comparador"), {
        "paso": "5", "oficio": "batting", "uno": uno.slug, "otro": otro.slug, "modo": "temporadas",
    }).content.decode()

    for campo in ("uno", "otro"):
        assert f'id="{campo}"' in cuerpo, f"el oculto de {campo} necesita id"
        assert f'data-elegido="{campo}"' in cuerpo, f"el desplegable de {campo} tiene que apuntarlo"
    assert reverse("comparador_temporadas") in cuerpo, "y saber de dónde pedir los años"



@pytest.mark.django_db
def test_al_relevista_se_le_pide_su_minimo_y_no_el_del_abridor(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """El oficio tiene que llegar hasta `inventario()`. Es el finding ARCH-01 del review v22.

    SIN ESTO, LA PANTALLA Y LA TARJETA SE CONTRADICEN: el asistente le exigía 30 IP —el mínimo del
    abridor— a un relevista que la tarjeta ya acepta con 20. Un cerrador con temporadas de 25 entradas
    recibía «no tiene temporadas suficientes» y, si escribías la URL a mano, la imagen salía contando
    esas mismas temporadas. Dos capas contando distinto sobre el mismo pelotero, y ninguna parece rota.
    """
    relevista = _jugador(1, "Cerrador", pos="RP")
    for anio in (2018, 2019, 2020):
        _pitcheo(relevista, anio, outs=75)  # 25 IP: pasa el mínimo del relevista (20), no el del abridor (30)

    anios = client.get(reverse("comparador_temporadas"), {"jugador": relevista.slug}).json()

    assert anios["oficio"] == "RP"
    assert anios["minimo"] == 20, "el suyo, no los 30 del abridor"
    assert anios["anios"] == [2020, 2019, 2018], "sus tres temporadas cuentan"


@pytest.mark.django_db
def test_no_se_compara_un_abridor_con_un_relevista(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """No es por las métricas —son las mismas quince— sino por el ranking (review v22, ARCH-01).

    Cada uno se rankea en su población y con su umbral, así que una tarjeta mixta tendría que elegir
    una de las dos. Antes elegía la del pelotero de la izquierda, y «la izquierda» sale de ordenar por
    `player_id`: azar. El mismo par daba rankings distintos según qué número de MLB tuviera cada uno.
    """
    abridor, relevista = _jugador(1, "Abridor", pos="SP"), _jugador(2, "Cerrador", pos="RP")
    for anio in (2019, 2020):
        _pitcheo(abridor, anio)
        _pitcheo(relevista, anio, outs=75)

    respuesta = client.get(reverse("comparador"), {
        "comparar": "1", "oficio": "SP", "uno": abridor.slug, "otro": relevista.slug, "modo": "carrera",
    })
    assert "abridor y el otro relevista" in _errores(respuesta)[0], "se explica, no se responde 404"

    # Y por URL escrita a mano, un 404: no describe una tarjeta que pueda existir.
    ruta = reverse("comparar", kwargs={"uno": abridor.slug, "otro": relevista.slug, "modo": "carrera"})
    assert client.get(ruta).status_code == 404


@pytest.mark.django_db
def test_la_tarjeta_se_dibuja_una_vez_por_combinacion(client, catalogo: None, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """La segunda petición sale de la caché sin volver a pintar. Es el finding SEC-01 del review v22.

    POR QUÉ IMPORTA: cada tarjeta resuelve dos peloteros, calcula los rankings de quince métricas sobre
    las 5.185 temporadas dominicanas y pinta un PNG de 200 KB con Pillow. Es la ruta más cara del sitio
    y es pública: un bot que pida combinaciones válidas la usa de ariete. Y cuando una comparación se
    hace viral, el tráfico natural golpea justo ahí.

    Se cuentan las llamadas al DIBUJO y no el tiempo: un test de rendimiento por reloj falla de vez en
    cuando en una máquina cargada y acaba desactivado.
    """
    from dglweb.stats import tarjeta

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    veces: list[int] = []
    original = tarjeta.png

    def contando(foto: dict) -> bytes:  # type: ignore[type-arg]
        veces.append(1)
        return original(foto)

    monkeypatch.setattr(tarjeta, "png", contando)

    ruta = reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})
    primera = client.get(ruta)
    segunda = client.get(ruta)

    assert len(veces) == 1, "la segunda salió de la caché"
    assert primera.content == segunda.content
    assert segunda["ETag"], "y el navegador puede ahorrarse hasta la descarga"
    assert "max-age" in segunda["Cache-Control"]

    # La previa es otra imagen y tiene su propia entrada: no se puede servir una por la otra.
    client.get(ruta, {"previa": "1"})
    assert len(veces) == 2


@pytest.mark.django_db
def test_la_previa_no_redibuja_la_tarjeta(catalogo: None) -> None:
    """Reescalar es barato; volver a pintar la tarjeta entera para reescalarla, no.

    `previa()` recibe los bytes de la vertical cuando quien llama ya los tiene. Sin eso encadenaba el
    dibujo completo y luego el reescalado, o sea el trabajo caro hecho dos veces por petición.
    """
    from io import BytesIO

    from PIL import Image

    from dglweb.stats import comparador, tarjeta

    uno = _jugador(1, "Uno")
    _bateo(uno, 2020)
    foto = comparador.comparar("batting", (1, None), (1, None), comparador.MODO_CARRERA)

    vertical = tarjeta.png(foto)
    desde_bytes = tarjeta.previa(foto, vertical)

    assert Image.open(BytesIO(desde_bytes)).size == (1200, 630)
    assert desde_bytes == tarjeta.previa(foto), "reusar los bytes da exactamente la misma imagen"


@pytest.mark.django_db
def test_la_clave_de_cache_es_canonica(client, catalogo: None, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """El par al revés y un slug viejo son la MISMA tarjeta y comparten entrada (review v23, SEC-01).

    EL AGUJERO: la clave era `request.path`, y a la misma comparación se llega por muchas rutas. El
    slug se resuelve por el id del final, así que `nombre-inventado-2` vale igual que el canónico. Un
    bot que fabricara variantes forzaba un redibujo por cada una y desalojaba con basura las 200
    entradas útiles. Para un usuario normal la caché seguía funcionando; contra tráfico adversarial,
    no — que es justo para lo que se puso.
    """
    from dglweb.stats import tarjeta

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    veces: list[int] = []
    original = tarjeta.png

    def contando(foto: dict) -> bytes:  # type: ignore[type-arg]
        veces.append(1)
        return original(foto)

    monkeypatch.setattr(tarjeta, "png", contando)

    client.get(reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"}))
    # El par invertido y un slug con otro texto pero el mismo id: las tres son la misma comparación.
    client.get(reverse("comparar_png", kwargs={"uno": otro.slug, "otro": uno.slug, "modo": "carrera"}))
    client.get("/comparar/inventado-1/vs/otro-nombre-2/carrera/tarjeta.png")

    assert len(veces) == 1, "las tres rutas comparten una sola entrada de caché"


@pytest.mark.django_db
def test_una_recarga_validada_responde_304(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Publicar un `ETag` no basta: hay que comparar el `If-None-Match` (review v23, QA-01).

    Sin esa comparación, quien revalida recibe un 200 con los 200 KB otra vez. El proyecto no monta
    `ConditionalGetMiddleware` —tocarlo afectaría a todas las respuestas del sitio— así que se hace en
    la única vista que sirve archivos grandes.

    LA PRUEBA ANTERIOR SOLO MIRABA QUE EL HEADER EXISTIERA, y eso daba una falsa sensación de
    cobertura: comprobaba el anuncio, no la negociación.
    """
    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)
    ruta = reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})

    primera = client.get(ruta)
    segunda = client.get(ruta, HTTP_IF_NONE_MATCH=primera["ETag"])

    assert primera.status_code == 200
    assert segunda.status_code == 304
    assert not segunda.content, "un 304 no lleva cuerpo"
    assert segunda["ETag"] == primera["ETag"]


@pytest.mark.django_db
def test_una_carga_nueva_invalida_las_tarjetas(client, catalogo: None, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """La tarjeta se repinta cuando cambian los DATOS, no cuando vence un reloj (dueño, 2026-08-13).

    LAS ESTADÍSTICAS SE CARGAN UNA VEZ AL DÍA, así que un temporizador no puede acertar: con seis horas
    la tarjeta se repintaba cuatro veces al día para producir el mismo PNG, y aun así una carga que
    terminara a las 6:05 tardaba seis horas en verse. Metiendo la marca de la última carga en la clave,
    la caché se invalida sola y en el instante correcto.

    Es la respuesta a «si Juan Soto pega un jonrón, su tarjeta debe ser distinta»: lo es en cuanto el
    dato existe.
    """
    from datetime import timedelta

    from django.utils import timezone

    from dglweb.stats import tarjeta
    from dglweb.stats.models import IngestRun

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    veces: list[int] = []
    original = tarjeta.png

    def contando(foto: dict) -> bytes:  # type: ignore[type-arg]
        veces.append(1)
        return original(foto)

    monkeypatch.setattr(tarjeta, "png", contando)
    ruta = reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})

    ahora = timezone.now()
    IngestRun.objects.create(
        command="batting", status=IngestRun.Status.SUCCESS, started_at=ahora, finished_at=ahora
    )
    client.get(ruta)
    client.get(ruta)
    assert len(veces) == 1, "sin carga nueva, la segunda sale de la caché"

    # Llega la carga del día siguiente. La versión cambia y con ella la clave.
    IngestRun.objects.create(
        command="batting",
        status=IngestRun.Status.SUCCESS,
        started_at=ahora + timedelta(days=1),
        finished_at=ahora + timedelta(days=1),
    )
    from django.conf import settings
    from django.core.cache import caches

    caches[settings.COMPARTIDA].clear()  # la versión se recuerda 5 minutos; acá se fuerza a releerla
    client.get(ruta)

    assert len(veces) == 2, "con datos nuevos se repinta"


@pytest.mark.django_db
def test_una_carga_fallida_no_invalida_nada(client, catalogo: None) -> None:  # type: ignore[no-untyped-def]
    """Una ejecución que falló no cambió ningún número, así que no debe tirar la caché."""
    from django.utils import timezone

    from dglweb.profiles import comparaciones
    from dglweb.stats.models import IngestRun

    ahora = timezone.now()
    IngestRun.objects.create(
        command="batting", status=IngestRun.Status.FAILED, started_at=ahora, finished_at=ahora
    )

    assert comparaciones._version_datos() == "sin-carga", "solo cuentan las que terminaron bien"


@pytest.mark.django_db
def test_la_url_publica_lleva_la_version_de_los_datos(client, catalogo: None, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Sin esto el navegador enseña el PNG viejo aunque el servidor ya repintó (review v24, QA-01).

    LA CLAVE DEL SERVIDOR NO ALCANZA AL CLIENTE. Invalida la caché de Django, pero el navegador, el
    proxy y el rastreador de la red social se quedan con lo que bajaron hasta que venza el `max-age` —
    seis horas de una imagen vieja circulando como si fuera actual. Es el fallo que solo se ve después
    de una carga real: el backend ya cambió y en pantalla no pasa nada.

    Colgando el sello de la URL, una carga nueva produce una dirección nueva y todos revalidan a la vez.
    """
    from datetime import timedelta

    from django.conf import settings
    from django.core.cache import caches
    from django.utils import timezone

    from dglweb.stats.models import IngestRun

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)
    pagina = reverse("comparar", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})

    ahora = timezone.now()
    IngestRun.objects.create(
        command="batting", status=IngestRun.Status.SUCCESS, started_at=ahora, finished_at=ahora
    )
    antes = client.get(pagina).context["url_png"]

    IngestRun.objects.create(
        command="batting",
        status=IngestRun.Status.SUCCESS,
        started_at=ahora + timedelta(days=1),
        finished_at=ahora + timedelta(days=1),
    )
    caches[settings.COMPARTIDA].clear()  # la versión se recuerda 5 minutos
    despues = client.get(pagina).context["url_png"]

    assert "?v=" in antes
    assert antes != despues, "una carga nueva cambia la dirección, así que el navegador la vuelve a pedir"
    assert antes.split("?")[0] == despues.split("?")[0], "y la ruta canónica no se mueve"


@pytest.mark.django_db
def test_un_v_inventado_no_multiplica_la_cache(client, catalogo: None, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """La clave del servidor ignora la cadena de consulta, así que `?v=` no es una vía de abuso."""
    from dglweb.stats import tarjeta

    uno, otro = _jugador(1, "Uno"), _jugador(2, "Otro")
    _bateo(uno, 2020)
    _bateo(otro, 2020)

    veces: list[int] = []
    original = tarjeta.png

    def contando(foto: dict) -> bytes:  # type: ignore[type-arg]
        veces.append(1)
        return original(foto)

    monkeypatch.setattr(tarjeta, "png", contando)
    ruta = reverse("comparar_png", kwargs={"uno": uno.slug, "otro": otro.slug, "modo": "carrera"})

    for basura in ("abc", "def", "123"):
        client.get(ruta, {"v": basura})

    assert len(veces) == 1, "tres direcciones distintas, una sola entrada"
