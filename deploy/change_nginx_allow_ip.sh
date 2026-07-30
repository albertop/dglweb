#!/bin/bash
# Script para actualizar automáticamente la IP permitida en la configuración de Nginx
# Útil para dominios con IP dinámica (como DuckDNS)
#
# ──────────────────────────────────────────────────────────────────────────────────────────────────
# VIVE EN `/usr/local/bin/change_nginx_allow_ip.sh` Y LO DISPARA EL CRON DE root.
#
#   sudo install -m 755 deploy/change_nginx_allow_ip.sh /usr/local/bin/change_nginx_allow_ip.sh
#
# Se versiona acá porque estaba SOLO en el servidor. Es el que decide quién puede entrar al CMS, a
# Revive, a Portainer y a pgAdmin: si el VPS se reinstala, esto es de las primeras cosas que hacen
# falta y de las que nadie se acuerda.
#
# `sync_access_ip.sh` NO TIENE ENTRADA PROPIA EN EL CRON, y no es un olvido. La cadena es:
#
#     crontab  →  change_nginx_allow_ip.sh  →  (al final)  sync_access_ip.sh "$NEW_IP"
#
# La IP la resuelve ESTE script con `dig` a DuckDNS. Con una entrada de cron propia, el otro tendría
# que resolverla por su cuenta — dos consultas, y dos valores distintos si el cambio de IP cae justo
# entre las dos. Encadenado hay UNA resolución, y el segundo trabaja con exactamente la misma IP que
# el primero acaba de aplicar a nginx. Además hereda el `flock` de acá, así que no pueden solaparse.
#
# QUÉ CUBRE CADA UNO, que es lo que se entendió mal durante meses:
#
#     este script          portainer.conf y pgadmin.conf — sitios privados ENTEROS
#     sync_access_ip.sh    el snippet (CMS + Revive), el `ignoreip` de fail2ban, la regla de ufw
#
# Y NO SE LE AÑADEN LOS CONF DE dglweb A `CFG_FILES`. Es lo primero que uno piensa y sería un
# desastre: el `awk` de abajo trabaja al nivel del `server`, porque portainer y pgadmin son privados
# de arriba abajo. En dglweb la restricción vive DENTRO de un `location` —solo `/cms` y
# `/django-admin`—, así que el `awk` no encontraría el `allow` donde lo busca, creería que falta, y lo
# insertaría en la raíz del `server`: **el sitio público entero cerrado al mundo salvo una IP**, con
# `nginx -t` en verde porque la sintaxis sería impecable. Para eso está el `include` del snippet.
# ──────────────────────────────────────────────────────────────────────────────────────────────────
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }

# Lockfile para prevenir ejecuciones concurrentes
LOCKFILE="/var/run/change_nginx_ip.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { echo "Script already running" >&2; exit 1; }
trap 'rm -f "$LOCKFILE"' EXIT

CFG_FILES=(
  "/etc/nginx/sites-available/portainer.conf"
  "/etc/nginx/sites-available/pgadmin.conf"
)
SERVER_NAMES=(
  "docker.prdm0.com"
  "pgadmin.prdm0.com"
)

[[ ${#CFG_FILES[@]} -eq ${#SERVER_NAMES[@]} ]] || { echo "CFG_FILES and SERVER_NAMES length mismatch"; exit 1; }

HOST="10860.duckdns.org"
LOG_DIR="/var/log/change_nginx_allow_ip"
LOG_FILE="$LOG_DIR/update-$(date '+%Y-%m-%d').log"

# Crear directorio de logs si no existe y asignar permisos seguros
if [[ ! -d "$LOG_DIR" ]]; then
  mkdir -p "$LOG_DIR"
  chmod 700 "$LOG_DIR"
  chown root:root "$LOG_DIR"
fi

# Eliminar logs más antiguos que 7 días
find "$LOG_DIR" -name "update-*.log" -type f -mtime +7 -delete

log_message() {
  if [[ ! -f "$LOG_FILE" ]]; then
    touch "$LOG_FILE"
    chmod 600 "$LOG_FILE"
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE" > /dev/null
}

command -v dig >/dev/null 2>&1 || { log_message "ERROR: 'dig' is not installed or not in PATH"; exit 1; }

NEW_IP="$(dig +time=2 +tries=1 +short A "$HOST" @1.1.1.1 | head -n1 | tr -d '[:space:]')"

if [[ ! "$NEW_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  log_message "ERROR: dig returned invalid IP format: '$NEW_IP'"
  exit 1
fi

IFS='.' read -r o1 o2 o3 o4 <<< "$NEW_IP"
if ((o1 > 255 || o2 > 255 || o3 > 255 || o4 > 255)); then
  log_message "ERROR: dig returned invalid IP octets: '$NEW_IP'"
  exit 1
fi

UPDATED=false

for IDX in "${!CFG_FILES[@]}"; do
  CFG="${CFG_FILES[$IDX]}"
  TARGET_SERVER="${SERVER_NAMES[$IDX]}"

  if [[ ! -f "$CFG" ]]; then
    log_message "WARNING: Config file not found: $CFG"
    continue
  fi

  if awk -v new_ip="$NEW_IP" -v target="$TARGET_SERVER" '
    function brace_delta(s,    t, o, c) {
      t=s; o=gsub(/\{/, "", t); c=gsub(/\}/, "", t); return o-c
    }
    function print_server_block(    i, top_depth, allow_seen, deny_count, inserted, line, depth_at) {
      top_depth = server_start_depth + 1
      allow_seen = 0
      deny_count = 0
      inserted = 0

      for (i=1; i<=n; i++) {
        line = lines[i]
        depth_at = depths[i]

        if (target_block) {
          if (depth_at == top_depth && line ~ /^\s*allow\s+[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+;/) {
            if (!allow_seen) {
              sub(/[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/, new_ip, line)
              allow_seen = 1
            }
            print line
            continue
          }

          if (depth_at == top_depth && line ~ /^\s*deny\s+all;/) {
            deny_count++
            if (deny_count > 1) {
              continue
            }
            if (!allow_seen) {
              print "  allow " new_ip ";"
              allow_seen = 1
            }
            print line
            continue
          }

          if (depth_at == top_depth && line ~ /^\s*location/ && !inserted) {
            if (!allow_seen) {
              if (deny_count == 0) {
                print "  # Lock to your IP"
              }
              print "  allow " new_ip ";"
              allow_seen = 1
            }
            if (deny_count == 0) {
              print "  deny all;"
              deny_count = 1
            }
            inserted = 1
          }

          if (depth_at == top_depth && line ~ /^\s*\}/ && !inserted) {
            if (!allow_seen) {
              if (deny_count == 0) {
                print "  # Lock to your IP"
              }
              print "  allow " new_ip ";"
              allow_seen = 1
            }
            if (deny_count == 0) {
              print "  deny all;"
              deny_count = 1
            }
            inserted = 1
          }
        }

        print line
      }
    }
    BEGIN {
      depth=0; in_server=0; server_start_depth=0;
      listen_443=0; target_server=0; target_block=0;
      found_target=0; n=0;
    }
    {
      line=$0
      delta=brace_delta(line)

      if (!in_server && line ~ /^\s*server\s*\{/) {
        in_server=1
        server_start_depth=depth
        listen_443=0
        target_server=0
        target_block=0
        n=0
      }

      if (in_server) {
        n++
        lines[n]=line
        depths[n]=depth

        if (line ~ /^\s*server_name\s+/) {
          for (i=2; i<=NF; i++) {
            name=$i
            sub(/;$/, "", name)
            if (name == target) target_server=1
          }
        }

        if (line !~ /^\s*#/ && line ~ /^\s*listen[[:space:]]+/ && line ~ /(^|[^0-9])443([^0-9]|$)/) {
          listen_443=1
        }

        depth += delta

        if (depth <= server_start_depth) {
          in_server=0
          target_block = (target_server && listen_443)
          if (target_block) { found_target=1 }
          print_server_block()
        }
        next
      }

      print line
      depth += delta
    }
    END { exit(found_target ? 0 : 1) }
  ' "$CFG" > "$CFG.tmp"; then
    if cmp -s "$CFG" "$CFG.tmp"; then
      rm -f "$CFG.tmp"
      log_message "No changes needed for $CFG"
    else
      cp -f "$CFG" "$CFG.backup-$(date +%Y%m%d-%H%M%S)"
      mv "$CFG.tmp" "$CFG"
      log_message "Updated access rules in $CFG"
      UPDATED=true
    fi
  else
    rm -f "$CFG.tmp"
    log_message "ERROR: Cannot update allow/deny for $CFG (target server_name: $TARGET_SERVER)"
    exit 1
  fi
done

if [[ "$UPDATED" == true ]]; then
  if nginx -t 2>&1 | tee -a "$LOG_FILE" > /dev/null; then
    systemctl reload nginx
    log_message "Nginx configuration reloaded successfully"
    for CFG in "${CFG_FILES[@]}"; do
      find "$(dirname "$CFG")" -name "*.backup-*" -type f -mtime +7 -delete 2>/dev/null || true
    done
  else
    log_message "ERROR: Nginx configuration test failed - configs NOT reloaded. Backups preserved."
    exit 1
  fi
fi

# ── Anadido 2026-07-30 ──────────────────────────────────────────────────────────
#
# La IP del dueno vivia en CUATRO sitios y este script actualizaba dos. Los otros
# —el snippet que incluyen el CMS y el panel de Revive, el ignoreip de fail2ban y
# la regla de ufw del 22— los sincroniza sync_access_ip.sh con la IP que este ya
# resolvio por DuckDNS.
#
# El de fail2ban era el que mordia: con una IP vieja alli, fail2ban no reconoce al
# dueno y puede banearlo — y el baneo es por IP, asi que se pierden el sitio, el
# CMS y SSH de una vez.
#
# Va aparte y no como mas lineas aqui porque el awk de arriba esta afinado para
# insertar allow/deny al nivel del `server`, que es lo que necesitan portainer y
# pgadmin. Ahi no hay nada que tocar.
#
# `|| true` para que un fallo suyo no rompa la parte de nginx, que es la critica.
if [[ -x /usr/local/bin/sync_access_ip.sh ]]; then
  /usr/local/bin/sync_access_ip.sh "$NEW_IP" \
    || log_message "WARNING: sync_access_ip.sh fallo para $NEW_IP"
fi
