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

# Backup dos dados vivos antes de qualquer coisa. financeiro.json e os
# demais são editados direto pela Juliane na tela — git protege contra o
# pull sobrescrever uma edição não commitada (ele recusa em vez de
# descartar), mas isso só ajuda se o pull realmente rodar até o fim; se
# travar no meio ou o erro passar despercebido, o backup é a rede de
# segurança de qualquer jeito.
mkdir -p financeiro/data/backups-deploy
carimbo="$(date +%Y%m%d-%H%M%S)"
for arq in financeiro.json configuracoes.json cargas.json apontamentos.json classificacoes.json; do
  [ -f "financeiro/data/$arq" ] && cp "financeiro/data/$arq" "financeiro/data/backups-deploy/${arq%.json}-$carimbo.json"
done

# A tela edita financeiro.json (e outros arquivos de dados) direto no
# working tree, sem passar por commit — então quase todo deploy encontra
# alguma edição pendente. Antes isso exigia rodar git stash na mão antes
# de chamar este script; agora o próprio script guarda e devolve sozinho,
# então voltar a bastar "deploy" puro (Juliane, 29/08).
stashed=0
if [ -n "$(git status --porcelain)" ]; then
  echo "→ Guardando edição pendente da tela antes de puxar"
  git stash push -u -m "atualizar.sh $carimbo"
  stashed=1
fi

# Devolve a edição guardada, se houver — chamada em todo caminho de saída
# a partir daqui, com ou sem sucesso, pra nunca deixar a edição perdida
# dentro do stash sem avisar.
devolver_stash() {
  if [ "$stashed" = 1 ]; then
    echo "→ Devolvendo a edição pendente que tinha sido guardada"
    if ! git stash pop; then
      echo
      echo "→ ATENÇÃO: a edição não voltou sozinha (conflito no merge)."
      echo "  Ela continua guardada — rode 'git stash list' e 'git stash show -p'"
      echo "  pra ver o que é, e resolva com cuidado antes de mexer em mais nada."
      return 1
    fi
  fi
  return 0
}

echo "→ Buscando atualizações de $BRANCH"
antes="$(git rev-parse HEAD)"
if ! git pull --ff-only origin "$BRANCH"; then
  echo
  echo "→ O pull foi recusado mesmo depois de guardar a edição pendente —"
  echo "  provavelmente a própria branch remota diverge da local (não é"
  echo "  fast-forward). O backup de agora está em"
  echo "  financeiro/data/backups-deploy/*-$carimbo.json se precisar conferir."
  devolver_stash
  exit 1
fi
depois="$(git rev-parse HEAD)"

if [ "$antes" = "$depois" ]; then
  echo "→ Nada novo. A dashboard já está na última versão."
  devolver_stash
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
      // Nem toda linha do arquivo e gasto. Alem do pagamento de fatura, agora ha
      // receita, transferencia entre contas, parcela de divida e emprestimo
      // tomado — somar tudo daria um numero que nao significa nada. Tem de
      // casar com NAO_E_CONSUMO no index.html.
      const fora=["pagamento","divida_parcelada","receita","ajuste","transferencia","emprestimo"];
      const brl=v=>"R$ "+v.toLocaleString("pt-BR",{minimumFractionDigits:2});
      const pessoal=x=>(x.ambito||"pessoal")==="pessoal";
      const gasto=t.filter(x=>!fora.includes(x.natureza));
      const receita=t.filter(x=>x.natureza==="receita"&&pessoal(x));
      console.log(`${t.length} lançamentos`);
      console.log(`   gasto ${brl(gasto.reduce((s,x)=>s+x.valor,0))} em ${gasto.length} linhas`);
      console.log(`   receita pessoal ${brl(receita.reduce((s,x)=>s+x.valor,0))} em ${receita.length} linhas`);
      console.log(`   ${t.length-gasto.length-receita.length} linhas fora dos totais: pagamento de fatura, transferência e dívida`);
    });')"
  echo "→ No ar: $total"
  echo
  devolver_stash
  echo "Pronto. Abra a dashboard e dê Ctrl+Shift+R para limpar o cache."
else
  echo "→ O serviço não respondeu. Veja o log com: pm2 logs $APP --lines 40"
  devolver_stash
  exit 1
fi
