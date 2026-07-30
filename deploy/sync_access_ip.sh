#!/bin/bash
# Sincroniza la IP del dueño en los TRES sitios que no cubría el cron de nginx.
#
#   sync_access_ip.sh 73.244.42.221
#
# Lo llama `change_nginx_allow_ip.sh` al final, pasándole la IP que ya resolvió por DuckDNS. También
# se puede correr a mano — es idempotente: si nada cambió, no toca nada y no recarga nada.
#
#
# POR QUÉ UN SCRIPT APARTE Y NO MÁS LÍNEAS EN EL DE NGINX
# --------------------------------------------------------
# Aquel funciona y lleva tiempo funcionando. Su `awk` está afinado para insertar `allow`/`deny all` al
# nivel del `server`, que es lo que necesitan portainer y pgadmin —sitios privados enteros—, y meterle
# más responsabilidades es arriesgar lo que ya está probado.
#
# Acá no hay nada que parsear: el `include` de nginx hizo que la IP viva en UNA línea de UN archivo.
#
#
# QUÉ AGUJERO CIERRA, Y NO ES EL DE NGINX
# ----------------------------------------
# El 2026-07-30 se vio que la IP estaba en cuatro sitios y el cron actualizaba dos. Los otros dos —el
# CMS de dglweb y el panel de Revive— seguían funcionando de casualidad. Eso ya está resuelto con el
# `include`.
#
# Pero había DOS sitios más que nadie miraba, y son los que de verdad muerden:
#
#   * `ignoreip` de fail2ban. Con la IP vieja, fail2ban NO te reconoce y **puede banearte**. Con
#     `nginx-404-scan` y `sshd` en cinco intentos, un rato probando URLs o dos SSH fallidos te meten
#     en el cortafuegos 12 o 24 horas — y el baneo es por IP, así que pierdes el sitio, el CMS y SSH
#     de una vez.
#
#   * La regla de ufw del 22. Menos grave: el puerto también está con `LIMIT` desde cualquier sitio,
#     así que se entra igual. Se sincroniza por coherencia, no porque bloquee.
#
# Y UN CASO QUE PARECE RARO Y NO LO ES: se pide `unban` de la IP nueva. Las IP residenciales rotan, así
# que se puede heredar una que un escáner quemó horas antes. Sin esto, el sitio simplemente no cargaría
# y no habría ninguna pista de por qué.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Hay que correrlo como root"; exit 1; }

IP="${1:-}"
[[ "$IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || { echo "IP inválida: '$IP'"; exit 1; }
IFS='.' read -r o1 o2 o3 o4 <<< "$IP"
((o1 <= 255 && o2 <= 255 && o3 <= 255 && o4 <= 255)) || { echo "Octetos fuera de rango: '$IP'"; exit 1; }

SNIPPET="/etc/nginx/snippets/ip-del-dueno.conf"
JAIL="/etc/fail2ban/jail.local"

# Lo que SIEMPRE va en `ignoreip`, aparte de la IP de casa. Si algún día hay que añadir algo fijo —el
# rango del tailnet, otra oficina— se añade acá y no a mano en `jail.local`: este script reescribe esa
# línea entera, así que una edición manual se perdería en la siguiente corrida sin avisar.
IGNORE_FIJAS="127.0.0.1/8 ::1"

LOG_DIR="/var/log/change_nginx_allow_ip"
mkdir -p "$LOG_DIR" && chmod 700 "$LOG_DIR"
log() { echo "[$(date '+%F %T')] sync_access_ip: $1" | tee -a "$LOG_DIR/update-$(date +%F).log" >/dev/null; }

# ── nginx: el snippet que incluyen el CMS y el panel de Revive ──────────────────────────────────
if [[ -f "$SNIPPET" ]]; then
    IP_VIEJA="$(grep -oE '^allow[[:space:]]+([0-9]{1,3}\.){3}[0-9]{1,3}' "$SNIPPET" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' || true)"
    if [[ "$IP_VIEJA" != "$IP" ]]; then
        cp -a "$SNIPPET" "$SNIPPET.backup-$(date +%Y%m%d-%H%M%S)"
        # Solo la línea que EMPIEZA por `allow`: los comentarios de arriba no se tocan.
        sed -i -E "s|^allow[[:space:]]+([0-9]{1,3}\.){3}[0-9]{1,3};|allow ${IP};|" "$SNIPPET"

        # `nginx -t` ANTES de recargar, siempre. Si algo quedó mal, nginx sigue sirviendo con lo que
        # tenía y el error queda en el log — en vez de tumbar cuatro sitios de madrugada.
        if nginx -t 2>/dev/null; then
            systemctl reload nginx
            log "nginx: $IP_VIEJA → $IP (recargado)"
        else
            log "ERROR: nginx -t falló tras cambiar el snippet. NO se recargó."
            exit 1
        fi
    fi
else
    log "AVISO: no existe $SNIPPET — el CMS y Revive no están usando el include"
fi

# ── fail2ban: que no te banee a ti ──────────────────────────────────────────────────────────────
if [[ -f "$JAIL" ]]; then
    DESEADA="ignoreip = ${IGNORE_FIJAS} ${IP}"
    if ! grep -qxF "$DESEADA" "$JAIL"; then
        cp -a "$JAIL" "$JAIL.backup-$(date +%Y%m%d-%H%M%S)"
        sed -i -E "s|^ignoreip[[:space:]]*=.*|${DESEADA}|" "$JAIL"
        fail2ban-client reload >/dev/null
        log "fail2ban: ignoreip → $IP (recargado)"
    fi
    # Idempotente y barato: si no estaba baneada, no hace nada.
    fail2ban-client unban "$IP" >/dev/null 2>&1 || true
fi

# ── ufw: el atajo del 22 ────────────────────────────────────────────────────────────────────────
#
# No bloquea nada por sí solo —el 22 también está con `LIMIT` desde cualquier sitio— así que un fallo
# acá no puede dejar a nadie fuera. Por eso va al final y no aborta el script.
# LA IP SE BUSCA EN LA LÍNEA, NO EN UNA COLUMNA FIJA, y esa es la corrección del primer intento:
# `ufw status` imprime tres columnas —`22/tcp  ALLOW  1.2.3.4`— y `ufw status verbose` imprime cuatro,
# porque ahí la acción es `ALLOW IN`. Miré el formato de `verbose`, escribí `$4`, y con el formato real
# no casaba nada: añadía la regla nueva y dejaba la vieja puesta. Se vio comprobando la salida.
if command -v ufw >/dev/null && ufw status | grep -q "^Status: active"; then
    reglas_del_22() {
        ufw status | awk '/^22\/tcp/ && /ALLOW/ {
            for (i = 1; i <= NF; i++) if ($i ~ /^([0-9]{1,3}\.){3}[0-9]{1,3}$/) print $i
        }'
    }
    if ! reglas_del_22 | grep -qxF "$IP"; then
        ufw allow from "$IP" to any port 22 proto tcp >/dev/null 2>&1 || true
        log "ufw: añadida la regla del 22 para $IP"
    fi
    # Las sobrantes se limpian SIEMPRE, no solo cuando se añade una: si un intento anterior dejó una
    # colgada, esto la recoge en la siguiente corrida en vez de acumularlas para siempre.
    for vieja in $(reglas_del_22); do
        [[ "$vieja" == "$IP" ]] && continue
        ufw --force delete allow from "$vieja" to any port 22 proto tcp >/dev/null 2>&1 || true
        log "ufw: borrada la regla del 22 de $vieja"
    done
fi
