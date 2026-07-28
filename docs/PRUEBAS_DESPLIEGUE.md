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
| Los trabajos del scheduler no corren | El contenedor no se llama `dglweb-web-live`. Renombrar exige **borrar el contenedor primero**; Portainer no lo hace solo. |
| 403 en las fotos | Los archivos quedaron dentro de `/var/lib/docker`, que es `0710 root:root` y nginx —como `www-data`— no puede atravesar. Tienen que estar en `/srv/dglweb-datos/`. |
| «Permission denied» al subir una imagen desde el CMS | La carpeta montada no es del uid **1000**. `chown -R 1000:1000 /srv/dglweb-datos`. |
| `MissingFileError` al construir la imagen | Un estático referencia un archivo que no existe (nos pasó con el `.map` de Bootstrap). El almacenamiento con manifiesto aborta si falta algo referenciado. |
| 413 al subir una foto grande | `client_max_body_size` en nginx. Su defecto es 1 MB y **no deja rastro en los logs de Django**. |

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
