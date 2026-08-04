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
| `rol` | `bateador` \| `lanzador` \| `fildeador` \| `corredor` \| `persona` — ver 3.1 |
| `mlb_id` | el jugador, ya traducido desde `retroID` por `dglMaster` |
| `nombre` | de `dglMaster.nameList`, SIEMPRE — ver 3.0 |
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
| **`cobertura`** | el rango de años que el detector puede ver — ver 5.2.5 |
| **`veces_total`** | cuántas veces ha pasado en la historia dominicana — ver 3.3 |
| **`jugadores_total`** | cuántos dominicanos DISTINTOS lo han hecho |
| **`orden`** | qué número es esta, en orden cronológico. `1` = la primera vez |
| **`veces_jugador`** | cuántas veces lo ha hecho ESTE jugador |
| **`orden_jugador`** | cuál de las suyas es esta |

Los cinco de conteo **los calcula el motor**, no el detector. Un detector no puede saberlos: dependen
de todas las filas de su tipo, y él solo ve las suyas. `cobertura` sí la declara el detector, porque
es lo único que él sabe y el motor no: hasta dónde alcanza su fuente.

### 3.0. EL NOMBRE SALE DE `nameList`. SIEMPRE.

Regla del dueño, y no admite excepciones: el nombre del jugador se toma de
**`dglMaster.nameList`**. Nunca de `nameFirst1 + nameLast1`, nunca del `nameLast2`, nunca armado a
mano.

No es una preferencia de estilo, es corrección. `dglMaster` guarda el nombre civil completo —dos
nombres y dos apellidos— y el nombre por el que se conoce al jugador es otro campo:

| `nameFirst1` | `nameLast1` | `nameLast2` | `nameNick` | **`nameList`** |
| --- | --- | --- | --- | --- |
| Samuel | Peralta | Sosa | Sammy | **Sammy Sosa** |
| Alexander | Rodríguez | | A-Rod | **Alex Rodríguez** |
| David | Ortiz | Arias | Big Papi | **David Ortiz** |

**Concatenar `nameFirst1 + nameLast1` produce «Samuel Peralta» para Sammy Sosa.** Medido: **107 de
las 984 filas** darían un nombre distinto del correcto, y son precisamente los más conocidos —
justamente los que más van a salir en el archivo.

Este error lo cometí yo en una consulta de sondeo mientras se diseñaba esto, y por eso queda escrito
acá: es invisible para quien lo escribe y evidente para cualquier lector dominicano.

`nameNick` existe en 304 de las 984 filas y **no sustituye a `nameList`**; a lo sumo se le suma como
adorno en el texto.

#### 3.0.1. `nameList` es para MOSTRAR. Para AGRUPAR se usa el id. Siempre.

La otra mitad de la regla, y la más peligrosa de las dos porque el error no se ve: **`nameList` no
es único**. Contar «cuántos dominicanos lo han hecho» agrupando por nombre da un número **menor** que
el real, y menor sin avisar.

Medido: **19 nombres repetidos, 41 jugadores afectados.** Y no son casos oscuros:

| nombre | jugadores distintos |
| --- | ---: |
| Luis Castillo | **3** |
| Luis De los Santos | 3 |
| Luis García | 3 |
| Nelson Cruz | 2 |
| José Ramírez | 2 |
| Tony Peña | 2 |
| …y 13 más | 2 |

Hay **dos Nelson Cruz** y **dos José Ramírez** en el maestro. Agrupar por nombre los fundiría en uno.

**Regla: `jugadores_total`, `veces_jugador`, `orden_jugador` y cualquier otro conteo se agrupan por
`retroID` / `mlbID`. `nameList` solo se imprime.**

Todos los números de este documento se midieron así — agrupando por `PLAYER_ID` — así que son
correctos. La regla queda escrita para que la implementación no se desvíe.

### 3.1. `rol` no es decorativo

El triple play sin asistencia lo hace **el fildeador**. Sin `rol`, el detector tendría que salir de
`BATTER_ID` y la efeméride quedaría atribuida al bateador rival — o sea, exactamente al revés de lo
que pasó.

`robo_home` (5.2.6) estrenó el quinto: **`corredor`**. Quien roba home no batea ni lanza, está en
tercera. Dos detectores han obligado ya a ampliar esta lista, así que conviene asumir que habrá más.

`rol = persona` es para cumpleaños, debut y fallecimiento, que no cuelgan de ningún juego.

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
| `rbi7` | 43 | 29 | 1,48 |
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
enfrentados, 162.797 medias entradas lanzadas. Ver 5.2.11.

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

## 5. El inventario: 61 detectores

| grupo | detectores |
| --- | ---: |
| gestas de juego (5.1) | 30 |
| gestas de evento (5.2) | 20 |
| hitos de carrera (5.4) | 7 |
| fechas de persona (5.5) | 4 |

La `N` de cada detector depende de su grano — ver 5.2.11. La columna *rareza* es lo que da la fórmula
hoy; el exportador la recalcula en cada corrida.

### 5.1. Gestas de juego (`retroDaily*`)

| detector | umbral | veces | rareza |
| --- | --- | ---: | ---: |
| `perfecto` | sin H, sin BB, sin HP, 27+ outs | 1 | 600 |
| `cg90` | juego completo bajo 90 lanzamientos — ver 5.1.8 | 8 | 500 |
| `fouls_juego` | 16+ fouls en un juego ⚠️ 2008+ — ver 5.1.9 | 11 | 476 |
| `rv_pitcheo` | 5+ carreras EVITADAS — ver 5.1.10 | 40 | 402 |
| `rv_bateo` | 5+ carreras de valor generadas — ver 5.1.10 | 94 | 378 |
| `hbp_recibidos` | 2+ pelotazos recibidos — ver 5.1.9 | 120 | 372 |
| `no_hitter` | `P_H = 0`, 27+ outs | 10 | 490 |
| `robadas4` | `B_SB >= 4` | 14 | 474 |
| `k15` | `P_SO >= 15` | 16 | 468 |
| `gidp_inducidos` | `P_GDP >= 4` — ver 5.1.13 | 19 | 460 |
| `ciclo_inverso` | HR, 3B, 2B y 1B EN ESE ORDEN — ver 5.2.10 | 1 | 600 |
| `ciclo_natural` | 1B, 2B, 3B y HR EN ESE ORDEN — ver 5.2.10 | 0 | — |
| `ciclo` | 1B, 2B, 3B y HR en el mismo juego | 20 | 457 |
| `extrabases4` | `B_2B + B_3B + B_HR >= 4` | 33 | 433 |
| `cg_1hit` | juego completo de un solo hit | 37 | 428 |
| `cg_dominante` | CG, 10+ K, cero limpias | 41 | 423 |
| `rbi7` | `B_RBI >= 7` | 43 | 421 |
| `hr3` | `B_HR >= 3` — nadie ha llegado a 4, ver 5.1.6 | 64 | 402 |
| `triples2` | `B_3B >= 2` — ver 5.1.1 | 74 | 395 |
| `k10_bb4` | `P_SO >= 10` y `P_BB >= 4` — dominante y salvaje | 73 | 395 |
| `boletos4` | `B_BB >= 4` | 75 | 394 |
| `bases12` | `B_TB >= 12` — ver 5.1.7 | 85 | 388 |
| `dobles3` | `B_2B >= 3` — ver 5.1.11 | 136 | 366 |
| `k12` | `P_SO >= 12` | 137 | 365 |
| `hits5` | `B_H >= 5` | 153 | 360 |
| `anotadas4` | `B_R >= 4` | 233 | 340 |
| `blanqueada` | `P_SHO >= 1` | 271 | 333 |
| `cs3` ⚠️ | `B_CS >= 3` — **`signo = -1`**, ver 5.1.5 | 1 | **300** |
| `gidp3` ⚠️ | `B_GDP >= 3` — **`signo = -1`**, ver 5.1.12 | 10 | **245** |
| `paliza` ⚠️ | `P_H >= 10` y `P_R >= 10` — **`signo = -1`** | 19 | **230** |
| `ponches5` ⚠️ | `B_SO >= 5` — **`signo = -1`** | 20 | **229** |
| `hbp_propinados` ⚠️ | 3+ pelotazos propinados — **`signo = -1`**, ver 5.1.9 | 25 | **223** |

#### 5.1.0. Cada cuánto pasa cada cosa

Las veces totales no dicen si un detector es ruidoso: hay que dividir por las 116 temporadas. Esta
es la tabla para decidir umbrales de aquí en adelante.

| detector | veces | por temporada |
| --- | ---: | ---: |
| `blanqueada` | 271 | 2,34 |
| `anotadas4` | 233 | 2,01 |
| `hits5` | 153 | 1,32 |
| `k12` | 137 | 1,18 |
| `bases12` | 85 | 0,73 |
| `boletos4` | 75 | 0,65 |
| `triples2` | 75 | 0,65 |
| `hr3` | 64 | 0,55 |
| `rbi7` | 43 | 0,37 |
| `cg_dominante` | 41 | 0,35 |
| `cg_1hit` | 37 | 0,32 |
| `extrabases4` | 33 | 0,28 |
| `ciclo` | 20 | 0,17 |
| `ponches5` | 20 | 0,17 |
| `k15` | 16 | 0,14 |
| `robadas4` | 14 | 0,12 |
| `no_hitter` | 10 | 0,09 |

**`hits5` está en 1,32 por temporada** — aproximadamente uno al año, o sea nada. Se revisó porque
parecía mucho en términos absolutos y no lo es. Y no tiene punto intermedio: subirlo a 6 lo llevaría
de 153 a **7**, de uno al año a uno cada 17 años.

Los dos que más volumen mueven, ya sin `bases10`, son `blanqueada` y `anotadas4` — ver 5.1.7 para
por qué `bases10` se eliminó.

#### 5.1.1. `rbi7` y no `rbi6`

Decisión del dueño. El umbral estaba en 6 y subió a 7. Medido, la diferencia es grande:

| empujadas | veces | jugadores |
| ---: | ---: | ---: |
| 6 | 122 | 61 |
| 7 | 32 | 21 |
| 8 | 7 | 6 |
| 9 | 3 | 3 |
| **10** | **1** | **1** |

Con `>= 6` eran 165 hechos y rareza 357. Con `>= 7` son **43 y rareza 421** — pasa de estar entre
las corrientes a estar entre las buenas. El tope dominicano son **10 empujadas en un juego**, una
sola vez: Alex Rodríguez, 26 de abril de 2005, con 3 jonrones y 13 bases alcanzadas.

#### 5.1.2. Cómo se eligió el umbral de los triples, y por qué NO hay un detector de 3

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

#### 5.1.3. Los siete juegos de 6 hits

Mismo patrón que los triples: entran por `hits5` y la magnitud los sube sola. De los 153 juegos de
5 o más hits, **7 son de 6 hits, por 7 jugadores distintos** — y seis de los siete fueron de 6-de-6:

| fecha | jugador | |
| --- | --- | --- |
| 1964-07-10 | Jesús Alou | 6-6, 1 HR |
| 1993-07-02 | Sammy Sosa | 6-6 |
| 2004-05-08 | Alfonso Soriano | 6-6, 4 RBI |
| 2004-05-27 | Carlos Peña | 6-6, **2 HR y 5 RBI** |
| 2013-05-28 | Jean Segura | 6 de 7 |
| 2019-08-13 | Rafael Devers | 6-6, 3 RBI |
| 2023-05-26 | Luis García | 6-6 |

Dos nombres de esta lista son la prueba de las reglas de la 3.0: **Sammy Sosa** —que concatenando
saldría como «Samuel Peralta»— y **Luis García**, que son tres jugadores distintos en el maestro.

#### 5.1.4. Las 14 de `robadas4`, y la única de 5

Es el detector más raro del grupo de juego (rareza 474). Las 14, completas — **12 jugadores
distintos**, con Luis Polonia y Elly De La Cruz repitiendo:

| robadas | fecha | jugador | |
| ---: | --- | --- | --- |
| **5** | 2008-06-14 | **Willy Taveras** | COL vs CHW |
| 4 | 1984-04-25 | Dámaso García | TOR |
| 4 | 1992-06-10 | Luis Polonia | CAL |
| 4 | 1993-09-29 | Sammy Sosa | CHC |
| 4 | 1994-06-26 | Luis Polonia | NYY |
| 4 | 1998-08-01 | José Offerman | KC |
| 4 | 2000-05-17 | Luis Castillo | FLA |
| 4 | 2004-06-19 | Ángel Berroa | KC |
| 4 | 2007-09-15 | Rafael Furcal | LAD |
| 4 | 2009-08-15 | Julio Borbón | TEX |
| 4 | 2018-05-15 | Jean Segura | SEA |
| 4 | 2023-04-26 | Esteury Ruiz | OAK |
| 4 | 2024-05-16 | Elly De La Cruz | CIN |
| 4 | 2024-07-28 | Elly De La Cruz | CIN |

**En 13 de los 14 no atraparon a nadie robando.** El único atrapado es De La Cruz en el primero de
los suyos. Es el tipo de dato que el campo `detalle` debe cargar: la gesta es «4 robadas», pero
«4 de 4» es mejor efeméride que «4 de 5».

#### 5.1.5. `cs3` — el umbral se puso en 3, no en 4

Se pidió «atrapado robando con 4+». Medido, ese detector nacería vacío:

| atrapado en un juego | dominicanos | toda la liga |
| ---: | ---: | ---: |
| 2 | 110 (53 jugadores) | 2.726 |
| **3** | **1** | 45 |
| 4 | **0** | **1 en 116 años** |

Ningún dominicano ha sido atrapado cuatro veces en un juego, y en toda la liga ha pasado una sola
vez. Por eso el umbral queda en **3**, siguiendo el criterio de 5.1.2: se corta donde deja de ser
rutina, no donde se vuelve único. Si algún día hay un 4, la magnitud lo sube sola.

El único: **Luis Polonia, 24 de mayo de 1993 — atrapado 3 veces, robó 0.** El mismo Polonia que
aparece dos veces en la lista de `robadas4`. Ladrón y víctima.

Rareza **300**, el tope de la escala negativa (4.5), porque `n = 1`.

#### 5.1.7. Las bases alcanzadas van en 12, y `bases10` se borró

Había DOS detectores del mismo stat, `bases10` y `bases12`, que contradice el patrón de 5.1.2: un
umbral por gesta, y la magnitud se encarga del resto. Se elimina `bases10` y queda `bases12`.

| bases | acumulado | por temporada |
| ---: | ---: | ---: |
| 9+ | 828 | 7,14 |
| 10+ | 369 | 3,18 |
| 11+ | 140 | 1,21 |
| **12+** | **85** | **0,73** |
| 13+ | 24 | 0,21 |
| 15 | 1 | 0,01 |

Con 10 era **el detector más ruidoso del inventario**. Con 12 queda en la misma liga que `hr3`
(0,55) y `triples2` (0,65). El único juego de 15 bases sube solo por magnitud.

#### 5.1.8. `cg90` — el juego completo de menos de 90 lanzamientos

**8 juegos, 7 lanzadores** (Framber Valdez lo hizo dos veces). Rareza **500**, entre el no-hitter y
el juego perfecto.

| lanz. | fecha | lanzador | |
| ---: | --- | --- | --- |
| **71** | 2025-05-30 | Framber Valdez | 3 H, 9 K |
| **73** | 2023-06-28 | Domingo Germán | **el juego perfecto** |
| 87 | 2002-06-25 | Odalis Pérez | blanqueada de 1 hit |
| 87 | 2003-06-07 | Bartolo Colón | 4 H |
| 87 | 2025-07-22 | Cristopher Sánchez | 12 K |
| 88 | 2023-08-01 | Framber Valdez | **el no-hitter** |
| 89 | 2006-08-15 | Pedro Astacio | blanqueada |
| 89 | 2019-05-19 | Sandy Alcántara | blanqueada de 2 hits |

Cinco de los ocho son blanqueadas y dos son sin hits.

**Este detector tiene DOS filtros que no son opcionales, y sin ellos da 19 en vez de 8:**

1. **`SEASON >= 1989`.** Regla del dueño: el conteo de lanzamientos solo es válido desde 1989. Antes
   está incompleto y es poco fiable — medido, de los 197 juegos completos dominicanos de los años
   sesenta solo 14 traen conteo, y de los 109 de los setenta solo 5. Sin este piso entraban tres
   juegos más, incluido uno de Marichal de 1971, con conteos que no valen.

2. **`P_OUT >= 27`.** `P_CG` marca «juego completo», y eso **incluye los acortados por lluvia**. Sin
   exigir las nueve entradas entraban 11 juegos más — entre ellos uno de Iván Nova de 57
   lanzamientos que son **16 outs**, o sea 5⅓ entradas. No es una joya, es un juego que se suspendió.

Su universo también es distinto: como el detector empieza en 1989, la `N` son los **251.106**
juegos-jugador de 1989 en adelante, no los 292.948 de toda la historia. Es la regla del grano (5.2.11)
aplicada al tiempo.

**Por qué `P_PITCH` y no `scastPitch`.** Se pidió usar `dbo.scastPitch`, pero esa tabla **empieza en
2008** y los juegos completos casi se extinguieron después: se perdería la mitad de la lista.
`retroDailyReg.P_PITCH` cubre desde 1989 y es completo desde entonces (178 de 189 en los noventa,
110 de 110 en los 2000, 90 de 90 en los 2010).

Se comprobó que las dos fuentes coinciden donde se solapan: de **131 juegos comparables, 115 dan el
mismo número** y 119 quedan dentro de dos lanzamientos. Las diferencias grandes parecen dobles juegos
en la unión por fecha, no discrepancias reales. `scastPitch` queda como verificación cruzada y como
puente al `game_pk` de MLB, no como fuente primaria.

#### 5.1.9. Los fouls y los pelotazos

Cuatro umbrales calculados con el mismo criterio: el entorno de **una vez por temporada**.

| detector | X | casos | por temporada | rareza | cobertura |
| --- | ---: | ---: | ---: | ---: | --- |
| `fouls_turno` | 10 | 10 | 0,53 | 493 | 2008+ |
| `fouls_juego` | 16 | 11 | 0,58 | 476 | 2008+ |
| `hbp_recibidos` | 2 | 120 | 1,03 | 372 | completa |
| `hbp_propinados` ⚠️ | 3 | 25 | 0,22 | 223 | completa |

Los descartes, para que no haya que volver a medirlos: 8 fouls en un turno son 4,95 por temporada;
14 en un juego, 2,05; 2 pelotazos propinados, 3,54. Todos demasiado corrientes.

Los topes dominicanos —**12 fouls en un turno, 19 en un juego, 3 pelotazos recibidos, 4
propinados**— entran por su detector y suben solos por magnitud.

**El signo de los pelotazos es un juicio, no un dato.** Los propinados van en negativo: hitear a tres
bateadores es un fallo de control. Los recibidos van en positivo, porque al bateador no le pasa por
culpa suya. Si preferís lo contrario, es cambiar un campo.

Los de fouls salen de `scastPitch.description` (`foul`, `foul_tip`, `foul_bunt`) y por eso solo ven
2008 en adelante. Los pelotazos salen de `B_HP` y `P_HP` del game log, con cobertura completa.

#### 5.1.10. `rv_bateo` y `rv_pitcheo` — el juego más valioso, sin umbrales de conteo

Idea del dueño, y es la mejor del inventario: en vez de preguntar «¿cuántos jonrones?» o «¿cuántos
hits?», sumar el **`RUN_VALUE` de todos los turnos** del jugador en ese juego. Da una sola medida de
cuánto produjo —o cuánto evitó— sin importar cómo.

| detector | umbral | casos | por temporada | rareza | `N` |
| --- | --- | ---: | ---: | ---: | ---: |
| `rv_bateo` | 5,0 carreras generadas | 94 | 0,81 | 378 | 220.653 |
| `rv_pitcheo` | 5,0 carreras evitadas | 40 | 0,34 | 402 | 71.046 |

**Lo que lo valida es que encuentra solo lo que ya sabíamos.** El mejor juego ofensivo de la historia
dominicana según esta métrica es **Alex Rodríguez, 26 de abril de 2005, 8,62 carreras de valor** —
exactamente el mismo juego que salió por el camino de las empujadas (3 jonrones, 10 RBI, 13 bases).
Dos métodos independientes, el mismo juego.

Y en pitcheo, **las tres mejores actuaciones son de Juan Marichal**, encabezadas por el **2 de julio
de 1963: 6,81 carreras evitadas** —el duelo de dieciséis entradas contra Warren Spahn— con Pedro
Martínez cuarto. Ningún umbral de conteo habría encontrado ese juego: no fue de 15 ponches ni de cero
hits, fue de aguantar dieciséis entradas.

| | |
| --- | --- |
| 8,62 | Alex Rodríguez, 2005-04-26 |
| 7,81 | Edwin Encarnación, 2015-08-29 |
| 7,50 | Sammy Sosa, 2002-08-10 |
| 6,81 | **Juan Marichal, 1963-07-02** (pitcheo) |
| 6,08 | Juan Marichal, 1966-05-26 (pitcheo) |

**Por qué `RUN_VALUE` y no `WPA`.** Miden cosas distintas y las dos están en `r24Events`: el valor de
carreras dice cuánto **produjo**, el WPA cuánto **acercó la victoria**. Un juegazo en una derrota de
12-2 tiene valor alto y WPA bajo. Acá se usa `RUN_VALUE` para el umbral —es la gesta— y el WPA sigue
alimentando el bono de impacto (4.3), que es donde el contexto debe pesar.

Cobertura completa, 1910–2025.

#### 5.1.11. `dobles3` — y por qué `extrabases4` no lo cubría

No lo teníamos. Había `extrabases4`, que suma dobles, triples y jonrones, y por eso **un juego de
tres dobles y nada más se le escapaba**: son tres extrabases, no cuatro.

| dobles | dominicanos | toda la liga |
| ---: | ---: | ---: |
| **3** | **133** (80 jugadores) | 1.962 |
| 4 | 3 | 53 |

**X = 3**: 136 juegos en total, **1,17 por temporada**, rareza 366 — la misma liga que `hits5` (1,32)
y `k12` (1,18). Con 4 quedarían tres juegos.

Los tres de cuatro dobles: Rafael Ramírez (1986-05-21, 4 de 4), Dámaso García (1986-06-27, 4 de 4) y
**Rafael Devers (2019-08-13, 4 dobles y 6 hits)**.

El de Devers es el ejemplo perfecto de por qué existe la regla de fusión (sección 7): ese mismo juego
ya estaba en la lista de 6 hits. Es **una** efeméride con dos etiquetas, no dos filas.

#### 5.1.12. `gidp3` — la doble matanza del bateador

Negativa, como `ponches5` y `cs3`.

| GIDP en un juego | dominicanos | toda la liga |
| ---: | ---: | ---: |
| 2 | 539 (165 jugadores) | 9.222 |
| **3** | **10** (10 jugadores) | 138 |
| 4 | **0** | 2 |

**X = 3**: diez juegos, 0,09 por temporada, rareza **245** en la escala negativa. Con 2 serían 549
juegos —4,73 por temporada— y eso no es efeméride, es un martes.

Ningún dominicano ha llegado a 4; en toda la liga solo ha pasado dos veces.

Los diez, con un detalle que el `detalle` debe cargar: **tres de ellos lo hicieron en solo 3 turnos**
—Teodoro Martínez (1974), Julio César Franco (1989) y José Bautista (2016)—, o sea que apagaron un
rally en cada aparición. También están Miguel Tejada, Plácido Polanco, Jean Segura, Jhonny Peralta,
Pedro Álvarez, Jesús Alou y **Albert Pujols** (2011-03-31).

#### 5.1.13. `gidp_inducidos` — la otra cara del `gidp3`

La misma jugada vista desde el montículo, y acá es **hazaña**: inducir dobles matanzas es salir de
los líos con un solo lanzamiento. `signo = +1`.

| inducidas en un juego | dominicanos | toda la liga |
| ---: | ---: | ---: |
| 3 | 160 (60 lanzadores) | 6.270 |
| **4** | **18** (14 lanzadores) | 868 |
| **5** | **1** | 82 |
| 6 | **0** | 5 |

**X = 4**: 19 juegos, 0,16 por temporada, rareza **460** — arriba del todo, entre el ciclo (457) y
los 15 ponches (468). Con 3 serían 179 juegos, 1,54 por temporada, que es zona corriente.

El récord dominicano: **Luis Perdomo, 28 de agosto de 2016 — cinco dobles matanzas inducidas en un
juego completo de una sola carrera limpia.** Ningún dominicano ha llegado a seis.

**Pedro Astacio aparece dos veces** (1992 y 1996), y el suyo del 3 de julio de 1992 fue juego
completo sin carreras limpias. Es el caso que `veces_jugador` convierte en «por segunda vez en su
carrera».

#### 5.1.6. Nadie ha bateado 4 jonrones

Los 64 juegos de `hr3` son **exactamente de 3**, por 36 jugadores. Ningún dominicano ha conectado
cuatro en un juego. Por eso el umbral se queda en 3 y no hay detector de 4 — el día que pase, la
magnitud (4.2) lo va a subir sola al tope de su tipo, igual que con los triples.

### 5.2. Gestas de evento (`r24Events`, `retroEventsReg`)

| detector | umbral | veces | rareza |
| --- | --- | ---: | ---: |
| `doble_slam` | 2 grand slams del mismo bateador en un juego | **1** | 600 |
| `triple_play_solo` | `TP_FL='T'`, los 3 outs del mismo fildeador, cero asistencias | **1** | 600 |
| `walkoff_slam` | walk-off de GRAND SLAM — ver 5.2.4 | 20 | 468 |
| `walkoff_2outs` | walk-off de jonrón, 2 outs, PERDIENDO | 22 | 464 |
| `hr_dentro_parque` | jonrón dentro del parque ⚠️ 2008+ | 22 | 456 |
| `hr480` | jonrón de 480+ pies ⚠️ 2015+ — ver 5.2.8 | 12 | 435 |
| `vel100` | 15+ rectas de 100 mph en un juego ⚠️ 2008+ — ver 5.2.8 | 40 | 392 |
| `walkoff_bb` | walk-off de boleto o golpeado | 28 | 453 |
| `robo_home` | robo de HOME — `rol = corredor` | 85 | 367 |
| `walkoff_hr` | walk-off de jonrón | 262 | 355 |
| `k4_inning` | 4 ponches en la misma entrada — ver 5.2.2 | 5 | 520 |
| `fouls_turno` | 10+ fouls en un turno ⚠️ 2008+ — ver 5.1.9 | 10 | 493 |
| `inmaculado` | 9 lanzamientos, 3 ponches ⚠️ 2008+ | 8 | 490 |
| `inning3lanz` | 3 lanzamientos, 3 outs ⚠️ 2008+ | 11 | 473 |
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

#### 5.2.4. Los walk-off, revisados contra la lista de MLB

De la lista de *game notes* de MLB salieron tres variantes que no teníamos, y **una corrección**.

| detector | veces | jugadores | rareza |
| --- | ---: | ---: | ---: |
| `walkoff_slam` | 20 | 17 | 468 |
| `walkoff_2outs` | 22 | 17 | 464 |
| `walkoff_bb` | 28 | 26 | 453 |
| `walkoff_hr` (ya estaba) | 262 | 100 | 355 |
| `walkoff` (ya estaba) | 955 | 232 | 299 |

**La corrección:** `walkoff_slam` estaba definido como «walk-off con 2 outs y bases llenas», que da
69 casos y **no es un walk-off grand slam** — la mayoría de esos 69 se ganaron con un sencillo. El
grand slam de verdad son **20**. Estaba mal desde que lo escribí y lo destapó cruzar el diseño contra
una lista externa.

`walkoff_bb` es la contraria y por eso vale: el juego se acaba con un boleto o un pelotazo, sin que
nadie batee. 28 veces.

#### 5.2.5. Cobertura parcial: cuando NO se puede decir cuántos hay

Regla del dueño. Cuatro detectores no ven toda la historia:

| detector | fuente | cobertura | veces |
| --- | --- | --- | ---: |
| `inmaculado` | `scastPitch` | **2008+** | 8 |
| `inning3lanz` | `scastPitch` | **2008+** | 11 |
| `hr_dentro_parque` | `scastPitch` (`des`) | **2008+** | 22 |
| `cg90` | `P_PITCH` | **1989+** | 8 |

**En estos, `veces_total` y `jugadores_total` van vacíos y el texto NO dice «uno de los N».** El
número que tenemos es el de la ventana que vemos, no el de la historia, y publicarlo como si fuera
total sería mentir con precisión decimal. Un inning inmaculado de 1985 existiría y no lo sabríamos.

Cada detector declara su `cobertura`; el motor la respeta sin que haya que acordarse caso por caso.
Lo que sí conservan es `orden_jugador` y `veces_jugador` —«por segunda vez en su carrera»— cuando el
jugador entero cae dentro de la ventana.

**Los inmaculados (8):** Rafael Soriano 2010, Juan Pérez 2011, Iván Nova 2013, Carlos Contreras 2014,
Santiago Casilla 2015, Juan Nicasio 2016, Dellin Betances 2017, Enyel De los Santos 2022.

**Los de 3 lanzamientos (11):** de Jesús Colomé (2008) a Blas Castaño (2026), pasando por Sandy
Alcántara y Luis Severino.

**El jonrón dentro del parque no está codificado en Retrosheet.** Se comprobó: ni `EVENT_TX` ni
`EVENT_CD` lo distinguen de uno por encima de la verja. Solo se detecta por el texto `des` de
Statcast, y de ahí que su cobertura sea 2008+.

#### 5.2.6. `robo_home` — y el quinto `rol`

**85 robos de home por 53 corredores dominicanos**, con cobertura completa: sale de
`retroEventsReg.RUN3_SB_FL`, que marca exactamente eso.

Obliga a un `rol` nuevo: **`corredor`**. El protagonista no batea ni lanza — está en tercera. Es el
mismo problema que destapó `triple_play_solo` con el fildeador, y la misma solución.

Su grano también es propio: la `N` son las **92.821** veces que un dominicano estuvo en tercera.

#### 5.2.8. Los dos de Statcast: `hr480` y `vel100`

Statcast permite dos gestas que Retrosheet no puede ver. Los umbrales se calcularon con el criterio
de 5.1.2 —cortar donde deja de ser rutina— buscando el entorno de **una por temporada**.

**`hr480` — el jonrón largo.** Las distancias van de **2015 a 2026, 12 temporadas**, sobre 8.549
jonrones dominicanos con medición:

| umbral | jonrones | por temporada | rareza |
| ---: | ---: | ---: | ---: |
| 460 pies | 102 | 8,50 | 293 |
| 470 pies | 34 | 2,83 | 366 |
| **480 pies** | **12** | **1,00** | **435** |
| 490 pies | 6 | 0,50 | 481 |

**480** da exactamente uno por temporada. Los cinco más largos: Nomar Mazara **505 pies** (2019),
Miguel Sanó 496, Jesús Sánchez 496, Miguel Sanó otra vez 495, Gary Sánchez 493.

**`vel100` — las rectas de 100 millas.** La velocidad va de **2008 a 2026, 19 temporadas**, sobre
42.494 juegos-lanzador:

| umbral | juegos | por temporada | rareza |
| ---: | ---: | ---: | ---: |
| 10+ rectas | 178 | 9,37 | 308 |
| **15+ rectas** | **40** | **2,11** | **392** |
| 20+ rectas | 6 | 0,32 | 499 |

**15** deja el detector en la liga de `hits5` (1,32) y `k12` (1,18). Con 20 quedarían solo 6 juegos —
está ahí si se prefiere más escaso.

El récord es de otra dimensión: **Yordano Ventura tiró 26 rectas de 100+ millas el 3 de octubre de
2014**, en postemporada. Le siguen Mauricio Cabrera y Jhoan Durán con 22.

Los dos son de cobertura parcial, así que **no publican totales** (5.2.5).

#### 5.2.10. `ciclo_natural` y `ciclo_inverso` — el orden importa

El ciclo pide los cuatro batazos; el **natural** los pide **en orden ascendente**: sencillo, doble,
triple, jonrón. Necesita `r24Events`, porque `retroDaily` solo dice cuántos hubo, no en qué orden.

Se detecta comparando el `EVENT_ID` del PRIMER batazo de cada tipo: natural si
`e(1B) < e(2B) < e(3B) < e(HR)`.

| | veces | jugadores |
| --- | ---: | ---: |
| ciclos (los cuatro batazos) | 20 | 16 |
| **ciclo natural** | **0** | 0 |
| **ciclo inverso** | **1** | 1 |

**Ningún dominicano ha bateado un ciclo natural en 116 años.** El detector se escribe igual y se deja
vacío, por lo mismo que `ponches6` (sección 8): cuesta nada y empieza a producir el día que pase.

**Pero hay un ciclo INVERSO** —jonrón, triple, doble, sencillo, en ese orden— que es la imagen espejo
y se celebra igual: **Carlos Gómez, 7 de mayo de 2008**, con Minnesota en Chicago. Único, así que
rareza 600.

**Y de paso, una comprobación que vale la pena registrar:** los 20 ciclos que cuenta `r24Events`
cuadran exactamente con los 20 de `retroDaily`. Son dos tablas distintas, con granos distintos,
llegando al mismo número. Cuando el detector de un lado y el del otro coinciden, la definición está
bien escrita.

#### 5.2.11. La `N` no depende del `rol`: depende del grano

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
| juegos-jugador con al menos una gesta | **1.264** |
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

## 11. Fuera de alcance

### 11.1. Descartado por decisión, no por dificultad

**Las gestas de EQUIPO.** La lista de *game notes* de MLB trae seis —remontar una desventaja de 7
carreras, 17+ carreras en un juego, 13+ entradas, tres jonrones seguidos, 8+ carreras en una entrada,
triple play— y el dueño las descartó el 2026-08-03.

La razón encaja con lo que es este archivo: **es de jugadores dominicanos, no de equipos**. Meterlas
obligaría a un `rol = equipo` sin `mlb_id`, y entonces la mitad del contrato —el nombre, los conteos
por jugador, el enlace a la ficha— se queda vacío. No es que no se pueda; es que sería otro archivo.

### 11.2. Pendiente, con el camino ya abierto

- **Triple plays con dominicano fildeando** de cualquier tipo: hay **68**, y saldrían por la misma
  vía que `triple_play_solo` ahora que el contrato tiene `rol`.
- **El Salón de la Fama dominicano.** `dglMaster.yearDomHof` da el año pero no el día, y una
  efeméride necesita fecha exacta. Son 24 de los 61 fallecidos, así que el dato existe y vale — lo
  que falta es la fecha.
