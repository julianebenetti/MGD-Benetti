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
