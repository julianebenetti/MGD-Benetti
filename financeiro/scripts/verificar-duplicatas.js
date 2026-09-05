#!/usr/bin/env node

/**
 * Script para verificar duplicatas de arquivos XLSX antes de importar
 *
 * Lê todos os arquivos .xlsx de uma pasta, calcula hash de cada um
 * e avisa se há arquivos com conteúdo idêntico.
 *
 * Uso:
 *   DIR_FATURAS=/path/to/faturas node verificar-duplicatas.js
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DIR_FATURAS = process.env.DIR_FATURAS;

if (!DIR_FATURAS) {
  console.error('Erro: variável de ambiente DIR_FATURAS não definida');
  console.error('Uso: DIR_FATURAS=/path/to/faturas node verificar-duplicatas.js');
  process.exit(1);
}

if (!fs.existsSync(DIR_FATURAS)) {
  console.error(`Erro: diretório ${DIR_FATURAS} não existe`);
  process.exit(1);
}

console.log(`Verificando duplicatas em: ${DIR_FATURAS}\n`);

// Ler arquivos .xlsx
const arquivos = fs
  .readdirSync(DIR_FATURAS)
  .filter(arquivo => arquivo.endsWith('.xlsx') || arquivo.endsWith('.xls'))
  .sort();

if (arquivos.length === 0) {
  console.log('ℹ️  Nenhum arquivo .xlsx encontrado');
  process.exit(0);
}

console.log(`Encontrados ${arquivos.length} arquivo(s):\n`);

// Calcular hash de cada arquivo
const hashes = new Map();
const porHash = new Map();

arquivos.forEach(arquivo => {
  const caminho = path.join(DIR_FATURAS, arquivo);
  const conteudo = fs.readFileSync(caminho);
  const hash = crypto.createHash('sha256').update(conteudo).digest('hex');

  console.log(`  ${arquivo}`);
  console.log(`    Tamanho: ${(conteudo.length / 1024).toFixed(1)} KB`);
  console.log(`    Hash: ${hash.substring(0, 16)}...`);

  hashes.set(arquivo, hash);

  if (!porHash.has(hash)) {
    porHash.set(hash, []);
  }
  porHash.get(hash).push(arquivo);
});

// Detectar duplicatas
console.log('\n' + '='.repeat(60));
const duplicatas = Array.from(porHash.entries()).filter(([_, arquivos]) => arquivos.length > 1);

if (duplicatas.length === 0) {
  console.log('✓ Nenhuma duplicata encontrada!');
  process.exit(0);
}

console.log(`\n❌ AVISO: ${duplicatas.length} grupo(s) de arquivo(s) idêntico(s) encontrado(s):\n`);

duplicatas.forEach(([hash, arquivos], indice) => {
  console.log(`Duplicata ${indice + 1}: ${arquivos.length} arquivo(s) com conteúdo idêntico`);
  console.log(`  Hash: ${hash.substring(0, 16)}...`);
  arquivos.forEach(arquivo => {
    console.log(`    - ${arquivo}`);
  });
  console.log();
});

console.log('⚠️  ANTES DE IMPORTAR: remova os arquivos duplicados!\n');
process.exit(1);
