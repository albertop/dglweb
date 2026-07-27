"""Quién puede hacer qué en el CMS. Tres roles y una regla que los ordena.

**Redactores** escriben y editan artículos, y NO pueden publicar. Esa es la pieza que hace que el
workflow signifique algo: si el que escribe puede publicarse solo, la revisión es voluntaria, y una
revisión voluntaria es ninguna. Al terminar mandan el artículo a revisión.

**Editores** hacen todo lo anterior y además aprueban y publican. Son el destinatario de la tarea de
aprobación: cuando un redactor envía, les llega a ellos.

**Administradores** son los dueños del sitio. Además del CMS tienen el Backoffice —el maestro de
jugadores, el catálogo de métricas, la bitácora de ingesta— y las cargas de datos de apoyo, que
reemplazan tablas enteras. Un redactor no tiene por qué ver nada de eso.

POR QUÉ EN ESPAÑOL, SI WAGTAIL LOS TRAE EN INGLÉS
-------------------------------------------------
Wagtail crea de fábrica `Editors` y `Moderators`. Se renombran porque los nombres se ven en la
pantalla de un CMS que está entero en español y lo van a usar periodistas, no programadores. Ojo al
leer la documentación de Wagtail: su «Editors» es nuestro `REDACTORES` —el que escribe y no publica—
y su «Moderators» es nuestro `EDITORES`. La traducción no es literal a propósito: en una redacción,
el «editor» es justamente el que aprueba.

Los tres nombres viven acá y no repartidos por el código para que una comprobación de permisos no se
quede apuntando a un grupo que alguien renombró. Ya pasó en pequeño: la guarda de datos de apoyo
buscaba un grupo «Administrators» que no existía, así que en la práctica solo pasaban los
superusuarios — funcionaba, pero por accidente.
"""

REDACTORES = "Redactores"
EDITORES = "Editores"
ADMINISTRADORES = "Administradores"

# Los que pueden entrar al Backoffice y a las cargas de datos de apoyo.
MANDAN = (ADMINISTRADORES,)
