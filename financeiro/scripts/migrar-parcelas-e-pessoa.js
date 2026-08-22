#!/usr/bin/env node
/**
 * Migração de dados do financeiro.json
 *
 *  1. Renomeia pessoa "Ambos" -> "Família"
 *  2. Consolida compras parceladas: linhas idênticas (mesma data, valor e
 *     descrição) que hoje ocupam todas o mesmo mês de fatura passam a ser
 *     parcelas numeradas, distribuídas em meses de fatura consecutivos.
 *  3. Marca estornos e as compras totalmente canceladas.
 *
 * Uso:
 *   node scripts/migrar-parcelas-e-pessoa.js --dry-run   (só relatório)
 *   node scripts/migrar-parcelas-e-pessoa.js --aplicar   (grava)
 */

const fs = require('fs');
const path = require('path');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const aplicar = process.argv.includes('--aplicar');
// Realocar o mês de fatura das parcelas é uma inferência, não um dado observado:
// depende de saber de qual fatura cada linha veio, informação que o importador
// perdeu. Fica desligado por padrão até termos as faturas originais.
const realocarMeses = process.argv.includes('--realocar-meses');

// ---------- helpers de mês de fatura ----------

function parseMesVenc(mv) {
  const [mes, ano] = mv.split('/');
  return { mes: MESES.indexOf(mes), ano: 2000 + parseInt(ano, 10) };
}

function formatMesVenc({ mes, ano }) {
  return `${MESES[mes]}/${String(ano).slice(2)}`;
}

function somarMeses(mv, n) {
  const { mes, ano } = parseMesVenc(mv);
  const total = mes + n;
  return formatMesVenc({ mes: ((total % 12) + 12) % 12, ano: ano + Math.floor(total / 12) });
}

// Datas de vencimento reais observadas nos dados; para meses futuros usa dia 27.
function construirMapaVencimento(transacoes) {
  const mapa = {};
  transacoes.forEach(t => {
    if (t.mes_vencimento && t.data_vencimento_fatura) mapa[t.mes_vencimento] = t.data_vencimento_fatura;
  });
  return mapa;
}

function dataVencimentoPara(mv, mapa) {
  if (mapa[mv]) return mapa[mv];
  const { mes, ano } = parseMesVenc(mv);
  return `${ano}-${String(mes + 1).padStart(2, '0')}-27`;
}

// ---------- normalização de descrição ----------

const PREFIXOS_ESTORNO = [/^Canc Parcela Sem Juros - /i, /^Cancelamento Parcial De Compra - /i, /^Estorno de /i];

function ehEstorno(t) {
  return t.valor < 0 || PREFIXOS_ESTORNO.some(re => re.test(t.descricao));
}

function descricaoBase(desc) {
  let d = desc;
  PREFIXOS_ESTORNO.forEach(re => { d = d.replace(re, ''); });
  return d.trim().toLowerCase();
}

// ---------- migração ----------

const dados = JSON.parse(fs.readFileSync(ARQUIVO, 'utf8'));
const transacoes = dados.fluxo_mensal.transacoes;
const mapaVenc = construirMapaVencimento(transacoes);

const relatorio = { pessoaRenomeada: 0, comprasParceladas: 0, linhasParcela: 0, mesesCorrigidos: 0, estornosMarcados: 0, comprasCanceladas: 0, mesesNaoConfiaveis: 0 };

// --- 1. Ambos -> Família ---
transacoes.forEach(t => {
  if (t.pessoa === 'Ambos') { t.pessoa = 'Família'; relatorio.pessoaRenomeada++; }
});

// --- 2. Identificar descrições totalmente estornadas ---
const liquidoPorDescricao = {};
transacoes.forEach(t => {
  const base = descricaoBase(t.descricao);
  liquidoPorDescricao[base] = (liquidoPorDescricao[base] || 0) + t.valor;
});
const totalmenteCanceladas = new Set(
  Object.entries(liquidoPorDescricao).filter(([, v]) => Math.abs(v) < 0.05).map(([k]) => k)
);

// --- 3. Marcar estornos ---
transacoes.forEach(t => {
  if (ehEstorno(t)) {
    t.natureza = 'estorno';
    relatorio.estornosMarcados++;
    if (totalmenteCanceladas.has(descricaoBase(t.descricao))) t.compra_cancelada = true;
  } else {
    t.natureza = 'despesa';
    if (totalmenteCanceladas.has(descricaoBase(t.descricao))) {
      t.compra_cancelada = true;
      relatorio.comprasCanceladas++;
    }
  }
});

// --- 4. Consolidar parcelamentos ---
// Agrupa apenas despesas positivas não canceladas, por data+valor+descrição.
// Agrupa por data + descricao. O valor NAO entra na chave porque a ultima
// parcela costuma trazer alguns centavos de ajuste de arredondamento
// (ex.: 4x R$ 1.133,33 + 1x R$ 1.133,35), e exigir valor identico faria a
// parcela final ficar de fora da compra a que pertence.
const grupos = {};
transacoes.forEach((t, idx) => {
  if (t.natureza !== 'despesa' || t.compra_cancelada) return;
  const chave = `${t.data}|${t.descricao}`;
  (grupos[chave] = grupos[chave] || []).push(idx);
});

// Dentro de um grupo, so sao parcelas da mesma compra os lancamentos de valor
// equivalente (ate 5 centavos de diferenca). Valores distintos no mesmo dia e
// no mesmo estabelecimento sao compras separadas.
function separarPorValor(indices) {
  const blocos = [];
  indices.forEach(idx => {
    const v = transacoes[idx].valor;
    const bloco = blocos.find(b => Math.abs(transacoes[b[0]].valor - v) <= 0.05);
    if (bloco) bloco.push(idx); else blocos.push([idx]);
  });
  return blocos;
}

Object.entries(grupos).forEach(([chave, todosIndices]) => {
  separarPorValor(todosIndices).forEach(indices => {
  if (indices.length < 2) return;

  const total = indices.length;
  const primeira = transacoes[indices[0]];
  const mesInicial = primeira.mes_vencimento;
  const idCompra = `compra_${primeira.id}`;
  const valorTotal = Math.round(indices.reduce((acc, i) => acc + transacoes[i].valor, 0) * 100) / 100;

  relatorio.comprasParceladas++;
  relatorio.linhasParcela += total;

  indices.forEach((idx, i) => {
    const t = transacoes[idx];
    const mesParcela = somarMeses(mesInicial, i);

    t.eh_parcelada = true;
    t.parcela_numero = i + 1;
    t.parcela_total = total;
    t.descricao_parcela = `${i + 1}/${total}`;
    t.id_compra = idCompra;
    t.valor_total_compra = valorTotal;
    t.data_compra_original = t.data;

    if (realocarMeses && t.mes_vencimento !== mesParcela) {
      t.mes_vencimento = mesParcela;
      t.data_vencimento_fatura = dataVencimentoPara(mesParcela, mapaVenc);
      relatorio.mesesCorrigidos++;
    }
  });
  });
});

// --- 5. Sinalizar lançamentos cujo mês de fatura é inferido e não confiável ---
// As 5 faturas importadas cobrem compras a partir de 2025-12-22. Qualquer
// compra anterior a isso só pode ser parcela de uma compra mais antiga, e o
// mês de fatura que o importador gravou (derivado da data da compra) aponta
// para faturas que nunca foram importadas.
// As faturas importadas cobrem compras a partir de 2025-12-22. Uma compra
// anterior a isso so pode estar aqui como parcela de uma compra mais antiga,
// cobrada em alguma das faturas de 2026.
//
// O importador derivou o mes da fatura da data da compra e com isso fabricou
// sete "faturas" de 2025 que nunca existiram — algumas com um unico
// lancamento. Mante-las faria a dashboard exibir como fatura de 2025 um gasto
// que na verdade saiu da conta em 2026.
//
// Esses lancamentos passam para o balde MES_A_CONFIRMAR: continuam contando
// no total (o dinheiro saiu mesmo), mas sem fingir saber de qual fatura vieram.
const PRIMEIRA_COMPRA_COBERTA = '2025-12-22';
const MES_A_CONFIRMAR = 'A confirmar';

transacoes.forEach(t => {
  if (t.data < PRIMEIRA_COMPRA_COBERTA) {
    t.mes_vencimento_importado = t.mes_vencimento;
    t.mes_vencimento = MES_A_CONFIRMAR;
    t.data_vencimento_fatura = null;
    t.mes_vencimento_confiavel = false;
    t.motivo_revisao = 'Parcela de compra anterior ao período das faturas importadas. Pertence a uma fatura de 2026, mas o importador não registrou qual.';
    relatorio.mesesNaoConfiaveis++;
  } else {
    t.mes_vencimento_confiavel = true;
  }
});

// ---------- saída ----------

const totalGeral = transacoes.reduce((s, t) => s + t.valor, 0);
const porMes = {};
transacoes.forEach(t => { porMes[t.mes_vencimento] = (porMes[t.mes_vencimento] || 0) + t.valor; });

console.log('\n=== MIGRAÇÃO ' + (aplicar ? '(APLICADA)' : '(SIMULAÇÃO — nada foi gravado)') + ' ===\n');
console.log(`Pessoa "Ambos" -> "Família":     ${relatorio.pessoaRenomeada} lançamentos`);
console.log(`Compras parceladas detectadas:   ${relatorio.comprasParceladas} (${relatorio.linhasParcela} parcelas)`);
console.log(`Parcelas realocadas de mês:      ${realocarMeses ? relatorio.mesesCorrigidos : 'desligado (use --realocar-meses)'}`);
console.log(`Estornos marcados:               ${relatorio.estornosMarcados}`);
console.log(`Compras 100% canceladas:         ${relatorio.comprasCanceladas} linhas`);
console.log(`Mês de fatura a confirmar:       ${relatorio.mesesNaoConfiaveis} lançamentos`);
console.log(`\nTotal de transações:             ${transacoes.length}`);
console.log(`Soma geral (inalterada):         R$ ${totalGeral.toFixed(2)}`);

console.log('\n--- Faturas depois da correção ---');
Object.keys(porMes)
  .sort((a, b) => {
    if (a === 'A confirmar') return 1;
    if (b === 'A confirmar') return -1;
    const A = parseMesVenc(a), B = parseMesVenc(b);
    return A.ano - B.ano || A.mes - B.mes;
  })
  .forEach(m => console.log(`  ${m.padEnd(8)} R$ ${porMes[m].toFixed(2)}`));

if (aplicar) {
  fs.writeFileSync(ARQUIVO, JSON.stringify(dados, null, 2), 'utf8');
  console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
} else {
  console.log('\nRode com --aplicar para gravar.\n');
}
