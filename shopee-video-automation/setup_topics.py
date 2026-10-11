#!/usr/bin/env python3
"""
Cria os tópicos (pastas) do grupo e grava os IDs no .env.
Pré-requisitos: Tópicos ativados no grupo e o bot admin com permissão "Gerenciar tópicos".
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv, set_key

from telegram_handler import TelegramMonitor

TOPICS = [
    ('TELEGRAM_TOPIC_ENVIOS', '📥 Envios', 0x6FB9F0),
    ('TELEGRAM_TOPIC_EDITADOS', '✅ Editados', 0x8EEE98),
    ('TELEGRAM_TOPIC_POSTADOS', '🚀 Postados', 0xFFD67E),
]


def main():
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    bot = TelegramMonitor(os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID'])

    for env_key, name, color in TOPICS:
        if os.getenv(env_key):
            print(f"↷ {name} já existe (id {os.getenv(env_key)})")
            continue
        try:
            thread_id = bot.create_topic(name, color)
        except RuntimeError as e:
            print(f"❌ Não consegui criar '{name}': {e}")
            print("   Confira: Tópicos ativados no grupo e bot admin com 'Gerenciar tópicos'.")
            sys.exit(1)
        set_key(str(env_path), env_key, str(thread_id))
        print(f"✅ {name} criado (id {thread_id})")


if __name__ == '__main__':
    main()
