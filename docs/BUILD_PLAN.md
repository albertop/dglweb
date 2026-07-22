# Plan de construcción interno — hacia el big-bang

> **Producto vs. construcción.** El `CONCEPT.md` tiene el *roadmap de producto* (Launch →
> fast-follows LIDOM/Spring → Fase 2). **Este documento es distinto:** son las **fases internas de
> ingeniería** para *construir* el launch scope — **una por una, paso a paso, NO de un tirón.**
>
> **Realidad reconocida:** el launch scope **NO es un MVP pequeño** (data pipeline + CMS + páginas
> data-driven + live + auth + ads + infra). Por eso, aunque la apertura sea "big-bang público",
> **internamente** se construye con fases disciplinadas y un **staging/beta** persistente.

## Reglas del juego (disciplina)

- **Staging permanente:** cada fase se despliega y se **verifica en staging** antes de pasar a la
  siguiente. El big-bang público es el **flip final** tras un **beta/dress-rehearsal** completo.
- **Una fase a la vez.** No se arranca la siguiente hasta que la actual cumple su "Done when".
- **TDD (ver CODING_STANDARDS):** cada pieza se construye test-first. "Done" incluye tests verdes.
- **Cada fase entrega algo demostrable** en staging (no trabajo invisible).
- **El contenido corre en paralelo:** escribir los **8–12 artículos** es el cuello de botella →
  empieza apenas exista el editor (Fase 5) y sigue en paralelo hasta el launch.

---

## Fase 0 — Mock / prototipo visual — ✅ COMPLETADA (2026-07-16)

- **Meta:** **ver y aprobar el layout y el estilo** del sitio **antes** de construir backend. Clave
  para un dueño sin background de diseño: quita el riesgo visual de entrada.
- **Entregado** (en `apps/dglweb/mockup/`): mock estático clickable de las **4 páginas clave**:
  - **`index.html`** (landing) — header navy + **players search**, **cintillo EN VIVO**,
    **Destacados de la jornada** (bateadores + lanzadores), widget de Líderes, grid de artículos,
    y **4 zonas de anuncio** (728×90 arriba, in-feed, 300×250 sidebar, 728×90 abajo).
  - **`article.html`** — tipografía híbrida (mono UI/títulos/stats + **serif legible** en cuerpo),
    bloques embebidos (pull quote, tabla de stats, menciones enlazadas).
  - **`player.html`** — estilo BBRef, hero + **tabs de stats** (extensible sin alargar la página).
  - **`leaders.html`** — **selector interactivo** (categoría → métrica → carrera/temporada = 1
    tabla a la vez); leyendas dominicanas reales.
- **Decisiones "lock" de la Fase 0:**
  - **CSS:** Bootstrap 5. **Paleta:** navy sobrio + acentos rojo/azul (guiño RD). Responsive OK.
  - **Tipografía:** **JetBrains Mono** (UI/stats/títulos) + **Source Serif** (cuerpo de artículo).
  - **Sin subtítulo** en el brand (redundante). Títulos de página a 3rem.
  - Módulo del sidebar = "Destacados de la jornada" (no pizarra); pizarra completa → página aparte.
- **⭐ No desechable:** el mock es **HTML/CSS reutilizable** → se convierte en los templates base de
  Django en la **Fase 1**.
- **✅ Done:** el dueño **aprobó** el layout/estilo. Fase 0 cerrada.

## Fase 1 — Fundaciones / esqueleto — ✅ COMPLETADA (2026-07-16)

- **Meta:** un sitio Django+Wagtail **desplegable**, vacío pero con todo el andamiaje.
- **Entregado:**
  - ✅ Proyecto Django+Wagtail con la estructura de `library-guidelines.md`; Postgres; Docker
    (`docker-compose`: web + db). Corre en **Python 3.13 dentro de Docker** (host tiene 3.14).
  - ✅ Settings por entorno (base/dev/prod), secrets por env con fallo-ruidoso.
  - ✅ **CI verde:** ruff (line-120, ANN/N) + mypy (**strict + django-stubs**) + pytest (TDD).
    Corre local (`make check`) **y en GitHub Actions** (repo privado `albertop/dglweb`).
  - ✅ **Shell de UI = mock (Fase 0) integrado** como templates Django (`base.html` + `home.html`).
  - ✅ 3 smoke tests, 100% cobertura. Wagtail admin en `/cms/`.
- **Staging:** por ahora = **stack local de Docker** (el VPS está intocado hasta el big-bang);
  se formaliza más cerca del lanzamiento.
- **🟡 Sub-item — proxy `mlb-api`:** ✅ **bumpeado a Python 3.13** (Dockerfile + pyproject), ✅
  line-120, ✅ **git en repo propio + CI de GitHub Actions**, ✅ 294 tests verdes en 3.13. Diferido
  (gradual, per estándar): **restructura a `src/`** y **mypy strict completo** (hoy lenient).
- **✅ Done when:** mock corre como sitio Django ✅, CI verde ✅, smoke tests pasan ✅.

## Fase 2 — Fundación de datos: tabla maestra + CRUD admin — ✅ COMPLETADA (2026-07-21)

- **Meta:** la **autoridad de "quién es dominicano"** operativa.
- **Entregado:**
  - **Modelo `Player`** (`dglweb/players/models.py`, tabla `dgl_master`, 28 campos) con el schema
    **derivado de los tipos reales** de `dbo.dglMaster` en SQL Server — nada asumido. La regla de
    autoridad y las 4 conversiones `0 → NULL` quedan documentadas en el docstring del módulo.
  - **Migración de datos ejecutada** contra el dev server **10.0.0.39**: **984/984 filas**, con las
    4 conversiones de centinela verificadas una por una (`yahoo_id` 143 nulos, `fangraphs_id` 3,
    `sign_year` 1, `dom_hof_year` 55 no-nulos; cero `0` restantes).
    `dom_players` (11 753 filas) **intacta** y reasignada a `dglweb_user`.
  - **Loader repetible:** `manage.py import_dgl_master` (valida las 28 columnas, exige `--replace`
    para sobrescribir, carga en una transacción).
  - **Sección Backoffice extensible** (`dglweb/backoffice/wagtail_hooks.py`): un
    `SnippetViewSetGroup` que es **el punto único de ensamblaje** de las herramientas de admin.
    El CRUD de jugadores es la primera; las próximas se agregan a `items` sin tocar el menú.
  - **CRUD de jugadores** (`dglweb/players/viewsets.py`): listado con búsqueda/filtros/orden y
    formulario agrupado en 6 secciones, **todo en español**.
- **Done when:** ✅ el admin gestiona los 984 jugadores; **21 tests verdes**, 99 % de cobertura,
  ruff + ruff format + mypy strict limpios.
- **Notas para fases siguientes:**
  - **Postgres alineado (2026-07-21):** los tres entornos usan **`postgres:18` (Debian)**.
    Local y CI corrían `16-alpine` contra un servidor 18.4 Debian, lo que además de romper
    `pg_dump` entre entornos ordenaba **mal los nombres en español** (musl ordena por byte:
    "Félix" después de "Freddy"). Hay un test de regresión que lo bloquea.
    **Regla:** la imagen de Postgres es la misma en local, CI y prod — **nunca `-alpine`**.
  - **Stack movido a LTS (2026-07-21):** Django 5.1 → **5.2 LTS** y Wagtail 6.4 → **7.4 LTS**.
    Ambas versiones viejas estaban **fuera de soporte** (Django 5.1 EOL dic-2025, Wagtail 6.4 EOL
    ago-2025). Se hizo ahora, con la superficie Wagtail mínima (un modelo + un viewset), y no
    después de la Fase 5. Cero migraciones propias; gate verde. Ver `library-guidelines.md`.
  - **Pendiente de Fase 5:** restringir el Backoffice al rol *administrators* (hoy es solo
    superusuario, que es el default seguro).

## Fase 3 — Pipeline de datos: scrapers en marcha (ANTES del backfill)

- **Meta:** la data **se actualiza sola** (regla del dueño: pipeline vivo antes que backfill).
- **Entrega:** scrapers como **management commands** + contenedor programado; tablas de stats
  (schema managed) pobladas/actualizadas vía ORM; degradación elegante si el proxy falla.
- **Done when:** los scrapers actualizan stats en schedule, observable en staging (con tests que
  mockean el proxy en los bordes).
- **Progreso (batting, 2026-07-21):**
  - `dglweb/mlb/client.py`: cliente del proxy — una sola excepción, reintentos solo en 5xx/timeout.
  - `mlb_batting` (75 col.), capa de mapeo y ligas por **id** (no por nombre: el mismo endpoint
    escribe la liga de 3 formas). Descarga por temporada + `import_batting` idempotente.
  - **Test de paridad** (`parity_batting` + `dglweb/stats/parity.py`): compara contra un extracto
    de `dbo.mlbBatting`. Conteos exactos, sabermétricas con tolerancia (MLB recalcula WAR).
  - **Paridad 2024 verificada: 106/106 filas, 0 faltantes, todos los conteos exactos.** Las
    únicas diferencias son esperadas y correctas: (a) WAR difiere en decimales por recálculo
    retroactivo de MLB; (b) `pos` — el origen usa `primaryPosition` (del jugador), nosotros la
    posición jugada esa temporada; (c) 13 lanzadores con `wOBA`/`wRC+` en NULL porque el proxy
    **no manda esas claves** para ellos (el origen tiene 0 por `replace_na`; NULL es más honesto).
- **Las 15 tasas derivadas portadas (2026-07-21, `dglweb/stats/derive.py`):**
  - **Grupo 1 (estándar):** AVG, OBP, SLG, OPS, BABIP, ISO, ABpHR, BBpSO, PApSO, RunsProduced.
  - **Grupo 2 (exóticas de `mlbstats`):** BsR, EqA, GrossProdAvg, RC (`rc3`), TotalAVG —
    portadas del código fuente de `mlbstats` que pasó el dueño.
  - **Cada fórmula verificada contra las 120 929 filas de origen**: en las filas con valor real,
    coinciden al float (0 divergencias). Dos sutilezas que la verificación fijó: SLG/ISO/GPA
    salen de los componentes de hits; **BsR/EqA/RC/TotalAVG usan el `TB` almacenado** (reproduce
    una inconsistencia real del origen en 28 filas viejas donde TB difiere de los componentes).
  - **Paridad 2024, tolerancia 0.001, las 15 columnas: 106/106 filas, 0 discrepancias.** Los
    únicos huecos son 13 lanzadores con AB=0 → NULL en vez del `.000` del origen (regla
    NULL-sobre-0, a propósito; el comando los marca como "sin poblar", que es correcto).
- **`pos` — decidido (opción b):** guardamos la **posición de la temporada** (viene en cada split
  de `/api/v1/stats`, sin llamada extra), no la `primaryPosition` del origen. Es más informativa
  para una página de jugador año por año. Diverge del origen a propósito, así que **`pos` se
  excluye de la comparación de paridad** (si no, marcaría cada cambiado y cada OF como falso
  positivo). El cargador ya lo hacía; no hubo cambio de descarga.
- **Bitácora + scraper programado (2026-07-21) — el pipeline ya se actualiza solo:**
  - **`IngestRun`** (`ingest_run`, genérico para todos los scrapers): registra cada corrida —
    comando, alcance, estado (RUNNING/SUCCESS/PARTIAL/FAILED), inicio/fin, filas, detalle/error.
    Fila RUNNING al entrar (un cuelgue es visible). Helper `record_run`
    (`dglweb/stats/runlog.py`). Solo lectura (`default_permissions = ("view",)`): es una caja
    negra, no se edita a mano.
  - **Visible en el Backoffice** (`IngestRunViewSet`, sección "Ejecuciones"): lista con estado,
    filas y duración; inspect con el detalle/error. Verificado en el navegador.
  - **`update_batting`**: refresca la temporada actual (idempotente); es lo que corre el
    scheduler. El backfill histórico sigue siendo `import_batting --from --to` a mano.
  - **Ofelia** en `docker-compose` (`scheduler`): cron docker-native, lee labels del servicio
    `web` y hace `job-exec` del comando (misma imagen, TZ America/Santo_Domingo, 6am). Verificado:
    job `batting-daily` registrado. Si algún día el update pesa → cambiar a `job-run` (contenedor
    efímero, aislamiento total).
  - Upsert compartido extraído a `dglweb/stats/loader.py` (`save_batting_rows`), usado por ambos
    comandos.
- **Pitching portado (2026-07-21) — segundo grupo sobre el motor probado:**
  - **`mlb_pitching` (101 col.)**, `pitching_mapping.py` (las tasas vienen directas del proxy como
    strings → parseadas a float), una sola fórmula `mlbstats` (**BAA**, verificada a 0 diferencias
    en toda la tabla), y `X1B`/`NIBB` derivados. Comandos `import_pitching` / `update_pitching`.
  - **Diferencia clave verificada contra el origen:** pitching **NO invierte los stints** (stint 1
    = equipo más antiguo), al revés que batting — porque el script R de pitching numera ascendente
    y el de batting invierte. Confirmado con un cambiado viejo de cada uno (Marte 2008, Astacio 2005)
    cruzando el orden del proxy. Es un flag por deporte (`reverse_stints`), no una suposición.
  - **Refactor DRY:** la maquinaria de descarga (`_download.py`, parametrizada por `SportConfig`),
    el loader (genérico sobre el modelo) y el cuerpo de los comandos (`ingest.py`) ahora se comparten
    entre batting y pitching; **fielding solo agregará su modelo + mapeo**. Batting intacto (tests verdes).
  - **Paridad pitching (2008–2009, tolerancia 0.02): 172/172 filas, 0 discrepancias.** Único matiz:
    la tabla `mlbPitching` de temporadas **recientes está desactualizada** (el dueño la corrió hace
    tiempo) → la paridad se hace contra una **temporada vieja estable**. Los huecos son 36/34 tasas
    indefinidas (win_pct sin decisiones, sb_pct sin intentos) → NULL-sobre-0, a propósito.
  - `update_pitching` agregado al scheduler Ofelia (6:15am, tras batting).
- **Campos extra del proxy (decisión del dueño, 2026-07-21):** el API ofrece más de lo que las
  tablas de origen guardan. La mayoría es redundante (ya lo calculamos, ej. AVG/OBP/SLG; o es un
  ratio de columnas que ya tenemos, ej. SBpct/whiff%/per-PA → se calculan al vuelo). Se persisten
  **solo los crudos no derivables**: batting `age`, `roe`, `gidp_opp`; pitching `age`, `ab`
  (turnos en contra), `sh_fail`, `sh_missed`. Son aditivos (sin contraparte en el origen), así que
  **no entran en la paridad** — verificado: pitching sigue 172/172, 0 discrepancias.
- **Fielding portado (2026-07-21) — tercer y último grupo de temporada regular:**
  - **`mlb_fielding` (26 col. + age)**, `fielding_mapping.py`. **Sin fórmulas** — todo directo del
    proxy; UZR de sabermetrics. La única función `mlbstats` posible (`baa`) es de pitching, no aquí.
  - **Llave limpia `(player, season, team, pos)` — decisión del dueño.** Fielding es por posición
    (un jugador defiende varias), y el `stint` del origen es un contador de R con **~178 grupos de
    filas duplicadas exactas**. Descartamos el contador y keyeamos por la identidad real; los
    duplicados colapsan. Un jugador cambiado tiene por posición: fila por equipo + fila `XXX` (el
    total de esa posición), tal como el proxy lo devuelve (el total NO se computa, viene del API).
  - **`fielding_source.py`** (propio, no usa `_download.py` porque ese es por-equipo): el bulk da el
    total por (jugador, posición); las per-equipo salen de la llamada por jugador (solo si cambió).
  - **Paridad 2006 (Héctor Luna incluido, tolerancia 0.02): 312/312 filas, 0 faltantes, 0 sobrantes.**
    Las 11 "discrepancias" son UZR donde **el origen tiene 0 y nosotros el valor real**: el merge
    por `stint` del script R **no adjunta UZR a varias filas de jugadores cambiados** → nuestro port
    lo arregla (adjunta por jugador+posición). Otro caso donde el port es más correcto que la fuente.
    Los huecos son NULL-sobre-0 (stats de catcher en no-catchers, tasas indefinidas).
  - `import_fielding`/`update_fielding` + `parity_fielding`; `update_fielding` en el scheduler
    (6:30am). Loader y paridad generalizados para aceptar la llave por-posición.
- **Postemporada de batting portada (2026-07-22) — `mlb_batting_post`:**
  - **Llave `(player, season, round)`** con rondas **DS/WC/LCS/WS** (gameType `D`/`F`/`L`/`W`).
    Verificado: 0 duplicados; sin stint/XXX/llamadas por jugador (un equipo por ronda). 59 columnas
    = conteos + tasas derivadas (grupos 1 y 2) + batted-ball; **sin sabermetrics** (el script solo
    usa season+seasonAdvanced). Reusa `map_regular`/`map_advanced`/`derived_rates` (se descartan los
    extras `age/roe/gidp_opp` que la fuente no tiene).
  - **`batting_post_source.py`** itera las 4 rondas con `gameType` — resuelve **FIX-7** para post.
    Loader/paridad/ingest reusados con la llave por ronda. `update_batting_post` en el scheduler.
  - **Paridad 2013 (David Ortiz incluido, tol. 0.001): 26/26 filas, 0 discrepancias.** WS de Ortiz
    .688 idéntico a la fuente. Huecos = NULL-sobre-0 (denominador cero).
- **Postemporada de pitching portada (2026-07-22) — `mlb_pitching_post`:** 88 columnas, llave
  `(player, season, round)`. Regular + advanced de pitching **sin sabermetrics ni extras**, con
  `BAA` (reusa `pitching_mapping`/`derive_pitching`; descarta age/ab/sh_fail/sh_missed).
  `pitching_post_source.py` itera las 4 rondas con `gameType`. **Paridad 2013: 20/20 filas, 0
  discrepancias** (huecos = tasas indefinidas NULL-sobre-0). `update_pitching_post` en el scheduler.
- **📌 Pendiente para cerrar la fase:** **postemporada de fielding** (`mlbFieldingPost`) — mismo
  patrón, sobre el motor probado. Es la última pieza de la Fase 3.

## Fase 4 — Backfill histórico + LÍDERES + páginas de jugador

- **Meta:** el **diferenciador estrella** vivo con datos reales.
- **Entrega:** command de **backfill** (una vez); **agregados de Líderes** (carrera + temporada)
  precalculados; **páginas de jugador (~970)** con stats **sabermétricas**; páginas de **Líderes**.
- **Done when:** páginas de jugador y Líderes navegables en staging con histórico real.
- **📌 Aparcado para esta fase (hallazgos de la Fase 3, NO implementar antes):**
  - **Hace falta un mínimo de apariciones.** Sin él, los líderes de por vida en promedio los
    encabezan relevistas de 2-de-2 (Gregory Soto y Esteban Yan en 1.000). Con un mínimo, la
    tabla queda publicable: Vladimir Guerrero .318, Manny Ramírez .312, Mateo Alou .307. El
    ruido está por debajo de las 1 000 PA; el top 5 es idéntico con 1 000 o con 3 000.
  - **El mínimo de temporada debe calcularse contra los juegos del equipo**, no fijarse en 502:
    los datos van de 1876 a 2025 e incluyen 2020 (60 juegos) y las Ligas Negras (~20).
  - **Los 7 de Ligas Negras** (Tetelo Vargas, Horacio Martínez, Enrique Lantigua, Sijo Gómez,
    Pedro San, Néstor Lambertus, Julio Báez — 6 de ellos en el Salón de la Fama dominicano)
    tienen 22 filas, sin WAR ni wOBA ni conteo de lanzamientos. Lo que MLB les reconoce es una
    astilla de su carrera real → sus páginas necesitan una nota de contexto.
  - **Decisión pendiente del dueño:** el valor del umbral (o hacerlo configurable en backoffice).

## Fase 5 — Editorial: Wagtail (artículos + workflow + roles)

- **Meta:** que **writers/editors** puedan producir contenido.
- **Entrega:** `Article` Page con **StreamField** (bloques: párrafo, **tabla**, **gráfico**,
  **embed de jugador**); **workflow de aprobación**; **roles/grupos**; hashtags; links por mención.
- **Done when:** flujo borrador → aprobación → publicación funciona en staging (con tests).
- **⏩ En paralelo desde aquí:** arranca la escritura de los **8–12 artículos semilla**.

## Fase 6 — Módulos vivos: pizarra MLB + resumen jornada + ticker (season-aware)

- **Meta:** el sitio "se siente vivo".
- **Entrega:** vistas **HTMX** que consultan el proxy (server-side, con timeout); lógica
  **season-aware**; degradación elegante en off-season/proxy caído.
- **Done when:** pizarra/ticker MLB actualizándose en staging.

## Fase 7 — Auth social + zonas de ads + landing + players search

- **Meta:** el sitio toma su forma final.
- **Entrega:** **django-allauth** (Google/Facebook, sin muro); **zonas de anuncio agnósticas** +
  tag del ad server hosted; **landing estilo Savant** (artículos + live + líderes ensamblados);
  **players search** (typeahead HTMX sobre la tabla maestra → página del jugador).
- **Done when:** el sitio completo (anónimo) navegable en staging; login social funciona; el
  buscador de jugadores lleva a la página correcta.

## Fase 8 — Endurecimiento para producción

- **Meta:** listo y resiliente para el mundo.
- **Entrega:** **SEO base** (URLs, sitemap, metadatos, datos estructurados); **legal** (privacidad
  + consentimiento cookies + ToS); **Umami Cloud**; **infra:** reverse proxy + TLS, Cloudflare,
  **backups offsite de Postgres**, monitor de uptime.
- **Done when:** checklist de producción completo; staging = réplica de prod.

## Fase 9 — Beta / ensayo general → 🚀 BIG-BANG

- **Meta:** abrir al público con confianza.
- **Entrega:** **8–12 artículos cargados**; QA end-to-end en staging (beta real); ajustes finales;
  **flip a público**.
- **Done when:** el sitio está vivo en `dominicanosengrandesligas.com`.

---

## Dependencias (por qué este orden)

- **0 (mock)** primero: aprueba el estilo/layout barato, antes de todo; su HTML/CSS **alimenta** la
  Fase 1 (no se tira).
- **2 (tabla maestra)** es la **llave** de todo el recorte dominicano → va temprano.
- **3 (scrapers) antes que 4 (backfill)** → regla explícita del dueño.
- **4 (Líderes)** necesita histórico (backfill) → después de 3.
- **5 (editorial)** destraba la escritura de contenido (el **cuello de botella**) → cuanto antes.
- **6–7 (live, auth, ads, landing, search)** ensamblan sobre datos + contenido ya existentes.
- **8 (infra/legal/SEO)** puede prepararse en paralelo, pero **cierra** antes del beta.
- **Backups offsite** deben existir **apenas haya contenido real** (no esperar a Fase 8 si ya se
  está cargando contenido en staging que no se quiera perder).
