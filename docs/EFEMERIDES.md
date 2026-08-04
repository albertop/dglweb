# Efemérides dominicanas

Un archivo estático, generado una vez al año, con lo que pasó **un día como hoy** en Grandes Ligas
protagonizado por dominicanos. El sitio no calcula nada: filtra por mes y día, ordena por puntaje y
pinta.

Este documento es el diseño. Todos los números que aparecen abajo están **medidos contra
`DGL` en SQL Server** el 2026-08-03, no estimados.

---

## 1. Por qué es contenido estático

Retrosheet publica una vez al año, en la offseason. Entre publicación y publicación **el pasado no
cambia**: las efemérides de 1999 son las mismas hoy que en marzo. Calcularlas al vuelo en cada visita
sería recalcular 116 temporadas para pintar cinco líneas.

La cadencia queda: Retrosheet publica → se corre el exportador → el administrador sube el CSV. Una
vez al año, a mano, con la pantalla de comparación del Backoffice enseñando exactamente qué agregó la
temporada nueva.

Prueba de que la cadencia es real: hoy hay **18 jugadores en `dglMaster` sin `retroID`**, y son
exactamente los 18 que debutaron en 2026. Retrosheet todavía no les asignó identificador. El año que
viene lo tendrán y entrarán solos.

---

## 2. Las fuentes, y lo que ya viene resuelto

Todo sale de **`DGL` (SQL Server)**, la misma base de la que ya salen salarios, `dom_players` y los
tipos de batazo — ver `DATOS_DE_APOYO.md`.

| tabla | filas | qué aporta |
| --- | ---: | --- |
| `dbo.dglMaster` | 984 | **el universo**: quién es dominicano, y el puente `retroID` ↔ `mlbID` |
| `dbo.retroDailyReg` | 5.325.173 | el line score de cada jugador en cada juego, 1910–2025 |
| `dbo.retroDailyPost` | 52.982 | lo mismo, postemporada |
| `dbo.retroDailyAS` | 4.466 | Juego de Estrellas |
| `dbo.r24Events` | 16.311.132 | turno por turno, **con `WPA`, `WE` y `LI` ya calculados** |
| `dbo.retroEventsReg` | 16.167.453 | el evento con detalle de fildeo (`TP_FL`, `PO*_FLD_CD`, `ASS*_FLD_CD`) |
| `dbo.retroGamesReg` | 203.908 | la fecha, el marcador y el contexto del juego |

### 2.1. Lo que NO hay que construir

`r24Events` trae por cada turno las columnas `WPA`, `WE`, `LI`, `CLUTCH_EVENT_BATTER`,
`CLUTCH_EVENT_PITCHER` y `RUN_VALUE_ADJ`, para **1910–2025**, regular (`GAME_TYPE='R'`) y
postemporada (`GAME_TYPE='P'`).

Eso elimina de un plumazo la parte cara del proyecto. No hay que derivar tablas de probabilidad de
victoria ni calcular leverage: ya están, y son las mismas que usa el resto de la base.

### 2.2. El universo dominicano

**Todo el que está en `dbo.dglMaster` es dominicano. Sin filtrar por nada.** No se mira
`birthCountry` — de las 984 filas, 27 dicen `US`, 2 `PR`, 1 `CA` y 1 `CW`, y las cuatro cosas son
dominicanas igual. La regla completa está en `AUTORIDAD.md`.

La salida hacia dglweb va siempre en **`mlbID`**, que es la llave que el sitio entiende. Las 984
filas lo tienen. `retroID` lo tienen 966, y los 18 que faltan son el asunto de la sección 1.

---

## 3. El contrato: qué devuelve un detector

Todos los detectores devuelven **exactamente las mismas columnas**. Esta es la pieza que hace que
agregar una efeméride sea barato: el detector dice *qué pasó, a quién y cuándo*; el motor hace todo
lo demás igual para todos.

| columna | qué es |
| --- | --- |
| `tipo` | el slug del detector: `ciclo`, `hr3`, `walkoff`, `hito_hr`… |
| `rol` | `bateador` \| `lanzador` \| `fildeador` \| `persona` |
| `mlb_id` | el jugador, ya traducido desde `retroID` por `dglMaster` |
| `fecha` | la del juego, o la del cumpleaños/debut/fallecimiento |
| `temporada` | |
| `game_id`, `event_id` | de Retrosheet; `event_id` es 0 en las gestas de juego completo |
| `game_type` | `R` \| `P` \| `A` (Juego de Estrellas) \| `-` (sin juego) |
| `equipo`, `rival`, `en_casa` | |
| `signo` | `+1` hazaña, `-1` deshonra — ver 4.5 |
| `magnitud` | el número que define la gesta: 3 jonrones, 15 ponches, 0,87 de WPA |
| `wpa_jugador` | cuánto movió la probabilidad de ganar ese juego |
| `li_max` | el leverage más alto en que estuvo |
| `detalle` | los datos propios del tipo, para el texto |
| **`veces_total`** | cuántas veces ha pasado en la historia dominicana — ver 3.3 |
| **`jugadores_total`** | cuántos dominicanos DISTINTOS lo han hecho |
| **`orden`** | qué número es esta, en orden cronológico. `1` = la primera vez |
| **`veces_jugador`** | cuántas veces lo ha hecho ESTE jugador |
| **`orden_jugador`** | cuál de las suyas es esta |

Los cinco últimos **los calcula el motor**, no el detector. Un detector no puede saberlos: dependen
de todas las filas de su tipo, y él solo ve las suyas.

### 3.1. `rol` no es decorativo

El triple play sin asistencia lo hace **el fildeador**. Sin `rol`, el detector tendría que salir de
`BATTER_ID` y la efeméride quedaría atribuida al bateador rival — o sea, exactamente al revés de lo
que pasó. `rol = persona` es para cumpleaños, debut y fallecimiento, que no cuelgan de ningún juego.

### 3.2. Lo que un detector NO hace

No calcula puntaje. No escribe texto. No sabe que existen otros detectores. Si un detector necesita
saber algo de eso, el diseño está mal.

### 3.3. La efeméride dice CUÁNTOS hay, y son DOS números

Decisión del dueño: cada efeméride tiene que situarse. No basta «Domingo Germán ponchó a cuatro en
una entrada»; hace falta **«uno de los 5 dominicanos que lo ha logrado»**. Eso es lo que convierte un
dato en una noticia — sin el denominador, el lector no sabe si vio algo raro o algo de todos los días.

**Y no es un número, son dos**, porque un mismo jugador repite. Medido:

| detector | veces | jugadores distintos | veces por jugador |
| --- | ---: | ---: | ---: |
| `rbi6` | 165 | 68 | 2,43 |
| `hits5` | 153 | 93 | 1,65 |
| **`k12`** | **137** | **34** | **4,03** |
| `triples2` | 75 | 47 | 1,60 |
| `hr3` | 64 | 36 | 1,78 |
| `ciclo` | 20 | 16 | 1,25 |
| `ponches5` | 20 | 17 | 1,18 |
| **`k15`** | **16** | **6** | **2,67** |
| `robadas4` | 14 | 12 | 1,17 |
| `no_hitter` | 10 | 10 | 1,00 |

`k12` es el caso que obliga a distinguir: 137 juegos, pero **34 lanzadores**, cuatro juegos cada uno
en promedio. Decir «uno de los 137» es engañoso — la frase honesta es «uno de los 34 dominicanos que
lo ha hecho». En el otro extremo, los 10 no-hitters son de 10 lanzadores distintos y ahí los dos
números coinciden.

**Qué habilita cada campo en el texto:**

| campo | la frase |
| --- | --- |
| `jugadores_total` | «uno de los 34 dominicanos que lo ha logrado» |
| `veces_total` + `orden` | «la 7ª vez que un dominicano lo hace» |
| `orden = 1` | «**el primer dominicano** en lograrlo» |
| `veces_total = 1` | «**el único dominicano** que lo ha hecho» — Tatís, Furcal |
| `veces_jugador > 1` | «por segunda vez en su carrera» |
| la fecha | «hace 42 años» |

`orden = 1` y `veces_total = 1` son exactamente lo que el bono de relieve dominicano (4.4) premiaba
a ciegas. Ahora es **dato en la fila**, no un número escondido en el puntaje: el sitio lo puede decir
con palabras además de ordenar por él.

---

## 4. El puntaje: 0–1000

### 4.1. Rareza (0–600) — la columna vertebral

**No se asigna a mano: se mide.**

```
rareza = 600 × (1 − log(n) / log(N))
```

`n` = cuántas veces ocurrió esa gesta en 116 temporadas. `N` = el universo del detector, y **no es
uno solo: depende del grano** — 292.948 juegos-jugador, 822.764 turnos al bate, 622.652 bateadores
enfrentados, 162.797 medias entradas lanzadas. Ver 5.2.3.

La propiedad que importa: **un detector nuevo se calibra solo**. Si mañana se agrega uno que dispara
5.000 veces, se hunde solo y no inunda el calendario. Nadie tiene que sentarse a decidir cuánto vale.

### 4.2. Magnitud (0–200)

Dentro del tipo, qué tan lejos del umbral, por percentil de la propia distribución. Cuatro jonrones
pesan más que tres sin que haya que escribir una regla para el cuatro.

### 4.3. Impacto (0–150)

El `WPA` del jugador en ese juego. Es la **misma vara para todos los tipos**: un ciclo en una paliza
de 14-2 vale menos que uno que ganó el juego. Sale directo de `r24Events`, no se calcula.

### 4.4. Relieve dominicano (0–50)

«Primer dominicano en…», «único dominicano con…». Sale de los campos de la 3.3 —`orden = 1`,
`veces_total = 1`— que el motor ya calcula para el texto. El bono y la frase leen el mismo dato, así
que no pueden contradecirse: si la efeméride dice «el primero», el puntaje lo refleja.

> Los cuatro topes —**600 / 200 / 150 / 50**— son **las únicas constantes puestas a mano** en todo el
> sistema. Cualquier otra cosa sale de los datos.

### 4.5. Los hechos negativos corren en otra escala

Medido: **ponchar 5 veces en un juego es exactamente tan raro como batear el ciclo** — 20 veces cada
uno. La fórmula de rareza les daría el mismo 457, porque la rareza no distingue una hazaña de una
vergüenza.

Por eso `signo = -1` cambia dos cosas:

1. la rareza corre en **0–300** en vez de 0–600 (el ponche cae a **229**, por debajo de las 6
   empujadas, que es donde debe estar);
2. **no aplica el bono de impacto** — usar el valor absoluto del WPA premiaría la mala noche.

El sitio recibe el `signo` y los puede presentar aparte, sin mezclarlos con las gestas.

### 4.6. Cumpleaños, debut y fallecimiento

La rareza no significa nada acá: todo el mundo tiene cumpleaños. Corren en escala propia **0–250**,
siempre por debajo de cualquier gesta real, escalada por la **huella del jugador** —juegos de su
carrera, que ya está en `retroDailyReg`— para que el cumpleaños de Pedro Martínez no pese igual que
el de alguien con tres juegos. Con bono por aniversario redondo: 50 años, 25 del debut.

### 4.7. Los hitos de carrera se puntúan por el número

Un hito no tiene «rareza de evento»; tiene **rareza de cifra**. El puntaje sale de cuántos
dominicanos han llegado alguna vez a ese número. El hit 3000 pesa lo que pesa porque lo han hecho
dos.

---

## 5. El inventario: 39 detectores

| grupo | detectores |
| --- | ---: |
| gestas de juego (5.1) | 19 |
| gestas de evento (5.2) | 9 |
| hitos de carrera (5.4) | 7 |
| fechas de persona (5.5) | 4 |

La `N` de cada detector depende de su grano — ver 5.2.3. La columna *rareza* es lo que da la fórmula
hoy; el exportador la recalcula en cada corrida.

### 5.1. Gestas de juego (`retroDaily*`)

| detector | umbral | veces | rareza |
| --- | --- | ---: | ---: |
| `perfecto` | sin H, sin BB, sin HP, 27+ outs | 1 | 600 |
| `no_hitter` | `P_H = 0`, 27+ outs | 10 | 490 |
| `robadas4` | `B_SB >= 4` | 14 | 474 |
| `k15` | `P_SO >= 15` | 16 | 468 |
| `ciclo` | 1B, 2B, 3B y HR en el mismo juego | 20 | 457 |
| `extrabases4` | `B_2B + B_3B + B_HR >= 4` | 33 | 433 |
| `cg_1hit` | juego completo de un solo hit | 37 | 428 |
| `cg_dominante` | CG, 10+ K, cero limpias | 41 | 423 |
| `hr3` | `B_HR >= 3` | 64 | 402 |
| `triples2` | `B_3B >= 2` — ver 5.1.1 | 74 | 395 |
| `boletos4` | `B_BB >= 4` | 75 | 394 |
| `bases12` | `B_TB >= 12` | 85 | 388 |
| `k12` | `P_SO >= 12` | 137 | 365 |
| `hits5` | `B_H >= 5` | 153 | 360 |
| `rbi6` | `B_RBI >= 6` | 165 | 357 |
| `anotadas4` | `B_R >= 4` | 233 | 340 |
| `blanqueada` | `P_SHO >= 1` | 271 | 333 |
| `bases10` | `B_TB >= 10` | 369 | 318 |
| `ponches5` ⚠️ | `B_SO >= 5` — **`signo = -1`** | 20 | **229** |

#### 5.1.1. Cómo se eligió el umbral de los triples, y por qué NO hay un detector de 3

Medido:

| triples en un juego | dominicanos | toda la liga |
| ---: | ---: | ---: |
| 2 | 74 | 2.019 |
| 3 | **1** | 39 |

Con `>= 2` el detector queda en rareza 395, en el centro del inventario — ni ruido ni pieza de
museo. Con `>= 3` daría una sola fila.

**Y no hace falta un detector aparte para el de 3.** El único juego de tres triples —Rafael Furcal,
21 de abril de 2002— entra por `triples2` y **el componente de magnitud (4.2) lo sube solo** hasta el
tope de su tipo. Eso es precisamente para lo que existe ese componente: un detector define *qué
cuenta*, la magnitud define *cuánto*.

Es el patrón a seguir para cualquier umbral nuevo: se elige el corte donde la gesta deja de ser
rutina, no donde se vuelve única.

### 5.2. Gestas de evento (`r24Events`, `retroEventsReg`)

| detector | umbral | veces | rareza |
| --- | --- | ---: | ---: |
| `doble_slam` | 2 grand slams del mismo bateador en un juego | **1** | 600 |
| `triple_play_solo` | `TP_FL='T'`, los 3 outs del mismo fildeador, cero asistencias | **1** | 600 |
| `walkoff_slam` | walk-off con 2 outs y bases llenas | 69 | 413 |
| `walkoff_hr` | walk-off de jonrón | 262 | 355 |
| `k4_inning` | 4 ponches en la misma entrada — ver 5.2.2 | 5 | 520 |
| `nobletiger` | bases llenas, 0 outs, sale sin carrera — ver 5.2.1 | 324 | 340 |
| `turno_clave` | `LI >= 2` **y** `WPA >= 0.40` | 154 | — |
| `grand_slam` | `HR=1` y `RBI=4` | 520 | 325 |
| `walkoff` | último turno, en casa, 9no o más, WPA positivo | 938 | 299 |

**Los dos de `n=1` son los que dan sentido a todo esto:**

- **`doble_slam`** — Fernando Tatís, 23 de abril de 1999, **los dos en el mismo inning**. Es el
  récord de Grandes Ligas y nadie más lo ha hecho nunca.
- **`triple_play_solo`** — Rafael Furcal, 10 de agosto de 2003, campocorto, quinto inning. De los
  13 sin asistencia que cubre Retrosheet, uno es dominicano.

#### 5.2.1. `nobletiger` — el escape

**N**o-**O**uts **B**ases-**L**oaded **E**nding with **T**eam **I**ncapable of **G**etting **E**asy
**R**un: el lanzador se encuentra **bases llenas y ningún out**, y sale del inning **sin permitir
carrera**.

Medido sobre lanzadores dominicanos:

| | |
| --- | ---: |
| veces que enfrentaron bases llenas sin outs | 2.522 |
| **escaparon con cero carreras** | **324** (12,9 %) |
| permitieron exactamente una | 596 |
| permitieron dos o más | 1.436 |
| de los escapes, en el 9no inning o más | 44 |
| de los escapes, en postemporada | 6 |

Rareza **340** sobre el universo de lanzador (ver 5.2.2).

**La magnitud NO es el `LI` del momento, es el `WPA` del escape.** Se probó con `LI` y el máximo
entre los 324 escapes fue 1,44 — no separa nada. Sumando el WPA del lanzador desde la situación
hasta el final de la media entrada, la escala se abre de golpe:

| | | |
| --- | --- | ---: |
| 2016-07-19 | Jeurys Familia, 9no | **+0,890** |
| 2012-09-29 | Kelvin Herrera, inning **14** | +0,878 |
| 2004-04-27 | Francisco Cordero, 9no | +0,877 |
| 2003-09-05 | Julián Tavárez, 9no | +0,701 |

Un escape de +0,890 es ganar el juego prácticamente solo. Los 44 del noveno en adelante son los que
el componente de impacto (4.3) levanta hasta arriba, y con razón.

**Detalle de implementación que no es opcional.** Para saber si entró carrera hay que comparar el
marcador del equipo al bate en el momento del aprieto contra el marcador cuando le toca batear otra
vez. En **182 de los 2.522 casos el juego terminó en esa misma media entrada**, así que no hay
«próxima vez al bate»: hay que caer al marcador final del juego, y buscarlo en `retroGamesReg`
**y en `retroGamesPost`**. Con solo la primera quedaban 2 casos de postemporada sin resolver.

#### 5.2.2. `k4_inning` — cuatro ponches en una entrada

Solo se puede si un strike tres se le escapa al receptor y el bateador llega a primera: el lanzador
poncha a cuatro y solo saca tres outs.

| | |
| --- | ---: |
| medias entradas lanzadas por dominicanos (`N`) | 162.797 |
| con 3 ponches | 3.869 |
| **con 4 ponches** | **5** |
| 4 ponches, toda la liga | 100 |
| 5 ponches, toda la liga | **0 — nunca ha pasado** |

Rareza **520**, entre el no-hitter (490) y el juego perfecto (600). Los cinco:

| fecha | lanzador | |
| --- | --- | --- |
| 1984-05-17 | Mario Soto | CIN, 3er inning |
| 2003-06-11 | Octavio Dotel | HOU, 8vo |
| 2012-06-05 | Francisco Liriano | MIN, 4to |
| 2018-07-08 | Miguel Díaz | SD, **inning 11** |
| 2021-07-25 | Domingo Germán | NYY, 7mo |

#### 5.2.3. La `N` no depende del `rol`: depende del grano

Primero se escribió que la `N` de la rareza dependía del `rol`. Con `k4_inning` quedó claro que eso
era quedarse corto: dos detectores de lanzador pueden tener universos distintos, porque lo que
cambia no es quién protagoniza sino **cuál es la unidad de oportunidad**.

| grano | universo | qué se cuenta |
| --- | ---: | --- |
| juego-jugador | 292.948 | la línea de un dominicano en un juego |
| turno al bate | 822.764 | un turno de un bateador dominicano |
| bateador enfrentado | 622.652 | un turno contra un lanzador dominicano |
| media entrada lanzada | 162.797 | una entrada de un lanzador dominicano |

`nobletiger` y `k4_inning` son los dos de lanzador y **no comparten `N`**: uno se pregunta «de cada
bateador que enfrentó», el otro «de cada entrada que lanzó».

Cada detector declara su grano y el motor toma la `N` que corresponde. Usar la equivocada no da
error: da un puntaje que parece razonable y está mal, que es peor.

### 5.3. El corte de `turno_clave`, medido

Primero, la escala de `LI`, porque el umbral no significa nada sin ella. Verificado sobre 4.777.761
turnos desde 2000: **media 0,940**, máximo **7,17**, `LI >= 2` es el **4,5 %** de los turnos y
`LI >= 3` el **0,65 %**. O sea que está normalizado como manda el estándar —promedio 1— y un umbral
de 2 significa «el doble de tensión que un turno cualquiera».

| corte | turnos |
| --- | ---: |
| `LI >= 2` | 34.683 |
| `LI >= 3` | 5.159 |
| `WPA >= 0.40` | 375 |
| **`LI >= 2` y `WPA >= 0.40`** | **154** |
| `LI >= 3` y `WPA >= 0.50` | 36 |

Se eligió `LI >= 2` **y** `WPA >= 0.40`: 154 momentos en 116 años, del mismo orden que las demás
gestas. Solo `LI >= 3` daría 5.159 turnos tensos que **no decidieron nada** — y tensión sin desenlace
no es efeméride.

### 5.4. Hitos de carrera (`retroDailyReg`, suma acumulada)

**831 cruces.** Es la efeméride clásica —«un día como hoy, X llegó a su jonrón 300»— y está fechada
al día exacto. Se detecta con una suma acumulada por jugador ordenada por fecha, buscando el juego
en que el total cruza un múltiplo del escalón.

**Suman temporada regular Y postemporada** (decisión del dueño, 2026-08-03). No es como los cuenta
MLB oficialmente —ellos separan— pero es coherente con el resto del archivo, donde octubre cuenta
igual que junio. La diferencia medida es de **13 cruces**: 818 solo con regular, 831 con las dos.

| detector | escalón | cruces |
| --- | ---: | ---: |
| `hito_hit` | 500 | 267 |
| `hito_hr` | 100 | 137 |
| `hito_k` (lanzador) | 500 | 117 |
| `hito_sb` | 100 | 88 |
| `hito_rbi` | 500 | 87 |
| `hito_sv` | 50 | 73 |
| `hito_win` | 50 | 62 |

El puntaje **no** sale de la fórmula de rareza de la 4.1 sino de la 4.7: cuántos dominicanos han
llegado alguna vez a esa cifra. Un jonrón 100 lo han cruzado decenas; el hit 3000, dos.

### 5.5. Fechas de persona (`dglMaster`)

| detector | filas | días del calendario |
| --- | ---: | ---: |
| `cumpleanos` | 923 | 335 de 366 |
| `debut` | 984 | 193 |
| `fallecimiento` | 61 | 55 |
| `juego_estrellas` | 283 apariciones de 111 jugadores | — |

**El cumpleaños se suprime si el jugador tiene `deathDate`.** Es la razón de que sean 923 y no 984:
61 fallecidos quedan fuera. Felicitar a un muerto por su cumpleaños es el tipo de error que un
sistema automático comete y una persona no. A esos 61 les corresponde su aniversario de
fallecimiento, que va por el detector `fallecimiento` (1943–2025, y **24 de ellos están en el Salón
de la Fama dominicano** según `yearDomHof`).

---

## 6. Por qué hacen falta las fechas de persona

Las gestas solas dejan el calendario con hoyos. Medido:

| | |
| --- | ---: |
| hechos de gesta (regular + postemporada) | 549 |
| días del calendario con al menos una gesta | 179 |
| **días en que de verdad se juega béisbol** | **232** |
| cobertura de la temporada | **77 %** |

O sea **53 días de temporada sin nada**. Con los 923 cumpleaños —que cubren 335 de 366 días— el
calendario queda prácticamente lleno, y sin que un cumpleaños pueda nunca desplazar a una gesta,
porque su escala tiene techo 250.

---

## 7. La fusión: un batazo, una efeméride

Un walk-off de grand slam dispara **tres** detectores sobre el mismo turno. Sin regla de fusión, el
día 23 de abril de 1999 aparecería el mismo batazo de Tatís repetido.

**Regla:** mismo `mlb_id` + mismo `game_id` + mismo `event_id` → se queda **el hecho de mayor
puntaje** y los demás se anexan como **etiquetas** del mismo hecho, no como filas sueltas.

Aplica igual entre niveles: si un juego de 3 jonrones incluye un grand slam de walk-off, la fila es
una sola con las tres etiquetas.

---

## 8. Cómo se agrega una efeméride nueva

```
static_data/efemerides/
  exportar_efemerides.ps1        ← el motor. NO se toca al agregar un detector.
  detectores/
    10_ciclo.sql
    20_hr3.sql
    …
    90_triple_play_solo.sql
```

El motor recorre el directorio, corre cada `.sql`, **valida que devuelva el contrato de la sección
3** —si falta una columna, falla ruidosamente en vez de exportar un archivo mutilado—, une todo,
puntúa, fusiona y escribe el CSV.

Agregar «robó home» es escribir `95_robo_home.sql` y nada más. Queda en git y se revisa como
cualquier otro código.

**Un detector que hoy devuelve cero está bien y se deja escrito.** Ningún dominicano se ha ponchado
6 veces en un juego —en toda la liga solo ha pasado 8 veces en 116 años— pero el detector cuesta
nada y empieza a producir el día que pase.

### 8.1. Por qué PowerShell y no Python

En la máquina del dueño **no hay Python fuera de Docker**, y un contenedor no llega a SQL Server con
Integrated Security. Los tres exportadores que ya existen (`export_dom_players.ps1`,
`export_dom_salaries.ps1`, `export_batted_ball_hits.ps1`) son PowerShell + ADO.NET por exactamente
esa razón. Esto sigue el mismo camino y no obliga a instalar nada.

La consecuencia de diseño: **la lógica vive en SQL**, y PowerShell es la tubería. Que es lo que
conviene igual — los detectores son consultas, no programas.

---

## 9. Cómo llega al sitio

Por la vía que **ya existe**: `StaticDataset` → CSV → pantalla del Backoffice. Eso da gratis la
validación de clave natural, la pantalla de comparación contra la carga anterior y el registro de
quién cargó y cuándo. Un JSON suelto no tiene nada de eso.

- **Tabla:** `dgl_efemerides`
- **Clave natural:** `tipo,game_id,mlb_id,event_id`
- **Modo:** `truncate` — el pasado se regenera entero en cada corrida

Cada fila trae, además de los datos, **el texto ya redactado** (titular y resumen). El sitio filtra
por mes y día y pinta: **agregar un tipo nuevo no toca el website**. Los campos estructurados van
igual, para poder enlazar la ficha del jugador y filtrar por tipo sin re-exportar.

**Tamaño.** No es la suma de las categorías de la sección 5 —se solapan, y la fusión de la sección 7
las colapsa—. Medido después de fusionar:

| | filas |
| --- | ---: |
| juegos-jugador con al menos una gesta | **1.354** |
| gestas y momentos de evento | ~1.900 |
| hitos de carrera | 831 |
| cumpleaños + debut + fallecimiento + Juego de Estrellas | ~2.250 |
| **total aproximado** | **~6.300** |

Bien por debajo de 5 MB. Para comparar: `dom_players` ya carga 9.133 filas por esta misma vía.

**Idempotencia:** misma base, mismo CSV. Al correrlo tras la actualización de Retrosheet, la pantalla
de comparación enseña exactamente lo que agregó la temporada nueva y nada más.

---

## 10. Supuestos, y lo que ya está confirmado

### 10.1. Confirmado por el dueño

**El debutante nunca sale en las efemérides de su propio año.** Se inscribe en `dglMaster`
*después* de debutar, y el archivo se genera *después* de que Retrosheet publica. O sea que **al
momento de correr el script, todo el que está en `dglMaster` ya tiene `retroID`**, y entra completo
—gestas, debut y cumpleaños— en la misma corrida.

Esto invalida un supuesto que yo había escrito acá: razoné sobre el estado de la base **a mitad de
temporada**, que es cuando la miré, y no sobre el estado **en el momento de la corrida**. Son
distintos, y el que manda es el segundo. Los 18 sin `retroID` de hoy no son un caso de diseño: son
una foto de agosto.

**Consecuencia práctica — esto se convierte en una comprobación, no en un supuesto.** El exportador
cuenta cuántas filas de `dglMaster` no tienen `retroID` y **lo reporta**. En una corrida normal ese
número es **0**. Si no lo es, algo pasó —Retrosheet no cubrió a alguien, o se inscribió a un jugador
que no ha debutado— y hay que mirarlo antes de subir el CSV, no después.

**La postemporada entra en todas las gestas**, con bono de contexto. Aporta poco en conteo —7 hechos
de 549, y 4 de 154 momentos— porque son 1.878 juegos contra 203.908. Su valor está en que esos pocos
son de octubre.

**Y también suma en los hitos de carrera**, aunque MLB los cuente separados. Es la decisión coherente
con la anterior: si octubre cuenta para el ciclo, cuenta para el hit 2000. Medido, la diferencia son
13 cruces — 818 contra 831.

### 10.2. Sin confirmar

Nada. Las tres decisiones abiertas se cerraron el 2026-08-03. Si aparece una nueva, va acá y no
enterrada en un `.sql`.

## 11. Fuera de alcance, por ahora

- **El inning inmaculado** (9 lanzamientos, 3 ponches). `r24Events_PitchCount` tiene 7.107.316 filas
  y probablemente lo soporta, pero no se ha medido si el conteo por lanzamiento alcanza para
  identificarlo con seguridad.
- **Triple plays con dominicano fildeando** de cualquier tipo: hay **68**, y saldrían por la misma
  vía que `triple_play_solo` ahora que el contrato tiene `rol`.
- **El Salón de la Fama dominicano.** `dglMaster.yearDomHof` da el año pero no el día, y una
  efeméride necesita fecha exacta.
