#!/usr/bin/env node
/**
 * Audita a completude e a coerência do razão, mês a mês.
 *
 * A dashboard junta três fontes que se sobrepõem — fatura do cartão, holerite e
 * extrato da conta. Cada uma vê um pedaço, e o mesmo dinheiro às vezes aparece
 * em duas. Este script responde três perguntas que decidem se dá para confiar
 * no total de um mês:
 *
 *   1. O que falta? Mês com extrato mas sem holerite, fatura sem pagamento.
 *   2. O que está contado duas vezes? Crédito de salário somando com o provento
 *      do holerite, pagamento de fatura somando com as compras.
 *   3. O que não bate? Líquido do comprovante contra o crédito na conta,
 *      pagamento no extrato contra o pago da fatura.
 *
 * Não grava nada. É só leitura.
 *
 * Uso:  node scripts/conciliar.js
 */

const fs = require('fs');
const path = require('path');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const brl = v => `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
const emOrdem = m => MESES.indexOf(m.split('/')[0]) + 12 * +m.split('/')[1];
const soma = arr => Math.round(arr.reduce((s, t) => s + t.valor, 0) * 100) / 100;

const dados = JSON.parse(fs.readFileSync(ARQUIVO, 'utf8'));
const T = dados.fluxo_mensal.transacoes;
const faturas = dados.faturas_cartao || [];

const daFonte = (f, filtro) => T.filter(t => t.origem === f && (!filtro || filtro(t)));
const meses = [...new Set(T.map(t => t.mes_vencimento))].sort((a, b) => emOrdem(a) - emOrdem(b));

let alertas = 0;
const alerta = (...linhas) => { alertas++; linhas.forEach(l => console.log(l)); };

console.log('\n══════════════════════════════════════════════════════════════');
console.log('  CONCILIAÇÃO DAS FONTES');
console.log('══════════════════════════════════════════════════════════════\n');

// ---------- cobertura mês a mês ----------

console.log('Cobertura de cada mês:\n');
console.log('mês      cartão   holerite   extrato    receita      consumo');
console.log('-'.repeat(64));

const NAO_E_CONSUMO = ['pagamento', 'divida_parcelada', 'receita', 'ajuste', 'transferencia', 'emprestimo'];

meses.forEach(m => {
  const doMes = T.filter(t => t.mes_vencimento === m);
  const cartao = doMes.filter(t => (t.origem || '').startsWith('cartao_credito')).length;
  const folha = doMes.filter(t => t.origem === 'holerite_elektro').length;
  const extrato = doMes.filter(t => t.origem === 'extrato_itau').length;
  const receita = soma(doMes.filter(t => t.natureza === 'receita' && (t.ambito || 'pessoal') === 'pessoal'));
  const consumo = soma(doMes.filter(t => !NAO_E_CONSUMO.includes(t.natureza) && (t.ambito || 'pessoal') === 'pessoal'));

  console.log(
    `${m.padEnd(8)} ${String(cartao || '—').padStart(6)}   ${String(folha || '—').padStart(8)}   ` +
    `${String(extrato || '—').padStart(7)}  ${brl(receita).padStart(11)}  ${brl(consumo).padStart(12)}`
  );
});

// ---------- 1. o que falta ----------

console.log('\n\n▸ O QUE FALTA\n');

// Mes com credito de salario no extrato e sem holerite: a renda daquele mes esta
// apoiada so no credito, sem o detalhe dos descontos.
const mesesComHolerite = new Set(daFonte('holerite_elektro').map(t => t.mes_vencimento));
const creditosSalario = daFonte('extrato_itau', t => /^REMUNERACAO\/SALARIO/i.test(t.descricao_original || ''));
const semHolerite = [...new Set(creditosSalario.map(t => t.mes_vencimento))]
  .filter(m => !mesesComHolerite.has(m))
  .sort((a, b) => emOrdem(a) - emOrdem(b));

if (semHolerite.length) {
  alerta(`  Holerite faltando em ${semHolerite.length} mês(es) que têm crédito de salário na conta:`);
  semHolerite.forEach(m => {
    const v = soma(creditosSalario.filter(t => t.mes_vencimento === m));
    console.log(`     ${m.padEnd(7)} crédito de ${brl(v)} contando como receita, sem o detalhe dos descontos`);
  });
  console.log('     Com o comprovante, entra o bruto e cada desconto — e o consignado aparece.');
} else {
  console.log('  Todo mês com crédito de salário tem o holerite correspondente.');
}

// Quanto das faturas saiu por esta conta.
//
// Nao da para casar fatura a fatura: quando a fatura e paga a menor, o valor que
// sai da conta e menor que o total, e um casamento por valor exato acusaria
// falta onde nao ha. A conta que fecha e o total do periodo, cartao a cartao.
const pagamentosNoExtrato = daFonte('extrato_itau', t => t.categoria === 'pagamento_fatura');

if (pagamentosNoExtrato.length) {
  const datasExtrato = daFonte('extrato_itau').map(t => t.data).sort();
  const de = datasExtrato[0], ate = datasExtrato[datasExtrato.length - 1];

  const pagoNasFaturas = Math.round(faturas
    .filter(f => f.vencimento >= de && f.vencimento <= ate)
    .reduce((s, f) => s + (f.pago || 0), 0) * 100) / 100;
  const saiuDaConta = soma(pagamentosNoExtrato);
  const foraDaConta = Math.round((pagoNasFaturas - saiuDaConta) * 100) / 100;

  console.log('');
  console.log(`  Faturas pagas no período: ${brl(pagoNasFaturas)}`);
  console.log(`  Saiu por esta conta:      ${brl(saiuDaConta)}`);

  if (Math.abs(foraDaConta) > 1) {
    console.log(`  Pago por outra origem:    ${brl(foraDaConta)}`);
    console.log('     Esperado: o 0442 é o cartão de tráfego pago da Benetti UP, e a fatura');
    console.log('     dele sai da conta da empresa. Vira alerta só se você esperava que tudo');
    console.log('     saísse daqui.');
  }
}

// ---------- 2. o que estaria contado duas vezes ----------

console.log('\n\n▸ DUPLA CONTAGEM\n');

const duplicado = creditosSalario.filter(t =>
  t.natureza === 'receita' && mesesComHolerite.has(t.mes_vencimento));

if (duplicado.length) {
  alerta(`  ${duplicado.length} crédito(s) de salário contando como receita em mês que JÁ tem holerite:`);
  duplicado.forEach(t => console.log(`     ${t.mes_vencimento}  ${brl(t.valor)}  ${t.data}`));
  console.log('     Rode: node scripts/importar-holerites.js <pasta> --aplicar');
} else {
  console.log('  Nenhum crédito de salário somando com o provento do holerite.');
}

const pagamentoComoDespesa = daFonte('extrato_itau', t =>
  t.natureza === 'despesa' && /FATURA|PGTO MIN|CARTAO TUDOAZUL|INT AZUL/i.test(t.descricao_original || ''));
if (pagamentoComoDespesa.length) {
  console.log('');
  alerta(`  ${pagamentoComoDespesa.length} pagamento(s) de fatura contando como despesa:`);
  pagamentoComoDespesa.slice(0, 6).forEach(t =>
    console.log(`     ${t.mes_vencimento}  ${brl(t.valor).padStart(12)}  ${t.descricao_original}`));
} else {
  console.log('  Nenhum pagamento de fatura somando com as compras da própria fatura.');
}

// ---------- 3. o que não bate ----------

console.log('\n\n▸ O QUE NÃO BATE\n');

// Liquido do holerite contra o credito na conta.
//
// O liquido sai do lado em que o valor esta no comprovante — provento ou
// desconto —, nao da natureza. O desconto do adiantamento da PLR e "ajuste" e
// mesmo assim reduz o que cai na conta: contando so as despesas, marco fecharia
// R$ 3.098,09 a mais e pareceria divergencia dos dados.
const liquidoPorMes = {};
daFonte('holerite_elektro').forEach(t => {
  const sinal = t.tipo === 'entrada' ? 1 : -1;
  liquidoPorMes[t.mes_vencimento] = (liquidoPorMes[t.mes_vencimento] || 0) + sinal * t.valor;
});

let divergencias = 0;
Object.keys(liquidoPorMes).sort((a, b) => emOrdem(a) - emOrdem(b)).forEach(m => {
  const noExtrato = soma(creditosSalario.filter(t => t.mes_vencimento === m));
  if (!noExtrato) return;
  const liquido = Math.round(liquidoPorMes[m] * 100) / 100;
  const bate = Math.abs(liquido - noExtrato) < 0.02;
  if (!bate) {
    divergencias++;
    alerta(`  ${m}: holerite líquido ${brl(liquido)} · crédito na conta ${brl(noExtrato)} · diferença ${brl(noExtrato - liquido)}`);
  }
});
if (!divergencias) console.log('  Todo líquido de holerite bate com o crédito na conta.');

// Reconciliacao das faturas.
const erroFatura = faturas.filter(f => {
  const lancado = soma(T.filter(t =>
    (t.origem || '').startsWith('cartao_credito')
    && (t.cartao_final || '4846') === (f.cartao || '4846')
    && t.mes_vencimento === f.mes
    && t.natureza !== 'pagamento'));
  return Math.abs(lancado - f.cobrado) > 0.05;
});
console.log('');
if (erroFatura.length) {
  alerta(`  ${erroFatura.length} fatura(s) em que os lançamentos não somam o cobrado.`);
} else {
  console.log(`  As ${faturas.length} faturas reconciliam com os lançamentos.`);
}

// ---------- fecho ----------

console.log('\n' + '─'.repeat(64));
console.log(alertas === 0
  ? 'Razão íntegro: nada faltando, nada contado duas vezes, tudo batendo.\n'
  : `${alertas} ponto(s) de atenção acima.\n`);
