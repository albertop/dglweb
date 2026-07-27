# Lo que servimos nosotros en vez de pedirlo a un CDN

Estos archivos son de terceros y están copiados aquí a propósito. **No se editan a mano**: si hay que
subir de versión o cambiar los pesos de una fuente, se vuelve a generar todo con el procedimiento de
abajo.

## Por qué están acá y no en un CDN

Venían de `cdn.jsdelivr.net` y de `fonts.googleapis.com`, y eso costaba tres cosas:

1. **Seguridad.** Llegaban sin `integrity`, así que un CDN comprometido ejecutaba código en todas las
   páginas del sitio — incluida la pantalla de acceso al CMS.
2. **Disponibilidad.** Si el CDN se cae, el sitio se queda sin estilos. El principio #0 del proyecto
   es resiliencia sobre features.
3. **Privacidad.** Cada visita le decía a Google quién entraba. Eso hay que declararlo en el aviso de
   cookies, y no declarar nada es más fácil que declararlo bien.

## Qué hay

| Archivo | Origen | Versión |
|---|---|---|
| `bootstrap.min.css` | `cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/` | 5.3.3 |
| `bootstrap.bundle.min.js` | `cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/` | 5.3.3 |
| `fuentes.css` + `fuentes/*.woff2` | `fonts.googleapis.com` / `fonts.gstatic.com` | — |

**Solo los alfabetos latino y latino extendido.** Google parte cada fuente en seis subconjuntos
—latino, latino extendido, cirílico, cirílico extendido, griego y vietnamita— y bajarlos todos eran
980 KB. Los tres últimos no los va a usar nunca un sitio de béisbol dominicano. El latino cubre las
tildes y la eñe; el extendido queda por si aparece un apellido extranjero. Con el recorte son
**664 KB**.

**Solo los pesos que el sitio usa**: JetBrains Mono en 400/500/700/800 y Source Serif 4 en 400, 600 y
400 itálica. Cada peso es un archivo más que baja cada visitante.

## Cómo se regenera

Con `vendorizar.py`, que está en esta misma carpeta. Hace tres cosas:

1. Baja los dos archivos de Bootstrap de jsDelivr.
2. Pide a Google el CSS de las fuentes **con un User-Agent de navegador moderno**. Esto no es un
   detalle: con el agente de una librería HTTP, Google devuelve `ttf`, que pesa el triple que `woff2`.
3. Guarda cada `.woff2` y reescribe el CSS para que apunte a la copia local.

Después se filtran los subconjuntos a latino y latino extendido, y se borran los `.woff2` que ya no
referencia el CSS.

## Al subir de versión

Bootstrap 5.3.3 es el que valida el diseño actual. Cambiar de versión mayor puede mover el layout, así
que **no es una actualización de rutina**: hay que mirar la portada, el índice de artículos, el perfil
del jugador y la página de líderes antes de darlo por bueno.
