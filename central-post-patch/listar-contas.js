#!/usr/bin/env node
/**
 * Lista as contas do Instagram/Página conectadas ao Central Post: nome, @, ID da Página e ID do Instagram.
 * SOMENTE leitura. Imprime só esses campos; tokens e segredos NUNCA são impressos.
 * Uso:  node listar-contas.js [/opt/central-post]
 */
const fs = require('fs'), cp = require('child_process');
const base = process.argv[2] || '/opt/central-post';
const r = cp.spawnSync('find', [base, '-maxdepth', '4', '-type', 'f', '-name', '*.json', '-not', '-path', '*/backup-*', '-not', '-path', '*/node_modules/*'], { encoding: 'utf8' });
let achou = false;
for (const f of r.stdout.split('\n').filter(Boolean)) {
  let j;
  try { if (fs.statSync(f).size > 5e6) continue; j = JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { continue; }
  if (!j || typeof j !== 'object' || Array.isArray(j) || !j.contas || typeof j.contas !== 'object') continue;
  const itens = Object.entries(j.contas).filter(([, c]) => c && typeof c === 'object' && (c.igUsername || c.instagram || c.pageName || c.pageId));
  if (!itens.length) continue;
  achou = true;
  console.log('Arquivo: ' + f + '\n');
  for (const [nome, c] of itens) {
    console.log('- ' + nome + ' | Página: ' + (c.pageName || '?') + ' (' + (c.pageId || '?') + ') | Instagram: @' + String(c.igUsername || c.instagram || '?').replace(/^@/, '') + ' (' + (c.igId || c.igBusinessAccountId || '?') + ')');
  }
  console.log('');
}
if (!achou) console.log('Não achei o arquivo com as contas em ' + base + '. Me diga e eu procuro em outro lugar.');
