// AfiliDash no VPS — roda as funções que antes ficavam na Netlify (pasta netlify/functions do repositório
// julianebenetti/afilidash), sem alterar uma linha delas. A página continua chamando os mesmos endereços:
//   /.netlify/functions/<nome>   e   /api/<nome>
// Também roda sozinho o "comissao-scheduled" (8h, 12h, 16h e 20h de Brasília), como a Netlify fazia.
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');

const BASE = __dirname;
for (const linha of (fs.existsSync(path.join(BASE, '.env')) ? fs.readFileSync(path.join(BASE, '.env'), 'utf8') : '').split('\n')) {
  const m = linha.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
}
const PORTA = Number(process.env.PORTA || 8791);
const FUNCOES = process.env.FUNCOES_DIR || path.join(BASE, 'afilidash', 'netlify', 'functions');
const PERMITIDAS = new Set(['config', 'sync', 'query', 'shopee', 'comissao']);   // as mesmas do netlify.toml

const log = (...a) => console.log(new Date().toISOString(), ...a);

function carregar(nome) {
  const arq = path.join(FUNCOES, nome + '.js');
  delete require.cache[require.resolve(arq)];          // pega a versão nova depois de atualizar
  return require(arq).handler;
}

const servidor = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const m = url.pathname.match(/^\/(?:\.netlify\/functions|api)\/([a-z-]+)\/?$/);
  if (!m || !PERMITIDAS.has(m[1])) { res.writeHead(404); return res.end('nao encontrado'); }
  let corpo = '';
  req.on('data', c => { corpo += c; if (corpo.length > 50e6) req.destroy(); });
  req.on('end', async () => {
    const evento = {
      httpMethod: req.method, path: url.pathname, headers: req.headers, body: corpo || null, isBase64Encoded: false,
      queryStringParameters: Object.fromEntries(url.searchParams),
    };
    try {
      const r = (await carregar(m[1])(evento, {})) || {};
      res.writeHead(r.statusCode || 200, { 'Content-Type': 'application/json; charset=utf-8', ...(r.headers || {}) });
      res.end(r.isBase64Encoded ? Buffer.from(r.body || '', 'base64') : (r.body || ''));
    } catch (e) {
      log(`erro em ${m[1]}:`, e);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e && e.message || e) }));
    }
  });
});

// Verificação de comissão 4x/dia (mesmo horário do netlify.toml: 11,15,19,23 UTC = 8,12,16,20 Brasília)
const HORAS_UTC = [11, 15, 19, 23];
let ultima = '';
setInterval(async () => {
  const agora = new Date();
  const chave = `${agora.toISOString().slice(0, 10)} ${agora.getUTCHours()}`;
  if (!HORAS_UTC.includes(agora.getUTCHours()) || agora.getUTCMinutes() > 10 || chave === ultima) return;
  ultima = chave;
  try { const r = await carregar('comissao-scheduled')({}, {}); log('comissao-scheduled:', r && r.statusCode); }
  catch (e) { log('comissao-scheduled falhou:', e); }
}, 60 * 1000);

if (!process.env.SUPABASE_KEY) log('⚠️  SUPABASE_KEY vazia no .env: as funções não vão conseguir gravar no Supabase');
servidor.listen(PORTA, '127.0.0.1', () => log(`AfiliDash (funções) em http://127.0.0.1:${PORTA} · funções: ${FUNCOES}`));
