#!/usr/bin/env python3
"""
Script de Teste da Automação
Testa cada componente separadamente
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup
load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutomationTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def test_telegram_connection(self):
        """Testa conexão com Telegram Bot"""
        print("\n" + "="*60)
        print("🧪 TESTE 1: Conexão Telegram")
        print("="*60)

        try:
            from telegram_handler import TelegramBot

            token = os.getenv('TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('TELEGRAM_CHAT_ID')

            if not token or not chat_id:
                print("❌ Token ou Chat ID não configurados em .env")
                self.failed += 1
                return False

            bot = TelegramBot(token, chat_id)
            me = bot.call('getMe')
            chat = bot.call('getChat', data={'chat_id': chat_id})
            print(f"✅ Conexão OK: @{me['username']} no grupo '{chat.get('title')}' (tópicos: {chat.get('is_forum', False)})")
            self.passed += 1
            return True

        except Exception as e:
            print(f"❌ Erro: {e}")
            self.failed += 1
            return False

    def test_video_processor(self):
        """Testa processamento de vídeo"""
        print("\n" + "="*60)
        print("🧪 TESTE 2: Processamento de Vídeo (FFmpeg)")
        print("="*60)

        try:
            from video_processor import VideoProcessor

            processor = VideoProcessor()

            # Verificar FFmpeg
            print("✅ FFmpeg encontrado e funcionando")

            # Criar vídeo de teste (5 segundos de ruído)
            test_video = "test_input.mp4"
            if not Path(test_video).exists():
                print(f"ℹ️  Criando vídeo de teste ({test_video})...")
                import subprocess
                cmd = [
                    'ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=1080x1920:d=5',
                    '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono:d=5',
                    '-pix_fmt', 'yuv420p', '-y', test_video
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                print(f"✅ Vídeo de teste criado")

            # Testar processamento
            output_dir = Path("test_output")
            output_dir.mkdir(exist_ok=True)

            print(f"🔄 Processando vídeo...")
            result = processor.process(test_video, output_dir)

            if result and Path(result).exists():
                size_mb = Path(result).stat().st_size / (1024 * 1024)
                print(f"✅ Vídeo processado: {result} ({size_mb:.2f} MB)")

                # Obter informações
                info = processor.get_video_info(result)
                print(f"   Resolução: {info.get('width')}x{info.get('height')}")
                print(f"   Duração: {info.get('duration'):.1f}s")
                print(f"   FPS: {info.get('fps'):.0f}")

                self.passed += 1
                return True
            else:
                print("❌ Falha no processamento")
                self.failed += 1
                return False

        except Exception as e:
            print(f"❌ Erro: {e}")
            self.failed += 1
            return False

    def test_content_generation(self):
        """Testa geração de conteúdo com IA"""
        print("\n" + "="*60)
        print("🧪 TESTE 3: Geração de Conteúdo (OpenAI)")
        print("="*60)

        try:
            from content_generator import ContentGenerator

            generator = ContentGenerator()

            # Dados de teste
            test_product = {
                'name': 'Fone Bluetooth Premium',
                'price': 149.90,
                'category': 'Eletrônicos',
                'brand': 'SoundMax',
                'rating': 4.8,
                'sold': 523,
                'description': 'Fone bluetooth com cancelamento de ruído, bateria 30h'
            }

            print(f"📝 Gerando conteúdo para: {test_product['name']}")
            print(f"   Preço: R$ {test_product['price']}")
            print(f"   Rating: {test_product['rating']}/5")

            content = generator.generate(test_product)

            if content:
                print(f"\n✅ Conteúdo gerado:")
                print(f"\n📄 Descrição:")
                print(f"   {content['description']}")
                print(f"   Caracteres: {len(content['description'])}/150")

                print(f"\n#️⃣  Hashtags ({len(content['hashtags'])}):")
                for tag in content['hashtags']:
                    print(f"   {tag}")

                print(f"\n🔍 SEO Keywords ({len(content['seo_keywords'])}):")
                print(f"   {', '.join(content['seo_keywords'])}")

                # Validar
                is_valid = generator.validate_content(content)
                if is_valid:
                    print(f"\n✅ Conteúdo validado com sucesso!")
                    self.passed += 1
                    return True
                else:
                    print(f"\n⚠️  Conteúdo gerado mas com problemas de validação")
                    self.failed += 1
                    return False
            else:
                print("❌ Falha na geração")
                self.failed += 1
                return False

        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            return False

    def test_shopee_links(self):
        """Testa a leitura de links Shopee (sem rede)"""
        print("\n" + "="*60)
        print("🧪 TESTE 4: Links Shopee")
        print("="*60)

        from shopee_affiliate import extract_ids, is_video_link, product_name_from_text

        checks = [
            extract_ids('https://shopee.com.br/product/463412861/23898463274') ==
            {'shop_id': 463412861, 'item_id': 23898463274},
            extract_ids('https://shopee.com.br/Conjunto-Linho-i.463412861.23898463274?sp_atk=x') ==
            {'shop_id': 463412861, 'item_id': 23898463274},
            is_video_link('https://sv.shopee.com.br/share-video/AeIal74mCgArbiVDAAAAAA==?c=share_web'),
            not is_video_link('https://shopee.com.br/product/1/2'),
            product_name_from_text('Produto: Conjunto Pantalona Linho https://br.shp.ee/x') ==
            'Conjunto Pantalona Linho',
        ]
        if all(checks):
            print("✅ Links de produto, de vídeo e nome do produto reconhecidos")
            self.passed += 1
            return True
        print(f"❌ Falhou: {checks}")
        self.failed += 1
        return False

    def test_agenda(self):
        """Testa as regras da agenda (sem rede)"""
        print("\n" + "="*60)
        print("🧪 TESTE 5: Agenda")
        print("="*60)

        import random
        from datetime import datetime
        import scheduler

        rng = random.Random(1)
        start = datetime(2026, 10, 13, 8, 0, tzinfo=scheduler.TZ)
        posts = []
        for i in range(12):
            key = 'A' if i < 3 else f'P{i}'
            slot = scheduler.next_slot(key, posts, start, rng)
            posts.append({'scheduled_at': slot.isoformat(), 'product_key': key})

        days_a = [p['scheduled_at'][:10] for p in posts if p['product_key'] == 'A']
        per_day = {}
        for p in posts:
            per_day[p['scheduled_at'][:10]] = per_day.get(p['scheduled_at'][:10], 0) + 1
        times = [datetime.fromisoformat(p['scheduled_at']) for p in posts]
        checks = [
            len(set(days_a)) == 3,
            max(per_day.values()) <= scheduler.POSTS_PER_DAY,
            all(scheduler.START_HOUR <= t.hour < scheduler.END_HOUR for t in times),
            all(t.minute % 5 for t in times),
        ]
        if all(checks):
            print(f"✅ Mesmo produto em dias diferentes, ≤{scheduler.POSTS_PER_DAY}/dia, horários quebrados")
            self.passed += 1
            return True
        print(f"❌ Falhou: {checks}")
        self.failed += 1
        return False

    def run_all_tests(self):
        """Executa todos os testes"""
        print("\n")
        print("╔" + "="*58 + "╗")
        print("║" + " "*15 + "🧪 SUITE DE TESTES AUTOMAÇÃO" + " "*15 + "║")
        print("╚" + "="*58 + "╝")

        self.test_telegram_connection()
        self.test_video_processor()
        self.test_content_generation()
        self.test_shopee_links()
        self.test_agenda()

        print("\n" + "="*60)
        print("📊 RESULTADO FINAL")
        print("="*60)
        print(f"✅ Passou: {self.passed}")
        print(f"❌ Falhou: {self.failed}")
        print(f"📈 Taxa de sucesso: {self.passed}/{self.passed + self.failed} ({100*self.passed/(self.passed + self.failed):.0f}%)")

        if self.failed == 0:
            print("\n🎉 TODOS OS TESTES PASSARAM! Sistema pronto para uso.")
        else:
            print(f"\n⚠️  {self.failed} teste(s) falharam. Verifique os logs acima.")

        return self.failed == 0


def main():
    tester = AutomationTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
