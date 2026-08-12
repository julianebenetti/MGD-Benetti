#!/usr/bin/env python3
"""
Shopee Video Posts Automation
Monitora grupo Telegram, processa vídeos e publica na Shopee Video
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from telegram_handler import TelegramMonitor
from video_processor import VideoProcessor
from shopee_scraper import ShopeeScraper
from content_generator import ContentGenerator

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ShopeeVideoAutomation:
    def __init__(self):
        self.telegram = TelegramMonitor(
            token=os.getenv('TELEGRAM_BOT_TOKEN'),
            chat_id=os.getenv('TELEGRAM_CHAT_ID')
        )
        self.video_processor = VideoProcessor(
            aspect_ratio=os.getenv('VIDEO_ASPECT_RATIO', '9:16'),
            width=int(os.getenv('VIDEO_WIDTH', '1080')),
            height=int(os.getenv('VIDEO_HEIGHT', '1920')),
            bitrate=os.getenv('VIDEO_BITRATE', '5M')
        )
        self.shopee = ShopeeScraper()
        self.content_gen = ContentGenerator()

        self.output_dir = Path(os.getenv('VIDEOS_OUTPUT_DIR', './processed_videos'))
        self.drafts_dir = Path(os.getenv('DRAFTS_OUTPUT_DIR', './drafts'))

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def process_video(self, video_path: str, product_url: str) -> dict:
        """Processa um vídeo do início ao fim"""
        logger.info(f"Iniciando processamento: {video_path}")

        try:
            # 1. Processar vídeo com FFmpeg
            logger.info("Processando vídeo...")
            processed_video = self.video_processor.process(video_path, self.output_dir)

            # 2. Extrair informações do produto
            logger.info("Extraindo informações do produto...")
            product_info = self.shopee.extract_product_info(product_url)

            # 3. Gerar metadados
            logger.info("Gerando descrição, hashtags e SEO...")
            metadata = self.content_gen.generate(product_info)

            # 4. Adicionar marca d'água
            logger.info("Adicionando marca d'água...")
            watermarked_video = self.video_processor.add_watermark(
                processed_video,
                "AfiliDash"
            )

            # 5. Salvar como rascunho
            logger.info("Salvando como rascunho...")
            draft_data = {
                'video_path': watermarked_video,
                'product_url': product_url,
                'product_info': product_info,
                'metadata': metadata,
                'timestamp': datetime.now().isoformat(),
                'status': 'draft'
            }

            return draft_data

        except Exception as e:
            logger.error(f"Erro ao processar vídeo: {e}", exc_info=True)
            return None

    def run(self):
        """Executa a automação"""
        logger.info("Iniciando automação de vídeos Shopee...")

        # Buscar vídeos e links do grupo Telegram
        messages = self.telegram.get_new_messages()

        for message in messages:
            video_file = message.get('video_file')
            product_link = message.get('product_link')

            if video_file and product_link:
                logger.info(f"Processando: {video_file} com produto {product_link}")
                result = self.process_video(video_file, product_link)

                if result:
                    logger.info(f"✅ Vídeo pronto para publicação: {result['video_path']}")
                else:
                    logger.error(f"❌ Falha ao processar vídeo")

        logger.info("Automação concluída")


def main():
    automation = ShopeeVideoAutomation()
    automation.run()


if __name__ == '__main__':
    main()
