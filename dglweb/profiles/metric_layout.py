"""El vocabulario que el perfil del jugador y la página de Líderes comparten.

Las dos pantallas hablan de las mismas métricas y tienen que agruparlas y describirlas igual: si el
perfil dice que ISO va en Avanzado y Líderes la pone en Estándar, el lector que salta de una a la otra
cree que son cosas distintas. Y si el perfil escribe el umbral como `PA ≥ 502` y Líderes como
`PA>=502`, es la misma regla con dos caras.

Existe porque antes esto vivía en `tabs.py` con nombres privados y `leaderboards.py` los importaba
igual —`from ...tabs import _puestos_layout, _pretty_qualifier`—, lo que decía dos mentiras a la vez:
que eran internos de los tabs (no lo son, los usan dos pantallas) y que Líderes depende del perfil
(no depende, son pares). Se sintió al agregar Fildeo: tocar el layout obligaba a revisar un módulo de
mil líneas que no tenía nada que ver.

Regla: lo que usen las dos pantallas vive acá y es público. Lo que use solo una se queda en su módulo
y sigue privado.
"""

from django.core.cache import cache

from dglweb.profiles import columns
from dglweb.stats import qualifier
from dglweb.stats.models import Metric, QualifierDefault, QualifierSeasonOverride

# Métricas descriptivas: miden un ESTILO, no un logro. Un GB% máximo de carrera no dice que el
# pelotero mejoró en nada — su perfil de batazos se movió, y si eso lo ayuda depende de su velocidad,
# su poder, el parque y la época. Pintar ese extremo con la misma insignia que un récord de jonrones
# invita a leerlo mal, así que no llevan marca de mejor marca personal ni etiqueta de "mejor/peor".
#
# Su `direction` se queda como está: el motor igual necesita un orden para rankear. Distinto de
# Contact% y Whiff%, que SÍ tienen una dirección deportiva clara y conservan el resaltado.
#
# PU% está acá por decisión del dueño: es reparto de batazos como las otras cuatro, no una virtud.
# Antes se leía como que una palomita era un out casi automático —mala para el bateador, buena para el
# lanzador— y quedaba con direcciones opuestas por grupo; ahora no juzga en ninguno de los dos.
DESCRIPTIVE_COLUMNS: frozenset[str] = frozenset({"gb_pct", "fb_pct", "ld_pct", "gb_fb", "pu_pct"})


def _insert_after(columns_: list[str], anchor: str, value: str) -> list[str]:
    """Una copia de `columns_` con `value` metido justo después de `anchor` (o al final si no está)."""
    out = list(columns_)
    out.insert(out.index(anchor) + 1 if anchor in out else len(out), value)
    return out


def divisions_for(group: str) -> list[tuple[str, list[str]]]:
    """Las divisiones de un oficio y el orden de sus métricas, salido de las tablas del perfil.

    Cada división es un panel. Una columna que ya apareció en una división anterior no se repite (OPS
    vive en Estándar, su primera tabla). Statcast y Coeficientes se saltan el prefijo de contexto
    (G/AB en bateo, G/IP en pitcheo), ya contado bajo Estándar. Dos métricas rankeables de bateo no
    están en ninguna tabla: Sencillos (1B) entra entre H y 2B, y Boletos intencionales (IBB) tras BB.
    """
    if group == "fielding":
        # Fildeo no tiene Statcast ni Coeficientes: los batazos (AO/GO/FH/BIP…) son del bateador y del
        # lanzador, no de la posición defensiva. Y "Receptor" es su propia división porque solo aplica
        # a C — la página de líderes la muestra cuando la posición elegida es esa.
        divisions = [
            ("Estándar", [c.attr for c in columns.FIELDING_STANDARD]),
            ("Avanzado", [c.attr for c in columns.FIELDING_ADVANCED]),
            ("Receptor", [c.attr for c in columns.FIELDING_CATCHER]),
        ]
    elif group == "batting":
        standard = [c.attr for c in columns.BATTING_STANDARD]
        standard = _insert_after(standard, "h", "x1b")  # Sencillos entre H y 2B
        standard = _insert_after(standard, "bb", "ibb")  # Boletos intencionales tras BB
        divisions = [
            ("Estándar", standard),
            ("Avanzado", [c.attr for c in columns.BATTING_ADVANCED]),
            ("Statcast", [c.attr for c in columns.BATTING_STATCAST[2:]]),
            ("Coeficientes", [c.attr for c in columns.BATTING_RATIOS[2:]]),
        ]
    else:
        divisions = [
            ("Estándar", [c.attr for c in columns.PITCHING_STANDARD]),
            ("Avanzado", [c.attr for c in columns.PITCHING_ADVANCED]),
            ("Statcast", [c.attr for c in columns.PITCHING_STATCAST[2:]]),
            ("Coeficientes", [c.attr for c in columns.PITCHING_RATIOS[2:]]),
        ]
    seen: set[str] = set()
    layout: list[tuple[str, list[str]]] = []
    for label, attrs in divisions:
        ordered: list[str] = []
        for attr in attrs:
            if attr not in seen:
                seen.add(attr)
                ordered.append(attr)
        layout.append((label, ordered))
    return layout


def pretty_qualifier(formula: str) -> str:
    """`PA>=502` -> `PA ≥ 502`; las columnas de coeficientes toman su etiqueta corta. Vacío queda vacío."""
    return (
        formula.replace("BALLS_IN_PLAY", "BIP")
        .replace("TOTAL_SWINGS", "swings")
        .replace(">=", " ≥ ")
        .replace("<=", " ≤ ")
        .strip()
    )


# Cuánto viven en caché las tablas de referencia. Un día: las edita el dueño en el Backoffice unas
# pocas veces al año, y una señal tira la entrada en cuanto lo hace (ver `conectar_senales`). El TTL
# es la red por si alguien las cambia por SQL a mano, sin pasar por el ORM.
SEGUNDOS = 60 * 60 * 24
CLAVE_UMBRALES = "perfil:umbrales"
CLAVE_METRICAS = "perfil:metricas"


def qualifier_lookups() -> tuple[qualifier.Defaults, qualifier.Overrides]:
    """La cascada de umbrales (piso por grupo + overrides por temporada), precargada de una vez.

    POR QUÉ ESTÁ CACHEADA
    ---------------------
    El docstring decía «precargada de una vez» y era verdad a medias: se precargaba de una vez POR
    LLAMADA, y la página de un jugador la llama una vez por tab. Medido el 2026-07-28 sobre el perfil
    de Pedro Martínez, de sus 44 consultas había **cuatro** a `dgl_qualifier_default` —una tabla de
    TRES filas— y otras cuatro a los overrides.

    Son tablas de referencia: diminutas, iguales para todos los visitantes y que cambian cuando el
    dueño toca el Backoffice. El caso exacto para el que existe una caché.

    Esto es lo que se hizo EN VEZ de la carga diferida de los tabs (DEV-01). Diferir habría atacado
    el síntoma equivocado —las consultas repetidas se repetirían dentro de cada petición diferida—
    y de paso habría sacado del HTML el contenido de tres tabs, que es lo que indexa Google en las
    ~970 páginas de jugador.
    """
    guardado: tuple[qualifier.Defaults, qualifier.Overrides] | None = cache.get(CLAVE_UMBRALES)
    if guardado is not None:
        return guardado
    defaults = {d.stat_group: (d.qualifier_season, d.qualifier_career) for d in QualifierDefault.objects.all()}
    overrides = {(o.stat_group, o.season): o.qualifier_season for o in QualifierSeasonOverride.objects.all()}
    cache.set(CLAVE_UMBRALES, (defaults, overrides), SEGUNDOS)
    return defaults, overrides


def metric_catalog(group: str) -> dict[str, Metric]:
    """{columna: Metric} de un oficio — le da a cada columna su dirección de ranking y su umbral.

    Cacheado por el mismo motivo que los umbrales: son 203 filas que no cambian entre visitas, y la
    página de un jugador pedía el catálogo una vez por tab.

    Se guardan los OBJETOS `Metric`, no sus ids: quien llama lee `metric.direction`, `metric.kind` y
    `metric.qualifier_*`, así que devolver ids obligaría a una consulta por métrica — cambiar cuatro
    consultas por doscientas.
    """
    guardado: dict[str, Metric] | None = cache.get(f"{CLAVE_METRICAS}:{group}")
    if guardado is not None:
        return guardado
    catalogo = {metric.column: metric for metric in Metric.objects.filter(stat_group=group)}
    cache.set(f"{CLAVE_METRICAS}:{group}", catalogo, SEGUNDOS)
    return catalogo


def _olvidar(**kwargs: object) -> None:
    """Tira las dos cachés. La llaman las señales — ver abajo.

    No mira QUÉ cambió: son cuatro entradas y recalcularlas cuesta cuatro consultas. Filtrar por
    modelo sería más código para ahorrar algo que no duele, y el riesgo de afinar de más acá es
    quedarse con un umbral viejo publicándose como bueno.
    """
    cache.delete(CLAVE_UMBRALES)
    cache.delete_many([f"{CLAVE_METRICAS}:{grupo}" for grupo in ("batting", "pitching", "fielding")])


def conectar_senales() -> None:
    """Engancha el olvido a los tres modelos. La llama `ProfilesConfig.ready()`.

    Sin esto, el dueño cambiaría un umbral en el Backoffice y el sitio seguiría publicando el viejo
    hasta 24 horas, sin nada que lo dijera. Una caché sin invalidación no es una optimización: es un
    fallo con retraso.
    """
    from django.db.models.signals import post_delete, post_save

    for modelo in (Metric, QualifierDefault, QualifierSeasonOverride):
        post_save.connect(_olvidar, sender=modelo, dispatch_uid=f"perfil-olvida-{modelo.__name__}")
        post_delete.connect(_olvidar, sender=modelo, dispatch_uid=f"perfil-borra-{modelo.__name__}")
