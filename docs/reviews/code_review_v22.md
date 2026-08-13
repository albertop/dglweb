# Code Review v22

Fecha: 2026-08-13

Alcance: revisión completa del proyecto con foco en los cambios actuales del comparador/generador, buscador, tarjeta PNG y configuración operativa. Antes de revisar se leyó la documentación bajo `docs/`, especialmente `TODO.md`, `COMPARADOR.md`, `CORTAFUEGOS.md`, `PRUEBAS_DESPLIEGUE.md`, `CODING_STANDARDS.md` y reviews previos. No revisé `_not_in_use` y no repito pendientes ya marcados en `docs/TODO.md`; por eso el bug de W-L/WPCT de carrera queda fuera de estos findings.

## Resumen Ejecutivo

Encontré tres issues nuevos:

1. `ruff` falla sobre archivos nuevos/relevantes, incluyendo un test duplicado que Python sobrescribe.
2. El contrato de oficio para relevistas no llega completo desde generador/endpoint hasta el cálculo.
3. El PNG del comparador no está cacheado aunque la documentación lo declara como defensa contra abuso.

Los tests funcionales Python del comparador pasaron, pero la suite JS no pudo arrancar por una dependencia opcional faltante de Rollup en `node_modules`.

## Persona 1: Python Principal Developer

### Finding DEV-01 - La rama no está limpia para `ruff` y un test queda sobrescrito

Severidad: P2

Evidencia:

- `dglweb/profiles/comparaciones.py:285` y `dglweb/profiles/comparaciones.py:325` usan `zip()` sin `strict=`.
- `dglweb/stats/comparador.py:160` define `TemporadasInsuficientes`, que viola la convención de nombres de excepciones configurada.
- `dglweb/stats/tarjeta.py:105`, `dglweb/stats/tarjeta.py:124`, `dglweb/stats/tarjeta.py:182` y `dglweb/stats/tarjeta.py:210` disparan reglas de typing/naming/Unicode.
- `tests/test_generador.py:488` redefine `test_el_paso_de_temporadas_deja_al_js_encontrar_a_los_peloteros`, por lo que la definición previa de `tests/test_generador.py:461` no se recolecta.
- La corrida `ruff check dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py tests/test_comparador.py tests/test_generador.py` falló con 37 errores.

Problema: aunque `pytest` pasa, el quality gate de lint queda rojo. El caso más delicado no es estético: el test duplicado con el mismo nombre hace que Python conserve solo la segunda función, así que una prueba puede parecer presente y no estar ejecutándose.

Sugerencia: corregir el lint antes de mergear: añadir `strict=` donde aplique, renombrar la excepción o excluirla explícitamente si se decide conservar el lenguaje de dominio, partir líneas largas, normalizar Unicode donde `ruff` lo exige, ajustar tipos de `tarjeta.dibujar()` y eliminar la duplicación del test. Si se quiere reexportar el fixture `catalogo`, conviene hacerlo de forma compatible con las reglas actuales o moverlo a `conftest.py`.

Razonamiento: una suite funcional verde no compensa un lint rojo si el proyecto usa `ruff` como puerta de calidad. Además, los tests duplicados erosionan la confianza en la cobertura justo en una feature con muchas reglas de negocio.

## Persona 2: QA / Reliability Engineer

El finding DEV-01 aplica también a QA por la prueba sobrescrita, pero se reporta una sola vez para no duplicarlo.

Sin findings adicionales.

La suite enfocada del comparador pasó:

```text
docker-compose run --rm web pytest --create-db tests/test_comparador.py tests/test_generador.py -q
54 passed in 87.31s
```

Limitación: no pude ejecutar `tests/js/comparador.test.js` ni `tests/js/buscador.test.js`. `vitest` falló al arrancar porque falta `@rollup/rollup-win32-x64-msvc` en `node_modules`.

## Persona 3: Frontend Engineer

Sin findings accionables propios de frontend.

El asistente de comparación tiene estructura semántica razonable: `h1` oculto para accesibilidad, progreso como lista ordenada, errores con `role="alert"` y foco programático, buscador con combobox/listbox y navegación de teclado cubierta por tests JS. El riesgo residual es la verificación no ejecutada de JS mencionada arriba.

## Persona 4: Security Engineer

### Finding SEC-01 - El endpoint de PNG genera imágenes en cada request aunque el diseño promete cache

Severidad: P3

Evidencia:

- `docs/COMPARADOR.md:575` declara: “La imagen se cachea por su ruta y solo se dibuja una vez por combinación”.
- `dglweb/profiles/comparaciones.py:245` genera la previa con `tarjeta.previa(foto)` por request.
- `dglweb/profiles/comparaciones.py:246` genera la tarjeta vertical con `tarjeta.png(foto)` por request.
- `dglweb/stats/tarjeta.py:396` genera la previa llamando otra vez a `png(foto)`, o sea que la previa encadena el dibujo completo de la tarjeta y luego el reescalado.

Escenario de ataque: un bot pide muchas URLs válidas de `tarjeta.png`, alternando jugadores/modos para evitar caché del navegador. Cada request entra a Django, resuelve jugadores, calcula rankings, consulta métricas, abre fuentes/retratos y renderiza PNG con Pillow.

Método de explotación: no necesita autenticación ni payload raro; basta con repetir requests GET sobre rutas públicas. Las modalidades son cerradas, pero el espacio de combinaciones válidas de dos peloteros dominicanos sigue siendo grande.

Impacto de negocio: consumo innecesario de CPU/hilos de gunicorn, degradación de páginas públicas y peor experiencia justo en una feature pensada para viralidad. Si una comparación se comparte mucho, el patrón natural de tráfico golpea el punto más caro.

Sugerencia: implementar caché real por clave canónica de ruta/modo/jugadores, por ejemplo con la caché compartida de Django o con archivos generados bajo un directorio controlado, y añadir `Cache-Control`/ETag apropiados para PNGs. La previa debería reutilizar bytes o una imagen base cacheada en vez de redibujar la tarjeta completa. Agregar un test que pida dos veces la misma tarjeta y verifique que la segunda no llama a `tarjeta.png()`/`tarjeta.previa()`.

Razonamiento: esto alinea la implementación con la defensa documentada y convierte una ruta computacionalmente cara en una respuesta barata y repetible.

## Persona 5: Backend Architect

### Finding ARCH-01 - El oficio de abridor/relevista se pierde en el contrato entre generador, endpoint y resultado

Severidad: P2

Evidencia:

- `docs/COMPARADOR.md:69`-`docs/COMPARADOR.md:76` define tres oficios y dice que un relevista se rankea entre relevistas.
- `docs/COMPARADOR.md:278` documenta que “cuenta como temporada” es 30 IP para abridores y 20 IP para relevistas.
- `dglweb/stats/comparador.py:88` implementa esos mínimos distintos.
- `dglweb/profiles/comparaciones.py:223` llama `comparador.inventario(grupo, pelotero.player_id)` sin oficio.
- `dglweb/profiles/comparaciones.py:316` valida “mejores X” con `comparador.inventario(grupo, ...)` sin oficio.
- `dglweb/profiles/comparaciones.py:335`, `dglweb/profiles/comparaciones.py:364` y `dglweb/profiles/comparaciones.py:369` muestran mensajes con `comparador.minimo_de(grupo)`, que para `pitching` cae al mínimo de abridor.
- `dglweb/profiles/comparaciones.py:437` normaliza el par por `player_id` y `dglweb/profiles/comparaciones.py:445` decide `oficio = _oficio_de(izquierda)`.

Problema: el cálculo principal ya sabe trabajar con RP, pero el generador y el endpoint de años siguen preguntando por “pitching” genérico. Eso puede hacer que un relevista con temporadas de 20-29 IP no aparezca como comparable o reciba un error diciendo que no llega a 30 IP, aunque el cálculo de la tarjeta RP sí lo aceptaría con 20 IP. Además, si alguien llega por URL directa a una comparación mixta SP/RP, el oficio usado para ranking depende del jugador que quede a la izquierda después de ordenar por `player_id`, no de una decisión de dominio.

Sugerencia: hacer que `inventario()` acepte `oficio` y propagarlo desde `temporadas_de()` y `_validar()` usando `estado["oficio"]` o `_oficio_de(pelotero)` según corresponda. Para la página de resultado, decidir explícitamente si SP vs RP está permitido. Si está permitido, el oficio no debería depender del orden canónico; si no está permitido, `_oficio()` debe rechazarlo igual que rechaza bateador vs lanzador. Añadir tests para un RP con 25 IP y para una URL SP/RP en ambos órdenes.

Razonamiento: el oficio ya no es una etiqueta visual; define población, umbral y significado del ranking. Si no viaja como parte del contrato, la UI y la tarjeta pueden contradecirse.

## Persona 6: Experto en Beisbol y Sabermetría

El finding ARCH-01 es también el finding sabermétrico principal.

No detecté otros usos incorrectos nuevos de estadísticas. Las decisiones de excluir Ligas Negras del universo del comparador, no rankear derrotas, no rankear WPCT mientras el bug de carrera esté abierto, ponderar wOBA/wRC+/FIP/ERA- y separar abridores de relevistas son razonables. El problema es que esa última decisión todavía no llega de forma consistente a todas las rutas.

## Persona 7: Docker / fail2ban / nginx

Sin findings accionables.

Revisé `Dockerfile.prod`, `docker-compose.yml`, `deploy/stack.yml`, `deploy/nginx-dglweb.conf`, `deploy/fail2ban/jail.d/nginx.local` y `deploy/fail2ban/filter.d/nginx-404-scan.conf`. La app de producción sigue publicada solo en loopback, los secretos requeridos fallan al arrancar si faltan, nginx mantiene límites para HTML/salud/estáticos, y fail2ban conserva la decisión documentada de no activar `nginx-limit-req`.

Nota: la amplitud de `nginx-404-scan` y su modo de observación siguen ya documentados en `docs/TODO.md`/`docs/CORTAFUEGOS.md`, así que no los repito como issue nuevo.

## Verificaciones Ejecutadas

```text
docker-compose config --quiet
Exit 0; warning local: no se pudo leer C:\Users\aperd\.docker\config.json.

docker-compose run --rm web pytest --create-db tests/test_comparador.py tests/test_generador.py -q
54 passed in 87.31s

docker-compose run --rm --no-deps web mypy dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py
Success: no issues found in 4 source files

docker-compose run --rm --no-deps web python manage.py check
System check identified no issues (4 silenced).

docker-compose run --rm --no-deps web ruff check dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py tests/test_comparador.py tests/test_generador.py
Falló con 37 errores.

git diff --check
Sin errores.
```

No ejecutado satisfactoriamente:

```text
node .\node_modules\vitest\vitest.mjs run tests\js\comparador.test.js tests\js\buscador.test.js
Startup Error: Cannot find module @rollup/rollup-win32-x64-msvc.
```

## Conclusión

No bloquearía por el diseño general del comparador: la idea está bien encaminada y los tests funcionales pasan. Sí bloquearía el merge hasta corregir `DEV-01`, porque el lint rojo y el test sobrescrito dejan el cambio por debajo del estándar del repo. Después cerraría `ARCH-01` antes de publicar comparaciones de relevistas, y `SEC-01` antes de empujar tráfico real hacia las tarjetas PNG.
