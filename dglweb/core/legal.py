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

# Quién responde. Es la agencia que gestiona el sitio, no la persona que escribe el código: quien
# responde ante un reclamo de datos personales tiene que ser quien decide qué se publica y para qué.
# Si Adcio Media está constituida, acá va su razón social registrada. Si es un nombre comercial y no
# una sociedad, «Adcio Media» está bien tal cual: lo que la ley pide es que se pueda identificar a
# quien responde, y con el nombre más el buzón de contacto se puede.
RESPONSABLE = "Adcio Media"
DOMINIO = "dominicanosengrandesligas.com"
# El buzón único del sitio. Uno solo y no tres alias por tema: un buzón que nadie lee es peor que no
# publicar ninguno, y tres multiplican por tres la posibilidad de que eso pase.
CONTACTO = "alberto@dominicanosengrandesligas.com"
PAIS = "República Dominicana"

# El alojamiento se nombra porque el proveedor procesa los registros del servidor por cuenta nuestra,
# y eso hay que declararlo. Deliberadamente NO dice en qué país: el VPS de producción todavía no
# existe —ver `docs/CONCEPT.md`, no se instala nada ahí hasta el big-bang— y afirmar hoy que está
# fuera del país sería inventarse un hecho. Cuando se contrate, acá se pone el proveedor y, si está
# en el extranjero, la frase de transferencia internacional. Es una línea.
ALOJAMIENTO = "un proveedor de infraestructura en la nube"

# Cuánto viven los registros del servidor. No es un número decorativo: es el compromiso que se
# adquiere con quien visita, y el proxy tiene que estar configurado para cumplirlo.
DIAS_DE_REGISTROS = 30  # ← confirmar contra la configuración real del proxy

# La fecha que sale en «última actualización». Se toca A MANO cuando cambia el texto, y por eso es
# una constante y no `date.today()`: una fecha que se mueve sola diría que el aviso se revisó hoy
# cuando lleva meses igual, que es exactamente la mentira que la fecha existe para evitar.
ACTUALIZADO = date(2026, 7, 27)

# EL AVISO DE RETROSHEET. Esto no es cortesía: es la ÚNICA condición que pone Retrosheet a cambio de
# dejar usar sus datos para lo que sea, incluso vendiéndolos. Su licencia dice, literalmente, que la
# declaración «must appear prominently».
#
# Va **en inglés y palabra por palabra**: lo que la licencia autoriza es ESTE texto, y una versión
# traducida o resumida es un texto distinto — quien concede el permiso es quien decide su forma. La
# traducción al español se pone al lado, marcada como tal, para quien la necesite.
#
# DÓNDE VA. Estuvo en el pie de todas las páginas y ahora está solo en los términos, por decisión del
# dueño (27-07-2026) al considerarlo redundante. Queda dicho que es la lectura menos conservadora de
# «prominently»: el aviso sigue publicado y enlazado desde el pie, pero a un clic de distancia. Si
# algún día Retrosheet objeta, la vuelta atrás es descomentar el bloque de `base.html`.
#
# `tests/test_legal.py` comprueba que sigue publicado y que nadie lo ha reescrito.
RETROSHEET = (
    "The information used here was obtained free of charge from and is copyrighted by Retrosheet. "
    'Interested parties may contact Retrosheet at "www.retrosheet.org".'
)

# Las tres páginas, en el orden en que se enlazan en el pie. La vista y las pruebas salen de acá:
# añadir una cuarta es añadir una línea y su plantilla, sin tocar `urls.py` ni la vista.
PAGINAS = {
    "privacidad": "Política de privacidad",
    "terminos": "Términos de servicio",
    "cookies": "Política de cookies",
}
