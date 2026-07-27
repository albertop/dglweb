# Datos de apoyo desde DGL (CSV → Postgres)

## Regla de autoridad — quién es dominicano

Antes que nada, porque gobierna todo lo demás: **un jugador es dominicano si y solo si está en
`dgl_master` o en `dom_players`.** La unión de las dos es el *universo dominicano*.

Ningún campo de país decide. Ni `birth_country_code` de `dgl_master`, que es dato informativo de la
fuente. Ni —sobre todo— el `birthCountry` que devuelve la API de MLB, **que no es confiable**: no se
usa para esto en ninguna parte del sistema, ni siquiera como pista.

La consecuencia práctica: si un jugador está jugando y no aparece en el universo, la respuesta no es
mirarle el país en la API, es que **falta agregarlo al maestro**. Mantener esas dos tablas al día es
lo que hace correcto todo lo que viene después.

## El principio

El sitio se alimenta del **proxy de MLB**, y así se queda. Cuanto más venga por ahí, más simple es
todo: un solo pipeline, una sola cadencia, una sola forma de fallar.

Pero hay datos que el proxy no da y que sí existen en la base **DGL** (SQL Server): salarios,
transacciones, y —lo que destapó este diseño— los **tipos de batazo en los hits**. Son datos de otra
naturaleza: no cambian a diario, no dependen de la temporada en curso, y se refrescan **una o dos
veces al año**. Datos de apoyo, casi estáticos.

No justifican un pipeline en vivo ni atar el proyecto a SQL Server. Lo que necesitan es una vía
manual, explícita y trazable.

## Cómo entra el dato

```
DGL (SQL Server)  ──PowerShell──▶  CSV  ──upload en Backoffice──▶  Postgres
```

**1. `static_data/scripts/` — los PowerShell.** Un script por dataset. Cada uno lleva:

- Una **constante con la ruta de salida** del CSV. ⚠️ *Pendiente: el dueño la define.*
- El **SQL a la vista**, formateado y legible — no una cadena armada a pedazos. Quien lo abra dentro
  de dos años tiene que poder leer qué se extrae sin ejecutar nada.
- Un **encabezado que explique por qué existe**: qué problema resuelve ese dataset y por qué no
  viene del proxy. Sin eso, el script se vuelve un artefacto huérfano.

**2. El registro de datasets — una tabla en Postgres con su CRUD.** La página de carga no lleva una
lista escrita a mano: lee de una tabla que el dueño administra desde el Backoffice. Agregar un
dataset nuevo es crear una fila, no tocar código.

| Columna | Qué es |
|---|---|
| `id` | PK autoincremental |
| `tabla` | La tabla de Postgres destino |
| `powershell` | El nombre del script en `static_data/` que genera el CSV |
| `csv` | El nombre del archivo que ese script produce |
| `truncate` | Marcado: se vacía la tabla y se carga de nuevo. Sin marcar: upsert idempotente |
| `clave_natural` | **Obligatoria.** Las columnas que identifican una fila, separadas por coma. Casi siempre compuesta |
| `comentario` | Texto libre: por qué existe este dataset, qué ojo hay que tenerle |
| `last_update` | Cuándo se subió por última vez |
| `last_filas` | Cuántas filas escribió esa última carga |
| `last_user` | Quién la subió |

**`clave_natural` es obligatoria siempre, marque o no `truncate`.** El upsert la necesita para decidir
entre actualizar e insertar, sí — pero no es el único que la usa:

- La **pantalla de comparación** la necesita en los dos modos. Sin clave no se puede decir qué
  desapareció, que es lo más importante que muestra.
- La **validación de unicidad** aplica en los dos modos. Un duplicado no es menos grave con truncate:
  ahí no se pisa una fila con otra, se insertan las dos, y la tabla queda con un registro fantasma
  que nadie pidió. En cualquiera de los dos casos es un export mal hecho.

El formulario la exige y valida que esas columnas existan en la tabla destino — descubrirlo a mitad
del import es tarde.

**Y la clave es compuesta casi siempre**, no por excepción: en este dominio ninguna tabla de stats se
identifica con una sola columna. `mlb_batting` va por *(jugador, temporada, stint)* y `mlb_fielding`
por *(jugador, temporada, equipo, posición)*. El diseño lo asume desde el principio, y eso aplica a
las tres piezas por igual:

- El **upsert** empareja por todas las columnas de la clave, no por la primera.
- La **comparación** agrupa por la clave completa para decir qué desaparece: contar jugadores
  distintos no sirve si lo que se perdió fue una posición de un jugador que sigue estando.
- La **validación de unicidad** evalúa la combinación entera. Que `player_id` se repita es normal y
  esperado; lo que no puede repetirse es *(jugador, temporada, stint)* completo.

Las tres columnas `last_*` no son adorno: le dan a la pantalla de comparación una **línea base
histórica**. Sin ellas se puede ver que un CSV trae menos filas que la tabla actual, pero no que el
dataset viene encogiéndose carga tras carga. Y en una operación que corre dos veces al año, saber
quién la hizo la última vez vale más que en una diaria.

`csv` sirve además para atajar el error obvio: si el archivo que se está subiendo no se llama como
dice la fila, la página avisa antes de nada. Cargar el CSV de salarios sobre la tabla de
transacciones es un error de una sola vez y de consecuencias largas.

**3. Backoffice — la página de carga.** Lista las filas del registro con un botón de upload al lado
de cada una. Es la interfaz de la operación semestral.

**4. El import, en dos pasos.** Con `truncate` marcado el CSV es la verdad completa del dataset y no
un delta: se vacía la tabla y se carga de nuevo, sin merges ni estados intermedios que auditar. Sin
marcar, se hace upsert por `clave_natural` — para los datasets que llegan por partes o donde borrar
lo viejo perdería algo.

Pero **nada se escribe sin que el usuario lo vea primero**. El flujo es:

```
subir CSV  ──▶  pantalla de comparación  ──▶  [Confirmar] o [Cancelar]
                (nada escrito todavía)          ↑ recién aquí se toca la tabla
```

Un truncate ejecutado a ciegas es irreversible y silencioso: si el CSV vino corto, la tabla queda
corta y nadie se entera hasta que alguien mira una página meses después. **Ese es exactamente el
fallo que originó este documento** — la fuente de MLB entregó el 1,8% de los hits tipificados de
2000 y el sitio lo publicó como si nada durante años.

### Qué muestra la pantalla de comparación

No un "¿está seguro?", sino los números lado a lado para que el desbalance salte a la vista:

| | En la tabla | En el CSV | Δ |
|---|---:|---:|---:|
| Filas | 12.480 | 12.512 | +32 |
| Temporadas cubiertas | 1989-2026 | 1989-2026 | — |
| Jugadores distintos | 941 | 944 | +3 |
| Suma de cada columna numérica | … | … | **% de cambio** |

Y encima de eso:

- **Temporadas o jugadores que desaparecen.** Estaban en la tabla y no vienen en el CSV. Es la
  señal de alarma más importante: un export que se cortó a la mitad se ve acá y en ningún otro lado.
  Solo aplica en modo truncate — con upsert las filas ausentes sobreviven, y la pantalla debe decirlo
  en vez de callarlo, porque "no desaparece nada" significa cosas distintas en cada modo.
- **Clave natural única.** Se corre siempre, en los dos modos: si la combinación de `clave_natural`
  se repite en el CSV, la pantalla lista las filas culpables y **no deja confirmar**. No es un aviso
  — es un export mal hecho, y dejarlo pasar corrompe la tabla en cualquiera de los dos modos.
- **La prueba de aceptación del dataset**, corrida sobre el CSV *antes* de escribir. Si
  `FH+GH+LH+PH ≠ H` para alguna fila, la pantalla lo dice y el botón de confirmar no aparece.
- **Una muestra de filas** del CSV, para detectar un desfase de columnas o un encoding roto de un
  vistazo.
- **Variaciones grandes marcadas.** Un total que cambia más de cierto porcentaje se resalta: puede
  ser legítimo (se cargó una temporada nueva) o puede ser el desastre.

### Cómo se sostiene técnicamente

El CSV se guarda en una **staging** —tabla temporal o archivo en disco con un token— y la pantalla
lee de ahí. El truncate y el insert corren juntos **dentro de una transacción** al confirmar, así que
o queda la tabla nueva completa o queda la vieja intacta; nunca un estado a medias.

## La tensión que hay que resolver antes de construir

⚠️ **"Truncar y reemplazar" no aplica igual a todos los datasets.**

- **Salarios y transacciones** son tablas *propias*: nadie más las escribe, así que truncarlas es
  seguro y es justo lo que se quiere.
- **Los tipos de batazo NO son una tabla propia.** Son cuatro columnas (`fly_hits`, `ground_hits`,
  `line_hits`, `pop_hits`) que viven dentro de `mlb_batting`, que **es del proxy**. Truncar esa tabla
  destruiría el backfill entero.

Las dos salidas posibles, a decidir:

- **(a) Tabla propia + lectura al derivar.** El CSV carga en algo como `dgl_batted_ball_hits`
  (jugador, temporada, los cuatro conteos) y el paso de `derive` prefiere ese dato sobre el del proxy
  cuando existe. La tabla se trunca y reemplaza sin tocar nada del proxy, y queda explícito de dónde
  salió cada número. Cuesta un paso más en el pipeline.
- **(b) Import que actualiza columnas.** El CSV escribe directo sobre `mlb_batting`, solo esas cuatro
  columnas. Menos piezas, pero rompe la regla de "truncar y reemplazar" y deja la tabla con dos
  dueños — la próxima corrida del proxy podría pisarlo.

**Recomendación: (a).** Mantiene la regla intacta, no le pone dos dueños a una tabla, y hace visible
que ese dato es de otra procedencia.

## Validación en el import

Cada dataset trae su propia prueba de aceptación, y el import falla ruidosamente si no pasa.

Para los tipos de batazo la prueba es **exacta**, no estadística: los cuatro tipos son una partición
de los hits, así que

```
fly_hits + ground_hits + line_hits + pop_hits = H
```

por (jugador, temporada). En 1999, con datos sanos, da 4.957 = 4.957 clavado.

### La otra mitad: contra `balls_in_play` (SAB-02)

Lo de arriba reconcilia hits contra hits. Falta el denominador, que es donde se puede publicar un
imposible:

```
gb_pct = (ground_outs + ground_hits) / balls_in_play
          └ MLB ────┘   └Retrosheet┘   └ MLB ────┘
```

Los cuatro tipos son una partición de los batazos, así que **sus proporciones no pueden sumar más de
100%**. Pueden hacerlo porque el numerador mezcla dos fuentes y el denominador viene de una tercera
cuenta. Se mide con `derive.batted_ball_excess()`, en batazos enteros y no en proporciones: son
exactos, así que `> 0` es una respuesta limpia sin epsilon que calibrar.

Se aplica en dos momentos: `post_apply` aborta la transacción si **lo que se carga empeora** el
desajuste —no si simplemente lo hay, ver abajo— y `manage.py check_batted_balls` audita lo que ya
está guardado.

### Anomalía conocida y aceptada: Rafael Soriano 2010

| | |
|---|---|
| **Fila** | `player_id` 400089, temporada 2010, pitcheo |
| **Qué pasa** | 129 outs + 36 hits = **165 batazos** contra **164** `balls_in_play` |
| **Efecto** | GB%+FB%+LD%+PU% suma **100,61%** en su perfil |
| **Origen** | **La fuente de MLB, no nosotros.** 2010 no está entre las temporadas que se cargan del CSV de Retrosheet: esos hits los entregó el proxy. Es MLB inconsistente consigo mismo. |
| **Decisión (2026-07-27)** | **Se deja como está.** Subir su `balls_in_play` a 165 para que cuadre sería corregir a la fuente por nuestra cuenta, y la regla de este proyecto es no inventar datos. Un batazo de diferencia sobre 164 no cambia ninguna lectura. |

### La tolerancia, y por qué NO va en porcentaje

La auditoría da por ruido de la fuente un exceso de **hasta 1 batazo**, que es exactamente el modo de
fallo observado: MLB descuadrado por uno consigo mismo.

Se planteó ponerla en porcentaje —«aceptar hasta 101%»— y **medida sale invertida**. Sobre las 6.896
filas reconciliables de hoy, cuyo `balls_in_play` va de unas decenas a 922, un 1% dejaría pasar:

| `balls_in_play` | Batazos imposibles que pasarían sin avisar |
|---|---|
| 20 | 0,2 — **no perdona ni uno**, justo donde una unidad no significa nada |
| 164 | 1,6 |
| 300 | 3,0 |
| 922 | 9,2 — **nueve**, justo donde un fallo sistemático se vería |

O sea: estricta con las muestras chicas y laxa con las grandes, al revés de lo que uno quiere. En
batazos enteros la regla vale igual para todas las filas.

**Lo tolerado se cuenta aunque no se liste.** Una fila suelta no dice nada, pero que el contador
salte de 1 a 800 es justo la señal de una carga mal armada — y sin ese renglón la tolerancia sería
una venda en vez de un umbral.

`--tolerancia 0` vuelve a la regla estricta. Con eso, hoy, sale solo la fila de Soriano.

`ACEPTADAS` —dentro del comando— queda para lo que la tolerancia no puede cubrir: un descuadre grande
que se investigó y se aceptó. Hoy está **vacía**, porque la única anomalía real cae dentro de la
tolerancia.

Se audita así, y no debería reportar nada fuera de lo esperado:

```
manage.py check_batted_balls
```

## Datasets

### 1. Tipos de batazo en los hits — el que originó esto

**El problema.** La API de MLB entrega los *outs* por tipo completos pero le faltan *hits* por tipo
en **diez temporadas**. Medido con la prueba de arriba sobre 1989+:

| Año | Cobertura | Faltan | | Año | Cobertura | Faltan |
|---|---:|---:|---|---|---:|---:|
| 2000 | 1.8% | 4.980 | | 1990 | 89.9% | 304 |
| 2001 | 2.2% | 5.063 | | 1996 | 90.6% | 316 |
| 2002 | 86.5% | 762 | | 1997 | 94.2% | 224 |
| 1989 | 95.2% | 137 | | 1993 | 96.5% | 100 |
| 1994 | 95.2% | 120 | | 1995 | 95.1% | 142 |

El daño se ve en que los cuatro coeficientes dejan de sumar 100%: los de Sammy Sosa suman 99.8% en
1999 y **55.9% en 2000**, y LD% —que son casi todos hits— cae de .204 a .036. Arrastra a los
tableros de líderes y a los coeficientes de por vida.

**La fuente.** `DGL.dbo.retroEventsReg` (Retrosheet), unida a `dbo.dglMaster` por `retroID`. La
columna **`BATTEDBALL_CD`** trae la trayectoria por evento, con `EVENT_TX` como respaldo (el
modificador tras la barra: `S8/L`, `D7/F`, `S6/G`).

| `BATTEDBALL_CD` | Trayectoria | Columna nuestra |
|---|---|---|
| `G` | roletazo | `ground_hits` |
| `F` | elevado | `fly_hits` |
| `L` | línea | `line_hits` |
| `P` | palomita | `pop_hits` |

**Cobertura verificada** (hits de dominicanos, `EVENT_CD IN (20,21,22,23)`):

| Año | Hits | Con trayectoria | Cobertura |
|---|---:|---:|---:|
| 1999 | 4.524 | 4.524 | 100% |
| 2000 | 4.612 | 4.486 | **97.3%** |
| 2001 | 4.714 | 4.599 | **97.6%** |
| 2002 | 4.814 | 4.729 | 98.2% |

O sea: **el hueco es de nuestra fuente, no del registro histórico.**

**Verificado además:** todo jonrón lleva trayectoria (0-1 nulos en cuatro años) y siempre `F` o `L`
— en 1999, 440 + 75 = 515 = el total exacto de HR. Y **nuestro `fly_hits` también incluye los
jonrones**, así que el mapeo es directo, sin ajuste. Los nulos residuales (~2,5%) son
sencillos/dobles/triples sin código, no jonrones.

**Pendiente de medir:** las palomitas. `PH` va de 106 en 1999 a 1, 0 y 1 en 2000-2002, y a 31-60 en
los noventa. Si Retrosheet trae ~100 `P` por año en todo el rango, ese tipo está mal cubierto de
forma sistemática en nuestra fuente y no solo en los años rotos.

**Al cargarlo:** desaparece la advertencia de la UI y se puede borrar
`derive.UNDERTYPED_STATCAST_SEASONS`. Cierra SAB-03.

### 2. Dominicanos en el sistema (`dom_players`)

**Qué es.** Los dominicanos del sistema profesional, **con y sin debut** en Grandes Ligas. No
confundir con `dgl_master`: ese es el maestro de los que sí llegaron y es la autoridad del sitio.
Esta es más ancha —incluye menores— y sirve para ver quién viene subiendo: detectar debuts y
movimientos de roster.

**De dónde sale.** La vista `v_dglweb_master_no_debuts` de SQL Server, vía
`export_dom_players.ps1` → `dom_players.csv`. Trece columnas; la vista trae más, pero cargar lo que
no se usa solo agrega columnas que hay que mantener sincronizadas en tres lugares.

**El filtro.** Solo los nacidos en los últimos 40 años: un dominicano de más de 40 que todavía no
debutó ya no va a debutar. Los que **no tienen fecha de nacimiento se incluyen a propósito** — sin
esa cláusula el `YEAR(NULL)` los dejaba fuera en silencio, y si a un prospecto le falta la fecha el
problema es la fecha, no el prospecto.

**Modo: truncate.** Se reemplaza entera y no se reconcilia con lo que había. La tabla existía desde
antes con 27 columnas cargadas por fuera de Django; la migración `0016` la dropea y la recrea con
las trece que se usan, porque el contenido viejo no servía.

**Validación.** Deliberadamente flaca: la única columna que importa es `player_id`, que tiene que
venir y ser única —de la unicidad se encarga el motor, que la exige siempre—. El resto es
descriptivo y puede faltar sin que la fila deje de servir. Lo que sí hace el loader es traducir los
tres tipos que cambian de forma al cruzar la frontera: el `bit` de SQL Server llega como
`True`/`False`, la fecha llega con hora, y los vacíos llegan como cadena vacía y no como NULL.

**No declara `rebuilds`:** no alimenta ningún cálculo. Cargarla no dispara `build_leaders`.

### 3. Salarios (`dom_salaries`)

**Qué es.** Lo que cobró cada dominicano, por temporada y equipo. No está en la API de MLB: solo
existe en DGL.

**De dónde sale.** La vista `v_dglweb_salaries`, vía `export_dom_salaries.ps1` → `dom_salaries.csv`.
Seis columnas: `player_id`, `season`, `team_id`, `league_id`, `age`, `salary`.

**El grano, que es lo único delicado acá.** La clave es **(jugador, temporada, equipo)** y el equipo
va incluido a propósito: un pelotero traspasado a mitad de año cobra de dos organizaciones, así que
su temporada son **dos filas legítimas**. Con la clave sin `team_id`, la validación de duplicados las
trataría como un error y bloquearía la carga entera — perdiendo la mitad de lo que ese jugador cobró.

**`team_id` y `league_id` son códigos de DGL, no de MLB.** `char(3)` y `char(2)`, y sus valores **no
se corresponden** con el `team`/`league` de las tablas del proxy (`"NYY"`, `"AL"`). Se guardan tal
cual; casarlos exigiría un mapeo que hoy no existe.

**Sin FK a `dgl_master`.** Si un salario llega de alguien que todavía no está en el maestro, la fila
se conserva: bloquear miles de filas por un jugador faltante costaría más de lo que protege.

**Validación.** La clave completa es obligatoria; liga, edad y salario pueden faltar. Y un salario
negativo bloquea: no es un dato raro, es un error de la vista o del export. Se ataja al validar y no
al escribir porque la columna es `PositiveBigInteger` — dejarlo pasar sería un 500 a mitad de carga.

**En la comparación se suma el salario y no la edad.** El total de la nómina es la señal que delata
un export corto; la suma de las edades no significa nada.

**No declara `rebuilds`:** no alimenta ningún cálculo.

### 4. Calendario de temporadas (`seasons_dates`)

**Qué es.** Una fila por temporada con sus fechas: apertura, fin de serie regular, Juego de
Estrellas, inicio de postemporada y cierre. Es lo que permite responder "¿este juego fue de serie
regular o de postemporada?" sin adivinar por el mes.

**De dónde sale.** La vista `v_dglweb_season_dates`, vía `export_seasons_dates.ps1` →
`seasons_dates.csv`. La clave es `(season, sports_id)`; `sports_id` es tinyint y **1 es MLB** — hoy
la única liga que el sitio usa, pero va en la clave para no tener que migrarla si mañana entra otra.

**Es el primero por UPSERT, y el primero con CRUD. Las dos cosas son la misma decisión.** Esta tabla
también se edita a mano en el Backoffice (*Calendario de temporadas*): son pocas filas, y cuando MLB
mueve una fecha conviene corregirla sin esperar a que alguien corra un export. Truncar en cada carga
borraría justamente esas correcciones, así que el modo tiene que respetar lo que ya está.

**La contracara del upsert, que cambia qué hay que validar.** Con truncate una fila mala desaparece
en la carga siguiente; con upsert **se queda para siempre**, porque nada la borra. Por eso la
validación es más estricta acá:

| Se rechaza | Por qué |
|---|---|
| Fechas fuera de orden | Una traspuesta no se ve mirando la fila —todas son plausibles por separado— pero rompe en silencio a quien después pregunte si una fecha cae en regular o en postemporada |
| Más de una temporada `is_active` | Con upsert la vieja no se apaga sola: si entran dos encendidas, quedan dos encendidas |
| `season_start_date` o `season_end_date` vacías | Una temporada es justamente el intervalo entre esas dos |

La regla de orden vive en `SeasonDates.clean()`, así que vale para **las dos puertas**: el CSV y el
formulario del Backoffice. Las otras tres fechas pueden faltar — no todos los años tienen registrado
el Juego de Estrellas, y una temporada en curso todavía no tiene fecha de postemporada.

> `reg_season_end_date` quedó **nullable**: la fuente no dijo si puede venir vacía, y ser permisivo
> donde no hay dato es lo seguro — exigirla y que llegue nula bloquearía la carga entera. Si resulta
> que nunca falta, conviene apretarlo.

**No declara `rebuilds`:** no alimenta ningún cálculo todavía.

**Pero sí gobierna al scheduler.** Desde que existe esta tabla, los jobs diarios no dependen solo del
reloj: al despertar consultan la temporada marcada como en curso y no hacen nada fuera de ventana
(`dglweb/stats/season_window.py`). O sea que **corregir una fecha acá cambia cuándo trabaja el
sitio**, sin tocar el compose ni desplegar.

### 5. Transacciones — diferido a después del lanzamiento

Existe en DGL y sin diseño todavía. **Decisión del dueño (2026-07-26): no es prioritario para el
lanzamiento**, así que no se especifica ni se construye por ahora. El motor ya soporta agregarlo
cuando toque —es un loader más— y no bloquea nada de lo que sí entra.

## Decisiones abiertas

- [ ] La **ruta de salida** de los CSV (constante en cada PowerShell). — *lo define el dueño*
- [ ] **(a) tabla propia** vs **(b) update de columnas** para los tipos de batazo. Recomendado: (a).
- [ ] Si el CSV se versiona en el repo o vive fuera. Vale la pena decidirlo temprano: son datos
      derivados de una base que no es pública, y el repo no es el lugar obvio.
- [ ] Quién puede subir (hoy el Backoffice es solo staff; la restricción por rol es de Fase 5).

## Cómo se agrega una tabla nueva

El motor es genérico y no se toca: agregar un dataset es escribir un `Loader` con tres atributos y,
si hace falta, dos hooks. El manual de operación está en **`docs/MOTOR_DATOS_APOYO.md`**.

## ⚠️ La prueba de aceptación de batazos necesita una decisión

`FH+GH+LH+PH = H` es exacta contra **nuestros** datos sanos (1999 da 4.957 = 4.957). Pero contra el
CSV de Retrosheet **no va a dar exacto**, por dos razones que no son errores:

1. A Retrosheet le falta la trayectoria en **~2,5%** de los hits (126 filas en 2000, 115 en 2001,
   0 en 1999). Quedan fuera de los cuatro conteos.
2. Nuestro maestro de dominicanos es **~10% más amplio** que el join con `dglMaster`, medido en 1999
   sobre las cuatro categorías y también sobre HR (569 contra 515). Es diferencia de población.

Por eso el PowerShell exporta **dos** totales, `h_typed` (hits con trayectoria) y `h_all` (todos).
Falta decidir:

- [ ] ¿Contra cuál compara el loader? `h_typed` hace la prueba exacta pero solo verifica coherencia
      interna del CSV. `h_all` compara contra la realidad pero nunca dará cero.
- [ ] Si es `h_all`, ¿con qué tolerancia? Un 3% dejaría pasar el ruido normal y seguiría atajando un
      export cortado a la mitad, que es lo que la prueba tiene que cazar.
- [ ] Qué se hace con el ~2,5% sin trayectoria: se ignora (los coeficientes quedan levemente
      subestimados, mucho menos que hoy) o se reparte proporcionalmente.

Hasta que se decida, `BattedBallHitsLoader.checks()` compara contra el `__h` que le llegue — hoy
mapeado a la columna `h`, que este CSV ya no trae con ese nombre. **Hay que ajustarlo antes de la
primera carga real.**
