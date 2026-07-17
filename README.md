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

## Database contexts (via `DATABASE_URL`)

- **Dev/CI:** disposable Postgres container (this compose file). Isolated; tests create/drop DBs.
- **Datos de desarrollo:** `10.0.0.39` — used when real data is populated (Fases 2–4).
- **Producción:** the VPS — not touched until the big-bang launch.

Switching context is just an env var; no code changes.
