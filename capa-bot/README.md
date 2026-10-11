# capa-bot — capas de Reels "Achei na Shopee" pelo Telegram

Segue o padrão visual documentado (1080×1920, Boogaloo + faixa branca Montserrat ExtraBold, estrelas,
contorno preto, sem overlay, bloco centralizado e 140px acima do centro).

## Como usar no Telegram
- **Vídeo**: o fundo é um frame do vídeo (botão "🖼 Outro frame" troca). O Claude olha o vídeo e sugere 3 textos.
- **Fotos** (várias na mesma mensagem): a **primeira é o fundo**; as demais são prints da Shopee só de contexto.
  Se não parecerem ser do mesmo produto, o bot avisa antes de seguir.
- Escolha uma opção, ou mande **3 linhas** (faixa / gancho / complemento) com o seu texto.
- Qualquer outra mensagem (ex.: "na verdade ele serve para…") é tratada como correção e gera novas sugestões.
- A capa volta como arquivo PNG (sem compressão).

## Instalar no VPS da Hostinger
```bash
apt install -y ffmpeg python3-venv
mkdir -p /opt/capa-bot && cp -r * /opt/capa-bot && cd /opt/capa-bot
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env        # preencha as chaves
cp capa-bot.service /etc/systemd/system/ && systemctl enable --now capa-bot
journalctl -u capa-bot -f                 # ver logs
```
1. Crie o bot no @BotFather (`/newbot`) e coloque o token no `.env`.
2. Mande `/start` pro bot: ele responde seu chat id → coloque em `ALLOWED_CHAT_IDS` e reinicie (`systemctl restart capa-bot`).

## Ajustar o visual
Constantes no topo de `cover.py` (tamanhos, espaçamentos, cores). Fontes em `fonts/` (licença OFL).
Limite do Telegram: bots só baixam arquivos de até 20 MB.
