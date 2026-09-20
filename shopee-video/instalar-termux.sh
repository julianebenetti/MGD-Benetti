#!/usr/bin/env bash
# Instalacao no proprio tablet Android, dentro do Termux.
# Roda o fluxo inteiro sem notebook e sem VPS.
#
#   bash instalar-termux.sh
#
set -u
cd "$(dirname "$0")"

echo "=============================================="
echo " Shopee Video — instalacao no tablet (Termux)"
echo "=============================================="
echo

if [ -z "${PREFIX:-}" ] || [ ! -d "$PREFIX" ]; then
  echo "⚠️  Isto aqui e para rodar dentro do Termux."
  echo "   No computador ou no VPS, use: bash instalar.sh"
  exit 1
fi

echo "⏳ atualizando a lista de pacotes..."
pkg update -y >/dev/null 2>&1

echo "⏳ instalando python, ffmpeg, git, adb e as fontes..."
pkg install -y python ffmpeg git android-tools python-pillow fontconfig >/dev/null 2>&1

faltando=""
for programa in python ffmpeg adb; do
  command -v "$programa" >/dev/null || faltando="$faltando $programa"
done
if [ -n "$faltando" ]; then
  echo "❌ nao instalou:$faltando"
  echo "   tente na mao: pkg install -y python ffmpeg android-tools"
  exit 1
fi
echo "✅ python, ffmpeg e adb instalados"

if python3 -c "import PIL" 2>/dev/null; then
  echo "✅ Pillow instalado"
else
  echo "⏳ instalando o Pillow pelo pip..."
  pip install --quiet pillow 2>/dev/null
  python3 -c "import PIL" 2>/dev/null \
    && echo "✅ Pillow instalado" \
    || { echo "❌ Pillow falhou. Tente: pkg install -y python-pillow"; exit 1; }
fi

# acesso a galeria do tablet, para salvar e ler videos
if [ ! -d "$HOME/storage" ]; then
  echo
  echo "⏳ pedindo acesso ao armazenamento do tablet..."
  echo "   Vai aparecer um aviso na tela. Toque em PERMITIR."
  termux-setup-storage
  sleep 3
fi

echo
echo "⏳ rodando os testes..."
if python3 testes.py > testes.log 2>&1; then
  echo "✅ todos os testes passaram"
else
  echo "❌ algum teste falhou. Me mande o arquivo testes.log"
  tail -5 testes.log
  exit 1
fi

echo
echo "⏳ montando um post de demonstracao..."
mkdir -p demo
if [ ! -f demo/video-de-teste.mp4 ]; then
  ffmpeg -hide_banner -y \
    -f lavfi -i "gradients=size=1080x1920:rate=30:duration=14" \
    -f lavfi -i "color=c=white:size=1080x1920:rate=30:duration=3" \
    -f lavfi -i "sine=frequency=320:duration=17:sample_rate=44100" \
    -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" -map "[v]" -map 2:a \
    -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest \
    demo/video-de-teste.mp4 >/dev/null 2>&1
fi

python3 pipeline.py \
  --video demo/video-de-teste.mp4 \
  --link "https://shopee.com.br/Vestido-Longo-Feminino-i.123456.789012" \
  --nome "Vestido Longo Feminino Fluido Verao" \
  --saida demo/saida 2>&1 | grep -v "^⚠️  Nao consegui" || true

PASTA=$(ls -d demo/saida/*/ 2>/dev/null | head -1)
echo
echo "=============================================="
if [ -n "$PASTA" ]; then
  echo " Deu certo."
  echo "=============================================="
  echo
  echo "  📁 $PASTA"
  ls -1 "$PASTA" | sed 's/^/     /'
  echo
  echo "  Para ver a capa e o video na galeria do tablet:"
  echo "     cp $PASTA/capa.jpg $PASTA/video.mp4 ~/storage/movies/"
  echo
  echo "  Proximo passo, ligar o adb no proprio tablet:"
  echo "     bash conectar-adb.sh"
else
  echo " ⚠️  a pasta de saida nao foi criada."
  echo "=============================================="
  echo "  Me mande o que apareceu acima."
fi
echo
