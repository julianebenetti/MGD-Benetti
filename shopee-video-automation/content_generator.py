"""
Content Generator
Gera descrição, hashtags e SEO usando Claude AI
"""

import logging
from typing import Dict, List

from claude_client import ask_json

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


class ContentGenerator:
    def generate(self, product_info: Dict, avoid_headlines: List[str] = ()) -> Dict:
        """Headline da capa, descrição, 5 hashtags, 10 palavras de SEO e nome curto (para o sub_id)."""
        try:
            logger.info(f"Gerando conteúdo para: {product_info.get('name', 'Produto')}")
            data = ask_json(self._build_prompt(product_info) + self._avoid_block(avoid_headlines), SCHEMA)
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
        """Só uma headline nova para a capa, diferente das já usadas para o produto."""
        data = ask_json(
            self._build_prompt(product_info) + self._avoid_block(avoid_headlines)
            + "\nNesta resposta só o campo cover_title importa; preencha os outros com o mínimo.",
            SCHEMA)
        return data['cover_title'][:60]

    @staticmethod
    def _avoid_block(headlines: List[str]) -> str:
        if not headlines:
            return ''
        lista = '\n'.join(f'- {h}' for h in headlines)
        return ("\n\nHEADLINES JÁ USADAS PARA ESTE PRODUTO (crie uma de ângulo diferente, "
                f"sem repetir nem parafrasear estas):\n{lista}\n")

    def _build_prompt(self, product_info: Dict) -> str:
        """Constrói o prompt para Claude gerar conteúdo"""
        product_name = product_info.get('name', 'Produto')
        price = product_info.get('price', 0)
        description = product_info.get('description', '')
        category = product_info.get('category', '')
        brand = product_info.get('brand', '')
        rating = product_info.get('rating', 0)
        sold = product_info.get('sold', 0)

        prompt = f"""
Você é um especialista em marketing de afiliados Shopee. Preciso de você gerar conteúdo otimizado para um vídeo de produto.

INFORMAÇÕES DO PRODUTO:
- Nome: {product_name}
- Preço: R$ {price}
- Categoria: {category}
- Marca: {brand}
- Rating: {rating}/5
- Vendas: {sold} unidades
- Descrição: {description[:300]}

CAMPOS:
- cover_title: gancho curto para a capa, em tom de conversa, que gere curiosidade. Pode começar com 1 emoji e deve terminar com 😱🔥. Ex: "Se você usa plus size, olha esse achado! 😱🔥"
- description: descrição atrativa para o Shopee Video, mencionando o benefício principal e convidando à ação
- hashtags: 5 hashtags começando com #
- seo_keywords: 10 palavras-chave
- short_name: nome curto do produto para identificação interna, 1 a 2 palavras, sem acento, sem espaço, cada palavra com inicial maiúscula (ex: "SapateiraBanco", "ConjuntoLinho")

REGRAS:
- Cover title: máximo 60 caracteres, não cite preço nem marca
- Description: máximo 150 caracteres, envolvente e com convite à ação
- Hashtags: 5 hashtags relevantes ao produto/categoria (começando com #)
- SEO Keywords: 10 palavras-chave diferentes (sem repetir nenhuma palavra), separadas por vírgula, ordenadas por relevância
- Nenhuma palavra pode se repetir entre description, hashtags e keywords

COMPLIANCE (obrigatório em todos os campos):
- Use apenas informações presentes nos dados do produto acima; não invente características nem benefícios
- Não invente avaliações, vendas, descontos ou cupons
- Não crie falsa escassez ou urgência ("últimas unidades", "só hoje", "corre que acaba")
- Não afirme que é o melhor, o mais barato ou o mais vendido
- Não cite preço (pode mudar até a publicação)
- Vendas e avaliação só como dado informativo, sem exagero
- Nunca mencione comissão nem a apresente como vantagem para quem compra
"""
        return prompt

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
