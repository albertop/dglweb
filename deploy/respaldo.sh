#!/bin/bash
# Respaldo diario de producción. Corre en el VPS; 10.0.0.39 viene a buscarlo después.
#
#   sudo install -m 755 deploy/respaldo.sh /usr/local/bin/respaldo.sh
#
#
# ESTO ES LA MITAD DE UN RESPALDO, Y LA MENOS IMPORTANTE
# -------------------------------------------------------
# Escribe en `/srv/respaldos`, o sea EN EL MISMO DISCO QUE PRETENDE PROTEGER. Eso cubre borrar una
# tabla por error y no cubre nada de lo que de verdad se teme. Lo que hace que esto sea un respaldo es
# que **10.0.0.39 se lo lleva cada noche**; acá solo se guardan tres corridas, como área de paso.
#
# LA CASA VA A BUSCAR, EL VPS NO EMPUJA. Con push, el VPS tendría credenciales para escribir en casa —
# y quien comprometa el VPS borraría los respaldos antes de cifrar nada, que es como opera el
# ransomware actual. Con pull, el VPS no sabe que las copias existen.
#
#
# CADA CORRIDA ES UNA CARPETA, Y SE PUBLICA CON UN SOLO `mv`
# -----------------------------------------------------------
# Se construye todo en `.trabajo/` y al final se mueve la carpeta entera a su nombre definitivo. Un
# `mv` dentro del mismo sistema de archivos es ATÓMICO, así que quien viene a buscar nunca puede
# encontrarse un volcado a medio escribir.
#
# Sin esto, el `rsync` de casa que caiga a mitad del volcado se lleva un archivo truncado — y como
# `rsync` compara por tamaño y fecha, en la siguiente pasada podría darlo por bueno y no volver a
# copiarlo. Un respaldo corrupto que nadie vuelve a tocar es peor que no tenerlo.
#
#
# EL MANIFIESTO SE ESCRIBE AL FINAL, A PROPÓSITO
# ------------------------------------------------
# `MANIFIESTO` lleva el sha256 de cada archivo y es lo ÚLTIMO que se crea. Su presencia es la señal de
# «esta corrida terminó bien», y sus sumas permiten que el otro lado compruebe que lo que llegó es lo
# que salió. La verificación de acá dice que el archivo se generó bien; la de allá, que viajó bien.
#
#
# EL VOLCADO CONTIENE CREDENCIALES. `globales.sql` trae los roles CON SUS HASHES de contraseña, y la
# base trae los correos de los usuarios del CMS. Por eso los secretos no se guardan además acá —van en
# el gestor de contraseñas— y por eso una copia en la nube tendría que ir cifrada.
set -euo pipefail

DESTINO="${DESTINO:-/srv/respaldos}"
CORRIDAS="${CORRIDAS:-3}"
FECHA=$(date +%Y-%m-%d_%H%M)
DB="postgres-postgres-1"
TRABAJO="$DESTINO/.trabajo"

avisar() {
    docker exec dglweb-web-live python manage.py shell -c "
from dglweb.core import notify
notify.enviar('''⚠️ $1''')" >/dev/null 2>&1 || true
}

# CUALQUIER fallo avisa. Sin esto, `set -e` corta el script en silencio y el respaldo simplemente deja
# de existir — que es justo el modo de fallo que un respaldo viene a evitar.
trap 'avisar "El respaldo del VPS falló en la línea $LINENO. Revisar /srv/respaldos."' ERR

rm -rf "$TRABAJO"
mkdir -p "$TRABAJO"

# ── 1. Postgres ─────────────────────────────────────────────────────────────────────────────────
#
# LAS DOS BASES. La instancia la comparten dglweb y Revive: un volcado solo de `dglweb` deja fuera las
# campañas y las estadísticas que se le facturan al anunciante.
#
# `-Fc` es el formato comprimido de Postgres: pesa menos que un `.sql` y permite restaurar tablas
# sueltas. Y es consistente por diseño —trabaja dentro de una transacción— así que no hay que parar
# nada: copiar los archivos del volumen en caliente sí daría una copia rota.
for base in dglweb revive; do
    docker exec "$DB" pg_dump -U postgres -d "$base" -Fc -f "/tmp/$base.dump"
    docker cp "$DB:/tmp/$base.dump" "$TRABAJO/$base.dump"
    docker exec "$DB" rm -f "/tmp/$base.dump"
done

# LOS ROLES, que `pg_dump` NO incluye. Sin esto, restaurar en una instancia nueva falla al primer
# `OWNER TO dglweb`: el rol no existe. Es el detalle que convierte una restauración de diez minutos en
# una tarde de averiguar por qué.
docker exec "$DB" pg_dumpall -U postgres --globals-only > "$TRABAJO/globales.sql"

# ── 2. Lo que no está en ninguna imagen ni en git ────────────────────────────────────────────────
#
# `--numeric-owner` NO es un detalle. Este VPS corre Docker con `userns-remap`, así que estas carpetas
# pertenecen al uid 101000 —el `appuser` del contenedor visto desde el anfitrión— y ESE uid no tiene
# entrada en `/etc/passwd`. Sin la bandera, `tar` guarda y restaura por NOMBRE de usuario, y al
# restaurar un dueño sin nombre el resultado depende de la versión: puede acabar en root.
#
# Y si acaba en root, los archivos vuelven pero el CMS no puede subir ni borrar ninguna imagen —el
# fallo que costó una tarde el 2026-07-28— justo el día que uno restaura, que es el peor día para
# descubrirlo. **Al restaurar hay que usar la misma bandera.**
tar czf "$TRABAJO/media.tgz"   --numeric-owner -C /srv/dglweb-datos media
tar czf "$TRABAJO/uploads.tgz" --numeric-owner -C /srv/dglweb-datos uploads

# LOS DOS VOLÚMENES DE REVIVE, y por motivos distintos:
#
#   revive_images   las creatividades que sube el anunciante. **Lo único verdaderamente
#                   irreemplazable de todo esto**: la base se reconstruye, un banner que un cliente
#                   mandó por correo hace ocho meses no. Hoy pesa 92 KB porque solo tiene las de
#                   prueba — es el que crece.
#
#   revive_var      la configuración que generó el instalador, CON la contraseña de Postgres dentro.
#                   Si se pierde, Revive vuelve a la pantalla de instalación con la base llena de
#                   campañas.
for v in revive_revive_images revive_revive_var; do
    punto=$(docker volume inspect -f '{{.Mountpoint}}' "$v")
    tar czf "$TRABAJO/$v.tgz" --numeric-owner -C "$(dirname "$punto")" "$(basename "$punto")"
done

# LOS CERTIFICADOS. Certbot puede reemitirlos con el desafío HTTP, así que perderlos es recuperable —
# pero en una reconstrucción se necesitan ANTES de que nginx arranque, y sin ellos no levanta ningún
# sitio del servidor. Pesa poco y evita un arranque en frío incómodo.
#
# SIN `-h`: los `live/*` son enlaces simbólicos a `archive/`, y hay que guardarlos COMO enlaces. Con
# `-h` se copiaría el contenido dos veces y se rompería la estructura que espera `certbot renew`.
tar czf "$TRABAJO/letsencrypt.tgz" --numeric-owner -C /etc letsencrypt

# ── 3. Verificar, que es la mitad que casi siempre falta ─────────────────────────────────────────
#
# Un respaldo que no se puede leer no es un respaldo, y eso solo se sabe intentándolo. `pg_restore -l`
# lee el índice del archivo: si está truncado o corrupto, falla acá y no el día que haga falta.
TABLAS=$(docker run --rm -v "$TRABAJO:/r:ro" postgres:18.4 pg_restore -l /r/dglweb.dump | grep -c "TABLE DATA")
docker run --rm -v "$TRABAJO:/r:ro" postgres:18.4 pg_restore -l /r/revive.dump >/dev/null
for t in "$TRABAJO"/*.tgz; do tar tzf "$t" >/dev/null; done

# EL UMBRAL NO ES ADORNO. Un volcado de una base VACÍA es un archivo válido de 20 KB que pasa todas las
# comprobaciones de arriba: `pg_restore -l` lo lee sin protestar. Contar tablas es lo único que
# distingue «se generó» de «se generó CON DATOS».
if [ "$TABLAS" -lt 50 ]; then
    avisar "El respaldo salió con solo $TABLAS tablas en dglweb. Revisar /srv/respaldos."
    exit 1
fi

# ── 4. Publicar de una sola vez ─────────────────────────────────────────────────────────────────
( cd "$TRABAJO" && sha256sum ./* > MANIFIESTO )
mv "$TRABAJO" "$DESTINO/$FECHA"

# ── 5. Podar ────────────────────────────────────────────────────────────────────────────────────
#
# Por NÚMERO de corridas y no por días: si el respaldo lleva una semana fallando, un `-mtime +3`
# borraría lo último bueno que queda. Contando carpetas, siempre sobreviven las tres últimas que
# existan, tengan la edad que tengan.
ls -1d "$DESTINO"/20*/ 2>/dev/null | sort -r | tail -n "+$((CORRIDAS + 1))" | xargs -r rm -rf

echo "$(date '+%F %T')  ok  $FECHA  $(du -sh "$DESTINO/$FECHA" | cut -f1)  ($TABLAS tablas)"
