# Code Review v23

Fecha: 2026-08-13

Alcance: revisión de los cambios posteriores a `code_review_v22.md`, con foco en el comparador/generador,
tarjeta PNG, caché de imágenes, contrato SP/RP y documentación asociada. Antes de revisar se leyeron los
`.md` bajo `docs/`, especialmente `TODO.md`, `COMPARADOR.md`, `CODING_STANDARDS.md`,
`PRUEBAS_DESPLIEGUE.md`, `CORTAFUEGOS.md` y los reviews previos. No revisé `_not_in_use` y no repito
pendientes ya marcados en `docs/TODO.md`.

## Resumen Ejecutivo

Las correcciones de v22 están mayormente bien encaminadas:

1. `ruff`, `mypy`, `manage.py check` y los tests Python enfocados pasan.
2. El contrato de relevistas ya viaja al endpoint de temporadas y al generador.
3. La comparación directa SP/RP ahora se rechaza en backend y tiene prueba.
4. La tarjeta PNG ya usa caché de Django y la previa reutiliza los bytes de la vertical.
5. El supuesto bug W-L/WPCT quedó cerrado correctamente como falso diagnóstico en `docs/TODO.md`; no lo
   reabro.

Encontré tres issues que todavía conviene corregir antes de dar el comparador por cerrado.

## Persona 1: Python Principal Developer

### Finding DEV-01 - En modo temporada, el umbral de tasas puede salir del año equivocado

Severidad: P2

Evidencia:

- `dglweb/stats/comparador.py:407` documenta que en temporada se resuelve el umbral de ese año.
- `dglweb/stats/comparador.py:551` calcula una sola `formula` con `izquierda[1] or derecha[1]`.
- `dglweb/stats/comparador.py:562` usa esa misma fórmula para cada temporada candidata de la población.
- `dglweb/stats/comparador.py:574` usa esa misma fórmula para validar ambos lados.
- `dglweb/stats/comparador.py:458` hace que `_umbral_de_la_bolsa()` devuelva el umbral fijo para todo lo
  que no sea `MODO_MEJORES`.
- `dglweb/stats/comparador.py:610` confirma que en `MODO_TEMPORADA` la población aporta una bolsa por
  cada año jugado.

Problema: si se compara una temporada corta contra una normal, por ejemplo 2020 contra 2021, toda la
población y ambos lados se miden con el umbral del primer año disponible en la ruta. Si el año izquierdo
es 2020, temporadas normales de la población podrían clasificar con un umbral demasiado bajo. Si el año
izquierdo es 2021, temporadas de 2020 que sí deberían clasificar podrían quedarse sin ranking por un
umbral demasiado alto.

Sugerencia: mover la lógica anual a `_umbral_de_la_bolsa()` también para `MODO_TEMPORADA`: cuando la
bolsa tenga una sola temporada, resolver `qualifier.resolve_season()` con `bolsa[0]["season"]`. La
fórmula fija puede quedar para carrera completa. Añadir un test con una métrica de tasa comparando 2020
vs 2021 en ambos órdenes, y una temporada candidata de la población que solo clasifique con su propio
umbral.

Razonamiento: el bug es sutil porque el resultado parece plausible: no rompe la página, solo cambia quién
compite por un puesto histórico. En una tarjeta sabermétrica, un ranking plausible pero mal calificado es
peor que un error visible.

## Persona 2: QA / Reliability Engineer

### Finding QA-01 - La prueba de caché no verifica el comportamiento 304 que prometen los comentarios

Severidad: P3

Evidencia:

- `dglweb/profiles/comparaciones.py:281`-`dglweb/profiles/comparaciones.py:284` dicen que una recarga
  responde 304 gracias al `ETag`.
- `config/settings/base.py:62` lista el middleware activo y no incluye `django.middleware.http.ConditionalGetMiddleware`.
- `tests/test_generador.py:560` solo verifica que el header `ETag` exista.

Problema: exponer un `ETag` no basta por sí solo para devolver `304 Not Modified`. Sin middleware
condicional o manejo explícito de `If-None-Match`, una recarga validada puede seguir recibiendo un `200`
con todo el PNG.

Sugerencia: añadir una prueba que haga una segunda petición con `HTTP_IF_NONE_MATCH=primera["ETag"]` y
espere `304` si ese es el contrato real. Luego implementar el manejo con `ConditionalGetMiddleware`,
`@condition`, o lógica explícita en `tarjeta_png()`. Si se decide que `304` no es requisito, ajustar el
comentario para que prometa solo caché por `max-age`.

Razonamiento: la caché de servidor ya reduce el trabajo caro, pero el contrato documentado habla también
del navegador/proxy. El test actual da una falsa sensación de cobertura porque comprueba el header, no la
negociación condicional.

## Persona 3: Frontend Engineer

Sin findings propios de frontend en esta ronda.

El flujo del asistente mantiene los controles esperados, el endpoint de temporadas ahora devuelve el
oficio/minimo correcto para RP, y la comparación SP/RP se bloquea antes de generar una URL inválida.

Limitación: no pude ejecutar la suite JS local. Vitest no arranca porque en `node_modules` falta
`@rollup/rollup-win32-x64-msvc`; solo están instalados los paquetes opcionales de Rollup para Linux.

## Persona 4: Security Engineer

### Finding SEC-01 - La caché del PNG se puede multiplicar con rutas no canónicas

Severidad: P3

Evidencia:

- `docs/COMPARADOR.md:611` dice que la clave usa el `request.path` canónico.
- `dglweb/profiles/comparaciones.py:269` construye la clave con el `request.path` crudo antes de resolver
  o normalizar la comparación.
- `dglweb/profiles/comparaciones.py:453`-`dglweb/profiles/comparaciones.py:457` resuelven el jugador por
  el id extraído del slug, no por igualdad estricta del slug completo.
- `dglweb/profiles/comparaciones.py:542`-`dglweb/profiles/comparaciones.py:546` sí redirige la página HTML
  a la ruta canónica, pero `tarjeta_png()` no hace esa redirección.

Escenario de abuso: un bot puede pedir directamente `tarjeta.png` con el par en orden inverso o con slugs
viejos/inventados que conserven el id final. Todas esas rutas resuelven a la misma comparación real, pero
entran como claves distintas y fuerzan redibujos hasta desplazar las 200 entradas útiles de
`dgl_cache_imagenes`.

Sugerencia: resolver primero la comparación y construir la clave desde los slugs canónicos, el modo
canónico y si es `previa` o vertical. Otra opción es aplicar a `tarjeta_png()` la misma redirección
permanente que usa `comparar()`. Para cerrar el hueco, añadir una prueba que pida la misma tarjeta por
ruta invertida/no canónica y verifique que no genera una segunda entrada ni redibuja.

Razonamiento: la caché se agregó como defensa de rendimiento ante tráfico viral o automatizado. Si la
clave acepta variantes de path que representan el mismo dato, la defensa sigue funcionando para usuarios
normales pero no para tráfico adversarial.

## Persona 5: Backend Architect

### Finding ARCH-01 - La documentación y un comentario interno todavía contradicen la regla SP/RP

Severidad: P3

Evidencia:

- `docs/COMPARADOR.md:86` todavía dice que un abridor contra un relevista sí se permite y que manda el
  oficio del primero.
- `dglweb/profiles/comparaciones.py:482` ahora rechaza esa comparación con `Http404`.
- `dglweb/profiles/comparaciones.py:515` conserva un comentario viejo que vuelve a decir que la
  comparación mixta es legítima y que manda el primero.
- `tests/test_generador.py:523`-`tests/test_generador.py:528` ya fijan el comportamiento nuevo de rechazo.

Problema: el código y las pruebas adoptaron la decisión correcta, pero el contrato escrito conserva la
decisión anterior. Eso deja dos fuentes de verdad: una para quien lee el documento y otra para quien lee
o ejecuta el backend.

Sugerencia: actualizar `docs/COMPARADOR.md` para explicar que SP y RP son poblaciones distintas y que la
comparación mixta se rechaza a propósito. También conviene borrar o reescribir el comentario viejo dentro
de `_resolver()`.

Razonamiento: esta fue una decisión de dominio, no un detalle técnico. Debe quedar documentada como tal
para que no se “corrija” de vuelta en una refactorización futura.

## Persona 6: Experto en Beisbol y Sabermetría

El finding DEV-01 es el principal riesgo sabermétrico: los rankings de tasa en modo temporada deben usar
el umbral del año de cada temporada, especialmente por 1981, 1994 y 2020.

El resto de las decisiones revisadas son consistentes: no rankear derrotas, mostrar WPCT pero rankearlo
solo para abridores, separar relevistas de abridores, ignorar postemporada en el comparador regular, y
usar `season_totals()` para no duplicar temporadas repartidas entre clubes.

## Persona 7: Docker / fail2ban / nginx

Sin findings nuevos de Docker, fail2ban o nginx.

El cambio sí agrega una tabla de caché nueva (`dgl_cache_imagenes`) creada por migración, y
`docs/COMPARADOR.md` ya documenta que los cambios de diseño de tarjeta requieren limpiar esa tabla. No
vi cambios en reglas de publicación, puertos o fail2ban.

## Estado de los Findings de v22

- `DEV-01`: corregido satisfactoriamente. `ruff` pasa en los archivos revisados y el test duplicado quedó
  como una sola definición.
- `SEC-01`: corregido en lo esencial. El PNG ya usa caché compartida y la previa reutiliza la vertical.
  Queda el nuevo finding `SEC-01` de v23 sobre canonicalización de la clave.
- `ARCH-01`: corregido en backend. El generador y el endpoint respetan oficio, y SP/RP se rechaza. Queda
  el nuevo finding `ARCH-01` de v23 porque documentación/comentario aún dicen lo contrario.

## Verificaciones Ejecutadas

```text
docker-compose run --rm web pytest --create-db tests/test_comparador.py tests/test_generador.py -q
63 passed in 100.51s

docker-compose run --rm --no-deps web ruff check dglweb/stats/comparador.py dglweb/stats/tarjeta.py dglweb/profiles/comparaciones.py dglweb/players/search.py tests/test_comparador.py tests/test_generador.py
All checks passed!

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
