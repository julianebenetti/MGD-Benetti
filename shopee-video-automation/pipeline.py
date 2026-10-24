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
        self.is_sold_out = lambda key: False   # o robô liga no banco (anúncios marcados como esgotados)

    def _check_all(self, video_path: str, candidates: List[Dict], strict: bool = False) -> List[Tuple[Dict, str, str]]:
        """Conferência de vários produtos ao mesmo tempo (cada uma é uma chamada à IA), na ordem recebida."""
        results = list(self.workers.map(lambda p: check_match(video_path, p, strict), candidates))
        return [(p, r, m) for p, (r, m) in zip(candidates, results)]

    def _confirmed(self, video_path: str, candidates: List[Dict], wanted: int, max_checks: int = 99,
                   accept_variation: bool = False, strict: bool = False) -> Tuple[List[Dict], List[str], List[str]]:
        """Produtos confirmados, motivos das recusas e motivos de 'outra variação' (quando não aceita)."""
        found, reasons, variations = [], [], []
        for product, resultado, motivo in self._check_all(video_path, candidates[:max_checks], strict):
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
            # já na chegada, a conferência detalhada: vídeo de IA que mudou um detalhe aparece aqui, antes de capa e textos
            main_found, reasons, variations = self._confirmed(video_file, candidates[:3], wanted=1, strict=True)
        if not main_found and variations:
            raise VariationMismatch("O produto do vídeo é o mesmo do link, mas em OUTRA VARIAÇÃO:\n"
                                    + "\n".join(variations) + "\n\n⚠️ A Shopee costuma punir como \"produto irrelevante\" "
                                    "quando o vídeo mostra outra variação da foto do anúncio. O melhor é responder esta "
                                    "mensagem com o link de um anúncio cuja foto seja igual ao vídeo. Toque ✅ Pode seguir para usar este link "
                                    "assim mesmo, ou responda esta mensagem com o link da variação certa.")
        if not main_found:
            raise PipelineError("O produto do vídeo não está idêntico ao anúncio:\n"
                                + "\n".join(reasons) + "\n\nA Shopee pune isso como \"produto irrelevante\". Se o vídeo "
                                "foi gerado por IA, gere de novo mantendo o produto igual à foto do anúncio (mesmos "
                                "detalhes) e mande de novo. Se o anúncio certo é outro, responda esta mensagem com o link.")
        main = main_found[0]
        main['commissionValue'] = commission_value(main)
        key = product_key(main)

        writing = self.workers.submit(self.content.generate, product_info(main), used_headlines(key))
        candidates = [p for p in self.shopee.other_sellers(main) if not self.is_sold_out(product_key(p))]
        others, _, _ = self._confirmed(video_file, candidates, wanted=MAX_BETTER + TOTAL_LINKS,
                                       max_checks=MAX_EXTRA_CHECKS)
        # outras lojas confirmadas, da maior para a menor comissão
        better = [p for p in others if p['commissionValue'] > main['commissionValue']][:MAX_BETTER]
        products = [main] + others[:TOTAL_LINKS - 1]
        logger.info(f"{len(products)} link(s) para {main['productName']}; {len(better)} opção(ões) com comissão maior")

        metadata = writing.result()
        metadata['cta'] = cta_text
        metadata['reservas'] = others   # lojas já conferidas, para repor um link esgotado
        metadata['principal_confirmado'] = trust_link   # você confirmou o produto (outra variação, link reenviado)
        sub_id = novo_sub_id(metadata['short_name'], reservar=False)   # provisório: o definitivo sai ao agendar
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

    def replace_sold_out(self, post: Dict, index: int, sold_out) -> Dict:
        """
        Tira o link `index` (0 = divulgado: a próxima loja vira a divulgada) e repõe com a loja conferida de
        maior comissão que ainda não está nos links nem esgotada. Devolve os campos a atualizar no post.
        """
        products = [p for i, p in enumerate(post['products']) if i != index]
        links = [l for i, l in enumerate(post['links']) if i != index]
        used = {str(p['shopId']) for p in post['products']}
        reserves = sorted(post['metadata'].get('reservas') or post.get('melhores') or [],
                          key=commission_value, reverse=True)
        extra = next((p for p in reserves if str(p['shopId']) not in used and not sold_out(product_key(p))), None)
        if extra:
            products.append(extra)
            links.append(self.shopee.affiliate_link(extra, post['sub_id']))
        if not products:
            raise PipelineError("Não sobrou nenhuma loja disponível para este produto.")
        return {'products': products, 'links': links, 'product_key': product_key(products[0]),
                'product_name': products[0]['productName'], 'reposto': extra}

    def validate(self, post: Dict) -> Dict:
        """
        Validação rigorosa antes de agendar: cada produto dos links contra 6 quadros do vídeo, exigindo o mesmo
        modelo. Lojas extras que não passam saem e são repostas com reservas que passem. Devolve
        {'main': (resultado, motivo), 'products', 'links', 'removed': [(loja, resultado, motivo)], 'added': [lojas]}.
        """
        clean = Path(post['video_path']).with_name(Path(post['video_path']).name.replace('watermarked_', '', 1))
        video = str(clean) if clean.exists() else post['video_path']
        checks = self._check_all(video, post['products'], strict=True)
        main_result = checks[0][1:]
        products, links, removed = [post['products'][0]], [post['links'][0]], []
        warnings = []
        for (product, result, reason), link in zip(checks[1:], post['links'][1:]):
            if result == 'sim' or product.get('escolhido'):   # link que você escolheu: fica, só avisa
                products.append(product)
                links.append(link)
                if result != 'sim':
                    warnings.append((product.get('shopName', ''), result, reason))
            else:
                removed.append((product.get('shopName', ''), result, reason))
        added = []
        used = {str(p['shopId']) for p in post['products']}
        reserves = [p for p in sorted(post['metadata'].get('reservas') or [], key=commission_value, reverse=True)
                    if str(p['shopId']) not in used and not self.is_sold_out(product_key(p))]
        missing = TOTAL_LINKS - len(products)
        if missing > 0 and reserves:
            for product, result, _ in self._check_all(video, reserves[:missing + 3], strict=True):
                if result == 'sim' and len(products) < TOTAL_LINKS:
                    products.append(product)
                    links.append(self.shopee.affiliate_link(product, post['sub_id']))
                    added.append(product.get('shopName', ''))
        return {'main': main_result, 'products': products, 'links': links, 'removed': removed, 'added': added,
                'warnings': warnings}

    def find_identical(self, post: Dict) -> Optional[Dict]:
        """
        Outro anúncio do mesmo produto cuja foto mostra EXATAMENTE o que aparece no vídeo (mesma variação), para
        substituir um divulgado que só bate como "outra variação". Procura nas reservas e em outras lojas.
        """
        clean = Path(post['video_path']).with_name(Path(post['video_path']).name.replace('watermarked_', '', 1))
        video = str(clean) if clean.exists() else post['video_path']
        used = {product_key(p) for p in post['products'][:1]}
        pool = {product_key(p): p for p in (post['metadata'].get('reservas') or []) + post['products'][1:]}
        try:
            for p in self.shopee.other_sellers(post['products'][0]):
                pool.setdefault(product_key(p), p)
        except Exception as e:
            logger.warning(f"Busca de anúncio idêntico falhou: {e}")
        candidates = [p for k, p in pool.items() if k not in used and not self.is_sold_out(k)]
        candidates.sort(key=lambda p: (int(p.get('sales') or 0) >= 100, commission_value(p)), reverse=True)
        for product, result, _ in self._check_all(video, candidates[:MAX_EXTRA_CHECKS], strict=True):
            if result == 'sim':
                return product
        return None

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
