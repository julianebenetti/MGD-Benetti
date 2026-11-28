# 📘 Robô de postagem na Página do Facebook

Posta **uma foto de produto na Página**, com o **link na legenda**, e depois escreve o **link no 1º comentário**.
Usa a Graph API oficial da Meta (só funciona em **Página**, não em perfil pessoal).

> Por padrão o robô **não envia nada** (modo teste). Só posta de verdade com `--enviar`.

## Como funciona
1. Você (ou outro robô) coloca os produtos na `fila.json`: nome, imagem (arquivo ou URL) e link.
2. O robô pega o próximo da fila, posta a foto, espera ~20 s e comenta o link.
3. Ele anota no `estado.json` o que já postou (não repete) e respeita o limite diário (`FB_LIMITE_DIA`, padrão 3).

`fila.json` (veja `fila.exemplo.json`):
```json
[{"id": "p1", "produto": "Nome do produto", "imagem": "imagens/p1.jpg", "link": "https://..."}]
```
Opcional por item: `"legenda"` e `"comentario"` próprios (senão usa os modelos do `.env`).

## Instalar no VPS
1. Copie a pasta `facebook-post/` para o VPS (Python 3, sem instalar nada extra).
2. `cp .env.example .env` e preencha `FB_PAGE_ID` e `FB_PAGE_TOKEN`.
3. Teste o acesso (não posta): `python3 facebook_post.py --testar-token`
4. Veja o que postaria (não envia): `python3 facebook_post.py`
5. Poste de verdade: `python3 facebook_post.py --enviar`

Para postar sozinho em horários (ex.: 10h, 15h e 20h), no `crontab -e`:
```
0 10,15,20 * * * cd /caminho/facebook-post && python3 facebook_post.py --enviar >> robo.log 2>&1
```

## Como conseguir o token da Página (uma vez só)
Os nomes das telas da Meta mudam; confirme na documentação oficial (developers.facebook.com).
1. No **app da Meta** que você já usa (o do Instagram), adicione o caso de uso para **Páginas** com as permissões
   `pages_manage_posts`, `pages_manage_engagement`, `pages_read_engagement` e `pages_show_list`.
2. No **Explorador da Graph API**, gere um token de usuário com essas permissões, escolhendo a sua Página.
3. Troque-o por um token de **longa duração** e peça `GET /me/accounts` para obter o **token da Página** (e o ID dela).
4. Guarde só no `.env` do VPS. **Nunca** cole o token em chat, e-mail ou GitHub.
5. Com o app em modo **Desenvolvimento** e você como admin do app e da Página, deve funcionar sem App Review.

## Cuidados
- Comece com **2 a 5 posts por dia**, variando imagem e legenda. Conteúdo repetitivo ou copiado perde alcance.
- Prefira imagem própria (a do Gemini com texto seu) em vez de imagem copiada de outro site.
- Mantenha a linha de **divulgação de afiliado** na legenda.
- Se a Meta aposentar a versão da API (`FB_GRAPH_VERSION`), atualize no `.env`.

---

# 🤖 Bot do Telegram: uma aba por Página

Você manda **uma foto com o nome do produto e o link na legenda** numa aba do Telegram; o bot enfileira, posta na Página
certa (foto + link na legenda + link no 1º comentário) e avisa na própria aba. Limites por Página (padrão: 3 posts/dia,
2 h de intervalo, só entre 8h e 22h, fila de até 30, 3 tentativas, pausa de 6 h se a Meta pedir calma).

**Começa em MODO TESTE:** não posta nada de verdade até você colocar `BOT_ENVIAR=sim` no `.env`.

## Passo a passo (uma vez só)
1. **Tokens das Páginas:** gere o token do usuário do sistema (Gerenciador de Negócios), coloque em `FB_SYSTEM_TOKEN` no `.env`
   e rode `node obter-tokens-paginas.js`. Ele cria o `paginas.json` (permissão 600). Depois apague `FB_SYSTEM_TOKEN` do `.env`.
2. **Bot do Telegram:** no @BotFather mande `/newbot`, escolha nome e usuário, e coloque o token em `TG_BOT_TOKEN` no `.env`.
   Ainda no @BotFather: `/setprivacy` → escolha o bot → **Disable** (assim ele enxerga as fotos nas abas).
3. **Grupo:** crie um grupo, ative **Tópicos** (Editar grupo → Tópicos), crie 3 abas (uma por Página/nicho) e **adicione o bot como administrador**.
4. **ID do grupo:** escreva qualquer coisa no grupo e rode `python3 bot_telegram.py --descobrir-chat`. Coloque o número em `TG_CHAT_ID`.
5. **Ligar o bot:** `sudo bash instalar-servico.sh` (reinicia sozinho; logs: `journalctl -u facebook-bot -f`).
6. **Ligar cada aba a uma Página:** dentro de cada aba, mande `/aqui bbc`, `/aqui vea` ou `/aqui vip`.
7. **Testar:** mande uma foto com legenda `Nome do produto` + link. No modo teste ele responde "🧪 Eu postaria agora...".
8. **Valendo:** quando estiver satisfeita, `BOT_ENVIAR=sim` no `.env` e `sudo systemctl restart facebook-bot`.

## Comandos (em qualquer aba)
`/fila` · `/postados` · `/desempenho` · `/pausar` · `/retomar` · `/limpar sim` · `/status` · `/ajuda` · `/aqui bbc|vea|vip`

## Por Página (opcional)
Copie `config-bot.exemplo.json` para `config-bot.json` e ajuste `limite_dia`, `intervalo_min` e, se quiser, `legenda`/`comentario`
próprios (use `{produto}` e `{link}`; `\n` quebra linha).

## Cuidados
- Não mande o **mesmo produto** para as 3 Páginas; a Meta trata conteúdo repetido como spam. Nichos separados ajudam.
- Se o bot avisar "A Meta pediu calma 3 vezes", pare e veja o status da Página no Facebook antes de `/retomar`.

---

## 🎬 Vídeos
Mande um **vídeo** (até **20 MB**, limite do Telegram para bots) com a legenda `Nome do produto` + link, igual à foto. O robô posta em
`/{página}/videos` e comenta o link no vídeo (tenta 2 vezes, porque o vídeo demora a processar). Acima de 20 MB ele avisa e não enfileira.

## 🔗 Link rastreável (Shopee)
Se o link for da Shopee (curto `s.shopee.com.br` ou completo), o robô **acha o produto, lê o nome oficial e gera o seu link de afiliado
com sub-ID** no padrão do robô da Shopee Vídeo: `facebook` + sigla da Página + nome breve, em partes separadas
(ex.: `facebook-vea-MacaquinhoCaneladoFe`; o relatório da Shopee junta com `-`). Repetição na mesma Página ganha `V2`, `V3`...
- Sem nome na legenda, a legenda usa o **nome oficial do produto**.
- Se a Shopee falhar, o post segue com o link original e o robô avisa **"SEM rastreio"**.
- Links de outras lojas (Mercado Livre etc.) vão como vieram.
- As chaves vêm do `.env` do robô da Shopee Vídeo (`SHOPEE_ENV`), só leitura. `BOT_CONVERTER_SHOPEE=nao` desliga.

## 📈 Mais posts por dia
Edite no `.env` e reinicie (`sudo systemctl restart facebook-bot`):
- `BOT_LIMITE_DIA` (posts por Página por dia) e `BOT_INTERVALO_MIN` (minutos entre posts). Com a janela 8h–22h (14 h),
  intervalo de 60 min permite até 14 posts/dia por Página; 90 min, até 9.
- **Aquecimento** (recomendado): `BOT_LIMITE_DIA=5`, `BOT_AUMENTO_DIA=1`, `BOT_LIMITE_MAX=12` começa em 5 e sobe 1 por dia até 12.
- Por Página, no `config-bot.json`: `limite_dia`, `limite_max`, `aumento_dia`, `intervalo_min`.
Quanto mais posts, mais atenção ao **alcance**: a Meta reduz a entrega de conteúdo repetitivo. Se o alcance cair, baixe o limite.

## 📜 Como saber o que já foi postado
- **`/postados`** (na aba da Página; ou no Geral para todas): lista os últimos 10 (`/postados 20` para mais) com hora, nome, sub-ID e o link do post.
- **Reação na foto/vídeo que você mandou:** 👀 na fila · 👍 postado · 👎 falhou. Fila cancelada com `/limpar sim` tira a reação.
- A confirmação "✅ Postado" e os avisos vêm como **resposta à própria foto/vídeo**.
- O histórico completo fica em `dados.json` (não vai para o GitHub).

## 📅 Histórico na agenda (aba Postados)
O bot grava `publico/postados.json` a cada mudança (produto, sub-ID, link, link do post, status; **sem tokens**). A agenda lê esse arquivo
na aba **📜 Postados**, com filtro por Página e por status (Postados / Na fila / Falhou). Para isso funcionar a agenda precisa estar no
mesmo endereço do VPS: veja `pauta-vps/README.md`.

## 📈 Desempenho (/desempenho)
Precisa do token com `read_insights` (o `obter-tokens-paginas.js` avisa). `/desempenho` (ou `/desempenho 10`) mede os últimos posts de verdade:
**alcance** (tenta `post_impressions_unique`, depois `post_media_view`, depois `post_impressions`), reações, comentários e compartilhamentos.
O que a Meta não entregar aparece como `—`. O resultado também vai para a aba **Postados** da agenda. Vendas: relatório da Shopee, filtrando `facebook-`.

## ✍️ Variações de legenda e comentário
Cada post usa uma legenda e um 1º comentário **sorteados** de uma lista (7 legendas e 5 comentários prontos), **sem repetir o último usado na mesma Página**.
Todos os modelos têm o aviso de link de afiliado. Para ter os seus, use `legendas` e `comentarios` por Página no `config-bot.json`
(veja `config-bot.exemplo.json`; `{produto}` e `{link}` são preenchidos sozinhos). Dica: escreva o nome do produto e **uma frase sua** na legenda
da foto; ela entra no lugar de `{produto}` e deixa cada post diferente.
