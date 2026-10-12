"""
Preparação de um vídeo: produto confirmado + links extras + textos + vídeo com logo + capa.
"""

import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from content_generator import ContentGenerator
from cover_generator import CoverGenerator
from product_matcher import check_match
from product_page_capture import capture_variation_thumbs
from variations_print import thumbs_from_print
from shopee_affiliate import ShopeeAffiliateClient, commission_value
from sub_id import novo_sub_id
from video_processor import VideoProcessor

logger = logging.getLogger(__name__)

TOTAL_LINKS = int(os.getenv('LINKS_POR_VIDEO', '5'))
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
MAX_EXTRA_CHECKS = 10   # outras lojas conferidas pela IA (em paralelo)
MAX_BETTER = 5          # opções de comissão maior oferecidas para troca


class PipelineError(Exception):
    """Erro com mensagem para mostrar no Telegram."""


class VariationMismatch(PipelineError):
    """Mesmo produto do link, mas o vídeo mostra outra variação: pede o ok da Juliane ou outro link."""


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
        self.workers = ThreadPoolExecutor(max_workers=6)

    def _check_all(self, video_path: str, candidates: List[Dict]) -> List[Tuple[Dict, str, str]]:
        """Conferência de vários produtos ao mesmo tempo (cada uma é uma chamada à IA), na ordem recebida."""
        results = list(self.workers.map(lambda p: check_match(video_path, p), candidates))
        return [(p, r, m) for p, (r, m) in zip(candidates, results)]

    def _confirmed(self, video_path: str, candidates: List[Dict], wanted: int,
                   max_checks: int = 99, accept_variation: bool = False) -> Tuple[List[Dict], List[str], List[str]]:
        """Produtos confirmados, motivos das recusas e motivos de 'outra variação' (quando não aceita)."""
        found, reasons, variations = [], [], []
        for product, resultado, motivo in self._check_all(video_path, candidates[:max_checks]):
            if len(found) >= wanted:
                break
            if resultado == 'sim' or (accept_variation and resultado == 'variacao'):
                found.append(product)
            elif resultado == 'variacao':
                variations.append(f"• {product['productName']}: {motivo}")
            else:
                reasons.append(f"• {product['productName']}: {resultado} ({motivo})")
        return found, reasons, variations

    def prepare(self, video_file: str, link: str, text: str, used_headlines, trust_link: bool = False) -> Dict:
        """
        `used_headlines(product_key) -> list` evita repetir headline do mesmo produto.
        `trust_link`: link reenviado pela Juliane depois de uma recusa, vale sem a conferência da IA.
        Levanta PipelineError com a explicação quando não dá para seguir.

        Para ganhar tempo, o vídeo é codificado enquanto a IA confere os produtos e escreve os textos.
        """
        candidates = self.shopee.find_candidates(link, text)
        if not candidates:
            raise PipelineError("Não consegui identificar o produto deste vídeo "
                                f"(o link abriu em: {self.shopee.last_final_url[:150]}). "
                                "Mande o link do PRODUTO respondendo esta mensagem que eu refaço.")

        cta_text = random.choice(CTAS)
        cta_png = self.cover.cta_overlay(cta_text, str(self.output_dir / f"{Path(video_file).stem}.cta.png"))
        rendering = self.workers.submit(self.video.render, video_file, self.output_dir, cta_png, CTA_SECONDS)

        if trust_link:
            main_found, reasons, variations = candidates[:1], [], []
        else:
            main_found, reasons, variations = self._confirmed(video_file, candidates[:3], wanted=1)
        if not main_found and variations:
            raise VariationMismatch("O produto do vídeo é o mesmo do link, mas em OUTRA VARIAÇÃO:\n"
                                    + "\n".join(variations) + "\n\nToque ✅ Pode seguir para usar este link "
                                    "assim mesmo, ou responda esta mensagem com o link da variação certa.")
        if not main_found:
            raise PipelineError("A conferência não confirmou que o produto é o do vídeo:\n"
                                + "\n".join(reasons) + "\n\nSe o produto é esse mesmo (ex.: outra cor), responda esta "
                                "mensagem com o link que eu sigo sem conferir. Se não, mande o link do produto certo.")
        main = main_found[0]
        main['commissionValue'] = commission_value(main)
        key = product_key(main)

        writing = self.workers.submit(self.content.generate, product_info(main), used_headlines(key))
        others, _, _ = self._confirmed(video_file, self.shopee.other_sellers(main), wanted=MAX_BETTER + TOTAL_LINKS,
                                       max_checks=MAX_EXTRA_CHECKS, accept_variation=True)
        # outras lojas confirmadas, da maior para a menor comissão
        better = [p for p in others if p['commissionValue'] > main['commissionValue']][:MAX_BETTER]
        products = [main] + others[:TOTAL_LINKS - 1]
        logger.info(f"{len(products)} link(s) para {main['productName']}; {len(better)} opção(ões) com comissão maior")

        metadata = writing.result()
        metadata['cta'] = cta_text
        sub_id = novo_sub_id(metadata['short_name'])
        links = [self.shopee.affiliate_link(p, sub_id) for p in products]

        rendered = rendering.result()
        if not rendered:
            raise PipelineError("Não consegui processar este vídeo.")
        final_video = rendered[1]
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
            'melhores': better,
            'troca': 'pendente' if better else 'sem',
        }

    def switch_to(self, post: Dict, index: int) -> Dict:
        """
        A loja escolhida (posição em `melhores`) vira o item divulgado (1º link); os outros links são as
        maiores comissões entre as lojas já conferidas (o produto do link original entra se couber).
        """
        best = post['melhores'][index]
        known = dict(zip(map(product_key, post['products']), post['links']))
        pool = {}  # uma vez cada loja, sem a loja escolhida
        for p in sorted(post['products'] + post['melhores'], key=commission_value, reverse=True):
            if str(p['shopId']) != str(best['shopId']):
                pool.setdefault(str(p['shopId']), p)
        for p in pool.values():
            p.setdefault('commissionValue', commission_value(p))
        rest = sorted(pool.values(), key=lambda p: p['commissionValue'], reverse=True)[:TOTAL_LINKS - 1]
        products = [best] + rest
        links = [known.get(product_key(p)) or self.shopee.affiliate_link(p, post['sub_id']) for p in products]
        return {'products': products, 'links': links, 'product_key': product_key(best),
                'product_name': best['productName']}

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

    def new_caption(self, post: Dict, avoid: List[str]) -> Dict:
        return self.content.new_caption(product_info(post['products'][0]), avoid)

    def new_headline(self, post: Dict, avoid: List[str]) -> str:
        return self.content.new_headline(product_info(post['products'][0]), avoid)
