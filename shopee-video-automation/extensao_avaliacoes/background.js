// Junta as avaliações de cada produto por alguns segundos e manda para o robô no VPS.
importScripts('config.js');

const pending = {};
let timer = null;

function idsFromUrl(url) {
  const m = /-i\.(\d+)\.(\d+)/.exec(url) || /\/product\/(\d+)\/(\d+)/.exec(url);
  return m ? {shop: m[1], item: m[2]} : {};
}

function badge(tabId, text, color) {
  if (tabId == null) return;
  chrome.action.setBadgeText({tabId, text});
  chrome.action.setBadgeBackgroundColor({tabId, color});
}

async function flush(tabId) {
  for (const key of Object.keys(pending)) {
    const [shopId, itemId] = key.split('/');
    const reviews = Object.values(pending[key]);
    delete pending[key];
    try {
      const resp = await fetch(self.AFILIDASH.url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Chave': self.AFILIDASH.chave},
        body: JSON.stringify({shopId, itemId, reviews})
      });
      const data = resp.ok ? await resp.json() : {};
      badge(tabId, resp.ok ? String(data.total || reviews.length) : '!', resp.ok ? '#16a34a' : '#dc2626');
    } catch (e) {
      badge(tabId, '!', '#dc2626');
    }
  }
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || msg.__afilidash !== 'avaliacoes') return;
  const ids = idsFromUrl(msg.page || '');
  for (const r of msg.ratings || []) {
    const item = String(r.itemid || ids.item || '');
    const shop = String(r.shopid || ids.shop || '');
    const text = (r.comentario || '').trim();
    if (!item || !text) continue;
    const key = `${shop}/${item}`;
    pending[key] = pending[key] || {};
    pending[key][r.cmtid || text] = {estrelas: r.estrelas, comentario: text, variacao: r.variacao || ''};
  }
  clearTimeout(timer);
  timer = setTimeout(() => flush(sender.tab && sender.tab.id), 3000);
});
