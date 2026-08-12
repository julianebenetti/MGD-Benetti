# Shopee Video Posts Automation

Automação completa para postagem de vídeos na Shopee Video com processamento de vídeos, geração de metadados e publicação.

## 🎯 Funcionalidades

- ✅ Monitora grupo Telegram para novos vídeos + links de produtos
- ✅ Processa vídeos com FFmpeg (redimensiona para 9:16 em 1080p)
- ✅ Extrai informações dos produtos via web scraping
- ✅ Gera descrição, hashtags e 10 palavras-chave SEO com IA (Claude)
- ✅ Adiciona marca d'água aos vídeos
- ✅ Salva em rascunho para validação antes de publicar
- ✅ Executa automaticamente via Routine diária às 14h

## 📋 Pré-requisitos

### Sistema
- Python 3.9+
- FFmpeg instalado
  ```bash
  # Ubuntu/Debian
  sudo apt-get install ffmpeg ffprobe
  
  # macOS
  brew install ffmpeg
  
  # Windows
  # Baixe de https://ffmpeg.org/download.html
  ```

### Credenciais
- Bot Token do Telegram
- Chat ID do grupo Telegram
- API Key da Anthropic (Claude)

## 🚀 Instalação

1. **Clone o repositório**
   ```bash
   git clone <repo>
   cd shopee-video-automation
   ```

2. **Instale dependências**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure variáveis de ambiente**
   ```bash
   cp .env.example .env
   # Edite .env com suas credenciais
   ```

4. **Estrutura de pastas**
   ```
   shopee-video-automation/
   ├── main.py                 # Script principal
   ├── telegram_handler.py     # Monitor do Telegram
   ├── video_processor.py      # Processamento com FFmpeg
   ├── shopee_scraper.py       # Web scraping
   ├── content_generator.py    # Geração de conteúdo com IA
   ├── routine.py              # Configuração da Routine
   ├── downloads/              # Vídeos baixados do Telegram
   ├── processed_videos/       # Vídeos processados
   ├── drafts/                 # Rascunhos prontos para publicação
   └── .env                    # Variáveis de ambiente (git ignore)
   ```

## 📖 Uso

### Execução Manual
```bash
# Processar vídeos pendentes
python main.py
```

### Execução Automática (Routine)
A automação roda automaticamente todos os dias às 14h (Brasília).

Configure via arquivo `routine.py`:
```bash
python routine.py setup
```

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=-seu_chat_id_aqui

# Shopee
SHOPEE_USERNAME=seu_usuario
SHOPEE_PASSWORD=sua_senha

# Claude AI
ANTHROPIC_API_KEY=sua_api_key

# Vídeo (9:16 vertical)
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_BITRATE=5M

# Diretórios
VIDEOS_OUTPUT_DIR=./processed_videos
DRAFTS_OUTPUT_DIR=./drafts

# Timing
ROUTINE_HOUR=14
ROUTINE_TIMEZONE=America/Sao_Paulo
```

## 📹 Processo de Publicação

1. **Enviar no Telegram**: Poste o vídeo + link Shopee no grupo
2. **Automação**: Bot baixa, processa e gera metadados
3. **Validação**: Vídeo fica em rascunho para revisar
4. **Publicação**: Upload manual na Shopee Video ou automático

## 🎬 Especificações de Vídeo

- **Proporção**: 9:16 (vertical)
- **Resolução**: 1920x1080
- **Bitrate**: 5 Mbps
- **FPS**: 30
- **Duração**: 15s - 10min
- **Tamanho máx**: 500MB

## 🔍 Logs

Verifique `automation.log` para debug:
```bash
tail -f automation.log
```

## 🐛 Troubleshooting

### "FFmpeg não encontrado"
```bash
# Instale FFmpeg
sudo apt-get install ffmpeg ffprobe
```

### "Erro ao baixar vídeo do Telegram"
- Verifique Bot Token
- Verifique Chat ID (deve ser negativo)
- Certifique-se que o bot é admin do grupo

### "Erro na geração de conteúdo"
- Verifique ANTHROPIC_API_KEY
- Verifique limite de tokens/requisições

## 📝 Estrutura de Saída

Cada vídeo processado gera:

```json
{
  "video_path": "processed_videos/processed_video.mp4",
  "product_url": "https://shopee.com.br/p/...",
  "product_info": {
    "name": "Nome do Produto",
    "price": 99.90,
    "category": "Eletrônicos",
    "description": "..."
  },
  "metadata": {
    "description": "Descrição otimizada...",
    "hashtags": ["#Shopee", "#Oferta", ...],
    "seo_keywords": ["produto", "oferta", ...]
  },
  "timestamp": "2024-01-15T14:30:00",
  "status": "draft"
}
```

## 🚨 Segurança

- ⚠️ **Nunca commite .env** (está em .gitignore)
- ⚠️ **Proteja suas credenciais**
- ⚠️ **Use variáveis de ambiente em produção**

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs (`automation.log`)
2. Consulte a documentação
3. Abra uma issue no repositório
