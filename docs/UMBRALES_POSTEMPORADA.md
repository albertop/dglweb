# Umbrales de las tasas en los liderazgos de postemporada

Los tableros de liderazgo de postemporada de **tasas** (bateo: AVG/OBP/SLG/OPS; pitcheo: ERA) exigen
un mínimo de turnos (PA) o entradas (IP) para que un jugador califique. Este documento explica **por
qué existen esos pisos** y **cómo se eligieron los números**. Los conteos (HR, RBI, SO de pitcheo…)
no llevan piso: no se puede liderar en un conteo que nunca se acumuló.

## El problema: octubre no tiene "qualifier"

La temporada regular tiene un estándar oficial: **3.1 PA por juego** del equipo (502 PA en 162
juegos) para bateo, **1 IP por juego** (162 IP) para pitcheo. Ese estándar existe para que una tasa
—que se distorsiona con muestras pequeñas— se rankee solo entre jugadores con suficiente volumen.

La postemporada **no tiene un estándar equivalente**, y no se le puede aplicar el mismo: ni un
octubre completo se acerca. Escalar 3.1 PA/juego a la postemporada exigiría batear en todos los
juegos de una corrida que gane la Serie Mundial en el máximo de juegos posibles — absurdo como
"mínimo". Por eso los libros de records usan **pisos fijos** para las tasas de postemporada, y hay
que fijar **dos escalas distintas** (temporada ≪ carrera) porque difieren en un orden de magnitud.

## El ejercicio: distribución real (universo dominicano, desde 1956)

Se midió la distribución real de PA (bateo) e IP (pitcheo) de postemporada, agregando el octubre
completo de cada jugador **por (jugador, temporada)** y **por carrera** — la misma agregación que
usan los tableros:

| Tabla | n | mediana | p75 | p90 | máx |
|---|---:|---:|---:|---:|---:|
| BAT PA / temporada | 521 | 13 | 32 | 53 | 89 |
| BAT PA / carrera | 208 | 22 | 78 | 131 | 493 |
| PIT IP / temporada | 317 | 4.3 | 8.0 | 13 | 28.7 |
| PIT IP / carrera | 133 | 8.7 | 19.3 | 30.7 | 96.3 |

Cuántos calificarían según el corte:

| Tablero | ≥ (elegido) | califican | alternativa estricta |
|---|---|---:|---|
| BAT temporada | **25 PA** | 161 (31%) | 40 PA → 19% |
| BAT carrera | **50 PA** | 77 (37%) | 100 PA → 17% |
| PIT temporada | **8 IP** | 82 (26%) | 10 IP → 17% |
| PIT carrera | **15 IP** | 45 (34%) | 25 IP → 18% |

## La decisión

**Criterio:** que cada tablero admita **≈⅓ de su población**. Suficientes candidatos para que "líder"
signifique ganarle a un campo real, pero cortando el cameo de pocos turnos (un 3-de-4 en un Wild Card
perdido no debe encabezar el AVG de octubre).

| Tablero | Piso | Fórmula en `_POST_QUALIFIER` |
|---|---|---|
| Bateo — temporada | **25 PA** | `PA>=25` |
| Bateo — carrera | **50 PA** | `PA>=50` |
| Pitcheo — temporada | **8 IP** | `IP>=8` |
| Pitcheo — carrera | **15 IP** | `IP>=15` |

**Por qué esta tier y no la estricta (~⅕):** los pools por temporada ya son delgadísimos (mediana
13 PA / 4.3 IP). Un piso más alto dejaría muchos años con 0–1 dominicanos calificados, volviendo el
tablero de temporada trivial o vacío. El ⅓ mantiene honesto el estándar sin vaciarlo, y son números
redondos, fáciles de explicar en el caption del perfil.

## Notas de implementación

- Los pisos son **fijos** y viven en `dglweb/stats/leaders.py` (`_POST_QUALIFIER`). **No** pasan por
  la cascada del qualifier regular (que daría 502 PA / 162 IP) — la evitan a propósito.
- El valor de la tasa se **recompone desde los totales agregados** (AVG = ΣH/ΣAB, OBP, SLG, OPS, y
  ERA = 27·ΣER/Σouts), reutilizando `career_rate.exact_value`. Nunca es un promedio de las tasas por
  ronda ("no son promedio de promedios").
- La dirección la maneja el motor: ERA es **menor-es-mejor**; el resto, mayor-es-mejor. Solo hay
  tableros "best" en postemporada (opción A, sin "peor").

## Cómo reproducir el ejercicio

```bash
docker compose exec -T -e DATABASE_URL="postgres://…@10.0.0.39:5432/dglweb" web python manage.py shell
```

```python
from collections import defaultdict
from dglweb.stats.models import BattingPost, PitchingPost
from dglweb.stats.leaders import FIRST_SEASON

def describe(vals, label, cuts):
    vals = sorted(vals); n = len(vals)
    q = lambda p: vals[min(n - 1, int(p * n))]
    print(f"\n{label} (n={n}) med={q(.5):.1f} p75={q(.75):.1f} p90={q(.9):.1f} max={vals[-1]:.1f}")
    for c in cuts:
        k = sum(1 for v in vals if v >= c)
        print(f"  >= {c}: {k} ({100 * k / n:.1f}%)")

bs, bc = defaultdict(float), defaultdict(float)
for r in BattingPost._default_manager.filter(season__gte=FIRST_SEASON).values("player_id", "season", "pa"):
    if r["pa"]:
        bs[(r["player_id"], r["season"])] += r["pa"]; bc[r["player_id"]] += r["pa"]
describe(list(bs.values()), "BAT PA/temporada", [15, 20, 25, 30, 40])
describe(list(bc.values()), "BAT PA/carrera", [30, 40, 50, 75, 100])

ps, pc = defaultdict(float), defaultdict(float)
for r in PitchingPost._default_manager.filter(season__gte=FIRST_SEASON).values("player_id", "season", "outs"):
    if r["outs"]:
        ps[(r["player_id"], r["season"])] += r["outs"]; pc[r["player_id"]] += r["outs"]
describe([v / 3 for v in ps.values()], "PIT IP/temporada", [5, 8, 10, 12, 15])
describe([v / 3 for v in pc.values()], "PIT IP/carrera", [10, 15, 20, 25, 30])
```
