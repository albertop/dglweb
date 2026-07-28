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

- ~~**Tabla de games (temporada en curso).**~~ **HECHO (2026-07-28).** Es `dgl_team_season_games`,
  con grano (temporada, liga, equipo), y **no hizo falta que el dueño la proveyera**: sale de
  `/api/v1/standings` del proxy, que cubre desde 1956. 1.856 filas en 23 segundos, y la temporada en
  curso se refresca sola como primer paso del refresco diario.

  El prorrateo llega a los tres niveles: el umbral del oficio (`3,1 x juegos`), el propio de cada
  métrica (los coeficientes) y el fijo como red. Motivo: con 107 juegos jugados, 2026 publicaba CERO
  líderes de AVG, OBP, OPS, wOBA, wRC+, ERA y WHIP. Ver `stats/qualifier.py` y SAB-03 en `TODO.md`.

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

- ~~**Boards de postemporada** (DEV-03).~~ **HECHO.** `build_leaders` genera los tableros de octubre
  —9.382 filas medidas el 2026-07-28— con su propia dimensión en `Leader.postseason` y sus pisos
  fijos, que NO pasan por la cascada. El porqué está en `docs/UMBRALES_POSTEMPORADA.md`.
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
- ~~**Hueco de batazos en 2000 y 2001** (Fase 4c).~~ **RESUELTO en la Fase 4e (2026-07).** La fuente
  entregaba el 2% de los hits tipificados de esos años; se cargaron los de Retrosheet y hoy están en
  **88,6% y 89,1%** (medido el 2026-07-28). El propio documento sugería «reintentar la ingesta por si
  la fuente ya los corrigió» — se hizo mejor: se trajeron de otra fuente.

  Lo que queda de aquel problema son **siete temporadas de 1989-97** que siguen incompletas, y esas no
  tienen arreglo: a Retrosheet le falta la trayectoria de ~10% de los hits de esos años y eso no lo
  anotó nadie en su momento. Es el techo del registro histórico, no algo por hacer. **Se advierte en
  la UI** desde el 2026-07-27 (SAB-03b): las celdas afectadas van subrayadas, y las que sí están
  completas —los cinco conteos de outs por tipo— quedan limpias. Ver `derive.UNDERTYPED_COLUMNS`.

## Producción / hardening (del code review v1)

- ~~**FIX-10 — Ofelia socket.**~~ **CERRADO como riesgo aceptado (dueño, 2026-07-27).** El montaje es
  root en el anfitrión —el `:ro` protege el archivo, **no** la API, y conviene no olvidarlo— pero
  explotarlo exige ejecutar código dentro del contenedor del scheduler primero, y esa vía se cerró
  pinneando la imagen por digest. Las alternativas (un proxy del socket, o cambiar Ofelia por cron)
  cuestan más de lo que compran en un VPS de un solo dueño. Ver `docs/TODO.md`, SEC-02/SEC-03.
- ~~**FIX-11 — SRI / CSP.**~~ **HECHO (2026-07-27).** El SRI dejó de aplicar porque el CDN dejó de
  existir: Bootstrap y las fuentes se sirven desde `static/vendor/`. La CSP está puesta en
  `dglweb/core/csp.py`, estricta en el sitio público —`script-src 'self'`, sin inline— y más floja en
  `/cms/`. Para que se cumpliera hubo que mudar doce enganches inline a archivos bajo `static/js/`.
  Queda un pendiente vivo en `TODO.md`: añadir el dominio del ad server cuando se elija, o su etiqueta
  no cargará.

## Scheduler

- ~~**Wire `parity_career` al scheduler**~~ **HECHO.** Corre los domingos a las 8:00
  (`parity-career-weekly` en `ofelia/config.ini`).

## Jugadores deshabilitados

Ver `docs/JUGADORES_DESHABILITADOS.md` para el diseño completo. Lo que quedó pendiente:

- **Blindar el import del maestro contra revivir una baja.** Hoy `import_dgl_master` solo actualiza
  las columnas del extract de SQL Server, y `hidden` no está entre ellas, así que un re-import no la
  pisa. Pero eso es un accidente feliz e invisible: si alguien suma la columna al extract, la baja se
  revierte sola y en silencio. Merece un test que lo fije. **Prioridad baja** — el maestro
  prácticamente no se vuelve a importar.
- ~~**La búsqueda todavía no existe.**~~ **HECHO.** El buscador del encabezado sugiere mientras se
  escribe (`static/js/buscador.js`), degrada a un GET normal sin JavaScript, ignora tildes y eñes vía
  `unaccent`, y parte de `Player.objects` — que ya filtra a los deshabilitados. Su teclado tiene
  pruebas propias desde el 2026-07-28 (`tests/js/buscador.test.js`).
