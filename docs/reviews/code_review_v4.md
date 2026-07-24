# Code Review v4 - dglweb

Fecha: 2026-07-24  
Proyecto: `C:\Users\aperd\Documents\DGLv2\apps\dglweb`

## Alcance

Antes de revisar codigo se leyeron los Markdown bajo `docs/`, incluyendo:

- `docs/BUILD_PLAN.md`
- `docs/CODING_STANDARDS.md`
- `docs/CONCEPT.md`
- `docs/FASE4_PLAN.md`
- `docs/MEJORAS_FUTURAS.md`
- `docs/TODO.md`
- `docs/UMBRALES_POSTEMPORADA.md`
- `docs/library-guidelines.md`
- reviews previos bajo `docs/reviews/`

No se modifico codigo fuente. El unico archivo creado por este review es este entregable.

Verificacion ejecutada:

- `docker-compose run --rm --no-deps web ruff check .` - OK
- `docker-compose run --rm --no-deps web mypy .` - FALLA: 5 errores en `tests/test_profiles.py`
- `docker-compose run --rm web pytest` - OK: 402 passed, cobertura total 96%

Nota operativa: el comando documentado con `docker compose ...` no corrio en este entorno; el CLI
disponible funciono con `docker-compose ...`.

## Resumen ejecutivo

El proyecto sigue en buen estado funcional: la suite completa pasa, hay cobertura alta, los fixes
de reviews anteriores se ven integrados, y el motor de lideres/postemporada ya esta bastante mejor
protegido que en Fase 4 temprana. Los riesgos principales de v4 no son de arquitectura gruesa, sino
de bordes: CI tipado roto, inconsistencias de configuracion de postemporada, badges que pueden no
aparecer en temporadas de octubre de una sola ronda, y algunas lecturas sabermetricas que la UI
puede expresar con mas precision.

---

# Persona 1: Python Principal Developer

## Finding DEV-01 - `mypy .` ya no esta verde

Severidad: Alta  
Evidencia: `pyproject.toml:43-47`, `README.md:20-30`, `tests/test_profiles.py:587-589`,
`tests/test_profiles.py:612-618`, `tests/test_profiles.py:640-643`

El estandar del proyecto declara `mypy strict`, el README expone `make typecheck`, y los reviews
anteriores registraban mypy verde. En esta revision, `mypy .` falla con 5 errores en
`tests/test_profiles.py`: `_flat()` recibe/retorna estructuras tipadas como `dict[str, object]`, y
luego se itera/indexa `object` como si fuera una lista/dict.

Riesgo: CI puede bloquear merges aunque runtime y pytest pasen. Ademas, cuando los tests pierden
tipado, dejan de servir como especificacion clara de la forma del contexto de `_puestos_context()`.

Sugerencia: definir `TypedDict` para las filas/secciones/celdas de Puestos, o usar `cast()` puntual
en el helper de test. Mejor aun, exportar una estructura tipada desde `profiles.tabs` para que tests
y vista hablen el mismo contrato.

## Finding DEV-02 - Los liderazgos de postemporada de una sola ronda no se pintan como lider de temporada

Severidad: Media  
Evidencia: `dglweb/profiles/tabs.py:218-260`, `dglweb/profiles/tabs.py:412-424`,
`dglweb/stats/leaders.py:374-376`

`_postseason()` solo agrega una fila subtotal `kind="season"` cuando el jugador tuvo mas de una
ronda en ese octubre. El overlay de lider de temporada de postemporada solo se aplica a
`entry["kind"] == "season"`. Pero `build_leaders` siempre crea un `BEST_SEASON` de postemporada por
(jugador, temporada), aunque el jugador haya jugado una sola ronda.

Riesgo: un jugador que lidero entre dominicanos en una postemporada corta puede tener el dato en
`dgl_leader`, pero la pagina del jugador no lo muestra con badge de lider de temporada. Es una
inconsistencia visible entre el motor y la UI.

Sugerencia: cuando un octubre tenga una sola ronda, tratar esa linea como el agregado de temporada
para efectos de highlights, o crear siempre un subtotal `Tot` y dejar que el template decida si lo
renderiza. Agregar un test con un jugador que tiene un `BEST_SEASON` postseason y una sola ronda.

## Finding DEV-03 - Los boards de postemporada ignoran `best_season` / `best_career`

Severidad: Media  
Evidencia: `dglweb/stats/models.py:774-784`, `dglweb/stats/leaders.py:270-283`,
`dglweb/stats/leaders.py:313-337`, `dglweb/stats/leaders.py:340-377`,
`dglweb/stats/leaders.py:430-433`

Para temporada regular, `build_leaders` respeta los flags `best_season`, `worst_season`,
`best_career` y `worst_career`. En postemporada, basta con `metric.postseason=True` para generar
siempre `BEST_SEASON` y `BEST_CAREER` en conteos y tasas permitidas. Eso hace que el backoffice tenga
controles que parecen universales, pero no gobiernan los boards de octubre.

Riesgo: si el admin apaga `best_career` o `best_season` para una metrica, la temporada regular
obedece y la postemporada no. Es un bug de configuracion y mantenibilidad.

Sugerencia: aplicar los mismos flags a postemporada (`if metric.best_season`, `if metric.best_career`)
o separar explicitamente flags de regular y post. Tambien actualizar el comentario de
`Metric.postseason`, que todavia lo llama "reservado" aunque el motor ya lo usa.

## Finding DEV-04 - `_innings_to_outs()` acepta fracciones imposibles de entradas

Severidad: Media  
Evidencia: `dglweb/stats/fielding_mapping.py:52-63`, `tests/test_fielding.py:206-212`,
`dglweb/stats/fielding_post_source.py:61`

El parser de innings de fildeo convierte solo el primer digito despues del punto en outs. Eso acepta
valores imposibles en notacion beisbolera como `111.3`, `111.9` o `111.25` en vez de rechazarlos o
marcarlos como dato corrupto. La misma funcion alimenta temporada regular y postemporada.

Riesgo: si el proxy o un fixture trae un valor mal formado, se persiste un `innings_outs` plausible
pero falso, que luego alimenta totales, RF/9 y leaderboards.

Sugerencia: validar que la fraccion sea vacia, `0`, `1` o `2` (y que no haya digitos extra no
esperados). Para ingest, conviene fallar loud o retornar `None` con un caso de paridad claro; en
cualquier caso, agregar tests para `.3`, `.9` y strings con basura.

## Finding DEV-05 - La pagina de jugador sigue calculando todos los tabs por request

Severidad: Baja/Media  
Evidencia: `dglweb/profiles/views.py:80-89`, `dglweb/profiles/tabs.py:382-407`,
`dglweb/profiles/tabs.py:562-681`, `dglweb/profiles/tabs.py:777-857`

`player_detail()` construye el contexto completo de cada tab aplicable antes de renderizar. Hoy la
suite mantiene un presupuesto de queries y el costo parece controlado, pero el patron sigue
escalando con cada tab nuevo: bateo, pitcheo, fildeo, postemporada, totales y Puestos se calculan
aunque el usuario solo vea el primer tab.

Riesgo: a medida que entren lideres UI, splits o game logs, el primer render pagara por datos que
quizas nunca se abran. Para un sitio publico, eso afecta latencia y cacheabilidad.

Sugerencia: mantener el shell SSR, pero cargar tabs secundarios con endpoints parciales HTMX o
lazy-load server-side. Si se pospone, dejar el test de query budget como guardarrail y medir con
jugadores "caros" como Pedro Martinez / David Ortiz.

---

# Persona 2: Experto en beisbol y sabermetria

## Finding SAB-01 - "Puestos" llama "mejor" a metricas descriptivas

Severidad: Media  
Evidencia: `dglweb/stats/management/commands/seed_metrics.py:89-98`,
`dglweb/stats/management/commands/seed_metrics.py:117-142`,
`templates/profiles/tabs/puestos.html:21-33`

El seed documenta correctamente que GB%, FB%, LD% y GB/FB describen perfil, no logro. Sin embargo,
el tab de Puestos muestra el signo `+` con tooltip/caption de "mas es mejor" y `-` como "menos es
mejor". Si un jugador aparece top-10 en GB% o FB%, la UI convierte "mas alto" en "mejor".

Riesgo sabermetrico: un GB% alto puede ser bueno o malo segun velocidad, poder, parque, era y rol;
un FB% alto tampoco es universalmente mejor. La tabla puede ensenar una falsa conclusion aunque el
ordenamiento tecnico sea correcto.

Sugerencia: agregar una categoria `profile`/`descriptive` en `Metric` o una lista curada en la UI.
Para esas metricas, mostrar "mas alto / mas bajo" o "perfil" en vez de "mas es mejor / menos es
mejor". Reservar "mejor" para metricas con direccion deportiva clara.

## Finding SAB-02 - El panel de receptor muestra volumen defensivo sin tasa de control del running game

Severidad: Media  
Evidencia: `dglweb/stats/models.py:435-442`, `dglweb/stats/models.py:1214-1224`,
`dglweb/profiles/columns.py:211-218`, `templates/profiles/tabs/fielding.html:61`

El tab de receptor presenta SB, CS, PB, WP, PkO y cERA. SB/CS crudos son utiles, pero sin intentos
ni porcentaje de atrapados (`CS / (SB + CS)`) mezclan talento, volumen, pitchers, scorekeeping y
cantidad de innings. cERA tambien es muy dependiente del staff y del contexto.

Riesgo sabermetrico: un catcher con muchas entradas puede verse "peor" por permitir mas robos en
volumen, o "mejor" por acumular mas CS, sin normalizar oportunidades. cERA puede sugerir una
responsabilidad causal mayor de la que tiene.

Sugerencia: derivar y mostrar al menos `CS%` cuando existan `stolen_bases + caught_stealing > 0`,
y considerar SB/9 o intentos por 9 para contexto de volumen. Etiquetar cERA como descriptiva, no
como evaluacion defensiva fuerte.

## Finding SAB-03 - La cobertura Statcast sigue siendo un piso por ano, no una cobertura real por metrica

Severidad: Media  
Evidencia: `dglweb/profiles/tabs.py:400-406`, `dglweb/profiles/tabs.py:470-472`,
`templates/profiles/tabs/batting.html:62`, `templates/profiles/tabs/pitching.html:143`,
`docs/MEJORAS_FUTURAS.md:62-69`

El perfil decide si muestra panes Statcast con `season >= FIRST_STATCAST_SEASON` y decide si hay
total con `len(statcast_seasons) == len(seasons)`. Eso cubre eras viejas, pero no huecos internos
documentados como 2000-2001, donde los tipos de batazo estan incompletos.

Riesgo sabermetrico: GB%, FB%, LD%, PU% y derivados pueden parecer comparables entre temporadas
modernas aunque algunas temporadas tengan cobertura parcial. Esto afecta lectura del perfil y
leaderboards de coeficientes.

Sugerencia: modelar cobertura por temporada/metrica (`complete`, `partial`, `missing`) o una tabla
de exclusiones. Mientras tanto, la nota de UI deberia mencionar explicitamente los anos parciales
si un jugador tiene filas 2000-2001 en esos panes.

## Finding SAB-04 - Postemporada de fildeo aparece en perfiles, pero sin liderazgos ni la misma explicacion contextual

Severidad: Baja/Media  
Evidencia: `dglweb/stats/leaders.py:267-283`, `dglweb/profiles/tabs.py:642-681`,
`templates/profiles/tabs/fielding.html:67-81`, `templates/profiles/tabs/fielding.html:116-125`

El motor excluye fildeo de leaderboards de postemporada, pero el perfil ya muestra postemporada de
fildeo y sus totales por posicion. Esto puede ser correcto como decision de producto, pero la pagina
no explica que esos datos no participan en badges/liderazgos de octubre, a diferencia de bateo y
pitcheo.

Riesgo sabermetrico: el lector puede inferir que la ausencia de badges significa que el jugador no
lidero, cuando en realidad esa dimension no se calcula. En fildeo, ademas, las muestras de octubre
por posicion son muy pequenas.

Sugerencia: agregar una nota breve en el tab de fildeo de postemporada: "Fildeo de postemporada se
muestra como registro descriptivo; no se rankea en liderazgos por ahora". Si se decide rankearlo
despues, usar umbrales por posicion/innings y evitar mezclar posiciones.

---

# Observaciones positivas

- `ruff` y `pytest` estan fuertes: 402 tests pasan y la cobertura se mantiene en 96%.
- Los querysets canonicos (`season_totals()` / `position_totals()`) reducen bien el riesgo de doble
  conteo en jugadores cambiados.
- La decision de usar `outs` / `innings_outs` como canonico esta reflejada en modelos, columnas y
  tests.
- Postemporada de tasas recompone desde componentes y usa pisos propios documentados; eso evita el
  error clasico de promediar tasas por ronda.
- El tab de fildeo trata posicion como entidad propia, lo cual es correcto para liderazgos y totales.

# Prioridad sugerida

1. Arreglar `mypy .` para recuperar el gate de CI.
2. Corregir los highlights de postemporada de una sola ronda.
3. Hacer que postemporada respete `best_season` / `best_career`, o separar flags.
4. Cambiar copy de Puestos para metricas descriptivas.
5. Validar fracciones de innings y derivar contexto de receptor (`CS%`, volumen).
