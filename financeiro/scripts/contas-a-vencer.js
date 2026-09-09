#!/usr/bin/env node
//
// O que vence agora — versão de linha de comando do bloco de vencimentos do
// Painel, para a rotina de alerta no celular poder responder sem abrir a tela.
//
// Só leitura: não grava nada, em lugar nenhum.
//
//   node scripts/contas-a-vencer.js [--dias 3] [--hoje 2026-09-15]
//
// As regras são as mesmas da dashboard, e é de propósito que sejam:
//   - fatura de cartão com pagamento parado não entra no que ela tem de pagar,
//     mas nunca some da tela — sai num bloco à parte;
//   - conta cadastrada que a Benetti UP paga aparece para ser lembrada e fica
//     fora do total do caixa dela;
//   - conta recorrente que ainda não virou lançamento entra pela mediana do
//     histórico, sempre marcada como previsão;
//   - nada é dado como atrasado enquanto o extrato daquele mês estiver
//     incompleto ou não alcançar a data — falta de arquivo não é falta de
//     pagamento, e acusar errado é o jeito mais rápido de ela parar de
//     confiar no alerta.

const fs = require('fs');
const path = require('path');

const DIR = path.join(__dirname, '..', 'data');
const dados = JSON.parse(fs.readFileSync(path.join(DIR, 'financeiro.json'), 'utf8'));
const config = JSON.parse(fs.readFileSync(path.join(DIR, 'configuracoes.json'), 'utf8'));

const MES_ORDEM = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const ANO_DASHBOARD = 26;

const arg = (nome, padrao) => {
  const i = process.argv.indexOf('--' + nome);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : padrao;
};

const JANELA = parseInt(arg('dias', '3'), 10);
const HOJE = arg('hoje', new Date().toISOString().slice(0, 10));
const limite = new Date(HOJE + 'T00:00:00');
limite.setDate(limite.getDate() + JANELA);
const LIMITE = limite.toISOString().slice(0, 10);

const brl = v => 'R$ ' + v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const transacoes = (dados.fluxo_mensal || {}).transacoes || [];
const faturas = dados.faturas_cartao || [];
const noEscopo = mv => !!mv && (mv === 'A confirmar' || parseInt(mv.split('/')[1], 10) === ANO_DASHBOARD);
const veioDoCartao = t => (t.origem || '').startsWith('cartao_credito');
const ehPagamentoDeCartaoNoExtrato = t =>
  t.origem === 'extrato_itau' &&
  (/^Cart[ãa]o\s/i.test(t.descricao || '') ||
   /bradescard/i.test((t.descricao || '') + ' ' + (t.descricao_original || '')));

const pagamentoSuspenso = cartao =>
  (config.cartoes || []).some(c => c.final === cartao && c.pagamento_suspenso);

const CHAVE_RECORRENTE = d => String(d || '')
  .toLowerCase().replace(/\d+/g, '').replace(/[^a-zà-ú ]/gi, ' ')
  .replace(/\s+/g, ' ').trim();

const mediana = v => {
  if (!v.length) return 0;
  const o = [...v].sort((a, b) => a - b), m = Math.floor(o.length / 2);
  return o.length % 2 ? o[m] : (o[m - 1] + o[m]) / 2;
};

const saidasForaDoCartaoDoMes = mes => transacoes
  .filter(t => noEscopo(t.mes_vencimento) && t.mes_vencimento === mes
            && t.origem !== 'holerite_elektro' && !veioDoCartao(t)
            && !ehPagamentoDeCartaoNoExtrato(t) && t.valor > 0
            && (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'));

function perfilDasRecorrentes() {
  const porChave = {};
  transacoes
    .filter(t => noEscopo(t.mes_vencimento) && t.origem !== 'holerite_elektro'
              && !veioDoCartao(t) && t.valor > 0
              && (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'))
    .forEach(t => {
      const k = CHAVE_RECORRENTE(t.descricao);
      if (!k) return;
      (porChave[k] = porChave[k] || { exemplo: t, meses: {}, valores: [], dias: [] });
      porChave[k].meses[t.mes_vencimento] = true;
      porChave[k].valores.push(t.valor);
      if (t.data) porChave[k].dias.push(parseInt(t.data.split('-')[2], 10));
    });
  return Object.entries(porChave)
    .map(([k, v]) => ({
      chave: k, descricao: v.exemplo.descricao, categoria: v.exemplo.categoria,
      nMeses: Object.keys(v.meses).length,
      valor: Math.round(mediana(v.valores) * 100) / 100,
      minimo: Math.min(...v.valores), maximo: Math.max(...v.valores),
      dia: Math.round(mediana(v.dias)) || 15
    }))
    .filter(r => r.nMeses >= 3 && r.valor > 0);
}

function recorrentesFaltandoEm(mes) {
  const jaTem = new Set(saidasForaDoCartaoDoMes(mes).map(t => CHAVE_RECORRENTE(t.descricao)));
  const ano = 2000 + parseInt(mes.split('/')[1], 10);
  const iMes = MES_ORDEM.indexOf(mes.split('/')[0]) + 1;
  const data = dia => `${ano}-${String(iMes).padStart(2, '0')}-${String(Math.min(Math.max(dia || 15, 1), 28)).padStart(2, '0')}`;

  const doHistorico = perfilDasRecorrentes()
    .filter(r => !jaTem.has(r.chave))
    .map(r => ({ ...r, previsto: true, data: data(r.dia) }));

  const jaProjetado = new Set(doHistorico.map(r => r.chave));
  const cadastradas = (config.contas_recorrentes || [])
    .filter(c => c.ativa !== false && Number(c.valor) > 0)
    .map(c => ({
      chave: CHAVE_RECORRENTE(c.descricao) || ('cad ' + c.id),
      descricao: c.descricao, categoria: c.categoria, valor: Number(c.valor),
      dia: c.dia || 15, nMeses: null, cadastrada: true, forma: c.forma || null,
      fora_da_conta: (c.paga_por || 'juliane') !== 'juliane',
      previsto: true, data: data(c.dia)
    }))
    .filter(c => !jaTem.has(c.chave) && !jaProjetado.has(c.chave));

  return [...doHistorico, ...cadastradas];
}

// Até onde o extrato importado enxerga, e em que meses ele está furado. Sem
// essas duas guardas o alerta acusa de atraso conta que ela pagou e a
// dashboard só não viu — foi o erro que o fechamento do plano já cometeu uma vez.
// Só a linha que já movimentou a conta diz até onde o arquivo enxerga: um PIX
// agendado prova que o extrato é anterior àquela data, nunca que cobre até lá.
const extratoCobreAte = () => {
  const datas = transacoes
    .filter(t => t.origem === 'extrato_itau' && t.data && t.data <= HOJE
              && t.status !== 'agendado')
    .map(t => t.data).sort();
  return datas.length ? datas[datas.length - 1] : null;
};
const extratoIncompletoNoMes = mes => {
  const doMes = transacoes.filter(t => t.mes_vencimento === mes);
  if (!doMes.some(t => t.origem === 'holerite_elektro' && t.natureza === 'receita')) return false;
  return !doMes.some(t => t.origem === 'extrato_itau' && /Crédito do salário/i.test(t.descricao || ''));
};

// Os meses que a janela toca — ela pode atravessar a virada do mês.
const mesesDaJanela = () => {
  const vistos = [];
  for (let d = new Date(HOJE + 'T00:00:00'); d <= limite; d.setDate(d.getDate() + 1)) {
    const m = `${MES_ORDEM[d.getMonth()]}/${String(d.getFullYear()).slice(2)}`;
    if (!vistos.includes(m)) vistos.push(m);
  }
  return vistos;
};

const ateOndeSabe = extratoCobreAte();
const compromissos = [];

mesesDaJanela().forEach(mes => {
  faturas.filter(f => f.mes === mes).forEach(f => compromissos.push({
    quando: f.vencimento,
    // Mesmo rótulo da tabela de vencimentos, para o alerta e a tela nomearem
    // a mesma fatura do mesmo jeito.
    titulo: `Fatura ${f.cartao_descricao || 'cartão ' + f.cartao}`,
    valor: f.em_aberto > 0 ? f.em_aberto : f.total_fatura,
    quitado: !(f.em_aberto > 0),
    suspenso: f.em_aberto > 0 && pagamentoSuspenso(f.cartao),
    detalhe: f.pago > 0 ? `pago ${brl(f.pago)} de ${brl(f.total_fatura)}` : `total ${brl(f.total_fatura)}`,
    julgavel: true          // a fatura diz sozinha se foi paga: não depende do extrato
  }));

  saidasForaDoCartaoDoMes(mes).forEach(t => compromissos.push({
    quando: t.data,
    titulo: t.descricao,
    valor: t.valor,
    // 'agendado' é verdade no dia da importação, não para sempre: se a data
    // passou e o extrato lista a linha, o dinheiro saiu.
    quitado: t.data <= HOJE,
    detalhe: t.categoria,
    julgavel: true
  }));

  recorrentesFaltandoEm(mes).forEach(r => compromissos.push({
    quando: r.data,
    titulo: r.descricao,
    valor: r.valor,
    quitado: false,
    previsto: true,
    fora_da_conta: !!r.fora_da_conta,
    detalhe: r.cadastrada
      ? `conta cadastrada, todo dia ${r.dia}${r.forma ? ' por ' + r.forma : ''}`
      : r.minimo === r.maximo
        ? `valor fixo nos últimos ${r.nMeses} meses`
        : `mediana de ${r.nMeses} meses, variou de ${brl(r.minimo)} a ${brl(r.maximo)}`,
    // Previsão de conta paga por outro caixa, ou de mês com extrato furado ou
    // ainda não alcançado, não pode ser chamada de atraso.
    julgavel: !r.fora_da_conta && !extratoIncompletoNoMes(mes)
              && !!ateOndeSabe && r.data <= ateOndeSabe
  }));
});

const naJanela = compromissos
  .filter(c => c.valor > 0 && c.quando && c.quando <= LIMITE)
  .sort((a, b) => a.quando.localeCompare(b.quando));

const dataBr = d => d.split('-').reverse().join('/');
const atrasadas = naJanela.filter(c => !c.quitado && !c.suspenso && !c.fora_da_conta && c.quando < HOJE && c.julgavel);
const hoje     = naJanela.filter(c => !c.quitado && !c.suspenso && !c.fora_da_conta && c.quando === HOJE);
const proximas = naJanela.filter(c => !c.quitado && !c.suspenso && !c.fora_da_conta && c.quando > HOJE);
const paradas  = naJanela.filter(c => !c.quitado && c.suspenso);
const daEmpresa = naJanela.filter(c => !c.quitado && c.fora_da_conta);
const soma = l => l.reduce((s, c) => s + c.valor, 0);
const linha = c => `  ${dataBr(c.quando)}  ${brl(c.valor).padStart(12)}  ${c.titulo}${c.previsto ? '  [previsto: ' + c.detalhe + ']' : ''}`;

const precisaAvisar = atrasadas.length || hoje.length || proximas.length;
const out = [];
out.push(`Contas a vencer — hoje ${dataBr(HOJE)}, janela de ${JANELA} dia(s) (até ${dataBr(LIMITE)})`);
out.push(`AVISAR: ${precisaAvisar ? 'SIM' : 'NAO'}`);
out.push('');

if (atrasadas.length) {
  // "Venceu e não apareceu no extrato" é o que a dashboard de fato sabe.
  // "Você não pagou" é conclusão que ela não tem como sustentar — e uma
  // acusação errada num alerta de celular queima o alerta inteiro.
  out.push(`JÁ VENCEU e não apareceu no extrato — ${atrasadas.length} conta(s), ${brl(soma(atrasadas))}`);
  atrasadas.forEach(c => out.push(linha(c)));
  out.push('');
}
if (hoje.length) {
  out.push(`VENCE HOJE — ${hoje.length} conta(s), ${brl(soma(hoje))}`);
  hoje.forEach(c => out.push(linha(c)));
  out.push('');
}
if (proximas.length) {
  out.push(`PRÓXIMOS ${JANELA} DIAS — ${proximas.length} conta(s), ${brl(soma(proximas))}`);
  proximas.forEach(c => out.push(linha(c)));
  out.push('');
}
if (!precisaAvisar) out.push('Nada a pagar nesta janela.\n');

if (daEmpresa.length) {
  out.push(`Fora do seu caixa — paga pela Benetti UP, ${brl(soma(daEmpresa))}:`);
  daEmpresa.forEach(c => out.push(linha(c)));
  out.push('');
}
if (paradas.length) {
  out.push(`Com pagamento parado por decisão dela, ${brl(soma(paradas))} (segue sendo cobrado, o saldo cresce):`);
  paradas.forEach(c => out.push(linha(c)));
  out.push('');
}

// A idade do dado importa mais que o número: alerta apoiado em extrato velho
// promete um mês mais barato do que ele é.
out.push(`Extrato importado vai até ${ateOndeSabe ? dataBr(ateOndeSabe) : 'nenhuma data'}.`);
const furados = mesesDaJanela().filter(extratoIncompletoNoMes);
if (furados.length) out.push(`Extrato incompleto em ${furados.join(', ')} — nada desses meses foi dado como atrasado.`);

console.log(out.join('\n'));
