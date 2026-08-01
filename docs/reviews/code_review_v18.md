# Code Review v18

Fecha: 2026-08-01

Alcance: verificación de las correcciones hechas después de `code_review_v17.md`. Antes de revisar se
leyeron los `.md` bajo `docs/`, incluyendo `TODO.md` y el review anterior. No se modificó código
fuente; este archivo es el único entregable.

Reglas aplicadas:

- No se reabren findings cerrados si la corrección y la prueba cubren el caso.
- No se repiten asuntos ya documentados en `docs/TODO.md`.
- No se reabre la decisión consciente de dejar fuera las Ligas Negras de ciertos liderazgos.
- Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resultado

No encontré findings nuevos. Los tres findings de `code_review_v17.md` aparecen corregidos.

## Persona 1 - Python Principal Developer

Sin findings nuevos.

**Verificación del cierre de DEV-01 de v17**

- `dglweb/stats/ventana.py:137-139` ya documenta `CORTES` como seis constantes: p85 y p15 para
  `bateo`, `abridor` y `relevista`.
- La documentación ahora coincide con la estructura real de `CORTES`.

## Persona 2 - QA / Reliability Engineer

Sin findings nuevos.

**Verificación del cierre de QA-01 de v17**

- `dglweb/stats/ventana.py:676` cambia `portada()` para recibir `hoy: date | None`.
- `dglweb/stats/management/commands/build_window_standouts.py:63` llama `ventana.portada(hasta)`, así
  que la muestra del comando usa la misma fecha que la ventana reproducida.
- `dglweb/stats/management/commands/build_window_standouts.py:67-70` diferencia la causa cuando no se
  puede mostrar: calendario fuera de ventana vs nadie cruzó corte.
- `tests/test_ventana.py:568-580` cubre que la muestra de reproducción use la fecha de la ventana.

Nota menor: la prueba valida el comportamiento a través de `ventana.portada(hasta)`, no con
`call_command("build_window_standouts", "--hasta", ...)`. Para el tamaño del cambio lo considero
suficiente, porque el command solo pasa el parámetro y no contiene lógica adicional compleja.

## Persona 3 - Frontend Engineer

Sin findings nuevos. Los cambios revisados no tocan HTML/CSS/JS de la portada ni el comportamiento de
despliegue móvil.

## Persona 4 - Security Engineer

Sin findings nuevos. No vi cambios que amplíen superficie pública, manejo de secretos, SQL dinámico,
deserialización insegura ni contratos de visibilidad.

## Persona 5 - Backend Architect

Sin findings nuevos. La función `portada(hoy=...)` preserva el comportamiento de producción al dejar
el parámetro como opcional y permite reproducibilidad explícita para el comando.

## Persona 6 - Experto en béisbol y sabermetría

Sin findings nuevos.

**Verificación del cierre de SAB-01 de v17**

- `dglweb/stats/ventana.py:448-452` ya exige que el relevo sea el uso dominante antes de permitir el
  fallback a `relevista`.
- `tests/test_ventana.py:542-552` cubre que un swingman con mitad aperturas no entre por la puerta de
  relevo.
- `tests/test_ventana.py:555-559` cubre que el opener real siga entrando como relevista.
- `tests/test_ventana.py:562-565` cubre que el relevista puro no se vea afectado.

La decisión sabermétrica queda coherente: primero se intenta clasificar al abridor real por IP, y solo
se permite caer a relevista cuando las salidas de relevo dominan la ventana.

## Persona 7 - Docker / fail2ban / nginx

Sin findings nuevos. Las validaciones de compose pasaron y no aparecieron nuevas rutas rotas en la
revisión de docs operativos.

## Verificación Ejecutada

- Lectura de `.md` bajo `docs/`, incluyendo `docs/TODO.md` y `docs/reviews/code_review_v17.md`.
- `docker compose run --rm web pytest --reuse-db tests/test_ventana.py tests/test_visibilidad_widgets.py`:
  **50 passed**.
- `docker compose run --rm --no-deps web ruff check .`: **All checks passed**.
- `docker compose run --rm --no-deps web mypy .`: **Success, 233 source files**.
- `docker compose -f deploy/stack.yml config -q` con variables dummy: OK.
- `docker compose -f deploy/postgres/stack.yml config -q` con variables dummy: OK.
- `docker compose -f deploy/adserver/stack.yml config -q`: OK.
- `git diff --check`: sin errores.
