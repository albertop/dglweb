#!/bin/bash
# El OTRO lado del respaldo. Corre en 10.0.0.39, no en el VPS.
#
#   sudo install -m 755 deploy/traer_respaldos.sh /usr/local/bin/traer_respaldos.sh
#   # en cron de 10.0.0.39:  0 7 * * *  /usr/local/bin/traer_respaldos.sh
#
#
# LA CASA VA A BUSCAR; EL VPS NO EMPUJA
# --------------------------------------
# Es la decisión de diseño que más pesa de todo esto. Con push, el VPS guardaría credenciales para
# escribir en esta máquina — y quien comprometa el VPS borraría los respaldos antes de cifrar nada,
# que es exactamente como opera el ransomware actual. Con pull, el VPS **no sabe que estas copias
# existen** y no tiene forma de alcanzarlas.
#
#
# LA CLAVE SSH VA RESTRINGIDA, Y ESO ES LA MITAD DE LA PROTECCIÓN
# ----------------------------------------------------------------
# En el VPS, `~/.ssh/authorized_keys` lleva esta línea:
#
#   command="rrsync -ro /srv/respaldos",no-pty,no-agent-forwarding,no-port-forwarding,no-X11-forwarding ssh-ed25519 AAAA…
#
# `rrsync` viene con rsync y está hecho para esto. Con `-ro`, esa clave solo puede LEER esa carpeta:
# aunque alguien se lleve la clave privada del disco de esta máquina, no obtiene una sesión en el VPS
# — obtiene leer unos respaldos que ya tiene.
#
# Sin el `command=`, esa misma clave sería acceso completo al servidor, guardado en una máquina de casa
# para que un cron lo use sin contraseña. Es la diferencia entre una llave de la casa y una del buzón.
#
#
# EL AVISO ES UN «HOMBRE MUERTO», NO UN MENSAJE DE ERROR
# --------------------------------------------------------
# Este script NO manda alertas cuando falla. Hace ping a un monitor **Push** de Uptime Kuma solo
# cuando todo salió bien, y es Kuma quien avisa si ese ping no llega.
#
# La razón es simple: **un script que se muere no puede avisar de que se murió**. Si la máquina está
# apagada, si el cron dejó de existir, si alguien renombró el archivo — un aviso escrito acá dentro no
# se envía nunca, y el silencio se lee igual que el éxito. Avisando por ausencia, los tres casos se
# ven.
#
# El monitor se crea en Kuma como tipo **Push**, con «Heartbeat Interval» de 2 días (172800 s): así un
# día saltado no despierta a nadie, pero dos seguidos sí.
set -euo pipefail

REMOTO="${REMOTO:-root@dominicanosengrandesligas.com}"
# LA RAIZ DE `rrsync`, QUE DESDE EL CLIENTE ES `/` Y NO LA RUTA REAL. El `command=` del VPS enraiza
# todo en `/srv/respaldos`, asi que pedir `:/srv/respaldos/` se resuelve como `/srv/respaldos` +
# `/srv/respaldos` y falla con un «No such file or directory» que manda a buscar al sitio equivocado.
# Solo se ve probando: la ruta que uno escribiria por logica es justo la que no funciona.
ORIGEN="${ORIGEN:-/}"
DESTINO="${DESTINO:-/srv/respaldos-dgl}"
CLAVE="${CLAVE:-/root/.ssh/respaldo_dgl}"
DIARIOS="${DIARIOS:-14}"
SEMANALES="${SEMANALES:-8}"
PUSH_KUMA="${PUSH_KUMA:-}"   # la URL del monitor Push; vacío = no se notifica

mkdir -p "$DESTINO"
cd "$DESTINO"

SSH="ssh -i $CLAVE -o BatchMode=yes -o ConnectTimeout=15"

# ── 1. Qué hay allá que no tengamos acá ─────────────────────────────────────────────────────────
#
# Se piden solo las carpetas CON `MANIFIESTO`. Ese archivo se escribe el último en el VPS, así que su
# presencia es la señal de que la corrida terminó — y así no se copia una que se esté generando ahora
# mismo. El `mv` atómico del otro lado ya lo hace improbable; esto lo hace imposible.
remotas=$(rsync -e "$SSH" --list-only "$REMOTO:$ORIGEN" 2>/dev/null \
          | awk '$5 ~ /^20[0-9][0-9]-/ {print $5}' | sort)

nuevas=0
for carpeta in $remotas; do
    [ -d "$DESTINO/$carpeta" ] && continue

    # `--partial-dir` para que una transferencia cortada se reanude en vez de empezar de cero. Va a un
    # directorio oculto y NO a un archivo parcial junto al bueno, que es lo que confundiría al `-d` de
    # arriba en la siguiente corrida: una carpeta a medias parecería una carpeta ya traída.
    rsync -e "$SSH" -a --partial-dir=.parcial --timeout=300 \
          "$REMOTO:$ORIGEN$carpeta" "$DESTINO/"

    # ── 2. Comprobar que llegó ENTERO ────────────────────────────────────────────────────────────
    #
    # El VPS verifica que el volcado se GENERÓ bien; esto verifica que VIAJÓ bien. Son dos preguntas
    # distintas y las dos hacen falta: un disco que empieza a fallar corrompe archivos que ya estaban
    # buenos cuando se escribieron.
    if ! ( cd "$DESTINO/$carpeta" && sha256sum -c --quiet MANIFIESTO ); then
        # Se BORRA la copia mala en vez de dejarla. Si se quedara, el `-d` de arriba la daría por
        # traída y no se volvería a intentar nunca — un respaldo corrupto que nadie vuelve a tocar.
        rm -rf "${DESTINO:?}/$carpeta"
        echo "$(date '+%F %T')  ERROR  $carpeta no cuadra con su manifiesto; descartada" >&2
        exit 1
    fi
    nuevas=$((nuevas + 1))
done

# ── 3. Rotar ────────────────────────────────────────────────────────────────────────────────────
#
# 14 diarias y 8 semanales, y las semanales importan más de lo que parecen: si algo se corrompe y
# tardas diez días en notarlo, con solo las diarias el último respaldo bueno ya se borró. Las
# semanales son las que cubren «llevo tiempo con esto mal y no me di cuenta».
todas=$(ls -1d 20*/ 2>/dev/null | tr -d / | sort -r)
i=0
declare -A semana_vista
for carpeta in $todas; do
    i=$((i + 1))
    [ "$i" -le "$DIARIOS" ] && continue

    # Fuera de las diarias, se conserva UNA por semana ISO. `%G-%V` y no `%Y-%V`: a fin de año, la
    # semana 1 puede pertenecer al año siguiente, y con `%Y` dos semanas distintas colisionarían.
    sem=$(date -d "${carpeta%%_*}" +%G-%V 2>/dev/null || echo "?")
    if [ -z "${semana_vista[$sem]:-}" ] && [ "${#semana_vista[@]}" -lt "$SEMANALES" ]; then
        semana_vista[$sem]=1
        continue
    fi
    rm -rf "${DESTINO:?}/$carpeta"
done

# ── 4. El latido ────────────────────────────────────────────────────────────────────────────────
#
# Solo si se llegó hasta acá. Cualquier fallo de arriba corta por `set -e` y el ping no se manda, que
# es precisamente lo que hace que Kuma se dé cuenta.
ultima=$(ls -1d 20*/ 2>/dev/null | sort -r | head -1 | tr -d /)
total=$(du -sh "$DESTINO" | cut -f1)
echo "$(date '+%F %T')  ok  nuevas=$nuevas  ultima=$ultima  copias=$(ls -1d 20*/ | wc -l)  total=$total"

# Se recorta lo que venga despues de `?`: Kuma enseña la URL de ejemplo CON parametros ya puestos
# (`?status=up&msg=OK&ping=`), y pegarla tal cual duplicaria `msg`. Asi funciona con la URL pelada y
# con la de ejemplo, que es la que uno copia sin mirar.
[ -n "$PUSH_KUMA" ] && curl -fsS -m 15 "${PUSH_KUMA%%?*}?status=up&msg=nuevas-$nuevas" -o /dev/null || true
