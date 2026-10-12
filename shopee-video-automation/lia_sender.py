"""
Envio do vídeo final para a LiA (@Liaautomacao_bot), que posta no Shopee Video.

Bot não conversa com bot no Telegram, então o envio sai pela conta da Juliane (Telethon),
com o login feito uma vez no VPS por `lia_login.py` (arquivo `lia.session`).
"""

import asyncio
import html
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from content_generator import HASHTAGS, fit_caption
from shopee_affiliate import commission_value

logger = logging.getLogger(__name__)

SESSION = Path(__file__).parent / 'lia'          # vira lia.session
WAIT_PUBLICAR = int(os.getenv('LIA_ESPERA_SEGUNDOS', '300'))


class LiaError(Exception):
    pass


@dataclass
class LiaResult:
    published: bool
    summary: str


def _setting(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip().lower()


def enabled() -> bool:
    return (_setting('LIA_ENVIAR', 'agenda') != 'nao' and bool(os.getenv('TELEGRAM_API_ID'))
            and bool(os.getenv('TELEGRAM_API_HASH')) and SESSION.with_suffix('.session').exists())


def links_for_lia(post: Dict) -> List[str]:
    """
    A LiA quer do MENOR para o MAIOR comissionamento e destaca o último: os outros links em ordem
    crescente de comissão e, por último, a loja que a Juliane escolheu divulgar (1º de `products`).
    """
    rest = sorted(zip(post['products'][1:], post['links'][1:]), key=lambda pl: commission_value(pl[0]))
    return [link for _, link in rest] + post['links'][:1]


def caption(post: Dict) -> str:
    tags = ['#postar' if _setting('LIA_MODO', 'postar') == 'postar' else '#rascunho', '#semcapa', '#semmarca']
    nossa = _setting('LIA_LEGENDA', 'nossa') == 'nossa'
    tags.append('#semia' if nossa else '#ia')
    tail = '\n\n' + '\n'.join(links_for_lia(post)) + '\n\n' + ' '.join(tags)
    if not nossa:
        return tail.strip()
    # legenda do Shopee Vídeo: descrição + 3 hashtags em até 150 caracteres (vale também para posts antigos)
    m = post['metadata']
    hashtags = m['hashtags'][:HASHTAGS]
    return f"{fit_caption(m['description'], hashtags)} {' '.join(hashtags)}{tail}"


def _publish_button(message):
    for row in message.buttons or []:
        for button in row:
            if 'publicar' in (button.text or '').lower():
                return button
    return None


async def _send(video_path: str, text: str) -> LiaResult:
    from telethon import TelegramClient

    client = TelegramClient(str(SESSION), int(os.environ['TELEGRAM_API_ID']), os.environ['TELEGRAM_API_HASH'])
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise LiaError("a conta não está logada no VPS (rode lia_login.py)")
        bot = await client.get_entity(os.getenv('LIA_BOT', '@Liaautomacao_bot'))
        sent = await client.send_file(bot, video_path, caption=text, supports_streaming=True)
        logger.info(f"Vídeo enviado à LiA (mensagem {sent.id})")

        last_text = ''
        deadline = time.time() + WAIT_PUBLICAR
        while time.time() < deadline:
            await asyncio.sleep(5)
            replies = [m for m in await client.get_messages(bot, min_id=sent.id, limit=20) if not m.out]
            if replies:
                last_text = replies[0].message or last_text   # a mais recente vem primeiro
            for message in replies:
                button = _publish_button(message)
                if not button:
                    continue
                summary = message.message or ''
                if _setting('LIA_PUBLICAR_AUTO', 'sim') != 'sim':
                    return LiaResult(False, summary)
                await button.click()
                logger.info("Toquei em Publicar na LiA")
                return LiaResult(True, summary)
        detail = f" Última resposta dela: {last_text[:300]}" if last_text else ''
        raise LiaError(f"a LiA não mostrou o botão Publicar em {WAIT_PUBLICAR // 60} min.{detail}")
    finally:
        await client.disconnect()


def send(post: Dict) -> LiaResult:
    """Manda o vídeo final (capa na abertura + logo) com os links; toca em Publicar se configurado."""
    video = post.get('final_video_path') or post['video_path']
    if not Path(video).exists():
        raise LiaError("o vídeo final não está mais no VPS")
    return asyncio.run(_send(video, caption(post)))


def summary_html(result: LiaResult) -> str:
    return html.escape(result.summary[:600]) if result.summary else ''
