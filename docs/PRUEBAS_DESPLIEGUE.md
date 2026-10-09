# Qué probar al desplegar una imagen nueva

Dos partes: **lo que cambió en esta versión** —que se vacía al desplegarla— y **la vuelta de
siempre**, que se corre entera cada vez porque lo que rompe un despliegue casi nunca es lo que se
tocó, sino lo que se dio por sentado.

Todo lo de acá se corre **en el VPS**, salvo donde diga otra cosa.

---

## Pendiente de probar en la próxima imagen

Lo que ya está en `main` y todavía no vive en producción. **Al desplegar, se comprueba y se borra de
esta lista.**

### «Destacados ayer y hoy» y las rachas en postemporada

Estaba congelado en el 27-09 porque solo pedía serie regular. Sin migraciones. Después de desplegar,
rehacer AYER —el refresco de la madrugada la guardó vacía y nada vuelve a mirarla—:

```bash
docker exec dglweb-web-live python manage.py build_daily_standouts --fecha $(date -d yesterday +%F)
```

- [ ] El comando termina con «N actuaciones guardadas» y no con «no hubo juegos», si ayer jugó algún
      dominicano en octubre.
- [ ] La portada enseña la jornada de ayer y, según van cerrando, los juegos de hoy por arriba.
- [ ] En el Backoffice, las corridas de `build_daily_standouts` ya no salen con 0 filas los días con
      juegos.
- [ ] «Quemando la liga» y «Pasando trabajo» vuelven a moverse en la siguiente corrida horaria de
      `build_window_standouts` — se rehacen enteras, no hay nada que rellenar. Una línea de lanzador
      con juegos de septiembre y de octubre enseña las entradas sumadas bien (`12.1`, nunca `11.4`).
### El comparador de peloteros

Trae más piezas que un cambio normal: **una migración, tipografías nuevas dentro del paquete, dos
archivos de JavaScript, una tabla de caché y metadatos de Open Graph**. La checklist existe para que
esas piezas dejen de vivir solo en la cabeza de quien las construyó.

**1. La migración crea la tabla de caché de imágenes.** Si falta, la primera petición de una tarjeta
revienta — y `/ready` lo diría antes con un 503.

```bash
docker exec dglweb-web-live python manage.py migrate
```

**2. El asistente carga y camina.** Seis pasos; el que importa probar es el 1, porque filtra a los
demás:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://dominicanosengrandesligas.com/comparar/
```

En el navegador: elegir «Lanzadores relevistas», comprobar que el buscador **no** ofrece a Marichal, y
llegar hasta el resumen.

**3. Las dos imágenes se sirven.** La vertical es la que se comparte como fichero; la apaisada es la
que ven las redes al pegar el enlace. Son distintas y se piden aparte:

```bash
curl -s -o /dev/null -w "vertical %{http_code} %{size_download}\n" "https://dominicanosengrandesligas.com/comparar/juan-marichal-118283/vs/pedro-martinez-118377/carrera/tarjeta.png"
curl -s -o /dev/null -w "previa   %{http_code} %{size_download}\n" "https://dominicanosengrandesligas.com/comparar/juan-marichal-118283/vs/pedro-martinez-118377/carrera/tarjeta.png?previa=1"
```

Si la vertical sale y la previa no, lo más probable es que falte una tipografía en la imagen: las tres
TTF viven en `dglweb/stats/fuentes/` y viajan con el paquete, no con los estáticos.

**4. Un abridor contra un relevista responde 404**, que es una decisión de dominio y no un fallo — se
rankean en poblaciones distintas. Ver `docs/COMPARADOR.md` §3:

```bash
curl -s -o /dev/null -w "%{http_code} (se espera 404)\n" "https://dominicanosengrandesligas.com/comparar/juan-marichal-118283/vs/fernando-rodney-407845/carrera/"
```

**5. Si el despliegue cambia el DISEÑO de la tarjeta, hay que limpiar la caché de imágenes.** La
invalidación automática es por versión de los DATOS: cambiar el dibujo no cambia ni la carga ni los
ids, así que la clave sigue siendo la misma y circulan hasta seis horas tarjetas con el formato
anterior. Pasó dos veces en desarrollo y las dos pareció que el cambio no había entrado.

```bash
docker exec dglweb-web-live python manage.py shell -c "from django.conf import settings; from django.core.cache import caches; caches[settings.IMAGENES].clear(); print('limpia')"
```


### 1.2026.2 — etiqueta de entorno en los avisos

Desde que hay producción son dos schedulers avisando al mismo chat de Telegram, y no había forma de
saber cuál hablaba. Ahora todo mensaje sale como `[PROD] …` o `[DEV] …`.

```bash
docker exec dglweb-web-live python manage.py telegram_check
```

- [ ] El mensaje que llega al teléfono **empieza por `[PROD]`**.
- [ ] Y desde tu Windows, el mismo comando llega como **`[DEV]`** — es la mitad que prueba que
      distingue de verdad y no que puso una etiqueta fija.

### 1.2026.3 — nomenclatura de lanzadores y el retrato del biobox

- [ ] En **/jugadores/**, los lanzadores dicen **`P-ABR`** y **`P-REL`**, no `SP` ni `RP`. La `P` a
      secas se queda como está.
- [ ] En la ficha de un lanzador, «Posición: P-ABR».
- [ ] El total de la frase de arriba sale en **negritas**.

### 1.2026.4 — SEO y el artículo fijado

**Trae una MIGRACIÓN** (`articles.0006`), así que `/ready` va a decir «migraciones pendientes» hasta
que corra `migrate`. No es un fallo: es el endpoint haciendo su trabajo.

```bash
docker exec dglweb-web-live python manage.py migrate
curl -s https://dominicanosengrandesligas.com/robots.txt
curl -s https://dominicanosengrandesligas.com/sitemap.xml | grep -o "<loc>" | wc -l
```

- [ ] `robots.txt` responde y su `Sitemap:` apunta al **dominio real**, no a localhost.
- [ ] El mapa trae **~990 URLs** — las fichas más los dos artículos reales y las páginas fijas.
- [ ] **Que NO aparezca ningún artículo de prueba en el mapa.** Los de desarrollo no están en la base
      de producción, pero conviene mirarlo: es justo lo que no se quiere anunciar.
- [ ] Pegar un enlace de un artículo en WhatsApp y ver que sale con foto, titular y bajada.
- [ ] Marcar un artículo como **«fijado arriba»** en el CMS y comprobar que encabeza la portada y el
      índice, aunque no sea el más reciente.

### 1.2026.5 — los arreglos del review v10

Nada de esto cambia la pantalla salvo el modal de video, así que lo que hay que mirar es el semáforo y
el log de ingesta.

```bash
curl -s -o /dev/null -w "%{http_code}
" https://dominicanosengrandesligas.com/health/pipeline
docker exec dglweb-web-live python manage.py build_daily_standouts --fecha-hoy
```

- [ ] El semáforo sigue en **200** después de desplegar. Si sale 503, mirar el detalle con el token:
      lo más probable es que `build_daily_standouts` todavía no tenga una corrida con el alcance
      nuevo, y se arregla solo en la siguiente hora.
- [ ] En el Backoffice, el log de ingesta enseña filas de `build_daily_standouts` con el alcance
      **«… en curso»** en el modo horario, y **sin** sufijo en la corrida de las 4:30.
- [ ] A media mañana, sin juegos cerrados, ese job deja un **salto** y el semáforo sigue verde.
- [ ] **A comprobar de madrugada, una vez:** entre la 1 y las 4 a. m., un juego de la costa oeste que
      cruzó la medianoche tiene que aparecer en «Destacados» sin esperar al refresco de las 4:30.
- [ ] **El modal de video, con teclado** —esto NO lo cubre ninguna prueba automática, porque jsdom no
      implementa `inert`—: abrir un clip, pulsar Tab cinco o seis veces y comprobar que el foco no se
      escapa a los enlaces de detrás. Cerrar con Escape y ver que vuelve al botón que lo abrió.

### EL ORDEN DEL DESPLIEGUE (corregido el 2026-07-30)

Desde que nginx sirve los estáticos hay un paso más, y va en un orden que no se puede invertir:

```bash
cd /srv/dglweb && git pull --ff-only && ./deploy_dglweb_image.sh
./deploy/estaticos.sh 1.2026.10          # ← ANTES de tocar el stack, y CON la versión
#   → actualizar el stack en Portainer (recrea el contenedor)
docker exec dglweb-web-live python manage.py migrate   # solo si la versión trae migraciones
```

**`estaticos.sh` va ANTES de recrear el contenedor, y con el número de versión.** Acá decía lo
contrario —«DESPUÉS», y sin argumento— y estaba mal desde que el script se reescribió el 2026-07-29.

El motivo del cambio: pasándole la versión, el script copia **de la imagen** con `docker create`, o
sea sin arrancar nada. Así los archivos están en disco ANTES de que exista el HTML que los pide. Sin
argumento copia del contenedor que corre, y entonces hay que hacerlo después — dejando unos segundos
en los que el contenedor nuevo ya sirve HTML con hashes nuevos y los archivos todavía no están.

Esa ventana costó una avería de verdad: el bloque `/static/` llevaba `always` en su `add_header`, así
que **el 404 salía con caché de un año y marcado como inmutable**, y el navegador de quien entrara ahí
no volvía a pedir el CSS nunca. Lo del `always` ya está arreglado; el orden es lo que cierra el resto.

Copiar antes es seguro porque **el script nunca borra**: los nombres llevan hash del contenido, así que
las dos versiones conviven y quien tenga la página anterior en pantalla sigue encontrando lo suyo. La
carpeta crece unos megas por despliegue; se limpia a mano, en frío.

### 1.2026.12 — la tarjeta social deja de salir en azul liso

Un solo cambio: la etiqueta `og:image` de la página del artículo. Si la imagen es una banda de
relleno, se usa la lámina de marca en vez de recortar la banda.

**Ojo con la caché antes de dar nada por malo:** WhatsApp y Telegram guardan la lámina **por URL
durante días**. Un enlace ya compartido va a seguir saliendo igual aunque el despliegue esté bien.
Para comprobarlo hace falta un artículo que no se haya compartido nunca, o el mismo con un `?x=1`
detrás.

- [ ] Pegar en WhatsApp el enlace de un artículo **con banda**: la tarjeta sale con el logotipo, no
      con el rectángulo azul.
- [ ] Pegar el de un artículo **con foto de verdad**: sale **su foto**, no la lámina genérica. Es la
      comprobación que importa — descartar una foto legítima se nota mucho menos que el azul liso y
      engaña más.
- [ ] `curl -s <url-del-articulo> | grep 'og:image'` para verlo sin depender de la caché de nadie.

Sin migraciones.

### 1.2026.11 — lo primero del día que ve el lector

Las dos cosas que cambian en pantalla, más los arreglos del review v14 —que no se ven— y los
scripts de respaldo, que no viajan en la imagen.

**Lo visible, y las dos se comprueban mirando:**

- [ ] En la portada y en `/articulos/`, la entradilla de las tarjetas llega a **tres líneas** y ya no
      se corta con «…» habiendo hueco debajo. El caso ajustado es una tarjeta **con etiquetas y
      titular de tres líneas**: si ahí la tercera línea toca el pie o se ve cortada por la mitad, hay
      que volver a dos en `.dgl-art .entradilla`.
- [ ] En un artículo cuya imagen sea una **banda** (`banner-ancho`, `banner-chico`), la cabecera va de
      los botones de compartir **directo al cuerpo**, sin el rectángulo azul con pie de foto.
- [ ] Y en uno con **foto de verdad**, la foto sigue saliendo. Es la mitad que prueba que el corte por
      proporción distingue y no que simplemente dejó de dibujar.

**Lo que no se ve:**

- [ ] `/health/pipeline` en **200**.
- [ ] Los cuatro dominios responden: el sitio, `promo.`, `sabertables.com` y `baseballsixdegrees.com`.

**Nada de esto trae migraciones**, así que `migrate` no debería hacer nada — si dice que aplicó algo,
parar y mirar antes de seguir.

### 1.2026.10 — lo acumulado desde la .7, en una sola imagen

**51 commits.** La .8 y la .9 nunca llegaron al VPS: la decisión del dueño (2026-07-28) fue juntar los
cambios y subirlos cuando hubiera algo que lo justificara. Lo de la .8 sigue más abajo y hay que
comprobarlo igual; acá va lo que se sumó después.

#### Lo que hay que tocar en el servidor, y va antes que nada

Estos NO viajan en la imagen. Si el conf llega sin el de zonas, `nginx -t` falla y el reload se
rechaza — el sitio se queda con la configuración vieja, que no tumba nada pero deja el despliegue a
medias sin avisar.

```bash
sudo cp deploy/nginx-limites.conf /etc/nginx/conf.d/limites.conf   # PRIMERO: declara las zonas
sudo cp deploy/nginx-dglweb.conf  /etc/nginx/sites-available/dglweb # después: las usa
sudo nginx -t && sudo systemctl reload nginx
```

- [ ] `nginx -t` en verde **antes** del reload. Si dice `unknown limit_req zone`, falta el primero.
- [ ] `ANALITICA_ENVIO_URL` **no** hace falta en el stack: trae un defecto que cubre a Umami Cloud.
      Solo se pone si Umami vuelve a mover el host de recolección.

#### La analítica, que llevaba días sin contar nada

Umami Cloud baja el script de `cloud.umami.is` y recolecta en `gateway.umami.is`. Cuando cambiaron lo
segundo, la CSP dejó de cubrirlo: el script cargaba, la página se veía idéntica y **cada envío lo
bloqueaba el navegador**. Se descubrió en la factura de eventos —2 en todo el mes—, no en una alerta.

- [ ] En el sitio, **F12 → Network → filtro `send` con `All`**: tiene que aparecer una fila con **200**.
- [ ] En **Console** no puede quedar ninguna línea de `Content Security Policy` sobre `umami`.
- [ ] En Umami, la vista **Realtime** enseña la visita en segundos.

#### Los límites de tasa, que es lo que puede echar gente fuera

Lo primero que hay que mirar después del reload, porque un límite mal puesto no se nota navegando
—uno solo hace una petición cada vez— y sí se nota en una hora punta.

```bash
sudo tail -f /var/log/nginx/error.log | grep limiting
```

- [ ] Navegar el sitio a ritmo normal **no** produce ninguna línea `limiting requests`.
- [ ] Ojo con el **CGNAT dominicano**: miles de móviles comparten una IP pública, así que un límite por
      IP puede afectar a media operadora. Si aparecen 429 de usuarios reales, subir el `rate` antes que
      cualquier otra cosa.

#### Compartir en redes

- [ ] Los cinco botones salen al final del artículo, en el perfil de jugador y en líderes.
- [ ] **Copiar enlace** copia de verdad, dice «¡Copiado!» y **el icono sigue ahí** después. (Se borraba:
      lo cazó una prueba nueva.)
- [ ] En un teléfono aparece el botón del menú **nativo** del sistema; en escritorio no.
- [ ] Pegar un enlace en WhatsApp: sale con foto, titular y bajada.

#### Los anuncios, ya sirviendo

Los huecos ya están vivos en producción (`ADSERVER_URL` puesto). Lo que cambia en esta imagen es el
**aislamiento** y el reparto por tamaños.

- [ ] Cada `<iframe>` de anuncio lleva `sandbox="allow-scripts allow-same-origin allow-popups
      allow-popups-to-escape-sandbox"`. Sin él, una creatividad de un anunciante puede llevarse al
      lector con `top.location`.
- [ ] Un clic en un anuncio **abre en otra pestaña** y llega al destino. Si no abriera, el `sandbox`
      estaría de más — pero Revive ya usa `target="_blank"`, así que debe funcionar.
- [ ] En móvil **no** aparece el carril de 300×600, y sí un 320×50 entre los widgets.
- [ ] En el panel de Revive, las impresiones suben **una por hueco visto**, no tres.

#### Rendimiento y base de datos

- [ ] `docker logs dglweb-web-live | head -20` enseña gunicorn con `gthread` y 4 workers.
- [ ] El sitio responde normal después de reiniciar **Postgres**: las conexiones persistentes traen
      `CONN_HEALTH_CHECKS`, así que una conexión muerta se sustituye sin que el visitante vea un 500.
      Es la mitad que de verdad prueba el ajuste.

#### Lo que no se ve pero cambió

- [ ] `/health/pipeline` sigue en **200**.
- [ ] En el Backoffice, el log de ingesta: si un derivado falla, el detalle nombra **al derivado**, no
      a las entradas.
- [ ] Los destacados de la portada siguen saliendo con 5–6 nombres. Los pisos se recalibraron al p80
      de la MLB y el de pitcheo quedó en 0,82 **a propósito** por encima del inning limpio de relevo.

### 1.2026.8 — SIN DESPLEGAR (se acumula a propósito)

**Decisión del dueño (2026-07-28): no se despliega por cada detalle.** Los cambios se juntan acá y
suben todos en la misma imagen cuando haya algo que lo justifique. La 1.2026.7 queda congelada y es
exactamente lo que corre en el VPS.

Lo que lleva acumulado:

- **La lámina de compartir**, ahora solo con el logotipo — sin la bajada ni la barra roja.
- **`core.W001`**, el aviso de arranque cuando el sitio corre en producción con el canal de Telegram
  apagado. Ya no hace falta para el problema que lo motivó —las credenciales están puestas— pero
  evita que vuelva a pasar en silencio.
- **El cintillo se esconde** cuando los movimientos que muestra tienen más de un día de atraso.
- **Las dos bandas** para tarjetas de artículo sin foto (`static_data/banners/`). No son código: se
  suben desde el CMS cuando el editor las necesite, así que no dependen de este despliegue.

- **La publicidad**, con las cuatro zonas de Revive conectadas a los trece huecos. **Necesita
  `ADSERVER_URL` en el stack**, o los huecos siguen mostrando el recuadro de maqueta — que es el
  comportamiento correcto, no un fallo.

Al desplegar:

- [ ] Añadir `ADSERVER_URL=https://promo.dominicanosengrandesligas.com` al stack (bloque
      `environment:` **y** «Environment variables»).
- [ ] En la portada, comprobar que los huecos son `<iframe>` y no el recuadro rayado.
- [ ] **En la consola del navegador no puede haber un error de CSP.** Si lo hay, falta el dominio en
      `frame-src` — y el hueco se queda vacío sin más pista que esa línea.
- [ ] En el panel de Revive, **Estadísticas**: las impresiones tienen que empezar a subir. Si el
      `iframe` carga pero no cuenta, mirar `mod_remoteip` antes que nada.
- [ ] **Crear el monitor del proxy en Kuma**, que hasta ahora no se podía porque el endpoint no
      existía en producción (404). Con la `1.2026.8` arriba, `/health/proxy` responde 200:

      - Monitor Type: **HTTP(s) - Keyword** · Friendly Name: `dglweb — proxy MLB`
      - URL: `https://dominicanosengrandesligas.com/health/proxy`
      - Keyword: `"status":"ok"` — **compacto, sin espacios**: Kuma no compara contra el cuerpo que
        llega sino contra su propio `JSON.stringify()`, y una clave copiada del navegador no coincide
        nunca.
      - Accepted Status Codes: `200-599` — con `200-299`, un 503 se vuelve error de petición antes de
        que Kuma mire el cuerpo, y se pierde el detalle de qué falló.
      - Headers: `{ "X-Monitor-Token": "…" }` · Intervalo `300` · Reintentos `2`

- [ ] Pegar un enlace del sitio en Telegram y ver que la lámina sale **solo con el logotipo**. Ojo:
      Telegram y WhatsApp **cachean la lámina por URL durante días**, así que puede seguir saliendo la
      vieja un rato aunque el despliegue esté bien. No es un fallo.
- [ ] `docker exec dglweb-web-live python manage.py check` no debe sacar `core.W001`. Si sale, el
      canal de avisos se quedó sin credenciales en el stack.

### 1.2026.6 y .7 — tarjetas y analítica

**La .7 no mide nada hasta tocar DOS SITIOS en Portainer**, y las dos mitades hacen falta. Es la
trampa de siempre: las «Environment variables» de Portainer no llegan al contenedor, solo sustituyen
`${VAR}` dentro del compose (ver la tabla de síntomas al final).

**1) En el compose del stack**, dentro de `environment:` del servicio `web`:

```yaml
      ANALITICA_URL: ${ANALITICA_URL:-}
      ANALITICA_ID: ${ANALITICA_ID:-}
```

**2) En «Environment variables» del stack**, dos pares:

```
ANALITICA_URL = https://cloud.umami.is
ANALITICA_ID  = bcd6507e-fac9-498b-9bff-1b42afad448f
```

**ESTE FALLA MÁS CALLADO QUE LOS OTROS.** Que falte `DJANGO_SECRET_KEY` revienta el arranque y se ve;
que falten estas dos no rompe nada — el sitio levanta perfecto, sirve todas las páginas y
sencillamente no cuenta ni una visita, porque el default es apagado a propósito. No hay error en el
log ni en la consola del navegador. **La única señal es el panel de Umami vacío**, así que la
comprobación de abajo no es opcional.

Los `:-` del compose son a propósito: sin ellos, un stack sin esas variables definidas ni siquiera
levanta, y la analítica no puede ser la razón de que el sitio no arranque.

- [ ] En el HTML de la portada aparece el `<script defer src="https://cloud.umami.is/script.js">`.
- [ ] En la consola del navegador **no hay ningún error de CSP**. Si lo hay, el dominio no llegó a la
      cabecera: comprobar que las DOS variables están puestas, porque la política se arma al arrancar
      el proceso y solo incluye la analítica si hay identificador.
- [ ] **En el panel de Umami se ve la visita.** Es la comprobación que importa: el script puede cargar
      perfectamente y no contar nada si `connect-src` bloquea el envío, y eso no deja ni un mensaje.
- [ ] `/legal/cookies/` y `/legal/privacidad/` cargan y la de privacidad nombra a Umami.
- [ ] Los titulares de las tarjetas llegan a **tres líneas** cuando hace falta.
- [ ] En `/articulos/` **solo la tarjeta grande de arriba** tiene el titular grande. Si las de la
      retícula también, el `only` de los `{% include %}` se perdió.

### El retrato del biobox — ARREGLO DE PRODUCCIÓN

El fallo: en producción la ficha no enseñaba la foto grande aunque el archivo estuviera. `existe()`
mira el disco **dentro del contenedor**, y al desplegar movimos los retratos al anfitrión para que
los sirviera nginx. Los pequeños sí salían porque esos se pintan siempre y se esconden con `onerror`.

La ficha **no puede** usar ese truco: un tercio de los peloteros no tiene retrato, y dibujar la
etiqueta para quitarla después haría que el nombre naciera corrido 120px y saltara a su sitio al
volver el 404.

El arreglo es un volumen más en el stack, de solo lectura:

```yaml
      - /srv/dglweb-datos/mugshots:/app/static/img/mugshots:ro
```

- [ ] La ficha de alguien **con** retrato lo enseña.
- [ ] La ficha de alguien **sin** retrato no deja hueco ni imagen rota.

---

## La vuelta de siempre

### 1. Arrancó y alcanza la base

```bash
docker ps --format "{{.Names}}\t{{.Status}}" | grep dglweb
curl -s http://127.0.0.1:3004/health; echo
curl -s http://127.0.0.1:3004/ready; echo
```

- [ ] El contenedor se llama **`dglweb-web-live`** y dice `healthy`.
- [ ] `/health` → `{"status": "ok"}`.
- [ ] `/ready` → `{"status": "ok"}`.

**El nombre no es un detalle.** `ofelia/config.ini` lo nombra seis veces; con otro nombre, los seis
trabajos fallan **en silencio** hasta la hora siguiente. Ofelia los registra al arrancar sin
comprobar que el objetivo exista.

**Si `/ready` dice «migraciones pendientes»**, falta correr `migrate` — la imagen trae código nuevo
que la base todavía no soporta.

### 2. Las páginas responden

```bash
for r in / /lideres/ /articulos/ /jugadores/ /legal/privacidad/ /contacto/; do
  printf "%-24s %s\n" "$r" "$(curl -s -o /dev/null -w '%{http_code}' https://dominicanosengrandesligas.com$r)"
done
```

- [ ] Las seis en **200**.

### 3. Las imágenes, que van por caminos distintos

Son tres orígenes y cada uno se rompe por su lado:

```bash
curl -s -o /dev/null -w "estático (WhiteNoise): %{http_code}\n" https://dominicanosengrandesligas.com/static/css/site.css
UNO=$(ls /srv/dglweb-datos/mugshots/120/ | head -1)
curl -s -o /dev/null -w "retrato (nginx):       %{http_code}\n" "https://dominicanosengrandesligas.com/static/img/mugshots/120/$UNO"
FOTO=$(docker exec postgres-postgres-1 psql -U postgres -d dglweb -tAc "SELECT '/media/'||file FROM wagtailimages_image LIMIT 1" | tr -d ' \r')
curl -s -o /dev/null -w "medio (nginx):         %{http_code}\n" "https://dominicanosengrandesligas.com$FOTO"
```

- [ ] Los tres en **200**.

**Por qué los tres.** El estático viaja DENTRO de la imagen y lo sirve WhiteNoise —si `collectstatic`
falló en el build, esto da 404—. Los retratos y los medios los sirve **nginx** desde
`/srv/dglweb-datos/`, así que no cambian al desplegar… salvo que alguien toque el `server` de nginx.

### 4. El scheduler alcanza al contenedor

```bash
docker logs dglweb-scheduler 2>&1 | tail -8
docker exec dglweb-web-live python manage.py update_roster_moves
```

- [ ] El log lista **seis** trabajos registrados.
- [ ] El comando termina diciendo cuántos movimientos trajo.

Ese comando prueba la cadena entera de una vez: sitio → proxy → API de MLB → base. Si el proxy no
respondiera, se ve acá y no a las 4:30 de la madrugada.

### 5. Lo que se ve, que no lo dice ningún `curl`

Abrir **https://dominicanosengrandesligas.com** y mirar:

- [ ] La portada trae pizarra, destacados y líderes — **con contenido**, no los recuadros vacíos.
- [ ] Un perfil de jugador enseña su retrato y sus tablas.
- [ ] Un artículo con foto la muestra.
- [ ] El cintillo de movimientos se mueve.

Un 200 solo dice que la página se armó. Un widget vacío también responde 200.

---

## Si algo falla, mirar primero acá

Lo que ya nos mordió una vez. Todo esto pasó de verdad el 2026-07-28.

| Síntoma | Causa probable |
|---|---|
| `ImproperlyConfigured: Set the DJANGO_SECRET_KEY` | Las «Environment variables» de Portainer **no llegan al contenedor**: solo sustituyen `${VAR}` dentro del compose. Hay que nombrarlas en un bloque `environment:`. |
| `env file … not found` al desplegar | `env_file` con ruta del anfitrión no sirve: Portainer corre en un contenedor y no ve ese sistema de archivos. |
| Los trabajos del scheduler no corren | Dos causas distintas. (a) `permission denied` sobre `/var/run/docker.sock` en el log de Ofelia: es el `userns-remap`, falta `userns_mode: "host"` en ese servicio — ver abajo. (b) El contenedor no se llama `dglweb-web-live`. Renombrar exige **borrar el contenedor primero**; Portainer no lo hace solo. |
| 403 en las fotos | Los archivos quedaron dentro de `/var/lib/docker`, que es `0710 root:root` y nginx —como `www-data`— no puede atravesar. Tienen que estar en `/srv/dglweb-datos/`. |
| «Permission denied» al subir o borrar una imagen desde el CMS | La carpeta montada no es del `appuser` del contenedor **visto desde el anfitrión**. Este Docker usa `userns-remap`, así que NO es el uid 1000 — ver la sección de abajo. |
| `MissingFileError` al construir la imagen | Un estático referencia un archivo que no existe (nos pasó con el `.map` de Bootstrap). El almacenamiento con manifiesto aborta si falta algo referenciado. |
| 413 al subir una foto grande | `client_max_body_size` en nginx. Su defecto es 1 MB y **no deja rastro en los logs de Django**. |

---

## El CMS está cerrado por IP (2026-07-29)

`/cms`, `/cms/`, su formulario de acceso y `/django-admin/` solo responden desde la IP del dueño. El
resto del sitio, intacto. En el `server` de nginx:

```nginx
location ~ ^/(cms|django-admin)(/|$) {
    include /etc/nginx/snippets/ip-del-dueno.conf;
    deny all;
    # … las mismas cabeceras de proxy que `location /`: NO se heredan entre `location`.
}
```

**La IP ya no se escribe acá** (2026-07-30). Vive en un solo archivo que reescribe el cron cuando la
IP de casa del dueño cambia — antes estaba a mano en este `location` y el cron no lo actualizaba, así
que seguía funcionando por casualidad. Ver `deploy/nginx-ip-del-dueno.conf`.

**El `(/|$)` importa.** Con solo `^/(cms|django-admin)/`, la URL sin barra final no casa: llega a
Django, que redirige a `/cms/`. El acceso queda bloqueado igual, pero esa redirección le confirma a
cualquiera que la ruta existe.

**Lo que NO se cierra, y es deliberado:** `/static/` —lo sirve WhiteNoise y el panel se quedaría sin
estilos ni JavaScript— y `/documents/`, que aunque sea de Wagtail es por donde se descargan los
documentos que enlaza un artículo, o sea contenido público.

**Al comprobarlo, cuidado con el relevo de procesos.** `systemctl reload nginx` devuelve el control
enseguida pero los trabajadores viejos siguen atendiendo un momento. Un `curl` encadenado al reload
puede caer en la configuración anterior y dar un resultado que no cuadra con el archivo — pasó, y
costó un rato de buscar una causa que no existía. Repetir la prueba unos segundos después.

**Y el riesgo que hay que tener presente:** esa IP es residencial. El día que cambie, el CMS queda
inaccesible hasta editar esta línea por SSH. Está en dos sitios —acá y en `pgadmin.conf`— así que hay
que cambiarla en los dos.

## El remapeo de usuarios de Docker, o por qué `chown 1000` no arregla nada

**Este VPS corre Docker con `userns-remap` activado** (`/etc/docker/daemon.json`). Costó una tarde
descubrirlo el 2026-07-28, así que queda escrito.

### El síntoma

Subir o borrar una imagen desde el CMS da error 500. **Verlas funciona perfectamente**, y esa
asimetría es la firma: leer sí, escribir no. En desarrollo no pasa.

### Por qué

Con `userns-remap`, el uid 1000 de DENTRO del contenedor es el uid `100000 + 1000 = 101000` en el
anfitrión. Son dos numeraciones distintas para el mismo proceso.

Y ahí está la trampa: **una carpeta creada con `mkdir` en el anfitrión pertenece a root, uid 0, que
cae FUERA del rango remapeado**. El kernel no puede expresar ese dueño dentro del espacio de nombres
del contenedor, así que se lo enseña como **65534 (`nobody`)**. Con permisos `755`, el contenedor
puede leer y no puede escribir.

Eso también explica por qué en desarrollo no ocurre, y **no es porque dev corra como root** —corre
como el mismo `appuser`—: en dev los medios están en un *volumen con nombre*, y Docker los crea
copiando el dueño que la carpeta tenga dentro de la imagen. Un *bind mount* no: respeta lo que haya
en el anfitrión. La diferencia es el tipo de montaje, no el usuario.

### El arreglo

El número correcto sale de `/etc/subuid`, no se adivina:

```bash
BU=$(awk -F: '$1=="dockremap"{print $2}' /etc/subuid)
BG=$(awk -F: '$1=="dockremap"{print $2}' /etc/subgid)
chown -R $((BU+1000)):$((BG+999)) /srv/dglweb-datos/media /srv/dglweb-datos/uploads
```

El `+1000` es el uid de `appuser` en el `Dockerfile.prod` y el `+999` su gid. Bien hecho, el
anfitrión enseña `101000 100999` y el contenedor enseña `1000 999`: **cada lado ve su propio número,
y eso es lo correcto, no un error**.

### Lo que hay que recordar

- **Toda carpeta nueva que se monte va a llegar rota igual.** No fue el accidente de una copia: es
  cómo se comportan los bind mounts en esta máquina. Montar algo escribible = chownearlo.
- **Los permisos no se tocan.** Siguen en `755`, que es lo que necesita nginx —como `www-data` en el
  anfitrión— para poder servir `/media/`. Un `chmod` de más acá rompería las imágenes con un 403.
- **`mugshots` va montado `:ro`** y se queda como está: el contenedor nunca escribe ahí, y quien
  copia los retratos es un script del anfitrión.
- Si algún día se quita `userns-remap` del `daemon.json`, **hay que deshacer estos `chown`** o el
  problema vuelve al revés.

### Y rompe el scheduler, que es la otra mitad de la misma causa

El 2026-07-28, con dos horas de diferencia, el remapeo causó **dos averías que no se parecen en nada**:
no se podían subir imágenes desde el CMS, y los tres jobs horarios llevaban seis horas fallando.

Lo del scheduler se ve así en `docker logs ofelia`:

```
ERROR [Job "mlb-leaders-hourly"] failed: true, error: error creating exec:
Post "http://unix.sock/containers/dglweb-web-live/exec":
dial unix /var/run/docker.sock: connect: permission denied
```

**Por qué.** Ofelia corre como root dentro de su contenedor, pero con el remapeo ese root es el uid
`100000` del anfitrión — que no es root y no está en el grupo `docker`. El socket es `0660
root:docker`. Permiso denegado en cada `exec`.

**Por qué funcionó hasta que dejó de funcionar.** Un contenedor vivo conserva el mapeo con el que
nació. Activar `userns-remap` no rompe nada de inmediato: rompe **la próxima vez que se recrea el
contenedor**, que puede ser semanas después y por un cambio que no tiene nada que ver. Acá fue un
redespliegue para añadir unas variables de entorno.

**El arreglo**, en el servicio del scheduler del compose:

```yaml
    userns_mode: "host"
```

**Y no empeora la seguridad**, aunque lo parezca: ese contenedor ya tiene el socket de Docker montado,
y quien controla el socket controla la máquina, remapeado o no. Es el riesgo que el dueño aceptó
explícitamente al dejar el socket como está. La alternativa de verdad sería un proxy del socket con
lista blanca de operaciones, no el remapeo.

**Lo que lo hizo visible fue el monitor externo**, a los minutos de encenderse. Doce ejecuciones
fallidas seguidas no habían generado ni una señal: Ofelia registra el fallo en su propio log y nadie
lee los logs de un contenedor que se supone que funciona.

### El `chown` sobrevive a todo… menos a tres cosas

Es metadato del disco, así que aguanta reiniciar Docker, reiniciar el servidor, recrear el contenedor
y redesplegar el stack. No hay que repetirlo. Lo que sí lo deshace:

1. **Restaurar el respaldo sin `--numeric-owner`.** `tar` restauraría por nombre de usuario, y el uid
   101000 no tiene nombre en este sistema. Por eso `deploy/respaldo.sh` guarda con esa bandera, y hay
   que restaurar con ella:

   ```bash
   tar xzf media-AAAAMMDD.tgz --numeric-owner -C /srv/dglweb-datos
   ```

   Después, comprobar: `docker exec dglweb-web-live ls -ldn /app/media` tiene que decir `1000 999`.

2. **Que cambie el gid de `appuser` en la imagen.** Va clavado en 999 en el `Dockerfile.prod`
   justamente por esto; antes lo elegía `useradd` solo y podía moverse con la imagen base.

3. **Montar una carpeta nueva.** Nace de root en el anfitrión y el contenedor la ve como `nobody`.

---

## Volver atrás

El stack apunta a una **versión concreta**, nunca a `latest`. Para deshacer un despliegue, se cambia
el número en Portainer y se actualiza — la imagen anterior sigue en el servidor.

```bash
docker images dglweb --format "{{.Tag}}  ({{.CreatedSince}})" | grep -v latest
```

⚠️ **Si el despliegue incluyó migraciones, volver atrás NO es solo cambiar la imagen**: la base ya
tiene el esquema nuevo y el código viejo puede no entenderlo. Ahí se restaura del respaldo, y por eso
importa haber probado una restauración antes de necesitarla.

---

## Después de reiniciar el VPS: espera dos minutos antes de asustarte

El 2026-07-30, un reinicio dejó `dominicanosengrandesligas.com` y `baseballsixdegrees.com` en **502**
mientras `sabertables.com` y Revive respondían. Parecía que dos contenedores no habían vuelto.

No era eso. Docker los arranca a todos casi a la vez —medido: los cuatro dentro de 100 ms— pero
**tardan distinto en estar LISTOS**. `sabertables` responde en cuanto levanta; `dglweb` arranca
gunicorn con `--preload`, carga Django y tiene `start_period: 20s` en su healthcheck. En esa ventana
nginx no tiene a quién proxear y devuelve 502.

**Cómo se distingue de un problema real**, que es lo único que hay que recordar:

```bash
docker inspect -f '{{.Name}} reinicios={{.RestartCount}} arrancado={{.State.StartedAt}}' \
  dglweb-web-live sixdegrees.com sabertables.com postgres-postgres-1
```

- **`reinicios=0` y arranques casi simultáneos** → nadie murió, solo están terminando de subir. Esperar.
- **`reinicios` alto** → hubo bucle contra algo. Ahí sí hay que mirar el log del que peleaba.

Y NO hace falta un `depends_on` hacia Postgres: no se puede —están en stacks distintos y `depends_on`
no cruza proyectos de compose— y tampoco corresponde, porque nada falló. `restart: unless-stopped` ya
cubre el caso en que un contenedor sí muera.

**Uptime Kuma avisó durante la caída**, así que la vigilancia hizo su trabajo. Vale la pena saber que
un reinicio del VPS va a disparar esas alertas y que remiten solas.
