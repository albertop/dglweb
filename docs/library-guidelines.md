# Library Guidelines — Django & Wagtail

> Complementa a `CODING_STANDARDS.md`. Aquí van los patrones y *gotchas* específicos de las
> librerías del stack. Donde una regla del estándar choca con la realidad de Django/Wagtail,
> **este documento manda** para el código del website. Escrito para alguien nuevo en Django/Wagtail.
>
> Objetivo transversal (Principio #0): **aburrido, resiliente, poco mantenimiento.** Preferir lo
> que trae el framework de fábrica antes que añadir piezas.

---

## 0. Versiones (verificar al implementar)

- **Python 3.13** (unificado en todo el proyecto).
- **Política: solo LTS.** Es la consecuencia directa del Principio #0 (resiliencia > features) en
  un proyecto de tiempo limitado: una versión LTS trae ~3 años de parches de seguridad, así que se
  actualiza **una vez cada par de años**, no cada trimestre. Las versiones no-LTS de Django duran
  ~8 meses de soporte principal — eso es una tarea de mantenimiento recurrente que no queremos.
- **Django 5.2 LTS** (parches hasta **abr-2028**). *No* subir a 6.0: no es LTS.
- **Wagtail 7.4 LTS** (soporte hasta **nov-2027**). Exige Django ≥ 5.2.
- Fijar versiones en `requirements.txt` con rango de major estable (`Django>=5.2,<6.0`) y
  actualizarlo siempre que se agregue una dependencia (regla del estándar).
- **Cuándo actualizar:** apenas la versión instalada quede fuera de soporte, y **lo antes posible
  dentro de la fase** — el costo del salto crece con la superficie de código que lo toca. El salto
  6.4→7.4 se hizo en la Fase 2 (un modelo + un viewset) justamente por eso.
- **Chequeo rápido de soporte:** `djangoproject.com/download/` y el
  [release schedule de Wagtail](https://github.com/wagtail/wagtail/wiki/Release-schedule).

---

## 1. Estructura del proyecto (reconciliación con `src/`)

El estándar pide `src/<package>/`. **Django NO usa ese layout** — tiene el suyo. Para el website
manda esta estructura; el layout `src/` del estándar aplica al **proxy** y a **scrapers no-Django**.

```
apps/dglweb/
  manage.py
  config/                # el "project" de Django (no una app)
    __init__.py
    settings/            # settings partido por entorno
      __init__.py
      base.py
      dev.py
      prod.py
    urls.py
    wsgi.py
    asgi.py
  dglweb/                # apps de dominio (cada una hace UNA cosa)
    articles/            # contenido editorial (Wagtail Pages)
    players/             # tabla maestra dominicana (~970) + CRUD admin
    stats/               # stats y LÍDERES (modelos de lectura + vistas)
    live/                # pizarra/cintillo (vistas HTMX que consultan el proxy)
    core/                # utilidades compartidas, templates base, mixins
  templates/             # templates a nivel proyecto
  static/                # CSS/JS/estáticos del proyecto
  tests/                 # espeja las apps (pytest-django)
  requirements.txt
```

- **Una app = una responsabilidad** (coherente con "cada función hace una cosa", a nivel app).
- `config/` es el proyecto (settings/urls/wsgi/asgi). Las **apps** viven bajo `dglweb/`.

---

## 2. Settings & configuración (secrets, fail-loud)

- **Settings partido:** `base.py` (común) + `dev.py` / `prod.py`. `DJANGO_SETTINGS_MODULE`
  selecciona cuál según entorno.
- **Secrets solo por entorno** (regla del estándar). Leer con **fallo ruidoso al arranque**:

  ```python
  import os

  SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]          # falla loud si falta
  DATABASE_URL = os.environ["DATABASE_URL"]
  PROXY_BASE_URL = os.environ["PROXY_BASE_URL"]         # el mlb-proxy
  PROXY_API_KEY = os.environ["PROXY_API_KEY"]           # NUNCA al cliente/navegador
  ```

  Herramienta cómoda: **`django-environ`** para parsear `DATABASE_URL` y tipos. (No hardcodear,
  no commitear `.env`.)
- **Prod endurecido** (detrás de Cloudflare + reverse proxy TLS):
  - `DEBUG = False`, `ALLOWED_HOSTS = [...dominio...]`.
  - `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
  - `CSRF_TRUSTED_ORIGINS = ["https://dominicanosengrandesligas.com"]`.
  - Cookies seguras: `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True`.
- `SECRET_KEY`, credenciales OAuth y `PROXY_API_KEY` **jamás** se loguean (regla del estándar).

---

## 3. Modelos, ORM y migraciones

- **El ORM es la fuente de verdad del schema.** Toda estructura de tabla = **migraciones**
  (`makemigrations` → `migrate`). Las migraciones **se commitean**. Nunca tocar el schema a mano.
- **`@dataclass`/Pydantic** del estándar aplica a *data containers* fuera de la DB (DTOs, config).
  Para tablas se usan **modelos Django** (no Pydantic).
- **Dos tipos de tablas en este proyecto:**
  - **Tabla maestra de jugadores dominicanos** → **modelo Django "managed" (con migraciones)**;
    la edita el admin (CRUD). Django la posee.
  - **Tablas de stats / LÍDERES (las que llenan los scrapers)** → ver §8. Recomendación: que las
    **posea el mismo proyecto Django** (un solo schema) y que los scrapers escriban vía el ORM
    corriendo como *management commands*. Evita tener dos definiciones de schema desincronizadas.

---

## 4. Wagtail — el corazón editorial

Wagtail es un CMS **sobre** Django. Nos da casi gratis lo que definimos en el concepto:

- **Artículos = Wagtail `Page` models.** No un modelo plano: usar **`StreamField`** con **bloques**.
  - `StreamField` deja al writer **componer el artículo con bloques**: párrafo rich-text,
    **bloque de tabla**, **bloque de gráfico/visualización**, **bloque de embed de jugador**,
    cita, imagen, etc. → resuelve el requisito "el writer inserta gráficos y tablas".
  - Se definen **bloques custom** (ej. `ChartBlock`, `StatTableBlock`, `PlayerEmbedBlock`).
- **Flujo editorial = Wagtail Workflows (moderación) built-in:** borrador → *submit for moderation*
  → aprobación → publicar. Exactamente el flujo que pediste, **sin construirlo**.
- **Roles = Wagtail Groups + permisos de Django:** mapear Writers / Editors / Administrators a
  grupos. (Wagtail trae grupos "Editors" y "Moderators" de base.)
- **Editor rich-text:** Draftail (el de Wagtail) para los bloques de texto. **Sanitización** de
  HTML la maneja Wagtail; si algún bloque acepta HTML crudo, sanitizar con **`bleach`**.
- **Hashtags / mención de jugadores:**
  - Hashtags → **`django-taggit`** (Wagtail ya lo usa) como taxonomía.
  - "Mencionar a Soto → link a su página" → un **bloque/entidad** que referencia al modelo de
    jugador y renderiza el enlace.
- **Búsqueda:** Wagtail trae backend de búsqueda (empezar con el de base de datos; suficiente).
- **CRUD de la tabla de jugadores en el admin de Wagtail:** exponerla con **`SnippetViewSet` /
  `ModelViewSet`** (Wagtail 6+) para que **todo viva en un solo admin** (el de Wagtail), no en dos.

---

## 5. Páginas data-driven (jugador, Líderes, pizarra)

- **No todo es Wagtail.** Las páginas de **jugador (~970)**, **Líderes** y **pizarra** son
  **data-driven**: vistas Django normales que renderizan desde las tablas de stats en Postgres.
- Usar **Class-Based Views** (o funciones cortas) + templates. Mantener vistas **≤20 líneas**
  (regla del estándar): la lógica de datos va en **funciones puras / managers del modelo**, no en
  la vista.
- **Líderes:** los agregados de carrera/temporada conviene **precalcularlos** (los scrapers los
  materializan en tablas), no calcularlos por request → rápido y resiliente.

---

## 6. Templates + HTMX (módulos vivos, sin SPA)

- **Server-side rendering** con templates de Django → bueno para SEO. Nada de framework JS pesado.
- **HTMX** para los módulos vivos (pizarra, cintillo):
  - Polling simple: `hx-get="/live/scoreboard" hx-trigger="every 30s" hx-swap="innerHTML"`.
  - La vista HTMX devuelve un **fragmento de template** (no página completa).
- **Season-aware:** la vista de la pizarra decide qué mostrar (MLB / LIDOM / Spring Training /
  vacío-elegante) según el estado de temporada → un solo punto de decisión.
- La vista que alimenta HTMX **llama al proxy** server-side (con `PROXY_API_KEY`, sync `httpx`),
  nunca desde el navegador. Poner **timeout** en esa llamada y **degradar con gracia** si el proxy
  no responde (mostrar "sin datos ahora", no romper la página) → Principio #0.

---

## 7. Estáticos, CSS y auth

- **CSS:** framework maduro (Bootstrap o Tailwind) → sobrio + responsive de fábrica. Decidir uno.
- **Servir estáticos en prod:** **WhiteNoise** (sirve estáticos desde el propio proceso Django) →
  cero piezas extra, muy alineado con "menos cosas que mantener". `collectstatic` en el build.
- **Auth social:** **`django-allauth`** para Google/Facebook (sin passwords). Credenciales OAuth
  por entorno.
- **Los dos mundos de usuario** (recordatorio del concepto):
  - **Editoriales** (writers/editors/admin) → usuarios `is_staff`, entran al admin de Wagtail.
  - **Lectores públicos** → usuarios normales vía allauth social. En el launch **sin muro**; el
    gating se enciende después (una comprobación en las vistas, no reescritura).

---

## 8. Scrapers ↔ Django (refinamiento de la arquitectura)

> Refina el "3 piezas" del concepto sin contradecirlo.

- **Recomendado:** los scrapers son **Django *management commands*** (`python manage.py
  backfill_stats`, `python manage.py update_daily`) que **comparten los modelos y el ORM** del
  website. Ventaja: **un solo schema** (migraciones), DRY, un solo lenguaje/proyecto.
- **Siguen siendo operacionalmente semi-independientes:** se ejecutan como un **contenedor aparte,
  programado** (scheduler/cron), usando la **misma imagen** que el website. → mantienes el
  desacople operativo (su propio ciclo de vida, su propio contenedor) sin duplicar el schema.
- **Backfill** = un management command puntual; **actualización continua** = commands en schedule.
- **Async:** aquí SÍ aplican las reglas async del estándar si un scraper hace muchas llamadas de
  red concurrentes (`asyncio.timeout`, `TaskGroup`). El **website (vistas)** es **sync-first** —
  no forzar async ahí.

---

## 9. mypy strict + Django (el gotcha crítico)

`mypy strict` sobre Django es **inviable sin plugins** (el ORM es muy dinámico). Obligatorio:

- Instalar **`django-stubs`** (y `djangorestframework-stubs` si algún día se usa DRF).
- Configurar el plugin en `pyproject.toml`:

  ```toml
  [tool.mypy]
  python_version = "3.13"
  strict = true
  plugins = ["mypy_django_plugin.main"]

  [tool.django-stubs]
  django_settings_module = "config.settings.dev"
  ```

- **Wagtail** tiene tipado parcial → habrá módulos donde toque relajar o usar
  `# type: ignore[code]` **con código de error** (regla del estándar). Ser pragmático: **strict
  global**, con relajación puntual y documentada en las zonas muy dinámicas de Wagtail.
- **Migrar el proxy a strict de forma gradual** (ya decidido): módulo por módulo, no de golpe.

---

## 10. Testing (pytest-django)

- **`pytest` + `pytest-django`** (coherente con el estándar: AAA, `test_<qué>_when_<condición>`,
  clases para agrupar, `parametrize` con `ids=`, probar errores/edge cases).
- **DB en tests:** marcar con acceso a base de datos (`@pytest.mark.django_db`); usar la DB de
  test que crea pytest-django.
- **Fábricas de datos:** **`factory_boy`** para crear jugadores/artículos con variaciones (encaja
  con "factory fixtures" del estándar).
- **Mockear en los bordes:** las llamadas al **proxy** se mockean (no la implementación interna).
  Para vistas, usar el `client` de pytest-django.
- **No testear comportamiento del framework** (regla del estándar): no tests triviales de modelos
  sin lógica; se prueban vía uso real (vistas).
- **`asyncio_mode = "auto"`** ya global (para scrapers async); las vistas Django son sync.

---

## 11. Seguridad (lo que Django ya te da — no reinventar)

- **CSRF** activado por defecto → **dejarlo activado**. Formularios con `{% csrf_token %}`.
- **XSS:** los templates de Django auto-escapan; Wagtail sanitiza el rich-text. Cuidado solo con
  HTML crudo custom (usar `bleach`).
- **SQL injection:** usar el ORM / parámetros; **nunca** SQL con f-strings.
- **Cabeceras/HTTPS:** los `SECURE_*` de §2 detrás de Cloudflare.
- **Nunca** loguear secrets (regla del estándar): OAuth, `PROXY_API_KEY`, `SECRET_KEY`.

---

## 12. Checklist rápido (nuevo módulo/feature)

- [ ] ¿App enfocada, una responsabilidad? ¿Vistas ≤20 líneas, lógica en funciones puras/managers?
- [ ] ¿Migraciones creadas y commiteadas?
- [ ] ¿Secrets/config por entorno, con fallo ruidoso al arranque?
- [ ] ¿Contenido editorial en `StreamField`/bloques (no HTML plano)?
- [ ] ¿Llamadas al proxy con timeout y degradación elegante?
- [ ] ¿Tipos en interfaces públicas? ¿`# type: ignore[code]` con código si hace falta?
- [ ] ¿Tests AAA cubriendo errores/edge cases? ¿Mock solo en bordes?
- [ ] ¿`requirements.txt` actualizado si agregaste una librería?
