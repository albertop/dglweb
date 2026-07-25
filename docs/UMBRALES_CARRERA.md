# Umbrales de calificación de carrera (PA≥3000, IP≥1000, G≥600)

Los tableros **de por vida** de las tasas exigen un mínimo de exposición para calificar. Este
documento explica de dónde salen esos tres números.

## El punto de partida: la temporada ya está resuelta

El piso de temporada no se elige, se hereda del estándar oficial de MLB:

| Grupo | Piso de temporada | De dónde sale |
|---|---|---|
| Bateo | `PA ≥ 502` | 3.1 PA por juego × 162 |
| Pitcheo | `IP ≥ 162` | 1.0 IP por juego × 162 |
| Fildeo | `G ≥ 100` | juegos en la posición (estándar de los libros de récords) |

La carrera no tiene un estándar equivalente, así que hay que derivarlo.

## Lo que se encontró: la regla ya existía, sin estar escrita

Al leer los valores vigentes como múltiplos de su propio piso de temporada aparece un patrón:

| Grupo | Piso de carrera | ÷ piso de temporada | = temporadas calificadas |
|---|---|---|---:|
| Bateo | 3000 | 3000 / 502 | **6.0** |
| Pitcheo | 1000 | 1000 / 162 | **6.2** |
| Fildeo | 1000 | 1000 / 100 | **10.0** |

Bateo y pitcheo coinciden en **seis temporadas calificadas**. No es casualidad: es una regla
coherente que alguien aplicó sin dejarla escrita. Fildeo se salió de ella y pedía diez.

El efecto de esa inconsistencia se ve en la población admitida:

| Tablero | Admite |
|---|---:|
| Fildeo, temporada (`G ≥ 100`) | 10.9% de las temporadas-posición |
| Fildeo, carrera (`G ≥ 1000`) | **2.6%** de las carreras-posición |

Un piso de carrera cuatro veces más exigente que el de su propia temporada, sin razón que lo
sostenga. Con seis temporadas (`G ≥ 600`) sube a 6.6%, en línea con los otros dos grupos.

## La regla

> **El piso de carrera son seis temporadas calificadas del propio grupo.**

| Grupo | Cálculo | Resultado |
|---|---|---:|
| Bateo | 6 × 502 = 3012 | **PA ≥ 3000** |
| Pitcheo | 6 × 162 = 972 | **IP ≥ 1000** |
| Fildeo | 6 × 100 = 600 | **G ≥ 600** |

Bateo y pitcheo **no cambian**: el ejercicio los confirma y les da por fin una justificación
escrita. Fildeo baja de 1000 a 600.

## Por qué seis y no otro número

Seis temporadas completas está por encima de lo que dura la mayoría: entre los dominicanos que
llegaron a calificar **al menos una vez**, la mediana es de 4 temporadas calificadas en bateo y 2 en
pitcheo. O sea que el piso deja fuera a más de la mitad de los que alguna vez fueron regulares — que
es exactamente lo que un tablero de por vida debe hacer.

Se consideró y descartó un criterio alternativo: **igualar la selectividad** del piso de temporada
(la regla oficial admite una mediana de 18.4% de los bateadores por temporada y 10.0% de los
lanzadores; replicar esas fracciones sobre la carrera daría PA≥2106 e IP≥775). Se descartó porque
"seis temporadas" es interpretable y estable —no se mueve si mañana cambia la composición de la
muestra— mientras que un percentil sí. Es el mismo motivo por el que se rehicieron los umbrales de
postemporada (`docs/UMBRALES_POSTEMPORADA.md`).

## Dónde vive esto en el código

`_QUALIFIER` en `dglweb/stats/management/commands/seed_metrics.py`, que siembra
`QualifierDefault` — el nivel 1 de la cascada. Una métrica puede sobrescribirlo (nivel 2,
`Metric.qualifier_*`, que es lo que hacen los coeficientes) y una temporada corta también
(nivel 3, `QualifierSeasonOverride`).
