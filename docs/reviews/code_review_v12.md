# Code Review v12

Fecha: 2026-07-29

Alcance: revisión del proyecto después de leer todos los archivos `.md` bajo `docs/`, incluido
`TODO.md`, los documentos de autoridad, operación, rendimiento, sabermetría y los reviews anteriores.

Reglas aplicadas:

- No se consideran findings los placeholders ni los datos falsos conocidos de la portada.
- No se repiten issues que están marcados como pendientes en `docs/TODO.md`.
- Un mismo problema aparece una sola vez, bajo la persona que mejor representa su riesgo principal.
- No se modificó código fuente. Este documento es el único entregable del review.

Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P2 | SEC-01 | Security Engineer | Los health checks públicos pueden ocupar simultáneamente todos los hilos de Gunicorn durante una caída de sus upstreams. |
| P2 | SAB-01 | Experto en béisbol y sabermetría | La implementación de Game Score v2 omite la penalización por boletos. |
| P3 | QA-01 | QA / Reliability Engineer | `/health/proxy` devuelve 500 cuando el proxy responde 200 con un cuerpo que no es JSON válido. |
| P3 | SAB-02 | Experto en béisbol y sabermetría | `(Game Score - 50) / 3` no convierte Game Score en carreras sobre promedio. |

## Persona 1 - Python Principal Developer

No encontré un hallazgo nuevo y exclusivo para esta persona después de filtrar `TODO.md` y deduplicar.

El manejo incompleto de la respuesta del proxy se reporta una sola vez como `QA-01`. La concurrencia
de los health checks se reporta como `SEC-01` porque su consecuencia más seria es permitir agotamiento
de capacidad desde endpoints anónimos.

## Persona 2 - QA / Reliability Engineer

### QA-01 [P3] `/health/proxy` convierte una respuesta inesperada del upstream en un error 500

**Evidencia**

- `dglweb/core/views.py:383-389` captura errores de transporte y códigos distintos de 200, pero llama
  `con_que.json().get(...)` fuera de cualquier validación del cuerpo.
- `httpx.Response.json()` puede lanzar `JSONDecodeError` si un proxy, nginx o página de error devuelve
  HTML con status 200. Un JSON válido que no sea un objeto también falla al intentar `.get()`.
- `tests/test_pipeline_health.py:553-646` cubre errores de conexión, status y visibilidad del detalle,
  pero no cubre un 200 con cuerpo inválido o con un tipo JSON inesperado.
- Reproducción realizada durante este review, con `httpx.get` mockeado para devolver
  `200 <html>upstream error</html>`: `/health/proxy` respondió 500 y registró un `JSONDecodeError` en
  `dglweb/core/views.py:389`.

**Riesgo**

El monitor sí detectará una respuesta no exitosa, pero el endpoint rompe su contrato de devolver 503
para dependencias no sanas. El 500 genera ruido como error interno de la aplicación, oculta el
diagnóstico correcto y puede disparar alertas equivocadas sobre un bug de Django cuando el fallo real
está en el proxy.

**Mejora sugerida**

Validar el cuerpo dentro del mismo bloque de manejo del upstream:

1. Capturar `ValueError`/`JSONDecodeError` al decodificar.
2. Comprobar que el resultado sea un diccionario antes de leer `version`.
3. Devolver `respuesta("error", 503, ...)` para cuerpo inválido.
4. Agregar tests para HTML con 200, lista JSON con 200 y objeto JSON sin `version`.

**Razonamiento**

Un health check debe degradar de forma predecible ante cualquier respuesta corrupta de la dependencia.
El dato `version` es accesorio; nunca debe tener capacidad de tumbar el propio endpoint de diagnóstico.

## Persona 3 - Frontend Engineer

No encontré un finding frontend nuevo que no fuera un placeholder conocido, una decisión documentada o
un issue ya cubierto por `TODO.md`/reviews anteriores. También se verificó que el arreglo de la carrera
del autocomplete reportada en v11 ya está incorporado, por lo que no se repite.

## Persona 4 - Security Engineer

### SEC-01 [P2] Los health checks públicos permiten un thundering herd que agota los hilos web

**Evidencia**

- `dglweb/core/views.py:369-383` y `dglweb/core/views.py:436-462` implementan el patrón
  `cache.get -> HTTP síncrono con timeout de 5s -> cache.set` para `/health/proxy` y
  `/health/adserver`.
- No hay lock, single-flight ni valor stale entre el miss y el `set`; todas las solicitudes que llegan
  durante la llamada lenta ven el mismo miss y abren su propia conexión al upstream.
- La caché usada es la `default`, que es `LocMemCache` por proceso (`config/settings/base.py:183-209`),
  así que los cuatro workers tampoco comparten el resultado.
- Producción tiene 4 workers por 4 hilos, 16 requests concurrentes (`Dockerfile.prod:74-80` y
  `Dockerfile.prod:103-107`). El límite general permite 20 requests/s con burst de 40
  (`deploy/nginx-limites.conf:30`, `deploy/nginx-dglweb.conf:128-139`), suficiente para ocupar los 16
  hilos antes de que venza el timeout.
- Reproducción concurrente realizada durante este review: 16 solicitudes simultáneas a
  `/health/proxy`, con el upstream mockeado para tardar 200 ms, produjeron **16 llamadas HTTP**. La
  caché no consolidó ninguna.

**Attack scenario**

El proxy de MLB o Revive está lento o caído. Un cliente anónimo mantiene tráfico sobre el health check,
especialmente alrededor de cada expiración de 30 segundos. Las solicitudes normales al sitio compiten
con sondeos que permanecen bloqueados hasta cinco segundos.

**Exploitation method**

No hacen falta credenciales ni payload especial: basta enviar solicitudes concurrentes a
`/health/proxy` o `/health/adserver`. El rate limit actual permite una ráfaga mayor que toda la
capacidad de Gunicorn. Cada miss se amplifica en una conexión saliente independiente.

**Business impact**

Una caída parcial de publicidad o del proxy puede convertirse en una caída total intermitente del
website: los 16 hilos quedan esperando al servicio que precisamente se intenta diagnosticar. También
aumenta la carga sobre un upstream ya degradado y puede producir falsos negativos por timeout en otros
requests.

**Recommended fix**

- Aplicar single-flight con un lock atómico (`cache.add`) y conservar un último estado stale mientras
  una sola solicitud refresca el dato.
- Usar la caché compartida para que los cuatro workers vean el mismo estado y lock. La caché compartida
  por sí sola no corrige la carrera; hacen falta ambas piezas.
- Mejor aún, ejecutar los sondeos fuera del request path mediante un job periódico y hacer que los
  endpoints solo lean el último resultado almacenado.
- Añadir un `limit_req` específico y mucho más bajo para `/health/proxy` y `/health/adserver`; un
  monitor que consulta una vez por minuto no necesita el burst general de las páginas públicas.
- Agregar una prueba concurrente que exija una sola llamada al upstream para N requests simultáneos.

**Razonamiento**

Cachear después de una operación bloqueante reduce frecuencia normal, pero no limita concurrencia en
el momento más peligroso: cuando la dependencia no responde. El health check debe aislar fallos, no
darles un multiplicador dentro del proceso web.

## Persona 5 - Backend Architect

No encontré un finding nuevo y exclusivo para esta persona después del filtro contra el backlog.

El cuello de botella arquitectónico más relevante es el fan-out síncrono de los health checks, pero se
reporta una sola vez como `SEC-01`. Su recomendación incluye separar el sondeo del request path y
compartir el estado entre workers.

## Persona 6 - Experto en béisbol y sabermetría

### SAB-01 [P2] Game Score v2 omite la penalización de dos puntos por boleto

**Evidencia**

- `dglweb/stats/daily.py:21` y `dglweb/stats/daily.py:162-170` declaran e implementan
  `40 + 2*outs + K - 2*H - 3*R - 6*HR`.
- La fórmula de Game Score actualizada por Tom Tango también resta **2 puntos por cada BB**. MLB la
  documenta como `40 + 2*outs + K - 2*BB - 2*H - 3*R - 6*HR`:
  [MLB Glossary - Game Score](https://www.mlb.com/glossary/advanced-stats/game-score).
- La explicación del propio autor presenta igualmente `-2 walks`:
  [Game Score Version 2.0](https://blogs.fangraphs.com/instagraphs/game-score-v2-0/).
- `tests/test_daily.py:110-128` prueba el peso de outs y jonrones, pero no compara dos salidas que solo
  difieran en boletos.

**Uso incorrecto de la estadística**

Cada boleto permitido infla el score implementado en 2 puntos. Una salida con seis BB recibe 12 puntos
de más, lo suficiente para cambiar el orden entre lanzadores y hacer que una actuación cruce el piso
de 50 usado para publicarse como destacada.

**Mejora sugerida**

Agregar `- 2 * _numero(stat, "BB")` a `game_score()`, corregir docstrings y añadir una prueba donde la
misma línea con más boletos obtenga exactamente dos puntos menos por BB. Como `DailyStandout.valor`
persiste el score, reprocesar al menos las jornadas que todavía pueden aparecer en portada y valorar
recalcular la temporada activa para no conservar rankings históricos calculados con otra fórmula.

**Razonamiento**

No es una variante editorial de la métrica: el código la llama explícitamente Game Score v2 de Tango.
Si se usa ese nombre, deben estar todos sus componentes; omitir BB favorece precisamente las salidas con
peor control.

### SAB-02 [P3] Dividir Game Score entre el coeficiente de carreras no lo convierte en carreras sobre promedio

**Evidencia**

- `dglweb/stats/daily.py:60-87` afirma que `(GS - 50) / 3` está "exactamente" en la misma unidad que
  los pesos lineales de bateo, porque Game Score resta tres puntos por carrera.
- `dglweb/stats/daily.py:492` usa esa conversión para ordenar bateadores y lanzadores en una sola lista.
- `tests/test_daily.py:280-312` fija la aritmética `65 -> 5` y el orden resultante, pero no valida que
  cinco sea una estimación de carreras sobre promedio.
- Game Score también asigna puntos a outs, K, BB, hits y HR. Dividir el score completo entre el
  coeficiente de `R` divide todos esos componentes, no aísla carreras prevenidas.
- Tango explica además que la constante puede ajustarse por temporada para alinear el promedio en 50;
  en 2015 habría sido 38 en vez de 40. Por tanto, 50 no es una referencia universal "por definición"
  de la versión sin ajustar.

**False assumption**

Que una expresión lineal se vuelve una métrica de carreras al dividirla por el coeficiente de uno de
sus términos. Con el mismo razonamiento, un ponche pasaría a valer un tercio de carrera, un out dos
tercios y un jonrón permitido ocho tercios por la suma de hit y HR; esos valores no son una escala de
runs above average calibrada.

**Impacto**

El orden mezclado de la portada presenta como comparación sabermétrica una equivalencia que no existe.
Puede colocar una apertura por encima o por debajo de un juego ofensivo con una precisión aparente de
"carreras" y trasladar al lector una conclusión falsa sobre el valor relativo de ambas actuaciones.

**Mejora sugerida**

Elegir explícitamente uno de estos contratos:

1. Volver a listas separadas de bateo y pitcheo, conservando Game Score como ranking interno de
   lanzadores.
2. Si la lista única es requisito de producto, expresar ambos oficios con un modelo realmente común,
   por ejemplo run expectancy/RE24 o WPA; para pitcheo también puede construirse una estimación de
   runs above average con innings y entorno de liga/parque.
3. Si se conserva la heurística actual por decisión editorial, renombrarla como puntaje mixto,
   eliminar la afirmación de que son carreras y calibrarla empíricamente. No debería llamarse
   conversión sabermétrica de unidades.

Agregar tests contra ejemplos de referencia del modelo elegido. La igualdad `en_carreras("pitcheo",
65) == 5` solo prueba la implementación, no la validez de la unidad.

**Razonamiento**

Game Score sirve para resumir y ordenar aperturas; no fue diseñado como una estimación aditiva de
carreras creadas o prevenidas ni para comparar directamente un bateador con un lanzador. Una lista
mixta necesita una métrica con el mismo significado en ambos lados, no solo números de magnitud
parecida.

## Verificación

- Ruff: `All checks passed`.
- mypy: `Success: no issues found in 224 source files`.
- Health checks dirigidos: 5 tests pasaron.
- `tests/test_daily.py`: 35 tests pasaron; esta suite confirma el coverage gap de BB, no la corrección
  sabermétrica de la fórmula actual.
- La suite completa no pudo validarse limpiamente: una sesión externa permanecía `idle in transaction`
  sobre `test_dglweb` e impedía recrear la base. No se terminó esa sesión para no alterar procesos del
  usuario. Un intento con `--reuse-db` encontró una base de pruebas incompleta, sin el `Site` inicial de
  Wagtail, por lo que los errores de artículos no se atribuyen al código revisado.
- Las pruebas JavaScript no arrancaron porque falta el binario opcional de Rollup para Windows y el
  entorno no permite descargarlo. No se modificaron dependencias del proyecto.

