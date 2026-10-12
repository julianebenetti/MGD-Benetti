#!/usr/bin/env python3
"""
Confere o bot e o grupo e cria os tópicos (pastas), gravando os IDs no .env.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv, set_key

from telegram_handler import TelegramBot

TOPICS = [
    ('TELEGRAM_TOPIC_ENVIOS', '📥 Envios', 0x6FB9F0),
    ('TELEGRAM_TOPIC_EDITADOS', '✅ Editados', 0x8EEE98),
    ('TELEGRAM_TOPIC_AGENDA', '⏰ Agenda', 0xFF93B2),
    ('TELEGRAM_TOPIC_POSTADOS', '🚀 Postados', 0xFFD67E),
    ('TELEGRAM_TOPIC_PENDENCIAS', '📌 Pendências', 0xFB6F5F),
]


def fail(msg: str):
    print(f"❌ {msg}")
    sys.exit(1)


def check(bot: TelegramBot, chat_id: str):
    token = bot.token
    if not token or ':' not in token or token != token.strip() or token.startswith(('"', "'")):
        fail("TELEGRAM_BOT_TOKEN vazio ou com espaço/aspas no .env. Cole só o código, logo depois do '='.")
    try:
        me = bot.call('getMe')
    except Exception:
        fail("O Telegram não reconheceu o TELEGRAM_BOT_TOKEN. Use o código NOVO do @BotFather "
             "(o antigo para de funcionar depois do /revoke) e confira se colou inteiro.")
    print(f"✅ Bot reconhecido: @{me['username']}")

    try:
        chat = bot.call('getChat', data={'chat_id': chat_id})
    except Exception as e:
        fail(f"Grupo {chat_id} não encontrado ({e}). Confira o TELEGRAM_CHAT_ID e se o bot está no grupo.")
    print(f"✅ Grupo: {chat.get('title')}")
    if not chat.get('is_forum'):
        fail("O grupo está com Tópicos DESATIVADOS. No Telegram: nome do grupo → Editar → ative 'Tópicos'.")

    member = bot.call('getChatMember', data={'chat_id': chat_id, 'user_id': me['id']})
    if member.get('status') != 'administrator':
        fail("O bot não é administrador do grupo. Em Administradores, adicione o bot.")
    missing = [label for key, label in (('can_manage_topics', 'Gerenciar tópicos'),
                                        ('can_delete_messages', 'Apagar mensagens'))
               if not member.get(key)]
    if missing:
        fail(f"Falta dar ao bot a permissão: {', '.join(missing)} (Administradores → bot).")
    print("✅ Permissões do bot ok")


def main():
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    bot = TelegramBot(os.getenv('TELEGRAM_BOT_TOKEN', ''), chat_id or '0')
    check(bot, chat_id)

    for env_key, name, color in TOPICS:
        if os.getenv(env_key):
            print(f"↷ {name} já existe (id {os.getenv(env_key)})")
            continue
        try:
            thread_id = bot.create_topic(name, color)
        except RuntimeError as e:
            fail(f"Não consegui criar '{name}': {e}")
        set_key(str(env_path), env_key, str(thread_id), quote_mode='never')
        print(f"✅ {name} criado (id {thread_id})")


if __name__ == '__main__':
    main()
