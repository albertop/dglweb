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

- **Boards de postemporada** (DEV-03). El flag `Metric.postseason` ya se guarda pero `build_leaders`
  no genera líderes de postemporada. Falta extender el motor para leer `BattingPost/PitchingPost/
  FieldingPost` y añadir la dimensión regular-vs-post a `Leader` sin mezclar contextos.
- **`parity_career`: refinar la comparación de `g`** (Fase 4). El proxy `career` reporta un `g` que
  no cuadra con su propio `yearByYear` para pitchers (cuenta juegos-lanzados en la línea de hitting),
  generando ~298 falsos positivos. Quitar `g` de las columnas comparadas o comparar contra el
  `yearByYear` sumado. Nuestros totales son correctos.
- **Paridad de fildeo de carrera** (`parity_career` v2): comparar por posición contra los splits de
  fielding del proxy (sumando, excluyendo DH).
- **DEV-05 — `build_leaders` re-escanea por métrica.** No es bug; escalamiento. Agrupar por
  `stat_group` y traer las columnas una vez por grupo/posición, o materializar season-totals.

## Producción / hardening (del code review v1)

- **FIX-10 — Ofelia socket.** Montar el socket de Docker de forma más segura en producción
  (hoy `:ro` es suficiente para dev).
- **FIX-11 — SRI / CSP.** Subresource Integrity y Content-Security-Policy para el front (Fase 8).

## Scheduler

- **Wire `parity_career` al scheduler** (semanal) una vez construido, junto a `build_leaders`.
