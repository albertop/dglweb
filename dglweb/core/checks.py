"""Comprobaciones de arranque: lo que tiene que estar puesto para que el sitio pueda avisar.

POR QUÉ EXISTE ESTE ARCHIVO
---------------------------
El 2026-07-28 se descubrió que **producción llevaba muda desde siempre**, y el porqué es una asimetría
entre los dos entornos que no salta a la vista:

- En desarrollo funciona porque `settings/base.py` hace `environ.Env.read_env(BASE_DIR / ".env")` y el
  compose monta el proyecto entero en `/app`. Django lee el archivo y ya está.
- En producción **no hay ningún `.env` que leer**: `.dockerignore` lo excluye —bien excluido, un
  secreto no viaja dentro de una imagen— y la imagen no monta el árbol del proyecto. Ahí las
  variables solo pueden venir del entorno del contenedor, y nadie las puso.

Nada falló. `notify.configurado()` devolvía falso, `enviar()` escribía una línea en nivel DEBUG y se
iba, y el refresco diario podía romperse todas las noches sin que nada lo dijera. **Un canal de avisos
apagado se ve exactamente igual que uno encendido por el que no ha pasado nada** — esa es toda la
dificultad, y es lo que hizo que durara.

Peor todavía: los avisos SÍ llegaban, desde desarrollo, así que la evidencia disponible decía que el
canal funcionaba. Hasta que se añadió la etiqueta `[PROD]`/`[DEV]` no había forma de notar que hablaba
siempre el mismo.

El sistema de comprobaciones de Django corre en cada `manage.py` y en cada arranque, así que a partir
de acá el silencio deja rastro.

AVISO Y NO ERROR, DELIBERADAMENTE
----------------------------------
Un `checks.Error` impide arrancar. Eso convertiría «no puedo avisar» en «no puedo servir el sitio», y
es exactamente la regla que el dueño puso el 2026-07-27 para el proxy de MLB: **nunca bloquear un
proceso automático por algo que no impide trabajar**. El sitio funciona perfectamente sin Telegram;
lo que no puede es contar que se rompió.

Solo se queja en PRODUCCIÓN. En desarrollo lo normal es no tener el canal puesto, y una advertencia
que sale siempre es una advertencia que nadie lee.
"""

from typing import Any

from django.core.checks import CheckMessage, Warning, register


@register()
def avisos_configurados(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:  # noqa: ANN401
    """W001 — en producción, que el canal de avisos tenga a dónde escribir."""
    from dglweb.core import notify

    if notify.entorno() != "PROD" or notify.configurado():
        return []
    return [
        Warning(
            "El canal de avisos está apagado: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.",
            hint=(
                "El sitio funciona igual, pero si el refresco diario falla nadie se va a enterar. "
                "Ojo: ponerlas en `.env` NO basta — ese archivo solo sustituye ${VAR} dentro del "
                "compose. Tienen que estar en el bloque `environment:` del servicio, y en Portainer "
                "además con valor en las «Environment variables» del stack. "
                "Comprobar con `manage.py telegram_check`."
            ),
            id="core.W001",
        )
    ]
