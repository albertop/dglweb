# Code Review v1 - dglweb

Fecha: 2026-07-22  
Proyecto: `C:\Users\aperd\Documents\DGLv2\apps\dglweb`

## Alcance

Antes de revisar codigo se leyeron los documentos Markdown bajo `docs/`:

- `docs/BUILD_PLAN.md`
- `docs/CODING_STANDARDS.md`
- `docs/CONCEPT.md`
- `docs/library-guidelines.md`
- `docs/TODO.md`

El review se hizo sin modificar codigo fuente. El unico archivo creado es este entregable.

Checks ejecutados:

- `docker compose run --rm --no-deps web ruff check .` - OK
- `docker compose run --rm --no-deps web mypy .` - OK, 74 source files
- `docker compose run --rm web pytest` - OK, 196 passed, cobertura total 92%

## Resumen ejecutivo

El proyecto esta mejor encaminado que un prototipo normal: hay una arquitectura Django/Wagtail coherente con los documentos, reglas de datos explicitas, loaders idempotentes, paridad contra fuentes historicas, `mypy strict`, `ruff` y una suite de tests amplia. El trabajo de port de batting/pitching/fielding tiene buena disciplina: funciones puras para mapeo, separacion de descarga/persistencia, `NULL` sobre `0` en tasas indefinidas y bitacora de ingesta.

Los riesgos principales no estan en estilo basico de Python, sino en la siguiente fase: agregados de lideres, paginas de jugador y operacion productiva. En particular, hay que blindar el doble conteo de temporadas con cambio de equipo y evitar que entradas en notacion beisbolera (`46.2` = 46 2/3) se sumen como floats decimales.

---

# Persona 1: Python Principal Developer

## Finding DEV-01 - `import_dgl_master --replace` puede borrar stats por cascada

Severidad: Alta  
Evidencia: `dglweb/players/management/commands/import_dgl_master.py:86-91`, `dglweb/stats/models.py:36-42`, `dglweb/stats/models.py:212`, `dglweb/stats/models.py:358`

El comando de importacion de la tabla maestra hace `Player.objects.all().delete()` cuando recibe `--replace`. Como `Batting`, `Pitching` y `Fielding` tienen FK a `Player` con `on_delete=models.CASCADE`, una recarga posterior de `dgl_master` puede borrar tambien las temporadas historicas ya cargadas.

Razonamiento: en Fase 2 esto era razonable porque la tabla maestra se cargo antes del backfill. Pero en Fase 4+ la tabla maestra sera una autoridad viva; corregir un nombre o un ID usando `--replace` podria destruir el activo de datos que alimenta lideres y paginas de jugador.

Sugerencia: convertir `--replace` en un upsert transaccional sobre `player_id`, con opcion explicita para borrar jugadores ausentes solo si se confirma una bandera peligrosa tipo `--delete-missing`. Como minimo, antes de borrar, detectar filas relacionadas en `mlb_batting`, `mlb_pitching` y `mlb_fielding` y abortar con un mensaje claro.

## Finding DEV-02 - La validacion del extracto maestro solo revisa la primera fila

Severidad: Media  
Evidencia: `dglweb/players/management/commands/import_dgl_master.py:77-80`

El comando valida `unexpected` y `missing` usando solo `records[0]`. Si una fila posterior trae columnas extra, columnas faltantes o una forma distinta, el error aparecera mas tarde como `TypeError`, `IntegrityError` o carga parcial abortada por transaccion, pero sin un diagnostico de fila/columna.

Razonamiento: es bueno que el loader falle loud, pero para un extracto externo de SQL Server conviene fallar loud y preciso. El costo de validar todas las filas es bajo para ~984 jugadores.

Sugerencia: recorrer todas las filas antes de abrir la transaccion y reportar indice/fila con columnas faltantes o inesperadas. Tambien conviene validar duplicados de `player_id` y de IDs unicos antes de `bulk_create` para producir errores de dominio, no errores crudos de DB.

## Finding DEV-03 - `record_run` guarda tracebacks completos en la base

Severidad: Media  
Evidencia: `dglweb/stats/runlog.py:58-60`

Ante cualquier excepcion, `record_run` guarda `str(exc)` mas `traceback.format_exc()` completo en `IngestRun.detail`. Eso ayuda en dev, pero en produccion puede filtrar paths internos, parametros de requests, detalles de infraestructura o mensajes de librerias que no quieres exponer en el backoffice. Tambien puede crecer sin limite si un fallo genera tracebacks largos cada noche.

Razonamiento: la bitacora es una pieza correcta para resiliencia, pero debe ser operativamente segura. El admin necesita diagnostico accionable, no necesariamente todo el traceback persistido para siempre.

Sugerencia: persistir un resumen sanitizado y acotado en `detail`, registrar el traceback completo via logging de servidor, y agregar truncamiento/limite. Si se quiere conservar tracebacks en DB durante desarrollo, hacerlo dependiente de `DEBUG` o de una variable explicita.

## Finding DEV-04 - Los comandos `parity_pitching` y `parity_fielding` no tienen cobertura directa

Severidad: Media  
Evidencia: resultado de cobertura de `pytest`: `dglweb/stats/management/commands/parity_pitching.py` 0%, `dglweb/stats/management/commands/parity_fielding.py` 0%; archivos en `dglweb/stats/management/commands/parity_pitching.py:30-60` y `dglweb/stats/management/commands/parity_fielding.py:29-61`

El core de paridad esta bien probado y `parity_batting` tiene pruebas de comando, pero los comandos de pitching y fielding no se ejercitan directamente. Son checks criticos porque validan el port contra el origen.

Razonamiento: estos comandos son "safety rails" del pipeline. Un rename, un extracto vacio, un JSON con forma rara o una rama de error podria romperse sin que CI lo note.

Sugerencia: factorizar el patron comun de comando de paridad o agregar tests analogos a `tests/test_parity_command.py` para pitching y fielding: OK, mismatch, archivo faltante, master vacia y detalles de filas sobrantes/faltantes.

## Finding DEV-05 - Ofelia con Docker socket no debe pasar a produccion sin hardening

Severidad: Media  
Evidencia: `docker-compose.yml:65-73`

El scheduler monta `/var/run/docker.sock` en modo read-only para que Ofelia ejecute jobs por labels. Es practico para dev, pero el socket de Docker es una frontera sensible: incluso en read-only, muchos setups permiten enumerar contenedores, imagenes, variables y metadatos.

Razonamiento: el Principio #0 pide resiliencia y minimo ops, no una superficie operacional dificil de auditar. El archivo se presenta como stack local, asi que no es un bug de prod hoy; es una advertencia para no copiarlo tal cual al VPS.

Sugerencia: en la imagen/compose de produccion, evaluar `job-run` con permisos minimos, un cron externo controlado, o un scheduler sin socket Docker si basta. Si se mantiene Ofelia, fijar version de imagen, limitar variables expuestas y documentar el modelo de permisos.

## Finding DEV-06 - Dependencias CDN sin SRI/CSP siguen siendo deuda de resiliencia

Severidad: Baja  
Evidencia: `templates/base.html:8-11`, `templates/base.html:72`

Bootstrap y fuentes cargan desde Google Fonts/jsDelivr sin `integrity`, y todavia no hay CSP. Esto ya aparece en `docs/TODO.md`, asi que no lo cuento como sorpresa, pero si como deuda real antes de produccion.

Razonamiento: el producto valora resiliencia y privacidad. CDNs externos pueden fallar, cambiar comportamiento, ser bloqueados por redes/ad blockers o complicar consentimiento/CSP.

Sugerencia: vendorizar Bootstrap y fuentes, o al menos agregar SRI donde aplique y una CSP compatible. Para un sitio server-rendered de bajo mantenimiento, self-host de assets criticos es una buena inversion.

---

# Persona 2: Experto en beisbol y sabermetria

## Finding SAB-01 - Entradas (`IP`/`innings`) como `float` en notacion beisbolera son peligrosas para agregados

Severidad: Alta  
Evidencia: `dglweb/stats/pitching_mapping.py:10`, `dglweb/stats/models.py:234`, `dglweb/stats/models.py:373`, `tests/test_pitching_mapping.py:117-119`, `tests/test_fielding.py:85`

El proyecto conserva `46.2` como "46 entradas y 2 outs", no como decimal. Eso reproduce la fuente, pero es una trampa para cualquier agregado posterior: sumar floats de notacion beisbolera produce resultados incorrectos. Ejemplo: `0.2 + 0.2 + 0.2` deberia ser `1.0` inning, pero aritmeticamente da `0.6`.

Razonamiento: Fase 4 construira lideres de carrera/temporada y paginas de jugador. Si se usa `Sum("ip")`, promedios por 9, rankings de innings, rate stats historicas o totales de fildeo con esos floats, los numeros quedaran sabermetricamente mal aunque los tests actuales pasen.

Sugerencia: almacenar una columna canonica en outs (`ip_outs`, `fielding_outs` o similar) para calculo, y renderizar a notacion beisbolera solo en display. Si se mantiene `ip` para paridad con la fuente, tratarlo como valor de presentacion/importacion, no como valor numerico agregable.

## Finding SAB-02 - Los lideres necesitan una abstraccion que excluya filas por equipo y use solo totales

Severidad: Alta  
Evidencia: regla documentada en `dglweb/stats/models.py:8-15`; constraints en `dglweb/stats/models.py:141-146`, `dglweb/stats/models.py:331-337`, `dglweb/stats/models.py:393-399`; tests base en `tests/test_batting_source.py:158-164` y `tests/test_pitching_source.py:131-135`

Batting y pitching guardan una fila por equipo mas una fila total `XXX` para jugadores cambiados. Fielding guarda una fila total por `(player, season, pos)` mas filas por equipo si hubo cambio. Esto es correcto para conservar detalle, pero si los lideres o paginas de carrera suman todas las filas, los jugadores cambiados se contaran doble.

Razonamiento: el diferenciador central del producto son lideres dominicanos. Un error de doble conteo en Manny, Soto, Cruz, Nelson, etc. seria visible y erosionaria confianza inmediatamente.

Sugerencia: antes de Fase 4, crear helpers/querysets canonicos tipo `Batting.objects.season_totals()`, `Pitching.objects.season_totals()` y `Fielding.objects.position_totals()`, con tests de agregacion. Para batting/pitching, seleccionar la fila de mayor `stint` por `(player, season)` o `team="XXX"` cuando exista y la unica fila cuando no exista. Para fielding, seleccionar `team="XXX"` por posicion cuando exista y la fila unica cuando no.

## Finding SAB-03 - El umbral de apariciones debe ser parte del modelo de lideres, no una constante escondida

Severidad: Alta  
Evidencia: decision pendiente en `docs/BUILD_PLAN.md:194-205`

La documentacion ya identifica el problema: sin minimo de PA/IP/J/G, los lideres de promedios los ganan muestras minusculas. Todavia no hay implementacion de lideres, pero este punto debe entrar como requisito tecnico de Fase 4, no como ajuste posterior.

Razonamiento: en sabermetria, un leaderboard sin calificacion muestra outliers triviales. Para batting, el minimo debe variar por temporada/juegos del equipo; para pitching y fielding la calificacion depende de metrica y rol. Un relevista no debe compararse igual que un abridor para rate stats de carrera sin contexto.

Sugerencia: modelar reglas de calificacion por deporte/metrica: PA para bateo, IP/BF/G/GS segun metrica de pitcheo, innings defensivos o chances para fildeo. Hacer los umbrales configurables en backoffice o al menos declarativos en codigo, con tests que prueben 2020, Ligas Negras y temporadas antiguas.

## Finding SAB-04 - `BAA` derivado usa una formula no estandar y puede divergir de la definicion oficial

Severidad: Media  
Evidencia: `dglweb/stats/pitching_mapping.py:201-221`, test en `tests/test_pitching_mapping.py:152-157`

El codigo deriva `BAA` como `H / (BF - BB - HBP - SH - SF - CI)`, documentado como formula `mlbstats`. Esa formula puede reproducir la fuente del dueno, pero no es exactamente la forma mas directa si ya se persiste `AB` contra el lanzador (`dglweb/stats/models.py:327`, mapeado desde proxy en `dglweb/stats/pitching_mapping.py:68`).

Razonamiento: desde el punto de vista beisbolero, batting average against normalmente es `H / AB` contra el pitcher. La formula desde `BF` reconstruye AB y depende de que `BF`, `SH`, `SF`, `CI`, `HBP` e `IBB/BB` esten perfectamente definidos para todas las eras. Como el proxy ya trae `AB`, hay una fuente mas directa.

Sugerencia: mantener la formula actual si el objetivo primario es paridad con `mlbstats`, pero documentar explicitamente que es "BAA segun fuente legacy". Para estadisticas publicas, comparar `H / AB` usando el `ab` del proxy contra el valor derivado y decidir cual mostrar. Agregar un test de divergencia cuando falte algun componente pero exista `AB`.

## Finding SAB-05 - Temporada regular esta hardcodeada; postemporada/LIDOM/Spring necesitaran parametros de deporte y `gameType`

Severidad: Media  
Evidencia: `dglweb/stats/_download.py:39`, `dglweb/stats/_download.py:74-78`, `dglweb/stats/fielding_source.py:59-63`, `dglweb/stats/management/commands/update_batting.py:24`, `dglweb/stats/management/commands/update_pitching.py:22`, `dglweb/stats/management/commands/update_fielding.py:22`, pendiente en `docs/BUILD_PLAN.md:185`

El pipeline actual usa `sportId=1`, `gameType=[R]` y `timezone.now().year`. Eso es correcto para temporada regular MLB, pero no escala solo a postemporada, LIDOM o Spring Training.

Razonamiento: LIDOM cruza anos calendario y Spring/Postseason cambian `gameType`/contexto. Si se reutiliza el pipeline sin parametrizar, puede cargar temporada equivocada, mezclar competiciones o dejar huecos invisibles.

Sugerencia: extender `SportConfig` o crear una configuracion de competicion con `sport_id`, `game_type`, temporada logica y calendario. Para `update_*`, evitar "ano actual" como unica regla y usar una funcion `current_mlb_season()` / `active_competition()` probada con fechas de enero, marzo, julio, octubre y noviembre.

## Finding SAB-06 - Las notas de contexto de Ligas Negras deben viajar con las paginas/stats, no solo con docs

Severidad: Media  
Evidencia: `docs/BUILD_PLAN.md:199-204`, mapeo de ligas en `dglweb/stats/leagues.py:25-40`

El codigo maneja bien los codigos de Negro Leagues por ID, pero la documentacion advierte que esas carreras vienen con cobertura incompleta: sin WAR, wOBA ni conteo de lanzamientos en varios casos. Si esas filas se presentan igual que MLB moderna, el lector puede inferir que las paginas reflejan la carrera completa del jugador.

Razonamiento: para Tetelo Vargas y otros, MLB reconoce solo una parte de la carrera real. Sabermetricamente, compararlos sin nota contra jugadores modernos es una falsa equivalencia.

Sugerencia: agregar un indicador de "cobertura historica limitada" por jugador/temporada/liga, y hacer que las paginas de jugador y lideres muestren nota contextual cuando una carrera incluya esas ligas. Tambien conviene que los lideres permitan excluir/incluir eras con cobertura incompleta segun la metrica.

---

# Observaciones positivas

- La separacion de responsabilidades esta bien lograda: cliente proxy (`dglweb/mlb/client.py`), descarga (`dglweb/stats/_download.py`), mapeos puros, loaders y comandos.
- La decision `NULL` sobre `0` para tasas indefinidas es correcta desde sabermetria y esta protegida por tests.
- La paridad contra fuente legacy esta tratada como herramienta de ingenieria, no como comentario manual.
- La regla de liga por ID, especialmente para Negro Leagues, evita un error real de clasificacion.
- `ruff`, `mypy strict` y `pytest` pasan en Docker; la base de calidad es alta.

# Prioridad sugerida

1. Antes de construir lideres: crear helpers/querysets de filas totales y normalizar entradas a outs para calculos.
2. Antes de seguir recargando master data: quitar o proteger el `delete()` cascada de `import_dgl_master --replace`.
3. Antes de produccion: sanitizar `IngestRun.detail`, vendorizar assets criticos y decidir el scheduler de prod.
4. Antes de cerrar Fase 3: cubrir `parity_pitching` y `parity_fielding` como comandos.
