/* ───────────────────────────────────────────────────────────────
   Capturador da API interna do painel do TikTok Shop
   ───────────────────────────────────────────────────────────────
   PRA QUE SERVE
   O painel em business.tiktokshop.com monta a tela chamando uma API interna.
   Se a gente descobrir qual é a chamada que traz os "Links de produtos
   ocultos", o robô pede a lista direto pra ela — bem mais confiável do que
   ler a tela, que muda de layout toda hora.

   PRIVACIDADE — LEIA
   Ele NÃO manda nada pra lugar nenhum. E, de propósito, ele NÃO guarda os
   valores dos dados: guarda só os NOMES dos campos e o tipo de cada um
   (texto, número...). Os valores só são mantidos em campos de status
   (status, reason, sold_out, stock e parecidos), que são os que me dizem
   como o TikTok escreve "esgotado". Nomes de cliente, e-mail, token e afins
   não vão junto. Valores de parâmetros da URL também saem mascarados.

   COMO USAR
   1. Abra https://business.tiktokshop.com/us/creator?from=portal_v4 logada.
   2. Aperte F12 → aba "Console".
   3. Cole tudo isso e aperte Enter. (Ligue a escuta ANTES de clicar.)
   4. Agora clique: Vídeos → Gerenciar → "Links de produtos ocultos".
   5. Volte no Console e rode:  copy(window.__ttApi())
   6. Cole o resultado pra mim.
   ─────────────────────────────────────────────────────────────── */

(() => {
  const INTERESSA = /video|product|item|link|content|creator|anchor|showcase/i;
  // Campos cujo VALOR ajuda a entender o significado — e que não são dados pessoais.
  const VALOR_OK = /^(.*_)?(status|state|reason|code|msg|message|type|kind|count|total|num|flag|sold.?out|stock|available|invalid|hidden|oculto)(_.*)?$/i;
  const capturas = [];

  function esqueleto(v, prof = 0, chave = '') {
    if (prof > 9) return '…';   // a lista útil costuma estar bem aninhada
    if (Array.isArray(v)) {
      return v.length ? [esqueleto(v[0], prof + 1), `…${v.length} item(s)`] : [];
    }
    if (v && typeof v === 'object') {
      const o = {};
      for (const k of Object.keys(v).slice(0, 60)) o[k] = esqueleto(v[k], prof + 1, k);
      return o;
    }
    if (VALOR_OK.test(chave)) {
      return typeof v === 'string' ? v.slice(0, 60) : v;   // valor preservado: é semântico
    }
    return typeof v;                                        // resto: só o tipo
  }

  function limparUrl(u) {
    try {
      const url = new URL(u, location.origin);
      const params = [...url.searchParams.keys()];
      return url.origin + url.pathname + (params.length ? `?${params.join('=•&')}=•` : '');
    } catch { return String(u).split('?')[0]; }
  }

  function registrar(url, status, texto) {
    if (!url || !INTERESSA.test(url)) return;
    let corpo;
    try { corpo = esqueleto(JSON.parse(texto)); }
    catch { corpo = `(resposta não-JSON, ${String(texto).length} caracteres)`; }
    capturas.push({ endpoint: limparUrl(url), status, estrutura: corpo });
    console.log('📡', limparUrl(url));
  }

  const fetchOriginal = window.fetch;
  window.fetch = async function (...args) {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
    const resp = await fetchOriginal.apply(this, args);
    if (url && INTERESSA.test(url)) {
      resp.clone().text().then(t => registrar(url, resp.status, t)).catch(() => {});
    }
    return resp;
  };

  const openOriginal = XMLHttpRequest.prototype.open;
  const sendOriginal = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (metodo, url, ...resto) {
    this.__ttUrl = url;
    return openOriginal.call(this, metodo, url, ...resto);
  };
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener('load', () => {
      try { registrar(this.__ttUrl, this.status, this.responseText); } catch {}
    });
    return sendOriginal.apply(this, args);
  };

  window.__ttApi = () => JSON.stringify({ pagina: limparUrl(location.href), capturas }, null, 2);

  console.log('%c✅ Escuta ligada.', 'color:#166534;font-weight:bold;font-size:14px');
  console.log('Agora clique: Vídeos → Gerenciar → "Links de produtos ocultos".');
  console.log('Depois rode:  copy(window.__ttApi())   — e cole o resultado pra mim.');
  console.log('Pra desligar, é só recarregar a página (F5).');
})();
