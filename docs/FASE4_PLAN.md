# Fase 4 — Backfill histórico + LÍDERES + páginas de jugador

Plan acordado con el dueño (2026-07-22). El diferenciador estrella: **líderes del subconjunto
dominicano** (carrera + temporada) + páginas de jugador, sobre el backfill histórico completo.

## Dónde vamos (2026-07-23)
- **4a Backfill** ✅ — 1920-2025 en 10.0.0.39 (6 tablas).
- **4b Motor de líderes** ✅ — `dgl_metric` + cascada de umbrales + `build_leaders`/`dgl_leader`
  (conteos, tasas temporada+carrera, fildeo por posición), agendado en Ofelia.
- **4b-bis Totales de carrera** ✅ — `mlb_*_career` con subtotales (equipo/liga/total bat-pit;
  posición/total fildeo), `level`+`sort_order`, DH excluido. `parity_career` (loop-safe opción "b",
  marcador `CareerParityIssue`) verifica vs el proxy; agendado semanal. Commits hasta `8e4d3b6`.
- **Code review v2** ✅ — 9 findings corregidos (commit `a6eb29f`), 1 descartado (SAB-05), 1 al backlog.
- **Primera paridad real** corrida: 298 disparidades, casi todas falsos positivos de `g` (el proxy
  `career` reporta un `g` que no cuadra con su propio `yearByYear` para pitchers). Nuestros totales
  son correctos. → refinar `parity_career` (quitar `g`) — en `docs/MEJORAS_FUTURAS.md`.
- **4c Páginas de jugador** ✅ — perfil data-driven con tabs Bateo/Pitcheo/Fildeo (Estándar, Avanzado,
  Statcast, Coeficientes, Postemporada, Totales), overlay de liderazgos (temporada/carrera), y
  **postemporada** (conteos + tasas con pisos fijos, `docs/UMBRALES_POSTEMPORADA.md`). Extra sobre el
  plan: **tab Puestos** (rejilla de puestos por métrica × temporada + columna de por vida, con pills
  Serie Regular / Postemporada). Commits hasta `e7b481a`.
- **4d Páginas de líderes — MVP** ✅ — `/lideres/` (`profiles/leaderboards.py`): Bateo/Pitcheo, serie
  regular, De por vida + Por temporada (selector de año), navegación por GET (cada board su URL).
  Reusa el layout de divisiones de Puestos y el formateo de `columns`. Falta v2: Postemporada como
  pill, Fildeo (por posición), detalle de fila (span/equipo), URLs con slug.
- **Code review v4** procesado (`docs/reviews/code_review_v4.md`) — DEV-01 (mypy .), SAB-01, SAB-04 y
  el label de `Metric.postseason` corregidos; resto evaluado y anotado en `docs/TODO.md`.
- **AQUÍ.** Pendiente Fase 4: **4d v2** (postemporada + fildeo en líderes), refinar paridad `g`, tabla
  de games, paridad de fildeo, y los findings abiertos del review v4. Backlog en `docs/MEJORAS_FUTURAS.md`.

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

### 4b-bis — Totales de carrera in-house + paridad contra el proxy (decidido 2026-07-23)

Las páginas de jugador necesitan **totales de carrera por jugador**, que hoy no tenemos
materializados (solo temporada por temporada). Investigado y decidido:

**Qué ofrece el proxy para carrera** (probado): `career` / `careerRegularSeason` (línea de carrera
autoritativa, mismos nombres de campo que por temporada), `careerAdvanced`, `careerPlayoffs`
(postemporada), fielding **por posición**. **NO** ofrece sabermetría de carrera (WAR/wOBA vuelven
vacío). Es un call por jugador.

**Decisión: totales in-house como fuente de la verdad, verificados contra el proxy como paridad.**
- **In-house** = materializar lo que el motor ya calcula (sumar `season_totals()`/`position_totals()`
  + recomputar tasas con `career_rate.py`). Casi gratis, y **garantiza que la carrera = la suma de
  las temporadas que se muestran** (consistencia en la página del jugador).
- La tabla de totales suma **todas** las temporadas del jugador — **incluidas las Ligas Negras**
  (a diferencia de los *liderazgos*, que cortan en 1956). Se compara contra `career`/`careerPlayoffs`.
- El proxy no aporta conteos/tasas que no derivemos, y no da WAR de carrera → la sabermetría de por
  vida se queda in-house (prorrateo) de todos modos ([[MEJORAS_FUTURAS]]).

**`parity_career` (loop-safe, opción "b" — solo marca/loguea, no auto-escribe):**
- Corre agendado (semanal), envuelto en `record_run`. Compara in-house vs proxy: conteos **exacto**,
  tasas con **tolerancia**.
- **Candado anti-loop:** marcador `CareerParityIssue(player, group, status, attempts)`. Disparidad
  nueva → se reporta y se marca; una vez marcada **UNRESOLVED no se vuelve a disparar** — queda
  logueada. La corrida cierra `SUCCESS` (todo cuadró) o **`PARTIAL`** con la lista irreconciliable en
  el `detail` (fila amarilla visible en *Ejecuciones*, nunca silenciosa, nunca en loop).
- **Qué significa un desajuste:** el proxy (MLB en vivo) es el árbitro de correctitud; un conteo que
  no cuadra casi siempre = **hueco o staleness en nuestras temporadas** → re-backfill de esas
  temporadas (manual en la opción "b"). Un humano arregla y borra el marcador. Edge cases
  irreconciliables se documentan como tolerancia conocida (como las 28 filas de `tb` en `derive.py`).

### 4c — Páginas de jugador (~970)
Vistas Django data-driven al mock `player.html`: hero + bio (`dgl_master`), tabs Bateo/Pitcheo/
Fildeo con Estándar + Avanzado/Sabermétrico, carrera + temporada, **regular + postemporada**. Slug
SEO; desambiguar nombres repetidos. Nota de cobertura para Ligas Negras.

### 4d — Páginas de líderes
Selector interactivo (categoría → tipo → métrica) del mock `leaders.html`, sobre las tablas de 4b.
Muestra el umbral aplicado y la nota "disponible desde YYYY".

### 4e — Datos de apoyo desde DGL (CSV → Postgres) — 📋 DISEÑADO, sin construir
Vía manual para lo que el proxy de MLB **no** da y sí existe en DGL: salarios, transacciones y los
tipos de batazo en los hits. Son datos casi estáticos, de una o dos actualizaciones al año, así que
no justifican un pipeline en vivo ni atar el proyecto a SQL Server.

El mecanismo: `static_data/` con un PowerShell por dataset (ruta de salida en constante, el SQL a la
vista, y el porqué documentado) → CSV → página de carga en el Backoffice → import que **trunca y
reemplaza**, con una prueba de aceptación propia por dataset.

Se construye **una vez** y cada dataset se monta encima. El primero es el de tipos de batazo, que
cierra SAB-03: hay diez temporadas donde a la API de MLB le faltan hits por tipo (2000 y 2001 en
~2%), y Retrosheet los tiene con 97% de cobertura — el hueco es de nuestra fuente, no del registro.

**Diseño completo, cobertura medida y decisiones abiertas: `docs/DATOS_DE_APOYO.md`.**

## Pendientes de code review que se cierran aquí
- **FIX-8** (umbral de apariciones): lo resuelve `dgl_metric` (qualifier configurable + override por
  temporada).
- **FIX-9** (nota Ligas Negras / cobertura): `available_from` + la nota en páginas/líderes.
