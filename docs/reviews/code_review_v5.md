# Code Review v5 - dglweb

Fecha: 2026-07-25  
Proyecto: `C:\Users\aperd\Documents\DGLv2\apps\dglweb`

## Alcance

Antes de revisar codigo se leyeron los `.md` bajo `docs/`, incluyendo documentos de plan,
estandares, umbrales, motor de datos de apoyo, backlog y reviews previos. No se modifico codigo
fuente; este archivo es el unico entregable creado.

Verificacion ejecutada:

- `docker-compose run --rm --no-deps web ruff check .` - OK
- `docker-compose run --rm --no-deps web mypy .` - OK, 131 source files
- `docker-compose run --rm web pytest` - OK, 432 passed, cobertura total 96%

Nota operativa: el arbol ya tenia cambios locales antes del review (`dglweb/stats/derive.py`
modificado). No se tocaron ni revirtieron esos cambios.

## Resumen ejecutivo

El proyecto esta muy fuerte para su fase: `ruff`, `mypy strict` y `pytest` pasan; los fixes de v4
estan mayormente integrados; y el motor de lideres ya cubre empates, precision mostrada, postemporada,
IP en outs, sabermetricas acumulativas y career totals con bastante disciplina.

Los riesgos nuevos se concentran en tres zonas: la ruta manual de datos de apoyo, la robustez de
estados vacios/configuracion editorial, y la operacion diaria durante temporada viva. En beisbol, el
punto mas delicado es que el CSV de hits por tipo puede corregir coeficientes, pero todavia no valida
todo el contrato sabermetrico que esos coeficientes implican.

---

# Persona 1 - Python Principal Developer

## Finding DEV-01 - La carga de CSV puede terminar en 500 por encoding o dataset inexistente

Severidad: Media  
Evidencia: `dglweb/stats/staticdata/views.py:36`, `:60`, `:64`, `:76`,
`dglweb/stats/staticdata/engine.py:106-109`

`upload()` y `confirm()` usan `StaticDataset.objects.get(pk=pk)` sin 404 controlado, y `engine.read()`
hace `raw.decode("utf-8-sig")` sin capturar `UnicodeDecodeError`. Un `pk` invalido o un CSV no UTF-8
produce error 500 en una herramienta de backoffice que deberia fallar de forma explicable.

Sugerencia: usar `get_object_or_404()`, envolver lectura/decodificacion en un `Problem` de validacion
y agregar tests de vista para `pk` inexistente, archivo binario y CSV con encoding incorrecto.

## Finding DEV-02 - `leaders_context()` asume que siempre existe al menos una division/metrica

Severidad: Media/Alta  
Evidencia: `dglweb/profiles/leaderboards.py:375-381`

Si `dgl_leader` esta vacia, si no hay metricas activas para el grupo/posicion, o si una configuracion
editorial deja sin lideres una division, `division_labels[0]` o `tab_metrics[0]` levantan
`IndexError`. Es un caso probable en una base recien migrada, staging limpio o backoffice mal editado.

Sugerencia: devolver un contexto vacio renderizable (`board.columns=[]`, mensaje "sin lideres") y
agregar un test `leaders_context()` sin `Leader`/`Metric` activos. La UI ya sabe mostrar filas vacias;
falta proteger el nivel anterior.

## Finding DEV-03 - La comparacion de support data carga tablas completas en memoria

Severidad: Baja/Media  
Evidencia: `dglweb/stats/staticdata/engine.py:167-189`

`compare()` materializa todos los rows existentes y todos los entrantes para calcular claves y sumas.
Para `dgl_batted_ball_hits` probablemente es tolerable, pero el motor es generico y los docs lo
presentan como base para salarios, transacciones y futuros datasets.

Sugerencia: definir limites de tamano por dataset y, para tablas grandes, calcular agregados con ORM
(`Count`, `Sum`) y comparar claves por streaming/batches. Como minimo, documentar que este motor es
para datasets semi-estaticos pequenos/medianos.

## Finding DEV-04 - El upsert generico hace una query por fila

Severidad: Baja/Media  
Evidencia: `dglweb/stats/staticdata/engine.py:233-236`

En modo `UPSERT`, cada fila hace `update_or_create()`. Es correcto pero O(n) queries y puede volverse
lento para archivos anuales grandes.

Sugerencia: usar `bulk_create(..., update_conflicts=True, unique_fields=key_columns, update_fields=...)`
en Postgres cuando el modelo tenga constraint compatible. Mantener `update_or_create` como fallback
para datasets pequenos o claves no compatibles.

---

# Persona 2 - QA / Reliability Engineer

## Finding QA-01 - Filas de support data se descartan en silencio si el jugador no existe en master

Severidad: Alta  
Evidencia: `dglweb/stats/staticdata/loaders.py:67-73`

`BattedBallHitsLoader.resolve()` retorna `None` cuando `mlb_id` esta vacio o no existe en
`dgl_master`. Eso descarta filas sin reportarlas como problema. Peor: las filas descartadas tampoco
entran en los totales de cobertura por temporada, asi que un master incompleto puede hacer que el CSV
parezca mas sano de lo que esta.

Sugerencia: distinguir "fila sin MLB ID" de "MLB ID no existe en nuestro master". El segundo caso
debe bloquear o al menos aparecer como `Problem` con conteo y muestra de IDs, porque puede indicar
que falta cargar un dominicano nuevo antes del dataset de apoyo.

## Finding QA-02 - Las vistas de static data casi no tienen cobertura

Severidad: Media  
Evidencia: cobertura de `pytest`: `dglweb/stats/staticdata/views.py` 31%; `tests/test_staticdata.py`
cubre engine/loader, no flujo HTTP completo.

La pieza mas peligrosa del backoffice reemplaza datos, pero sus permisos, CSRF, sesion, archivo malo,
confirmacion y mensajes de error no estan ejercitados end-to-end.

Sugerencia: agregar tests con `Client`: anonimo redirige, usuario no admin no entra, admin sube CSV
valido y ve comparacion, `aviso_nombre`, problemas bloquean confirmacion, confirm sin sesion redirige,
CSV invalido no devuelve 500.

## Finding QA-03 - El scheduler encadena jobs por horario, no por un workflow observable

Severidad: Media  
Evidencia: `docker-compose.yml:54-73`, `docs/MEJORAS_FUTURAS.md:8-21`

Los jobs corren separados por minutos: updates, career totals, leaders, prune y parity. Si un update
falla, los rebuilds posteriores pueden correr con data parcial o vieja. El backlog ya reconoce que
orden/acoplamiento de jobs y temporada en curso siguen "A DISCUTIR".

Sugerencia: crear un comando orquestador diario que ejecute los pasos en orden, pare o marque
`PARTIAL` ante fallos, y deje un unico resumen operacional. Eso reduce estados intermedios invisibles.

## Finding QA-04 - La advertencia de nombre de archivo no bloquea la confirmacion

Severidad: Media  
Evidencia: `dglweb/stats/staticdata/views.py:54-68`, `templates/staticdata/compare.html:13`, `:64-67`

Si el nombre del CSV no coincide, la UI solo muestra warning; si el schema pasa, el boton de confirmar
sigue disponible. Para datasets con columnas compatibles accidentalmente, esto permite aplicar el
archivo equivocado.

Sugerencia: tratar mismatch de nombre como `Problem` bloqueante, o exigir una confirmacion adicional
explicita. La razon del control es evitar errores humanos de alto impacto, no solo informar.

---

# Persona 3 - Frontend Engineer

## Finding FE-01 - Hay rutas publicas visibles que no hacen nada

Severidad: Media  
Evidencia: `templates/base.html:25-33`, `:55-60`, `templates/home.html` contiene multiples `href="#"`

El buscador principal cancela submit con `onsubmit="return false"` y varios enlaces publicos apuntan
a `#` (`Articulos`, `Jugadores`, `Entrar`, legal y cards del home). En una beta esto se percibe como
camino roto, especialmente en mobile donde el nav es una de las pocas formas de explorar.

Sugerencia: ocultar links no implementados, apuntarlos a paginas reales/placeholder editorial, o
marcarlos como disabled sin `href`. Para el buscador, conectar typeahead/HTMX o quitarlo hasta que
exista la ruta.

## Finding FE-02 - Falta accesibilidad basica en controles de navegacion

Severidad: Baja/Media  
Evidencia: `templates/base.html:21-22`, `templates/profiles/leaders.html` nav tabs/pills

El navbar toggler no declara `aria-controls`, `aria-expanded` ni `aria-label`. Los tabs/pills de
leaders son links validos, pero no comunican `aria-current="page"` o `aria-selected` cuando estan
activos.

Sugerencia: completar atributos ARIA de Bootstrap y agregar `aria-current="page"` en links activos.
Esto mejora keyboard/screen readers sin cambiar arquitectura ni estilos.

## Finding FE-03 - El estado vacio de leaders depende de que el backend entregue columnas

Severidad: Media  
Evidencia: `dglweb/profiles/leaderboards.py:375-381`, `templates/profiles/leaders.html:102-131`

El template tiene `{% empty %}` para una columna sin rows, pero si no hay divisiones/metricas el
backend revienta antes de renderizar. El resultado no es un empty state sino un 500.

Sugerencia: crear un estado de pagina vacia a nivel de contexto: sin divisiones, sin metricas, sin
board. Renderizar copy corto y controles deshabilitados/ocultos.

---

# Persona 4 - Security Engineer

## Finding SEC-01 - Upload CSV sin limite de tamano permite DoS autenticado

Severidad: Alta  
Evidencia: `dglweb/stats/staticdata/views.py:58-64`, `dglweb/stats/staticdata/engine.py:106-109`

Attack scenario: una cuenta con acceso al grupo `Administrators` sube un CSV enorme o binario muchas
veces desde `/cms/datos-apoyo/<pk>/`.  
Exploitation method: el servidor hace `subido.read()`, decodifica todo en memoria, construye listas
completas y guarda el CSV completo en la sesion.  
Business impact: agotamiento de memoria/DB de sesiones, lentitud del backoffice, posible caida del
web process y bloqueo de una herramienta que reemplaza datos.  
Recommended fix: configurar limite por dataset (`max_upload_bytes`), rechazar `content_type`/extension
fuera de CSV, parsear con limite de filas/columnas, y guardar el borrador en una tabla temporal con
TTL en vez de la sesion.

## Finding SEC-02 - Dependencias CDN sin SRI/CSP siguen abiertas

Severidad: Media  
Evidencia: `templates/base.html:8-11`, `:67`, `docs/TODO.md` mantiene SRI/CSP en backlog.

Attack scenario: un CDN o ruta de red comprometida sirve CSS/JS malicioso.  
Exploitation method: el navegador carga Bootstrap JS desde jsDelivr y fuentes/CSS externos sin
`integrity` ni una CSP estricta que limite scripts/styles.  
Business impact: XSS supply-chain, robo de sesiones de usuarios, manipulacion del contenido visible
o redireccion a phishing.  
Recommended fix: vendorizar Bootstrap/fuentes o agregar SRI; definir CSP con `script-src`, `style-src`,
`font-src` y nonces/hashes para inline scripts necesarios.

## Finding SEC-03 - Ofelia usa Docker socket y una imagen `latest`

Severidad: Media  
Evidencia: `docker-compose.yml:79-88`

Attack scenario: compromiso del contenedor scheduler o de la imagen upstream de Ofelia.  
Exploitation method: el contenedor tiene acceso al Docker socket (`/var/run/docker.sock:ro`) y corre
`mcuadros/ofelia:latest`, que puede cambiar sin revision.  
Business impact: enumeracion de contenedores, metadatos/env, posible escalamiento segun version de
Docker/socket, y ejecucion no revisada de una nueva imagen.  
Recommended fix: pinnear digest/version, separar compose dev/prod, evaluar scheduler sin socket o
`job-run` con permisos minimos, y documentar el threat model antes de produccion.

## Finding SEC-04 - Controles OWASP revisados sin hallazgo activo

No se observaron usos de `eval`, `pickle`, SQL con f-strings, `csrf_exempt`, passwords propios o JWT
custom. Los formularios revisados incluyen CSRF, Django auto-escapa templates, secrets criticos salen
de entorno en prod, y el cliente HTTP tiene timeout/retry controlado.

---

# Persona 5 - Backend Architect

## Finding ARCH-01 - Cargar datos de apoyo actualiza season rows, pero no recompone derivados downstream

Severidad: Alta  
Evidencia: `dglweb/stats/staticdata/loaders.py:132-178`, `docker-compose.yml:66-69`

`post_apply()` reescribe hits por tipo en `Batting`/`Pitching` y recalcula coeficientes de esas filas,
pero no reconstruye `BattingCareer`/`PitchingCareer` ni `dgl_leader`. Hasta el siguiente job diario,
paginas de carrera y leaders pueden quedar sirviendo valores viejos.

Sugerencia: despues de un apply exitoso, disparar explicitamente `build_career_totals` y
`build_leaders`, o marcar esos artefactos como stale y mostrar estado en backoffice. Si el rebuild es
costoso, encolar una tarea y bloquear nuevas cargas hasta que termine.

## Finding ARCH-02 - El borrador de CSV vive en sesion, no como staging auditable

Severidad: Media  
Evidencia: `dglweb/stats/staticdata/views.py:63-64`, `:77-88`

La comparacion y confirmacion dependen de un unico valor de sesion. No hay id de revision, hash del
CSV, snapshot de comparacion, expiracion visible ni historial del archivo confirmado. Dos admins
pueden comparar contra estados distintos y confirmar en orden cruzado.

Sugerencia: introducir `StaticDatasetUpload` con `status`, `sha256`, usuario, created_at, dataset,
raw file/blob o storage path, comparison snapshot y estado aplicado. Confirmar por upload id con
optimistic locking contra `last_update`/hash de tabla.

## Finding ARCH-03 - La pagina de leaders depende de helpers privados de tabs

Severidad: Baja/Media  
Evidencia: `dglweb/profiles/leaderboards.py:18-21`

`leaderboards.py` importa `_DESCRIPTIVE_COLUMNS`, `_pretty_qualifier`, `_puestos_layout` y
`_qualifier_context` desde `profiles.tabs`. Son helpers privados de otra vista. Esto acopla dos
superficies publicas distintas y hace que un refactor de tabs pueda romper `/lideres/`.

Sugerencia: mover layout de metricas, formato de qualifiers y categorias descriptivas a un modulo
publico (`profiles.metric_catalog` o `stats.presentation`). Mantener `tabs.py` y `leaderboards.py`
como consumidores.

## Finding ARCH-04 - `StaticDataset` permite configuraciones que el engine no puede cumplir

Severidad: Media  
Evidencia: `dglweb/stats/models.py:1296-1358`, `dglweb/stats/staticdata/engine.py:112-145`,
`dglweb/stats/staticdata/views.py:36-43`

El admin puede crear una fila con `table` sin loader, `natural_key` que no existe en el modelo, o un
modo upsert sin constraint compatible. Algunos casos muestran "sin loader"; otros fallan mas tarde
como keys vacias, duplicados raros o `KeyError`.

Sugerencia: validar `table in REGISTRY`, `natural_key` contra campos resolvidos del loader/modelo, y
modo `UPSERT` contra una constraint unica. Hacerlo en `clean()` del modelo o en el form de Wagtail.

---

# Persona 6 - Experto en beisbol y sabermetria

## Finding SAB-01 - La cobertura de hits por tipo se valida por temporada, no por oficio

Severidad: Media/Alta  
Evidencia: `dglweb/stats/staticdata/loaders.py:101-120`

`checks()` agrega `h_typed/h_all` solo por `season`. Si `batting` esta completo y `pitching` viene
incompleto (o al reves), el agregado combinado puede pasar el 80% y dejar que un grupo defectuoso
alimente coeficientes.

Sugerencia: validar cobertura por `(season, stat_group)` y reportar ambos cortes. Bateadores y
lanzadores usan los mismos nombres de columnas, pero sabermetricamente son universos distintos.

## Finding SAB-02 - No se reconcilian hits tipificados con el `H`/`BIP` de la fila de temporada

Severidad: Media  
Evidencia: `dglweb/stats/staticdata/loaders.py:165-174`,
`dglweb/stats/derive.py:137-158`

El loader pisa hits por tipo si Retrosheet trae mas hits tipificados que el proxy, y luego divide
tipos de batazo entre `balls_in_play` existente. No valida que `ground_hits+fly_hits+line_hits+pop_hits`
sea compatible con `Batting.h`/`Pitching.h` ni que tipos + outs no excedan BIP.

Riesgo sabermetrico: si el CSV usa una poblacion o definicion distinta, los coeficientes pueden sumar
mas de 100%, o mejorar la cobertura aparente con componentes que no pertenecen exactamente al mismo
denominador.

Sugerencia: antes de actualizar cada season total, validar `typed_hits <= h` cuando exista `h`, y
`typed_hits + typed_outs <= balls_in_play` con tolerancia documentada. Si falla, bloquear la carga o
reportar esos rows como excepciones a revisar.

## Finding SAB-03 - La temporada viva todavia no tiene umbrales prorrateados por juegos jugados

Severidad: Media  
Evidencia: `dglweb/stats/management/commands/update_batting.py:23-25`,
`docs/MEJORAS_FUTURAS.md:8-21`

Los `update_*` usan `timezone.now().year` y el scheduler reconstruye leaders diariamente, pero el
backlog reconoce que faltan tabla de juegos, temporada logica y politica de datos parciales. En una
temporada en curso, los rate leaders con 502 PA/162 IP pueden salir vacios o sesgados hasta muy tarde.

Sugerencia: no publicar leaderboards de tasa de la temporada actual hasta tener `team_games`/games
played y marca visual de "temporada en curso", o prorratear qualifiers con una tabla de calendario.

## Finding SAB-04 - Skips de jugadores faltantes pueden sesgar el universo dominicano

Severidad: Media  
Evidencia: `dglweb/stats/staticdata/loaders.py:67-73`,
`docs/CONCEPT.md` define `dgl_master` como autoridad del subset dominicano.

Desde el punto de vista del producto, la tabla maestra es la autoridad. Si un CSV de apoyo trae un
`mlb_id` que no esta en master y se descarta sin alarma, el subset dominicano queda incompleto y los
leaderboards/historicos pueden omitir un jugador real.

Sugerencia: convertir IDs desconocidos en reporte de cobertura de master. El admin debe resolver la
tabla maestra antes de cargar apoyo estadistico que afecte rankings.

---

# Observaciones positivas

- Los gates estan verdes: ruff, mypy strict y 432 tests.
- Los problemas fuertes de v4 aparecen corregidos: postemporada respeta flags, single-round badges,
  fracciones de innings invalidas, CS% y copy de descriptivas tienen tests.
- La decision NULL-sobre-0 sigue bien aplicada y protegida por tests.
- `build_leaders` tiene advisory lock y constraint unica; buena defensa para rebuilds completos.
- Los docs nuevos de datos de apoyo explican muy bien el contrato operacional antes de tocar tablas.

# Prioridad sugerida

1. Endurecer la ruta de support data: limites de upload, errores controlados, tests de vista y staging auditable.
2. Evitar datos silenciosamente omitidos: unknown `mlb_id` debe bloquear o reportarse.
3. Hacer que support data marque/reconstruya career totals y leaders inmediatamente.
4. Proteger estados vacios en `/lideres/`.
5. Cerrar la politica de temporada viva antes de publicar rate leaderboards diarios.
