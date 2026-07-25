# Umbrales de calificación en los liderazgos de postemporada

Los tableros de postemporada exigen un mínimo de turnos (PA) o entradas (IP) para calificar. Este
documento explica **por qué existen** y, sobre todo, **de dónde salen los números**.

Llevan piso las **tasas** (bateo: AVG/OBP/SLG/OPS; pitcheo: ERA, PCT, H/9, BB/9, SO/9) y los
**conteos que apuntan hacia abajo** (bateo: SO; pitcheo: H, ER, BB). Los conteos que apuntan hacia
arriba (HR, RBI, SO de pitcheo…) no lo llevan: no se puede liderar en jonrones de octubre sin
batearlos. Es la misma regla de la serie regular — el umbral lo pide el extremo que mira el tablero,
no la dirección de la métrica.

## El problema: octubre no tiene "qualifier" oficial

La temporada regular sí tiene un estándar: **3.1 PA por juego** del equipo (502 PA en 162 juegos)
para bateo y **1.0 IP por juego** (162 IP) para pitcheo. Existe para que una tasa —que se distorsiona
con muestras pequeñas— se rankee solo entre jugadores con volumen suficiente.

La postemporada no tiene un equivalente, y la cascada normal no se le puede aplicar: ni la corrida
más larga de la historia se acerca a 502 PA. Con el umbral de serie regular, todos los tableros de
octubre saldrían vacíos.

## El criterio: anclar, no elegir un percentil

**La versión anterior de estos umbrales se fijó por percentil** — se eligieron los cortes que
admitían "≈⅓ de la población". Ese criterio es arbitrario: el tercio no se deriva de nada, y si
mañana entra una generación de dominicanos a octubre, el mismo percentil da otro número.

El criterio correcto es el que ya usa el sitio para los coeficientes
(`docs/UMBRALES_COEFICIENTES.md`): **anclar a un estándar establecido**. Acá el estándar existe y es
el oficial de MLB; lo único que faltaba era la unidad a la que aplicarlo.

En la serie regular esa unidad es la temporada (162 juegos). En octubre, la unidad natural es **una
serie completa**. Medido sobre nuestros propios datos (305 equipos-temporada desde 1956), la ronda
más larga son **7 juegos**, que es además el máximo estructural de cualquier serie.

De ahí salen los pisos, sin ninguna elección discrecional:

| Piso | Regla oficial | Unidad | Resultado |
|---|---|---|---:|
| Bateo, temporada | 3.1 PA/juego | 1 serie completa (7 j) | **PA ≥ 22** |
| Bateo, carrera | 3.1 PA/juego | 2 series completas | **PA ≥ 44** |
| Pitcheo, temporada | 1.0 IP/juego | 1 serie completa (7 j) | **IP ≥ 7** |
| Pitcheo, carrera | 1.0 IP/juego | 2 series completas | **IP ≥ 14** |

El salto de temporada a carrera es ×2, no el ×6 de la serie regular (502 → 3000). La razón es que
octubre no se juega todos los años: exigir seis series completas dejaría los tableros de por vida en
un puñado de nombres. Dos series es el equivalente honesto de "no fue una sola aparición".

## La distribución real (universo dominicano, desde 1956)

Agregando el octubre completo de cada jugador, igual que lo hacen los tableros:

| Tabla | n | mediana | p75 | p90 | máx |
|---|---:|---:|---:|---:|---:|
| BAT PA / temporada | 666 | 8 | 24 | 51 | 89 |
| BAT PA / carrera | 208 | 21.5 | 78 | 131 | 493 |
| PIT IP / temporada | 322 | 4.0 | 8.0 | — | 28.7 |
| PIT IP / carrera | 133 | 8.7 | 19.3 | 30.7 | 96.3 |

Cuánto admite cada piso:

| Tablero | Umbral | Califican |
|---|---|---:|
| Bateo, temporada | PA ≥ 22 | 184 de 666 (28%) |
| Bateo, carrera | PA ≥ 44 | 78 de 208 (38%) |
| Pitcheo, temporada | IP ≥ 7 | 96 de 322 (30%) |
| Pitcheo, carrera | IP ≥ 14 | 51 de 133 (38%) |

Los cuatro dejan fuera a la mitad o más de la muestra, que es lo que se busca: un tablero de octubre
no debe abrir con un jugador que fue de 4-3 en una serie de comodines perdida.

## Nota sobre los números anteriores

Los pisos previos eran PA ≥ 25 / 50 e IP ≥ 8 / 15. El ejercicio anclado los mueve poco (22/44 y
7/14), lo que dice que la intuición detrás de ellos era buena. Lo que cambia es que ahora el número
**se deriva** de la regla oficial en vez de justificarse con un percentil, así que se puede defender
—y recalcular— sin apelar al criterio de quien lo eligió.

## Dónde vive esto en el código

`_POST_QUALIFIER` en `dglweb/stats/leaders.py`. No pasa por la cascada `QualifierDefault` /
`Metric.qualifier_*` / `QualifierSeasonOverride`: es un piso fijo, a propósito.
