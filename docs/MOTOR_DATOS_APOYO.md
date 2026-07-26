# El motor de datos de apoyo — cómo agregar una tabla

Este documento es el manual de operación. El **por qué** de todo esto está en
`docs/DATOS_DE_APOYO.md`; acá está el **cómo**.

## La idea

El motor (`dglweb/stats/staticdata/engine.py`) no sabe nada de ningún dataset. Sabe leer un CSV,
verificar que las columnas estén, exigir que la clave natural sea única, armar la comparación contra
lo que ya hay, y escribir en una transacción. Nada más.

Todo lo que es propio de un dataset —qué columna es qué campo, cómo se resuelve un identificador
externo, qué hace que ese dato esté sano— vive en su **`Loader`**. Agregar una tabla es escribir un
loader; el motor no se toca.

```
leer  ──▶  validar  ──▶  comparar  ──▶  aplicar
             │              │              └─ trunca o hace upsert, atómico
             │              └─ lo que ve el usuario antes de decidir
             └─ si falla, no hay botón de confirmar
```

## Agregar un dataset nuevo — los cuatro pasos

### 1. El modelo

Una tabla normal de Django. **Que sea suya**: no cargues un CSV sobre una tabla que llena el proxy —
truncarla destruiría el backfill. Si el dato tiene que convivir con datos del proxy, va en su propia
tabla y el paso que lo consume decide cuál prefiere.

### 2. El PowerShell

En `static_data/scripts/`, uno por dataset. Lleva la ruta de salida en una constante, el SQL a la vista, y un
encabezado que explique por qué existe. Escribe el CSV en `static_data/csv/`, que está en
`.gitignore`: los scripts se versionan —son código y explican de dónde sale cada dato— pero los
volcados no.

### 3. El loader

En `loaders.py`. Lo mínimo son tres atributos:

```python
@register
class SalariosLoader(Loader):
    table = "dgl_salario"          # tiene que coincidir con StaticDataset.table
    model = Salario
    columns: ClassVar[dict[str, str]] = {"mlb_id": "player", "season": "season", "monto": "amount"}
```

Y dos hooks, solo si hacen falta:

**`prepare()`** — corre una vez antes de leer las filas. Acá van los lookups que si no serían por
fila. Sin esto, un `resolve` que consulte la base hace una query por línea del CSV:

```python
    def prepare(self) -> None:
        self._by_mlb = dict(Player.objects.values_list("player_id", "pk"))
```

**`resolve(row)`** — traduce una fila del CSV a kwargs del modelo. Devolver `None` la descarta en
silencio, que es lo correcto cuando el CSV trae filas que no son nuestras. Lanzar `ValueError` la
reporta como fila ilegible:

```python
    def resolve(self, row):
        pk = self._by_mlb.get(row["mlb_id"])
        if pk is None:
            return None                      # no está en el maestro: se ignora
        return {"player_id": pk, "season": int(row["season"]), "amount": int(row["monto"])}
```

**`checks(rows)`** — la prueba de aceptación del dataset. Es lo más valioso que se escribe acá:
el conocimiento que solo aplica a estos datos.

```python
    def checks(self, rows):
        malas = [r for r in rows if r["amount"] < 0]
        return [Problem(f"{len(malas)} salario(s) negativos.", ...)] if malas else []
```

Una columna del CSV que solo sirva para validar y no se guarde se mapea a un campo con prefijo
`__`; el motor lo descarta antes de escribir. Así el loader de batazos compara los cuatro tipos
contra el total `H` sin tener que guardarlo.

### 4. La fila en el registro

En el Backoffice, crear el `StaticDataset`: tabla destino, nombre del PowerShell, nombre del CSV,
modo (truncate o upsert), y la **clave natural**.

La clave es obligatoria en los dos modos, y casi siempre compuesta: acá ninguna tabla de stats se
identifica con una sola columna.

El formulario valida la fila al guardarla (`StaticDataset.clean()`), y rechaza las tres
configuraciones que el motor no puede cumplir:

| Se escribe | Por qué no sirve |
|---|---|
| Una tabla sin loader | El motor no sabría leer su CSV. El mensaje lista las tablas que sí tienen |
| Una clave con columnas que el modelo no tiene | El chequeo de duplicados y "qué desaparece" agrupan por ella. La FK vale de las dos formas: `player` y `player_id` |
| Upsert sin restricción de unicidad detrás de la clave | `update_or_create` dejaría convivir dos filas iguales y a la carga siguiente reventaría al encontrar las dos: el modo se llama idempotente y no lo sería |

Se valida acá y no en la carga porque agregar un dataset es crear una fila y no tocar código — la
contracara es que se puede escribir una configuración imposible, y sin esto nada se quejaba hasta el
día de la carga, que es el peor momento para enterarse: el CSV ya está hecho y hay alguien esperando.

## Lo que el motor hace solo

No hay que escribirlo en cada loader:

| | |
|---|---|
| Columnas ausentes | Si al CSV le falta una columna declarada, corta antes de leer filas |
| Clave duplicada | Se evalúa la combinación entera. Corre **en los dos modos** |
| Filas ilegibles | Las agrupa y muestra una muestra con el número de línea |
| Qué desaparece | Claves que están en la tabla y no en el CSV. Solo con truncate |
| Sumas por columna | Antes, después y % de cambio, en cada columna numérica que sea una **medida** |
| Atomicidad | El truncate y el insert van juntos: o queda todo, o queda lo viejo |

## Por qué la unicidad se valida siempre

Es el error que más caro sale y el menos obvio. Con **upsert**, una clave repetida hace que la
segunda fila pise a la primera sin decir nada. Con **truncate** es peor de otra forma: no pisa nada,
inserta las dos, y la tabla queda con un registro fantasma que nadie pidió y que ninguna consulta
espera.

En los dos casos el origen es el mismo —un export mal hecho— así que el motor no lo trata como aviso:
lista las filas culpables y no deja confirmar.

## Por qué "qué desaparece" solo aplica con truncate

Con upsert las filas que no vienen en el CSV sobreviven. Decir "no se pierde nada" en ese modo sería
leerlo como una propiedad del CSV cuando es una propiedad del modo. La pantalla lo distingue.

Y es la señal más importante que muestra: **un export que se cortó a la mitad no se ve de ninguna
otra forma.** Es exactamente el fallo que originó todo esto — la fuente de MLB entregó el 1,8% de los
hits tipificados de 2000 y el sitio lo publicó durante años.

## Los tests

`tests/test_staticdata.py` prueba el motor con un **loader de juguete**, no con el de batazos. El
punto del motor es que no sabe nada de ningún dataset; un test atado al dataset real no probaría eso.

Al agregar un loader, lo que hay que testear es **su** `checks()` — la regla de negocio. El resto ya
está cubierto.

## `post_apply()` — cuando cargar el dato no alcanza

El tercer hook, y el menos obvio. Corre **después de escribir y dentro de la misma transacción**, y
es para los datasets que corrigen un dato del que otros dependen.

El caso que lo motivó: cargar los hits por tipo no sirve de nada si `GB%`, `FB%`, `LD%` y `PU%`
—que salen de ellos— siguen calculados con los viejos. El loader de batazos lo usa para reescribir
los cuatro conteos en la fila de temporada y recalcular sus coeficientes de una vez.

Al ir dentro de la transacción, o queda todo consistente o no queda nada: nunca los hits nuevos con
los porcentajes viejos.

```python
    def post_apply(self, rows):
        # recalcular lo que dependa de este dato
```

La mayoría de los datasets no lo necesitan. Un salario no alimenta ningún cálculo derivado.

## `no_sum` — las columnas numéricas que no son medidas

La pantalla de comparación suma cada columna numérica antes y después, para que un cambio grande
salte a la vista. Eso sirve para los **conteos** —hits, carreras, entradas— y no sirve para los
**atributos**: la suma de los pesos de 9.133 peloteros dio 1.640.576 libras, un número sin
significado en una fila que invitaba a interpretarlo.

Los identificadores ya quedan fuera solos (la clave natural no es una medida; sumar `season` daba la
suma de todos los años). Lo demás lo declara el loader:

```python
    no_sum = ("weight",)
```

Un dataset puro de atributos, como `dom_players`, termina sin ninguna columna en la comparación — y
está bien: ahí lo único que importa es cuántas filas entran y cuántas se van.

## `rebuilds` — lo que hay que rehacer después

`post_apply()` deja consistente lo que se puede arreglar en el momento; `rebuilds` declara lo que
hay que **volver a derivar entero**. Es una tupla de comandos, en orden de dependencia:

```python
    rebuilds = ("build_career_totals", "build_leaders")
```

Por qué existe: sin esto, la carga quedaba a medias sin decirlo. Los hits nuevos entraban y los
coeficientes de temporada quedaban al día, pero los totales de carrera los seguían sumando viejos y
los liderazgos los seguían rankeando viejos. El sitio servía números vencidos hasta que alguien se
acordaba de correr `build_leaders` a mano — y "acordarse" no es un mecanismo.

Tres decisiones que conviene entender antes de tocarlo:

- **Fuera de la transacción.** `build_leaders` tarda cerca de un minuto y reescribe 400.000 filas;
  sostener la transacción de la carga todo ese rato bloquearía la tabla de origen sin necesidad.
  Además son cosas distintas: si la reconstrucción falla, el dato igual quedó bien cargado y lo
  único pendiente es volver a derivar, que es reintentable.
- **En un hilo.** Si no, la respuesta HTTP espera ese minuto largo, que es justo el tipo de request
  que un proxy corta a los 30 segundos — y cortarla no detiene el trabajo, solo deja al usuario sin
  saber cómo terminó. Es un hilo suelto y no una cola porque este proyecto no tiene worker, la carga
  la dispara una persona que está mirando, y el cron de las 7:30 ya es la red de seguridad si el
  proceso se reinicia a mitad.
- **Queda en el log.** Cada comando se registra solo en `IngestRun` (vía `record_run`), así que una
  reconstrucción disparada desde el Backoffice se ve igual que la del scheduler.

Un dataset que no alimenta ningún cálculo —salarios, otra vez— no declara nada y no lanza ningún
hilo.

## Dónde dejar el CSV en el VPS

En desarrollo el CSV sale del PowerShell a `static_data/csv/` y se sube desde el navegador de la
misma máquina. **En el servidor no hay navegador ni SQL Server**, así que hace falta una ruta
conocida donde dejar el archivo:

```
/app/uploads          (volumen dglweb_uploads, creado en el Dockerfile)
```

Va **fuera** de `/app/static_data` a propósito: esa carpeta es de los PowerShell —código, versionado,
y excluida de la imagen— y esta es dato de operación.

El flujo en el VPS:

```bash
scp batted_ball_hits.csv usuario@vps:/tmp/
docker cp /tmp/batted_ball_hits.csv <contenedor-web>:/app/uploads/
```

y desde ahí se sube por el Backoffice como siempre. El volumen es nombrado, así que el archivo
sobrevive a un redeploy — útil si hay que repetir una carga.
