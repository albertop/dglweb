# Respaldo y restauración

Montado el 2026-07-30. Dos procesos que no se coordinan entre sí, y un tercero que es el único que
demuestra que los dos primeros sirven de algo.

```
04:30   refresh_daily          el pipeline del día
05:30   respaldo.sh            VPS  → genera y publica en /srv/respaldos
07:00   traer_respaldos.sh     casa → va a buscar, verifica, rota, hace ping a Kuma
```

## Las tres decisiones que lo sostienen

**La casa va a buscar; el VPS no empuja.** Con push, el VPS guardaría credenciales para escribir en
10.0.0.39 — y quien comprometa el VPS borraría los respaldos antes de cifrar nada, que es como opera
el ransomware actual. Con pull, el VPS no sabe que las copias existen.

**La clave SSH no abre sesión.** En `authorized_keys` del VPS:

```
command="/usr/bin/rrsync -ro /srv/respaldos",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ssh-ed25519 AAAA…
```

Comprobado pidiéndole una sesión a propósito: `SSH_ORIGINAL_COMMAND does not run rsync`. Una clave sin
contraseña que vive en el disco de una máquina de casa solo es aceptable si de verdad no abre nada, y
eso se verifica intentándolo, no leyéndolo.

**El aviso es por AUSENCIA, no por error.** El script no alerta cuando falla: hace ping a un monitor
Push de Uptime Kuma cuando todo salió bien, y Kuma avisa si ese ping no llega en 48 horas.

Un script que se muere no puede avisar de que se murió. Si la máquina está apagada, si el cron
desapareció, si alguien renombró el archivo — un aviso escrito dentro nunca se envía, y el silencio se
lee igual que el éxito.

## Qué hay en cada copia

| | |
|---|---|
| `dglweb.dump` | la base del sitio (`-Fc`, comprimido) |
| `revive.dump` | las campañas y estadísticas del anunciante — **misma instancia, base distinta** |
| `globales.sql` | los roles. `pg_dump` NO los incluye, y sin ellos la restauración falla al primer `OWNER TO` |
| `media.tgz`, `uploads.tgz` | lo que subió el editor desde el CMS |
| `revive_revive_images.tgz` | las creatividades del anunciante — **lo único irreemplazable** |
| `revive_revive_var.tgz` | la config de Revive, con la contraseña de Postgres dentro |
| `letsencrypt.tgz` | los certificados; se necesitan antes de que nginx arranque |
| `MANIFIESTO` | sha256 de todo. **Se escribe el último**: su presencia es la señal de «esta corrida terminó» |

Unos 14 MB por corrida. Fuera quedan los retratos (se regeneran con el script de descarga) y la
configuración del servidor (está en `deploy/`).

**Estas copias contienen credenciales**: `globales.sql` trae los hashes de contraseña de los roles y
la base trae los correos de los usuarios del CMS. Por eso los secretos NO se guardan además acá —van
en 1Password— y por eso una copia en la nube tendría que ir cifrada.

## Restaurar

### La base

```bash
# 1. Los roles PRIMERO, o el resto falla al asignar propietarios.
docker exec -i postgres-postgres-1 psql -U postgres < globales.sql

# 2. Cada base. `-C` la crea; sin él hay que crearla a mano antes.
docker cp dglweb.dump postgres-postgres-1:/tmp/
docker exec postgres-postgres-1 pg_restore -U postgres -C -d postgres /tmp/dglweb.dump
```

### Los archivos — **CON `--numeric-owner`, y esto no es opcional**

```bash
tar xzf media.tgz --numeric-owner -C /srv/dglweb-datos
```

Este VPS corre Docker con `userns-remap`, así que esas carpetas pertenecen al uid **101000** —el
`appuser` del contenedor visto desde el anfitrión— y ese uid no tiene entrada en `/etc/passwd`. Sin la
bandera, `tar` restaura por NOMBRE de usuario, no lo encuentra, y los archivos acaban en `root`.

Y si acaban en root, **los archivos vuelven pero el CMS no puede subir ni borrar ninguna imagen**. Es
el fallo que costó una tarde el 2026-07-28, y el peor día para volver a encontrárselo es justo el día
que uno está restaurando.

### Revive

Los dos volúmenes se restauran igual, en `/var/lib/docker/volumes/`. **`revive_var` importa tanto como
las imágenes**: si falta, Revive vuelve a la pantalla de instalación con la base llena de campañas, y
la contraseña de Postgres que guarda dentro tiene que seguir coincidiendo con la del rol.

## La prueba trimestral

**Un respaldo que nunca se restauró es una suposición.** Cada tres meses:

1. Levantar un Postgres aparte en 10.0.0.39 desde la última copia.
2. Restaurar `globales.sql` y `dglweb.dump`.
3. Arrancar el sitio contra esa base y **abrir un artículo con foto**.
4. Anotar la fecha y el resultado acá abajo.

El paso 3 es el que importa. Que `pg_restore` no dé error solo dice que el archivo se leyó — abrir un
artículo con foto comprueba de una vez la base, los medios y los permisos de los archivos, que son
las tres cosas que se rompen por separado.

| fecha | resultado |
|---|---|
| — | *pendiente: la primera toca en octubre de 2026* |

## Lo que este montaje NO cubre

- **Una tercera copia fuera de las dos casas.** Un incendio o un robo en 10.0.0.39 deja solo el VPS.
  Con 14 MB por corrida cabe de sobra en cualquier tier gratuito de 10 GB, **cifrada**. Queda como
  fase aparte.
- **Los valores de las variables de Portainer.** Van en 1Password, y es tarea del dueño.
- **La cuenta de AWS** (registrador y DNS de los cuatro dominios) **y la de RackNerd**. Son lo único
  del inventario cuya pérdida no se repara con tiempo y trabajo.
