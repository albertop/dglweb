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
- [ ] **DEV-02 — liderazgo de postemporada de UNA sola ronda no se pinta como líder de temporada.**
  De acuerdo que es una inconsistencia motor↔UI. **PERO** choca con la decisión previa del dueño
  ("el badge va solo en la fila Tot, nunca en filas de ronda"): en un octubre de una sola ronda no
  hay fila Tot. Opciones: (a) tratar la línea única como el agregado para el highlight, o (b) emitir
  siempre una fila Tot. **Necesita decisión de producto** antes de tocar.
- [x] **DEV-03 (gating) — los boards de octubre ignoran `best_season`/`best_career`.** **Corregido**:
  `_postseason_leaders` / `_postseason_rate_leaders` gatean el board de carrera por `best_career` y el
  de temporada por `best_season`; los predicados `_wants_postseason*` saltan si no se quiere ninguno.
  Con test. (No hubo que reconstruir: 0 métricas de octubre tenían un flag apagado.)
- [ ] **DEV-04 — `_innings_to_outs` acepta fracciones imposibles (.3, .9, .25).** De acuerdo. El
  parser solo mira el primer dígito. Fix: validar que la fracción sea 0/1/2 y fallar-loud/`None` en
  ingest. Toca paridad, así que con cuidado + tests (.3/.9/basura). Pendiente.
- [ ] **DEV-05 — todos los tabs se calculan por request.** Ya conocido (v3 DEV-01). Carga diferida
  (HTMX/endpoints por tab) sigue pendiente; el test de presupuesto de queries es el guardarrail.
- [ ] **SAB-02 — panel de receptor sin CS% ni contexto de volumen.** De acuerdo. Derivar
  `CS% = CS/(SB+CS)` cuando `SB+CS > 0`, y etiquetar cERA como descriptiva. Feature, pendiente.
- [ ] **SAB-03 — cobertura Statcast es piso por año, no por métrica (hueco 2000-2001).** Ya conocido
  (v3 SAB-01, `MEJORAS_FUTURAS.md`). Barato mientras tanto: mencionar los años parciales en la nota
  de la UI si el jugador tiene filas 2000-2001 en esos panes.
