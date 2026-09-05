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

// --- 4. Consolidar parcelamentos e alocar cada parcela na sua fatura ---
//
// A fatura do cartao fecha por volta do dia DIA_FECHAMENTO. Uma compra ate
// esse dia entra na fatura do proprio mes; depois dele, na do mes seguinte.
//
// Numa compra parcelada, a fatura traz TODAS as parcelas com a data da compra
// original. Ao importar cinco faturas seguidas, a mesma compra aparece varias
// vezes com a mesma data — uma vez por fatura em que uma parcela foi cobrada.
// Por isso as linhas repetidas nao sao duplicatas: sao parcelas distintas, e
// cada uma pertence a um mes de fatura diferente, em sequencia.
//
// Quando a compra e anterior ao periodo importado, as primeiras parcelas
// caem em faturas que nao temos. As parcelas visiveis comecam entao na
// primeira fatura importada, e a numeracao e deduzida da distancia entre a
// fatura de origem da compra e essa primeira fatura.

const DIA_FECHAMENTO = parseInt((process.argv.find(a => a.startsWith('--fechamento=')) || '').split('=')[1], 10) || 16;
const PRIMEIRA_FATURA = (process.argv.find(a => a.startsWith('--primeira-fatura=')) || '').split('=')[1] || 'Jan/26';

function indiceMes(mv) {
  const { mes, ano } = parseMesVenc(mv);
  return ano * 12 + mes;
}

function mesDeIndice(i) {
  return `${MESES[((i % 12) + 12) % 12]}/${String(Math.floor(i / 12)).slice(2)}`;
}

// Fatura em que uma compra feita nesta data e cobrada.
function faturaDaCompra(data) {
  const [ano, mes, dia] = data.split('-').map(Number);
  const base = ano * 12 + (mes - 1);
  return dia <= DIA_FECHAMENTO ? base : base + 1;
}

const idxPrimeira = indiceMes(PRIMEIRA_FATURA);

const grupos = {};
transacoes.forEach((t, idx) => {
  const chave = `${t.data}|${t.descricao}`;
  (grupos[chave] = grupos[chave] || []).push(idx);
});

// Dentro de um grupo, so sao parcelas da mesma compra os lancamentos de valor
// equivalente (ate 5 centavos de diferenca, por conta do ajuste que o banco
// faz na ultima parcela). Valores distintos no mesmo dia e no mesmo
// estabelecimento sao compras separadas.
function separarPorValor(indices) {
  const blocos = [];
  indices.forEach(idx => {
    const v = transacoes[idx].valor;
    const bloco = blocos.find(b => Math.abs(transacoes[b[0]].valor - v) <= 0.05);
    if (bloco) bloco.push(idx); else blocos.push([idx]);
  });
  return blocos;
}

Object.values(grupos).forEach(todosIndices => {
  separarPorValor(todosIndices).forEach(indices => {
    const faturaOrigem = faturaDaCompra(transacoes[indices[0]].data);
    const primeiraVisivel = Math.max(faturaOrigem, idxPrimeira);
    // Se a compra e anterior ao periodo importado, as parcelas que vemos nao
    // comecam na primeira: a numeracao arranca na distancia ate a fatura inicial.
    const numeroInicial = primeiraVisivel - faturaOrigem + 1;
    const ehParcelada = indices.length > 1 || numeroInicial > 1;

    indices.forEach((idx, i) => {
      const t = transacoes[idx];
      const fatura = primeiraVisivel + i;

      if (t.mes_vencimento !== mesDeIndice(fatura)) relatorio.mesesCorrigidos++;
      t.mes_vencimento = mesDeIndice(fatura);
      t.data_vencimento_fatura = dataVencimentoPara(t.mes_vencimento, mapaVenc);

      if (ehParcelada) {
        t.eh_parcelada = true;
        t.parcela_numero = numeroInicial + i;
        t.id_compra = `compra_${transacoes[indices[0]].id}`;
        t.data_compra_original = t.data;
        // O total de parcelas so e conhecido quando a compra inteira esta
        // dentro do periodo importado. Fora disso, sabemos o numero da
        // parcela mas nao quantas sao ao todo.
        if (numeroInicial === 1) {
          t.parcela_total = indices.length;
          t.descricao_parcela = `${t.parcela_numero}/${indices.length}`;
          t.valor_total_compra = Math.round(indices.reduce((a, j) => a + transacoes[j].valor, 0) * 100) / 100;
          t.total_parcelas_conhecido = true;
        } else {
          t.parcela_total = null;
          t.descricao_parcela = `${t.parcela_numero}/?`;
          t.valor_total_compra = null;
          t.total_parcelas_conhecido = false;
          t.motivo_revisao = 'Compra anterior às faturas importadas: sabemos o número da parcela, não o total.';
        }
      }
    });

    if (ehParcelada) {
      relatorio.comprasParceladas++;
      relatorio.linhasParcela += indices.length;
      if (numeroInicial > 1) relatorio.mesesNaoConfiaveis += indices.length;
    }
  });
});

transacoes.forEach(t => { t.mes_vencimento_confiavel = true; });

// ---------- saída ----------

const totalGeral = transacoes.reduce((s, t) => s + t.valor, 0);
const porMes = {};
transacoes.forEach(t => { porMes[t.mes_vencimento] = (porMes[t.mes_vencimento] || 0) + t.valor; });

console.log('\n=== MIGRAÇÃO ' + (aplicar ? '(APLICADA)' : '(SIMULAÇÃO — nada foi gravado)') + ' ===\n');
console.log(`Pessoa "Ambos" -> "Família":     ${relatorio.pessoaRenomeada} lançamentos`);
console.log(`Compras parceladas detectadas:   ${relatorio.comprasParceladas} (${relatorio.linhasParcela} parcelas)`);
console.log(`Parcelas realocadas de fatura:   ${relatorio.mesesCorrigidos}`);
console.log(`Estornos marcados:               ${relatorio.estornosMarcados}`);
console.log(`Compras 100% canceladas:         ${relatorio.comprasCanceladas} linhas`);
console.log(`Parcelas de compra anterior:     ${relatorio.mesesNaoConfiaveis} (total de parcelas desconhecido)`);
console.log(`Ciclo usado:                     fecha dia ${DIA_FECHAMENTO}, primeira fatura ${PRIMEIRA_FATURA}`);
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
