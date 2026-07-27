# Code Review v7

Fecha: 2026-07-26  
Alcance: lectura previa de `docs/*.md` y `docs/reviews/*.md`, con filtro contra `docs/TODO.md`.

## Exclusiones aplicadas

- No se reportan placeholders ni datos falsos de la pagina principal: es un known issue de desarrollo.
- No se repiten pendientes ya marcados en `docs/TODO.md`, incluyendo tabs calculados por request, SRI/CSP, exactitud futura de WAR/wOBA/wRC+/ERA-, umbrales in-season por juegos, staging de CSV en sesion, trazabilidad del rebuild en background, rate limiting amplio del buscador y hardening de `/ready`.
- Los hallazgos siguientes son nuevos o suficientemente distintos del backlog actual.

## Persona 1: Python Principal Developer

### DEV-01 [P1] `SeasonDates` permite terminar con mas de una temporada activa

**Evidencia:** `dglweb/stats/models.py:1602`, `dglweb/stats/models.py:1607`, `dglweb/stats/staticdata/loaders.py:485`, `dglweb/stats/season_window.py:72`.

**Finding:** la tabla solo tiene unicidad por `(season, sports_id)`. `SeasonDates.clean()` valida orden de fechas, pero no que exista una sola fila `is_active=True` por deporte. El loader detecta multiples activas dentro del CSV entrante, pero no compara contra filas activas ya persistidas. Como el dataset es `upsert`, una temporada vieja activa puede sobrevivir si el CSV nuevo no la incluye o si alguien marca otra activa desde Backoffice.

**Riesgo:** `season_window.evaluate()` resuelve el conflicto con `order_by("-season").first()`, es decir, el sistema queda en un estado invalido pero silencioso. El scheduler puede correr o saltar con la temporada equivocada.

**Sugerencia:** agregar una `UniqueConstraint` parcial por `sports_id` con `condition=Q(is_active=True)`, y completar `SeasonDates.clean()` con una consulta que excluya `self.pk`. El loader tambien deberia validar el resultado final esperado contra la base cuando aplica un upsert.

### DEV-02 [P2] `build_career_totals` hace delete+bulk insert sin candado ni clave natural

**Evidencia:** `dglweb/stats/career_totals.py:179`, `dglweb/stats/career_totals.py:222`, `dglweb/stats/career_totals.py:227`, contraste con `dglweb/stats/leaders.py:454` y `dglweb/stats/models.py:952`.

**Finding:** `build_leaders` protege su rebuild con advisory lock y una constraint unica. Las tablas `mlb_*_career`, en cambio, tienen solo indices por lectura (`player`, `sort_order`) y el rebuild borra e inserta todo dentro de una transaccion. Un `refresh_daily` y un rebuild disparado por Backoffice pueden pisarse.

**Riesgo:** carreras duplicadas, ventanas donde perfiles lean totales incompletos, o resultados de un rebuild viejo publicados despues de uno nuevo.

**Sugerencia:** usar un advisory lock tambien en `build_career_totals` y considerar constraints naturales por tabla: bateo/pitcheo `(player, level, team, league)` con `nulls_distinct=False`, fildeo `(player, level, pos)`.

### DEV-03 [P3] Quedan `verbose_name` con siglas espanolas en modelos de stats

**Evidencia:** `docs/AUTORIDAD.md:26`, `docs/AUTORIDAD.md:33`, `dglweb/stats/models.py:87-110`, `dglweb/stats/models.py:120`, `dglweb/stats/models.py:125`. Las columnas publicas de perfiles ya usan siglas inglesas en `dglweb/profiles/columns.py:56-72`.

**Finding:** aunque la UI principal ya usa `G`, `PA`, `R`, `SB`, `CS`, `SO`, `HBP`, etc., el metadata de modelo conserva labels como `J`, `AP`, `C`, `BR`, `AR`, `P`, `GP`, `TS`, `ES`, `DEB` y `AP/P`.

**Riesgo:** cualquier admin generico, export, formulario futuro o herramienta introspectiva puede reintroducir las siglas que `AUTORIDAD.md` prohibe.

**Sugerencia:** hacer un pase de labels de modelo para alinear metadata con la autoridad, aunque hoy esas tablas no esten expuestas como CRUD publico.

## Persona 2: QA / Reliability Engineer

### QA-01 [P1] Falta prueba del estado final cuando `seasons_dates` hace upsert

**Evidencia:** `tests/test_season_dates_loader.py:102` cubre dos activas en el CSV, pero no una activa existente mas una activa entrante. `engine.apply()` en `dglweb/stats/staticdata/engine.py:259-271` actualiza o crea sin apagar ausentes.

**Finding:** la prueba actual valida la forma del archivo, no la invariancia final de la tabla bajo modo upsert.

**Impacto usuario:** una carga aparentemente valida puede dejar al monitor y al scheduler leyendo la temporada equivocada.

**Sugerencia:** agregar test con 2025 activa persistida y CSV que solo trae 2026 activa. La expectativa deberia ser bloqueo o apagado explicito de la anterior.

### QA-02 [P2] El detalle de la pizarra solo se abre con hover

**Evidencia:** `templates/widgets/_pizarra_juego.html:8`, `templates/widgets/_pizarra_juego.html:27`, `static/js/pizarra.js:118-126`.

**Finding:** los dominicanos dentro de cada juego viven en un `<template>` que se muestra con `mouseenter`/`mouseleave`. La tarjeta no es focusable y no hay evento equivalente para teclado o touch.

**Impacto usuario:** en movil o navegando con teclado, el usuario puede ver la bandera de "hay dominicanos" pero no acceder al detalle ni a los videos asociados.

**Sugerencia:** convertir las tarjetas detallables en botones/focus targets con `aria-expanded`, abrir con click/Enter/Space/focus, y mantener hover como mejora para mouse.

## Persona 3: Frontend Engineer

### FE-01 [P2] La interaccion principal del widget de pizarra no es accesible por teclado/touch

**Evidencia:** `static/js/pizarra.js:50`, `static/js/pizarra.js:118-126`, `templates/widgets/_pizarra_juego.html:8`.

**Finding:** el patron actual depende de hover para descubrir contenido interactivo. Eso rompe keyboard navigation y pantallas tactiles.

**Sugerencia:** modelar cada juego con detalle como control expandible. El panel `#pizarra-detalle` deberia anunciarse con `aria-controls`/`aria-live` o quedar inmediatamente despues del control activo para que el foco tenga camino claro.

## Persona 4: Security Engineer

### SEC-01 [P2] `/health/pipeline` expone telemetria operativa sin autenticacion

**Evidencia:** `config/urls.py:21`, `dglweb/core/views.py:54`, `dglweb/core/views.py:91-100`, `tests/test_pipeline_health.py:84`.

**Attack scenario:** un tercero consulta `/health/pipeline` periodicamente y aprende si el scheduler esta caido, si el refresco fallo, que comandos existen y que paso fallo.

**Exploitation method:** GET anonimo al endpoint publico. En fallo parcial, la respuesta incluye `pasos` con el detalle del `IngestRun`.

**Business impact:** facilita reconocimiento operativo y permite atacar o publicar datos justo cuando el sitio esta sirviendo informacion vieja.

**Recommended fix:** mantener el status 200/503 para el monitor externo, pero devolver cuerpo minimo a clientes no autorizados. Para detalle, exigir header secreto del monitor, allowlist de IP, Basic Auth, o mover detalle completo al Backoffice.

## Persona 5: Backend Architect

### ARCH-01 [P1] La integridad de "una temporada activa" debe vivir en base de datos

**Evidencia:** `dglweb/stats/models.py:1602`, `dglweb/stats/season_window.py:72`.

**Finding:** esta es una regla de dominio global, no solo una validacion de formulario o CSV. Hoy cualquier camino que no pase exactamente por el loader feliz puede romperla.

**Sugerencia:** constraint parcial en Postgres: una fila activa por `sports_id`. Luego adaptar loader/backoffice para presentar un error claro antes de que la DB rechace el write.

### ARCH-02 [P2] Rebuilds derivados no comparten la misma estrategia de concurrencia

**Evidencia:** `dglweb/stats/rebuilds.py:18`, `dglweb/stats/leaders.py:454`, `dglweb/stats/career_totals.py:179`, `dglweb/stats/career_totals.py:222`.

**Finding:** `build_career_totals` y `build_leaders` son una cadena, pero solo la segunda mitad esta protegida contra ejecuciones concurrentes. No es el pendiente de trazabilidad del thread; es integridad/idempotencia del dato derivado.

**Sugerencia:** definir un lock de rebuild derivado para toda la cadena o locks separados pero ordenados. Evitar que dos procesos puedan reconstruir carrera y lideres sobre snapshots distintos.

## Persona 6: Experto en beisbol y sabermetria

### SAB-01 [P1] La cERA de carrera parece ponderarse por juegos, no por innings de receptor

**Evidencia:** `dglweb/profiles/columns.py:224`, `dglweb/stats/career_rate.py:82`, `dglweb/stats/career_rate.py:154-168`, `dglweb/stats/career_totals.py:81-107`, `dglweb/profiles/tabs.py:637-641`.

**False assumption:** que una tasa de receptor se puede ponderar por `G` igual que otras tasas de fildeo. `cERA` es carreras limpias permitidas por 9 entradas mientras el catcher esta detras del plato; su ponderador natural es innings/outs, no juegos.

**Impacto beisbolero:** dos temporadas con el mismo numero de juegos pero cargas de innings muy distintas influyen igual. Eso puede distorsionar la linea de carrera de receptores, especialmente backups, cambios defensivos o temporadas con uso parcial.

**Sugerencia:** tratar `catcher_era` como tasa especial ponderada por `innings_outs` de la fila de C, o guardar los componentes necesarios si la fuente los provee. Si no se puede reconstruir con confianza, marcarla como aproximada o no mostrar total de carrera.

### SAB-02 [P3] Siglas internas aun contradicen la autoridad editorial

**Evidencia:** `docs/AUTORIDAD.md:26-41`, `dglweb/stats/models.py:87-110`.

**Finding:** aunque el lector ya ve `RBI` y no `CI`, quedan siglas espanolas para otras estadisticas en metadata interna (`J`, `AP`, `C`, `BR`, `AR`, `P`, etc.).

**Sugerencia:** alinear esos labels con convenciones MLB/baseball-reference: `G`, `PA`, `R`, `SB`, `CS`, `SO`, `IBB`, `HBP`, `SH`, `SF`, `LOB`. Esto evita que futuras pantallas administrativas o exports salgan con lenguaje mixto.

## Prioridad recomendada

1. Corregir integridad de `SeasonDates`: constraint parcial + validacion contra estado final del upsert.
2. Proteger `build_career_totals` con lock/constraints antes de tener mas rebuilds manuales concurrentes.
3. Arreglar cERA de carrera o marcarla como aproximada.
4. Hacer accesible el detalle de pizarra por click/teclado/touch.
5. Reducir informacion anonima de `/health/pipeline`.
6. Limpiar `verbose_name` residuales de stats.
