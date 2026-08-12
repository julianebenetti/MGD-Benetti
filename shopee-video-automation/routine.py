#!/usr/bin/env python3
"""
Routine Setup
Configura a automação para rodar todos os dias às 14h (Brasília)
"""

import os
import sys
import logging
from datetime import datetime, time
from pathlib import Path
import json
from dotenv import load_dotenv

# Usar a ferramenta create_trigger do Claude Code
# Esta é uma wrapper que será executada como parte da Routine

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoutineConfig:
    """Configuração e setup da Routine automática"""

    ROUTINE_NAME = "Shopee Video - Postagens Automáticas"
    ROUTINE_HOUR = int(os.getenv('ROUTINE_HOUR', '14'))
    ROUTINE_TIMEZONE = os.getenv('ROUTINE_TIMEZONE', 'America/Sao_Paulo')
    ROUTINE_CRON = f"0 {ROUTINE_HOUR} * * *"  # 14h todos os dias

    @staticmethod
    def get_routine_config() -> dict:
        """Retorna configuração da Routine para create_trigger"""
        return {
            'name': RoutineConfig.ROUTINE_NAME,
            'cron_expression': RoutineConfig.ROUTINE_CRON,
            'prompt': RoutineConfig.get_prompt(),
            'description': 'Automação diária para processar e publicar vídeos Shopee'
        }

    @staticmethod
    def get_prompt() -> str:
        """Prompt que será executado pela Routine diariamente"""
        return """
🎬 Executando Automação Shopee Video Posts

**Tarefa**: Processar vídeos e links enviados ao grupo Telegram

Executar:
1. Buscar novas mensagens no grupo Telegram com vídeos + links Shopee
2. Para cada vídeo encontrado:
   - Baixar vídeo do Telegram
   - Processar com FFmpeg (9:16, 1080p, com marca d'água)
   - Extrair informações do produto Shopee
   - Gerar descrição + 5 hashtags + 10 palavras-chave SEO
   - Salvar como rascunho para validação

3. Enviar relatório por email:
   - Quantidade de vídeos processados
   - Links dos rascunhos
   - Erros (se houver)

Status esperado: "✅ Automação concluída com sucesso"
        """

    @staticmethod
    def setup() -> bool:
        """Setup da Routine (é chamado via CLI)"""
        logger.info("🚀 Configurando Routine automática...")

        # Verificar variáveis de ambiente
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID',
            'ANTHROPIC_API_KEY'
        ]

        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)

        if missing:
            logger.error(f"❌ Variáveis de ambiente faltando: {', '.join(missing)}")
            logger.info("Configure-as em .env ou nas variáveis do sistema")
            return False

        config = RoutineConfig.get_routine_config()

        logger.info(f"""
✅ Configuração da Routine:
   Nome: {config['name']}
   Horário: {RoutineConfig.ROUTINE_HOUR}h (diariamente)
   Timezone: {RoutineConfig.ROUTINE_TIMEZONE}
   Cron: {RoutineConfig.ROUTINE_CRON}

📝 Próximos passos:
   1. Use a CLI do Claude Code para criar a Routine:
      claude create-routine --name "{config['name']}" --cron "{config['cron_expression']}"

   2. Ou use diretamente no web interface em claude.ai/code

Para desabilitar a automação:
   - Acesse: https://claude.ai/code/routines
   - Desabilite ou delete a Routine
        """)

        return True

    @staticmethod
    def get_cli_command() -> str:
        """Comando CLI para criar a Routine"""
        config = RoutineConfig.get_routine_config()
        return f"""
claude create-routine \\
  --name "{config['name']}" \\
  --cron "{config['cron_expression']}" \\
  --prompt "{config['prompt']}"
        """


def main():
    """Executa setup da Routine"""
    if len(sys.argv) > 1 and sys.argv[1] == 'setup':
        success = RoutineConfig.setup()
        sys.exit(0 if success else 1)
    else:
        print("Uso: python routine.py setup")
        print(f"Comando CLI: {RoutineConfig.get_cli_command()}")


if __name__ == '__main__':
    main()
