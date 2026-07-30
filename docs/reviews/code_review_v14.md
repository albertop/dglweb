# Code Review v14

Fecha: 2026-07-30

Alcance: revisión de `d9706fd`, después de leer todos los archivos `.md` bajo `docs/`, incluidos
`TODO.md`, los documentos de operación, despliegue, rendimiento, datos y sabermetría, y los reviews
anteriores con sus resoluciones.

Reglas aplicadas:

- No se modificó código fuente. Este documento es el único entregable del review.
- No se consideran findings los placeholders ni los datos falsos conocidos de la portada.
- No se repiten asuntos pendientes en `docs/TODO.md`.
- Un problema que cruza varias especialidades aparece una sola vez, bajo la persona que mejor
  representa su riesgo principal.
- El alcance nuevo de respaldos y el manejo de secretos en 1Password fueron revisados, pero no se
  reportan como findings porque la estrategia completa sigue marcada como pendiente en `TODO.md`.
- El riesgo aceptado del socket de Docker de Ofelia tampoco se reabre.

Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P2 | DEV-01 | Python Principal Developer | Una contraseña válida con comilla rompe el bootstrap de Postgres porque se interpola como SQL. |
| P2 | OPS-01 | Docker / fail2ban / nginx | El sincronizador de IP depende de una extensión de `gawk` y puede ocultar una actualización parcial. |
| P3 | SEC-01 | Security Engineer | La configuración versionada de fail2ban no contiene el filtro ni el baseline que necesita para reconstruirse. |
| P3 | ARCH-01 | Backend Architect | El script de release puede construir cambios sin commit y atribuir la imagen al `HEAD`. |
| P4 | SEC-02 | Security Engineer | Las dos rutas de Revive pierden HSTS por las reglas de herencia de `add_header`. |

No se encontraron findings P1.

## Persona 1 - Python Principal Developer

### DEV-01 [P2] El bootstrap inserta la contraseña de la aplicación directamente dentro de SQL

**Evidencia**

- `deploy/postgres/init/10-dglweb.sh:42-44` expande `DGLWEB_DB_PASSWORD` dentro de un literal SQL:
  `PASSWORD '${DGLWEB_DB_PASSWORD}'`.
- El stack solo exige que la variable exista; no declara que deba excluir comillas, saltos de línea u
  otros caracteres válidos en una contraseña (`deploy/postgres/stack.yml:58-62`).
- Reproducción ejecutada en un contenedor limpio de PostgreSQL 18.4 con
  `DGLWEB_DB_PASSWORD="abc'def"`: el init abortó con `unrecognized role option "def"` y no creó la
  base. Es una contraseña legítima; no es un payload artificial.

**Bug / edge case**

Una contraseña generada por un gestor puede contener `'`. El fallo solo aparece al inicializar un
volumen vacío, precisamente durante una instalación nueva o una recuperación. Postgres arranca, pero
el script de init se interrumpe y deja la instancia sin la base utilizable.

La construcción también tiene forma de inyección SQL si el valor fuera controlado maliciosamente,
pero no se presenta como una vulnerabilidad remota: hoy esa variable solo la puede definir quien ya
controla el despliegue. El defecto real y reproducido es de quoting y recuperación fiable.

**Mejora sugerida**

Pasar el secreto como variable de `psql`, por ejemplo con
`--set=dglweb_password="$DGLWEB_DB_PASSWORD"`, y usar `PASSWORD :'dglweb_password'` para que `psql`
produzca un literal correctamente escapado. Añadir una prueba de bootstrap sobre un volumen efímero
con comilla, espacio y barra invertida en la contraseña.

**Razonamiento**

Un secreto es dato, no código SQL. Restringir el alfabeto del generador escondería el problema en la
operación; parametrizarlo preserva todo el espacio válido y hace repetible la recuperación.

## Persona 2 - QA / Reliability Engineer

No se encontró un finding adicional independiente. Los dos escenarios de crash/recovery detectados
se reportan una sola vez como DEV-01 y OPS-01. La suite sí cubre ampliamente validación, nulos,
errores de dependencias, estados vacíos, timeouts y consistencia del pipeline de aplicación.

La brecha de cobertura relevante está en los artefactos operativos: CI ejecuta Python y JavaScript,
pero no prueba el bootstrap de Postgres, los scripts de IP, `nginx -t` ni fail2ban. Esa brecha no se
duplica como finding; forma parte de las correcciones propuestas en DEV-01, OPS-01 y SEC-01.

## Persona 3 - Frontend Engineer

No se encontraron findings nuevos. Se revisaron arquitectura de templates, JavaScript, estados
vacíos/error, accesibilidad, teclado, sandbox de anuncios, carga responsive y contratos de CSP.

Las 47 pruebas Vitest pasan, incluidas las suites de anuncios y compartir que estaban ausentes en el
review v13. Las rutas SSR mantienen estados vacíos y de error probados; no se observó hidratación,
estado cliente duplicado ni un flujo UX roto fuera de los placeholders conocidos de la portada.

## Persona 4 - Security Engineer

### SEC-01 [P3] El despliegue versionado de fail2ban no es autosuficiente

**Evidencia**

- `deploy/fail2ban-nginx.local:64-74` activa una jail llamada `nginx-404-scan` sin declarar `filter =`;
  por contrato, fail2ban buscará un filtro del mismo nombre.
- No existe ningún `nginx-404-scan.conf`, `failregex` ni directorio de filtros bajo `deploy/`.
- `nginx-404-scan` tampoco forma parte del catálogo oficial de jails/filtros de fail2ban. Los filtros
  nginx estándar listados son, entre otros, `nginx-botsearch`, `nginx-bad-request`,
  `nginx-http-auth` y `nginx-limit-req`: [configuración oficial de fail2ban](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf).
- `deploy/sync_access_ip.sh:47-48` depende además de `/etc/fail2ban/jail.local`, y
  `deploy/sync_access_ip.sh:82-92` simplemente omite toda la actualización si ese archivo no existe.
  Ese baseline tampoco está versionado.

El VPS actual casi con certeza conserva ambos archivos fuera del repositorio, porque la documentación
registra coincidencias reales. El finding es que una reconstrucción desde este proyecto no puede
reproducir el control que se afirma versionado.

**Attack scenario**

Después de reinstalar el VPS, restaurar solo los archivos del repositorio o perder una personalización
de `/etc/fail2ban`, la jail de 404 no carga o el dueño queda fuera de `ignoreip`. El panel puede seguir
mostrando otras jails activas, dando apariencia de protección parcial.

**Exploitation method**

Un atacante continúa escaneando rutas inexistentes sin alcanzar el umbral de una jail que no pudo
inicializarse. En el caso inverso, tráfico legítimo del dueño puede acumular coincidencias y ser
baneado porque la lista blanca no se reconstruyó.

**Business impact**

Pérdida silenciosa del control anti-scan, consumo innecesario durante ataques automatizados y posible
bloqueo del único operador. También alarga una recuperación: la configuración efectiva tendría que
reconstruirse desde la memoria o desde el servidor averiado.

**Recommended fix**

Versionar el filtro como `deploy/fail2ban/filter.d/nginx-404-scan.conf` y el baseline de defaults o un
drop-in dedicado que contenga la lista blanca administrada. Añadir un instalador idempotente y probar:

- `fail2ban-regex` contra fixtures de 404 normales, estáticos viejos y escaneos reales.
- `fail2ban-client -t` antes de recargar.
- Instalación desde una raíz `/etc/fail2ban` limpia, no solo sobre el VPS actual.

**Razonamiento**

Versionar solo la jail conserva referencias, no el control completo. Un artefacto de seguridad debe
poder reconstruirse junto con sus filtros, acciones y defaults, o su recuperación depende de estado
oculto.

### SEC-02 [P4] Las respuestas de Revive no heredan la cabecera HSTS del `server`

**Evidencia**

- `deploy/adserver/nginx-promo.conf:70` declara HSTS a nivel de `server`.
- El panel declara sus propios `add_header` en `deploy/adserver/nginx-promo.conf:102-110`.
- La entrega pública también declara sus propios `add_header` en
  `deploy/adserver/nginx-promo.conf:132-140`.
- En nginx, las cabeceras del nivel padre se heredan únicamente cuando el nivel actual no contiene
  ningún `add_header`; `always` no cambia esa regla: [documentación oficial de nginx](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header).

Por tanto, el panel recibe `X-Frame-Options` y `nosniff`, y la entrega recibe CSP y `nosniff`, pero
ninguna de las dos rutas recibe el HSTS declarado arriba.

**Attack scenario**

En la primera visita directa por HTTP a `promo.dominicanosengrandesligas.com`, un atacante en la red
puede intentar retirar o sustituir el redirect antes de que el navegador haya aprendido HSTS.

**Exploitation method**

Ataque de downgrade/SSL stripping sobre una conexión inicial directa al subdominio. El caso normal
queda bastante reducido porque la página principal ya envía HSTS con `includeSubDomains`; el riesgo
residual es un navegador que llegue primero al subdominio de Revive.

**Business impact**

Exposición limitada de la sesión o navegación del panel/entrega en una primera visita bajo red hostil.
La prioridad es baja por el HSTS del dominio padre, TLS obligatorio en los enlaces normales y la
lista blanca del panel, pero la configuración no cumple el control que sus comentarios afirman.

**Recommended fix**

Repetir HSTS en ambos `location`, o incluir en cada uno un snippet común de cabeceras compatible con
la versión antigua de nginx del VPS. No usar `add_header_inherit merge` sin actualizar primero: esa
directiva apareció en nginx 1.29.3. Verificar con `curl -I` una ruta pública y una del panel, no solo
el bloque raíz.

**Razonamiento**

La sintaxis es válida y `nginx -t` queda verde; el error está en la configuración efectiva. Las
cabeceras de seguridad deben probarse por cada `location` que redefine `add_header`.

### Controles OWASP revisados sin finding adicional

No se observaron JWT o autenticación propios, passwords de usuarios fuera de Django/Wagtail,
endpoints `csrf_exempt`, `pickle`, `eval`, command injection desde requests, SSRF controlable por el
usuario, redirects abiertos, bypass nuevo de roles, uploads públicos sin los controles ya descritos
ni una frontera multi-tenant. Cookies, CSRF, sesiones y autorización se mantienen delegados a
Django/Wagtail; CMS, pgAdmin, Portainer y el panel de Revive están además limitados por IP.

El socket de Docker de Ofelia conserva impacto de host, pero figura como riesgo aceptado y cerrado en
`TODO.md`; no se repite.

## Persona 5 - Backend Architect

### ARCH-01 [P3] Una imagen puede contener cambios sin commit mientras el release afirma otro origen

**Evidencia**

- `deploy_dglweb_image.sh:27-29` hace `git pull --ff-only` y registra el hash de `HEAD`.
- No comprueba `git status --porcelain`, ni archivos modificados ni archivos nuevos no ignorados.
- `deploy_dglweb_image.sh:39-45` permite reemplazar una etiqueta de versión existente.
- `deploy_dglweb_image.sh:51` construye con `.` como contexto, por lo que Docker incorpora cualquier
  cambio local no excluido por `.dockerignore`, aunque no pertenezca al commit mostrado en la línea 29.

**Escenario de fallo**

El VPS conserva un hotfix, una edición de diagnóstico o un archivo nuevo. `git pull --ff-only` puede
terminar correctamente si el cambio no colisiona con lo traído. El build produce entonces una imagen
distinta al commit registrado y puede sobrescribir la misma etiqueta después de una confirmación.

**Impacto arquitectónico / operativo**

La versión deja de identificar un artefacto inmutable. Un rollback por etiqueta puede volver a bytes
distintos de los probados, comparar producción con Git no explica el comportamiento y una
reconstrucción del mismo commit no reproduce la imagen desplegada.

**Mejora sugerida**

Abortar si `git status --porcelain --untracked-files=all` no está vacío. Para una garantía más fuerte,
construir desde un worktree limpio o desde un archivo generado por Git, no desde el checkout operativo.
Etiquetar además la imagen con `org.opencontainers.image.revision=$COMMIT` y guardar su digest tras el
build. Si se permite reemplazar una versión, registrar explícitamente el digest anterior y el nuevo.

**Razonamiento**

El hash solo aporta trazabilidad si los bytes del contexto pertenecen a ese hash. El control debe
comprobar esa precondición antes de construir, no confiar en que `git pull` la imponga.

No se hallaron nuevos N+1, inconsistencias transaccionales, deadlocks, carreras o cuellos de botella
de aplicación fuera de los asuntos ya pendientes. Los límites de concurrencia y memoria fueron
medidos y documentados; no se reabre una optimización genérica sin evidencia.

## Persona 6 - Experto en béisbol y sabermetría

No se encontraron findings nuevos.

Se verificaron las fórmulas de conteo y tasas, conversión de innings a outs, reglas de clasificación,
temporadas cortas, postemporada, daily standouts y la comparación bateo/pitcheo. La asimetría de outs
de corredor detectada en v13 ya no se presenta como simetría exacta: está cuantificada, documentada
como heurística con distinta cobertura y fijada por pruebas. Las líneas diarias imposibles se excluyen
y dejan diagnóstico en vez de producir valores negativos plausibles.

No se reportan como defectos las decisiones estadísticas documentadas ni los datos falsos conocidos
de la portada.

## Persona 7 - Experto en Docker, fail2ban y nginx

### OPS-01 [P2] La actualización de la IP permitida no garantiza que todos los controles converjan

**Evidencia**

- El parser de `deploy/change_nginx_allow_ip.sh:104-224` usa repetidamente `\s` en expresiones de
  `awk` (`:119`, `:128`, `:141`, `:156`, `:184`, `:198`, `:206`).
- `\s` es un operador específico de `gawk`, no POSIX; su equivalente portable es
  `[[:space:]]`: [manual oficial de GNU awk](https://www.gnu.org/software/gawk/manual/html_node/GNU-Regexp-Operators.html).
- Reproducción ejecutada: la expresión que encuentra `server {` sí coincidió en BusyBox awk, pero no
  produjo ninguna coincidencia con `mawk 1.3.4` dentro de la imagen Debian de PostgreSQL 18. Debian y
  Ubuntu suelen resolver `/usr/bin/awk` a `mawk` salvo que se instale/seleccione otra implementación.
- Si el primer tramo funciona, `deploy/change_nginx_allow_ip.sh:271-273` convierte cualquier fallo de
  `sync_access_ip.sh` en un warning y termina exitosamente.
- Ese hijo actualiza el snippet de CMS/Revive, `ignoreip` y UFW. Por tanto, éxito del padre no significa
  que los cinco consumidores hayan recibido la misma IP.

**Crash / reliability scenario**

En un host con `mawk`, el parser no encuentra el bloque HTTPS y aborta antes de ejecutar la
sincronización. En un host con `gawk`, pgAdmin y Portainer pueden actualizarse y recargar nginx, pero
un fallo posterior de fail2ban o del snippet se traga. El cron devuelve éxito y la única evidencia
queda en un log local que ningún monitor consulta.

**Impacto**

Después de rotar la IP residencial, el dueño puede perder acceso al CMS, Revive, pgAdmin o Portainer;
fail2ban puede conservar una lista blanca vieja y banear la IP nueva. Tailscale reduce el riesgo de
lockout total, pero no evita la caída operativa ni el falso éxito del cron.

**Mejora sugerida**

1. Reemplazar cada `\s` por `[[:space:]]`, o exigir y comprobar explícitamente `gawk`.
2. Hacer que el fallo del hijo se propague con exit no cero y una alerta externa; registrar warning no
   equivale a completar la operación.
3. Verificar postcondiciones: exactamente un `allow` esperado por destino, `ignoreip` efectivo y la
   regla UFW nueva antes de retirar la anterior.
4. Añadir fixtures de Portainer/pgAdmin y ejecutar el parser con `mawk` y `gawk` en CI.
5. Preferir una sola fase de validación y una sola recarga después de preparar todos los archivos, para
   reducir estados parciales.

**Razonamiento**

El contrato del job no es "actualicé dos archivos" sino "todos los puntos de acceso reconocen la
misma IP". La automatización debe fallar si no puede demostrar esa postcondición y debe usar sintaxis
compatible con el sistema que pretende reconstruir.

### Aspectos operativos revisados sin finding adicional

- Los puertos públicos de los stacks versionados están atados a `127.0.0.1`; Postgres no publica
  puerto y nginx conserva la única entrada pública.
- La imagen de Ofelia está fijada por digest y su riesgo de socket está aceptado explícitamente.
- Los stacks pasan `docker compose config --no-interpolate --quiet`.
- Los scripts Bash pasan `bash -n`; esto valida sintaxis, no semántica de awk/nginx/fail2ban.
- TLS global empieza en 1.2, los upstreams principales reutilizan conexiones y las rutas caras tienen
  límites separados.
- La configuración de fail2ban usa backend de archivo para nginx y deja deliberadamente desactivado
  el baneo por 429 debido a CGNAT. El modo de observación sigue en `TODO.md` y no se repite.

## Verificación ejecutada

- Python: **1.280 passed, 1 deselected**, cobertura total 95%.
- JavaScript: **47 passed** en 5 archivos Vitest.
- Ruff: `All checks passed!`.
- mypy strict: `Success: no issues found in 228 source files`.
- Django `check --deploy`: solo los warnings de política ya documentada, más el warning esperado por
  usar una clave corta de prueba en esa invocación.
- Docker Compose: los tres stacks de producción pasan validación sintáctica.
- Bash: todos los scripts versionados pasan `bash -n`.
- Reproducción PostgreSQL: contraseña con comilla aborta `10-dglweb.sh`.
- Reproducción awk: el patrón con `\s` funciona en BusyBox y falla en `mawk 1.3.4`.
- `git diff --check`: sin errores de whitespace al cerrar el review.

No se pudo ejecutar `nginx -t` ni `fail2ban-client -t` contra la configuración efectiva del VPS desde
este workspace. La semántica de `add_header` se contrastó con la documentación oficial de nginx y la
lista de filtros con el repositorio oficial de fail2ban.

## Exclusiones explícitas del backlog

No se reabrieron identidad individual de `IngestRun`, observación inicial de fail2ban, cron/pull y
restauración del respaldo, copias fuera del VPS, secretos en 1Password, login social, evaluación de
caché de métricas, Cloudflare, artículos semilla, metadatos de política del `Loader`, Salarios,
memoria de `compare()` ni el upgrade a treebeard 6. Todos continúan marcados como pendientes o
aplazados en `docs/TODO.md`.
