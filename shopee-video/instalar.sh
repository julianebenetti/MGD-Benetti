#!/usr/bin/env bash
# Primeiro teste do fluxo de postagens. Instala o que falta, roda os testes
# e monta um post de demonstracao, sem precisar de chave nenhuma.
#
#   bash instalar.sh
#
set -u
cd "$(dirname "$0")"

echo "=============================================="
echo " Shopee Video — primeiro teste"
echo "=============================================="
echo

# ── 1. Python ────────────────────────────────────────────────────
if ! command -v python3 >/dev/null; then
  echo "❌ Python 3 nao encontrado. Instale com: sudo apt install -y python3 python3-pip"
  exit 1
fi
echo "✅ Python $(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"

# ── 2. ffmpeg ────────────────────────────────────────────────────
if command -v ffmpeg >/dev/null; then
  echo "✅ ffmpeg ja instalado"
else
  echo "⏳ instalando o ffmpeg..."
  if sudo -n apt-get install -y ffmpeg >/dev/null 2>&1 || apt-get install -y ffmpeg >/dev/null 2>&1; then
    echo "✅ ffmpeg instalado"
  else
    echo "⏳ sem permissao para o apt, usando a versao que vem pelo pip..."
    python3 -m pip install --quiet imageio-ffmpeg 2>/dev/null
    if python3 -c "import imageio_ffmpeg" 2>/dev/null; then
      echo "✅ ffmpeg pelo pip (para valer, depois rode: sudo apt install -y ffmpeg)"
    else
      echo "❌ nao consegui instalar o ffmpeg. Rode: sudo apt install -y ffmpeg"
      exit 1
    fi
  fi
fi

# ── 3. Pillow ────────────────────────────────────────────────────
if python3 -c "import PIL" 2>/dev/null; then
  echo "✅ Pillow ja instalado"
else
  echo "⏳ instalando o Pillow..."
  python3 -m pip install --quiet pillow 2>/dev/null
  if python3 -c "import PIL" 2>/dev/null; then
    echo "✅ Pillow instalado"
  else
    echo "❌ nao consegui instalar o Pillow. Rode: pip3 install pillow"
    exit 1
  fi
fi

# ── 4. Testes ────────────────────────────────────────────────────
echo
echo "⏳ rodando os testes..."
if python3 testes.py > /tmp/testes-shopee.log 2>&1; then
  echo "✅ todos os testes passaram"
else
  echo "❌ algum teste falhou. Me mande este arquivo:"
  echo "   /tmp/testes-shopee.log"
  tail -5 /tmp/testes-shopee.log
  exit 1
fi

# ── 5. Video de demonstracao ─────────────────────────────────────
DEMO="demo"
mkdir -p "$DEMO"
FF=$(command -v ffmpeg || python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null)
if [ ! -f "$DEMO/video-de-teste.mp4" ]; then
  echo "⏳ criando um video de teste (com cartao final, feito o do CapCut)..."
  "$FF" -hide_banner -y \
    -f lavfi -i "gradients=size=1080x1920:rate=30:duration=14" \
    -f lavfi -i "color=c=white:size=1080x1920:rate=30:duration=3" \
    -f lavfi -i "sine=frequency=320:duration=17:sample_rate=44100" \
    -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" -map "[v]" -map 2:a \
    -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest \
    "$DEMO/video-de-teste.mp4" >/dev/null 2>&1
fi
[ -f "$DEMO/video-de-teste.mp4" ] && echo "✅ video de teste pronto"

echo
echo "⏳ montando o post de demonstracao..."
python3 pipeline.py \
  --video "$DEMO/video-de-teste.mp4" \
  --link "https://shopee.com.br/Vestido-Longo-Feminino-i.123456.789012" \
  --nome "Vestido Longo Feminino Fluido Verao" \
  --saida "$DEMO/saida" 2>&1 | grep -v "^⚠️  Nao consegui" || true

echo
echo "=============================================="
echo " Deu certo. O que olhar agora:"
echo "=============================================="
PASTA=$(ls -d "$DEMO"/saida/*/ 2>/dev/null | head -1)
if [ -n "$PASTA" ]; then
  echo
  echo "  📁 $PASTA"
  ls -1 "$PASTA" | sed 's/^/     /'
  echo
  echo "  Abra a capa.jpg e o video.mp4 para ver como ficaram."
  echo "  A legenda esta em legenda-shopee-video.txt."
  echo "  O passo a passo do app esta em roteiro.txt."
else
  echo "  ⚠️  a pasta de saida nao foi criada. Me mande o que apareceu acima."
fi
echo
echo "  Para ver a fila no celular, sirva a pasta $DEMO/saida:"
echo "     cd $DEMO/saida && python3 -m http.server 8080"
echo "  e abra http://SEU-IP-DO-VPS:8080/app-postagens.html"
echo
