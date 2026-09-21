/* ───────────────────────────────────────────────────────────────
   Inspetor do painel de vídeos do TikTok (no navegador)
   ───────────────────────────────────────────────────────────────
   PRA QUE SERVE
   Descobrir se a tela de "Links de produtos ocultos" existe na versão web
   e como ela é montada, pra dar pra escrever um robô que leia essa lista.

   O QUE ELE FAZ: só LÊ o que já está na tela e imprime no console.
   Não clica em nada, não envia nada pra lugar nenhum, não muda nada na
   sua conta. Dá pra ler o código inteiro abaixo — são 25 linhas.

   COMO USAR
   1. Abra affiliate.tiktok.com (ou seller-br.tiktok.com), logada.
   2. Navegue até a área de Vídeos / Conteúdo e aplique o filtro de
      links ocultos, se existir.
   3. Aperte F12 → aba "Console".
   4. Cole tudo isso e aperte Enter.
   5. Mande pra mim o que aparecer (print serve).
   ─────────────────────────────────────────────────────────────── */

(() => {
  const alvo = /oculto|hidden|precisam de aten|need(s)? attention|esgotad|sold ?out|out of stock|removid|unavailable|indispon|vincular|relink/i;

  const achados = [];
  document.querySelectorAll('body *').forEach(el => {
    if (el.children.length) return;                 // só folhas: evita repetir o texto do pai
    const t = (el.textContent || '').trim();
    if (t && t.length < 160 && alvo.test(t)) {
      achados.push({ texto: t, tag: el.tagName, classe: String(el.className).slice(0, 60) });
    }
  });

  const videos = [...new Set([...document.querySelectorAll('a[href*="/video/"]')].map(a => a.href))];

  console.log('%c── Inspetor do painel TikTok ──', 'font-weight:bold;font-size:14px');
  console.log('URL atual :', location.href);
  console.log('Trechos relevantes encontrados:', achados.length);
  console.table(achados.slice(0, 40));
  console.log('Links de vídeo visíveis na página:', videos.length);
  console.log(videos.slice(0, 20));

  if (!achados.length) {
    console.log('%c⚠ Nada encontrado nesta tela.', 'color:#b45309');
    console.log('Tente navegar até a lista de vídeos e rodar de novo, ou me diga quais');
    console.log('menus aparecem no site — pode ser que o filtro só exista no app.');
  }

  console.log('\nPra copiar o resultado inteiro, rode: copy(window.__ttResultado)');
  window.__ttResultado = { url: location.href, achados, videos };
  return `${achados.length} trecho(s) e ${videos.length} link(s) de vídeo. Veja a tabela acima.`;
})();
