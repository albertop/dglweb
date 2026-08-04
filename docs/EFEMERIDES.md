# Efemérides dominicanas

Un archivo estático, generado una vez al año, con lo que pasó **un día como hoy** en Grandes Ligas
protagonizado por dominicanos. El sitio no calcula nada: filtra por mes y día, ordena por puntaje y
pinta.

Este documento es el diseño. Todos los números que aparecen abajo están **medidos contra `DGL` en
SQL Server**, no estimados. Última revisión completa: **2026-08-04**, con 96 detectores corriendo.

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

Son **25 columnas**, y la lista vive en la constante `$CONTRATO` del motor. Si a un detector le falta
una, la corrida **aborta entera** en vez de colar filas mutiladas que nadie va a mirar hasta que
salgan mal en la página. Si devuelve una de más, el motor **avisa** y sigue: casi siempre es una
columna mal nombrada.

**Las que declara el detector:**

| columna | qué es |
| --- | --- |
| `tipo` | el slug del detector: `ciclo`, `hr3`, `walkoff`, `hito_hr`… |
| `gesta` | qué se cuenta, en palabras: «5+ hits en un juego» — ver 3.7 |
| `rol` | `bateador` \| `lanzador` \| `fildeador` \| `corredor` \| `persona` — ver 3.1 |
| `cobertura` | `completa` \| `parcial` — hasta dónde alcanza su fuente, ver 5.3 |
| `universo` | la `N` de la rareza, que depende del **grano** — ver 5.11 |
| `plantilla` | la forma del titular, con marcadores `{campo}` — ver 3.4 |
| `situar` | `0` \| `1` \| `2` — si la frase «uno de los N» aplica, ver 3.5 |
| `mlb_id` | el jugador, ya traducido desde `retroID` por `dglMaster` |
| `nombre` | de `dglMaster.nameList`, SIEMPRE — ver 3.0 |
| `fecha` | la del juego, o la del cumpleaños/debut/fallecimiento |
| `temporada` | |
| `game_id`, `event_id` | de Retrosheet; `event_id` es 0 en las gestas de juego completo |
| `game_type` | `R` \| `P` \| `A` (Juego de Estrellas) \| `-` (sin juego) |
| `equipo`, `rival`, `en_casa` | los códigos de Retrosheet |
| `equipo_nombre`, `rival_nombre` | el nombre de la época, resuelto por el preludio — ver 3.6 |
| `oponente` | el lanzador o bateador al que enfrentó, cuando la gesta es de un turno |
| `signo` | `+1` hazaña, `-1` deshonra — ver 4.5 |
| `magnitud` | el número que define la gesta: 3 jonrones, 15 ponches, 0,87 de WPA |
| `wpa_jugador` | cuánto movió la probabilidad de ganar ese juego |
| `li_max` | el leverage más alto en que estuvo |
| `detalle` | los datos propios del tipo, para el texto |

**Las que agrega el motor**, y que ningún detector podría saber porque dependen de todas las filas de
su tipo y él solo ve las suyas:

| columna | qué es |
| --- | --- |
| `veces_total` | cuántas veces ha pasado en la historia dominicana — ver 3.3 |
| `jugadores_total` | cuántos dominicanos DISTINTOS lo han hecho |
| `orden` | qué número es esta, en orden cronológico. `1` = la primera vez |
| `veces_jugador` | cuántas veces lo ha hecho ESTE jugador |
| `orden_jugador` | cuál de las suyas es esta |
| `rareza`, `puntaje` | la sección 4 |
| `mes`, `dia`, `anos` | derivados de `fecha`, para que el sitio filtre sin parsear |
| `titular`, `situacion` | el texto ya redactado — ver 3.4 |
| `etiquetas` | los otros tipos que dispararon sobre el mismo hecho — ver 7 |

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

`robo_home` (5.2) estrenó el quinto: **`corredor`**. Quien roba home no batea ni lanza, está en
tercera. Dos detectores han obligado ya a ampliar esta lista, así que conviene asumir que habrá más.

`rol = persona` es para cumpleaños, debut y fallecimiento, que no cuelgan de ningún juego.

**El `rol` no tiene por qué ser constante dentro de un detector.** `estrellas_actuacion` (5.2.12) lo
decide fila por fila —`CASE WHEN a.P_OUT > 0 THEN 'lanzador' ELSE 'bateador' END`— porque en el Juego
de Estrellas la misma consulta recoge al que dio el jonrón y al que se llevó la victoria. El contrato
pide una columna, no una constante.

La familia de alineaciones (5.2.13) usa `fildeador` para gestas que no son de un fildeo sino de una
**foto de la defensa**. Es el rol correcto igual: nadie bateó ni lanzó, estaban parados en el terreno.

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
| `sombrero_platino` | 20 | 17 | 1,18 |
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

### 3.4. El texto: la plantilla la declara el detector, la rellena el motor

El diseño original decía que el detector «no escribe texto». En la práctica eso obligaba a poner la
redacción en el motor, y entonces agregar una efeméride dejaba de ser tocar un solo archivo — que es
la propiedad que sostiene todo esto (sección 8).

La solución conserva las dos cosas: el detector declara la **forma** como una constante de su
`SELECT`, con marcadores; el motor los rellena con los valores de la fila.

```sql
'Conectó 3 jonrones contra {rival_nombre}: {detalle}.' AS plantilla,
```

El detector no redacta ni sabe de conteos: declara la forma y el motor la completa con lo que el
detector no puede saber. Así la consulta y su texto se leen juntos, de un vistazo, en el mismo
archivo.

El motor produce **dos** campos de texto y el sitio los pinta seguidos:

| campo | de dónde sale |
| --- | --- |
| `titular` | la plantilla del detector, con los `{campo}` sustituidos |
| `situacion` | la frase «uno de los N dominicanos…», que arma el motor — ver 3.5 |

Una autocomprobación (8.1) verifica que **ninguna fila publicada conserve un `{campo}` sin rellenar**:
una plantilla mal escrita deja el marcador crudo en la página, y eso se ve.

### 3.5. `situar` tiene TRES estados, no dos

Dice si la frase «uno de los N dominicanos que lo ha logrado» tiene sentido para esa gesta. Lo
declara el detector porque es lo único que él sabe. **No se puede decidir por `rol`**: `debut` también
es `rol = persona` y ahí la frase sí vale.

| valor | qué significa | quién lo usa |
| ---: | --- | --- |
| **1** | la frase aplica siempre | los 55 detectores de gesta |
| **0** | la frase no aplica nunca | `cumpleanos`, `fallecimiento`, la familia de alineaciones, `primero_posicion` |
| **2** | solo si es **el primero o el único** | `debut` y los 7 hitos de carrera |

**El `2` apareció con el debut y es el estado que el diseño no tenía.** Los 984 del maestro debutaron,
así que «Es uno de los 984 dominicanos que lo ha logrado» no dice absolutamente nada. Pero «Fue el
primer dominicano en llegar a Grandes Ligas» es de las mejores efemérides del archivo, y se perdía
entera si el detector se apagaba con `situar = 0`. Con `2` el motor calla en las 983 y habla en la
que importa.

**El `0` de las colectivas es distinto y llegó después.** `jardin_dominicano`, `cuadro_dominicano` y
`seis_dominicanos` publicaban «Fue el primer dominicano en lograrlo» para gestas de tres, cuatro o
seis hombres a la vez. La frase del motor habla en singular por construcción, y acá el sujeto es
plural: no hay valor de `situar` que la arregle. Lo que sí valía —que fue la primera vez que se vio—
se calcula dentro del propio `.sql` y se pega al titular.

`primero_posicion` lleva `0` por lo contrario: su titular **ya dice** que fue el primero, y añadirle
«fue el primer dominicano en lograrlo» sería repetirlo con otras palabras.

### 3.6. Los nombres de equipo son los de la época, no los de hoy

Pedido del dueño: la efeméride tiene que decir contra quién fue. Y decirlo bien — Felipe Alou jugó
para los **San Francisco Giants**, no para «SFN», y quien enfrentó a los Montreal Expos en 1979 no
enfrentó a los Washington Nationals.

El preludio `_00_comun.sql` arma la tabla `#equipos` con el nombre **vigente en cada rango de
fechas**, y los detectores la cruzan por código *y* por fecha:

```sql
LEFT JOIN #equipos eq ON eq.codigo = g.HOME_TEAM_ID
                     AND f.fecha BETWEEN eq.desde AND eq.hasta
```

Hacen falta **las dos tablas de equipos**, y esto se midió: `retroTeams_6d` da los rangos de fechas
por franquicia pero no cubre todos los códigos; `retroTeams` cubre 292 códigos pero sin rango. Con
solo la primera quedaban **131 pares equipo-fecha sin resolver** de 158.127. Se usa `retroTeams_6d`
y se cae a `retroTeams` cuando no hay rango.

**El centinela de `lastGame`.** En `retroTeams_6d`, un `lastGame` de `1899-12-30` significa **equipo
vigente**, no que dejó de jugar en 1899. Regla del dueño. Sin traducirlo a «hasta hoy», todos los
equipos actuales quedaban fuera de rango y ninguna efeméride moderna resolvía su nombre.

### 3.7. `gesta`: la frase tiene que decir QUÉ se cuenta

El campo más joven del contrato, y salió de un error que estuvo publicado meses:

> Disparó 6 hits contra Detroit Tigers: 6 turnos, 4 empujadas.
> *Es uno de los 93 dominicanos que **lo** ha logrado.*

**Noventa y tres dominicanos no han dado 6 hits en un juego: han dado CINCO O MÁS**, que es donde
`hits5` puso su corte. El titular habla del caso concreto y el denominador cuenta la categoría, así
que el «lo» los pegaba mal. El dueño lo cazó sobre tres detectores a la vez —`hits5`, `k12` con 14
ponches contra un umbral de 12, y `k15` con 17 contra 15—.

**El motor no puede deducirlo.** Solo el `.sql` sabe dónde puso su corte, así que la gesta la declara
el detector, igual que la `plantilla`. Es un sintagma nominal, no una oración, para que encaje en las
tres construcciones:

| | |
| --- | --- |
| resto | «Es uno de los 93 dominicanos **con 5+ hits en un juego**.» |
| primero | «Fue el primer dominicano **con 3+ jonrones en un juego**.» |
| único | «Es el único dominicano **con un juego perfecto**.» |

**Lo que se perdió al hacerlo, y por qué se aceptó.** La construcción con «con» no tiene verbo, así
que desaparece la distinción entre «lo ha logrado» y «le ha pasado» que se había introducido para las
deshonras (4.5). Se aceptó porque decir QUÉ se cuenta importa más que el matiz del verbo — y porque
el matiz no se pierde del todo: sobrevive en la coletilla, que sigue diciendo «Para él fue la 3ª de
sus 5 veces» o «A él le pasó 3 veces» según el signo.

Una autocomprobación (8.1) verifica que **ningún detector que sitúa deje la gesta vacía**: la frase se
arma con ella dentro, así que sin gesta no sale incompleta, sale rota.

---

## 4. El puntaje: 0–1000

### 4.1. Rareza (0–600) — la columna vertebral

**No se asigna a mano: se mide.**

```
rareza = 600 × (1 − log(n) / log(N))
```

`n` = cuántas veces ocurrió esa gesta en 116 temporadas. `N` = el universo del detector, y **no es
uno solo: depende del grano** — 292.948 juegos-jugador, 822.764 turnos al bate, 622.652 bateadores
enfrentados, 162.797 medias entradas lanzadas. Ver 5.11.

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

### 4.5. Los hechos negativos corren a MEDIA ESCALA EN TODO

Medido: **ponchar 5 veces en un juego es exactamente tan raro como batear el ciclo** — 20 veces cada
uno. La fórmula de rareza les daría el mismo 457, porque la rareza no distingue una hazaña de una
vergüenza.

`signo = -1` cambia **cuatro** cosas, y las tres últimas se descubrieron corriendo el motor:

| componente | positivo | negativo |
| --- | ---: | ---: |
| rareza | 0–600 | **0–300** |
| magnitud | 0–200 | **0–100** |
| impacto | 0–150 | **0** |
| relieve | 0–50 | **0** |
| **techo** | **1000** | **400** |

**El diseño solo partía la rareza, y no alcanzaba.** Con 33 detectores corriendo salió el caso que lo
prueba: `cs3` —atrapado robando tres veces, cosa que pasó **una sola vez** en la historia dominicana—
sacaba **550** y le empataba a un juego de **tres jonrones** (552). La rareza estaba correctamente
partida; lo que lo subía era todo lo demás.

- **La magnitud tenía que partirse igual.** Con `n = 1` el percentil satura en el tope de su tipo, así
  que `cs3` cobraba los 200 completos. A media escala cobra 100.
- **El relieve no se da nunca.** Ser «el único dominicano al que le ha pasado» no es un honor, y
  premiarlo era la otra mitad de lo que ponía a `cs3` a la altura de un juegazo.
- **El impacto ya estaba fuera** por el diseño: usar el valor absoluto del WPA premiaría la mala
  noche, que es exactamente al revés.

Hoy `cs3` saca **400** —el techo exacto de su escala— y queda por debajo de cualquier gesta real. Una
autocomprobación (8.1) verifica en cada corrida que **ninguna deshonra pase de 400**.

**Y el verbo también cambia con el signo.** La primera versión decía «lo ha logrado» para todo, y la
muestra de redacción lo dejó en evidencia: *«Bateó para 3 dobles matanzas… Fue el primer dominicano
en lograrlo»*. Nadie **logra** un ponche; a una deshonra **le pasa**.

| | positivo | negativo |
| --- | --- | --- |
| único | «Es el único dominicano que lo ha logrado.» | «Es el único dominicano al que le ha pasado.» |
| primero | «Fue el primer dominicano en lograrlo.» | «Fue el primer dominicano al que le pasó.» |
| resto | «Es uno de los N dominicanos que lo ha logrado.» | «Le ha pasado a N dominicanos.» |

El sitio recibe el `signo` y los puede presentar aparte, sin mezclarlos con las gestas.

### 4.6. Cumpleaños, debut y fallecimiento

La rareza no significa nada acá: todo el mundo tiene cumpleaños. **Y no hizo falta una escala aparte
para eso** — el propio mecanismo los hunde solo, que es la propiedad de la sección 4.1.

Su universo es `N = 984`, el maestro entero, y su magnitud es la **huella del jugador**: los juegos de
su carrera, contados en `retroDailyReg`, para que el cumpleaños de Pedro Martínez no pese igual que el
de alguien con tres juegos. Nadie mantiene una lista de «importantes».

| detector | `n` | rareza | puntaje máximo |
| --- | ---: | ---: | ---: |
| `debut` | 984 de 984 | **0,0** | 200 |
| `cumpleanos` | 923 de 984 | **5,6** | 206 |
| `fallecimiento` | 61 de 984 | **242,1** | **442** |

Con `n` casi igual a `N` la rareza se va a cero por construcción, y lo que queda es la magnitud: puro
tamaño de carrera, 0–200. Es exactamente el techo de 250 que el diseño quería, sin escribir la regla.

#### 4.6.1. El fallecimiento necesitó universo propio, y el error era de planteamiento

Con `N = 984` la fórmula veía 61 de 984 y decía «esto es raro»: **242 de rareza y techo 442**. Eso lo
ponía por encima de gestas reales —`robo_home` tiene techo 397 y `jardin_dominicano` 374— y rompía el
principio de que una fecha de persona nunca desplace a una hazaña.

**No era un problema de calibración sino de pregunta mal hecha.** «¿Qué tan raro es que un dominicano
tenga aniversario de fallecimiento?» solo tiene sentido **entre los que fallecieron**, y entre ellos
la respuesta es «todos». Con el universo correcto —los 61— la rareza se va a **cero** por
construcción y el puntaje lo pone entero la magnitud, exactamente igual que en el cumpleaños y el
debut:

| detector | `N` | `n` | rareza | puntaje máximo |
| --- | ---: | ---: | ---: | ---: |
| `debut` | 984 | 980 | 0,4 | 200 |
| `cumpleanos` | 984 | 905 | 7,3 | 207 |
| `fallecimiento` | **61** | 61 | **0,0** | **200** |

Los tres quedan por debajo de la gesta más baja del inventario (`debut_dificil`, 348), que es donde
tienen que estar.

**La cifra se cuenta, no se escribe.** El detector calcula su universo con
`SELECT COUNT(1) FROM dglMaster WHERE deathDate IS NOT NULL`: sube sola cada vez que muere un
pelotero. Un `61` fijo se quedaría viejo en silencio, dando rareza positiva sin que nadie se entere.

Es la regla del grano (5.11) aplicada bien, y vale para cualquier detector futuro cuya pregunta solo
tenga sentido dentro de un subconjunto.

### 4.7. Los hitos de carrera se puntúan por el número

Un hito no tiene «rareza de evento»; tiene **rareza de cifra**. El puntaje sale de cuántos
dominicanos han llegado alguna vez a ese número. El hit 3000 pesa lo que pesa porque lo han hecho
dos.

---

## 5. El inventario: 96 detectores

| grupo | detectores |
| --- | ---: |
| gestas de juego (5.1) | 27 |
| gestas de evento (5.2) | 17 |
| gestas de Statcast (5.3) | 3 |
| gestas colectivas (5.4) | 6 |
| hitos de carrera (5.5) | 10 |
| hitos de temporada (5.6) | 10 |
| debut, edad y Juego de Estrellas (5.7) | 8 |
| fuera de sitio: el que no debería estar ahí (5.8) | 4 |
| fechas de persona y primicias (5.9) | 4 |
| quiebre de no-hitter y de perfecto (5.10) | 4 |
| ⚠️ diseñados y **nunca construidos** (5.12) | 7 |

> **DÓNDE VIVE EL PORQUÉ DE CADA UMBRAL.** En su propio `.sql`, no acá. Cada detector abre con un
> bloque de comentario que trae la distribución medida, el umbral elegido, los umbrales descartados y
> el récord dominicano. No es duplicación evitada por pereza: el umbral y la consulta que lo aplica
> tienen que leerse juntos, o la próxima persona cambia uno sin enterarse del otro. Este documento
> guarda las REGLAS; los `.sql` guardan las MEDICIONES.

`n` es lo que devuelve el detector; `filas` es lo que queda tras la fusión (sección 7), que es menos
porque un mismo hecho puede dispararse en varios detectores. La rareza es la que da la fórmula hoy —
el exportador la recalcula en cada corrida.

### 5.1. Gestas de juego (grano juego-jugador, `N` = 292.948)

| detector | gesta declarada | n | rareza |
| --- | --- | ---: | ---: |
| `perfecto` | un juego perfecto | 1 | **600** |
| `cg90` ⚠️ | un juego completo de menos de 90 lanzamientos | 5 | 522 |
| `toques3` | 3+ toques de sacrificio en un juego | 6 | 515 |
| `no_hitter` | un juego sin hits | 10 | 490 |
| `anotadas5` | 5+ carreras anotadas en un juego | 12 | 482 |
| `robadas4` | 4+ robos en un juego | 14 | 474 |
| `k15` | 15+ ponches en un juego | 16 | 468 |
| `cg_extra` | un juego completo de más de nueve entradas | 17 | 465 |
| `gidp_inducidos` | 4+ dobles matanzas inducidas en un juego | 19 | 460 |
| `cg_1hit` | un juego completo de un solo hit | 25 | 447 |
| `extrabases4` | 4+ extrabases en un juego | 33 | 433 |
| `cg_dominante` | un juego completo con 10+ ponches y cero limpias | 41 | 423 |
| `hits_sin_limpias` | 8+ hits permitidos sin una carrera limpia | 40 | 424 |
| `rbi7` | 7+ empujadas en un juego | 43 | 421 |
| `hr3` | 3+ jonrones en un juego | 64 | 402 |
| `k10_bb4` | 10+ ponches y 4+ boletos en un juego | 73 | 396 |
| `boletos4` | 4+ boletos en un juego | 75 | 394 |
| `triples2` | 2+ triples en un juego | 75 | 394 |
| `hbp_recibidos` | 2+ pelotazos recibidos en un juego | 120 | 372 |
| `dobles3` | 3+ dobles en un juego | 136 | 366 |
| `k12` | 12+ ponches en un juego | 137 | 366 |
| `salvado_largo` | un salvado de 3+ entradas | 146 | 363 |
| `hits5` | 5+ hits en un juego | 153 | 360 |
| `blanqueada` | una blanqueada en juego completo | 271 | 333 |
| `cs3` ⚠️ | 3+ veces atrapado robando en un juego | 1 | **300** |
| `gidp3` ⚠️ | 3+ dobles matanzas bateadas en un juego | 10 | **245** |
| `sombrero_platino` ⚠️ | 5 ponches en un juego | 20 | **229** |
| `hbp_propinados` ⚠️ | 3+ pelotazos propinados en un juego | 25 | **223** |
| `paliza` ⚠️ | una salida de una carrera por bateador enfrentado | 79 | **196** |
| `sombrero_titanio` ⚠️ | 6+ ponches en un juego | **0** | — |

⚠️ = escala negativa (4.5), salvo `cg90` que lleva universo propio (251.106, desde 1989).

#### 5.1.1. El sombrero dorado se estrechó dos veces, y al final quedó uno

El detector más ruidoso que ha tenido el inventario: 499 filas, 4,30 por temporada. El dueño lo marcó
como demasiado y tenía razón. Pasó por tres versiones y las dos primeras están retiradas:

| versión | n | qué pedía | |
| --- | ---: | --- | --- |
| `sombrero_dorado` | 499 | 4 ponches, daba igual cuántas veces fue al plato | retirada |
| `sombrero_puro` | 231 | 4 ponches en **4 apariciones exactas** — ni una vez en base | retirada |
| **`sombrero_mismo_lanzador`** | **28** | los 4 ponches **del mismo hombre** (5.2) | vive |

**Por qué no bastó la segunda.** Exigir 4-de-4 partió la lista por la mitad, pero con 231 filas seguía
siendo el detector más abundante del archivo con diferencia. Y el problema de fondo no era el número:
poncharse cuatro veces contra cuatro lanzadores distintos es una mala tarde repartida, no una
historia. Que te ponche cuatro veces **el mismo hombre** sí lo es — no es que el bateador estuviera
mal, es que el otro pudo con él cada vez que se vieron.

Los escalones de arriba —`sombrero_platino` (5) y `sombrero_titanio` (6+, que nadie ha alcanzado)—
siguen en pie sin pedir un solo lanzador: a esa altura el número ya basta. Y son **exactos, no
acumulativos**: en la jerarquía real un juego de cinco ponches es platino, no dorado.

**Efecto en el archivo:** las efemérides negativas bajaron de 379 a 166. El sombrero pasó de ser un
tercio de las deshonras a ser una de tantas.

### 5.2. Gestas de evento (grano turno al bate, `N` = 822.764)

| detector | gesta declarada | n | rareza |
| --- | --- | ---: | ---: |
| `doble_slam` | dos grand slams en el mismo juego | 1 | **600** |
| `triple_play_solo` | un triple play sin asistencia | 1 | **600** |
| `perfecto_roto` | el embasado que rompió un juego perfecto en el noveno | 2 | 570 |
| `nohit_roto` | el hit que rompió un no-hitter en el noveno | 13 | 487 |
| `walkoff_slam` | un walk-off de grand slam | 20 | 468 |
| `walkoff_2outs` | un walk-off de jonrón con dos outs y perdiendo | 22 | 464 |
| `walkoff_sin_batear` | un walk-off sin batear la pelota | 28 | 453 |
| `ciclo` | un ciclo | 20 | 457 |
| `ciclo_inverso` | un ciclo inverso | 1 | **600** |
| `ciclo_natural` | un ciclo natural | **0** | — |
| `grand_slam_vs_dominicano` | un grand slam ante un lanzador dominicano | 53 | 425 |
| `walkoff` | un walk-off estando abajo en el marcador | 108 | 394 |
| `turno_clave` | un batazo que decidió un juego | 153 | 378 |
| `walkoff_hr` | un walk-off de jonrón | 262 | 355 |

Con universo propio, porque el grano es otro (5.11):

| detector | gesta | `N` | n | rareza |
| --- | --- | ---: | ---: | ---: |
| `k4_inning` | 4 ponches en una sola entrada | 162.797 | 5 | 520 |
| `nobletiger` | un escape de bases llenas sin outs en el noveno o más allá | 622.652 | 45 | 429 |
| `robo_home` | un robo de home | 92.821 | 85 | 367 |
| `hr_primer_turno` | un jonrón en su primer turno de Grandes Ligas | 723 | 15 | 353 |
| `sombrero_mismo_lanzador` ⚠️ | 4 ponches del mismo lanzador en un juego | 292.948 | 28 | **221** |
| `sombrero_propinado` | ponchar 4 veces al mismo bateador en un juego | 292.948 | 25 | 447 |

#### 5.2.1. `walkoff` pide estar PERDIENDO, y los hermanos no

El catch-all de los walk-off daba 621 filas. Medido sobre los 955 walk-off dominicanos:

| | n |
| --- | ---: |
| con el juego **empatado** | 847 |
| **perdiendo** | **108** |

Ocho de cada nueve son con el marcador igualado, y ahí el batazo rompe un empate: es la forma normal
en que termina un juego cerrado. Estar abajo y ganarlo en el mismo turno obliga a empujar la carrera
del empate y la de la ventaja de una sola vez — o sea, un extrabase con gente en base.

Como el equipo de casa no puede estar ganando cuando batea en el noveno o más allá —el juego ya
habría terminado— «no empatado» y «perdiendo» son la misma condición.

**Los hermanos no cambiaron**: `walkoff_hr`, `walkoff_slam` y `walkoff_sin_batear` siguen cubriendo
los empatados dentro de su propia forma, que es lo que los hace específicos. `walkoff_2outs` ya pedía
«perdiendo» y ahora es un subconjunto estricto del general.

#### 5.2.2. El mismo duelo visto por los dos lados

`sombrero_mismo_lanzador` (el bateador) y `sombrero_propinado` (el lanzador) son el mismo hecho con
el signo invertido. Y eso creó un problema que la fusión no puede resolver: **cuando los dos son
dominicanos, la misma noche saldría dos veces**, una por cada protagonista, porque la clave de fusión
lleva el `mlb_id` y son dos jugadores distintos.

Pasa **una sola vez** en 116 temporadas: Pedro Martínez ponchando cuatro veces a Alfonso Soriano el
16 de octubre de 2003, séptimo juego de una serie de campeonato. Se calla el lado del bateador y
habla el del lanzador, que es la versión positiva y además nombra a los dos.

Es el mismo patrón que `nohit_roto` / `nohit_perdido` y `perfecto_roto` / `perfecto_perdido` — con la
diferencia de que en esos el choque dominicano-contra-dominicano todavía no ha ocurrido.

### 5.3. Gestas de Statcast — cobertura PARCIAL

| detector | gesta | cobertura | n | rareza |
| --- | --- | --- | ---: | ---: |
| `inmaculado` | un inning inmaculado | **2008+** | 8 | 490 |
| `inning3lanz` | una entrada de tres lanzamientos | **2008+** | 10 | 478 |
| `hr_dentro_parque` | un jonrón dentro del parque | **2008+** | 21 | 458 |

**Declaran `cobertura = 'parcial'` y por eso NO publican totales.** El número que tenemos es el de la
ventana que vemos, no el de la historia, y publicarlo como total sería mentir con precisión decimal:
un inning inmaculado de 1985 existiría y no lo sabríamos. El motor lo respeta solo — vacía
`veces_total` y `jugadores_total`, y `Get-Situacion` devuelve cadena vacía.

**El jonrón dentro del parque no está codificado en Retrosheet.** Se comprobó: ni `EVENT_TX` ni
`EVENT_CD` lo distinguen de uno por encima de la verja. Solo se ve en el texto `des` de Statcast.

#### 5.3.1. El conteo de lanzamientos: Retrosheet hasta 2007, Statcast desde 2008

Regla del dueño, y salió de un error publicado. `cg90` decía que Framber Valdez había lanzado un juego
completo de **71 lanzamientos**; la crónica del día decía 83. Contra Statcast, que cuenta uno por uno:

| | `P_PITCH` | Statcast |
| --- | ---: | ---: |
| Sandy Alcántara 2019-05-19 | 89 | **89** ✔ |
| Domingo Germán 2023-06-28 — **el perfecto** | 73 | **99** |
| Framber Valdez 2025-05-30 | 71 | **84** |
| Cristopher Sánchez 2025-07-22 | 87 | **106** |

`retroDailyReg.P_PITCH` **subcuenta en los juegos modernos**, y no por poco: al juego perfecto le
faltaban veintiséis lanzamientos. **Tres de los ocho juegos que `cg90` publicaba no calificaban.**

Esto corrige lo que este mismo documento afirmaba antes —que las dos fuentes coincidían donde se
solapan—. Coinciden en volumen, no en los extremos, que es justo donde vive un detector de mínimos.
Antes de 2008 no hay alternativa y se sigue usando `P_PITCH`.

### 5.4. Gestas colectivas — cuando la efeméride no es de un hombre

| detector | gesta | grano | `N` | n | rareza |
| --- | --- | --- | ---: | ---: | ---: |
| `cuadro_dominicano` | el cuadro entero dominicano | juego-equipo | 407.816 | 12 | 485 |
| `seis_dominicanos` | seis dominicanos en el terreno a la vez | juego-equipo | 407.816 | 15 | 474 |
| `dominicanos_juego` | 10+ dominicanos en un mismo juego | juego | 203.908 | 54 | 404 |
| `lanzadores_equipo` | 4+ lanzadores dominicanos en un mismo equipo | juego-equipo | 407.816 | 96 | 388 |
| `jardin_dominicano` | el jardín entero dominicano | juego-equipo | 407.816 | 131 | 374 |
| `lanzadores_juego` | 5+ lanzadores dominicanos en un juego | juego | 203.908 | 136 | 359 |

**LOS RÉCORDS, que en esta familia son el dato:**

| | máximo | cuándo |
| --- | ---: | --- |
| en el terreno a la vez, un equipo | **6** | Chicago Cubs, 1999-06-20 — nadie ha puesto siete |
| lanzadores, un equipo | **6** | Pittsburgh Pirates, 2023-06-03 |
| lanzadores, los dos equipos | **7** | 2006-09-16 y 2023-07-30 |
| participantes, los dos equipos | **12** | Pittsburgh-Miami, 2019-09-03 |

Los tres primeros jardines son de los hermanos Alou y Manuel Mota (1962-1963). El jardín y el cuadro
enteros dominicanos **nunca han coincidido en el mismo juego** en 116 temporadas.

#### 5.4.1. Estas gestas obligaron a dos decisiones de diseño

**A quién se le atribuye.** El contrato tiene UN `mlb_id` por fila y estas gestas son de tres, cuatro
o doce hombres. Emitir una fila por cada uno daría efemérides idénticas repetidas el mismo día;
emitir una sola obliga a elegir. Se elige **al de más juegos de carrera** —vía `#huella` en
`_04_alineaciones.sql`— y **el texto nombra a todos**. La alternativa era un `rol = equipo` sin
`mlb_id`, que es justo lo que el dueño descartó para las gestas de equipo (11.1).

**Todas llevan `situar = 0`.** La frase del motor habla de UN dominicano y acá el sujeto es plural: no
hay valor de `situar` que la arregle. Lo que sí vale —que fue la primera vez que se vio— se calcula
dentro del propio `.sql`.

### 5.5. Hitos de carrera (suma acumulada, `N` = 292.948)

| detector | gesta | marcas | n |
| --- | --- | --- | ---: |
| `hito_hit` | un hito de hits de por vida | cada 500 | 267 |
| `hito_hr` | un hito de jonrones de por vida | **100, 200, 300, 450, 500, 600, 700** | 135 |
| `hito_k` | un hito de ponches de por vida | cada 500 | 117 |
| `hito_sb` | un hito de robos de por vida | cada 100 | 88 |
| `hito_rbi` | un hito de empujadas de por vida | cada 500 | 87 |
| `hito_sv` | un hito de salvados de por vida | cada 50 | 73 |
| `hito_win` | un hito de victorias de por vida | cada 50 | 62 |
| `hito_2b` | un hito de dobles de por vida | **450, 500, 600** | 19 |
| `hito_3b` | un hito de triples de por vida | **75, 100** | 7 |
| `hito_r` | un hito de carreras anotadas de por vida | **1500, 2000** | 5 |

#### 5.5.1. Las marcas se declaran en una LISTA, no en un escalón

`hito_hr` se detectaba con división entera cada 100. El dueño cambió el 400 por el **450** y eso
rompió el mecanismo: una progresión regular no puede expresar «450 pero no 400».

Ahora el detector declara sus marcas explícitamente y el cruce se comprueba contra el acumulado del
juego anterior, lo que sirve para cualquier lista. **Y era necesario**, porque las tres estadísticas
nuevas no tienen marcas equiespaciadas: 450-500-600 en dobles, 75-100 en triples, 1500-2000 en
carreras anotadas.

**El umbral sale de la distribución de la propia estadística, no de copiar el de otra.** Cien triples
de por vida son más difíciles hoy que quinientos dobles: el triple se extinguió con los estadios
modernos, y ponerle el hito en 200 —como en los jonrones— dejaría el detector vacío para siempre.

| | los que llegan | el techo dominicano |
| --- | ---: | --- |
| 700 jonrones | 2 | Albert Pujols, 722 |
| 2.000 anotadas | **1** | Alex Rodríguez, 2.064 |
| 600 dobles | 3 | Albert Pujols, 704 |
| 100 triples | 2 | José Reyes, 132 |

**Suman temporada regular Y postemporada** (decisión del dueño). No es como los cuenta MLB —ellos
separan— pero es coherente con el resto del archivo, donde octubre cuenta igual que junio. La
diferencia medida son 13 cruces.

**Los siete llevan `situar = 2`** (3.5): la frase solo aparece si es el primero o el único. Y su
plantilla no es constante — cada fila trae la suya, para poder añadir «Solo 3 dominicanos han llegado
ahí» cuando son cinco o menos. Es la 4.7 aplicada.

### 5.6. Hitos de TEMPORADA — los números que la gente se sabe

| detector | gesta | n | jugadores | rareza |
| --- | --- | ---: | ---: | ---: |
| `hito_k300` | 300+ ponches en una temporada | 2 | **1** | 567 |
| `hito_4040` | una temporada de 40+ jonrones y 40+ robos | 2 | 2 | 567 |
| `hito_hr60` | 60+ jonrones en una temporada | 3 | **1** | 548 |
| `hito_rbi150` | 150+ empujadas en una temporada | 5 | 4 | 523 |
| `hito_hr50` | 50+ jonrones en una temporada | 9 | 4 | 495 |
| `hito_w20` | 20+ victorias en una temporada | 15 | 7 | 471 |
| `hito_3030` | una temporada de 30+ jonrones y 30+ robos | 18 | 12 | 462 |
| `hito_h200` | 200+ hits en una temporada | 28 | 18 | 441 |
| `hito_rbi125` | 125+ empujadas en una temporada | 31 | 10 | 436 |
| `hito_k200` | 200+ ponches en una temporada | 46 | 23 | 418 |

**Las tres listas de un solo hombre:** los 300 ponches y los 60 jonrones. Pedro Martínez llegó a 300
dos veces (313 en 1999, 305 en 1997) y **nadie más ha llegado**; Sammy Sosa pasó de 60 tres veces
(66, 64, 63) y tampoco tiene compañía. En victorias, **Marichal seis veces**, con 26 en 1968.

#### 5.6.1. La ÚNICA excepción del archivo: acá la postemporada NO entra

En todo lo demás octubre cuenta igual que junio. Acá no puede: **«50 jonrones en una temporada» es una
cifra de temporada regular**, la que sale en los récords y en la prensa. Sumarle la postemporada daría
un número que no coincide con ninguna fuente del mundo y **además movería la fecha del cruce**, que es
el dato que la efeméride publica.

Es la excepción, y existe porque acá el hito ES el número.

#### 5.6.2. Los escalones conviven a propósito

`hito_hr50` y `hito_hr60` disparan sobre la misma temporada de Sosa; `hito_rbi125` y `hito_rbi150`
sobre la misma de Manny; `hito_k200` y `hito_k300` sobre la misma de Pedro; `hito_3030` y `hito_4040`
sobre la misma de Soriano. **No se fusionan**, y es correcto: el jonrón 50 y el 60 cayeron en juegos
distintos, o sea en días distintos del calendario. Cada hito cae donde le toca y los dos son noticia.

#### 5.6.3. La magnitud es el total de la temporada, no el acumulado al cruzar

Al cruzar el umbral todos rondan la misma cifra y no se distinguirían. Con el total con que cerró el
año, la temporada de 66 jonrones pesa más que la de 50 — y el titular puede decirlo: «llegó a 50 y
terminó con 66».

### 5.7. Debut, edad y Juego de Estrellas

| detector | gesta | `N` | n | rareza |
| --- | --- | ---: | ---: | ---: |
| `debut_grande` | un debut de 1.5+ carreras de valor | 292.948 | 11 | 486 |
| `debut_veterano` | un debut a los 30 años o más | **961** | 9 | 408 |
| `debut_joven` | un debut antes de los 20 años | **961** | 15 | 363 |
| `debut_dificil` ⚠️ | un debut de -1.5 carreras de valor o peor | 292.948 | 9 | **248** |
| `estrellas_primicia` | la primera apertura dominicana en su posición en un Juego de Estrellas | **283** | 9 | 367 |
| `estrellas_decision` | una decisión en el Juego de Estrellas | **283** | 11 | 345 |
| `estrellas_actuacion` | una actuación destacada en el Juego de Estrellas | **283** | 32 | 232 |

**El debut se mide por valor de carreras, no por conteo** (idea del dueño). «Dio 3 hits» no dice si
fueron sencillos con el juego 11-1 o el batazo que lo ganó. El mejor: **Starlin Castro, 2010-05-07,
+3.06**. El peor: Rufino Linares, 1981 — y el segundo peor es **Juan Marichal**, que ese mismo día
lanzó una blanqueada de un hit con doce ponches.

**La edad al debutar va en AÑOS Y DÍAS** (dueño). «18 años» tapa la diferencia entre el que debutó
recién cumplidos y el que estaba a una semana de cumplir 19, y en precocidad esa diferencia ES el
dato. Los umbrales, medidos sobre los 961 debuts con edad fiable (media 23,5 años): menos de 19 daría
3 filas, menos de 21 daría 55; 30 o más da 9, 31 o más daría 5.

**Los dos debutantes dominicanos más viejos son hermanos:** Guayubín Olivo (41 años, 1960) y Chichí
Olivo (35, 1961).

**El Juego de Estrellas solo publica ACTUACIÓN, no asistencia.** Las 283 apariciones dominicanas caben
en **18 días del calendario**, y el 13 de julio solo se llevaría 43: un detector de asistencia
convertiría esos dieciocho días en un muro de nombres y desplazaría gestas reales de esas fechas. Su
universo son las 283 apariciones, no los juegos de temporada regular — es raro DENTRO del Juego de
Estrellas, que es donde ocurre.

**Las derrotas del Juego de Estrellas entran, y no como deshonra.** `estrellas_decision` lleva
`signo = +1` para las tres: al Juego de Estrellas no se llega por casualidad, y cargar con la decisión
significa que te pusieron en el momento que decidía. Son 6 ganados, 3 perdidos y 2 salvados.

### 5.8. Fuera de sitio: el que no debería estar ahí

Cuatro detectores de una familia que no existía en el diseño, y que salió de una idea del dueño: la
efeméride no siempre es una hazaña, a veces es una **estampa**.

| detector | gesta | n | jugadores | rareza |
| --- | --- | ---: | ---: | ---: |
| `lanzador_en_posicion` | un juego jugando otra posición siendo lanzador | **2** | 2 | 567 |
| `lanzador_emergente` | un turno de bateador emergente siendo lanzador | 22 | 15 | 453 |
| `lanzador_jonron` | un jonrón siendo lanzador | 41 | 24 | 423 |
| `posicion_lanzando` | un juego lanzando siendo jugador de posición | 69 | 35 | 398 |

**QUIÉN ES LANZADOR Y QUIÉN NO SE MIDE, NO SE LISTA.** Un jugador es «de posición» si en toda su
carrera lanzó en menos del 10 % de sus juegos, y «lanzador» si lanzó en más del 90 %. Así no hace
falta mantener una lista de nombres ni fiarse de una etiqueta: el expediente del hombre dice lo que
era.

**Y el umbral no es sensible, que es la señal de que está bien puesto.** Los casos reales quedan
lejísimos de la frontera: Amed Rosario lanzó 1 juego en 1.016, Gary Sánchez 1 en 893, Pedro Strop
jugó una posición en 584 juegos casi todos lanzando. Mover el corte al 5 % o al 15 % no cambiaría
ninguna lista.

**La asimetría tiene sentido:** el campocorto sube a la loma 69 veces —un manager lo hace cuando el
juego ya se perdió— pero poner al lanzador en el jardín obliga a rehacer la alineación entera, y solo
ha pasado dos veces.

**Dos de estos se van a secar solos**, y está bien. El bateador designado universal llegó en 2022, así
que `lanzador_jonron` y `lanzador_emergente` ya casi no pueden producir. El archivo guarda una
costumbre que se acabó, que es exactamente para lo que sirve.

### 5.9. Fechas de persona y primicias

| detector | gesta | `situar` | n | días del calendario |
| --- | --- | ---: | ---: | ---: |
| `debut` | un debut en Grandes Ligas | 2 | 980 | 193 |
| `cumpleanos` | un cumpleaños | 0 | 905 | ~330 |
| `fallecimiento` | un aniversario de fallecimiento | 0 | 61 | 55 |
| `primero_posicion` | la primera apertura dominicana en su posición | 0 | 9 | 9 |

**El cumpleaños se suprime si el jugador tiene `deathDate`.** Felicitar a un muerto por su cumpleaños
es el tipo de error que un sistema automático comete y una persona no.

**El debut dice la EDAD, no los años transcurridos** — «a los 21 años» y no «hace 25 años» (dueño). La
edad dice algo del hombre; los años transcurridos solo dicen en qué año estamos, y envejecen solos
cada 1 de enero.

#### 5.9.1. El 1 de enero es relleno, y NO se puede tratar igual en las dos fechas

`dglMaster` guarda el **1 de enero** cuando solo se conoce el año. Y la regla para apagarlo es
distinta según el campo, porque el mundo es distinto:

| campo | ¿se puede apagar por regla? | por qué |
| --- | --- | --- |
| `debutDate` | **sí** | En Grandes Ligas no se juega el 1 de enero — medido, los 984 debuts caen entre marzo y octubre salvo cuatro. Ninguno legítimo que borrar. |
| `birthDate` | **no** | La gente sí nace el 1 de enero. Figuran tres y **dos son de verdad**: Fernando Tatís (949 juegos) y Rafael Roque (56). |

Por eso el debut lleva una regla y el nacimiento lleva una **lista a mano** en `_00_comun.sql`, caso
por caso, cuando el dueño confirma cuál es relleno. Hoy tiene uno: Pedro San, de quien se sabe que
nació en 1895 y nada más. Sale de cumpleaños, y su aniversario de fallecimiento se publica pero **sin
decir la edad**, porque restar de una fecha inventada da una cifra falsa con toda la seguridad de una
cifra exacta.

#### 5.9.2. El override de las Ligas Negras

`primero_posicion` y `estrellas_primicia` son **los únicos detectores que preguntan «¿quién fue el
primero?»**, y eso los hace distintos. A un conteo le pueden faltar casos y sigue siendo honesto
llamarlo «los que tenemos»; a una primicia, un hueco en la fuente no le da un número bajo: **le da una
respuesta falsa con nombre y apellido**.

Pasó exactamente eso. El detector publicaba que **Horacio Martínez** fue el primer dominicano en abrir
en el campocorto, el 1935-07-13. No es cierto: fue **Tetelo Vargas, el 1927-08-14** (dueño). La
cobertura de Retrosheet de las Ligas Negras tiene huecos — de Tetelo Vargas el juego más antiguo que
hay es de 1942, y solo como jardinero central.

Por eso este detector admite **overrides**: una lista de `(puesto, retroID, fecha)` dentro del propio
`.sql`. El dato lo pone el dueño; la consulta no puede llegar a él por ningún camino. Cuando hay
override la fila **no cuelga de ningún juego** —`game_id`, equipo y rival van vacíos— porque ese juego
no está en la base e inventarle un contexto sería repetir el error en otra columna.

### 5.10. El quiebre: no-hitter y juego perfecto, por los dos lados

| detector | gesta | rol | n | rareza |
| --- | --- | --- | ---: | ---: |
| `perfecto_perdido` | un juego perfecto perdido en el noveno o más allá | lanzador | **1** | **600** |
| `perfecto_roto` | el embasado que rompió un juego perfecto en el noveno | bateador | 2 | 570 |
| `nohit_perdido` | un no-hitter perdido en el noveno o más allá | lanzador | 15 | 471 |
| `nohit_roto` | el hit que rompió un no-hitter en el noveno | bateador | 13 | 487 |

**Se separó el perfecto del no-hitter** (dueño) porque son dos cosas distintas: un no-hitter se rompe
con un hit, un perfecto con **cualquier hombre en base**. De 272 no-hitters rotos en el noveno en toda
la liga, solo 45 eran perfectos.

**Las historias:**

- **`perfecto_perdido` tiene un solo nombre: Pedro Martínez, 3 de junio de 1995.** Retiró a los
  veintisiete y lo perdió en el inning 10. Es el único dominicano que ha estado ahí.
- **Pedro también perdió tres no-hitters** en el noveno (1994, 1995, 2000).
- **Nelson Liriano rompió un no-hitter dos veces en cinco días**, en abril de 1989.

**`nohit_perdido` y `perfecto_perdido` llevan `signo = +1`, y eso se pensó.** Lo obvio sería marcarlo
como deshonra —se perdió algo— pero es leer el hecho al revés: llegar al noveno sin permitir un hit lo
han hecho quince dominicanos en 116 temporadas, y la escala negativa lo hundiría a un techo de 400. No
es que falló: es que estuvo a tres outs de la inmortalidad. El texto carga la pérdida; el puntaje
carga la hazaña.

> ⚠️ **LIMITACIÓN DECLARADA.** En los dos detectores de perfecto se cuenta como «hombre en base» el
> hit, el boleto y el pelotazo. **Un error también rompe un perfecto** y con estas columnas no se
> distingue, así que un perfecto roto por error no lo ve el detector. Los dos casos dominicanos fueron
> con hit, así que hoy no cambia nada — pero el hueco existe y queda escrito en vez de disimulado.

### 5.11. La `N` no depende del `rol`: depende del grano

Primero se escribió que la `N` de la rareza dependía del `rol`. Con `k4_inning` quedó claro que era
quedarse corto: dos detectores de lanzador pueden tener universos distintos, porque lo que cambia no
es quién protagoniza sino **cuál es la unidad de oportunidad**.

| grano | universo | qué se cuenta |
| --- | ---: | --- |
| juego-jugador | 292.948 | la línea de un dominicano en un juego |
| juego-equipo | 407.816 | un equipo en un juego (203.908 × 2) |
| juego | 203.908 | el partido entero |
| turno al bate | 822.764 | un turno de un bateador dominicano |
| bateador enfrentado | 622.652 | un turno contra un lanzador dominicano |
| media entrada lanzada | 162.797 | una entrada de un lanzador dominicano |
| veces en tercera | 92.821 | la oportunidad de robar home |
| juego-jugador desde 1989 | 251.106 | para `cg90`, que no puede ver más atrás |
| debut de bateador | 723 | el primer turno de Grandes Ligas |
| debut con edad fiable | 961 | para los dos detectores de edad |
| aparición en el Juego de Estrellas | 283 | |
| el maestro | 984 | para cumpleaños y debut |
| **los fallecidos** | **61** | para `fallecimiento` — ver 4.6.1 |

`nobletiger` y `k4_inning` son los dos de lanzador y **no comparten `N`**: uno se pregunta «de cada
bateador que enfrentó», el otro «de cada entrada que lanzó».

Cada detector declara su grano y el motor toma la `N` que corresponde. Usar la equivocada no da error:
da un puntaje que parece razonable y está mal, que es peor.

### 5.12. ⚠️ Siete detectores diseñados que NUNCA se construyeron

Este documento los daba por hechos en versiones anteriores. **No existen como archivo.**

| detector | qué iba a ser | por qué no está |
| --- | --- | --- |
| `fouls_turno` | 10+ fouls en un turno, 2008+ | nunca se implementó |
| `fouls_juego` | 16+ fouls en un juego, 2008+ | nunca se implementó |
| `rv_bateo` | 5+ carreras de valor generadas | nunca se implementó |
| `rv_pitcheo` | 5+ carreras evitadas | nunca se implementó |
| `hr480` | jonrón de 480+ pies, 2015+ | nunca se implementó |
| `vel100` | 15+ rectas de 100 mph, 2008+ | nunca se implementó |
| `juego_estrellas` | asistencia al Juego de Estrellas | **descartado a propósito** — ver 5.7 |

`rv_bateo` y `rv_pitcheo` envejecieron bien: la misma métrica que iban a usar —valor de carreras— es
la que hoy sostiene `paliza`, `debut_grande` y `debut_dificil`.

### 5.13. Tres detectores retirados

| detector | por qué se quitó |
| --- | --- |
| `bases10` | contradecía el patrón de un umbral por gesta: se quedó `bases12` |
| `bases12` | **perdía 77 de sus 85 filas en la fusión** — casi todas eran también juegos de 5 hits o de 3 jonrones. Aportaba 8 efemérides y ninguna era suya |
| `sombrero_dorado` | demasiado ancho (499) — ver 5.1.1 |
| `sombrero_puro` | **seguía siendo demasiado ancho** (231), aun después de exigir 4-de-4. Queda solo `sombrero_mismo_lanzador`, con 28 |

**La cuenta de fusión de la muestra fue lo que delató a `bases12`.** No se veía hasta que el bloque de
redacción empezó a imprimir «de 85, 77 fusionadas» (8.2): un detector puede parecer sano por su `n` y
no estar aportando ninguna fila propia.

### 5.14. El corte de `turno_clave`, medido

La escala de `LI` está verificada sobre 4.777.761 turnos desde 2000: **media 0,940**, máximo **7,17**,
`LI >= 2` es el **4,5 %** de los turnos y `LI >= 3` el **0,65 %**. Está normalizado como manda el
estándar, así que un umbral de 2 significa «el doble de tensión que un turno cualquiera».

| corte | turnos |
| --- | ---: |
| `LI >= 2` | 34.683 |
| `LI >= 3` | 5.159 |
| `WPA >= 0.40` | 375 |
| **`LI >= 2` y `WPA >= 0.40`** | **153** |

Se eligió pedir **las dos cosas**. Solo `LI >= 3` daría 5.159 turnos tensos que **no decidieron nada**,
y tensión sin desenlace no es efeméride.

**El número publicado NO lleva la cifra de leverage.** Decía «con la tensión 4,1 veces la de un turno
corriente», que es exacto y no significa nada para quien lee. Ahora dice «con el juego en la línea».
El dato sigue en la columna `li_max` para quien quiera ordenar o filtrar.
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

**Regla:** mismo `mlb_id` + mismo `game_id` + mismo `event_id` **+ misma `fecha`** → se queda **el
hecho de mayor RAREZA** y los demás se anexan como **etiquetas** del mismo hecho, no como filas
sueltas.

Aplica igual entre niveles: si un juego de 3 jonrones incluye un grand slam de walk-off, la fila es
una sola con las tres etiquetas.

**Las dos piezas en negrita se corrigieron después de verlas fallar, y las dos fallaban en silencio.**

**1. Manda la rareza, no el puntaje.** La regla original decía «el de mayor puntaje». Con 46
detectores corriendo salió el síntoma: un **walk-off de grand slam** aparecía etiquetado como simple
walk-off de jonrón. Los dos disparan sobre el mismo turno y, aunque la rareza del slam es 468 contra
355, el jonrón ganaba por puntaje total — el slam quedaba en percentil bajo dentro de sus 20 hermanos
mientras el jonrón quedaba alto dentro de sus 262. **Siete de los veinte walk-off de grand slam se
estaban perdiendo así.**

La rareza es lo que codifica QUÉ TAN ESPECÍFICO es el hecho, y un hecho más específico nunca debe
perder contra uno que lo contiene. El puntaje solo desempata.

**2. La fecha va en la clave, y no es redundante aunque lo parezca.** Las gestas de PERSONA no
cuelgan de ningún juego: cumpleaños, debut y fallecimiento del mismo jugador llevan todos
`game_id = ''` y `event_id = 0`, así que colisionaban entre sí. El síntoma fue exacto: `91_debut.sql`
devolvía 984 filas y el archivo terminaba con **cero debuts**, porque cada uno se fusionaba con el
cumpleaños del mismo hombre. Lo destapó la muestra de redacción, no una comprobación — el conteo por
tipo lo enseñaba y nadie lo estaba leyendo.

**Y hay solapes que son deliberados.** `93_lanzadores_equipo` y `94_lanzadores_juego` disparan sobre
el mismo juego casi siempre; la fusión se queda con el del mismo equipo, que es la gesta más
específica, y el otro queda de etiqueta. Eso es exactamente lo que esta regla existe para resolver.

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

### 8.0. Las siete cosas que la implementación destapó

Ninguna de estas estaba en el diseño. Todas salieron de correr el motor y **mirar la salida**, y por
eso el bloque de «muestra de redacción» —una línea real por detector— vale lo que cuesta.

**1. El `WPA` de `r24Events` está visto desde el EQUIPO DE CASA, no desde el bateador.** Lo sospechó
el dueño y la medición no dejó lugar a dudas:

| | jonrones | WPA medio | con WPA positivo |
| --- | ---: | ---: | ---: |
| bateador LOCAL | 166.115 | +0,1277 | 166.093 |
| bateador VISITANTE | 165.069 | −0,1264 | **0** |

Cero de 165.069. No es una tendencia, es la definición de la columna. Los preludios lo tomaban como
si fuera del bateador, así que **a todo bateador visitante le entraba su mejor juego como número
negativo** y el bono de impacto se lo daba en cero. Peor: `turno_clave` pide `wpa >= 0.40`, o sea que
**solo podía encontrar turnos de bateadores locales** — media liga fuera, sin avisar. La conversión
correcta está en `_00_comun.sql`, y ojo con el lado del lanzador: cuando batea la casa, el que lanza
es el visitante.

**2. `orden` se calculaba por el aniversario, no por el año.** Las gestas de persona guardan en
`fecha` el aniversario de ESTE año, para que `mes`/`dia` salgan solos. El motor ordenaba por ahí, así
que «el primer dominicano en debutar» salía siendo **quien debutó más temprano en el calendario**. El
archivo publicaba «Sijo Gómez, el primer dominicano en llegar a Grandes Ligas», que es falso: ganaba
el puesto por tener fecha de relleno del 1 de enero. Los primeros de verdad son Pedro San (1926) y
Tetelo Vargas (1927). Se ordena por `temporada` primero; para las gestas de juego es equivalente.

**3. `situar` — un campo más del contrato, y con tres estados.** Ver 3.5.

**4. `gesta` — otro campo más.** Ver 3.7.

**5. El juego perfecto necesita detector propio.** Metido dentro de `no_hitter`, el perfecto de
Domingo Germán sacaba **767 puntos y quedaba DEBAJO** del no-hitter de Ervin Santana (774): el de
Santana fue un juego cerrado y el de Germán un 11-0, así que el bono de impacto hundía la gesta más
rara del béisbol. Esto **no contradice** el patrón de no crear un detector por escalón, lo delimita:
tres triples es la *misma* gesta que dos, más grande; un perfecto **no es un no-hitter mejor**, es no
permitir nada.

**6. Los negativos había que partirlos en TODO, no solo en la rareza.** Ver 4.5.

**7. La fusión tenía dos errores silenciosos.** Ver 7.

### 8.0.1. Dos reglas de operación

**1. El orden del archivo.** Decisión del dueño: `mes`, `dia`, luego **puntaje descendente** —dentro
del día manda la importancia— y **fecha ascendente** como desempate. El tercer nivel no sobra: dos
gestas del mismo tipo el mismo día del calendario sacan casi el mismo puntaje, y sin él el orden lo
decidiría el azar. Con la fecha, el archivo es **estable**: la misma entrada da siempre la misma
salida, que es lo que hace que la pantalla de comparación enseñe solo lo que de verdad cambió.

**2. Los `.ps1` van en UTF-8 CON BOM.** Windows PowerShell 5.1 —el `powershell` del gate, no el
`pwsh` 7— lee un `.ps1` sin BOM **como ANSI**. Las rayas largas y los acentos se decodifican en bytes
que incluyen comillas, desbalancean las cadenas y el archivo deja de parsear. El motor no arrancaba
bajo 5.1 y sí bajo 7.

De paso se descubrió que **el gate solo miraba un `.ps1`** y los seis de `static_data/` nunca se
comprobaron — justo los que corren una o dos veces al año, o sea los que más tardan en delatar un
error. `make checkps1` ahora los recorre todos.

### 8.2. La muestra de redacción: un bloque por DETECTOR, no por tipo publicado

Al final de cada corrida el motor imprime **una línea real de cada detector**, con su frase de
situación pegada. Es lo único que valida la redacción: un umbral se comprueba midiendo, pero una
frase solo se comprueba leyéndola. El «Cumple 46 años. Es uno de los 923 dominicanos que lo ha
logrado» y la concordancia de «1 empujadas» no los cazó ninguna medición — los cazó leer la salida.

**Recorre los archivos de `detectores/`, no los tipos que sobrevivieron a la fusión** (pedido del
dueño). La versión anterior agrupaba las efemérides ya fusionadas, con dos consecuencias malas: un
detector que producía filas y las perdía TODAS en la fusión desaparecía de la muestra, y encima salía
listado como «sin filas hoy», que es falso. Produjo y fue absorbido son dos cosas distintas.

Hoy hay tres estados, y siempre son tantos bloques como detectores:

| marca | qué significa |
| --- | --- |
| `[+]` / `[-]` | tiene titular propio; el signo dice si es hazaña o deshonra |
| `[~]` | produjo filas pero la fusión se las llevó todas; se muestra desde los hechos crudos |
| `[ ]` | no devolvió nada. Es una decisión, no un olvido |

**Y cada línea dice cuántas de sus filas se fusionaron**, que es un dato que no existía:

```
[+] walkoff     n=83   pts=736 (de 108, 25 fusionadas)
[+] bases12     n=8    pts=558 (de 85, 77 fusionadas)
```

Esa segunda línea es la que retiró a `bases12` (5.13). Un detector puede parecer sano por su `n` y no
estar aportando ninguna fila propia, y sin esta cuenta no hay forma de verlo.

### 8.1. Por qué PowerShell y no Python

En la máquina del dueño **no hay Python fuera de Docker**, y un contenedor no llega a SQL Server con
Integrated Security. Los tres exportadores que ya existen (`export_dom_players.ps1`,
`export_dom_salaries.ps1`, `export_batted_ball_hits.ps1`) son PowerShell + ADO.NET por exactamente
esa razón. Esto sigue el mismo camino y no obliga a instalar nada.

La consecuencia de diseño: **la lógica vive en SQL**, y PowerShell es la tubería. Que es lo que
conviene igual — los detectores son consultas, no programas.

El dueño ofreció pasarlo a Python el 2026-08-03 y se mantuvo PowerShell por lo de arriba. **Lo que se
pierde es real y conviene decirlo**: en Python el motor tendría `ruff`, `mypy` y tests unitarios del
puntaje; acá solo tiene comprobación de sintaxis.

Se compensa con **autocomprobaciones dentro del propio script** (sección 6 de
`exportar_efemerides.ps1`): puntaje dentro de 0-1000, ninguna fila sin titular, ningún marcador
`{campo}` sin rellenar, ninguna deshonra por encima del tope de su escala, ninguna fila de cobertura
parcial publicando totales, y ninguna clave repetida tras la fusión. No son teóricas: los dos
primeros fallos del motor se cazaron mirando la salida, y esto es mirarla sin depender de que alguien
se acuerde.

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
| gestas de juego, evento, Statcast y colectivas | 1.718 |
| hitos de carrera y de temporada | 998 |
| cumpleaños + debut + fallecimiento | 1.920 |
| Juego de Estrellas, debut y primicias | 114 |
| **total, medido tras la fusión** | **5.750** |

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
