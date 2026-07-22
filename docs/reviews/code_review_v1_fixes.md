# Code Review v1 — Fixes (to-do)

Fecha: 2026-07-22
Basado en `code_review_v1.md`. **Cada finding fue verificado contra el código real** antes de
entrar aquí; los que no comparto (o que no son cambios de código) están al final con su razón.

Leyenda de "cuándo":
- **AHORA** = antes de arrancar la postemporada (bugs/hygiene baratos y reales).
- **FASE 4** = requisito a implementar al construir líderes/páginas; se registra ahora.
- **POSTEMPORADA** = se resuelve como parte del próximo trabajo.
- **PROD / FASE 8** = checklist de despliegue, no cambio de hoy.

---

## AHORA — antes de postemporada

### [x] FIX-1 · Proteger `import_dgl_master --replace` del borrado en cascada (DEV-01, Alta)
`import_dgl_master.py:88` hace `Player.objects.all().delete()`; los 3 modelos de stats tienen FK
`CASCADE` a `Player` (`models.py:38, 212, 358`). Con `--replace` en Fase 4, corregir un nombre
borraría todo el backfill de batting/pitching/fielding.
- Convertir `--replace` en **upsert por `player_id`** (`bulk_create(update_conflicts=True,
  unique_fields=["player_id"], update_fields=[...])`), sin `delete()`.
- Eliminar jugadores ausentes **solo** con una bandera explícita `--delete-missing`, y que esa
  bandera **aborte si hay filas en `mlb_batting`/`mlb_pitching`/`mlb_fielding`** para los
  jugadores a borrar (mensaje claro), salvo un `--force` adicional.
- Tests: upsert no borra stats; `--delete-missing` sin stats OK; con stats aborta.
- **Decisión del dueño:** ¿mantengo `--replace` como alias de upsert, o renombro el flag?

### [x] FIX-2 · Validar todas las filas del extracto maestro, no solo la primera (DEV-02, Media)
`import_dgl_master.py:77-78` valida columnas usando solo `records[0]`.
- Recorrer todas las filas: reportar índice + columnas faltantes/inesperadas.
- Detectar `player_id` duplicados y unique-IDs duplicados **antes** de `bulk_create` (error de
  dominio claro, no `IntegrityError` crudo).
- Test: fila N con columna extra/faltante → error con el índice; `player_id` duplicado → error claro.

### [x] FIX-3 · Acotar `IngestRun.detail` (DEV-03, Baja)
`runlog.py:60` guarda `str(exc) + traceback.format_exc()` completo.
- Mantener el traceback (es útil para diagnosticar scrapes), pero **truncar** a un límite (p. ej.
  8–16 KB) con marcador de "…(truncado)".
- Test: un traceback largo se persiste truncado.
- *(No implemento sanitización por `DEBUG`: el backoffice es solo-superusuario e infra propia.)*

### [x] FIX-4 · Tests de comando para `parity_pitching` y `parity_fielding` (DEV-04, Media)
Confirmado: `test_parity_command.py` solo cubre `parity_batting` (los otros 0%).
- Replicar el patrón: OK, mismatch (falla), archivo faltante, master vacía, y —para fielding—
  filas sobrantes/faltantes por la llave `(player, season, team, pos)`.
- Opcional: factorizar el cuerpo común de los 3 comandos de paridad para reducir duplicación.

---

## AHORA (recomendado) — guardarraíl pre-líderes

### [x] FIX-5 · Convención de entradas: nunca sumar `ip`/`innings` beisboleros (SAB-01, Alta)
`ip` (pitching) e `innings` (fielding) están en notación beisbolera (`46.2` = 46⅔). Sumarlos como
decimales da resultados sabermétricamente falsos. **Hoy no hay ninguna agregación**, así que es un
guardarraíl, no un bug activo. Estado real:
- **Pitching ya tiene `outs`** (columna canónica, sumable) → las agregaciones deben usar `outs`.
- **Fielding solo tiene `innings`** → agregar un `innings_outs` (convertir `"111.1"` → `111*3+1`
  al cargar) para poder calificar/rankear por entradas defensivas.
- Documentar la regla en el docstring de los modelos: `ip`/`innings` son de **display/paridad**,
  no agregables; usar `outs`/`innings_outs`.
- Tests: `outs` suma correcto; `innings_outs` = conversión correcta; guard/lint que evite `Sum("ip")`.
- **Decisión del dueño:** ¿agrego `innings_outs` a fielding ahora, o lo dejo para Fase 4?

### [x] FIX-6 · Querysets canónicos de totales (SAB-02, Alta — de Fase 4, pero construible ya)
Batting/pitching guardan fila por-equipo + `XXX`; fielding guarda por-equipo + `XXX` por posición.
Sumar todas doble-cuenta a los jugadores cambiados (Manny, Soto, Cruz…). Los querysets son puros
y testeables **sin UI**, así que conviene tenerlos listos antes de que exista el primer líder:
- `Batting.objects.season_totals()` / `Pitching.objects.season_totals()`: por `(player, season)`,
  la fila `team="XXX"` si existe, si no la única fila.
- `Fielding.objects.position_totals()`: por `(player, season, pos)`, la fila `team="XXX"` si
  existe, si no la única.
- Tests de agregación con un jugador cambiado y uno no cambiado (sin doble conteo).

---

## POSTEMPORADA — se resuelve en el próximo trabajo

### [ ] FIX-7 · Parametrizar `gameType` / competición (SAB-05, Media)
`_download.py:76` y `fielding_source.py:61` hardcodean `gameType=[R]`, `sportId=1`; los `update_*`
usan `timezone.now().year`.
- Extender `SportConfig` (o una config de competición) con `game_type` y `sport_id`; la
  postemporada usa `gameType=[P]` y escribe en tablas `*Post`.
- Reemplazar "año actual" por una función probada (`current_season()` / competición activa) —
  necesaria para LIDOM (cruza años) y Spring; tests con fechas de ene/mar/jul/oct/nov.
- *(Esto se hace naturalmente al portar la postemporada; queda registrado como parte de ese diseño.)*

---

## FASE 4 — requisitos registrados (implementar al construir líderes/páginas)

### [ ] FIX-8 · Umbral de apariciones en el modelo de líderes (SAB-03, Alta)
Ya en `BUILD_PLAN.md`. Reglas de calificación por deporte/métrica (PA bateo; IP/BF/G/GS pitcheo;
innings/chances fildeo), **calculadas contra los juegos del equipo esa temporada** (no fijo en 502),
configurables o declarativas, con tests para 2020, Ligas Negras y era antigua.

### [ ] FIX-9 · Nota de "cobertura histórica limitada" en páginas/líderes (SAB-06, Media)
Ya en `BUILD_PLAN.md` (los 7 de Ligas Negras). Indicador por jugador/temporada/liga que las
páginas de jugador y líderes muestren cuando una carrera incluya ligas con cobertura incompleta;
permitir incluir/excluir esas eras en los líderes según la métrica.

---

## PROD / FASE 8 — checklist de despliegue (no cambio de hoy)

### [ ] FIX-10 · Hardening del scheduler en prod (DEV-05, Media)
El `docker-compose.yml` local monta `/var/run/docker.sock`. En prod: fijar versión de imagen de
Ofelia, evaluar `job-run` con permisos mínimos o un cron externo sin socket, y documentar el
modelo de permisos. (El compose actual es explícitamente local/dev.)

### [ ] FIX-11 · Vendorizar assets / SRI / CSP (DEV-06, Baja)
`base.html:10-11, 67` cargan Google Fonts y Bootstrap desde CDN sin `integrity`. Ya está en
`docs/TODO.md`. Self-host + CSP antes del big-bang.

---

## Revisados y NO accionados (con razón)

- **SAB-04 (fórmula de BAA):** la fórmula `H/(BF−BB−HBP−SH−SF−CI)` es la de `mlbstats` que usa la
  tabla de origen y está **verificada a 0 diferencias en 60 804 filas**. Cambiarla a `H/ab`
  rompería la paridad. Único ajuste: una línea de doc aclarando que es la definición legacy.
  → convertido en sub-tarea de doc dentro de FIX-5 si se quiere; no es un cambio de lógica.
