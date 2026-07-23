# Code Review v2 - dglweb

Fecha: 2026-07-23  
Proyecto: `C:\Users\aperd\Documents\DGLv2\apps\dglweb`

## Alcance

Antes de revisar codigo se leyeron los Markdown bajo `docs/`:

- `docs/BUILD_PLAN.md`
- `docs/CODING_STANDARDS.md`
- `docs/CONCEPT.md`
- `docs/FASE4_PLAN.md`
- `docs/TODO.md`
- `docs/library-guidelines.md`
- `docs/reviews/code_review_v1.md` existente
- `docs/reviews/code_review_v1_fixes.md`

No se modifico codigo fuente. Este archivo es el unico entregable tocado por el review.

Checks ejecutados:

- `docker compose run --rm --no-deps web ruff check .` - OK
- `docker compose run --rm --no-deps web mypy .` - OK, 106 source files
- `docker compose run --rm web pytest` - OK, 323 passed, cobertura total 97%

Nota: la suite muestra warnings de Django por `staticfiles/` ausente en dev; no falla y ya encaja
con la deuda documentada de imagen prod/`collectstatic`.

## Resumen ejecutivo

El proyecto esta en muy buena forma para una Fase 4: los fixes del review anterior estan
implementados, hay querysets canonicos para no doble-contar jugadores cambiados, `innings_outs`
para evitar sumar entradas beisboleras, logs acotados, comandos de paridad cubiertos y un motor de
lideres probado con rankings, empates, umbrales y tasas de carrera.

Los riesgos actuales ya no son de estilo basico de Python. Estan en dos zonas: configuracion
operativa que deberia fallar mas temprano, y semantica sabermetrica de los lideres. En especial,
hay una decision de producto sobre excluir Ligas Negras de los lideratos que deberia quedar mas
visible en la documentacion, y hay metricas cuyo tipo no se puede inferir solo por `IntegerField`
vs `FloatField`.

---

# Persona 1: Python Principal Developer

## Finding DEV-01 - El parser de umbrales falla abierto y no soporta `AND`

Severidad: Alta  
Evidencia: `dglweb/stats/qualifier.py:26`, `dglweb/stats/qualifier.py:58-61`,
`docs/FASE4_PLAN.md:39`

`qualifies()` acepta solo una expresion `FIELD OP NUMBER`. Si el admin escribe una formula compuesta
como `PA>=502 AND G>=100` -caso prometido en el plan- o comete un typo, el regex no matchea y el
codigo devuelve `True` para todo el mundo.

Razonamiento: el peor modo de fallo de un leaderboard es publicar rankings sin calificacion por un
error de texto en backoffice. Es fail-open en una regla de negocio critica.

Sugerencia: soportar `AND` de forma explicita o rechazar formulas no parseables con `ValidationError`
en el modelo/formulario y con excepcion loud en el builder. Una formula vacia puede significar "sin
umbral"; una formula invalida no deberia significar "todos califican".

## Finding DEV-02 - `config.settings.prod` no exige `MLB_PROXY_URL` ni `MLB_PROXY_API_KEY`

Severidad: Media  
Evidencia: `config/settings/base.py:114-115`, `config/settings/prod.py`, `docker-compose.yml:34-35`

`SECRET_KEY` y `DATABASE_URL` fallan loud, pero el proxy usa defaults (`localhost:3002` y API key
vacia). En produccion el sitio podria arrancar sano y fallar recien cuando corran scrapers o modulos
live.

Razonamiento: los documentos piden configuracion por entorno y fallo ruidoso. El proxy es una pieza
central del pipeline; descubrir una key vacia en la bitacora de madrugada es demasiado tarde.

Sugerencia: en `prod.py`, leer `MLB_PROXY_URL = env("MLB_PROXY_URL")` y
`MLB_PROXY_API_KEY = env("MLB_PROXY_API_KEY")` sin defaults, o agregar un Django system check que
falle en prod si estan vacios.

## Finding DEV-03 - `Metric.postseason` existe pero `build_leaders` no lo usa

Severidad: Media  
Evidencia: `dglweb/stats/models.py:740`, `dglweb/stats/management/commands/seed_metrics.py:332`,
`dglweb/stats/leaders.py:30`, `dglweb/stats/leaders.py:63-72`

El catalogo guarda si una metrica aplica a postemporada, y ya existen modelos `BattingPost`,
`PitchingPost` y `FieldingPost`, pero el motor de lideres solo lee `Batting`, `Pitching` y
`Fielding` de temporada regular.

Razonamiento: es una configuracion visible en backoffice que no tiene efecto. Eso crea una falsa
sensacion de cobertura y puede llevar a que el owner active/edite flags esperando lideres de
postemporada que nunca se calculan.

Sugerencia: decidir una de dos: implementar boards separados de postemporada, o esconder/remover el
flag hasta que exista esa dimension. Si se implementa, separar claramente regular vs post en
`Leader` para no mezclar contextos.

## Finding DEV-04 - `build_leaders` no tiene proteccion contra ejecuciones concurrentes

Severidad: Media  
Evidencia: `dglweb/stats/leaders.py:205`, `dglweb/stats/leaders.py:232-236`,
`dglweb/stats/models.py:819-851`

El rebuild borra todo `dgl_leader` y luego hace `bulk_create`, pero `Leader` solo tiene indice de
lectura, no constraint de unicidad por `(metric, board, season, fielding_pos, player)`.

Razonamiento: el scheduler corre una vez al dia, pero un comando manual simultaneo o un retry mal
coordinado podria insertar duplicados. Como el read side ordena por rank, duplicar filas seria muy
visible.

Sugerencia: agregar un lock de aplicacion/advisory lock al comando y una constraint unica adecuada.
En Postgres hay que tratar `NULL` en `season`/`fielding_pos` con cuidado (`nulls_distinct=False` o
columnas normalizadas), porque los boards de carrera usan `season=NULL`.

## Finding DEV-05 - El motor de lideres reescanea las tablas por metrica

Severidad: Baja/Media  
Evidencia: `dglweb/stats/leaders.py:63-77`, `dglweb/stats/leaders.py:205-231`

Por cada metrica activa, y por cada posicion de fildeo, `_totals()` vuelve a consultar las tablas de
stats. Hoy el volumen es manejable, pero el catalogo ya supera 100 metricas y la Fase 4 agregara
historico completo.

Razonamiento: no es un bug actual; es un punto de escalamiento. El rebuild completo diario puede
seguir siendo simple, pero conviene evitar O(metricas x posiciones x scans historicos) cuando una
extraccion por grupo podria alimentar varias metricas.

Sugerencia: agrupar por `stat_group` y traer una matriz de columnas necesarias una sola vez por
grupo/posicion, o materializar una tabla intermedia de season totals. Mantener el rebuild completo,
pero reducir scans repetidos.

---

# Persona 2: Experto en beisbol y sabermetria

## Finding SAB-01 - La exclusion de Ligas Negras en lideres necesita mejor documentacion

Severidad: Media  
Evidencia: `dglweb/stats/leaders.py:5`, `dglweb/stats/leaders.py:30`,
`dglweb/stats/leaders.py:63-66`, `docs/FASE4_PLAN.md:15`, `docs/FASE4_PLAN.md:60`

El codigo define `FIRST_SEASON = 1956` y filtra los leaderboards con `season__gte=FIRST_SEASON`,
lo cual deja fuera las Ligas Negras de los lideres. Si esta es una decision consciente de producto,
el problema no es el filtro: es que la decision no queda suficientemente explicita en la
documentacion de Fase 4, donde tambien se habla de incluir esos jugadores en paginas/stats con nota
de cobertura.

Razonamiento: sin esa aclaracion, un futuro maintainer puede interpretar `FIRST_SEASON = 1956` como
un bug o intentar "arreglarlo" metiendo Ligas Negras en los rankings. Tambien el lector/admin
necesita entender la diferencia entre "incluidos en paginas historicas" y "excluidos de lideres
comparativos".

Sugerencia: documentar la regla en `FASE4_PLAN.md` y en el docstring/comentario de `FIRST_SEASON`:
las Ligas Negras se muestran con contexto en paginas de jugador, pero no participan en lideres por
cobertura incompleta y comparabilidad historica. Si la UI de lideres menciona cobertura, agregar una
nota breve tipo "Lideres desde 1956; Ligas Negras excluidas de rankings por cobertura parcial".

## Finding SAB-02 - Los lideres de innings pueden publicar outs crudos o quedar inactivos

Severidad: Alta  
Evidencia: `dglweb/stats/management/commands/seed_metrics.py:80`,
`dglweb/stats/management/commands/seed_metrics.py:107`,
`dglweb/stats/management/commands/seed_metrics.py:138`,
`dglweb/stats/management/commands/seed_metrics.py:142`,
`dglweb/stats/management/commands/seed_metrics.py:319`,
`dglweb/stats/leaders.py:86`, `dglweb/stats/leaders.py:124`

El proyecto correctamente evita rankear `ip`/`innings` beisboleros y usa `outs` /
`innings_outs`. Pero `Leader.value` guarda `row[metric.column]` o la suma de esa columna. Para
pitcheo, eso significa que el lider de "IP" puede quedar con valor `outs` (486) en vez de 162.0 IP.
En fildeo, `innings_outs` se aliasa a `InnOuts`, pero la configuracion heredada lo deja inactivo,
mientras `Inn` era el activo historico.

Razonamiento: guardar outs como canonical value esta bien para calculo, pero publicarlo como innings
seria beisboleramente incorrecto. Y dejar inactivo el leaderboard de innings defensivas pierde una
metrica esperada.

Sugerencia: separar `value_raw` de `value_display`, o convertir `outs` a innings al crear/mostrar
lideres de IP/Inn. En `seed_metrics`, setear `abbrev`/`name_es` con el codigo alias (`IP`, `Inn`)
y trasladar la configuracion activa de `Inn` a `innings_outs`.

## Finding SAB-03 - El tipo de una metrica no se puede inferir solo por `FloatField`

Severidad: Alta  
Evidencia: `dglweb/stats/management/commands/seed_metrics.py:287-292`,
`dglweb/stats/models.py:143-160`, `dglweb/stats/models.py:325-353`,
`dglweb/stats/career_rate.py:99-106`

`seed_metrics` clasifica todo `FloatField` como tasa (`PRO`). Eso funciona para AVG/ERA/FIP, pero
no para valores sabermetricos aditivos expresados como floats: WAR, RAR, wRAA, wRC, UBR, wGDP, wSB,
RA9-WAR, UZR, etc.

Razonamiento: muchas sabermetricas de "runs" o "wins" son decimales pero acumulativas. En carrera
deben sumarse, no promediarse ni pasar por el fallback de tasa ponderada. Si el owner activa WAR o
UZR como lider de carrera, el motor puede rankear una aproximacion equivocada.

Sugerencia: agregar una tabla/constante curada de `kind` por columna. Regla practica: porcentajes,
promedios y por-9 son `RATE`; WAR/RAR/wRAA/wRC/UZR/run values son `CUMULATIVE` aunque sean floats.
Agregar tests para career WAR y career UZR.

## Finding SAB-04 - Las temporadas cortas no estan modeladas por juegos reales del equipo

Severidad: Media  
Evidencia: `dglweb/stats/management/commands/seed_qualifier_overrides.py:25-32`,
`dglweb/stats/management/commands/seed_qualifier_overrides.py:44`,
`tests/test_metrics.py:150`, `docs/BUILD_PLAN.md:223`

Los overrides usan una lista corta fija: 1956-1959, 1981, 1994 y 2020. Falta 1960 para el calendario
de 154 juegos, 1961 fue mixto por liga, y 1981/1994 se declaran aproximados aunque los equipos no
jugaron todos la misma cantidad.

Razonamiento: el propio plan dice que el umbral de temporada debe calcularse contra los juegos del
equipo, no contra una constante. Para leaderboards historicos, un umbral incorrecto puede excluir o
incluir temporadas al borde.

Sugerencia: introducir una fuente `team_games(season, team)` o una tabla de calendario por equipo.
Para un primer paso, completar 1960 y documentar 1961; para el paso correcto, calcular PA/IP/G
calificados por equipo y temporada.

## Finding SAB-05 - BAA de temporada y BAA de carrera usan definiciones distintas

Severidad: Media  
Evidencia: `dglweb/stats/pitching_mapping.py:201-221`, `dglweb/stats/career_rate.py:84`

La BAA de temporada se deriva con la formula legacy `H / (BF - BB - HBP - SH - SF - CI)`. La BAA
de carrera en `career_rate.py` usa `H / AB`.

Razonamiento: ambas formulas pueden ser defendibles segun fuente, pero no deben mezclarse en la
misma metrica sin decirlo. Un jugador podria tener temporada y carrera calculadas con reglas
distintas, y eso es dificil de explicar al lector.

Sugerencia: elegir una definicion canonica para BAA publica. Si se mantiene la legacy por paridad,
la carrera debe recomputarse con la misma reconstruccion desde BF; si se cambia a `H/AB`, actualizar
la documentacion y los tests de paridad para aclarar la divergencia.

## Finding SAB-06 - Empates de tasas se comparan con floats exactos

Severidad: Baja  
Evidencia: `dglweb/stats/leaders.py:43-52`

`_dense_rank()` considera empate solo si `value != previous` es falso exactamente. Para tasas
derivadas, dos valores que se muestran iguales a tres decimales pueden no empatar por diferencias
minimas de float.

Razonamiento: en beisbol, el ranking publicado normalmente empata segun la precision mostrada o
segun una regla oficial clara. Un leaderboard que muestra `.300` y `.300` como rangos distintos se
ve mal aunque internamente haya una diferencia de `1e-15`.

Sugerencia: rankear con una clave normalizada por formato de la metrica (`fmt`) o con `Decimal` /
redondeo explicito por tipo de stat. La regla debe coincidir con lo que se renderiza.

---

# Observaciones positivas

- La suite actual es fuerte: 323 tests, 97% cobertura, `ruff` y `mypy strict` verdes.
- Los fixes previos importantes estan implementados: upsert seguro de `dgl_master`, logs acotados,
paridad de comandos y proteccion contra doble conteo por `XXX`.
- La decision `NULL` sobre `0` para datos ausentes sigue siendo correcta y esta bien documentada.
- La separacion cliente proxy -> fuentes -> mapping -> loader -> lideres es clara y mantenible.
- El motor de lideres ya evita varios errores sabermetricos clasicos: recomputa AVG/ERA de carrera
desde componentes, no promedia AVG de temporadas, y usa `outs`/`innings_outs` para calculo.

# Prioridad sugerida

1. Corregir el parser de umbrales para que no falle abierto.
2. Documentar la decision de excluir Ligas Negras de los lideres antes de publicarlos.
3. Curar `Metric.kind` para sabermetricas acumulativas y arreglar la presentacion de IP/Inn.
4. Exigir configuracion del proxy en prod y proteger concurrencia de `build_leaders`.
5. Reemplazar overrides aproximados por juegos reales de equipo cuando el calendario historico este disponible.
