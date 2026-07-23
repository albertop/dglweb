# Mejoras futuras (backlog)

Ideas discutidas y **diferidas a propósito** — no son deuda ni bugs, son cosas que decidimos hacer
después. Cada una con el contexto suficiente para retomarla sin la conversación original.

## Motor de líderes / datos

- **Auto-remediación de paridad (opción "a").** Hoy `parity_career` solo **marca y loguea** las
  disparidades (opción "b"). Encima del mismo marcador `CareerParityIssue` se puede activar el
  auto-sanado: al detectar disparidad nueva, re-fetchear del proxy las temporadas de ese jugador y
  recargarlas (un intento, guardado por el marcador; si sigue mal → PARTIAL en bitácora, no reintenta).
  El candado anti-loop ya estaría hecho; solo se le agrega la acción de escritura.

- **Tabla de games (temporada en curso).** Para los umbrales de tasa en la temporada viva hay que
  prorratear por juegos jugados. Los **conteos** en curso ya funcionan (acumulación simple, sin
  umbral). Falta la tabla `games` (temporada → juegos del equipo, actualizada a diario) que el dueño
  proveerá; el motor consultaría esos juegos para prorratear el qualifier. Ver `stats/qualifier.py`.

- **Sabermetría de carrera exacta (WAR, wOBA, wRC+, ERA-…).** Hoy se **prorratean** (promedio
  ponderado por playing-time) porque no tienen suma limpia y **el proxy no da sabermetría de carrera**
  (probado: `stats=sabermetrics` a nivel carrera vuelve vacío). Si algún día se consigue una fuente
  o fórmula con contexto de liga por año, reemplazar el prorrateo por el cálculo exacto en
  `stats/career_rate.py`.

- **Liderazgos all-MLB (todos los peloteros).** El dueño tiene "otro plan" para esto. El sitio viejo
  ya lo hacía en paralelo (`dgl_lideres_all` desde vistas `vw_bdb_*`). Por ahora **solo dominicanos**.

- **`veces` — "más veces líder".** Rollup de cuántas veces un jugador aparece como líder
  (el sitio viejo lo tenía en `dgl_lideres_seasons_resumen`). Diferido: es feature de UI, el foco fue
  el engine. Derivable de `dgl_leader`.

- **`uzr` mal clasificado como tasa.** UZR es acumulativo (runs sobre el promedio), pero el heurístico
  `Float→PRO` lo marcó como tasa. En carrera se prorratea (aproximado) cuando debería sumarse. Ajuste
  de metadata en `dgl_metric` (o un tipo "float acumulable").

## Producción / hardening (del code review v1)

- **FIX-10 — Ofelia socket.** Montar el socket de Docker de forma más segura en producción
  (hoy `:ro` es suficiente para dev).
- **FIX-11 — SRI / CSP.** Subresource Integrity y Content-Security-Policy para el front (Fase 8).

## Scheduler

- **Wire `parity_career` al scheduler** (semanal) una vez construido, junto a `build_leaders`.
