# dglweb — Dominicanos en Grandes Ligas (website)

Django + Wagtail. Runs on **Python 3.13 inside Docker** (no local Python needed).
See `docs/` for concept, build plan, coding standards, and Django/Wagtail guidelines.

## Quick start (local dev)

```bash
docker compose build          # or: make build
docker compose up -d          # web (:8000) + Postgres
docker compose run --rm web python manage.py migrate
# open http://localhost:8000/   (landing)  ·  /cms/ (Wagtail admin)
```

## Quality gate (what must be green before every commit)

```bash
make check          # = lint + typecheck + test
# or individually:
make lint           # ruff check .
make typecheck      # mypy .  (strict + django-stubs)
make test           # pytest  (TDD; write the test first)
```

If `make` isn't available, run the underlying commands directly:

```bash
docker compose run --rm --no-deps web ruff check .
docker compose run --rm --no-deps web mypy .
docker compose run --rm web pytest
```

### El JavaScript

Va aparte porque no comparte nada con el gate de Python: ni Postgres, ni dependencias, ni siquiera
el lenguaje. Corre con **vitest sobre jsdom** —no un navegador de verdad: lo que se prueba son
decisiones de teclado y de DOM, no pintado— y **no hace falta tener Node instalado**, igual que no
hace falta tener Python:

```bash
docker run --rm -v "$PWD":/app -w /app node:22-alpine sh -c "npm ci && npm test"
```

Existe desde el 28-07-2026 por FE-02 del review v6 (el teclado del buscador sin pruebas). Se aplazó
mientras hubo un solo archivo de JS, porque el corredor costaba más que lo que protegía; hoy son
ocho archivos y ~860 líneas.

## Database contexts (via `DATABASE_URL`)

- **Dev/CI:** disposable Postgres container (this compose file). Isolated; tests create/drop DBs.
- **Datos de desarrollo:** `10.0.0.39` — used when real data is populated (Fases 2–4).
- **Producción:** the VPS — not touched until the big-bang launch.

Switching context is just an env var; no code changes.
