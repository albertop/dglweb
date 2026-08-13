"""La página de comparación entre dos peloteros. Ver `docs/COMPARADOR.md`.

Acá NO se calcula nada: el cálculo vive en `stats/comparador.py` y esto lo pinta. La división es la
misma que hay entre `stats/leaders.py` y `profiles/leaderboards.py`.

LAS TRES MODALIDADES SON TRES RUTAS Y NO UN `?modo=`
-----------------------------------------------------
    /comparar/juan-soto-665742/vs/albert-pujols-405395/carrera/
    /comparar/juan-soto-665742/vs/albert-pujols-405395/mejores-5/
    /comparar/juan-soto-665742/vs/albert-pujols-405395/temporadas/2024-2021/

El sitio calcula la canónica desde `request.path` y descarta la cadena de consulta —ver `base.html`—
así que un `?modo=carrera` haría que las tres versiones se declararan como la MISMA página. Con la
modalidad en la ruta, cada comparación es un enlace propio e indexable, que es de lo que va el
feature: lo que trae tráfico no es el PNG sino la URL que lo acompaña.

EL PAR SE NORMALIZA A UN ORDEN FIJO
------------------------------------
`soto/vs/pujols` y `pujols/vs/soto` son la misma comparación. Sin normalizar existirían las dos para
Google —contenido duplicado— y el PNG se cachearía dos veces. Se ordena por `player_id` y la otra
forma redirige, igual que hace el perfil cuando el slug no es el canónico.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from django.conf import settings
from django.core.cache import caches
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from dglweb.players.models import Player
from dglweb.stats import comparador
from dglweb.stats.models import Metric

# `mejores-5`, y nada más. El número se valida contra el rango en `comparador.comparar`, así que acá
# solo hace falta reconocer la forma.
_MEJORES = re.compile(r"^mejores-(\d+)$")
# `2024-2021`: el año de cada uno, en el orden de la URL. No tienen por qué coincidir — ahí está la
# gracia de la modalidad.
_TEMPORADAS = re.compile(r"^(\d{4})-(\d{4})$")


# LAS IMÁGENES SE CACHEAN, y no es un lujo: cada una resuelve dos peloteros, calcula los rankings de
# todas sus métricas sobre las 5.185 temporadas dominicanas, abre tipografías y retratos y pinta un PNG
# de 200 KB con Pillow. Es la ruta más cara del sitio y es pública, sin autenticación: un bot que pida
# combinaciones válidas la usa de ariete contra los hilos de gunicorn — y justo cuando una comparación
# se hace viral, el tráfico natural golpea ahí.
#
# EN SU PROPIA CACHÉ, `settings.IMAGENES`, y no en la compartida: una tarjeta pesa 200 KB y desalojaría
# las entradas pequeñas que se leen en todas las páginas. El porqué entero está junto a `CACHES`.
#
# Y en base y no en `locmem`: con varios trabajadores de gunicorn, la memoria local guardaría una copia
# por proceso y la primera petición sería cara tantas veces como procesos haya.
#
# VEINTICINCO HORAS, Y LA FRESCURA NO LA DA EL RELOJ SINO LA CLAVE (dueño: «las estadísticas se cargan
# una vez al día», 2026-08-13).
#
# EL PRIMER INTENTO FUERON SEIS HORAS Y ERA UN NÚMERO MAL ELEGIDO por los dos lados: la tarjeta se
# repintaba hasta cuatro veces al día para producir el MISMO PNG —los datos no cambian entre cargas— y
# aun así una carga que terminara a las 6:05 tardaba seis horas en verse. Un temporizador no puede
# acertar: o sobra trabajo o sobra retraso.
#
# LO QUE SE HACE EN SU LUGAR: la marca de la última carga entra en la clave (ver `_version_datos`).
# Cuando el pipeline termina, la clave cambia y la tarjeta se repinta en la siguiente petición — si
# Soto batea un jonrón, su tarjeta lo trae en cuanto el dato existe, no cuando venza un reloj.
#
# Y ADEMÁS UN TTL DE SEIS HORAS, que no sobra: son dos defensas para dos fallos distintos (dueño).
#
# LA CLAVE cubre el caso normal —carga nueva, tarjeta nueva, al instante— pero DEPENDE DE QUE EL
# PIPELINE ESCRIBA SU `IngestRun`. Un cargador que no pase por `record_run`, o uno que se cuelgue en
# RUNNING sin cerrar, deja la versión congelada: sin reloj, la tarjeta se quedaría cacheada para
# siempre y nadie lo notaría, porque una imagen vieja no se ve vieja.
#
# EL RELOJ cubre eso, y acota el daño a seis horas pase lo que pase. El coste de tenerlo de más es
# repintar un PNG idéntico cuatro veces al día; el de no tenerlo, publicar cifras de la semana pasada.
CACHE_TARJETA = 6 * 60 * 60
_PREFIJO_CACHE = "cmp-tarjeta"
# Cuánto se cree la versión sin volver a preguntarla. Es una consulta barata, pero corre en CADA
# petición de imagen y el objetivo era justamente que un acierto de caché no tocara la base. Cinco
# minutos de retraso sobre una carga diaria no se notan.
_CACHE_VERSION = 5 * 60


# EL ASISTENTE: SEIS PASOS, UNA PREGUNTA CADA UNO (dueño, 2026-08-13).
#
# Hubo un formulario de una pantalla y no le gustó, con razón: obligaba a entender las tres
# modalidades, los dos buscadores y el umbral ANTES de haber elegido nada. Preguntar de una en una
# también deja que cada paso use lo contestado en el anterior — el buscador del paso 2 solo ofrece
# bateadores si en el 1 dijiste «bateadores».
#
# EL ESTADO VIAJA EN LA URL y no en la sesión. Así el botón «atrás» del navegador funciona, se puede
# recargar sin perder nada, y cada paso es una dirección que se puede probar y depurar a mano. Una
# sesión daría comportamientos distintos en dos pestañas del mismo navegador.
PASOS = 6

# QUÉ CAMPO PINTA CADA PASO. Se usa para NO repetirlo como oculto: el navegador mandaría los dos y
# gana el primero, así que cambiar una respuesta al retroceder no tendría efecto.
_CAMPOS_DEL_PASO: dict[int, tuple[str, ...]] = {
    1: ("oficio",),
    2: ("uno",),
    3: ("otro",),
    4: ("modo",),
    5: ("cuantas", "anio_uno", "anio_otro"),
}

OFICIOS = (
    ("batting", "Bateadores"),
    ("SP", "Lanzadores abridores"),
    ("RP", "Lanzadores relevistas"),
)

MODALIDADES = (
    ("carrera", "La carrera completa"),
    ("mejores", "Sus mejores temporadas, por WAR"),
    ("temporadas", "Una temporada específica de cada uno"),
)


def _grupo_del_oficio(oficio: str) -> str:
    """De los tres oficios del asistente a los dos del catálogo de métricas.

    Abridores y relevistas comparten las mismas métricas de pitcheo: el oficio separa QUIÉN aparece en
    los buscadores, contra quién se rankea y qué umbral se le exige — no qué se mide. Por eso hace
    falta la traducción: el catálogo de métricas solo conoce dos grupos.
    """
    return "batting" if oficio == "batting" else "pitching"


def generador(request: HttpRequest) -> HttpResponse:
    """El asistente que arma la comparación, paso a paso. Ver `docs/COMPARADOR.md`.

    ES UN GENERADOR Y UN DISTRIBUIDOR: acá se eligen los parámetros y al final se SALTA a la tarjeta,
    que es la que trae los botones de compartir. Esto no pinta nunca una comparación — redirige a la
    URL canónica — y así lo que se comparte es un enlace propio e indexable y no un formulario relleno.

    CADA PASO VALIDA LO SUYO Y NO DEJA AVANZAR. «No quiero que el site tome decisiones que el usuario
    luego no entienda qué pasó» (dueño): por eso nada se rellena solo ni se baja en silencio.
    """
    datos = request.GET
    estado = {
        "oficio": datos.get("oficio") or "",
        "uno": datos.get("uno") or "",
        "otro": datos.get("otro") or "",
        "modo": datos.get("modo") or "",
        "cuantas": datos.get("cuantas") or "",
        "anio_uno": datos.get("anio_uno") or "",
        "anio_otro": datos.get("anio_otro") or "",
    }
    paso = min(max(_entero(datos.get("paso"), 1), 1), PASOS)
    # NO SE PUEDE SALTAR A UN PASO SIN HABER CONTESTADO LOS ANTERIORES. Pasa al pegar una URL vieja o
    # al retroceder y cambiar algo de arriba: se cae al primer paso que le falte respuesta, en vez de
    # enseñar una pantalla que da por hecho algo que ya no es cierto.
    paso = min(paso, _primero_incompleto(estado))
    # EL PASO 5 NO EXISTE PARA LA CARRERA COMPLETA. Los botones ya lo saltan, pero se puede llegar
    # escribiendo la URL o retrocediendo tras cambiar la modalidad, y ahí saldría la pantalla de años
    # de una comparación que no usa años.
    if paso == 5 and estado["modo"] == "carrera":
        paso = PASOS

    errores: list[str] = []
    if datos.get("comparar"):
        destino = _validar(estado, errores)
        if destino:
            return redirect(destino)
        paso = PASOS

    grupo = _grupo_del_oficio(estado["oficio"])
    nombres = {"uno": _nombre(estado["uno"]), "otro": _nombre(estado["otro"])}
    return render(request, "profiles/generador.html", {
        "paso": paso,
        "pasos": PASOS,
        "pasos_lista": range(1, PASOS + 1),
        # EL SALTO DEL PASO 5 EN CARRERA se calcula acá y no en la plantilla: es una regla del flujo,
        # no de presentación, y en la plantilla habría que repetirla en los dos botones.
        "anterior": _anterior(paso, estado),
        "siguiente": _siguiente(paso, estado),
        # Lo ya contestado, MENOS lo que pinta el paso actual: repetirlo mandaría el campo dos veces y
        # el valor viejo ganaría al nuevo en la mitad de los casos.
        "ocultos": [(k, v) for k, v in estado.items() if v and k not in _CAMPOS_DEL_PASO.get(paso, ())],
        "estado": estado,
        # EL RÓTULO ES EL NOMBRE A SECAS (dueño): la pregunta del paso ya dice «¿Qué temporada de cada
        # uno?», así que repetir «Temporada de» delante de los dos nombres es ruido.
        "anios_campos": [
            ("uno", nombres["uno"], estado["anio_uno"]),
            ("otro", nombres["otro"], estado["anio_otro"]),
        ],
        "errores": errores,
        "oficios": OFICIOS,
        "modalidades": MODALIDADES,
        "rango": range(comparador.TEMPORADAS_MINIMAS, comparador.TEMPORADAS_MAXIMAS + 1),
        # El mínimo que se enseña en el paso 5 es el del oficio elegido en el paso 1, no el genérico.
        "minimo": comparador.minimo_de(grupo, estado["oficio"]),
        "unidad": "entradas lanzadas" if grupo == "pitching" else "apariciones al plato",
        "nombres": nombres,
        # El resumen del último paso, en castellano y no en jerga de parámetros: es la última
        # oportunidad de que alguien vea que pidió otra cosa.
        "resumen": _resumen(estado) if paso == PASOS else [],
    })


def _primero_incompleto(estado: dict[str, str]) -> int:
    """El primer paso que todavía no tiene respuesta. Es el techo hasta donde se puede avanzar."""
    if not estado["oficio"]:
        return 1
    if not estado["uno"]:
        return 2
    if not estado["otro"]:
        return 3
    if not estado["modo"]:
        return 4
    # LA CARRERA COMPLETA NO PIDE NADA MÁS, así que el paso 5 se salta entero. Enseñar una pantalla
    # vacía con un «siguiente» sería peor que no enseñarla.
    if estado["modo"] == "carrera":
        return PASOS
    if estado["modo"] == "mejores" and not estado["cuantas"]:
        return 5
    if estado["modo"] == "temporadas" and not (estado["anio_uno"] and estado["anio_otro"]):
        return 5
    return PASOS


def _resumen(estado: dict[str, str]) -> list[tuple[str, str]]:
    """Lo elegido, en frases. Lo lee el último paso antes de generar."""
    oficio = dict(OFICIOS).get(estado["oficio"], "")
    filas = [
        ("Qué se compara", oficio),
        ("Primer pelotero", _nombre(estado["uno"])),
        ("Segundo pelotero", _nombre(estado["otro"])),
    ]
    if estado["modo"] == "carrera":
        filas.append(("Modalidad", "La carrera completa"))
    elif estado["modo"] == "mejores":
        cuantas = _entero(estado["cuantas"], 5)
        filas.append(
            ("Modalidad", "Su mejor temporada por WAR" if cuantas == 1 else f"Sus mejores {cuantas} temporadas por WAR")
        )
    elif estado["modo"] == "temporadas":
        filas.append(("Modalidad", "Una temporada específica de cada uno"))
        filas.append((f"Temporada de {_nombre(estado['uno'])}", estado["anio_uno"]))
        filas.append((f"Temporada de {_nombre(estado['otro'])}", estado["anio_otro"]))
    return filas


def temporadas_de(request: HttpRequest) -> JsonResponse:
    """Los años comparables de un pelotero, para llenar el desplegable. JSON, sin plantilla.

    POR QUÉ NO SE PINTAN CON LA PÁGINA: los años dependen de a quién se eligió, y a quién se eligió se
    decide en el navegador. La alternativa sería recargar entera la página al elegir cada pelotero, y
    eso pierde el foco y lo escrito en el otro lado del formulario.

    SOLO SALEN LOS AÑOS QUE CUENTAN COMO TEMPORADA (dueño). Un desplegable que ofrece el año de veinte
    turnos está invitando a una comparación cuyo resultado no dice nada, y el usuario no tiene forma
    de saberlo hasta que la ve.
    """
    from dglweb.profiles.views import _player_id_from_slug

    slug = request.GET.get("jugador") or ""
    pelotero = Player.objects.filter(pk=_player_id_from_slug(slug)).first() if slug else None
    if not pelotero:
        return JsonResponse({"anios": []})

    grupo, oficio = _grupo_de(pelotero), _oficio_de(pelotero)
    anios, _ = comparador.inventario(grupo, pelotero.player_id, oficio=oficio)[pelotero.player_id]
    return JsonResponse({
        "anios": anios,
        "grupo": grupo,
        "oficio": oficio,
        "minimo": comparador.minimo_de(grupo, oficio),
        "nombre": pelotero.full_name,
    })


def tarjeta_png(request: HttpRequest, uno: str, otro: str, modo: str, extra: str | None = None) -> HttpResponse:
    """La tarjeta como imagen. Es LO MISMO que muestra la página, no una versión aparte.

    UNA SOLA REPRESENTACIÓN DEL RESULTADO (dueño, 2026-08-13). La página no pinta una tabla y además
    ofrece una imagen: la página ES la imagen. Dos versiones del mismo dato acaban divergiendo, y la
    que circula por WhatsApp es la que nadie puede corregir.

    Se sirve desde la misma URL que la página, con `.png` al final, para que compartir el enlace y
    compartir el fichero lleven al mismo sitio.
    """
    # LA PREVIA DE LAS REDES ES OTRA IMAGEN, apaisada: ver `tarjeta.previa`. Se sirve desde la misma
    # vista con `?previa=1` porque es la MISMA comparación en otro encuadre, no otro contenido.
    quiere_previa = bool(request.GET.get("previa"))
    clave = _clave(uno, otro, modo, extra, quiere_previa)

    imagen: bytes | None = caches[settings.IMAGENES].get(clave)
    if imagen is None:
        imagen = _dibujar(uno, otro, modo, extra, quiere_previa)
        caches[settings.IMAGENES].set(clave, imagen, CACHE_TARJETA)

    # EL 304 SE CONTESTA ACÁ, y hay que hacerlo a mano (review v23, QA-01).
    #
    # Publicar un `ETag` NO basta: quien valida con `If-None-Match` recibe un 200 con los 200 KB otra
    # vez a menos que alguien compare. El proyecto no monta `ConditionalGetMiddleware` —tocarlo
    # afectaría a todas las respuestas del sitio— así que la comparación va donde es barata y donde su
    # efecto se entiende: en la única vista que sirve archivos grandes.
    #
    # El `ETag` sale del contenido, así que si los números cambian el hash cambia con ellos y el
    # navegador se entera sin esperar a que caduque nada.
    etiqueta = f'"{hashlib.sha256(imagen).hexdigest()[:32]}"'
    if request.headers.get("If-None-Match") == etiqueta:
        respuesta = HttpResponse(status=304)
    else:
        respuesta = HttpResponse(imagen, content_type="image/png")
        # `inline` y no `attachment`: la página la muestra. El botón de descargar lo fuerza aparte con
        # el atributo `download`, que es cosa del navegador y no del servidor.
        respuesta["Content-Disposition"] = f'inline; filename="{uno}-vs-{otro}-{modo}.png"'

    # EN DESARROLLO EL NAVEGADOR NO CACHEA. Con seis horas de `max-age`, limpiar la caché del servidor
    # no sirve de nada: el navegador sigue enseñando el PNG que ya tiene y parece que el cambio de
    # diseño no entró. Pasó dos veces mirando la tarjeta en dev.
    edad = 0 if settings.DEBUG else CACHE_TARJETA
    respuesta["Cache-Control"] = f"public, max-age={edad}" if edad else "no-cache"
    respuesta["ETag"] = etiqueta
    return respuesta


def _dibujar(uno: str, otro: str, modo: str, extra: str | None, quiere_previa: bool) -> bytes:
    """El trabajo caro: resolver la comparación y pintar. Solo se entra acá si la caché falló."""
    from dglweb.stats import tarjeta

    _, _, foto = _resolver(uno, otro, modo, extra)
    vertical = tarjeta.png(foto)
    # LA PREVIA REUSA LOS BYTES DE LA VERTICAL. Sin pasárselos, `previa()` vuelve a dibujar la tarjeta
    # entera —tipografías, retratos, todas las filas— solo para reescalarla.
    return tarjeta.previa(foto, vertical) if quiere_previa else vertical


def _entero(bruto: str | None, defecto: int) -> int:
    try:
        return int(bruto or "")
    except ValueError:
        return defecto


def _nombre(slug: str) -> str:
    from dglweb.profiles.views import _player_id_from_slug

    if not slug:
        return ""
    hallado = Player.objects.filter(pk=_player_id_from_slug(slug)).first()
    return hallado.full_name if hallado else ""


def _validar(estado: dict[str, str], errores: list[str]) -> str | None:
    """Los dos peloteros y los parámetros, o la lista de errores llena. Devuelve la ruta de destino.

    SE VALIDA TODO OTRA VEZ AL FINAL aunque cada paso ya haya comprobado lo suyo: el estado viaja en
    la URL, así que se puede llegar acá con cualquier combinación escrita a mano. Los pasos evitan el
    error; esto lo impide.
    """
    from dglweb.profiles.views import _player_id_from_slug

    elegidos = [estado["uno"], estado["otro"]]
    modo = estado["modo"]
    cuantas = _entero(estado["cuantas"], 5)
    anios = [estado["anio_uno"], estado["anio_otro"]]

    peloteros: list[Player] = []
    for slug, etiqueta in zip(elegidos, ("primer", "segundo"), strict=True):
        hallado = Player.objects.filter(pk=_player_id_from_slug(slug)).first() if slug else None
        if not hallado:
            errores.append(f"Falta elegir el {etiqueta} pelotero: escribe su nombre y elígelo de la lista.")
        else:
            peloteros.append(hallado)
    if len(peloteros) < 2:
        return None
    if peloteros[0].player_id == peloteros[1].player_id:
        errores.append("Son el mismo pelotero. Elige dos distintos.")
        return None

    # BATEADOR CONTRA LANZADOR NO COMPARTE NI UNA SOLA MÉTRICA, así que la tabla saldría
    # vacía. La tarjeta responde 404; acá se puede decir por qué.
    oficios = {p.player_id: _grupo_de(p) for p in peloteros}
    if len(set(oficios.values())) > 1:
        errores.append(
            f"{peloteros[0].full_name} y {peloteros[1].full_name} no se pueden comparar: "
            "uno es lanzador y el otro bateador, y no comparten ninguna estadística."
        )
        return None
    grupo = next(iter(oficios.values()))

    # ABRIDOR CONTRA RELEVISTA NO, y acá se explica en vez de responder 404: cada uno se rankea en su
    # población y con su umbral, así que la tarjeta tendría que elegir una de las dos.
    if len({_oficio_de(p) for p in peloteros}) > 1:
        errores.append(
            f"{peloteros[0].full_name} y {peloteros[1].full_name} no se pueden comparar: uno es "
            "abridor y el otro relevista, y sus puestos se calculan contra grupos distintos."
        )
        return None

    fuera = [p for p in peloteros if p.player_id not in comparador.universo(grupo)]
    if fuera:
        errores.append(
            f"{fuera[0].full_name} debutó antes de 1956 y sus números no son comparables con los "
            "de Grandes Ligas."
        )
        return None

    # CADA PELOTERO CON SU OFICIO: en un par de relevistas el mínimo es 20 IP y no 30, que es lo que
    # la tarjeta va a usar. Se resuelve uno a uno porque el oficio es de cada pelotero, no del par.
    inventario = {}
    for p in peloteros:
        inventario.update(comparador.inventario(grupo, p.player_id, oficio=_oficio_de(p)))
    ruta = {"uno": peloteros[0].slug, "otro": peloteros[1].slug}

    if modo == "carrera":
        return reverse("comparar", kwargs={**ruta, "modo": "carrera"})

    if modo == "temporadas":
        unidad_anio = "IP" if grupo == "pitching" else "PA"
        pedidos: list[int] = []
        for pelotero, bruto in zip(peloteros, anios, strict=True):
            comparables = inventario[pelotero.player_id][0]
            anio = _entero(bruto, 0)
            if anio not in comparables:
                # SE DISTINGUE «no jugó» DE «jugó demasiado poco», porque son dos cosas distintas y
                # la segunda deja al usuario mirando un año que él sabe que existió. El desplegable
                # no ofrece ninguno de los dos casos; esto es la red para la URL escrita a mano.
                if not comparables:
                    errores.append(
                        f"{pelotero.full_name} no tiene ninguna temporada de al menos "
                        f"{comparador.minimo_de(grupo, _oficio_de(pelotero))} {unidad_anio}."
                    )
                else:
                    errores.append(
                        f"{pelotero.full_name} no tiene una temporada comparable en {bruto or '—'}. "
                        f"Elige entre {comparables[-1]} y {comparables[0]}."
                    )
            pedidos.append(anio)
        if errores:
            return None
        return reverse("comparar", kwargs={**ruta, "modo": "temporadas", "extra": f"{pedidos[0]}-{pedidos[1]}"})

    if not comparador.TEMPORADAS_MINIMAS <= cuantas <= comparador.TEMPORADAS_MAXIMAS:
        errores.append(
            f"Se comparan entre {comparador.TEMPORADAS_MINIMAS} y {comparador.TEMPORADAS_MAXIMAS} temporadas."
        )
        return None

    # EL ERROR QUE PIDIÓ EL DUEÑO, NOMBRANDO AL PELOTERO Y DICIENDO QUÉ PEDIR. Se comprueban los dos y
    # se reporta el que menos tenga, porque bajar a lo que aguante el más corto es lo que hay que
    # pedir para que la comparación sea posible: enfrentar 7 temporadas contra 4 le daría la victoria
    # al de carrera larga por construcción.
    unidad = "IP" if grupo == "pitching" else "PA"
    cortos = [(p, inventario[p.player_id][1]) for p in peloteros if inventario[p.player_id][1] < cuantas]
    if cortos:
        pelotero, tiene = min(cortos, key=lambda par: par[1])
        if tiene == 0:
            errores.append(
                f"{pelotero.full_name} no tiene ninguna temporada de al menos "
                f"{comparador.minimo_de(grupo, _oficio_de(pelotero))} {unidad}, así que no entra en esta modalidad."
            )
        else:
            errores.append(
                f"{pelotero.full_name} tiene {tiene} temporada{'s' if tiene != 1 else ''} de al menos "
                f"{comparador.minimo_de(grupo, _oficio_de(pelotero))} {unidad}, no {cuantas}. "
                f"Compara con {tiene} o menos."
            )
        return None

    return reverse("comparar", kwargs={**ruta, "modo": f"mejores-{cuantas}"})


def _grupo_de(pelotero: Player) -> str:
    return "pitching" if (pelotero.pos or "").upper() in {"P", "SP", "RP"} else "batting"


def _oficio_de(pelotero: Player) -> str:
    """Bateador, abridor o relevista. Es lo que parte la población del ranking y los umbrales.

    UN «P» A SECAS CAE EN ABRIDOR, que es el umbral estricto de siempre. Prefiero quedarme corto —que
    a alguien le falte un puesto— antes que darle uno calculado contra la población equivocada.
    """
    pos = (pelotero.pos or "").upper()
    if pos == comparador.OFICIO_RELEVISTA:
        return comparador.OFICIO_RELEVISTA
    if pos in {"P", comparador.OFICIO_ABRIDOR}:
        return comparador.OFICIO_ABRIDOR
    return comparador.OFICIO_BATEO


def _jugador(slug: str) -> Player:
    """El pelotero del slug, o 404. `Player.objects` filtra a los deshabilitados."""
    from dglweb.profiles.views import _player_id_from_slug

    return get_object_or_404(Player.objects, pk=_player_id_from_slug(slug))


def _oficio(uno: Player, otro: Player) -> str:
    """Bateo o pitcheo, y los dos tienen que ser lo mismo.

    NO SE COMPARA UN BATEADOR CON UN LANZADOR: no comparten ni una sola métrica, así que la
    tabla saldría vacía. El selector ya lo impide, y esto es la red para la URL escrita a mano.
    """
    oficios = {p.player_id: _grupo_de(p) for p in (uno, otro)}
    if len(set(oficios.values())) > 1:
        raise Http404("no se compara un bateador con un lanzador")

    # UN ABRIDOR CONTRA UN RELEVISTA TAMPOCO, y esto cambió al separar los umbrales (2026-08-13).
    #
    # No es por las métricas —son las mismas— sino por el RANKING: cada uno se rankea en su
    # población y con su umbral, así que una tarjeta mixta tendría que elegir una de las dos. Antes
    # elegía la del pelotero de la izquierda, y «la izquierda» sale de ordenar por `player_id`: azar.
    # El mismo par podía dar dos rankings distintos según qué número de MLB tuviera cada uno.
    #
    # Las alternativas eran rankear cada lado en su propia población —y entonces la cabecera tendría
    # que decir dos oficios, y el «(2º)» de una fila y el de la de al lado significarían cosas
    # distintas— o negarse. Negarse es lo honesto: el asistente no puede producir esta comparación,
    # porque el oficio se fija en el paso 1, así que esto solo alcanza a la URL escrita a mano.
    if len({_oficio_de(p) for p in (uno, otro)}) > 1:
        raise Http404("no se compara un abridor con un relevista: se rankean en poblaciones distintas")
    return next(iter(oficios.values()))


def _leer_modo(modo: str, extra: str | None) -> tuple[str, int, tuple[int | None, int | None]]:
    """La ruta a `(modalidad, cuántas, (año izquierdo, año derecho))`, o 404 si no encaja.

    Un 404 y no un valor por defecto: una ruta que no existe tiene que decirlo. Cayendo a «carrera»
    se serviría contenido bajo una dirección inventada, y Google la indexaría.
    """
    if modo == "carrera":
        return comparador.MODO_CARRERA, 5, (None, None)
    if hallado := _MEJORES.match(modo):
        return comparador.MODO_MEJORES, int(hallado.group(1)), (None, None)
    if modo == "temporadas" and extra and (anios := _TEMPORADAS.match(extra)):
        return comparador.MODO_TEMPORADA, 5, (int(anios.group(1)), int(anios.group(2)))
    raise Http404(f"modalidad desconocida: {modo}")


def _resolver(uno: str, otro: str, modo: str, extra: str | None) -> tuple[Player, Player, dict[str, Any]]:
    """Los dos peloteros en orden canónico y la foto calculada. Lo comparten la página y el PNG.

    Está factorizado porque son la MISMA comparación servida de dos formas: si la página y la imagen
    resolvieran la URL cada una por su lado, un cambio en la lectura de la modalidad se aplicaría solo
    a una y la imagen empezaría a decir algo distinto de la página que la enseña.
    """
    izquierda, derecha = _jugador(uno), _jugador(otro)
    if izquierda.player_id > derecha.player_id:
        izquierda, derecha = derecha, izquierda

    modalidad, cuantas, anios = _leer_modo(modo, extra)
    grupo = _oficio(izquierda, derecha)
    # EL OFICIO SALE DEL LADO IZQUIERDO, y a estas alturas eso ya no es una elección: `_oficio` acaba
    # de comprobar que los dos son el mismo, y RECHAZA el par mixto (review v22). Tomar el izquierdo
    # es tomar el de los dos.
    #
    # Antes sí era una elección, y mala: «el izquierdo» sale de ordenar por `player_id`, o sea por el
    # número que MLB le asignó a cada uno. El mismo par daba rankings distintos según quién tuviera el
    # número más bajo.
    oficio = _oficio_de(izquierda)
    try:
        foto = comparador.comparar(
            grupo, (izquierda.player_id, anios[0]), (derecha.player_id, anios[1]), modalidad,
            cuantas=cuantas, oficio=oficio,
        )
    except ValueError as error:
        # Lo que `comparar` rechaza son peticiones imposibles —un 12 en «mejores», alguien sin WAR—
        # y eso es un 404 y no un 500: la URL no describe una página que pueda existir.
        raise Http404(str(error)) from error
    return izquierda, derecha, foto


def comparar(request: HttpRequest, uno: str, otro: str, modo: str, extra: str | None = None) -> HttpResponse:
    """La página de resultado: LA TARJETA Y LOS BOTONES DE COMPARTIR, nada más.

    NO HAY TABLA EN HTML (dueño, 2026-08-13). La hubo y se quitó: lo que la gente comparte es una
    imagen, así que la página tiene que enseñar exactamente eso y no una segunda versión del mismo
    dato que acabaría divergiendo.
    """
    # EL ORDEN CANÓNICO Y LOS SLUGS CANÓNICOS, en una sola redirección permanente. El perfil hace lo
    # mismo cuando el slug no está al día; acá se suma que el par puede venir al revés.
    izquierda, derecha = _jugador(uno), _jugador(otro)
    if izquierda.player_id > derecha.player_id:
        izquierda, derecha = derecha, izquierda
    if (uno, otro) != (izquierda.slug, derecha.slug):
        destino = {"uno": izquierda.slug, "otro": derecha.slug, "modo": modo}
        if extra:
            destino["extra"] = extra
        return redirect("comparar", permanent=True, **destino)

    izquierda, derecha, foto = _resolver(uno, otro, modo, extra)
    return render(request, "profiles/comparar.html", _contexto(foto, izquierda, derecha, foto["grupo"]))


def _rotulo(foto: dict[str, Any]) -> str:
    """Cómo se llama esta comparación en una frase. Es lo que va en el título y en la descripción."""
    if foto["modo"] == comparador.MODO_CARRERA:
        return "carrera completa"
    if foto["modo"] == comparador.MODO_MEJORES:
        # El singular se escribe entero, igual que en la tarjeta: «su mejor temporada», no «sus
        # mejores 1 temporadas». Ver el mismo caso en `stats/tarjeta.py`.
        if foto["cuantas"] == 1:
            return "su mejor temporada por WAR"
        return f"sus mejores {foto['cuantas']} temporadas por WAR"
    return f"temporada {foto['izquierda']['temporadas'][0]}"


def _alt(foto: dict[str, Any], izquierda: Player, derecha: Player, grupo: str) -> str:
    """El texto alternativo de la tarjeta, con las cifras dentro.

    LA IMAGEN ES EL CONTENIDO DE LA PÁGINA, no un adorno: si el `alt` dice «tarjeta comparativa»,
    quien usa lector de pantalla se queda sin la comparación entera. Por eso se enumeran las métricas
    con sus valores, que es lo que la imagen enseña.

    Se corta en las seis primeras y se remite a la página: un `alt` de dieciséis cifras leído de corrido
    es tan inservible como uno vacío, y las seis primeras son las que encabezan la tarjeta.
    """
    from dglweb.profiles.leaderboards import _format

    metricas = {m.column: m for m in Metric.objects.filter(stat_group=grupo)}
    trozos = []
    for columna in comparador.METRICAS[grupo][:6]:
        izq, der = (foto[lado]["celdas"].get(columna) for lado in ("izquierda", "derecha"))
        metrica = metricas.get(columna)
        if not (izq and der and metrica):
            continue
        uno = _format(grupo, columna, izq.valor) if izq.valor is not None else "sin dato"
        otro = _format(grupo, columna, der.valor) if der.valor is not None else "sin dato"
        trozos.append(f"{metrica.abbrev} {uno} contra {otro}")
    return (
        f"{izquierda.full_name} contra {derecha.full_name}, {_rotulo(foto)}. "
        + "; ".join(trozos)
        + ". La tarjeta incluye el resto de las métricas y el puesto histórico de cada cifra."
    )


def _contexto(foto: dict[str, Any], izquierda: Player, derecha: Player, grupo: str) -> dict[str, Any]:
    """Lo que la plantilla necesita, ya masticado: ni una decisión de presentación en el HTML."""
    modo = foto["modo"]
    ruta = {"uno": izquierda.slug, "otro": derecha.slug}
    if modo == comparador.MODO_MEJORES:
        ruta["modo"] = f"mejores-{foto['cuantas']}"
    elif modo == comparador.MODO_TEMPORADA:
        ruta["modo"] = "temporadas"
        ruta["extra"] = f"{foto['izquierda']['temporadas'][0]}-{foto['derecha']['temporadas'][0]}"
    else:
        ruta["modo"] = "carrera"

    return {
        "modo": modo,
        "grupo": grupo,
        "rotulo": _rotulo(foto),
        "alt": _alt(foto, izquierda, derecha, grupo),
        # EL TEXTO DEL MENSAJE al compartir el enlace. Lleva los dos nombres y la modalidad porque «un
        # enlace con datos se abre y uno genérico se ignora» —lo dice el propio tag `compartir`— y
        # porque en WhatsApp esta línea es lo ÚNICO que se lee antes de decidir si se pincha.
        "titulo_compartir": f"{izquierda.full_name} vs. {derecha.full_name} — {_rotulo(foto)}",
        "url_png": f"{reverse('comparar_png', kwargs=ruta)}?v={_version_url()}",
        # La que ven X, WhatsApp y Facebook al pegar el enlace. Apaisada porque todas recortan a
        # ~1.91:1 y la tarjeta es 4:5: sin esto se pierden la cabecera con la marca y el pie con la
        # dirección del sitio, que son las dos cosas por las que se comparte.
        "url_previa": f"{reverse('comparar_png', kwargs=ruta)}?previa=1&v={_version_url()}",
        # El nombre con el que se guarda al descargar. Lleva los dos peloteros y la modalidad para que
        # una carpeta con veinte tarjetas siga siendo legible.
        "nombre_archivo": f"{izquierda.slug}-vs-{derecha.slug}-{ruta['modo']}.png",
        "lados": [
            {"player": jugador, "temporadas": foto[lado]["temporadas"]}
            for lado, jugador in (("izquierda", izquierda), ("derecha", derecha))
        ],
    }


def _anterior(paso: int, estado: dict[str, str]) -> int:
    """El paso al que lleva «Atrás», saltando el 5 cuando la modalidad no pide parámetros."""
    if paso == PASOS and estado["modo"] == "carrera":
        return 4
    return max(paso - 1, 1)


def _siguiente(paso: int, estado: dict[str, str]) -> int:
    """El paso al que lleva «Siguiente».

    LA CARRERA COMPLETA SE SALTA EL 5 porque no pide nada más. Enseñar una pantalla vacía con un botón
    de seguir sería peor que no enseñarla: el usuario se queda buscando qué tenía que contestar.
    """
    if paso == 4 and estado["modo"] == "carrera":
        return PASOS
    return min(paso + 1, PASOS)


def _clave(uno: str, otro: str, modo: str, extra: str | None, previa: bool) -> str:
    """La clave de caché de una tarjeta. CANÓNICA, no la ruta que se pidió (review v23, SEC-01).

    EL AGUJERO QUE CIERRA: la clave era `request.path`, y a la misma comparación se llega por muchas
    rutas. El par al revés —`b/vs/a`— es la misma tarjeta, y el slug se resuelve por el id del final,
    así que `soto-viejo-665742` y `juan-soto-665742` también. Un bot que fabricara variantes forzaba
    un redibujo por cada una y desalojaba las 200 entradas útiles con basura. Para un usuario normal
    la caché seguía funcionando; contra tráfico adversarial, no.

    SE NORMALIZA SIN TOCAR LA BASE, que es lo que la hace útil: `_player_id_from_slug` es una
    operación de cadena, así que un acierto de caché sigue sin costar una consulta. Ordenar los dos
    ids reproduce el mismo orden canónico al que redirige la página.
    """
    from dglweb.profiles.views import _player_id_from_slug

    ids = sorted(str(_player_id_from_slug(s)) for s in (uno, otro))
    partes = [_PREFIJO_CACHE, _version_datos(), "previa" if previa else "png", *ids, modo, extra or ""]
    return ":".join(partes)


def _version_datos() -> str:
    """La marca de la última carga terminada. Es lo que hace caducar las tarjetas cuando toca.

    LAS ESTADÍSTICAS SE CARGAN UNA VEZ AL DÍA (dueño), así que una tarjeta solo puede cambiar cuando
    cambia esa carga. Metiendo la marca en la clave, la caché se invalida SOLA y en el instante
    correcto: ni antes —repintar lo mismo— ni después —publicar lo viejo—.

    `IngestRun` es el registro de vuelo del pipeline y ya guarda `finished_at` de cada ejecución; se
    mira solo las que terminaron BIEN, porque una fallida no cambió ningún número.

    SIN NINGUNA CARGA REGISTRADA devuelve un centinela en vez de reventar: en una base recién montada
    —o en las pruebas— la tarjeta tiene que salir igual, y todas comparten la misma versión.
    """
    from django.db.models import Max

    from dglweb.stats.models import IngestRun

    clave = f"{_PREFIJO_CACHE}:version"
    version: str | None = caches[settings.COMPARTIDA].get(clave)
    if version is None:
        ultima = (
            IngestRun.objects.filter(status=IngestRun.Status.SUCCESS)
            .aggregate(cuando=Max("finished_at"))["cuando"]
        )
        version = ultima.isoformat() if ultima else "sin-carga"
        caches[settings.COMPARTIDA].set(clave, version, _CACHE_VERSION)
    return version


def _version_url() -> str:
    """La versión de los datos en forma de sello corto, para colgarla de la URL pública.

    LA CLAVE DEL SERVIDOR NO BASTA (review v24, QA-01). Invalida la caché de Django, pero el navegador,
    el proxy y el rastreador de la red social se quedan con el PNG que ya bajaron hasta que venza el
    `max-age`. El backend repintaba y en pantalla seguía la imagen vieja — que es exactamente el fallo
    que solo se ve después de una carga real.

    Colgando el sello de la URL, una carga nueva produce una dirección nueva y todos revalidan a la vez.
    Y NO MULTIPLICA ENTRADAS: la clave del servidor se arma con los ids, la modalidad y el tipo de
    imagen, así que ignora la cadena de consulta. Un bot que invente `?v=` recibe siempre la misma.

    Ocho caracteres de hash y no la marca de tiempo entera: en la URL solo tiene que CAMBIAR, no
    leerse, y una fecha ISO metida en una dirección compartible es ruido.
    """
    return hashlib.sha256(_version_datos().encode()).hexdigest()[:8]
