# Code Review v8

Fecha: 2026-07-27  
Alcance: review estatico del proyecto, despues de leer los `.md` bajo `docs/`.  
Restriccion aplicada: no se modifica codigo fuente; solo se crea este documento.

## Filtro aplicado antes del review

No repito hallazgos que ya estan marcados como pendientes en `docs/TODO.md`, incluyendo buscador de articulos, paginacion real del indice, "Lo mas leido" real, seed de articulos, servir/respaldar `media`, monitor externo para `/health/pipeline`, restart pendiente del scheduler, correcciones SQL Server de posiciones, SRI/CSP/vendor assets y mejoras sabermetricas exactas ya aparcadas.

Tampoco reporto los placeholders o datos falsos de la portada, porque el dueno aclaro que son un known issue de desarrollo.

## Persona 1: Python Principal Developer

### DEV-01 [P2] `update_roster_moves` no usa el cliente MLB centralizado ni lo cierra

**Evidencia:** `dglweb/stats/management/commands/update_roster_moves.py:42-44`; el resto de comandos usa `build_client()` en `dglweb/mlb/client.py`.

**Finding:** el comando instancia `MlbProxyClient(settings.MLB_PROXY_URL, settings.MLB_PROXY_API_KEY)` directamente. Eso omite `settings.MLB_PROXY_TIMEOUT`, evita el patron `with build_client() as client` y deja el cierre del cliente a la salida del proceso.

**Impacto:** comportamiento inconsistente entre scrapers. Si produccion ajusta `MLB_PROXY_TIMEOUT`, este job no respeta la configuracion. Tambien complica testear politicas de cliente en un solo punto.

**Mejora sugerida:** usar `from dglweb.mlb.client import build_client` y envolverlo en `with build_client() as cliente:`. Razonamiento: una sola puerta para timeouts, headers, retries y cierre reduce drift operativo.

### DEV-02 [P2] Una transaccion malformada puede tumbar la corrida completa de roster moves

**Evidencia:** `dglweb/stats/roster_moves.py:189-199` convierte `id`, `person.id` y `date` con `int()` / `date.fromisoformat()` sin aislar errores por fila.

**Finding:** `_movimiento()` devuelve `None` cuando faltan campos, pero no captura `ValueError` / `TypeError` si el feed trae un `id` no numerico o una fecha con formato inesperado. En ese caso, una sola fila del API puede abortar todo `update_roster_moves`.

**Impacto:** crash del job horario y cintillo viejo aunque las demas transacciones fueran validas.

**Mejora sugerida:** envolver la normalizacion de una fila en `try/except (TypeError, ValueError)` y saltar/quarentenar esa fila con nota en `IngestRun`. Agregar tests para `date="2026-07-20T00:00:00Z"` y `id="abc"`.

### DEV-03 [P3] El contrato editorial de categoria obligatoria no esta codificado

**Evidencia:** `dglweb/articles/models.py:197-204` permite `categoria = ForeignKey(..., null=True, blank=True)`, mientras el docstring del modulo dice que la categoria es "una y solo una".

**Finding:** un articulo live puede salir sin categoria. Las plantillas lo toleran, pero el contrato editorial que organiza el indice no queda protegido por modelo, validacion de Wagtail ni test.

**Impacto:** tarjetas sin kicker, articulos que no aparecen bajo ningun filtro de categoria y drift entre documentacion y comportamiento real.

**Mejora sugerida:** si la regla sigue siendo obligatoria, hacer `blank=False, null=False` con migracion de datos o validar en `clean()` solo al publicar. Si se quiere permitir "sin categoria", ajustar docstring y tests para que sea una decision explicita.

## Persona 2: QA / Reliability Engineer

### QA-01 [P2] Los jobs horarios vivos no estan cubiertos por el semaforo operativo

**Evidencia:** Ofelia define `mlb-leaders-hourly` y `roster-moves-hourly` en `ofelia/config.ini:77-100`, pero `/health/pipeline` solo consulta la ultima fila `refresh_daily` en `dglweb/core/views.py:118-131`. El pipeline diario tampoco incluye roster moves en `dglweb/stats/pipeline.py:42-48`.

**Finding:** si `build_mlb_leaders` o `update_roster_moves` fallan durante horas, el monitor de `/health/pipeline` puede seguir verde mientras la portada muestra modulos "vivos" viejos.

**Impacto:** falla user-facing silenciosa: lideres MLB y cintillo dejan de actualizarse sin alertar por el semaforo principal.

**Mejora sugerida:** agregar un health separado para widgets horarios o extender el actual con checks de frescura por comando critico (`build_mlb_leaders`, `update_roster_moves`) con umbrales distintos. Testear estados: missing row, stale row, failed row.

### QA-02 [P2] El parser de roster moves no tiene pruebas de filas parcialmente corruptas

**Evidencia:** `tests/test_roster_moves.py` cubre traducciones, duplicados, universo dominicano y filtro del cintillo, pero no entradas con tipos/fechas invalidas; el punto de falla esta en `dglweb/stats/roster_moves.py:189-199`.

**Finding:** hay buena cobertura del happy path y de "no mostrar ingles", pero falta cobertura de contratos externos rotos.

**Impacto:** regressions de confiabilidad no se detectan antes del scheduler.

**Mejora sugerida:** tests parametrizados para filas con `person=None`, `id=None`, `id="x"`, `date=""`, `date` con timestamp y `transactions` no-list. El resultado esperado debe ser saltar la fila y dejar trazabilidad, no abortar el lote.

### QA-03 [P3] "Ver mas articulos" no degrada bien si falla JavaScript

**Evidencia:** `templates/articles/article_index_page.html` renderiza articulos extra con `hidden`, y `static/js/articulos.js` es el unico que los destapa.

**Finding:** si JS falla o esta deshabilitado, el boton queda visible pero no puede revelar el contenido ya presente en HTML.

**Impacto:** UX rota en un camino de lectura: el usuario ve que hay mas articulos pero el control no funciona.

**Mejora sugerida:** usar un fallback `<noscript>` que muestre los articulos ocultos o renderizar enlaces de paginacion/filtro cuando no hay JS. Esto no reemplaza la paginacion pendiente del backlog; solo evita un control muerto.

## Persona 3: Frontend Engineer

### FE-01 [P1] El cintillo duplica enlaces dentro de `aria-hidden`

**Evidencia:** `templates/widgets/_cintillo.html:26-32` duplica la lista; la segunda `ul` lleva `aria-hidden="true"`, pero sus `<a>` siguen siendo focusables. El CSS solo pausa con hover en `static/css/site.css:1137`.

**Finding:** `aria-hidden` no saca los enlaces del orden de tabulacion. Un usuario de teclado puede caer en enlaces que el lector de pantalla debe ignorar. Ademas, al enfocar un link del cintillo, la animacion no se pausa porque solo existe `:hover`, no `:focus-within`.

**Impacto:** navegacion por teclado confusa y posible incumplimiento de accesibilidad: foco visible moviendose en una tira animada y elementos interactivos ocultos para tecnologias asistivas.

**Mejora sugerida:** marcar la lista duplicada como `inert` o poner `tabindex="-1"` en sus enlaces, y pausar con `.dgl-cintillo:focus-within .dgl-cintillo-tira`. Agregar test de template que asegure que la copia `aria-hidden` no contiene anchors focusables.

### FE-02 [P2] La pizarra acumula listeners globales en cada refresco

**Evidencia:** `static/js/pizarra.js:131-200`; `preparar()` registra `document.addEventListener("click", ...)` cada vez que se reemplaza el fragmento tras `fetch("/pizarra/")`.

**Finding:** durante juegos en vivo, el widget se refresca cada minuto y vuelve a llamar `preparar(nuevo, false)`. Cada llamada deja un listener global nuevo cerrando sobre un `raiz` viejo.

**Impacto:** fuga gradual de memoria y handlers duplicados durante sesiones largas; tambien puede ejecutar cierres sobre nodos que ya no estan en el DOM.

**Mejora sugerida:** registrar el listener global una sola vez o usar `AbortController` / cleanup al reemplazar el banner. Otra opcion: delegar el click en un contenedor estable.

### FE-03 [P3] El control de "Ver mas articulos" depende totalmente de JS

**Evidencia:** `static/js/articulos.js` remueve `hidden`; sin ese script, el HTML extra sigue oculto.

**Finding:** el componente esta cerca de progressive enhancement, pero no llega: los articulos ya estan en el HTML, solo que inaccesibles sin JS.

**Impacto:** camino roto para navegadores restrictivos, errores de carga JS o lectores que no ejecuten scripts.

**Mejora sugerida:** renderizar los extras visibles por defecto y ocultarlos solo cuando JS inicializa correctamente, o proveer fallback `<noscript>`.

## Persona 4: Security Engineer

### SEC-01 [P2] Endpoint publico con consulta a DB sin throttle/cache defensivo

**Evidencia:** `/health/pipeline` esta publico por diseno en `dglweb/core/views.py:72-100` y toca base en `dglweb/core/views.py:104-131`.

**Attack scenario:** un tercero automatiza requests frecuentes a `/health/pipeline`. Aunque ya no vea detalle anonimo, cada request fuerza evaluacion de ventana de temporada y consulta a `IngestRun`.

**Exploitation method:** HTTP flood barato contra un endpoint que no requiere autenticacion. No necesita payload especial ni credenciales.

**Business impact:** consumo innecesario de conexiones/CPU de la app y la base; en un VPS pequeno puede degradar la portada o el Backoffice. Tambien facilita distinguir si el endpoint existe y esta vivo.

**Recommended fix:** cachear el semaforo anonimo por 30-60 segundos y aplicar rate limit en proxy/app. Mantener detalle solo para staff/token como esta ahora. Si el monitor necesita frescura alta, usar TTL corto y headers `Cache-Control` apropiados.

### SEC-02 [P3] Documentos subidos por Wagtail quedan servidos publicamente

**Evidencia:** `config/urls.py` incluye `path("documents/", include(wagtaildocs_urls))`; `config/settings/base.py` habilita `wagtail.documents` y extensiones `csv`, `docx`, `pdf`, `xlsx`.

**Attack scenario:** un editor sube por error un spreadsheet o PDF interno al CMS pensando que es un adjunto privado. El archivo queda disponible por URL publica bajo `/documents/`.

**Exploitation method:** enumeracion de URLs conocidas/compartidas, indexacion accidental o fuga por enlaces en previews/correos.

**Business impact:** exposicion de documentos editoriales, datos operativos o archivos de soporte que no estaban pensados para publico.

**Recommended fix:** definir politica explicita: documentos Wagtail son publicos. Si no se necesitan documentos publicos, quitar `wagtail.documents`/ruta o reemplazar el serve view por uno con permisos. Agregar prueba que confirme el comportamiento esperado.

### SEC-03 [P3] No se observo XSS/SQLi directo en bloques editoriales, pero falta una prueba de regresion para links enriquecidos

**Evidencia:** los bloques de articulos escapan valores en plantillas y `RichTextBlock` limita features a `bold`, `italic`, `link`, `ol`, `ul` en `dglweb/articles/blocks.py`.

**Attack scenario:** un usuario editorial intenta insertar enlaces con esquemas peligrosos o HTML no permitido en rich text/table cells.

**Exploitation method:** payload en Wagtail RichText o TableBlock si una futura ampliacion activa features mas permisivas.

**Business impact:** riesgo futuro de XSS almacenado en paginas de articulo.

**Recommended fix:** agregar tests con payloads como `javascript:` y HTML en celdas/entradilla para congelar el comportamiento seguro actual antes de ampliar features.

## Persona 5: Backend Architect

### ARCH-01 [P2] Observabilidad fragmentada entre pipeline diario y jobs horarios

**Evidencia:** jobs horarios en `ofelia/config.ini:77-100`; `pipeline.py` agrupa `refresh_daily` y widgets diarios, pero no los horarios en `dglweb/stats/pipeline.py:42-48`.

**Finding:** la arquitectura ya resolvio el problema de "un dia como unidad" para el refresco diario, pero los modulos vivos nuevos vuelven a quedar como procesos separados que dependen de leer `IngestRun` manualmente.

**Impacto:** single point of failure operacional: Ofelia puede correr el pipeline diario y fallar un job horario sin que la salud agregada lo capture.

**Mejora sugerida:** crear una entidad de salud para "live widgets" con freshness por comando, o registrar un agregado horario pequeno. Separar umbrales: diario para `refresh_daily`, 2-3 horas para `build_mlb_leaders`/`update_roster_moves`.

### ARCH-02 [P3] Cache de URL de articulos puede quedar obsoleto tras mover/despublicar el indice

**Evidencia:** `dglweb/articles/context_processors.py:22-40` cachea la URL por 24h en `articles:indice`.

**Finding:** el comentario de diseno dice que se guarda por ID para tolerar movimientos, pero el codigo cachea la URL. Si el editor mueve, renombra o despublica el indice, menu/pie pueden apuntar a una ruta vieja hasta un dia.

**Impacto:** navegacion rota temporal despues de una operacion editorial legitima.

**Mejora sugerida:** cachear el `pk` y resolver URL con invalidacion por senales de Wagtail, o cachear URL pero limpiar `articles:indice` en publish/move/unpublish. Agregar test que mueva el indice y verifique que el menu cambia sin esperar TTL.

### ARCH-03 [P3] El indice del cintillo no coincide con la consulta principal

**Evidencia:** `RosterMove.Meta` indexa `["-fecha", "mlb_id"]`; `roster_moves.portada()` filtra `fecha__gte`, `player__isnull=False`, `texto <> ""` y ordena por `-fecha`, `-transaction_id`.

**Finding:** para el volumen actual no duele, pero el indice no esta alineado con el query path del header que corre en todas las paginas cuando vence cache.

**Impacto:** a largo plazo, mas scanning del necesario sobre una tabla historica de transacciones.

**Mejora sugerida:** considerar un indice parcial para portada: fecha desc + transaction_id desc, con condicion `player_id IS NOT NULL` y `texto <> ''` si Postgres es el target. Mantener el indice por `mlb_id` si hace falta para pantallas historicas por jugador.

## Persona 6: Experto en beisbol y sabermetria

### SAB-01 [P1] El grafico de barras asume que todas las metricas son no negativas

**Evidencia:** `_escala()` devuelve `(0, max(valores))` para barras en `dglweb/articles/blocks.py:61-75`; la geometria usa ese rango en `dglweb/articles/blocks.py:133-149`.

**Finding:** en beisbol muchas metricas validas pueden ser negativas: OAA, DRS, run value, WPA, RE24, WAR en muestras cortas, diferenciales y valores contra promedio. Con valores negativos o mixtos, las barras pueden renderizar alturas negativas, ejes invertidos o una comparacion visual falsa.

**Impacto:** articulo sabermetrico puede publicar un grafico que visualmente miente aunque los numeros escritos sean correctos.

**Mejora sugerida:** para barras, usar dominio `min(0, min(valores))` a `max(0, max(valores))`, calcular la linea base de cero dentro del SVG y dibujar barras positivas hacia arriba y negativas hacia abajo. Agregar tests para `[5, -3]` y `[-8, -2]`.

### SAB-02 [P2] La fuente del grafico es opcional aunque el propio bloque dice que sin fuente no se puede comprobar

**Evidencia:** `GraficoBlock.fuente` tiene `required=False` en `dglweb/articles/blocks.py:105-108`.

**Finding:** para periodismo de datos y sabermetria, un grafico sin fuente o metodologia no es verificable. El help text reconoce la regla, pero el modelo no la hace cumplir.

**Impacto:** lectores pueden ver comparaciones de WAR, wOBA, percentiles o conteos historicos sin saber si vienen de MLB, Baseball Savant, FanGraphs, Baseball-Reference o calculo propio. Eso abre la puerta a conclusiones no reproducibles.

**Mejora sugerida:** hacer `fuente` obligatoria o reemplazarla por un bloque estructurado con `origen` y `nota_metodologica`. Permitir una opcion explicita como "Datos propios de DGL" cuando salga de las tablas internas.

### SAB-03 [P3] El bloque de jugador puede enlazar jugadores ocultos editorialmente

**Evidencia:** `JugadorBlock` permite escoger cualquier snippet `players.Player` en `dglweb/articles/blocks.py`, y la plantilla siempre genera enlace si hay jugador.

**Finding:** si un jugador se marca `hidden=True` despues de publicar un articulo, la mencion editorial puede conservar un enlace hacia una ficha que el sitio publico ya oculta/404.

**Impacto:** articulo con link roto o inconsistente con la politica de jugadores deshabilitados.

**Mejora sugerida:** al renderizar, comprobar visibilidad publica antes de enlazar; si esta oculto, mostrar solo texto o una nota editorial. Agregar test con jugador hidden mencionado en un articulo.

## Notas positivas

- La autoridad dominicana respeta `dgl_master` / `dom_players` y no usa `birthCountry` en los modulos revisados.
- Los bloques de articulos escapan contenido editable y el grafico SVG incluye `role="img"` con descripcion.
- La pizarra tiene cache corta y respaldo, evitando pedir al proxy por visita.
- El review v7 parece incorporado en varios puntos: siglas inglesas, detalle anonimo reducido en `/health/pipeline`, accesibilidad de pizarra y candado de derivados.

## Verificacion realizada

- Lectura de documentacion bajo `docs/`, incluyendo `TODO.md`, planes, autoridad, estandares y reviews anteriores.
- Inspeccion estatica de modelos, comandos, templates, JS, CSS, settings, scheduler y tests relacionados.
- No se ejecutaron cambios de codigo fuente ni migraciones.
