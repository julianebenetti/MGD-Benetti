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
  echo "    Preencha POSTZAP_SENHA e NUMEROS_AUTORIZADOS, salve (Ctrl+O, Enter, Ctrl+X) e rode o comando de novo."
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

# ---- Endereço público (Nginx + HTTPS), só se o domínio já aponta para este VPS e ninguém mais usa a porta 80
DOMINIO=$(grep -oP '^URL_PUBLICA=https?://\K[^/]+' .env || echo posts.descontoirresistivel.com.br)
PORTA=$(grep -oP '^POSTZAP_PORTA=\K[0-9]+' .env || echo 8790)
IP_VPS=$(curl -fsS4 https://api.ipify.org || true)
IP_DNS=$(getent ahostsv4 "$DOMINIO" | awk 'NR==1{print $1}' || true)
SITE=/etc/nginx/sites-available/postzap
if [ -n "$IP_VPS" ] && [ "$IP_VPS" = "$IP_DNS" ]; then
  OCUPA80=$($SUDO ss -ltnpH 'sport = :80' | grep -v nginx || true)
  if [ -n "$OCUPA80" ]; then
    echo "⚠️  A porta 80 já é usada por outro programa (não Nginx). Não mexi em nada:"; echo "$OCUPA80"
  elif ! [ -f "$SITE" ] && grep -rqs "server_name[^;]*$DOMINIO" /etc/nginx/ 2>/dev/null; then
    echo "⚠️  O Nginx já tem um site para $DOMINIO. Coloque dentro dele:"
    echo "    location /zap/ { proxy_pass http://127.0.0.1:$PORTA; proxy_set_header Host \$host; }"
  else
    echo "▶ Publicando em https://$DOMINIO/zap/"
    command -v nginx >/dev/null || $SUDO apt-get install -y -qq nginx
    command -v certbot >/dev/null || $SUDO apt-get install -y -qq certbot python3-certbot-nginx
    if ! [ -f "$SITE" ]; then
      $SUDO tee "$SITE" >/dev/null <<NGX
server {
    listen 80;
    server_name $DOMINIO;
    location = /zap { return 301 /zap/; }
    location /zap/ { proxy_pass http://127.0.0.1:$PORTA; proxy_set_header Host \$host; proxy_read_timeout 120s; }
}
NGX
      $SUDO ln -sf "$SITE" /etc/nginx/sites-enabled/postzap
    fi
    $SUDO nginx -t && $SUDO systemctl reload nginx
    $SUDO certbot --nginx -n --agree-tos --register-unsafely-without-email --redirect -d "$DOMINIO" \
      || echo "⚠️  O HTTPS falhou (veja a mensagem acima); o endereço funciona com http:// por enquanto"
    echo "✅ Abra: https://$DOMINIO/zap/"
  fi
else
  echo "⚠️  $DOMINIO ainda não aponta para este VPS (DNS: ${IP_DNS:-nenhum} · VPS: ${IP_VPS:-?})."
  echo "    Crie no DNS do domínio um registro A:  posts  →  $IP_VPS   e rode este comando de novo depois."
fi

cat <<TXT

Ver o que está acontecendo:  journalctl -u $SERVICE -f
TXT
