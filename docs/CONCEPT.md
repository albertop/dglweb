# Concepto — Dominicanos en Grandes Ligas

> Notas de la conversación con el dueño del proyecto. Documento vivo (borrador).
> Fecha de inicio: 2026-07-16

## Qué es

Relanzamiento de un sitio que **ya existió hace muchos años**. Website que **combina un blog
con estadísticas de béisbol**, con un diferenciador central:

**El "catch":** las estadísticas se presentan **únicamente para el subconjunto de peloteros
dominicanos** en las Grandes Ligas (MLB). Es el recorte "dominicanos" como lente del sitio.

## El giro respecto al sitio original

- **Sitio original:** las **estadísticas eran la espina dorsal**; el blog era una parte
  secundaria y pequeña.
- **Ahora se invierte:** los **artículos (blog) pasan a ser lo central**, y las estadísticas
  quedan como **parte secundaria** (de apoyo).
- **Razón:** en estadísticas puras no se puede competir con Baseball Reference / Baseball Savant
  / FanGraphs, aun limitándose al nicho dominicano. El valor diferencial está en el **contenido
  editorial**, no en ser una base de datos de stats.

## Identidad

- **Nombre:** Dominicanos en Grandes Ligas
- **Dominio:** `dominicanosengrandesligas.com`
  - Registrado hace **20+ años** → activo histórico valioso para **SEO** (autoridad de dominio).
- **Idioma:** Español.

## Audiencia

- Mayormente **masculina**.
- Principalmente de **República Dominicana**.

## ⭐ Principio #0 (el más importante) — RESILIENCIA sobre features

> Para el dueño, **la resiliencia de lo que se construya vale más que los features en sí.**

- Es un **proyecto sideline / hobby**. En la fase inicial hay **poco tiempo** disponible, y sobre
  todo **poco/nada de tiempo para tareas de sysadmin**.
- **El sitio NO puede ser frágil — ni el frontend ni el backend.** Debe aguantar solo.
- Prioridad: **robustez, bajo mantenimiento, auto-recuperación** > cantidad de features.
- Implicaciones de diseño (a tener presente en todas las decisiones):
  - Tecnología **aburrida y probada**, no experimental.
  - Preferir **servicios gestionados / librerías maduras** donde reduzcan carga operativa.
  - **Auto-restart, healthchecks, degradación elegante** (que una pieza caída no tumbe todo).
  - Menos piezas móviles y menos "magia" = menos cosas que se rompen a las 2am.
- ⚠️ **Tensión a resolver:** "cada pieza dockerizada" (self-host) vs "mínimo sysadmin". Hay que
  elegir setups dockerizados que sean **de bajo mantenimiento** (como se hizo con el mlb-proxy:
  healthcheck, restart policy, Portainer) o apoyarse en gestionados donde convenga.

## Arquitectura — piezas (todas dockerizadas)

El website se divide en **al menos 3 piezas**, cada una corriendo **dockerizada** y pensada como
**semi-independiente** (que el fallo de una no arrastre a las otras):

1. **`mlb-proxy`** — *(ya existe)* extracción de datos **en tiempo real** desde mlb.com.
2. **Data pulling programado → PostgreSQL** — scripts que corren **en schedule** para poblar la
   base de datos. Se ve como **pieza semi-independiente** (su propio ciclo de vida).
3. **El website en sí** — **Django + Wagtail** (un solo proyecto Python; front y back en la misma
   pieza, server-rendered + HTMX). Ver *Stack tecnológico*.

> Nota de diseño: el desacople en piezas semi-independientes es coherente con el Principio #0
> (resiliencia): cada una falla y se recupera por separado.

## Pilar 1 (CENTRAL) — El blog / artículos

- **Modelo de contenido:** estilo **blog de FanGraphs**, NO noticioso.
- No se trata de dar noticias del día, sino contenido **novedoso y analítico**:
  - Sabermetría.
  - "Cosas raras" / curiosidades.
  - Ángulos originales sobre el béisbol (y los dominicanos en él).
- Es lo que hace volver a la gente; el corazón del sitio.
- **Formato:** arranca con **artículos largos (long-form)**, análisis a profundidad.
  - ⚠️ **Pero sin cerrar la puerta** a piezas más cortas/frecuentes si las cosas cambian. El
    diseño y la arquitectura NO deben asumir solo long-form. (Ver principio transversal abajo.)

## Pilar 2 (SECUNDARIO) — Las estadísticas

> Nota: hay dos tipos de stats según su origen (arquitectura). **Profundidad decidida:**
> **ambiciosa / sabermétrica**, no solo las básicas — porque los artículos hablan de sabermetría
> y necesitan **tablas más complejas** que las respalden. Cobertura: **batting, fielding,
> pitching**.

### Tipo A — Tiempo real / "on the fly" (vía el MLB proxy)

Se obtienen al vuelo desde el proxy `mlb-api` ya construido. Ejemplos:

- **Pizarra de juegos** — juegos en curso + los de ayer.
- **Movimiento de rosters** — actualizado casi al minuto.
- **Resumen de la jornada** — cómo les fue a los dominicanos ayer.
- **Cintillo / ticker** — lo último que han hecho los dominicanos (feed en vivo).

### Tipo B — Programadas / scraped (vía scripts + PostgreSQL)

- **Scripts scrapers** que corren **en schedule** y actualizan **tablas en una base de datos
  PostgreSQL**.
- Para stats que no salen directo del proxy o que conviene precalcular/almacenar.
- Categorías habituales: pitcheo, bateo, defensa, etc. (detalle pendiente).

## ⭐ Feature estrella — LÍDERES del subconjunto dominicano

> Esta es **la joya diferenciadora** del sitio (y fue un **gran éxito en la versión anterior**).

- **Qué es:** rankings de **líderes** calculados **solo sobre el subconjunto de jugadores
  dominicanos**, en dos dimensiones:
  - **Líderes de por vida / carrera (all-time):** "¿quién es el líder dominicano de todos los
    tiempos en X?"
  - **Líderes de temporada (single-season):** "¿quién tiene la mejor temporada dominicana en Y?"
- **Por qué es único (el "por qué nadie más lo tiene"):** en Baseball Reference es fácil saber el
  líder all-time o de temporada **de MLB en general**, pero **filtrar eso por un subconjunto**
  (los dominicanos) es **difícil o imposible** ahí. Aquí es el eje del sitio.
- **Cobertura:** batting, fielding, pitching (con métricas **sabermétricas**, no solo básicas).
- **Implicación de datos/arquitectura:** los líderes de **carrera** y **por temporada** requieren
  **datos históricos completos** (todas las temporadas de todos los dominicanos, siempre) →
  viven en la **pieza Postgres precalculada (scrapers en schedule)**, NO en el proxy en tiempo
  real. Encaja con que los datos son la **fortaleza del dueño**.

## Producto — Páginas de jugador e interconexión artículo ↔ stats

- **Página por jugador dominicano** — **~970 jugadores**, cada uno con su página de **información
  estadística tipo Baseball Reference**. Es una pieza central del producto (no solo el blog).
- **Datos = fortaleza del dueño.** Él **tiene los datos o sabe dónde conseguirlos** (~970
  dominicanos, definición de "dominicano", fuentes). Este punto —el más importante— es también
  el que **mejor domina**; no es un riesgo del proyecto.
- **Interconexión (la "magia" del sitio):**
  - El **writer debe poder insertar gráficos y tablas dentro del artículo** → por eso el **editor
    rich-text es mandatorio** (y debe soportar incrustar visualizaciones/tablas, no solo texto).
  - **Mencionar a un jugador** (ej. "Soto") debería **enlazar a su página** de stats.
  - Sistema de **hashtags estilo Twitter** en los artículos (para jugadores/temas) → navegación
    y descubrimiento por etiqueta.

## Datos — flujo, tabla maestra y bootstrap

> **El 99% de los datos viene de MLB** (vía scrapers + proxy). El sitio no inventa datos; los
> orquesta.

### Tabla maestra de jugadores dominicanos (la definición del subset)

- La lista de **quiénes son dominicanos** (~970) se mantiene en una **tabla maestra en Postgres**
  que el **administrador gestiona con una página CRUD** (en el ámbito del rol *administrator*).
- **⭐ La tabla maestra es la ÚNICA fuente de verdad / autoridad final** sobre quién es dominicano.
- El **`birthCountry` de MLB es solo un INPUT/semilla** (ayuda a poblar/sugerir la lista), **NO la
  regla**. La decisión final la tiene el admin en la tabla → control total sobre **casos borde**
  (nacidos en USA de ascendencia dominicana, mal etiquetados por MLB, altas/bajas, etc.).
- Esta tabla es el **filtro** que aplica el recorte "solo dominicanos" a todo lo demás.

### Bootstrap (una sola vez, ANTES de lanzar)

- **Backfill histórico de datos** — carga inicial de todas las temporadas/carreras de los
  dominicanos (necesario para los **Líderes** de carrera y temporada).
- Fuente del backfill: el **proxy mismo** o una **base de datos local** dedicada a ese fin.
- Es una operación **puntual**, distinta del flujo continuo.

### Operación continua (una vez el sitio "vuela solo")

- **Actualización en tiempo real:** **scrapers + proxy** desde MLB.
- **Scrapers en schedule** pueblan/actualizan las tablas de Postgres (stats, líderes, etc.).
- Regla: **una vez en producción, los datos vienen de los scrapers** (el backfill no se repite;
  los scrapers mantienen todo al día).

### Secuencia y prioridades (corrección del dueño)

- **El backfill histórico NO es el cuello de botella:** el dueño estima tenerlo listo en **una
  jornada de trabajo** (los datos son su fortaleza). ⬅️ *corrige mi supuesto anterior.*
- **Lo obligatorio antes del backfill:** tener **operativos los scrapers + la página CRUD**, para
  que **apenas se haga el backfill, la data siga actualizándose sola** (no un dato muerto).
  → El orden es: **pipeline vivo primero, backfill después.**
- **El verdadero cuello de botella son los 8–12 artículos semilla** (creación de contenido de
  calidad). Esa es la pieza a vigilar de cerca en el cronograma hacia el big-bang.

## Estacionalidad — modo temporada vs. temporada muerta

> Observación clave del dueño: **el sitio tiene "vida propia" mientras la temporada MLB está en
> curso**; en **temporada muerta** hay que evitar que se vea **abandonado**.

- **Módulos "vivos" dependientes de temporada:** pizarra de juegos, cintillo, resumen de la
  jornada, y en general los espacios de "día a día".
  - **En temporada:** activos, actualizándose.
  - **En temporada muerta:** **NO** deben quedarse mostrando la última pizarra (se vería
    abandonado). Tienen que **desaparecer con gracia** o **transformarse en otra cosa**.
- **Los artículos siguen vivos todo el año** (el blog no es estacional).
- **Implicación de diseño:** el sitio debe ser **season-aware** — los componentes en vivo son
  **condicionales al estado de la temporada** (degradación elegante, alineado con Principio #0).
  El layout no puede asumir que siempre hay juegos hoy.

### ✅ Calendario de "pizarras" — el sitio nunca duerme (DECIDIDO)

La pizarra/módulos vivos **cambian de fuente según la época del año**, dando cobertura los 12
meses:

| Época (aprox.) | Qué se muestra |
|---|---|
| **Temporada MLB** (abr–oct) | Pizarra **MLB** (dominicanos en MLB) |
| **Spring Training** (feb–mar) | Pizarra **Spring Training** ✅ |
| **Off-season / invierno** (nov–ene) | Pizarra **LIDOM** (liga invernal dominicana) ✅ |

- **LIDOM + Spring Training = comprometidos** (ya no son "semilla"). Con esto el sitio **sigue
  vivo en off-season** y es **súper on-brand** para la audiencia RD.
- **✅ Nota de datos (confirmada por el dueño): LIDOM es un `sportId` en el MLB statsapi.** Es
  decir, **LIDOM, Spring Training y (Fase 2) Minor Leagues salen TODOS del mismo statsapi** que ya
  fronteas con el proxy — solo cambian `sportId` / `gameType`. **Una sola fuente de datos, un solo
  proxy, cero integraciones nuevas.** Desaparece la única incógnita de fuente que teníamos.
- **✅ Fase decidida:** en el **launch** va **solo la pizarra MLB**. Luego:
  - **Fast-follow #1: LIDOM.**
  - **Fast-follow #2: Spring Training.**
  - Este orden calza con el calendario: se lanza en temporada MLB → termina (oct) → **LIDOM**
    (nov–ene) → **Spring Training** (feb–mar). Cada fast-follow llega justo cuando su temporada
    empieza. Implica **lanzar durante la temporada MLB**, con LIDOM listo antes del off-season.

## Landing page (home)

- **Referencia directa:** el landing de **Baseball Savant** → **artículos rodeados de
  estadísticas**. Es decir, el contenido editorial manda visualmente, pero envuelto/acompañado
  por módulos de stats vivas (pizarra, cintillo, líderes, etc.).
- Jerarquía: artículos destacados como protagonista + stats en vivo como marco.
- **Módulo principal del sidebar: "Destacados de la jornada"** — los dominicanos que más se
  destacaron **ayer**, separados en **bateadores** y **lanzadores** (con su línea del día). Es más
  on-brand que una pizarra genérica → al entrar ves cómo la rompieron los dominicanos. (La
  **pizarra completa de juegos** pasa a su **propia página**, enlazada, no al sidebar del home.)
- **🔎 Players search (en el landing):** buscador de jugadores (typeahead/autocomplete por nombre)
  que lleva a la **página del jugador**. Encaja con HTMX (búsqueda mientras se escribe). Solo busca
  dentro del **subset dominicano** (usa la tabla maestra). Es la vía rápida a las ~970 páginas.

## Propósito y monetización

- **Naturaleza:** primero es un **proyecto de pasión / hobby**.
- **Motivación de fondo:** el dueño tiene fuerte conocimiento de **sabermetría**, algo que en RD
  es poco conocido → hay un ángulo **educativo / divulgativo** (traer sabermetría al público
  dominicano).
- **Monetización desde el inicio:** aunque sea hobby, se quiere **contemplar monetización desde
  el día uno**. El **diseño debe reservar espacios para anuncios** (ad slots) de entrada, no
  como un parche posterior.

### Anuncios auto-gestionados / venta directa (modelo primario)

- **Contexto RD:** plataformas tipo **AdSense tienen presencia limitada** en RD. No se puede
  depender de ellas como fuente principal.
- **Requisito:** poder vender y poner anuncios **"como en los viejos tiempos"** → **venta
  directa**: alguien quiere pagar por un banner, y **el propio admin lo administra** desde el
  sitio, **sin depender de una plataforma externa**.
- **Implica un módulo de administración de anuncios** (parte del back-office / admin). Necesita,
  como mínimo:
  - Subir **creativos** (banners/imágenes) con su **URL de destino**.
  - Asignarlos a **zonas/ad slots** del layout.
  - **Programación** (fechas de inicio/fin de la campaña).
  - (Deseable) **métricas básicas** de impresiones/clics para reportar al anunciante y renovar.
  - (Deseable) datos del **anunciante** (quién paga, vigencia).
- **⚠️ No cerrar puertas:** las zonas de anuncios deben poder alojar **tanto un creativo propio
  (directo) como, si algún día conviene, un tag de un tercero** (AdSense u otra red). Diseñar el
  "ad slot" como algo **agnóstico** al origen del anuncio.
### ✅ Enfoque preferido: ad server HOSTED (SaaS en la nube)

- **Idea del dueño (muy alineada con el Principio #0):** en vez de self-hostear, **pagar una suma
  módica mensual** a una **plataforma de anuncios en la nube**, gerenciar los anuncios desde ahí,
  y que el website **solo tenga que enlazarse** a esa plataforma (pegar un tag/snippet). Cero
  infraestructura de ad server propia.
- **Esto supera el dilema anterior** (self-host Revive con PHP+MySQL vs. módulo propio): un ad
  server **hosted** da la misma capacidad **sin** correr PHP+MySQL ni construir nada.
- **Opciones reales (a evaluar):**
  - **Google Ad Manager (GAM)** — **gratis**, hosted por Google, potente; maneja **venta directa
    (tus anunciantes) + house ads + programático** en un solo lugar. Más complejo; probablemente
    overkill al inicio, pero escala.
  - **AdButler / Broadstreet / AdSpeed** — ad servers **hosted de pago mensual módico**,
    orientados a publishers independientes/locales → encajan con la **venta directa** a
    anunciantes RD. Simples: creas zonas, gerencias campañas, te dan el tag para pegar.
  - **Revive Cloud** (Revive hosteado por terceros) — si gusta Revive pero sin self-host.
- **Lado del website = trivial y agnóstico:** solo hay que **renderizar el tag** de la plataforma
  dentro de las **zonas de anuncio** ya previstas. La zona sigue siendo **agnóstica** (tag de un
  hosted server hoy, creativo directo o AdSense mañana) → no hay que decidir el proveedor ahora,
  solo construir slots que rendericen un snippet.
- **Notas honestas:** los tags de ads son client-side → interactúan con **ad blockers** y suelen
  **setear cookies** (se ata al consentimiento/privacidad). Nada grave, solo tenerlo presente.

### Membresías / Patreon — ⏸️ PENDING (aplazado)

> Estado: **parqueado.** El dueño confirma que hay temas más apremiantes primero. No se decide
> nada ahora; se retoma más adelante. Notas para cuando se retome:

- El dueño pregunta si vale la pena contemplar **Patreon** (u otra membresía) desde ya, por si
  integrarlo después exige **diseñar algo específico** de entrada.
- **Recomendación:** **no construirlo ahora** (prematuro: aún no hay audiencia ni contenido;
  hacerlo hoy viola "simple / no sobre-ingeniería"). **Pero sí dejar la puerta abierta barato.**
- **Lo único que hay que diseñar bien desde el inicio** para no cerrarse: modelar el acceso al
  contenido como **entitlements por niveles/tiers**, NO como binario "anónimo vs registrado".
  - Si el gating pregunta *"¿este usuario tiene derecho a ver esto?"* según atributos/nivel,
    entonces añadir "es patrocinador tier X" luego es una **extensión, no una reescritura**.
  - Cubre Patreon **y** cualquier alternativa (Ko-fi, Memberful, Stripe, etc.) sin casarse con
    una hoy.
- **Por qué Patreon encaja con el Principio #0 (resiliencia/bajo-ops):** **externaliza pagos,
  facturación e impuestos** → cero infraestructura de cobros que mantener. Encaja con "apoyarse
  en servicios/librerías conocidos".
- **Estado:** carril de monetización **futuro y opcional**. Diseñar el acceso como tiers ahora;
  decidir proveedor (Patreon vs otros) cuando haya tracción.

## Plataforma / CMS (desde el inicio)

- Se necesita un **motor de contenido tipo CMS headless desde el arranque**.
- **Razón:** los artículos serán escritos por **al menos dos personas** → hace falta gestión de
  contenido multi-autor, con usuarios y roles, no un blog de un solo autor hardcodeado.
- **✅ DECISIÓN: adoptar un CMS maduro — NO construir uno.** (Fiel a "no reinventar" +
  resiliencia.)
- **Requisito duro:** que **use PostgreSQL** (ya hay una instancia Postgres para apalancarse).
- **✅ CMS ELEGIDO: Wagtail** (sobre Django/Postgres) — consecuencia de la decisión de stack
  Python. Da roles + workflow de aprobación + editor rich-text (StreamField/Draftail) casi de
  fábrica. Ver *Stack tecnológico*. (Los candidatos Node —Directus/Strapi/Payload— eran para el
  camino TypeScript, ya descartado.)
- **⚠️ Matiz de arquitectura a recordar:** el sistema de usuarios de un CMS suele ser para los
  **usuarios editoriales** (writers/editors/admin). Los **lectores públicos** (registro + login
  social + gating) probablemente sean un **sistema de auth aparte**. Son dos mundos de usuarios;
  no asumir que el CMS resuelve también las cuentas de los lectores.

## Flujo editorial (ciclo de vida del contenido)

- El **writer escribe** su artículo en un **control de texto enriquecido (rich-text / WYSIWYG)**
  de algún tipo (idealmente una librería/editor OSS conocido, fiel a "no reinventar").
- Al terminar, el artículo entra en un **flujo de aprobación sencillo** (simple, no burocrático).
- Una vez **aprobado**, se **publica** en el website.
- Estados implícitos: **borrador → pendiente de aprobación → aprobado/publicado.**
- Encaja con los roles: **writers** crean, **editors** (o **administrators**) aprueban.
- ⚠️ Mantenerlo **simple** (Principio #0 / no cerrar puertas): un flujo básico que después se
  pueda enriquecer si hace falta, sin sobre-ingeniería inicial.

## Roles / permisos

Cuatro roles contemplados:

- **Users** — lectores registrados (consumen contenido tras el registro).
- **Writers** — escriben artículos.
- **Editors** — revisan/editan/aprueban contenido.
- **Administrators** — gestión total del sitio. Incluye la **página CRUD de la tabla maestra de
  jugadores dominicanos** (mantener el subset) y la gestión de anuncios.

## Modelo de acceso (gating / muro de registro)

- **✅ En el launch: 100% abierto, sin muro** (ver "Launch scope"). El gating se **activa después**.
- El sitio es **público** en general (SEO, alcance).
- (Cuando se active) al **cruzar cierta línea** se le **exige al usuario registrarse**.
  - La línea **aún no está definida**. Ejemplo mencionado: **leer un artículo (completo)**.
  - Es un modelo de **contenido con muro/gating** en un umbral por definir (podría ser: leer
    más de N artículos, acceder a artículo completo, ver ciertas stats, etc.).
- Implicación de diseño: hay que soportar estados **anónimo** vs **registrado** y decidir dónde
  cae el muro (flexible, ver principio de no cerrar puertas).
- **(PENDING)** Considerar modelar el acceso como "entitlements por niveles/tiers" en vez de
  binario, para dejar abierta la puerta a membresías/Patreon. **Decisión aplazada** a cuando se
  diseñe la capa de acceso — solo dejar la nota en el radar (ver sección Membresías/Patreon).

## Autenticación

- **No manejar passwords propios** (no lidiar con almacenamiento/reset de contraseñas).
- **Login social / federado:** Google, Facebook, etc. (OAuth / social login).
- Encaja con "apalancarse en librerías/servicios conocidos" y reduce superficie de seguridad.

## SEO

- Del sitio antiguo **solo sobrevive el nombre de dominio** — **no hay contenido ni URLs viejas**
  que preservar/redirigir. Simplifica: no hay migración.
- La jugada SEO es aprovechar la **antigüedad/autoridad del dominio (20+ años)** + construir
  contenido nuevo con **buena arquitectura SEO** desde el inicio: URLs limpias, metadatos,
  sitemap, datos estructurados (schema), velocidad y buen comportamiento en móvil.
- El **contenido de nicho en español** (dominicanos + sabermetría) tiene poca competencia → buena
  oportunidad de posicionar.

## Legal / derechos (a atender antes del lanzamiento)

- **Privacidad + consentimiento de cookies:** con **registro de usuarios, login social, anuncios
  y analytics**, hacen falta **política de privacidad** y **banner de consentimiento de cookies**
  (obligatorio, no opcional).
- **Términos de servicio** básicos.
- **🖼️ Imágenes / fotos — el punto delicado.** Postura del dueño (medio en broma): "¿usarlas y
  esperar la desist letter?". **Recomendación honesta:** NO. Un "cease & desist" es el resultado
  *amable*; también puede haber DMCA takedowns, **baneo de redes de anuncios** por contenido
  infractor, o daños. Para un proyecto que quieres **crecer y monetizar**, arrancar limpio es más
  inteligente. Opciones seguras:
  - **Apoyarse en tus propias visualizaciones/gráficos como imagen principal** — encaja perfecto
    con tu identidad (data/sabermetría, estilo Savant) y es **riesgo legal ~cero**. La data-viz
    como lenguaje visual del sitio, no las fotos.
  - Fuentes libres/licenciadas: Wikimedia Commons (algunas de jugadores en CC), Unsplash/Pexels,
    Flickr CC. Verificar licencia caso por caso.
  - Headshots oficiales de MLB (vía su contenido) — revisar términos de uso antes.
  - Fotos de prensa (AP/Getty) = pago; evitar salvo licencia.
  - **Decisión del dueño:** por ahora, **las fotos esperan** (no usar infractoras). Empezar con
    data-viz + fuentes libres.

## Lanzamiento — estrategia "big-bang"

- **Postura del dueño:** este tipo de proyecto se **lanza tipo big-bang**, no a medias. Lanzar un
  sitio incompleto y luego perder viewers es contraproducente (primera impresión + reputación del
  dominio).
- ✅ Se respeta: el **lanzamiento público debe sentirse completo y pulido**.
- ⚠️ **Matiz (Principio #0 / riesgo real):** "big-bang" NO significa "construir todo antes de
  validar" ni caer en scope creep infinito. El riesgo del big-bang es **nunca lanzar**. Por eso:
  definir con disciplina un **"launch scope" acotado** = el conjunto mínimo que hace que el sitio
  se sienta completo. Internamente se construye por fases; solo se **abre al público** cuando ese
  núcleo está sólido.
- ⚠️ **El launch scope NO es un MVP pequeño** (data pipeline + CMS + páginas data-driven + live +
  auth + ads + infra). Por eso **internamente** se construye **fase a fase, con staging/beta
  disciplinado** — NO de un tirón. → Ver **`docs/BUILD_PLAN.md`** (fases 0–8 de construcción).

## Launch scope (acordado)

> El alcance del big-bang, validado con el dueño. **Cómo se construye** (fase a fase, con
> staging/beta) está en `docs/BUILD_PLAN.md`. Regla de oro: **todo lo que no esté en "Entra en el
> launch" es post-launch.**

### Entra en el launch (el sitio debe SENTIRSE completo)

- **Contenido semilla:** **8–12 artículos** de calidad **listos el día 1** (✅ acordado). (Un
  relanzamiento con el blog vacío se siente muerto y quema la primera impresión — clave para el
  big-bang.)
- **CMS + flujo editorial funcionando:** writer escribe en rich-text con embeds → aprobación →
  publicación. Los 2 mundos de usuarios operativos (editoriales; lectores).
- **Páginas de jugador (~970):** todas existen, con stats **ambiciosas/sabermétricas** (batting,
  fielding, pitching) — **no solo básicas** — ya en el launch, para respaldar los artículos. (El
  **listado exacto de métricas** queda por definir —decisión del dueño, es su fortaleza— pero el
  **nivel es sabermétrico, no básico**.)
- **⭐ Sección de LÍDERES (subset dominicano):** el diferenciador estrella — líderes de **carrera**
  y de **temporada**. **✅ INNEGOCIABLE para el launch** (parte de sentirse "completo"). Requiere
  el **backfill histórico** hecho antes de lanzar (ver Datos).
- **Landing estilo Savant:** artículos destacados + módulos de stats vivas + **players search**
  (typeahead a la página del jugador, dentro del subset dominicano).
- **Módulos en tiempo real (proxy) — solo pizarra MLB en el launch:** pizarra de juegos MLB +
  resumen de la jornada dominicana + cintillo. (Es lo que hace sentir el sitio "vivo".) **Deben
  ser season-aware** (no mostrar la última pizarra en off-season). **LIDOM y Spring Training NO
  van en el launch** → son fast-follow #1 y #2 (implica lanzar en temporada MLB).
- **Auth social** (Google + Facebook) **disponible**, pero **SIN muro de registro en el launch**
  (ver decisión abajo): el registro existe (opcional), el sitio abre 100% público.
- **Zonas de anuncio agnósticas** presentes en el layout (aunque arranquen con house ads).
- **Diseño** sobrio + responsive sobre librería UI, **pulido**.
- **Infra/resiliencia (no-negociables):** HTTPS (reverse proxy + TLS), Cloudflare, **backups
  offsite de Postgres**, monitor de uptime.
- **Legal:** privacidad + consentimiento de cookies + ToS.
- **Analítica:** Umami Cloud conectado.
- **SEO base:** URLs limpias, metadatos, sitemap, datos estructurados, rápido en móvil.

### NO entra (explícitamente post-launch)

- Patreon / membresías por tiers · comentarios/comunidad · newsletter (todos parqueados).
- **Tooling interactivo avanzado** sobre las stats (filtros dinámicos, splits, percentiles,
  visualizaciones interactivas). Aclaración: **la profundidad de los números SÍ entra** en el
  launch (nivel sabermétrico); lo que se difiere es la **interactividad/herramientas** encima.
- Formatos cortos/frecuentes de contenido (arrancar long-form).
- Escalado multi-VPS.
- Ad server sofisticado (arrancar simple: house ads o un anunciante directo vía plataforma hosted).

### Decisión del launch — muro de registro

- **✅ DECIDIDO: lanzar 100% abierto; el muro de registro se activa DESPUÉS.** Maximiza viewers e
  indexación de Google al arranque y evita fricción temprana. El registro social existe como
  opción desde el launch, pero **no bloquea** nada todavía.
- Implicación de diseño: el sitio funciona **completo para usuarios anónimos**; el gating es una
  capa que se **enciende más adelante** sin reescribir (coherente con "no cerrar puertas").

## Roadmap / fases (consolidado)

- **🚀 Lanzamiento (big-bang, Fase 1):** blog + páginas de jugador (~970) + **Líderes** + **pizarra
  MLB** (season-aware) + landing + auth social (sin muro) + ads slots + infra resiliente. Se lanza
  **durante la temporada MLB**, 100% abierto.
- **Fast-follow #1: LIDOM** (pizarra invernal; antes del off-season nov–ene).
- **Fast-follow #2: Spring Training** (pizarra feb–mar).
- **Post-launch (cuando aplique):** activar el **muro de registro** / gating.
- **Fase 2 (tras el éxito):** **Minor Leagues** (prospectos dominicanos). Membresías/Patreon,
  comentarios, newsletter — según se decida.
- Todas las pizarras (MLB/LIDOM/Spring/menores) = **mismo statsapi, mismo proxy**.

## Analítica

- **✅ Decisión: Umami Cloud** (ver detalle abajo). Se evaluó Google Analytics pero se descartó
  como punto de partida por las **cookies** (fricción de consentimiento) y por **ceder los datos
  de la audiencia a Google**.

### Umami (elegido — punto de partida)

- **Qué es:** analítica web **open-source**, ligera, **enfocada en privacidad**. Dashboard simple
  (visitas, páginas, referrers, países, dispositivos) — lo esencial, sin la complejidad de GA.
- **Encaja con el stack:** corre sobre **PostgreSQL** (o MySQL); dockerizable.
- **Ventaja legal:** **sin cookies por defecto / no recolecta datos personales** → normalmente
  **no requiere banner de consentimiento** → menos fricción legal que GA.
- **Dos formas de usarlo:**
  - **Self-host** (gratis) — es **una pieza más** que mantener (roza el "mínimo ops").
  - **Umami Cloud** — versión hosteada con **tier gratis**; te da los beneficios de privacidad
    **sin** montar el contenedor → probablemente lo mejor para este proyecto (cero ops).
- **Trade-off honesto:** GA es **más potente y cero-infra** (Google lo hospeda), pero trae cookies
  y cede datos a Google. Umami es **más simple y privacy-first**, pero self-host suma una pieza
  (mitigable con Umami Cloud).
- **✅ DECISIÓN: arrancar con Umami Cloud** (tier gratis) como punto de partida → privacidad +
  cero-ops (sin contenedor propio) + probablemente sin banner de cookies. Reevaluable después.

## Temas abiertos (parqueados para discutir luego)

- **Qué ofrecer al usuario registrado:** aún no definido. El dueño reconoce que **hay que
  ofrecer algo** a cambio del registro, pero todavía no sabe qué. (Semillas a explorar más
  adelante: comentar, guardar favoritos/seguir jugadores, contenido/artículos exclusivos,
  acceso a ciertas stats/visualizaciones, newsletter.)
- **Newsletter:** no está en los planes ahora, **pero no se cierra la puerta** — se contempla
  como oportunidad futura. (Diseñar para poder capturar emails aunque no se use al inicio.)
- **Comentarios / comunidad:** el dueño tiene **reservas** — no tiene tiempo para **moderar**.
  Tensión: el béisbol en RD genera mucha conversación (activo potencial) vs. la carga de
  moderación. **Se discutirá luego.** (Nota: existen opciones de bajo mantenimiento —
  proveedores externos, comentarios solo para registrados, moderación asistida — a evaluar.)

- **LIDOM + Spring Training:** ✅ **comprometidos** (ver Estacionalidad) — ya no parqueados.
  **LIDOM confirmado como `sportId` del statsapi** → mismo proxy. Solo queda decidir si entran en
  launch o fast-follow.
- **FASE 2 — Minor Leagues:** poner información relevante de ligas menores (prospectos
  dominicanos, etc.). **Explícitamente post-éxito de la Fase 1.** Igual salen del **statsapi**
  (mismo proxy, distinto sportId) → costo incremental razonable. **Parqueado como Fase 2.**

## Principio transversal — NO cerrar puertas

> "Uno sabe cómo empieza, pero no cómo termina." Evitar decisiones tempranas que limiten después.

- No sobre-optimizar para un solo formato (long-form) ni un solo tipo de contenido.
- Mantener **flexibilidad** en arquitectura, modelo de contenido y diseño para poder evolucionar
  (más frecuencia, nuevos formatos, más stats) sin reescribir.

## Diseño visual / estética

- **Dueño sin background de diseño** (ingeniero, "distingo 16 colores" 😄) → el diseño debe
  resolverse **sin depender del talento visual del dueño**: apoyarse en una **librería CSS/UI
  conocida con un tema por defecto sensato**.
- **Dirección estética:** **sobrio, limpio, minimalista, funcional.**
  - Sin **ruido visual**, sin adornos, sin **efectos especiales que no aporten**.
  - Nada de "flores y colores" — audiencia masculina; estética contenida y seria.
  - **Funcionalidad y usabilidad por encima de bells & whistles.**
- **Paleta:** contenida / neutra (por definir; probablemente tonos sobrios, alto contraste,
  data-forward al estilo Baseball Savant).
- **✅ Tipografía (sistema híbrido, decidido):**
  - **Monospace (JetBrains Mono)** para **UI, navegación, stats, tablas y títulos** → identidad
    "data/sabermetría" + números que alinean solos.
  - **Fuente legible** (serif o sans, por afinar en la página de artículo) para el **cuerpo de los
    artículos long-form** → lectura cómoda. "Lo mejor de ambos."
- **📱 Responsive (requisito, no opcional):** el sitio debe **auto-ajustarse a pantallas de
  celular** y **reaccionar con gracia y fluidez** en teléfono. Debe **funcionar bien en móvil**,
  no solo "verse aceptable".
  - ⚠️ Matiz del dueño: **NO se compromete a "mobile-first"** como filosofía de diseño. El
    requisito es que **funcione bien en ambos** (desktop y móvil), sin priorizar formalmente uno.
  - Aplica a **todo**: artículos long-form legibles en móvil, pizarra/cintillo/stats que se
    reacomodan bien en pantalla chica, navegación cómoda.
- **Encaja con los otros principios:** una librería de componentes madura da **responsividad,
  accesibilidad y consistencia "gratis"** (menos código propio, más resiliencia, cero necesidad
  de talento de diseño). Coherente con "no reinventar CSS". La responsividad **viene incluida**.

## ✅ Stack tecnológico (DECIDIDO — Python en todo)

> Decisión basada en: el dueño es más productivo en **Python** y prefiere **un solo lenguaje**;
> la UX es de **sitio de contenido** (no app-like). Máxima alineación con el Principio #0.

- **Lenguaje único: Python** en las 3 piezas → menos context-switching, menos mantenimiento.
- **Website: Django + Wagtail** (CMS sobre **Postgres**).
  - **Wagtail** cubre el lado editorial casi de fábrica: **artículos/blog, roles, flujo de
    aprobación (workflow built-in), editor rich-text (Draftail)** → justo lo que definimos.
  - **Django** cubre el lado data-driven: **páginas de jugador (~970), Líderes y pizarra** como
    vistas que renderizan desde las tablas Postgres; **admin/CRUD** de la tabla maestra dominicana
    casi gratis (Django admin / Wagtail snippets).
  - Ambos conviven en **un solo proyecto Django**.
- **Interactividad / módulos vivos:** **HTMX** (polling simple al proxy) para pizarra/cintillo →
  resiliente, sin necesidad de SPA ni framework JS pesado.
- **Auth social:** **django-allauth** (Google/Facebook), sin passwords. (No reinventar.)
- **UI / CSS:** framework maduro (Bootstrap o Tailwind) → sobrio + responsive de fábrica.
- **Data-viz / gráficos:** librería de charts embebida o SVG server-side; mantener simple.
- **Datos:** proxy **FastAPI** (Python, hecho) + **scrapers Python** → **Postgres** (compartida
  con Wagtail).
- **Todo dockerizado**, un VPS, Cloudflare + TLS + backups.
- **Por qué:** framework "aburrido" y batteries-included, un solo lenguaje, pocas piezas móviles →
  lo más resiliente y de menor mantenimiento para un mantenedor solo. Wagtail regala CMS + roles +
  workflow + CRUD sobre Postgres.
- **Versión:** **Python 3.13 unificado** en las 3 piezas (incluye bumpear el proxy, hoy 3.12).
  Requiere **Django 5.1+ / Wagtail 6.3+** (verificar al implementar).

### Estándar de código (adoptado)

- **`docs/CODING_STANDARDS.md`** es el estándar oficial (Python 3.13: ruff line-120 + ANN/N,
  mypy strict, tipos modernos, fail-loud, funciones ≤20 líneas, testing AAA, etc.).
- **Aplica a todo el código nuevo** (website + scrapers) desde el día 1.
- **El proxy existente se ALINEA** a la convención (estructura `src/`, line 120, 3.13),
  **apretando `mypy strict` de forma gradual** (no de golpe). → tarea de la fase de ejecución.
- **✅ `docs/library-guidelines.md` creado** — convenciones Django/Wagtail: estructura de proyecto,
  settings por env, ORM/migraciones, Wagtail (StreamField/workflow/roles/SnippetViewSet), páginas
  data-driven, HTMX, `django-stubs` para mypy strict, testing pytest-django, seguridad.
- **Refinamiento (de library-guidelines):** los **scrapers = Django management commands** que
  comparten modelos/ORM (un solo schema), pero **corren como contenedor programado aparte** (misma
  imagen) → siguen operacionalmente semi-independientes. *No contradice el "3 piezas"; lo precisa.*

### Nota — CMS

- La decisión Python **hace del CMS = Wagtail**. Los candidatos Node que se habían listado antes
  (Directus / Strapi / Payload) quedan **superados** (eran para el camino TypeScript).
- **Reparto de responsabilidades:** Wagtail = contenido editorial (artículos). Django (vistas) =
  lo data-driven (páginas de jugador, Líderes, pizarra) desde las tablas de stats en Postgres.

## Principios de ingeniería (definidos por el dueño)

- **Apalancarse al máximo en librerías open-source ampliamente conocidas.**
- **No reinventar:** si una librería ya implementa algo, se usa la librería en vez de codificarlo
  a mano. Aplica también a **librerías de CSS** (no escribir CSS a mano si un framework lo cubre).

## Mapa del discovery — cobertura por área

Estado de cada dimensión típica de un discovery (✅ cubierto · 🟡 parcial · ⬜ sin tocar):

- ✅ **Visión / diferenciador** (dominicanos, blog>stats, propósito).
- ✅ **Identidad / audiencia** (nombre, dominio, español, RD masculino).
- ✅ **Modelo de contenido** (FanGraphs-style, long-form, flujo editorial, roles).
- ✅ **Plataforma / auth** (CMS headless, roles, login social, gating).
- ✅ **Arquitectura / infra** (3 piezas dockerizadas, 1 VPS→multi, resiliencia, backups).
- ✅ **Diseño visual** (sobrio, responsive, librería UI).
- 🟡 **Monetización** (ads directos definidos; Patreon parqueado).
- 🟡 **Estadísticas** (2 fuentes definidas; detalle diferido — es la fortaleza del dueño).
- ✅ **Definición de "dominicano" / datos** — **tabla maestra curada por admin (CRUD)**; ~970
  jugadores; fortaleza del dueño; no es riesgo.
- ✅ **Interconexión artículo ↔ stats / páginas de jugador** (páginas ~970, embeds, links,
  hashtags).
- ✅ **SEO** (solo sobrevive el dominio; jugada = autoridad del dominio + arquitectura SEO nueva).
- 🟡 **Legal / derechos** (plan: data-viz + fuentes libres, fotos esperan; falta redactar
  privacidad/cookies/ToS).
- ✅ **Analítica** — **Umami Cloud** (decidido; privacy-first, cero-ops).
- ✅ **Lanzamiento** — big-bang decidido, **launch scope acordado**, y fases de construcción en
  `BUILD_PLAN.md`.
- ✅ **CMS** — **Wagtail** (Django/Postgres), consecuencia de la decisión de stack Python.
- ✅ **Stack del website** — Python en todo: **Django + Wagtail + HTMX + django-allauth**, Postgres.
- ✅ **Estándar de código** — `CODING_STANDARDS.md` + `library-guidelines.md` (Django/Wagtail);
  **Python 3.13 unificado**; proxy se alinea (mypy strict gradual con `django-stubs`).

## Pendiente de definir (próximas charlas)

- Dónde cae exactamente el **muro de registro** (qué acción/umbral lo dispara).
- **Membresías / Patreon** y el modelo de acceso por tiers (aplazado; hay cosas más apremiantes).
- Proveedores de login social a soportar (Google + Facebook confirmados; ¿otros?).
- ✅ Feature estrella → **RESUELTO: LÍDERES del subset dominicano** (carrera + temporada).
- Referencias visuales / de producto (más allá de Baseball Savant para el landing).
- Estrategia SEO para aprovechar el dominio antiguo.
- Ad server hosted: elegir proveedor (GAM gratis vs. AdButler/Broadstreet/AdSpeed de pago) ·
  formatos/tamaños de banner · zonas.
- Detalle de las estadísticas / listado exacto de métricas (más adelante, por decisión del dueño).

## Decidido hasta ahora

- Blog al centro, stats de apoyo (inversión del sitio original).
- Blog estilo FanGraphs (analítico/novedoso, no noticioso); arranca long-form sin cerrar puertas.
- Landing estilo Baseball Savant (artículos rodeados de stats).
- Stats en 2 fuentes: proxy MLB (tiempo real) + Postgres vía scrapers (programadas).
- **⭐ Feature estrella: LÍDERES del subset dominicano** (carrera + temporada) — la joya, fue éxito
  antes; imposible de replicar en Baseball Reference para un subconjunto.
- **Stats ambiciosas/sabermétricas** (no básicas) en batting/fielding/pitching, para respaldar los
  artículos.
- **8–12 artículos semilla** listos el día 1.
- **Líderes = innegociables para el launch.**
- **Datos:** tabla maestra dominicana vía **CRUD del admin**; **backfill histórico una sola vez**
  antes de lanzar (proxy o DB local); luego todo por **scrapers + proxy**. Orden: **scrapers +
  CRUD operativos ANTES del backfill** (para que la data siga viva sola).
- **Sitio season-aware con cobertura 12 meses:** pizarra **MLB** (temporada) → **Spring Training**
  (feb–mar) → **LIDOM** (invierno). El sitio nunca se ve abandonado. Artículos viven todo el año.
- **Fase 2 (post-éxito): Minor Leagues** (prospectos dominicanos) — parqueado.
- **Cuello de botella real = los 8–12 artículos** (contenido), no los datos.
- Monetización contemplada desde el día uno (ad slots en el diseño).
- **Anuncios de venta directa / auto-gestionados** (AdSense tiene poca presencia en RD): el admin
  administra los banners; zonas de anuncio **agnósticas** (creativo propio o tag de tercero).
- **Ad server HOSTED (SaaS)** como enfoque preferido: pagar mensual módico, gerenciar desde la
  plataforma, el sitio solo pega el tag. Supera el self-host de Revive. Sitio = solo renderiza
  tags en zonas agnósticas.
- **Big-bang solo en el lanzamiento público**; por detrás se construye por fases hasta llegar.
- **CMS:** dos mundos de usuarios aceptados (editoriales vs lectores) · fotos "por la ley"
  (data-viz primero) · **Umami Cloud** para analítica.
- Stack apoyado en librerías OSS conocidas; mínimo código propio.
- Español; audiencia masculina de RD.
- **CMS multi-autor** desde el inicio → **Wagtail** (sobre Django/Postgres).
- **Stack: Python en todo** — Django + Wagtail + HTMX + django-allauth (social); proxy + scrapers
  también Python; Postgres compartida.
- **Roles:** users, writers, editors, administrators.
- **Flujo editorial simple:** writer escribe en rich-text/WYSIWYG → aprobación → publicación.
- **Launch 100% abierto** (sin muro); el registro/gating se activa **post-launch**.
- **Auth social** (Google/Facebook/etc.), sin passwords propios.
- **⭐ Resiliencia > features** (Principio #0): bajo mantenimiento, nada frágil, mínimo sysadmin.
- **Diseño sobrio/minimalista/funcional**, apoyado en librería UI conocida (sin talento de
  diseño requerido; sin ruido visual ni efectos innecesarios).
- **📱 Responsive obligatorio** — debe funcionar bien en celular (sin comprometerse a
  "mobile-first" como filosofía; buena experiencia en desktop y móvil).
- **Arquitectura en ≥3 piezas dockerizadas y semi-independientes:** mlb-proxy (hecho),
  data-pulling→Postgres, website (Django + Wagtail, un solo proyecto Python).
- **Hosting:** un **solo VPS** hospeda todo dockerizado al inicio (suficiente para el
  lanzamiento), **pero diseñado para poder separar piezas en VPS distintos si se crece** (comms
  por red con endpoints configurables, nada de `localhost` hardcodeado). Se le suman: **backups
  offsite de Postgres (crítico)**, Cloudflare free, reverse proxy con TLS auto, monitor de uptime.

## Infraestructura / hosting

- **Al inicio: un solo VPS hospeda todo**, todo **dockerizado junto**: mlb-proxy + website
  (front+back) + PostgreSQL + scrapers. (La IP `10.0.0.39` era solo entorno de pruebas.)
- **Para cómputo, el VPS alcanza para el lanzamiento inicial** (hobby, bajo tráfico).
- **🚀 No cerrar la puerta a escalar horizontalmente:** si el proyecto crece, las piezas deben
  poder **moverse a VPS distintos** sin reescribir. Implicación de diseño (ya alineada con la
  arquitectura en piezas dockerizadas semi-independientes):
  - Las piezas se comunican **por red con endpoints configurables** (URLs, hostnames, connection
    strings vía **variables de entorno**), **nunca hardcodeando `localhost`** ni asumiendo
    co-ubicación. Así, pasar de "todo en un VPS" a "cada pieza en su VPS" es **cambio de config,
    no de código** (justo como el website consumirá el proxy vía URL + API key).
- **Sizing:** depende del stack final; el límite práctico será la **RAM** (suma de contenedores:
  Postgres + backend + proxy + scrapers). A dimensionar cuando se elija el stack.
- **🗄️ Tres contextos de base de datos (todo vía `DATABASE_URL` — config, no código):**
  1. **Dev/CI local:** Postgres **desechable en Docker** (aislado; los tests crean/borran bases;
     NO toca nada externo). Es lo que se usa ahora.
  2. **Servidor de datos de desarrollo = `10.0.0.39` (requisito del dueño, no negociable):** cuando
     se pueblen **datos reales** (tabla maestra, backfill, stats, líderes — Fases 2–4), la Postgres
     autoritativa **durante el desarrollo** es la de 10.0.0.39.
  3. **Producción = VPS (otra IP):** **NO se instala nada ahí hasta el big-bang.** En el
     lanzamiento se despliega todo al VPS (app + Postgres + proxy + scrapers).
  - Cambiar de un contexto a otro = **una variable de entorno**, sin tocar código.

### "Algo más" que sí hace falta (bajo esfuerzo, alto valor — Principio #0)

Un VPS único es un **punto único de falla**; estas piezas lo hacen resiliente sin sumar ops:

1. **🔴 Backups automáticos y OFFSITE de PostgreSQL** — el más crítico. El activo central son los
   **artículos** (escritos por personas). Sin backup offsite, un fallo de disco = pérdida total
   del contenido. Dump programado → object storage. **Innegociable** dado el Principio #0.
2. **Cloudflare (free tier) delante del VPS** — CDN, caché, HTTPS, DDoS, esconde IP de origen.
   Gratis, setup mínimo, gran ganancia de resiliencia + performance.
3. **Reverse proxy con TLS automático** (Caddy / Traefik) — HTTPS obligatorio; el **login social
   (OAuth) exige https**. Certificados auto-renovados = cero mantenimiento.
4. **Monitor de uptime** (ej. UptimeRobot, gratis) — avisa si el sitio cae, sin tener que
   vigilarlo (clave en un sideline).

### Dependencias que NO son hardware (pero hay que preverlas)

- Registrar las **apps OAuth** (Google/Facebook) con el dominio de producción y sus callbacks.
- Aprobación de la **red de anuncios** (ej. AdSense) una vez el sitio esté vivo.
- DNS del dominio apuntando al VPS (vía Cloudflare si se usa).

## Contexto técnico (sin entrar en código todavía)

- Fuente de datos en vivo: **proxy MLB** (`mlb-api`) — ya expone stats con traducciones al
  español; encaja con el sitio en español. El recorte "solo dominicanos" se aplica **filtrando por
  la tabla maestra en Postgres** (autoridad final), **no** por el `birthCountry` de MLB
  directamente (ese es solo input/semilla — ver Datos).
- Fuente de datos precalculada: **PostgreSQL** alimentada por **scrapers en schedule**.
- Filosofía: **stack basado en librerías OSS conocidas**, mínimo código propio.
