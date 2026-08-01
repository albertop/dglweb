# Code Review v17

Fecha: 2026-08-01

Alcance: revisión del estado actual después de las correcciones posteriores a `code_review_v16.md`.
Antes de revisar se leyeron los `.md` bajo `docs/`, con foco en `TODO.md`, `RENDIMIENTO.md`,
`RESTAURAR.md` y el review anterior. No se modificó código fuente; este archivo es el único
entregable.

Reglas aplicadas:

- No se repiten asuntos ya resueltos en v16.
- No se reabre la decisión consciente de dejar fuera las Ligas Negras de ciertos liderazgos.
- Si varias personas detectan el mismo problema, aparece una sola vez bajo la persona que mejor
  representa el riesgo principal.
- Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P3 | SAB-01 | Experto en béisbol y sabermetría | El fallback de opener a relevista puede meter abridores cortos en la población de relevistas. |
| P3 | QA-01 | QA / Reliability Engineer | `build_window_standouts --hasta` imprime la muestra usando la fecha actual, no la fecha reproducida. |
| P4 | DEV-01 | Python Principal Developer | El comentario de `CORTES` todavía dice "cuatro constantes" aunque ahora hay seis cortes. |

No se encontraron findings P1 ni P2.

## Persona 1 - Python Principal Developer

### DEV-01 [P4] El comentario de `CORTES` quedó desfasado con la estructura real

**Evidencia**

- `dglweb/stats/ventana.py:135` dice: "Cuatro constantes: p85 y p15 de cada oficio".
- `dglweb/stats/ventana.py:190-195` define tres clases: `bateo`, `abridor` y `relevista`, cada una
  con p85 y p15. Son seis constantes efectivas, no cuatro.

**Riesgo**

No rompe la ejecución ni las pruebas. Es deuda de mantenibilidad en una zona donde los comentarios son
parte importante del contrato estadístico. Alguien que llegue luego a remedir cortes puede leer
"oficio" como bateo/pitcheo y pasar por alto que pitcheo ya está dividido en dos poblaciones.

**Mejora sugerida**

Actualizar esa frase a "seis constantes: p85 y p15 de cada clase" o "tres clases". Es una corrección
documental mínima, pero deja el comentario alineado con la decisión sabermétrica que ya está bien
codificada.

## Persona 2 - QA / Reliability Engineer

### QA-01 [P3] `build_window_standouts --hasta` no reproduce la muestra con la fecha solicitada

**Evidencia**

- `dglweb/stats/management/commands/build_window_standouts.py:3-5` documenta `--hasta` como forma de
  reproducir una foto vieja.
- `dglweb/stats/management/commands/build_window_standouts.py:39-45` calcula y guarda la ventana con
  `hasta = options["hasta"] or timezone.localdate()`.
- `dglweb/stats/management/commands/build_window_standouts.py:57-61` llama `ventana.portada()` para
  imprimir la muestra.
- `dglweb/stats/ventana.py:604-630` hace que `se_puede_publicar()` use `timezone.localdate()` cuando
  no recibe fecha.
- `dglweb/stats/ventana.py:676-677` hace que `portada()` dependa de esa fecha actual.
- `rg` no encontró tests que llamen `build_window_standouts`; las pruebas cubren `ventana`, no el
  management command.

**Bug / edge case**

El comando guarda la ventana de `--hasta`, pero la muestra que imprime decide si puede publicarse con
la fecha de hoy. En temporada regular puede pasar inadvertido. En invierno, o reproduciendo una foto
de la primera quincena, `portada()` puede devolver `None` por el calendario actual y el comando imprime
`"(menos de cinco: no alcanza para partir en quintos)"`, aunque la causa real no sea el reparto ni la
cantidad de candidatos.

**Impacto**

Medio-bajo pero operativo: el comando que existe para reproducir fotos viejas puede dar una señal falsa
justo cuando alguien está depurando una corrida. No corrompe datos, porque `guardar()` ya escribió la
foto calculada; confunde el diagnóstico.

**Mejora sugerida**

Hacer que la vista de diagnóstico use la misma fecha que el cálculo. Opciones:

- permitir `ventana.portada(hoy=hasta)` y pasarle `hasta` desde el comando;
- o separar una función de armado de listas que reciba explícitamente la fecha de publicación;
- o, como mínimo, distinguir en el mensaje si `portada()` no sale por calendario, por tabla vacía o
  por no cruzar cortes.

Añadir una prueba de management command con `call_command("build_window_standouts", "--hasta", "...")`
y una temporada activa que haga visible la diferencia entre `hasta` y `timezone.localdate()`.

## Persona 3 - Frontend Engineer

No encontré un finding frontend nuevo. Las correcciones revisadas son de cálculo, persistencia,
calendario de publicación y operación del comando; no vi evidencia de regresión en plantilla, estado
ARIA, botones móviles o truncamiento visual.

## Persona 4 - Security Engineer

No encontré un finding de seguridad nuevo. El filtro de visibilidad de jugadores ocultos se mantiene
aplicado en la lectura pública de la ventana, y la revisión de fail2ban no mostró rutas operativas
rotas nuevas.

## Persona 5 - Backend Architect

No encontré un finding arquitectónico independiente nuevo. La migración `0032_vaciar_window_standout`
cierra correctamente el riesgo de v16: borra la snapshot vieja en vez de adivinar `abridor` desde una
fila que no guardaba `GS`.

QA-01 toca arquitectura de comando, pero el riesgo principal es verificabilidad y diagnóstico de
operación, por eso queda bajo QA.

## Persona 6 - Experto en béisbol y sabermetría

### SAB-01 [P3] El fallback de opener puede reclasificar abridores cortos como relevistas

**Evidencia**

- `dglweb/stats/ventana.py:415-430` documenta que quien abrió pero no llega al umbral de abridor cae
  al de relevista.
- `dglweb/stats/ventana.py:429-431` implementa esa prioridad: primero abridor si `GS > 0` e IP
  suficiente; si no, `return "relevista" if G >= APARICIONES_RELEVO else ""`.
- `tests/test_ventana.py:488-502` cubre el caso de opener/swingman con `GS=1, G=8`.
- `tests/test_ventana.py:505-511` cubre un abridor flojo con `GS=2, G=2`, pero no uno con varias
  aperturas cortas y `G >= 4`.

**False assumption sabermétrico**

La corrección arregla un caso real: el opener o relevista largo que abrió una vez no debe desaparecer
por una apertura administrativa. El problema es que el fallback no distingue "abrió una vez y relevó
el resto" de "todas sus apariciones fueron aperturas cortas".

Ejemplo: `GS=4, G=4, outsPitched=36` son cuatro aperturas y 12.0 IP en la ventana. No llega al umbral
de abridor si el equipo jugó 13, pero con la regla actual califica como `relevista` porque `G >= 4`.
Eso lo mediría contra p85/p15 de relevistas, una distribución de una entrada por aparición, aunque su
uso real fue de abridor.

**Impacto sabermétrico**

Puede mover pitchers entre poblaciones no comparables. Un abridor con pocas entradas por salida,
precisamente un perfil que puede aparecer en "Pasando trabajo", recibiría el corte más permisivo de
relevistas en vez del de abridores. La separación abridor/relevista era la mejora fuerte; este borde
puede reintroducir mezcla por el lado de los starters cortos.

**Mejora sugerida**

Acotar el fallback a relevista con una condición de rol dominante, no solo con `G`:

- permitir fallback cuando `GS == 1` y `G >= APARICIONES_RELEVO`;
- o usar una proporción, por ejemplo `GS / G <= 0.25`;
- o documentar que cualquier pitcher que no llegue al umbral de abridor compite como relevista, y
  congelar con una prueba el caso `GS=4, G=4`.

**Razonamiento**

El dato `GS` y el dato `G` no miden el mismo concepto. Para decidir población sabermétrica en una
ventana corta, conviene separar "tuvo una apertura" de "su rol principal fue abrir".

## Persona 7 - Docker / fail2ban / nginx

No encontré un finding nuevo. La referencia residual de v16 quedó corregida en
`deploy/fail2ban/jail.local:26`, y los documentos operativos siguen apuntando a las rutas actuales.

## Verificación ejecutada

- Lectura de `.md` bajo `docs/`, incluyendo `docs/TODO.md`, `docs/RENDIMIENTO.md`,
  `docs/RESTAURAR.md` y `docs/reviews/code_review_v16.md`.
- `docker compose run --rm web pytest --reuse-db tests/test_ventana.py tests/test_visibilidad_widgets.py`:
  **46 passed**.
- `docker compose run --rm --no-deps web ruff check .`: **All checks passed**.
- `docker compose run --rm --no-deps web mypy .`: **Success, 233 source files**.
- `docker compose -f deploy/stack.yml config -q` con variables dummy: OK.
- `docker compose -f deploy/postgres/stack.yml config -q` con variables dummy: OK.
- `docker compose -f deploy/adserver/stack.yml config -q`: OK.
- `git diff --check`: sin errores.
