# Robô do Shopee Video — Achados Relâmpagos

Robô de Telegram sempre ligado que prepara os vídeos do Shopee Video: vídeo 9:16 com logo,
capa com headline, descrição, hashtags, SEO e 3 links de afiliado (o produto do vídeo + 2 de
outros vendedores), com aprovação e agenda.

## Fluxo (tópicos do grupo "Shopee Video Bot")

```
📥 Envios  →  ✅ Editados (sua aprovação)  →  ⏰ Agenda  →  🚀 Postados
```

**📥 Envios** — mande o vídeo com o link Shopee na legenda. Também vale:
- vários vídeos e depois **um link** (vale para todos);
- **o link antes** e os vídeos depois (até 10 min);
- se faltar o link por 30 s, o robô pergunta uma vez.

Reações: 👌 recebido · ✍ link guardado para a próxima leva · 👍 editado · 🤔 não deu (o robô explica).

**✅ Editados** — capa + vídeo + textos e links. Botões **✅ Aprovar** · **🔄 Outra headline** ·
**❌ Descartar**. Para usar uma headline sua, **responda** a mensagem com o texto.

**⏰ Agenda** — aprovados com dia e horário. Na hora: aviso "⏰ Hora de postar!" e botão
**✅ Postei**, que move para Postados. (Quando o bot que posta na Shopee for conectado, esse envio
fica automático.)

## Regras

| Tema | Regra |
|---|---|
| Produto | Descoberto pelo link (produto, link curto ou link de vídeo); a IA confere nos quadros do vídeo |
| Links extras | Mesmo produto em outras lojas, maior comissão, comissão ≥ R$ 9 e nota ≥ 4,5, confirmado pela IA |
| Sub_id | `Data + SV + Produto` (ex.: `11Out26SVSapateiraBanco`), `V2`/`V3` se repetir; o mesmo nos 3 links |
| Headline | Gerada pela IA, até 60 caracteres, termina com 😱🔥, nunca repete para o mesmo produto |
| Compliance | Sem preço, sem falsa escassez, sem inventar características, avaliações ou descontos |
| Agenda | 10 posts/dia entre 9h e 22h, horários quebrados, nunca o mesmo produto no mesmo dia |

Ajustes no `.env`: `LINKS_POR_VIDEO`, `AGENDA_POSTS_POR_DIA`, `AGENDA_INICIO`, `AGENDA_FIM`.

## Instalação no VPS

1. Copie esta pasta para o VPS.
2. Ative **Tópicos** no grupo e deixe o bot admin com **Gerenciar tópicos**.
3. Rode `bash instalar.sh`. Na primeira vez ele cria o `.env`: preencha as chaves e rode de novo.
   Ele instala tudo, cria os tópicos e liga o serviço `shopee-video`.

| O quê | Comando |
|---|---|
| Ver logs | `journalctl -u shopee-video -n 50` |
| Reiniciar | `sudo systemctl restart shopee-video` |
| Testes rápidos | `.venv/bin/python test_automation.py` |

Se a Shopee pedir login/captcha ao abrir páginas de vídeo, rode uma vez com
`SHOPEE_BROWSER_HEADLESS=false` numa máquina com tela para entrar na conta.

## Arquivos

| Arquivo | Função |
|---|---|
| `bot.py` | Robô: Telegram, botões, fila, agenda |
| `pipeline.py` | Prepara um vídeo do início ao fim |
| `shopee_affiliate.py` | API de afiliados: produto, outros vendedores, link de afiliado |
| `video_page_reader.py` | Abre a página do Shopee Video e acha os produtos |
| `product_matcher.py` | Conferência vídeo × produto por IA |
| `content_generator.py` | Headline, descrição, hashtags, SEO |
| `video_processor.py` / `cover_generator.py` | Vídeo 9:16 com logo / capa |
| `scheduler.py` / `storage.py` | Agenda / estado (SQLite `estado.db`) |
| `sub_id.py` | Sub_id dos links |
| `setup_topics.py` / `instalar.sh` | Configuração inicial |

## Limites conhecidos

- O Telegram só deixa o bot baixar arquivos de até **20 MB**.
- Cada vídeo usa várias chamadas à Claude (conferência de até 7 produtos + textos).
