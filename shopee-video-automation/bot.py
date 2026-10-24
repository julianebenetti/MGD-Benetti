#!/usr/bin/env python3
"""
Robô do Shopee Video (sempre ligado).

📥 Envios → ✅ Editados (aprovação) → ⏰ Agenda → 🚀 Postados
"""

import html
import json
import re
import logging
from datetime import date, timedelta
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

import conversions  # noqa: E402
import ideas  # noqa: E402
import lia_sender  # noqa: E402
import scheduler  # noqa: E402  (lê a configuração da agenda do .env)
from pipeline import Pipeline, PipelineError, VariationMismatch  # noqa: E402
from content_generator import HASHTAGS, fit_caption  # noqa: E402
from sub_id import nome_do_sub_id, novo_sub_id, prefixo  # noqa: E402
from shopee_affiliate import commission_value  # noqa: E402
from shopee_session import CookieError, save_cookies  # noqa: E402
from storage import Storage  # noqa: E402
from telegram_handler import TelegramBot, extract_shopee_links, keyboard  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('bot')

BASE = Path(__file__).parent
ASK_AFTER_SECONDS = 8   # só o tempo de chegarem os outros vídeos de um álbum (o link pode vir em um deles)
BATCH_LINK_TTL = 600
FAILED_RETRY_TTL = 1800
COVER_SECONDS = float(os.getenv('CAPA_SEGUNDOS', '1'))
VIDEO_WORKERS = int(os.getenv('VIDEOS_AO_MESMO_TEMPO', '2'))   # vídeos preparados ao mesmo tempo
DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


def topic(name: str) -> Optional[int]:
    return int(os.getenv(name) or 0) or None


ENVIOS = topic('TELEGRAM_TOPIC_ENVIOS')
EDITADOS = topic('TELEGRAM_TOPIC_EDITADOS')
AGENDA = topic('TELEGRAM_TOPIC_AGENDA')
POSTADOS = topic('TELEGRAM_TOPIC_POSTADOS')
PENDENCIAS = topic('TELEGRAM_TOPIC_PENDENCIAS')
RELATORIO = topic('TELEGRAM_TOPIC_RELATORIO')
IDEIAS = topic('TELEGRAM_TOPIC_IDEIAS')
IDEAS_TIME = os.getenv('IDEIAS_HORA', '07:30')    # lista diária de ideias em 💡 Ideias
LIA_CHECK_SECONDS = 300                                              # lê a conversa com a LiA a cada 5 min
LIA_ALERT_SECONDS = int(float(os.getenv('LIA_ALERTA_HORAS', '2')) * 3600)   # sem confirmação: avisa                          # ideia sugerida não volta antes disso
REPORT_TIME = os.getenv('RELATORIO_HORA', '22:30')   # relatório do dia, depois do último horário da agenda
FAILURES_SHOWN = 7 * 24 * 3600    # falhas sem resposta aparecem nas pendências por até 7 dias
MAX_PENDING_LINES = 40


def fmt_when(iso: str) -> str:
    when = datetime.fromisoformat(iso).astimezone(scheduler.TZ)
    return f"{DIAS[when.weekday()]}, {when:%d/%m} às {when:%H:%M}"


def brl(value: float) -> str:
    return f"R$ {value:.2f}".replace('.', ',')


def price(p: Dict) -> str:
    low, high = float(p.get('priceMin') or p.get('price') or 0), float(p.get('priceMax') or 0)
    return f"{brl(low)} a {brl(high)}" if high > low else brl(low)


def details(p: Dict) -> str:
    """Preço · nota · comissão da loja."""
    return f"{price(p)} · nota {p.get('ratingStar') or '-'} · comissão <b>{brl(commission_value(p))}</b>"


def product_url(p: Dict) -> str:
    return f"https://shopee.com.br/product/{p['shopId']}/{p['itemId']}"


def postados_caption(post: Dict, label: str) -> str:
    """Resumo curto para a foto em Postados (legenda de foto tem limite de 1024 caracteres; sem links)."""
    e = html.escape
    main = post['products'][0] if post['products'] else {}
    return (f"{label} ({fmt_when(scheduler.now().isoformat())})\n\n"
            f"🎬 {e(post['metadata'].get('cover_title', ''))}\n"
            f"🛍️ {e(post['product_name'][:120])}\n"
            f"⭐ {e(main.get('shopName', ''))}" + (f" · comissão {brl(commission_value(main))}" if main else '') + "\n"
            f"🔗 {len(post['links'])} link(s) · 🏷️ {e(post['sub_id'])}")[:1024]


def post_text(post: Dict, hint: bool = False) -> str:
    e = html.escape
    m = post['metadata']
    links = '\n'.join(
        f"{i}. {e(p.get('shopName', ''))}{' ⭐ divulgado' if i == 1 else ''}: {details(p)}\n{e(link)}"
        + (f"\n   🔎 <a href=\"{e(product_url(p))}\">conferir o anúncio</a>" if p.get('shopId') else '')
        for i, (p, link) in enumerate(zip(post['products'], post['links']), 1))
    return (
        f"🎬 <b>Headline:</b> {e(m['cover_title'])}\n\n"
        f"📝 <b>Legenda</b> ({len(m['description']) + 1 + len(' '.join(m['hashtags']))}/150 caracteres):\n"
        f"{e(m['description'])}\n\n"
        f"#️⃣ <b>Hashtags:</b>\n{e(' '.join(m['hashtags']))}\n\n"
        f"🔍 <b>SEO:</b>\n{e(', '.join(m['seo_keywords']))}\n\n"
        + (f"📣 <b>CTA (5 s finais):</b> {e(m['cta'])}\n\n" if m.get('cta') else '') +
        f"🛍️ <b>Produto:</b> {e(post['product_name'])}\n"
        f"🔗 <b>Links</b> (para a LiA vão do menor pro maior comissionamento, o divulgado por último):\n{links}\n"
        f"🏷️ <b>Sub_id:</b> {e(post['sub_id'])}"
        + (f"\n🔎 {e(m['validacao'])}" if m.get('validacao') else '')
        + ("\n\n✍️ <i>Responda esta mensagem: texto curto = nova headline · texto com #hashtags = nova legenda</i>"
           "\n🚫 <i>Link esgotado? Toque no 🚫 com o número dele: troco pela próxima loja.</i>"
           "\n🔁 <i>Achou um link melhor? Responda com o número e o link (ex.: 3 https://…): troco pelo seu.</i>"
           if hint else '')
    )


class Bot:
    def __init__(self):
        self.tg = TelegramBot(os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID'])
        self.db = Storage()
        self.pipeline = Pipeline(BASE / os.getenv('VIDEOS_OUTPUT_DIR', 'processed_videos'))
        self.pipeline.is_sold_out = self.db.is_sold_out
        # vídeos novos numa fila; botões e respostas em outra (não esperam os vídeos); LiA na sua
        self.queues = {'video': queue.Queue(), 'ui': queue.Queue(), 'lia': queue.Queue(), 'report': queue.Queue()}
        self.pending: List[Dict] = []
        self.album_links: Dict[str, Dict] = {}
        self.batch_link: Optional[Dict] = None
        self.lia = lia_sender.enabled()
        self.lia_when = os.getenv('LIA_ENVIAR', 'agenda').strip().lower()
        self.pending_last = ''
        self.lia_checked = 0.0

    def submit(self, job: tuple):
        kind = job[0]
        name = 'video' if kind == 'video' else 'lia' if kind in ('lia', 'lia_check', 'lia_retro') else 'report' if kind in ('report', 'sales', 'ideas') \
            else 'ui'
        self.queues[name].put(job)

    # ---------- Envios ----------

    def on_cookies(self, msg: Dict, text: str):
        """/cookies + arquivo exportado (Cookie-Editor JSON ou cookies.txt), ou colado na mensagem."""
        try:
            if msg.get('document'):
                path = self.tg.download(msg['document']['file_id'], BASE / 'downloads')
                raw = path.read_text(errors='ignore')
                path.unlink(missing_ok=True)
            else:
                raw = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ''
            count, validade = save_cookies(raw)
            reply = f"✅ Login da Shopee salvo ({count} cookies, válido até {validade}). Mensagem apagada por segurança."
        except CookieError as e:
            reply = f"⚠️ {html.escape(str(e))}"
        except Exception as e:
            logger.exception("Falha ao salvar cookies")
            reply = f"⚠️ Não consegui ler os cookies: {html.escape(str(e))}"
        self.tg.delete([msg['message_id']])
        self.tg.send_text(ENVIOS, reply)

    def on_envios(self, msg: Dict):
        try:
            self._on_envios(msg)
        finally:
            self.save_pending()

    def _on_envios(self, msg: Dict):
        command = (msg.get('caption') or msg.get('text') or '').strip()
        if command.lower().startswith('/cookies'):
            self.on_cookies(msg, command)
            return
        file_id = None
        if 'video' in msg:
            file_id = msg['video']['file_id']
        elif msg.get('document', {}).get('mime_type', '').startswith('video/'):
            file_id = msg['document']['file_id']
        text = msg.get('caption') or msg.get('text') or ''
        links = extract_shopee_links(text)

        album = msg.get('media_group_id')
        logger.info(f"Envios: mensagem {msg['message_id']} ({'vídeo' if file_id else 'texto'}"
                    f"{', com link' if links else ', sem link'}"
                    f"{', resposta a ' + str(msg['reply_to_message']['message_id']) if msg.get('reply_to_message') else ''})")
        if file_id:
            if links:
                self.enqueue_video(msg['message_id'], file_id, links[0], text)
                if album:  # álbum: a legenda com o link vem num vídeo só e vale para os outros do álbum
                    self.album_links[album] = {'link': links[0], 'text': text, 'at': time.time()}
                    for p in [p for p in self.pending if p.get('album') == album]:
                        self.pending.remove(p)
                        self.enqueue_video(p['msg_id'], p['file_id'], links[0], f"{p['text']}\n{text}")
            elif album in self.album_links:
                shared = self.album_links[album]
                self.enqueue_video(msg['message_id'], file_id, shared['link'], f"{shared['text']}\n{text}")
            elif self.batch_link and time.time() - self.batch_link['at'] < BATCH_LINK_TTL:
                self.enqueue_video(msg['message_id'], file_id, self.batch_link['link'],
                                   f"{self.batch_link['text']}\n{text}")
            else:
                self.tg.react(msg['message_id'], '👀')   # recebido; o pedido do link vem em seguida
                self.pending.append({'msg_id': msg['message_id'], 'file_id': file_id, 'text': text,
                                     'at': time.time(), 'album': album, 'asked': False})
        elif links:
            replied_id = (msg.get('reply_to_message') or {}).get('message_id')
            waiting = next((p for p in self.pending if p['msg_id'] == replied_id), None)
            retry = None if waiting else self.failed_to_retry(msg, allow_latest=not self.pending)
            if waiting:  # resposta a um vídeo que esperava o link: só ele, com a conferência normal
                self.pending.remove(waiting)
                self.tg.react(msg['message_id'], '👌')
                self.enqueue_video(waiting['msg_id'], waiting['file_id'], links[0], f"{waiting['text']}\n{text}")
            elif retry:
                self.db.remove_failure(retry['msg_id'])
                self.tg.react(msg['message_id'], '👌')
                # link reenviado por você: vale o link, sem a conferência da IA
                self.enqueue_video(retry['msg_id'], retry['file_id'], links[0], f"{retry['text']}\n{text}",
                                   trust_link=True)
            elif self.pending:  # link solto: vale para todos os vídeos que estavam sem link
                for p in self.pending:
                    self.enqueue_video(p['msg_id'], p['file_id'], links[0], f"{p['text']}\n{text}")
                self.pending = []
                self.tg.react(msg['message_id'], '👌')
            else:
                self.batch_link = {'link': links[0], 'text': text, 'at': time.time()}
                self.tg.react(msg['message_id'], '✍')

    def failed_to_retry(self, msg: Dict, allow_latest: bool = True) -> Optional[Dict]:
        """
        Vídeo a refazer quando chega só um link: o vídeo respondido (o Telegram manda o vídeo junto
        com a resposta), a falha cuja mensagem de erro foi respondida, ou (link solto, sem vídeos
        esperando link) a falha mais recente.
        """
        replied = msg.get('reply_to_message') or {}
        video = replied.get('video') or (replied.get('document') if replied.get('document', {})
                                         .get('mime_type', '').startswith('video/') else None)
        if video:
            return {'msg_id': replied['message_id'], 'file_id': video['file_id'],
                    'text': replied.get('caption') or ''}
        failure = self.db.find_failure(replied.get('message_id'), FAILED_RETRY_TTL)
        if failure and not allow_latest and replied.get('message_id') not in (failure['msg_id'], failure['err_msg_id']):
            return None
        return failure

    def enqueue_video(self, msg_id: int, file_id: str, link: str, text: str, trust_link: bool = False):
        self.tg.react(msg_id, '👌')
        self.db.add_video_job(msg_id, file_id, link, text, trust_link)
        self.submit(('video', msg_id, file_id, link, text, trust_link))

    def save_pending(self):
        """Vídeos esperando link ficam gravados: um reinício (ex.: atualização) não os perde."""
        self.db.set_meta('videos_sem_link', json.dumps(self.pending))

    def job_video(self, msg_id: int, file_id: str, link: str, text: str, trust_link: bool = False):
        try:
            self._job_video(msg_id, file_id, link, text, trust_link)
        finally:
            self.db.remove_video_job(msg_id)

    def _job_video(self, msg_id: int, file_id: str, link: str, text: str, trust_link: bool = False):
        try:
            video = self.tg.download(file_id, BASE / 'downloads')
            result = self.pipeline.prepare(str(video), link, text, self.db.headlines_for, trust_link)
        except Exception as e:
            if not isinstance(e, PipelineError):
                logger.exception("Falha ao preparar vídeo")
            reason = str(e) if isinstance(e, PipelineError) else f"Erro inesperado: {e}"
            self.tg.react(msg_id, '🤔')
            markup = keyboard([('✅ Pode seguir', f"vk:{msg_id}")]) if isinstance(e, VariationMismatch) else None
            err_id = self.tg.send_text(ENVIOS, f"⚠️ {html.escape(reason)}", reply_to=msg_id, markup=markup)
            self.db.add_failure(msg_id, err_id, file_id, text, link)
            return
        post_id = self.db.create_post(source_msg_id=msg_id, **result)
        self.db.add_headline(result['product_key'], result['metadata']['cover_title'])
        self.send_to_editados(self.db.get_post(post_id))
        self.tg.react(msg_id, '👍')

    # ---------- Editados ----------

    @staticmethod
    def editados_markup(post: Dict) -> str:
        pid = post['id']
        # ⬜ falta aprovar · ✔️ já aprovado (tocar de novo não faz nada) · 🔒 agendar libera com capa e legenda
        capa = ('✔️ CAPA APROVADA', f"cv:{pid}") if post['cover_approved'] else ('⬜ Aprovar capa', f"cv:{pid}")
        legenda = ('✔️ LEGENDA APROVADA', f"ca:{pid}") if post.get('caption_approved') \
            else ('⬜ Aprovar legenda', f"ca:{pid}")
        ready = post['cover_approved'] and post.get('caption_approved')
        agendar = ('📅 Aprovar e agendar', f"ap:{pid}") if ready else ('🔒 Aprovar e agendar', f"ap:{pid}")
        esgotado = [(f"🚫 {i}", f"eg{i}:{pid}") for i in range(1, len(post['links']) + 1)]
        return keyboard(
            [capa, ('🔄 Outra headline', f"hl:{pid}")],
            [legenda, ('📝 Outra legenda', f"lg:{pid}")],
            esgotado,
            [agendar, ('❌ Descartar', f"dc:{pid}")])

    def send_to_editados(self, post: Dict):
        """Capa, vídeo, textos com botões e, enquanto faltar, o pedido do print das variações."""
        ids = self.tg.send_cover_and_video(EDITADOS, post['cover_path'], post['video_path'])
        ids.append(self.tg.send_text(EDITADOS, post_text(post, hint=True), markup=self.editados_markup(post)))
        if post.get('troca') == 'pendente':
            options = [[(f"{i}. {p.get('shopName', '')[:24]} ({brl(commission_value(p))})", f"tm{i}:{post['id']}")]
                       for i, p in enumerate(post['melhores'], 1)]
            ids.append(self.tg.send_text(EDITADOS, self.switch_question(post), reply_to=ids[-1], markup=keyboard(
                *options, [('Manter o meu', f"mm:{post['id']}")])))
        elif post.get('variacoes', 'pendente') == 'pendente' and not post.get('sticker_path'):
            ids.append(self.tg.send_text(
                EDITADOS, "🖼️ <b>Responda esta mensagem com o print das variações</b> do produto "
                          "(a tela com as miniaturas). Eu recorto e coloco o cartão na capa.",
                reply_to=ids[-1], markup=keyboard([('Sem variações', f"sv:{post['id']}")])))
        self.db.update_post(post['id'], editados_msgs=ids)

    @staticmethod
    def switch_question(post: Dict) -> str:
        e = html.escape
        mine = post['products'][0]
        options = '\n\n'.join(
            f"<b>{i}. {e(p.get('shopName', ''))}</b>\n{details(p)}\n{e(product_url(p))}"
            for i, p in enumerate(post['melhores'], 1))
        return (f"💰 <b>Achei {len(post['melhores'])} loja(s) pagando mais que a do seu link</b>\n\n"
                f"<b>Seu link: {e(mine.get('shopName', ''))}</b>\n{details(mine)}\n\n{options}\n\n"
                "Toque na loja que você quer <b>divulgar</b> (ou Manter o meu). Abra o link dela para tirar "
                "o print das variações, que eu peço em seguida.")

    def job_switch(self, post_id: int, escolha: Optional[int]):
        """Troca o item divulgado pela loja escolhida (posição em `melhores`; None mantém) e reenvia o post."""
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado' or post.get('troca') != 'pendente':
            return
        trocar = escolha is not None and escolha < len(post['melhores'])
        fields = self.pipeline.switch_to(post, escolha) if trocar else {}
        self.tg.delete(post['editados_msgs'])
        self.db.update_post(post_id, troca='trocado' if trocar else 'mantido', **fields)
        if trocar:
            self.db.add_headline(fields['product_key'], post['metadata']['cover_title'])
        self.send_to_editados(self.db.get_post(post_id))

    def job_headline(self, post_id: int, headline: Optional[str]):
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado':
            return
        if headline is None:
            headline = self.pipeline.new_headline(post, self.db.headlines_for(post['product_key']))
        cover = self.pipeline.make_cover(post['video_path'], headline, post.get('sticker_path'))
        metadata = {**post['metadata'], 'cover_title': headline}
        # headline nova = capa nova: precisa aprovar de novo
        self.tg.delete(post['editados_msgs'])
        self.db.update_post(post_id, metadata=metadata, cover_path=cover, cover_approved=0)
        self.db.add_headline(post['product_key'], headline)
        self.send_to_editados(self.db.get_post(post_id))

    def job_caption(self, post_id: int, text: Optional[str]):
        """Outra legenda da IA (None) ou a sua (com #hashtags, já aprovada); atualiza a mensagem dos textos."""
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado':
            return
        m = post['metadata']
        if text is None:
            avoid = m.get('legendas_usadas', []) + [m['description']]
            new = self.pipeline.new_caption(post, avoid)
            approved = 0
        else:
            hashtags = re.findall(r'#\w+', text)[:HASHTAGS] or m['hashtags']
            new = {'description': fit_caption(re.sub(r'#\w+', '', text), hashtags), 'hashtags': hashtags}
            approved = 1
        new['description'] = fit_caption(new['description'], new['hashtags'])
        metadata = {**m, **new, 'legendas_usadas': m.get('legendas_usadas', []) + [m['description']]}
        self.db.update_post(post_id, metadata=metadata, caption_approved=approved)
        post = self.db.get_post(post_id)
        if len(post['editados_msgs']) > 2:
            self.tg.edit_text(post['editados_msgs'][2], post_text(post, hint=True), markup=self.editados_markup(post))

    def job_replace_link(self, post_id: int, index: int, url: str, reply_to: int):
        """Troca o link `index` pelo produto do link que você mandou (com o seu link de afiliado e o mesmo sub_id)."""
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado':
            return
        index = min(index, len(post['products']))   # número além da lista: entra no fim
        shopee = self.pipeline.shopee
        found = shopee.find_candidates(url)
        if not found:
            self.tg.react(reply_to, '🤔')
            self.tg.send_text(EDITADOS, "⚠️ Não encontrei o produto desse link. Mande o link do anúncio (produto).",
                              reply_to=reply_to)
            return
        new = found[0]
        new['commissionValue'] = commission_value(new)
        new['escolhido'] = True   # você escolheu: a validação antes de agendar só avisa, não tira
        products, links = list(post['products']), list(post['links'])
        same_shop = [i + 1 for i, p in enumerate(products) if str(p['shopId']) == str(new['shopId']) and i != index]
        link = shopee.affiliate_link(new, post['sub_id'])
        if index < len(products):
            products[index], links[index] = new, link
        else:
            products.append(new)
            links.append(link)
        fields = {'products': products, 'links': links}
        if index == 0:
            fields.update(product_key=f"{new['shopId']}:{new['itemId']}", product_name=new['productName'])
        self.db.update_post(post_id, **fields)
        post = self.db.get_post(post_id)
        if len(post['editados_msgs']) > 2:
            self.tg.edit_text(post['editados_msgs'][2], post_text(post, hint=True), markup=self.editados_markup(post))
        note = f"🔁 Link {index + 1} trocado por <b>{html.escape(new.get('shopName', ''))}</b>: {details(new)}"
        if same_shop:
            note += f"\n⚠️ Essa loja já está no link {', '.join(map(str, same_shop))}."
        self.tg.react(reply_to, '👍')
        self.tg.send_text(EDITADOS, note, reply_to=reply_to)

    def job_sold_out(self, post_id: int, index: int):
        """Link esgotado: anota (não volta por 7 dias), tira e repõe com a próxima loja conferida."""
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado' or index >= len(post['products']):
            return
        self.db.mark_sold_out(f"{post['products'][index]['shopId']}:{post['products'][index]['itemId']}")
        fields = self.pipeline.replace_sold_out(post, index, self.db.is_sold_out)
        extra = fields.pop('reposto')
        self.db.update_post(post_id, **fields)
        post = self.db.get_post(post_id)
        if len(post['editados_msgs']) > 2:
            self.tg.edit_text(post['editados_msgs'][2], post_text(post, hint=True), markup=self.editados_markup(post))
        note = (f"🚫 Link {index + 1} tirado (esgotado)"
                + (f" e trocado por <b>{html.escape(extra.get('shopName', ''))}</b>." if extra
                   else ". Não havia outra loja conferida para repor."))
        if index == 0:
            note += f"\n⭐ Agora a divulgada é <b>{html.escape(post['products'][0].get('shopName', ''))}</b>."
        self.tg.send_text(EDITADOS, note, reply_to=post['editados_msgs'][2] if len(post['editados_msgs']) > 2 else None)

    def validate_before_agenda(self, post: Dict) -> Optional[Dict]:
        """
        Validação rigorosa (6 quadros, mesmo modelo) antes de agendar. Tira lojas extras que não são o produto
        do vídeo (e repõe com reservas validadas). Se o produto divulgado não bater, devolve None: o post volta
        para Editados com o motivo e o botão "Agendar mesmo assim".
        """
        e = html.escape
        v = self.pipeline.validate(post)
        result, reason = v['main']
        confirmed = (post['metadata'].get('principal_confirmado') or post['products'][0].get('escolhido')
                     or post['metadata'].get('validacao_forcada'))   # "Agendar mesmo assim" vale só para o divulgado
        if result in ('nao', 'incerto') and not confirmed:
            self.db.update_post(post['id'], status='editado')
            post = self.db.get_post(post['id'])
            self.refresh_buttons(post)
            self.tg.send_text(
                EDITADOS, f"🔎 <b>Validação: o produto divulgado não bate com o vídeo</b>\n"
                          f"{e(post['product_name'][:80])}\n{'Diferente' if result == 'nao' else 'Não deu para confirmar'}: "
                          f"{e(reason)}\n\nPara não arriscar \"produto irrelevante\", não agendei. Troque o link 1 "
                          "(responda os textos com <code>1 https://…</code>) ou, se tiver certeza, toque abaixo.",
                reply_to=post['editados_msgs'][2] if len(post['editados_msgs']) > 2 else None,
                markup=keyboard([('📅 Agendar mesmo assim', f"af:{post['id']}")]))
            return None
        lines = [f"🔎 <b>Validação antes da Agenda:</b> {len(v['products'])} link(s) idênticos ao vídeo"]
        if result != 'sim':
            lines.append(f"• Divulgado: {e(reason)} (confirmado por você)" if confirmed
                         else f"• Divulgado em outra variação do mesmo anúncio: {e(reason)}")
        lines += [f"• ❌ Tirei {e(shop)}: {e(why)}" for shop, _, why in v['removed']]
        lines += [f"• ➕ Pus {e(shop)} no lugar (validado)" for shop in v['added']]
        lines += [f"• ⚠️ {e(shop)} (escolhido por você) pode não ser idêntico: {e(why)}" for shop, _, why in v['warnings']]
        metadata = {**post['metadata'], 'validacao': f"{len(v['products'])} link(s) validados (mesmo modelo do vídeo)"}
        self.db.update_post(post['id'], products=v['products'], links=v['links'], metadata=metadata)
        return {'note': '\n'.join(lines)}

    def job_approve(self, post_id: int):
        """Valida os produtos, junta a capa na abertura do vídeo, reserva o horário e move para a Agenda."""
        post = self.db.get_post(post_id)
        checked = self.validate_before_agenda(post)
        if checked is None:
            return
        note = checked['note']
        post = self.db.get_post(post_id)
        final = str(Path(post['video_path']).with_name(f"final_{post_id}.mp4"))
        if not self.pipeline.video.prepend_cover(post['cover_path'], post['video_path'], final, COVER_SECONDS):
            self.db.update_post(post_id, status='editado')
            self.refresh_buttons(self.db.get_post(post_id))
            self.tg.send_text(EDITADOS, "⚠️ Não consegui juntar a capa ao vídeo. Tente aprovar de novo.",
                              reply_to=post['editados_msgs'][-1] if post['editados_msgs'] else None)
            return
        slot = self.next_slot(post)
        self.tg.delete(post['editados_msgs'])
        self.db.update_post(post_id, status='agendado', scheduled_at=slot.isoformat(),
                            editados_msgs=[], final_video_path=final)
        self.resubid(self.db.get_post(post_id), force=True)   # sub_id definitivo, com a data da publicação
        post = self.db.get_post(post_id)
        ids = self.tg.send_cover_and_video(AGENDA, post['cover_path'], final)
        ids.append(self.tg.send_text(
            AGENDA, f"⏰ <b>{fmt_when(post['scheduled_at'])}</b>\n\n{post_text(post)}",
            markup=self.agenda_markup(post_id)))
        if note:
            ids.append(self.tg.send_text(AGENDA, note, reply_to=ids[-1]))
        self.db.update_post(post_id, agenda_msgs=ids)
        if self.lia and self.lia_when == 'aprovar':
            self.send_to_lia(self.db.get_post(post_id))

    def next_slot(self, post: Dict) -> datetime:
        """Próximo horário livre da agenda para o post (os já postados contam no limite do dia)."""
        since = (scheduler.now() - timedelta(days=2)).isoformat()
        posted = [p for p in self.db.with_status('postado') if p['posted_at'] and p['posted_at'] >= since]
        last = max((p['posted_at'] for p in posted), default=None)
        others = [p for p in self.db.scheduled() if p['id'] != post['id']]
        return scheduler.next_slot(post['product_key'], others, posted=posted,
                                   last_posted=datetime.fromisoformat(last) if last else None)

    def reschedule(self, post: Dict, reason: str):
        """
        A LiA não conseguiu publicar: o post ganha o próximo horário livre da agenda (mesmas regras) e, nessa
        hora, vai de novo para a LiA, até ser publicado. Avisa na Agenda com o motivo e o novo horário.
        """
        slot = self.next_slot(post)
        tries = post['metadata'].get('lia_tentativas', 0) + 1
        self.db.update_post(post['id'], status='agendado', scheduled_at=slot.isoformat(), posted_at=None,
                            posted_via=None, metadata={**post['metadata'], 'lia_tentou': True,
                                                       'lia_tentativas': tries, 'lia_alertado': False})
        self.resubid(self.db.get_post(post['id']))   # a data da publicação mudou: sub_id e links acompanham
        post = self.db.get_post(post['id'])
        text = f"⏰ <b>{fmt_when(post['scheduled_at'])}</b>\n\n{post_text(post)}"
        msgs = post['agenda_msgs']
        if len(msgs) > 2 and self.tg.edit_text(msgs[2], text, markup=self.agenda_markup(post['id'])):
            ids = list(msgs)
        else:   # as mensagens da Agenda já tinham sido apagadas (ex.: tinha ido para Postados)
            video = post.get('final_video_path') or post['video_path']
            ids = self.tg.send_cover_and_video(AGENDA, post['cover_path'], video) if Path(video).exists() else []
            ids.append(self.tg.send_text(AGENDA, text, markup=self.agenda_markup(post['id'])))
        ids.append(self.tg.send_text(
            AGENDA, f"❌ <b>A LiA não conseguiu publicar</b> {html.escape(post['product_name'][:60])} "
                    f"(tentativa {tries})\nMotivo: {html.escape(reason)}\n\n🔁 <b>Reagendado para "
                    f"{fmt_when(post['scheduled_at'])}</b>: nessa hora mando de novo. Deixe o tablet/celular "
                    "ligado e conectado.", reply_to=ids[-1] if ids else None, markup=self.agenda_markup(post['id'])))
        self.db.update_post(post['id'], agenda_msgs=ids)

    def resubid(self, post: Dict, force: bool = False) -> bool:
        """
        Refaz o sub_id com a data agendada (SV-<data>-<produto>) e os links com ele. Vídeo e horário não
        mudam. Se a Shopee falhar, mantém o sub_id e os links que já estavam.
        """
        when = datetime.fromisoformat(post['scheduled_at']).astimezone(scheduler.TZ).date()
        name = post['metadata'].get('short_name') or nome_do_sub_id(post['sub_id'])
        if not force and post['sub_id'].startswith(prefixo(when)):
            return False   # já está com a data certa
        sub_id = novo_sub_id(name, when)
        try:
            links = [self.pipeline.shopee.affiliate_link(p, sub_id) for p in post['products']]
        except Exception as e:
            logger.warning(f"Não consegui refazer os links do post {post['id']} com o sub_id {sub_id}: {e}")
            return False
        self.db.update_post(post['id'], sub_id=sub_id, links=links)
        logger.info(f"Post {post['id']}: sub_id {post['sub_id']} -> {sub_id}")
        return True

    def job_resubid_agenda(self):
        """Posts que já estavam na Agenda: sub_id novo com a data agendada e a mensagem atualizada."""
        changed = 0
        for post in self.db.with_status('agendado', 'avisado'):
            if not post['scheduled_at'] or not self.resubid(post):
                continue
            changed += 1
            post = self.db.get_post(post['id'])
            if len(post['agenda_msgs']) > 2:
                self.tg.edit_text(post['agenda_msgs'][2], f"⏰ <b>{fmt_when(post['scheduled_at'])}</b>\n\n{post_text(post)}",
                                  markup=self.agenda_markup(post['id']))
        if changed:
            self.tg.send_text(AGENDA, f"🏷️ Sub_id atualizado em {changed} post(s) da Agenda: agora é "
                                      "SV-&lt;data da publicação&gt;-&lt;produto&gt;. Vídeos e horários não mudaram.")

    # ---------- Agenda / LiA ----------

    def agenda_markup(self, post_id: int) -> str:
        row = [('✅ Postei', f"ok:{post_id}")]
        if self.lia:
            row.append(('📤 Enviar à LiA', f"la:{post_id}"))
        return keyboard(row, [('❌ Descartar', f"dc:{post_id}")])

    def send_to_lia(self, post: Dict):
        self.db.update_post(post['id'], status='enviando')
        self.submit(('lia', post['id']))

    def job_lia(self, post_id: int):
        """Manda o vídeo final para a LiA e toca em Publicar; deu certo → Postados."""
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'enviando':
            return
        reply_to = post['agenda_msgs'][-1] if post['agenda_msgs'] else None
        try:
            result = lia_sender.send(post)
        except Exception as e:
            if not isinstance(e, lia_sender.LiaError):
                logger.exception("Falha ao enviar à LiA")
            self.reschedule(post, f"não consegui passar o vídeo para a LiA ({e})")
            return
        if result.published:   # a publicação acontece depois, no aparelho: confirmo lendo a LiA
            self.db.update_post(post_id, status='na_lia', lia_msg_id=result.sent_id, lia_sent_at=time.time())
            msg_id = self.tg.send_text(AGENDA, f"🤖 <b>{html.escape(post['product_name'][:60])}</b> está com a LiA, "
                                               "publicando. Te aviso se der problema.", reply_to=reply_to)
            self.db.update_post(post_id, agenda_msgs=post['agenda_msgs'] + [msg_id])
            return
        self.db.update_post(post_id, status='avisado')
        msg_id = self.tg.send_text(
            AGENDA, f"📤 Enviado à LiA: falta tocar <b>Publicar</b> na conversa com ela. Depois toque ✅ Postei."
                    f"\n\n{lia_sender.summary_html(result)}", reply_to=reply_to, markup=self.agenda_markup(post_id))
        self.db.update_post(post_id, agenda_msgs=post['agenda_msgs'] + [msg_id])

    def job_lia_check(self):
        """Confere na conversa com a LiA se os vídeos foram publicados ou se ela não conseguiu."""
        waiting = [p for p in self.db.with_status('na_lia') if p.get('lia_msg_id')]
        if not waiting:
            return
        try:
            results = lia_sender.check(waiting)
        except Exception as e:
            logger.warning(f"Não consegui ler a conversa com a LiA: {e}")
            return
        for post in waiting:
            outcome = results.get(post['id'])
            reply_to = post['agenda_msgs'][-1] if post['agenda_msgs'] else None
            if outcome and outcome[0] == 'ok':
                self.move_to_postados(post, "🤖 Publicado pela LiA", via='lia', when=outcome[2])
            elif outcome:
                self.reschedule(post, outcome[1])
            elif time.time() - (post.get('lia_sent_at') or time.time()) > LIA_ALERT_SECONDS \
                    and not post['metadata'].get('lia_alertado'):
                self.db.update_post(post['id'], metadata={**post['metadata'], 'lia_alertado': True})
                msg_id = self.tg.send_text(
                    AGENDA, f"⏳ A LiA ainda não confirmou a publicação de "
                            f"<b>{html.escape(post['product_name'][:60])}</b> (faz mais de "
                            f"{LIA_ALERT_SECONDS // 3600} h). O tablet/celular está ligado? Se já postou, toque ✅ Postei.",
                    reply_to=reply_to, markup=self.agenda_markup(post['id']))
                self.db.update_post(post['id'], agenda_msgs=post['agenda_msgs'] + [msg_id])

    def job_lia_retro(self, thread: Optional[int] = None):
        """
        Confere a conversa toda com a LiA e acerta cada vídeo pelo resultado da ÚLTIMA tentativa:
        - deu certo (reenviado depois de uma falha, inclusive): fica em Postados com a data/hora real da
          mensagem "Vídeo salvo na Shopee";
        - falhou e não houve tentativa depois: ganha um novo horário na Agenda (reagendado) e é reenviado nele.
        """
        try:
            results = lia_sender.recent_outcomes()
        except Exception as e:
            logger.warning(f"Não consegui ler a conversa com a LiA: {e}")
            if thread:
                self.tg.send_text(thread, f"⚠️ Não consegui ler a conversa com a LiA: {html.escape(str(e)[:200])}")
            return
        fixed, back = [], []
        # posts 'na_lia' (reenviados, esperando a LiA) ficam com a checagem de 5 min, que só olha as respostas
        # depois do envio: aqui uma falha antiga do mesmo produto os reagendaria por engano
        for post in self.db.with_status('postado', 'avisado'):
            sent_to_lia = post.get('lia_msg_id') or post['metadata'].get('lia_tentou') or post.get('posted_via') == 'lia'
            if not sent_to_lia:
                continue
            outcome = next((v for k, v in results.items() if lia_sender.same_product(k, post['product_name'])), None)
            if not outcome:
                continue
            status, text, when = outcome
            real = datetime.fromisoformat(when).astimezone(scheduler.TZ)
            if status == 'ok' and post['status'] == 'postado':
                if post['posted_at'] != real.isoformat(timespec='seconds'):
                    self.db.update_post(post['id'], posted_at=real.isoformat(timespec='seconds'), posted_via='lia')
                    fixed.append(f"{post['product_name'][:45]} → {real:%d/%m %H:%M}")
            elif status == 'ok':
                self.move_to_postados(post, "🤖 Publicado pela LiA", via='lia', when=when)
                fixed.append(f"{post['product_name'][:45]} → {real:%d/%m %H:%M}")
            elif post['status'] == 'postado':
                self.reschedule(post, text)
                back.append(post['product_name'][:50])
        parts = []
        if fixed:
            parts.append(f"✅ {len(fixed)} vídeo(s) publicados pela LiA, com a data/hora real da postagem:\n"
                         + '\n'.join(f"• {html.escape(f)}" for f in fixed))
        if back:
            parts.append(f"❌ {len(back)} vídeo(s) não foram publicados e foram reagendados na ⏰ Agenda:\n"
                         + '\n'.join(f"• {html.escape(n)}" for n in back))
        if parts or thread:
            self.tg.send_text(thread or AGENDA, "🔎 <b>Conferi a conversa com a LiA</b>\n\n"
                              + ('\n\n'.join(parts) if parts else "Tudo certo: nenhum vídeo ficou sem publicar."))

    def move_to_postados(self, post: Dict, label: str = "✅ Postado", via: str = 'manual',
                         when: Optional[str] = None):
        """`when`: horário real da publicação (ex.: a mensagem "Vídeo salvo na Shopee" da LiA); sem ele, agora."""
        posted_at = (datetime.fromisoformat(when).astimezone(scheduler.TZ) if when else scheduler.now())
        self.tg.delete(post['agenda_msgs'])
        self.db.update_post(post['id'], status='postado', agenda_msgs=[],
                            posted_at=posted_at.isoformat(timespec='seconds'), posted_via=via)
        self.tg.send_photo(POSTADOS, post['cover_path'], postados_caption(post, label))

    def job_variations(self, post_id: int, file_id: str, reply_to: int):
        """Print das variações → cartão → capa refeita (precisa aprovar de novo)."""
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado':
            return
        folder = Path(post['video_path']).parent / f"variacoes_post_{post_id}"
        image = self.tg.download(file_id, folder)
        card = self.pipeline.variations_card_from_print(str(image), folder)
        if not card:
            self.tg.react(reply_to, '🤔')
            self.tg.send_text(EDITADOS, "⚠️ Não encontrei as miniaturas das variações nesse print. "
                                        "Mande um print em que elas apareçam (ou toque em Sem variações).",
                              reply_to=reply_to)
            return
        cover = self.pipeline.make_cover(post['video_path'], post['metadata']['cover_title'], card)
        self.tg.delete(post['editados_msgs'] + [reply_to])
        self.db.update_post(post_id, sticker_path=card, cover_path=cover, cover_approved=0, variacoes='ok')
        self.send_to_editados(self.db.get_post(post_id))

    def on_editados_reply(self, msg: Dict):
        post = self.db.post_by_editados_msg(msg['reply_to_message']['message_id'])
        if not post:
            return
        image_id = None
        if msg.get('photo'):
            image_id = msg['photo'][-1]['file_id']  # maior resolução
        elif msg.get('document', {}).get('mime_type', '').startswith('image/'):
            image_id = msg['document']['file_id']
        text = (msg.get('text') or '').strip()
        if image_id and post.get('troca') == 'pendente':
            self.tg.send_text(EDITADOS, "Antes do print, escolha a loja que vai divulgar "
                                        "(botões da mensagem 💰).", reply_to=msg['message_id'])
        elif image_id:
            self.tg.react(msg['message_id'], '👌')
            self.submit(('variations', post['id'], image_id, msg['message_id']))
        elif text and re.match(r'^\s*\d\s+\S', text) and extract_shopee_links(text):  # "3 <link>": troca o link 3
            self.tg.react(msg['message_id'], '👌')
            self.submit(('replace_link', post['id'], int(text.strip()[0]) - 1, extract_shopee_links(text)[0],
                         msg['message_id']))
        elif text and extract_shopee_links(text):
            self.tg.send_text(EDITADOS, "Para trocar um link, mande o <b>número</b> dele e o link novo, "
                                        "ex.: <code>3 https://s.shopee.com.br/…</code>", reply_to=msg['message_id'])
        elif text and '#' in text:  # com hashtags: é uma legenda sua
            self.tg.react(msg['message_id'], '✍')
            self.submit(('caption', post['id'], text))
        elif text:
            self.tg.react(msg['message_id'], '✍')
            self.submit(('headline', post['id'], text[:60]))

    # ---------- Botões ----------

    def on_variation_ok(self, cb: Dict, msg_id: int):
        """✅ Pode seguir: outra variação confirmada por você, refaz com o mesmo link sem conferir."""
        failure = self.db.find_failure(msg_id, 0)
        if not failure or failure['msg_id'] != msg_id or not failure.get('link'):
            self.tg.answer_callback(cb['id'], 'Já resolvido')
            return
        self.db.remove_failure(msg_id)
        self.tg.edit_markup(failure['err_msg_id'], keyboard())
        self.tg.answer_callback(cb['id'], 'Ok, seguindo com este link')
        self.enqueue_video(msg_id, failure['file_id'], failure['link'], failure['text'], trust_link=True)

    def refresh_buttons(self, post: Dict):
        """Põe os botões atuais na mensagem dos textos (posts enviados antes de uma atualização)."""
        if len(post['editados_msgs']) > 2:
            self.tg.edit_markup(post['editados_msgs'][2], self.editados_markup(post))

    def on_callback(self, cb: Dict):
        action, _, raw_id = cb.get('data', '').partition(':')
        logger.info(f"Botão {cb.get('data', '')}")
        if action == 'vk' and raw_id.isdigit():
            self.on_variation_ok(cb, int(raw_id))
            return
        post = self.db.get_post(int(raw_id)) if raw_id.isdigit() else None
        if not post:
            self.tg.answer_callback(cb['id'], 'Post não encontrado')
            return

        if action == 'sv' and post['status'] == 'editado':
            pedido = post['editados_msgs'][3:]
            self.tg.delete(pedido)
            self.db.update_post(post['id'], variacoes='sem', editados_msgs=post['editados_msgs'][:3])
            self.tg.answer_callback(cb['id'], 'Ok, capa sem cartão de variações')

        elif (action == 'mm' or action[:2] == 'tm' and action[2:].isdigit()) and post['status'] == 'editado' \
                and post.get('troca') == 'pendente':
            escolha = int(action[2:]) - 1 if action != 'mm' else None
            self.tg.answer_callback(cb['id'], 'Trocando a loja divulgada…' if escolha is not None
                                    else 'Ok, mantendo o seu link')
            self.submit(('switch', post['id'], escolha))

        elif action in ('cv', 'ap') and post['status'] == 'editado' and post.get('troca') == 'pendente':
            self.tg.answer_callback(cb['id'], 'Antes, escolha a loja que vai divulgar')

        elif action == 'cv' and post['status'] == 'editado' and post.get('variacoes') == 'pendente' \
                and not post.get('sticker_path'):
            self.tg.answer_callback(cb['id'], 'Antes, mande o print das variações (ou toque em Sem variações)')

        elif action == 'cv' and post['status'] == 'editado':
            if post['cover_approved']:
                self.refresh_buttons(post)
                self.tg.answer_callback(cb['id'], 'Capa já aprovada')
                return
            self.db.update_post(post['id'], cover_approved=1)
            self.tg.edit_markup(post['editados_msgs'][2], self.editados_markup(self.db.get_post(post['id'])))
            self.tg.answer_callback(cb['id'], 'Capa aprovada')

        elif action == 'ap' and post['status'] == 'editado' and not post['cover_approved']:
            self.refresh_buttons(post)
            self.tg.answer_callback(cb['id'], 'Aprove a capa primeiro (⬜ Aprovar capa)')

        elif action == 'ap' and post['status'] == 'editado' and not post.get('caption_approved'):
            self.refresh_buttons(post)  # mensagens antigas não tinham o botão da legenda
            self.tg.answer_callback(cb['id'], 'Aprove a legenda primeiro (⬜ Aprovar legenda, logo acima)')

        elif action == 'ca' and post['status'] == 'editado':
            if post.get('caption_approved'):
                self.tg.answer_callback(cb['id'], 'Legenda já aprovada')
                return
            self.db.update_post(post['id'], caption_approved=1)
            self.tg.edit_markup(post['editados_msgs'][2], self.editados_markup(self.db.get_post(post['id'])))
            self.tg.answer_callback(cb['id'], 'Legenda aprovada')

        elif action == 'lg' and post['status'] == 'editado':
            self.tg.answer_callback(cb['id'], 'Gerando outra legenda…')
            self.submit(('caption', post['id'], None))

        elif action == 'ap' and post['status'] == 'editado':
            self.db.update_post(post['id'], status='agendando')
            self.tg.edit_markup(post['editados_msgs'][2], keyboard([('⏳ Agendando…', f"ag:{post['id']}")]))
            self.tg.answer_callback(cb['id'], 'Validando os produtos e agendando… (até 1 minuto)')
            self.submit(('approve', post['id']))

        elif action[:2] == 'eg' and action[2:].isdigit() and post['status'] == 'editado':
            index = int(action[2:]) - 1
            if index >= len(post['links']):
                self.tg.answer_callback(cb['id'], 'Esse link já foi trocado')
                return
            self.tg.answer_callback(cb['id'], f"Trocando o link {index + 1} (esgotado)…")
            self.submit(('soldout', post['id'], index))

        elif action == 'af' and post['status'] == 'editado':
            self.db.update_post(post['id'], status='agendando',
                                metadata={**post['metadata'], 'validacao_forcada': True})
            self.tg.answer_callback(cb['id'], 'Ok, agendando mesmo assim…')
            self.submit(('approve', post['id']))

        elif action == 'ag':
            self.tg.answer_callback(cb['id'], 'Já estou agendando, aguarde uns segundos')

        elif action == 'hl' and post['status'] == 'editado':
            self.tg.answer_callback(cb['id'], 'Gerando outra headline…')
            self.submit(('headline', post['id'], None))

        elif action == 'dc' and post['status'] in ('editado', 'agendado', 'avisado', 'na_lia'):
            self.tg.delete(post['editados_msgs'] + post['agenda_msgs'])
            self.db.update_post(post['id'], status='descartado',
                                discarded_at=scheduler.now().isoformat(timespec='seconds'))
            self.tg.answer_callback(cb['id'], 'Descartado')

        elif action == 'ok' and post['status'] in ('agendado', 'avisado', 'na_lia'):
            self.move_to_postados(post)
            self.tg.answer_callback(cb['id'], 'Movido para Postados')

        elif action == 'la' and post['status'] in ('agendado', 'avisado', 'na_lia') and self.lia:
            self.send_to_lia(post)
            self.tg.answer_callback(cb['id'], 'Enviando à LiA…')

        else:
            self.tg.answer_callback(cb['id'], 'Já resolvido')

    # ---------- Relógio ----------

    def tick(self):
        for album in [a for a, v in self.album_links.items() if time.time() - v['at'] > BATCH_LINK_TTL]:
            del self.album_links[album]
        for p in self.pending:  # cada vídeo sem link é perguntado sozinho; os outros seguem
            if not p['asked'] and time.time() - p['at'] > ASK_AFTER_SECONDS:
                p['asked'] = True
                self.save_pending()
                self.tg.send_text(ENVIOS, "🔗 Falta o link deste vídeo: <b>responda este vídeo</b> com o link do "
                                          "produto.", reply_to=p['msg_id'])

        current = scheduler.now()
        for post in self.db.scheduled():
            if post['status'] == 'agendado' and datetime.fromisoformat(post['scheduled_at']) <= current:
                if self.lia and self.lia_when == 'agenda':
                    self.send_to_lia(post)
                    continue
                reply_to = post['agenda_msgs'][-1] if post['agenda_msgs'] else None
                msg_id = self.tg.send_text(AGENDA, f"⏰ <b>Hora de postar!</b> {html.escape(post['product_name'])}",
                                           reply_to=reply_to)
                self.db.update_post(post['id'], status='avisado', agenda_msgs=post['agenda_msgs'] + [msg_id])

    # ---------- Pendências ----------

    def pending_items(self) -> List[tuple]:
        """(quando, tópico, o que fazer, nome, mensagem) de tudo que espera uma ação sua."""
        items = []
        for p in self.pending:
            items.append((p['at'], ENVIOS, '🔗 Mandar o link', 'vídeo sem link', p['msg_id']))
        for f in self.db.recent_failures(FAILURES_SHOWN):
            what = '✅ Confirmar variação ou mandar outro link' if f.get('link') else '⚠️ Responder com o link certo'
            items.append((f['at'], ENVIOS, what, 'vídeo que não passou', f['err_msg_id'] or f['msg_id']))
        for post in self.db.with_status('editado'):
            msgs = post['editados_msgs']
            if len(msgs) < 3:
                continue
            if post.get('troca') == 'pendente':
                what, target = '💰 Escolher a loja divulgada', msgs[3] if len(msgs) > 3 else msgs[2]
            elif post.get('variacoes') == 'pendente' and not post.get('sticker_path'):
                what, target = '🖼️ Mandar o print das variações', msgs[3] if len(msgs) > 3 else msgs[2]
            elif not post['cover_approved']:
                what, target = '✅ Aprovar a capa', msgs[2]
            elif not post.get('caption_approved'):
                what, target = '✍️ Aprovar a legenda', msgs[2]
            else:
                what, target = '✅ Aprovar e agendar', msgs[2]
            items.append((datetime.fromisoformat(post['created_at']).timestamp(), EDITADOS, what,
                          post['product_name'], target))
        for post in self.db.with_status('avisado'):
            if post['agenda_msgs']:
                items.append((datetime.fromisoformat(post['scheduled_at']).timestamp(), AGENDA,
                              '🚀 Postar (ou reenviar à LiA) e tocar ✅ Postei', post['product_name'],
                              post['agenda_msgs'][-1]))
        return sorted(items)

    def pending_text(self) -> str:
        items = self.pending_items()
        if not items:
            return "📌 <b>Pendências</b>\n\n✅ Nada esperando por você."
        names = {ENVIOS: '📥 Envios', EDITADOS: '✅ Editados', AGENDA: '⏰ Agenda'}
        lines = [f"📌 <b>Pendências ({len(items)})</b> · toque no item para ir até a mensagem"]
        for thread in (ENVIOS, EDITADOS, AGENDA):
            group = [i for i in items if i[1] == thread]
            if not group:
                continue
            lines.append(f"\n<b>{names[thread]}</b>")
            for when, _, what, name, msg_id in group[:MAX_PENDING_LINES]:
                since = datetime.fromtimestamp(when, scheduler.TZ).strftime('%d/%m %H:%M')
                link = self.tg.message_link(thread, msg_id)
                lines.append(f"• {what}: <a href=\"{link}\">{html.escape(name[:45])}</a> · desde {since}")
            if len(group) > MAX_PENDING_LINES:
                lines.append(f"… e mais {len(group) - MAX_PENDING_LINES}")
        return '\n'.join(lines)[:4000]

    def refresh_pending(self):
        """Mantém uma mensagem fixada em 📌 Pendências com tudo que espera ação (só edita se mudou)."""
        if not PENDENCIAS:
            return
        text = self.pending_text()
        if text == self.pending_last:
            return
        msg_id = int(self.db.get_meta('pendencias_msg', '0'))
        if not msg_id or not self.tg.edit_text(msg_id, text):
            msg_id = self.tg.send_text(PENDENCIAS, text)
            self.db.set_meta('pendencias_msg', str(msg_id))
            self.tg.pin(msg_id)
        self.pending_last = text

    # ---------- Relatório ----------

    @staticmethod
    def _day(iso: Optional[str]) -> Optional[date]:
        return datetime.fromisoformat(iso).astimezone(scheduler.TZ).date() if iso else None

    def report_text(self, day: date) -> str:
        e = html.escape
        posted = [p for p in self.db.with_status('postado') if self._day(p['posted_at'] or p['scheduled_at']) == day]
        posted.sort(key=lambda p: p['posted_at'] or p['scheduled_at'] or '')
        discarded = [p for p in self.db.with_status('descartado') if self._day(p['discarded_at']) == day]
        by_lia = sum(1 for p in posted if p['posted_via'] == 'lia')
        meta = scheduler.POSTS_PER_DAY
        lines = [f"📊 <b>Relatório de {DIAS[day.weekday()]}, {day:%d/%m}</b>", "",
                 f"🚀 Postados: <b>{len(posted)}</b> de {meta} (meta do dia)"]
        if posted:
            lines.append(f"     🤖 pela LiA: {by_lia} · ✋ manual: {len(posted) - by_lia}")
        lines.append(f"❌ Descartados: {len(discarded)}")
        if posted:
            values = [commission_value(p['products'][0]) for p in posted if p['products']]
            best = max(posted, key=lambda p: commission_value(p['products'][0]) if p['products'] else 0)
            lines.append(f"💰 Comissão por venda dos itens divulgados: média {brl(sum(values) / len(values))}, "
                         f"maior {brl(max(values))} ({e(best['product_name'][:30])})")
            trocas = sum(1 for p in posted if p.get('troca') == 'trocado')
            lines.append(f"🔁 Trocados por loja de comissão maior: {trocas}")
            lines += ["", "<b>Postados</b>"]
            for p in posted:
                when = datetime.fromisoformat(p['posted_at'] or p['scheduled_at']).astimezone(scheduler.TZ)
                main = p['products'][0] if p['products'] else {}
                lines.append(f"{when:%H:%M} · {e(p['product_name'][:40])} · {e(main.get('shopName', '')[:20])} "
                             f"({brl(commission_value(main)) if main else '-'})")

        lines += ["", f"💵 Vendas do dia (Shopee): {self.day_sales(day)}"]

        tomorrow = day + timedelta(days=1)
        scheduled = self.db.scheduled()
        lines += ["", "<b>Agora</b>",
                  f"✅ Em Editados: {len(self.db.with_status('editado'))}",
                  f"⏰ Agendados: {len(scheduled)} (para {tomorrow:%d/%m}: "
                  f"{sum(1 for p in scheduled if self._day(p['scheduled_at']) == tomorrow)})",
                  f"📌 Pendências: {len(self.pending_items())}"]

        all_posted = self.db.with_status('postado')
        week = [(day - timedelta(days=i)) for i in range(6, -1, -1)]
        counts = [sum(1 for p in all_posted if self._day(p['posted_at'] or p['scheduled_at']) == d) for d in week]
        lines += ["", "<b>Últimos 7 dias</b>"]
        for d, n in zip(week, counts):
            lines.append(f"<code>{DIAS[d.weekday()]} {d:%d/%m} {'▇' * min(n, 15):<15} {n}</code>")
        lines.append(f"Total: <b>{sum(counts)}</b> · média {sum(counts) / 7:.1f} por dia".replace('.', ','))
        return '\n'.join(lines)[:4000]

    def posts_by_sub(self) -> Dict[str, str]:
        return {p['sub_id']: p['product_name'] for p in
                self.db.with_status('editado', 'agendando', 'agendado', 'enviando', 'avisado', 'postado', 'descartado')
                if p['sub_id']}

    def day_sales(self, day: date) -> str:
        start = datetime.combine(day, datetime.min.time(), scheduler.TZ)
        try:
            items = conversions.fetch(self.pipeline.shopee, start, min(start + timedelta(days=1), scheduler.now()))
        except Exception as e:
            logger.warning(f"Relatório de conversões falhou: {e}")
            return f"não consegui consultar ({html.escape(str(e)[:120])})"
        return conversions.summary_line(items)

    def job_sales(self, thread: Optional[int], days: int):
        end = scheduler.now()
        start = datetime.combine((end - timedelta(days=days - 1)).date(), datetime.min.time(), scheduler.TZ)
        try:
            items = conversions.fetch(self.pipeline.shopee, start, end)
        except Exception as e:
            logger.warning(f"Relatório de conversões falhou: {e}")
            self.tg.send_text(thread, f"⚠️ Não consegui consultar as vendas na Shopee: {html.escape(str(e)[:300])}")
            return
        title = 'Vendas de hoje' if days == 1 else f"Vendas dos últimos {days} dias ({start:%d/%m} a {end:%d/%m})"
        self.tg.send_text(thread, conversions.report(items, self.posts_by_sub(), title)[:4000])

    def on_sales_command(self, thread: Optional[int], command: str):
        """/vendas (últimos 7 dias), /vendas hoje ou /vendas 30."""
        arg = command.split()[1].lower() if len(command.split()) > 1 else '7'
        days = 1 if arg == 'hoje' else int(arg) if arg.isdigit() else 0
        if not 1 <= days <= 90:
            self.tg.send_text(thread, "Use /vendas, /vendas hoje ou /vendas 30 (até 90 dias).")
            return
        self.tg.send_text(thread or RELATORIO, "💵 Consultando as vendas na Shopee… (leva até 1 minuto)")
        self.submit(('sales', thread or RELATORIO, days))

    def on_report_command(self, thread: Optional[int], command: str):
        """/relatorio (hoje) ou /relatorio 10/10 (outro dia), respondido no tópico em que foi pedido."""
        day = scheduler.now().date()
        arg = command.split()[1] if len(command.split()) > 1 else ''
        try:
            if arg:
                d, m = (int(x) for x in arg.split('/')[:2])
                day = date(day.year, m, d)
        except ValueError:
            self.tg.send_text(thread, "Use /relatorio ou /relatorio 10/10.")
            return
        self.submit(('report', thread or RELATORIO, day))

    def job_ideas(self, thread: Optional[int]):
        """
        Lista de ideias sem repetir: nada já postado/agendado (nem parecido) e nada sugerido nos últimos
        ideas.REPEAT_DAYS dias, nem o mesmo anúncio nem o mesmo tipo de produto de outra loja.
        """
        today = scheduler.now().date()
        active = self.db.with_status('editado', 'agendando', 'agendado', 'enviando', 'na_lia', 'avisado', 'postado')
        used = {p['product_key'] for p in active}
        used_types = {ideas.similar_key(p['product_name']) for p in active}
        for p in active:
            used |= {f"{x['shopId']}:{x['itemId']}" for x in p['products'] or []}
        cutoff = (today - timedelta(days=ideas.REPEAT_DAYS)).isoformat()
        suggested = {k: d for k, d in json.loads(self.db.get_meta('ideias_sugeridas', '{}')).items() if d > cutoff}
        types = {k: d for k, d in json.loads(self.db.get_meta('ideias_tipos', '{}')).items() if d > cutoff}

        def skip(p: Dict) -> bool:
            kind = ideas.similar_key(p.get('productName', ''))
            key = f"{p['shopId']}:{p['itemId']}"
            return key in used or key in suggested or kind in types or kind in used_types

        try:
            seasonal, evergreen, cheap = ideas.collect(self.pipeline.shopee, today, skip)
        except Exception as e:
            logger.exception("Ideias falharam")
            self.tg.send_text(thread, f"⚠️ Não consegui buscar ideias agora: {html.escape(str(e)[:200])}")
            return
        for message in ideas.render(seasonal, evergreen, cheap, today):
            self.tg.send_text(thread, message)
        for p in seasonal + evergreen + cheap:
            suggested[f"{p['shopId']}:{p['itemId']}"] = today.isoformat()
            types[ideas.similar_key(p['productName'])] = today.isoformat()
        self.db.set_meta('ideias_sugeridas', json.dumps(suggested))
        self.db.set_meta('ideias_tipos', json.dumps(types))

    def daily_ideas(self):
        """No horário IDEIAS_HORA, a lista do dia vai sozinha para 💡 Ideias (uma vez por dia)."""
        if not IDEIAS:
            return
        current = scheduler.now()
        hour, minute = (int(x) for x in IDEAS_TIME.split(':'))
        today = current.date().isoformat()
        if (current.hour, current.minute) < (hour, minute) or self.db.get_meta('ideias_dia') == today:
            return
        self.db.set_meta('ideias_dia', today)
        self.submit(('ideas', IDEIAS))

    def daily_report(self):
        """No horário RELATORIO_HORA, o relatório do dia vai sozinho para 📊 Relatório (uma vez por dia)."""
        current = scheduler.now()
        hour, minute = (int(x) for x in REPORT_TIME.split(':'))
        today = current.date().isoformat()
        if (current.hour, current.minute) < (hour, minute) or self.db.get_meta('relatorio_dia') == today:
            return
        self.db.set_meta('relatorio_dia', today)
        self.submit(('report', RELATORIO or POSTADOS, current.date()))

    # ---------- Loop ----------

    def worker(self, jobs: queue.Queue):
        while True:
            job = jobs.get()
            try:
                if job[0] == 'video':
                    self.job_video(*job[1:])
                elif job[0] == 'headline':
                    self.job_headline(*job[1:])
                elif job[0] == 'approve':
                    self.job_approve(*job[1:])
                elif job[0] == 'variations':
                    self.job_variations(*job[1:])
                elif job[0] == 'lia':
                    self.job_lia(*job[1:])
                elif job[0] == 'lia_check':
                    self.job_lia_check()
                elif job[0] == 'lia_retro':
                    self.job_lia_retro(*job[1:])
                elif job[0] == 'resubid_agenda':
                    self.job_resubid_agenda()
                elif job[0] == 'replace_link':
                    self.job_replace_link(*job[1:])
                elif job[0] == 'soldout':
                    self.job_sold_out(*job[1:])
                elif job[0] == 'caption':
                    self.job_caption(*job[1:])
                elif job[0] == 'switch':
                    self.job_switch(*job[1:])
                elif job[0] == 'report':
                    self.tg.send_text(job[1], self.report_text(job[2]))
                elif job[0] == 'ideas':
                    self.job_ideas(*job[1:])
                elif job[0] == 'sales':
                    self.job_sales(*job[1:])
            except Exception:
                logger.exception(f"Falha no job {job[0]}")

    def handle(self, update: Dict):
        if 'callback_query' in update:
            self.on_callback(update['callback_query'])
            return
        msg = update.get('message')
        if not msg:
            return
        if msg.get('chat', {}).get('id') != self.tg.chat_id:
            self.on_external(msg)
            return
        thread = msg.get('message_thread_id')
        command = (msg.get('text') or '').strip()
        if command.lower().startswith('/relatorio'):
            self.on_report_command(thread, command)
            return
        if command.lower().startswith('/sugestoes') or command.lower().startswith('/sugestões'):
            target = thread or IDEIAS
            self.tg.send_text(target, "💡 Buscando ideias na Shopee… (leva 1 a 2 minutos)")
            self.submit(('ideas', target))
            return
        if command.lower().startswith('/verificarlia'):
            self.tg.send_text(thread or AGENDA, "🔎 Conferindo a conversa com a LiA…")
            self.submit(('lia_retro', thread or AGENDA))
            return
        if command.lower().startswith('/vendas'):
            self.on_sales_command(thread, command)
            return
        if thread == ENVIOS:
            self.on_envios(msg)
        elif thread == EDITADOS and msg.get('reply_to_message') and not msg.get('from', {}).get('is_bot'):
            self.on_editados_reply(msg)

    # ---------- Central Post TikTok (tópico Brutos) ----------

    def on_external(self, msg: Dict):
        """Grupo de fora: só o tópico registrado com /brutos interessa; o robô não fala nada lá."""
        chat_id = msg['chat']['id']
        thread = msg.get('message_thread_id')
        text = (msg.get('text') or '').strip().lower()
        if text.startswith('/brutos'):
            self.db.set_meta('fonte_chat', str(chat_id))
            self.db.set_meta('fonte_topico', str(thread or ''))
            nome = html.escape(msg['chat'].get('title', 'grupo'))
            self.tg.send_text(ENVIOS, f"🔗 Conectado: vídeos novos do tópico em <b>{nome}</b> serão copiados para cá.")
            logger.info(f"Fonte de vídeos registrada: chat {chat_id}, tópico {thread}")
            return

        if str(chat_id) != self.db.get_meta('fonte_chat') or str(thread or '') != self.db.get_meta('fonte_topico'):
            return
        file_id = (msg.get('video') or {}).get('file_id')
        if not file_id and msg.get('document', {}).get('mime_type', '').startswith('video/'):
            file_id = msg['document']['file_id']
        if not file_id:
            return
        copied = self.tg.copy(ENVIOS, chat_id, msg['message_id'])
        self.on_envios({'message_id': copied, 'video': {'file_id': file_id},
                        'caption': msg.get('caption') or ''})

    def recover_lia(self):
        """Envio à LiA interrompido por reinício: não reenvia sozinho (pode ter chegado lá)."""
        for post in self.db.scheduled():
            if post['status'] != 'enviando':
                continue
            self.db.update_post(post['id'], status='avisado')
            msg_id = self.tg.send_text(
                AGENDA, f"⚠️ O robô reiniciou enquanto enviava <b>{html.escape(post['product_name'])}</b> à LiA. "
                        "Confira na conversa com ela; se não chegou, toque 📤 Enviar à LiA.",
                reply_to=post['agenda_msgs'][-1] if post['agenda_msgs'] else None,
                markup=self.agenda_markup(post['id']))
            self.db.update_post(post['id'], agenda_msgs=post['agenda_msgs'] + [msg_id])

    def register_commands(self):
        """Menu do / : no grupo do robô, os comandos dele; nos outros grupos, só o /brutos."""
        self.tg.set_commands([
            ('relatorio', 'Resumo de hoje (ou /relatorio 10/10 para outro dia)'),
            ('vendas', 'Vendas reais por vídeo: 7 dias (ou /vendas hoje, /vendas 30)'),
            ('sugestoes', 'Ideias de produtos para gravar (comissão ≥ R$ 9)'),
            ('verificarlia', 'Confere na LiA se algum vídeo ficou sem publicar'),
            ('cookies', 'Login da Shopee: mande junto o arquivo exportado (em Envios)'),
        ], {'type': 'chat', 'chat_id': self.tg.chat_id})
        self.tg.set_commands([
            ('brutos', 'Conecta este tópico: vídeos novos vão para Envios'),
        ], {'type': 'all_group_chats'})

    def resume_after_restart(self):
        """Retoma o que estava em andamento quando o robô foi reiniciado (ex.: por uma atualização)."""
        self.pending = json.loads(self.db.get_meta('videos_sem_link', '[]'))
        jobs = self.db.video_jobs()
        for j in jobs:
            self.submit(('video', j['msg_id'], j['file_id'], j['link'], j['text'], bool(j['trust'])))
        stuck = self.db.with_status('agendando')
        for post in stuck:
            self.submit(('approve', post['id']))
        if jobs or stuck:
            logger.info(f"Retomando depois do reinício: {len(jobs)} vídeo(s) na fila, {len(stuck)} agendamento(s)")

    def run(self):
        self.register_commands()
        self.resume_after_restart()
        self.submit(('resubid_agenda',))
        if self.lia and self.db.get_meta('lia_retro_feito') != '2':   # uma vez: acerta os vídeos antigos
            self.db.set_meta('lia_retro_feito', '2')
            self.submit(('lia_retro',))
        self.recover_lia()
        for name, jobs in self.queues.items():
            for _ in range(VIDEO_WORKERS if name == 'video' else 1):
                threading.Thread(target=self.worker, args=(jobs,), daemon=True).start()
        logger.info(f"LiA: {'ligada (' + self.lia_when + ')' if self.lia else 'desligada'}")
        offset = int(self.db.get_meta('offset', '0'))
        logger.info("Robô do Shopee Video ligado")
        while True:
            try:
                for update in self.tg.get_updates(offset, timeout=20):
                    offset = update['update_id'] + 1
                    self.db.set_meta('offset', str(offset))
                    try:
                        self.handle(update)
                    except Exception:
                        logger.exception("Falha ao tratar update")
                self.tick()
                self.refresh_pending()
                self.daily_report()
                self.daily_ideas()
                if self.lia and time.time() - self.lia_checked > LIA_CHECK_SECONDS:
                    self.lia_checked = time.time()
                    self.submit(('lia_check',))
            except requests.RequestException as e:
                logger.warning(f"Telegram sem resposta ({e.__class__.__name__}); tentando de novo")
                time.sleep(5)
            except Exception:
                logger.exception("Falha no loop principal")
                time.sleep(5)


if __name__ == '__main__':
    Bot().run()
