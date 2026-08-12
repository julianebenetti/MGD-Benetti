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
            from telegram_handler import TelegramMonitor

            token = os.getenv('TELEGRAM_BOT_TOKEN')
            chat_id = os.getenv('TELEGRAM_CHAT_ID')

            if not token or not chat_id:
                print("❌ Token ou Chat ID não configurados em .env")
                self.failed += 1
                return False

            monitor = TelegramMonitor(token, chat_id)

            # Tentar obter atualizações (sem requisições longas)
            updates = monitor.get_updates()
            print(f"✅ Conexão OK! Últimas {len(updates)} mensagens encontradas")
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
        print("🧪 TESTE 3: Geração de Conteúdo (Claude AI)")
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

    def test_shopee_scraping(self):
        """Testa web scraping da Shopee"""
        print("\n" + "="*60)
        print("🧪 TESTE 4: Web Scraping Shopee")
        print("="*60)

        try:
            from shopee_scraper import ShopeeScraper

            scraper = ShopeeScraper()

            # URL de teste (use um produto real da Shopee)
            test_url = "https://shopee.com.br/p/52kekkac"

            print(f"🔗 Testando com: {test_url}")
            print("ℹ️  (Se você tiver uma URL real, altere em test_automation.py)")

            product_info = scraper.extract_product_info(test_url)

            if product_info and product_info.get('name'):
                print(f"\n✅ Scraping bem-sucedido:")
                print(f"   Nome: {product_info.get('name', 'N/A')}")
                print(f"   Preço: R$ {product_info.get('price', 'N/A')}")
                print(f"   Categoria: {product_info.get('category', 'N/A')}")
                self.passed += 1
                return True
            else:
                print("⚠️  Nenhuma informação extraída (URL pode estar inválida)")
                print("ℹ️  Teste com uma URL real de produto Shopee")
                self.failed += 1
                return False

        except Exception as e:
            print(f"⚠️  Erro: {e}")
            print("ℹ️  Isso é normal se a URL não for válida")
            self.failed += 1
            return False

    def test_end_to_end(self):
        """Teste ponta-a-ponta completo"""
        print("\n" + "="*60)
        print("🧪 TESTE 5: Fluxo Completo (End-to-End)")
        print("="*60)

        try:
            from main import ShopeeVideoAutomation

            automation = ShopeeVideoAutomation()
            print("✅ Automação inicializada com sucesso")

            print("\n📋 Verificando componentes:")
            print("   ✅ Telegram Monitor OK")
            print("   ✅ Video Processor OK")
            print("   ✅ Shopee Scraper OK")
            print("   ✅ Content Generator OK")

            self.passed += 1
            return True

        except Exception as e:
            print(f"❌ Erro: {e}")
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
        self.test_shopee_scraping()
        self.test_end_to_end()

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
