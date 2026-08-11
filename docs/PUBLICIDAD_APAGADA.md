# Encender y apagar la publicidad

Cómo esconder los espacios publicitarios del sitio **sin perder la integración con Revive**, y cómo
devolverla. El montaje del servidor de anuncios está en `ADSERVER.md`; esto es solo el interruptor.

Decidido y construido el **2026-08-10**, a petición del dueño: el sitio ya estaba integrado con Revive
pero los primeros anunciantes iban a tardar, y mientras tanto la página enseñaba espacios en blanco.

---

## Lo único que hay que saber

```
ANUNCIOS_VISIBLES=false     esconde toda la publicidad
ANUNCIOS_VISIBLES=true      la devuelve entera        (por defecto)
```

Es una variable de entorno. Nada más. No hay HTML que tocar, ni zonas que borrar, ni nada que volver a
configurar cuando se encienda.

### En producción

En Portainer → **Stacks → dglweb → Editor**, en las variables de entorno del stack:

```yaml
ANUNCIOS_VISIBLES: "false"
```

**Update the stack** y listo. No hace falta reconstruir la imagen ni migrar nada.

### En desarrollo

```bash
echo "ANUNCIOS_VISIBLES=false" >> .env
```

```bash
docker compose up -d web
```

Para una prueba rápida sin tocar el `.env`, la variable delante del comando basta:

```bash
ANUNCIOS_VISIBLES=false docker compose up -d web
```

---

## Qué desaparece, exactamente

**Los dieciséis huecos publicitarios** de las seis páginas que los llevan — portada, índice de
artículos, artículo, índice de jugadores, perfil y líderes. Ni el `<iframe>`, ni el recuadro rayado de
maqueta, ni un `<div>` vacío: no queda nada en el HTML.

**El bloque «Publicidad» de `/contacto/`**, el que dice a quién escribir para comprar espacios.
Ofrecerlos en una página donde no se ve ni un anuncio son dos mensajes que se contradicen.

**El crédito de Adcio Media en el pie**, en todas las páginas. Es la agencia de publicidad del sitio,
así que con la publicidad escondida su crédito sería la única pista de que hay un negocio montado.
La columna del pie se queda —debajo vive «Síguenos», que no tiene nada que ver.

**Y la portada se recompone**, que es la parte que costó pensar. Al desaparecer el carril de 300×600:

| | con publicidad | sin publicidad |
| --- | --- | --- |
| artículos por fila | 2 (`col-md-6`) | **3** (`col-lg-4`) |
| tarjetas visibles en escritorio | 3 | **6** |
| carril lateral | 300px + gutter | — |

Las tres tarjetas de más no se inventan: son las `articulos_de_mas` que la vista ya mandaba y que en
escritorio estaban escondidas **precisamente porque estirarían la fila que sostenía el anuncio de
600px de alto**. Sin ese anuncio la restricción no existe, y el hueco se llena con artículos de verdad
en vez de con aire.

---

## Qué NO desaparece, y por qué importa

La instrucción del dueño fue, en mayúsculas y dos veces: **no perder la integración con Revive**. Así
que apagar no borra nada.

- **Los dieciséis `{% anuncio_horizontal %}` y `{% anuncio_rango %}` siguen escritos** en las
  plantillas, con su zona. Hay una prueba que los cuenta (`test_los_tags_siguen_escritos_en_las_plantillas`)
  y que falla si alguien decide «limpiar» el HTML que hoy no dibuja nada.
- **`ADSERVER_URL` sigue apuntando a Revive**, así que la CSP lo sigue permitiendo en `frame-src` y
  `/health/adserver` lo sigue vigilando.
- **El servidor de Revive sigue corriendo** con sus zonas y sus campañas. Esto no lo toca.

---

## El error que hay que NO cometer

**No se apaga vaciando `ADSERVER_URL`.** Es lo primero que uno piensa —«si no hay servidor, no hay
anuncios»— y rompe tres cosas a la vez:

1. **`/health/adserver` responde 503 en producción** sin esa URL. Despertarías al monitor externo por
   una decisión editorial, y el aviso diría que el servidor de anuncios está caído cuando está
   perfectamente.
2. **La CSP deja de permitir el origen de Revive**, y se calcula **una sola vez al arrancar el
   proceso**. Volver a encenderlo exigiría reiniciar el contenedor — y hasta entonces los anuncios se
   bloquearían en silencio, que es el peor de los fallos posibles: todo parece bien y no carga nada.
3. **Los huecos dibujarían el recuadro de maqueta** que dice «Espacio publicitario», o sea que
   cambiarías un hueco en blanco por un cartel anunciando que falta algo.

Por eso son dos ajustes y no uno:

| ajuste | qué contesta |
| --- | --- |
| `ADSERVER_URL` | ¿dónde está Revive? |
| `ANUNCIOS_VISIBLES` | ¿enseñamos publicidad hoy? |

---

## Por qué no se esconde con CSS

Un `display: none` habría sido una línea. **Y habría facturado aire.**

Un `<iframe>` escondido con CSS **sigue pidiendo su documento**: está medido en este proyecto, y está
escrito en el docstring de `anuncio_horizontal`. La primera versión del hueco adaptable dibujaba los
tres tamaños y ocultaba dos, dando por hecho que un marco oculto no carga — los tres pidieron su
anuncio, con `loading="lazy"` puesto y todo.

Escondiendo con CSS, Revive contaría una impresión por cada hueco que nadie vio. En venta directa eso
no es un defecto técnico: es un informe mentiroso para el anunciante.

Lo que no se dibuja no se pide. Por eso el apagado ocurre **en el tag**, antes de que exista el HTML.

---

## Dónde vive cada pieza

| pieza | archivo |
| --- | --- |
| el ajuste | `config/settings/base.py` — `ANUNCIOS_VISIBLES` |
| la puerta | `dglweb/core/templatetags/anuncios.py` — `_apagado()`, en los tres tags |
| las plantillas de marco | `templates/widgets/_anuncio.html`, `_anuncio_horizontal.html` |
| la bandera para el layout | `dglweb/core/context_processors.py` — `anuncios` |
| la rejilla de la portada | `templates/home.html` + `.sin-anuncios` en `static/css/site.css` |
| el bloque de contacto | `templates/contacto.html` |
| el crédito del pie | `templates/base.html` |
| producción / desarrollo | `deploy/stack.yml`, `docker-compose.yml` |
| las pruebas | `tests/test_anuncios_apagados.py` (18) |

**El tag lleva la puerta y el context processor la bandera, y hacen falta los dos.** El tag apaga los
huecos, pero los tags son `inclusion_tag` y **no reciben el contexto de la petición**, así que el
procesador no llega a esas plantillas. Y al revés: la portada necesita saberlo para cambiar de
rejilla, y eso no lo puede decidir un hueco.

---

## Cuando lleguen los anunciantes

Poner `ANUNCIOS_VISIBLES=true` (o quitar la variable, que por defecto está encendido) y actualizar el
stack. Vuelven los dieciséis huecos, el bloque de contacto, el crédito del pie y la portada a dos
columnas con su carril.

Conviene comprobar después:

```bash
curl -s http://127.0.0.1:3004/health/adserver
```

Y mirar la portada: los huecos de arriba y abajo con anuncio de verdad, y el carril de 300×600 a la
derecha del bloque de artículos.
