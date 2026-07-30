#!/bin/bash
# Crea la base y el rol de dglweb. Va en `/srv/postgres/init/`, que el stack monta en
# `/docker-entrypoint-initdb.d` — ver `deploy/postgres/stack.yml`.
#
#   sudo install -D -m 755 deploy/postgres/init/10-dglweb.sh /srv/postgres/init/10-dglweb.sh
#
#
# CORRE UNA SOLA VEZ EN LA VIDA DE LA INSTANCIA, Y ESO ES LA TRAMPA
# ------------------------------------------------------------------
# Postgres ejecuta lo que haya en `/docker-entrypoint-initdb.d` **solo cuando el volumen está vacío**.
# En una base ya creada no se mira siquiera, así que:
#
#   * Un olvido NO se arregla reiniciando el stack ni recreándolo. Hay que hacer el `CREATE ROLE` y el
#     `CREATE DATABASE` a mano, o vaciar el volumen — que es perder los datos.
#   * Si falta en un servidor nuevo, **Postgres levanta perfectamente y el healthcheck da verde**. El
#     fallo aparece más tarde y en otro sitio: la aplicación no puede conectarse porque su rol no
#     existe, o `migrate` revienta al llegar a `players/0005_unaccent.py`.
#
# Por eso está versionado. Es de los archivos que no se echan de menos hasta el día en que hacen falta,
# y ese día uno no está para reconstruirlo de memoria.
#
#
# POR QUÉ LA EXTENSIÓN LA CREA ESTE SCRIPT Y NO UNA MIGRACIÓN
# ------------------------------------------------------------
# `unaccent` es lo que hace que «nunez» encuentre a Núñez en el buscador de jugadores — sin ella, media
# tabla del maestro es inalcanzable escribiendo sin tildes, que es como escribe todo el mundo.
#
# Existe `players/0005_unaccent.py`, pero `CREATE EXTENSION` pide permisos elevados y **la aplicación
# se conecta con el rol `dglweb`, que no los tiene**. Así que la crea acá el superusuario, una vez, y
# la migración se la encuentra hecha. En un Postgres gestionado con usuario restringido, esto es lo que
# hay que resolver antes de migrar — no después.
#
#
# LO QUE ESTE SCRIPT NO HACE: LA BASE DE REVIVE
# ----------------------------------------------
# La instancia la comparten dglweb y Revive, pero acá solo se crea lo de dglweb. La de Revive la hizo
# su instalador conectándose como superusuario.
#
# En una reconstrucción desde cero eso hay que recordarlo: este script deja el servidor listo para el
# sitio y **no** para la publicidad. Ver `docs/ADSERVER.md`.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-SQL
  CREATE ROLE dglweb LOGIN PASSWORD '${DGLWEB_DB_PASSWORD}';
  CREATE DATABASE dglweb OWNER dglweb;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname dglweb <<-SQL
  CREATE EXTENSION IF NOT EXISTS unaccent;
SQL
