# Code Review v13

Fecha: 2026-07-29

Alcance: revisión de `1bf03e9` después de leer todos los archivos `.md` bajo `docs/`, incluidos
`TODO.md`, los documentos de autoridad, operación, despliegue, rendimiento y sabermetría, y los
reviews anteriores con sus resoluciones.

Reglas aplicadas:

- No se modificó código fuente. Este documento es el único entregable del review.
- No se consideran findings los placeholders ni los datos falsos conocidos de la portada.
- No se repiten asuntos pendientes en `docs/TODO.md`.
- Un problema que cruza varias especialidades aparece una sola vez, bajo la persona que mejor
  representa su riesgo principal.
- Las decisiones documentadas se respetaron, pero una decisión no se trató como control de seguridad
  cuando el mecanismo elegido todavía deja una capacidad explotable.

Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P2 | QA-01 | QA / Reliability Engineer | Dos `refresh_daily` solapados pueden atribuirse mutuamente el resultado de sus pasos. |
| P2 | ARCH-01 | Backend Architect | La cadena marca los derivados como publicados antes de saber si terminaron y continúa después de un fallo. |
| P3 | DEV-01 | Python Principal Developer | Una línea estadística incompleta puede producir conteos negativos y un valor diario ficticio. |
| P3 | QA-02 | QA / Reliability Engineer | El JavaScript que decide impresiones publicitarias y compartir no tiene pruebas ejecutables. |
| P3 | SEC-01 | Security Engineer | Los anuncios se ejecutan en iframes sin `sandbox`, ampliando el impacto de comprometer Revive o una creatividad. |
| P3 | SAB-01 | Experto en béisbol y sabermetría | El valor de pitcheo cuenta outs que el valor ofensivo no cuenta y, por tanto, no es simétrico “por construcción”. |
| P4 | FE-01 | Frontend Engineer | Los controles de compartir llaman “artículo” a perfiles y leaderboards para lectores de pantalla. |

## Persona 1 - Python Principal Developer

### DEV-01 [P3] Los componentes derivados de una línea estadística pueden quedar negativos

**Evidencia**

- `_numero()` convierte cualquier valor ausente o ilegible en cero sin distinguir dato realmente
  nulo de dato corrupto (`dglweb/stats/daily.py:173-178`).
- Los sencillos se calculan como `H - X2B - X3B - HR`, los boletos no intencionales como `BB - IBB`
  y los outs ofensivos como `AB - H - K + SF + SH`, sin validar sus invariantes
  (`dglweb/stats/daily.py:188-205`).
- El cálculo de pitcheo repite las dos primeras restas. Solo protege de negativos a
  `outs_en_juego` (`dglweb/stats/daily.py:269-301`).
- `tests/test_daily.py` cubre líneas coherentes y valores cero, pero no una respuesta parcial como
  `H=None, X2B=1` o `BB=0, IBB=1`.

**Bug / edge case**

Si el proxy omite `H` pero entrega un doble, el código inventa `-1` sencillos. Si `IBB > BB`, crea
boletos no intencionales negativos. En bateo eso resta valor al jugador; en pitcheo, por el signo
exterior, puede premiar al lanzador. La función devuelve un `float` perfectamente válido, por lo que
el error no falla ruidosamente: puede ordenar o publicar un destacado falso.

**Mejora sugerida**

Validar antes de puntuar las invariantes `X2B + X3B + HR <= H`, `IBB <= BB` y la descomposición de
outs. Una línea inválida debería excluirse del ranking y dejar diagnóstico en `IngestRun`, no
convertirse silenciosamente en cero ni arreglarse con `max()` en cada resta. Añadir pruebas
parametrizadas para campos ausentes, texto ilegible y conteos internamente imposibles.

**Razonamiento**

Estos valores son datos derivados, no observaciones independientes. Aceptar cada campo por separado
y luego restarlos pierde la garantía básica del modelo. Fallar una fila con explicación protege mejor
la credibilidad de la portada que publicar un número plausible construido con componentes imposibles.

## Persona 2 - QA / Reliability Engineer

### QA-01 [P2] Las corridas solapadas de `refresh_daily` no están aisladas

**Evidencia**

- El management command llama directamente `pipeline.run_and_record()` sin un lock de workflow
  (`dglweb/stats/management/commands/refresh_daily.py:34-39`).
- El único lock existente protege la cadena de derivados, no las entradas ni la corrida completa
  (`dglweb/stats/locks.py:41-66`, `dglweb/stats/pipeline.py:185-187`).
- Después de cada comando, `_estado_de()` busca la fila más reciente con el mismo nombre y
  `started_at >= inicio`; no busca la fila creada por esa invocación
  (`dglweb/stats/pipeline.py:97-108`).
- `IngestRun` guarda `command`, `scope` y timestamps, pero no un identificador de la corrida padre
  (`dglweb/stats/models.py:192-213`).
- Las pruebas simulan una sola corrida y una sola fila por comando; no cubren dos workflows
  concurrentes (`tests/test_pipeline.py:38-63`).

**Escenario de fallo**

El scheduler todavía está corriendo cuando un operador lanza un retry manual, o una ejecución tarda
más que su siguiente ventana. Ambas invocaciones ejecutan `update_batting`. Cuando la primera termina,
la consulta “última fila desde que empecé” puede devolver la fila más nueva de la segunda. Un
`PARTIAL` puede leerse como `SUCCESS`, o viceversa, y la decisión de reconstruir derivados deja de
pertenecer a la corrida que se está registrando.

**Impacto**

El estado agregado puede mentir, Telegram puede nombrar el detalle de otra ejecución y una corrida
puede publicar derivados aunque uno de sus propios insumos no estuviera completo. Las escrituras de
los comandos de entrada también quedan libres para intercalarse.

**Mejora sugerida**

Tomar un advisory try-lock exclusivo al entrar en `refresh_daily` y registrar claramente el segundo
intento como omitido por corrida activa. Como defensa estructural, agregar un `pipeline_run_id` o
correlation id a cada `IngestRun` hijo y resolver `_estado_de()` por esa identidad, no por una ventana
temporal. Probar dos invocaciones solapadas y exigir que cada una solo vea sus filas.

**Razonamiento**

El tiempo aproxima causalidad, pero no la representa. Un orquestador fiable necesita identidad de
ejecución y exclusión explícita; de otro modo, precisamente un retry operativo puede volver ambiguo el
diagnóstico que intenta aclarar.

### QA-02 [P3] Dos flujos JavaScript nuevos quedaron fuera del corredor de pruebas

**Evidencia**

- `static/js/anuncios.js:31-95` elige una sola zona según viewport y contenedor, elimina huecos que
  no aplican y evita asignar un segundo `src`. Esa lógica determina qué impresión factura Revive.
- `static/js/compartir.js:28-101` decide entre Clipboard API y fallback, habilita Web Share y maneja
  estados de éxito y error.
- El corredor Vitest existe, pero `tests/js/` solo contiene pruebas para buscador, pizarra y video.
- `tests/test_rangos_de_anuncio.py` y `tests/test_legal.py:405-429` comprueban contratos estáticos de
  plantilla; no ejecutan selección de breakpoint, parseo JSON ni la regla “un solo `src`”.
- `tests/test_compartir.py` valida URLs y HTML del inclusion tag, no `navigator.share`, clipboard ni
  el fallback de `execCommand`.

**Riesgo**

Una regresión de JavaScript puede dejar todos los banners horizontales vacíos o solicitar una zona
incorrecta mientras la suite Python sigue verde. En el peor caso, una reasignación doble de `src`
infla impresiones facturables. En compartir, un fallo puede dejar un botón visible que no copia o un
estado de error que nunca se restaura.

**Mejora sugerida**

Extraer o exponer las funciones puras mínimas y añadir pruebas jsdom para breakpoints, ancho real del
contenedor, JSON inválido, ninguna opción, montaje idempotente y exactamente una asignación de `src`.
Para compartir, simular Web Share presente/ausente, Clipboard resuelto/rechazado, fallback y
restauración del texto con fake timers. Incluir ambos archivos en el mismo gate Vitest que ya usa CI.

**Razonamiento**

No se pide un framework nuevo: la infraestructura ya existe. El costo marginal es pequeño y la lógica
publicitaria tiene una consecuencia contable que merece una prueba ejecutable, no solo comentarios y
expresiones regulares sobre el HTML.

## Persona 3 - Frontend Engineer

### FE-01 [P4] El nombre accesible del componente de compartir no corresponde a todas sus páginas

**Evidencia**

- El componente fija `aria-label="Compartir este artículo"`
  (`templates/widgets/_compartir.html:45-46`).
- El inclusion tag no acepta un nombre accesible alternativo
  (`dglweb/core/templatetags/compartir.py:32-54`).
- El mismo componente se usa en artículos, perfiles de jugador y leaderboards
  (`templates/articles/article_page.html:76,94`, `templates/profiles/player_detail.html:93`,
  `templates/profiles/leaders.html:226`).

**Broken UX path**

En el perfil de Juan Soto o en una tabla de líderes, un lector de pantalla oye que los controles
comparten “este artículo”. Los enlaces funcionan, pero el tipo de contenido anunciado contradice la
página actual y reduce la confianza en la navegación asistida.

**Mejora sugerida**

Usar un nombre neutral como “Opciones para compartir” o aceptar un parámetro opcional para producir
“Compartir este perfil”, “Compartir esta tabla” y “Compartir este artículo”. Añadir aserciones en los
tres contextos de uso.

**Razonamiento**

El `role="group"` está bien elegido; el defecto está únicamente en reutilizar texto específico dentro
de un componente genérico. Resolverlo en el tag conserva una sola fuente de markup y evita variantes
de plantilla.

## Persona 4 - Security Engineer

### SEC-01 [P3] El iframe publicitario confía capacidades de navegación a Revive y a sus creatividades

**Evidencia**

- Los dos tipos de anuncio omiten deliberadamente el atributo `sandbox`
  (`templates/widgets/_anuncio.html:20-27`,
  `templates/widgets/_anuncio_horizontal.html:20-28`).
- La justificación es que el click necesita navegar y que Revive es propio. Sin embargo, Revive es
  una aplicación PHP públicamente expuesta y también ejecuta creatividades administradas desde su
  panel; “propio” no equivale a contenido de confianza permanente.
- La CSP del sitio limita el documento padre y `frame-src`, pero no reduce las capacidades del
  documento ya autorizado dentro del iframe (`dglweb/core/csp.py:82-101`).

**Attack scenario**

Una vulnerabilidad de Revive, credenciales de administrador robadas o una creatividad maliciosa
permiten servir HTML/JavaScript controlado por un atacante en cada hueco publicitario.

**Exploitation method**

El código queda aislado del DOM de `dominicanosengrandesligas.com` por Same-Origin Policy, por lo que
no puede leerlo directamente. Pero, al no estar sandboxed, conserva capacidades del navegador para
abrir ventanas, iniciar descargas o intentar reemplazar la navegación superior cuando existe
activación del usuario. El atacante puede convertir un click legítimo sobre el anuncio en redirección
a login falso, descarga o malvertising.

**Business impact**

Phishing y distribución de contenido malicioso desde una propiedad de la marca, pérdida de confianza
de lectores y anunciantes, y posible compromiso posterior de cuentas. Además, un incidente del
adserver deja de estar contenido al subdominio de publicidad desde la perspectiva de navegación del
usuario.

**Recommended fix**

Probar Revive con un sandbox mínimo, por ejemplo `allow-scripts allow-same-origin allow-popups
allow-popups-to-escape-sandbox`, omitiendo top navigation, formularios y descargas salvo necesidad
demostrada. Configurar las creatividades para abrir el destino en una pestaña nueva y verificar que el
click tracking siga contabilizando. Si algún formato exige navegación superior, habilitar únicamente
`allow-top-navigation-by-user-activation` para ese formato y documentar el riesgo residual. Añadir
una prueba que exija el sandbox acordado en ambos templates.

**Razonamiento**

El iframe y el origen separado ya reducen mucho el impacto, pero aislamiento de origen y restricción
de capacidades son controles distintos. El click tracking no requiere entregar por defecto todas las
capacidades del documento embebido.

## Persona 5 - Backend Architect

### ARCH-01 [P2] La cadena derivada puede publicar una foto mixta y reportarla como publicada

**Evidencia**

- El contrato declara que `build_leaders` depende de `build_career_totals`
  (`dglweb/stats/pipeline.py:47-48`).
- `resultado.derivados_publicados` cambia a `True` antes de ejecutar cualquiera de los dos comandos
  (`dglweb/stats/pipeline.py:181-187`).
- `_correr()` convierte excepciones y estados `PARTIAL`/`FAILED` en un `Paso`, pero nunca propaga el
  fallo ni detiene la cadena (`dglweb/stats/pipeline.py:112-137`).
- Por tanto, si `build_career_totals` falla, el loop todavía llama `build_leaders`. Si cualquiera de
  los dos falla, el flag permanece en `True`.
- El registro y el aviso solo dicen que los líderes no se reconstruyeron cuando ese flag es falso
  (`dglweb/stats/pipeline.py:216-219`, `dglweb/stats/pipeline.py:234-240`).
- Las pruebas cubren fallos de insumos antes de entrar a la cadena, pero no un fallo en el primer o
  segundo derivado (`tests/test_pipeline.py:69-119`).

**Fallo y consistencia de datos**

Con entradas nuevas y `build_career_totals` fallido, `build_leaders` puede reconstruir rankings de
temporada con datos de hoy y rankings de carrera con los totales anteriores. El pipeline queda
`PARTIAL`, pero su mensaje omite la afirmación operativa más importante porque
`derivados_publicados=True`. Si falla solo `build_leaders`, los totales cambian mientras los snapshots
de líderes quedan viejos y el mismo flag vuelve a afirmar publicación completa.

**Mejora sugerida**

Ejecutar los derivados como una dependencia real: si `build_career_totals` no termina en `SUCCESS`,
registrar `build_leaders` como omitido y no llamarlo. Cambiar `derivados_publicados` a `True` solo
después de que toda la cadena termine con éxito, o separar estados `intentados`, `parciales` y
`publicados`. Añadir pruebas para fallo, `PARTIAL` y ausencia de fila en cada posición, verificando
orden, flag, detalle agregado y Telegram.

Para atomicidad de publicación más fuerte, construir ambas familias en staging versionado y cambiar
el snapshot activo solo al completar la cadena. El advisory lock evita dos escritores simultáneos,
pero no convierte dos commits independientes en una sola publicación.

**Razonamiento**

El lock protege exclusión mutua; no protege el contrato de dependencia ni el significado del estado.
En un pipeline, “se intentó publicar” y “se publicó una foto coherente” no son equivalentes.

## Persona 6 - Experto en béisbol y sabermetría

### SAB-01 [P3] La supuesta simetría bateo-pitcheo usa inventarios de eventos distintos

**Evidencia**

- El código afirma que ambas actuaciones quedan en la misma unidad “por construcción” al usar la
  misma matriz de pesos (`dglweb/stats/daily.py:212-240`).
- Bateo deriva outs del bateador con `AB - H - K + SF + SH`
  (`dglweb/stats/daily.py:188-205`).
- Pitcheo parte de `outsPitched`, que incluye outs de corredores, y solo descuenta `K` y `CS`
  (`dglweb/stats/daily.py:242-284`). Los pickoffs y el segundo out de un doble play permanecen como
  outs genéricos.
- La propia documentación estima que la aproximación afecta 13,3% de las salidas
  (`dglweb/stats/daily.py:261-265`).
- La prueba fija que un doble play del lanzador vale exactamente dos outs sueltos, aunque el cálculo
  ofensivo del bateador que batea para doble play solo registra su propio out
  (`tests/test_daily.py:279-290`).

**False assumption / uso incorrecto**

Usar los mismos coeficientes no produce simetría si cada lado multiplica cantidades distintas. El
segundo out de un doble play suma al valor del lanzador como out genérico, pero no aparece como evento
negativo equivalente del bateador; un pickoff tiene el mismo desbalance. Declararlo como aproximación
hace transparente la limitación, pero no vuelve cierta la afirmación de que ambos lados miran los
mismos eventos ni evita que altere el ranking mixto.

**Impacto sabermétrico**

Los pitchers con más dobles plays o pickoffs reciben crédito adicional frente a bateadores cuyo valor
se calcula en otro universo de outs. El número sigue expresado con pesos de carreras, pero la
comparación individual deja de ser el negativo del valor ofensivo permitido y mezcla pitcheo con
defensa, catcher y contexto de corredores.

**Mejora sugerida**

Para conservar el modelo agregado actual, derivar los outs de bateadores con los componentes de la
línea de pitcheo y omitir en ambos lados los outs de corredores que no tengan evento y peso explícito.
Mantener SB/CS como eventos separados donde la fuente los identifica. Si se quiere acreditar dobles
plays, pickoffs y responsabilidad compartida con precisión, migrar el ranking diario a eventos
play-by-play y RE24, donde el cambio de estado de bases/outs asigna el valor real sin inventar un peso.

Mientras se conserve la aproximación, cambiar el texto de producto y docstrings de “misma unidad por
construcción” a “heurística común de pesos lineales con distinta cobertura de eventos”, y calibrar el
orden contra RE24 antes de presentarlo como comparación sabermétrica exacta.

**Razonamiento**

La unidad puede ser carreras estimadas y aun así la atribución ser asimétrica. Para comparar un
bateador y un lanzador en una sola lista hacen falta ambos requisitos: pesos compatibles e inventario
de eventos compatible.

## Controles OWASP revisados sin finding nuevo

No se observaron autenticación/JWT propios, almacenamiento de contraseñas fuera de Django, SQL o
comandos construidos con input del usuario, `pickle`, `eval`, endpoints `csrf_exempt`, uploads sin los
controles ya implementados, redirects abiertos ni una frontera multi-tenant. Roles, CSRF, cookies y
secrets de producción siguen delegados a Django/Wagtail y variables de entorno. Los riesgos ya
pendientes de resiliencia, backups y Cloudflare permanecen en `TODO.md` y no se duplican aquí.

## Verificación

- Suite Python aislada: **1.221 passed, 1 deselected** con `pytest --create-db -q`.
- Ruff: `All checks passed!`.
- mypy: `Success: no issues found in 227 source files`.
- `manage.py check --deploy` solo emitió los dos warnings de política ya documentada: redirect HTTPS
  delegado a nginx y HSTS sin `preload`.
- El corredor JavaScript no arrancó en este checkout de Windows porque `node_modules` contiene los
  binarios opcionales de Rollup para Linux y falta `@rollup/rollup-win32-x64-msvc`. CI reinstala con
  `npm ci`; este problema local de dependencias no se reporta como finding del código.

## Exclusiones explícitas del backlog

No se reabrieron login social, evaluación de caché de métricas, backup fuera del VPS, Cloudflare,
artículos semilla, metadatos de política del `Loader`, Salarios, memoria de `compare()`, prueba de
restauración ni el upgrade a treebeard 6. Todos continúan marcados como pendientes en `docs/TODO.md`.
