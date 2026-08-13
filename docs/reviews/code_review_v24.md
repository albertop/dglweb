# Code Review v24

Fecha: 2026-08-13

Actualizado: revalidado después de cambios que entraron mientras se escribía la primera versión de este
review. El documento del comparador ya describe la clave por versión de datos y la canonicalización; los
findings de abajo reflejan el estado actual.

Alcance: revisión de los cambios posteriores a `code_review_v23.md`, con foco en el comparador,
generador, caché de PNG, pruebas nuevas y documentación operativa. Antes de revisar se leyeron los
`.md` bajo `docs/`, especialmente `TODO.md`, `COMPARADOR.md`, `CODING_STANDARDS.md`,
`PRUEBAS_DESPLIEGUE.md`, `CORTAFUEGOS.md` y los reviews previos. No revisé `_not_in_use` y no repito
pendientes ya marcados en `docs/TODO.md`.

## Resumen Ejecutivo

Las correcciones de v23 están bien encaminadas:

1. El umbral por temporada ahora se calcula por bolsa/año y tiene prueba.
2. El endpoint PNG ya responde `304` con `If-None-Match`.
3. La clave de caché ya se canonicaliza por ids ordenados, modo, extra, tipo de imagen y versión de
   datos.
4. La documentación SP/RP ya dice que la comparación mixta se rechaza a propósito, y el comentario viejo
   de `_resolver()` fue corregido.
5. La suite Python enfocada pasa.

Quedan cuatro issues nuevos o residuales antes de considerar este bloque listo. Ninguno toca la lógica
sabermétrica central, pero dos sí afectan confianza operativa: Ruff queda rojo y la caché pública puede
seguir sirviendo PNGs viejos hasta que venza `max-age`.

## Persona 1: Python Principal Developer

### Finding DEV-01 - Ruff vuelve a fallar por imports desordenados en un test nuevo

Severidad: P2

Evidencia:

- `tests/test_generador.py:661` importa `IngestRun` antes de `tarjeta`.
- `tests/test_generador.py:662` importa `tarjeta` después de `dglweb.stats.models`, lo que dispara
  `I001`.
- La corrida de Ruff falló con:

```text
I001 Import block is un-sorted or un-formatted
--> tests/test_generador.py:657:5
Found 1 error.
```

Problema: funcionalmente los tests pasan, pero el quality gate del proyecto queda rojo. Es pequeño, pero
bloqueante si `ruff` es la puerta de entrada como declara `docs/CODING_STANDARDS.md`.

Sugerencia: ordenar esos imports (`from dglweb.stats import tarjeta` antes de
`from dglweb.stats.models import IngestRun`) y volver a correr Ruff.

Razonamiento: esto no cambia comportamiento, pero evita que una corrección funcional llegue con CI rojo.

## Persona 2: QA / Reliability Engineer

### Finding QA-01 - La invalidación por versión no llega a la URL pública del PNG

Severidad: P2

Evidencia:

- `dglweb/profiles/comparaciones.py:68`-`dglweb/profiles/comparaciones.py:70` afirma que, cuando cambia
  la versión de datos, la tarjeta sale nueva “en cuanto el dato existe”.
- `dglweb/profiles/comparaciones.py:319`-`dglweb/profiles/comparaciones.py:320` envía
  `Cache-Control: public, max-age=21600`.
- `dglweb/profiles/comparaciones.py:652` y `dglweb/profiles/comparaciones.py:656` generan `url_png` y
  `url_previa` sin versión en la URL pública.
- `templates/profiles/comparar.html:29`, `templates/profiles/comparar.html:36` y
  `templates/profiles/comparar.html:38` usan esas mismas URLs estables para Open Graph, `data-png` e
  `<img>`.
- `tests/test_generador.py:691` fuerza `caches[settings.COMPARTIDA].clear()` para probar el cambio de
  clave del servidor, pero no prueba qué pasa con un cliente que todavía tiene la URL fresca por
  `max-age`.
- `docs/COMPARADOR.md:659`-`docs/COMPARADOR.md:663` ya documenta correctamente que la clave interna
  incluye versión de datos, ids ordenados, modalidad y tipo de imagen.
- `docs/COMPARADOR.md:669`-`docs/COMPARADOR.md:671` dice que la carga corta el TTL “en curso” y que la
  tarjeta se repinta en la siguiente petición. Eso es cierto para la caché del servidor, no para
  navegadores/proxies que no revalidan una URL todavía fresca.

Problema: la versión en la clave invalida la caché del servidor, pero no invalida la caché del navegador,
proxy o scraper social, porque la URL pública no cambia. Un usuario que ya recibió `/tarjeta.png` puede
seguir usando el PNG viejo hasta seis horas sin revalidar, aunque el servidor ya tenga una clave nueva.
Lo mismo aplica a la previa `?previa=1`.

Sugerencia: decidir explícitamente el contrato. Si se quiere frescura “en cuanto el dato existe”, incluir
la versión en la URL pública, por ejemplo `tarjeta.png?v=<version>` y `tarjeta.png?previa=1&v=<version>`,
manteniendo la clave del servidor inmune a parámetros basura. Si se acepta hasta seis horas de retraso en
clientes, ajustar comentarios y tests para no prometer invalidación instantánea fuera del servidor.

Razonamiento: este es el tipo de bug que se ve solo después de una carga real: el backend ya repintó, pero
el navegador enseña lo que tiene guardado y parece que los datos no cambiaron.

## Persona 3: Frontend Engineer

### Finding FE-01 - Volver al paso de temporadas pierde visualmente el año elegido

Severidad: P2

Evidencia:

- `templates/profiles/generador.html:135` renderiza `data-elegido-valor="{{ elegido }}"` en cada selector
  de temporada.
- `static/js/comparador.js:29` recuerda `var antes = select.value`.
- `static/js/comparador.js:41` restaura `select.value = antes` solo si ese valor aparece en los años
  cargados.
- `tests/js/comparador.test.js:191` prueba que al volver con un pelotero puesto se cargan años, pero no
  que se restaure el año previo.

Problema: al volver desde el resumen al paso 5, el HTML trae los años elegidos en `data-elegido-valor`,
pero el `<select>` todavía no tiene opciones y `select.value` está vacío. Cuando el JS llena las opciones,
elige el primer año disponible en vez del año que el usuario ya había elegido. Si el usuario pulsa
“Siguiente” sin darse cuenta, puede cambiar la comparación.

Sugerencia: en `llenar()`, usar `select.dataset.elegidoValor || select.value` como valor previo y añadir
un test JS con `data-elegido-valor="2021"` que espere `select.value === "2021"` después de cargar años.

Razonamiento: el servidor valida, pero no puede adivinar intención si el propio formulario manda un año
distinto. La pantalla debe conservar exactamente lo que el usuario eligió.

## Persona 4: Security Engineer

El finding QA-01 también aplica aquí por caché pública: no es una vulnerabilidad de datos privados, pero
sí un riesgo de integridad del contenido compartido. Una imagen pública vieja con ranking viejo puede
circular como si fuera actual.

Sin findings adicionales de seguridad.

## Persona 5: Backend Architect

El finding QA-01 también es arquitectónico: la clave interna tiene versión, pero la URL pública no. El
contrato de caché queda partido entre dos niveles con semánticas distintas. La actualización de
`docs/COMPARADOR.md` ya explica mejor la clave interna, pero todavía no resuelve la diferencia entre
caché del servidor y caché pública.

Sin findings adicionales.

## Persona 6: Experto en Beisbol y Sabermetría

Sin findings sabermétricos nuevos.

El finding DEV-01 de v23 quedó corregido satisfactoriamente: `tests/test_comparador.py` ya cubre que, en
modo temporada, cada bolsa se mida con el umbral de su propio año. La separación SP/RP, WPCT solo para
abridores, derrotas sin ranking, postemporada fuera del comparador regular y `season_totals()` siguen
consistentes.

Riesgo residual: FE-01 puede hacer que el usuario termine comparando otro año sin querer; eso no es un
cálculo sabermétrico incorrecto, pero sí produce una tarjeta semánticamente distinta a la intención.

## Persona 7: Docker / fail2ban / nginx

### Finding OPS-01 - La checklist de despliegue no tiene una sección para el comparador y su migración

Severidad: P3

Evidencia:

- `dglweb/core/migrations/0003_tabla_de_cache_de_imagenes.py:23` crea la tabla de caché con
  `createcachetable`.
- `config/settings/base.py:232`-`config/settings/base.py:238` configura el alias `IMAGENES` sobre
  `dgl_cache_imagenes`.
- `docs/COMPARADOR.md:678` recuerda limpiar `dgl_cache_imagenes` al desplegar un cambio de diseño.
- `docs/PRUEBAS_DESPLIEGUE.md` no menciona `dgl_cache_imagenes`, el comparador, la nueva migración ni
  una prueba manual de `/comparar/`.

Problema: el código trae migración, estáticos/JS nuevos, tipografías nuevas y una tabla de caché que puede
necesitar limpieza en cambios visuales, pero la checklist operativa no lo aterriza. En producción, esto
puede convertirse en “la feature funciona en tests, pero la imagen vieja sigue circulando” o en `/ready`
marcando migraciones pendientes sin una sección clara para esta versión.

Sugerencia: agregar en `docs/PRUEBAS_DESPLIEGUE.md` una sección para la versión del comparador: correr
`migrate`, verificar que `/comparar/` carga, generar una tarjeta, validar `tarjeta.png`, validar la previa
`?previa=1`, probar una URL SP/RP manual con 404, y limpiar `dgl_cache_imagenes` cuando cambie el diseño.

Razonamiento: esta feature depende de más que Python: migración, estáticos, caché, Open Graph y navegador.
La checklist es donde esas piezas dejan de vivir solo en la cabeza de quien la construyó.

## Estado de los Findings de v23

- `DEV-01`: corregido satisfactoriamente en lógica y prueba.
- `QA-01`: corregido para `304`, pero queda el nuevo `QA-01` de v24 sobre caché pública y URL sin versión.
- `SEC-01`: corregido satisfactoriamente; la clave ya es canónica y tiene prueba.
- `ARCH-01`: corregido satisfactoriamente; documentación y comentario interno ya explican el rechazo SP/RP.

## Verificaciones Ejecutadas

```text
docker-compose run --rm web pytest --create-db tests/test_comparador.py tests/test_generador.py -q
68 passed in 106.92s

docker-compose run --rm --no-deps web ruff check dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py tests/test_comparador.py tests/test_generador.py
FAILED: I001 Import block is un-sorted or un-formatted en tests/test_generador.py

docker-compose run --rm --no-deps web mypy dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py
Success: no issues found in 4 source files

docker-compose run --rm --no-deps web python manage.py check
System check identified no issues (4 silenced).
```

No ejecutado:

```text
node .\node_modules\vitest\vitest.mjs run tests/js/comparador.test.js tests/js/buscador.test.js
Startup Error: Cannot find module @rollup/rollup-win32-x64-msvc
```
