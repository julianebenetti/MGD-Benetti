"""
Preparação de um vídeo: produto confirmado + links extras + textos + vídeo com logo + capa.
"""

import logging
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from content_generator import ContentGenerator
from cover_generator import CoverGenerator
from product_matcher import check_match
from product_page_capture import capture_variation_thumbs
from variations_print import thumbs_from_print
from shopee_affiliate import ShopeeAffiliateClient
from sub_id import novo_sub_id
from video_processor import VideoProcessor

logger = logging.getLogger(__name__)

TOTAL_LINKS = int(os.getenv('LINKS_POR_VIDEO', '3'))
CTA_SECONDS = float(os.getenv('CTA_SEGUNDOS', '5'))
CTAS = [
    'Adicione já ao carrinho! 🛒',
    'Compre agora e aproveite o desconto! 🛒',
    'Clique na sacolinha e garanta o seu! 🛒',
    'Leva esse achadinho pra casa! 🛒',
    'Já coloca no carrinho e garante o seu! 🛒',
    'Aproveita o preço especial! 🛒',
    'Compre com o cupom! 🛒',
]
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
        self.variations_blocked = False

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

        metadata['cta'] = random.choice(CTAS)
        cta = self.cover.cta_overlay(metadata['cta'], str(Path(processed).with_suffix('.cta.png')))
        final_video = self.video.add_watermark(processed, cta_path=cta, cta_seconds=CTA_SECONDS)
        if not final_video:
            raise PipelineError("Falha ao aplicar o logo no vídeo.")
        from shopee_session import PAGES_ENABLED
        sticker = self.variations_print(main) if PAGES_ENABLED else None  # senão, vem do print enviado
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
        """Cartão "N Variações Disponíveis" com as miniaturas (None se o produto não tiver variações)."""
        url = f"https://shopee.com.br/product/{product['shopId']}/{product['itemId']}"
        folder = self.output_dir / f"variacoes_{product['shopId']}_{product['itemId']}"
        self.variations_blocked = False
        try:
            thumbs, total = capture_variation_thumbs(url, folder)
        except Exception as e:
            logger.warning(f"Captura das variações falhou: {e.__class__.__name__}: {e}")
            self.variations_blocked = e.__class__.__name__ == 'ShopeeBlocked'
            return None
        if len(thumbs) < 2:
            return None
        return self.cover.colors_card([str(t) for t in thumbs], str(folder / 'cartao.png'),
                                      label=f"{total} Variações Disponíveis")

    def variations_card_from_print(self, image_path: str, out_dir: Path) -> Optional[str]:
        """Cartão a partir do print das variações que a Juliane manda (a IA recorta as miniaturas)."""
        thumbs, total = thumbs_from_print(image_path, out_dir)
        if len(thumbs) < 2:
            return None
        return self.cover.colors_card([str(t) for t in thumbs], str(out_dir / 'cartao.png'),
                                      label=f"{total} Variações Disponíveis")

    def make_cover(self, video_path: str, headline: str, sticker_path: Optional[str] = None) -> str:
        n = len(list(Path(video_path).parent.glob(f"{Path(video_path).stem}.capa*.jpg")))
        out = str(Path(video_path).with_suffix(f'.capa{n or ""}.jpg'))
        # o quadro da capa vem do vídeo sem logo; a capa põe o logo na área visível da grade
        clean = Path(video_path).with_name(Path(video_path).name.replace('watermarked_', '', 1))
        source = str(clean) if clean.exists() else video_path
        if not self.cover.generate(source, headline, out, sticker_path):
            raise PipelineError("Falha ao gerar a capa.")
        return out

    def new_headline(self, post: Dict, avoid: List[str]) -> str:
        return self.content.new_headline(product_info(post['products'][0]), avoid)
