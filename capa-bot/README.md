# capa-bot — capas de Reels pelo Telegram

Fluxo: você manda o vídeo → Claude lê 3 frames e sugere 3 headlines → você escolhe
(ou digita a sua) → IA gera o fundo estilo Pinterest → o bot aplica a headline e devolve a capa 1080x1920.

## Instalar no VPS da Hostinger
```bash
apt install -y ffmpeg python3-venv
mkdir -p /opt/capa-bot && cp -r * /opt/capa-bot && cd /opt/capa-bot
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env        # preencha as chaves
mkdir fonts                               # coloque sua fonte em fonts/headline.ttf
cp capa-bot.service /etc/systemd/system/ && systemctl enable --now capa-bot
journalctl -u capa-bot -f                 # ver logs
```
1. Crie o bot no @BotFather (`/newbot`) e coloque o token no `.env`.
2. Mande `/start` pro bot: ele responde seu chat id → coloque em `ALLOWED_CHAT_IDS`.

## Ajustar o visual
Tudo em `style.py` (fonte, cores, posição da headline, prompt do fundo).
Limite: o Telegram só deixa bots baixarem vídeos de até 20 MB.
