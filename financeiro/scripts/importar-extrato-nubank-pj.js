#!/usr/bin/env node
'use strict';
//
// Lê o extrato da conta PJ da Benetti UP no Nubank (ag. 0001, c/c 977727920-1).
//
// A Benetti UP já era uma leitura separada na dashboard — o seletor do topo, a
// pessoa cadastrada, o campo `ambito` em 456 lançamentos de 2026. O que faltava
// era a CONTA dela: tudo que a tela sabia da empresa tinha entrado pelo cartão
// pessoal e pelo extrato do Itaú, ou seja, só o que vaza para o lado pessoal.
// O efeito disso era uma empresa que só aparecia gastando: R$ 188 mil de
// despesa no cartão e **nenhuma entrada** — a receita das processadoras (SHPP,
// depois Maree) cai aqui e não era lida em lugar nenhum.
//
// O risco desta fonte é contar duas vezes, e ele é maior aqui do que em
// qualquer outra: quase todo movimento grande desta conta tem a outra ponta já
// lançada. Três regras cuidam disso, e todas seguem o que já valia no extrato
// do Itaú:
//
//   * **pagamento de fatura** (Pix para o Itaú Holding) é `transferencia` — as
//     compras já estão lançadas uma a uma na fatura do 0442/3794;
//   * **dinheiro indo da empresa para a Juliane** é `despesa`/`pro_labore`
//     aqui, porque o extrato pessoal já lança a mesma quantia como receita
//     dela. Marcar como transferência dos dois lados faria o consolidado
//     ("Tudo somado") ganhar uma receita que não existe: esse dinheiro já foi
//     contado quando a processadora pagou;
//   * **dinheiro indo da Juliane para a empresa** é `transferencia` dos dois
//     lados — é aporte de capital, não venda. Chamar de receita inventaria
//     faturamento feito do próprio bolso dela.
//
// E a conferência de sempre: o saldo impresso tem de ser reproduzido pelos
// movimentos lidos, dia a dia e no total. Sem isso não grava.
//
// Sem --aplicar, apenas simula.

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const aplicar = process.argv.includes('--aplicar');
const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
if (!alvos.length) {
  console.error('uso: node scripts/importar-extrato-nubank-pj.js <extrato.pdf> [...] [--aplicar]');
  process.exit(1);
}

const num = s => parseFloat(String(s).replace(/\./g, '').replace(',', '.'));
const brl = v => (v < 0 ? '-' : '') + 'R$ ' + Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const MES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const MES_PDF = { JAN: 1, FEV: 2, MAR: 3, ABR: 4, MAI: 5, JUN: 6, JUL: 7, AGO: 8, SET: 9, OUT: 10, NOV: 11, DEZ: 12 };
const mesDe = d => `${MES[+d.slice(5, 7) - 1]}/${d.slice(2, 4)}`;

// ---------- regras ----------
//
// A ordem importa: a primeira que casar vence.
const REGRAS = [
  {
    // Pix para o Itaú Holding é pagamento de fatura do 0442/3794. Contar como
    // despesa somaria de novo compras que a fatura já lança linha a linha.
    padrao: /ITAU UNIBANCO HOLDING/i,
    natureza: 'transferencia', categoria: 'pagamento_fatura',
    descricao: 'Pagamento de fatura de cartão (Itaú)',
  },
  {
    // Dinheiro da empresa para a Juliane: o extrato pessoal já lança a entrada.
    padrao: /JULIANE FERREIRA BENETTI/i, sentido: 'saida',
    natureza: 'despesa', categoria: 'pro_labore',
    descricao: 'Retirada da Benetti UP para a Juliane',
  },
  {
    // Dinheiro da Juliane para a empresa: aporte, não venda.
    padrao: /JULIANE FERREIRA BENETTI/i, sentido: 'entrada',
    natureza: 'transferencia', categoria: 'aporte_na_empresa',
    descricao: 'Aporte da Juliane na Benetti UP',
  },
  {
    // A receita de verdade da empresa. SHPP primeiro, Maree depois — troca de
    // processadora confirmada pela Juliane, não queda de venda.
    padrao: /MAREE|SHPP|SHOPEE/i, sentido: 'entrada',
    natureza: 'receita', categoria: 'vendas',
    descricao: 'Repasse da processadora (vendas de afiliado)',
  },
  {
    padrao: /DAS-SIMPLES NACIONAL|SIMPLES NACIONAL/i,
    natureza: 'despesa', categoria: 'imposto_empresa',
    descricao: 'DAS — Simples Nacional',
  },
  {
    padrao: /STIMA CONTABIL/i,
    natureza: 'despesa', categoria: 'contabilidade',
    descricao: 'Contabilidade STIMA',
  },
  {
    padrao: /RECEITA FEDERAL/i,
    natureza: 'despesa', categoria: 'imposto_empresa',
    descricao: 'Receita Federal',
  },
  {
    padrao: /APLICA[CÇ][AÃ]O|RDB|RESGATE/i,
    natureza: 'transferencia', categoria: 'aplicacao',
    descricao: 'Aplicação / resgate',
  },
];

const regraDe = (texto, sentido) => REGRAS.find(r => r.padrao.test(texto)
  && (!r.sentido || r.sentido === sentido)) || null;

// ---------- leitura ----------

const DIA = /^(\d{2})\s+([A-Z]{3})\s+(\d{4})\s+Total de (entradas|sa[íi]das)/i;
const TOTAL = /^Total de (entradas|sa[íi]das)\s+[+-]?\s*([\d.]+,\d{2})/i;
const SALDO_DIA = /^Saldo do dia\s+(-?[\d.]+,\d{2})/i;
// "Transferência recebida pelo Pix   NOME - CNPJ - BANCO    1.234,56"
const MOV = /^(Transfer[êe]ncia (?:recebida|enviada) pelo Pix|Pagamento de boleto efetuado|Compra no d[ée]bito|Dep[óo]sito[^\d]*?|Resgate[^\d]*?|Aplica[cç][ãa]o[^\d]*?)\s{2,}(.+?)\s{2,}([\d.]+,\d{2})$/i;

function ler(arquivo) {
  const texto = execFileSync('pdftotext', ['-layout', arquivo, '-'], { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 })
    .replace(/\f/g, '\n');
  const linhas = texto.split('\n').map(l => l.replace(/\s+$/, ''));

  const mAg = texto.match(/Ag[êe]ncia\s+(\d+)\s+Conta\s*\n?\s*([\d-]+)/i);
  const mSaldo = texto.match(/Saldo inicial\s+(-?[\d.]+,\d{2})/i);
  const mFinal = texto.match(/Saldo final do per[íi]odo\s+(-?[\d.]+,\d{2})/i);
  const mPeriodo = texto.match(/(\d{1,2}) DE ([A-ZÇ]+) DE (\d{4}) a (\d{1,2}) DE ([A-ZÇ]+) DE (\d{4})/i);
  const mEmitido = texto.match(/Extrato gerado dia (\d{1,2}) de ([a-zç]+) de (\d{4})/i);

  const itens = [];
  const dias = [];
  let dataAtual = null, sentido = null;

  linhas.forEach(linha => {
    const t = linha.trim();
    if (!t) return;

    const d = t.match(DIA);
    if (d) {
      dataAtual = `${d[3]}-${String(MES_PDF[d[2].toUpperCase()]).padStart(2, '0')}-${d[1]}`;
      sentido = /entrada/i.test(d[4]) ? 'entrada' : 'saida';
      return;
    }
    const tt = t.match(TOTAL);
    if (tt && dataAtual) { sentido = /entrada/i.test(tt[1]) ? 'entrada' : 'saida'; return; }

    const sd = t.match(SALDO_DIA);
    if (sd && dataAtual) { dias.push({ data: dataAtual, saldo: num(sd[1]) }); return; }

    const m = t.match(MOV);
    if (!m || !dataAtual) return;
    itens.push({
      data: dataAtual,
      sentido,
      tipoMovimento: m[1].trim(),
      contraparte: m[2].replace(/\s+/g, ' ').trim(),
      valor: num(m[3]),
    });
  });

  return {
    arquivo,
    agencia: mAg ? mAg[1] : null,
    conta: mAg ? mAg[2] : null,
    saldoInicial: mSaldo ? num(mSaldo[1]) : null,
    saldoFinal: mFinal ? num(mFinal[1]) : null,
    periodo: mPeriodo ? mPeriodo[0] : null,
    emitidoEm: mEmitido ? mEmitido[0] : null,
    itens, dias,
  };
}

// A conferência: partindo do saldo inicial, cada "Saldo do dia" impresso tem de
// ser reproduzido pelos movimentos lidos até ali. Um movimento que a leitura
// não pegou aparece como diferença no primeiro dia seguinte.
function conferir(e) {
  const falhas = [];
  let saldo = e.saldoInicial;
  e.dias.forEach(d => {
    e.itens.filter(i => i.data === d.data)
      .forEach(i => { saldo += i.sentido === 'entrada' ? i.valor : -i.valor; });
    if (Math.abs(saldo - d.saldo) > 0.01) {
      falhas.push({ data: d.data, lido: d.saldo, calculado: Math.round(saldo * 100) / 100 });
      saldo = d.saldo; // segue do impresso, para não propagar o erro
    }
  });
  const fim = e.dias.length ? e.dias[e.dias.length - 1].saldo : e.saldoInicial;
  const fechaNoTotal = e.saldoFinal == null || Math.abs(fim - e.saldoFinal) <= 0.01;
  return { falhas, fechaNoTotal, saldoFinalLido: fim };
}

// ---------- execução ----------

const extratos = alvos.map(ler);

console.log(`\n=== EXTRATO NUBANK PJ — BENETTI UP ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);

let impede = false;
extratos.forEach(e => {
  const c = conferir(e);
  console.log(`${path.basename(e.arquivo)}`);
  console.log(`   ag. ${e.agencia || '?'} c/c ${e.conta || '?'} · ${e.itens.length} movimentos · ${e.periodo || '?'}`);
  console.log(`   saldo inicial ${brl(e.saldoInicial)} → final ${brl(e.saldoFinal)}`);
  if (c.falhas.length) {
    impede = true;
    console.log(`   ⚠️  o saldo do dia não fecha em ${c.falhas.length} dia(s):`);
    c.falhas.forEach(f => console.log(`      ${f.data.split('-').reverse().join('/')}  extrato diz ${brl(f.lido)}, a soma dá ${brl(f.calculado)}`));
  } else if (!c.fechaNoTotal) {
    impede = true;
    console.log(`   ⚠️  o último saldo do dia (${brl(c.saldoFinalLido)}) não bate com o saldo final do período (${brl(e.saldoFinal)})`);
  } else {
    console.log('   ✓ fecha: todo saldo impresso é reproduzido pelos movimentos lidos');
  }
});

if (impede && aplicar) {
  console.error('\n❌ Não gravei: o saldo do extrato não fecha com os movimentos lidos.');
  console.error('   Isso quase sempre é linha que a leitura não pegou. Corrija o leitor antes de importar.\n');
  process.exit(1);
}

const DIR = path.join(__dirname, '..', 'data');
const ARQ = path.join(DIR, 'financeiro.json');
const dados = JSON.parse(fs.readFileSync(ARQ, 'utf8'));

const transacoes = [];
let semRegra = 0;
extratos.forEach(e => {
  e.itens.forEach((i, n) => {
    const alvo = `${i.tipoMovimento} ${i.contraparte}`;
    const r = regraDe(alvo, i.sentido);
    if (!r) semRegra++;
    const valor = i.sentido === 'entrada' ? -Math.abs(i.valor) : Math.abs(i.valor);
    // Sinal: o resto da base usa positivo para saída (gasto) e negativo para
    // entrada, e `receita` guarda o valor positivo. Mantido igual aqui.
    const natureza = r ? r.natureza : (i.sentido === 'entrada' ? 'receita' : 'despesa');
    transacoes.push({
      id: `txn_nubankpj_${i.data.replace(/-/g, '')}_${String(n).padStart(3, '0')}`,
      data: i.data,
      tipo: i.sentido === 'entrada' ? 'entrada' : 'saida',
      natureza,
      descricao: r ? r.descricao : `${i.tipoMovimento} — ${i.contraparte.split(' - ')[0]}`,
      descricao_original: alvo,
      valor: natureza === 'receita' ? Math.abs(i.valor) : valor,
      pessoa: 'Benetti UP',
      ambito: 'empresa',
      categoria: r ? r.categoria : 'nao_classificado',
      classificado_por: r ? 'regra' : null,
      conta_origem: 'Nubank PJ — Benetti UP',
      conta_destino: i.contraparte.split(' - ')[0],
      status: 'confirmado',
      origem: 'extrato_nubank_pj',
      mes_vencimento: mesDe(i.data),
      mes_referencia: mesDe(i.data),
      eh_parcelada: false,
      carga_id: 'extrato_nubank_pj',
    });
  });
});

// Mesclagem: o que é relido é substituído, não acrescentado — mesma regra dos
// outros importadores. O período relido é o que os arquivos cobrem.
const mesesRelidos = new Set(transacoes.map(t => t.mes_vencimento));
const antes = dados.fluxo_mensal.transacoes.length;
dados.fluxo_mensal.transacoes = dados.fluxo_mensal.transacoes
  .filter(t => !(t.origem === 'extrato_nubank_pj' && mesesRelidos.has(t.mes_vencimento)));
const substituidos = antes - dados.fluxo_mensal.transacoes.length;
dados.fluxo_mensal.transacoes.push(...transacoes);

const porCategoria = {};
transacoes.forEach(t => {
  const k = `${t.natureza} / ${t.categoria}`;
  porCategoria[k] = (porCategoria[k] || 0) + Math.abs(t.valor);
});

console.log('\nO que vai entrar:');
Object.entries(porCategoria).sort((a, b) => b[1] - a[1])
  .forEach(([k, v]) => console.log(`   ${brl(v).padStart(14)}   ${k}`));

const receita = transacoes.filter(t => t.natureza === 'receita').reduce((s, t) => s + Math.abs(t.valor), 0);
const despesa = transacoes.filter(t => t.natureza === 'despesa').reduce((s, t) => s + Math.abs(t.valor), 0);
console.log(`\n   receita da empresa ${brl(receita)} · despesa ${brl(despesa)} · margem ${brl(receita - despesa)}`);
console.log(`   (transferência fica fora dos dois: é dinheiro que a outra ponta já lança)`);

if (semRegra) console.log(`\n${semRegra} movimento(s) sem regra, em "nao_classificado".`);
console.log(`\n${substituidos} lançamento(s) desta conta substituídos, ${transacoes.length} gravados, ${dados.fluxo_mensal.transacoes.length} no total.`);

if (!aplicar) { console.log('\nRode com --aplicar para gravar.\n'); process.exit(0); }

fs.writeFileSync(ARQ, JSON.stringify(dados, null, 2));
console.log(`\n✅ Gravado em ${ARQ}\n`);
