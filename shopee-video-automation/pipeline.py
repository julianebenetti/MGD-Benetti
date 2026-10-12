"""
Preparação de um vídeo: produto confirmado + links extras + textos + vídeo com logo + capa.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from content_generator import ContentGenerator
from cover_generator import CoverGenerator
from product_matcher import check_match
from product_page_capture import capture_color_thumbs
from shopee_affiliate import ShopeeAffiliateClient
from sub_id import novo_sub_id
from video_processor import VideoProcessor

logger = logging.getLogger(__name__)

TOTAL_LINKS = int(os.getenv('LINKS_POR_VIDEO', '3'))
MAX_EXTRA_CHECKS = 6


class PipelineError(Exception):
    """Erro com mensagem para mostrar no Telegram."""


def product_key(product: Dict) -> str:
    return f"{product['shopId']}:{product['itemId']}"


def product_info(product: Dict) -> Dict:
    return {
        'name': product['productName'],
        'price': product.get('priceMin') or product.get('price'),
        'rating': product.get('ratingStar'),
        'sold': product.get('sales'),
    }


class Pipeline:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        self.video = VideoProcessor()
        self.shopee = ShopeeAffiliateClient(
            app_id=os.environ['SHOPEE_AFFILIATE_APP_ID'],
            secret=os.environ['SHOPEE_AFFILIATE_SECRET'],
        )
        self.content = ContentGenerator()
        self.cover = CoverGenerator()

    def _confirmed(self, video_path: str, candidates: List[Dict], wanted: int,
                   max_checks: int = 99) -> Tuple[List[Dict], List[str]]:
        found, reasons = [], []
        for product in candidates[:max_checks]:
            resultado, motivo = check_match(video_path, product)
            if resultado == 'sim':
                found.append(product)
                if len(found) >= wanted:
                    break
            else:
                reasons.append(f"• {product['productName']}: {resultado} ({motivo})")
        return found, reasons

    def prepare(self, video_file: str, link: str, text: str, used_headlines) -> Dict:
        """
        `used_headlines(product_key) -> list` evita repetir headline do mesmo produto.
        Levanta PipelineError com a explicação quando não dá para seguir.
        """
        candidates = self.shopee.find_candidates(link, text)
        if not candidates:
            raise PipelineError("Não consegui identificar o produto deste vídeo "
                                f"(o link abriu em: {self.shopee.last_final_url[:150]}). "
                                "Mande o link do PRODUTO respondendo esta mensagem que eu refaço.")

        processed = self.video.process(video_file, self.output_dir)
        if not processed:
            raise PipelineError("Não consegui processar este vídeo.")

        main_found, reasons = self._confirmed(processed, candidates, wanted=1)
        if not main_found:
            raise PipelineError("A conferência não confirmou que o produto é o do vídeo:\n"
                                + "\n".join(reasons) + "\n\nMande o link do produto certo respondendo esta mensagem que eu refaço.")
        main = main_found[0]
        key = product_key(main)

        extras, _ = self._confirmed(processed, self.shopee.other_sellers(main),
                                    wanted=TOTAL_LINKS - 1, max_checks=MAX_EXTRA_CHECKS)
        products = [main] + extras
        logger.info(f"{len(products)} link(s) para {main['productName']}")

        info = product_info(main)
        metadata = self.content.generate(info, used_headlines(key))
        sub_id = novo_sub_id(metadata['short_name'])
        links = [self.shopee.affiliate_link(p, sub_id) for p in products]

        final_video = self.video.add_watermark(processed)
        if not final_video:
            raise PipelineError("Falha ao aplicar o logo no vídeo.")
        sticker = self.variations_print(main)
        cover = self.make_cover(final_video, metadata['cover_title'], sticker)

        return {
            'product_key': key,
            'product_name': main['productName'],
            'products': products,
            'links': links,
            'sub_id': sub_id,
            'metadata': metadata,
            'video_path': final_video,
            'cover_path': cover,
            'sticker_path': sticker,
        }

    def variations_print(self, product: Dict) -> Optional[str]:
        """Cartão com as miniaturas das cores do produto (None se não tiver cores)."""
        url = f"https://shopee.com.br/product/{product['shopId']}/{product['itemId']}"
        folder = self.output_dir / f"cores_{product['shopId']}_{product['itemId']}"
        try:
            thumbs = capture_color_thumbs(url, folder)
        except Exception as e:
            logger.warning(f"Captura das cores falhou: {e}")
            return None
        if len(thumbs) < 2:
            return None
        return self.cover.colors_card([str(t) for t in thumbs], str(folder / 'cartao.png'))

    def make_cover(self, video_path: str, headline: str, sticker_path: Optional[str] = None) -> str:
        n = len(list(Path(video_path).parent.glob(f"{Path(video_path).stem}.capa*.jpg")))
        out = str(Path(video_path).with_suffix(f'.capa{n or ""}.jpg'))
        if not self.cover.generate(video_path, headline, out, sticker_path):
            raise PipelineError("Falha ao gerar a capa.")
        return out

    def new_headline(self, post: Dict, avoid: List[str]) -> str:
        return self.content.new_headline(product_info(post['products'][0]), avoid)
