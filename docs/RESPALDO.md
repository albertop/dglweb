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

**El procedimiento completo está en `docs/RESTAURAR.md`**, escrito para seguirlo un mal día sin tener
que leer antes este documento. Cubre cinco escenarios —desde recuperar una tabla borrada hasta
levantar el VPS entero desde cero— y trae los dos errores que más caros salen: el `--numeric-owner` de
los `tar` y el orden de `globales.sql` antes que las bases.

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

## La tercera copia: Backblaze B2, cifrada (2026-07-30)

Cubre lo que las otras dos no: que **esta casa** desaparezca —incendio, robo— o que un ransomware
llegue a 10.0.0.39 por otra vía y cifre también la carpeta de respaldos.

```
tras verificar el manifiesto  →  tar de la corrida  →  age  →  b2 file upload  →  b2 file info
```

**Diaria, no semanal.** La primera propuesta fue semanal mirando solo el espacio; lo que importa es
cuánto se pierde si la casa desaparece un miércoles. Con semanales, hasta siete días de artículos —lo
único que escribe una persona y no se reconstruye—. Con diarias, uno.

**Retención: 90 días, y la ejecuta B2.** Una *lifecycle rule* del bucket
(`daysFromUploadingToHiding: 90`), no el script. ~1,3 GB de los 10 GB gratis.

### Las dos propiedades que la hacen valer

**`age` es asimétrico.** En 10.0.0.39 solo vive la clave PÚBLICA (`/root/.age-dgl.pub`). Quien
comprometa esa máquina encuentra con qué cifrar y **no puede leer nada de lo que ya está en B2**. La
privada existe únicamente en 1Password. Con `gpg` simétrico la contraseña estaría en el disco y esa
propiedad se pierde.

**La clave de B2 no sabe borrar.** `listBuckets,listFiles,readFiles,writeFiles`, sin `deleteFiles`,
acotada al bucket `dglweb`. Si el borrado lo hiciera el script haría falta darle ese permiso, y las
tres copias volverían al mismo dominio de confianza — que es justo lo que esta tercera viene a romper.

Tampoco puede tocar la regla de ciclo de vida: sin eso, un atacante la pondría en un día y esperaría.

### Restaurar desde B2

En `docs/RESTAURAR.md`, con el comando que pide la clave por el prompt sin que toque el disco ni el
historial.

**Probado el 2026-07-30**, de punta a punta: subida, descarga, descifrado con la clave de 1Password y
listado del contenido. Eso es lo que distingue esta copia de una carpeta que crece — una copia cifrada
que nadie ha intentado descifrar es exactamente igual de inútil que no tenerla.

**La prueba trimestral incluye repetir esto**, no solo restaurar la copia local.

## Lo que este montaje NO cubre

Los ACCESOS —variables de Portainer, AWS, RackNerd, la clave SSH, GitHub, DuckDNS, Umami, X y Kuma—
ya no faltan: están en 1Password desde el 2026-07-30. Y siguen sin ir en el respaldo a propósito: un
volcado con credenciales dentro convierte cada copia en un problema, y las copias se multiplican.
