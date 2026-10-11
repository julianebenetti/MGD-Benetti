"""
Content Generator
Gera headline, descrição, hashtags e SEO com a OpenAI
"""

import logging
from typing import Dict, List

from ai_client import ask_json

logger = logging.getLogger(__name__)

SCHEMA = {
    'type': 'object',
    'properties': {
        'cover_title': {'type': 'string'},
        'description': {'type': 'string'},
        'hashtags': {'type': 'array', 'items': {'type': 'string'}},
        'seo_keywords': {'type': 'array', 'items': {'type': 'string'}},
        'short_name': {'type': 'string'},
    },
    'required': ['cover_title', 'description', 'hashtags', 'seo_keywords', 'short_name'],
    'additionalProperties': False,
}


# Rodízio de gatilhos (mesmo método do Central Post): cada headline nova do produto usa o próximo
GATILHOS = [
    ('Choque', 'surpresa ou descrença com o que o produto faz ("não acreditei que isso existia")'),
    ('Urgência', 'motivo para agir agora sem inventar prazo ou estoque ("antes de comprar outro, olha esse")'),
    ('Curiosidade', 'abre uma lacuna que só o vídeo responde ("o detalhe que ninguém repara")'),
    ('Dor', 'nomeia um incômodo do dia a dia que o produto resolve ("cansada do hall bagunçado?")'),
    ('Autoridade', 'prova social com dados reais de vendas/nota, se houver ("o queridinho de quem organiza a casa")'),
]


class ContentGenerator:
    def generate(self, product_info: Dict, avoid_headlines: List[str] = ()) -> Dict:
        """Headline da capa, descrição, 5 hashtags, 10 palavras de SEO e nome curto (para o sub_id)."""
        try:
            logger.info(f"Gerando conteúdo para: {product_info.get('name', 'Produto')}")
            data = ask_json(self._build_prompt(product_info, avoid_headlines), SCHEMA, name='conteudo')
            result = {
                'cover_title': data['cover_title'][:60],
                'description': data['description'][:150],
                'hashtags': [h if h.startswith('#') else f'#{h}' for h in data['hashtags']][:5],
                'seo_keywords': data['seo_keywords'][:10],
                'short_name': data['short_name'],
            }
            logger.info("✅ Conteúdo gerado com sucesso")
            return result
        except Exception as e:
            logger.error(f"Erro ao gerar conteúdo: {e}")
            return self._default_content(product_info)

    def new_headline(self, product_info: Dict, avoid_headlines: List[str]) -> str:
        """Só uma headline nova para a capa, com o próximo gatilho e diferente das já usadas."""
        data = ask_json(
            self._build_prompt(product_info, avoid_headlines)
            + "\nNesta resposta só o campo cover_title importa; preencha os outros com o mínimo.",
            SCHEMA, name='conteudo')
        return data['cover_title'][:60]

    def _build_prompt(self, product_info: Dict, avoid_headlines: List[str] = ()) -> str:
        gatilho, explicacao = GATILHOS[len(avoid_headlines) % len(GATILHOS)]
        usadas = ''
        if avoid_headlines:
            lista = '\n'.join(f'- {h}' for h in avoid_headlines)
            usadas = f"\nHeadlines já usadas para este produto (não repita nem parafraseie):\n{lista}\n"

        return f"""Você cria o conteúdo dos vídeos do perfil Achados Relâmpagos no Shopee Video, no método MGD.

PRODUTO
- Nome: {product_info.get('name', 'Produto')}
- Nota: {product_info.get('rating') or 'não informada'}
- Vendas: {product_info.get('sold') or 'não informado'}
- Descrição da Shopee: {(product_info.get('description') or 'não informada')[:600]}

CAMPOS
- cover_title: headline escrita na capa do vídeo. Até 60 caracteres, tom de conversa, vende a TRANSFORMAÇÃO
  (o que muda na vida de quem usa), não a característica técnica. Pode começar com 1 emoji e termina com 😱🔥.
  Gatilho obrigatório desta vez: {gatilho}: {explicacao}.
  Exemplos do perfil: "Se você usa plus size, olha esse achado! 😱🔥", "E se sua academia pudesse ficar dentro de casa? 😱🔥",
  "A escova que faz o trabalho pesado por você 😱🔥".
{usadas}- description: legenda do vídeo, até 150 caracteres, no tom de uma amiga recomendando (sem começar com "Amiga"),
  com o benefício principal e um convite para ver o produto.
- hashtags: exatamente 5, específicas do produto e da categoria; evite genéricas como #shopee #achadinhos.
- seo_keywords: 10 palavras-chave que uma pessoa digitaria para buscar este produto, da mais para a menos relevante.
- short_name: nome curto do produto para identificação interna, 1 a 2 palavras, sem acento, sem espaço,
  cada palavra com inicial maiúscula (ex: "SapateiraBanco", "ConjuntoLinho").

REGRAS
- Nenhuma palavra pode se repetir entre description, hashtags e seo_keywords, nem dentro de cada um.
- Use apenas o que está nos dados do produto: não invente características, benefícios, avaliações ou vendas.
- Não cite preço, desconto, cupom nem frete grátis (podem mudar até a publicação).
- Não crie falsa escassez ("últimas unidades", "só hoje", "corre que acaba").
- Não afirme que é o melhor, o mais barato ou o mais vendido; nunca mencione comissão.
"""

    def _default_content(self, product_info: Dict) -> Dict:
        """Conteúdo padrão caso a IA falhe"""
        product_name = product_info.get('name', 'Produto')
        return {
            'cover_title': 'Olha esse achado! 😱🔥',
            'description': f'{product_name} 👀 Confira os detalhes no link do produto.'[:150],
            'hashtags': ['#Shopee', '#ShopeeVideo', '#Achadinhos', '#AchadosShopee', '#AchadosRelampagos'],
            'seo_keywords': list(dict.fromkeys(
                [w for w in product_name.lower().split() if len(w) > 2]
                + ['shopee', 'achadinhos', 'achados', 'video', 'dicas', 'compras', 'novidade']
            ))[:10],
            'short_name': ''.join(w.capitalize() for w in product_name.split()[:2]) or 'Produto',
        }

    def validate_content(self, content: Dict) -> bool:
        """Valida se o conteúdo atende aos requisitos"""
        try:
            # Verificar descrição
            if not content.get('description') or len(content['description']) > 150:
                logger.warning("Descrição inválida")
                return False

            # Verificar hashtags
            hashtags = content.get('hashtags', [])
            if len(hashtags) != 5 or not all(h.startswith('#') for h in hashtags):
                logger.warning("Hashtags inválidas")
                return False

            # Verificar keywords (10 únicos)
            keywords = content.get('seo_keywords', [])
            if len(keywords) != 10 or len(set(keywords)) != 10:
                logger.warning("Keywords inválidas ou repetidas")
                return False

            # Verificar se há repetição entre campos
            all_words = set()
            desc_words = content['description'].lower().split()
            hashtag_words = [h.lower().replace('#', '') for h in hashtags]
            keyword_words = keywords

            all_words.update(desc_words + hashtag_words + keyword_words)

            if len(all_words) < len(desc_words) + len(hashtag_words) + len(keyword_words):
                logger.warning("Há palavras repetidas entre description, hashtags e keywords")
                return False

            logger.info("✅ Conteúdo validado com sucesso")
            return True

        except Exception as e:
            logger.error(f"Erro ao validar conteúdo: {e}")
            return False
