# dglweb — dev / quality-gate helpers. Everything runs in Docker (Python 3.13 inside),
# so you don't need a local Python. `make check` is exactly what CI runs.

.PHONY: build up down logs migrate makemigrations superuser test lint format typecheck check shell

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
testjs: ; docker run --rm -v "$(CURDIR)":/app -w /app node:22-alpine sh -c "npm ci --silent && npm test"

# Full quality gate (lint + types + tests). Run before every commit.
check: lint typecheck test testjs
