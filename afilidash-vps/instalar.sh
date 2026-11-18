#!/usr/bin/env bash
# Faz a AfiliDash voltar a sincronizar com o Supabase no VPS (as funções da Netlify passam a rodar aqui).
# Comando único (terminal da Hostinger):
# curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/admiring-dirac-ku5zlh/afilidash-vps/instalar.sh | bash
set -euo pipefail
SUDO=$([ "$(id -u)" -eq 0 ] && echo '' || echo sudo)
REPO=https://github.com/julianebenetti/MGD-Benetti.git
BRANCH=claude/admiring-dirac-ku5zlh
DIR_BASE=/opt/afilidash-vps
SERVICO=afilidash-funcoes

if [ -f "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/servidor.js" ]; then
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  if [ -d "$DIR_BASE/.git" ]; then
    $SUDO git -C "$DIR_BASE" fetch -q --depth 1 origin "$BRANCH" && $SUDO git -C "$DIR_BASE" reset -q --hard FETCH_HEAD
  else
    $SUDO git clone -q --depth 1 --branch "$BRANCH" --filter=blob:none --sparse "$REPO" "$DIR_BASE"
    $SUDO git -C "$DIR_BASE" sparse-checkout set afilidash-vps
  fi
  exec bash "$DIR_BASE/afilidash-vps/instalar.sh"     # roda a versão recém-baixada
fi
cd "$DIR"

echo "▶ Funções da AfiliDash (repositório julianebenetti/afilidash, sem alterações)"
if [ -d afilidash/.git ]; then
  git -C afilidash fetch -q --depth 1 origin && git -C afilidash reset -q --hard FETCH_HEAD
else
  git clone -q --depth 1 --filter=blob:none --sparse https://github.com/julianebenetti/afilidash.git afilidash
  git -C afilidash sparse-checkout set netlify/functions
fi
ls afilidash/netlify/functions/*.js >/dev/null

echo "▶ Node.js"
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 18 ]; then
  $SUDO apt-get update -qq && $SUDO apt-get install -y -qq nodejs
fi
node -v

if [ ! -f .env ]; then cp .env.example .env; fi
if ! grep -q '^SUPABASE_KEY=.' .env; then
  echo "⚠️  Falta a chave do Supabase. Abra:  nano $DIR/.env"
  echo "    e cole a chave service_role em SUPABASE_KEY= (Supabase → Settings → API → service_role)."
  echo "    Salve (Ctrl+O, Enter, Ctrl+X) e rode o comando de novo."
  exit 1
fi
PORTA=$(grep -oP '^PORTA=\K[0-9]+' .env || echo 8791)

echo "▶ Serviço"
$SUDO tee /etc/systemd/system/$SERVICO.service >/dev/null <<UNIT
[Unit]
Description=AfiliDash - funcoes (sync, config, query, shopee, comissao) no VPS
After=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=$(command -v node) $DIR/servidor.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
$SUDO systemctl daemon-reload && $SUDO systemctl enable -q $SERVICO && $SUDO systemctl restart $SERVICO
sleep 2
curl -fsS "http://127.0.0.1:$PORTA/.netlify/functions/config?action=keys" >/dev/null && echo "✅ Funções respondendo em 127.0.0.1:$PORTA"

echo "▶ Ligando os endereços no site da AfiliDash (Nginx)"
SITE=$(grep -rlis 'server_name[^;]*afilidash' /etc/nginx/sites-available/ | head -1 || true)
if [ -z "$SITE" ]; then
  echo "⚠️  Não achei o site da AfiliDash no Nginx. Me mande o resultado de:  ls /etc/nginx/sites-available"
  exit 0
fi
echo "    site: $SITE"
if grep -q 'location /.netlify/functions/' "$SITE"; then
  echo "    já estava configurado"
else
  cp "$SITE" /root/nginx-afilidash-backup.conf
  BLOCO="location /.netlify/functions/ { proxy_pass http://127.0.0.1:$PORTA; proxy_set_header Host \$host; proxy_read_timeout 300s; client_max_body_size 50m; }\n    location /api/ { proxy_pass http://127.0.0.1:$PORTA; proxy_set_header Host \$host; proxy_read_timeout 300s; client_max_body_size 50m; }\n\n    location / {"
  if grep -qE '^\s*location / \{' "$SITE"; then
    sed -i -E "s#^(\s*)location / \{#\1${BLOCO}#" "$SITE"
  else
    LOCS="location /.netlify/functions/ { proxy_pass http://127.0.0.1:$PORTA; proxy_set_header Host \$host; proxy_read_timeout 300s; client_max_body_size 50m; }\n    location /api/ { proxy_pass http://127.0.0.1:$PORTA; proxy_set_header Host \$host; proxy_read_timeout 300s; client_max_body_size 50m; }"
    sed -i -E "/^\s*server_name[^;]*afilidash[^;]*;/a\    ${LOCS}" "$SITE"
  fi
  if $SUDO nginx -t 2>/dev/null; then
    $SUDO systemctl reload nginx && echo "✅ Endereços ligados (cópia do original em /root/nginx-afilidash-backup.conf)"
  else
    cp /root/nginx-afilidash-backup.conf "$SITE"; $SUDO systemctl reload nginx
    echo "❌ O Nginx não aceitou a mudança — voltei como estava. Me mande o print."
  fi
fi
echo
echo "Pronto. Abra a AfiliDash, atualize (Ctrl+F5) e clique em sincronizar. Logs: journalctl -u $SERVICO -f"
