#!/usr/bin/env node
/**
 * Busca o token permanente de cada Página do Facebook e guarda em paginas.json (permissão 600).
 * Usa o token do USUÁRIO DO SISTEMA (FB_SYSTEM_TOKEN, no .env). Depois de rodar, o robô só lê o paginas.json.
 * NUNCA imprime tokens: mostra só nome, validade e se o token pode publicar/comentar.
 * Uso:  node obter-tokens-paginas.js
 */
const fs = require('fs'), path = require('path');
const AQUI = __dirname;

// carrega o .env (sem sobrescrever o que já está no ambiente)
try {
  for (const l of fs.readFileSync(path.join(AQUI, '.env'), 'utf8').split('\n')) {
    const m = l.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (m && !l.trim().startsWith('#') && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
} catch (e) { /* sem .env */ }

const BASE = process.env.FB_GRAPH_BASE || 'https://graph.facebook.com';
const VERSAO = process.env.FB_GRAPH_VERSION || 'v25.0';
const TOKEN = process.env.FB_SYSTEM_TOKEN || '';
// chave curta -> ID da Página (ajuste aqui se mudar de Página)
const PAGINAS = { bbc: '1247549898433750', vea: '264864416717882', vip: '1136231269570276' };
const PRECISA = ['pages_manage_posts', 'pages_manage_engagement'];

async function graph(caminho, params) {
  const url = BASE + '/' + VERSAO + '/' + caminho + '?' + new URLSearchParams(params);
  const r = await fetch(url);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error('Meta respondeu ' + r.status + ': ' + String((j.error && j.error.message) || '').slice(0, 200));
  return j;
}

(async () => {
  if (!TOKEN) { console.error('Faltou FB_SYSTEM_TOKEN no arquivo .env (veja o passo a passo).'); process.exit(1); }
  const saida = {};
  let falhas = 0;
  for (const [chave, id] of Object.entries(PAGINAS)) {
    try {
      const p = await graph(id, { fields: 'id,name,access_token', access_token: TOKEN });
      if (!p.access_token) throw new Error('a Meta não devolveu o token desta Página (o usuário do sistema tem acesso a ela?)');
      saida[chave] = { page_id: p.id, nome: p.name, token: p.access_token };
      let info = '';
      try {
        const d = (await graph('debug_token', { input_token: p.access_token, access_token: TOKEN })).data || {};
        const sc = d.scopes || [];
        const falta = PRECISA.filter((x) => !sc.includes(x));
        info = ' · validade: ' + (d.expires_at ? new Date(d.expires_at * 1000).toLocaleDateString('pt-BR') : 'nunca') +
               ' · ' + (falta.length ? 'FALTAM permissões: ' + falta.join(', ') : 'pode publicar e comentar') + (d.is_valid === false ? ' · TOKEN INVÁLIDO' : '');
      } catch (e) { info = ' · (não consegui conferir as permissões: ' + e.message + ')'; }
      console.log('✅ ' + chave + ' — ' + p.name + info);
    } catch (e) { falhas++; console.log('✖ ' + chave + ' (' + id + '): ' + e.message); }
  }
  if (!Object.keys(saida).length) { console.error('\nNenhuma Página obtida; nada foi gravado.'); process.exit(1); }
  const arq = path.join(AQUI, 'paginas.json');
  fs.writeFileSync(arq, JSON.stringify(saida, null, 2), { mode: 0o600 });
  fs.chmodSync(arq, 0o600);
  console.log('\nGravado em ' + arq + ' (somente o administrador lê). ' + (falhas ? falhas + ' Página(s) falharam.' : 'Todas as Páginas OK.'));
})();
