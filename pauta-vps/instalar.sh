#!/usr/bin/env bash
# Publica a agenda (minha-pauta.html) no VPS, protegida por SENHA, junto com o histórico do robô do Facebook.
#   curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/eager-wozniak-yxsgfc/pauta-vps/instalar.sh | sudo bash
# Pode rodar de novo para atualizar a agenda. Não mexe em nenhum outro site do servidor.
set -euo pipefail

REPO="${REPO:-https://github.com/julianebenetti/MGD-Benetti.git}"
BRANCH="${BRANCH:-claude/eager-wozniak-yxsgfc}"
DIR="${DIR:-/opt/minha-pauta}"
SNIPPET="${SNIPPET:-/etc/nginx/snippets/pauta.conf}"
HTPASS="${HTPASS:-/etc/nginx/.htpasswd-pauta}"
USUARIO="${PAUTA_USUARIO:-Benetti}"
HIST="${HIST:-/opt/facebook-post/facebook-post}"
SUDO=""; [ "$(id -u)" != 0 ] && SUDO="sudo"

command -v git >/dev/null || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq git; }
command -v openssl >/dev/null || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq openssl; }

echo "→ Baixando a agenda…"
if [ -d "$DIR/.git" ]; then
  $SUDO git -C "$DIR" fetch -q --depth 1 origin "$BRANCH"
  $SUDO git -C "$DIR" reset -q --hard FETCH_HEAD
else
  $SUDO mkdir -p "$DIR"
  $SUDO git clone -q --depth 1 --branch "$BRANCH" --sparse "$REPO" "$DIR"
  $SUDO git -C "$DIR" sparse-checkout set --no-cone /minha-pauta.html
fi
[ -f "$DIR/minha-pauta.html" ] || { echo "✖ Não achei minha-pauta.html em $DIR"; exit 1; }
$SUDO chmod -R a+rX "$DIR"

# senha de entrada (só na primeira vez)
if [ ! -f "$HTPASS" ]; then
  if [ -n "${PAUTA_SENHA:-}" ]; then SENHA="$PAUTA_SENHA"
  else
    read -r -s -p "Escolha uma SENHA para entrar na agenda: " SENHA </dev/tty; echo
    read -r -s -p "Repita a senha: " SENHA2 </dev/tty; echo
    [ "$SENHA" = "$SENHA2" ] || { echo "✖ As senhas não conferem. Rode de novo."; exit 1; }
  fi
  [ "${#SENHA}" -ge 8 ] || { echo "✖ Use pelo menos 8 caracteres."; exit 1; }
  HASH="$(openssl passwd -apr1 -stdin <<<"$SENHA")"
  $SUDO mkdir -p "$(dirname "$HTPASS")"
  echo "$USUARIO:$HASH" | $SUDO tee "$HTPASS" >/dev/null
  $SUDO chown root:www-data "$HTPASS" 2>/dev/null || true
  $SUDO chmod 640 "$HTPASS"
  echo "→ Senha criada. Usuário para entrar: $USUARIO"
fi

# pasta do histórico legível pelo nginx (só o arquivo postados.json; o .env e os tokens continuam protegidos)
$SUDO mkdir -p "$HIST/publico" && $SUDO chmod 755 "$HIST/publico"

$SUDO mkdir -p "$(dirname "$SNIPPET")"
$SUDO tee "$SNIPPET" >/dev/null <<NGINX
# Minha Agenda (gerado por pauta-vps/instalar.sh)
location = /pauta { return 301 /pauta/; }
location /pauta/ {
    alias $DIR/;
    index minha-pauta.html;
    auth_basic "Minha Agenda";
    auth_basic_user_file $HTPASS;
    add_header Cache-Control "no-cache";
}
location = /facebook/postados.json {
    alias $HIST/publico/postados.json;
    auth_basic "Minha Agenda";
    auth_basic_user_file $HTPASS;
    default_type application/json;
    add_header Cache-Control "no-store";
}
NGINX

echo
echo "✅ Agenda instalada em $DIR e configuração do nginx em $SNIPPET"
echo
echo "Falta UMA coisa, feita uma vez: ligar essa configuração ao seu site."
echo "  1) Ache o arquivo do site:   grep -rl posts.descontoirresistivel.com.br /etc/nginx/"
echo "  2) Abra-o (nano) e, DENTRO do bloco  server { ... }  do site (o do HTTPS, porta 443), acrescente a linha:"
echo "         include $SNIPPET;"
echo "  3) Teste e recarregue:       sudo nginx -t && sudo systemctl reload nginx"
echo "  4) Abra:  https://posts.descontoirresistivel.com.br/pauta/   (usuário: $USUARIO)"
