# Code Review v21

Fecha: 2026-08-04

Alcance: verificacion posterior a las correcciones recientes de lideres "Todas", efemerides colectivas, widget de portada "Un dia como hoy" y configuracion operativa. Antes de revisar se leyeron los `.md` bajo `docs/`, incluyendo `TODO.md`, `EFEMERIDES.md`, `CORTAFUEGOS.md`, `PRUEBAS_DESPLIEGUE.md`, `CODING_STANDARDS.md` y reviews previos. No repito como finding ningun punto que ya aparece pendiente en `docs/TODO.md`.

## Resumen ejecutivo

Los issues revisados quedaron corregidos satisfactoriamente en lo funcional:

- Las gestas colectivas ahora usan `participantes` y aparecen en los perfiles de todos los jugadores involucrados sin duplicar el calendario.
- La vista de lideres incorpora "Todas", excluye temporadas acortadas documentadas, oculta colas poco utiles para conteos ofensivos y conserva la temporada visible en rankings historicos por temporada.
- El widget "Un dia como hoy" esta conectado a portada, tiene HTML, CSS, JS y cobertura Python; la logica JS quedo cubierta por tests de archivo, aunque no pude ejecutarlos en esta sesion por entorno local de Node.
- Docker/nginx/fail2ban siguen alineados con la documentacion operativa; los riesgos abiertos ya estan reflejados en `TODO.md`.

Encontré un solo finding nuevo, de severidad baja, relacionado con determinismo de ordenamiento.

## Persona 1: Python Principal Developer

Sin findings accionables propios de esta persona.

El codigo Python revisado mantiene consultas acotadas, evita N+1 en el widget con `in_bulk()`, usa funciones auxiliares de alcance claro y conserva pruebas enfocadas para los bordes principales. `ruff`, `mypy` y `manage.py check` pasaron sobre los archivos relevantes.

Riesgo residual no bloqueante: `dglweb.stats.efemerides.del_dia()` todavia retorna diccionarios flexibles hacia plantilla. Es consistente con el estilo Django del proyecto, pero si el contrato crece convendria formalizarlo con `TypedDict` para reducir regresiones silenciosas.

## Persona 2: QA / Reliability Engineer

### Finding QA-01 - Orden no deterministico en "Todas" cuando un mismo jugador empata consigo mismo

Severidad: P4 baja

Evidencia:

- `dglweb/profiles/leaderboards.py:434` ordena los candidatos de todos los tiempos por valor y `row.player.full_name`.
- `dglweb/profiles/leaderboards.py:486` carga candidatos con `order_by("rank", "player__full_name")`, sin incluir `season`.
- `templates/profiles/leaders.html:192` y `templates/profiles/leaders.html:200` muestran la temporada cuando `board.shows_season` esta activo.

Problema: si el mismo jugador tiene dos temporadas con el mismo valor en una metrica de "Todas", ambas filas tienen la misma llave de ordenamiento visible. El ranking numerico seria correcto, pero el orden relativo de esos dos anos podria depender del orden entregado por la base de datos o de detalles de insercion. Como la temporada se renderiza en la tabla, esa inestabilidad puede aparecer en UI, snapshots, cache o diffs de pruebas.

Sugerencia: agregar un desempate explicito y editorialmente elegido en `_de_todos_los_tiempos`, por ejemplo temporada descendente o ascendente, y luego `player_id` como llave final estable. Tambien agregaria una prueba con el mismo jugador, dos temporadas y el mismo valor para fijar el comportamiento esperado.

Razonamiento: no cambia el modelo sabermetrico ni los ranks; solo hace reproducible el orden de filas empatadas.

## Persona 3: Frontend Engineer

Sin findings accionables.

La plantilla del widget y el CSS contemplan estados con y sin JS, vista movil de una tarjeta, vista desktop de dos tarjetas, controles, puntos, pausa visual y `prefers-reduced-motion`. La tabla de lideres muestra la columna "Temporada" solamente cuando corresponde a "Todas", lo cual evita confundir rankings de carrera con rankings por temporada.

Limitacion de verificacion: no hice inspeccion visual con navegador/captura en esta vuelta. La cobertura de HTML/CSS/JS parece suficiente para el cambio, pero una pasada visual responsive sigue siendo el siguiente nivel de confianza antes de publicar.

## Persona 4: Security Engineer

Sin findings accionables.

No observe nuevas entradas de usuario peligrosas, SQL dinamico desde request, secretos hardcodeados, deserializacion insegura ni `subprocess`/`eval` sospechosos en el alcance revisado. Los valores sensibles de produccion siguen viniendo de variables de entorno y las plantillas dependen del escaping por defecto de Django.

## Persona 5: Backend Architect

Sin findings accionables adicionales.

La solucion de `participantes` mantiene una sola fuente para cada efemeride y evita duplicacion fisica de gestas colectivas. En lideres, la separacion entre alcance de temporada, carrera y "Todas" quedo contenida en `leaderboards.py` sin propagar decisiones de presentacion a modelos o loaders.

El finding QA-01 tambien aplica arquitectonicamente como mejora de reproducibilidad, pero lo reporto una sola vez para evitar duplicado entre personas.

## Persona 6: Experto en beisbol y sabermetria

Sin findings accionables.

Las decisiones revisadas son defendibles desde baseball/sabermetria:

- Excluir 1981, 1994 y 2020 de "Todas" evita comparar temporadas estructuralmente acortadas contra temporadas completas.
- Conservar 1995 es razonable porque no es equivalente en duracion/contexto competitivo a 1994 o 2020.
- Omitir colas de conteos ofensivos como HR, SB, HBP, SH o SF en "Todas" evita producir "peores lideres" que no tienen lectura sabermetrica util.
- Excluir la temporada actual de colas mientras sigue viva evita falsos negativos por conteos incompletos.
- Las gestas colectivas pertenecen al perfil de todos los participantes sin convertir el evento historico en multiples eventos.

No detecte falso entendimiento de estadisticas ni assumptions baseball incorrectos nuevos.

## Persona 7: Docker / fail2ban / nginx

Sin findings accionables.

`deploy/stack.yml` mantiene el bind de la app en `127.0.0.1`, nginx conserva allowlists para superficies administrativas, fail2ban sigue en la configuracion documentada y los riesgos operativos conocidos permanecen cubiertos por `docs/TODO.md` o `docs/CORTAFUEGOS.md`. No repito el punto de observacion de fail2ban porque ya esta pendiente en `TODO.md`.

## Verificaciones ejecutadas

```text
docker-compose config --quiet
Exit 0; mostro un warning local de acceso a C:\Users\aperd\.docker\config.json, pero la configuracion valido.

docker-compose run --rm --no-deps web ruff check dglweb/profiles/leaderboards.py dglweb/stats/season_window.py dglweb/stats/efemerides.py dglweb/core/views.py dglweb/profiles/tabs.py dglweb/stats/staticdata/loaders.py tests/test_leaders_page.py tests/test_dia_como_hoy.py
All checks passed!

docker-compose run --rm --no-deps web mypy dglweb/profiles/leaderboards.py dglweb/stats/season_window.py dglweb/stats/efemerides.py
Success: no issues found in 3 source files

docker-compose run --rm --no-deps web python manage.py check
System check identified no issues (4 silenced).

docker-compose run --rm web pytest --create-db tests/test_leaders_page.py tests/test_dia_como_hoy.py tests/test_efemerides_loader.py tests/test_efemerides_tab.py tests/test_efemerides_csv_real.py -q
106 passed in 50.05s

git diff --check
Sin errores de whitespace; solo warnings de normalizacion CRLF/LF en archivos ya tocados.
```

No pude ejecutar los tests JS de `tests/js/dia_como_hoy.test.js`: `npm` no estaba disponible en PATH y `pnpm test` intento resolver dependencias desde la red restringida, fallando al descargar `jsdom`. Por eso no cuento esa suite como verificada en esta revision.

## Conclusión

Las correcciones fueron satisfactorias. No bloquearia el merge por el finding QA-01, pero si conviene cerrar ese desempate para que los lideres "Todas" sean 100% reproducibles cuando existan empates exactos del mismo jugador entre temporadas.
