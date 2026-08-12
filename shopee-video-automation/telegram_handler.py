"""
Telegram Bot Handler
Monitora o grupo Shopee Video e extrai vídeos + links de produtos
"""

import logging
import requests
import re
from typing import List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TelegramMonitor:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0

    def get_updates(self) -> List[Dict]:
        """Obtém mensagens novas do grupo"""
        try:
            params = {
                'allowed_updates': ['message'],
                'timeout': 30
            }
            if self.last_update_id:
                params['offset'] = self.last_update_id + 1

            response = requests.get(f"{self.api_url}/getUpdates", params=params)
            response.raise_for_status()

            updates = response.json().get('result', [])

            if updates:
                self.last_update_id = updates[-1]['update_id']

            return updates

        except Exception as e:
            logger.error(f"Erro ao buscar updates: {e}")
            return []

    def extract_shopee_links(self, text: str) -> List[str]:
        """Extrai links Shopee do texto"""
        if not text:
            return []

        pattern = r'https://(?:br\.)?shopee\.com(?:\.br)?/[^\s]+'
        matches = re.findall(pattern, text)
        return matches

    def get_new_messages(self) -> List[Dict]:
        """Busca mensagens novas com vídeos e links Shopee"""
        updates = self.get_updates()
        processed_messages = []

        for update in updates:
            if 'message' not in update:
                continue

            message = update['message']

            # Verificar se é do grupo correto
            if message.get('chat', {}).get('id') != int(self.chat_id):
                continue

            # Extrair vídeo
            video_file_id = None
            if 'video' in message:
                video_file_id = message['video']['file_id']
            elif 'document' in message:
                # Também aceitar vídeos como documentos
                if message['document']['mime_type'].startswith('video/'):
                    video_file_id = message['document']['file_id']

            # Extrair links Shopee
            text = message.get('text', '') or message.get('caption', '')
            shopee_links = self.extract_shopee_links(text)

            # Se tem vídeo E link Shopee, processar
            if video_file_id and shopee_links:
                for link in shopee_links:
                    video_path = self.download_video(video_file_id)
                    if video_path:
                        processed_messages.append({
                            'video_file': video_path,
                            'product_link': link,
                            'message_id': message['message_id'],
                            'from_user': message.get('from', {}).get('username', 'unknown')
                        })
                        logger.info(f"Mensagem processada: {link}")

        return processed_messages

    def download_video(self, file_id: str) -> str:
        """Baixa vídeo do Telegram"""
        try:
            # 1. Obter informações do arquivo
            response = requests.get(f"{self.api_url}/getFile", params={'file_id': file_id})
            response.raise_for_status()

            file_path = response.json()['result']['file_path']

            # 2. Baixar arquivo
            download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            video_response = requests.get(download_url)
            video_response.raise_for_status()

            # 3. Salvar localmente
            output_file = f"./downloads/{file_id}.mp4"
            import os
            os.makedirs('./downloads', exist_ok=True)

            with open(output_file, 'wb') as f:
                f.write(video_response.content)

            logger.info(f"Vídeo baixado: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Erro ao baixar vídeo: {e}")
            return None
