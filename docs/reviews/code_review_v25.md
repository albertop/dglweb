# Code Review v25

Fecha: 2026-08-13

Alcance: revisión de los cambios posteriores a `code_review_v24.md`, con foco en las correcciones del
comparador, el generador de temporadas, la URL versionada del PNG, la checklist de despliegue y la
documentación. Antes de revisar se leyeron los `.md` bajo `docs/`, especialmente `TODO.md`,
`COMPARADOR.md`, `CODING_STANDARDS.md`, `PRUEBAS_DESPLIEGUE.md`, `CORTAFUEGOS.md` y los reviews
previos. No revisé `_not_in_use` y no repito pendientes ya marcados en `docs/TODO.md`.

## Resumen Ejecutivo

Los findings de v24 quedaron corregidos satisfactoriamente en lo esencial:

1. Ruff volvió a verde; el bloque de imports del test nuevo ya no dispara `I001`.
2. La URL pública del PNG y de la previa ya incluye `?v=<version>`, así que navegadores, proxies y
   scrapers sociales ven una dirección nueva cuando cambia la versión de datos.
3. El servidor mantiene la clave interna canónica e ignora `?v=` inventados, evitando multiplicar
   entradas de caché.
4. El generador ya restaura el año elegido al volver al paso de temporadas.
5. La checklist de despliegue ya tiene una sección específica para el comparador, migración, PNG,
   previa, rechazo SP/RP y limpieza de `dgl_cache_imagenes`.

Quedan dos hallazgos menores/residuales. Ninguno invalida la lógica sabermétrica ni bloquea el feature,
pero conviene cerrarlos para evitar confusión de usuario y documentación contradictoria.

## Persona 1: Python Principal Developer

### Finding DEV-01 - El año restaurado del servidor se queda pegado al cambiar de pelotero

Severidad: P3

Evidencia:

- `templates/profiles/generador.html:135` renderiza `data-elegido-valor="{{ elegido }}"` para conservar
  el año elegido al volver desde el resumen.
- `static/js/comparador.js:34` usa `select.dataset.elegidoValor || select.value` como valor previo.
- `static/js/comparador.js:103` recarga los años cuando cambia el campo oculto del pelotero, pero no
  limpia ese `data-elegido-valor`.
- `tests/js/comparador.test.js:216` cubre bien el regreso desde servidor con `data-elegido-valor="2021"`,
  pero no cubre el caso posterior de cambiar el pelotero en esa misma pantalla.

Problema: el arreglo de v24 preserva correctamente el año al volver al paso 5, pero ese valor queda
como preferencia permanente del `<select>`. Si el usuario vuelve con Soto 2021, cambia el pelotero por
otro que también tiene 2021, el selector conserva 2021 en vez de caer al año más reciente del nuevo
pelotero. Reproducción con el JS actual:

```text
inicial 2021
tras-cambio 2021
```

Eso no rompe la validación del servidor, pero sí puede producir una comparación distinta a la intención:
al cambiar de jugador normalmente se espera escoger de nuevo, o al menos empezar por el año más reciente
de ese jugador, no heredar el año del jugador anterior.

Sugerencia: consumir `data-elegido-valor` una sola vez. Por ejemplo, después de calcular `antes`, limpiar
`select.dataset.elegidoValor = ""`; o limpiar ese dataset justo antes de `cargar(select)` cuando el
evento venga de un cambio de pelotero. Añadir un test JS donde se vuelva con `data-elegido-valor="2021"`,
se cambie el hidden a otro slug con años `[2022, 2021, 2020]`, y se espere `select.value === "2022"`.

Razonamiento: `data-elegido-valor` representa estado restaurado desde servidor, no una preferencia global
del control. Preservarlo una vez arregla v24; preservarlo para cambios posteriores introduce estado viejo.

### Finding DEV-02 - La documentación todavía dice que la imagen se cachea por ruta

Severidad: P4

Evidencia:

- `docs/COMPARADOR.md:703` dice: "La imagen se cachea por su ruta".
- `docs/COMPARADOR.md:723` ya documenta la clave real: versión de datos + `player_id` ordenados +
  modalidad + tipo de imagen.
- `dglweb/profiles/comparaciones.py:652` y `dglweb/profiles/comparaciones.py:656` generan URLs públicas
  versionadas.
- `dglweb/profiles/comparaciones.py:734` define `_version_url()`.

Problema: la frase vieja quedó contradictoria con el diseño actual. El código ya no cachea por ruta
cruda: cachea por una clave canónica que deliberadamente ignora orden de slugs, slugs viejos y query
params basura. La tabla de la sección sí está correcta, así que el riesgo es de lectura: alguien que lea
solo los bullets iniciales puede volver a pensar el problema que v23/v24 acabaron de cerrar.

Sugerencia: cambiar esa viñeta por algo como: "La imagen se cachea por una clave canónica de comparación
y versión de datos; la ruta pública solo identifica cómo pedirla".

Razonamiento: no es un bug runtime, pero los docs de este proyecto funcionan como contrato operativo.
Cuando una frase de alto nivel contradice la tabla técnica, el próximo cambio de caché empieza desde una
premisa equivocada.

## Persona 2: Experto en Beisbol y Sabermetría

Sin findings sabermétricos nuevos.

La separación bateadores / abridores / relevistas sigue correcta: los relevistas se rankean contra
relevistas, con umbrales propios; abridor contra relevista se rechaza a propósito; WPCT se rankea solo
en abridores; derrotas se muestran sin ranking; postemporada queda fuera del comparador regular; y las
temporadas repartidas por equipos se colapsan con la fila combinada.

La exclusión de peloteros de Ligas Negras está documentada como decisión consciente de comparabilidad de
fuente y WAR, no como bug. No la trato como finding.

Riesgo residual sabermétrico indirecto: `DEV-01` puede hacer que el usuario termine comparando un año
heredado de otro pelotero. El cálculo sería correcto para los parámetros enviados, pero la intención del
usuario podría no ser esa.

## Estado de los Findings de v24

- `DEV-01`: corregido satisfactoriamente. Ruff pasa.
- `QA-01`: corregido satisfactoriamente. `url_png` y `url_previa` llevan `?v=`, y hay tests para que la
  URL cambie tras un `IngestRun` exitoso sin multiplicar caché por `v` inventado.
- `FE-01`: corregido para el regreso desde servidor; queda el residual `DEV-01` de este review al cambiar
  de pelotero después de restaurar el año.
- `OPS-01`: corregido satisfactoriamente. `docs/PRUEBAS_DESPLIEGUE.md` ya incluye la sección del
  comparador.

## Verificaciones Ejecutadas

```text
docker-compose run --rm --no-deps web ruff check dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py tests/test_comparador.py tests/test_generador.py
All checks passed!

docker-compose run --rm --no-deps web mypy dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py
Success: no issues found in 4 source files

docker-compose run --rm --no-deps web python manage.py check
System check identified no issues (4 silenced).

docker-compose run --rm web pytest --reuse-db tests/test_comparador.py tests/test_generador.py -q
70 passed in 127.53s
```

Nota: el primer intento con `--create-db` no llegó a ejecutar la suite porque `test_dglweb` ya existía y
tenía una sesión abierta. Reintentado con `--reuse-db`, la suite enfocada pasó completa.

No ejecutado satisfactoriamente:

```text
C:\Users\aperd\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe .\node_modules\vitest\vitest.mjs run tests/js/comparador.test.js tests/js/buscador.test.js
Startup Error: Cannot find module @rollup/rollup-win32-x64-msvc
```

Ese bloqueo es del `node_modules` local de Rollup/Vitest, no de una aserción fallida de los tests JS.
