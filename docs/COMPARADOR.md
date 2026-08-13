# Comparador de peloteros

Estado: **construido y probado de punta a punta** (2026-08-13). El cálculo en `stats/comparador.py`,
la imagen en `stats/tarjeta.py`, el asistente y la página de resultado en `profiles/comparaciones.py`.
Pendiente: nada bloqueante.

Diseñado y acordado con el dueño el 2026-08-11; el generador, la página-imagen y el reparto, el
2026-08-13.

Una herramienta para comparar dos dominicanos y sacar de ahí un PNG que la gente pueda pegar en
WhatsApp, X o Instagram. La referencia es el comparador de Stathead, y el objetivo declarado del
dueño es traer tráfico.

---

## 1. Lo que hace que esto traiga tráfico, y no solo imágenes

Conviene separar dos cosas que suenan iguales. **El PNG es lo que se comparte; la URL es lo que trae
gente.** Una imagen suelta circulando por WhatsApp no lleva a nadie a ningún sitio.

Así que son tres piezas y la del medio es la que justifica el trabajo:

1. Un **generador** en `/comparar/` donde se eligen los parámetros — enlazado desde el menú, entre
   Jugadores y Artículos.
2. Una **página de resultado** con URL propia y estable, que **es** la tarjeta y trae los botones de
   reparto.
3. El **PNG** en sí, servido desde esa misma URL con `.png`, más una previa apaisada para que el
   enlace se vea bien al pegarlo.

Con eso, cada comparación compartida es un enlace indexable con la marca detrás.

---

## 2. El universo: dominicanos con debut desde 1956

**981 peloteros.** Se excluyen los siete de las Ligas Negras — Pedro San, Tetelo Vargas, Néstor
Lambertus, Sijo Gómez, Horacio Martínez, Enrique Lantigua y Julio Báez.

**El motivo no es la fecha, es la fuente.** Sus estadísticas de Ligas Negras no son comparables con
las de Grandes Ligas, y el WAR ni siquiera existe para ellas: de las 27 temporadas suyas que hay en
la base, ninguna tiene WAR. Compararlos sería inventar una equivalencia que los datos no sostienen.

El corte se aplica **una sola vez, en el universo** — no repartido por cada consulta— y vale para el
selector, el cálculo y los rankings. Ningún pelotero tiene la fecha de debut vacía, así que la
condición no deja a nadie en tierra de nadie.

> **Cuidado si alguien mueve el corte.** Cinco de esos siete tienen fecha de debut el 1 de enero
> porque se conoce el año y no el día — Tetelo Vargas debutó en 1927, no el 1 de enero de 1927. Para
> un corte por AÑO da igual; para uno dentro del año, dejaría de funcionar.

Tras excluirlos, solo faltan **5 registros de WAR en toda la base** (2 de bateo, 3 de pitcheo), todos
de 2026 y presumiblemente por recalcular.

---

## 3. Dos jugadores, y los oficios son TRES

Dos y no más: tres aprietan la imagen y cuatro obligan a formato horizontal con letra pequeña.
Stathead admite muchos porque su salida es una tabla web, no una imagen.

**Bateador contra lanzador no se permite**, y lo impide el selector en vez de dejar elegir y luego dar
error: elegido el primero, el segundo se filtra a su mismo oficio. El sitio ya sabe qué es cada uno
—hay un criterio de posición por entradas jugadas que se mantiene solo y distingue abridor de
relevista— así que no hace falta nada nuevo.

Para un pelotero que hiciera las dos cosas de verdad, manda su posición registrada. No se inventa una
comparación mixta.

**Y el pitcheo son DOS oficios, no uno** (dueño, 2026-08-13): bateadores, **lanzadores abridores** y
**lanzadores relevistas**. Es la primera pregunta del asistente.

Comparten las mismas métricas de pitcheo — un relevista tiene efectividad, WHIP y FIP como cualquiera
— pero **no comparten ni umbrales ni población de ranking**. Ver §5. Lo que el oficio decide es:

1. **Quién sale en el buscador** del paso siguiente. Quien dijo «relevistas» no tropieza con Marichal.
2. **Contra quién se rankea.** Un relevista, entre relevistas.
3. **Qué umbral se le exige** a las tasas.

`Player.pos` ya los distingue —hay un criterio por juegos abiertos en `players/positions.py`, más de
la mitad es abridor— así que no hizo falta clasificación nueva.

**Un `P` a secas cae en abridor**, que es el umbral estricto. Es preferible que a alguien le falte un
puesto a dárselo calculado contra la población equivocada.

**Un abridor contra un relevista NO se permite**, y esto cambió sobre la marcha (review v22, ARCH-01).
No es por las métricas —son las mismas— sino por el ranking: cada uno se rankea en su
población y con su umbral, así que una tarjeta mixta tendría que elegir una de las dos.

La primera versión elegía la del pelotero de la izquierda, y «la izquierda» sale de ordenar el par por
`player_id`, o sea por el número que MLB le asignó a cada uno: **azar**. El mismo par daba rankings
distintos según quién tuviera el número más bajo.

La alternativa era rankear cada lado en su propia población, y entonces la cabecera tendría que decir
dos oficios y un «(2º)» significaría algo distinto que el de la fila de al lado. Un ranking que cambia
de sentido dentro de la misma imagen no es un ranking. Se rechaza.

El asistente no puede producir esa comparación —el oficio se fija en el paso 1— así que la negativa
solo alcanza a la URL escrita a mano, que responde 404.

> **José Mesa contra Rafael Soriano sigue funcionando**, que era el ejemplo que preocupaba: los dos
> son `RP`. Mesa abrió 95 juegos en su carrera pero su posición registrada es relevista.

---

## 3.bis. La temporada repartida entre equipos cuenta UNA vez, y entera

**Son 338 temporadas en la base**, así que no es un caso marginal. La fuente trae una fila por club
**más una línea combinada**, marcada con el centinela `XXX` en vez de un equipo. Santo Alcalá, 1977:

| stint | equipo | G | HR | PA |
| ---: | --- | ---: | ---: | ---: |
| 1 | MTL | 31 | 1 | 27 |
| 2 | CIN | 7 | 0 | 3 |
| 3 | **XXX** | **38** | **1** | **30** |

El comparador ve **una sola fila con 38, 1 y 30**: la temporada completa. Lo resuelve `season_totals()`
—el mismo método que usan la página de líderes y los perfiles— así que el comparador cuenta igual que
el resto del sitio.

**Y el peligro no es quedarse corto, es contar de más.** Leyendo las filas crudas se sumarían los
tramos MÁS la combinada, y la temporada valdría el doble. Sobre una carrera con varios traspasos los
totales saldrían inflados sin que nada pareciera roto: es exactamente la diferencia que apareció al
medir a Fernando Rodney, **61-88 crudo contra 48-71 colapsado**, donde lo segundo es su récord real.

---

## 4. Las tres modalidades

### Por temporada

Cada jugador aporta una temporada, y **no tienen por qué ser la misma**. Ahí está la gracia: «Soto
2024 vs. Guerrero 2021» es una comparación que nadie más publica. Si coinciden, la imagen puede
decirlo.

### Por carrera

Los totales de por vida.

### Sus mejores X temporadas por WAR

Se ordenan las temporadas de cada uno por WAR y se toman las mejores. Es el modo que iguala a un
veterano con uno en activo y responde a «en su mejor versión, ¿quién fue mejor?».

El dueño lo llama **el killer feature** de los tres, y por eso se le abrió el rango.

**X va de 1 a 7.** El suelo de tres que tenía el diseño original desapareció con esa decisión, y tiene
sentido: existía porque «pico de carrera» no significa nada con dos años. Pero **con X=1 la pregunta
cambia y vuelve a ser buena** —«su mejor año contra su mejor año»— y **no se solapa con el modo
temporada**: allí el año lo elige quien compara, acá lo elige el WAR.

El techo en 7 sale de la medición: solo 305 bateadores y 162 lanzadores llegan a seis temporadas, así
que de ahí para arriba la modalidad se convierte en la de carrera para casi todo el mundo.

**Quien no llega a las pedidas, NO baja: se le dice.** Esto cambió al montar el generador
(2026-08-13). La primera versión igualaba por abajo en silencio y lo declaraba en el rótulo; con un
formulario delante eso es peor, porque el usuario ve un 5 en la pantalla y recibe una tarjeta de 3.
El error nombra al pelotero y dice qué pedir:

> Jordany Valdespín tiene 3 temporadas de al menos 100 PA, no 5. Compara con 3 o menos.

Lo que **no** cambió es el principio: nunca se enfrentan 7 temporadas contra 4. Cinco acumulan más de
todo que tres, así que el de carrera larga ganaría cualquier acumulado **por construcción**. Antes eso
se evitaba igualando; ahora, negándose. No es un caso raro — es la mayoría:

| | con 5+ temporadas | con menos de 5 |
| --- | ---: | ---: |
| bateadores (863 con WAR) | 366 (42 %) | 497 (58 %) |
| lanzadores (563 con WAR) | 197 (35 %) | 366 (65 %) |

Quien **pide un 12** en la URL también se lleva un error: devolverle «las 7 mejores» escondería el
fallo de quien escribió la dirección y dejaría dos URLs apuntando a la misma página.

**El número viaja en la URL**, porque el ranking depende de él: «sus 4 mejores» hay que rankearlo
contra los mejores cuatrienios de los demás, no contra los quinquenios.

### Qué cuenta como temporada: 100 PA · 30 IP abridores · 20 IP relevistas

**Fijo, no configurable** (dueño, 2026-08-11). Un año de cinco turnos aporta un WAR cercano a cero, y
si alguien tiene exactamente cinco temporadas y una es de café, pasa la validación y luego arrastra el
agregado.

Los números son bajos **a propósito**. La primera propuesta fue 400 PA y 50 IP, y medido se llevaba el
feature por delante — 400 PA describe «una temporada de TITULAR», y lo que hay que excluir es «una
temporada que no existió»:

| | sin umbral | ≥100 PA | ≥200 PA | ≥400 PA |
| --- | ---: | ---: | ---: | ---: |
| bateadores capaces de «mejores 5» | 366 | **161** | 125 | 84 |

| | sin umbral | ≥30 IP | ≥60 IP | ≥150 IP |
| --- | ---: | ---: | ---: | ---: |
| lanzadores capaces de «mejores 5» | 197 | **132** | 79 | 24 |

> **Los lanzadores se partieron después.** Abridor 30 IP, relevista **20 IP** — un año de relevo entero
> son 60-70 entradas, así que el mismo número no describe lo mismo en los dos oficios. Ver §5.

**Por qué no lo elige el usuario.** Se planteó como campo del formulario y se descartó: el umbral
cambia también la POBLACIÓN DEL RANKING. Con uno pidiendo 100 PA y otro 400, el «2º histórico» de la
misma tarjeta diría cosas distintas — dos verdades incompatibles circulando con la misma marca.

**En carrera NO se filtra nada**: los 703 jonrones de Pujols incluyen su última temporada, valga lo que
valga. En la modalidad de temporada suelta sí manda, porque el desplegable de años solo ofrece
temporadas comparables: ofrecer el año de veinte turnos sería invitar a una comparación cuyo resultado
no dice nada.

El umbral **se escribe en la tarjeta y en la pantalla del generador**. Una imagen que dice «2º
histórico» sin decir entre quiénes es una cifra que nadie puede comprobar, y estas imágenes circulan
sueltas por WhatsApp.

---

## 5. El ranking: UNO, y es el histórico

Contra dominicanos, siempre. El sitio existe para ordenarlos entre ellos; «3º dominicano de todos los
tiempos» es una frase que nadie más publica. Rankear contra toda la MLB exigiría datos de la liga
entera que el sitio no tiene.

**Se descartó el ranking por temporada, y el motivo es que no informa.** El universo dominicano de una
temporada es pequeño, y para las tasas se encoge mucho más porque solo entran los que califican. Lo
vio el dueño: si Soto lidera OBP ocho veces, «1º en 2024» dice lo mismo que dijo en 2021, 2022 y 2023.
Un número que casi siempre sale igual no distingue nada.

**«6º de todos los tiempos» sí es raro**, porque compite contra las 5.185 temporadas dominicanas de la
historia. Ese es el que cuesta y el que se comparte.

Quitarlo resolvió tres cosas de golpe: se fue el número flojo, las tres modalidades quedaron iguales
—una celda, un valor, un ranking, sin casos especiales— y la imagen pudo simplificarse.

### El umbral de las tasas escala con las temporadas

Lo encontró el dueño el 2026-08-13 mirando a los dos Vladimir Guerrero: **padre e hijo salían los dos
«1º»** en promedio, OBP, SLG, OPS, wOBA y wRC+ a la vez.

**La causa:** a una bolsa de «mejores 3» se le exigía el umbral de CARRERA —PA≥3.000— que ninguna
bolsa de tres temporadas puede alcanzar. La población quedaba vacía y el puesto salía «1 de 0». En la
tarjeta eso no parece un error, **parece un dato**, que es la peor forma de fallar.

La regla ahora es **sumar el umbral de cada año que trae la bolsa**. No es multiplicar por X: se
resuelve año por año porque el umbral baja en las temporadas cortas —1981, 1994, 2020— y pedirle 502
apariciones al año del confinamiento dejaría fuera a quien le tocó. Cada bolsa candidata trae sus
propios años y se mide contra su propia suma; la pregunta es si ese pelotero fue titular **en los años
que está aportando**.

| mejores X | bateadores | compiten | lanzadores | compiten |
| ---: | --- | ---: | --- | ---: |
| 1 | PA ≥ 502 | 113 | IP ≥ 162 | 54 |
| 2 | PA ≥ 1.004 | 93 | IP ≥ 324 | 39 |
| 3 | PA ≥ 1.506 | 87 | IP ≥ 486 | 40 |
| 4 | PA ≥ 2.008 | 82 | IP ≥ 648 | 32 |
| 5 | PA ≥ 2.510 | 73 | IP ≥ 810 | 27 |
| 6 | PA ≥ 3.012 | 65 | IP ≥ 972 | 22 |
| 7 | PA ≥ 3.514 | 60 | IP ≥ 1.134 | 19 |

En pitcheo la población es delgada arriba, y es la verdad: solo 19 dominicanos han lanzado 1.134
entradas en sus siete mejores años. No se compensa bajando el umbral, porque entonces un relevista de
60 entradas por año competiría en efectividad contra Pedro Martínez.

**Al propio pelotero también se le exige su umbral.** La población ya está filtrada, así que sin eso un
.400 en 300 turnos saldría PRIMERO sobre gente que jugó entero. El valor se sigue pintando —es suyo y
es cierto— pero sin puesto.

> Las pruebas de esto comprueban **`de`**, o sea cuántos había en la población, y no solo `rank`. Con
> la población vacía el puesto siempre es 1, así que un `rank == 1` no distingue al mejor de la
> historia de un cálculo roto. Es la lección que dejó el fallo.

### Abridores y relevistas no se miden con la misma vara

Lo encontró el dueño el 2026-08-13 en la tarjeta de **José Mesa contra Rafael Soriano**: a Soriano le
faltaban los puestos de TODAS las tasas —efectividad, WHIP, FIP, SO/9— mientras Mesa los tenía.

**La causa:** el umbral de carrera del catálogo es `IP>=1000`, que es de abridor. Soriano lanzó 636
entradas en catorce temporadas porque era cerrador, y ningún cerrador se acerca a mil.

**Medido, y el número sorprende: solo 87 de los 527 lanzadores dominicanos son abridores.** El umbral
no estaba mal calibrado «para lanzadores» — estaba calibrado para el 17 % de ellos. De los 440
relevistas, **siete** llegan a 1.000 IP, y son los que abrieron parte de su carrera; Mesa, con 95
aperturas, es uno de ellos.

| Umbral de carrera | Abridores (87) | Relevistas (440) |
| --- | ---: | ---: |
| IP ≥ 1.000 | 29 | **7** |
| IP ≥ 600 | 38 | 32 |
| IP ≥ 500 | 45 | 49 |
| **IP ≥ 400** | 49 | **63** |
| IP ≥ 300 | 53 | 89 |

Los números salen de **igualar la proporción que compite**, no de igualar las entradas:

| | abridores | relevistas |
| --- | --- | --- |
| carrera | `IP>=1000` → 29 peloteros | **`IP>=400`** → 63 |
| temporada | `IP>=162` → 35 % de sus años | **`IP>=50`** → 37 % de los suyos |
| cuenta como temporada | 30 IP | **20 IP** |

El 50 lo eligió el dueño sobre el 40, que habría dado 81 relevistas capaces de «mejores 5» en vez de
64: prefiere la población más selecta y simétrica con la de los abridores.

**La población del ranking se parte también, y eso es la mitad que hace que el número signifique
algo.** Bajarle el umbral al relevista sin separar la población lo metería a competir en efectividad
contra abridores de 200 entradas al año, que es otra pregunta. «1º en efectividad» tiene que querer
decir «entre relevistas».

Manda `Player.pos`, o sea el oficio de HOY: un abridor reconvertido a cerrador aparece donde diga su
posición actual, que es como se le conoce y como se le va a buscar.

**Solo se sustituye el umbral si la fórmula original hablaba de entradas.** Hay métricas con umbral
propio —los coeficientes de bola en juego se miden en `BALLS_IN_PLAY`, no en IP— y cambiárselo por uno
de entradas las dejaría midiendo otra cosa.

Con esto, Soriano pasa de no tener puesto en ninguna tasa a **1º en efectividad, 2º en WHIP y 1º en
FIP-** entre relevistas dominicanos.

### Cómo se calcula

**Al vuelo, en cada comparación.** Con 5.185 temporadas de bateo y 3.046 de pitcheo, contar cuántos
superan un valor es instantáneo. No hace falta tabla nueva ni proceso nocturno, y así el ranking nunca
queda desfasado respecto a los datos.

**El tablero de líderes NO sirve para esto** y conviene saberlo antes de intentarlo: está pensado para
publicar puntas, no para responder «¿en qué puesto quedó este señor?». Para jonrones en 2019 guarda 69
de los 142 que batearon. Apoyarse en él dejaría la mitad de las comparaciones en «no rankeado» — justo
la mitad interesante, la de los peloteros normales.

**Con el umbral puesto.** Rankear promedio de bateo sin mínimo de apariciones lo gana quien tuvo tres
turnos. Se aplica la misma cascada que la página de líderes: el umbral general por oficio y el
ajustado por temporada para los años cortos.

**Empates a puesto compartido**, y el siguiente sigue — como el motor de líderes.

---

## 6. Las métricas

Elegidas por el dueño.

| | bateo (13 filas) | pitcheo (16 filas) |
| --- | --- | --- |
| volumen | WAR · G · PA · H · HR · RBI · SB | WAR · G · GS · IP · W · L · PCT |
| calidad | AVG · OBP · SLG · OPS · wOBA · wRC+ | ERA · ERA- · WHIP · FIP · FIP- |
| por 9 entradas | | SO · SOx9 · BBx9 · HRx9 |

**Todas existen y están activas en el catálogo.** Tres sustituciones sobre lo que se pidió al
principio, y conviene saber por qué:

- **K% y BB% no existen** ni como métrica ni como columna. Se cambiaron por **SOx9 y BBx9**, que sí.
- **BB salió y entró HRx9** (dueño, 2026-08-11). Al ver la tarjeta de Pedro Martínez, sus 760 boletos
  aparecían en el puesto 556 de 563: el ranking es correcto —menos boletos es mejor— pero la pregunta
  no lo es, porque «1º en menos boletos de por vida» lo gana quien lanzó tres entradas. HRx9 es una
  TASA, así que sí pasa por el umbral de las mil entradas y compara a quienes lanzaron de verdad.
- **WHIP entró después** (dueño), junto a ERA-, y es de las exactas: se recalcula sumando hits,
  boletos y entradas, así que no lleva asterisco.

Se escriben con la nomenclatura del sitio —`SOx9`, no `SO/9`— para que quien llegue desde la
comparación reconozca las columnas.

Dos notas de implementación:

- **IP se guarda en outs.** Ya hay formato que lo escribe en notación de béisbol; reusarlo, no dividir
  a mano.
- **W y L van en filas separadas.** El diseño preveía una sola celda —«219-100 (.687)»— y se dejaron
  aparte (dueño). `L` **no se rankea**: «menos derrotas» lo gana quien menos lanzó, el mismo problema
  que sacó a BB. Ver la sección 8.

> **Queda un asunto de fondo, y el dueño lo marcó como muy baja prioridad.** El umbral solo se le
> exige a las TASAS, no a los conteos — es una regla deliberada, y las pruebas la destaparon: al
> pedírselo a los conteos, el ranking de jonrones de carrera salía sobre una población vacía porque
> casi nadie llega a 3.000 apariciones. Pero eso deja sin piso a los conteos de «menos es mejor»
> —BB, L en pitcheo; SO, CS, GIDP en bateo— cuyo ranking gana quien menos jugó. En el comparador ya no
> se ve, porque ninguno de esos está rankeado en los dos sets. **En la página de líderes sí**, en la
> tabla de «Últimos», y eso está publicado.

### Los tres caminos de agregación

Al agregar (carrera o mejores X), cada métrica va por uno. El motor ya reparte así para sus tableros
de carrera, o sea que el comparador **no estrena nada**: reusa el mismo mecanismo cambiando qué
temporadas entran en la suma.

| camino | bateo | pitcheo |
| --- | --- | --- |
| **se suman** | WAR · G · PA · H · HR · RBI · SB | WAR · G · GS · IP · W · L · SO |
| **se recalculan exacto** desde componentes | AVG · OBP · SLG · OPS | ERA · WHIP · SOx9 · BBx9 · HRx9 |
| **se ponderan** por PA / IP | wOBA · wRC+ | FIP · ERA- · FIP- |

**La imagen ya NO dice cuál se usó** (dueño, 2026-08-13). Hubo un asterisco en wOBA y wRC+ con su nota
al pie —«media ponderada por PA»— y se quitó al compactar el pie a dos líneas: «no vale mucho», y es
cierto. Lo que decía era «este número es aproximado», que es una discusión que no cabe en una imagen
que se mira diez segundos en un teléfono.

Se fueron los dos JUNTOS, marcador y leyenda, y eso no es negociable: **un marcador sin leyenda es peor
que ninguno** — el lector ve una llamada, la busca, no la encuentra y se queda pensando qué se le
escapa.

El dato no se pierde del sistema: `Celda.aproximada` sigue viajando en la foto, así que la página HTML
puede explicarlo con todo el sitio del mundo si algún día hace falta.

Las exactas se recalculan sumando los componentes y dividiendo UNA vez — para el promedio se suman
hits y turnos de las cinco temporadas—, que no es lo mismo que promediar cinco promedios ponderados.
Con temporadas de volumen muy distinto la diferencia se ve en la tercera cifra.

**Las cinco ponderadas lo son porque sus coeficientes cambian cada año.** wOBA, wRC+, ERA- y FIP-
llevan ajuste anual y de parque, y FIP necesita su constante de temporada. Sumar cinco años de
componentes y aplicarles un solo juego de pesos mezclaría la escala de 2015 con la de 2024.

Comprobado: `derived_rates` calcula veintidós tasas de bateo desde componentes y **wOBA no está entre
ellas** — devuelve `None`.

> **Hay que marcarlas en la imagen.** Cinco de las trece filas no son el número exacto sino una media
> ponderada. Es la aproximación estándar y es lo correcto, pero un asterisco discreto con nota al pie
> evita que alguien compare el wOBA de carrera con el de FanGraphs y encuentre una diferencia en la
> tercera cifra que no sepa explicar.
>
> **Y es el punto más débil del feature en el modo «mejores X»**: ponderar wOBA sobre cinco temporadas
> que pueden estar repartidas entre 2010 y 2024 es más discutible que sobre una carrera continua.
> Sigue siendo lo mejor disponible sin recalcular los coeficientes.

---

## 7. La imagen

**1080×1350, o sea 4:5 exacto.** La proporción manda más que el tamaño: es la vertical MÁXIMA que
Instagram admite sin recortar, X la muestra entera y WhatsApp aguanta de sobra. Se probó 980×1350
—proporción 0,73— y se pasaba de alto en los dos sitios donde más se comparte.

**Lo estrecho no lo da el lienzo sino la columna del centro**, que pasó de 340 px a 130: solo tiene
que caber «wRC+», y todo lo que se llevaba de más separaba los dos valores que se vienen a comparar.

### La página de resultado ES la imagen

Hubo una tabla en HTML y **se quitó** (dueño, 2026-08-13): «lo que quiero ahí es el PNG auto creado…
NO QUIERO HTML». La página muestra el PNG y los botones de reparto, y nada más. El motivo técnico
coincide con el gusto: dos representaciones del mismo resultado acaban divergiendo, y la que circula
por WhatsApp es la que nadie puede corregir.

Como la imagen **es** el contenido, su texto alternativo la cuenta con cifras dentro —métrica a
métrica— y no dice «tarjeta comparativa». Quien usa lector de pantalla se quedaría sin la comparación
entera.

### La previa de las redes es apaisada

**1200×630, aparte de la tarjeta.** X, WhatsApp y Facebook recortan la previsualización a ~1.91:1, y
un recorte así sobre una imagen 4:5 se lleva la cabecera con la marca y el pie con la dirección del
sitio — las dos cosas por las que se comparte. La previa encaja la tarjeta **entera** sobre el azul de
la marca. Se sirve desde la misma vista con `?previa=1`.

> **Ninguna red permite adjuntar la imagen por un enlace de compartir.** El *web intent* de X no tiene
> parámetro para media, y subirla exige la API con OAuth publicando en nombre del usuario. Los botones
> de WhatsApp, X y Facebook mandan el ENLACE; lo que se ve al pegarlo es esta previa.
>
> El único camino que manda el fichero es **la Web Share API con `files`**, que es lo que hace el botón
> «Compartir…» de la fila: abre la hoja del sistema con el PNG dentro y de ahí va a WhatsApp, a
> Instagram o a donde haya. Existe en los móviles y casi nunca en escritorio, así que
> `comparador_compartir.js` lo comprueba con `canShare({files})` antes de engancharle el fichero — y
> si no puede, ese botón comparte el enlace como en el resto del sitio.

**Formato de Stathead, en columnas simétricas** (decisión del dueño, con captura de referencia): la
métrica en la columna del CENTRO y los valores flanqueándola. Para un cara a cara importa, porque el
ojo compara cruzando un eje en vez de leer una fila de izquierda a derecha. Y deja el sitio natural
para la marca arriba, entre los dos retratos.

```
        .419              OBP              .362
      3º histórico                     41º histórico
```

De arriba abajo: la cabecera; los dos retratos con nombre y años activos —los mugshots de 360 ya están
en disco—; las filas; y el pie.

### La cabecera: marca a la izquierda, comparación a la derecha

```
DGL  Dominicanos                                          Carrera completa
     EN GRANDES LIGAS                                   Lanzadores abridores
     dominicanosengrandesligas.com
```

**El dominio va con la marca** (dueño, 2026-08-13). Antes vivía al pie, donde competía con la leyenda
de los paréntesis; arriba está donde el ojo lo busca, y es lo que convierte una imagen prestada en una
visita. Va en el mismo gris azulado que las demás aclaraciones de la tarjeta: acompaña a la marca sin
competir con ella.

Las tres líneas se reparten el alto que ya ocupaba el monograma —de 29 a 103— **en vez de hacer crecer
la banda**: ese espacio lo necesita la tabla, que reparte lo que sobra entre sus filas.

**Bajo la modalidad va el oficio** —«Bateadores», «Lanzadores abridores», «Lanzadores relevistas»— en
cuerpo menor y en gris azulado, porque es la aclaración y no el titular. Va en TODAS las tarjetas
(dueño, 2026-08-13) y no es decorativo: desde que abridores y relevistas se rankean por separado, un
«17º» significa dos cosas distintas según quién salga en la imagen, y la imagen circula sola.

### El pie: dos líneas y nada más

```
𝕏 @dglmlb                         ( ) puesto histórico entre dominicanos
2026-08-13                        Puestos de promedios: mínimo 1,000 IP
```

**A la izquierda el arroba y la fecha; a la derecha las aclaraciones de lectura.** El reparto tiene una
lógica: arriba, junto a la marca, va lo que trae gente al sitio; abajo, el arroba, que es lo que
alguien copia para citar la fuente dentro de la propia red. El logo de X delante dice de qué red es la
cuenta sin gastar una palabra — se transcribe del SVG que ya usa `_compartir.html`, que es solo rectas.

**Eran tres líneas a la derecha y son dos** (dueño, 2026-08-13). Salió la de la media ponderada; ver
§6 para qué se pierde y por qué se aceptó. El pie bajó de 126 a 88px y esos 38 se reparten entre las
filas de la tabla.

> **Se probó 95 y NO CABÍA**: la fecha se montaba sobre el arroba y las líneas de la derecha se
> pisaban. Los números de este pie son medidos, no estimados — conviene saberlo antes de volver a
> apretarlo.

**«Puestos de promedios: mínimo 1,000 IP»**, con los dos puntos y en ese orden. Decía «Los rankings de
promedios exigen…» y se leía como una regla del sitio que aplica a todo lo que tienes delante; con el
ámbito por delante queda claro desde la primera palabra a qué se refiere y, por omisión, a qué no —
los acumulados no llevan umbral. Y salió más corta, que en ese renglón importa.

La nota **dice el umbral que se usó de verdad**, no el del catálogo. Leyendo el catálogo a secas, la
tarjeta de Soriano anunciaba 1.000 IP mientras su ranking se había hecho con 400 (ver §5). Una nota
que contradice sus propios números es peor que no ponerla.

**La línea de años no abrevia**: «1960–1975 · 16 temporadas», y en singular «2020 · 1 temporada». Ahí
sobra sitio, así que un «temp.» solo hacía que la tarjeta pareciera apretada donde no lo está.

### Qué tamaño y qué color lleva cada cosa

| | | por qué |
| --- | --- | --- |
| valor | Inter Bold **40** | es lo que se viene a leer |
| **puesto** entre paréntesis | Mono 25, **`(44, 50, 62)`** | más oscuro que el gris de contexto: a 25px se caía de la fila. Sigue por debajo de la tinta del valor — acompaña a la cifra, no compite |
| métrica | Mono Bold 31, azul de la marca | rotula, no informa |
| **nombre** del pelotero | Mono Bold **35** | subió de 31: con las cifras en Inter se había quedado pequeño al lado de lo que rotula |
| años bajo el nombre | Mono 18, `PUESTO` | dice CUÁNTAS temporadas entraron —en «mejores X», cuáles— así que no es relleno |

**Solo queda un gris claro en la tarjeta**, `SUAVE`, y ya no lo usa ningún texto de la tabla. El puesto
y la línea de años se oscurecieron los dos (dueño, 2026-08-13) porque ninguno era relleno: el ordinal
es la mitad de lo que hace valiosa esta tarjeta, y los años dicen qué se está comparando.

### Las cifras van en sans proporcional, el resto en monoespaciada

**Inter Bold para los números; JetBrains Mono para métricas, marca y pie** (2026-08-13).

Salió de comparar la tarjeta con la de Stathead en un teléfono, y el resultado desmontó la hipótesis
obvia. Medido:

| | alto de fila | dígito, % del ancho |
| --- | ---: | ---: |
| nuestra | ~50px | **3,5%** |
| Stathead | ~39px | 3,1% |

**Nuestras cifras ya eran más grandes que las suyas y aun así se leían peor**, así que subir el cuerpo
—que era lo que yo iba a proponer— habría sido perseguir algo que ya teníamos.

Lo que sí difería: los dígitos de una monoespaciada se dibujan **estrechos** para caber en un avance
fijo, así que a igual altura se leen más finos que los de una proporcional en negrita. Inter trae
cifras tabulares, que es lo que mantiene las columnas alineadas sin ser monoespaciada.

La misma comparación dejó un segundo dato que sigue en pie: **el 42% de nuestro lienzo era cromo** —136
de cabecera, 300 de retratos y 126 de pie, de 1350— contra casi nada en el suyo. De ahí salió apretar
el bloque de retratos a 264 (con la foto más GRANDE: 176 en vez de 168, porque lo que sobraba era el
aire) y el pie a 88.

> **Lo que NO se puede copiar de Stathead es prescindir del cromo.** Ellos no llevan marca ni pie
> porque nadie llega a Stathead por una imagen. Acá la marca y el dominio son el motivo de que
> compartir sirva de algo, y el pie es lo único que hace verificable ese «2º».

**Y la franja negra del teléfono no se arregla con nada de esto.** Un card 4:5 en una pantalla 9:19,5
ocupa el 56% del alto — es geometría, no tipografía. La de Stathead también las deja. Lo que se
arregla es poder leer las métricas, que era el problema real.

**Quién gana cada fila sale de la dirección de la métrica**, que el catálogo ya declara: en efectividad
gana el más bajo, y en boletos de un lanzador también.

Dos cambios respecto a Stathead:

- **El resaltado del ganador no va en verde.** Ellos usan un verde pálido que no existe en la paleta
  del sitio. Con el azul propio en tono muy bajo se consigue lo mismo y la imagen se ve nuestra, no
  una captura de otra web — que importa cuando el objetivo es que la reconozcan.
- **El empate se dibuja tiñendo las dos celdas**, como hacen ellos. Es una decisión, no un descuido: o
  las dos o ninguna.

**Y el empate se juzga por el número TAL COMO SE ESCRIBE, no por el float de dentro.** Lo encontró el
dueño en wRC+: Alex Rodríguez y Pujols salían los dos con 141 y solo uno aparecía resaltado, porque
por dentro difieren en decimales que la tarjeta redondea. La imagen se contradecía — dos cifras
idénticas y una pintada como mejor, sin nada que lo explique. La diferencia real no se pierde: sigue
en los puestos entre paréntesis, que ahí sí salen distintos (4º y 3º).

**Se dibuja con Pillow**, que ya es dependencia del proyecto y con la que se generaron las cabeceras de
artículo. La alternativa —renderizar HTML con un navegador headless— es más cómoda de maquetar y mete
un binario pesado, arranques lentos y una superficie nueva que mantener. Para una tarjeta de datos,
Pillow sobra.

**Las tres tipografías viven en `dglweb/stats/fuentes/`** —JetBrains Mono en dos pesos, Inter Bold y
Source Serif—, junto al módulo y no bajo `static/`: no las
carga ningún navegador, las lee Pillow en el servidor. Están versionadas con el repo (~418 KB) porque
la imagen del contenedor solo trae fuentes de iconos. Se rehacen con `static_data/bajar_ttf_tarjeta.py`,
que las pide con un agente viejo — Google sirve TTF a esos y woff2 al resto, y Pillow solo lee TTF.

---

## 8. El porcentaje de victorias sí se rankea, y las derrotas no

Las tres celdas van seguidas: **W**, **L** y **PCT**. Solo dos llevan puesto.

**Las derrotas no se rankean nunca.** «5º dominicano en derrotas» no es un logro, y en una imagen
pensada para compartirse solo puede leerse como burla — sobre todo porque liderar derrotas suele
significar haber sido lo bastante bueno para que te dieran la pelota veinte años. Quien quiera saber
quién ganó más de lo que perdió lo lee en PCT, que es la métrica que responde a eso.

**El PCT se rankea SOLO EN ABRIDORES** (dueño, 2026-08-13):

| | Marichal | Pedro Martínez |
| --- | ---: | ---: |
| W | 243 (2º) | 219 (3º) |
| L | 142 | 100 |
| **PCT** | **.631 (2º)** | **.687 (1º)** |

En un relevista el W-L es casi ruido: sus victorias suelen venir de salvamentos volados —entra
perdiendo, el equipo remonta y se le apunta a él— así que ordenar cerradores por porcentaje premia una
carambola. En una tarjeta de relevistas la cifra se pinta y el paréntesis no aparece: el valor es suyo
y es cierto, simplemente no encabeza ninguna lista que valga la pena publicar.

> **Esto estuvo bloqueado meses por un bug que no existía.** El diseño original decía «sin ranking,
> por un bug abierto y no diagnosticado» y citaba tres fuentes que no cuadraban en el W-L de carrera
> de Fernando Rodney. Investigado el 2026-08-13: **las tres eran mediciones mal hechas**, todas por
> consultar una tabla sin la columna que la discrimina. El 1.000 del tablero era su récord de
> POSTEMPORADA (1-0), y el 15-30 de `PitchingCareer` era su récord con Detroit. Los datos siempre
> estuvieron bien. Ver `docs/TODO.md`.

Queda en pie una reserva sabermétrica que conviene no perder de vista: **el WPCT mide al equipo tanto
como al lanzador**. El apoyo ofensivo y el bullpen deciden buena parte de esas victorias, y por eso va
acompañado de ERA-, FIP- y WAR en la misma tarjeta y no solo.

---

## 9. URLs

```
/comparar/                                                            el generador (formulario)
/comparar/temporadas/?jugador=<slug>                                  JSON: años comparables de uno
/jugadores/buscar/?universo=comparador&oficio=RP                      el buscador del paso 2 y 3
/comparar/albert-pujols-405395/vs/sammy-sosa-122544/carrera/          la página-imagen
/comparar/pedro-martinez-118377/vs/juan-marichal-118283/mejores-5/
/comparar/juan-soto-665742/vs/vladimir-guerrero-jr-665489/temporadas/2024-2021/
/comparar/<uno>/vs/<otro>/<modo>/tarjeta.png                          el PNG 1080×1350
/comparar/<uno>/vs/<otro>/<modo>/tarjeta.png?previa=1                 la previa 1200×630
```

**El generador es un ASISTENTE DE SEIS PASOS que redirige, y nunca pinta una comparación.** Lo que el
usuario copia de la barra tiene que ser un enlace indexable, no un formulario relleno. Y las
validaciones viven ahí y no en la página-imagen, que solo puede devolver un 404: con el formulario
delante se puede decir qué falló y qué pedir en su lugar.

```
1  ¿Qué quieres comparar?          bateadores · abridores · relevistas
2  Primer pelotero                 el buscador solo ofrece el oficio del paso 1
3  Segundo pelotero
4  ¿Qué comparar de ellos?         carrera · mejores por WAR · una temporada
5  Los parámetros                  cuántas temporadas, o los dos años
6  Resumen + Generar
```

**Hubo un formulario de una pantalla y el dueño lo rechazó** (2026-08-13): obligaba a entender las
tres modalidades, los dos buscadores y el umbral antes de elegir nada. Preguntando de una en una,
además, cada paso usa lo contestado en el anterior — de ahí que el buscador sea «inteligente».

**El estado viaja en la URL, no en la sesión.** Así «atrás» del navegador funciona, recargar no pierde
nada y cada paso es una dirección que se puede probar a mano. Con sesión, dos pestañas del mismo
navegador se pisarían.

Tres reglas del flujo que cuesta ver leyendo la plantilla:

- **No se puede saltar a un paso sin contestar los anteriores**: se cae al primero que falte. Pasa al
  pegar una URL vieja o al retroceder y cambiar el oficio.
- **La carrera completa se salta el paso 5**, porque no pide nada. Una pantalla vacía con un botón de
  seguir deja al usuario buscando qué tenía que contestar.
- **Atrás y Siguiente son botones de envío, no enlaces**, para que lo elegido en la pantalla actual
  viaje también al retroceder. El de Atrás lleva `formnovalidate`: sin eso el navegador se niega a
  volver desde un paso con un campo obligatorio vacío, que es justo cuando más falta hace.

> **El `id` de los ocultos no es decorativo.** `comparador.js` busca el slug del pelotero por
> `getElementById` para saber de quién pedir los años. Al pasar de formulario a asistente se pintaron
> con `name` pero sin `id`, y los desplegables de temporada salían vacíos — ni error ni aviso, dos
> selectores muertos. Hay una prueba que vigila ese contrato.

**El buscador del asistente excluye a los de debut anterior a 1956** (`?universo=comparador`) y filtra
por oficio (`&oficio=batting|SP|RP`). **La caja del encabezado sigue encontrándolos a todos**: Tetelo Vargas
es parte del sitio; lo que no es, es comparable. Son dos comportamientos y hay una prueba para cada
uno.

**La modalidad va en la ruta, no en la query.** El sitio calcula la canónica desde `request.path` y
descarta la cadena de consulta, así que una modalidad en `?modo=` haría que las tres versiones se
declararan como la misma página.

**El par se normaliza a un orden fijo**, o cada comparación existiría dos veces para Google.

El PNG cuelga de la misma ruta con `.png` para que compartir el enlace y compartir el fichero lleven
al mismo sitio. Lo que la página declara en Open Graph es la PREVIA apaisada, no la tarjeta: ver §7.

---

## 10. Caché y abuso

Un endpoint que genera imágenes con parámetros libres es un generador de carga a petición de
cualquiera. Tres defensas:

- La imagen se cachea por una **clave canónica de comparación y versión de datos**, no por la ruta que
  se pidió: el par al revés, un slug viejo o un `?v=` inventado caen todos en la misma entrada. La ruta
  pública solo dice cómo pedirla. Ver «La clave es canónica» más abajo.
- Solo se aceptan peloteros **que existan en el universo y no estén deshabilitados**.
- Las modalidades son **un conjunto cerrado**, no un número libre.

**Esto último estuvo escrito antes de ser cierto** — la revisión v22 lo cazó como SEC-01: el
documento prometía la caché y el endpoint dibujaba en cada petición. Implementado el 2026-08-13.

### Por qué la ruta cara es esta

Cada tarjeta resuelve dos peloteros, calcula los rankings de todas sus métricas sobre las 5.185
temporadas dominicanas, abre tipografías y retratos, y pinta un PNG de 200 KB con Pillow. Es pública y
sin autenticación, así que un bot que pida combinaciones válidas la usa de ariete contra los hilos de
gunicorn. Y no hace falta un bot: **cuando una comparación se hace viral, el tráfico natural golpea
justo ahí**.

### Cómo se cachea

| | |
| --- | --- |
| dónde | `dgl_cache_imagenes`, alias `settings.IMAGENES`, tabla creada por `core.0003` |
| clave | **la versión de los datos** + los dos `player_id` ORDENADOS + modalidad + previa o vertical |
| cuánto | **6 horas** (`CACHE_TARJETA`), y es la red, no el mecanismo |
| cuántas | `MAX_ENTRIES` 200, unos 55 MB de tabla |
| además | `Cache-Control: public, max-age=…`, `ETag` del contenido y **304 a un `If-None-Match`** |

### La frescura la da la clave, no el reloj

**Las estadísticas se cargan una vez al día** (dueño), así que una tarjeta solo puede cambiar cuando
cambia esa carga. Por eso la marca de la última carga entra en la clave: cuando el pipeline termina,
la clave cambia, las entradas viejas quedan inalcanzables en el acto y la tarjeta se repinta en la
siguiente petición. **La carga corta el TTL en curso sin que nadie limpie nada.**

Un temporizador solo no puede acertar, y el primer intento —seis horas a secas— fallaba por los dos
lados: repintaba el MISMO PNG hasta cuatro veces al día, y aun así una carga que terminara a las 6:05
tardaba seis horas en verse.

La versión sale de `IngestRun`, el registro de vuelo del pipeline, mirando solo las ejecuciones que
terminaron **bien**: una fallida no cambió ningún número. Se consulta como mucho cada cinco minutos,
para que un acierto de caché siga sin tocar la base.

**Y el reloj se queda igualmente, porque cubre otro fallo.** La clave depende de que el pipeline
escriba su `IngestRun`: un cargador que no pase por `record_run`, o uno que se cuelgue en `RUNNING`
sin cerrar, deja la versión congelada. Sin reloj, la tarjeta se quedaría cacheada para siempre y nadie
lo notaría — **una imagen vieja no se ve vieja**. El coste de tenerlo de más es repintar un PNG
idéntico cuatro veces al día; el de no tenerlo, publicar cifras de la semana pasada.

### La clave es canónica, no la ruta que se pidió

A la misma comparación se llega por muchas rutas: el par al revés es la misma tarjeta, y el slug se
resuelve por el id del final, así que `nombre-inventado-2` vale igual que el canónico. Con la ruta
cruda como clave, un bot que fabricara variantes forzaba un redibujo por cada una y desalojaba con
basura las 200 entradas útiles — para un usuario normal la caché seguía funcionando, y contra tráfico
adversarial, que es para lo que se puso, no.

Se normaliza **sin tocar la base**: `_player_id_from_slug` es una operación de cadena, así que un
acierto de caché sigue sin costar una consulta.

**La tabla es propia y no la compartida, y el motivo no es el espacio sino el DESALOJO.** Una tarjeta
pesa 200 KB —unos 270 KB ya serializada en base64 por Django— contra los 34 KB que mide todo lo que
guarda la caché compartida junto. `MAX_ENTRIES` se aplica por tabla, así que metiéndolas juntas un
puñado de PNGs expulsaría las entradas de la pizarra, que son baratas y se leen en TODAS las páginas,
para dejar sitio a una imagen que quizá nadie vuelva a pedir.

**Va en base y no en `locmem`** porque con varios trabajadores de gunicorn la memoria local guardaría
una copia por proceso, y la primera petición sería cara tantas veces como procesos haya.

> **AL DESPLEGAR UN CAMBIO DE DISEÑO HAY QUE LIMPIAR `dgl_cache_imagenes`.** La invalidación por
> versión sirve para los DATOS, no para el dibujo: cambiar el PNG no cambia ni la carga ni los ids, así
> que la clave sigue siendo la misma y circulan hasta seis horas tarjetas con el formato anterior. Pasó
> dos veces —al añadir la fila de PCT y al mover el dominio a la cabecera— y las dos veces pareció que
> el cambio no había entrado.
>
> Y en dev el navegador tampoco cachea (`max-age=0` con `DEBUG`), porque limpiar el servidor no sirve
> de nada si el navegador sigue enseñando el PNG que ya tiene.

**No hay nada en disco y no hace falta ningún janitor.** El PNG se dibuja en memoria (`BytesIO`) y
vive en filas de Postgres que caducan por TTL y se purgan solas al pasarse de `MAX_ENTRIES`.

### Y la previa no redibuja la tarjeta

`previa()` recibe los bytes de la vertical cuando quien llama ya los tiene. Sin eso encadenaba el
dibujo completo —tipografías, retratos, todas las filas— y luego el reescalado: el trabajo caro hecho dos
veces en la misma petición.

---

## 11. Cómo quedó repartido el código

| pieza | dónde |
| --- | --- |
| el cálculo y el ranking | `dglweb/stats/comparador.py` |
| el dibujo del PNG y la previa | `dglweb/stats/tarjeta.py` (tipografías en `stats/fuentes/`) |
| el generador, la página-imagen y el endpoint de años | `dglweb/profiles/comparaciones.py` |
| el asistente de seis pasos | `templates/profiles/generador.html` + `_cmp_lado.html` |
| la caché de las imágenes | `dgl_cache_imagenes`, creada por `dglweb/core/migrations/0003_…` |
| la página de resultado | `templates/profiles/comparar.html` |
| enseñar y esconder campos, llenar los años | `static/js/comparador.js` |
| compartir el FICHERO por la hoja del sistema | `static/js/comparador_compartir.js` |
| el modo selector del buscador | `static/js/buscador.js` (`data-elige`) |

Pruebas: `tests/test_comparador.py` (el cálculo), `tests/test_generador.py` (las vistas),
`tests/js/comparador.test.js` y `tests/js/buscador.test.js`.

El orden en que se construyó —cálculo probado, luego página, luego imagen— fue el correcto y conviene
mantenerlo si se amplía: el trabajo gráfico no empezó hasta que los números estaban acordados.

---

## 12. Decisiones abiertas

- **¿Una versión corta para Instagram?** Trece métricas con su ranking son 26 números: se comparte bien
  en un grupo de béisbol, pero para Instagram quizá funcione mejor una imagen de seis u ocho y que la
  página tenga las trece. La página y el PNG salen del mismo cálculo, así que se puede decidir después
  de ver la primera imagen real — pero conviene saberlo antes de dibujar, porque cambia si el molde es
  uno o dos.
- **«Líder X veces»** como dato junto al nombre. Es lo que sustituiría con ventaja al ranking de
  temporada que se descartó: «líder dominicano en OBP 8 veces» es una frase que ningún ranking de una
  temporada suelta da. No es un ranking sino un dato de carrera, así que iría junto al jugador y no
  dentro de la tabla. Se decide después de ver cuánto sitio queda.
