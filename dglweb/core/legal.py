"""Los datos que las páginas legales no pueden inventarse.

Un aviso de privacidad que dice «contáctanos» sin decir a quién ni dónde no sirve de nada: la Ley
172-13 y el RGPD piden que el responsable esté identificado con nombre y una vía de contacto real.
Esos datos NO los puede sacar el código de ningún sitio, así que viven acá arriba, en un solo lugar,
y no repartidos por tres plantillas donde cambiar el correo significa buscarlo tres veces.

CONFIRMAR ANTES DE ANUNCIAR EL SITIO
------------------------------------
Lo de abajo es lo que se sabe hoy. Cada línea marcada con `# ← confirmar` es una afirmación sobre el
mundo real que hay que verificar con el dueño; publicarla equivocada es peor que no publicarla,
porque un aviso legal con datos falsos es un incumplimiento por sí mismo.

Y una advertencia que no cabe en la página pero sí acá: estos textos los redactó el equipo del
proyecto, no un abogado. Describen con exactitud lo que el sitio hace —eso está medido y hay tests
que lo sostienen— pero la calificación jurídica de esa descripción la tiene que revisar alguien
habilitado antes de que el sitio reciba anuncios o abra cuentas de usuario.
"""

from datetime import date

# Quién responde. Mientras el sitio sea de una persona y no de una sociedad, va el nombre de la
# persona: inventar una razón social que no existe en el registro mercantil sería peor que esto.
RESPONSABLE = "Alberto Perdomo"  # ← confirmar: ¿persona física o una sociedad con RNC?
DOMINIO = "dominicanosengrandesligas.com"
CONTACTO = "privacidad@dominicanosengrandesligas.com"  # ← confirmar: que el buzón exista y se lea
PAIS = "República Dominicana"

# El alojamiento importa porque una transferencia internacional de datos hay que declararla. El VPS
# está fuera del país, así que se dice; si algún día se muda, se cambia acá.
ALOJAMIENTO = "un proveedor de servidores en la nube fuera de la República Dominicana"  # ← confirmar

# Cuánto viven los registros del servidor. No es un número decorativo: es el compromiso que se
# adquiere con quien visita, y el proxy tiene que estar configurado para cumplirlo.
DIAS_DE_REGISTROS = 30  # ← confirmar contra la configuración real del proxy

# La fecha que sale en «última actualización». Se toca A MANO cuando cambia el texto, y por eso es
# una constante y no `date.today()`: una fecha que se mueve sola diría que el aviso se revisó hoy
# cuando lleva meses igual, que es exactamente la mentira que la fecha existe para evitar.
ACTUALIZADO = date(2026, 7, 27)

# Las tres páginas, en el orden en que se enlazan en el pie. La vista y las pruebas salen de acá:
# añadir una cuarta es añadir una línea y su plantilla, sin tocar `urls.py` ni la vista.
PAGINAS = {
    "privacidad": "Política de privacidad",
    "terminos": "Términos de servicio",
    "cookies": "Política de cookies",
}
