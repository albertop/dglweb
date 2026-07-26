# Code Review v6

Fecha: 2026-07-26
**Evaluado por el equipo el 2026-07-26.** Cada finding lleva abajo un bloque `> **Evaluación:**` con
el veredicto, verificado contra el código y contra la base real — no aceptado ni descartado de plano.
Lo aceptado está en `docs/TODO.md` con prioridad y fase; lo corregido dice qué se hizo.


Proyecto: `dglweb`  
Alcance: revisión de código y documentos bajo `/docs`, sin modificar código fuente.  

## Verificación Ejecutada

- Leídos los `.md` bajo `/docs`, incluyendo `TODO.md`, `DATOS_DE_APOYO.md`, `MOTOR_DATOS_APOYO.md`, `JUGADORES_DESHABILITADOS.md`, planes de fase, umbrales y reviews anteriores.
- `docker-compose run --rm --no-deps web ruff check .` -> OK.
- `docker-compose run --rm --no-deps web mypy .` -> OK.
- `docker-compose run --rm web pytest` -> OK: 587 passed, 52 warnings.

## Nota de Alcance

La página principal todavía está en etapa de desarrollo y contiene placeholders/contenido de maqueta. Por decisión del dueño, esos datos falsos del home son un known issue y quedan fuera de los findings de este review.

## Resumen Ejecutivo

El proyecto mejoró mucho desde v5: `only_visible()` ya protege líderes/totales materializados, el import del maestro no pisa `hidden`, el motor de datos de apoyo valida nombre/tamaño/encoding y la suite está amplia. Los riesgos principales que quedan no son de sintaxis: son de orquestación operacional, hardening, consistencia eventual y algunas asunciones de dominio.

Hallazgos más importantes:

- El scheduler sigue encadenado por horarios fijos, no por resultado de workflow.
- La reconstrucción derivada desde Backoffice corre en hilos daemon no durables.
- CDN sin SRI/CSP y Ofelia con `latest` + Docker socket siguen siendo riesgos de producción.
- Los umbrales de temporada viva siguen sin prorrateo por juegos disputados.

---

# Persona 1: Python Principal Developer

## DEV-01 [P2] `detect_debuts` usa `except Exception` y oculta errores de contrato

**Evidencia:** `dglweb/players/debuts.py:63-74`; estándar: `docs/CODING_STANDARDS.md:70`.  

**Finding:** `_detail()` captura cualquier `Exception` y devuelve un debut sin nombre. Eso degrada bien ante red/proxy, pero también puede ocultar bugs de programación, cambios de schema inesperados o errores de parsing.

**Sugerencia:** capturar explícitamente `MlbProxyError`, `IndexError`, `KeyError` y `TypeError`, registrar el error con `logger.warning`, y dejar que errores inesperados fallen en tests o en el run log. Mantiene la resiliencia del aviso sin convertir bugs reales en datos incompletos silenciosos.

> **Evaluación: ACEPTADO Y CORREGIDO.** Tiene razón, y además viola nuestro propio
> `CODING_STANDARDS.md`, que dice "Catch specific exceptions only". La intención era resiliencia, pero
> así también se tragaba un bug de contrato y lo convertía en un debut sin nombre: no falla nada, solo
> empeora el dato en silencio, que es la peor forma de enterarse. Ahora captura `MlbProxyError`,
> `IndexError`, `KeyError`, `TypeError` y `ValueError`, y loguea con `exc_info`.
>
> **De paso destapó un test flojo**: `test_a_failure_fetching_the_name_still_reports_the_debut`
> levantaba un `RuntimeError` pelado y pasaba solo porque se atrapaba cualquier cosa. Ahora usa
> `MlbProxyError`, que es lo que levanta el cliente de verdad, y hay un test nuevo que exige que un
> `AttributeError` —un bug nuestro— SÍ estalle.

## DEV-02 [P2] El upsert genérico del motor escala fila por fila

**Evidencia:** `dglweb/stats/staticdata/engine.py:259-271`.  

**Finding:** `apply()` usa `update_or_create()` por fila en modo UPSERT. Hoy `seasons_dates` es pequeño, pero el motor es genérico y `StaticDataset` permite registrar nuevos datasets. Si un dataset grande se configura como upsert, esto se vuelve N queries con transacción larga.

**Sugerencia:** soportar `bulk_create(update_conflicts=True, unique_fields=..., update_fields=...)` cuando el backend lo permita, o exigir que cada loader declare `max_expected_rows`/modo recomendado. La razón no es micro-optimización: evita que una configuración futura convierta una carga operativa en un cuello de botella o timeout.

> **Evaluación: DIFERIDO — se hace cuando exista el problema.** El diagnóstico es correcto: el
> `update_or_create` por fila es O(N) queries. Pero hoy hay **un** dataset en upsert con **70 filas**,
> y el cambio agrega una segunda rama de escritura que habría que probar en los dos caminos. Escribir
> un motor genérico para un tamaño que ningún dataset tiene es trabajo que envejece sin usarse.
>
> **El disparador es concreto**: el día que se registre un dataset en upsert con miles de filas, esto
> se hace antes de su primera carga. Ver ARCH-03, que pide lo mismo desde los metadatos.

---

# Persona 2: QA / Reliability Engineer

## QA-01 [P1] Scheduler por reloj permite pipelines diarios inconsistentes

**Evidencia:** `docker-compose.yml:71-94`; backlog reconocido en `docs/TODO.md:226`.  

**Finding:** batting, pitching, fielding, postemporada, career totals y leaders se encadenan por horario fijo. Si un job se retrasa, falla parcialmente o el proxy responde lento, el siguiente job corre igual y puede materializar líderes con mezcla de datos nuevos y viejos.

**Escenario usuario:** a las 7:30 corre `build_leaders` aunque `update_fielding_post` haya fallado o siga corriendo. El sitio queda verde en `/health`, pero muestra rankings inconsistentes.

**Sugerencia:** crear un comando orquestador diario que ejecute pasos secuenciales, valide `IngestRun` del paso anterior, aborte o marque `PARTIAL` si hay fallo, y solo reconstruya derivados cuando los insumos del día estén completos. Alternativamente, usar una cola/workflow con dependencias explícitas.

> **Evaluación: ACEPTADO, pero P2 y no P1.** El escenario es real y ya estaba anotado (QA-03 del
> v5, y el comentario del propio `docker-compose.yml`). Donde discrepo es en la gravedad: el rebuild
> es **completo, no incremental**, así que un día con datos mezclados se cura solo a la mañana
> siguiente sin que nadie intervenga. Eso no está al nivel de los P1 de seguridad, que no se curan
> solos. Va al TODO junto con ARCH-01, que es el mismo hallazgo desde la arquitectura.

## QA-02 [P1] Rebuilds en hilos daemon no son durables

**Evidencia:** `dglweb/stats/staticdata/views.py:130`, `dglweb/stats/staticdata/engine.py:288-290`, `dglweb/stats/rebuilds.py:46-60`.  

**Finding:** al confirmar una carga de apoyo, el dato se aplica y luego se lanza un `threading.Thread(..., daemon=True)`. Si el proceso web reinicia entre el commit y el fin del hilo, `build_career_totals`/`build_leaders` puede no terminar. El dato fuente queda nuevo, pero las tablas derivadas quedan viejas hasta el cron.

**Sugerencia:** persistir un job antes de arrancar, con estado visible y retry, o mover rebuilds a una cola/management command invocado por un worker. Como mínimo, crear una fila padre de `IngestRun`/`BackgroundJob` antes de lanzar el hilo y mostrar estado real en Backoffice.

> **Evaluación: ACEPTADO en su forma mínima, P2.** El hilo daemon fue decisión consciente y está
> documentada en `rebuilds.py`: no hay worker en este proyecto, la carga la dispara una persona que
> está mirando, y el cron de la mañana es la red de seguridad.
>
> El reviewer aporta algo que no estaba cubierto y es justo: **si el hilo muere antes de que el
> comando cree su `IngestRun`, no queda ninguna evidencia**. La ventana son milisegundos, pero el
> resultado sería una carga aplicada sin rastro de su rebuild. La fila padre creada ANTES de lanzar el
> hilo cierra eso y es barata. La cola con retry es rediseño y no entra antes del lanzamiento.

## QA-03 [P2] Staging de CSV en sesión puede crecer y quedar abandonado

**Evidencia:** `dglweb/stats/staticdata/views.py:101`, `dglweb/stats/staticdata/engine.py:124`.  

**Finding:** el CSV validado se guarda entero en sesión, hasta 20 MB por upload. Se elimina al confirmar, pero no al abandonar la pantalla. Con sesiones en DB, esto puede inflar la tabla de sesiones; con otro backend futuro, puede romper límites o mover datos operativos a un sitio no pensado para staging.

**Sugerencia:** usar una tabla/archivo temporal de staging con `uploaded_by`, `dataset_id`, `filename`, `sha256`, tamaño, expiración y estado. Confirmar por token de staging, no por CSV crudo en sesión.

> **Evaluación: YA EVALUADO Y DESPRIORIZADO.** Es el mismo hallazgo que ARCH-02 del v5, que el
> dueño bajó a prioridad muy baja el 2026-07-26 con su motivo en el TODO: el escenario exige dos
> administradores cargando a la vez, y hoy carga una sola persona una o dos veces al año. La parte
> urgente —un CSV enorme decodificado entero en memoria— se cerró en SEC-01 con el tope de 20 MB
> verificado antes de leer.
>
> **Nuevo respecto del v5**: nota que la sesión no se limpia al abandonar la pantalla. Es cierto, y lo
> resuelve solo el TTL de sesión de Django sin código nuestro.

---

# Persona 3: Frontend Engineer

## FE-01 [P2] CDN externo sin fallback degrada render y control de bundle

**Evidencia:** `templates/base.html:8-11`, `templates/base.html:83`.  

**Finding:** Bootstrap y fuentes dependen de Google/jsDelivr. Si CDN falla o es bloqueado por privacidad/red, la UI pierde estilos/interactividad.

**Sugerencia:** vendorizar Bootstrap y fuentes en `static/`, o al menos añadir SRI y fallback local. Esto también ayuda a CSP y rendimiento.

> **Evaluación: ACEPTADO, y ya estaba en Fase 8.** Mismo punto que SEC-02 desde el frente. Ver
> `TODO.md`, sección "Deferido a Fase 8": *"Vendorizar Bootstrap + fuentes (o al menos SRI)"*.

## FE-02 [P3] El buscador está bien encaminado, pero falta protección anti-regresión de accesibilidad completa

**Evidencia positiva:** `static/js/buscador.js:77-121` usa `textContent`/nodos, no `innerHTML` con datos del servidor; `templates/base.html:33-37` y `templates/profiles/players_index.html:25-32` tienen label/fallback de formulario.  

**Riesgo restante:** la cobertura actual valida ARIA base, pero no prueba navegación real con flechas/cierre/fila "ver todos".

**Sugerencia:** añadir tests browser-level o unitarios JS para ArrowUp/ArrowDown/Enter/Escape, y para que la fila "y N más" no reciba `role="option"`.

> **Evaluación: ACEPTADO, P3.** El riesgo es real y el reviewer reconoce lo que sí está cubierto.
> El costo no es escribir los tests sino **montar el corredor**: hoy no hay infraestructura de tests
> JS, y sumarla trae Node al gate, que hasta ahora es solo Python.
>
> Se verificó a mano en navegador (flechas, Escape, y que la fila "ver todos" no reciba foco). Va al
> TODO para cuando haya una segunda pieza de JS que lo justifique: con una sola, el corredor cuesta
> más que lo que protege.

---

# Persona 4: Security Engineer

## SEC-01 [P1] Ofelia usa imagen `latest` y acceso al Docker socket

**Evidencia:** `docker-compose.yml:100-108`.  

**Attack scenario:** un atacante compromete la imagen de scheduler, una dependencia de Ofelia o el contenedor por una vulnerabilidad runtime.  

**Exploitation method:** con `/var/run/docker.sock` montado, aunque sea `:ro` a nivel filesystem, el proceso puede hablar con el Docker API. En la práctica esto suele permitir inspeccionar contenedores, ejecutar comandos o pivotear hacia secretos/env del stack, según permisos del daemon. Además `mcuadros/ofelia:latest` permite cambios no revisados entre despliegues.  

**Business impact:** toma de control del stack, lectura de `MLB_PROXY_API_KEY`, modificación/borrado de datos, publicación de contenido falso o caída del sitio.  

**Recommended fix:** pinnear versión/digest, usar Docker socket proxy con endpoints mínimos, ejecutar scheduler con usuario/capabilities reducidas, auditar updates y considerar un cron/worker sin acceso directo al daemon. Si Ofelia se mantiene, documentar threat model y alertar cambios de digest.

## SEC-02 [P1] CDN sin SRI ni CSP

**Evidencia:** `templates/base.html:8-11`, `templates/base.html:83`; no hay CSP en `config/settings/prod.py`.  

**Attack scenario:** compromiso de CDN, manipulación de respuesta o dependencia externa inesperada.  

**Exploitation method:** Bootstrap JS o CSS externo modificado puede ejecutar o facilitar inyección en páginas públicas; si un admin navega autenticado, puede intentar robar sesión o inducir acciones en Backoffice.  

**Business impact:** desfiguración del sitio, robo de sesión, pérdida de confianza editorial y posible escalamiento sobre Wagtail/Django admin.  

**Recommended fix:** self-host de assets o SRI (`integrity` + `crossorigin`) con versiones pinneadas. Añadir CSP estricta (`default-src 'self'`, `script-src` con hashes/nonces, `style-src` controlado, `font-src 'self'`) y eliminar dependencias externas donde sea viable.

## SEC-03 [P2] La imagen/compose actual es de dev, no de producción

**Evidencia:** `Dockerfile:2-4`, `Dockerfile:11`, `Dockerfile:36`, `docker-compose.yml:28-30`; backlog en `docs/TODO.md:36-41`.  

**Attack scenario:** el mismo compose se usa por accidente en producción.  

**Exploitation method:** `runserver` y `config.settings.dev` quedan expuestos; falta `collectstatic` de prod/gunicorn y no hay `restart` policy para `web`.  

**Business impact:** menor resiliencia, exposición de configuración de desarrollo, handling deficiente de carga/concurrencia y caídas que no se recuperan solas.  

**Recommended fix:** crear Dockerfile/compose de producción separado: runtime deps, `config.settings.prod`, gunicorn/uvicorn según arquitectura, `collectstatic`, usuario no root, healthcheck DB-aware si aplica, `restart: unless-stopped`, límites de recursos y variables obligatorias fail-loud.

## SEC-04 [P2] Endpoint de sugerencias público sin rate limiting explícito

**Evidencia:** `dglweb/profiles/views.py:175-187`, `dglweb/players/search.py:79-117`.  

**Attack scenario:** actor automatiza requests a `/jugadores/buscar/?q=...`.  

**Exploitation method:** muchas consultas con `unaccent(Lower(full_name)) contains` disparan trabajo DB repetido. Hoy el maestro es pequeño, pero el patrón queda público y sin throttle.  

**Business impact:** degradación del sitio bajo abuso barato; ruido en logs y posible consumo innecesario de DB.  

**Recommended fix:** cachear resultados frecuentes, limitar longitud de `q`, añadir rate limit por IP/session en endpoints JSON públicos y considerar índice funcional si el volumen crece.

> **Evaluación: ACEPTADO A MEDIAS, P3.** El endpoint es público y sin throttle, cierto. Pero el
> costo por consulta es un `LIKE` sobre **984 filas** más tres agregados: un recorrido secuencial de
> una tabla que entra entera en memoria de Postgres. Como vector de abuso rinde muy poco, y el rate
> limiting real necesita middleware y almacén compartido, o sea infraestructura nueva.
>
> **Lo barato sí conviene y va al TODO**: topar el largo de `q`. El índice funcional no hace falta con
> este tamaño — lo pediría a partir de decenas de miles de filas.

---

# Persona 5: Backend Architect

## ARCH-01 [P1] El pipeline diario necesita una unidad transaccional/orquestada

**Evidencia:** `docker-compose.yml:71-94`; `dglweb/stats/runlog.py:45-81` registra runs individuales, no workflow completo.  

**Finding:** `IngestRun` da observabilidad por comando, pero no hay entidad "daily refresh 2026-07-26" que agrupe dependencias, estado final, abortos y retries. Los derivados se reconstruyen aunque una etapa upstream falle si el reloj llega.

**Sugerencia:** crear `PipelineRun` o un command `refresh_daily` con pasos, locks, estado agregado y política de retry. `build_career_totals` y `build_leaders` deberían depender de que batting/pitching/fielding/post jobs del scope estén `SUCCESS` o de una decisión explícita de publicar parcial.

> **Evaluación: ACEPTADO, P2 — es QA-01 desde la arquitectura.** Se trata como un solo pendiente
> en el TODO para no partirlo en dos entradas que se pisan. El `refresh_daily` con estado agregado es
> la forma correcta, y la puerta de temporada agregada hoy ya mostró que concentrar una decisión en un
> solo lugar funciona mejor que repartirla entre diez horarios.

## ARCH-02 [P1] Los rebuilds derivados son consistencia eventual sin contrato operativo fuerte

**Evidencia:** `dglweb/stats/rebuilds.py:46-60`, `templates/staticdata/done.html:7-12`.  

**Finding:** la pantalla dice que el rebuild arrancó y que quedará en log, pero no hay ID de job ni estado que el usuario pueda seguir desde esa operación. Si el hilo muere antes de crear `IngestRun`, no queda evidencia.

**Sugerencia:** modelar rebuilds como jobs persistidos. Mostrar "pendiente/en curso/éxito/falló" ligado a la carga de apoyo. Esto elimina la zona gris entre dato fuente aplicado y derivado publicado.

> **Evaluación: mismo pendiente que QA-02**, donde está la evaluación completa.

## ARCH-03 [P2] `StaticDataset` es extensible, pero no fuerza políticas por tamaño/modo

**Evidencia:** `dglweb/stats/models.py:1299-1394`, `dglweb/stats/staticdata/engine.py:259-271`.  

**Finding:** la arquitectura permite sumar datasets creando filas y loaders, pero la seguridad/performance del modo depende de convenciones. Un loader grande en `UPSERT` hereda el path fila-por-fila.

**Sugerencia:** extender `Loader` con metadatos: `expected_max_rows`, `supports_bulk_upsert`, `staging_required`, `requires_rebuilds`. `StaticDataset.clean()` debería validar esos contratos, no solo loader/clave/constraint.

> **Evaluación: DIFERIDO, igual que DEV-02.** `requires_rebuilds` **ya existe** como
> `Loader.rebuilds` (ARCH-01 del v5). Los otros tres describen políticas para datasets que no existen,
> y cada metadato nuevo es una cosa más que `clean()` valida, un caso más que probar y una decisión
> más al agregar una tabla — hoy agregar un dataset son tres atributos y funciona.
>
> **Se revisa cuando entre el segundo dataset en upsert**: ahí habrá dos casos que comparar y el
> diseño saldrá del uso en vez de la especulación.

## ARCH-04 [P2] `/health` no valida dependencias críticas

**Evidencia:** `dglweb/core/views.py:7-10`; `docker-compose.yml:45-49`.  

**Finding:** el healthcheck solo verifica que el proceso responde. Es correcto como liveness, pero no sirve como readiness: DB caída, migraciones pendientes o Wagtail roto podrían pasar `/health`.

**Sugerencia:** mantener `/health` liviano para liveness y añadir `/ready` o un management check para readiness con DB y migraciones. En producción, el reverse proxy/deploy debería usar readiness para sacar instancias del pool.

> **Evaluación: ACEPTADO, P3, junto con Fase 8.** La distinción liveness/readiness es correcta, y
> el reviewer reconoce que `/health` está bien como está — su docstring ya explica que **no toca la DB
> a propósito**, para que un parpadeo de Postgres no mate un proceso web sano.
>
> Lo que falta es el `/ready`, y hoy **no hay nada que lo consuma**: no hay orquestador ni pool de
> instancias, y el healthcheck del compose es de liveness. Se construye junto con el compose de
> producción, no antes: un endpoint de readiness que nadie consulta es solo código.

---

# Persona 6: Experto en Beisbol y Sabermetría

## SAB-01 [P2] Umbrales de temporada viva siguen usando cortes de temporada completa

**Evidencia:** defaults en `dglweb/stats/management/commands/seed_metrics.py:335-336`; resolución estática en `dglweb/stats/qualifier.py:35-42`; backlog en `docs/MEJORAS_FUTURAS.md:33-36`.  

**Finding:** las tasas de temporada usan umbrales como `PA>=502` e `IP>=162`, salvo overrides de temporadas cortas históricas. En una temporada viva, eso sub-publica líderes de tasa durante buena parte del año o fuerza a no mostrar boards útiles hasta que se alcancen cortes de temporada completa.

**False assumption:** que el qualifier oficial de fin de año se puede aplicar igual en julio. Para leaderboards in-season se suele prorratear por juegos del equipo/liga ya disputados.

**Sugerencia:** introducir tabla `games` o `season_progress` y resolver qualifiers dinámicos para la temporada activa: `PA >= 3.1 * team_games` e `IP >= 1.0 * team_games` para rate boards de temporada. Mostrar el umbral efectivo en UI.

> **Evaluación: ACEPTADO, ya conocido, y ahora más cerca de poder hacerse.** Está en
> `MEJORAS_FUTURAS.md` y como SAB-03 del v5. Aporta las fórmulas concretas —3,1 PA y 1,0 IP por juego
> de equipo, que son las de MLB— y eso ahorra volver a investigarlas.
>
> **Lo que cambió hoy**: `seasons_dates` ya está cargada. Aun así el prorrateo correcto es por **juegos
> disputados** y no por días transcurridos, porque los equipos no juegan todos los días ni al mismo
> ritmo — así que sigue haciendo falta el conteo de juegos, no solo el calendario.

## SAB-02 [P2] Detección de debuts puede perder casos sin bateo/pitcheo

**Evidencia:** `dglweb/players/debuts.py:21-26`.  

**Finding:** `detect_debuts` busca candidatos con stats en grupos `hitting` y `pitching`. El comentario asume que "para tener estadísticas hay que batear o lanzar" y que un caso solo de fildeo prácticamente no ocurre. En MLB un debut puede darse como reemplazo defensivo o corredor emergente sin PA ni pitcheo.

**False assumption:** que toda aparición MLB detectable para debut produce línea de bateo o pitcheo. Si StatsAPI no incluye a un defensor con 0 PA dentro de `hitting`, el debut no se reporta hasta que tenga PA o lance.

**Sugerencia:** añadir `fielding` al barrido de debut o crear un test con un prospecto que solo aparece en fielding. El costo es una llamada bulk adicional y evita perder el primer día de Grandes Ligas de un jugador.

> **Evaluación: ACEPTADO Y CORREGIDO — el mejor hallazgo del review.** Detecta una **incoherencia
> con una decisión ya tomada por el dueño**: cuando pidió incluir fildeo en la lista de "vieron acción"
> del índice de jugadores, su motivo fue exactamente este ("un debutante puede tener acción solo como
> pinch runner o como defensa"). El principio se aplicó allí y no acá. `detect_debuts` ya barre los
> tres oficios, con test.
>
> **Matiz que el reviewer no midió y conviene registrar**: hoy el impacto es CERO. De los 1.323
> jugadores con fildeo en 2026, **ninguno** carece de bateo o pitcheo, porque la API emite línea de
> bateo para cualquiera que aparezca en un juego. No se están perdiendo debuts ahora mismo — lo que se
> compra es no depender de que esa costumbre de la API siga cumpliéndose.

## SAB-03 [P2] Salarios está bien deshabilitado; mantenerlo así hasta que la cobertura sea confiable

**Evidencia:** `dglweb/profiles/tabs.py:930-962`, `templates/profiles/tabs/salarios.html:45`.  

**Finding positivo:** el tab de salarios está implementado y probado, pero fuera de `REGISTRY` porque la fuente no cubre jugadores/temporadas claves. Esa es la decisión correcta: una tabla parcial se leería como historial completo.

**Sugerencia:** antes de activar, exigir métricas de cobertura por temporada y reconciliación contra una fuente salarial confiable. En la UI, si se activa, rotular "salarios conocidos en DGL" y no "salarios de carrera".

> **Evaluación: DE ACUERDO, sin acción.** Confirma la decisión ya tomada. La sugerencia de rotular
> *"salarios conocidos en DGL"* al reactivarlo es buena y queda anotada en el pendiente del TODO.

## SAB-04 [P2] Prorratear sabermetría de carrera sin fórmula exacta debe seguir marcado como aproximación

**Evidencia:** `dglweb/stats/career_rate.py:1-8`, `docs/MEJORAS_FUTURAS.md:38-42`.  

**Finding:** el motor diferencia tasas exactas vs prorrateadas. Esto es razonable, pero métricas como wOBA, wRC+, ERA-, FIP- o índices dependientes de contexto de liga/año pueden requerir contexto anual para una carrera exacta.

**Sugerencia:** mantener notas visibles donde aplique y priorizar import/contexto de liga si esas métricas van a aparecer como "de por vida". Un promedio ponderado es útil, pero no debe presentarse como recomputación oficial de carrera.

> **Evaluación: ACEPTADO, ya conocido.** Está en `MEJORAS_FUTURAS.md`. El motor ya separa tasas
> exactas de prorrateadas y el perfil lo marca; lo que falta es el contexto de liga por año para las
> que dependen de él (wOBA, wRC+, ERA-, FIP-). No cambia nada hoy ni bloquea el lanzamiento.

---

# Backlog Recomendado Priorizado

1. Reemplazar scheduler por workflow/orquestador diario con dependencias y estado agregado.
2. Convertir rebuilds de Backoffice en jobs persistidos con retry/status.
3. Hardening prod: Dockerfile/compose prod, SRI/CSP o self-host de assets, Ofelia pinneada y sin socket amplio.
4. Implementar prorrateo de qualifiers para temporada viva con tabla de juegos.
5. Cambiar staging de CSV desde sesión hacia staging persistido con hash/expiración.
6. Cubrir debut defensivo-only/pinch-runner-only en `detect_debuts`.
