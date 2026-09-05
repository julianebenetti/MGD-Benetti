#!/usr/bin/env node
/**
 * Corretor de Classificações - AfiliDash Financeiro
 *
 * Identifica transações com categoria null ou pessoa null
 * Sugere classificações e permite aplicar correções
 */

const fs = require('fs');
const path = require('path');

const FINANCEIRO_PATH = path.join(__dirname, 'data', 'financeiro.json');

// Mapeamento inteligente de categorias
const CATEGORIA_MAP = {
  'APPLE': 'assinatura',
  'SPOTIFY': 'assinatura',
  'GOOGLE ONE': 'assinatura',
  'GOOGLE': 'assinatura',
  'NETFLIX': 'assinatura',
  'IFOOD': 'assinatura',
  'PRIME': 'assinatura',
  'MAGALU': 'pessoal',
  'LOJA': 'pessoal',
  'ROUPAS': 'pessoal',
  'ROUPA': 'pessoal',
  'UNIAO': 'pessoal',
  'GUILHERME': 'educacao',
  'VAN': 'educacao',
  'ESCOLA': 'educacao',
  'CURSO': 'educacao',
  'KIWIFY': 'educacao',
  'IGREJA': 'doacao',
  'SALARIO': 'entrada',
  'REMUNERACAO': 'entrada'
};

// Padrões de pessoa
const PESSOA_MAP = {
  'APPLE': 'Juliane',
  'SPOTIFY': 'Juliane',
  'GOOGLE': 'Juliane',
  'KIWIFY': 'Juliane',
  'UNIAO': 'Juliane',
  'MAGALU': 'Juliane',
  '99APP': 'Juliane',
  'UBER': 'Juliane',
  'COMBUSTIVEL': 'Hugo',
  'POSTO': 'Hugo',
  'TOKIO': 'Hugo',
  'SAVEGNAGO': 'Hugo',
  'MARCIA': 'Hugo',
  'SUPERMERCADOS JL': 'Hugo'
};

function readJSON(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (err) {
    console.error(`Erro lendo ${filePath}:`, err.message);
    return null;
  }
}

function writeJSON(filePath, data) {
  try {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error(`Erro escrevendo ${filePath}:`, err.message);
    return false;
  }
}

function buscarCategoria(descricao, categoria) {
  if (categoria) return categoria; // Já tem categoria

  const desc = (descricao || '').toUpperCase();

  for (const [palavra, cat] of Object.entries(CATEGORIA_MAP)) {
    if (desc.includes(palavra)) {
      return cat;
    }
  }

  return null;
}

function buscarPessoa(descricao, pessoa) {
  if (pessoa && pessoa !== 'Ambos') return pessoa; // Já tem pessoa

  const desc = (descricao || '').toUpperCase();

  for (const [palavra, p] of Object.entries(PESSOA_MAP)) {
    if (desc.includes(palavra)) {
      return p;
    }
  }

  return pessoa || 'Ambos'; // Retorna o original ou Ambos como padrão
}

function corrigirClassificacoes() {
  console.log('\n=== CORRETOR DE CLASSIFICAÇÕES ===\n');

  const financeiro = readJSON(FINANCEIRO_PATH);
  if (!financeiro || !financeiro.fluxo_mensal || !financeiro.fluxo_mensal.transacoes) {
    console.error('Erro: dados não encontrados');
    process.exit(1);
  }

  const transacoes = financeiro.fluxo_mensal.transacoes;
  console.log(`Total de transações: ${transacoes.length}\n`);

  // Identificar problemas
  const comProblema = [];
  transacoes.forEach((txn, idx) => {
    if (!txn.categoria || !txn.pessoa) {
      comProblema.push({
        indice: idx,
        txn: txn,
        faltaCategoria: !txn.categoria,
        faltaPessoa: !txn.pessoa
      });
    }
  });

  if (comProblema.length === 0) {
    console.log('✅ Todas as transações estão classificadas!\n');
    return;
  }

  console.log(`⚠️  ${comProblema.length} transações com problemas de classificação:\n`);

  let corrigidas = 0;
  const relatorio = [];

  comProblema.forEach((item) => {
    const txn = item.txn;
    const idx = item.indice;
    const novaCategoria = buscarCategoria(txn.descricao, txn.categoria);
    const novaPessoa = buscarPessoa(txn.descricao, txn.pessoa);

    if (novaCategoria && item.faltaCategoria) {
      txn.categoria = novaCategoria;
      corrigidas++;
    }

    if (novaPessoa !== txn.pessoa && item.faltaPessoa) {
      txn.pessoa = novaPessoa;
      corrigidas++;
    }

    const status = (!item.faltaCategoria || txn.categoria) && (!item.faltaPessoa || txn.pessoa) ? '✅' : '⚠️';
    console.log(`[${idx + 1}] ${status} ${txn.descricao}`);
    console.log(`       Categoria: ${txn.categoria || 'FALTA'} | Pessoa: ${txn.pessoa || 'FALTA'}`);

    relatorio.push({
      indice: idx + 1,
      descricao: txn.descricao,
      categoria: txn.categoria,
      pessoa: txn.pessoa,
      corrigida: status === '✅'
    });
  });

  // Salvar se houver correções
  if (corrigidas > 0) {
    if (writeJSON(FINANCEIRO_PATH, financeiro)) {
      console.log(`\n✅ ${corrigidas} campo(s) corrigido(s) e salvos!\n`);
    } else {
      console.error('\n❌ Erro ao salvar dados\n');
      process.exit(1);
    }
  }

  // Resumo
  const fulmenteclassificadas = relatorio.filter(r => r.categoria && r.pessoa).length;
  console.log('=== RESUMO ===');
  console.log(`Total de transações com problemas: ${comProblema.length}`);
  console.log(`Transações corrigidas: ${fulmenteclassificadas}`);
  console.log(`Taxa de sucesso: ${((fulmenteclassificadas / comProblema.length) * 100).toFixed(1)}%\n`);

  // Mostrar ainda não classificadas
  const aindaNao = relatorio.filter(r => !r.categoria || !r.pessoa);
  if (aindaNao.length > 0) {
    console.log('Transações que ainda precisam de classificação manual:');
    aindaNao.forEach(item => {
      console.log(`  [${item.indice}] ${item.descricao}`);
      if (!item.categoria) console.log(`       → Categoria: FALTA`);
      if (!item.pessoa) console.log(`       → Pessoa: FALTA`);
    });
    console.log('');
  }
}

if (require.main === module) {
  corrigirClassificacoes();
}

module.exports = { corrigirClassificacoes };
