#!/usr/bin/env node

/**
 * Script para remover faturas duplicadas do arquivo financeiro.json
 *
 * Verifica se há faturas com a mesma combinação de cartão + mês
 * e remove as duplicatas, mantendo apenas a primeira ocorrência.
 */

const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, '../data');
const FINANCEIRO_FILE = path.join(DATA_DIR, 'financeiro.json');

if (!fs.existsSync(FINANCEIRO_FILE)) {
  console.error(`Erro: arquivo ${FINANCEIRO_FILE} não encontrado`);
  process.exit(1);
}

console.log(`Lendo ${FINANCEIRO_FILE}...`);
const data = JSON.parse(fs.readFileSync(FINANCEIRO_FILE, 'utf-8'));

// Manter registro de faturas já vistas
const vistas = new Set();
const duplicatas = [];
const faturasLimpas = [];

console.log(`\nAnalisando ${data.faturas_cartao.length} faturas...`);

data.faturas_cartao.forEach((fatura, indice) => {
  const chave = `${fatura.cartao}|${fatura.mes}`;

  if (vistas.has(chave)) {
    console.log(`  ⚠️  DUPLICATA encontrada: cartão ${fatura.cartao}, mês ${fatura.mes} (índice ${indice})`);
    duplicatas.push({ indice, chave, fatura });
  } else {
    vistas.add(chave);
    faturasLimpas.push(fatura);
    console.log(`  ✓ ${fatura.cartao} | ${fatura.mes}`);
  }
});

if (duplicatas.length === 0) {
  console.log('\n✓ Nenhuma duplicata encontrada!');
  process.exit(0);
}

console.log(`\n❌ Encontradas ${duplicatas.length} faturas duplicadas:`);
duplicatas.forEach(({ indice, chave, fatura }) => {
  console.log(`  - Índice ${indice}: ${chave} (total: R$ ${fatura.total_fatura})`);
});

if (process.argv.includes('--aplicar')) {
  console.log(`\nRemovendo ${duplicatas.length} duplicatas...`);
  data.faturas_cartao = faturasLimpas;

  fs.writeFileSync(FINANCEIRO_FILE, JSON.stringify(data, null, 2));
  console.log(`✓ Arquivo atualizado: ${data.faturas_cartao.length} faturas (antes: ${data.faturas_cartao.length + duplicatas.length})`);
  console.log(`✓ Arquivo salvo em ${FINANCEIRO_FILE}`);
} else {
  console.log('\nUse --aplicar para remover as duplicatas');
}
