#!/usr/bin/env bash
# Instala/atualiza o robô do Shopee Video como serviço (rode dentro desta pasta, no VPS).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE=shopee-video
cd "$DIR"

echo "▶ Pacotes do sistema"
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg python3-venv fonts-noto-color-emoji

echo "▶ Ambiente Python"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium

if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  Criei o arquivo .env. Preencha as chaves (Telegram, Shopee, Claude) e rode este instalador de novo."
  exit 1
fi

if ! grep -q '^TELEGRAM_TOPIC_ENVIOS=[0-9]' .env; then
  echo "▶ Criando os tópicos no grupo"
  .venv/bin/python setup_topics.py
fi

echo "▶ Serviço $SERVICE"
sudo tee /etc/systemd/system/$SERVICE.service >/dev/null <<EOF
[Unit]
Description=Robô do Shopee Video (Achados Relâmpagos)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/bot.py
Restart=always
RestartSec=5
User=$(id -un)

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now $SERVICE
sudo systemctl restart $SERVICE
echo "✅ Robô ligado. Logs: journalctl -u $SERVICE -n 50"
