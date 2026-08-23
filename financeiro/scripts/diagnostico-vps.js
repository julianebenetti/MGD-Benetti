#!/usr/bin/env node
/**
 * Script para diagnosticar qual versão do código está rodando no VPS
 * e comparar com o arquivo local
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function hashFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    return crypto.createHash('sha256').update(content).digest('hex');
  } catch (err) {
    return null;
  }
}

function countTransacoes(filePath) {
  try {
    const content = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return content.fluxo_mensal?.transacoes?.length || 0;
  } catch (err) {
    console.error(`Erro lendo ${filePath}:`, err.message);
    return null;
  }
}

console.log('=== DIAGNÓSTICO DO ARQUIVO FINANCEIRO ===\n');

const localPath = path.join(__dirname, '..', 'data', 'financeiro.json');
const localCount = countTransacoes(localPath);
const localHash = hashFile(localPath);

console.log('LOCAL:');
console.log(`  Caminho: ${localPath}`);
console.log(`  Lançamentos: ${localCount}`);
console.log(`  SHA256: ${localHash}`);
console.log('');

console.log('INSTRUÇÕES PARA O VPS:');
console.log('1. Conecte-se ao VPS via SSH');
console.log('2. Execute:');
console.log('   cd /root/mgd-benetti');
console.log('   node -e "const f=require(\'fs\'),c=JSON.parse(f.readFileSync(\'financeiro/data/financeiro.json\',\'utf8\')); console.log(\'VPS Lançamentos:\',c.fluxo_mensal?.transacoes?.length); const h=require(\'crypto\').createHash(\'sha256\').update(f.readFileSync(\'financeiro/data/financeiro.json\',\'utf8\')).digest(\'hex\'); console.log(\'VPS SHA256:\',h);"');
console.log('');
console.log('3. Compare os valores:');
console.log(`   Se VPS SHA256 != ${localHash.substring(0, 8)}...`);
console.log('   Então o arquivo no VPS é DIFERENTE. Execute:');
console.log('   cd /root/mgd-benetti && git pull origin claude/financial-dashboard-pbj1ts');
console.log('   pm2 restart financeiro');
