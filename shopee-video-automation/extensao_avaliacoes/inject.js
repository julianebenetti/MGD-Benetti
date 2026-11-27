// Roda dentro da página da Shopee. NÃO faz nenhum pedido: só observa as respostas que a própria página já
// recebe (as avaliações do produto e, na página de Oferta Relâmpago, a lista de produtos da oferta) e repassa.
(() => {
  const RE = /rating|review/i;

  function scan(obj, out, depth) {
    if (!obj || typeof obj !== 'object' || depth > 6) return;
    if (Array.isArray(obj)) {
      for (const o of obj) {
        if (o && typeof o === 'object' && typeof o.comment === 'string' && ('rating_star' in o || 'rating' in o)) out.push(o);
        else scan(o, out, depth + 1);
      }
    } else {
      for (const k in obj) scan(obj[k], out, depth + 1);
    }
  }

  // ⚡ Oferta Relâmpago: os produtos que a página da oferta já carregou (itemid, shopid, nome, fim da oferta)
  function scanFlash(obj, out, depth) {
    if (!obj || typeof obj !== 'object' || depth > 7) return;
    if (Array.isArray(obj)) { for (const o of obj) scanFlash(o, out, depth + 1); return; }
    if (obj.itemid && obj.shopid && (obj.name || obj.item_name)) {
      out.push({itemid: obj.itemid, shopid: obj.shopid, nome: obj.name || obj.item_name,
                fim: obj.end_time || obj.flash_sale_end_time || 0});
      return;
    }
    for (const k in obj) scanFlash(obj[k], out, depth + 1);
  }

  function handleFlash(url, text) {
    let data;
    try { data = JSON.parse(text); } catch (e) { return; }
    const found = [];
    scanFlash(data, found, 0);
    if (found.length) window.postMessage({__afilidash: 'relampago', page: location.href, items: found}, location.origin);
  }

  const FLASH = /flash_sale|flashsale/i;
  function route(url, text) {
    if (FLASH.test(url) || FLASH.test(location.pathname)) handleFlash(url, text);
    if (RE.test(url)) handle(url, text);
  }

  function handle(url, text) {
    let data;
    try { data = JSON.parse(text); } catch (e) { return; }
    const found = [];
    scan(data, found, 0);
    if (!found.length) return;
    window.postMessage({
      __afilidash: 'avaliacoes',
      page: location.href,
      ratings: found.map(r => ({
        itemid: r.itemid, shopid: r.shopid, cmtid: r.cmtid,
        estrelas: r.rating_star ?? r.rating,
        comentario: r.comment,
        variacao: (r.product_items && r.product_items[0] && r.product_items[0].model_name) || ''
      }))
    }, location.origin);
  }

  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const resp = await origFetch.apply(this, args);
    try {
      const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
      if (RE.test(url) || FLASH.test(url) || FLASH.test(location.pathname)) resp.clone().text().then(t => route(url, t)).catch(() => {});
    } catch (e) { /* nunca atrapalha a página */ }
    return resp;
  };

  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__afilidashUrl = String(url);
    return origOpen.call(this, method, url, ...rest);
  };
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener('load', () => {
      try {
        const url = this.__afilidashUrl || '';
        if (!RE.test(url) && !FLASH.test(url) && !FLASH.test(location.pathname)) return;
        if (this.responseType === '' || this.responseType === 'text') route(url, this.responseText);
        else if (this.responseType === 'json') route(url, JSON.stringify(this.response));
      } catch (e) { /* nunca atrapalha a página */ }
    });
    return origSend.apply(this, args);
  };
})();
