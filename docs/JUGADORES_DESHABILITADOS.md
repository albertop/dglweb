# Dar de baja a un jugador

Un inscrito que no debería estar (se cargó por error, no califica, se detectó un duplicado) se **da
de baja**, no se borra. Borrar es irreversible y además se lleva por CASCADE todas sus estadísticas,
que costaron años de backfill. La baja es un flag, y se revierte apagándolo.

Es un caso raro. Todo lo que sigue está pensado para que, cuando ocurra, no haya que acordarse de
nada.

## Qué pasa cuando se prende

| | |
|---|---|
| Perfil | `/jugador/<slug>/` devuelve **404**. Sacarlo de las listas no alcanza: el enlace directo sobrevive en Google y en cualquier chat |
| Búsqueda y listados | No aparece. Sale del manager por defecto, así que también lo cubre lo que todavía no existe |
| Liderazgos y Puestos | No aparece, **y los puestos de los demás se cierran detrás de él** |
| Totales de carrera | No se calculan |
| Estadísticas crudas | **Se conservan intactas** y se le siguen actualizando a diario |
| Backoffice | Sí aparece, es donde se reactiva |

Lo de seguir bajándole estadísticas es deliberado: cuesta lo mismo y hace que reactivarlo sea
instantáneo. Si se lo excluyera del ingest, al volver le faltarían las temporadas del período de baja
y habría que hacer un backfill a mano.

## La regla para lo que venga

> **Si una consulta parte de `Player`, el manager por defecto ya te cubre.
> Si parte de una tabla de stats, tenés que pasarla por `only_visible()`.**

`Player.objects` es el manager filtrado — el que se usa sin pensar es el seguro. Ver a los ocultos
hay que **pedirlo** con `Player.todos`, que es lo que usan el ingest diario, los `parity_*`, el
import del maestro y la validación de los CSV de apoyo: la tubería trabaja con todos.

Y hay un agujero que el manager no tapa, que es el que importa: **`build_leaders` y
`build_career_totals` nunca consultan `Player`**. Leen `Batting`/`Pitching`/`Fielding` y agrupan por
`player_id` crudo. Por eso existe `dglweb.players.visibility.only_visible()`, y por eso hay que
llamarlo en cada punto de entrada de esos motores.

### Por qué se filtra al construir y no al mostrar

Los liderazgos están **materializados**: `dgl_leader` guarda el puesto ya calculado. Esconder una
fila al leer dejaría la lista numerada 1, 2, 4 — y, peor, al que venía cuarto en un puesto que no le
corresponde, porque su `rank` ya está escrito. La exclusión tiene que pasar cuando se construyen.

De ahí que prender o apagar el flag **dispare la reconstrucción solo**
(`dglweb.stats.rebuilds.DERIVED`), en segundo plano y al confirmarse el commit. Tarda alrededor de un
minuto. Si el proceso se reinicia a mitad, el cron de las 7:30 lo rehace igual.

## Dos detalles del `_default_manager`

Django distingue el manager que usa el código (`Player.objects`) del que usa su plomería
(`_default_manager`). Acá el segundo es **`todos`, el que NO filtra**, y es a propósito:

- El Backoffice resuelve la pantalla de edición con él. Con el filtrado, editar a un jugador oculto
  daba **404** — o sea, la baja era irreversible desde la interfaz.
- La validación de unicidad de los formularios también lo usa. Con el filtrado, un `dgl_id` ocupado
  por un jugador oculto pasaba desapercibido al dar de alta a otro.

Por eso la vista pública pide el manager filtrado de forma explícita:
`get_object_or_404(Player.objects, ...)`.

## El motivo es obligatorio

`disabled_reason` no puede quedar vacío cuando `hidden` está prendido; lo valida `Player.clean()` y
lo muestra el formulario del Backoffice. Un booleano solo dice "está apagado": dentro de un año, ese
texto es lo único que va a explicar por qué falta ese jugador y si puede volver.
