#!/usr/bin/env python3
"""
Robô do Shopee Video (sempre ligado).

📥 Envios → ✅ Editados (aprovação) → ⏰ Agenda → 🚀 Postados
"""

import html
import logging
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

import scheduler  # noqa: E402  (lê a configuração da agenda do .env)
from pipeline import Pipeline, PipelineError  # noqa: E402
from shopee_session import CookieError, save_cookies  # noqa: E402
from storage import Storage  # noqa: E402
from telegram_handler import TelegramBot, extract_shopee_links, keyboard  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('bot')

BASE = Path(__file__).parent
ASK_AFTER_SECONDS = 30
BATCH_LINK_TTL = 600
FAILED_RETRY_TTL = 1800
COVER_SECONDS = float(os.getenv('CAPA_SEGUNDOS', '1'))
DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


def topic(name: str) -> Optional[int]:
    return int(os.getenv(name) or 0) or None


ENVIOS = topic('TELEGRAM_TOPIC_ENVIOS')
EDITADOS = topic('TELEGRAM_TOPIC_EDITADOS')
AGENDA = topic('TELEGRAM_TOPIC_AGENDA')
POSTADOS = topic('TELEGRAM_TOPIC_POSTADOS')


def fmt_when(iso: str) -> str:
    when = datetime.fromisoformat(iso).astimezone(scheduler.TZ)
    return f"{DIAS[when.weekday()]}, {when:%d/%m} às {when:%H:%M}"


def post_text(post: Dict) -> str:
    e = html.escape
    m = post['metadata']
    links = '\n'.join(
        f"{i}. {e(p.get('shopName', ''))}: {e(link)}"
        for i, (p, link) in enumerate(zip(post['products'], post['links']), 1))
    return (
        f"🎬 <b>Headline:</b> {e(m['cover_title'])}\n\n"
        f"📝 <b>Descrição:</b>\n{e(m['description'])}\n\n"
        f"#️⃣ <b>Hashtags:</b>\n{e(' '.join(m['hashtags']))}\n\n"
        f"🔍 <b>SEO:</b>\n{e(', '.join(m['seo_keywords']))}\n\n"
        f"🛍️ <b>Produto:</b> {e(post['product_name'])}\n"
        f"🔗 <b>Links:</b>\n{links}\n"
        f"🏷️ <b>Sub_id:</b> {e(post['sub_id'])}"
        + ("" if post.get('sticker_path') else
           "\n\n⚠️ Capa sem o cartão de variações: o produto não tem variações, ou a Shopee pediu login "
           "(mande os cookies da Shopee com /cookies).")
    )


class Bot:
    def __init__(self):
        self.tg = TelegramBot(os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID'])
        self.db = Storage()
        self.pipeline = Pipeline(BASE / os.getenv('VIDEOS_OUTPUT_DIR', 'processed_videos'))
        self.jobs: queue.Queue = queue.Queue()
        self.pending: List[Dict] = []
        self.pending_asked = False
        self.batch_link: Optional[Dict] = None

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

        if file_id:
            if links:
                self.enqueue_video(msg['message_id'], file_id, links[0], text)
            elif self.batch_link and time.time() - self.batch_link['at'] < BATCH_LINK_TTL:
                self.enqueue_video(msg['message_id'], file_id, self.batch_link['link'],
                                   f"{self.batch_link['text']}\n{text}")
            else:
                self.pending.append({'msg_id': msg['message_id'], 'file_id': file_id,
                                     'text': text, 'at': time.time()})
        elif links:
            retry = self.failed_to_retry(msg)
            if retry:
                self.db.remove_failure(retry['msg_id'])
                self.tg.react(msg['message_id'], '👌')
                self.enqueue_video(retry['msg_id'], retry['file_id'], links[0], f"{retry['text']}\n{text}")
            elif self.pending:
                for p in self.pending:
                    self.enqueue_video(p['msg_id'], p['file_id'], links[0], f"{p['text']}\n{text}")
                self.pending, self.pending_asked = [], False
                self.tg.react(msg['message_id'], '👌')
            else:
                self.batch_link = {'link': links[0], 'text': text, 'at': time.time()}
                self.tg.react(msg['message_id'], '✍')

    def failed_to_retry(self, msg: Dict) -> Optional[Dict]:
        """
        Vídeo a refazer quando chega só um link: o vídeo respondido (o Telegram manda o vídeo junto
        com a resposta), a falha cuja mensagem de erro foi respondida, ou a falha mais recente.
        """
        replied = msg.get('reply_to_message') or {}
        video = replied.get('video') or (replied.get('document') if replied.get('document', {})
                                         .get('mime_type', '').startswith('video/') else None)
        if video:
            return {'msg_id': replied['message_id'], 'file_id': video['file_id'],
                    'text': replied.get('caption') or ''}
        return self.db.find_failure(replied.get('message_id'), FAILED_RETRY_TTL)

    def enqueue_video(self, msg_id: int, file_id: str, link: str, text: str):
        self.tg.react(msg_id, '👌')
        self.jobs.put(('video', msg_id, file_id, link, text))

    def job_video(self, msg_id: int, file_id: str, link: str, text: str):
        try:
            video = self.tg.download(file_id, BASE / 'downloads')
            result = self.pipeline.prepare(str(video), link, text, self.db.headlines_for)
        except Exception as e:
            if not isinstance(e, PipelineError):
                logger.exception("Falha ao preparar vídeo")
            reason = str(e) if isinstance(e, PipelineError) else f"Erro inesperado: {e}"
            self.tg.react(msg_id, '🤔')
            err_id = self.tg.send_text(ENVIOS, f"⚠️ {html.escape(reason)}", reply_to=msg_id)
            self.db.add_failure(msg_id, err_id, file_id, text)
            return
        post_id = self.db.create_post(source_msg_id=msg_id, **result)
        self.db.add_headline(result['product_key'], result['metadata']['cover_title'])
        self.send_to_editados(self.db.get_post(post_id))
        self.tg.react(msg_id, '👍')

    # ---------- Editados ----------

    @staticmethod
    def editados_markup(post: Dict) -> str:
        pid = post['id']
        capa = ('✅ Capa aprovada', f"cv:{pid}") if post['cover_approved'] else ('✅ Aprovar capa', f"cv:{pid}")
        return keyboard(
            [capa, ('🔄 Outra headline', f"hl:{pid}")],
            [('✅ Aprovar e agendar', f"ap:{pid}"), ('❌ Descartar', f"dc:{pid}")])

    def send_to_editados(self, post: Dict):
        ids = self.tg.send_cover_and_video(EDITADOS, post['cover_path'], post['video_path'])
        ids.append(self.tg.send_text(EDITADOS, post_text(post), markup=self.editados_markup(post)))
        self.db.update_post(post['id'], editados_msgs=ids)

    def job_headline(self, post_id: int, headline: Optional[str]):
        post = self.db.get_post(post_id)
        if not post or post['status'] != 'editado':
            return
        if headline is None:
            headline = self.pipeline.new_headline(post, self.db.headlines_for(post['product_key']))
        cover = self.pipeline.make_cover(post['video_path'], headline, post.get('sticker_path'))
        metadata = {**post['metadata'], 'cover_title': headline}
        self.tg.delete(post['editados_msgs'])
        self.db.update_post(post_id, metadata=metadata, cover_path=cover, cover_approved=0)
        self.db.add_headline(post['product_key'], headline)
        self.send_to_editados(self.db.get_post(post_id))

    def job_approve(self, post_id: int):
        """Junta a capa na abertura do vídeo, reserva o horário e move para a Agenda."""
        post = self.db.get_post(post_id)
        final = str(Path(post['video_path']).with_name(f"final_{post_id}.mp4"))
        if not self.pipeline.video.prepend_cover(post['cover_path'], post['video_path'], final, COVER_SECONDS):
            self.db.update_post(post_id, status='editado')
            self.tg.send_text(EDITADOS, "⚠️ Não consegui juntar a capa ao vídeo. Tente aprovar de novo.",
                              reply_to=post['editados_msgs'][-1] if post['editados_msgs'] else None)
            return
        slot = scheduler.next_slot(post['product_key'], self.db.scheduled())
        self.tg.delete(post['editados_msgs'])
        self.db.update_post(post_id, status='agendado', scheduled_at=slot.isoformat(),
                            editados_msgs=[], final_video_path=final)
        post = self.db.get_post(post_id)
        ids = self.tg.send_cover_and_video(AGENDA, post['cover_path'], final)
        ids.append(self.tg.send_text(
            AGENDA, f"⏰ <b>{fmt_when(post['scheduled_at'])}</b>\n\n{post_text(post)}",
            markup=keyboard([('✅ Postei', f"ok:{post_id}"), ('❌ Descartar', f"dc:{post_id}")])))
        self.db.update_post(post_id, agenda_msgs=ids)

    def on_editados_reply(self, msg: Dict):
        post = self.db.post_by_editados_msg(msg['reply_to_message']['message_id'])
        text = (msg.get('text') or '').strip()
        if post and text:
            self.tg.react(msg['message_id'], '✍')
            self.jobs.put(('headline', post['id'], text[:60]))

    # ---------- Botões ----------

    def on_callback(self, cb: Dict):
        action, _, raw_id = cb.get('data', '').partition(':')
        post = self.db.get_post(int(raw_id)) if raw_id.isdigit() else None
        if not post:
            self.tg.answer_callback(cb['id'], 'Post não encontrado')
            return

        if action == 'cv' and post['status'] == 'editado':
            if post['cover_approved']:
                self.tg.answer_callback(cb['id'], 'Capa já aprovada')
                return
            self.db.update_post(post['id'], cover_approved=1)
            self.tg.edit_markup(post['editados_msgs'][-1], self.editados_markup(self.db.get_post(post['id'])))
            self.tg.answer_callback(cb['id'], 'Capa aprovada')

        elif action == 'ap' and post['status'] == 'editado' and not post['cover_approved']:
            self.tg.answer_callback(cb['id'], 'Aprove a capa primeiro (✅ Aprovar capa)')

        elif action == 'ap' and post['status'] == 'editado':
            self.db.update_post(post['id'], status='agendando')
            self.tg.answer_callback(cb['id'], 'Juntando a capa ao vídeo e agendando…')
            self.jobs.put(('approve', post['id']))

        elif action == 'hl' and post['status'] == 'editado':
            self.tg.answer_callback(cb['id'], 'Gerando outra headline…')
            self.jobs.put(('headline', post['id'], None))

        elif action == 'dc' and post['status'] in ('editado', 'agendado', 'avisado'):
            self.tg.delete(post['editados_msgs'] + post['agenda_msgs'])
            self.db.update_post(post['id'], status='descartado')
            self.tg.answer_callback(cb['id'], 'Descartado')

        elif action == 'ok' and post['status'] in ('agendado', 'avisado'):
            self.tg.delete(post['agenda_msgs'])
            self.db.update_post(post['id'], status='postado', agenda_msgs=[])
            self.tg.send_photo(POSTADOS, post['cover_path'],
                               f"✅ Postado ({fmt_when(scheduler.now().isoformat())})\n\n{post_text(post)}"[:1024])
            self.tg.answer_callback(cb['id'], 'Movido para Postados')

        else:
            self.tg.answer_callback(cb['id'], 'Já resolvido')

    # ---------- Relógio ----------

    def tick(self):
        if self.pending and not self.pending_asked and time.time() - self.pending[0]['at'] > ASK_AFTER_SECONDS:
            self.pending_asked = True
            n = len(self.pending)
            self.tg.send_text(ENVIOS, f"🔗 Recebi {n} vídeo(s) sem link. Mande o link do produto "
                                      f"(vale para {'todos' if n > 1 else 'ele'}).",
                              reply_to=self.pending[0]['msg_id'])

        current = scheduler.now()
        for post in self.db.scheduled():
            if post['status'] == 'agendado' and datetime.fromisoformat(post['scheduled_at']) <= current:
                reply_to = post['agenda_msgs'][-1] if post['agenda_msgs'] else None
                msg_id = self.tg.send_text(AGENDA, f"⏰ <b>Hora de postar!</b> {html.escape(post['product_name'])}",
                                           reply_to=reply_to)
                self.db.update_post(post['id'], status='avisado', agenda_msgs=post['agenda_msgs'] + [msg_id])

    # ---------- Loop ----------

    def worker(self):
        while True:
            job = self.jobs.get()
            try:
                if job[0] == 'video':
                    self.job_video(*job[1:])
                elif job[0] == 'headline':
                    self.job_headline(*job[1:])
                elif job[0] == 'approve':
                    self.job_approve(*job[1:])
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

    def run(self):
        threading.Thread(target=self.worker, daemon=True).start()
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
            except Exception:
                logger.exception("Falha no loop principal")
                time.sleep(5)


if __name__ == '__main__':
    Bot().run()
