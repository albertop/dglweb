# Umbrales de calificación de los coeficientes (de forma y de contacto)

Los coeficientes de batazo (GB%, FB%, LD%, PU%, GB/FB) y de swing (Contact%, Whiff%) son **tasas**, así
que sus tableros de líderes exigen un mínimo para calificar. Este documento explica **de dónde salen los
números**, sobre todo el de **carrera** (de por vida), que antes estaba mal calibrado.

## El problema

Los coeficientes no se calculan sobre PA/IP sino sobre su **propia cobertura**: las de forma sobre las
**bolas en juego** (`BALLS_IN_PLAY`), las de contacto sobre los **swings** (`TOTAL_SWINGS`). Gatearlos con
PA/IP dejaría que una era sin clasificación de batazo encabece el tablero (Felipe Alou lideró PU% con una
sola bola en juego en 7,908 PA), así que el umbral es sobre la cobertura misma.

El umbral de **temporada** siempre fue `BIP≥400` / `swings≥1000` — razonable, es ~una campaña calificada.
El error: ese mismo 400/1000 se aplicó también a la **carrera**, donde es trivialmente bajo. Una carrera
tiene miles de bolas en juego, así que `BIP≥400` de carrera admitía a cualquiera con ~una temporada
(203 de 609 dominicanos, 33 %) — no es un tablero de líderes de por vida, es casi todo el mundo.

## El criterio

Anclar el umbral de carrera al **estándar del sitio**: los demás tableros de tasa de carrera usan
**PA≥3000** (bateo) e **IP≥1000** (pitcheo). El umbral de coeficientes de carrera debe admitir el mismo
campo de "peloteros de carrera", traducido a BIP/swings.

## El estudio (dominicanos, temporadas 1989+, que es cuando existe el dato)

**Distribución del BIP de carrera (bateo, n=609 con dato):** muy sesgada — mediana 106, p75 781, p90 2,595.

| Umbral BIP carrera | Califican |
|---|---|
| 400 (antes) | 203 (33 %) — demasiado |
| 1,000 | 137 (22 %) |
| 1,500 | 111 (18 %) |
| **2,000** | **85 (14 %)** |
| 3,000 | 55 (9 %) |

**Anclaje a PA≥3000 (bateo):** los 74 dominicanos con PA(1989+)≥3000 tienen **BIP mínimo 1,926**, ratio
medio BIP/PA = 0.73 → 3000 PA ≈ **~2,000 BIP**. Y **swings mínimo 4,951** → ≈ **~5,000 swings**.

**Anclaje a IP≥1000 (pitcheo):** un lanzador enfrenta muchas más bolas en juego por carrera. Los 29
dominicanos con IP(1989+)≥1000 tienen **BIP mínimo 2,622** (~3,000) y **swings mínimo 7,742** (~8,000). Por
eso el pitcheo lleva un piso más alto que el bateo — con 2,000 calificaría casi cualquier lanzador de
carrera.

## Los umbrales

| Qualifier | Temporada (sin cambio) | **Carrera** |
|---|---|---|
| Bateo — coef. de forma (GB%/FB%/LD%/PU%/GB-FB) | `BIP≥400` | **`BIP≥2000`** |
| Bateo — Contact% / Whiff% | `swings≥1000` | **`swings≥5000`** |
| Pitcheo — coef. de forma | `BIP≥400` | **`BIP≥3000`** |
| Pitcheo — Contact% / Whiff% | `swings≥1000` | **`swings≥8000`** |

Campo resultante de carrera: ~85 bateadores y ~27 lanzadores (comparable a los 74 con PA≥3000 y 29 con
IP≥1000). Números redondos, anclados al estándar que ya usa el sitio.

## Implementación

- Viven en `seed_metrics._OWN_QUALIFIER` como `(temporada, carrera)` por `(grupo, columna)`. El motor de
  líderes recompone la tasa de carrera desde los componentes sumados y aplica `qualifier_career`.
- Editables en el Backoffice (`Metric.qualifier_season` / `qualifier_career`).
- Cambiar el umbral de carrera **cambia quién califica**, así que hay que reconstruir `dgl_leader`
  (`build_leaders`) después de tocar la BD.

## Cómo reproducir

```bash
docker compose run --rm --no-deps -e DATABASE_URL="postgres://…@10.0.0.39:5432/dglweb" web python manage.py shell
```

```python
from collections import defaultdict
from dglweb.stats.models import Batting  # o Pitching
pa = defaultdict(float); bip = defaultdict(float); sw = defaultdict(float)
for r in Batting.objects.season_totals().filter(season__gte=1989).values("player_id", "pa", "balls_in_play", "total_swings"):
    for k, acc in (("pa", pa), ("balls_in_play", bip), ("total_swings", sw)):
        if r[k]:
            acc[r["player_id"]] += r[k]
# BIP de los que tienen PA>=3000 (el ancla)
qual = [p for p in pa if pa[p] >= 3000]
print("n:", len(qual), "BIP min:", min(bip[p] for p in qual), "swings min:", min(sw[p] for p in qual))
```
