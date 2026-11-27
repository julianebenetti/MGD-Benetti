#!/usr/bin/env bash
# Cria o serviço que mantém o bot do Facebook ligado (reinicia sozinho). Rode como administrador.
#   sudo bash instalar-servico.sh            instala e liga
#   bash instalar-servico.sh --mostrar       só mostra o arquivo do serviço, sem instalar
set -euo pipefail
APP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DONO="${SUDO_USER:-$(id -un)}"
PY="$(command -v python3)"
UNIT="[Unit]
Description=Bot do Facebook (Telegram)
After=network-online.target
Wants=network-online.target

[Service]
User=$DONO
WorkingDirectory=$APP
ExecStart=$PY bot_telegram.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"
if [ "${1:-}" = "--mostrar" ]; then echo "$UNIT"; exit 0; fi
[ -f "$APP/.env" ] || { echo "Falta o arquivo .env em $APP"; exit 1; }
[ -f "$APP/paginas.json" ] || { echo "Falta o paginas.json (rode antes: node obter-tokens-paginas.js)"; exit 1; }
echo "$UNIT" > /etc/systemd/system/facebook-bot.service
systemctl daemon-reload
systemctl enable --now facebook-bot
sleep 2
systemctl --no-pager status facebook-bot | head -8
echo; echo "Logs: journalctl -u facebook-bot -f"
