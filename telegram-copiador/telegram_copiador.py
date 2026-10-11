"""Copia mensagens de um grupo do Telegram para outro, usando a sua conta.

Configuração via variáveis de ambiente (ou arquivo .env, veja .env.example).
Na primeira execução o Telegram pede seu telefone e o código de login;
depois disso a sessão fica salva em copiador.session.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient, events

load_dotenv()

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ.get("TG_SESSION", "copiador")


def _entidade(valor: str):
    """Aceita ID numérico (-100123...) ou @username / link do grupo."""
    valor = valor.strip()
    try:
        return int(valor)
    except ValueError:
        return valor


ORIGEM = _entidade(os.environ["TG_ORIGEM"])
DESTINO = _entidade(os.environ["TG_DESTINO"])

client = TelegramClient(SESSION, API_ID, API_HASH)


@client.on(events.Album(chats=ORIGEM))
async def copiar_album(event):
    await client.send_file(
        DESTINO,
        [m.media for m in event.messages],
        caption=[m.message for m in event.messages],
    )


@client.on(events.NewMessage(chats=ORIGEM))
async def copiar_mensagem(event):
    if event.grouped_id:  # fotos/vídeos em álbum são tratados acima
        return
    try:
        await client.send_message(DESTINO, event.message)
    except Exception as e:  # ex.: grupo com cópia restrita
        print(f"Falha ao copiar mensagem {event.id}: {e}", file=sys.stderr)


async def listar_grupos():
    """Ajuda a descobrir os IDs: python telegram_copiador.py --listar"""
    async for d in client.iter_dialogs():
        if d.is_group or d.is_channel:
            print(f"{d.id}\t{d.name}")


async def main():
    await client.start()
    if "--listar" in sys.argv:
        await listar_grupos()
        return
    print("Copiador rodando. Ctrl+C para parar.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
