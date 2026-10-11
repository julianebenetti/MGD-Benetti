#!/usr/bin/env python3
"""
Shopee Video Posts Automation
Monitora grupo Telegram, processa vídeos e publica na Shopee Video
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from telegram_handler import TelegramMonitor
from video_processor import VideoProcessor
from shopee_affiliate import ShopeeAffiliateClient
from content_generator import ContentGenerator
from cover_generator import CoverGenerator
from product_matcher import check_match
from sub_id import novo_sub_id

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

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _pick_product(self, video_path: str, candidates: list):
        """Primeiro candidato que a IA confirma estar no vídeo; senão (None, motivos)."""
        motivos = []
        for product in candidates:
            resultado, motivo = check_match(video_path, product)
            if resultado == 'sim':
                return product, []
            motivos.append(f"• {product['productName']}: {resultado} ({motivo})")
        return None, motivos

    def process_message(self, message: dict):
        link = message['product_link']
        candidates = self.shopee.find_candidates(link, message.get('text', ''))
        if not candidates:
            logger.warning(f"Produto não identificado para {link}")
            self.telegram.reply_in_envios(
                message['message_id'],
                "⚠️ Não consegui identificar o produto deste vídeo. "
                "Reenvie com o link do PRODUTO (não do vídeo) ou com o nome exato do produto."
            )
            return

        processed_video = self.video_processor.process(message['video_file'], self.output_dir)
        if not processed_video:
            self.telegram.reply_in_envios(message['message_id'], "⚠️ Não consegui processar este vídeo.")
            return

        product, motivos = self._pick_product(processed_video, candidates)
        if not product:
            self.telegram.reply_in_envios(
                message['message_id'],
                "⚠️ A conferência não confirmou que o produto é o do vídeo, então não segui:\n"
                + "\n".join(motivos)
                + "\n\nReenvie com o link do produto certo."
            )
            return

        product_info = {
            'name': product['productName'],
            'price': product.get('priceMin') or product.get('price'),
            'rating': product.get('ratingStar'),
            'sold': product.get('sales'),
        }
        logger.info("Gerando headline, descrição, hashtags e SEO...")
        metadata = self.content_gen.generate(product_info)

        sub_id = novo_sub_id(metadata['short_name'])
        affiliate_link = self.shopee.affiliate_link(product, sub_id)
        logger.info(f"Link de afiliado ({sub_id}): {affiliate_link}")

        watermarked_video = self.video_processor.add_watermark(processed_video)
        cover_path = self.cover_gen.generate(
            watermarked_video,
            metadata['cover_title'],
            str(Path(watermarked_video).with_suffix('.capa.jpg'))
        )
        if not watermarked_video or not cover_path:
            self.telegram.reply_in_envios(message['message_id'], "⚠️ Falha ao gerar o vídeo final ou a capa.")
            return

        self.telegram.send_edited(
            watermarked_video, cover_path, metadata, affiliate_link,
            product_info['name'], sub_id
        )
        logger.info(f"✅ Vídeo pronto: {watermarked_video}")

    def run(self):
        logger.info("Iniciando automação de vídeos Shopee...")
        for message in self.telegram.get_new_messages():
            try:
                self.process_message(message)
            except Exception as e:
                logger.error(f"Erro ao processar mensagem {message.get('message_id')}: {e}", exc_info=True)
                self.telegram.reply_in_envios(message['message_id'], f"⚠️ Erro inesperado: {e}")
        logger.info("Automação concluída")


def main():
    automation = ShopeeVideoAutomation()
    automation.run()


if __name__ == '__main__':
    main()
