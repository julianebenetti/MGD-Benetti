"""
Envio do vídeo final para a LiA (@Liaautomacao_bot), que posta no Shopee Video.

Bot não conversa com bot no Telegram, então o envio sai pela conta da Juliane (Telethon),
com o login feito uma vez no VPS por `lia_login.py` (arquivo `lia.session`).
"""

import asyncio
import html
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from content_generator import HASHTAGS, fit_caption
from shopee_affiliate import commission_value

logger = logging.getLogger(__name__)

SESSION = Path(__file__).parent / 'lia'          # vira lia.session
WAIT_PUBLICAR = int(os.getenv('LIA_ESPERA_SEGUNDOS', '300'))


class LiaError(Exception):
    pass


def _organized_only(text: str) -> bool:
    """A LiA só guardou o vídeo para publicar pelo app ("1 vídeo(s) organizado(s) na Lia. Abra o app…")."""
    low = (text or '').lower()
    return 'organizad' in low and ('abra o app' in low or 'nova postagem' in low)


@dataclass
class LiaResult:
    published: bool
    summary: str
    sent_id: int = 0          # mensagem do vídeo na conversa com a LiA (para acompanhar o resultado)
    organized: bool = False   # ficou no app da LiA esperando ela publicar (não reenviar)


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
    extras = sorted(zip(post['products'][1:], post['links'][1:]), key=lambda pl: commission_value(pl[0]))
    # LIA_MAX_LINKS (padrão 1, só o divulgado): a Shopee pune "produtos adicionais" ao anúncio vinculado; com mais,
    # cada link extra é mais um produto que ela pode julgar "irrelevante"; ficam os de
    # maior comissão
    keep = max(0, int(os.getenv('LIA_MAX_LINKS', '1')) - 1)
    extras = extras[len(extras) - keep:] if keep else []
    return [link for _, link in extras] + post['links'][:1]


def caption(post: Dict) -> str:
    tags = ['#postar' if _setting('LIA_MODO', 'postar') == 'postar' else '#rascunho', '#semcapa', '#semmarca']
    # #ia/#semia na LiA = o VÍDEO foi feito por IA (aviso no vídeo + rótulo de IA na Shopee), não a legenda; a legenda
    # dela segue o /opcoes (Legenda Manual = usa a nossa)
    tags.append('#semia' if _setting('LIA_VIDEO_IA', 'sim') == 'nao' else '#ia')
    nossa = _setting('LIA_LEGENDA', 'nossa') == 'nossa'
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
                if _organized_only(message.message):
                    logger.info("A LiA só organizou o vídeo (publicar pelo app)")
                    return LiaResult(False, message.message or '', sent.id, organized=True)
                button = _publish_button(message)
                if not button:
                    continue
                summary = message.message or ''
                if _setting('LIA_PUBLICAR_AUTO', 'sim') != 'sim':
                    return LiaResult(False, summary, sent.id)
                await button.click()
                logger.info("Toquei em Publicar na LiA")
                return LiaResult(True, summary, sent.id)
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


def _is_success(text: str) -> bool:
    """
    Confirmação da LiA: "Vídeo salvo na Shopee ✅" (ou "publicado"/"postado"). As mensagens de fila também
    têm ✅ e "é publicado" ("Aprovado ✅ … indo pra fila", "Na fila ✅ Vou preparar…"): ficam de fora.
    """
    low = (text or '').lower()
    if 'salvo na shopee' in low:
        return True
    if any(w in low for w in ('fila', 'aprovado', 'vou preparar', 'iniciando')):
        return False
    return 'publicad' in low or 'postad' in low or '✅' in text


def _is_failure(text: str) -> bool:
    low = (text or '').lower()
    return 'não consegui' in low or 'nao consegui' in low or '❌' in text


def _norm(text: str) -> str:
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', (text or '').lower()).split())


def same_product(norm_name: str, product_name: str) -> bool:
    mine = _norm(product_name)
    return bool(norm_name) and (mine.startswith(norm_name[:30]) or norm_name.startswith(mine[:30]))


Message = Tuple[int, str, str]          # (id, texto, data ISO)
Outcome = Tuple[str, str, str]          # ('ok'|'falhou', texto ou motivo, data ISO da mensagem)


def attempts(messages: List[Message]) -> List[Tuple[int, str, Outcome]]:
    """
    Cada tentativa de publicação na conversa (da mais antiga para a mais nova): (id do "Iniciando", nome do
    produto normalizado, resultado). A LiA avisa "Iniciando: <produto>" e depois "Não consegui publicar…
    Motivo: …" ou "Vídeo salvo na Shopee ✅".
    """
    found, current = [], None
    for msg_id, text, when in messages:
        if 'iniciando' in (text or '').lower():
            current = (msg_id, _norm(text.split(':', 1)[-1])[:40])
            continue
        if not current:
            continue
        if _is_failure(text):
            reason = text.split('Motivo:', 1)[-1].strip() if 'Motivo:' in text else text.strip()
            found.append((current[0], current[1], ('falhou', reason[:300], when)))
            current = None
        elif _is_success(text):
            found.append((current[0], current[1], ('ok', text.strip()[:300], when)))
            current = None
    return found


def outcomes(messages: List[Message], posts: List[Dict]) -> Dict[int, Outcome]:
    """{post_id: resultado} da primeira tentativa de cada post depois do envio dele (lia_msg_id)."""
    result: Dict[int, Outcome] = {}
    for start_id, name, outcome in attempts(messages):
        post = next((p for p in posts if p['id'] not in result and start_id > (p.get('lia_msg_id') or 0)
                     and same_product(name, p['product_name'])), None)
        if post:
            result[post['id']] = outcome
    return result


def last_outcome_by_name(messages: List[Message]) -> Dict[str, Outcome]:
    """{produto normalizado: resultado da ÚLTIMA tentativa} (reenviou e deu certo: vale o sucesso)."""
    result: Dict[str, Outcome] = {}
    for _, name, outcome in attempts(messages):
        result[name] = outcome
    return result


def recent_outcomes(limit: int = 1000) -> Dict[str, Outcome]:
    """Último resultado de cada produto nas últimas `limit` mensagens da LiA."""
    return last_outcome_by_name(asyncio.run(_read(0, limit)))


async def _read(min_id: int, limit: int = 300) -> List[Message]:
    from telethon import TelegramClient

    client = TelegramClient(str(SESSION), int(os.environ['TELEGRAM_API_ID']), os.environ['TELEGRAM_API_HASH'])
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise LiaError("a conta não está logada no VPS (rode lia_login.py)")
        bot = await client.get_entity(os.getenv('LIA_BOT', '@Liaautomacao_bot'))
        messages = await client.get_messages(bot, min_id=min_id, limit=limit)
        return [(m.id, m.message or '', m.date.isoformat()) for m in reversed(messages) if not m.out]
    finally:
        await client.disconnect()


def check(posts: List[Dict]) -> Dict[int, Outcome]:
    """Resultado da publicação dos posts que a LiA está publicando (lê a conversa com ela)."""
    if not posts:
        return {}
    return outcomes(asyncio.run(_read(min(p['lia_msg_id'] for p in posts) - 1)), posts)


def summary_html(result: LiaResult) -> str:
    return html.escape(result.summary[:600]) if result.summary else ''
