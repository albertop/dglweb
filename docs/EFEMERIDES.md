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

### 3.1. `rol` no es decorativo

El triple play sin asistencia lo hace **el fildeador**. Sin `rol`, el detector tendría que salir de
`BATTER_ID` y la efeméride quedaría atribuida al bateador rival — o sea, exactamente al revés de lo
que pasó. `rol = persona` es para cumpleaños, debut y fallecimiento, que no cuelgan de ningún juego.

### 3.2. Lo que un detector NO hace

No calcula puntaje. No escribe texto. No sabe que existen otros detectores. Si un detector necesita
saber algo de eso, el diseño está mal.

---

## 4. El puntaje: 0–1000

### 4.1. Rareza (0–600) — la columna vertebral

**No se asigna a mano: se mide.**

```
rareza = 600 × (1 − log(n) / log(N))
```

`n` = cuántas veces ocurrió esa gesta en 116 temporadas. `N` = el universo del detector
(**292.948** juegos-jugador para las de juego, **822.764** turnos para las de evento).

La propiedad que importa: **un detector nuevo se calibra solo**. Si mañana se agrega uno que dispara
5.000 veces, se hunde solo y no inunda el calendario. Nadie tiene que sentarse a decidir cuánto vale.

### 4.2. Magnitud (0–200)

Dentro del tipo, qué tan lejos del umbral, por percentil de la propia distribución. Cuatro jonrones
pesan más que tres sin que haya que escribir una regla para el cuatro.

### 4.3. Impacto (0–150)

El `WPA` del jugador en ese juego. Es la **misma vara para todos los tipos**: un ciclo en una paliza
de 14-2 vale menos que uno que ganó el juego. Sale directo de `r24Events`, no se calcula.

### 4.4. Relieve dominicano (0–50)

«Primer dominicano en…», «único dominicano con…». Se computa comparando el hecho contra el resto del
archivo, una vez que todos los detectores corrieron.

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

## 5. El inventario: 37 detectores

| grupo | detectores |
| --- | ---: |
| gestas de juego (5.1) | 19 |
| gestas de evento (5.2) | 7 |
| hitos de carrera (5.4) | 7 |
| fechas de persona (5.5) | 4 |

`N` de juego = 292.948 · `N` de evento = 822.764. La columna *rareza* es lo que da la fórmula hoy;
el exportador la recalcula en cada corrida.

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
| `turno_clave` | `LI >= 2` **y** `WPA >= 0.40` | 154 | — |
| `grand_slam` | `HR=1` y `RBI=4` | 520 | 325 |
| `walkoff` | último turno, en casa, 9no o más, WPA positivo | 938 | 299 |

**Los dos de `n=1` son los que dan sentido a todo esto:**

- **`doble_slam`** — Fernando Tatís, 23 de abril de 1999, **los dos en el mismo inning**. Es el
  récord de Grandes Ligas y nadie más lo ha hecho nunca.
- **`triple_play_solo`** — Rafael Furcal, 10 de agosto de 2003, campocorto, quinto inning. De los
  13 sin asistencia que cubre Retrosheet, uno es dominicano.

### 5.3. El corte de `turno_clave`, medido

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

**818 cruces.** Es la efeméride clásica —«un día como hoy, X llegó a su jonrón 300»— y está fechada
al día exacto. Se detecta con una suma acumulada por jugador ordenada por fecha, buscando el juego
en que el total cruza un múltiplo del escalón.

| detector | escalón | cruces |
| --- | ---: | ---: |
| `hito_hit` | 500 | 264 |
| `hito_hr` | 100 | 134 |
| `hito_k` (lanzador) | 500 | 115 |
| `hito_sb` | 100 | 86 |
| `hito_rbi` | 500 | 85 |
| `hito_sv` | 50 | 73 |
| `hito_win` | 50 | 61 |

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
| hitos de carrera | 818 |
| cumpleaños + debut + fallecimiento + Juego de Estrellas | ~2.250 |
| **total aproximado** | **~6.300** |

Bien por debajo de 5 MB. Para comparar: `dom_players` ya carga 9.133 filas por esta misma vía.

**Idempotencia:** misma base, mismo CSV. Al correrlo tras la actualización de Retrosheet, la pantalla
de comparación enseña exactamente lo que agregó la temporada nueva y nada más.

---

## 10. Supuestos que tomé, y cómo cambiarlos

Ninguno de estos está confirmado por el dueño. Están acá para que se vean, no escondidos en el
código.

1. **Los hitos de carrera cuentan solo temporada regular.** Es como se cuentan oficialmente. Si la
   postemporada debe sumar, cambia el `UNION` del detector de hitos y los 818 cruces se recalculan.
2. **Los 18 debutantes de 2026 sí aparecen** con cumpleaños y debut, porque esas fechas salen de
   `dglMaster` y no de Retrosheet. No tendrán gestas hasta que Retrosheet les asigne `retroID`. Si se
   prefiere que no aparezcan del todo hasta entonces, es un `WHERE retroID IS NOT NULL` en los tres
   detectores de persona.
3. **La postemporada entra** en todas las gestas, con bono de contexto. Aporta poco en conteo
   —7 hechos de 549, y 4 de 154 momentos— porque son 1.878 juegos contra 203.908. Su valor está en
   que esos pocos son de octubre.

## 11. Fuera de alcance, por ahora

- **El inning inmaculado** (9 lanzamientos, 3 ponches). `r24Events_PitchCount` tiene 7.107.316 filas
  y probablemente lo soporta, pero no se ha medido si el conteo por lanzamiento alcanza para
  identificarlo con seguridad.
- **Triple plays con dominicano fildeando** de cualquier tipo: hay **68**, y saldrían por la misma
  vía que `triple_play_solo` ahora que el contrato tiene `rol`.
- **El Salón de la Fama dominicano.** `dglMaster.yearDomHof` da el año pero no el día, y una
  efeméride necesita fecha exacta.
