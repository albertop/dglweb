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
