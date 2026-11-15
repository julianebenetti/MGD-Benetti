# 📲 PostZap

App **separado** da AfiliDash e do robô do Shopee Vídeo para postar links da Shopee nos grupos de WhatsApp,
**com aprovação de cada postagem**. Endereço: `posts.descontoirresistivel.com.br/zap`.

## O que ele faz
- **Produtos** de duas fontes, só leitura (nada é alterado nelas):
  - 🎬 **Vendeu em vídeo** e 💡 **Ideias** — da Central Shopee Vídeo (`estado.db` do robô no VPS);
  - ⛏️ **Garimpo** — tabela `garimpo_produtos` do Supabase.
  - Suplementos/vitaminas/colágeno/whey são bloqueados; comissão mínima R$ 9.
- 🏬 **Outras lojas** (Magalu, Mercado Livre, Amazon…): cole o seu link de afiliado; o PostZap tenta ler nome, foto e
  preço da página (se a loja bloquear, você preenche à mão). O link enviado é sempre o seu, com o seu código de afiliado.
- **Preparar postagem** → mensagem pronta pelo modelo (editável) → escolhe grupos e horário → **✅ Aprovar**.
- **Mensagem no formato dos grupos de ofertas**: chamada em maiúsculas, 🛍️ nome, ~De~ / *Por* ✅, 🔗 Compre aqui, ⚠️ aviso.
- **Prévia do link** (miniatura + título `@descontoirresistivel`): o link vira `posts.descontoirresistivel.com.br/zap/l/xxxx`,
  que mostra a foto do produto no WhatsApp e leva para o link de afiliado da Shopee (com Sub ID `postzap`, para ver no
  relatório as vendas do WhatsApp). Conta os cliques. É só texto: não pesa no celular de quem recebe.
- **3 chips (admins)**: cada postagem sorteia qual chip envia em cada grupo (sem repetir o mesmo chip seguido no
  grupo), embaralha a ordem dos grupos e espera 90–240 s entre eles. Limite de 8 posts/dia por grupo.
- 💬 **Conversa no WhatsApp**: do seu número (`NUMEROS_AUTORIZADOS`), compartilhe o link de um produto com qualquer
  um dos chips. Ele responde com a prévia pronta (chamada automática por IA, foto, preço, link curto) e o menu:
  `1` aprovar · `2` chamada · `3` preço De · `4` preço Por · `5 20h` agendar · `0` descartar. Avisa quando terminar.
- Avisa quando o produto já foi postado; histórico de tudo que saiu; botão ⏸️ para pausar todos os envios.
- Dados próprios em `postzap.db` (grupos, fila, histórico). Não usa nenhuma tabela da AfiliDash.

## Instalar no VPS (terminal da Hostinger)
```
curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/admiring-dirac-ku5zlh/postzap/instalar.sh | bash
```
Na primeira vez ele cria `/opt/postzap/postzap/.env`: preencha `POSTZAP_SENHA` (senha de entrada) e `SUPABASE_KEY`
(a mesma chave anon usada no `garimpo-shopee.html`) e rode o comando de novo. Ele instala o Docker (se faltar),
sobe o WhatsApp (Evolution API) e cria o serviço `postzap`.

## Publicar no endereço (uma vez)
1. No painel DNS do domínio: registro **A** `posts` → IP do VPS (se ainda não existir).
2. No Nginx do VPS, dentro do `server { server_name posts.descontoirresistivel.com.br; ... }`:
   ```
   location /zap/ { proxy_pass http://127.0.0.1:8790; proxy_set_header Host $host; }
   location = /zap { return 301 /zap/; }
   ```
   `sudo nginx -t && sudo systemctl reload nginx` (HTTPS: `sudo certbot --nginx -d posts.descontoirresistivel.com.br`).

## Primeiro uso
1. 🔗 **WhatsApp** → leia o QR de **cada um dos 3 chips** (Aparelhos conectados).
2. 👥 **Grupos** → "Buscar grupos" e marque onde pode postar.
3. ✏️ **Modelo** → ajuste a mensagem (vamos copiar o formato do PromosApp quando chegarem os prints).
4. 🛍️ **Produtos** → Preparar postagem → Aprovar.

## Cuidados contra ban
Chip só para isso, admin nos grupos, poucas postagens por dia, nunca o mesmo texto em dezenas de grupos seguidos.
Ajuste `INTERVALO_*` e `LIMITE_POSTS_DIA_POR_GRUPO` no `.env`.

Logs: `journalctl -u postzap -f` · WhatsApp: `docker logs -f postzap-evolution`
