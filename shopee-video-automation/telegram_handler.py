"""
Telegram Bot Handler
Tópicos do grupo: "📥 Envios" (entrada), "✅ Editados" (material pronto) e
"🚀 Postados" (o que já foi enviado ao bot da Shopee).
"""

import html
import json
import logging
import os
import re
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

SHOPEE_LINK_RE = re.compile(
    r'https?://(?:[\w-]+\.)?(?:shopee\.com\.br|shp\.ee)/\S+', re.IGNORECASE)


class TelegramMonitor:
    def __init__(self, token: str, chat_id: str,
                 topic_envios: Optional[int] = None, topic_editados: Optional[int] = None):
        self.token = token
        self.chat_id = int(chat_id)
        self.topic_envios = topic_envios
        self.topic_editados = topic_editados
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0

    def _call(self, method: str, **kwargs) -> Dict:
        resp = requests.post(f"{self.api_url}/{method}", timeout=120, **kwargs)
        data = resp.json()
        if not data.get('ok'):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data['result']

    def create_topic(self, name: str, icon_color: int) -> int:
        """Cria um tópico no grupo e devolve o message_thread_id."""
        result = self._call('createForumTopic', data={
            'chat_id': self.chat_id, 'name': name, 'icon_color': icon_color})
        return result['message_thread_id']

    def get_updates(self) -> List[Dict]:
        try:
            params = {'allowed_updates': json.dumps(['message']), 'timeout': 0}
            if self.last_update_id:
                params['offset'] = self.last_update_id + 1
            updates = self._call('getUpdates', data=params)
            if updates:
                self.last_update_id = updates[-1]['update_id']
                # Confirma no Telegram para a próxima execução não reprocessar
                self._call('getUpdates', data={'offset': self.last_update_id + 1, 'timeout': 0, 'limit': 1})
            return updates
        except Exception as e:
            logger.error(f"Erro ao buscar updates: {e}")
            return []

    def extract_shopee_links(self, text: str) -> List[str]:
        return SHOPEE_LINK_RE.findall(text or '')

    def _in_envios(self, message: Dict) -> bool:
        if message.get('chat', {}).get('id') != self.chat_id:
            return False
        if self.topic_envios is None:
            return True
        return message.get('message_thread_id') == self.topic_envios

    def get_new_messages(self) -> List[Dict]:
        """Vídeos enviados no tópico Envios com o link Shopee na legenda (ou na mensagem seguinte)."""
        processed = []
        pending_video: Optional[Dict] = None

        for update in self.get_updates():
            message = update.get('message')
            if not message or not self._in_envios(message):
                continue

            video_file_id = None
            if 'video' in message:
                video_file_id = message['video']['file_id']
            elif message.get('document', {}).get('mime_type', '').startswith('video/'):
                video_file_id = message['document']['file_id']

            links = self.extract_shopee_links(message.get('text') or message.get('caption'))

            if video_file_id and links:
                pending_video = None
                self._queue(processed, video_file_id, links[0], message)
            elif video_file_id:
                pending_video = {'file_id': video_file_id, 'message': message}
            elif links and pending_video:
                self._queue(processed, pending_video['file_id'], links[0], pending_video['message'])
                pending_video = None

        if pending_video:
            logger.warning(f"Vídeo sem link Shopee ignorado (msg {pending_video['message']['message_id']})")
        return processed

    def _queue(self, processed: List[Dict], file_id: str, link: str, message: Dict):
        video_path = self.download_video(file_id)
        if video_path:
            processed.append({
                'video_file': video_path,
                'product_link': link,
                'message_id': message['message_id'],
            })
            logger.info(f"Envio recebido: {link}")

    def download_video(self, file_id: str) -> Optional[str]:
        try:
            file_path = self._call('getFile', data={'file_id': file_id})['file_path']
            resp = requests.get(f"https://api.telegram.org/file/bot{self.token}/{file_path}", timeout=300)
            resp.raise_for_status()
            os.makedirs('./downloads', exist_ok=True)
            output_file = f"./downloads/{file_id}.mp4"
            with open(output_file, 'wb') as f:
                f.write(resp.content)
            logger.info(f"Vídeo baixado: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"Erro ao baixar vídeo: {e}")
            return None

    def send_edited(self, video_path: str, cover_path: str, metadata: Dict,
                    product_url: str, reply_to: Optional[int] = None) -> bool:
        """Entrega capa + vídeo + textos no tópico Editados."""
        try:
            thread = {'message_thread_id': self.topic_editados} if self.topic_editados else {}

            with open(cover_path, 'rb') as cover, open(video_path, 'rb') as video:
                media = [
                    {'type': 'photo', 'media': 'attach://cover'},
                    {'type': 'video', 'media': 'attach://video', 'supports_streaming': True},
                ]
                self._call('sendMediaGroup',
                           data={'chat_id': self.chat_id, 'media': json.dumps(media), **thread},
                           files={'cover': cover, 'video': video})

            e = html.escape
            text = (
                f"🎬 <b>Capa:</b> {e(metadata['cover_title'])}\n\n"
                f"📝 <b>Descrição:</b>\n{e(metadata['description'])}\n\n"
                f"#️⃣ <b>Hashtags:</b>\n{e(' '.join(metadata['hashtags']))}\n\n"
                f"🔍 <b>SEO:</b>\n{e(', '.join(metadata['seo_keywords']))}\n\n"
                f"🔗 <b>Produto:</b>\n{e(product_url)}"
            )
            self._call('sendMessage', data={
                'chat_id': self.chat_id, 'text': text, 'parse_mode': 'HTML',
                'disable_web_page_preview': True, **thread})
            logger.info("✅ Material entregue no tópico Editados")
            return True
        except Exception as e:
            logger.error(f"Erro ao entregar no Telegram: {e}")
            return False
