# Revive Adserver, construido desde su código. Ver `docs/ADSERVER.md` para el porqué de todo esto.
#
# POR QUÉ UNA IMAGEN PROPIA
# -------------------------
# Revive no publica imagen oficial y su repositorio no trae `Dockerfile`. En Docker Hub hay diez
# resultados de la comunidad, **la más popular con 5 estrellas** y ninguna mantenida (buscado el
# 2026-07-28). Esta es la pieza que sirve JavaScript a CADA visitante del sitio: no se le confía a una
# imagen abandonada de un desconocido.
#
# Y SE COMPILA DESDE EL CÓDIGO, NO DESDE UN PAQUETE
# --------------------------------------------------
# Porque el paquete no se puede automatizar: las publicaciones de GitHub **no traen adjuntos** y la
# descarga directa de `download.revive-adserver.com` responde 403. Compilar desde la etiqueta tiene
# además la ventaja de que se ve exactamente qué entra.

# ── Etapa 1: las dependencias ───────────────────────────────────────────────────────────────────
FROM composer:2 AS dependencias

# La versión va como argumento y con valor por defecto, no escrita entre el código: subirla es
# cambiar un número, y queda registrado en el historial qué versión se construyó cada vez.
ARG REVIVE_VERSION=v6.0.8

# `git` para clonar, y **`intl` porque Composer lo exige para resolver**: Revive lo declara en
# `require` y la imagen oficial de Composer no lo trae, así que sin esto la instalación aborta con
# «ext-intl is missing from your system» antes de bajar una sola dependencia.
#
# Se INSTALA en vez de saltárselo con `--ignore-platform-req`: esa bandera apaga la comprobación
# entera, así que también dejaría pasar una extensión que de verdad falte en la imagen final — y ese
# fallo aparecería en ejecución, no acá.
RUN apk add --no-cache git icu-dev $PHPIZE_DEPS \
    && docker-php-ext-install -j"$(nproc)" intl \
    && apk del $PHPIZE_DEPS

WORKDIR /origen
# `--depth 1` sobre la etiqueta: no hace falta el historial para construir, y clonarlo entero son
# cientos de megas de nada.
RUN git clone --depth 1 --branch "${REVIVE_VERSION}" \
        https://github.com/revive-adserver/revive-adserver.git . \
    && rm -rf .git .github

# `--no-dev` deja fuera las herramientas de prueba, que en producción son superficie de ataque y
# nada más. `--no-scripts` NO se usa: los scripts de post-instalación de Revive copian ficheros que
# la aplicación necesita (ver `post-install-cmd` en su `composer.json`), y sin ellos arranca rota.
RUN composer install --no-dev --optimize-autoloader --no-interaction --no-progress

# Lo que no tiene nada que hacer en un servidor público. En Revive la raíz de la instalación ES la
# raíz del sitio, así que todo esto quedaría bajo el techo web: las pruebas del propio proyecto, los
# tutoriales y los ficheros de construcción.
#
# La configuración de Apache de más abajo ya les devuelve 403, pero eso es un cinturón. **Lo que no
# está en la imagen no se puede servir por un fallo de configuración**, y son 4 MB que no aportan
# nada en ejecución.
RUN rm -rf tests tutorials build.xml build-filelist.xml .git-blame-ignore-revs

# ── Etapa 2: lo que corre ───────────────────────────────────────────────────────────────────────
#
# PHP 8.3 y no otra: es la que fija el propio CI de Revive (`PHP_VERSION: 8.3` en su `ci.yml`).
# Prueban de la 8.1 a la 8.5, así que hay margen, pero se elige la que ellos usan para construir.
#
# La variante `-apache` y no `-fpm`: con FPM harían falta dos procesos y un servidor web aparte
# dentro del contenedor. Acá delante ya hay nginx haciendo de proxy inverso, así que un Apache
# sencillo escuchando en el 80 es una pieza menos que configurar y que se pueda romper.
FROM php:8.3-apache

# Las extensiones salen de la lista que declara SU CI, no de la memoria de nadie:
#   ctype curl dom fileinfo iconv json libxml mbstring openssl simplexml tokenizer xml xmlwriter
#     -> ya vienen compiladas en la imagen oficial de PHP
#   intl pgsql zip
#     -> hay que instalarlas, y cada una necesita su biblioteca de desarrollo
#
# `pgsql` es la que hace que este montaje sea de UN solo motor de base de datos: Revive usa el
# Postgres que ya está en el VPS. Ver la decisión correspondiente en `docs/ADSERVER.md`.
#
# GD NO va, y no es olvido: el comprobador de entorno de Revive (`EnvironmentManager`) solo exige
# `mbstring` y `zlib`. Añadir GD serían dos bibliotecas más y más superficie para algo que no pide.
# CUIDADO CON LA LIMPIEZA DE ESTE BLOQUE. La primera versión terminaba con
# `apt-get purge --auto-remove libicu-dev libpq-dev libzip-dev`, que parece lo correcto y **deja la
# imagen rota**: junto a las cabeceras se lleva las bibliotecas de EJECUCIÓN —`libicuio.so`,
# `libpq.so.5`, `libzip.so.5`— y entonces las cuatro extensiones no cargan.
#
# Y no falla al construir. La imagen se genera tan campante y el fallo aparece al arrancar, en unos
# avisos de PHP que nadie mira, con `pgsql` ausente: o sea, Revive sin base de datos.
#
# La receta de abajo es la que usan las imágenes oficiales de WordPress y Drupal para esto mismo:
# marcar todo como automático, y volver a marcar como MANUAL solo los paquetes de los que dependen de
# verdad los `.so` compilados, preguntándoselo a `ldd`. Así se va lo que sobra sin tocar lo que hace
# falta, y sin escribir a mano nombres como `libicu76` que cambian con cada versión de Debian.
RUN set -eux; \
    savedAptMark="$(apt-mark showmanual)"; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libicu-dev \
        libpq-dev \
        libzip-dev \
    ; \
    docker-php-ext-configure intl; \
    docker-php-ext-install -j"$(nproc)" intl pgsql pdo_pgsql zip; \
    apt-mark auto '.*' > /dev/null; \
    apt-mark manual $savedAptMark > /dev/null; \
    ldd "$(php -r 'echo ini_get("extension_dir");')"/*.so \
        | awk '/=>/ { so = $(NF-1); if (index(so, "/usr/local/") == 1) next; gsub("^/(usr/)?", "", so); printf "*%s\n", so }' \
        | sort -u \
        | xargs -r dpkg-query --search 2>/dev/null \
        | cut -d: -f1 \
        | sort -u \
        | xargs -r apt-mark manual > /dev/null; \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
    rm -rf /var/lib/apt/lists/*; \
    # La comprobación que la primera versión no tenía: si una extensión no carga, el `build` FALLA
    # acá y no tres semanas después en producción.
    php -r 'foreach (["intl","pgsql","pdo_pgsql","zip"] as $e) { if (!extension_loaded($e)) { fwrite(STDERR, "FALTA la extension $e\n"); exit(1); } } echo "extensiones ok\n";'

# La configuración de PHP para producción. La imagen oficial trae las dos plantillas y no activa
# ninguna: sin esta línea corre con los avisos de desarrollo visibles, que en un servidor público
# significa enseñarle rutas internas y trazas a cualquiera que provoque un error.
RUN mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini"

# Subir creatividades es el uso normal de esto, y el defecto de PHP son 2 MB — un banner de campaña
# grande no entra. Se sube a 16, que sigue siendo un techo razonable.
RUN { \
        echo 'upload_max_filesize = 16M'; \
        echo 'post_max_size = 20M'; \
        echo 'expose_php = Off'; \
    } > "$PHP_INI_DIR/conf.d/revive.ini"

# `expose_php = Off` de arriba y esto: sin las dos, cada respuesta anuncia la versión exacta de PHP y
# de Apache en sus cabeceras. No es una vulnerabilidad por sí mismo; es decirle a quien busca
# objetivos qué exploits probar primero.
#
# EL NOMBRE EMPIEZA POR `zz-` Y ESO ES LO QUE LO HACE FUNCIONAR. Debian trae su propio
# `security.conf` con `ServerTokens OS`, activado de fábrica, y Apache carga `conf-enabled/` en orden
# alfabético: llamándolo `endurecer.conf` el de Debian iba después y ganaba. Comprobado — la cabecera
# seguía diciendo `Apache/2.4.68 (Debian)` con esta configuración puesta y aparentemente activa.
RUN { \
        echo 'ServerTokens Prod'; \
        echo 'ServerSignature Off'; \
        echo 'TraceEnable Off'; \
    } > /etc/apache2/conf-available/zz-endurecer.conf \
    && a2enconf zz-endurecer

# VIVIR DETRÁS DE UN PROXY INVERSO. Las dos líneas de abajo arreglan dos fallos distintos que se
# manifiestan de forma muy distinta, y ninguno se ve al probar el contenedor suelto.
#
# 1. `HTTPS=on` — SIN ESTO EL PANEL NO ABRE. Revive mira `$_SERVER['HTTPS']` para construir sus URL,
#    y detrás del proxy llega vacío: genera `http://`, nginx redirige a `https://`, Revive vuelve a
#    `http://`… y el navegador corta con ERR_TOO_MANY_REDIRECTS. Pasó el 2026-07-28.
#
# 2. `mod_remoteip` — SIN ESTO LOS INFORMES SON FALSOS, y en silencio. nginx manda `X-Forwarded-For`,
#    pero **esa cabecera sola no hace nada**: Apache y PHP siguen leyendo la IP del proxy en
#    `REMOTE_ADDR`. Revive contaría todas las impresiones como un único visitante de un único país, y
#    esos son los números que se le facturan al cliente.
#
#    `RemoteIPInternalProxy` con los rangos privados y no una IP concreta: nginx corre en el
#    anfitrión y el contenedor lo ve llegar por la pasarela de la red de Docker, que cambia de
#    dirección cada vez que se recrea la red.
RUN a2enmod remoteip \
    && { \
        echo 'SetEnvIf X-Forwarded-Proto "https" HTTPS=on'; \
        echo 'RemoteIPHeader X-Forwarded-For'; \
        echo 'RemoteIPInternalProxy 127.0.0.0/8'; \
        echo 'RemoteIPInternalProxy 172.16.0.0/12'; \
        echo 'RemoteIPInternalProxy 10.0.0.0/8'; \
        echo 'RemoteIPInternalProxy 192.168.0.0/16'; \
    } > /etc/apache2/conf-available/zz-proxy.conf \
    && a2enconf zz-proxy

WORKDIR /var/www/html
COPY --from=dependencias --chown=www-data:www-data /origen/ /var/www/html/

# LO QUE NO PUEDE SERVIRSE POR WEB, y es la mitad de la seguridad de este montaje.
#
# En Revive la raíz de la instalación ES la raíz del sitio: se navega a `/www/admin/` y a
# `/www/delivery/`. Eso deja bajo el mismo techo `lib/`, `etc/`, `var/` y `vendor/` — el código
# entero, los esquemas de base de datos y, sobre todo, **el fichero de configuración con la
# contraseña de Postgres**, que vive en `var/`.
#
# Un `.php` ahí dentro lo ejecutaría el intérprete y no pasaría nada visible, pero un `.conf.php`
# servido como texto por un fallo de configuración regala las credenciales. Se cierra por lista
# negra explícita, que es lo que se puede leer y auditar de un vistazo.
RUN { \
        echo '<Directory /var/www/html>'; \
        echo '    Options -Indexes -FollowSymLinks'; \
        echo '    AllowOverride All'; \
        echo '    Require all granted'; \
        echo '</Directory>'; \
        echo '<DirectoryMatch "^/var/www/html/(lib|etc|var|vendor|plugins|scripts|tests|docs)/">'; \
        echo '    Require all denied'; \
        echo '</DirectoryMatch>'; \
        echo '<FilesMatch "\.(md|txt|xml|lock|json|dist|sql)$">'; \
        echo '    Require all denied'; \
        echo '</FilesMatch>'; \
    } > /etc/apache2/conf-available/revive.conf \
    && a2enconf revive

# `AllowOverride All` de arriba está a propósito: Revive reparte sus propios `.htaccess` por el
# árbol y esta imagen no los va a segundo-adivinar. La lista negra es el cinturón encima.

# Las dos carpetas que la aplicación ESCRIBE, y que por lo tanto van en volúmenes:
#   var/         la configuración que genera el instalador, más cachés
#   www/images/  las creatividades que sube Adcio — irreemplazables, hay que respaldarlas
# Se crean acá con el dueño correcto para que el volumen nazca bien: Docker copia los permisos de la
# carpeta de la imagen al crear un volumen vacío encima.
RUN mkdir -p var www/images \
    && chown -R www-data:www-data var www/images

EXPOSE 80
