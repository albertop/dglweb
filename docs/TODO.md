# TODO — dglweb

Lista de pendientes que van surgiendo sobre la marcha. (Ítems de decisión / afinado, no el
roadmap de fases — eso está en `BUILD_PLAN.md`.)

## Hecho: tab de Fildeo

**Construido y en producción.** `FieldingTab` está en el registro con su `_fielding_context` propio
—que fue lo único que necesitó código nuevo, porque `_group_context` no le servía: las líneas de
fildeo son por POSICIÓN y no por stint—, cinco pills (Estándar, Avanzado, Receptor, Postemporada,
Totales) y cuatro archivos de test.

Esta sección decía "Próximo" mucho después de que el tab existiera. Vale la pena anotar por qué:
un TODO que describe trabajo ya hecho es peor que uno incompleto, porque se lee como si fuera cierto
y guía decisiones. Pasó: al preguntar "¿qué queda pendiente?" recomendé priorizar deuda técnica
"antes de Fildeo" — que ya había pasado.

## Diseño / branding

- [x] ~~Definir el subtítulo del brand~~ → **descartado**: se quita, es redundante con el nombre.
- [ ] Afinar el tamaño del brand en móvil (el nombre completo se recorta un poco a 375px).

## Contenido

- [ ] Escribir los 8–12 artículos semilla (cuello de botella — empezar temprano, en paralelo).

## Deferido a Fase 8 (hardening de prod) — de code review

- [ ] **Imagen prod separada:** Dockerfile de producción con `collectstatic` en el build, solo
  deps de runtime, `config.settings.prod` por defecto, gunicorn, y fallo-ruidoso si faltan
  secretos. (El manifest storage de prod requiere `collectstatic`, que hoy no corre en el build.)
- [ ] **Vendorizar Bootstrap + fuentes** (o al menos SRI): hoy vienen de CDN sin `integrity`.
  Self-host mejora resiliencia (Principio #0), privacidad y prepara CSP.
- [ ] **`restart` policy** del contenedor web en el compose de prod.

## Templates — cuando existan las páginas (Fases 4–5)

- [x] ~~Nav (Artículos/Líderes/Jugadores/Entrar) y buscador apuntan a `#`/submit desactivado.~~
  **Hecho en FE-01**: escondidos hasta que las páginas existan, con el markup preservado en comentarios.

## Code review v3 — findings

Medidos, no asumidos. Ver `docs/reviews/code_review_v3.md`.

- [x] **DEV-02 — `backfill_batting_rates` sin cobertura.** Verificado: 0%, el módulo ni se importaba
  en la suite. Es una herramienta de escritura masiva sobre las tablas de stats. **Corregido.**
- [x] **DEV-04 — los filtros numéricos revientan con texto.** Reproducido: `rate`, `dec`, `pct` e
  `innings` lanzan `ValueError` con `"N/A"` → 500 en una página pública. **Corregido** (fail-soft en
  render, fail-loud sigue en ingest).
- [x] **SAB-03 — mejor marca personal sobre métricas descriptivas.** GB%, FB%, LD% y GB/FB no tienen
  "mejor": un extremo solo dice que cambió el perfil. **Corregido**: no se resaltan.
- [ ] **DEV-01 — todos los tabs se calculan en cada request.** Cierto, pero **la magnitud del finding
  está sobrestimada**: medido son 25 queries / 415 ms para Pedro Martínez (dos tabs completos) contra
  16 / 221 ms para Ortiz (uno). El segundo tab cuesta 9 queries, no cientos, y ~340 ms de esos 415
  son latencia de red contra 10.0.0.39. No es urgente, pero cada tab nuevo cobra impuesto: con Fildeo
  real y luego Splits/Game Logs sí se nota. Agregado un test de presupuesto de queries para que no
  crezca en silencio; la carga diferida (HTMX o endpoints por tab) queda pendiente.
- [x] **DEV-03 — las tablas repiten listas de columnas a mano.** **Corregido** con el refactor declarativo que el propio finding proponía: `profiles/columns.py` define `Column(label, attr, fmt)` y las listas por división, y las plantillas rinden con partials comunes (`{% include "profiles/_season_head.html" with cols=… %}`). Hoy quedan CERO `<th>` escritos a mano en las tablas de bateo, pitcheo, fildeo y puestos. Fildeo se construyó ya sobre esto, que era justamente el plazo que el finding se ponía.
  ~~ Real y ya lo sufrimos: cada columna
  agregada (LOB, TotAvg, BsR, G, AB) obligó a editar encabezado + fila + total en varios bloques, y
  las desalineaciones solo se detectaron con un script ad-hoc. **Conviene resolverlo ANTES de Fildeo**,
  que sería la tercera copia del patrón. Propuesta: mover las columnas a una lista declarativa en
  Python `(label, attr, formato, clase)` y renderizar con un partial común.
- [x] **SAB-02 — boards descriptivos etiquetados como "mejor/peor".** **Corregido** al construir Líderes: las métricas de `DESCRIPTIVE_COLUMNS` rotulan sus dos tablas «Los más altos» / «Los más bajos» en vez de primeros/últimos, y el tooltip del signo en Puestos dice «ordena de más alto a más bajo (perfil, no mejor/peor)».
  ~~ GB%, FB%, LD% y GB/FB se
  rankean, pero llamarlos "mejor" implica un valor competitivo que no tienen. La corrección natural
  es de etiquetas ("Más alto / Más bajo") y vive en la UI de líderes, que **todavía no existe**
  (Fase 5). Cuando se construya, usar la misma marca de métrica descriptiva que ya usa SAB-03.
- [ ] **SAB-01 — la cobertura Statcast se decide por año, no por completitud.** El reviewer llegó de
  forma independiente al hueco de 2000-2001 que ya está documentado en `MEJORAS_FUTURAS.md`. Decisión
  del dueño: dejarlo así por ahora. Su sugerencia extra —advertirlo en la UI, no solo en el backlog—
  sigue disponible y es barata.

## Incidente — el scheduler llevaba días sin correr (2026-07-26)

**Encontrado por accidente**, midiendo duraciones de jobs para evaluar QA-01 del review v6: los
`update_*` no tenían **ni una sola** corrida en `IngestRun`. El log de Ofelia lo confirmó:

```
27 corridas fallidas · 1 exitosa
error creating exec: No such container: dglweb-web-run-9eeececf11da
```

**Causa raíz.** Los jobs vivían como `labels` del servicio `web` y Ofelia los descubría por el socket
de Docker. Pero **`docker compose run` clona las etiquetas del servicio**: cada comando suelto creaba
un contenedor efímero con `ofelia.enabled=true`, Ofelia se re-apuntaba a él, el contenedor moría con
`--rm`, y desde ahí todos los jobs fallaban para siempre. Verificado en vivo antes y después del
arreglo.

**Lo que lo hizo invisible.** `IngestRun` existe para que un fallo silencioso sea una fila roja en el
Backoffice — pero **no puede registrar un job que nunca llegó a arrancar**. El log se veía limpio
porque no había nada que registrar. Los datos estaban al día solo porque los `import_*` se corrieron
a mano.

**Corregido**: el calendario salió a `ofelia/config.ini`, apuntando por **nombre de contenedor** en
vez de por etiqueta, y el scheduler arranca con `--config` en lugar de `--docker`. Un contenedor
efímero ya no puede robarle el objetivo (comprobado: los `-run-` ahora nacen sin la etiqueta).
Verificado que registra los 11 jobs y que el `exec` por nombre ejecuta el comando.
De paso la imagen de Ofelia queda pinneada por digest — es el contenedor con el socket de Docker
montado, o sea donde menos conviene una actualización sorpresa (parte de SEC-01 del v6).

### Pendiente de este incidente

- [x] **Recrear el servicio `web` para que tome el `container_name`.** **Hecho**: el huérfano era un `cd458e3c94dd_dglweb-web-live` en estado *Created* que nunca arrancó (el `dglweb-web-1` ya se había ido solo). Se borró y se levantó `web` desde compose. Ahora lo gestiona compose, sin etiqueta de Ofelia y con el volumen `dglweb_uploads` montado. **Y destapó otra cosa**: el contenedor viejo apuntaba a la base real por una variable puesta a mano, así que al recrear el sitio se fue a la base local. `DATABASE_URL` ahora sale de `.env`.
  ~~ El compose ahora fija
  `container_name: dglweb-web-live`, que es el nombre al que apunta el scheduler. Hoy el contenedor
  que sirve YA se llama así, pero quedó además un `dglweb-web-1` **parado desde hace dos días** que
  bloquea la recreación por conflicto de nombre. Hay que borrar ese contenedor muerto y levantar de
  nuevo — es cosa de una vez, y sin eso un `docker compose up -d web` futuro fallaría.
- [ ] **Vigilar que el scheduler se note cuando falla.** Este incidente duró días sin señal. Una
  alerta barata: si `IngestRun` no tiene ninguna corrida de `update_batting` en las últimas 48 horas
  dentro de temporada, algo está roto. Encaja natural en el orquestador de QA-01+ARCH-01.

## Code review v6 — findings (2026-07-26)

Ver `docs/reviews/code_review_v6.md`, donde cada finding lleva la evaluación completa. Acá va solo lo
**aceptado**, con su prioridad. Lo diferido y lo ya conocido se justifica allá y no se duplica acá.

### Corregidos en el momento

- [x] **SAB-02 — la detección de debuts no miraba fildeo.** **Corregido**: `detect_debuts` barre los
  tres oficios. Era una incoherencia con una decisión ya tomada — el dueño había pedido incluir
  fildeo en la lista de "vieron acción" del índice por este mismo motivo, y el principio no se había
  aplicado acá. **Impacto medido hoy: cero** — de los 1.323 jugadores con fildeo en 2026, ninguno
  carece de bateo o pitcheo, porque la API emite línea de bateo para cualquiera que aparezca. Lo que
  se compra es no depender de esa costumbre de la API.
- [x] **DEV-01 — `except Exception` en `debuts._detail()`.** **Corregido**: captura los tipos
  concretos y loguea con `exc_info`. Violaba `CODING_STANDARDS.md` y convertía un bug de contrato en
  un debut sin nombre, que es la peor forma de enterarse: no falla nada, solo empeora el dato. De
  paso destapó un test que pasaba solo porque se atrapaba cualquier cosa.

### P2 — antes de que el sitio dependa de que el pipeline no falle

- [ ] **QA-01 + ARCH-01 — el pipeline diario necesita un orquestador, no diez horarios.** Un solo
  pendiente porque son el mismo hallazgo desde QA y desde arquitectura, y ya venía del v5 (QA-03).
  Hoy `build_leaders` corre a las 7:30 aunque `update_fielding_post` haya fallado, y publica
  liderazgos con mezcla de dato nuevo y viejo sin que `/health` se entere. **Forma**: un comando
  `refresh_daily` con pasos, estado agregado y una decisión explícita de publicar parcial, en vez de
  encadenar por reloj.
  **Por qué P2 y no P1**: el rebuild es completo y no incremental, así que un día malo se cura solo a
  la mañana siguiente. Es un problema de calidad de dato temporal, no de integridad permanente.
- [ ] **QA-02 + ARCH-02 — el rebuild de Backoffice puede no dejar rastro.** El hilo daemon fue
  decisión consciente (ver `rebuilds.py`) y el cron de la mañana es su red de seguridad. Pero hay una
  ventana real que no estaba cubierta: **si el hilo muere antes de que el comando cree su
  `IngestRun`, la carga queda aplicada sin ninguna evidencia de su rebuild**. Son milisegundos, pero
  el resultado es indistinguible de "nunca se lanzó".
  **Forma mínima aceptada**: crear la fila padre ANTES de lanzar el hilo y mostrar su estado en la
  pantalla de carga. La cola con retry es rediseño y no entra antes del lanzamiento.

### P3 — cuando haya qué lo justifique

- [ ] **SEC-04 (parcial) — topar el largo de `q` en el buscador.** Una línea, evita que alguien mande
  una consulta de un megabyte al endpoint público. El rate limiting completo NO se acepta por ahora:
  el costo por consulta es un `LIKE` sobre 984 filas, así que como vector de abuso rinde muy poco, y
  el throttle real necesita middleware y almacén compartido.
- [ ] **FE-02 — tests de teclado del buscador (flechas, Enter, Escape, la fila "ver todos").** El
  riesgo es real; el costo no son los tests sino **montar el corredor**, que trae Node a un gate que
  hoy es solo Python. Se verificó a mano en navegador. Vale la pena cuando exista una segunda pieza
  de JS: con una sola, el corredor cuesta más que lo que protege.
- [ ] **ARCH-04 — falta un `/ready` que valide DB y migraciones.** `/health` está bien como está: no
  toca la DB **a propósito**, para que un parpadeo de Postgres no mate un proceso web sano. Lo que
  falta es el readiness, y hoy **nadie lo consumiría** — no hay orquestador ni pool de instancias.
  **Va con Fase 8**, junto al compose de producción: un endpoint de readiness que nadie consulta es
  solo código.

### Diferidos con disparador explícito

- [ ] **DEV-02 + ARCH-03 — upsert fila por fila y metadatos de política en el `Loader`.** El
  diagnóstico es correcto, pero hoy hay **un** dataset en upsert con **70 filas**. **Disparador: el
  segundo dataset en upsert, o el primero con miles de filas** — ahí se hace antes de su primera
  carga, y con dos casos reales que comparar el diseño sale del uso y no de la especulación.

## Por decidir (traído del CONCEPT)

- [ ] Proveedor de ad server hosted (GAM vs AdButler/Broadstreet/AdSpeed).
- [ ] Listado exacto de métricas sabermétricas por página de jugador.
- [ ] Redactar legal: privacidad + consentimiento de cookies + ToS.
- [ ] Dónde/ cuándo se activa el muro de registro (post-launch).

## Code review v4 — findings (2026-07-24)

Ver `docs/reviews/code_review_v4.md`. Evaluados uno a uno; mi acuerdo/decisión:

- [x] **DEV-01 — `mypy .` no estaba verde.** De acuerdo, real: el gate corría `mypy dglweb`
  (78 archivos) y no veía los tests. `mypy .` fallaba en `tests/test_profiles.py` (`_flat`
  iterando `object`). **Corregido** (helpers de test tipados con `Any`). **El gate ahora corre
  `mypy .`, no `mypy dglweb`.**
- [x] **SAB-01 — Puestos llamaba "mejor" a métricas descriptivas.** De acuerdo. GB%/FB%/LD%/GB-FB
  no tienen dirección deportiva. **Corregido**: el tooltip del signo dice "ordena de más alto a más
  bajo (perfil, no mejor/peor)" para descriptivas (misma regla SAB-02 que ya usa Líderes).
- [x] **SAB-04 — fildeo de postemporada sin explicación.** De acuerdo, barato. **Corregido**: nota
  en el caption ("registro descriptivo; no participa en liderazgos por ahora").
- [x] **DEV-03 (parcial) — comentario/label de `Metric.postseason` decía "reservado".** Ya no lo es.
  **Corregido** el label y el comentario (migración 0013).
- [x] **DEV-02 — liderazgo de postemporada de UNA sola ronda no se pintaba como líder de temporada.**
  El dueño eligió la **opción A**: una fila `line` que es la única de su temporada ES el agregado de
  todo su octubre, así que lleva el badge (nunca una ronda *parcial* de un octubre de varias).
  **Corregido** el overlay + comentarios contradictorios. Con test. Validado: Felipe Alou 1962 (SM de
  una ronda) ahora marca sus liderazgos. Cambio de UI, no toca el motor ni requiere rebuild.
- [x] **DEV-03 (gating) — los boards de octubre ignoran `best_season`/`best_career`.** **Corregido**:
  `_postseason_leaders` / `_postseason_rate_leaders` gatean el board de carrera por `best_career` y el
  de temporada por `best_season`; los predicados `_wants_postseason*` saltan si no se quiere ninguno.
  Con test. (No hubo que reconstruir: 0 métricas de octubre tenían un flag apagado.)
- [x] **DEV-04 — `_innings_to_outs` acepta fracciones imposibles (.3, .9, .25).** **Corregido**:
  la fracción solo puede ser vacío/0/1/2; cualquier otra cosa (`.3`, `.9`, `.25`, basura, doble punto)
  retorna `None` en vez de un outs plausible-pero-falso. Fail-soft en ingest → sale como disparidad en
  paridad. Tests para `.3`/`.9`/`.25`/`abc`/`111.1.2`. (No re-ingesté: la fuente manda notación válida;
  si algún día se re-ingesta fildeo, un valor malo pasaría a NULL y saltaría en paridad.)
- [ ] **DEV-05 — todos los tabs se calculan por request.** Ya conocido (v3 DEV-01). Carga diferida
  (HTMX/endpoints por tab) sigue pendiente; el test de presupuesto de queries es el guardarrail.
- [x] **SAB-02 — panel de receptor sin CS%.** **Corregido**: columna **CS%** (property `cs_pct` en
  `Fielding`/`FieldingCareer`, `CS/(SB+CS)`, recomputada de los conteos de la fila; None sin intentos).
  Caption aclara que CS% normaliza el volumen crudo y que cERA es contexto (depende del staff), no una
  evaluación defensiva fuerte. Validado: Tony Peña carrera 34.9 %.
- [x] **SAB-03 — cobertura Statcast es piso por año, no por métrica (hueco 2000-2001).**
  **Resuelto, pero no como proponía el finding.** La salida no fue "cobertura por métrica" sino
  **traer el dato que faltaba**: Retrosheet tenía la trayectoria de esos años con 97% de cobertura,
  o sea que el hueco era de nuestra fuente y no del registro histórico. Cargado por la Fase 4e
  (`docs/DATOS_DE_APOYO.md`), 2000 pasó de 1,8% a 97,3%, 2001 de 2,2% a 97,6% y 2002 de 86,5% a
  98,2%. Sammy Sosa 2000 pasó de que sus coeficientes sumaran 55,9% a sumar 97,3%, y su LD% de .036
  a .218. La advertencia de la UI bajó de diez temporadas a siete.
  **Residuo, separado abajo**: la advertencia sigue siendo por año.
- [ ] **SAB-03b — la advertencia marca el panel entero cuando solo los hits están incompletos.**
  Ojo con la redacción: en las siete temporadas que quedan (1989-90, 1993-97) **el dato ya se trajo**
  — la carga de Retrosheet cubrió las diez, no solo 2000-2002. Lo que pasa es que ahí Retrosheet
  tampoco clasificó todo: en 1990 registra los 2.575 hits pero solo le puso trayectoria a 2.314. Ese
  10% no lo anotó nadie en 1990; es el techo del registro histórico, no algo por hacer.
  Lo que sí queda pendiente es de precisión en la UI: los cinco conteos de OUTS por tipo
  (AO/GO/FO/PO/LO) están completos en esos años, y hoy se advierte sobre el panel Statcast entero
  como si estuvieran todos afectados. Un piso por (métrica, temporada) lo diría con exactitud.
  **Prioridad baja**: la advertencia sobra en cinco columnas de doce, pero no miente.
- [x] **DEV-02 / FE-03 — `leaders_context()` revienta con la base vacía.** **Corregido**: `_empty_context()` devuelve un contexto renderizable y la plantilla tiene su rama para base vacía. Con test.
  ~~ **Reproducido**:
  `IndexError: list index out of range` en `division_labels[0]`. Pasa en staging limpio, base recién
  migrada, o si alguien desactiva las métricas de un grupo desde el Backoffice. Es el más grave
  porque tumba una página pública entera, no un caso de borde. Falta un contexto vacío renderizable.
- [x] **QA-01 / SAB-04 — las filas con `mlb_id` desconocido se descartan en silencio.** **Corregido**: se separa «sin mlb_id» (se descarta) de «mlb_id que no está en el maestro» (se acumula en `_huerfanas` y se reporta con conteo, hits perdidos y muestra de ids).
  ~~ Real, y el
  reviewer ve algo que a mí se me pasó: las descartadas **tampoco entran en los totales de cobertura**,
  así que un maestro incompleto hace que el CSV parezca MÁS sano de lo que está. La validación se
  autoengaña. Hay que separar "sin mlb_id" de "mlb_id que no existe en el maestro" y reportar el
  segundo con conteo y muestra.
- [x] **SAB-01 — la cobertura se valida por temporada, no por (temporada, oficio).** **Corregido**: la clave del acumulador es `(season, stat_group)`, así que un oficio roto ya no se esconde tras el otro completo.
  ~~ Verificado:
  `por_temporada.setdefault(row["season"], ...)` mezcla bateo y pitcheo. Si un oficio viene completo
  y el otro roto, el promedio pasa el 80% y el roto entra igual. Error mío al escribir `checks()`.
- [x] **ARCH-01 — cargar datos de apoyo no reconstruye lo que depende de ellos.** **Corregido**: el `Loader` declara `rebuilds = ("build_career_totals", "build_leaders")` y la vista los dispara sola al confirmar. Corren fuera de la transacción (son reintentables, y no hay por qué bloquear la tabla de origen un minuto) y en un hilo (si no, la respuesta HTTP espera el minuto que tarda `build_leaders`, que es justo lo que un proxy corta a los 30s). Quedan en `IngestRun` como cualquier corrida del scheduler. Documentado en `MOTOR_DATOS_APOYO.md`.
  ~~ Real y ya lo
  vivimos: tras la carga hubo que correr `build_leaders` a mano, y hasta que se corrió las páginas
  servían coeficientes viejos. `BattingCareer`/`PitchingCareer` tampoco se rehacen.
- [x] **SEC-01 — subida de CSV sin límite de tamaño.** **Corregido**: tope de 20 MB (el CSV real pesa ~250 KB) y rechazo por extensión, verificados ANTES de leer — no se decodifica en memoria algo que no se va a aplicar. El staging fuera de sesión sigue pendiente en ARCH-02.
  ~~ Verificado: no hay `DATA_UPLOAD_MAX_*` en
  settings, y el CSV entero se guarda en sesión. Aunque exige cuenta admin, un archivo grande tumba
  el proceso. Límite por dataset + rechazo por extensión + staging con TTL en vez de sesión.
- [x] **QA-04 — el nombre de archivo equivocado avisa pero deja confirmar.** **Corregido**: ahora es un `Problem` bloqueante. Un archivo bien nombrado es trivial de conseguir; una tabla reemplazada con el dataset equivocado, no.
  ~~ De acuerdo, y es
  incoherente con lo que yo mismo escribí en `DATOS_DE_APOYO.md`: que el chequeo existe para atajar
  cargar el CSV de salarios sobre la tabla de transacciones. Si solo avisa, no ataja nada.
- [x] **DEV-01 — 500 por `pk` inexistente o CSV no UTF-8.** **Corregido**: `get_object_or_404` y `UnreadableCSVError` que se convierte en `Problem`. Con tests de vista (7), que además cierran buena parte de QA-02.
  ~~ Real: `objects.get()` sin `get_object_or_404`
  y `decode("utf-8-sig")` sin capturar. Barato de arreglar.
- [x] **ARCH-04 — `StaticDataset` admite configuraciones que el motor no puede cumplir.** **Corregido**: `clean()` rechaza los tres casos y el formulario del Backoffice muestra el mensaje (verificado contra la vista real, no solo `full_clean()`). La FK se acepta escrita de las dos formas (`player` y `player_id`), que es el error de dedo más probable. 7 tests.
  ~~ Real: tabla
  sin loader, clave natural con columnas inexistentes, upsert sin constraint. Validar en `clean()`.

### Afinado del scheduler

- [x] **Los jobs `*_post` corrían toda la temporada, no solo en octubre.** **Corregido**: usan una
  ventana más corta, desde `post_season_start_date`. Medido con el dato real de 2026, dejan de correr
  del 25 de marzo al 28 de septiembre — unas 550 llamadas al proxy que ya no se hacen. Si la fecha
  falta caen al fin de la serie regular, y si tampoco está, a la apertura: se degrada hacia correr y
  nunca hacia callar, y el motivo del salto dice qué fecha se usó.

### Esperando dato, no código

- [ ] **Reactivar el tab Salarios del perfil.** **Decisión del dueño (2026-07-26): queda apagado por un buen rato — no se hará por ahora.** El código no se toca: sigue construido, probado y fuera de `REGISTRY`. No hace falta volver a evaluarlo hasta que la vista `v_dglweb_salaries` mejore de verdad, y quien la mejore será el dueño. Está construido, probado y **apagado a propósito**
  (línea comentada en `profiles/tabs.REGISTRY`). La fuente no da la talla: `dom_salaries` trae 1.385
  filas para 343 jugadores en sesenta temporadas, 2025 tiene 12 filas, y al dominicano mejor pagado
  de la historia le falta el registro — el máximo de todo el archivo es Luis Castillo con 24,15
  millones en 2024, cuando Soto cobró ~31 ese mismo año. Con esa cobertura el tab no informa,
  desinforma: un perfil que muestra tres de las doce temporadas que el pelotero cobró se lee como su
  historial completo, y el footer de advertencia no deshace esa lectura. **Bloqueado por la vista
  `v_dglweb_salaries`**, que el dueño está mejorando; cuando el dato esté, se descomenta una línea.
  Hay un test que fija el apagado para que volver sea una decisión y no un descuido.
  **Del review v6 (SAB-03), que confirma la decisión**: al reactivarlo, rotular la tabla como
  «salarios conocidos en DGL» y no como historial de carrera — y exigir antes una métrica de
  cobertura por temporada, no solo la impresión de que mejoró.

### Aceptados, menor prioridad

- [ ] **ARCH-02 — el borrador vive en sesión, no en staging auditable.** Buen señalamiento: sin id de
  revisión ni hash, dos admins pueden confirmar en orden cruzado. Es rediseño, no parche.
  **Decisión del dueño (2026-07-26): prioridad muy baja, no entra antes del lanzamiento.** El
  escenario que arregla exige DOS administradores cargando el mismo dataset a la vez, y hoy carga una
  sola persona una o dos veces al año. La parte urgente del finding —un CSV enorme decodificado
  entero en memoria— ya se cerró en SEC-01. Sube de prioridad el día que entre otra persona a cargar
  datos.
- [x] **ARCH-03 — `leaderboards.py` importa helpers privados de `tabs.py`.** **Corregido**: nace `profiles/metric_layout.py`, público, con lo que las dos pantallas comparten — `DESCRIPTIVE_COLUMNS`, `divisions_for()`, `pretty_qualifier()` y `qualifier_lookups()`. Ya no hay imports de nombres privados entre módulos de `profiles`. Con tests propios que fijan el acuerdo (ninguna métrica en dos divisiones, el umbral se escribe igual en las dos pantallas).
  ~~ Cierto y lo sufrí al
  agregar fildeo. Mover el layout de métricas y el formato de umbrales a un módulo público.
- [ ] **QA-02 — las vistas de carga casi no tienen tests (31%).** De acuerdo: es la pieza que
  reemplaza tablas y no está ejercitada end-to-end. Los tests que escribí cubren motor y loader.
- [ ] **SAB-02 — no se reconcilia lo cargado contra `H`/`BIP` de la fila.** La validación defensiva es
  correcta. **Matiz**: el modo de fallo que describe (coeficientes sumando >100%) no se materializó —
  medido tras la carga real, Sosa 2000 suma .973. La guarda de "solo pisar si tipifica más" ya evita
  el caso obvio. Vale igual como red de seguridad.
- [ ] **DEV-03 / DEV-04 — `compare()` carga todo en memoria; el upsert hace una query por fila.**
  Ciertos. Con 1.500 filas no se nota; el propio review dice que es tolerable. Documentar el límite
  del motor y volver si aparece un dataset grande.
- [x] **FE-02 — falta ARIA básico en nav/tabs/pills.** **Corregido**: cabecera (nav con nombre, `role="search"` + label del buscador, hamburguesa con `aria-label`/`aria-expanded`/`aria-controls`), pestañas del perfil con el juego completo (`aria-selected`, `aria-controls`↔`aria-labelledby`, `role="presentation"` en los `<li>`) y los cinco tablists con nombre propio. En Líderes NO se pusieron roles de pestaña a propósito: son enlaces que recargan, así que van en `<nav>` con nombre y `aria-current="page"`. Con tests (`tests/test_accessibility.py`) que fijan el acuerdo, incluido que cada tablist anuncie exactamente una seleccionada.
  ~~ Cierto y barato.

### Aceptados pero ya conocidos (no son de esta sesión)

- [x] **«Jugadores» del nav volvió**, apuntando a `/jugadores/`: índice con buscador (acentos y eñes
  insensibles vía `unaccent`) y la plantilla dominicana de la última temporada. Quedan escondidos
  Artículos (Fase 5) y Entrar (Fase 7).
- [x] **FE-01 — enlaces públicos que no hacen nada.** **Corregido**: cero `href="#"` renderizados en portada, perfil y Líderes, con un test que lo fija sobre el HTML servido. Se ocultaron nav (Artículos, Jugadores, Entrar), buscador y la columna Legal del pie; los "desglose ▸" pasaron a `<button>` porque sí hacen algo y eran acción, no destino.
  **Y apareció algo más grave que el finding**: los ocho enlaces de `home.html` estaban pegados a contenido INVENTADO —cinco titulares con fecha y firma, líneas de juego atribuidas a peloteros reales («Juan Soto 3-4, 2 HR», «Ayer · 15 jul») y una tabla de líderes de jonrones 2026 con números falsos—. En un sitio de estadísticas eso no es maquetado: son cifras falsas sobre personas reales en la primera página. Se sacó completo y NO se reemplazó por otros titulares o números. La portada quedó con un `h1` de verdad (no tenía) y el enlace a Líderes.
  **Pendiente de Fase 5**: la portada necesita contenido. El panel de líderes es el primero que conviene rehacer, porque el dato ya existe en `dgl_leader` y solo falta la consulta.
  ~~ Verificado: 7 `href="#"` en `base.html` y 8 en
  `home.html`, más el buscador con `onsubmit="return false"`.
- [ ] **QA-03 — el scheduler encadena por horario, no por workflow.** Ya está en `MEJORAS_FUTURAS.md`
  como "A DISCUTIR". El review coincide.
- [ ] **SAB-03 — la temporada en curso no tiene umbrales prorrateados.** Mismo caso: ya identificado.
- [ ] **SEC-02 / SEC-03 — CDN sin SRI/CSP; Ofelia con socket.** **Parcial**: la imagen de Ofelia ya no es `latest`, queda pinneada por digest (2026-07-26). Sigue pendiente el socket de Docker y todo lo del CDN.
  ~~ original: Ya en backlog para
  Fase 8 (endurecimiento). El review no agrega información nueva pero confirma la prioridad.

### Sin acción

- **SEC-04** — revisión OWASP sin hallazgos. Nada que hacer.

## Umbral de coeficientes DE POR VIDA (BIP)

- [x] **El qualifier de carrera de los coeficientes usaba `BALLS_IN_PLAY>=400` — arbitrario (era el de
  temporada).** **Resuelto** con estudio estadístico (`docs/UMBRALES_COEFICIENTES.md`): el umbral de
  carrera se ancló al estándar del sitio (bateo PA≥3000, pitcheo IP≥1000). Nuevos umbrales de **carrera**:
  bateo `BIP≥2000` / `swings≥5000`, pitcheo `BIP≥3000` / `swings≥8000` (el pitcheo enfrenta muchas más
  BIP). Temporada intacta (400/1000). BD actualizada y `dgl_leader` reconstruido (GB% carrera bateo pasó
  de 203 a 85 calificados).
