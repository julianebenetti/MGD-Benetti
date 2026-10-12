#!/usr/bin/env bash
# Instala/atualiza o robô do Shopee Video como serviço no VPS.
# Comando único: curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/shopee-video-posts-fy4an1/shopee-video-automation/instalar.sh | bash
set -euo pipefail

SUDO=$([ "$(id -u)" -eq 0 ] && echo '' || echo sudo)

SERVICE=shopee-video
REPO=https://github.com/julianebenetti/MGD-Benetti.git
BRANCH=claude/shopee-video-posts-fy4an1
INSTALL_DIR=/opt/shopee-video

# Rodando pelo comando único (curl | bash): baixa ou atualiza o código em $INSTALL_DIR
if [ -f "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/bot.py" ]; then
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  $SUDO apt-get update -qq && $SUDO apt-get install -y -qq git
  if [ -d "$INSTALL_DIR/.git" ]; then
    echo "▶ Atualizando o código"
    $SUDO git -C "$INSTALL_DIR" fetch -q --depth 1 origin "$BRANCH"
    $SUDO git -C "$INSTALL_DIR" reset -q --hard FETCH_HEAD
  else
    echo "▶ Baixando o código"
    $SUDO git clone -q --depth 1 --branch "$BRANCH" --filter=blob:none --sparse "$REPO" "$INSTALL_DIR"
    $SUDO git -C "$INSTALL_DIR" sparse-checkout set shopee-video-automation
  fi
  $SUDO chown -R "$(id -un)" "$INSTALL_DIR"
  DIR="$INSTALL_DIR/shopee-video-automation"
fi
cd "$DIR"

echo "▶ Pacotes do sistema"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ffmpeg python3-venv fonts-noto-color-emoji

echo "▶ Ambiente Python"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium

if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  Criei o arquivo $DIR/.env"
  echo "    Abra com:  nano $DIR/.env"
  echo "    Preencha as chaves, salve (Ctrl+O, Enter, Ctrl+X) e rode o mesmo comando de instalação de novo."
  exit 1
fi

# 5 links por vídeo (todos vão para a LiA); .env antigos vinham com 3
sed -i 's/^LINKS_POR_VIDEO=3$/LINKS_POR_VIDEO=5/' .env

if ! grep -q '^TELEGRAM_TOPIC_ENVIOS=[0-9]' .env; then
  echo "▶ Criando os tópicos no grupo"
  .venv/bin/python setup_topics.py
fi

echo "▶ Serviço $SERVICE"
$SUDO tee /etc/systemd/system/$SERVICE.service >/dev/null <<EOF
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

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now $SERVICE
$SUDO systemctl restart $SERVICE
echo "✅ Robô ligado. Logs: journalctl -u $SERVICE -n 50"
