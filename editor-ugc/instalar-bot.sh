#!/usr/bin/env bash
# Instala (ou atualiza) o robô do Telegram "Editor UGC" no VPS.
# Uso, no terminal do VPS (como root):
#   curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/ugc-tiktok-video-editing-7d11hx/editor-ugc/instalar-bot.sh | bash
set -euo pipefail

RAMO="${RAMO:-claude/ugc-tiktok-video-editing-7d11hx}"
BASE="https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/${RAMO}/editor-ugc"
DIR=/opt/editor-ugc
ENV=/etc/editor-ugc.env

[ "$(id -u)" = 0 ] || { echo "Rode como root (ou com sudo)."; exit 1; }

echo "→ Instalando python3 e ffmpeg..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 ffmpeg curl ca-certificates >/dev/null

echo "→ Baixando o robô..."
mkdir -p "$DIR"
for f in cortar_parados.py bot_telegram.py; do
  curl -fsSL "$BASE/$f" -o "$DIR/$f"
done
id editorugc >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin editorugc

if [ ! -f "$ENV" ]; then
  echo
  echo "Cole o token que o @BotFather te deu (não aparece enquanto digita) e aperte Enter:"
  read -rs TOKEN < /dev/tty; echo
  echo "Agora o seu ID do Telegram (mande /start pro @userinfobot pra descobrir)."
  echo "Se mais de uma pessoa for usar, separe por vírgula:"
  read -r IDS < /dev/tty
  umask 077
  printf 'TELEGRAM_BOT_TOKEN=%s\nUSUARIOS_PERMITIDOS=%s\n' "$TOKEN" "$IDS" > "$ENV"
  chmod 600 "$ENV"
fi

cat > /etc/systemd/system/editor-ugc.service <<UNIT
[Unit]
Description=Robô do Telegram - Editor UGC (corta paradas dos vídeos)
After=network-online.target
Wants=network-online.target

[Service]
User=editorugc
EnvironmentFile=$ENV
Environment=EDITOR_UGC_DADOS=/var/lib/editor-ugc
Environment=PYTHONUNBUFFERED=1
StateDirectory=editor-ugc
ExecStart=/usr/bin/python3 $DIR/bot_telegram.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable editor-ugc >/dev/null 2>&1
systemctl restart editor-ugc
sleep 3
if systemctl is-active --quiet editor-ugc; then
  echo
  echo "✅ Robô rodando! Abra ele no Telegram e mande /start."
  journalctl -u editor-ugc -n 3 --no-pager -o cat
else
  echo "❌ O robô não subiu. Veja o erro:"
  journalctl -u editor-ugc -n 20 --no-pager -o cat
  exit 1
fi
