#!/usr/bin/env node
'use strict';
//
// Grava no financeiro.json a fatura do Itaú lida do PDF.
//
// Mesma disciplina do importador do Bradesco, e pelos mesmos motivos aprendidos
// lá:
//
//  * **o que é relido é substituído, não somado.** Reimportar a mesma fatura
//    depois de já ter uma foto do ciclo em aberto faria a soma dos lançamentos
//    passar do que a fatura cobra;
//  * **a purga vem antes de montar o índice de ids existentes.** Feita depois,
//    todo id repetido parece "já existe", o lançamento novo não chega a ser
//    gerado, e a purga apaga o antigo sem repor — foi assim que 9 faturas
//    ficaram com cabeçalho e zero compra;
//  * **nada é gravado se a fatura não fechar** — a conferência mora no leitor.
//
// Sem --aplicar, apenas simula.

const fs = require('fs');
const path = require('path');
const { ler, brl } = require('./ler-fatura-itau-pdf');

const aplicar = process.argv.includes('--aplicar');
const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
if (!alvos.length) {
  console.error('uso: node scripts/importar-fatura-itau-pdf.js <fatura.pdf> [...] [--aplicar]');
  process.exit(1);
}

const DIR = path.join(__dirname, '..', 'data');
const ARQ = path.join(DIR, 'financeiro.json');
const dados = JSON.parse(fs.readFileSync(ARQ, 'utf8'));

const MES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
// O mês da fatura vem do VENCIMENTO, nunca do ciclo: pelo regime de caixa, o
// que importa é quando o dinheiro sai da conta.
const mesDoVencimento = v => `${MES[+v.slice(5, 7) - 1]}/${v.slice(2, 4)}`;

const normalizar = d => String(d).toLowerCase().replace(/\s+/g, ' ').trim();
const regras = (JSON.parse(fs.readFileSync(path.join(DIR, 'regras-classificacao.json'), 'utf8')).regras || [])
  .map(r => ({ ...r, re: new RegExp(r.padrao, 'i') }));
const aplicarRegra = (descricao, valor) => regras.find(r => r.re.test(normalizar(descricao))
  && (r.valor === undefined || Math.abs(valor - r.valor) < 0.01)) || null;

const config = JSON.parse(fs.readFileSync(path.join(DIR, 'configuracoes.json'), 'utf8'));
const empresas = new Set((config.pessoas || []).filter(p => p.tipo === 'empresa').map(p => p.nome));

// O que já foi decidido para a mesma descrição continua valendo: classificação
// feita à mão é legítima e não pode ser apagada por uma reimportação.
const herdadoPor = {};
(dados.fluxo_mensal.transacoes || []).forEach(t => {
  if (t.origem !== 'cartao_credito_itau' || !t.categoria || t.categoria === 'nao_classificado') return;
  herdadoPor[normalizar(t.descricao)] = { categoria: t.categoria, pessoa: t.pessoa };
});

// A parcela de fatura renegociada não é consumo novo: as compras que geraram a
// dívida já foram contadas uma a uma na fatura em que aconteceram.
const DIVIDA_PARCELADA = /(parc fatura|parcela de ref|credito por parcelamento|cred parc fat)/i;

const lidas = alvos.map(a => ler(a));
const ruins = lidas.filter(f => f.erros.length);
if (ruins.length) {
  console.error('\n❌ Não gravei: fatura que não fecha não entra.\n');
  ruins.forEach(f => { console.error(`   ${f.arquivo}`); f.erros.forEach(e => console.error(`      ${e}`)); });
  process.exit(1);
}

const faturas = dados.faturas_cartao = dados.faturas_cartao || [];
let tx = dados.fluxo_mensal.transacoes;

// --- purga ANTES de montar o índice: ver o comentário do topo ---
const relidas = new Set(lidas.map(f => `${f.cabecalho.cartao}|${mesDoVencimento(f.cabecalho.vencimento)}`));
const antes = tx.length;
tx = dados.fluxo_mensal.transacoes = tx.filter(t => !relidas.has(t.fatura_origem));
const purgados = antes - tx.length;

let seq = 0;
const resumo = [];

lidas.forEach(f => {
  const c = f.cabecalho;
  const mes = mesDoVencimento(c.vencimento);
  const chave = `${c.cartao}|${mes}`;

  const novas = f.itens.map(item => {
    const natureza = DIVIDA_PARCELADA.test(item.descricao) ? 'divida_parcelada'
                   : item.valor < 0 ? 'estorno' : 'despesa';
    const regra = aplicarRegra(item.descricao, item.valor);
    const herdado = herdadoPor[normalizar(item.descricao)] || {};
    const pessoa = (regra && regra.pessoa) || herdado.pessoa || 'Juliane';
    const categoria = natureza === 'divida_parcelada' ? 'divida_parcelada'
                    : (regra && regra.categoria) || herdado.categoria || 'nao_classificado';
    return {
      id: `txn_pdf_${c.cartao}_${mes.replace('/', '')}_${String(++seq).padStart(4, '0')}`,
      data: item.data,
      tipo: item.valor >= 0 ? 'saida' : 'entrada',
      natureza,
      descricao: item.descricao,
      valor: item.valor,
      pessoa,
      ambito: empresas.has(pessoa) ? 'empresa' : 'pessoal',
      categoria,
      classificado_por: regra ? 'regra' : (herdado.categoria ? 'herdado' : null),
      conta_origem: 'Cartão de Crédito Itaú',
      cartao_final: c.cartao,
      conta_destino: 'Comerciante',
      status: 'confirmado',
      origem: 'cartao_credito_itau',
      mes_vencimento: mes,
      data_vencimento_fatura: c.vencimento,
      mes_referencia: mes,
      fatura_origem: chave,
      eh_parcelada: !!item.parcela,
      parcela_numero: item.parcela,
      parcela_total: item.de_parcelas,
      descricao_parcela: item.parcela ? `${item.parcela}/${item.de_parcelas}` : null,
      parcela_fonte: item.parcela ? 'pdf' : null,
      carga_id: 'fatura_itau_pdf',
    };
  });

  // A linha "Pagamento efetuado" quita a fatura ANTERIOR, mas vem impressa
  // dentro desta — igual no XLSX. Ela não é despesa (as compras que a geraram
  // já foram contadas uma a uma), e fica de fora do `cobrado`; mas precisa
  // existir, senão a fatura anterior fica sem nenhum pagamento registrado.
  if (c.pagamento_anterior) {
    novas.push({
      id: `txn_pdf_${c.cartao}_${mes.replace('/', '')}_pag`,
      data: c.pago_em || c.vencimento,
      tipo: 'entrada',
      natureza: 'pagamento',
      descricao: 'Pagamento via conta',
      valor: c.pagamento_anterior,
      pessoa: 'Juliane',
      ambito: 'pessoal',
      categoria: 'pagamento_fatura',
      classificado_por: null,
      conta_origem: 'Cartão de Crédito Itaú',
      cartao_final: c.cartao,
      conta_destino: 'Itaú',
      status: 'confirmado',
      origem: 'cartao_credito_itau',
      mes_vencimento: mes,
      data_vencimento_fatura: c.vencimento,
      mes_referencia: mes,
      fatura_origem: chave,
      eh_parcelada: false,
      parcela_numero: null,
      parcela_total: null,
      carga_id: 'fatura_itau_pdf',
    });
  }

  tx.push(...novas);

  // O cabeçalho: `cobrado` é a soma dos lançamentos do período (o que serve de
  // gasto); `total_fatura` é a obrigação de pagamento. Eles diferem quando há
  // saldo anterior rolado.
  // O pagamento não entra no cobrado: ele quita a fatura anterior.
  const cobrado = Math.round(novas.filter(t => t.natureza !== 'pagamento')
    .reduce((s, t) => s + t.valor, 0) * 100) / 100;
  const quitada = Math.abs((c.total_fatura || 0)) < 0.01;
  const cab = {
    cartao: c.cartao,
    mes,
    vencimento: c.vencimento,
    total_fatura: c.total_fatura,
    saldo_anterior: Math.round(((c.fatura_anterior || 0) + (c.pagamento_anterior || 0)) * 100) / 100,
    cobrado,
    pago: 0,
    em_aberto: c.total_fatura,
    situacao: quitada ? 'paga' : 'fechada',
    lancamentos: novas.length,
    fonte: path.basename(f.arquivo),
  };

  const i = faturas.findIndex(x => x.cartao === c.cartao && x.mes === mes);
  const anterior = i >= 0 ? faturas[i] : null;
  if (i >= 0) faturas[i] = { ...anterior, ...cab };
  else faturas.push(cab);

  resumo.push({ chave, mes, cab, anterior, novas: novas.length });
});

// Religa as parcelas da MESMA compra, inclusive as que vieram por outro
// caminho (XLSX) em faturas anteriores. A chave é a mesma de
// `importar-faturas-itau.js` (`chaveDaCompra`): data da compra + descrição +
// total de parcelas. Se ela mudar lá, tem de mudar aqui — sem isso a parcela
// 4/12 lida do PDF vira uma compra própria, e a numeração aparece com buraco.
const PARCELA_NA_DESCRICAO = /(\d{2})d(\d{2})/i;
const chaveDaCompra = t => {
  const desc = normalizar(t.descricao).replace(PARCELA_NA_DESCRICAO, 'NNdMM');
  return t.parcela_fonte === 'descricao'
    ? `recorrente|${desc}|${t.parcela_total}`
    : `${t.data}|${desc}|${t.parcela_total}`;
};

const porCompra = {};
tx.filter(t => t.origem === 'cartao_credito_itau' && t.eh_parcelada)
  .forEach(t => { (porCompra[chaveDaCompra(t)] = porCompra[chaveDaCompra(t)] || []).push(t); });

// **O PDF corta a descrição na largura da coluna**, e o XLSX não.
// "Parcela De Refinanciamento" vira "PARCELA DE REF"; "Parc Fatura Seg" vira
// "PARC FATURA SE". Como a descrição entra na chave, a parcela lida do PDF
// ganhava um grupo próprio e a mesma compra virava duas — a numeração aparecia
// com buraco e a previsão de quitação saía errada.
//
// O mesmo cartão, na mesma data de compra, com o mesmo número de parcelas, e
// com um texto que é começo do outro: é a mesma compra. O teste de prefixo é o
// que impede fundir duas compras de verdade que só coincidam em data e prazo.
{
  const mesmaCompra = (a, b) => {
    const [x, y] = [a.toLowerCase(), b.toLowerCase()];
    return x.startsWith(y) || y.startsWith(x);
  };
  const chaves = Object.keys(porCompra);
  chaves.forEach(k => {
    if (!porCompra[k]) return;
    const base = porCompra[k][0];
    chaves.forEach(o => {
      if (o === k || !porCompra[o] || !porCompra[k]) return;
      const outro = porCompra[o][0];
      if (outro.cartao_final === base.cartao_final
       && outro.data === base.data
       && outro.parcela_total === base.parcela_total
       && mesmaCompra(base.descricao, outro.descricao)) {
        porCompra[k].push(...porCompra[o]);
        delete porCompra[o];
      }
    });
  });
}

Object.values(porCompra).forEach(parcelas => {
  parcelas.sort((a, b) => a.parcela_numero - b.parcela_numero);
  const idCompra = parcelas.map(p => p.id_compra).find(Boolean) || `compra_${parcelas[0].id}`;
  const completa = parcelas.length === parcelas[0].parcela_total;
  const valorTotal = completa
    ? Math.round(parcelas.reduce((a, p) => a + p.valor, 0) * 100) / 100
    : Math.round(parcelas[0].valor * parcelas[0].parcela_total * 100) / 100;
  parcelas.forEach(p => {
    p.id_compra = idCompra;
    p.data_compra_original = p.data;
    p.valor_total_compra = valorTotal;
    p.valor_total_exato = completa;
    p.parcelas_no_periodo = parcelas.length;
  });
});

console.log(`\n=== FATURA ITAÚ EM PDF ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);
resumo.forEach(r => {
  console.log(`${r.chave} — vence ${r.cab.vencimento.split('-').reverse().join('/')}`);
  if (r.anterior) {
    console.log(`   antes:  ${brl(r.anterior.total_fatura || 0)} · ${r.anterior.lancamentos ?? '?'} lançamentos · ${r.anterior.situacao}`);
  } else {
    console.log('   antes:  não existia');
  }
  console.log(`   agora:  ${brl(r.cab.total_fatura)} · ${r.novas} lançamentos · ${r.cab.situacao}`);
  console.log(`   cobrado no período ${brl(r.cab.cobrado)} · saldo anterior ${brl(r.cab.saldo_anterior)}`);
});
console.log(`\n${purgados} lançamento(s) da leitura anterior substituídos, ${tx.length} no total.`);

const semRegra = lidas.flatMap(f => f.itens).filter(i => {
  const r = aplicarRegra(i.descricao, i.valor);
  return !r && !herdadoPor[normalizar(i.descricao)] && !DIVIDA_PARCELADA.test(i.descricao);
});
if (semRegra.length) {
  console.log(`\n${semRegra.length} lançamento(s) sem regra, em "nao_classificado":`);
  semRegra.forEach(i => console.log(`   ${brl(i.valor).padStart(14)}  ${i.descricao}`));
}

if (!aplicar) { console.log('\nRode com --aplicar para gravar.\n'); process.exit(0); }

fs.writeFileSync(ARQ, JSON.stringify(dados, null, 2));
console.log(`\n✅ Gravado em ${ARQ}\n`);
