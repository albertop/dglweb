# Reglas de autoridad

Decisiones del dueño que **no se discuten ni se reinterpretan**. Van acá y no en un comentario porque
valen para todo el sitio y para cualquiera que escriba código en él, hoy o dentro de dos años.

Si algo que vas a escribir contradice una de estas reglas, la regla gana. Si crees que una está mal,
pregunta antes de cambiarla — no la ajustes por tu cuenta.

---

## 1. Quién es dominicano

**La ÚNICA forma de determinar si un jugador es dominicano es si pertenece a `dgl_master` o a
`dom_players`.** El `birthCountry` que devuelve la API de MLB **no sirve para eso, no es confiable**.

Ningún campo de país decide, ni el nuestro ni el de la fuente. La unión de esas dos tablas es el
universo dominicano y punto. Está implementado en `dglweb/players/universe.py`, y cualquier consulta
que necesite el universo debe pasar por ahí en vez de filtrar por país.

**Y no se audita quién está en la tabla.** Si un nombre parece no encajar, no encaja con lo que uno
cree saber, que no es la autoridad. Un jugador puede ser dominicano por madre o padre y haber jugado
con la selección sin que su lugar de nacimiento lo diga — le pasa a Austin Wells, que jugó el Clásico
Mundial con República Dominicana. Quién entra y quién sale de esas tablas lo decide el dueño; no hay
nada que revisar ni que reportar.

## 2. Siglas de estadísticas: en inglés, nunca en español

**No se usan abreviaturas en español en ninguna parte del sitio.** Ni en la portada, ni en los
perfiles, ni en las tablas del Backoffice, ni en los nombres visibles de los modelos.

| Se escribe | No se escribe |
| ---------- | ------------- |
| `RBI`      | `CI`          |
| `R`        | `CA`          |
| `ER`       | `CL`          |
| `AB`       | `VB`          |
| `AVG`      | `AVE`         |
| `W` / `L`  | `G` / `P`     |
| `RP`       | `CP`          |

Es como se lee el béisbol en República Dominicana: el aficionado ve RBI y HR, no CI ni JR. Traducir
las siglas no acerca el dato a nadie, lo aleja.

Esto vale para las **siglas**. El texto corrido va en español, como todo el sitio.

## 3. La base de datos es la de 10.0.0.39

El sitio sirve desde la base remota. Un contenedor que apunte a la base local muestra números que no
son los del sitio y no hay nada en pantalla que lo delate — ya pasó una vez.

## 4. `albertop_DGL` (SQL Server) está desactualizada

**No se sacan datos de esa base.** Sirve solo como referencia de diseño.

## 5. Nada de asumir esquemas

Las tablas, los campos y las fuentes los define el dueño. No se inventan columnas ni se deduce de
dónde sale un dato: se pregunta.
