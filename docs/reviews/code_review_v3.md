# Code Review v3

Alcance: revision estatica del proyecto, despues de leer los `.md` debajo de `docs/`.
No se modifico codigo fuente.

Verificacion ejecutada:

- `docker compose run --rm --no-deps web ruff check .` - OK
- `docker compose run --rm --no-deps web mypy .` - OK, 122 source files
- `docker compose run --rm web pytest` - OK, 373 passed, cobertura total 96%

Nota de contexto: el arbol de trabajo ya tenia cambios locales antes de este review. Este archivo
solo registra findings; no revierte ni toca esos cambios.

## Persona 1 - Python Principal Developer

### Finding DEV-01 - La pagina de jugador calcula todos los tabs en cada request

Severidad: Media

Evidencia:

- `dglweb/profiles/views.py:81-89` construye la lista de tabs y llama `tab.context(player)` para
  cada tab aplicable, aunque solo el primer tab se muestra activo.
- `dglweb/profiles/tabs.py:305-371` arma el contexto completo de bateo/pitcheo: temporadas,
  lineas, liderazgos, qualifiers, mejores personales, carrera, postemporada y Statcast.
- `dglweb/profiles/tabs.py:382`, `dglweb/profiles/tabs.py:398` y
  `dglweb/profiles/tabs.py:423` hacen queries de existencia por tab antes de calcular los contextos.
- `dglweb/profiles/views.py:95-96` vuelve a consultar totales de carrera para el hero.

Riesgo:

La pagina escala por "cantidad de tabs y tablas", no por lo que el usuario esta viendo. Un jugador
con bateo, pitcheo, fildeo y postemporada dispara varias consultas y agregaciones aun si el usuario
solo abre el tab inicial. Hoy la suite pasa, pero el costo se notara mas cuando fielding deje de ser
placeholder o cuando se agreguen Splits/Game Logs.

Sugerencia:

Hacer lazy loading por tab, idealmente con HTMX o endpoints parciales (`/jugador/<slug>/batting/`,
`/pitching/`, etc.), y dejar en el render inicial solo el tab activo y los datos del hero. Si se
prefiere mantener SSR completo, agregar un test de presupuesto de queries para un jugador con
bateo+pitcheo+postemporada y reutilizar los totales ya calculados en el contexto del tab para el
hero. Esto preserva la arquitectura de registro de tabs, pero evita que cada nueva pestana cobre
impuesto en cada request.

### Finding DEV-02 - Un comando que reescribe tablas estadisticas no tiene cobertura directa

Severidad: Media

Evidencia:

- `dglweb/stats/management/commands/backfill_batting_rates.py:24-28` define cuatro targets:
  batting, post, pitching y pitching_post.
- `dglweb/stats/management/commands/backfill_batting_rates.py:38-53` itera todos los rows y hace
  `bulk_update` dentro de una transaccion.
- La cobertura de `pytest` reporto `dglweb/stats/management/commands/backfill_batting_rates.py`
  con 0%.

Riesgo:

El comando es idempotente por diseno, pero tambien es una herramienta de escritura masiva. Un cambio
futuro en `derive({})`, en nombres de columnas o en el batching podria terminar escribiendo columnas
equivocadas, saltando el ultimo batch o recalculando pitching con formulas que no corresponden. El
resto del pipeline tiene buena disciplina de tests; este comando quedo como excepcion.

Sugerencia:

Agregar tests unitarios/pytest-django para:

- `--only` selecciona solo el modelo pedido.
- una fila recalcula las columnas derivadas esperadas y no toca las demas.
- dataset vacio devuelve 0 sin error.
- el ultimo batch menor que `_BATCH` se persiste.
- pitching solo recalcula coeficientes de batted-ball, no tasas de pitcheo mapeadas desde fuente.

La razon es simple: una herramienta de reparacion debe ser mas confiable que el bug que intenta
arreglar.

### Finding DEV-03 - Los templates de stats estan demasiado acoplados a listas de columnas

Severidad: Baja

Evidencia:

- `templates/profiles/tabs/batting.html:17`, `:64`, `:108`, `:150`, `:190`, `:220`, `:254`,
  `:286`, `:317`, `:343`, `:369` repiten estructuras de tablas con columnas hardcodeadas.
- `templates/profiles/tabs/pitching.html:20`, `:73`, `:124`, `:168`, `:209`, `:239`, `:273`,
  `:306`, `:338`, `:364`, `:390` repiten el mismo patron para pitcheo.

Riesgo:

Cada nueva metrica o cambio de formato obliga a editar varios bloques manualmente: temporadas,
totales, postemporada, Statcast y coeficientes. Eso aumenta el riesgo de inconsistencias sutiles,
por ejemplo una columna presente en temporadas pero no en totales, o un filtro de formato distinto
entre bateo y pitcheo.

Sugerencia:

Extraer una especificacion declarativa por tabla, por ejemplo `columns = [(label, attr, formatter,
css_key)]`, y renderizar con un partial comun. No hace falta crear una abstraccion enorme: basta con
mover las listas de columnas a Python o a un include de template para que el cambio de una metrica
tenga un solo punto de mantenimiento.

### Finding DEV-04 - Los filtros de formato son fragiles ante valores no numericos inesperados

Severidad: Baja

Evidencia:

- `dglweb/profiles/templatetags/stats_extras.py:11-16` hace `float(value)` para tasas.
- `dglweb/profiles/templatetags/stats_extras.py:23-26` hace `float(value)` para decimales.
- `dglweb/profiles/templatetags/stats_extras.py:52-55` hace `float(value)` para porcentajes.

Riesgo:

Los mappers ya convierten placeholders no parseables a `None`, y los tests cubren los casos
normales. Aun asi, si un valor textual llega desde una fila parcial, un fixture manual, un backfill
interrumpido o un futuro campo calculado, el template puede producir un 500 en vez de mostrar `-`.

Sugerencia:

Mantener fail-loud en ingest, pero hacer fail-soft en template filters: capturar `TypeError` y
`ValueError`, devolver `-`, y agregar un test con `"--"` o `"N/A"`. En UI publica conviene que la
pagina sobreviva a un valor corrupto y que la corrupcion se detecte en paridad/ingest, no en render.

## Persona 2 - Experto en beisbol y sabermetria

### Finding SAB-01 - La cobertura Statcast se decide por ano minimo, no por completitud real de datos

Severidad: Media

Evidencia:

- `dglweb/profiles/tabs.py:346-347` incluye filas Statcast si `row.season >= FIRST_STATCAST_SEASON`.
- `dglweb/profiles/tabs.py:371` considera `statcast_full` cuando todas las temporadas del jugador
  estan despues del piso de 1989.
- `templates/profiles/tabs/batting.html:128`, `:168`, `:316` y
  `templates/profiles/tabs/pitching.html:146`, `:187`, `:337` muestran totales Statcast si
  `d.statcast_full`.
- `docs/MEJORAS_FUTURAS.md:62-69` documenta el hueco de 2000-2001: la fuente tiene outs por tipo,
  pero casi no tiene hits por tipo, por lo que los cuatro tipos suman alrededor de 67% en vez de
  100%.

Riesgo sabermetrico:

El corte de 1989 evita eras sin clasificacion, pero no captura huecos internos. Un jugador cuya
carrera moderna incluye 2000-2001 puede mostrar panels y totales que parecen completos, aunque sus
GB%/FB%/LD%/PU% de esos anos estan subestimados por construccion. Esto puede afectar lectura de
perfil de batazo y, si esos coeficientes alimentan lideres, puede castigar o beneficiar perfiles
con carreras concentradas en esos anos.

Sugerencia:

Si la decision sigue siendo dejar 2000-2001 como esta, documentarla tambien en la UI cerca de los
panels Statcast y en cualquier leader board de coeficientes, no solo en backlog. Mejor aun, modelar
cobertura por temporada/metrica (`coverage_status`, `is_partial`, o una tabla de exclusiones) y usar
eso para decidir `has_statcast`, `statcast_full` y elegibilidad de lideres. La regla por piso es
demasiado gruesa para una fuente historica irregular.

### Finding SAB-02 - Algunos boards de batted-ball profile mezclan ranking con descripcion de estilo

Severidad: Media

Evidencia:

- `dglweb/stats/management/commands/seed_metrics.py:89-96` define direcciones para coeficientes de
  bateo y reconoce que GB%, FB%, LD% y GB/FB son descriptivos mas que "bueno/malo".
- `dglweb/stats/management/commands/seed_metrics.py:128-134` hace una aclaracion similar para
  pitcheo: GB%, FB%, LD% y GB/FB se mantienen descriptivos, mientras PU%, Contact% y Whiff% si
  tienen lectura de valor mas clara.
- El mismo catalogo activa best/worst season y career para esos coeficientes descriptivos.

Riesgo sabermetrico:

Un "lider de GB%" o "lider de FB%" puede ser valido como "mayor porcentaje", pero llamarlo "best"
o "worst" sugiere valor competitivo. En bateo, un GB% alto no es universalmente mejor; depende de
velocidad, poder, parque, contexto ofensivo y era. En pitcheo, GB% alto suele ser deseable, pero no
es absoluto sin K%, BB%, HR/FB, defensa y parque. LD% bajo o alto tambien cambia por medicion y
sample.

Sugerencia:

Separar semanticamente estos boards en "Mas alto / Mas bajo" o "Perfil" para metricas descriptivas,
y reservar "Mejor / Peor" para metricas con direccion deportiva clara. Otra opcion es mantener las
filas pero cambiar copy/labels en la UI y en `Metric.Direction` solo para ordenamiento tecnico. Eso
evita una falsa assumption de sabermetria sin perder el valor exploratorio del dato.

### Finding SAB-03 - Los mejores personales resaltan extremos descriptivos como si fueran logros

Severidad: Baja

Evidencia:

- `dglweb/profiles/tabs.py:91-134` calcula mejores personales para todo campo numerico presente en
  el catalogo.
- `dglweb/profiles/tabs.py:237-251` pinta esos extremos en la fila total de temporada.
- Los coeficientes descriptivos de batted-ball entran al catalogo como metricas activas en
  `dglweb/stats/management/commands/seed_metrics.py:89-96` y `:128-134`.

Riesgo sabermetrico:

Para HR, WAR, OBP, ERA o WHIP, un "personal best" es natural. Para GB%, FB%, LD% o GB/FB, el extremo
no necesariamente es mejor; puede ser solo un cambio de perfil. Resaltarlo con la misma jerarquia
visual que un logro puede inducir una lectura falsa del jugador.

Sugerencia:

Agregar una categoria de metrica, por ejemplo `achievement` vs `profile`, o un flag tipo
`highlight_personal_best`. Mantener highlights para valor competitivo claro y cambiar los
descriptivos a "max/min de perfil" o dejarlos sin highlight. Esto mejora la interpretacion sin
tocar las formulas.

## Revisado y no levantado como bug

- La exclusion de Ligas Negras en lideres esta documentada como decision consciente en
  `dglweb/stats/leaders.py:11-16` y `:18-23`; las paginas de jugador si conservan esas lineas.
- La notacion de innings ya usa `outs` y el filtro `innings`, no suma strings de IP.
- WAR/RAR/UZR estan tratados como acumulativos, no como tasas prorrateadas.
- `ruff`, `mypy` y la suite completa estan verdes en la revision actual.
