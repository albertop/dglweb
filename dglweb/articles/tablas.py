"""El filtro que deja entrar una tabla pegada desde fuera, y nada más.

POR QUÉ HTML Y NO UNA CUADRÍCULA
--------------------------------
El bloque `tabla` de Wagtail es una cuadrícula tipo Excel y sirve para lo que sirve: cuatro filas por
cinco columnas. Se queda corto en cuanto la tabla viene de un script.

Medido contra una salida de `gt` de R —144 filas de datos por 13 columnas—: son 1.872 celdas, y sobre
todo **la cuadrícula no sabe de encabezados de dos niveles**. «Best Hitters» abarcando Name/Age/WAR no
se puede expresar ahí, y sin eso la tabla pierde justo lo que la hace legible. Tampoco tiene notas al
pie, que en una tabla con metodología —«solo bateadores con 1500 PA»— no son adorno: sin ellas la
tabla afirma algo que no es.

El HTML ya dice todo eso de forma nativa: `colspan`, `rowspan`, `scope`, `<caption>`, `<tfoot>`. No
hay nada que inventar; solo hay que dejarlo pasar sin dejar pasar lo demás.

QUÉ SOBREVIVE, MEDIDO
---------------------
Sobre ese mismo archivo de `gt`, que son 216.521 bytes de HTML con toda su hoja de estilos incrustada:

    entrada                216.521 bytes
    salida                  36.468 bytes   — 84% descartado
    filas 152 · celdas 1.734               — el contenido, intacto
    colspan 23 · rowspan 17 · scope 161    — los dos niveles de encabezado
    style / class / id / script  0

O sea que **se pega el archivo entero tal como sale de R** y no hay que preparar nada. Lo que se tira
es presentación ajena: la tabla se pinta con `.dgl-stats-table`, la misma de la ficha del jugador, y
así el artículo no tiene dos estilos de tabla.

LA LISTA ES BLANCA, NO NEGRA
----------------------------
Se enumera lo que entra, no lo que se prohíbe. Una lista negra hay que acertarla entera y para
siempre; una blanca falla del lado seguro cuando aparece algo que no estaba previsto.

`script`, `style` y compañía se DESTRUYEN con su contenido —`decompose`— y no se desenvuelven. La
diferencia importa: `unwrap` quita la etiqueta y **conserva el texto**, así que un `<script>` acabaría
volcando su código como texto visible en mitad de la tabla. Inofensivo, pero absurdo.
"""

from bs4 import BeautifulSoup, Comment, Tag

# Lo que puede quedar dentro de la tabla. `div` y `span` NO están: se desenvuelven y su texto sigue
# ahí, que es lo que se quiere — `gt` envuelve cada encabezado en dos `<span>` que no aportan nada.
ETIQUETAS = frozenset(
    {
        "caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "th", "td",
        "a", "b", "strong", "i", "em", "small", "sup", "sub", "br", "code", "abbr",
    }
)  # fmt: skip

# Por etiqueta, porque `colspan` en un `<a>` no significa nada y `href` en un `<td>` tampoco. Todo lo
# que no esté acá se cae: `style`, `id`, `width`, `bgcolor` y cualquier `on…`.
#
# `class` entra solo donde sirve para alinear, y aun así no pasa cualquier valor: ver `ALINEACIONES`.
ATRIBUTOS = {
    "th": {"colspan", "rowspan", "scope", "abbr", "class"},
    "td": {"colspan", "rowspan", "class"},
    "col": {"span", "class"},
    "colgroup": {"span"},
    "a": {"href"},
}

# LA ALINEACIÓN SE DECLARA UNA VEZ POR COLUMNA, EN `<colgroup>`
# -------------------------------------------------------------
# `.dgl-stats-table` alinea a la derecha —son cifras— y deja la primera columna a la izquierda. Eso
# vale para la tabla de una ficha, donde la primera columna es el año y el resto números. En una tabla
# pegada las columnas son las que sean: nombres en la 2 y en la 5, cifras en la 4 y en la 7.
#
# Así que se declara así, y una sola vez:
#
#     <colgroup>
#       <col class="izq"><col class="izq"><col class="centro"><col class="der">
#     </colgroup>
#
# `<colgroup>` es la etiqueta que existe justo para hablar de columnas, así que no hay nada que
# inventar. Lo que sí hay que hacer es BAJAR esa clase a cada celda: CSS no puede alinear texto desde
# un `<col>` —`text-align` no está entre las poquísimas propiedades que un `<col>` propaga— y esa es
# la razón de que la etiqueta parezca no servir para nada. Acá sirve.
#
# También se aceptan sueltas en un `th` o un `td` para la excepción de una celda. Y el vocabulario es
# CERRADO: cualquier otro valor de `class` se cae, así que esto no es una rendija por donde entren las
# clases de Bootstrap ni las de `gt`.
ALINEACIONES = frozenset({"izq", "centro", "der"})

# Con su contenido dentro. Ver la cabecera del módulo.
DESTRUIR = ("script", "style", "template", "iframe", "object", "embed", "noscript", "form", "input")

# Un enlace puede ser al propio sitio o a algo público por TLS. `javascript:` y `data:` son las dos
# formas clásicas de meter código donde solo se esperaba una dirección.
ESQUEMAS = ("/", "https://", "#")

# Dónde el espacio entre etiquetas no se pinta y por tanto se puede tirar. DENTRO de un `<td>` no se
# toca: ahí el espacio separa palabras.
#
# Se tira para que la salida sea CANÓNICA. Al quitar un comentario queda el espacio que lo rodeaba, y
# la siguiente pasada lo normaliza de otra forma — o sea que guardar dos veces daba dos textos
# distintos y la ida y vuelta dejaba de ser exacta. Medido con el `<colgroup>` comentado del archivo de
# prueba: 5.508 bytes la primera pasada y 5.505 la segunda, por tres espacios.
ESTRUCTURALES = frozenset({"table", "colgroup", "thead", "tbody", "tfoot", "tr"})


class SinTablaError(ValueError):
    """Lo pegado no tiene una tabla que valga. Lo atrapa el bloque para enseñárselo al editor."""


def _entero(valor: object, *, por_defecto: int = 1) -> int:
    """Un `colspan="tres"` no puede tumbar el artículo. Lo pegado viene de fuera."""
    try:
        return max(1, int(str(valor)))
    except (TypeError, ValueError):
        return por_defecto


def _alineacion_de(nodo: Tag) -> str:
    """La única clase de alineación que lleve el nodo, o cadena vacía.

    `class` es un atributo de varios valores, así que `bs4` lo devuelve como lista —salvo cuando el
    parser no lo sabe y devuelve la cadena cruda—. Se normalizan los dos casos y se descarta todo lo
    que no esté en el vocabulario: `gt_row gt_center` entra y no sale nada.
    """
    crudo = nodo.get("class")
    valores = [crudo] if isinstance(crudo, str) else list(crudo or [])
    return next((str(v) for v in valores if str(v) in ALINEACIONES), "")


def _bajar_alineacion(tabla: Tag) -> None:
    """Copia la clase de cada `<col>` a las celdas de esa columna. Ver `ALINEACIONES`.

    HAY QUE CONTAR LA REJILLA DE VERDAD, y no ir sumando uno por celda. Con encabezados de dos niveles
    —que son la razón de existir de este bloque— la posición de una celda NO es su orden dentro de la
    fila: un `colspan="3"` ocupa tres columnas, y un `rowspan="2"` de la fila de arriba deja un hueco
    reservado en la de abajo. Contando ingenuamente, la segunda fila del encabezado de la tabla de
    prueba salía corrida una columna y la alineación se aplicaba a la vecina.

    `pendientes` lleva, por columna, cuántas filas le quedan ocupadas por un `rowspan` anterior. Es el
    algoritmo de la rejilla de HTML reducido a lo que hace falta acá.

    A la celda que abarca varias columnas no se le pone nada: una columna es la que puede decir cómo
    se alinea, y un encabezado que cubre tres no tiene una sola respuesta.
    """
    por_columna: dict[int, str] = {}
    columna = 0
    for col in tabla.select("col"):
        ancho = _entero(col.get("span"))
        if clase := _alineacion_de(col):
            for desplazamiento in range(ancho):
                por_columna[columna + desplazamiento] = clase
        columna += ancho

    if not por_columna:
        return

    pendientes: dict[int, int] = {}
    for fila in tabla.select("tr"):
        columna = 0
        for celda in fila.find_all(["th", "td"], recursive=False):
            while pendientes.get(columna, 0) > 0:
                columna += 1
            ancho, alto = _entero(celda.get("colspan")), _entero(celda.get("rowspan"))
            # La clase puesta a mano en la celda manda sobre la de la columna: es la excepción, y una
            # excepción que la regla pisara no serviría de nada.
            if ancho == 1 and "class" not in celda.attrs and columna in por_columna:
                celda["class"] = por_columna[columna]
            if alto > 1:
                for ocupada in range(columna, columna + ancho):
                    pendientes[ocupada] = alto
            columna += ancho
        # Al cerrar la fila: lo reservado por un `rowspan` cuenta una fila menos. Se descuenta acá y
        # no al empezar la siguiente para que la fila que lo declaró también consuma su turno.
        for ocupada in list(pendientes):
            pendientes[ocupada] -= 1
            if pendientes[ocupada] <= 0:
                del pendientes[ocupada]


def limpiar(html: str, *, clases: str = "") -> str:
    """La primera `<table>` que aparezca, ENTERA, sin nada que no esté en la lista blanca.

    DEVUELVE LA TABLA COMPLETA Y NO SU INTERIOR, y eso es una corrección. La primera versión devolvía
    `decode_contents()` —sin el `<table>`— para que el elemento y sus clases los escribiera la
    plantilla. Suena más limpio y estaba roto: lo que `clean` guarda es lo que devuelve esta función,
    así que en la base quedaba un valor SIN `<table>`… que esta misma función ya no sabía leer.

    Los tres síntomas salían de ahí: al guardar desaparecía el `<table>`, al pintar no se veía nada
    —no encontraba tabla y devolvía vacío— y al volver a editar la página no se dejaba guardar. La
    regla que faltaba es que **la salida tiene que poder volver a entrar**; hay una prueba de ida y
    vuelta para que no se pierda otra vez.

    `clases` es lo único que se le pone al elemento, y lo decide quien llama. Así el módulo sigue sin
    saber de Bootstrap ni de `.dgl-stats-table`: al guardar se llama sin nada —el valor almacenado es
    estructura pura— y al pintar se le pasan las del sitio. Como el atributo `class` no está en la
    lista blanca, se descarta y se vuelve a poner en cada pasada, que es lo que la hace idempotente.

    Levanta `SinTablaError` si no hay tabla o si está vacía. Callar y devolver cadena vacía dejaría un
    hueco en el artículo sin que nadie supiera por qué.
    """
    sopa = BeautifulSoup(html or "", "html.parser")

    # Filas sueltas, sin tabla que las envuelva. Pasa al copiar de una hoja de cálculo y al pegar un
    # trozo, y no hay motivo para rechazarlo cuando se sabe exactamente qué falta. Se envuelve ANTES
    # de filtrar, así que lo pegado pasa por la lista blanca igual que si hubiera venido completo.
    if sopa.find("table") is None and sopa.find("tr") is not None:
        sopa = BeautifulSoup(f"<table>{html}</table>", "html.parser")

    # ANTES de buscar la tabla: un `<script>` dentro de una celda tiene que morir aunque la tabla que
    # lo contiene sea la buena.
    for etiqueta in sopa.find_all(DESTRUIR):
        etiqueta.decompose()
    # Los comentarios no los devuelve `find_all(True)` —no son etiquetas— y sobrevivirían al `str()`.
    for comentario in sopa.find_all(string=lambda t: isinstance(t, Comment)):
        comentario.extract()

    tabla = sopa.find("table")
    if tabla is None:
        raise SinTablaError("No se encontró ninguna <table> en lo que pegaste.")

    for nodo in tabla.find_all(True):
        if nodo.name not in ETIQUETAS:
            # Se queda el texto y se va la etiqueta: los `<span>` y `<div>` de envoltorio desaparecen
            # sin llevarse el dato.
            nodo.unwrap()
            continue
        nodo.attrs = {
            nombre: valor for nombre, valor in nodo.attrs.items() if nombre in ATRIBUTOS.get(nodo.name, set())
        }
        # El vocabulario de `class` es cerrado. `bs4` devuelve una lista porque `class` es un atributo
        # de varios valores, así que basta con quedarse con los que están en la lista y borrar el
        # atributo si no queda ninguno: `gt_row gt_center` entra y sale sin dejar nada.
        if "class" in nodo.attrs:
            alineacion = _alineacion_de(nodo)
            if alineacion:
                nodo["class"] = alineacion
            else:
                del nodo["class"]
        # El enlace con destino raro pierde la etiqueta, no solo el atributo: un `<a>` sin `href` es
        # texto subrayado que no lleva a ninguna parte, y eso confunde más que no tener enlace.
        if nodo.name == "a" and not str(nodo.attrs.get("href", "")).startswith(ESQUEMAS):
            nodo.unwrap()

    if not tabla.find("tr"):
        raise SinTablaError("La tabla no tiene ninguna fila.")

    # Ver `ESTRUCTURALES`. Va antes de bajar la alineación porque esa recorre celdas, no texto.
    for texto in tabla.find_all(string=True):
        if not texto.strip() and texto.parent is not None and texto.parent.name in ESTRUCTURALES:
            texto.extract()

    _bajar_alineacion(tabla)

    # Aparte del bucle porque `find_all` recorre los DESCENDIENTES y no el propio elemento: sin esta
    # línea, el `class="gt_table"` y el `data-quarto-…` del original se colarían. La asignación
    # reemplaza el diccionario entero, así que con `clases` vacío no queda ningún atributo.
    tabla.attrs = {"class": clases} if clases else {}
    return str(tabla)
