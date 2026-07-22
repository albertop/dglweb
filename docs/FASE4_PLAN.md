# Fase 4 — Backfill histórico + LÍDERES + páginas de jugador

Plan acordado con el dueño (2026-07-22). El diferenciador estrella: **líderes del subconjunto
dominicano** (carrera + temporada) + páginas de jugador, sobre el backfill histórico completo.

## Decisiones cerradas
- **Backfill desde el proxy** (no copiar de SQL Server): reproduce nuestro schema con todas las
  correcciones (NULL-sobre-0, UZR arreglado, innings_outs, tasas derivadas).
- **Líderes precalculados** (no al vuelo): tablas `dgl_leaders_*`, refrescadas por comando en el
  scheduler. Espejan la estructura de `dbo.mlbLeaders*` pero **re-rankeadas solo para dominicanos**
  desde nuestras tablas. Tipos: **Career + Seasons + BySeasons** (sin el split por liga por ahora).
- **Todas las categorías** de la fuente (hitting 26, pitching 45, fielding 15, catching 28) — los
  nombres del statsapi (`homeRuns`, `battingAverage`, `era`…).
- **URLs de jugador con slug SEO** (`/jugador/adrian-beltre/`).
- **Ligas Negras (los 7):** incluidos, **incluida la sabermetría**, con nota "disponible desde la
  temporada YYYY" (por métrica, según cuándo empieza el dato).

## Sub-fases (fase a fase)

### 4a — Backfill histórico  ← EMPEZAMOS AQUÍ
Correr los 6 `import_*` sobre todas las temporadas con dominicanos → **10.0.0.39**:
- Regular (batting/pitching/fielding): **1926–2025**. Postemporada: **1962–2025**.
- Requiere `migrate` en 10.0.0.39 primero (crea las tablas de stats).
- One-time, idempotente/reanudable, logueado en la bitácora. Verificar conteos vs la fuente.

### 4b — Tabla maestra de métricas + motor de líderes
**`dgl_metric`** (editable en el Backoffice), una fila por métrica:
- `stat_group` (batting/pitching/fielding/catching), `category` (nombre statsapi, llave con la
  fuente), `abbrev` (HR), `description` (Cuadrangulares).
- `direction` (high/low — mejor es alto o bajo), `kind` (cumulative/rate).
- **`qualifier_career`** y **`qualifier_season`**: fórmulas simples tipo `PA>502` / `IP>=50`
  (default por métrica). Los conteos no llevan umbral; solo las tasas.
- `available_from` (año desde el que hay dato, para la nota), `is_active`.
- Se **siembra** desde las categorías de `mlbLeaders` + defaults; el dueño la ajusta en el Backoffice.

**`dgl_metric_season_override`**: `(metric, season, qualifier_formula)` — **override del umbral por
temporada** (2020 con 60 juegos, eras antiguas). Aplica sobre `qualifier_season`.

Las fórmulas se evalúan con un **parser seguro** (no `eval`): `CAMPO OP NÚMERO` (y `AND`), campos =
nuestras columnas agregadas (PA, IP, BF, G…).

**Motor `build_leaders`** (comando, corre en el scheduler tras el backfill): por cada métrica
activa computa el `value` (cumulative = SUM sobre `season_totals()`; rate = recompute con
`derive.py` sobre los totales), aplica el qualifier, rankea por `direction`, escribe
`dgl_leaders_career/seasons/by_seasons`. **Verificación:** los 22 dominicanos que SÍ están en tu
`mlbLeaders` all-MLB → nuestro value de carrera debe coincidir (paridad del motor).

### 4c — Páginas de jugador (~970)
Vistas Django data-driven al mock `player.html`: hero + bio (`dgl_master`), tabs Bateo/Pitcheo/
Fildeo con Estándar + Avanzado/Sabermétrico, carrera + temporada, **regular + postemporada**. Slug
SEO; desambiguar nombres repetidos. Nota de cobertura para Ligas Negras.

### 4d — Páginas de líderes
Selector interactivo (categoría → tipo → métrica) del mock `leaders.html`, sobre las tablas de 4b.
Muestra el umbral aplicado y la nota "disponible desde YYYY".

## Pendientes de code review que se cierran aquí
- **FIX-8** (umbral de apariciones): lo resuelve `dgl_metric` (qualifier configurable + override por
  temporada).
- **FIX-9** (nota Ligas Negras / cobertura): `available_from` + la nota en páginas/líderes.
