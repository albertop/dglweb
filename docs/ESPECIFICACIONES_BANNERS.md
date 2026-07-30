# Especificaciones para banners publicitarios

**dominicanosengrandesligas.com**

Documento para los equipos de diseño de nuestros anunciantes. Reúne todo lo necesario para preparar
una campaña que entre sin ajustes ni reenvíos.

Si una pieza cumple lo que está aquí, se publica el mismo día que se recibe.

---

## Los cuatro formatos

| Formato | Medida | Dónde aparece | Peso máximo |
|---|---|---|---|
| **Banner grande** | 970 × 90 px | Pantallas de escritorio, en todas las páginas | 150 KB |
| **Banner mediano** | 728 × 90 px | Portátiles y tabletas apaisadas | 120 KB |
| **Banner móvil** | 320 × 50 px | Teléfonos | 40 KB |
| **Rascacielos** | 300 × 600 px | Columna lateral, solo escritorio | 200 KB |

**Una campaña completa necesita los cuatro.** No son alternativas entre sí: cada visitante ve el que
corresponde a su pantalla, y si falta uno, esa parte de la audiencia no ve nada.

Los tres banners horizontales son el mismo mensaje en tres proporciones, no tres diseños distintos.
El rascacielos sí es una pieza aparte, por su formato vertical.

---

## Requisitos comunes

### Formato de archivo

| Se acepta | Cuándo usarlo |
|---|---|
| **JPG** | Fotografías e imágenes con degradados |
| **PNG** | Logotipos, texto, colores planos, cualquier pieza con bordes definidos |
| **GIF** | Solo si la pieza está animada |

**PNG para las piezas con texto.** El JPG comprime repartiendo el error alrededor de los contornos, y
en un banner de 90 px de alto eso deja las letras con un halo sucio. Con colores planos, además, el
PNG suele pesar menos.

No se aceptan SVG, WebP, vídeo ni piezas en Flash.

### Dimensiones

**Exactas, en píxeles, sin márgenes añadidos.** Un archivo de 972 × 92 no se recorta ni se ajusta: se
devuelve.

Si quieres nitidez en pantallas de alta densidad, puedes entregar la pieza al doble (por ejemplo
1940 × 180 para el banner grande). **El peso máximo no cambia** — si al duplicar la resolución la
pieza se pasa de límite, es preferible entregarla en tamaño real.

### Peso

Los límites de la tabla son máximos, no objetivos. Cuanto más ligera, antes aparece.

El motivo no es técnico sino de audiencia: buena parte de nuestros lectores entra desde el teléfono
con datos móviles. Un banner que pesa más que la página en la que va se nota, y lo que se nota
primero es el retraso, no el mensaje.

### Animación

Solo en GIF, y con tres condiciones:

- **Máximo 15 segundos** en total.
- **Máximo 3 repeticiones**, y después se detiene. Nada de bucles infinitos.
- **El último fotograma tiene que funcionar solo**: con el logotipo, el mensaje y la llamada a la
  acción legibles. Mucha gente llega a la página cuando la animación ya terminó, y ese fotograma es
  el único anuncio que va a ver.

Sin parpadeos rápidos ni cambios bruscos de contraste.

### Legibilidad

- **Deja al menos 8 px de margen interno.** El texto pegado al borde se lee mal y se corta en algunas
  pantallas.
- **El texto más pequeño, a 14 px o más.** En el banner de 320 × 50 esto obliga a ser breve: tres o
  cuatro palabras y el logotipo.
- **Evita el fondo blanco puro.** El área de contenido del sitio es clara, así que una pieza con fondo
  blanco parece flotar sin límites. Un fondo de color o un borde fino de 1 px la enmarcan.

---

## Cada formato en detalle

### Banner grande — 970 × 90 px

El más visible del sitio. Aparece en pantallas de escritorio, arriba del contenido y al final de la
página, en todas las secciones.

**Qué funciona en este espacio:** es muy ancho y muy bajo, así que la composición natural es
horizontal — logotipo a un lado, mensaje al centro, llamada a la acción al otro extremo. Con 90 px de
alto no caben dos líneas de texto grandes; una sola frase corta rinde mucho mejor que un párrafo.

**Qué evitar:** texto centrado en un bloque, imágenes con detalle fino, y cualquier cosa que dependa
de leerse de arriba abajo.

### Banner mediano — 728 × 90 px

El mismo mensaje que el anterior, en un ancho menor. Aparece en portátiles y tabletas apaisadas.

**No es un recorte del de 970.** Al perder 242 px de ancho, un diseño escalado deja el texto pequeño y
los márgenes descuadrados. Conviene recomponer: normalmente basta con acortar el mensaje o reducir el
espacio entre los elementos.

### Banner móvil — 320 × 50 px

El de mayor alcance real, porque la mayoría de nuestros lectores entra desde el teléfono. También el
más exigente: es una franja pequeña vista a distancia corta y con luz variable.

**Qué funciona:** logotipo + tres o cuatro palabras. Nada más.

**Qué evitar:** reducir el banner de 970 hasta que quepa. El resultado es ilegible y desperdicia el
formato con más audiencia del sitio.

Es el único que aparece **también en dos espacios propios** dentro del contenido, así que tiene aún
más presencia de la que sugiere su tamaño.

### Rascacielos — 300 × 600 px

Columna lateral, solo en pantallas de escritorio. Permanece a la vista mientras el lector baja por la
página, así que es el formato con más tiempo de exposición.

**Qué funciona:** es el único con espacio real para una composición. Admite una imagen de producto
grande, dos o tres líneas de texto y un botón. La lectura es vertical: lo más importante arriba, la
llamada a la acción abajo.

**Qué evitar:** llenarlo. Tener sitio no obliga a usarlo todo, y en 300 px de ancho el texto largo se
vuelve una columna estrecha e incómoda.

---

## Cómo se muestran los anuncios

Conviene conocer tres detalles del montaje, porque afectan a lo que se puede y no se puede hacer.

**Cada anuncio vive en un marco aislado.** No puede leer ni modificar la página que lo contiene, ni
cambiar su propio tamaño, ni detectar en qué artículo está. Una pieza que intente cualquiera de esas
cosas no fallará con un error: simplemente no hará nada.

**El clic abre una pestaña nueva.** Es el comportamiento estándar y no hay que programarlo: basta con
entregar la dirección de destino junto a la pieza. Una creatividad que intente redirigir la ventana
principal por su cuenta será bloqueada.

**Si la pieza carga recursos externos** —tipografías, píxeles de medición, scripts de terceros—,
avísanos al entregarla. Funcionan, pero preferimos saberlo por adelantado.

---

## Qué entregar

Por cada campaña:

1. **Las cuatro piezas**, nombradas así:

   ```
   anunciante_campaña_970x90.jpg
   anunciante_campaña_728x90.jpg
   anunciante_campaña_320x50.png
   anunciante_campaña_300x600.jpg
   ```

2. **La dirección de destino** (URL completa, con `https://`). Si es distinta por pieza, indícalo.

3. **Las fechas** de inicio y fin de la campaña.

4. **Un contacto** para dudas sobre la creatividad.

Todo junto, en un solo envío. El límite por archivo es de 20 MB, muy por encima de lo que necesita
cualquier pieza que cumpla los pesos de arriba.

---

## Lista de verificación

Antes de enviar:

- [ ] Las cuatro medidas, exactas al píxel
- [ ] Cada archivo por debajo de su peso máximo
- [ ] PNG en las piezas con texto o colores planos
- [ ] Si hay animación: máximo 15 s, máximo 3 repeticiones, y el último fotograma se entiende solo
- [ ] Texto a 14 px o más, con 8 px de margen interno
- [ ] La pieza no se confunde con el fondo claro del sitio
- [ ] Dirección de destino incluida y comprobada
- [ ] Fechas de campaña indicadas

---

*Ante cualquier duda sobre estas especificaciones, escríbenos antes de producir las piezas. Resolver
una consulta cuesta cinco minutos; rehacer una campaña completa, bastante más.*
