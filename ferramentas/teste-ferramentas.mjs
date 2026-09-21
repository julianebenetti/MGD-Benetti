/* Testes das ferramentas de navegador (ferramentas/*.js).
   Rode de dentro da pasta ferramentas/:   node teste-ferramentas.mjs

   Garante duas coisas:
   - o inspetor acha os sinais certos na tela e ignora o resto;
   - o capturador de API NÃO deixa vazar dado pessoal — só estrutura,
     nomes de campo e valores de status. */

import fs from 'node:fs';

let falhas = 0;
const checa = (nome, cond, extra = '') => {
  if (!cond) falhas++;
  console.log(`${cond ? '✅' : '❌'} ${nome}${cond ? '' : ' — ' + extra}`);
};
const silenciar = () => { const o = console.log; console.log = () => {}; return () => { console.log = o; }; };

// ─────────────────────────────────────────────────────────────
console.log('── inspecionar-painel-tiktok.js ──');
{
  const els = [
    { tagName:'SPAN',  className:'filtro-tab', children:[],   textContent:'Links de produtos ocultos (10)' },
    { tagName:'DIV',   className:'warn-text',  children:[],   textContent:'1 links do produto precisam de atenção' },
    { tagName:'SPAN',  className:'motivo',     children:[],   textContent:'O produto vinculado está esgotado.' },
    { tagName:'SPAN',  className:'motivo',     children:[],   textContent:'O produto que você vinculou foi removido.' },
    { tagName:'BUTTON',className:'btn',        children:[],   textContent:'Vincular' },
    { tagName:'DIV',   className:'pai',        children:[{}], textContent:'container inteiro, tem esgotado dentro, deve ser ignorado' },
    { tagName:'SPAN',  className:'ruido',      children:[],   textContent:'Curtidas' },
  ];
  const anchors = [
    { href:'https://www.tiktok.com/@ela/video/111' },
    { href:'https://www.tiktok.com/@ela/video/111' },
    { href:'https://www.tiktok.com/@ela/video/222' },
  ];
  globalThis.document = { querySelectorAll: s => s.includes('a[href') ? anchors : els };
  globalThis.location = { href:'https://business.tiktokshop.com/us/creator?from=portal_v4' };
  globalThis.window = globalThis;

  const restaurar = silenciar();
  eval(fs.readFileSync('./inspecionar-painel-tiktok.js', 'utf8'));
  restaurar();

  const r = globalThis.window.__ttResultado;
  checa('pega o contador do filtro',  r.achados.some(a => a.texto.includes('ocultos (10)')));
  checa('pega o aviso vermelho',      r.achados.some(a => a.texto.includes('precisam de atenção')));
  checa('pega o motivo esgotado',     r.achados.some(a => a.texto.includes('esgotado')));
  checa('pega o motivo removido',     r.achados.some(a => a.texto.includes('removido')));
  checa('pega o botão Vincular',      r.achados.some(a => a.texto === 'Vincular'));
  checa('ignora o container pai',     !r.achados.some(a => a.classe === 'pai'));
  checa('ignora texto irrelevante',   !r.achados.some(a => a.texto === 'Curtidas'));
  checa('links de vídeo sem repetir', r.videos.length === 2, String(r.videos.length));
}

// ─────────────────────────────────────────────────────────────
console.log('\n── capturar-api-tiktok.js ──');
{
  globalThis.location = {
    origin:'https://business.tiktokshop.com',
    href:'https://business.tiktokshop.com/us/creator?from=portal_v4&shop_id=123',
  };
  globalThis.window = globalThis;
  globalThis.XMLHttpRequest = function () {};
  XMLHttpRequest.prototype.open = function () {};
  XMLHttpRequest.prototype.send = function () {};

  const resposta = {
    code: 0, message: 'success',
    data: { total: 10, video_list: [{
      video_id: '7412345678901234567',
      title: 'look do dia com calça wide leg',
      creator_name: 'Juliane Benetti',
      share_url: 'https://www.tiktok.com/@ela/video/7412345678901234567',
      product_list: [{
        product_id: '1729419574822508544', product_name: 'Calça wide leg bege',
        status: 'SOLD_OUT', reason: 'product_sold_out', sold_out: true,
      }],
    }] },
  };
  globalThis.fetch = async () => ({ status:200, clone: () => ({ text: async () => JSON.stringify(resposta) }) });

  const restaurar = silenciar();
  eval(fs.readFileSync('./capturar-api-tiktok.js', 'utf8'));
  await window.fetch('https://business.tiktokshop.com/api/v1/creator/video/list?page=1&token=SEGREDO123');
  await window.fetch('https://business.tiktokshop.com/api/v1/metrics/dashboard_theme'); // não interessa
  await new Promise(r => setTimeout(r, 30));
  restaurar();

  const out  = JSON.parse(window.__ttApi());
  const cap  = out.capturas[0];
  const item = cap?.estrutura?.data?.video_list?.[0];
  const prod = item?.product_list?.[0];

  checa('capturou só a chamada relevante',   out.capturas.length === 1, `capturou ${out.capturas.length}`);
  checa('mascarou o token na URL',           !JSON.stringify(out).includes('SEGREDO123'));
  checa('manteve o caminho do endpoint',     cap.endpoint.includes('/api/v1/creator/video/list'));
  checa('NÃO vaza o id do vídeo',            item.video_id === 'string', String(item.video_id));
  checa('NÃO vaza o título do vídeo',        item.title === 'string');
  checa('NÃO vaza o nome da criadora',       item.creator_name === 'string');
  checa('NÃO vaza o nome do produto',        prod.product_name === 'string');
  checa('preserva status',                   prod.status === 'SOLD_OUT', String(prod.status));
  checa('preserva reason',                   prod.reason === 'product_sold_out');
  checa('preserva sold_out',                 prod.sold_out === true);
  checa('preserva o total',                  cap.estrutura.data.total === 10);
  checa('marca o tamanho da lista',          String(cap.estrutura.data.video_list[1]).includes('1 item'));
}

console.log(falhas ? `\n❌ ${falhas} falha(s)` : '\n🎉 Ferramentas de navegador OK');
process.exit(falhas ? 1 : 0);
