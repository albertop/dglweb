# Datos de apoyo desde DGL (CSV → Postgres)

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

**1. `static_data/` — los PowerShell.** Un script por dataset. Cada uno lleva:

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

### 2. Salarios — pendiente de especificar

Existe en DGL. Sin diseño todavía: falta definir el grano (¿por jugador-temporada? ¿por contrato?) y
qué se publica.

### 3. Transacciones — pendiente de especificar

Existe en DGL. Sin diseño todavía.

## Decisiones abiertas

- [ ] La **ruta de salida** de los CSV (constante en cada PowerShell). — *lo define el dueño*
- [ ] **(a) tabla propia** vs **(b) update de columnas** para los tipos de batazo. Recomendado: (a).
- [ ] Si el CSV se versiona en el repo o vive fuera. Vale la pena decidirlo temprano: son datos
      derivados de una base que no es pública, y el repo no es el lugar obvio.
- [ ] Quién puede subir (hoy el Backoffice es solo staff; la restricción por rol es de Fase 5).
