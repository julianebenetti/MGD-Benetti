#!/usr/bin/env bash
#
# Atualiza a dashboard financeira no VPS.
#
# É a única coisa que precisa rodar no servidor: puxa o que foi preparado no
# repositório e reinicia o serviço. Importação de fatura, regras de
# classificação e testes rodam no ambiente de desenvolvimento, não aqui.
#
#   cd /root/mgd-benetti/financeiro && ./atualizar.sh
#
set -euo pipefail

BRANCH="${BRANCH:-claude/financial-dashboard-pbj1ts}"
APP="${APP:-financeiro}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$RAIZ"

echo "→ Buscando atualizações de $BRANCH"
antes="$(git rev-parse HEAD)"
git pull --ff-only origin "$BRANCH"
depois="$(git rev-parse HEAD)"

if [ "$antes" = "$depois" ]; then
  echo "→ Nada novo. A dashboard já está na última versão."
  exit 0
fi

echo
echo "→ O que mudou:"
git log --oneline "$antes..$depois" | sed 's/^/   /'

# Dependência nova só aparece se package.json mudou
if git diff --name-only "$antes" "$depois" | grep -q '^financeiro/package.json$'; then
  echo
  echo "→ package.json mudou, instalando dependências"
  (cd financeiro && npm install --omit=dev --silent)
fi

echo
echo "→ Reiniciando $APP"
pm2 restart "$APP" --update-env

sleep 2
if curl -sf localhost:3001/api/health > /dev/null; then
  total="$(curl -s localhost:3001/api/dados | node -e '
    let e="";process.stdin.on("data",d=>e+=d).on("end",()=>{
      const t=(JSON.parse(e).fluxo_mensal||{}).transacoes||[];
      const g=t.filter(x=>x.natureza!=="pagamento");
      // Conferir contra o arquivo dá números diferentes se este total não
      // disser que as linhas de pagamento de fatura ficam de fora.
      const pag=t.length-g.length;
      console.log(`${g.length} lançamentos · R$ ${g.reduce((s,x)=>s+x.valor,0).toLocaleString("pt-BR",{minimumFractionDigits:2})}`);
      console.log(`   (${t.length} linhas no arquivo, menos ${pag} de pagamento de fatura)`);
    });')"
  echo "→ No ar: $total"
  echo
  echo "Pronto. Abra a dashboard e dê Ctrl+Shift+R para limpar o cache."
else
  echo "→ O serviço não respondeu. Veja o log com: pm2 logs $APP --lines 40"
  exit 1
fi
