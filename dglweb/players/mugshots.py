"""Dónde está el retrato de un pelotero.

POR QUÉ UN MÓDULO Y NO UNA F-STRING EN CADA SITIO
-------------------------------------------------
La ruta se armaba a mano en el widget de líderes y en el de destacados. Con el retrato del perfil
serían tres copias de la misma cadena, y el día que cambie la carpeta —o que se agregue un tamaño—
hay que acordarse de los tres. Acá está una vez, con los tamaños que existen de verdad.

POR QUÉ NO SE USA `{% static %}`
--------------------------------
Los retratos NO entran a la imagen de Docker ni los recoge `collectstatic`: son 1.274 archivos que se
bajan aparte con `download_mugshots.ps1` y la carpeta se monta en el contenedor. Nunca están en el
manifiesto de producción, así que `{% static %}` fallaría al buscarlos. Se sirven por su ruta literal.

QUÉ PASA CON EL QUE NO TIENE FOTO
---------------------------------
Falta a menudo, y no es un error: el script baja a los que jugaron en las dos últimas temporadas —637
de los 981 del maestro— así que un tercio de los perfiles no tiene retrato, y los siete de las Ligas
Negras no lo van a tener nunca.

Hay dos maneras de resolverlo y cada sitio usa la que le toca:

* Los **widgets** lo dejan en manos del navegador, con `onerror` en la etiqueta. Muestran veinte
  jugadores por página y casi todos tienen foto —son los que jugaron esta semana—, así que preguntar
  por el disco veinte veces por visita sería pagar por adivinar lo que el navegador sabe al pedirlo.
* La **ficha** pregunta antes, con `existe()`. Es un jugador y un acceso a disco, en una página que
  ya hace varias consultas a la base; y ahí sí importa, porque el `onerror` borra la foto DESPUÉS de
  que el navegador se dio el viaje: el nombre nace corrido 120px a la derecha y salta a su sitio
  cuando vuelve el 404. En un tercio de las fichas.
"""

from pathlib import Path

from django.conf import settings

# Los dos tamaños que baja `download_mugshots.ps1`, una carpeta cada uno. Si se agrega otro hay que
# bajarlo primero: acá solo se arma la ruta, nadie redimensiona nada al vuelo.
CHICO = 120  # los widgets de la portada
GRANDE = 360  # la ficha del jugador


def url(player_id: int, tamano: int = CHICO) -> str:
    """La ruta del retrato. No promete que el archivo exista — ver la cabecera."""
    return f"{settings.STATIC_URL}img/mugshots/{tamano}/{player_id}.png"


def existe(player_id: int, tamano: int = CHICO) -> bool:
    """Si el archivo está en el disco. Un acceso a disco: usar por jugador, no por lista.

    Mira la carpeta de origen —la que monta el compose— y no `STATIC_ROOT`: los retratos no los
    recoge `collectstatic`, así que en producción no están ahí. Es la misma carpeta que sirve las
    peticiones, de modo que la respuesta vale para lo que el navegador va a pedir después.
    """
    return (Path(settings.STATICFILES_DIRS[0]) / "img" / "mugshots" / str(tamano) / f"{player_id}.png").is_file()
