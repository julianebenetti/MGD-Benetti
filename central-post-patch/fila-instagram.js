#!/usr/bin/env node
/**
 * Ferramenta da fila de publicação do Instagram (tasks.json do Central Post).
 *   node fila-instagram.js status                  mostra quantos vídeos esperam e quantos estão parados
 *   node fila-instagram.js segurar [--aplicar]     para TODOS os vídeos da fila (não apaga nada)
 *   node fila-instagram.js liberar 5 [--aplicar]   libera os 5 mais antigos que foram parados por "segurar"
 * Sem --aplicar só mostra o que faria. Ao aplicar, guarda cópia: tasks.json.bak-AAAAMMDD-HHMMSS
 * IMPORTANTE: para aplicar, pare o serviço antes (sudo systemctl stop central-post) e ligue depois.
 */
const fs = require('fs'), path = require('path'), cp = require('child_process');
const args = process.argv.slice(2);
const cmd = args[0];
const aplicar = args.includes('--aplicar');
const iArq = args.indexOf('--arquivo');
const MAX = Number(process.env.IG_MAX_TENTATIVAS || 3);

function achar() {
  if (iArq >= 0) return args[iArq + 1];
  const r = cp.spawnSync('find', ['/opt/central-post', '-name', 'tasks.json', '-not', '-path', '*/backup-*', '-not', '-path', '*/node_modules/*'], { encoding: 'utf8' });
  const l = r.stdout.split('\n').filter(Boolean);
  if (l.length !== 1) { console.error('Não consegui achar um único tasks.json (' + l.length + '). Use --arquivo /caminho/tasks.json'); process.exit(1); }
  return l[0];
}
const arq = achar();
const tasks = JSON.parse(fs.readFileSync(arq, 'utf8'));
if (!Array.isArray(tasks)) { console.error('tasks.json não é uma lista; não mexo.'); process.exit(1); }

const pronta = (t) => t.status === 'Fila' && !t.instagramPostedAt && t.media && t.media.type === 'video';
const fila = tasks.filter(pronta);
const parados = fila.filter((t) => (t.instagramFalhas || 0) >= MAX);
const ativos = fila.filter((t) => (t.instagramFalhas || 0) < MAX);
const ordem = (a, b) => String(a.createdAt || a.updatedAt || '').localeCompare(String(b.createdAt || b.updatedAt || ''));

function salvar() {
  const d = new Date(), p = (n) => String(n).padStart(2, '0');
  let bak = arq + '.bak-' + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '-' + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  for (let k = 2; fs.existsSync(bak); k++) bak = bak.replace(/(-\d+)?$/, '') + '-' + k; // nunca sobrescreve uma cópia anterior
  fs.copyFileSync(arq, bak);
  fs.writeFileSync(arq, JSON.stringify(tasks, null, 2));
  console.log('✔ Gravado. Cópia de segurança: ' + bak);
}

console.log('Arquivo: ' + arq);
console.log('Vídeos na fila: ' + fila.length + '  ·  tentando publicar: ' + ativos.length + '  ·  parados: ' + parados.length);

if (cmd === 'status' || !cmd) {
  for (const t of fila.slice(0, 15)) console.log(' - ' + (t.id || '?') + '  falhas=' + (t.instagramFalhas || 0) + '  ' + String(t.instagramLastError || '').slice(0, 70));
} else if (cmd === 'segurar') {
  console.log((aplicar ? 'Parando ' : 'Pararia ') + ativos.length + ' vídeo(s).');
  if (aplicar) { for (const t of ativos) { t.instagramFalhas = MAX; t.instagramSegurado = true; } salvar(); }
  else console.log('(simulação: nada foi gravado; use --aplicar)');
} else if (cmd === 'liberar') {
  const n = Number(args[1]);
  if (!n || n < 1) { console.error('Informe quantos liberar: liberar 5'); process.exit(1); }
  const alvo = parados.filter((t) => t.instagramSegurado).sort(ordem).slice(0, n);
  console.log((aplicar ? 'Liberando ' : 'Liberaria ') + alvo.length + ' vídeo(s) (os mais antigos dos parados).');
  if (aplicar) { for (const t of alvo) { t.instagramFalhas = 0; delete t.instagramSegurado; t.instagramLastError = ''; } salvar(); }
  else console.log('(simulação: nada foi gravado; use --aplicar)');
} else { console.error('Comando desconhecido: ' + cmd); process.exit(1); }
