"""Los rangos de pantalla de los huecos que solo existen en algunas — y que no dejen ni hueco ni solape.

QUÉ SE PROTEGE, Y POR QUÉ NO SE VE MIRANDO LA PANTALLA
------------------------------------------------------
Hay huecos que solo existen en un rango: el carril de 300x600 desde escritorio, y un banner de 320x50
solo en móvil. El rango se declara DOS VECES y en dos lenguajes distintos:

* en el CSS, con las clases de Bootstrap (`d-lg-none`, `d-none d-xl-flex`), para que no haya salto de
  maquetación mientras el script decide;
* en la etiqueta (`minimo=` / `maximo=`), que es lo que respeta `anuncios.js` al poner el `src`.

Si los dos números no coinciden pasa una de estas dos cosas, y **ninguna se nota mirando el sitio**:

  El CSS esconde y la etiqueta permite  ->  IMPRESIÓN FANTASMA. Un `iframe` oculto con CSS SÍ CARGA
                                            su documento (comprobado en el navegador), así que Revive
                                            le cobra al anunciante un anuncio que nadie vio.

  El CSS enseña y la etiqueta prohíbe    ->  FRANJA SIN ANUNCIO. El script quita el marco por estar
                                            fuera de rango y ese ancho de pantalla se queda sin nada.

Los dos son de dinero, y los dos son invisibles: la única forma de cazarlos es comparar los números.

Pasó de verdad al montar líderes: la etiqueta decía 992 y `.dgl-col-torre` empieza en 1200, así que
entre 992 y 1199 la torre se cargaba escondida.
"""

from __future__ import annotations

import pathlib
import re

import pytest

PLANTILLAS = pathlib.Path(__file__).resolve().parent.parent / "templates"

# Los cortes de Bootstrap, que son los que usan las clases `d-*`.
CORTES = {"sm": 576, "md": 768, "lg": 992, "xl": 1200, "xxl": 1400}

# Cada pareja de huecos complementarios: el de móvil y el de escritorio de la misma página.
PAREJAS = [
    ("home.html", "portada"),
    ("profiles/leaders.html", "líderes"),
]


def _rangos(texto: str) -> list[dict[str, int]]:
    """Los `anuncio_rango` de una plantilla, con su mínimo y su máximo."""
    salida = []
    for m in re.finditer(r"\{% anuncio_rango (\d+) (\d+) (\d+)([^%]*)%\}", texto):
        resto = m.group(4)
        minimo = re.search(r"minimo=(\d+)", resto)
        maximo = re.search(r"maximo=(\d+)", resto)
        salida.append(
            {
                "zona": int(m.group(1)),
                "ancho": int(m.group(2)),
                "min": int(minimo.group(1)) if minimo else 0,
                "max": int(maximo.group(1)) if maximo else 0,
            }
        )
    return salida


@pytest.mark.parametrize(("archivo", "pagina"), PAREJAS)
def test_los_dos_rangos_de_la_pagina_son_complementarios(archivo: str, pagina: str) -> None:
    """Sin hueco y sin solape: donde acaba uno empieza el otro, al píxel."""
    rangos = _rangos((PLANTILLAS / archivo).read_text(encoding="utf-8"))
    assert len(rangos) == 2, f"{pagina}: se esperaban dos huecos con rango, hay {len(rangos)}"

    movil = next(r for r in rangos if r["max"])
    escritorio = next(r for r in rangos if r["min"] and not r["max"])

    assert movil["max"] + 1 == escritorio["min"], (
        f"{pagina}: el hueco de móvil llega a {movil['max']} y el de escritorio empieza en "
        f"{escritorio['min']}. Si hay salto, esa franja de pantallas se queda sin anuncio; si hay "
        f"solape, se cuentan dos impresiones por visita."
    )


@pytest.mark.parametrize(("archivo", "pagina"), PAREJAS)
def test_el_rango_coincide_con_la_clase_de_bootstrap(archivo: str, pagina: str) -> None:
    """LA PRUEBA QUE CAZA EL FALLO REAL: que el número de la etiqueta sea el del CSS.

    Se busca el `d-{corte}-none` que esconde el hueco de móvil y se exige que su corte sea el mínimo
    que declara el de escritorio. En líderes eso estuvo mal: la etiqueta decía 992 y la clase era
    `d-xl-*`, o sea 1200.
    """
    texto = (PLANTILLAS / archivo).read_text(encoding="utf-8")
    rangos = _rangos(texto)
    escritorio = next(r for r in rangos if r["min"] and not r["max"])

    # `d-lg-none` / `d-xl-none`: la clase que esconde el hueco de móvil a partir de ese corte.
    cortes_usados = {CORTES[c] for c in re.findall(r"\bd-(lg|xl|md|sm|xxl)-none\b", texto)}
    assert escritorio["min"] in cortes_usados, (
        f"{pagina}: la etiqueta declara minimo={escritorio['min']} pero las clases de Bootstrap de la "
        f"plantilla cortan en {sorted(cortes_usados)}. Los dos números tienen que ser el mismo, o hay "
        f"una franja de pantallas con impresion fantasma o sin anuncio."
    )
