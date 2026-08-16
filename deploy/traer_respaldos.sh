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

# UNO A LA VEZ. Dos corridas solapadas escriben con `rsync` en la MISMA carpeta mientras la rotación de
# una puede borrar lo que la otra está copiando — y el resultado pasaría la comprobación del manifiesto
# o no según el orden, que es la peor clase de fallo: intermitente y sin causa visible.
#
# No es hipotético: el 2026-07-30 el comando que añadía la línea al crontab se corrió dos veces y
# quedaron dos entradas idénticas a las 7:00.
#
# `-n` para no encolar, y salida 0: si ya hay uno corriendo, este sobra.
exec 200>/var/run/traer_respaldos.lock
flock -n 200 || { echo "Ya hay una descarga corriendo; esta se omite."; exit 0; }

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

# La tercera copia. Vacío = no se sube nada, y el resto sigue funcionando igual.
B2_BUCKET="${B2_BUCKET:-}"
AGE_PUB="${AGE_PUB:-/root/.age-dgl.pub}"

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
recien=""
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
    recien="$recien $carpeta"
done

# ── La tercera copia: cifrada, en B2 ────────────────────────────────────────────────────────────
#
# CONTRA QUÉ PROTEGE, que no es lo mismo que las otras dos. El VPS y esta máquina cubren un disco
# roto, un borrado por error o el servidor perdido. No cubren que ESTA CASA desaparezca —incendio,
# robo— ni que un ransomware llegue acá por otra vía y cifre también la carpeta de respaldos.
#
# SE CIFRA ACÁ Y NO SE CONFÍA EN EL CIFRADO DEL PROVEEDOR. El volcado lleva los hashes de contraseña
# de los roles de Postgres y los correos de los usuarios del CMS. Subirlo en claro convierte cada
# copia en una filtración esperando a pasar.
#
# `age` es asimétrico, y esa es la propiedad que se está comprando: acá solo vive la clave PÚBLICA.
# Si algo compromete esta máquina encuentra con qué cifrar y **no puede leer nada de lo que ya está en
# B2**. La privada existe únicamente en 1Password, y solo hace falta para restaurar.
#
# Y LA CLAVE DE B2 NO SABE BORRAR: se creó con `listFiles,readFiles,writeFiles` y sin `deleteFiles`.
# La rotación la ejecuta B2 con una regla de ciclo de vida a 90 días, desde su lado. Si el borrado lo
# hiciera este script, habría que darle permiso de borrar — y entonces las tres copias volverían a
# estar en el mismo dominio de confianza, que es justo lo que esta tercera viene a romper.
if [[ -n "$B2_BUCKET" && -n "$recien" ]]; then
    [[ -f "$AGE_PUB" ]] || { echo "$(date '+%F %T')  ERROR: falta $AGE_PUB; no se sube nada" >&2; exit 1; }
    destinatario="$(cat "$AGE_PUB")"

    for carpeta in $recien; do
        cifrado="$DESTINO/.$carpeta.tar.age"
        # Un solo archivo por corrida: restaurar es bajar uno, descifrar y desempaquetar. Con los
        # archivos sueltos habría que acordarse de cuáles son ocho meses después.
        tar -cf - -C "$DESTINO" "$carpeta" | age -r "$destinatario" > "$cifrado"

        b2 file upload --quiet "$B2_BUCKET" "$cifrado" "$carpeta.tar.age" >/dev/null

        # SE COMPRUEBA QUE LLEGÓ, no que el comando devolvió cero. Es la misma lección del día: un
        # `b2 file upload` que sale bien no demuestra que el objeto esté en el bucket.
        if ! b2 file info "b2://$B2_BUCKET/$carpeta.tar.age" >/dev/null 2>&1; then
            rm -f "$cifrado"
            echo "$(date '+%F %T')  ERROR  $carpeta no llegó a B2" >&2
            exit 1
        fi
        rm -f "$cifrado"
    done
fi

# ── 3. Rotar ────────────────────────────────────────────────────────────────────────────────────
#
# 14 diarias y 8 semanales, y las semanales importan más de lo que parecen: si algo se corrompe y
# tardas diez días en notarlo, con solo las diarias el último respaldo bueno ya se borró. Las
# semanales son las que cubren «llevo tiempo con esto mal y no me di cuenta».
todas=$(ls -1d 20*/ 2>/dev/null | tr -d / | sort -r)
i=0
# EL CONTADOR EXISTE PORQUE `${#semana_vista[@]}` NO SE PUEDE USAR ACÁ (2026-08-12).
#
# Con `set -u`, un array asociativo VACÍO cuenta como NO ASIGNADO: `declare -A` lo declara pero no lo
# crea hasta que recibe su primer elemento, así que preguntarle el tamaño mata el script con
# «semana_vista: unbound variable». Leer un elemento sí está a salvo, y por eso el `:-` del `if`
# bastaba y el `${#...}` de al lado no.
#
# ESTUVO DOCE DÍAS SIN DAR LA CARA, y conviene saber por qué: el cuerpo del bucle solo se alcanza a
# partir de la copia número quince —antes lo salta el `continue` de las diarias—, así que el fallo
# esperó a que la carpeta se llenara. Lo mismo puede pasarle a cualquier cosa que se escriba aquí
# dentro: no se ejecuta hasta que hay más de `$DIARIOS` copias.
#
# No se pierde nada: `rm -rf` va DESPUÉS del `if`, así que al morir en la comparación no llegó a
# borrar ninguna.
semanas=0
declare -A semana_vista=()
for carpeta in $todas; do
    i=$((i + 1))
    [ "$i" -le "$DIARIOS" ] && continue

    # Fuera de las diarias, se conserva UNA por semana ISO. `%G-%V` y no `%Y-%V`: a fin de año, la
    # semana 1 puede pertenecer al año siguiente, y con `%Y` dos semanas distintas colisionarían.
    sem=$(date -d "${carpeta%%_*}" +%G-%V 2>/dev/null || echo "?")
    if [ -z "${semana_vista[$sem]:-}" ] && [ "$semanas" -lt "$SEMANALES" ]; then
        semana_vista[$sem]=1
        semanas=$((semanas + 1))
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

# B2 SE NOMBRA SOLO SI SE SUBIÓ ALGO, por lo mismo que el mensaje de ufw del otro script: una línea
# de resumen que afirma más de lo que hizo es peor que no tenerla, porque es lo que alguien lee para
# decidir si mirar más.
if [[ -z "$B2_BUCKET" ]]; then
    en_b2=""
elif [[ -n "$recien" ]]; then
    en_b2="  b2=subido"
else
    en_b2="  b2=sin-novedad"
fi

echo "$(date '+%F %T')  ok  nuevas=$nuevas  ultima=$ultima  copias=$(ls -1d 20*/ | wc -l)  total=$total$en_b2"

# Se recorta lo que venga despues de `?`: Kuma enseña la URL de ejemplo CON parametros ya puestos
# (`?status=up&msg=OK&ping=`), y pegarla tal cual duplicaria `msg`. Asi funciona con la URL pelada y
# con la de ejemplo, que es la que uno copia sin mirar.
# Se nombra B2 solo si de verdad se subio algo, por lo mismo que el mensaje de ufw en el otro script.
# EL `?` VA ESCAPADO, y no es un detalle de estilo: sin la barra invertida, `?` es el comodín de UN
# carácter del shell, así que `${PUSH_KUMA%%?*}` borra desde el primer carácter y deja la variable
# VACÍA. Estuvo así desde que se escribió — comprobado en el registro de linuxbox, el 31 de julio y el
# 1 de agosto:
#
#     2026-08-01 07:00:22  ok  nuevas=1  ultima=2026-08-01_0530  copias=4  total=60M
#     curl: (3) URL rejected: No host part in the URL
#
# El respaldo se trajo perfecto las dos veces y el monitor de Kuma se quedó en rojo, así que el dueño
# creyó durante dos días que el respaldo no estaba corriendo. Un aviso roto es peor que no tener
# aviso: no dice «no sé», dice «está mal».
#
# El recorte SÍ hace falta —permite que `PUSH_KUMA` venga con su propia cadena de consulta sin acabar
# con dos `?` en la URL— y con el escape funciona: deja la URL entera si no la trae.
[ -n "$PUSH_KUMA" ] && curl -fsS -m 15 "${PUSH_KUMA%%\?*}?status=up&msg=nuevas-$nuevas" -o /dev/null || true
