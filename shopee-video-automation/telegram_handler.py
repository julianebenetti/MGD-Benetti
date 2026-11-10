"""
Cliente da Bot API do Telegram usado pelo robô.
"""

import json
import logging
import os
import re
import socket
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
import urllib3.util.connection

logger = logging.getLogger(__name__)

# Em VPS com IPv6 instável, a conexão com o Telegram fica pendurada até estourar o tempo ("sem resposta").
# Por padrão as conexões do robô (requests: Telegram e Shopee) usam só IPv4. FORCAR_IPV4=nao desliga.
if os.getenv('FORCAR_IPV4', 'sim').strip().lower() != 'nao':
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET

SHOPEE_LINK_RE = re.compile(
    r'https?://(?:[\w-]+\.)?(?:shopee\.com\.br|shp\.ee)/\S+', re.IGNORECASE)


def placeholder() -> Path:
    """Imagem pequena que substitui capa/vídeo que o Telegram não deixou apagar."""
    path = Path(__file__).parent / 'assets' / 'resolvido.png'
    if not path.exists():
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (320, 80), (34, 139, 34))
        ImageDraw.Draw(img).text((20, 30), 'OK - resolvido', fill=(255, 255, 255))
        path.parent.mkdir(exist_ok=True)
        img.save(path)
    return path


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
        self.last_delete_error = ''   # motivo da última recusa ao apagar (mostrado no /limparagenda)
        self.on_sent = None   # (tópico, [ids]) de cada mensagem enviada: o robô anota as da Agenda para limpar depois

    def call(self, method: str, timeout: int = 30, **kwargs):
        """
        Chamada à Bot API. Conexão lenta/instável (ex.: vários vídeos subindo ao mesmo tempo no VPS): tenta de novo
        até 3 vezes, esperando 5 s e 15 s. Envio com arquivo só repete se nem conectou (para não duplicar).
        """
        waits = [] if method == 'getUpdates' else [5, 15]
        for attempt in range(len(waits) + 1):
            try:
                if attempt and kwargs.get('files'):
                    for f in kwargs['files'].values():
                        handle = f[1] if isinstance(f, tuple) else f
                        if hasattr(handle, 'seek'):
                            handle.seek(0)
                resp = requests.post(f"{self.api_url}/{method}", timeout=timeout, **kwargs)
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                sent = isinstance(e, requests.ReadTimeout) and kwargs.get('files')
                if attempt == len(waits) or sent:
                    raise
                logger.warning(f"Telegram {method}: sem resposta ({e}); tentando de novo em {waits[attempt]} s")
                time.sleep(waits[attempt])
        data = resp.json()
        if not data.get('ok'):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        thread = (kwargs.get('data') or {}).get('message_thread_id')
        if self.on_sent and thread and method in ('sendMessage', 'sendMediaGroup', 'sendPhoto', 'sendDocument'):
            result = data['result']
            try:
                self.on_sent(int(thread), [m['message_id'] for m in result] if isinstance(result, list)
                             else [result['message_id']])
            except Exception as e:
                logger.warning(f"Não anotei a mensagem enviada: {e}")
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
            return self.call('sendPhoto', timeout=120, data={
                'chat_id': self.chat_id, 'caption': caption, 'parse_mode': 'HTML', **self._thread(thread_id)},
                files={'photo': photo})['message_id']

    def send_document(self, thread_id: Optional[int], name: str, content: bytes, caption: str = '') -> int:
        return self.call('sendDocument', timeout=120, data={
            'chat_id': self.chat_id, 'caption': caption, 'parse_mode': 'HTML', **self._thread(thread_id)},
            files={'document': (name, content)})['message_id']

    def edit_text(self, message_id: int, text: str, markup: Optional[str] = None) -> bool:
        """Troca o texto (e os botões) de uma mensagem; False se ela não existe mais (foi apagada)."""
        try:
            self.call('editMessageText', data={
                'chat_id': self.chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML',
                'link_preview_options': json.dumps({'is_disabled': True}),
                **({'reply_markup': markup} if markup else {})})
        except RuntimeError as e:
            if 'not modified' in str(e):
                return True
            logger.warning(f"Não consegui editar a mensagem {message_id}: {e}")
            return False
        return True

    def set_commands(self, commands: List[tuple], scope: Dict):
        """Menu que aparece ao digitar / (lista de (comando, descrição))."""
        try:
            self.call('setMyCommands', data={
                'commands': json.dumps([{'command': c, 'description': d} for c, d in commands], ensure_ascii=False),
                'scope': json.dumps(scope)})
        except RuntimeError as e:
            logger.warning(f"Não consegui registrar os comandos: {e}")

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
            if 'not modified' not in str(e):
                logger.warning(f"Não consegui atualizar os botões: {e}")

    def delete(self, message_ids: List[int]) -> List[int]:
        """Apaga as mensagens; devolve as que o Telegram não deixou apagar (o lote falhou: tenta uma a uma)."""
        failed = []
        self.last_delete_error = ''
        for chunk in range(0, len(message_ids), 100):
            ids = message_ids[chunk:chunk + 100]
            try:
                self.call('deleteMessages', data={'chat_id': self.chat_id, 'message_ids': json.dumps(ids)})
                continue
            except (RuntimeError, requests.RequestException) as e:
                logger.warning(f"Não consegui apagar {len(ids)} mensagem(ns) de uma vez: {e}")
            for msg_id in ids:
                try:
                    self.call('deleteMessage', data={'chat_id': self.chat_id, 'message_id': msg_id})
                except RuntimeError as e:
                    if 'not found' not in str(e).lower():
                        failed.append(msg_id)
                        self.last_delete_error = str(e)
                        logger.warning(f"Não consegui apagar a mensagem {msg_id}: {e}")
                except requests.RequestException as e:
                    failed.append(msg_id)
                    self.last_delete_error = f"sem resposta do Telegram ({e})"
        return failed

    def can_delete(self) -> Optional[bool]:
        """O robô é administrador com a permissão "Apagar mensagens" no grupo? (None: não deu para saber)"""
        try:
            me = self.call('getMe')['id']
            member = self.call('getChatMember', data={'chat_id': self.chat_id, 'user_id': me})
        except (RuntimeError, requests.RequestException) as e:
            logger.warning(f"Não consegui ver as permissões do robô: {e}")
            return None
        return member.get('status') == 'creator' or bool(member.get('can_delete_messages'))

    def tidy(self, message_ids: List[int], note: str) -> List[int]:
        """Como tidy_report; devolve só as que nem apagar nem resumir deu."""
        return self.tidy_report(message_ids, note)[2]

    def tidy_report(self, message_ids: List[int], note: str):
        """
        Tira as mensagens do caminho: apaga; se o Telegram não deixar, vira uma linha curta (`note`) sem botões
        (texto) ou uma imagem pequena com a `note` (capa/vídeo). Devolve (apagadas, resumidas, nem isso).
        """
        failed = self.delete(message_ids)
        left, summarized = [], []
        for msg_id in failed:
            empty = json.dumps({'inline_keyboard': []})
            try:
                self.call('editMessageText', data={'chat_id': self.chat_id, 'message_id': msg_id, 'text': note,
                                                   'reply_markup': empty})
                summarized.append(msg_id)
                continue
            except RuntimeError as e:
                if 'not modified' in str(e):
                    summarized.append(msg_id)
                    continue
            try:   # foto/vídeo: troca pela imagem pequena
                with open(placeholder(), 'rb') as img:
                    self.call('editMessageMedia', timeout=60, data={
                        'chat_id': self.chat_id, 'message_id': msg_id, 'reply_markup': empty,
                        'media': json.dumps({'type': 'photo', 'media': 'attach://img', 'caption': note})},
                        files={'img': img})
                summarized.append(msg_id)
                continue
            except (RuntimeError, requests.RequestException, OSError) as e:
                if 'not modified' in str(e):
                    summarized.append(msg_id)
                    continue
                logger.warning(f"Não consegui apagar nem resumir a mensagem {msg_id}: {e}")
            left.append(msg_id)
        deleted = [i for i in message_ids if i not in failed]
        return deleted, summarized, left

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
        file_path = self.call('getFile', timeout=60, data={'file_id': file_id})['file_path']
        for attempt in range(3):
            try:
                resp = requests.get(f"https://api.telegram.org/file/bot{self.token}/{file_path}", timeout=600)
                resp.raise_for_status()
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 2:
                    raise
                logger.warning(f"Download do Telegram falhou ({e}); tentando de novo")
                time.sleep(10)
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{file_id}{Path(file_path).suffix or '.mp4'}"
        out.write_bytes(resp.content)
        return out
