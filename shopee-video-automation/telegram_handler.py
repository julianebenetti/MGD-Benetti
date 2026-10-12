"""
Cliente da Bot API do Telegram usado pelo robô.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

SHOPEE_LINK_RE = re.compile(
    r'https?://(?:[\w-]+\.)?(?:shopee\.com\.br|shp\.ee)/\S+', re.IGNORECASE)


def extract_shopee_links(text: str) -> List[str]:
    return SHOPEE_LINK_RE.findall(text or '')


def keyboard(*rows: List[tuple]) -> str:
    return json.dumps({'inline_keyboard': [
        [{'text': label, 'callback_data': data} for label, data in row] for row in rows]})


class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = int(chat_id)
        self.api_url = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, timeout: int = 120, **kwargs):
        resp = requests.post(f"{self.api_url}/{method}", timeout=timeout, **kwargs)
        data = resp.json()
        if not data.get('ok'):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data['result']

    def get_updates(self, offset: int, timeout: int = 30) -> List[Dict]:
        return self.call('getUpdates', timeout=timeout + 15, data={
            'offset': offset, 'timeout': timeout,
            'allowed_updates': json.dumps(['message', 'callback_query'])})

    def create_topic(self, name: str, icon_color: int) -> int:
        return self.call('createForumTopic', data={
            'chat_id': self.chat_id, 'name': name, 'icon_color': icon_color})['message_thread_id']

    def _thread(self, thread_id: Optional[int]) -> Dict:
        return {'message_thread_id': thread_id} if thread_id else {}

    def send_text(self, thread_id: Optional[int], text: str, reply_to: Optional[int] = None,
                  markup: Optional[str] = None) -> int:
        data = {'chat_id': self.chat_id, 'text': text, 'parse_mode': 'HTML',
                'link_preview_options': json.dumps({'is_disabled': True}), **self._thread(thread_id)}
        if reply_to:
            data['reply_parameters'] = json.dumps({'message_id': reply_to, 'allow_sending_without_reply': True})
        if markup:
            data['reply_markup'] = markup
        return self.call('sendMessage', data=data)['message_id']

    def copy(self, thread_id: Optional[int], from_chat_id: int, message_id: int) -> int:
        """Copia uma mensagem de outro grupo para cá (sem o 'encaminhado de')."""
        return self.call('copyMessage', data={
            'chat_id': self.chat_id, 'from_chat_id': from_chat_id, 'message_id': message_id,
            **self._thread(thread_id)})['message_id']

    def send_cover_and_video(self, thread_id: Optional[int], cover_path: str, video_path: str) -> List[int]:
        media = [
            {'type': 'photo', 'media': 'attach://cover'},
            {'type': 'video', 'media': 'attach://video', 'supports_streaming': True},
        ]
        with open(cover_path, 'rb') as cover, open(video_path, 'rb') as video:
            result = self.call('sendMediaGroup', timeout=600,
                               data={'chat_id': self.chat_id, 'media': json.dumps(media), **self._thread(thread_id)},
                               files={'cover': cover, 'video': video})
        return [m['message_id'] for m in result]

    def send_photo(self, thread_id: Optional[int], photo_path: str, caption: str = '') -> int:
        with open(photo_path, 'rb') as photo:
            return self.call('sendPhoto', data={
                'chat_id': self.chat_id, 'caption': caption, 'parse_mode': 'HTML', **self._thread(thread_id)},
                files={'photo': photo})['message_id']

    def edit_text(self, message_id: int, text: str) -> bool:
        """Troca o texto de uma mensagem; False se ela não existe mais (foi apagada)."""
        try:
            self.call('editMessageText', data={
                'chat_id': self.chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML',
                'link_preview_options': json.dumps({'is_disabled': True})})
        except RuntimeError as e:
            if 'not modified' in str(e):
                return True
            logger.warning(f"Não consegui editar a mensagem {message_id}: {e}")
            return False
        return True

    def pin(self, message_id: int):
        try:
            self.call('pinChatMessage', data={'chat_id': self.chat_id, 'message_id': message_id,
                                              'disable_notification': True})
        except RuntimeError as e:
            logger.warning(f"Não consegui fixar a mensagem: {e}")

    def message_link(self, thread_id: Optional[int], message_id: int) -> str:
        """Link que abre a mensagem dentro do tópico."""
        internal = str(self.chat_id).removeprefix('-100')
        return f"https://t.me/c/{internal}/{thread_id}/{message_id}" if thread_id \
            else f"https://t.me/c/{internal}/{message_id}"

    def edit_markup(self, message_id: int, markup: str):
        try:
            self.call('editMessageReplyMarkup', data={
                'chat_id': self.chat_id, 'message_id': message_id, 'reply_markup': markup})
        except RuntimeError as e:
            logger.warning(f"Não consegui atualizar os botões: {e}")

    def delete(self, message_ids: List[int]):
        for chunk in range(0, len(message_ids), 100):
            try:
                self.call('deleteMessages', data={
                    'chat_id': self.chat_id, 'message_ids': json.dumps(message_ids[chunk:chunk + 100])})
            except RuntimeError as e:
                logger.warning(f"Não consegui apagar mensagens: {e}")

    def react(self, message_id: int, emoji: str):
        try:
            self.call('setMessageReaction', data={
                'chat_id': self.chat_id, 'message_id': message_id,
                'reaction': json.dumps([{'type': 'emoji', 'emoji': emoji}])})
        except RuntimeError as e:
            logger.warning(f"Reação {emoji} falhou: {e}")

    def answer_callback(self, callback_id: str, text: str = ''):
        try:
            self.call('answerCallbackQuery', data={'callback_query_id': callback_id, 'text': text})
        except RuntimeError as e:
            logger.warning(f"answerCallbackQuery falhou: {e}")

    def download(self, file_id: str, dest_dir: Path) -> Path:
        file_path = self.call('getFile', data={'file_id': file_id})['file_path']
        resp = requests.get(f"https://api.telegram.org/file/bot{self.token}/{file_path}", timeout=600)
        resp.raise_for_status()
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{file_id}{Path(file_path).suffix or '.mp4'}"
        out.write_bytes(resp.content)
        return out
