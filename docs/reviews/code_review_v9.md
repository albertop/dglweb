# Code Review v9

Fecha: 2026-07-28  
Alcance: revisión de código sin cambios al código fuente. Antes de revisar se leyeron los `.md` bajo `docs/`, incluyendo `docs/TODO.md` y los reviews previos.

## Filtros aplicados

- No repito issues que ya aparecen en `docs/TODO.md` como pendientes.
- No marco los placeholders ni datos falsos de la página principal: el dueño confirmó que son un known issue de desarrollo.
- No repito hallazgos cerrados de reviews anteriores, como búsqueda/paginación de artículos, documentos públicos de Wagtail por decisión, CSP/vendor assets, detalle anónimo de `/health/pipeline`, categoría/fuente obligatoria, umbrales in-season y mejoras sabermétricas ya aparcadas.

## Resumen ejecutivo

Encontré 4 hallazgos nuevos:

1. [P2] `/ready` expone detalles operativos a cualquier visitante cuando falla.
2. [P2] La pizarra acumula listeners globales en cada refresco en vivo.
3. [P3] El formato de hora de la pizarra usa `%-I`, no portable a Windows.
4. [P3] Las tarjetas de artículos pueden hacer N+1 queries para imágenes y hashtags.

## Persona 1: Python Principal Developer

### DEV-01 [P2] La pizarra acumula closures sobre nodos reemplazados

**Evidencia:** `static/js/pizarra.js:117-122` reemplaza `actual.outerHTML` y llama `preparar(nuevo, false)`. Dentro de `preparar()`, `static/js/pizarra.js:197-199` registra un nuevo `document.addEventListener("click", ...)` que cierra sobre el `raiz` de esa versión del banner.

**Finding:** cada refresco en vivo deja vivo un listener global que referencia el banner anterior. En juegos live, el refresco corre cada minuto; una sesión larga acumula handlers y DOM retenido innecesariamente.

**Mejora sugerida:** registrar el listener global una sola vez y resolver el banner actual dentro del handler, o usar `AbortController`/cleanup antes de reemplazar el HTML. También se puede delegar todo en un contenedor estable.

**Razonamiento:** el bug no rompe la primera interacción, por eso es fácil pasarlo por alto, pero degrada con el tiempo y se vuelve más visible justo cuando hay más tráfico: juegos en vivo.

### DEV-02 [P3] `_detalle()` usa un formato de fecha no portable

**Evidencia:** `dglweb/stats/scoreboard.py:373-374` hace `timezone.localtime(momento).strftime("%-I:%M %p").lower()`.

**Finding:** `%-I` es un modificador típico de Unix/glibc. En Windows suele fallar o no comportarse igual. El proyecto se desarrolla en Windows y ese camino se ejecuta para juegos programados con `gameDate`.

**Mejora sugerida:** evitar modificadores dependientes de plataforma. Por ejemplo: formatear con `%I:%M %p`, quitar el cero inicial con Python (`lstrip("0")`) y normalizar `AM/PM` a la forma deseada. Agregar un test unitario de `_detalle()` para un juego programado.

**Razonamiento:** aunque producción corra en Linux, el código debe ser ejecutable en el entorno local del proyecto. Un fallo por formato de hora bloquea tests o debugging de la pizarra sin relación con el dominio.

### DEV-03 [P3] Las tarjetas de artículos pueden disparar N+1 queries

**Evidencia:** `dglweb/articles/models.py:178-182` hace `select_related("categoria")`, pero las tarjetas leen `articulo.imagen` y `articulo.hashtags.all` en `templates/articles/_tarjeta.html:15-25` y `:37-39`. La primera página además arma `recientes` con otra consulta en `dglweb/articles/models.py:245-247`.

**Finding:** cada tarjeta puede consultar su imagen/rendition y sus tags de forma individual. Hoy el índice pagina a 12, pero la página 1 puede renderizar índice + panel de recientes; el costo crece linealmente con los artículos visibles.

**Mejora sugerida:** prefetch/select de lo que la tarjeta necesita: `select_related("categoria", "imagen")` y `prefetch_related("hashtags")` donde aplique. Para renditions de Wagtail, considerar `prefetch_renditions()` si la versión instalada lo soporta, o medir con `CaptureQueriesContext` y fijar presupuesto.

**Razonamiento:** no es un problema de escala masiva, es de previsibilidad. Las páginas editoriales son públicas y cacheables; conviene que el número de queries dependa del layout esperado, no de llamadas ocultas por tarjeta.

## Persona 2: QA / Reliability Engineer

### QA-01 [P2] Refrescos live de la pizarra degradan la sesión del usuario

**Evidencia:** mismo flujo de `static/js/pizarra.js:117-122` y `:197-199`.

**Bug user-facing:** después de muchos minutos con juegos vivos, un clic fuera del banner ejecuta varios handlers viejos. El efecto visible puede ser latencia, cierres redundantes del detalle y memoria retenida en sesiones largas.

**Crash scenario:** no es un crash inmediato, pero sí un riesgo de degradación progresiva en móviles o laptops con recursos limitados.

**Mejora sugerida:** agregar test JS que simule dos refrescos reemplazando `#pizarra` y verifique que solo queda un handler global activo, o mover el cierre por click fuera de `preparar()`.

### QA-02 [P3] Falta cobertura para horario de juego programado en entorno Windows

**Evidencia:** `dglweb/stats/scoreboard.py:368-374`.

**Crash scenario:** un juego programado con `gameDate` puede romper el armado de la pizarra en Windows por `strftime("%-I")`.

**Mejora sugerida:** test unitario de `_detalle()` con un `gameDate` ISO y estado `PROGRAMADO`, ejecutable sin proxy. El fix debería ser puro Python para no depender del sistema operativo.

### QA-03 [P3] No hay presupuesto de queries para el índice de artículos

**Evidencia:** hay presupuesto de queries para perfil en `tests/test_profiles.py`, pero no un equivalente para `/articulos/`; la tarjeta lee relaciones no prefetchadas en `templates/articles/_tarjeta.html:15-39`.

**Riesgo:** regresiones de performance pueden entrar sin romper tests funcionales. La página seguirá respondiendo 200, pero con latencia creciente al sumar contenido real.

**Mejora sugerida:** agregar un test con 12 artículos, imágenes y hashtags, midiendo un máximo razonable de queries para `/articulos/`.

## Persona 3: Frontend Engineer

### FE-01 [P2] El handler global de cierre de pizarra no tiene ciclo de vida

**Evidencia:** `document.addEventListener("click", ...)` vive dentro de `preparar()` en `static/js/pizarra.js:197-199`; `preparar()` se llama en cada refresco desde `static/js/pizarra.js:122`.

**Broken UX path:** el componente es progressive-enhanced y bien trabajado para teclado/touch, pero el refresco live no desmonta el comportamiento anterior.

**Mejora sugerida:** inicializar el listener de documento una sola vez al cargar el módulo, o encapsular listeners de una instancia con `AbortController` y abortar antes de `outerHTML`.

**Razonamiento:** el estado visual actual pertenece al banner nuevo; listeners sobre banners viejos son estado zombie que complica mantenimiento y debugging.

## Persona 4: Security Engineer

### SEC-01 [P2] `/ready` filtra detalles internos sin autenticación

**Evidencia:** `dglweb/core/views.py:159-165` devuelve `{"detalle": "<Tipo>: <error>"}` para excepciones y lista hasta 20 migraciones pendientes. La ruta está registrada públicamente en `config/urls.py`.

**Attack scenario:** un atacante consulta `/ready` durante una caída o despliegue fallido y obtiene nombres de excepciones, mensajes de conexión, apps/migraciones pendientes y señales de estado del release.

**Exploitation method:** polling HTTP simple contra `/ready`; no requiere sesión ni token. Si la base falla, Django/driver puede incluir host, usuario, nombre de base o causa exacta. Si faltan migraciones, se exponen apps internas y ritmo de despliegue.

**Business impact:** facilita reconocimiento operativo y timing de ataques. También puede exponer detalles suficientes para ingeniería social o para encadenar vulnerabilidades conocidas de dependencias/apps.

**Recommended fix:** devolver públicamente solo `{"status": "error"}` con 503. Enviar el detalle a logs internos, o protegerlo con el mismo patrón de `/health/pipeline`: staff o `X-Monitor-Token`. Idealmente limitar `/ready` en el reverse proxy a la red interna del health checker.

**Razonamiento:** el semáforo público basta para un balanceador o monitor. El diagnóstico detallado es para operadores, no para Internet.

## Persona 5: Backend Architect

### ARCH-01 [P3] El índice de artículos todavía no tiene estrategia explícita de carga

**Evidencia:** `ArticleIndexPage.articulos()` solo optimiza `categoria` (`dglweb/articles/models.py:178-182`), mientras el partial compartido usa imagen y hashtags (`templates/articles/_tarjeta.html:15-39`).

**Scalability bottleneck:** el diseño editorial ya está paginado, pero la capa de datos no declara el contrato del componente tarjeta. Cuando el sitio tenga artículos semilla y luego archivo real, cada página puede sumar consultas por relación/rendition.

**Recommended fix:** definir un queryset "para tarjeta" reusable, por ejemplo `ArticlePage.cards_queryset()` o helper local, que centralice `select_related`, `prefetch_related` y cualquier prefetch de renditions. Usarlo en portada, índice, búsqueda y recientes.

**Razonamiento:** hoy portada e índice comparten template, pero no comparten una política de carga de datos. Esa asimetría es donde nacen los N+1.

### ARCH-02 [P2] `/ready` mezcla contrato externo con diagnóstico interno

**Evidencia:** `dglweb/core/views.py:123-167`.

**Single point likely to fail under load:** durante incidentes, `/ready` no se cachea y toca DB + grafo de migraciones por petición. Eso es correcto para un readiness interno, pero caro y revelador si queda público y alguien lo golpea.

**Recommended fix:** separar endpoint interno de readiness detallado y endpoint público mínimo, o mover el control de acceso al proxy. Mantener sin caché el endpoint interno, pero no hacerlo una superficie pública de diagnóstico.

## Persona 6: Experto en béisbol y sabermetría

### SAB-01 Sin hallazgos nuevos de concepto sabermétrico

**Revisión:** miré específicamente los cambios alrededor de umbrales prorrateados, `TeamSeasonGames`, traspasados (`XXX`/`XX`), postemporada, valores negativos en gráficos y autoridad dominicana.

**Resultado:** no encontré un falso entendimiento nuevo que no esté ya cubierto por código/tests/docs. En particular:

- El prorrateo por juegos respeta el criterio por equipo/liga y cae al máximo de liga/temporada para traspasados.
- Los umbrales propios de métricas de coeficientes se escalan preservando campo y operador.
- La postemporada usa pisos propios documentados en `docs/UMBRALES_POSTEMPORADA.md`.
- La autoridad dominicana sigue saliendo de `dgl_master`/`dom_players`, no de `birthCountry`.

**Sugerencia:** mantener este enfoque: cuando se agreguen WAR/wOBA/wRC+/ERA-/FIP- exactos, exigir una fuente/fórmula explícita por métrica y pruebas contra fixtures conocidos, porque ahí sí el riesgo sabermétrico sube.

## Notas positivas

- El review v8 está mayormente incorporado: pizarra accesible por teclado/touch, rich text filtrado contra `javascript:`, categorías/fuentes obligatorias, health del pipeline con detalle protegido y caché anónima.
- El motor de líderes tiene buena defensa contra muestras chicas, conteos "últimos", temporadas cortas y traspasados.
- La carga de CSV no escribe sin confirmación y revalida antes de aplicar; la deuda de staging fuera de sesión ya está en backlog, por eso no se repite.

