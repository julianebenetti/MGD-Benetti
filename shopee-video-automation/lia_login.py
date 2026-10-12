#!/usr/bin/env python3
"""
Login (uma vez só) da conta do Telegram que manda os vídeos para a LiA.

Rode no VPS:  .venv/bin/python lia_login.py
Pede o telefone, o código que chega no seu Telegram e, se tiver, a senha de duas etapas.
O login fica em lia.session (só no VPS, nunca no GitHub). Depois: sudo systemctl restart shopee-video
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

from lia_sender import SESSION  # noqa: E402


def main():
    api_id, api_hash = os.getenv('TELEGRAM_API_ID'), os.getenv('TELEGRAM_API_HASH')
    if not (api_id and api_hash and api_id.strip().isdigit()):
        print("❌ Preencha TELEGRAM_API_ID (só números) e TELEGRAM_API_HASH no .env "
              "(my.telegram.org → API development tools).")
        sys.exit(1)

    from telethon.sync import TelegramClient

    client = TelegramClient(str(SESSION), int(api_id), api_hash)
    client.start()   # pergunta telefone, código e senha de duas etapas
    session_file = SESSION.with_suffix('.session')
    os.chmod(session_file, 0o600)
    me = client.get_me()
    print(f"✅ Logado como {me.first_name} (@{me.username or 'sem usuário'})")

    lia = os.getenv('LIA_BOT', '@Liaautomacao_bot')
    try:
        bot = client.get_entity(lia)
        print(f"✅ LiA encontrada: @{bot.username}")
    except Exception as e:
        print(f"⚠️ Não achei {lia} ({e}). Abra a conversa com ela no Telegram e confira LIA_BOT no .env.")
    client.disconnect()
    print("Agora rode: sudo systemctl restart shopee-video")


if __name__ == '__main__':
    main()
