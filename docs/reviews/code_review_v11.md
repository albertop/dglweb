# Code Review v11

Fecha: 2026-07-29

Alcance: revision del proyecto despues de leer los `.md` bajo `docs/`, incluyendo `TODO.md`, guias de autoridad, rendimiento, despliegue, jugadores deshabilitados y reviews anteriores.

Reglas aplicadas:

- No se revisaron como findings los placeholders/datos falsos conocidos de la portada.
- No se repiten issues ya aceptados, corregidos o pendientes en `docs/TODO.md`.
- Si dos personas detectaban el mismo problema, se reporta una sola vez en la persona donde aporta mas valor.
- No se modifico codigo fuente; este archivo es el unico entregable.

Escala: P1 bloqueante/alta urgencia, P2 alta, P3 media, P4 baja.

## Persona 1 - Python Principal Developer

No encontre un hallazgo nuevo y unico para esta persona despues del filtro contra `TODO.md` y la deduplicacion.

La preocupacion mas cercana a calidad/backend es el contrato de visibilidad de jugadores, pero queda reportada una sola vez bajo QA/Reliability porque el riesgo principal es inconsistencia publica y fuga funcional de datos deshabilitados.

## Persona 2 - QA / Reliability Engineer

### QA-01 [P2] Widgets publicos pueden mostrar jugadores deshabilitados

**Evidencia**

- `docs/JUGADORES_DESHABILITADOS.md` define la regla operativa: cuando la consulta arranca desde tablas de estadisticas o derivados, debe pasar por `only_visible()` o filtrar jugadores ocultos antes de publicar.
- `dglweb/stats/daily.py:431`, `dglweb/stats/daily.py:438` y `dglweb/stats/daily.py:444` consultan `DailyStandout` directamente para construir la portada, con `select_related("player")`, pero sin `player__hidden=False`.
- `dglweb/stats/mlb_leaders.py:216` arma el widget de lideres MLB desde `MlbLeader.objects.filter(metric__visible_en_widget_lideres=True)` sin filtrar jugadores ocultos.
- `dglweb/stats/roster_moves.py:309` arma movimientos publicables con `RosterMove.objects.filter(player__isnull=False).exclude(texto="")`, tambien sin excluir `player__hidden=True`.
- `tests/test_player_visibility.py` cubre perfiles, buscador/listados, leaderboards, career totals y rebuilds, pero no cubre `DailyStandout`, `MlbLeader` ni `RosterMove` como superficies publicas.

**Riesgo**

Un jugador deshabilitado puede desaparecer correctamente del perfil, buscador y leaderboards, pero seguir apareciendo en widgets de portada, lideres MLB o cintillo de movimientos si ya existe en snapshots derivados. Eso rompe el contrato de producto de "deshabilitado", genera inconsistencias visibles y puede revivir datos que el admin quiso ocultar.

**Mejora sugerida**

Aplicar el filtro de visibilidad en los puntos de lectura publica de esas tablas derivadas, por ejemplo con `exclude(player__hidden=True)` o un helper compartido equivalente a `only_visible()` para querysets que tienen FK `player`. Mantendria la carga historica intacta, porque los docs dicen que el dato crudo debe seguir entrando, pero la presentacion publica obedeceria el contrato.

Agregar pruebas enfocadas:

- Un `DailyStandout` de jugador oculto no aparece en `daily.portada()`.
- Un `MlbLeader` de jugador oculto no aparece en `mlb_leaders.portada()`.
- Un `RosterMove` de jugador oculto no aparece en `roster_moves.portada()`.

**Razonamiento**

El bug esta en la frontera publicacion/visibilidad, no en ingestion. La solucion debe preservar los snapshots y filtrar al publicar, asi el backoffice conserva trazabilidad y el sitio publico mantiene una regla consistente.

## Persona 3 - Frontend Engineer

### FE-01 [P3] El autocomplete puede reabrirse con sugerencias viejas despues de cerrar o limpiar la busqueda

**Evidencia**

- `static/js/buscador.js:58` cierra la lista limpiando DOM, `aria-expanded` y `aria-activedescendant`, pero no invalida la solicitud en vuelo.
- `static/js/buscador.js:150` llama `cerrar()` cuando el texto queda por debajo del minimo.
- `static/js/buscador.js:156` guarda un token en `enVuelo`, y `static/js/buscador.js:157` inicia el `fetch`.
- La respuesta pinta resultados si `enVuelo === mio`, pero si el usuario limpia la caja o presiona Escape antes de que llegue la respuesta, `enVuelo` sigue apuntando al token viejo.
- `tests/js/buscador.test.js:155` cubre Escape, pero no una respuesta tardia despues de cerrar la lista.

**Riesgo**

Un usuario puede escribir una busqueda valida, borrar el texto hasta quedar bajo el minimo o cerrar con Escape, y luego ver reaparecer sugerencias de la consulta anterior cuando responde el `fetch`. Es una ruta UX rota y tambien deja el estado ARIA inconsistente: la caja puede volver a `aria-expanded="true"` aunque la intencion actual sea cerrada.

**Mejora sugerida**

Invalidar solicitudes pendientes dentro de `cerrar()`, por ejemplo con `enVuelo = null`, o cambiar a un contador monotono que tambien compare el texto vigente contra el texto consultado. Como mejora adicional, usar `AbortController` para cancelar el request anterior cuando se dispara una nueva busqueda o se cierra la lista.

Agregar un test con promesa diferida:

1. Escribir una consulta que dispara `fetch`.
2. Antes de resolver la promesa, limpiar el input o enviar Escape.
3. Resolver la respuesta vieja.
4. Afirmar que la lista sigue oculta y no se pintan resultados obsoletos.

**Razonamiento**

El debounce reduce llamadas, pero no elimina carreras de red. La fuente de verdad del widget debe ser la busqueda actual, no la ultima respuesta que llegue.

## Persona 4 - Security Engineer

No encontre un hallazgo OWASP nuevo y unico que no estuviera ya cubierto por `TODO.md` o por findings anteriores.

Puntos revisados y filtrados:

- Rate limiting, HSTS `includeSubDomains` y fail2ban ya estan documentados como pendientes o decisiones de despliegue en `docs/TODO.md` y `docs/RENDIMIENTO.md`.
- `/ready` con detalles internos ya fue corregido/aceptado en el backlog.
- El buscador publico ya limita largo de `q` y evita interpolar HTML en sugerencias.
- Uploads CSV de datos de apoyo pasan por admin, CSRF, validacion de extension/tamano, decodificacion controlada y revalidacion antes de aplicar.
- El adserver esta aislado en subdominio, usa iframe por decision de CSP y esta desactivado por defecto via `ADSERVER_URL`.

## Persona 5 - Backend Architect

### ARCH-01 [P3] Canonical, Open Graph, robots y sitemap dependen del host recibido aunque nginx sirve apex y www

**Evidencia**

- `deploy/nginx-dglweb.conf:22` sirve `dominicanosengrandesligas.com` y `www.dominicanosengrandesligas.com` en el mismo bloque HTTPS.
- `deploy/nginx-dglweb.conf:147` y `deploy/nginx-dglweb.conf:151` redirigen HTTP a HTTPS preservando `$host`, asi que `www` sigue siendo `www` en HTTPS.
- `templates/base.html:23` arma el canonical con `request.scheme`, `request.get_host` y `request.path`.
- `templates/base.html:36` y `templates/base.html:39` hacen lo mismo para `og:url` y `og:image`.
- `dglweb/core/views.py:157` genera `robots.txt` con `request.get_host()`.
- `dglweb/core/sitemaps.py:30`, `dglweb/core/sitemaps.py:48` y `dglweb/core/sitemaps.py:66` fijan `https`, pero el host efectivo del sitemap queda atado al host de la request/site.

**Riesgo**

Si el apex y `www` responden 200, cada host se declara a si mismo canonical. Eso puede partir senales SEO, generar duplicados indexables y producir metadatos sociales distintos para la misma URL logica. No es un bug de seguridad, pero si una inconsistencia de arquitectura de publicacion.

**Mejora sugerida**

Elegir un host canonico - por ejemplo `dominicanosengrandesligas.com` - y hacerlo cumplir de forma unica:

- Redirigir `www` a apex en nginx tanto para HTTP como para HTTPS, o
- Introducir una setting `PUBLIC_SITE_URL`/`CANONICAL_HOST` y usarla para canonical, Open Graph, robots y sitemap.

Agregar pruebas con `HTTP_HOST="www.dominicanosengrandesligas.com"` para fijar la decision: o se espera redirect a apex, o se espera que canonical/robots/sitemap emitan siempre el host canonico.

**Razonamiento**

El sitio ya esta cuidando sitemap, robots y metadatos. La pieza que falta es que todos esos productores compartan una autoridad unica de host; dejarlo en `request.get_host()` hace que proxies, aliases o crawlers dicten la identidad canonica.

## Persona 6 - Experto en beisbol y sabermetria

No encontre un hallazgo sabermetrico nuevo y unico despues de leer los documentos de autoridad, umbrales, datos de apoyo, motor de apoyo y reviews anteriores.

Notas de alcance:

- No se reportan los placeholders/datos falsos de portada porque fueron declarados known issue por el owner.
- No se repiten mejoras futuras ya documentadas: exactitud de WAR/OPS+/ERA+, Retrosheet batted-ball holes, umbrales de conteo, equivalencias de ligas menores, postseason y refinamientos del motor de datos de apoyo.
- El posible impacto sabermetrico de mostrar un jugador oculto en widgets publicos queda deduplicado en `QA-01`, porque el problema raiz es el contrato de visibilidad.

