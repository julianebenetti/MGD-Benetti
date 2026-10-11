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
from shopee_affiliate import ShopeeAffiliateClient
from content_generator import ContentGenerator
from cover_generator import CoverGenerator

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
            chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            topic_envios=int(os.getenv('TELEGRAM_TOPIC_ENVIOS') or 0) or None,
            topic_editados=int(os.getenv('TELEGRAM_TOPIC_EDITADOS') or 0) or None
        )
        self.video_processor = VideoProcessor(
            aspect_ratio=os.getenv('VIDEO_ASPECT_RATIO', '9:16'),
            width=int(os.getenv('VIDEO_WIDTH', '1080')),
            height=int(os.getenv('VIDEO_HEIGHT', '1920')),
            bitrate=os.getenv('VIDEO_BITRATE', '5M')
        )
        self.shopee = ShopeeAffiliateClient(
            app_id=os.environ['SHOPEE_AFFILIATE_APP_ID'],
            secret=os.environ['SHOPEE_AFFILIATE_SECRET']
        )
        self.content_gen = ContentGenerator()
        self.cover_gen = CoverGenerator()

        self.output_dir = Path(os.getenv('VIDEOS_OUTPUT_DIR', './processed_videos'))
        self.drafts_dir = Path(os.getenv('DRAFTS_OUTPUT_DIR', './drafts'))

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)

    def process_video(self, video_path: str, product: dict, affiliate_link: str) -> dict:
        """Processa um vídeo do início ao fim"""
        logger.info(f"Iniciando processamento: {video_path}")

        try:
            processed_video = self.video_processor.process(video_path, self.output_dir)

            product_info = {
                'name': product['productName'],
                'price': product.get('priceMin') or product.get('price'),
                'rating': product.get('ratingStar'),
                'sold': product.get('sales'),
            }
            logger.info("Gerando headline, descrição, hashtags e SEO...")
            metadata = self.content_gen.generate(product_info)

            logger.info("Adicionando marca d'água...")
            watermarked_video = self.video_processor.add_watermark(processed_video)

            logger.info("Gerando capa...")
            cover_path = self.cover_gen.generate(
                watermarked_video,
                metadata['cover_title'],
                str(Path(watermarked_video).with_suffix('.capa.jpg'))
            )

            return {
                'video_path': watermarked_video,
                'cover_path': cover_path,
                'product_url': affiliate_link,
                'product_info': product_info,
                'metadata': metadata,
                'timestamp': datetime.now().isoformat(),
                'status': 'draft'
            }

        except Exception as e:
            logger.error(f"Erro ao processar vídeo: {e}", exc_info=True)
            return None

    def run(self):
        """Executa a automação"""
        logger.info("Iniciando automação de vídeos Shopee...")

        for message in self.telegram.get_new_messages():
            link = message['product_link']
            resolved = self.shopee.resolve(link, message.get('text', ''))
            if not resolved:
                logger.warning(f"Produto não identificado para {link}")
                self.telegram.reply_in_envios(
                    message['message_id'],
                    "⚠️ Não consegui identificar o produto deste vídeo com segurança. "
                    "Reenvie o vídeo com o link do PRODUTO (não do vídeo) ou com o nome exato do produto."
                )
                continue

            result = self.process_video(message['video_file'], resolved['product'], resolved['affiliate_link'])
            if result:
                logger.info(f"✅ Vídeo pronto: {result['video_path']}")
                self.telegram.send_edited(
                    result['video_path'], result['cover_path'],
                    result['metadata'], result['product_url']
                )
            else:
                logger.error("❌ Falha ao processar vídeo")

        logger.info("Automação concluída")


def main():
    automation = ShopeeVideoAutomation()
    automation.run()


if __name__ == '__main__':
    main()
