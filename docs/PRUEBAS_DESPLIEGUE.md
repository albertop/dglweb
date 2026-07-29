# Qué probar al desplegar una imagen nueva

Dos partes: **lo que cambió en esta versión** —que se vacía al desplegarla— y **la vuelta de
siempre**, que se corre entera cada vez porque lo que rompe un despliegue casi nunca es lo que se
tocó, sino lo que se dio por sentado.

Todo lo de acá se corre **en el VPS**, salvo donde diga otra cosa.

---

## Pendiente de probar en la próxima imagen

Lo que ya está en `main` y todavía no vive en producción. **Al desplegar, se comprueba y se borra de
esta lista.**

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

### EL ORDEN DEL DESPLIEGUE CAMBIÓ (2026-07-29)

Desde que nginx sirve los estáticos hay **un paso más, y va en un orden que no se puede invertir**:

```bash
cd /srv/dglweb && git pull --ff-only && ./deploy_dglweb_image.sh
#   → actualizar el stack en Portainer (recrea el contenedor)
./deploy/estaticos.sh
docker exec dglweb-web-live python manage.py migrate   # solo si la versión trae migraciones
```

**`estaticos.sh` va DESPUÉS de recrear el contenedor.** Al revés se copiarían los estáticos de la
versión anterior mientras el HTML nuevo pide hashes que no existen: el sitio sale sin hojas de estilo
y sin JavaScript, y en la consola del navegador solo hay 404.

El script **no borra nada**, y eso es lo que evita una ventana de sitio roto: los nombres llevan hash,
así que las dos versiones conviven y los navegadores que aún tienen la página anterior en pantalla
siguen encontrando lo suyo. La carpeta crece unos megas por despliegue; se limpia a mano, en frío.

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
    allow 73.244.42.221;
    deny all;
    # … las mismas cabeceras de proxy que `location /`: NO se heredan entre `location`.
}
```

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
