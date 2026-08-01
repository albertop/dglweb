# Code Review v19

Fecha: 2026-08-01

Alcance: verificación de las correcciones hechas después de `code_review_v18.md`, con foco en el
cambio de portada donde, en móvil, `Ver más artículos` despliega tres tarjetas adicionales. Antes de
revisar se leyeron los `.md` bajo `docs/`, incluyendo `TODO.md` y los reviews anteriores. No se
modificó código fuente; este archivo es el único entregable.

Reglas aplicadas:

- No se repiten asuntos ya marcados como pendientes en `docs/TODO.md`.
- Si varias personas detectan el mismo problema, aparece una sola vez bajo la persona que mejor
  representa el riesgo principal.
- No se reabre la decisión consciente de excluir Ligas Negras de ciertos liderazgos.
- Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P3 | FE-01 | Frontend Engineer | El nuevo botón móvil de `Ver más artículos` queda muerto si `site.js` no ejecuta. |

No se encontraron findings P1 ni P2.

## Persona 1 - Python Principal Developer

Sin findings nuevos.

La vista de portada mantiene el corte en Python y no empuja lógica de conteo a la plantilla:
`dglweb/core/views.py:68-89` calcula el total a leer y separa `articulo`, `articulos` y
`articulos_de_mas` con slices claros. `para_tarjetas(...)` sigue siendo el punto compartido para
evitar N+1 en las tarjetas.

## Persona 2 - QA / Reliability Engineer

Sin finding separado. La falta de cobertura queda absorbida por FE-01, porque el riesgo observable es
de experiencia progresivamente mejorada: si JS no carga, el control visible no hace nada.

Recomendación de prueba asociada a FE-01: agregar un test de template/home con más de tres artículos
que congele el fallback esperado, y un test JS pequeño para `static/js/site.js` que pruebe `data-
desplegar`, `esta-desplegado`, `aria-expanded` y el cambio de texto.

## Persona 3 - Frontend Engineer

### FE-01 [P3] El nuevo botón móvil de `Ver más artículos` queda muerto si `site.js` no ejecuta

**Evidencia**

- `templates/home.html:186-189` renderiza en móvil un `<button>` con
  `data-desplegar="#portada-articulos"`, pero sin `href`, `aria-controls` ni alternativa
  `<noscript>`.
- `static/css/site.css:437-442` oculta `.dgl-art-de-mas` por defecto y solo lo vuelve visible cuando
  `#portada-articulos` recibe la clase `esta-desplegado`.
- `static/js/site.js:59-65` es el único sitio que agrega esa clase y actualiza `aria-expanded`.
- `docs/TODO.md:2592-2594` dejó cerrado el problema anterior con la misma regla de producto: un
  control visible que no hace nada es peor que no tenerlo.

**Bug / edge case**

En móvil, si `site.js` no carga, se bloquea por CSP, falla por un error previo o el visitante navega
sin JavaScript, el usuario ve el botón `Ver más artículos`, pero el click no cambia nada. Las tres
tarjetas extra siguen escondidas por CSS. El enlace de menú a `Artículos` todavía existe si hay índice,
pero el CTA visible de esa sección queda roto.

**Impacto**

Medio: no rompe la portada completa ni oculta los primeros tres artículos, pero reintroduce una clase
de fallo que el proyecto ya decidió evitar. También deja sin una relación accesible clara al botón,
porque `aria-expanded` no declara qué región controla.

**Mejora sugerida**

Usar progressive enhancement: renderizar un `<a href="{{ indice }}">Ver más artículos</a>` como
fallback real y convertirlo en despliegue solo cuando `site.js` inicializa, o agregar una alternativa
`<noscript>` que oculte el botón y muestre un enlace funcional al índice. Si se mantiene el botón,
sumar `aria-controls="portada-articulos"` para que el estado expandido tenga un destino explícito.

## Persona 4 - Security Engineer

Sin findings nuevos.

No vi nuevos sinks de HTML crudo, SQL dinámico, secretos, endpoints administrativos ni cambios en CSP.
El comportamiento nuevo depende de JS propio servido desde `static/js/site.js`, no de terceros.

## Persona 5 - Backend Architect

Sin findings nuevos.

La decisión de leer seis artículos en la portada está centralizada en constantes (`PORTADA_DESTACADO`,
`PORTADA_RESTO`, `PORTADA_MOVIL_EXTRA`) y conserva el orden editorial `-fijado`, `-fecha`, `-pk`.
El cache-buster de CSS fue actualizado en `templates/base.html:96` a `?v=141`, así que no queda el
riesgo de desplegar HTML nuevo con CSS viejo cacheado.

## Persona 6 - Experto en béisbol y sabermetría

Sin findings nuevos.

El cambio revisado es de portada/artículos y no altera cálculos de líderes, ventanas, destacados,
qualifiers, clasificación de abridores/relevistas ni supuestos sabermétricos.

## Persona 7 - Docker / fail2ban / nginx

Sin findings nuevos.

No hubo cambios en `Dockerfile`, `docker-compose.yml`, `deploy/`, nginx ni fail2ban. La configuración
local de compose valida correctamente.

## Verificación Ejecutada

- Lectura de `.md` bajo `docs/`, incluyendo `docs/TODO.md`, `docs/reviews/code_review_v17.md` y
  `docs/reviews/code_review_v18.md`.
- `git show --stat --oneline HEAD`: confirma el cambio `feat(portada): en el teléfono, «Ver más
  artículos» despliega en vez de saltar`, con cambios en `core/views.py`, `site.css`, `base.html` y
  `home.html`.
- `docker-compose run --rm web pytest tests/test_smoke.py tests/test_articles.py::test_si_el_indice_esta_restringido_la_portada_no_enlaza_a_el`:
  **11 passed**.
- `docker-compose run --rm web ruff check dglweb/core/views.py`: **All checks passed**.
- `docker-compose config --quiet`: OK.
- `git diff --check`: sin errores.

No se pudo ejecutar la suite JS: `npm` no está disponible en el PATH de esta sesión; usando el runtime
bundled de Codex, Vitest no arrancó porque falta la dependencia opcional
`@rollup/rollup-win32-x64-msvc` en `node_modules`, y `pnpm` intentó reinstalar dependencias pero falló
por red restringida.
