#!/usr/bin/env bash
# Instala/atualiza o PostZap no VPS. Comando único (terminal da Hostinger):
# curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/admiring-dirac-ku5zlh/postzap/instalar.sh | bash
set -euo pipefail
SUDO=$([ "$(id -u)" -eq 0 ] && echo '' || echo sudo)
REPO=https://github.com/julianebenetti/MGD-Benetti.git
BRANCH=claude/admiring-dirac-ku5zlh
INSTALL_DIR=/opt/postzap
SERVICE=postzap

if [ -f "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/app.py" ]; then
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  command -v git >/dev/null || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq git; }
  if [ -d "$INSTALL_DIR/.git" ]; then
    echo "▶ Atualizando o código"
    $SUDO git -C "$INSTALL_DIR" fetch -q --depth 1 origin "$BRANCH"
    $SUDO git -C "$INSTALL_DIR" reset -q --hard FETCH_HEAD
  else
    echo "▶ Baixando o código"
    $SUDO git clone -q --depth 1 --branch "$BRANCH" --filter=blob:none --sparse "$REPO" "$INSTALL_DIR"
    $SUDO git -C "$INSTALL_DIR" sparse-checkout set postzap
  fi
  $SUDO chown -R "$(id -un)" "$INSTALL_DIR"
  DIR="$INSTALL_DIR/postzap"
fi
cd "$DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^EVOLUTION_KEY=.*/EVOLUTION_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(20))')/" .env
  echo "⚠️  Criei $DIR/.env — abra com:  nano $DIR/.env"
  echo "    Preencha POSTZAP_SENHA, SUPABASE_KEY e NUMEROS_AUTORIZADOS, salve (Ctrl+O, Enter, Ctrl+X) e rode o comando de novo."
  exit 1
fi
if ! grep -q '^WEBHOOK_SEGREDO=.' .env; then
  sed -i '/^WEBHOOK_SEGREDO=/d' .env
  echo "WEBHOOK_SEGREDO=$(python3 -c 'import secrets; print(secrets.token_hex(16))')" >> .env
fi
grep -q '^EVOLUTION_INSTANCIAS=' .env || echo "EVOLUTION_INSTANCIAS=chip1,chip2,chip3" >> .env
grep -q '^POSTZAP_SENHA=.' .env || { echo "⚠️  Falta POSTZAP_SENHA no $DIR/.env"; exit 1; }

echo "▶ Docker (WhatsApp / Evolution API)"
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | $SUDO sh; fi
$SUDO docker compose --env-file .env up -d

echo "▶ Serviço do PostZap"
$SUDO tee /etc/systemd/system/$SERVICE.service >/dev/null <<UNIT
[Unit]
Description=PostZap (links da Shopee nos grupos de WhatsApp)
After=network-online.target docker.service

[Service]
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 $DIR/app.py
Restart=always
RestartSec=5
User=$(id -un)

[Install]
WantedBy=multi-user.target
UNIT
$SUDO systemctl daemon-reload
$SUDO systemctl enable -q $SERVICE
$SUDO systemctl restart $SERVICE
sleep 2
$SUDO systemctl is-active --quiet $SERVICE && echo "✅ PostZap rodando em 127.0.0.1:$(grep -oP '^POSTZAP_PORTA=\K[0-9]+' .env || echo 8790)"

cat <<TXT

Falta publicar no endereço (só na primeira vez) — veja o README:
  posts.descontoirresistivel.com.br/zap  →  127.0.0.1:8790
Ver o que está acontecendo:  journalctl -u $SERVICE -f
TXT
