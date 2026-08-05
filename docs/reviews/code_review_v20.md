# Code Review v20

Fecha: 2026-08-04

Alcance: verificación posterior a las correcciones sobre efemérides, participantes de gestas colectivas y el widget de portada "Un día como hoy". Antes de revisar se leyeron los `.md` bajo `docs/`, incluyendo `TODO.md`, `EFEMERIDES.md`, `CODING_STANDARDS.md`, `DATOS_DE_APOYO.md`, `MOTOR_DATOS_APOYO.md`, `RENDIMIENTO.md` y reviews previos.

## Resumen ejecutivo

No encontré findings accionables nuevos en el código revisado. Los issues que motivaron las correcciones quedaron cubiertos satisfactoriamente:

- Las gestas colectivas ahora llegan al perfil de todos sus participantes mediante `participantes` y búsqueda con espacios de guarda.
- El contrato del CSV, loader, modelo, migración y detectores SQL está alineado con la nueva columna.
- El widget "Un día como hoy" está conectado a portada, tiene template, CSS, JS, cache bust de CSS y cobertura de tests.
- La decisión de excluir cumpleaños del perfil pero permitirlos en portada está documentada y probada.

## Persona 1: Python Principal Developer

Sin findings accionables.

Validé que `dglweb.stats.efemerides.del_dia()` mantiene una superficie pequeña, con consultas acotadas por índice, `in_bulk()` para evitar N+1, dataclass inmutable para el contrato hacia la plantilla y tests sobre los bordes principales: día vacío, límite de tarjetas, jugadores ocultos, pares impares y duración mínima/máxima. También pasó `ruff` y `mypy` sobre los archivos Python nuevos/relevantes.

Riesgo residual: el widget se apoya en un diccionario genérico `dict[str, Any]` para el contexto de plantilla. No lo marco como finding porque es consistente con el estilo Django del proyecto y está cubierto por tests de render, pero si este módulo crece convendría considerar un `TypedDict` o dataclass de contexto.

## Persona 2: QA / Reliability Engineer

Sin findings accionables.

La suite específica terminó limpia en la corrida final:

```text
46 passed in 52.00s
```

Nota de verificación: una corrida intermedia falló porque lancé dos `pytest` de Django en paralelo contra la misma base `test_dglweb`; al recrear la base y correr serialmente, el resultado quedó limpio. No lo considero bug del cambio, sino ruido operativo de la verificación.

Riesgo residual: no vi una prueba de navegador real para la rotación JavaScript del widget. Hay cobertura del HTML y del cálculo de tiempos, pero no una prueba end-to-end que pulse los puntos o valide `prefers-reduced-motion` en browser. Es un gap aceptable para este cambio, no un blocker.

## Persona 3: Frontend Engineer

Sin findings accionables.

La integración visual existe y está completa a nivel de artefactos: `templates/home.html` incluye el widget, `templates/base.html` carga `static/js/dia_como_hoy.js`, `static/css/site.css` define los estados `.dgl-dch-par`/`.es-visible`, y el JS maneja rotación, pausa por foco/hover, `visibilitychange`, puntos de navegación y `prefers-reduced-motion`.

Riesgo residual: faltó inspección visual con navegador/captura. El CSS parece razonable y evita saltos de altura manteniendo los pares en la misma celda de grid, pero un screenshot responsive sería el siguiente nivel de confianza antes de publicar.

## Persona 4: Security Engineer

Sin findings accionables.

No observé entrada de usuario nueva, SQL dinámico desde request, secretos, deserialización insegura ni exposición adicional de endpoints. El widget renderiza datos internos ya generados por el pipeline estático y Django escapa el contenido de plantilla por defecto.

## Persona 5: Backend Architect

Sin findings accionables.

La decisión arquitectónica de no duplicar filas colectivas en el calendario y usar `participantes` para perfiles está bien contenida: calendario conserva una fila por efeméride, perfil recupera las colectivas por ID, y el loader normaliza los espacios de guarda para evitar falsos positivos por substring.

La migración `0034_efemeride_participantes` agrega un `CharField` no nulo con default temporal seguro para tabla poblada; `sqlmigrate` previo confirmó un `ADD COLUMN ... DEFAULT '' NOT NULL` seguido por `DROP DEFAULT`.

## Persona 6: Experto en beisbol y sabermetría

Sin findings accionables.

La corrección respeta el modelo baseball/sabermétrico documentado:

- Una gesta colectiva debe pertenecer a todos los participantes en el perfil, sin multiplicarse en el calendario.
- Las frases históricas se leen desde `nameList`/CSV y no desde `player.full_name`, lo cual conserva la autoridad editorial del archivo.
- Cumpleaños quedan fuera del perfil porque son afirmaciones relativas al presente, pero entran en portada porque el widget es explícitamente "hoy".
- Las deshonras viajan marcadas por `signo < 0` y no se mezclan como hazañas.

No detecté falso entendimiento de estadísticas ni uso incorrecto de conceptos de béisbol en lo revisado.

## Persona 7: Docker / fail2ban / nginx

Sin findings accionables.

No hubo cambios sustantivos en Docker, nginx o fail2ban dentro del alcance revisado. `docker-compose config --quiet` había pasado en la verificación previa de este ciclo, y los comandos de test/lint ejecutaron correctamente dentro del servicio `web` después de usar la base de prueba de forma serial.

## Verificaciones ejecutadas

```text
docker-compose run --rm --no-deps web ruff check dglweb/stats/efemerides.py dglweb/core/views.py tests/test_dia_como_hoy.py
All checks passed!

docker-compose run --rm --no-deps web mypy dglweb/stats/efemerides.py dglweb/core/views.py tests/test_dia_como_hoy.py
Success: no issues found in 3 source files

docker-compose run --rm --no-deps web python manage.py check
System check identified no issues (4 silenced).

docker-compose run --rm web pytest --create-db tests/test_dia_como_hoy.py tests/test_efemerides_loader.py tests/test_efemerides_tab.py tests/test_efemerides_csv_real.py -q
46 passed in 52.00s

git diff --check
Sin errores; solo warnings existentes de normalización CRLF/LF en archivos tocados.
```

## Conclusión

Las correcciones revisadas quedaron satisfactorias. No recomiendo bloquear el merge por ninguno de los puntos observados; lo único que dejaría como mejora futura es una prueba visual/browser del widget de portada para cubrir la rotación y los estados responsive desde el navegador real.
