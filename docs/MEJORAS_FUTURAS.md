# Mejoras futuras (backlog)

Ideas discutidas y **diferidas a propósito** — no son deuda ni bugs, son cosas que decidimos hacer
después. Cada una con el contexto suficiente para retomarla sin la conversación original.

## Daily refresh de temporada en curso — **A DISCUTIR** (no es trivial)

Hoy el scheduler corre `update_*` (refresh de la temporada actual) → `build_career_totals` →
`build_leaders`. Parece simple pero hay decisiones abiertas que hay que aterrizar juntos:

- **¿Qué es "temporada actual"?** Detección del año (rollover en enero, spring training, offseason);
  no hardcodear.
- **Datos parciales en curso.** La temporada viva es incompleta a diario. ¿Aparece en líderes (con
  umbral prorrateado por la **tabla de games**) y en totales de carrera (sí, acumula)? ¿Se marca como
  parcial en la UI?
- **Orden y acoplamiento de jobs:** refresh temporada → totales de carrera → líderes → `parity_career`.
  Un fallo intermedio no debe dejar líderes/carreras a medio construir.
- **Chicken-and-egg con la paridad:** `parity_career` marca "falta la temporada actual" hasta que el
  refresh corra ese día. ¿Se tolera la temporada en curso en la comparación?
- **Cierre de temporada:** transición de "en curso" a "final"; postemporada solo oct/nov.
- **Costo:** el refresh + rebuilds + parity son ~miles de llamadas/día. ¿Frecuencia, ventana, reintentos?

Es una conversación de diseño, no un ticket. Retomar antes de dar por cerrado el pipeline diario.

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
- **Postemporada de fildeo en el perfil** (Fase 4c). El tab de Fildeo se lanzó sin pill de
  Postemporada: `mlb_fielding_post` existe y tiene los datos, pero agregarlos es turbio. A diferencia
  de bateo/pitcheo, una línea de fildeo es por **posición**, así que un subtotal por ronda o por año
  mezclaría posiciones (PO como receptor + como jardinero en una sola fila), y las tasas —Fld%, RF—
  no tienen sentido sumadas entre posiciones. Si se retoma, mostrar el detalle por (temporada, ronda,
  posición) SIN subtotales agregados, o decidir con el dueño una agregación por posición. Bajo valor;
  revisar si en algún momento hace sentido.
- **Hueco de batazos en 2000 y 2001** (Fase 4c). En esas dos temporadas la fuente entregó los **outs**
  por tipo completos pero casi ningún **hit** por tipo: 91 hits tipificados en 2000 y 113 en 2001,
  contra ~5 100 hits reales (un 2%). En 1999 el match es exacto (4 957 = 4 957) y en 2003 casi
  (6 001 de 6 013). Consecuencia: GB%/FB%/LD%/PU% de esos años cuentan casi solo outs, los cuatro
  tipos suman ~67% en vez de 100%, y cada uno queda subestimado alrededor de un tercio.
  Quedan **dentro** del piso de 1989 (`derive.FIRST_STATCAST_SEASON`), así que el corte por año no
  las protege, y ahora los coeficientes alimentan tableros de líderes: un jugador con carrera corta
  concentrada en 2000-2001 compite con ratios malos. Decisión del dueño: **dejarlo así por ahora**
  para no agregar otra capa. Si se retoma, `available_from` no sirve (es un piso, no un hueco
  intermedio) — habría que excluir esas dos temporadas explícitamente, o mejor, reintentar la
  ingesta de esos años por si la fuente ya los corrigió.

## Producción / hardening (del code review v1)

- **FIX-10 — Ofelia socket.** Montar el socket de Docker de forma más segura en producción
  (hoy `:ro` es suficiente para dev).
- **FIX-11 — SRI / CSP.** Subresource Integrity y Content-Security-Policy para el front (Fase 8).

## Scheduler

- **Wire `parity_career` al scheduler** (semanal) una vez construido, junto a `build_leaders`.

## Jugadores deshabilitados

Ver `docs/JUGADORES_DESHABILITADOS.md` para el diseño completo. Lo que quedó pendiente:

- **Blindar el import del maestro contra revivir una baja.** Hoy `import_dgl_master` solo actualiza
  las columnas del extract de SQL Server, y `hidden` no está entre ellas, así que un re-import no la
  pisa. Pero eso es un accidente feliz e invisible: si alguien suma la columna al extract, la baja se
  revierte sola y en silencio. Merece un test que lo fije. **Prioridad baja** — el maestro
  prácticamente no se vuelve a importar.
- **La búsqueda todavía no existe** (el input del header es un placeholder). Cuando se construya,
  tiene que partir de `Player.objects`, que ya filtra.
