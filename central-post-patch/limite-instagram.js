#!/usr/bin/env node
/**
 * Prepara (NÃO instala) a alteração de limites de publicação do Instagram no server.js do Central Post.
 *
 * Problema resolvido: o agendador tentava publicar TODA a fila (depois das 20h sem ritmo nenhum) e repetia as falhas
 * para sempre, o que fazia o Instagram responder "User is performing too many actions".
 *
 * O que a alteração faz:
 *   - máximo de posts automáticos por conta por dia (IG_MAX_POR_DIA, padrão 6)
 *   - no máximo 1 post por conta por rodada e espaço mínimo entre posts (IG_INTERVALO_MIN, padrão 60 min)
 *   - desiste do item depois de IG_MAX_TENTATIVAS falhas (padrão 3); ele fica na fila, parado, com o erro anotado
 *   - ao receber "too many actions"/spam/limite, pausa a conta por IG_PAUSA_HORAS (padrão 6 h)
 *
 * Uso:  node limite-instagram.js [/opt/central-post/server.js] [/home/benetti/staged-limite-ig]
 * Ele só escreve a versão nova na pasta "staged", confere a sintaxe e mostra os comandos de instalação.
 */
const fs = require('fs'), os = require('os'), path = require('path'), cp = require('child_process');

const ORIGEM = process.argv[2] || '/opt/central-post/server.js';
const DESTINO_DIR = process.argv[3] || '/home/benetti/staged-limite-ig';

const HELPERS = `// ── Limites de publicação no Instagram (adicionado para evitar "User is performing too many actions") ──
const IG_MAX_POR_DIA = Number(process.env.IG_MAX_POR_DIA || 6);
const IG_INTERVALO_MS = Number(process.env.IG_INTERVALO_MIN || 60) * 60 * 1000;
const IG_MAX_TENTATIVAS = Number(process.env.IG_MAX_TENTATIVAS || 3);
const IG_PAUSA_MS = Number(process.env.IG_PAUSA_HORAS || 6) * 60 * 60 * 1000;
const igPausaAte = new Map();
let igCache = { chave: null, valor: {} };
function igDiaBR(ms) { return new Date(ms).toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" }); }
// a leitura da fila vale só dentro da mesma rodada do agendador (a chave é o objeto "selecionados" da rodada)
async function igResumoPorConta(chave) {
  if (igCache.chave === chave) return igCache.valor;
  const hoje = igDiaBR(Date.now());
  const resumo = {};
  await mutateTasks((ts) => {
    for (const t of ts) {
      if (!t.instagramPostedAt) continue;
      let nome;
      try { nome = contaDaFicha(t).nome; } catch (e) { continue; }
      const r = (resumo[nome] = resumo[nome] || { hoje: 0, ultimo: 0 });
      const quando = new Date(t.instagramPostedAt).getTime();
      if (igDiaBR(quando) === hoje) r.hoje++;
      if (quando > r.ultimo) r.ultimo = quando;
    }
  });
  igCache = { chave, valor: resumo };
  return resumo;
}
// true = NÃO publicar este item agora
async function igDeveSegurar(task, conta, selecionados) {
  if ((task.instagramFalhas || 0) >= IG_MAX_TENTATIVAS) return true;
  if ((igPausaAte.get(conta.nome) || 0) > Date.now()) return true;
  const r = (await igResumoPorConta(selecionados))[conta.nome] || { hoje: 0, ultimo: 0 };
  const jaSel = selecionados[conta.nome] || 0;
  if (r.hoje + jaSel >= IG_MAX_POR_DIA) return true;
  if (jaSel >= 1 || Date.now() - r.ultimo < IG_INTERVALO_MS) return true;
  return false;
}
async function igRegistrarFalha(taskId, snapshot, error) {
  try {
    await mutateTasks((ts) => { const f = ts.find((x) => x.id === taskId); if (f) f.instagramFalhas = (f.instagramFalhas || 0) + 1; });
    const msg = String((error && error.message) || "");
    if (/too many actions|spam|restrict|2207042|2207051|request limit|rate limit|publishing limit|daily limit/i.test(msg)) {
      const nome = contaDaFicha(snapshot).nome;
      igPausaAte.set(nome, Date.now() + IG_PAUSA_MS);
      console.error("Instagram: conta " + nome + " em pausa por " + (IG_PAUSA_MS / 3600000) + "h (excesso de ações)");
    }
  } catch (e) { console.error("Instagram: não consegui registrar a falha:", e.message); }
}
`;

const A1 = 'let instagramSchedulerRunning = false;';
const FIM = 'setInterval(runInstagramScheduler, 60 * 1000);';
const SEL = 'if (task.instagramPostedAt) continue;';
const ERR = 'console.error("Instagram: falha ao publicar automaticamente", taskId, error.message);';
const conta = (s, t) => s.split(t).length - 1;
const sai = (m) => { console.error('✖ ' + m + '\n  Nada foi alterado.'); process.exit(1); };

const src = fs.readFileSync(ORIGEM, 'utf8');
if (src.includes('igDeveSegurar')) sai('Este arquivo já tem a alteração aplicada.');
if (conta(src, A1) !== 1) sai('Não achei (ou achei mais de uma vez) a linha: ' + A1);
const i0 = src.indexOf(A1), i1 = src.indexOf(FIM, i0);
if (i1 < 0) sai('Não achei o fim do agendador: ' + FIM);
const regiao = src.slice(i0, i1);
for (const [nome, t] of [['seleção do item', SEL], ['mensagem de falha', ERR]])
  if (conta(regiao, t) !== 1) sai('No agendador, esperava 1 ocorrência de (' + nome + ') e achei ' + conta(regiao, t) + ': ' + t);
for (const v of ['selecionadosNesteCicloPorConta', 'const snapshot', 'const conta = contaDaFicha(task)'])
  if (!regiao.includes(v)) sai('O agendador não tem o trecho esperado: ' + v);

const nova = regiao
  .split(SEL).join(SEL + '\n      if (await igDeveSegurar(task, conta, selecionadosNesteCicloPorConta)) continue;')
  .split(ERR).join('await igRegistrarFalha(taskId, snapshot, error);\n      ' + ERR);
const saida = src.slice(0, i0) + HELPERS + '\n' + nova + src.slice(i1);

// confere a sintaxe (ESM se o arquivo usa import, senão CommonJS)
const ext = /^\s*import\s/m.test(src) ? '.mjs' : '.cjs';
const tmp = path.join(os.tmpdir(), 'checa-server' + ext);
fs.writeFileSync(tmp, saida);
const r = cp.spawnSync(process.execPath, ['--check', tmp], { encoding: 'utf8' });
if (r.status !== 0) sai('A versão nova não passou na conferência de sintaxe:\n' + r.stderr);

fs.mkdirSync(DESTINO_DIR, { recursive: true });
const destino = path.join(DESTINO_DIR, 'server.js');
fs.writeFileSync(destino, saida);
console.log('✔ Versão nova preparada e com a sintaxe OK: ' + destino);
console.log('  (+' + (saida.split('\n').length - src.split('\n').length) + ' linhas; o original NÃO foi tocado)\n');
console.log('Para instalar (com cópia de segurança):');
console.log('  B=/opt/central-post/backup-antes-limite-ig-$(date +%Y%m%d-%H%M%S) && sudo mkdir -p $B && sudo cp ' + ORIGEM + ' $B/server.js');
console.log('  sudo cp ' + destino + ' ' + ORIGEM + ' && sudo systemctl restart central-post');
console.log('Para desfazer:  sudo cp $B/server.js ' + ORIGEM + ' && sudo systemctl restart central-post');
