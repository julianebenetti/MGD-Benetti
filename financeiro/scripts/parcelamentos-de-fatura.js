#!/usr/bin/env node
'use strict';
//
// Compilado dos parcelamentos de fatura, para a reclamação junto ao Itaú.
//
// A Juliane relatou (21/09/2026) que o Itaú vem parcelando faturas dela sem
// autorização. Ela reconhece o de 26/06 no Black — o primeiro, feito por ela —
// e não reconhece os posteriores.
//
// Este script **não decide o que foi ou não autorizado**: isso é conhecimento
// dela e mora em `configuracoes.json` → `parcelamentos_fatura[]`
// (`autorizado: true | false | null`). Aqui só se reúne o que os documentos
// dizem, para cada evento:
//
//   * quando aconteceu e qual fatura foi parcelada;
//   * quanto foi financiado, em quantas parcelas e a que custo;
//   * a taxa efetiva, calculada das próprias parcelas — não copiada de lugar
//     nenhum;
//   * quais parcelas já foram cobradas e em qual fatura, e quais ainda vêm;
//   * os encargos que vieram atrás (IOF, encargos de refinanciamento, multa,
//     mora).
//
// **Nada aqui é estimativa.** Todo valor sai de um lançamento gravado, e o
// script diz de qual fatura cada um veio. Onde falta documento, ele diz que
// falta em vez de completar a conta — é peça de reclamação, e número inventado
// aqui custaria caro.
//
// Só leitura. Uso:
//   node scripts/parcelamentos-de-fatura.js

const fs = require('fs');
const path = require('path');

const DIR = path.join(__dirname, '..', 'data');
const dados = JSON.parse(fs.readFileSync(path.join(DIR, 'financeiro.json'), 'utf8'));
const config = JSON.parse(fs.readFileSync(path.join(DIR, 'configuracoes.json'), 'utf8'));

const tx = dados.fluxo_mensal.transacoes || [];
const faturas = dados.faturas_cartao || [];

const brl = v => (v < 0 ? '-' : '') + 'R$ ' + Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const br = d => String(d || '').split('-').reverse().join('/');
const nomeCartao = c => {
  const k = (config.cartoes || []).find(x => x.final === c);
  return k ? `${k.nome} (final ${c})` : `cartão final ${c}`;
};

// O Itaú usa nomes diferentes para o mesmo mecanismo. "Seguro" em
// "Parc Fatura Seg" é o nome do produto de parcelamento de fatura, não uma
// apólice — isso já estava documentado e vale repetir na peça.
const CREDITO  = /^(credito por parcelamento|cred parc fat)/i;
const PARCELA  = /^(parcela de ref|parc fatura se)/i;
const ENTRADA  = /^pagamento parcelamento fatura/i;
const IOF      = /^iof refinanciamento/i;
const ENCARGO  = /^encargos refinanciamento/i;
const PUNICAO  = /^(multa|juros de mora)/i;

// Taxa efetiva a partir das próprias parcelas: a que iguala o valor financiado
// ao valor presente das parcelas. Calculada, não copiada.
function taxaMensal(pv, pmt, n) {
  if (!(pv > 0) || !(pmt > 0) || !(n > 0)) return null;
  const f = i => pmt * (1 - Math.pow(1 + i, -n)) / i - pv;
  let lo = 1e-6, hi = 5;
  if (f(lo) < 0) return null;
  for (let k = 0; k < 300; k++) { const m = (lo + hi) / 2; if (f(m) > 0) lo = m; else hi = m; }
  return (lo + hi) / 2;
}

// Um evento de parcelamento = cartão + data em que ele foi feito. Todas as
// peças (crédito, entrada, IOF e as parcelas) carregam essa mesma data.
const eventos = {};
tx.filter(t => t.cartao_final && (CREDITO.test(t.descricao || '') || PARCELA.test(t.descricao || '')
             || ENTRADA.test(t.descricao || '') || IOF.test(t.descricao || '')))
  .forEach(t => {
    const k = `${t.cartao_final}_${t.data}`;
    (eventos[k] = eventos[k] || { cartao: t.cartao_final, data: t.data, itens: [] }).itens.push(t);
  });

const lista = Object.entries(eventos)
  .map(([id, e]) => {
    const credito  = e.itens.find(t => CREDITO.test(t.descricao));
    const entrada  = e.itens.find(t => ENTRADA.test(t.descricao));
    const iof      = e.itens.find(t => IOF.test(t.descricao));
    const parcelas = e.itens.filter(t => PARCELA.test(t.descricao))
      .sort((a, b) => (a.parcela_numero || 0) - (b.parcela_numero || 0));
    if (!credito || !parcelas.length) return null;

    const financiado = Math.abs(credito.valor);
    const pmt = parcelas[0].valor;
    const n = parcelas[0].parcela_total || parcelas.length;
    // A dívida de verdade é o que sobrou da fatura; o IOF é custo somado a ela.
    const dividaReal = Math.round((financiado - Math.abs(iof ? iof.valor : 0)) * 100) / 100;

    const cadastro = (config.parcelamentos_fatura || []).find(x => x.id === id) || {};
    const i = taxaMensal(dividaReal, pmt, n);

    const cobradas = parcelas.map(p => p.parcela_numero).filter(Boolean);
    const faltam = [...Array(n).keys()].map(x => x + 1).filter(x => !cobradas.includes(x));

    return {
      id, cartao: e.cartao, data: e.data,
      financiado, dividaReal, entrada: entrada ? Math.abs(entrada.valor) : 0,
      iof: iof ? Math.abs(iof.valor) : 0,
      pmt, n, parcelas, cobradas, faltam,
      desembolso: Math.round((pmt * n + (entrada ? Math.abs(entrada.valor) : 0)) * 100) / 100,
      custo: Math.round((pmt * n - dividaReal) * 100) / 100,
      taxa: i,
      autorizado: cadastro.autorizado,
      nota: cadastro.observacao || null,
    };
  })
  .filter(Boolean);

// Parcelamento que ainda não gerou lançamento nenhum: a fatura já foi marcada
// como parcelada (`financiado_em_parcelas`) e o contrato existe em Dívidas, mas
// a primeira parcela só vai ser cobrada na fatura seguinte, que ainda não foi
// importada. Sem isto o compilado diria "3 parcelamentos" havendo 4.
faturas.filter(f => (f.financiado_em_parcelas || 0) > 0.05).forEach(f => {
  const jaTem = lista.some(p => p.cartao === f.cartao
    && Math.abs(p.dividaReal - f.financiado_em_parcelas) < 0.05);
  if (jaTem) return;
  const contrato = (dados.dividas || []).find(x =>
    `${x.nome || ''} ${x.observacao || ''}`.includes(f.mes) &&
    `${x.nome || ''} ${x.observacao || ''}`.includes(f.cartao));
  const pmt = contrato && contrato.parcela_mensal;
  const n = pmt ? Math.round((contrato.montante || 0) / pmt) : null;
  const cad = (config.parcelamentos_fatura || []).find(x => x.cartao === f.cartao
    && x.data && x.data >= f.vencimento) || {};
  lista.push({
    id: `${f.cartao}_${cad.data || f.vencimento}`,
    cartao: f.cartao, data: cad.data || f.vencimento,
    financiado: f.financiado_em_parcelas, dividaReal: f.financiado_em_parcelas,
    entrada: f.pago || 0, iof: 0,
    pmt: pmt || 0, n: n || 0, parcelas: [], cobradas: [],
    faltam: n ? [...Array(n).keys()].map(x => x + 1) : [],
    desembolso: Math.round(((pmt || 0) * (n || 0) + (f.pago || 0)) * 100) / 100,
    custo: Math.round(((pmt || 0) * (n || 0) - f.financiado_em_parcelas) * 100) / 100,
    taxa: pmt && n ? taxaMensal(f.financiado_em_parcelas, pmt, n) : null,
    autorizado: cad.autorizado,
    nota: cad.observacao || null,
    fatura: f,
  });
});

lista.sort((a, b) => a.data.localeCompare(b.data));

// ---------------------------------------------------------------- relatório

console.log('\n' + '='.repeat(74));
console.log('  PARCELAMENTOS DE FATURA — COMPILADO PARA O ITAÚ');
console.log('  gerado em ' + new Date().toLocaleString('pt-BR'));
console.log('='.repeat(74));

let totFin = 0, totCusto = 0, totNaoRec = 0, totCancelavel = 0;

lista.forEach((p, k) => {
  const selo = p.autorizado === true ? 'RECONHECIDO por ela'
             : p.autorizado === false ? 'NEGADO por ela'
             : 'NÃO RECONHECIDO — ela não se recorda de ter autorizado';

  console.log(`\n${'-'.repeat(74)}`);
  console.log(`${k + 1}. ${nomeCartao(p.cartao)} — parcelado em ${br(p.data)}`);
  console.log(`   ${selo}`);
  if (p.nota) console.log(`   ${p.nota}`);
  console.log('');

  // Qual fatura foi parcelada. A aritmética identifica melhor que a data: se
  // entrada + dívida refinanciada dá o total de uma fatura, é aquela, e de
  // quebra isso prova que a fatura INTEIRA foi parcelada. Sem casar, cai para a
  // fatura do cartão com vencimento mais próximo — e o relatório diz qual dos
  // dois critérios usou, porque a força da prova é diferente.
  const doCartao = faturas.filter(f => f.cartao === p.cartao);
  const alvo = Math.round((p.entrada + p.dividaReal) * 100) / 100;
  const porConta = doCartao.find(f => Math.abs((f.total_fatura || 0) - alvo) < 0.02);
  const porData = p.fatura || doCartao
    .slice().sort((a, b) => Math.abs(new Date(a.vencimento) - new Date(p.data))
                          - Math.abs(new Date(b.vencimento) - new Date(p.data)))[0];
  const fat = porConta || porData;
  p.faturaCasada = porConta || null;

  if (fat && porConta) {
    console.log(`   Fatura parcelada: ${fat.mes}, vencimento ${br(fat.vencimento)}, total ${brl(fat.total_fatura)}`);
    console.log(`      ✓ a fatura INTEIRA foi parcelada — entrada + dívida dá o total dela, ao centavo`);
  } else if (fat) {
    console.log(`   Fatura parcelada: provavelmente ${fat.mes}, vencimento ${br(fat.vencimento)}, total ${brl(fat.total_fatura)}`);
    console.log(`      ⚠ entrada + dívida (${brl(alvo)}) NÃO fecha com o total dessa fatura —`);
    console.log(`        ou só parte dela foi parcelada, ou falta a fatura certa. Pedir o extrato ao Itaú.`);
  } else {
    console.log(`   Fatura parcelada: nenhuma fatura importada deste cartão bate — falta o documento.`);
  }

  if (p.entrada) console.log(`   Entrada paga no dia .......... ${brl(p.entrada)}`);
  console.log(`   Dívida refinanciada .......... ${brl(p.dividaReal)}`);
  if (p.iof) console.log(`   IOF do refinanciamento ....... ${brl(p.iof)}`);
  console.log(`   Valor financiado ............. ${brl(p.financiado)}`);
  console.log(`   Parcelas ..................... ${p.n}x ${brl(p.pmt)} = ${brl(p.pmt * p.n)}`);
  console.log(`   Desembolso total ............. ${brl(p.desembolso)}`);
  console.log(`   CUSTO (juros + IOF) .......... ${brl(p.custo)}`);
  if (p.taxa) {
    console.log(`   Taxa efetiva ................. ${(p.taxa * 100).toFixed(2)}% ao mês  ·  ${((Math.pow(1 + p.taxa, 12) - 1) * 100).toFixed(2)}% ao ano`);
  }

  console.log('\n   Parcelas já cobradas:');
  p.parcelas.forEach(x => console.log(`      ${x.parcela_numero}/${x.parcela_total}  ${brl(x.valor)}  na fatura de ${x.mes_vencimento}`));
  if (p.faltam.length) {
    console.log(`   Parcelas ainda NÃO cobradas: ${p.faltam.join(', ')} de ${p.n}  —  ${brl(p.pmt * p.faltam.length)}`);
    console.log('      (é o que ainda dá para cancelar antes de ser lançado)');
  } else {
    console.log('   Todas as parcelas já foram cobradas.');
  }

  totFin += p.dividaReal;
  totCusto += p.custo;
  if (p.autorizado !== true) { totNaoRec += p.custo; totCancelavel += p.pmt * p.faltam.length; }
});

// Encargos que vieram atrás do parcelamento — pedaço separado da conta, porque
// não são o preço do crédito, são o preço de ele ter atrasado.
const extras = tx.filter(t => ENCARGO.test(t.descricao || '') || PUNICAO.test(t.descricao || ''));
if (extras.length) {
  console.log(`\n${'-'.repeat(74)}`);
  console.log('ENCARGOS COBRADOS DEPOIS (multa, mora e encargos de refinanciamento)');
  extras.sort((a, b) => a.data.localeCompare(b.data)).forEach(t =>
    console.log(`   ${br(t.data)}  ${nomeCartao(t.cartao_final).padEnd(46)} ${brl(t.valor).padStart(12)}  ${t.descricao}`));
  console.log(`   ${' '.repeat(60)}${brl(extras.reduce((s, t) => s + t.valor, 0)).padStart(12)}  total`);
}

console.log(`\n${'='.repeat(74)}`);
console.log('  RESUMO');
console.log('='.repeat(74));
console.log(`   Parcelamentos encontrados .................... ${lista.length}`);
console.log(`   Dívida total refinanciada ................... ${brl(totFin)}`);
console.log(`   Custo total (juros + IOF) ................... ${brl(totCusto)}`);
console.log(`   Custo dos que ela NÃO reconhece ............. ${brl(totNaoRec)}`);
console.log(`   Parcelas não reconhecidas ainda a cobrar .... ${brl(totCancelavel)}`);

// O que o compilado NÃO sabe, dito em vez de omitido.
const buracos = [];
lista.forEach(p => {
  if (p.faltam.length) buracos.push(`as parcelas ${p.faltam.join(', ')} do parcelamento de ${br(p.data)} (${nomeCartao(p.cartao)}) ainda não apareceram em nenhuma fatura importada`);
});
// Só é pendência a fatura que NÃO casou pela aritmética lá em cima. Antes esta
// checagem exigia vencimento igual à data do parcelamento, e acusava de
// faltante uma fatura que o próprio relatório tinha acabado de identificar — um
// compilado de reclamação não pode se contradizer.
lista.filter(p => !p.faturaCasada).forEach(p => buracos.push(
  `a fatura parcelada em ${br(p.data)} do ${nomeCartao(p.cartao)} não pôde ser identificada com certeza — entrada + dívida não fecha com nenhuma fatura importada`));

if (buracos.length) {
  console.log(`\n${'-'.repeat(74)}`);
  console.log('O QUE FALTA PARA O COMPILADO FICAR COMPLETO');
  buracos.forEach(b => console.log(`   · ${b}`));
}

console.log(`\n${'-'.repeat(74)}`);
console.log('O QUE PEDIR AO ITAÚ, PARA CADA PARCELAMENTO');
console.log('   · a gravação, o aceite no app ou o documento que registra a autorização,');
console.log('     com data e hora;');
console.log('   · o contrato do parcelamento, com taxa de juros, IOF e CET;');
console.log('   · o cancelamento das parcelas ainda não cobradas;');
console.log('   · o estorno dos juros e do IOF já cobrados no que não foi autorizado.');
console.log('');
console.log('   "Parc Fatura Seg" na fatura é o nome do produto de parcelamento do');
console.log('   Itaú — "Seguro" ali NÃO é uma apólice de seguro.');
console.log('');
