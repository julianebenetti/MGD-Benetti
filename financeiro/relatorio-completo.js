#!/usr/bin/env node
/**
 * Relatório Completo de Classificações - AfiliDash Financeiro
 *
 * Gera análise detalhada de transações classificadas
 */

const fs = require('fs');
const path = require('path');

const FINANCEIRO_PATH = path.join(__dirname, 'data', 'financeiro.json');

function readJSON(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (err) {
    console.error(`Erro lendo ${filePath}:`, err.message);
    return null;
  }
}

function formatarValor(valor) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(valor);
}

function gerarRelatorio() {
  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║        RELATÓRIO COMPLETO DE CLASSIFICAÇÕES                 ║');
  console.log('║           AfiliDash Financeiro - Agosto 2026                ║');
  console.log('╚══════════════════════════════════════════════════════════════╝\n');

  const financeiro = readJSON(FINANCEIRO_PATH);
  if (!financeiro || !financeiro.fluxo_mensal || !financeiro.fluxo_mensal.transacoes) {
    console.error('Erro: dados não encontrados');
    process.exit(1);
  }

  const transacoes = financeiro.fluxo_mensal.transacoes;

  // Análise por categoria
  console.log('📊 ANÁLISE POR CATEGORIA\n');
  const porCategoria = {};
  transacoes.forEach(txn => {
    const cat = txn.categoria || 'sem_classificacao';
    if (!porCategoria[cat]) {
      porCategoria[cat] = { count: 0, valor: 0, transacoes: [] };
    }
    porCategoria[cat].count++;
    porCategoria[cat].valor += txn.valor || 0;
    porCategoria[cat].transacoes.push(txn);
  });

  const categoriasSorted = Object.entries(porCategoria).sort((a, b) => Math.abs(b[1].valor) - Math.abs(a[1].valor));
  categoriasSorted.forEach(([cat, dados]) => {
    console.log(`\n  ${cat.toUpperCase()}`);
    console.log(`  └─ Transações: ${dados.count} | Total: ${formatarValor(dados.valor)}`);
  });

  // Análise por pessoa
  console.log('\n\n👥 ANÁLISE POR PESSOA\n');
  const porPessoa = {};
  transacoes.forEach(txn => {
    const pessoa = txn.pessoa || 'sem_classificacao';
    if (!porPessoa[pessoa]) {
      porPessoa[pessoa] = { count: 0, valor: 0, transacoes: [] };
    }
    porPessoa[pessoa].count++;
    porPessoa[pessoa].valor += txn.valor || 0;
    porPessoa[pessoa].transacoes.push(txn);
  });

  const pessoasSorted = Object.entries(porPessoa).sort((a, b) => b[1].count - a[1].count);
  pessoasSorted.forEach(([pessoa, dados]) => {
    console.log(`\n  ${pessoa}`);
    console.log(`  └─ Transações: ${dados.count} | Total: ${formatarValor(dados.valor)}`);
  });

  // Análise por tipo
  console.log('\n\n💰 ANÁLISE POR TIPO (ENTRADA/SAÍDA)\n');
  const porTipo = {};
  transacoes.forEach(txn => {
    const tipo = txn.tipo || 'desconhecido';
    if (!porTipo[tipo]) {
      porTipo[tipo] = { count: 0, valor: 0 };
    }
    porTipo[tipo].count++;
    porTipo[tipo].valor += txn.valor || 0;
  });

  Object.entries(porTipo).forEach(([tipo, dados]) => {
    const simbolo = tipo === 'entrada' ? '📈' : '📉';
    console.log(`\n  ${simbolo} ${tipo.toUpperCase()}`);
    console.log(`  └─ Transações: ${dados.count} | Total: ${formatarValor(dados.valor)}`);
  });

  // Análise de origem
  console.log('\n\n📋 ANÁLISE POR ORIGEM\n');
  const porOrigem = {};
  transacoes.forEach(txn => {
    const origem = txn.origem || 'desconhecida';
    if (!porOrigem[origem]) {
      porOrigem[origem] = { count: 0 };
    }
    porOrigem[origem].count++;
  });

  Object.entries(porOrigem).forEach(([origem, dados]) => {
    const simbolo = origem === 'importacao' ? '📥' : '✏️';
    console.log(`\n  ${simbolo} ${origem.toUpperCase()}`);
    console.log(`  └─ Transações: ${dados.count}`);
  });

  // Resumo geral
  console.log('\n\n✨ RESUMO GERAL\n');
  const totalTransacoes = transacoes.length;
  const totalEntrada = transacoes.reduce((sum, txn) => txn.tipo === 'entrada' ? sum + txn.valor : sum, 0);
  const totalSaida = transacoes.reduce((sum, txn) => txn.tipo === 'saida' ? sum + txn.valor : sum, 0);
  const saldo = totalEntrada + totalSaida;

  console.log(`  Total de transações: ${totalTransacoes}`);
  console.log(`  Total de entradas: ${formatarValor(totalEntrada)}`);
  console.log(`  Total de saídas: ${formatarValor(totalSaida)}`);
  console.log(`  Saldo: ${formatarValor(saldo)}`);

  const naoClassificadas = transacoes.filter(t => !t.categoria || !t.pessoa).length;
  console.log(`  Não classificadas: ${naoClassificadas}`);
  console.log(`  Taxa de cobertura: ${((totalTransacoes - naoClassificadas) / totalTransacoes * 100).toFixed(1)}%`);

  // Top 10 maiores transações
  console.log('\n\n🏆 TOP 10 MAIORES TRANSAÇÕES\n');
  const maiores = [...transacoes].sort((a, b) => Math.abs(b.valor) - Math.abs(a.valor)).slice(0, 10);
  maiores.forEach((txn, idx) => {
    const simbolo = txn.valor > 0 ? '📈' : '📉';
    console.log(`  ${idx + 1}. ${simbolo} ${txn.descricao}`);
    console.log(`     ${formatarValor(txn.valor)} - ${txn.categoria} (${txn.pessoa})`);
  });

  console.log('\n═══════════════════════════════════════════════════════════════\n');
}

if (require.main === module) {
  gerarRelatorio();
}

module.exports = { gerarRelatorio };
