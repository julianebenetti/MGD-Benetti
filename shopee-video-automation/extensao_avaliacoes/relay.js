// Ponte entre a página (inject.js) e a extensão (background.js).
window.addEventListener('message', e => {
  if (e.source === window && e.data && e.data.__afilidash === 'avaliacoes') {
    chrome.runtime.sendMessage(e.data).catch(() => {});
  }
});
