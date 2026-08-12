# 🧪 Guia de Testes - Automação Shopee Video

Guia passo a passo para testar cada componente da automação.

---

## 📋 Pré-requisitos

```bash
# Instale dependências
pip install -r requirements.txt

# Configure .env
cp .env.example .env
# Edite .env com suas credenciais:
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID
# - ANTHROPIC_API_KEY
```

---

## 🚀 Teste Rápido Automatizado

Execute o script de teste completo:

```bash
python test_automation.py
```

Isso vai testar:
- ✅ Conexão Telegram
- ✅ Processamento FFmpeg
- ✅ Geração de conteúdo (IA)
- ✅ Web scraping Shopee
- ✅ Fluxo completo

---

## 🧪 Testes Individuais

### Teste 1: Telegram Connection

**Objetivo**: Verificar se o bot consegue se conectar ao grupo

```bash
python -c "
from telegram_handler import TelegramMonitor
import os
from dotenv import load_dotenv

load_dotenv()
monitor = TelegramMonitor(
    os.getenv('TELEGRAM_BOT_TOKEN'),
    os.getenv('TELEGRAM_CHAT_ID')
)
updates = monitor.get_updates()
print(f'✅ Bot conectado! {len(updates)} mensagens encontradas')
"
```

**Esperado**: `✅ Bot conectado! X mensagens encontradas`

**Troubleshooting**:
- ❌ `"Invalid token"` → Token incorreto em .env
- ❌ `"Chat not found"` → Chat ID incorreto
- ❌ `"Bot doesn't have permission"` → Bot não é admin do grupo

---

### Teste 2: FFmpeg Video Processing

**Objetivo**: Testar se vídeos são processados corretamente para 9:16

```bash
python -c "
from video_processor import VideoProcessor
from pathlib import Path

# Criar vídeo de teste (5 segundos)
import subprocess
test_video = 'test_input.mp4'
cmd = [
    'ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:d=5',
    '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono:d=5',
    '-pix_fmt', 'yuv420p', '-y', test_video
]
subprocess.run(cmd, capture_output=True)

# Processar
processor = VideoProcessor()
output_dir = Path('test_output')
output_dir.mkdir(exist_ok=True)

result = processor.process(test_video, output_dir)
if result:
    info = processor.get_video_info(result)
    print(f'✅ Vídeo processado!')
    print(f'   Resolução: {info[\"width\"]}x{info[\"height\"]}')
    print(f'   Esperado: 1080x1920 (9:16)')
else:
    print('❌ Processamento falhou')
"
```

**Esperado**:
```
✅ Vídeo processado!
   Resolução: 1080x1920
   Esperado: 1080x1920 (9:16)
```

**Troubleshooting**:
- ❌ `"ffmpeg: command not found"` → Instale FFmpeg
- ❌ Resolução incorreta → Verificar video_processor.py

---

### Teste 3: Content Generation (Claude AI)

**Objetivo**: Testar geração de descrição, hashtags e SEO

```bash
python -c "
from content_generator import ContentGenerator
import json

generator = ContentGenerator()

# Dados de teste
product = {
    'name': 'Fone Bluetooth Premium',
    'price': 149.90,
    'category': 'Eletrônicos',
    'brand': 'SoundMax',
    'rating': 4.8,
    'sold': 523,
    'description': 'Fone bluetooth com cancelamento de ruído, bateria 30h'
}

content = generator.generate(product)

print('✅ Conteúdo gerado:')
print(f'Descrição: {content[\"description\"]}')
print(f'Hashtags: {content[\"hashtags\"]}')
print(f'Keywords: {content[\"seo_keywords\"]}')

# Validar
is_valid = generator.validate_content(content)
print(f'Validação: {\"✅ OK\" if is_valid else \"❌ Falhou\"}')
"
```

**Esperado**:
```
✅ Conteúdo gerado:
Descrição: [texto até 150 chars]
Hashtags: ['#hashtag1', '#hashtag2', ...]
Keywords: ['palavra1', 'palavra2', ...]
Validação: ✅ OK
```

**Troubleshooting**:
- ❌ `"Authentication failed"` → ANTHROPIC_API_KEY inválida
- ❌ Descrição > 150 caracteres → Editar content_generator.py
- ❌ Palavras repetidas → Ajustar prompt

---

### Teste 4: Shopee Web Scraping

**Objetivo**: Testar extração de informações de produtos

```bash
python -c "
from shopee_scraper import ShopeeScraper

scraper = ShopeeScraper()

# Use uma URL real de produto
url = 'https://shopee.com.br/p/52kekkac'  # Ajuste com URL real

product_info = scraper.extract_product_info(url)

if product_info.get('name'):
    print('✅ Scraping bem-sucedido!')
    print(f'Nome: {product_info[\"name\"]}')
    print(f'Preço: R$ {product_info[\"price\"]}')
    print(f'Categoria: {product_info[\"category\"]}')
else:
    print('❌ Nenhuma informação extraída')
"
```

**Esperado**:
```
✅ Scraping bem-sucedido!
Nome: [nome do produto]
Preço: R$ [preço]
Categoria: [categoria]
```

**Troubleshooting**:
- ❌ Sem resultados → URL pode estar inválida ou mudou
- ❌ Rate limit → Aguarde alguns minutos

---

## 📱 Teste Manual com Telegram

### Passo 1: Preparar um vídeo
Tenha um vídeo em formato MP4 no seu PC/telefone

### Passo 2: Enviar ao grupo
1. Abra o grupo "Shopee Video Bot" no Telegram
2. Envie o vídeo
3. Na mesma mensagem ou em resposta, envie um link Shopee:
   ```
   https://shopee.com.br/p/52kekkac
   ```

### Passo 3: Executar automação
```bash
python main.py
```

### Passo 4: Verificar resultado
```bash
# Listar rascunhos gerados
ls -la processed_videos/
ls -la drafts/
```

**Esperado**: 
- Vídeo processado em `processed_videos/`
- Rascunho salvo em `drafts/` com JSON completo

---

## 🔍 Debugging

### Ver logs detalhados
```bash
# Executar com debug
python -u main.py 2>&1 | tee debug.log

# Consultar arquivo de log
tail -f automation.log
```

### Verificar arquivo de rascunho
```bash
# Listar rascunhos
ls -la drafts/

# Visualizar conteúdo de um rascunho
cat drafts/draft_20240115_143000.json | python -m json.tool
```

### Testar componente isoladamente

**Telegram**:
```python
from telegram_handler import TelegramMonitor
monitor = TelegramMonitor('TOKEN', 'CHAT_ID')
messages = monitor.get_new_messages()
print(messages)
```

**Vídeo**:
```python
from video_processor import VideoProcessor
processor = VideoProcessor()
result = processor.process('input.mp4', './output')
print(result)
```

**Conteúdo**:
```python
from content_generator import ContentGenerator
gen = ContentGenerator()
content = gen.generate({'name': 'Produto'})
print(content)
```

---

## ✅ Checklist de Testes

- [ ] **Conexão Telegram** - Bot consegue se conectar
- [ ] **Processamento de Vídeo** - FFmpeg gera 9:16 corretamente
- [ ] **Geração de Conteúdo** - Claude gera descrição + hashtags + SEO
- [ ] **Web Scraping** - Extrai informações do produto
- [ ] **Teste Manual** - Enviar vídeo + link no Telegram e processar
- [ ] **Validação de Rascunho** - Arquivo JSON gerado corretamente
- [ ] **Marca d'água** - Vídeo tem watermark "AfiliDash"

---

## 🚨 Erros Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| `Token invalid` | Token Telegram errado | Verificar .env |
| `Chat not found` | Chat ID errado | Usar `/getid` no grupo |
| `ffmpeg not found` | FFmpeg não instalado | `apt-get install ffmpeg` |
| `API rate limit` | Muitos requests | Aguardar ~1 hora |
| `No video extracted` | Link Shopee inválido | Usar URL de produto real |

---

## 📞 Próximos Passos

Após passar em todos os testes:

1. ✅ Criar Routine automática (14h diariamente)
2. ✅ Configurar Supabase para armazenar drafts
3. ✅ Criar dashboard web para validação
4. ✅ Implementar upload automático na Shopee Video

---

**Dúvidas?** Verifique `automation.log` ou abra uma issue no GitHub.
