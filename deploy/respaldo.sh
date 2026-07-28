#!/bin/bash
# Respaldo diario de producción: la base y lo que subió el editor.
#
# QUÉ SE RESPALDA Y QUÉ NO
# ------------------------
# La base y `media/`. Los RETRATOS no: son 1.970 archivos que se regeneran con el script de descarga
# del dueño, y meterlos multiplicaría por seis el tamaño del respaldo para guardar algo reproducible.
#
# De lo que sí entra, lo verdaderamente irremplazable son los artículos y sus fotos: las estadísticas
# se pueden reconstruir desde el proxy o desde DGL, pero lo que escribió una persona en el CMS solo
# existe acá.
#
# POR QUÉ `pg_dump` Y NO UN RESPALDO DEL VOLUMEN
# ----------------------------------------------
# Copiar los archivos de Postgres en caliente da una copia inconsistente: hay que parar la base o
# usar herramientas de nivel de bloque. `pg_dump` es consistente por diseño —trabaja dentro de una
# transacción— y con 8 MB comprimidos no hay razón para complicarlo.

set -euo pipefail

DESTINO="${DESTINO:-/srv/respaldos}"
DIAS="${DIAS:-30}"
FECHA=$(date +%Y-%m-%d_%H%M)
CONTENEDOR_DB="postgres-postgres-1"

mkdir -p "$DESTINO"

# 1. La base. `-Fc` es el formato comprimido de Postgres: pesa menos y permite restaurar tablas
#    sueltas, cosa que un `.sql` plano no.
docker exec "$CONTENEDOR_DB" pg_dump -U postgres -d dglweb -Fc -f /tmp/respaldo.dump
docker cp "$CONTENEDOR_DB:/tmp/respaldo.dump" "$DESTINO/dglweb-$FECHA.dump"
docker exec "$CONTENEDOR_DB" rm -f /tmp/respaldo.dump

# 2. Lo que subió el editor.
tar czf "$DESTINO/media-$FECHA.tgz" -C /srv/dglweb-datos media

# 3. Podar. `-mtime` cuenta días completos; con 30 se guarda un mes.
find "$DESTINO" -name "dglweb-*.dump" -mtime "+$DIAS" -delete
find "$DESTINO" -name "media-*.tgz" -mtime "+$DIAS" -delete

# 4. VERIFICAR, que es la mitad que casi siempre falta. Un respaldo que no se puede leer no es un
#    respaldo, y eso solo se sabe intentándolo. `pg_restore -l` lee el índice del archivo: si está
#    truncado o corrupto, falla acá y no el día que haga falta de verdad.
TABLAS=$(docker run --rm -v "$DESTINO:/r:ro" postgres:18.4 pg_restore -l "/r/dglweb-$FECHA.dump" | grep -c "TABLE DATA")
tar tzf "$DESTINO/media-$FECHA.tgz" > /dev/null

echo "$(date '+%F %T')  ok  base=$(du -h "$DESTINO/dglweb-$FECHA.dump" | cut -f1) ($TABLAS tablas)  media=$(du -h "$DESTINO/media-$FECHA.tgz" | cut -f1)"

# 5. Si la verificación no cuadra, avisar por el mismo canal que todo lo demás. Un respaldo que falla
#    en silencio es exactamente el fallo que un respaldo viene a evitar.
if [ "$TABLAS" -lt 50 ]; then
    docker exec dglweb-web-live python manage.py shell -c "
from dglweb.core import notify
notify.enviar('⚠️ El respaldo de anoche salió con solo $TABLAS tablas. Revisar /srv/respaldos.')
" || true
    exit 1
fi
