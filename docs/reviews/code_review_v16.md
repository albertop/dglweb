# Code Review v16

Fecha: 2026-08-01

Alcance: nueva revisión del estado actual después de leer los `.md` bajo `docs/`, con énfasis en las
correcciones hechas después de `code_review_v15.md`. No se modificó código fuente; este archivo es el
único entregable.

Reglas aplicadas:

- No se repiten asuntos que ya están en `docs/TODO.md` como pendientes.
- No se reabre la decisión consciente de dejar fuera las Ligas Negras de ciertos liderazgos.
- Si varias personas detectan el mismo problema, aparece una sola vez bajo la persona que mejor
  representa el riesgo principal.
- Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P2 | DEV-01 | Python Principal Developer | Si el denominador de juegos sale en cero, el umbral de bateadores y abridores también queda en cero. |
| P3 | ARCH-01 | Backend Architect | La migración marca toda foto vieja de `WindowStandout` como relevista hasta el siguiente rebuild. |
| P3 | SAB-01 | Experto en béisbol y sabermetría | `GS > 0` captura abridores, pero también puede expulsar opener/bulk relievers de la población correcta. |
| P4 | DEV-02 | Python Principal Developer | El contrato dice “no recortar en servidor”, pero `calcular()` todavía trunca `linea` a 160 caracteres. |
| P4 | OPS-01 | Docker / fail2ban / nginx | Queda una referencia documental vieja a `deploy/fail2ban-nginx.local`. |

No se encontraron findings P1.

## Persona 1 - Python Principal Developer

### DEV-01 [P2] El denominador cero convierte los umbrales en cero

**Evidencia**

- `dglweb/stats/ventana.py:360` calcula los juegos del equipo desde los splits de bateo.
- `dglweb/stats/ventana.py:376-377` devuelve `0` cuando no hay splits.
- `dglweb/stats/ventana.py:399-403` usa `PA_POR_JUEGO * juegos` e `IP_POR_JUEGO * juegos` sin
  proteger `juegos <= 0`.
- `tests/test_ventana.py:54-58` cubre que la ventana vacía no divide por cero, pero no cubre qué hace
  `_califica()` ni `calcular()` con ese denominador.

**Bug / edge case**

Si el proxy devuelve una respuesta parcial, por ejemplo bateo vacío pero pitcheo con filas, `juegos`
queda en `0`. Con eso:

- un bateador con `PA` ausente o `PA = 0` califica como `bateo`, porque `0 >= 3.1 * 0`;
- un pitcher con `GS > 0` y `outsPitched` ausente o `0` califica como `abridor`, porque `0 >= 1.0 * 0`.

El caso más peligroso no es la pretemporada limpia sin datos, sino una corrida en temporada con payload
parcial que termina reemplazando la foto transaccional por candidatos que no pasaron un umbral real.

**Mejora sugerida**

Hacer explícito el contrato cuando `juegos <= 0`: o bien `calcular()` debe abortar/no guardar nada y
registrar la corrida como fallida si no puede inferir juegos del equipo, o `_califica()` debe devolver
`""` para bateadores y abridores mientras el denominador no exista.

Añadir pruebas directas:

- `_califica({"PA": "0"}, "hitting", juegos=0) == ""`;
- `_califica({"GS": "1", "outsPitched": "0"}, "pitching", juegos=0) == ""`;
- `calcular()` con splits de bateo vacíos y splits de pitcheo presentes no publica una foto falsa.

**Razonamiento**

Un denominador desconocido no es un denominador de cero juegos jugados. Es una señal de dato incompleto.
Fail closed aquí evita que una dependencia externa convierta un guard defensivo contra división por cero
en una autorización para publicar cualquier fila.

### DEV-02 [P4] El código todavía recorta la línea aunque el contrato dice lo contrario

**Evidencia**

- `dglweb/stats/ventana.py:263` documenta que la línea no se recorta en el servidor.
- `tests/test_ventana.py:286-307` prueba esa decisión en `linea_de_bateo()`.
- `dglweb/stats/ventana.py:461` guarda `"linea": describir(stat)[:160]`.
- `dglweb/stats/models.py:1789` define `WindowStandout.linea` con `max_length=160`.

**Riesgo**

Hoy las líneas reales parecen bastante más cortas que 160 caracteres, así que no lo subo como bug de
usuario. El problema es de contrato: el test valida la función de formato, pero el camino real de
persistencia todavía tiene un truncado silencioso.

**Mejora sugerida**

Elegir una sola verdad:

- si la línea debe poder ir completa, subir el `max_length` o usar `TextField`, quitar el slice y
  añadir una prueba sobre `calcular()`;
- si 160 es el límite deliberado de persistencia, cambiar los comentarios y el test para decir
  “no se recorta por cantidad de estadísticas, solo por límite técnico de almacenamiento”.

**Razonamiento**

Las decisiones editoriales de este módulo están muy bien documentadas. Precisamente por eso conviene
que el código de producción y las pruebas hablen el mismo idioma.

## Persona 2 - QA / Reliability Engineer

No encontré un finding QA independiente nuevo. La corrección principal de v15 quedó cubierta:
`tests/test_visibilidad_widgets.py:184-221` ahora prueba que `WindowStandout` respeta jugadores
ocultos en la punta de arriba, en la de abajo y cuando el único candidato está oculto.

El hueco de prueba más importante está reportado como DEV-01 porque el defecto nace en la lógica de
umbral, aunque QA debería cubrirlo con payloads parciales del proxy.

## Persona 3 - Frontend Engineer

No encontré un finding frontend nuevo. La mecánica del widget sigue apoyándose en el mismo patrón de
plantilla compartida, despliegue móvil y tooltip por truncamiento visual. No vi evidencia de solape,
IDs duplicados o estado ARIA roto en esta ronda.

## Persona 4 - Security Engineer

No encontré un finding de seguridad nuevo. La superficie pública que sí tenía ángulo de privacidad en
v15, jugadores ocultos reapareciendo en la ventana, ahora usa el mismo contrato de visibilidad que los
otros widgets.

## Persona 5 - Backend Architect

### ARCH-01 [P3] La migración puede publicar pitchers viejos con la clase equivocada hasta el rebuild

**Evidencia**

- `dglweb/stats/migrations/0031_windowstandout_abridor_and_more.py:15-17` agrega `abridor` con
  `default=False`.
- `dglweb/stats/ventana.py:563-571` interpreta cualquier fila de pitcheo con `abridor=False` como
  `relevista`.
- `dglweb/stats/ventana.py:605-608` aplica cortes distintos para abridores y relevistas.
- `ofelia/config.ini:130-133` corre `build_window_standouts` de forma horaria, no necesariamente justo
  después de migrar.

**Bug / edge case**

Si `WindowStandout` ya tenía filas antes de aplicar esta migración, todas las filas de pitcheo viejas
nacen como `abridor=False`. Durante la ventana entre `migrate` y el próximo
`build_window_standouts`, la portada puede medir un abridor viejo contra el corte de relevistas. Un
`+4.0` que no llega al p85 de abridores (`+5.7`) sí pasa el p85 de relevistas (`+2.4`).

**Mejora sugerida**

Tratar la migración como cambio de contrato de snapshot:

- correr `build_window_standouts` inmediatamente después de `migrate` en el checklist de despliegue;
- o vaciar/ocultar la tabla hasta el primer rebuild posterior a `0031`;
- o incluir una migración de datos si existe forma confiable de inferir `abridor` en las filas viejas.

**Razonamiento**

`WindowStandout` es una foto, no una tabla histórica. Cuando cambia la semántica de esa foto, el
deploy debe garantizar que la lectura pública no mezcle filas con el contrato viejo y cortes nuevos.

## Persona 6 - Experto en béisbol y sabermetría

### SAB-01 [P3] `GS > 0` puede clasificar mal a openers y bulk relievers

**Evidencia**

- `dglweb/stats/ventana.py:399-403` decide el rol de pitcheo con esta prioridad: si `GS > 0`, solo
  puede calificar como `abridor`; si no, puede calificar como `relevista`.
- `tests/test_ventana.py:359-382` cubre abridor puro y relevista puro, pero no un pitcher con
  apariciones de relevo y una apertura aislada.

**False assumption sabermétrico**

En béisbol moderno, `GS > 0` no siempre significa “este pitcher pertenece a la población de abridores”
durante la ventana. Puede ser un opener, un bullpen game, o un relevista/bulk pitcher que abrió una
vez y luego trabajó como relevo. Con la regla actual, un pitcher con `GS=1`, `G=5` y cuatro apariciones
totales no puede entrar como relevista aunque su uso real de la ventana haya sido mayormente de relevo.

**Impacto sabermétrico**

El widget puede dejar fuera una racha legítima de relevo por una apertura administrativa, o medirla
contra una distribución de abridores que no describe su rol. Eso no rompe el cálculo de carreras, pero
sí cambia la población comparada, que es justo lo delicado de separar abridor y relevista.

**Mejora sugerida**

Definir el contrato de rol con una regla más resistente o documentar la decisión:

- si se quiere “cualquier apertura lo convierte en abridor”, agregar un comentario y una prueba de
  opener para congelar esa política;
- si se quiere rol dominante de la ventana, considerar `GS / G`, un mínimo de aperturas, o permitir
  fallback a relevista cuando `GS > 0` pero no llega al umbral de IP de abridor y sí llega a
  `APARICIONES_RELEVO`.

**Razonamiento**

Separar abridores y relevistas fue una buena corrección sabermétrica. El siguiente borde natural es
que `GS` por sí solo mezcla rol táctico de un juego con rol estadístico de una ventana de catorce días.

## Persona 7 - Docker / fail2ban / nginx

### OPS-01 [P4] Queda una referencia vieja a la ruta anterior del jail de nginx

**Evidencia**

- `deploy/fail2ban/jail.d/nginx.local:3-7` ya documenta la ruta nueva y aclara que la vieja era
  `deploy/fail2ban-nginx.local`.
- `docs/RENDIMIENTO.md:293-298` ya marca fail2ban como hecho y deja pendiente solo observar
  `nginx-404-scan`.
- `docs/RESTAURAR.md:186-188` instala desde las rutas correctas.
- `deploy/fail2ban/jail.local:26` todavía dice que `deploy/fail2ban-nginx.local` pone `backend =
  auto`, pero esa ruta ya no existe.

**Impacto**

Bajo: la configuración activa está bien y los docs operativos principales quedaron corregidos. El
riesgo es que alguien lea el comentario de `jail.local` durante una restauración o una auditoría y
persiga una ruta fantasma.

**Mejora sugerida**

Cambiar esa referencia residual a `deploy/fail2ban/jail.d/nginx.local`.

**Razonamiento**

La corrección de v15 quedó esencialmente resuelta; esto es solo limpiar la última migaja documental
para que todos los archivos de fail2ban apunten al mismo lugar.

## Verificación ejecutada

- Lectura de `.md` bajo `docs/`, incluyendo `docs/TODO.md`, `docs/RENDIMIENTO.md`,
  `docs/RESTAURAR.md` y `docs/reviews/code_review_v15.md`.
- `docker compose run --rm web pytest tests/test_ventana.py tests/test_visibilidad_widgets.py`:
  falló al intentar recrear `test_dglweb` porque ya existía y tenía una sesión activa.
- `docker compose run --rm web pytest --reuse-db tests/test_ventana.py tests/test_visibilidad_widgets.py`:
  **37 passed**.
- `docker compose run --rm --no-deps web ruff check .`: **All checks passed**.
- `docker compose run --rm --no-deps web mypy .`: **Success, 233 source files**.
- `docker compose -f deploy/stack.yml config -q` con variables dummy: OK.
- `docker compose -f deploy/postgres/stack.yml config -q` con variables dummy: OK.
- `docker compose -f deploy/adserver/stack.yml config -q`: OK.
- `git diff --check`: sin errores.
