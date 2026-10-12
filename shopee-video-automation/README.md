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
- se faltar o link por 30 s, o robô pergunta uma vez;
- se o robô não achar o produto, **responda a mensagem de erro (ou o próprio vídeo) com o link certo**:
  ele refaz o vídeo sem você reenviar nada (vale mesmo depois de o robô reiniciar).

**Vídeos da Central Post TikTok** — o bot precisa estar no grupo do TikTok como **administrador**
(sem permissões especiais). Mande **`/brutos`** uma vez dentro do tópico Brutos: a partir daí cada
vídeo novo ali é copiado para 📥 Envios, onde o robô pede o link. Nada é escrito no grupo do TikTok.

Reações: 👌 recebido · ✍ link guardado para a próxima leva · 👍 editado · 🤔 não deu (o robô explica).

**✅ Editados** — capa + vídeo + textos e links. Botões **✅ Aprovar capa** · **🔄 Outra headline** ·
**✅ Aprovar e agendar** (só depois da capa aprovada) · **❌ Descartar**. Trocar a headline pede nova
aprovação da capa. Para usar uma headline sua, **responda** a mensagem com o texto.

Ao **✅ Aprovar e agendar**, o robô junta a capa na abertura do vídeo (`CAPA_SEGUNDOS`, padrão 1 s):
esse vídeo final é o que vai para a Agenda.

**⏰ Agenda** — aprovados com dia e horário. Na hora: aviso "⏰ Hora de postar!" e botão
**✅ Postei**, que move para Postados. (Quando o bot que posta na Shopee for conectado, esse envio
fica automático.)

## Regras

| Tema | Regra |
|---|---|
| Produto | Descoberto pelo link (produto, link curto ou link de vídeo); a IA confere nos quadros do vídeo |
| Links extras | Mesmo produto em outras lojas, maior comissão (sem piso), nota ≥ 4,5, confirmado pela IA |
| Sub_id | `Data + SV + Produto` (ex.: `11Out26SVSapateiraBanco`), `V2`/`V3` se repetir; o mesmo nos 3 links |
| Capa | Tudo dentro do recorte 3:4 da grade do perfil (logo a 14%; cartão ancorado logo acima do contador de views, crescendo para cima até quase a headline). Quadro do vídeo com logo, headline e **cartão "N Variações Disponíveis"** (miniaturas das variações do produto principal: cor, modelo, voltagem, kit…), à esquerda, sem inclinação |
| Headline | Gerada pela IA, até 60 caracteres, termina com 😱🔥, vende a transformação; gatilhos em rodízio (Choque, Urgência, Curiosidade, Dor, Autoridade); nunca repete para o mesmo produto |
| Compliance | Sem preço, sem falsa escassez, sem inventar características, avaliações ou descontos |
| Agenda | 10 posts/dia entre 9h e 22h, horários quebrados, nunca o mesmo produto no mesmo dia |

Ajustes no `.env`: `LINKS_POR_VIDEO`, `AGENDA_POSTS_POR_DIA`, `AGENDA_INICIO`, `AGENDA_FIM`.

## Instalação no VPS

1. Ative **Tópicos** no grupo e deixe o bot admin com **Gerenciar tópicos** e **Apagar mensagens**.
2. No terminal do VPS, rode:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/julianebenetti/MGD-Benetti/claude/shopee-video-posts-fy4an1/shopee-video-automation/instalar.sh | bash
   ```
   Na primeira vez ele baixa o código em `/opt/shopee-video`, cria o `.env` e para.
3. `nano /opt/shopee-video/shopee-video-automation/.env`, preencha as chaves, salve e rode o mesmo comando.
   Ele instala tudo, cria os tópicos e liga o serviço `shopee-video`. O mesmo comando também atualiza.

| O quê | Comando |
|---|---|
| Ver logs | `journalctl -u shopee-video -n 50` |
| Reiniciar | `sudo systemctl restart shopee-video` |
| Testes rápidos | `.venv/bin/python test_automation.py` |
| Diagnóstico do cartão de variações | `.venv/bin/python diagnostico.py <link do produto>` (manda o print da página para Envios) |

Se a Shopee pedir login/captcha ao abrir páginas de vídeo, rode uma vez com
`SHOPEE_BROWSER_HEADLESS=false` numa máquina com tela para entrar na conta.

## Arquivos

| Arquivo | Função |
|---|---|
| `bot.py` | Robô: Telegram, botões, fila, agenda |
| `pipeline.py` | Prepara um vídeo do início ao fim |
| `shopee_affiliate.py` | API de afiliados: produto, outros vendedores, link de afiliado |
| `video_page_reader.py` | Abre a página do Shopee Video e acha os produtos |
| `product_page_capture.py` | Miniaturas das variações disponíveis na página do produto |
| `product_matcher.py` | Conferência vídeo × produto por IA |
| `content_generator.py` | Headline (rodízio de 5 gatilhos), descrição, hashtags, SEO |
| `ai_client.py` | Chamada à OpenAI com resposta em JSON por esquema |
| `video_processor.py` / `cover_generator.py` | Vídeo 9:16 com logo / capa |
| `scheduler.py` / `storage.py` | Agenda / estado (SQLite `estado.db`) |
| `sub_id.py` | Sub_id dos links |
| `setup_topics.py` / `instalar.sh` | Configuração inicial |

## Limites conhecidos

- O Telegram só deixa o bot baixar arquivos de até **20 MB**.
- Cada vídeo usa várias chamadas à OpenAI (conferência de até 7 produtos + textos).
