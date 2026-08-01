# dglweb — dev / quality-gate helpers. Everything runs in Docker (Python 3.13 inside),
# so you don't need a local Python. `make check` is exactly what CI runs.

.PHONY: build up down logs migrate makemigrations superuser test lint format typecheck check shell testjs checkshell checkps1 checkstacks

build: ; docker compose build
up: ; docker compose up -d
down: ; docker compose down
logs: ; docker compose logs -f web
migrate: ; docker compose run --rm web python manage.py migrate
makemigrations: ; docker compose run --rm web python manage.py makemigrations
superuser: ; docker compose run --rm web python manage.py createsuperuser
shell: ; docker compose run --rm web python manage.py shell

test: ; docker compose run --rm web pytest
lint: ; docker compose run --rm --no-deps web ruff check .
format: ; docker compose run --rm --no-deps web ruff format .
typecheck: ; docker compose run --rm --no-deps web mypy .

# El JavaScript, con vitest sobre jsdom. En su propio contenedor y no en `web`: la imagen del sitio
# es Python puro y meterle Node solo para probar sería cargar el runtime de producción con una
# herramienta de desarrollo. Así tampoco hace falta tener Node instalado en la máquina.
#
# `MSYS_NO_PATHCONV=1` es para Git Bash, que es desde donde se corre esto en Windows. MSYS traduce
# solo los argumentos que PARECEN rutas de Unix, así que el `/app` de `-v ...:/app` se salva por venir
# detrás de dos puntos y el de `-w /app` no: Docker lo recibía como `C:/Program Files/Git/app` y
# abortaba. En Linux y en el CI la variable sencillamente no la mira nadie.
testjs: ; MSYS_NO_PATHCONV=1 docker run --rm -v "$(CURDIR)":/app -w /app node:22-alpine sh -c "npm ci --silent && npm test"

# ── Lo que NO es Python ni JavaScript ───────────────────────────────────────────────────────────
#
# Siete scripts de shell, uno de PowerShell y tres stacks de compose. Ninguno lo miraba `check`, y
# son justo los archivos con el peor modo de fallo del repositorio: **nadie los ejecuta al
# desarrollar**, así que un error de sintaxis espera hasta que los dispare un cron o un despliegue.
#
#     respaldo.sh          a las 5:30 de la mañana, sin nadie delante
#     traer_respaldos.sh   a las 7:00, en la otra máquina
#     deploy/stack.yml     al recrear el stack, con el sitio abajo
#     el .ps1              al generar el PDF para un anunciante
#
# El 2026-07-30 se tocaron casi todos en un día y se pasaron a mano tras cada cambio. Salieron
# limpios — pero eso dependía de que alguien se acordara, que es la clase de garantía que este
# proyecto lleva tiempo sustituyendo por comprobaciones.
#
# `bash -n` valida SINTAXIS, no semántica: no detecta un `awk` con una extensión de gawk ni un `sed`
# que no casa. Para eso están las pruebas de verdad; esto es la red de abajo.
checkshell: ; @for f in deploy/*.sh deploy/postgres/init/*.sh deploy_dglweb_image.sh; do \
	printf "  %-42s " "$$f"; bash -n "$$f" || exit 1; echo ok; done

# El de PowerShell se comprueba con el analizador de .NET, sin ejecutarlo. Solo corre donde haya
# `pwsh` o `powershell` —o sea, en la máquina del dueño— y se salta en silencio en otros sitios: es
# preferible a que el gate falle en el CI por un archivo que allí nadie va a usar.
checkps1: ; @command -v powershell >/dev/null 2>&1 || command -v pwsh >/dev/null 2>&1 || { echo "  (sin PowerShell, se omite)"; exit 0; }; \
	printf "  %-42s " "docs/generar_pdf_banners.ps1"; \
	powershell -NoProfile -Command "\$$e=\$$null; \$$null=[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'docs/generar_pdf_banners.ps1'),[ref]\$$null,[ref]\$$e); if(\$$e.Count){exit 1}"; echo ok

# `config -q` valida sintaxis Y esquema de compose. Las variables van con valores de mentira porque
# los `${VAR:?falta}` abortarían — y esos `:?` son deliberados, así que hay que darles algo.
checkstacks:
	@printf "  %-42s " "deploy/stack.yml"; DJANGO_SECRET_KEY=x DJANGO_ALLOWED_HOSTS=x DATABASE_URL=x \
	  MLB_PROXY_URL=x MLB_PROXY_API_KEY=x WAGTAILADMIN_BASE_URL=x \
	  docker compose -f deploy/stack.yml config -q && echo ok
	@printf "  %-42s " "deploy/postgres/stack.yml"; POSTGRES_PASSWORD=x DGLWEB_DB_PASSWORD=x \
	  PGADMIN_PASSWORD=x PGADMIN_DEFAULT_EMAIL=x \
	  docker compose -f deploy/postgres/stack.yml config -q && echo ok
	@printf "  %-42s " "deploy/adserver/stack.yml"; docker compose -f deploy/adserver/stack.yml config -q && echo ok
# El drop-in de systemd reinicia el scheduler por NOMBRE de contenedor. Si alguien renombra el
# servicio en el stack, ese arreglo deja de funcionar y no lo dice nadie — que es exactamente el modo
# de fallo del incidente que lo motivó (2026-08-01, ver `docs/TODO.md`). Acá se atan los dos.
#
# Se comprueba en ESTE sentido —del drop-in al stack y no al revés— para que renombrar el servicio en
# los dos sitios a la vez siga pasando. Lo que no puede pasar es que el drop-in reinicie un nombre que
# ya no existe, porque eso falla en silencio.
	@printf "  %-42s " "systemd <-> stack.yml"; \
	  nombre=$$(grep -oE 'docker restart [a-zA-Z0-9_.-]+' deploy/systemd/reiniciar-scheduler.conf | awk '{print $$3}'); \
	  test -n "$$nombre" || { echo "FALLA: el drop-in no reinicia ningún contenedor"; exit 1; }; \
	  grep -q "container_name: *$$nombre\b" deploy/stack.yml \
	    || { echo "FALLA: el drop-in reinicia '$$nombre', que no existe en deploy/stack.yml"; exit 1; }; \
	  echo "ok ($$nombre)"

# Full quality gate. Run before every commit.
#
# Los tres últimos van AL FINAL y no al principio a propósito: tardan segundos, así que ponerlos
# delante solo retrasaría el fallo que de verdad importa —una prueba rota— unos cuantos minutos.
check: lint typecheck test testjs checkshell checkps1 checkstacks
