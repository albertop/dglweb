"""Comprobar el canal de avisos: token, chat id y un mensaje de prueba.

    manage.py telegram_check           # diagnostica: token válido, chat id configurado
    manage.py telegram_check --buscar  # busca el chat id en los mensajes recibidos
    manage.py telegram_check --probar  # manda un mensaje de verdad

Existe porque conectar un bot de Telegram tiene un paso que confunde a todo el mundo: el chat id no
te lo dan, hay que sacarlo de `getUpdates`, y `getUpdates` solo devuelve algo si vos le escribiste
primero al bot —un bot no puede iniciar la conversación—. Armar esa URL a mano con el token pegado
es justo el momento en que un secreto termina en el historial del navegador.
"""

from typing import Any

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from dglweb.core import notify

_API = "https://api.telegram.org/bot{token}/{metodo}"
_TIMEOUT = 10.0


class Command(BaseCommand):
    help = "Comprueba la configuración de los avisos por Telegram."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--buscar", action="store_true", help="Busca el chat id en los mensajes recibidos.")
        parser.add_argument("--probar", action="store_true", help="Manda un mensaje de prueba al chat configurado.")

    def _llamar(self, metodo: str) -> dict[str, Any]:
        respuesta = httpx.get(_API.format(token=settings.TELEGRAM_BOT_TOKEN, metodo=metodo), timeout=_TIMEOUT)
        datos: dict[str, Any] = respuesta.json()
        return datos

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR("Falta TELEGRAM_BOT_TOKEN en .env. Pedilo a @BotFather con /newbot."))
            return

        try:
            yo = self._llamar("getMe")
        except httpx.HTTPError as error:
            self.stderr.write(self.style.ERROR(f"No se pudo hablar con Telegram: {error}"))
            return
        if not yo.get("ok"):
            self.stderr.write(self.style.ERROR(f"El token no sirve: {yo.get('description', 'sin detalle')}"))
            return
        self.stdout.write(self.style.SUCCESS(f"Token válido — bot @{yo['result']['username']}"))

        if options["buscar"]:
            self._buscar_chat()
        if not settings.TELEGRAM_CHAT_ID:
            self.stdout.write("Falta TELEGRAM_CHAT_ID. Corré con --buscar tras escribirle al bot.")
            return
        self.stdout.write(f"Chat configurado: {settings.TELEGRAM_CHAT_ID}")

        if options["probar"]:
            enviado = notify.enviar("✅ Prueba de avisos de dglweb. Si leés esto, el canal funciona.")
            estilo = self.style.SUCCESS if enviado else self.style.ERROR
            self.stdout.write(estilo("Mensaje de prueba enviado." if enviado else "No se pudo enviar (ver el log)."))

    def _buscar_chat(self) -> None:
        """Los chats que le escribieron al bot. Es el paso que nadie adivina la primera vez."""
        actualizaciones = self._llamar("getUpdates").get("result") or []
        chats = {}
        for item in actualizaciones:
            mensaje = item.get("message") or item.get("my_chat_member") or {}
            chat = mensaje.get("chat") or {}
            if chat.get("id") is not None:
                chats[chat["id"]] = chat.get("username") or chat.get("title") or chat.get("first_name") or ""

        if not chats:
            self.stdout.write(
                "Ningún mensaje recibido todavía. Un bot no puede escribir primero: buscá el bot en "
                "Telegram, mandale cualquier cosa, y volvé a correr esto."
            )
            return
        self.stdout.write("Chats que le escribieron:")
        for chat_id, quien in chats.items():
            self.stdout.write(f"  TELEGRAM_CHAT_ID={chat_id}   ({quien})")
