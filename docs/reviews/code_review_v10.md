# Code Review v10

Fecha: 2026-07-28  
Alcance: review estático del proyecto después de leer los `.md` bajo `docs/`, incluyendo `TODO.md`,
planes, autoridad, estándares, umbrales y reviews anteriores.  
Restricción aplicada: no se modifica código fuente; este archivo es el único entregable.

## Filtro aplicado

No repito issues ya aceptados, pendientes o cerrados en `docs/TODO.md`. En particular quedan fuera:
placeholders/datos falsos de portada, hardening ya listado para despliegue, media/backups, monitor
externo, límites de rate limit ya decididos, mejoras sabermétricas futuras documentadas, cachés ya
aceptadas, correcciones de v9 y de reviews previos.

Tampoco vuelvo a levantar CDN/SRI/CSP como deuda: en el código actual ya hay assets locales bajo
`static/vendor/` y middleware CSP propio.

## Resumen ejecutivo

No encontré P1 nuevos. El proyecto viene cerrando deuda rápido y varias clases de bugs de reviews
anteriores ya tienen tests. Los riesgos nuevos están en cuatro bordes:

- Un job horario visible en portada (`build_daily_standouts --fecha-hoy`) quedó fuera del semáforo
  `/health/pipeline`.
- Ese mismo job usa fecha calendario local para una realidad beisbolera que cruza medianoche.
- Los listados propios de artículos usan `live()` pero no `public()`, lo que puede filtrar metadata
  de páginas Wagtail restringidas.
- El modal de video restauró foco al cerrar, pero todavía no atrapa foco mientras está abierto.

---

## Persona 1: Python Principal Developer

### DEV-01 [P2] La lista de jobs horarios vigilados tiene una fuente de verdad duplicada

**Evidencia:** `dglweb/core/views.py:23` define `HORARIOS = ("build_mlb_leaders", "update_roster_moves")`, mientras `ofelia/config.ini:117-120` agregó `daily-standouts-hourly` con `python manage.py build_daily_standouts --fecha-hoy`. Los tests parametrizan desde `HORARIOS` en `tests/test_pipeline_health.py:232` y `:246`, así que tampoco detectan la omisión.

**Finding:** el scheduler y el healthcheck operativo evolucionan por listas separadas. Cuando entra un módulo vivo nuevo, el test sigue verde porque valida la misma lista incompleta que usa producción.

**Impacto:** un widget horario puede romperse sin que `/health/pipeline` se ponga rojo.

**Mejora sugerida:** mover la definición de jobs vivos a un registro único con metadata (`command`, `cadence`, `freshness`, `healthy_statuses`, `season_window`, `scope/mode`) y consumirlo desde el healthcheck. Como mínimo, agregar una prueba que compare los jobs horarios esperados del calendario con los comandos vigilados.

**Razonamiento:** el problema no es la tupla en sí; es que una decisión operacional vive en dos sitios que no se validan entre sí.

---

## Persona 2: QA / Reliability Engineer

### QA-01 [P2] El job horario de destacados de hoy puede fallar y el semáforo seguir verde

**Evidencia:** `ofelia/config.ini:117-120` corre `build_daily_standouts --fecha-hoy` cada hora; `dglweb/core/views.py:23` solo vigila `build_mlb_leaders` y `update_roster_moves`; `_horarios_atrasados()` recorre solo `HORARIOS` en `dglweb/core/views.py:336`.

**Finding:** “Destacados de la jornada en curso” alimenta un widget visible de portada, pero no participa del check de frescura horario. Si falla durante horas, el monitor externo puede seguir verde siempre que el refresco diario y los otros dos jobs estén sanos.

**User-facing bug:** la portada parece viva pero no sube actuaciones nuevas de juegos ya terminados.

**Mejora sugerida:** incluir este job en el semáforo con una política propia: `SUCCESS` debe contar como sano, y algunos `SKIPPED` esperados también, por ejemplo “ningún juego ha terminado todavía”. Agregar tests para: success reciente, fallos repetidos, skipped sano, skipped inesperado y job ausente.

**Razonamiento:** este job no es mantenimiento interno; publica contenido fresco. Si se queda atrás, el usuario ve dato viejo con apariencia de actualidad.

### QA-02 [P3] `--fecha-hoy` no cubre bien juegos tardíos después de medianoche

**Evidencia:** el calendario dice que el job corre toda la noche para cubrir juegos del Pacífico (`ofelia/config.ini:102-115`), pero el comando calcula `dia` con `timezone.localdate()` cuando se usa `--fecha-hoy` (`dglweb/stats/management/commands/build_daily_standouts.py:56`). Luego filtra equipos terminados para ese `dia` exacto (`dglweb/stats/management/commands/build_daily_standouts.py:72`, `dglweb/stats/daily.py:378-395`).

**Finding:** a las 00:50 en República Dominicana, un juego de la costa oeste que empezó la noche anterior sigue perteneciendo a la jornada MLB anterior, pero `--fecha-hoy` ya apunta al nuevo día calendario local.

**Crash/user-facing scenario:** no crashea; peor: salta o guarda la jornada equivocada. Los destacados de un dominicano en un juego tardío pueden no aparecer hasta el refresco diario de las 4:30.

**Mejora sugerida:** resolver “jornada viva” desde la pizarra/calendario MLB, no desde `localdate()` a secas. Opciones: procesar todas las jornadas de la pizarra que tengan juegos vivos o finalizados recientemente, o usar un corte beisbolero tipo “antes de 4:00 a. m. todavía cuenta como ayer” con test congelado a `00:50`.

**Razonamiento:** en béisbol, la fecha de juego no siempre coincide con la fecha civil del servidor cuando el juego cruza medianoche.

---

## Persona 3: Frontend Engineer

### FE-01 [P3] El modal de video no atrapa el foco

**Evidencia:** `static/js/video.js:18-38` crea un `div` con `role="dialog"` y escucha Escape; `static/js/video.js:51` enfoca el botón de cerrar; `static/js/video.js:62` devuelve el foco al cerrar. No hay trap para Tab/Shift+Tab ni `inert`/bloqueo del contenido de fondo.

**Finding:** el modal hace bien varias cosas, pero mientras está abierto el usuario de teclado puede tabular hacia enlaces y botones detrás del overlay.

**Broken UX path:** abrir un video, presionar Tab varias veces, y el foco sale visualmente del diálogo aunque el modal siga abierto.

**Mejora sugerida:** usar `<dialog>.showModal()` si encaja con el soporte objetivo, o implementar focus trap: calcular elementos tabbables dentro del modal, ciclar Tab/Shift+Tab, marcar el fondo como `inert` mientras está abierto y añadir test JS.

**Razonamiento:** `aria-modal="true"` promete que el resto de la página queda fuera de interacción; el comportamiento de teclado tiene que cumplir esa promesa.

---

## Persona 4: Security Engineer

### SEC-01 [P2] Los listados propios pueden exponer metadata de páginas Wagtail restringidas

**Evidencia:** `ArticleIndexPage.articulos()` usa `ArticlePage.objects.child_of(self).live()` en `dglweb/articles/models.py:203`; la portada usa `ArticlePage.objects.live()` en `dglweb/core/views.py:48`; el enlace del índice usa `ArticleIndexPage.objects.live().first()` en `dglweb/core/views.py:72`. No aparece uso de `.public()` en el proyecto.

**Attack scenario:** un editor marca un artículo o sección Wagtail como restringido/privado para embargo editorial. Wagtail protegería el detalle servido por su router, pero las vistas propias de portada/índice/búsqueda siguen consultando páginas `live`.

**Exploitation method:** usuario anónimo visita `/`, `/articulos/` o `/articulos/?q=...` y ve título, entradilla, imagen, categoría, tags y fecha en tarjetas/listados, aunque el cuerpo completo esté protegido.

**Business impact:** fuga de contenido editorial no publicado para público general: titulares de primicias, imagen asociada, tema del artículo o existencia de una pieza privada.

**Recommended fix:** cambiar los querysets públicos de artículos e índice a `live().public()` cuando la intención sea respetar restricciones Wagtail. Agregar tests con `PageViewRestriction` que comprueben que un artículo restringido no aparece en portada, índice ni búsqueda. Si el producto decide no usar privacidad Wagtail, documentarlo explícitamente y deshabilitar/evitar esa expectativa editorial.

**Razonamiento:** en Wagtail, “live” significa publicado en el árbol; no necesariamente “visible para cualquier visitante”.

---

## Persona 5: Backend Architect

### ARCH-01 [P2] La observabilidad de widgets vivos no tiene contrato por tipo de job

**Evidencia:** `_horarios_atrasados()` filtra por `command` y exige `status=SUCCESS` (`dglweb/core/views.py:334-343`). `build_daily_standouts` se usa en dos modos: diario dentro de `refresh_daily` (`dglweb/stats/pipeline.py:51`) y horario con `--fecha-hoy` (`ofelia/config.ini:120`), pero ambos escriben `command="build_daily_standouts"` (`dglweb/stats/management/commands/build_daily_standouts.py:80`).

**Finding:** al agregar el job faltante, el modelo actual todavía queda ambiguo: una corrida diaria exitosa para “ayer” puede parecer frescura del job horario de “hoy”, y un `SKIPPED` sano puede parecer falla si se exige solo `SUCCESS`.

**Scalability bottleneck:** cada widget vivo nuevo obliga a codificar una excepción en el healthcheck. Eso escala mal cuando portada empieza a tener más módulos live.

**Mejora sugerida:** modelar jobs vivos como contrato explícito, no solo `command`: `job_id` o `mode` (`daily_standouts_current_day`), scope esperado, estados saludables aceptados, umbral de frescura y ventana de temporada. Guardarlo en `IngestRun` o derivarlo de un registro central.

**Razonamiento:** la arquitectura ya resolvió el pipeline diario como unidad; los widgets horarios necesitan una unidad similar para no volver a observabilidad fragmentada.

---

## Persona 6: Experto en béisbol y sabermetría

### SAB-01 [P3] Falsa asunción: la fecha civil local equivale a la jornada MLB activa

**Evidencia:** `build_daily_standouts --fecha-hoy` usa `timezone.localdate()` como jornada (`dglweb/stats/management/commands/build_daily_standouts.py:56`) y el comentario del scheduler justifica correr de madrugada por los juegos del Pacífico (`ofelia/config.ini:102-115`).

**False assumption:** que “hoy” en Santo Domingo es siempre la jornada que debe actualizarse. Para MLB, un juego que empieza el 28 de julio y termina a la 1:15 a. m. dominicana del 29 sigue siendo parte de la fecha de juego del 28.

**Uso incorrecto de contexto beisbolero:** los splits `byDateRange` y la pizarra se interpretan por fecha de juego; usar el reloj civil puede omitir actuaciones tardías o meterlas tarde.

**Mejora sugerida:** definir una función de “baseball day” o derivar la jornada desde `scoreboard.Pizarra`: si hay juegos vivos/finalizados en la jornada anterior después de medianoche, procesar esa fecha hasta que todos terminen. Cubrirlo con test de juego Costa Oeste cruzando medianoche.

**Razonamiento:** la métrica de jornada debe seguir la fecha oficial del juego, no el cambio de día del servidor.

### SAB-02 [P3] La documentación del modelo `DailyStandout` contradice la mezcla actual de bateo y pitcheo

**Evidencia:** el docstring del modelo dice que los valores de bateo y pitcheo “NO se comparan entre sí” y que por eso hay dos listas (`dglweb/stats/models.py:1689-1728` aprox.); el código actual sí los ordena juntos con `en_carreras()` (`dglweb/stats/daily.py:81-87`, `dglweb/stats/daily.py:311-312`, `dglweb/stats/daily.py:478`).

**Finding:** el comportamiento actual parece correcto y está razonado: Game Score se traduce a carreras sobre promedio. El problema es que una explicación vieja sigue viva en el modelo y puede inducir a un futuro cambio equivocado.

**Mejora sugerida:** actualizar el docstring para separar dos ideas: `valor` crudo no es comparable sin mirar `grupo`, pero la presentación sí usa `en_carreras()` para ordenar ambos oficios en una unidad común.

**Razonamiento:** en sabermetría, la unidad importa. Si el código normaliza bien pero la documentación dice lo contrario, el próximo maintainer puede “arreglar” lo que no está roto.

## Verificación

- Leídos los Markdown bajo `docs/`, incluyendo `TODO.md` y reviews anteriores.
- Inspección estática de vistas, modelos, comandos, scheduler, templates y JavaScript relacionados.
- No ejecuté suite de tests ni linters en este review.
- No modifiqué código fuente.
