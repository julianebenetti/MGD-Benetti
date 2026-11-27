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
`/fila` · `/pausar` · `/retomar` · `/limpar sim` · `/status` · `/ajuda` · `/aqui bbc|vea|vip`

## Por Página (opcional)
Copie `config-bot.exemplo.json` para `config-bot.json` e ajuste `limite_dia`, `intervalo_min` e, se quiser, `legenda`/`comentario`
próprios (use `{produto}` e `{link}`; `\n` quebra linha).

## Cuidados
- Não mande o **mesmo produto** para as 3 Páginas; a Meta trata conteúdo repetido como spam. Nichos separados ajudam.
- Se o bot avisar "A Meta pediu calma 3 vezes", pare e veja o status da Página no Facebook antes de `/retomar`.
