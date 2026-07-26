# TODO — dglweb

Lista de pendientes que van surgiendo sobre la marcha. (Ítems de decisión / afinado, no el
roadmap de fases — eso está en `BUILD_PLAN.md`.)

## Próximo: tab de Fildeo

Bateo y Pitcheo están completos (seis pills cada uno: Estándar, Avanzado, Statcast, Coeficientes,
Postemporada, Totales). **Falta Fildeo**, y arranca en buenas condiciones tras el refactor de
columnas declarativas:

- Sus columnas son una lista más en `dglweb/profiles/columns.py`, y reusa tal cual las seis
  partials (`templates/profiles/_season_*.html`, `_label_*.html`, `_post_*.html`), la leyenda,
  `_personal_bests`, los filtros de formato y todo el sistema de resaltado.
- **Lo único que necesita código propio es el ensamblado del contexto**: `_group_context` NO le
  sirve. Las líneas de fildeo son **por posición**, no por stint (un jugador tiene una fila por
  cada posición que jugó cada temporada), así que la lógica de "temporada dividida / combinada XXX"
  no aplica igual. `FieldingCareer` ya usa `level=pos` en vez de team/league, y `career_totals` ya
  agrega fildeo por posición. Hay que escribir un `_fielding_context` que arme filas por posición.
- El motor de líderes ya rankea fildeo **por posición** (`fielding_pos` en `dgl_leader`), así que
  los liderazgos por posición ya existen en la base — solo falta consumirlos en la página.
- `_leaderships` hoy es agnóstico de posición (bateo/pitcheo llevan `fielding_pos=NULL`); para
  fildeo habrá que filtrar por la posición de cada fila.

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

- [ ] Nav (Artículos/Líderes/Jugadores/Entrar) y buscador apuntan a `#`/submit desactivado.
  Poner URLs reales o esconderlos hasta que las páginas existan.

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
- [ ] **DEV-03 — las tablas repiten listas de columnas a mano.** Real y ya lo sufrimos: cada columna
  agregada (LOB, TotAvg, BsR, G, AB) obligó a editar encabezado + fila + total en varios bloques, y
  las desalineaciones solo se detectaron con un script ad-hoc. **Conviene resolverlo ANTES de Fildeo**,
  que sería la tercera copia del patrón. Propuesta: mover las columnas a una lista declarativa en
  Python `(label, attr, formato, clase)` y renderizar con un partial común.
- [ ] **SAB-02 — boards descriptivos etiquetados como "mejor/peor".** GB%, FB%, LD% y GB/FB se
  rankean, pero llamarlos "mejor" implica un valor competitivo que no tienen. La corrección natural
  es de etiquetas ("Más alto / Más bajo") y vive en la UI de líderes, que **todavía no existe**
  (Fase 5). Cuando se construya, usar la misma marca de métrica descriptiva que ya usa SAB-03.
- [ ] **SAB-01 — la cobertura Statcast se decide por año, no por completitud.** El reviewer llegó de
  forma independiente al hueco de 2000-2001 que ya está documentado en `MEJORAS_FUTURAS.md`. Decisión
  del dueño: dejarlo así por ahora. Su sugerencia extra —advertirlo en la UI, no solo en el backlog—
  sigue disponible y es barata.

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
- [ ] **SAB-03 — cobertura Statcast es piso por año, no por métrica (hueco 2000-2001).** Ya conocido
  (v3 SAB-01, `MEJORAS_FUTURAS.md`). **Mitigado en la UI**: los paneles Statcast y Coeficientes
  nombran las temporadas afectadas del propio jugador (`derive.UNDERTYPED_STATCAST_SEASONS`) y
  explican qué columnas mirar con reservas — Sosa marca 2000 y 2001, Pujols solo 2001, y quien no
  jugó esos años no ve nada. Medido: los cuatro coeficientes de Sosa suman 99.8% en 1999 y 55.9% en
  2000, con LD% cayendo de .204 a .036. **Son diez temporadas, no dos** — la prueba que las encuentra
  es exacta: los cuatro tipos de hit son una partición de H.
  **El arreglo de fondo ya está diseñado y no es "cobertura por métrica" sino traer el dato**:
  Retrosheet SÍ tiene la trayectoria en esos años (97% en 2000-2001), así que el hueco es de nuestra
  fuente y no del registro histórico. Ver **Fase 4e** y `docs/DATOS_DE_APOYO.md`. Al cargarlo se
  borra `derive.UNDERTYPED_STATCAST_SEASONS` y esto cierra.

## Code review v5 — findings (2026-07-25)

Ver `docs/reviews/code_review_v5.md`. 22 findings en seis personas. Evaluados uno a uno; mi
acuerdo/decisión. **De acuerdo con casi todo**: el review acertó sobre todo en la Fase 4e, que es
código de esta misma sesión y donde varios huecos son míos y verificables.

### Aceptados y verificados — arreglar primero

- [ ] **DEV-02 / FE-03 — `leaders_context()` revienta con la base vacía.** **Reproducido**:
  `IndexError: list index out of range` en `division_labels[0]`. Pasa en staging limpio, base recién
  migrada, o si alguien desactiva las métricas de un grupo desde el Backoffice. Es el más grave
  porque tumba una página pública entera, no un caso de borde. Falta un contexto vacío renderizable.
- [ ] **QA-01 / SAB-04 — las filas con `mlb_id` desconocido se descartan en silencio.** Real, y el
  reviewer ve algo que a mí se me pasó: las descartadas **tampoco entran en los totales de cobertura**,
  así que un maestro incompleto hace que el CSV parezca MÁS sano de lo que está. La validación se
  autoengaña. Hay que separar "sin mlb_id" de "mlb_id que no existe en el maestro" y reportar el
  segundo con conteo y muestra.
- [ ] **SAB-01 — la cobertura se valida por temporada, no por (temporada, oficio).** Verificado:
  `por_temporada.setdefault(row["season"], ...)` mezcla bateo y pitcheo. Si un oficio viene completo
  y el otro roto, el promedio pasa el 80% y el roto entra igual. Error mío al escribir `checks()`.
- [ ] **ARCH-01 — cargar datos de apoyo no reconstruye lo que depende de ellos.** Real y ya lo
  vivimos: tras la carga hubo que correr `build_leaders` a mano, y hasta que se corrió las páginas
  servían coeficientes viejos. `BattingCareer`/`PitchingCareer` tampoco se rehacen.
- [ ] **SEC-01 — subida de CSV sin límite de tamaño.** Verificado: no hay `DATA_UPLOAD_MAX_*` en
  settings, y el CSV entero se guarda en sesión. Aunque exige cuenta admin, un archivo grande tumba
  el proceso. Límite por dataset + rechazo por extensión + staging con TTL en vez de sesión.
- [ ] **QA-04 — el nombre de archivo equivocado avisa pero deja confirmar.** De acuerdo, y es
  incoherente con lo que yo mismo escribí en `DATOS_DE_APOYO.md`: que el chequeo existe para atajar
  cargar el CSV de salarios sobre la tabla de transacciones. Si solo avisa, no ataja nada.
- [ ] **DEV-01 — 500 por `pk` inexistente o CSV no UTF-8.** Real: `objects.get()` sin `get_object_or_404`
  y `decode("utf-8-sig")` sin capturar. Barato de arreglar.
- [ ] **ARCH-04 — `StaticDataset` admite configuraciones que el motor no puede cumplir.** Real: tabla
  sin loader, clave natural con columnas inexistentes, upsert sin constraint. Validar en `clean()`.

### Aceptados, menor prioridad

- [ ] **ARCH-02 — el borrador vive en sesión, no en staging auditable.** Buen señalamiento: sin id de
  revisión ni hash, dos admins pueden confirmar en orden cruzado. Es rediseño, no parche.
- [ ] **ARCH-03 — `leaderboards.py` importa helpers privados de `tabs.py`.** Cierto y lo sufrí al
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
- [ ] **FE-02 — falta ARIA básico en nav/tabs/pills.** Cierto y barato.

### Aceptados pero ya conocidos (no son de esta sesión)

- [ ] **FE-01 — enlaces públicos que no hacen nada.** Verificado: 7 `href="#"` en `base.html` y 8 en
  `home.html`, más el buscador con `onsubmit="return false"`. Es el andamiaje de Fase 0 esperando
  Fase 5 (editorial) y Fase 7 (auth/búsqueda). Vale ocultarlos antes de que alguien externo lo vea.
- [ ] **QA-03 — el scheduler encadena por horario, no por workflow.** Ya está en `MEJORAS_FUTURAS.md`
  como "A DISCUTIR". El review coincide.
- [ ] **SAB-03 — la temporada en curso no tiene umbrales prorrateados.** Mismo caso: ya identificado.
- [ ] **SEC-02 / SEC-03 — CDN sin SRI/CSP; Ofelia con socket e imagen `latest`.** Ya en backlog para
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
