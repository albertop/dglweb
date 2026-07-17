# Plan de construcción interno — hacia el big-bang

> **Producto vs. construcción.** El `CONCEPT.md` tiene el *roadmap de producto* (Launch →
> fast-follows LIDOM/Spring → Fase 2). **Este documento es distinto:** son las **fases internas de
> ingeniería** para *construir* el launch scope — **una por una, paso a paso, NO de un tirón.**
>
> **Realidad reconocida:** el launch scope **NO es un MVP pequeño** (data pipeline + CMS + páginas
> data-driven + live + auth + ads + infra). Por eso, aunque la apertura sea "big-bang público",
> **internamente** se construye con fases disciplinadas y un **staging/beta** persistente.

## Reglas del juego (disciplina)

- **Staging permanente:** cada fase se despliega y se **verifica en staging** antes de pasar a la
  siguiente. El big-bang público es el **flip final** tras un **beta/dress-rehearsal** completo.
- **Una fase a la vez.** No se arranca la siguiente hasta que la actual cumple su "Done when".
- **TDD (ver CODING_STANDARDS):** cada pieza se construye test-first. "Done" incluye tests verdes.
- **Cada fase entrega algo demostrable** en staging (no trabajo invisible).
- **El contenido corre en paralelo:** escribir los **8–12 artículos** es el cuello de botella →
  empieza apenas exista el editor (Fase 5) y sigue en paralelo hasta el launch.

---

## Fase 0 — Mock / prototipo visual — ✅ COMPLETADA (2026-07-16)

- **Meta:** **ver y aprobar el layout y el estilo** del sitio **antes** de construir backend. Clave
  para un dueño sin background de diseño: quita el riesgo visual de entrada.
- **Entregado** (en `apps/dglweb/mockup/`): mock estático clickable de las **4 páginas clave**:
  - **`index.html`** (landing) — header navy + **players search**, **cintillo EN VIVO**,
    **Destacados de la jornada** (bateadores + lanzadores), widget de Líderes, grid de artículos,
    y **4 zonas de anuncio** (728×90 arriba, in-feed, 300×250 sidebar, 728×90 abajo).
  - **`article.html`** — tipografía híbrida (mono UI/títulos/stats + **serif legible** en cuerpo),
    bloques embebidos (pull quote, tabla de stats, menciones enlazadas).
  - **`player.html`** — estilo BBRef, hero + **tabs de stats** (extensible sin alargar la página).
  - **`leaders.html`** — **selector interactivo** (categoría → métrica → carrera/temporada = 1
    tabla a la vez); leyendas dominicanas reales.
- **Decisiones "lock" de la Fase 0:**
  - **CSS:** Bootstrap 5. **Paleta:** navy sobrio + acentos rojo/azul (guiño RD). Responsive OK.
  - **Tipografía:** **JetBrains Mono** (UI/stats/títulos) + **Source Serif** (cuerpo de artículo).
  - **Sin subtítulo** en el brand (redundante). Títulos de página a 3rem.
  - Módulo del sidebar = "Destacados de la jornada" (no pizarra); pizarra completa → página aparte.
- **⭐ No desechable:** el mock es **HTML/CSS reutilizable** → se convierte en los templates base de
  Django en la **Fase 1**.
- **✅ Done:** el dueño **aprobó** el layout/estilo. Fase 0 cerrada.

## Fase 1 — Fundaciones / esqueleto

- **Meta:** un sitio Django+Wagtail **desplegable en staging**, vacío pero con todo el andamiaje.
- **Entrega:**
  - Proyecto Django+Wagtail con la estructura de `library-guidelines.md`; Postgres; Docker.
  - Settings por entorno (dev/prod), secrets por env con fallo-ruidoso.
  - **CI verde:** ruff (line-120, ANN/N) + mypy (strict + django-stubs, gradual) + pytest (TDD).
  - **Shell de UI = integrar el mock aprobado (Fase 0)** como templates base de Django.
  - Entorno **staging** operativo.
  - (Aquí también) **alinear el proxy** a 3.13 + convención (restructura, mypy strict gradual).
- **Done when:** el mock corre como sitio Django en staging, CI verde, un test de humo pasa.

## Fase 2 — Fundación de datos: tabla maestra + CRUD admin

- **Meta:** la **autoridad de "quién es dominicano"** operativa.
- **Entrega:** modelo `players` (tabla maestra en Postgres) + **página CRUD** en el admin;
  `birthCountry` de MLB solo como input/semilla.
- **Done when:** el admin gestiona los ~970 jugadores en staging (con tests).

## Fase 3 — Pipeline de datos: scrapers en marcha (ANTES del backfill)

- **Meta:** la data **se actualiza sola** (regla del dueño: pipeline vivo antes que backfill).
- **Entrega:** scrapers como **management commands** + contenedor programado; tablas de stats
  (schema managed) pobladas/actualizadas vía ORM; degradación elegante si el proxy falla.
- **Done when:** los scrapers actualizan stats en schedule, observable en staging (con tests que
  mockean el proxy en los bordes).

## Fase 4 — Backfill histórico + LÍDERES + páginas de jugador

- **Meta:** el **diferenciador estrella** vivo con datos reales.
- **Entrega:** command de **backfill** (una vez); **agregados de Líderes** (carrera + temporada)
  precalculados; **páginas de jugador (~970)** con stats **sabermétricas**; páginas de **Líderes**.
- **Done when:** páginas de jugador y Líderes navegables en staging con histórico real.

## Fase 5 — Editorial: Wagtail (artículos + workflow + roles)

- **Meta:** que **writers/editors** puedan producir contenido.
- **Entrega:** `Article` Page con **StreamField** (bloques: párrafo, **tabla**, **gráfico**,
  **embed de jugador**); **workflow de aprobación**; **roles/grupos**; hashtags; links por mención.
- **Done when:** flujo borrador → aprobación → publicación funciona en staging (con tests).
- **⏩ En paralelo desde aquí:** arranca la escritura de los **8–12 artículos semilla**.

## Fase 6 — Módulos vivos: pizarra MLB + resumen jornada + ticker (season-aware)

- **Meta:** el sitio "se siente vivo".
- **Entrega:** vistas **HTMX** que consultan el proxy (server-side, con timeout); lógica
  **season-aware**; degradación elegante en off-season/proxy caído.
- **Done when:** pizarra/ticker MLB actualizándose en staging.

## Fase 7 — Auth social + zonas de ads + landing + players search

- **Meta:** el sitio toma su forma final.
- **Entrega:** **django-allauth** (Google/Facebook, sin muro); **zonas de anuncio agnósticas** +
  tag del ad server hosted; **landing estilo Savant** (artículos + live + líderes ensamblados);
  **players search** (typeahead HTMX sobre la tabla maestra → página del jugador).
- **Done when:** el sitio completo (anónimo) navegable en staging; login social funciona; el
  buscador de jugadores lleva a la página correcta.

## Fase 8 — Endurecimiento para producción

- **Meta:** listo y resiliente para el mundo.
- **Entrega:** **SEO base** (URLs, sitemap, metadatos, datos estructurados); **legal** (privacidad
  + consentimiento cookies + ToS); **Umami Cloud**; **infra:** reverse proxy + TLS, Cloudflare,
  **backups offsite de Postgres**, monitor de uptime.
- **Done when:** checklist de producción completo; staging = réplica de prod.

## Fase 9 — Beta / ensayo general → 🚀 BIG-BANG

- **Meta:** abrir al público con confianza.
- **Entrega:** **8–12 artículos cargados**; QA end-to-end en staging (beta real); ajustes finales;
  **flip a público**.
- **Done when:** el sitio está vivo en `dominicanosengrandesligas.com`.

---

## Dependencias (por qué este orden)

- **0 (mock)** primero: aprueba el estilo/layout barato, antes de todo; su HTML/CSS **alimenta** la
  Fase 1 (no se tira).
- **2 (tabla maestra)** es la **llave** de todo el recorte dominicano → va temprano.
- **3 (scrapers) antes que 4 (backfill)** → regla explícita del dueño.
- **4 (Líderes)** necesita histórico (backfill) → después de 3.
- **5 (editorial)** destraba la escritura de contenido (el **cuello de botella**) → cuanto antes.
- **6–7 (live, auth, ads, landing, search)** ensamblan sobre datos + contenido ya existentes.
- **8 (infra/legal/SEO)** puede prepararse en paralelo, pero **cierra** antes del beta.
- **Backups offsite** deben existir **apenas haya contenido real** (no esperar a Fase 8 si ya se
  está cargando contenido en staging que no se quiera perder).
