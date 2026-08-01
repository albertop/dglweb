# Code Review v15

Fecha: 2026-08-01

Alcance: revisión del estado actual del proyecto después de leer los `.md` bajo `docs/`, incluyendo
`TODO.md`, documentos de operación/despliegue, sabermetría, seguridad, reviews anteriores y sus
resoluciones. No se modificó código fuente; este archivo es el único entregable.

Reglas aplicadas:

- No se repiten asuntos que ya están en `docs/TODO.md` como pendientes.
- Si varias personas detectan el mismo problema, aparece una sola vez bajo la persona que mejor
  representa el riesgo principal.
- No se reabren decisiones conscientes ya documentadas, como dejar fuera las Ligas Negras de ciertos
  liderazgos o mantener `nginx-limit-req` de fail2ban apagado por CGNAT.
- Escala: P1 bloqueante, P2 alta, P3 media, P4 baja.

## Resumen de findings

| Prioridad | ID | Persona | Finding |
|---|---|---|---|
| P2 | QA-01 | QA / Reliability Engineer | La nueva ventana de 14 días puede volver a publicar jugadores deshabilitados. |
| P3 | SAB-01 | Experto en béisbol y sabermetría | El umbral de pitcheo de la ventana mezcla la regla `IP por juego` con `G` como apariciones del lanzador. |
| P4 | OPS-01 | Docker / fail2ban / nginx | Hay deriva documental en la instalación de fail2ban: un path viejo y un checklist pendiente ya resuelto. |

No se encontraron findings P1.

## Persona 1 - Python Principal Developer

No encontré un finding nuevo independiente de calidad Python. El código mantiene tipado estricto,
funciones pequeñas en las rutas revisadas, uso consistente de helpers locales y separación razonable
entre cálculo, persistencia y presentación.

La mejora de `ventana.portada()` que se propone en QA-01 también es Pythonic: extraer un helper
`_publicables()` como en `daily.py` evita duplicar una regla de visibilidad que ya existe en
`dglweb.players.visibility.only_visible`.

## Persona 2 - QA / Reliability Engineer

### QA-01 [P2] La ventana de 14 días no respeta el contrato de jugadores deshabilitados

**Evidencia**

- `dglweb/players/models.py:106` promete que un jugador deshabilitado desaparece del sitio.
- `tests/test_visibilidad_widgets.py:97`, `:127` y `:151` prueban esa regla para destacados del día,
  líderes MLB y cintillo, pero no para `WindowStandout`.
- `dglweb/stats/daily.py:715` centraliza la lectura pública de destacados con `only_visible(...)`.
- `dglweb/stats/ventana.py:460` lee `WindowStandout.objects.select_related("player")` directamente y
  no excluye `player__hidden=True`.
- `templates/home.html:48-51` publica esas filas en “Quemando la liga” y “Pasando trabajo”.

**Bug / edge case**

Si un jugador se deshabilita después de que `build_window_standouts` guardó la foto, la siguiente
petición a la portada todavía puede mostrarlo en las rachas. Es el mismo tipo de fallo que ya se
corrigió para otros widgets, pero la nueva superficie no entró en esa suite.

**Impacto**

User-facing y de contrato: una baja marcada como “desaparece del sitio” puede reaparecer justo en la
portada. Si la baja responde a una corrección editorial, legal o de privacidad, el fallo es visible y
difícil de explicar.

**Mejora sugerida**

Crear en `ventana.py` un helper equivalente a `_publicables()`:

```python
from dglweb.players.visibility import only_visible

def _publicables():
    return only_visible(WindowStandout.objects.all())
```

Usarlo en `portada()` antes del `select_related()` y añadir tests a `tests/test_visibilidad_widgets.py`
para estos dos casos:

- Con un visible y un oculto, solo sale el visible.
- Si el único que cruza el corte está oculto, el widget no se dibuja.

**Razonamiento**

Filtrar al leer conserva la decisión ya usada en destacados, líderes MLB y roster moves: el dato crudo
sigue guardado, y reactivar a un jugador lo devuelve de inmediato sin esperar otro rebuild. Lo
importante es que todas las superficies públicas obedezcan la misma regla.

## Persona 3 - Frontend Engineer

No encontré un flujo frontend roto nuevo. La racha nueva usa una plantilla compartida, IDs distintos
por panel, botón delegado con `aria-expanded`, y CSS que solo muestra el despliegue en móvil.

Riesgo residual: `static/js/site.js` no tiene suite JS propia para `data-desplegar` ni para el tooltip
de líneas truncadas. No lo subo como finding separado porque hoy no vi un bug de UX reproducible, pero
conviene cubrirlo cuando se toque esa mecánica.

## Persona 4 - Security Engineer

No encontré un finding OWASP nuevo. Los puntos de v14 que afectaban recuperación/seguridad quedaron
corregidos en el estado actual: Postgres ya no interpola la contraseña como SQL, `/ready` recorta el
detalle público, Revive repite HSTS por `location`, y la configuración de fail2ban ya incluye filtro,
jail y baseline.

QA-01 tiene un ángulo de privacidad, pero se reporta una sola vez como contrato de publicación.

## Persona 5 - Backend Architect

No encontré un finding nuevo independiente de arquitectura. El job `build_window_standouts` está
incluido en `dglweb/stats/jobs.py:63`, por lo que el semáforo horario ya lo vigila; la tabla
`WindowStandout` es una foto reemplazada transaccionalmente y no introduce histórico ambiguo.

La recomendación de QA-01 debe aplicarse en la capa de lectura pública, no en la ingesta, para mantener
la arquitectura reversible de jugadores deshabilitados.

## Persona 6 - Experto en béisbol y sabermetría

### SAB-01 [P3] El umbral de pitcheo usa apariciones como si fueran juegos del calendario

**Evidencia**

- `dglweb/stats/ventana.py:79-84` documenta `IP_POR_JUEGO = 1.0` como derivado del qualifier de
  temporada completa dividido entre 162.
- `dglweb/stats/ventana.py:278-291` calcula el denominador con el p90 de `G` en los splits.
- En bateo, `G` se acerca a juegos del equipo/jugador; en pitcheo, `G` es apariciones del lanzador.
- `dglweb/stats/ventana.py:321-342` aplica `("pitching", "IP", IP_POR_JUEGO, ...)`, así que el corte
  termina siendo `1 IP x p90 de apariciones`, no `1 IP x juegos del equipo en la ventana`.
- El propio modelo histórico advierte el tipo de problema: `dglweb/stats/models.py:276-278` dice que
  `ip` es notación de béisbol y que para sumar se use outs.

**False assumption**

La frase “IP por juego” viene de la regla oficial de ERA/IP, que se basa en juegos del equipo. En la
implementación de la ventana, el “juego” del lanzador es una aparición. Eso baja mucho el listón para
pitcheo en una ventana de dos semanas: la documentación del propio módulo dice que el p90 medido fue
6,0 IP para pitcheo, mientras un equipo suele jugar alrededor de 12 partidos en 14 días.

Eso puede ser una decisión válida si el widget quiere incluir relevistas, pero entonces no es el mismo
criterio conceptual que el qualifier de temporada.

**Impacto sabermétrico**

El widget puede presentar como “calificado” a lanzadores con carga de relevo, no a lanzadores que
cumplen el ritmo de un inning por juego del equipo. En “Quemando/Pasando” eso cambia la población:
relievers de cinco o seis entradas en la quincena compiten contra abridores y bateadores que sí pasan
un umbral de volumen más cercano al calendario.

**Mejora sugerida**

Elegir explícitamente una de estas dos políticas y codificarla con nombre:

- Si se quiere el criterio oficial/prorrateado: basar pitcheo en juegos de equipo dentro de la ventana
  o en un calendario equivalente, y guardar oportunidades como `outsPitched / 3`.
- Si se quiere una ventana reliever-friendly: documentarlo como `IP por aparición p90`, no como
  derivación directa del qualifier de temporada, y añadir pruebas que congelen ese contrato.

En ambos casos, para el valor guardado en `oportunidades`, preferir `outsPitched / 3` sobre `IP`
parseado con `float()`, porque `6.2` en béisbol es 6 2/3, no 6.2.

**Razonamiento**

El problema no es que el corte sea generoso o estricto; es que el nombre estadístico y la semántica
del campo no dicen la misma cosa. En un sitio de sabermetría, ese tipo de contrato debe quedar
explícito para que el lector y el futuro código sepan qué población están comparando.

## Persona 7 - Docker / fail2ban / nginx

### OPS-01 [P4] La documentación de fail2ban quedó con un path viejo y un checklist desactualizado

**Evidencia**

- `docs/RESTAURAR.md:186-188` instala correctamente:
  `deploy/fail2ban/filter.d/nginx-404-scan.conf`, `deploy/fail2ban/jail.local` y
  `deploy/fail2ban/jail.d/nginx.local`.
- `deploy/fail2ban/jail.d/nginx.local:3` todavía instruye:
  `sudo cp deploy/fail2ban-nginx.local /etc/fail2ban/jail.d/nginx.local`, un path que ya no existe.
- `docs/RENDIMIENTO.md:293` conserva como pendiente “fail2ban sobre los registros de nginx”, aunque
  `docs/TODO.md:185-209` y `deploy/fail2ban/` muestran que esa parte ya quedó versionada; lo pendiente
  real es observar unos días lo que captura.

**Escenario de fallo**

Durante una restauración o hardening manual, alguien sigue el comentario del archivo de jail y copia
una ruta inexistente. O lee `RENDIMIENTO.md` y cree que fail2ban todavía no está montado, duplicando
trabajo o cambiando una configuración que ya fue afinada.

**Impacto operativo**

Bajo: no rompe el stack actual. Pero sí aumenta fricción en el peor momento, que es una recuperación
desde cero o una rotación de servidor.

**Mejora sugerida**

Actualizar el comentario de `deploy/fail2ban/jail.d/nginx.local` para usar el path actual y cambiar
`docs/RENDIMIENTO.md` de “pendiente fail2ban sobre nginx” a “pendiente observar `nginx-404-scan` en
modo aviso”. Mantener `docs/RESTAURAR.md` como fuente operativa principal, porque ahí el comando ya
está correcto.

**Razonamiento**

La configuración de seguridad ya está versionada; el riesgo restante es que las instrucciones de
recuperación no sean convergentes. En infraestructura, un path viejo en un comentario puede costar más
que un error de sintaxis, porque se descubre cuando alguien lo necesita.

## Verificación ejecutada

- Lectura de `.md` bajo `docs/`, con filtro explícito contra `docs/TODO.md`.
- `docker compose run --rm web pytest tests/test_ventana.py tests/test_visibilidad_widgets.py`: **29 passed**.
- `docker compose run --rm --no-deps web ruff check .`: **All checks passed**.
- `docker compose run --rm --no-deps web mypy .`: **Success, 233 source files**.
- `docker compose -f deploy/stack.yml config -q`: OK con variables dummy.
- `docker compose -f deploy/postgres/stack.yml config -q`: OK con variables dummy.
- `docker compose -f deploy/adserver/stack.yml config -q`: OK.
- `git diff --check`: sin errores.

No pude ejecutar `npm test` directamente en Windows porque `npm` no está instalado en el PATH de esta
máquina. No usé `nginx -t` ni `fail2ban-client -t` contra el VPS real desde este workspace.
