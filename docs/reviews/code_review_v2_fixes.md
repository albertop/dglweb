# Code Review v2 — plan de fixes

Análisis a fondo de cada finding (no se aceptó ninguno a ciegas). Decisiones del dueño (2026-07-23).

## To-do (findings reales)

- [x] **DEV-01** — Parser de umbrales *fail-open*. Validar las fórmulas al guardar (rechazar
  inválidas en el form) y en `qualifies()` fail-**closed** (vacío = sin umbral → todos; inválida →
  NO todos). No se agrega `AND` (no se usa).
- [x] **DEV-02** — `prod.py` debe exigir `MLB_PROXY_URL` y `MLB_PROXY_API_KEY` (sin default).
- [x] **DEV-03** — Flag `postseason` sin efecto. **Decisión: diferir + documentar** (marcar como
  reservado; boards de postemporada = fase aparte sobre las tablas `*_post`).
- [x] **DEV-04** — `build_leaders` sin protección de concurrencia. Advisory lock + `UniqueConstraint`
  en `Leader` con `nulls_distinct=False` (PG18).
- [x] **SAB-01** — Documentar la exclusión de Ligas Negras de los líderes (comentario en
  `FIRST_SEASON` + `FASE4_PLAN`).
- [x] **SAB-02** — Innings. **Decisión: activar el board de innings de fildeo** (alias
  `innings_outs`→`Inn` activo) **y convertir el valor de IP/Inn a entradas** (`outs/3`) en `dgl_leader`.
- [x] **SAB-03** — `kind` de floats acumulativos. **Decisión: curar** — CUMULATIVE: WAR, RAR, wRAA,
  wRC, UBR, wGDP, wSB, ra9_war, UZR y run-components (positional_adj, batting, fielding, base_running,
  replacement, w_league). RATE: wOBA, wRC+, SPD, FIP-, ERA-, LI. Tests: career WAR y career UZR.
- [x] **SAB-04** — Agregar **1960** (154 juegos) a los overrides de temporada corta. (1961 mixto y el
  cálculo por juegos reales → tabla de games, backlog.)
- [x] **SAB-06** — Empates de tasas por float exacto. Rankear/almacenar con la precisión de despliegue.

## Descartados / diferidos

- **SAB-05** — **NO es real.** Verificado: nuestro `ab` de pitcheo = turnos-en-contra
  (`BF-BB-HBP-SH-SF-CI`, 2920/2923 filas). BAA de carrera (`H/ab`) usa la **misma** definición que la
  de temporada. El reviewer no tenía ese dato.
- **DEV-05** — Re-scan por métrica en `build_leaders`. El reviewer mismo dice "no es bug"; es
  escalamiento → `docs/MEJORAS_FUTURAS.md`.

## Nota de Fase 4 (no del review)

La primera `parity_career` real dio **298 disparidades**, dominadas por `g` (juegos). Diagnóstico:
el proxy `career` reporta un `g` que **no cuadra con su propio `yearByYear`** para pitchers (cuenta
juegos-lanzados en la línea de hitting). **Nuestros totales son correctos** (suman al yearByYear).
→ Fase 4: refinar `parity_career` (quitar `g` de la comparación o comparar contra yearByYear sumado).
