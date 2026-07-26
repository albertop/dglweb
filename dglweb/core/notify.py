"""Avisos por Telegram: lo que conviene que llegue al bolsillo en vez de esperar en un log.

Dos cosas la usan, y son de naturaleza opuesta. El refresco diario avisa cuando **algo se rompió** —
el monitor externo dirá «503», esto dice cuál paso—. Y la detección de debuts avisa cuando pasó algo
**bueno y raro**: un dominicano llegó a Grandes Ligas, un puñado de veces al año, y hoy ese aviso
espera en el log de ingesta a que alguien vaya a mirarlo.

Tres reglas que no se negocian, porque un canal de avisos mal hecho hace más daño que no tenerlo:

**Nunca rompe a quien la llama.** Un refresco de 400.000 filas no puede fallar porque Telegram esté
caído. Todo error se registra y se traga; la función devuelve si pudo o no, y el llamador sigue.

**Sin configurar, no hace nada y no se queja.** El token y el chat viven en `.env`. En desarrollo no
están, y llenar la consola de advertencias por eso enseñaría a ignorar las advertencias de verdad.

**Texto plano, sin `parse_mode`.** Con Markdown o HTML, un nombre con un guion bajo o un signo suelto
rompe el mensaje entero o —peor— lo hace rechazar por la API. Los nombres de peloteros vienen de una
fuente externa; no vale la pena escaparlos para poner una palabra en negrita.
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# Corto a propósito: esto cuelga del final de un job. Si Telegram no contesta en cinco segundos, el
# aviso se pierde y el job sigue — al revés sería sostener el pipeline por un mensaje.
_TIMEOUT = 5.0
_API = "https://api.telegram.org/bot{token}/sendMessage"


def configurado() -> bool:
    """¿Hay a dónde mandar? Sirve para no armar el mensaje si nadie lo va a recibir."""
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def enviar(texto: str) -> bool:
    """Manda el mensaje. Devuelve si lo logró; nunca lanza.

    El valor de retorno es para los tests y para el log del llamador, no para decidir nada: si el
    aviso no sale, lo que estaba haciendo el llamador sigue siendo válido.
    """
    if not configurado():
        logger.debug("Telegram sin configurar; no se envía el aviso.")
        return False
    try:
        respuesta = httpx.post(
            _API.format(token=settings.TELEGRAM_BOT_TOKEN),
            json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": texto, "disable_web_page_preview": True},
            timeout=_TIMEOUT,
        )
        respuesta.raise_for_status()
    except (httpx.HTTPError, ValueError):
        # `ValueError` cubre una respuesta que no es JSON válido. Se registra con traza porque un
        # canal de avisos que falla en silencio es exactamente el problema que vino a resolver.
        logger.warning("No se pudo enviar el aviso por Telegram.", exc_info=True)
        return False
    return True
