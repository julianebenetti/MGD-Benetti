#!/usr/bin/env bash
# Instala/atualiza o robô do Facebook no VPS (mesmo jeito do PostZap).
#   curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/eager-wozniak-yxsgfc/facebook-post/instalar.sh | bash
# Seguro rodar de novo: atualiza o código e NÃO mexe no seu .env, fila.json, estado.json nem imagens.
set -euo pipefail

REPO="${REPO:-https://github.com/julianebenetti/MGD-Benetti.git}"
BRANCH="${BRANCH:-claude/eager-wozniak-yxsgfc}"
DIR="${DIR:-/opt/facebook-post}"
APP="$DIR/facebook-post"
SUDO=""; [ "$(id -u)" != 0 ] && SUDO="sudo"
DONO="${SUDO_USER:-$(id -un)}"

command -v git >/dev/null || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq git; }
command -v python3 >/dev/null || { $SUDO apt-get update -qq && $SUDO apt-get install -y -qq python3; }

if [ -d "$DIR/.git" ]; then
  echo "→ Atualizando o código…"
  $SUDO git -C "$DIR" fetch -q --depth 1 origin "$BRANCH"
  $SUDO git -C "$DIR" reset -q --hard FETCH_HEAD
else
  echo "→ Baixando o código…"
  $SUDO mkdir -p "$DIR"
  $SUDO git clone -q --depth 1 --branch "$BRANCH" --sparse "$REPO" "$DIR"
  $SUDO git -C "$DIR" sparse-checkout set facebook-post
fi
$SUDO chown -R "$DONO" "$DIR"

cd "$APP"
mkdir -p imagens
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "→ Criei o arquivo .env"
fi
[ -f fila.json ] || echo "[]" > fila.json

echo
echo "✅ Instalado em: $APP"
if ! grep -q '^FB_PAGE_TOKEN=.\+' .env || ! grep -q '^FB_PAGE_ID=.\+' .env; then
  echo "Próximo passo: preencha FB_PAGE_ID e FB_PAGE_TOKEN →  nano $APP/.env"
else
  echo "Teste o acesso (não posta nada):  cd $APP && python3 facebook_post.py --testar-token"
fi
