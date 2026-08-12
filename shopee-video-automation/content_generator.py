"""
Content Generator
Gera descrição, hashtags e SEO usando Claude AI
"""

import logging
import json
import os
from typing import Dict
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self):
        self.client = Anthropic()
        self.model = "claude-3-5-sonnet-20241022"

    def generate(self, product_info: Dict) -> Dict:
        """
        Gera conteúdo completo para o vídeo:
        - Descrição otimizada
        - 5 hashtags relevantes
        - 10 palavras-chave SEO (sem repetição)
        """
        try:
            logger.info(f"Gerando conteúdo para: {product_info.get('name', 'Produto')}")

            # Preparar prompt com informações do produto
            prompt = self._build_prompt(product_info)

            # Chamar Claude para gerar conteúdo
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extrair e parsear resposta
            content = response.content[0].text

            # Extrair JSON da resposta
            result = self._parse_response(content)

            logger.info("✅ Conteúdo gerado com sucesso")
            return result

        except Exception as e:
            logger.error(f"Erro ao gerar conteúdo: {e}")
            return self._default_content(product_info)

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

TAREFA:
Gere um JSON com exatamente este formato (responda APENAS com JSON válido):

{{
  "description": "Uma descrição atrativa e engajante para o vídeo Shopee Video (máx 150 caracteres). Deve mencionar benefício principal, ser persuasiva e convidar à ação.",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3", "#hashtag4", "#hashtag5"],
  "seo_keywords": ["palavra1", "palavra2", "palavra3", "palavra4", "palavra5", "palavra6", "palavra7", "palavra8", "palavra9", "palavra10"]
}}

REGRAS:
- Description: máximo 150 caracteres, urgente e envolvente
- Hashtags: 5 hashtags relevantes ao produto/categoria (começando com #)
- SEO Keywords: 10 palavras-chave diferentes (sem repetir nenhuma palavra), separadas por vírgula, ordenadas por relevância
- Nenhuma palavra pode se repetir entre description, hashtags e keywords
- Sempre retorna JSON válido

Responda APENAS com o JSON, sem explicações adicionais.
"""
        return prompt

    def _parse_response(self, response_text: str) -> Dict:
        """Parseia a resposta JSON do Claude"""
        try:
            # Tentar extrair JSON da resposta
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                # Validar campos
                if 'description' in data and 'hashtags' in data and 'seo_keywords' in data:
                    return {
                        'description': data['description'][:150],
                        'hashtags': data['hashtags'][:5],
                        'seo_keywords': data['seo_keywords'][:10]
                    }

            logger.warning("Resposta JSON inválida, usando conteúdo padrão")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse JSON: {e}")
            return None

    def _default_content(self, product_info: Dict) -> Dict:
        """Conteúdo padrão caso a IA falhe"""
        product_name = product_info.get('name', 'Produto')
        category = product_info.get('category', 'Categoria')

        return {
            'description': f'🎯 Confira este {category}! Qualidade garantida. Link na bio! 👆',
            'hashtags': [
                f'#{category.replace(" ", "")}',
                '#Shopee',
                '#Oferta',
                '#Promoção',
                '#Compre'
            ],
            'seo_keywords': [
                product_name.split()[0] if product_name else 'produto',
                category,
                'shopee',
                'oferta',
                'comprar',
                'promoção',
                'melhor preço',
                'qualidade',
                'entrega rápida',
                'confiável'
            ]
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
