# TODO — dglweb

Lista de pendientes que van surgiendo sobre la marcha. (Ítems de decisión / afinado, no el
roadmap de fases — eso está en `BUILD_PLAN.md`.)

## Hecho: tab de Fildeo

**Construido y en producción.** `FieldingTab` está en el registro con su `_fielding_context` propio
—que fue lo único que necesitó código nuevo, porque `_group_context` no le servía: las líneas de
fildeo son por POSICIÓN y no por stint—, cinco pills (Estándar, Avanzado, Receptor, Postemporada,
Totales) y cuatro archivos de test.

Esta sección decía "Próximo" mucho después de que el tab existiera. Vale la pena anotar por qué:
un TODO que describe trabajo ya hecho es peor que uno incompleto, porque se lee como si fuera cierto
y guía decisiones. Pasó: al preguntar "¿qué queda pendiente?" recomendé priorizar deuda técnica
"antes de Fildeo" — que ya había pasado.

## Antes de salir a producción

- [ ] **Verificar que el usuario de Postgres pueda `CREATE EXTENSION unaccent`.** El buscador de jugadores depende de esa extensión —es lo que hace que «nunez» encuentre a Núñez, y sin ella la mitad del maestro es inalcanzable—. No va en `requirements.txt` porque no es un paquete de Python: vive en la base. La migración `players/0005_unaccent.py` la crea sola al correr `migrate`, pero `CREATE EXTENSION` pide permisos elevados. En el Postgres actual funciona; en uno gestionado con usuario restringido, `migrate` fallaría ahí. **Comprobarlo antes de migrar**, no después.

- [ ] **Rotar el token del bot de Telegram.** Quedó expuesto durante la configuración, así que conviene renovarlo antes de producción: @BotFather → `/mybots` → el bot → *API Token* → *Revoke current token*, y reemplazar `TELEGRAM_BOT_TOKEN` en `.env`. El bot y el grupo siguen siendo los mismos; solo cambia la llave.

- [ ] **Recomendar un monitor de uptime y dejarlo apuntando a `/health/pipeline`.** El endpoint ya
  está; lo que falta es el servicio de afuera que lo consulte, que es la mitad que importa: el
  scheduler estuvo días caído justamente porque lo único que podía avisar corría en el mismo
  scheduler. El dueño no usa ninguno todavía, así que hay que recomendarle uno (hay opciones
  gratuitas que alertan por correo y por Telegram) y configurarlo con la URL pública. **Recordarlo
  cuando se prepare el despliegue**, no antes — sin dominio público no hay nada que vigilar.

- [x] **Avisos por Telegram.** **Funcionando** (`dglweb/core/notify.py`), verificado con un mensaje real el 2026-07-26. El bot es `@dglweb_avisos_bot` y escribe a un **grupo**, no a un chat privado: el id es negativo y eso tiene una ventaja — sumar a otra persona a los avisos es agregarla al grupo, sin tocar configuración. Avisa cuando **un paso del refresco falla** —diciendo cuál, que es lo que el «503» del monitor externo no puede decir— y cuando **aparece un debut nuevo**.
  Los debuts se avisan **todos los días** mientras sigan pendientes. Hubo una versión que avisaba una sola vez por debutante —yo puse esa deduplicación para no cansar— y **el dueño pidió lo contrario, con razón**: si el aviso sale un martes y ese día no lo ve, el pelotero se queda fuera del sitio sin que nada vuelva a recordarlo. La repetición ES el mecanismo, y para en cuanto lo carga, que es el acuse de recibo. Puede insistir sin cansar porque son pocos y raros: un puñado al año.
  El mensaje lleva el `player_id` rotulado y en su propia línea, que es lo que hace falta para darlo de alta en el Backoffice.
  Un refresco limpio NO avisa: un «todo bien» diario se vuelve ruido en una semana.
  **Para encenderlo** hacen falta dos valores en `.env` — hablar con @BotFather para el token y sacar el chat id; sin ellos no se manda nada y no se protesta, que es lo correcto en desarrollo:
  ```
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
  ```
  ~~ Al dueño le sirve más que el correo y no cuesta nada: un bot, un
  token y un chat id en `.env`, y `httpx` ya está entre las dependencias. Dos usos, y el segundo es
  el que de verdad quiere:
  - **El refresco que falla**: qué paso se cayó, no solo que algo se cayó. El monitor externo va a
    decir «503»; Telegram puede decir «update_fielding falló».
  - **Los debuts detectados**: hoy `detect_debuts` deja el aviso en el log de ingesta y hay que ir a
    buscarlo. Un debut es noticia y es raro —un puñado al año— así que es exactamente el tipo de
    cosa que vale la pena que llegue al bolsillo en vez de esperar a que alguien abra el Backoffice.

## Diseño / branding

- [x] ~~Definir el subtítulo del brand~~ → **descartado**: se quita, es redundante con el nombre.
- [x] ~~Afinar el tamaño del brand en móvil~~ **Hecho**, aunque el diagnóstico estaba mal: el nombre NO se recortaba. Lo que pasaba es que a 375px la hamburguesa caía a una segunda fila y el header pasaba de 54px a 84px. Dos escalones (`≤400px` y `≤340px`) lo devuelven a una fila hasta 320px, sin partir ni abreviar el nombre. Verificado a 320, 375 y 1280.

## Fase 5 — artículos en Wagtail (2026-07-27)

**Hecho:** el modelo `ArticlePage` bajo `ArticleIndexPage`, que sirve `/articulos/` y
`/articulos/<slug>/` desde el árbol de Wagtail. Categoría única (snippet, siete sembradas por la
migración) + hashtags libres. Siete bloques de cuerpo: párrafo, subtítulo, imagen, cita, tabla,
mención de jugador y gráfico. La portada y el índice listan lo publicado; se fueron las tarjetas de
muestra escritas a mano.

**Lo que falta de la fase**, y no es poco:

- [x] **Workflow de aprobación y roles/grupos.** Hecho el 2026-07-27: tres roles montados por
      migración (Redactores / Editores / Administradores), permisos colgados de la sección Artículos
      y no de la raíz, y 9 tests que cubren el flujo entero. Ver `dglweb/core/roles.py`.
- [x] **Buscador de artículos.** **Hecho el 2026-07-27.** Va en `/articulos/?q=…`, con formulario GET
      —o sea que la búsqueda se puede compartir y marcar, y funciona sin JavaScript— y se combina con
      el filtro de categoría. Con consulta, la página deja de ser un índice y pasa a ser una lista de
      resultados: sin destacado ni panel, porque ahí ordena la relevancia y no la fecha.

      **Lo que costó de verdad no fue buscar, fue el español.** Medido: «grafico» sin tilde devolvía
      CERO resultados y «gráfico» devolvía dos. Se resolvió con una configuración de texto de
      Postgres propia (`espanol_sin_tildes`, migración `articles/0005`) que copia la de español y le
      antepone `unaccent` — la misma extensión que ya hacía buscable el maestro de jugadores. De
      paso vino el stemmer: «lanzadores» encuentra «lanzador».

      **Al tocar `search_fields` hay que correr `manage.py update_index`**: lo nuevo se indexa solo
      por señales, pero lo ya guardado no se entera. Sin eso, el buscador miente en silencio.

      ~~Pedido del dueño el 2026-07-27. Hoy solo se navega por categoría y
      por la lista; con cincuenta artículos publicados eso deja de alcanzar, y los hashtags no sirven
      de índice si no hay dónde escribirlos. Wagtail ya indexa `title`, `entradilla` y `cuerpo` —
      están declarados en `search_fields` de `ArticlePage`— así que la parte de datos está hecha:
      falta la caja, la página de resultados y decidir si comparte sitio con el buscador de
      jugadores del header o va aparte, dentro de `/articulos/`.~~ (resuelto: aparte, dentro del
      índice; el del header sigue siendo solo de jugadores para que buscar «Soto» no mezcle una ficha
      con un artículo sin decir cuál es cuál.)
- [x] **Paginación del índice.** **Hecha el 2026-07-27**: doce por página, con enlaces de verdad que
      arrastran la búsqueda y la categoría. Sustituye al botón de JavaScript, así que se fueron con
      él `articulos.js`, el `<noscript>` y el tope de 24 — y con eso queda cerrado también el
      QA-03/FE-03 del v8, que era el control muerto sin JavaScript.

      ~~Hoy se dibujan hasta 24 artículos y el botón los descubre de seis en
      seis sin ir al servidor (ver `TANDAS` en el modelo). Con cientos publicados eso es una página
      de cientos: ahí hace falta paginación de verdad. Es además la salida buena para el botón que
      queda muerto sin JavaScript — ver el rechazo razonado de QA-03/FE-03 en el review v8.
- [x] **Restringir el Backoffice al rol *Administradores*.** Hecho el 2026-07-27. A un redactor no
      le aparece el menú siquiera, y no por una regla suelta sino porque no tiene permisos sobre esos
      modelos — Wagtail esconde lo que no se puede tocar.
- [ ] **«Lo más leído» de verdad.** El panel dice «Lo más reciente» porque no hay analítica; el
      dueño lo prefirió así antes que inventar un ranking. Cuando haya cuentas de lectura, volver.

## Contenido

- [ ] Escribir los 8–12 artículos semilla (cuello de botella — **ya no está bloqueado**: el CMS
      quedó utilizable el 2026-07-27).

## Deferido a Fase 8 (hardening de prod) — de code review

- [ ] **Imagen prod separada:** Dockerfile de producción con `collectstatic` en el build, solo
  deps de runtime, `config.settings.prod` por defecto, gunicorn, y fallo-ruidoso si faltan
  secretos. (El manifest storage de prod requiere `collectstatic`, que hoy no corre en el build.)
- [x] **Vendorizar Bootstrap + fuentes.** **Hecho el 2026-07-27**, y entero: no queda una sola
      petición a terceros en ninguna página. 664 KB en `static/vendor/`, con su README y el script
      que los regenera. Se recortaron los alfabetos cirílico, griego y vietnamita —que un sitio de
      béisbol dominicano no va a usar— y eso solo ahorró 321 KB.
  Self-host mejora resiliencia (Principio #0), privacidad y prepara CSP.
- [ ] **`restart` policy** del contenedor web en el compose de prod.

## Templates — cuando existan las páginas (Fases 4–5)

- [x] ~~Nav (Artículos/Líderes/Jugadores/Entrar) y buscador apuntan a `#`/submit desactivado.~~
  **Hecho en FE-01**: escondidos hasta que las páginas existan, con el markup preservado en comentarios.

## Code review v3 — findings

Medidos, no asumidos. Ver `docs/reviews/code_review_v3.md`.

- [x] **DEV-02 — `backfill_batting_rates` sin cobertura.** Verificado: 0%, el módulo ni se importaba
  en la suite. Es una herramienta de escritura masiva sobre las tablas de stats. **Corregido.**
- [x] **DEV-04 — los filtros numéricos revientan con texto.** Reproducido: `rate`, `dec`, `pct` e
  `innings` lanzan `ValueError` con `"N/A"` → 500 en una página pública. **Corregido** (fail-soft en
  render, fail-loud sigue en ingest).
- [x] **SAB-03 — mejor marca personal sobre métricas descriptivas.** GB%, FB%, LD% y GB/FB no tienen
  "mejor": un extremo solo dice que cambió el perfil. **Corregido**: no se resaltan.
- [ ] **DEV-01 — todos los tabs se calculan en cada request.** Cierto, pero **la magnitud del finding
  está sobrestimada**: medido son 25 queries / 415 ms para Pedro Martínez (dos tabs completos) contra
  16 / 221 ms para Ortiz (uno). El segundo tab cuesta 9 queries, no cientos, y ~340 ms de esos 415
  son latencia de red contra 10.0.0.39. No es urgente, pero cada tab nuevo cobra impuesto: con Fildeo
  real y luego Splits/Game Logs sí se nota. Agregado un test de presupuesto de queries para que no
  crezca en silencio; la carga diferida (HTMX o endpoints por tab) queda pendiente.
- [x] **DEV-03 — las tablas repiten listas de columnas a mano.** **Corregido** con el refactor declarativo que el propio finding proponía: `profiles/columns.py` define `Column(label, attr, fmt)` y las listas por división, y las plantillas rinden con partials comunes (`{% include "profiles/_season_head.html" with cols=… %}`). Hoy quedan CERO `<th>` escritos a mano en las tablas de bateo, pitcheo, fildeo y puestos. Fildeo se construyó ya sobre esto, que era justamente el plazo que el finding se ponía.
  ~~ Real y ya lo sufrimos: cada columna
  agregada (LOB, TotAvg, BsR, G, AB) obligó a editar encabezado + fila + total en varios bloques, y
  las desalineaciones solo se detectaron con un script ad-hoc. **Conviene resolverlo ANTES de Fildeo**,
  que sería la tercera copia del patrón. Propuesta: mover las columnas a una lista declarativa en
  Python `(label, attr, formato, clase)` y renderizar con un partial común.
- [x] **SAB-02 — boards descriptivos etiquetados como "mejor/peor".** **Corregido** al construir Líderes: las métricas de `DESCRIPTIVE_COLUMNS` rotulan sus dos tablas «Los más altos» / «Los más bajos» en vez de primeros/últimos, y el tooltip del signo en Puestos dice «ordena de más alto a más bajo (perfil, no mejor/peor)».
  ~~ GB%, FB%, LD% y GB/FB se
  rankean, pero llamarlos "mejor" implica un valor competitivo que no tienen. La corrección natural
  es de etiquetas ("Más alto / Más bajo") y vive en la UI de líderes, que **todavía no existe**
  (Fase 5). Cuando se construya, usar la misma marca de métrica descriptiva que ya usa SAB-03.
- [ ] **SAB-01 — la cobertura Statcast se decide por año, no por completitud.** El reviewer llegó de
  forma independiente al hueco de 2000-2001 que ya está documentado en `MEJORAS_FUTURAS.md`. Decisión
  del dueño: dejarlo así por ahora. Su sugerencia extra —advertirlo en la UI, no solo en el backlog—
  sigue disponible y es barata.

## Incidente — el scheduler llevaba días sin correr (2026-07-26)

**Encontrado por accidente**, midiendo duraciones de jobs para evaluar QA-01 del review v6: los
`update_*` no tenían **ni una sola** corrida en `IngestRun`. El log de Ofelia lo confirmó:

```
27 corridas fallidas · 1 exitosa
error creating exec: No such container: dglweb-web-run-9eeececf11da
```

**Causa raíz.** Los jobs vivían como `labels` del servicio `web` y Ofelia los descubría por el socket
de Docker. Pero **`docker compose run` clona las etiquetas del servicio**: cada comando suelto creaba
un contenedor efímero con `ofelia.enabled=true`, Ofelia se re-apuntaba a él, el contenedor moría con
`--rm`, y desde ahí todos los jobs fallaban para siempre. Verificado en vivo antes y después del
arreglo.

**Lo que lo hizo invisible.** `IngestRun` existe para que un fallo silencioso sea una fila roja en el
Backoffice — pero **no puede registrar un job que nunca llegó a arrancar**. El log se veía limpio
porque no había nada que registrar. Los datos estaban al día solo porque los `import_*` se corrieron
a mano.

**Corregido**: el calendario salió a `ofelia/config.ini`, apuntando por **nombre de contenedor** en
vez de por etiqueta, y el scheduler arranca con `--config` en lugar de `--docker`. Un contenedor
efímero ya no puede robarle el objetivo (comprobado: los `-run-` ahora nacen sin la etiqueta).
Verificado que registra los 11 jobs y que el `exec` por nombre ejecuta el comando.
De paso la imagen de Ofelia queda pinneada por digest — es el contenedor con el socket de Docker
montado, o sea donde menos conviene una actualización sorpresa (parte de SEC-01 del v6).

### Pendiente de este incidente

- [x] **Recrear el servicio `web` para que tome el `container_name`.** **Hecho**: el huérfano era un `cd458e3c94dd_dglweb-web-live` en estado *Created* que nunca arrancó (el `dglweb-web-1` ya se había ido solo). Se borró y se levantó `web` desde compose. Ahora lo gestiona compose, sin etiqueta de Ofelia y con el volumen `dglweb_uploads` montado. **Y destapó otra cosa**: el contenedor viejo apuntaba a la base real por una variable puesta a mano, así que al recrear el sitio se fue a la base local. `DATABASE_URL` ahora sale de `.env`.
  ~~ El compose ahora fija
  `container_name: dglweb-web-live`, que es el nombre al que apunta el scheduler. Hoy el contenedor
  que sirve YA se llama así, pero quedó además un `dglweb-web-1` **parado desde hace dos días** que
  bloquea la recreación por conflicto de nombre. Hay que borrar ese contenedor muerto y levantar de
  nuevo — es cosa de una vez, y sin eso un `docker compose up -d web` futuro fallaría.
- [x] **Vigilar que el scheduler se note cuando falla.** **Hecho a medias, y a propósito**: existe
  `/health/pipeline`, que responde 200 o 503 según el último `refresh_daily`. Cubre los DOS modos de
  fallo con una sola respuesta — corrió y algo falló (la fila no es `success`), y **no corrió**
  (no hay fila reciente), que es el que ninguna alerta interna puede detectar porque una ausencia no
  deja rastro que consultar. Fuera de temporada devuelve 200: un 503 diario durante el invierno
  enseñaría a ignorar la alerta, y una alerta ignorada es peor que ninguna.
  Falta la otra mitad, que es quién lo mira — ver abajo.
  ~~ Este incidente duró días sin señal. Una
  alerta barata: si `IngestRun` no tiene ninguna corrida de `update_batting` en las últimas 48 horas
  dentro de temporada, algo está roto. Encaja natural en el orquestador de QA-01+ARCH-01.

## Code review v7 — findings (2026-07-26)

Ver `docs/reviews/code_review_v7.md`. Doce hallazgos que son **seis problemas**: el review los reporta
desde varias personas y se solapan (DEV-01 = ARCH-01 = QA-01, DEV-02 = ARCH-02, DEV-03 = SAB-02,
QA-02 = FE-01). Acá van agrupados por problema, que es como se arreglan. Verificados uno por uno
contra el código antes de aceptarlos.

### P1 — integridad del dato

- [x] **Una sola temporada activa, garantizada por la base** *(DEV-01 + ARCH-01 + QA-01)*. **Corregido.**
  Verificado: `seasons_dates` solo tiene unicidad por `(season, sports_id)`, `clean()` no menciona
  `is_active` ni una vez, y el loader compara las activas *dentro del CSV* pero no contra las que ya
  están guardadas. Como el dataset es **upsert**, un CSV que no incluya la temporada vieja la deja
  activa junto a la nueva.
  Lo grave es cómo falla: `season_window` resuelve el empate con `order_by("-season").first()`, así
  que el sistema **no se rompe, se equivoca en silencio** — el scheduler corre o salta según una
  temporada que nadie eligió. Es el mismo patrón del incidente de Ofelia: lo que no avisa es peor que
  lo que falla.
  **Arreglado en tres capas**, porque hay tres caminos que escriben esta tabla:
  1. **La base** — `UniqueConstraint` parcial con `condition=Q(is_active=True)` por `sports_id`
     (migración `0025`). Es la única que nadie puede saltarse.
  2. **`clean()`** — repite la regla consultando la base y excluyendo `self.pk`, para que el
     Backoffice diga *cuál* es la temporada que estorba. La constraint dice que la regla se rompió;
     no dice qué fila hay que apagar.
  3. **El loader** — compara la activa entrante contra las activas ya guardadas que el CSV **no
     trae**. Era la mitad que faltaba: el export normal del año siguiente trae 2026 y no vuelve a
     mencionar 2025, así que el archivo está perfecto y aun así la tabla acaba con dos.

  Verificado contra la base real: rechaza la segunda activa con `IntegrityError`, `clean()` nombra
  a 2026 como la culpable, y editar la que ya es la activa sigue funcionando.
  Seis tests nuevos, incluido el que el review pedía (2025 activa persistida + CSV que solo trae
  2026) y su contrario, el camino bueno — un validador que no deja hacer lo correcto se termina
  desactivando.

- [x] **cERA de carrera se pondera por juegos, no por entradas** *(SAB-01)*. **Corregido.**
  Verificado: `career_rate.WEIGHT["fielding"] = "gp"` y `catcher_era` no está en `_FIELDING`, así que
  el motor lo prorratea por juegos. Dos temporadas de 50 juegos pesan igual aunque una sean 900
  entradas detrás del plato y la otra 90 — que es la diferencia entre un receptor titular y un
  cambio defensivo.
  **El review se queda corto en la solución**: ponderar por `innings_outs` no es solo *mejor*, es
  **exacto**. Como cERA = 9·ER/IP, la media ponderada por entradas Σ(cERA·IP)/ΣIP colapsa a
  9·ΣER/ΣIP, que es la cERA de carrera de verdad. Pasa de aproximación a fórmula cerrada.
  **Arreglado**: el motor de carrera pasa de un peso por oficio a un peso **por tasa**
  (`career_rate.PESO_PROPIO`), y la cERA declara el suyo, `innings_outs`.

  De regalo, el cambio arregla algo que nadie había reportado: el peso se sumaba mirando solo el
  tiempo de juego, viniera o no la tasa, así que una temporada con entradas pero **sin** cERA
  registrada entraba en el divisor y no en el dividendo, y empujaba la carrera hacia abajo. Ahora
  cada tasa suma peso solo cuando tiene valor. Vale para todas, no solo para la cERA.

  Medido reconstruyendo la base real: **28 de 52 receptores cambiaron**, media 0,095 y máximo 1,04.
  El caso extremo es el ejemplo perfecto — Guillermo García, 82,7 entradas en 11 juegos con 6,31 y
  luego 4,3 entradas en 3 juegos con 0,00: por juegos daba 4,96 y por entradas da 6,00. Tres
  apariciones de un inning le rebajaban la carrera un punto entero.

  Comprobado además que el valor guardado ES la media ponderada por entradas, recalculándolo a mano
  desde `position_totals()` para los 50 receptores: cero discrepancias.

### P2 — concurrencia y acceso

- [x] **`build_career_totals` no tiene candado** *(DEV-02 + ARCH-02)*. **Corregido.**
  Verificado: `build_leaders` toma `pg_advisory_xact_lock` antes de reconstruir; `career_totals` no
  tiene nada, y borra e inserta las tres tablas de carrera. Son una cadena (`rebuilds.py`) con solo
  la segunda mitad protegida.
  Dejó de ser teórico cuando se implementó que cargar datos de apoyo dispare los rebuilds: ahora el
  Backoffice y el orquestador pueden reconstruir a la vez, cada uno sobre una foto distinta, y el que
  termine último publica.

  **Arreglado con UNA sola clave en dos niveles** (`stats/locks.py`), que es lo que evita razonar
  sobre el orden en que se toman — de ahí salen los abrazos mortales:
  * **De sesión**, tomada por quien corre la cadena completa: el orquestador (`pipeline.py`) y el
    hilo del Backoffice (`rebuilds.py`). Cubre los dos comandos y NO se suelta entre uno y otro.
  * **De transacción**, dentro de cada comando, para cuando alguien lo corre suelto desde
    `manage.py`.

  Funciona porque los advisory locks de Postgres son **reentrantes dentro de una sesión**: el comando
  vuelve a pedir la clave que su propia cadena ya tiene y sigue de largo, mientras que otra sesión
  espera.

  Comprobado contra Postgres real, con dos conexiones: la segunda cadena espera (1,01 s medidos) y
  entra en cuanto la primera suelta; el comando no se cuelga dentro de su propia cadena; y una
  excepción a mitad del rebuild no deja el candado tomado — cero `advisory` colgados después.
  Cuatro tests, uno de ellos leyendo el código para que nadie le dé a un comando su propia clave
  «para que no se estorben», que es exactamente lo que hay que evitar.

- [x] **El detalle de la pizarra solo se abre con el mouse** *(QA-02 + FE-01)*. **Corregido.**
  Verificado: `pizarra.js` solo escucha `mouseenter`/`mouseleave`, y la tarjeta no tiene `tabindex`
  ni `role`. **En un teléfono no hay hover**: se ve la banderita que promete dominicanos y no hay
  forma de llegar al detalle ni a los videos.
  Pesa más ahora que antes, porque este panel creció: enseña la línea de los juegos en curso y el
  abridor probable de los que no han empezado.

  **Arreglado.** La tarjeta con detalle pasa a ser un control de verdad: `role="button"`,
  `tabindex="0"`, `aria-expanded` y `aria-controls` apuntando al panel. Abre con clic —que es lo
  único que un teléfono puede hacer—, con Enter, con Espacio y al recibir el foco; cierra con Escape,
  con un toque fuera o al salir. El hover se queda como comodidad del ratón.

  **Lo que casi se me pasa**: hacer la tarjeta focusable no bastaba. El panel está DESPUÉS de las
  quince tarjetas en el orden del documento, así que tabular desde una tarjeta llevaba a la
  siguiente, nunca a los nombres ni a los botones de video — medido, no supuesto. Por eso Enter y
  Espacio además **meten el foco dentro del panel**, y Escape lo devuelve a la tarjeta.

  Comprobado en el navegador: Enter deja el foco en «J. Ramírez», tabular dentro no cierra, hay 3
  elementos alcanzables, Escape cierra y vuelve, el clic alterna, y Espacio abre sin desplazar la
  página. Las 15 tarjetas tabulables con su ARIA completa.
  El único punto que no se pudo probar con eventos reales es el foco: el panel del navegador va
  oculto (`document.hasFocus()` en falso) y el motor no emite `focus`. Con evento sintético el
  manejador responde bien.

### P3 — higiene

- [x] **`/health/pipeline` entrega el detalle de los fallos a cualquiera** *(SEC-01, aceptado a medias)*. **Corregido.**
  **No estoy de acuerdo con cerrar el endpoint.** Que responda 200/503 sin autenticación fue una
  decisión deliberada del dueño: el que tiene que leerlo es un monitor de uptime externo, y pedirle
  credenciales a un servicio gratuito es cambiar una fuga menor por un monitor que nadie configura.
  **Sí estoy de acuerdo con la parte concreta**: en el fallo, la respuesta incluía `pasos` con el
  `detail` completo del `IngestRun` —nombres de comandos y el texto del error—, que es lo único con
  valor de reconocimiento.

  **Arreglado.** El anónimo recibe `{"status": "ok"}` o `{"status": "error"}` y nada más; el código
  HTTP no cambia, así que el monitor externo sigue enterándose igual. El cuerpo completo lo ven dos:
  el personal del Backoffice por su sesión —ya ve el log de ingesta entero, no hay nada que
  ocultarle— y quien mande `X-Monitor-Token` con el valor de `PIPELINE_HEALTH_TOKEN`.

  Tres decisiones dentro del arreglo:
  * **El token en un encabezado y no en la URL.** Una query string acaba en los logs del servidor,
    en el historial del navegador y en el `Referer` de cualquier enlace que se pulse.
  * **`compare_digest` y no `==`.** Acá el riesgo de medir tiempos es remoto, pero la excepción es lo
    que se termina copiando a un sitio donde sí importa.
  * **Sin token configurado, nadie anónimo ve detalle.** El default inverso —«sin token, sin
    restricción»— es el fallo clásico: el sitio sale a producción sin la variable y el recorte no
    protege nada.

  Verificado en vivo: `/health/pipeline` anónimo devuelve `{"status": "ok"}`. Seis tests nuevos.
  **Falta una línea de operación**: poner `PIPELINE_HEALTH_TOKEN` en el `.env` del VPS y dárselo al
  monitor de uptime cuando se configure — va junto al pendiente de arriba, no antes.

- [x] **Siglas españolas en los `verbose_name` de los modelos de stats** *(DEV-03 + SAB-02)*. **Corregido.**
  Verificado: quedan `J`, `AP`, `C`, `BR`, `AR`, `P`, `GP`, `TS`, `ES`. `docs/AUTORIDAD.md` manda
  siglas inglesas y las columnas que ve el lector ya las usan (`profiles/columns.py`), así que esto
  es metadata desalineada, no un error visible.
  No urge —esas tablas no tienen CRUD— pero es exactamente por donde vuelve: cualquier admin
  genérico, export o formulario futuro las reintroduce sin que nadie lo decida.

  **Arreglado**: 15 etiquetas, migración `0026`. Ocho no se inventaron — el sitio ya las mostraba así
  en `profiles/columns.py` (`G`, `R`, `SO`, `IBB`, `HBP`, `LOB`, `RP`) y el mapeo de la fuente ya
  usaba `PA`, `SB`, `CS`, `SH`, `SF`. Los modelos eran los únicos desalineados.

  | campo | decía | dice |
  |---|---|---|
  | `g` `pa` `r` | J AP C | **G PA R** |
  | `sb` `cs` `so` | BR AR P | **SB CS SO** |
  | `ibb` `nibb` `hbp` | BBI BBNI GP | **IBB NIBB HBP** |
  | `sh` `sf` `lob` | TS ES DEB | **SH SF LOB** |
  | `bb_per_so` `pa_per_so` `runs_produced` | BB/P AP/P CP | **BB/SO PA/SO RP** |

  `total_avg` se queda en `TA`: *Total Average* ya es inglés.
  Y los tres `"CI"` de los mapeos **no se tocan**: son claves del payload de MLB —*catcher
  interference*— y no etiquetas nuestras. Queda dicho para que nadie los «arregle».

  Con guardián: `tests/test_autoridad_siglas.py` recorre por introspección todos los campos de la app
  `stats` y falla si aparece cualquiera de las veinte siglas prohibidas, diciendo cuál poner. Lleva
  además un test que comprueba que `AUTORIDAD.md` sigue diciendo esto — sin ese anclaje la regla
  queda huérfana y la siguiente persona la borra por molesta en vez de discutirla.


## Code review v6 — findings (2026-07-26)

Ver `docs/reviews/code_review_v6.md`, donde cada finding lleva la evaluación completa. Acá va solo lo
**aceptado**, con su prioridad. Lo diferido y lo ya conocido se justifica allá y no se duplica acá.

### Corregidos en el momento

- [x] **SAB-02 — la detección de debuts no miraba fildeo.** **Corregido**: `detect_debuts` barre los
  tres oficios. Era una incoherencia con una decisión ya tomada — el dueño había pedido incluir
  fildeo en la lista de "vieron acción" del índice por este mismo motivo, y el principio no se había
  aplicado acá. **Impacto medido hoy: cero** — de los 1.323 jugadores con fildeo en 2026, ninguno
  carece de bateo o pitcheo, porque la API emite línea de bateo para cualquiera que aparezca. Lo que
  se compra es no depender de esa costumbre de la API.
- [x] **DEV-01 — `except Exception` en `debuts._detail()`.** **Corregido**: captura los tipos
  concretos y loguea con `exc_info`. Violaba `CODING_STANDARDS.md` y convertía un bug de contrato en
  un debut sin nombre, que es la peor forma de enterarse: no falla nada, solo empeora el dato. De
  paso destapó un test que pasaba solo porque se atrapaba cualquier cosa.

### P2 — antes de que el sitio dependa de que el pipeline no falle

- [x] **QA-01 + ARCH-01 — el pipeline diario necesita un orquestador, no diez horarios.** **Corregido**: nace `refresh_daily` (`stats/pipeline.py`). Corre los pasos en orden, lee el `IngestRun` de cada uno —no si lanzó excepción, porque un comando puede terminar limpio y haber quedado en PARTIAL— y **no reconstruye los derivados si alguna entrada falló o quedó parcial**. Publicar igual existe pero hay que pedirlo: `--publicar-parcial`.
  Deja UNA fila `refresh_daily` con el estado del día, abierta ANTES de trabajar para que un refresco colgado se vea. Un paso que no deja fila cuenta como fallo — es exactamente lo que pasó con Ofelia, donde el log limpio se leía como «todo en orden».
  El calendario pasó de once jobs a dos. Medido contra la base real: 6/6 pasos, 417.470 filas, 80s.
  ~~ Un solo
  pendiente porque son el mismo hallazgo desde QA y desde arquitectura, y ya venía del v5 (QA-03).
  Hoy `build_leaders` corre a las 7:30 aunque `update_fielding_post` haya fallado, y publica
  liderazgos con mezcla de dato nuevo y viejo sin que `/health` se entere. **Forma**: un comando
  `refresh_daily` con pasos, estado agregado y una decisión explícita de publicar parcial, en vez de
  encadenar por reloj.
  **Por qué P2 y no P1**: el rebuild es completo y no incremental, así que un día malo se cura solo a
  la mañana siguiente. Es un problema de calidad de dato temporal, no de integridad permanente.
- [ ] **QA-02 + ARCH-02 — el rebuild de Backoffice puede no dejar rastro.** El hilo daemon fue
  decisión consciente (ver `rebuilds.py`) y el cron de la mañana es su red de seguridad. Pero hay una
  ventana real que no estaba cubierta: **si el hilo muere antes de que el comando cree su
  `IngestRun`, la carga queda aplicada sin ninguna evidencia de su rebuild**. Son milisegundos, pero
  el resultado es indistinguible de "nunca se lanzó".
  **Forma mínima aceptada**: crear la fila padre ANTES de lanzar el hilo y mostrar su estado en la
  pantalla de carga. La cola con retry es rediseño y no entra antes del lanzamiento.

### P3 — cuando haya qué lo justifique

- [x] **SEC-04 (parcial) — topar el largo de `q` en el buscador.** **Hecho**, y el tope sale del propio modelo: `full_name` mide 50, así que una consulta más larga no puede estar contenida en ningún nombre. Devolver vacío sin ir a la base es el resultado CORRECTO, no una heurística — la protección viene de regalo. Con test que exige cero consultas.
  ~~ Una línea, evita que alguien mande
  una consulta de un megabyte al endpoint público. El rate limiting completo NO se acepta por ahora:
  el costo por consulta es un `LIKE` sobre 984 filas, así que como vector de abuso rinde muy poco, y
  el throttle real necesita middleware y almacén compartido.
- [ ] **FE-02 — tests de teclado del buscador (flechas, Enter, Escape, la fila "ver todos").** El
  riesgo es real; el costo no son los tests sino **montar el corredor**, que trae Node a un gate que
  hoy es solo Python. Se verificó a mano en navegador. Vale la pena cuando exista una segunda pieza
  de JS: con una sola, el corredor cuesta más que lo que protege.
- [ ] **ARCH-04 — falta un `/ready` que valide DB y migraciones.** `/health` está bien como está: no
  toca la DB **a propósito**, para que un parpadeo de Postgres no mate un proceso web sano. Lo que
  falta es el readiness, y hoy **nadie lo consumiría** — no hay orquestador ni pool de instancias.
  **Va con Fase 8**, junto al compose de producción: un endpoint de readiness que nadie consulta es
  solo código.

### Diferidos con disparador explícito

- [ ] **DEV-02 + ARCH-03 — upsert fila por fila y metadatos de política en el `Loader`.** El
  diagnóstico es correcto, pero hoy hay **un** dataset en upsert con **70 filas**. **Disparador: el
  segundo dataset en upsert, o el primero con miles de filas** — ahí se hace antes de su primera
  carga, y con dos casos reales que comparar el diseño sale del uso y no de la especulación.

## Por decidir (traído del CONCEPT)

- [ ] **Proveedor de ad server** (GAM vs AdButler/Broadstreet/AdSpeed vs construirlo acá).

  **El criterio cambió el 2026-07-27.** El dueño puso el dato que faltaba: esto es para República
  Dominicana, donde lo que paga AdSense es ínfimo. Así que **el relleno programático no es el
  negocio**: el negocio es la venta directa a anunciantes dominicanos, y el dueño necesita colgar sus
  propios anuncios. Eso reordena lo que hay que buscar:

  1. Cargar la creatividad propia con fechas de inicio y fin.
  2. Rotar varios anunciantes en el mismo hueco.
  3. **El reporte para el anunciante** — impresiones y clics. Es lo que RENUEVA el contrato: quien
     pagó un mes va a preguntar cuánta gente lo vio, y «no sé» no vende el segundo mes.

  Lo que NO hace falta: subastas, segmentación fina, integraciones programáticas. Las tarifas de este
  mercado son planas por mes, no por millar.

  **Recomendación: Google Ad Manager**, ya no por su demanda —que se ignora— sino porque como
  servidor de venta directa hace las tres cosas y **cuesta cero**, con roles para delegar el día a
  día (requisito del dueño). El pero: es la herramienta más compleja de las cuatro y se usaría una
  fracción pequeña. Plan B si la interfaz espanta: **AdSpeed** (barato y simple). **Broadstreet**
  encaja como un guante con el modelo —prensa local vendiendo a comercios locales— pero es el más
  caro.

  **Tercera opción, que con este criterio deja de ser exótica: construirlo en el Backoffice.** Las
  necesidades son inusualmente simples y la infraestructura ya está: CMS con roles, un Backoffice
  donde las herramientas se agregan sin tocar el menú, Postgres y un scheduler. Sería anunciante,
  imagen, enlace, hueco, fechas, peso, y contadores de impresiones y clics. Costo cero y sin
  dependencia externa. La letra chica: contar impresiones de verdad tiene trampas (bots que inflan,
  cachés que esconden) y es código propio que mantener, además de trabajo antes del lanzamiento.

  **Siguiente paso sugerido:** abrir una cuenta de GAM y montar un banner de prueba. Es gratis y en
  una tarde se sabe si la interfaz sirve o espanta — y esa prueba decide entre las tres mejor que
  cualquier comparativa.

  ⚠️ Los precios de estas plataformas son conocidos hasta mayo de 2026 y cambian; verificar antes de
  contratar. Del lado del código no urge: los huecos ya están en las plantillas, con alto fijo y
  agnósticos de proveedor. Elegir es pegar una etiqueta en un sitio.
- [ ] Listado exacto de métricas sabermétricas por página de jugador.
- [x] **Redactar legal: privacidad + cookies + ToS.** (2026-07-27) Los tres documentos están escritos
  y publicados en `/legal/privacidad/`, `/legal/terminos/` y `/legal/cookies/`, enlazados desde el
  pie de todas las páginas. Son plantillas del repositorio y no páginas del CMS: un aviso legal no
  se puede despublicar con un clic, y el historial que importa ante un reclamo es un `git log` con
  fecha y autor, no las revisiones de Wagtail.

  Describen lo que el sitio hace HOY, medido: quien solo navega **no recibe ninguna cookie** ni deja
  nada en el almacenamiento del navegador, y las páginas públicas **no piden nada a terceros** desde
  que se vendorizaron las fuentes. Las dos afirmaciones están sostenidas por pruebas
  (`tests/test_legal.py`), así que el día que entre una etiqueta de analítica o de anuncios el gate
  se cae y obliga a actualizar el texto — que es el fallo clásico: la política que se queda atrás
  del código sin que nadie lo note, porque una cookie no se ve.

  **NO hay cartel de consentimiento, a propósito.** No hay ninguna cookie no esencial que consentir,
  y un cartel que pide permiso para nada enseña a pulsar «aceptar» sin leer. Se construye cuando
  entre la primera, o sea con la publicidad — y la página de cookies ya declara por escrito el
  compromiso de cómo será (rechazar tan fácil como aceptar, nada se instala antes de elegir).

  Pendiente y **es del dueño**: confirmar los cuatro datos marcados con `# ← confirmar` en
  `dglweb/core/legal.py` —identidad del responsable, buzón de contacto, proveedor de alojamiento y
  días de retención de los registros del proxy— y que un abogado revise la calificación jurídica.
  El texto describe los hechos con exactitud; que esa descripción cumpla la Ley 172-13 y el RGPD lo
  tiene que decir alguien habilitado, sobre todo antes de que entren anuncios o cuentas de usuario.

  **El responsable declarado es Adcio Media**, la agencia que gestiona el sitio — no quien escribe
  el código. Quien responde ante un reclamo de datos personales tiene que ser quien decide qué se
  publica y para qué.

  **El aviso de Retrosheet**, en inglés y palabra por palabra, con la traducción al lado marcada
  como tal — lo que la licencia autoriza es el texto en inglés y no una versión nuestra. Es la única
  condición que ponen a cambio de dejar usar sus datos. Estuvo en el pie de todas las páginas y hoy
  vive solo en los términos, por decisión del dueño al considerarlo redundante; queda apuntado en
  `core/legal.py` que es la lectura menos conservadora de «prominently», y la vuelta atrás es
  descomentar el bloque de `base.html`. Dos pruebas lo vigilan: que siga publicado y que nadie lo
  haya reescrito.

  **Página de contacto** en `/contacto/`, enlazada desde el pie. Es una dirección de correo y no un
  formulario, y es una decisión: un formulario exige servidor de salida, defensa contra robots y
  dónde guardar lo que llega, y mientras alguna de las tres falle acepta el mensaje, dice «gracias»
  y lo tira. Un `mailto` no puede fallar en silencio. El buzón es
  `alberto@dominicanosengrandesligas.com` — uno solo y no tres alias por tema, porque un buzón que
  nadie lee es peor que no publicar ninguno. Con eso **quedan tres** de los cuatro `# ← confirmar`.

  **El pie pasó a cuatro columnas** (marca · agencia · secciones · legal). La ficha de Adcio Media
  tenía su propia franja bajo el filete y costaba unos 60px de alto en todas las páginas para decir
  tres líneas: 270px → 207px.
- [ ] Dónde/ cuándo se activa el muro de registro (post-launch).

## Code review v4 — findings (2026-07-24)

Ver `docs/reviews/code_review_v4.md`. Evaluados uno a uno; mi acuerdo/decisión:

- [x] **DEV-01 — `mypy .` no estaba verde.** De acuerdo, real: el gate corría `mypy dglweb`
  (78 archivos) y no veía los tests. `mypy .` fallaba en `tests/test_profiles.py` (`_flat`
  iterando `object`). **Corregido** (helpers de test tipados con `Any`). **El gate ahora corre
  `mypy .`, no `mypy dglweb`.**
- [x] **SAB-01 — Puestos llamaba "mejor" a métricas descriptivas.** De acuerdo. GB%/FB%/LD%/GB-FB
  no tienen dirección deportiva. **Corregido**: el tooltip del signo dice "ordena de más alto a más
  bajo (perfil, no mejor/peor)" para descriptivas (misma regla SAB-02 que ya usa Líderes).
- [x] **SAB-04 — fildeo de postemporada sin explicación.** De acuerdo, barato. **Corregido**: nota
  en el caption ("registro descriptivo; no participa en liderazgos por ahora").
- [x] **DEV-03 (parcial) — comentario/label de `Metric.postseason` decía "reservado".** Ya no lo es.
  **Corregido** el label y el comentario (migración 0013).
- [x] **DEV-02 — liderazgo de postemporada de UNA sola ronda no se pintaba como líder de temporada.**
  El dueño eligió la **opción A**: una fila `line` que es la única de su temporada ES el agregado de
  todo su octubre, así que lleva el badge (nunca una ronda *parcial* de un octubre de varias).
  **Corregido** el overlay + comentarios contradictorios. Con test. Validado: Felipe Alou 1962 (SM de
  una ronda) ahora marca sus liderazgos. Cambio de UI, no toca el motor ni requiere rebuild.
- [x] **DEV-03 (gating) — los boards de octubre ignoran `best_season`/`best_career`.** **Corregido**:
  `_postseason_leaders` / `_postseason_rate_leaders` gatean el board de carrera por `best_career` y el
  de temporada por `best_season`; los predicados `_wants_postseason*` saltan si no se quiere ninguno.
  Con test. (No hubo que reconstruir: 0 métricas de octubre tenían un flag apagado.)
- [x] **DEV-04 — `_innings_to_outs` acepta fracciones imposibles (.3, .9, .25).** **Corregido**:
  la fracción solo puede ser vacío/0/1/2; cualquier otra cosa (`.3`, `.9`, `.25`, basura, doble punto)
  retorna `None` en vez de un outs plausible-pero-falso. Fail-soft en ingest → sale como disparidad en
  paridad. Tests para `.3`/`.9`/`.25`/`abc`/`111.1.2`. (No re-ingesté: la fuente manda notación válida;
  si algún día se re-ingesta fildeo, un valor malo pasaría a NULL y saltaría en paridad.)
- [ ] **DEV-05 — todos los tabs se calculan por request.** → **Es el mismo ítem que DEV-01 del v3**, que es donde se sigue con la medición.
  ~~ Ya conocido (v3 DEV-01). Carga diferida
  (HTMX/endpoints por tab) sigue pendiente; el test de presupuesto de queries es el guardarrail.
- [x] **SAB-02 — panel de receptor sin CS%.** **Corregido**: columna **CS%** (property `cs_pct` en
  `Fielding`/`FieldingCareer`, `CS/(SB+CS)`, recomputada de los conteos de la fila; None sin intentos).
  Caption aclara que CS% normaliza el volumen crudo y que cERA es contexto (depende del staff), no una
  evaluación defensiva fuerte. Validado: Tony Peña carrera 34.9 %.
- [x] **SAB-03 — cobertura Statcast es piso por año, no por métrica (hueco 2000-2001).**
  **Resuelto, pero no como proponía el finding.** La salida no fue "cobertura por métrica" sino
  **traer el dato que faltaba**: Retrosheet tenía la trayectoria de esos años con 97% de cobertura,
  o sea que el hueco era de nuestra fuente y no del registro histórico. Cargado por la Fase 4e
  (`docs/DATOS_DE_APOYO.md`), 2000 pasó de 1,8% a 97,3%, 2001 de 2,2% a 97,6% y 2002 de 86,5% a
  98,2%. Sammy Sosa 2000 pasó de que sus coeficientes sumaran 55,9% a sumar 97,3%, y su LD% de .036
  a .218. La advertencia de la UI bajó de diez temporadas a siete.
  **Residuo, separado abajo**: la advertencia sigue siendo por año.
- [ ] **SAB-03b — la advertencia marca el panel entero cuando solo los hits están incompletos.**
  Ojo con la redacción: en las siete temporadas que quedan (1989-90, 1993-97) **el dato ya se trajo**
  — la carga de Retrosheet cubrió las diez, no solo 2000-2002. Lo que pasa es que ahí Retrosheet
  tampoco clasificó todo: en 1990 registra los 2.575 hits pero solo le puso trayectoria a 2.314. Ese
  10% no lo anotó nadie en 1990; es el techo del registro histórico, no algo por hacer.
  Lo que sí queda pendiente es de precisión en la UI: los cinco conteos de OUTS por tipo
  (AO/GO/FO/PO/LO) están completos en esos años, y hoy se advierte sobre el panel Statcast entero
  como si estuvieran todos afectados. Un piso por (métrica, temporada) lo diría con exactitud.
  **Prioridad baja**: la advertencia sobra en cinco columnas de doce, pero no miente.
- [x] **DEV-02 / FE-03 — `leaders_context()` revienta con la base vacía.** **Corregido**: `_empty_context()` devuelve un contexto renderizable y la plantilla tiene su rama para base vacía. Con test.
  ~~ **Reproducido**:
  `IndexError: list index out of range` en `division_labels[0]`. Pasa en staging limpio, base recién
  migrada, o si alguien desactiva las métricas de un grupo desde el Backoffice. Es el más grave
  porque tumba una página pública entera, no un caso de borde. Falta un contexto vacío renderizable.
- [x] **QA-01 / SAB-04 — las filas con `mlb_id` desconocido se descartan en silencio.** **Corregido**: se separa «sin mlb_id» (se descarta) de «mlb_id que no está en el maestro» (se acumula en `_huerfanas` y se reporta con conteo, hits perdidos y muestra de ids).
  ~~ Real, y el
  reviewer ve algo que a mí se me pasó: las descartadas **tampoco entran en los totales de cobertura**,
  así que un maestro incompleto hace que el CSV parezca MÁS sano de lo que está. La validación se
  autoengaña. Hay que separar "sin mlb_id" de "mlb_id que no existe en el maestro" y reportar el
  segundo con conteo y muestra.
- [x] **SAB-01 — la cobertura se valida por temporada, no por (temporada, oficio).** **Corregido**: la clave del acumulador es `(season, stat_group)`, así que un oficio roto ya no se esconde tras el otro completo.
  ~~ Verificado:
  `por_temporada.setdefault(row["season"], ...)` mezcla bateo y pitcheo. Si un oficio viene completo
  y el otro roto, el promedio pasa el 80% y el roto entra igual. Error mío al escribir `checks()`.
- [x] **ARCH-01 — cargar datos de apoyo no reconstruye lo que depende de ellos.** **Corregido**: el `Loader` declara `rebuilds = ("build_career_totals", "build_leaders")` y la vista los dispara sola al confirmar. Corren fuera de la transacción (son reintentables, y no hay por qué bloquear la tabla de origen un minuto) y en un hilo (si no, la respuesta HTTP espera el minuto que tarda `build_leaders`, que es justo lo que un proxy corta a los 30s). Quedan en `IngestRun` como cualquier corrida del scheduler. Documentado en `MOTOR_DATOS_APOYO.md`.
  ~~ Real y ya lo
  vivimos: tras la carga hubo que correr `build_leaders` a mano, y hasta que se corrió las páginas
  servían coeficientes viejos. `BattingCareer`/`PitchingCareer` tampoco se rehacen.
- [x] **SEC-01 — subida de CSV sin límite de tamaño.** **Corregido**: tope de 20 MB (el CSV real pesa ~250 KB) y rechazo por extensión, verificados ANTES de leer — no se decodifica en memoria algo que no se va a aplicar. El staging fuera de sesión sigue pendiente en ARCH-02.
  ~~ Verificado: no hay `DATA_UPLOAD_MAX_*` en
  settings, y el CSV entero se guarda en sesión. Aunque exige cuenta admin, un archivo grande tumba
  el proceso. Límite por dataset + rechazo por extensión + staging con TTL en vez de sesión.
- [x] **QA-04 — el nombre de archivo equivocado avisa pero deja confirmar.** **Corregido**: ahora es un `Problem` bloqueante. Un archivo bien nombrado es trivial de conseguir; una tabla reemplazada con el dataset equivocado, no.
  ~~ De acuerdo, y es
  incoherente con lo que yo mismo escribí en `DATOS_DE_APOYO.md`: que el chequeo existe para atajar
  cargar el CSV de salarios sobre la tabla de transacciones. Si solo avisa, no ataja nada.
- [x] **DEV-01 — 500 por `pk` inexistente o CSV no UTF-8.** **Corregido**: `get_object_or_404` y `UnreadableCSVError` que se convierte en `Problem`. Con tests de vista (7), que además cierran buena parte de QA-02.
  ~~ Real: `objects.get()` sin `get_object_or_404`
  y `decode("utf-8-sig")` sin capturar. Barato de arreglar.
- [x] **ARCH-04 — `StaticDataset` admite configuraciones que el motor no puede cumplir.** **Corregido**: `clean()` rechaza los tres casos y el formulario del Backoffice muestra el mensaje (verificado contra la vista real, no solo `full_clean()`). La FK se acepta escrita de las dos formas (`player` y `player_id`), que es el error de dedo más probable. 7 tests.
  ~~ Real: tabla
  sin loader, clave natural con columnas inexistentes, upsert sin constraint. Validar en `clean()`.

### Afinado del scheduler

- [x] **Los jobs `*_post` corrían toda la temporada, no solo en octubre.** **Corregido**: usan una
  ventana más corta, desde `post_season_start_date`. Medido con el dato real de 2026, dejan de correr
  del 25 de marzo al 28 de septiembre — unas 550 llamadas al proxy que ya no se hacen. Si la fecha
  falta caen al fin de la serie regular, y si tampoco está, a la apertura: se degrada hacia correr y
  nunca hacia callar, y el motivo del salto dice qué fecha se usó.

### Esperando dato, no código

- [ ] **Reactivar el tab Salarios del perfil.** **Decisión del dueño (2026-07-26): queda apagado por un buen rato — no se hará por ahora.** El código no se toca: sigue construido, probado y fuera de `REGISTRY`. No hace falta volver a evaluarlo hasta que la vista `v_dglweb_salaries` mejore de verdad, y quien la mejore será el dueño. Está construido, probado y **apagado a propósito**
  (línea comentada en `profiles/tabs.REGISTRY`). La fuente no da la talla: `dom_salaries` trae 1.385
  filas para 343 jugadores en sesenta temporadas, 2025 tiene 12 filas, y al dominicano mejor pagado
  de la historia le falta el registro — el máximo de todo el archivo es Luis Castillo con 24,15
  millones en 2024, cuando Soto cobró ~31 ese mismo año. Con esa cobertura el tab no informa,
  desinforma: un perfil que muestra tres de las doce temporadas que el pelotero cobró se lee como su
  historial completo, y el footer de advertencia no deshace esa lectura. **Bloqueado por la vista
  `v_dglweb_salaries`**, que el dueño está mejorando; cuando el dato esté, se descomenta una línea.
  Hay un test que fija el apagado para que volver sea una decisión y no un descuido.
  **Del review v6 (SAB-03), que confirma la decisión**: al reactivarlo, rotular la tabla como
  «salarios conocidos en DGL» y no como historial de carrera — y exigir antes una métrica de
  cobertura por temporada, no solo la impresión de que mejoró.

### Aceptados, menor prioridad

- [ ] **ARCH-02 — el borrador vive en sesión, no en staging auditable.** Buen señalamiento: sin id de
  revisión ni hash, dos admins pueden confirmar en orden cruzado. Es rediseño, no parche.
  **Decisión del dueño (2026-07-26): prioridad muy baja, no entra antes del lanzamiento.** El
  escenario que arregla exige DOS administradores cargando el mismo dataset a la vez, y hoy carga una
  sola persona una o dos veces al año. La parte urgente del finding —un CSV enorme decodificado
  entero en memoria— ya se cerró en SEC-01. Sube de prioridad el día que entre otra persona a cargar
  datos.
- [x] **ARCH-03 — `leaderboards.py` importa helpers privados de `tabs.py`.** **Corregido**: nace `profiles/metric_layout.py`, público, con lo que las dos pantallas comparten — `DESCRIPTIVE_COLUMNS`, `divisions_for()`, `pretty_qualifier()` y `qualifier_lookups()`. Ya no hay imports de nombres privados entre módulos de `profiles`. Con tests propios que fijan el acuerdo (ninguna métrica en dos divisiones, el umbral se escribe igual en las dos pantallas).
  ~~ Cierto y lo sufrí al
  agregar fildeo. Mover el layout de métricas y el formato de umbrales a un módulo público.
- [x] **QA-02 — las vistas de carga casi no tienen tests (31%).** **Corregido**: medido hoy, `staticdata/views.py` está en **91%** y `engine.py`/`loaders.py` en 98%. Los tests cubren permisos (anónimo, staff no-admin), los tres portazos (nombre, tamaño, binario), el pk inexistente, confirmar sin borrador, el camino feliz y el disparo de la reconstrucción.
  ~~ De acuerdo: es la pieza que
  reemplaza tablas y no está ejercitada end-to-end. Los tests que escribí cubren motor y loader.
- [ ] **SAB-02 — no se reconcilia lo cargado contra `H`/`BIP` de la fila.** La validación defensiva es
  correcta. **Matiz**: el modo de fallo que describe (coeficientes sumando >100%) no se materializó —
  medido tras la carga real, Sosa 2000 suma .973. La guarda de "solo pisar si tipifica más" ya evita
  el caso obvio. Vale igual como red de seguridad.
- [ ] **DEV-03 / DEV-04 — `compare()` carga todo en memoria; el upsert hace una query por fila.**
  Ciertos. Con 1.500 filas no se nota; el propio review dice que es tolerable. Documentar el límite
  del motor y volver si aparece un dataset grande.
- [x] **FE-02 — falta ARIA básico en nav/tabs/pills.** **Corregido**: cabecera (nav con nombre, `role="search"` + label del buscador, hamburguesa con `aria-label`/`aria-expanded`/`aria-controls`), pestañas del perfil con el juego completo (`aria-selected`, `aria-controls`↔`aria-labelledby`, `role="presentation"` en los `<li>`) y los cinco tablists con nombre propio. En Líderes NO se pusieron roles de pestaña a propósito: son enlaces que recargan, así que van en `<nav>` con nombre y `aria-current="page"`. Con tests (`tests/test_accessibility.py`) que fijan el acuerdo, incluido que cada tablist anuncie exactamente una seleccionada.
  ~~ Cierto y barato.

### Aceptados pero ya conocidos (no son de esta sesión)

- [x] **«Jugadores» del nav volvió**, apuntando a `/jugadores/`: índice con buscador (acentos y eñes
  insensibles vía `unaccent`) y la plantilla dominicana de la última temporada. Quedan escondidos
  Artículos (Fase 5) y Entrar (Fase 7).
- [x] **FE-01 — enlaces públicos que no hacen nada.** **Corregido**: cero `href="#"` renderizados en portada, perfil y Líderes, con un test que lo fija sobre el HTML servido. Se ocultaron nav (Artículos, Jugadores, Entrar), buscador y la columna Legal del pie; los "desglose ▸" pasaron a `<button>` porque sí hacen algo y eran acción, no destino.
  **Y apareció algo más grave que el finding**: los ocho enlaces de `home.html` estaban pegados a contenido INVENTADO —cinco titulares con fecha y firma, líneas de juego atribuidas a peloteros reales («Juan Soto 3-4, 2 HR», «Ayer · 15 jul») y una tabla de líderes de jonrones 2026 con números falsos—. En un sitio de estadísticas eso no es maquetado: son cifras falsas sobre personas reales en la primera página. Se sacó completo y NO se reemplazó por otros titulares o números. La portada quedó con un `h1` de verdad (no tenía) y el enlace a Líderes.
  **Pendiente de Fase 5**: la portada necesita contenido. El panel de líderes es el primero que conviene rehacer, porque el dato ya existe en `dgl_leader` y solo falta la consulta.
  ~~ Verificado: 7 `href="#"` en `base.html` y 8 en
  `home.html`, más el buscador con `onsubmit="return false"`.
- [x] **QA-03 — el scheduler encadena por horario, no por workflow.** **Corregido** con `refresh_daily` — es el mismo ítem que QA-01 + ARCH-01 del v6, que es donde se sigue. Anotado tres veces en tres reviews; se cuenta una.
  ~~ Ya está en `MEJORAS_FUTURAS.md`
  como "A DISCUTIR". El review coincide.
- [ ] **SAB-03 — la temporada en curso no tiene umbrales prorrateados.** → **Es el mismo ítem que SAB-01 del v6**, que trae además la fórmula propuesta (`PA >= 3.1 * team_games`).
  ~~ Mismo caso: ya identificado.
- [ ] **SEC-02 / SEC-03 — CDN sin SRI/CSP; Ofelia con socket.** **Parcial**: la imagen de Ofelia ya no es `latest`, queda pinneada por digest (2026-07-26). **El CDN dejó de existir (2026-07-27)**: Bootstrap y las fuentes se sirven desde `static/vendor/`, así que ya no hay nada que firmar con SRI ni ningún tercero al que pedirle recursos. Siguen pendientes el socket de Docker de Ofelia y la CSP.
  ~~ original: Ya en backlog para
  Fase 8 (endurecimiento). El review no agrega información nueva pero confirma la prioridad.

### Sin acción

- **SEC-04** — revisión OWASP sin hallazgos. Nada que hacer.

## Umbral de coeficientes DE POR VIDA (BIP)

- [x] **El qualifier de carrera de los coeficientes usaba `BALLS_IN_PLAY>=400` — arbitrario (era el de
  temporada).** **Resuelto** con estudio estadístico (`docs/UMBRALES_COEFICIENTES.md`): el umbral de
  carrera se ancló al estándar del sitio (bateo PA≥3000, pitcheo IP≥1000). Nuevos umbrales de **carrera**:
  bateo `BIP≥2000` / `swings≥5000`, pitcheo `BIP≥3000` / `swings≥8000` (el pitcheo enfrenta muchas más
  BIP). Temporada intacta (400/1000). BD actualizada y `dgl_leader` reconstruido (GB% carrera bateo pasó
  de 203 a 85 calificados).

## Mejorar la cobertura de ciertos tests (2026-07-27)

Pedido del dueño mirando el reporte de `pytest --cov`. El total es 96% (5.734 sentencias, 246 sin
cubrir) y **el número global no es la meta**: subirlo a 98% persiguiendo migraciones no protege nada.
Lo que sigue está ordenado por lo que duele si se rompe, no por porcentaje.

**Lo que NO hay que perseguir**, para que nadie gaste el día ahí:
* Las migraciones al 89–92% (`0016`, `0017`, `0018`, `0023`). Lo que falta es la función de reversa,
  que solo corre si alguien deshace la migración a mano.
* `download_team_logos.py` al **0%**. Es un script de una sola vez: los treinta SVG ya están bajados
  y commiteados. Escribirle tests es cubrir código que no va a volver a correr.
* `models.py`, 24 líneas de 1.081. Son `__str__` y ramas de propiedades sueltas.

**Hecho el 2026-07-27 (puntos 1, 2 y 3).** Los cuatro módulos quedaron al 100%: `refresh_daily`
71→100, `pipeline` 90→100, `rebuilds` 83→100, `telegram_check` 68→100. 21 tests nuevos.

Y no fue solo tapar líneas: escribir el del paso que revienta **destapó un bug**. Cuando un comando
explotaba ANTES de registrarse, `_correr` descartaba el mensaje de la excepción porque `_estado_de`
ya había puesto «no dejó fila en el log» —que es truthy— y ese texto ganaba. O sea que el caso más
común de fallo reportaba un problema de registro en vez del error real. Es el mismo mensaje que
confundió una mañana entera (ver el incidente de Telegram). Arreglado: `SIN_FILA` es ahora una
constante y `_correr` la trata como «no sabemos nada», no como una explicación del comando.

### 1. `refresh_daily` y `pipeline` — el trabajo de las 4:30 AM

Lo más caro de la lista. `refresh_daily.py` está al **71%** y lo que falta (líneas 42–43 y 50–53) es
justo **la salida con fallos**: el `stderr` ruidoso, el listado de los pasos que fallaron y el corte
por ventana de temporada. O sea, el camino que solo se recorre la mañana que algo se rompe — el único
que nadie va a ver hasta que pase de verdad.

En `pipeline.py` (90%) faltan las 108–115: el `except` que convierte el fallo de un paso en dato en
vez de dejarlo reventar, incluido el caso de que el paso no haya dejado fila en el log. Ese camino ya
nos confundió una vez (ver el incidente de Telegram más abajo, «no dejó fila en el log»).

- [x] Cubrir la salida con fallos de `refresh_daily` y el `except` de `_correr` en `pipeline`.

### 2. `rebuilds.py` (83%) — el hilo del Backoffice

Faltan la 50 y las 67–68: el `close_all()` de las conexiones cuando corre en su propio hilo, y el
lanzamiento del hilo. Es el código que ya tiene un finding abierto (QA-02 / ARCH-02: «el rebuild
puede no dejar rastro»), y una conexión de Postgres que se queda colgada por carga no se nota hasta
que se acaban.

- [x] Un test que compruebe que el hilo cierra sus conexiones y que el hilo principal NO cierra las
      que no abrió.

### 3. `telegram_check` (68%) — el canal de avisos

Es el más bajo de todo el código real. Lo que falta son los tres caminos de error que justifican que
el comando exista: token que no sirve, Telegram que no contesta, y `--buscar` sin ningún mensaje
recibido. Prioridad media: es una herramienta de mano, no algo que corra solo. Pero es el comando al
que uno acude **cuando los avisos ya fallaron**, y ahí no es momento de descubrir que tiene un bug.

- [x] Cubrir los tres caminos de error con `httpx` simulado (nunca red real — ver el marcador
      `telegram` en `pyproject.toml`).

### 4. Los motores de datos, si sobra tiempo

`leaders.py` (94%, 14 líneas), `leaderboards.py` (92%, 15), `tabs.py` (95%, 17) y `qualifier.py`
(91%, 4). Son ramas de borde de mucho código que ya tiene paridad comprobada contra la base real, así
que el riesgo está más cubierto de lo que dice el porcentaje. Último de la lista a propósito.

- [ ] Revisar caso por caso si cada línea suelta es una rama real o código muerto que conviene borrar.

## Incidente — el CI llevaba doce pushes en rojo y nadie lo vio (2026-07-27)

**Qué pasó.** Desde `508635e` (run #141, 26 de julio) hasta `24e359b` (#152) TODAS las corridas de
GitHub Actions fallaron. 558 errores por corrida, siempre el mismo: `failed to resolve host 'db'`.
Los 269 tests que no tocan la base pasaban; el resto ni arrancaba.

**Por qué.** Ese commit clavó `HOST: "db"` en `config/settings/test.py`. El arreglo era correcto en
su intención —evitar que la suite heredara `DATABASE_URL` y se pusiera a crear bases contra la real
en 10.0.0.39— pero `db` es el nombre del servicio de compose y solo existe dentro de la red de
Docker. En un runner de GitHub el Postgres es un `service` con el puerto publicado: `localhost`.

**Cómo se arregló.** El host y el puerto salen ahora de `DGLWEB_TEST_DB_HOST` / `..._PORT`, con el
del compose por defecto, y el workflow pone `localhost`. Es una variable SOLO de la suite: no la
hereda el contenedor y no puede apuntar sin querer a la base real, que era el riesgo original.

**Sin aviso automático, por decisión del dueño (2026-07-27).** El gate local siguió en verde los doce
pushes, así que nada avisó del rojo. Se planteó mandar los fallos del CI al grupo de Telegram que ya
recibe los del refresco diario y el dueño lo descartó: se sigue adelante mirando Actions a mano.
Queda escrito para que nadie lo vuelva a proponer como si fuera un olvido.

**Confirmado**: el run #153 cerró en verde, el primero desde el #140.

## Incidente — la suite mandaba alertas de Telegram de verdad (2026-07-27)

**Qué pasó.** El dueño recibió en el grupo de avisos mensajes como «Refresco diario con fallos —
update_fielding: failed (10 filas)» y «Debut dominicano — Jugador 2», minutos después de una corrida
de tests. No había ningún fallo: `IngestRun` tenía cero corridas no exitosas en 36 horas y el
refresco de las 6:00 salió limpio, 8/8 pasos y 417.575 filas.

**Por qué.** `config/settings/test.py` no tocaba las credenciales de Telegram, así que heredaba las
reales del `.env`. Y `tests/test_pipeline.py` hace fallar pasos **a propósito** —es lo que prueba—
sin silenciar el aviso. Cada corrida de la suite disparaba mensajes auténticos.

Se reconocían por el detalle: «no dejó fila en el log» en los nueve pasos a la vez, y «10 filas»,
que es exactamente lo que escribe el doble de `call_command`. Ningún fallo real se ve así.

**Lo que se rompía de verdad** no era el ruido: un canal de alertas donde la mitad son falsas deja de
leerse, y entonces la alerta real llega igual y nadie la mira. Es el mismo daño que el incidente de
Ofelia, por el otro extremo — allá no avisaba nada, acá avisaba de más.

**Arreglado**: `settings.test` vacía `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. `notify` ya tenía
previsto ese caso —sin token no manda y no protesta— así que no hizo falta código nuevo.

**No se hizo con un prefijo «TEST»**, que fue la primera idea: seguiría mandando mensajes reales y
seguiría metiendo la red en la suite. Para probar el canal a mano está `manage.py telegram_check
--probar`.

Con guardián: `tests/test_no_avisar_en_tests.py` comprueba que la suite no tiene credenciales, que
`enviar()` es un no-op, y que ni siquiera intenta llamar a `httpx.post`.

## Pendiente de operación — el scheduler no recarga el calendario

- [x] **Reiniciar `scheduler` después de tocar `ofelia/config.ini`.** **REGLA PERMANENTE, no una
  tarea**: hay que hacerlo CADA vez que se toque el archivo. Se cumplió el 2026-07-27 al agregar
  `roster-moves-hourly` — el log dijo «Starting scheduler with 5 jobs», que es la comprobación.
  Descubierto el 2026-07-27: el
  job `mlb-leaders-hourly` se agregó al archivo a las 18:58 del 26, y el scheduler llevaba corriendo
  desde las 15:39. Ofelia lee el calendario **solo al arrancar**, así que el proceso tenía cargados 2
  jobs —`Starting scheduler with 2 jobs` en su log— y el horario nunca se registró: `build_mlb_leaders`
  no corrió sola ni una vez.
  El archivo montado sí tenía el job; el proceso no. Es la misma familia de fallo que el incidente de
  Ofelia y vuelve por una puerta nueva: no por etiquetas robadas, sino por cambiar el calendario sin
  reiniciar. **Se arregla con `docker compose restart scheduler`**, y conviene dejarlo escrito en el
  propio `config.ini` para el próximo cambio.

## Comprobar el canal de avisos a mano

- [x] **`pytest -m telegram` manda un mensaje real y verifica que la llave funciona.** Existe porque
  los demás tests de `notify` parchean `httpx.post`: comprueban que el mensaje se arma bien y que un
  401 no tumba el job, pero **ninguno se enteraría de que el token está vencido, revocado o mal
  copiado en el `.env`** — y un aviso que no llega no avisa de que no llegó.
  Está excluido de la suite por defecto (`addopts = -m 'not telegram'`), que es la contrapartida de
  vaciar las credenciales en `settings.test`: aquello garantiza que los tests normales no manden
  nada, esto deja una forma de comprobar que el canal sí funciona.
  El mensaje empieza por «TEST» y dice de dónde salió — es la única vez que el sitio manda algo a
  propósito desde los tests y tiene que ser imposible confundirlo con una alerta.
  **Correrlo después de rotar el token**, que es el pendiente de arriba.

## Self-healing de `dgl_master.pos` (2026-07-27)

`pos` es la única columna del maestro que **envejece sola**. La fecha de nacimiento no cambia; la
posición sí, y varias veces: un campocorto se muda a segunda a los treinta, un jardinero central pasa
a la esquina, un abridor termina de cerrador. Se llenó una vez y nadie la volvió a mirar.

Medido: **96 de 981 ya no correspondían** — Tatis en el jardín derecho y no en el campocorto, Soto en
el derecho y no en el izquierdo, Polanco en segunda.

- [x] **`manage.py check_positions`, semanal (domingos 8:30).** Compara y **solo informa**. Con
  `--aplicar` escribe, a mano y a sabiendas: `dgl_master` es la tabla del dueño y un proceso que
  sobrescriba por su cuenta puede pisar una corrección hecha a mano sin que nadie se entere.

  El criterio, con el porqué en `players/positions.py`:
  * **Entradas y no juegos.** Un cambio defensivo de un inning cuenta un juego igual que una novena
    completa.
  * **Últimas 3 temporadas**, no la carrera. La pregunta es qué juega HOY. Con el total de carrera,
    Polanco seguiría diciendo SS durante años. Para quien ya no juega se mira la carrera, que además
    ya no va a cambiar.
  * **Si es `P`, decide `GS/G`**: más de la mitad de sus juegos abiertos es `SP`, si no `RP`.
  * **Sin mínimo de entradas para lanzadores.** Un relevista novato con cinco entradas ES un
    relevista y su `GS/G` ya lo dice; el umbral lo dejaría en «P» para siempre, que es justo lo que
    hay que curar — 30 casos.
  * **Mínimo 20 IP para los de posición.** Elegido midiendo: descarta cuatro casos de ocho y nueve
    entradas y no toca ninguno legítimo.
  * **`PH`, `PR`, `DH` y `OF` no se tocan nunca.** Son roles, no posiciones, y alguien los puso a
    propósito — 71 jugadores. Decisión del dueño.

- [ ] **Aplicar las 96 correcciones en el DGL de SQL Server.** El comando escribe en Postgres, pero
  la fuente de verdad es `dbo.dglMaster`: si solo se corrige acá, la próxima carga lo revierte.
  Generado `static_data/csv/posiciones_update.sql` con las 96 sentencias, cada una comentada con el
  nombre, el cambio, las entradas y —en los lanzadores— las aperturas sobre juegos.

## La ficha del jugador debe llevar su foto

- [x] **Poner el retrato en el biobox del perfil**, a la izquierda del nombre. **Hecho el
  2026-07-27.** La ruta la arma ahora `players/mugshots.py` para los tres sitios (ficha, líderes,
  destacados) en vez de tres f-strings sueltas.

  **Se resolvió distinto en un punto**: acá abajo pedía *reservar el espacio aunque falte la foto*, y
  lo que se hizo es preguntarle al disco (`mugshots.existe`) y no dibujar nada cuando no está. El
  `onerror` que sugería el resto de la nota borra la foto DESPUÉS del viaje del navegador — el nombre
  nace corrido 120px y salta al volver el 404, en un tercio de las fichas — y reservar un disco vacío
  se lee como una foto que no cargó, 350 veces. Un `stat()` por visita en una página que ya hace
  varias consultas lo evita todo. Los widgets sí siguen con `onerror`: ahí son veinte por página y
  casi todos tienen foto.

  **De paso**: el hero pasó de `.flex-grow-1` a `.dgl-hero-quien` con `flex-basis: 0`. Con base
  automática la fila repartía por ancho natural, los 120px del retrato desbordaban y los statboxes
  caían a una segunda línea (hero de 135px a 217px).

  **Los activos ya están**: `static/img/mugshots/360/<player_id>.png`, 637 retratos con fondo
  transparente, bajados en su día justamente para esto (el tamaño 360 se eligió para mostrarse a
  ~180px en el perfil, el doble de lo que se ve, que es lo que evita que se vean borrosos en un
  monitor denso). Los de 120 son para los widgets.

  Lo que quedó, todo con patrón ya establecido en el sitio:
  * La ruta se arma en Python y **no con `{% static %}`**: los retratos no entran a la imagen de
    Docker ni los recoge `collectstatic`, así que nunca están en el manifiesto y esa etiqueta
    fallaría al buscarlos.
  * `alt` vacío: el nombre está al lado en un `<h1>` y repetirlo hace que un lector de pantalla lo
    diga dos veces.

## Servir los medios en producción (2026-07-27)

`MEDIA_ROOT` y `MEDIA_URL` quedaron configurados con la Fase 5: sin ellos Wagtail no podía aceptar
una imagen, porque los archivos caían en la raíz del proyecto y ninguna URL los alcanzaba. En
desarrollo las sirve Django (`static()` en `config/urls.py`, que se anula solo cuando `DEBUG` es
falso). Los archivos viven en el volumen `dglweb_media`.

- [ ] **En producción los tiene que servir el proxy** desde `MEDIA_ROOT`. WhiteNoise NO sirve medios:
      está para los estáticos, que son los que entran a la imagen. Sin esta regla, en el VPS el CMS
      acepta la imagen y después la muestra rota.
- [ ] **Respaldar `dglweb_media`.** Es contenido del sitio escrito por una persona, igual que la base:
      si se pierde el volumen, las fotos de todos los artículos se van con él y no hay de dónde
      recuperarlas.

## El cintillo de movimientos de roster — ✅ CONSTRUIDO (2026-07-27)

Se aparcó por la mañana con prioridad muy baja y se construyó por la tarde, cuando el dueño decidió
qué mostraba. Lo que sigue es el registro de las decisiones, que siguen valiendo para mantenerlo.

- [x] **El ticker de movimientos de roster.** **Hecho**: `stats/roster_moves.py`, el comando
  `update_roster_moves`, el job horario y el widget `_cintillo.html`. 30 plantillas traducen el 100%
  de las transacciones de un mes; una llamada al API por corrida. Qué muestra ya está decidido (dueño, 2026-07-27):
  **los movimientos de roster de nuestros peloteros** — firmados, subidos, bajados, cambiados,
  liberados. No marcadores en vivo ni jugadas del día.

  El hueco está reservado desde la Fase 1: `base.html` tiene un `{% block ticker %}` vacío con un
  comentario que dice que espera «a data-driven, season-aware component». Esa es la regla que hay que
  respetar al retomarlo — **no se publica una cintilla con datos falsos** para que el sitio parezca
  vivo.

  **La preocupación del dueño es el costo en llamadas al API, y con razón: hay que pensarlo mil veces
  antes de hacerlo.** Su idea era leer el endpoint de rosters y sacar los movimientos por diferencia
  entre la foto de ayer y la de hoy. Antes de tomar ese camino, un dato medido el 2026-07-27:

  **El proxy ya expone `/api/v1/transactions`**, y una sola llamada con `startDate`/`endDate` del
  mismo día devolvió **142 transacciones de toda la MLB**. O sea **1 llamada por día**, contra **30**
  —una por equipo— del camino de las diferencias de roster.

  Y no es solo más barato, es mejor dato. Cada fila trae `typeDesc` (*Signed*, *Optioned*,
  *Recalled*, *Released*, *Trade*…), la persona, los dos equipos y una descripción ya redactada. La
  diferencia entre dos rosters solo dice que alguien dejó de estar: **no distingue** una bajada a
  ligas menores de una cesión, de un cambio o de una liberación, que es justamente lo que hace
  noticiable el movimiento. Sacar eso del diff pediría más llamadas, no menos.

  Filtrar a los nuestros no cuesta llamadas: es un cruce contra `dgl_master` ∪ `dom_players`, que es
  la única autoridad de quién es dominicano — **el `birthCountry` del API no vale**.

  Lo que NO hay que decidir: la técnica de refresco. El plan de la fase decía «vistas HTMX» y **HTMX
  nunca se instaló**. La pizarra se refresca con `static/js/pizarra.js`, cuarenta líneas de `fetch`
  contra un fragmento, con respaldo en caché cuando el proxy falla. Funciona, está probado y no
  arrastra una dependencia por CDN — que es justo la deuda que la Fase 8 viene a pagar. El ticker
  debería seguir ese mismo patrón, y además leer de nuestra tabla y no del proxy en cada visita: los
  movimientos los trae un job diario, como todo lo demás.

  ### El español, sin LLM — medido el 2026-07-27

  **Sí se puede con reglas.** MLB no escribe prosa: rellena plantillas. Sobre un mes real (2.139
  transacciones de toda la MLB, traídas en 5 llamadas), sustituyendo nombres, equipos, posiciones y
  números por marcadores:

  | | |
  |---|---|
  | Frases totales | 2.139 |
  | Esqueletos distintos | 226 |
  | **Esqueletos que cubren el 90%** | **29** |
  | De los nuestros, en el mes | 165 filas · **36 esqueletos** |

  Las más frecuentes son de este tenor — `{EQUIPO} optioned {POS} {JUGADOR} to {EQUIPO}.`,
  `{EQUIPO} activated {POS} {JUGADOR} from the {N}-day injured list.` — o sea una tabla de unas
  treinta entradas, no un modelo de lenguaje.

  **El atajo que NO funciona**, para que nadie lo intente de nuevo: componer la frase solo desde los
  campos estructurados, ignorando el inglés. `typeDesc` es demasiado grueso. «Status Change» —el
  segundo tipo más frecuente— mete en la misma bolsa *activado*, *lista de lesionados*, *paternidad*,
  *duelo*, *restringido* y *suspendido*. Saldría «cambio de estatus» donde la noticia era la lesión.

  **Lo correcto es híbrido:** reconocer la frase inglesa contra la tabla de patrones, y rellenar la
  plantilla española con los CAMPOS DEL JSON —`person`, `toTeam`, `fromTeam`—, no con lo que se
  extraiga del texto. Dos residuos: el detalle de la lesión («Left hamstring strain»), texto libre
  pero de vocabulario acotado que cubre un glosario chico; y lo que no encaje en ningún patrón, donde
  **la regla es no mostrar nunca el inglés** — se omite del ticker o se cae a una frase genérica. Una
  línea en inglés dentro de una cintilla en español se lee como un error, no como un dato.

  ### El costo en llamadas, medido

  El endpoint acepta rangos de fechas: **una sola llamada trajo dos semanas enteras**. Contra las 30
  diarias (una por equipo) del camino de diferencias de roster que se barajó primero, no hay color. Y
  de esas 2.139 filas del mes, **165 eran nuestras** (unas 5 por día), así que el ticker tiene
  material sin quedarse vacío ni desbordarse.

  ### Cada cuánto correrlo

  Un job DIARIO no sirve —lo señaló el dueño— porque un movimiento de las 3pm saldría al día
  siguiente. **Cada hora, todo el día.** Son 24 llamadas diarias, y el yardstick es que el job de
  líderes ya corre cada hora haciendo **2 llamadas** (mete las 23 categorías en una sola petición por
  grupo): 48 al día. Sumar una por hora es ruido.

  Se descartó acotarlo a 8am–6pm, que fue la primera idea: los juegos nocturnos terminan entre las 10
  y las 11, y ahí caen lesiones y movimientos posteriores. Con corte a las 6pm, una lista de
  lesionados de las 9pm aparece a las 8 de la mañana siguiente y sale en la cintilla como noticia
  fresca cuando ya tiene once horas. Como cuesta lo mismo, no hay razón para recortar la ventana.

  **El horario es solo una perilla de latencia, no de correctitud**, y eso es a propósito: cada
  transacción trae un `id` propio, así que la corrida pide los ÚLTIMOS DOS DÍAS y guarda con upsert
  por ese id. Una corrida que falle no pierde nada; la siguiente la recupera. Mismo patrón
  idempotente que el resto del pipeline.

  **Salvedad:** el payload NO trae hora, solo `date`. Así que a qué hora del día caen los movimientos
  no está medido — lo de los juegos nocturnos es razonamiento sobre el calendario de MLB. Si alguna
  vez importa afinar la ventana, hay que observarlo unos días primero.

**La página aparte de la pizarra NO se va a hacer** — decisión del dueño (2026-07-27). La Fase 0 la
mencionaba («pizarra completa → página aparte») y queda descartada: la pizarra vive en la portada y
ya está. Se escribe acá para que nadie la vuelva a proponer leyendo aquel plan viejo.

## El ruido de `treebeard.E001` en los logs (2026-07-27)

Cada corrida de CADA job del scheduler escribe cuatro líneas de aviso por `stderr`:

```
(treebeard.E001) django.db.models.manager.BasePageManagerFromPageQuerySet does not subclass
treebeard.mp_tree.MP_NodeManager. This will cause an error in Treebeard 6.
```

**No es nuestro código.** Es Wagtail 7.4.2 contra django-treebeard 5.3.0: los managers de `Page` y
`Collection` los define Wagtail y no heredan de `MP_NodeManager`, que es lo que treebeard 6 va a
exigir. Hoy es solo un aviso y nada se rompe.

**Por qué molesta igual.** Sale en el `stderr` de las cinco corridas, o sea decenas de veces al día,
y **entierra el `stderr` de verdad**. El día que `refresh_daily` escriba un error real —que es
justamente el canal por el que avisa— va a estar mezclado con ese ruido en el mismo bloque del log. Un
canal de errores donde casi todo es ruido deja de leerse, que es el mismo problema que tuvimos con
las alertas de Telegram.

- [ ] **Silenciarlo con `SILENCED_SYSTEM_CHECKS = ["treebeard.E001"]`** en `config/settings/base.py`.
      Es una línea, y hay que escribir al lado POR QUÉ se silencia y qué se está aplazando — un
      `SILENCED_SYSTEM_CHECKS` sin explicación es una trampa para el que venga.
- [ ] **Antes de subir a treebeard 6, quitar ese silencio y ver qué queda.** El aviso dice que
      entonces será un error, y ahí ya no es cosmético: no arranca. Como la política del proyecto es
      quedarse en versiones LTS, esto no urge — pero cuando toque el salto, es lo primero que hay que
      mirar. La decisión no es nuestra: la tiene que resolver Wagtail en su código.

## Code review v8 — findings (2026-07-27)

Quince findings, **verificados uno por uno contra el código** antes de decidir. Lo que sigue dice qué
se acepta, qué no, y por qué. Los duplicados van fusionados: QA-01 y ARCH-01 son el mismo problema
visto por dos personas, igual que DEV-02/QA-02 y QA-03/FE-03.

### Aceptados — prioridad alta

- [x] **SAB-01 — el gráfico de barras se rompe con valores negativos.** **Corregido el 2026-07-27.** Aceptado, y **es peor de lo
      que dice el review**. Comprobado ejecutando `_escala()`: con `[-8, -2]` la escala sale
      `(0, -2)`, o sea rango NEGATIVO, y la proporción da 4 — la barra se dibujaría cuatro veces más
      alta que el lienzo. Con `[5, -3]` el alto sale negativo y el `<rect>` no se dibuja: la barra
      desaparece sin avisar.

      Importa mucho acá: OAA, DRS, run value, WPA, RE24 y el WAR en muestras cortas son
      rutinariamente negativos, y este es un sitio de sabermetría. Un artículo publicaría un gráfico
      que miente aunque las cifras escritas estén bien. Arreglo: dominio de `min(0, mínimo)` a
      `max(0, máximo)`, la línea de cero dibujada dentro del SVG, y las barras hacia arriba o hacia
      abajo según el signo. Con tests para `[5, -3]` y `[-8, -2]`.

- [x] **FE-01 — el cintillo deja enlaces enfocables dentro de `aria-hidden`.** **Corregido el 2026-07-27**: de 18 enlaces, ahora solo 9 alcanzables con Tab. Aceptado. La lista va
      duplicada para que el ciclo empalme, y la copia lleva `aria-hidden="true"` — pero eso **no la
      saca del orden de tabulación**. Quien navega con teclado cae en enlaces que el lector de
      pantalla ignora, dentro de una tira en movimiento, y la animación no se detiene porque solo
      existe `:hover`. Arreglo: `inert` en la copia y `:focus-within` para pausar. Es barato, y lo
      escribí yo hoy.

### Aceptados — prioridad media

- [x] **DEV-01 — `update_roster_moves` no usa `build_client()`.** **Corregido el 2026-07-27.** Aceptado, y es culpa mía de hoy.
      Comprobado: `build_client()` existe, aplica `MLB_PROXY_TIMEOUT`, y lo usan otros diez comandos;
      el mío instancia el cliente a mano y **se salta el timeout configurado**. Son tres líneas.

- [x] **DEV-02 + QA-02 — una fila malformada tumba la corrida entera.** **Corregido el 2026-07-27**, con seis casos parametrizados de fila podrida. Aceptados como uno solo: es
      el mismo problema, visto en el código por una persona y en los tests por otra. `_movimiento()`
      maneja los campos que faltan pero no captura `ValueError`/`TypeError`, así que un `id` no
      numérico o una fecha con formato raro aborta las 130 filas buenas. Arreglo: aislar la
      conversión de cada fila, saltar la mala y dejar nota en `IngestRun`. Con tests de
      `date="2026-07-20T00:00:00Z"`, `id="abc"` y un `transactions` que no sea lista.

- [x] **QA-01 + ARCH-01 — los jobs horarios no los vigila el semáforo.** **Corregido el 2026-07-27**: umbral propio de 3h en `PIPELINE_HOURLY_STALE_HOURS`. Aceptados como uno.
      Comprobado: `/health/pipeline` solo mira la última fila de `refresh_daily`. Si
      `build_mlb_leaders` o `update_roster_moves` fallan seis horas seguidas, el monitor sigue verde
      mientras la portada enseña líderes viejos y un cintillo congelado. Arreglo: frescura por
      comando con umbrales distintos — un día para el refresco diario, dos o tres horas para los
      horarios.

- [x] **SEC-01 (parcial) — cachear el semáforo anónimo.** **Corregido el 2026-07-27**: 30s, y comprobado que la segunda petición no toca la base. Aceptada la mitad barata: cachear la
      respuesta pública 30–60s, que quita la consulta a `IngestRun` en cada petición. El *rate limit*
      NO se acepta acá — ver el rechazo razonado más abajo.

- [x] **SEC-03 — falta prueba de regresión para el texto enriquecido.** **Corregido el 2026-07-27, y el test encontró un fallo REAL**: Wagtail no filtra el esquema de los enlaces, así que un `javascript:` en el cuerpo llegaba tal cual a la página. Ahora hay un filtro de lista blanca (`enlaces_seguros`) que parsea con bs4 en vez de usar regex sobre HTML. Aceptado. Hoy el
      comportamiento es seguro —`RichTextBlock` limita a `bold/italic/link/ol/ul` y las plantillas
      escapan— pero nada lo congela. Tests con `javascript:` en un enlace y con HTML en celdas de
      tabla y en la entradilla, para que ampliar `features` mañana falle ruidosamente y no en
      silencio.

### Aceptados — prioridad baja

- [x] **ARCH-02 — la URL del índice cacheada puede quedar vieja, y el comentario MIENTE.** **Corregido el 2026-07-27**: invalidación por señales de Wagtail y comentario reescrito. Aceptado,
      y lo segundo molesta más que lo primero: el comentario dice literalmente «se guarda en caché
      por su ID, no por su URL» y el código guarda la URL. Lo escribí yo. Si el editor mueve o
      despublica el índice, el menú y el pie apuntan a una ruta muerta hasta 24 horas. Arreglo:
      limpiar la caché con las señales de Wagtail al publicar, mover y despublicar, y corregir el
      comentario. Con un test que mueva la página y compruebe que el menú cambia sin esperar el TTL.

- [x] **SAB-03 — se puede enlazar a un jugador oculto.** **Corregido el 2026-07-27**: sin enlace si no es visible, pero el nombre se queda. Aceptado. Comprobado: el modelo declara
      `default_manager_name = "todos"`, que es el manager que SÍ incluye a los deshabilitados, así
      que el selector del CMS los ofrece. Y el perfil público usa `Player.objects`, que los excluye —
      o sea 404. Un artículo publicado hoy queda con un enlace roto el día que el dueño deshabilite a
      ese jugador. Hoy no hay ninguno deshabilitado (984 = 984), así que no urge. Arreglo: comprobar
      la visibilidad al renderizar y mostrar solo el nombre si está oculto.

- [x] **SEC-02 — política de documentos del CMS.** **Decidido el 2026-07-27: son PÚBLICOS**, con un test que congela la decisión. Aceptado como decisión, no como código. Los
      documentos de Wagtail se sirven públicos bajo `/documents/`, y hoy no usamos ninguno. Hay que
      elegir: o se quita `wagtail.documents` con su ruta, o se escribe que **son públicos** para que
      ningún editor suba ahí algo creyendo que es privado. Con un test que congele la elección.

- [x] **QA-03 + FE-03 (parcial) — el botón «Ver más artículos» queda muerto sin JavaScript.** **Corregido el 2026-07-27** con `<noscript>`.
      Aceptada solo la mitigación barata: esconderlo con `<noscript>`. Un control visible que no hace
      nada es peor que no tenerlo. El resto se rechaza — ver abajo.

### Rechazados, con su razón

- **DEV-03 — hacer obligatoria la categoría del artículo.** No se acepta *como está planteado*, pero
  el reviewer tiene razón a medias y la parte cierta no es la que propone.

  El docstring dice «una y solo una» en contraste con los hashtags, que son varios: significa **como
  máximo una**, no «obligatoria». Y que la tarjeta funcione sin categoría es deliberado y está
  probado. Así que no hay drift entre documentación y código.

  Lo que sí es cierto, y el review roza sin nombrarlo: **un artículo sin categoría no aparece bajo
  ningún filtro del índice**. Solo se llega a él desde la lista general. Eso no es un defecto del
  modelo, es una decisión editorial — y es del dueño. Queda como pregunta abierta, no como tarea.

- **ARCH-03 — índice parcial para la consulta del cintillo.** Rechazado por ahora, y el propio review
  lo concede: «para el volumen actual no duele». Son 128 filas, la consulta está cacheada 15 minutos
  y corre una vez por cuarto de hora, no por visita. Un índice parcial hoy es optimizar sin medir. Se
  revisa cuando la tabla pase de unas decenas de miles de filas — a cuatro movimientos nuestros por
  día, eso es dentro de varios años.

- **SEC-01 (la otra mitad) — rate limit dentro de la aplicación.** Rechazado en este sitio. Un
  limitador dentro de Django gasta el proceso que quiere proteger: para cuando cuenta la petición, ya
  la aceptó. Donde corresponde es en el proxy inverso, y eso es Fase 8 y ya está en el plan. Se
  acepta solo la caché, que sí quita trabajo de verdad.

- **QA-03 + FE-03 (el resto) — dibujar los 24 artículos visibles y esconderlos con JS.** Rechazado.
  Cambia un control muerto por un defecto peor y visible para TODOS: la página cargaría con
  veinticuatro tarjetas y se encogería a seis en cuanto arrancara el script. Y el arreglo de verdad
  ya está en el TODO — la paginación del servidor, que resuelve esto y el peso de la página a la vez.

- **SAB-02 — hacer obligatoria la fuente del gráfico.** No lo decido yo: es una regla editorial y la
  pone el dueño. El argumento del review es bueno —un gráfico sin fuente no se puede comprobar, y el
  propio texto de ayuda ya lo dice— y **lo recomiendo**. La contrapartida es que obliga a escribir
  algo aunque el dato salga de nuestras tablas, y se resuelve con un valor por defecto tipo «Cálculo
  propio sobre dgl_batting». Pregunta abierta al dueño.

### Preguntas abiertas del dueño (salidas de este review)

- [x] **¿La categoría del artículo es obligatoria?** **Sí, e IMPLEMENTADO el 2026-07-27.** Obligatoria
      en el modelo, con `PROTECT` para que borrar una categoría con artículos dentro falle en vez de
      dejarlos huérfanos. La migración va en dos pasos —primero rellena, después prohíbe el nulo— y
      ASIGNA en vez de borrar: una migración que borra filas se lleva trabajo de verdad el día que
      alguien la corra sobre otra base. Eran cuatro artículos de 31.
- [x] **¿La fuente del gráfico es obligatoria?** **Sí, e IMPLEMENTADO el 2026-07-27**, con el valor
      «Cálculo propio sobre datos de dglweb» llegando escrito en el formulario.
- [x] **¿Los documentos del CMS se quitan o se declaran públicos?** **Públicos** — decisión del dueño
      (2026-07-27). Se quedan, y queda escrito que **todo lo que entre ahí es público**: se sirve en
      `/documents/<id>/<archivo>` sin pedir permisos. El riesgo no era técnico sino de expectativa —
      un editor subiendo algo interno creyendo que es privado— así que se resuelve diciéndolo, no
      borrando una función que probablemente haga falta («descarga los datos de este gráfico»).
      Falta: escribirlo donde lo lea quien escribe, y un test que congele la decisión.

## Lo hecho el 2026-07-27 — resumen de la jornada

Un día largo, y esto es el índice para no tener que reconstruirlo del historial de git.

**Fase 5 cerrada.** `ArticlePage` bajo `ArticleIndexPage`, siete bloques de cuerpo, categoría única +
hashtags, medios en un volumen, y el flujo editorial con tres roles montados por migración
(Redactores / Editores / Administradores). El «Done when» de la fase —borrador → revisión →
publicado— está cubierto por 9 tests.

**Fase 6 cerrada**, con su «Done when» enmendado y escrito como enmienda: la pizarra y los destacados
ya cumplían los tres requisitos, y el ticker salió del camino crítico… hasta que el mismo día se
construyó, cuando el dueño decidió que mostraba movimientos de roster.

**El cintillo**, entero: fuente decidida contra alternativas medidas, 1 llamada al API por corrida,
30 plantillas que traducen el 100% de un mes sin LLM, y un job horario idempotente.

**Review v8 completo**: 15 findings verificados uno por uno contra el código, 11 aceptados y
corregidos, 4 rechazados con su razón escrita.

**Dos hallazgos que valen más que los findings que los provocaron**, los dos encontrados por tests
que se escribieron para confirmar que todo estaba bien:

* El gráfico de barras **se rompía con valores negativos** —barra cuatro veces más alta que el lienzo,
  o barra invisible— y en un sitio de sabermetría eso no es hipotético.
* El texto enriquecido **no filtraba el esquema de los enlaces**: un `javascript:` en el cuerpo
  llegaba intacto a la página.

**Y uno que encontró el CI**: la suite llevaba doce pushes en rojo porque `settings.test` clavaba el
host `db`, que solo existe dentro de Docker.

**Cobertura**: `refresh_daily`, `pipeline`, `rebuilds` y `telegram_check` al 100%, y de paso apareció
un bug — cuando un paso reventaba antes de registrarse, el mensaje de la excepción se perdía y salía
«no dejó fila en el log», que es justo el mensaje que ya había confundido una mañana entera.

La suite pasó de 825 a 946 tests.
