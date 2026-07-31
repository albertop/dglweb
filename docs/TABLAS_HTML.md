# Tablas pegadas en un artículo — formato

Cómo tiene que venir el HTML de una tabla para que el bloque **«Tabla (HTML)»** del CMS la acepte
entera. Está escrito para dos lectores: el que escribe el artículo y **el modelo de lenguaje al que se
le pide que genere la tabla** — la última sección es un bloque para copiar tal cual dentro del prompt.

El filtro vive en `dglweb/articles/tablas.py` y las pruebas en `tests/test_tablas_html.py`. Si algo de
acá deja de ser cierto, esos dos archivos mandan.

---

## El contrato, en una frase

**Se pega HTML; sobrevive la estructura y se descarta la presentación.**

No hay que preparar nada: se puede pegar el archivo entero tal como sale de `gt` de R, con su hoja de
estilos incrustada. Medido con una salida real de 216.521 bytes, quedaron 36.468 —el 84% descartado—
sin perder una sola celda, y con los 23 `colspan` del encabezado de dos niveles intactos.

Lo que se descarta es el estilo ajeno, porque **el aspecto lo pone el sitio**: la tabla del artículo
se pinta igual que la de la ficha del jugador. Una tabla con su propia tipografía y sus propios
colores se leería como un cuerpo extraño en mitad del texto.

---

## El esqueleto

```html
<table>
  <caption>…</caption>          <!-- opcional; sale DEBAJO, en gris y pequeño -->
  <colgroup>…</colgroup>        <!-- opcional; controla la alineación. Ver abajo -->
  <thead>…</thead>              <!-- las filas de títulos -->
  <tbody>…</tbody>              <!-- los datos -->
  <tfoot>…</tfoot>              <!-- opcional; notas al pie y fuente -->
</table>
```

Reglas que no son opcionales:

* **Una sola tabla.** Si el HTML trae varias, se queda con la **primera** y el resto se pierde sin
  aviso. Dos tablas son dos bloques.
* **Los títulos van en `<th>`, no en `<td>`.** Es lo que permite que un lector de pantalla diga
  «Cap Anson, WAR, 14.9» en vez de leer números sueltos, y es también lo que les da el fondo azul.
* **`scope` en cada `<th>`.** `scope="col"` si titula una columna, `scope="row"` si es la etiqueta de
  una fila, `scope="colgroup"` si abarca varias columnas.
* **Los números, tal como se van a leer.** El filtro no formatea: no redondea, no pone separador de
  miles y no traduce el punto decimal. Lo que se escribe es lo que sale.

---

## Alineación

Por defecto el sitio alinea **todo a la derecha** —son cifras— y deja **la primera columna a la
izquierda**. Eso vale para la tabla de una ficha, donde la primera columna es el año y el resto
números; casi nunca vale para una tabla pegada, donde puede haber nombres en la 2 y en la 5.

### Se declara una vez por columna, en `<colgroup>`

```html
<colgroup>
  <col class="izq">
  <col class="izq"><col class="centro"><col class="der">
  <col class="izq"><col class="centro"><col class="der">
</colgroup>
```

Tres valores y ningún otro: **`izq`**, **`centro`**, **`der`**.

**`<colgroup>` es una lista plana de las columnas REALES, de izquierda a derecha.** No sabe nada del
encabezado: no le importa que haya dos filas de títulos ni que uno abarque tres columnas. Si la tabla
tiene siete columnas, van siete `<col>`, en orden.

Los saltos de línea del ejemplo no significan nada — los siete podrían ir seguidos. Están puestos así
para que visualmente cuadren con los tres grupos del encabezado.

Con `span` se acortan las columnas seguidas que comparten alineación:

```html
<col span="3" class="der">     <!-- equivale a tres <col class="der"> -->
```

Una columna sin `<col>` se queda con el comportamiento por defecto.

### La excepción: una celda concreta

La clase puesta en la celda **manda sobre la de su columna**:

```html
<td class="centro">24-28</td>
```

### La celda que abarca varias columnas hay que decirla

Una celda con `colspan` **no hereda** alineación, porque no tiene una sola columna de la que
heredarla. *Best Hitters* cubre `izq`, `centro` y `der` a la vez: no hay una respuesta. Así que ahí se
pone a mano, y en la práctica casi siempre es `centro`:

```html
<th scope="colgroup" colspan="3" class="centro">Best Hitters</th>
```

### Por qué el orden de los `<col>` es por columnas reales

Porque la posición de una celda **no es su orden dentro de la fila**. En este encabezado:

```
columna:          1          2        3       4        5        6       7
<col class=>     izq        izq    centro    der      izq    centro    der

thead fila 1   Seasons    ├──── Best Hitters ────┤  ├──── Worst Hitters ───┤
                (rowspan=2)        (colspan=3)             (colspan=3)

thead fila 2      ·         Name     Age     WAR     Name     Age     WAR

tbody          1876-1880  Cap Anson  24-28   14.9  Jack Burdock 24-28   6.6
```

La **segunda fila del encabezado tiene 6 celdas, no 7**: *Seasons* lleva `rowspan="2"` y ya ocupa la
columna 1 en las dos filas. El filtro lleva la cuenta de la rejilla de verdad —qué columnas quedaron
reservadas por un `rowspan` de arriba, cuántas casillas ocupa cada `colspan`— así que se puede confiar
en que `<col>` número *n* le toca a la columna *n* pase lo que pase arriba.

### Por qué la clase acaba en cada celda

CSS **no puede alinear texto desde un `<col>`**: un `<col>` solo propaga ancho, fondo, borde y
visibilidad. Por eso `<colgroup>` tiene fama de no servir para nada. El filtro lee la declaración y
**copia la clase a cada celda de esa columna** antes de guardar. Se escribe 7 veces y quedan escritas
140.

---

## Lista blanca

Lo que no está acá **no entra**. Se enumera lo que pasa y no lo que se prohíbe: una lista de
prohibiciones hay que acertarla entera y para siempre.

### Etiquetas

| | |
|---|---|
| **estructura** | `table` `caption` `colgroup` `col` `thead` `tbody` `tfoot` `tr` `th` `td` |
| **dentro de una celda** | `a` `b` `strong` `i` `em` `small` `sup` `sub` `br` `code` `abbr` |

### Atributos, por etiqueta

| etiqueta | atributos |
|---|---|
| `th` | `colspan` `rowspan` `scope` `abbr` `class` |
| `td` | `colspan` `rowspan` `class` |
| `col` | `span` `class` |
| `colgroup` | `span` |
| `a` | `href` |
| el resto | ninguno |

* **`class`** solo acepta `izq`, `centro` o `der`. `class="gt_row gt_center bg-danger"` entra y no
  sale nada: no es una rendija por donde colar Bootstrap.
* **`href`** tiene que empezar por `/` (una página del sitio), `https://` o `#` (un ancla). Con
  cualquier otra cosa se pierde la etiqueta `<a>` entera y queda solo el texto — un enlace sin destino
  es texto subrayado que engaña.

---

## Lo que se descarta

| qué | qué le pasa |
|---|---|
| `script` `style` `template` `iframe` `object` `embed` `noscript` `form` `input` | **se borran con su contenido dentro** |
| cualquier otra etiqueta (`div`, `span`, `p`, `img`, `font`…) | se quita la etiqueta y **se conserva su texto** |
| `style=` `id=` `width=` `bgcolor=` `align=` y cualquier `on…=` | se caen |
| comentarios `<!-- … -->` | se borran |
| el espacio **entre** etiquetas de estructura | se descarta (dentro de una celda no se toca) |

Consecuencia práctica: **no se pueden meter imágenes en una celda.** `<img>` se va y no deja nada.

---

## Cuándo falla

El bloque no deja guardar la página y explica por qué:

* **«No se encontró ninguna `<table>` en lo que pegaste»** — el HTML no trae tabla. Ojo: si trae
  `<tr>` sueltas sin `<table>` alrededor, se envuelven solas y no falla.
* **«La tabla no tiene ninguna fila»** — hay `<table>` pero ni un `<tr>`.

---

## Cómo se ve

* Tipografía monoespaciada, cuerpo pequeño, cifras de ancho fijo.
* Encabezados con **fondo azul marino y texto blanco**.
* Filas alternas en gris muy claro.
* La primera columna de `<tbody>`, si va en `<th scope="row">`, sale **sin** el azul: en negrita y a la
  izquierda, para que no compita con la fila de títulos.
* **El `<caption>` sale DEBAJO de la tabla**, en gris y pequeño. Sirve como pie o como fuente, no como
  titular. Un título de verdad va como bloque «Subtítulo» encima de la tabla.
* En pantalla estrecha la tabla se desplaza sola a lo ancho sin empujar la página.

---

## Ejemplo completo

```html
<table>
  <caption>Fuente: MLB · Cálculo propio</caption>
  <colgroup>
    <col class="izq">
    <col class="izq"><col class="centro"><col class="der">
    <col class="izq"><col class="centro"><col class="der">
  </colgroup>
  <thead>
    <tr>
      <th scope="col" rowspan="2">Seasons</th>
      <th scope="colgroup" colspan="3" class="centro">Best Hitters</th>
      <th scope="colgroup" colspan="3" class="centro">Worst Hitters<sup>1</sup></th>
    </tr>
    <tr>
      <th scope="col">Name</th><th scope="col">Age</th><th scope="col">WAR</th>
      <th scope="col">Name</th><th scope="col">Age</th><th scope="col">WAR</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">1876-1880</th>
      <td>Cap Anson</td><td>24-28</td><td>14.9</td>
      <td>Jack Burdock</td><td>24-28</td><td>6.6</td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td colspan="7"><sup>1</sup> Solo bateadores con al menos 1500 PA en 5 temporadas seguidas.</td>
    </tr>
  </tfoot>
</table>
```

---

## Para el prompt del modelo

Copiar de acá abajo tal cual, y añadir después los datos y qué columnas se quieren.

> Genera una tabla en HTML puro, sin CSS, sin `<style>`, sin `class` que no sean de alineación y sin
> atributos de presentación (`width`, `bgcolor`, `align`, `style`). Devuelve **solo** el `<table>`, sin
> `<html>` ni `<body>` ni explicación alrededor.
>
> Reglas:
>
> 1. Una sola `<table>`. Estructura: `<caption>` opcional, `<colgroup>`, `<thead>`, `<tbody>`,
>    `<tfoot>` opcional.
> 2. Los títulos van en `<th>` con `scope`: `col` si titula una columna, `row` si es la etiqueta de la
>    fila, `colgroup` si abarca varias columnas con `colspan`.
> 3. La primera columna de cada fila de datos va en `<th scope="row">` si es una etiqueta (año, rango,
>    nombre de equipo); si es un número, en `<td>`.
> 4. **Alineación**: incluye un `<colgroup>` con un `<col>` por cada columna real de la tabla, de
>    izquierda a derecha, con `class="izq"`, `class="centro"` o `class="der"`. Solo esos tres valores.
>    Texto → `izq`. Números → `der`. Códigos y rangos cortos (`24-28`, `SS`, `BOS`) → `centro`.
> 5. El número de `<col>` tiene que ser igual al número de columnas reales, contando las que ocupa
>    cada `colspan`. No cuentes celdas del encabezado: cuenta columnas.
> 6. Una celda con `colspan` no hereda alineación, así que ponle tú `class="centro"` si la quieres
>    centrada.
> 7. Las notas al pie: marcador `<sup>1</sup>` en el encabezado y el texto en una fila de `<tfoot>`
>    con un `<td colspan="N">` que cubra toda la tabla.
> 8. Etiquetas permitidas dentro de una celda: `a` (solo con `href` que empiece por `/`, `https://` o
>    `#`), `b`, `strong`, `i`, `em`, `small`, `sup`, `sub`, `br`, `code`, `abbr`. Nada de `div`,
>    `span`, `p` ni `img`.
> 9. No formatees los números de ninguna manera especial: escríbelos como se van a leer.

---

## Límites conocidos

* **Una tabla por bloque.** La segunda `<table>` de un mismo pegado se pierde sin aviso.
* **Sin imágenes** dentro de las celdas.
* **Sin ordenar ni buscar.** Es una tabla estática; el navegador no la reordena.
* **Sin plegado ni columna fija.** Una tabla de muchas filas o muchas columnas sale entera y se
  desplaza a lo ancho. Si hace falta acortarla, se acorta en el origen.
* **El `<caption>` va abajo.** Para un titular encima, usar el bloque «Subtítulo».
