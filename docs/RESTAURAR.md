# Cómo restaurar

Esto se lee un mal día. Está ordenado para seguirlo de arriba abajo sin tener que entender antes cómo
funciona el respaldo — eso está en `docs/RESPALDO.md` y no hace falta para usar esto.

**Lo primero, siempre: no borres nada todavía.** Casi ningún escenario de los de abajo mejora
borrando algo, y varios empeoran. Si el sitio está caído, seguirá caído diez minutos más mientras se
mira qué pasó de verdad.

## Dónde están las copias

| dónde | cuánto guarda | cómo se llega |
|---|---|---|
| VPS, `/srv/respaldos` | **3 corridas** | ya estás ahí |
| 10.0.0.39, `/srv/respaldos-dgl` | **14 diarias + 8 semanales** | es la casa |
| Backblaze B2, bucket `dglweb` | **90 días**, cifradas | `b2 file download` + `age` |

Cada corrida es una carpeta `AAAA-MM-DD_HHMM` con estos archivos:

```
dglweb.dump                 la base del sitio
revive.dump                 campañas y estadísticas del anunciante
globales.sql                los roles de Postgres, con sus contraseñas
media.tgz  uploads.tgz      lo que subió el editor desde el CMS
revive_revive_images.tgz    las creatividades del anunciante
revive_revive_var.tgz       la configuración de Revive
letsencrypt.tgz             los certificados
MANIFIESTO                  sha256 de todo lo anterior
```

**Antes de usar cualquier copia, comprueba que está entera:**

```bash
cd <la-carpeta> && sha256sum -c MANIFIESTO
```

Si falla, usa la anterior. Restaurar desde un respaldo corrupto es la única forma de empeorar un mal
día.

---

## Escenario 1 — Se borró algo de la base y el sitio funciona

El más común, y **el que no se arregla restaurando encima**. Restaurar `dglweb.dump` completo tira
todo lo que pasó desde el respaldo.

Levanta la copia **al lado**, en una base aparte, y saca solo lo que falta:

```bash
docker exec postgres-postgres-1 createdb -U postgres rescate
docker cp dglweb.dump postgres-postgres-1:/tmp/
docker exec postgres-postgres-1 pg_restore -U postgres -d rescate /tmp/dglweb.dump
```

Ahora `rescate` tiene la foto de esa noche. Copia las filas que hagan falta con un `INSERT … SELECT`
entre bases, o exporta esa tabla suelta:

```bash
docker exec postgres-postgres-1 pg_restore -U postgres -d dglweb -t <tabla> --data-only /tmp/dglweb.dump
```

Cuando termines, `dropdb rescate`.

---

## Escenario 2 — La base entera está perdida o corrupta

```bash
# 1. LOS ROLES PRIMERO. Sin esto, el paso 2 falla en el primer `OWNER TO dglweb`.
docker exec -i postgres-postgres-1 psql -U postgres < globales.sql
```

**Va a dar errores de `role "dglweb" already exists` si la instancia ya lo tenía. Eso es normal y no
importa**: el `CREATE ROLE` falla, el `ALTER ROLE … PASSWORD` de la línea siguiente sí se aplica, y esa
es la que importa. No uses `ON_ERROR_STOP` acá.

```bash
# 2. La base. `-C` la crea; si ya existe, bórrala antes o el restore se mezcla con lo que hay.
docker exec postgres-postgres-1 dropdb -U postgres --if-exists dglweb
docker cp dglweb.dump postgres-postgres-1:/tmp/
docker exec postgres-postgres-1 pg_restore -U postgres -C -d postgres /tmp/dglweb.dump

# 3. Comprobar antes de cantar victoria.
docker exec postgres-postgres-1 psql -U postgres -d dglweb -Atc \
  "select count(*) from articles_articlepage"
```

Si el conteo es 0, algo salió mal aunque `pg_restore` no protestara.

**La de Revive va igual**, cambiando `dglweb` por `revive`. No la olvides: es la instancia compartida,
y sin ella el anunciante pierde sus campañas y sus informes.

---

## Escenario 3 — Se perdieron las imágenes del CMS

```bash
tar xzf media.tgz --numeric-owner -C /srv/dglweb-datos
tar xzf uploads.tgz --numeric-owner -C /srv/dglweb-datos
```

**`--numeric-owner` NO ES OPCIONAL, y es el error más caro de este documento.**

Este VPS corre Docker con `userns-remap`, así que esas carpetas pertenecen al uid **101000** —el
`appuser` del contenedor visto desde el anfitrión— y ese uid no tiene entrada en `/etc/passwd`. Sin la
bandera, `tar` restaura por NOMBRE de usuario, no lo encuentra, y los archivos acaban en `root`.

Y si acaban en `root`, **los archivos vuelven y el CMS no puede subir ni borrar ninguna imagen**. El
sitio se ve perfecto; el editor descubre el problema días después. Costó una tarde el 2026-07-28.

Se comprueba así:

```bash
ls -n /srv/dglweb-datos/media | head -3     # el uid tiene que ser 101000, no 0
```

---

## Escenario 4 — Revive perdió su configuración o sus creatividades

```bash
docker compose -f deploy/adserver/stack.yml down     # o parar el stack en Portainer
tar xzf revive_revive_var.tgz    --numeric-owner -C /var/lib/docker/volumes/
tar xzf revive_revive_images.tgz --numeric-owner -C /var/lib/docker/volumes/
```

**`revive_var` importa tanto como las imágenes.** Si falta, Revive vuelve a la pantalla de instalación
con la base llena de campañas — y la contraseña de Postgres que guarda dentro tiene que seguir
coincidiendo con la del rol. Si restauraste la base con `globales.sql` de la misma corrida, coincide.

`revive_images` es **lo único verdaderamente irreemplazable de todo el sistema**: la base se
reconstruye, un banner que un cliente mandó por correo hace ocho meses no.

---

## Escenario 5 — El VPS entero, desde cero

El orden importa. Cada paso depende del anterior.

**Lo que hace falta antes de empezar**, y ninguna de las tres cosas está en el servidor:

| dónde | qué |
|---|---|
| **1Password** | RackNerd, AWS (DNS), la clave SSH, Portainer, y **los valores de las variables de los stacks** |
| **git** | `deploy/` — stacks, nginx, fail2ban, scripts |
| **el respaldo** | los datos |

```bash
# 1. Servidor nuevo en RackNerd. Apuntar el DNS de AWS a la IP nueva — los seis dominios.
#    Hasta que el DNS propague, Certbot no puede emitir nada.

# 2. Docker, y la red que comparten los tres stacks.
docker network create backend

# 3. El repositorio y los directorios de datos.
git clone git@github.com:albertop/dglweb.git /srv/dglweb
mkdir -p /srv/dglweb-datos/{media,uploads,mugshots} /srv/postgres/init

# 4. El init de Postgres ANTES de levantar la base: solo corre con el volumen vacío,
#    y si falta, `migrate` revienta después en `players/0005_unaccent.py`.
install -m 755 /srv/dglweb/deploy/postgres/init/10-dglweb.sh /srv/postgres/init/

# 5. Los tres stacks en Portainer, con sus variables sacadas de 1Password.
#    Postgres primero; dglweb y Revive dependen de él.

# 6. Restaurar los datos: escenarios 2, 3 y 4 de arriba, en ese orden.

# 7. nginx y los certificados.
tar xzf letsencrypt.tgz --numeric-owner -C /etc
cp /srv/dglweb/deploy/nginx.conf /etc/nginx/nginx.conf
cp /srv/dglweb/deploy/nginx-limites.conf   /etc/nginx/conf.d/limites.conf
cp /srv/dglweb/deploy/nginx-hardening.conf /etc/nginx/conf.d/hardening.conf
cp /srv/dglweb/deploy/nginx-keepalive.conf /etc/nginx/conf.d/keepalive.conf
install -D -m 644 /srv/dglweb/deploy/nginx-ip-del-dueno.conf /etc/nginx/snippets/ip-del-dueno.conf
cp /srv/dglweb/deploy/nginx-dglweb.conf   /etc/nginx/sites-available/dominicanosengrandesligas.com
cp /srv/dglweb/deploy/adserver/nginx-promo.conf /etc/nginx/sites-available/promo.dominicanosengrandesligas.com
cp /srv/dglweb/deploy/nginx-pgadmin.conf  /etc/nginx/sites-available/pgadmin.conf
cp /srv/dglweb/deploy/nginx-portainer.conf /etc/nginx/sites-available/portainer.conf
# enlazar los que toque en sites-enabled/, y solo entonces:
nginx -t && systemctl reload nginx

# 8. Los estáticos, que no están en el respaldo: salen de la imagen.
/srv/dglweb/deploy/estaticos.sh <version>

# 9. fail2ban, cortafuegos y el cron de la IP.
install -D -m 644 /srv/dglweb/deploy/fail2ban/filter.d/nginx-404-scan.conf /etc/fail2ban/filter.d/
install -m 644 /srv/dglweb/deploy/fail2ban/jail.local /etc/fail2ban/jail.local
install -m 644 /srv/dglweb/deploy/fail2ban/jail.d/nginx.local /etc/fail2ban/jail.d/nginx.local
install -m 755 /srv/dglweb/deploy/change_nginx_allow_ip.sh /usr/local/bin/
install -m 755 /srv/dglweb/deploy/sync_access_ip.sh /usr/local/bin/
/usr/local/bin/change_nginx_allow_ip.sh      # pone la IP del dueño en los cinco sitios
fail2ban-client reload

# 10. El drop-in que reinicia el scheduler cuando arranca el demonio de Docker.
#     NO es opcional: sin él, cualquier reinicio de `docker.service` —una actualización
#     automática de paquetes basta— deja el pipeline sin correr y sin avisar. El porqué,
#     con las horas medidas del incidente, está dentro del propio archivo.
mkdir -p /etc/systemd/system/docker.service.d
install -m 644 /srv/dglweb/deploy/systemd/reiniciar-scheduler.conf \
               /etc/systemd/system/docker.service.d/reiniciar-scheduler.conf
systemctl daemon-reload

# 11. Y volver a montar el respaldo, que ahora apunta a un servidor nuevo:
#     la clave pública de 10.0.0.39 en `authorized_keys` con su `command="rrsync -ro …"`.
```

**Lo que NO hay que restaurar**: los retratos (`mugshots/`) se regeneran con el script de descarga, y
la imagen de Docker se reconstruye con `deploy_dglweb_image.sh`.

---

## Traer una copia desde B2

Cuando el VPS y la casa no sirvan, o para la prueba trimestral.

```bash
b2 file download "b2://dglweb/AAAA-MM-DD_HHMM.tar.age" /tmp/x.tar.age
```

Descifrar **sin que la clave toque el disco ni el historial** — se pide por el prompt y viaja por un
descriptor de `/dev/fd`:

```bash
sudo bash -c 'read -rsp "Clave privada: " K; echo; age -d -i <(printf "%s\n" "$K") /tmp/x.tar.age | tar -xf - -C /destino'
```

La clave privada (`AGE-SECRET-KEY-…`) **solo existe en 1Password**. No está en el VPS ni en 10.0.0.39
—allí vive únicamente la pública, que solo sirve para cifrar—, y eso es deliberado: quien comprometa
cualquiera de las dos máquinas no puede leer nada de lo que está en B2.

Si `age` dice `no identity matched any of the recipients`, la clave no es la que cifró ese archivo.
No hay forma de recuperarlo sin ella.

---

## La prueba trimestral

Un respaldo que nunca se restauró es una suposición. **Cada tres meses**, y anotado en
`docs/RESPALDO.md` con fecha y resultado:

1. Bajar la última copia **de B2** y descifrarla — así se prueban las tres capas de una vez.
2. Levantar un Postgres aparte y restaurar `globales.sql` y `dglweb.dump`.
3. Arrancar el sitio contra esa base y **abrir un artículo con foto**.

El paso 3 es el que cuenta. Que `pg_restore` no dé error solo dice que el archivo se leyó; abrir un
artículo con foto comprueba de una vez la base, los medios y los permisos de los archivos — que son
las tres cosas que se rompen por separado y solo se notan juntas.
