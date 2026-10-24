# Robô do Shopee Video — Achados Relâmpagos

Robô de Telegram sempre ligado que prepara os vídeos do Shopee Video: vídeo 9:16 com logo,
capa com headline, descrição, 3 hashtags, SEO e 5 links de afiliado (a loja divulgada + 4 de
outros vendedores), com aprovação e agenda.

## Fluxo (tópicos do grupo "Shopee Video Bot")

```
📥 Envios  →  ✅ Editados (sua aprovação)  →  ⏰ Agenda  →  🚀 Postados      (+ 📌 Pendências e 📊 Relatório)
```

**📥 Envios** — mande o vídeo com o link Shopee na legenda. Também vale:
- vários vídeos e depois **um link** (vale para todos);
- **o link antes** e os vídeos depois (até 10 min);
- vários vídeos num **álbum** com o link na legenda de um deles: vale para o álbum todo;
- vídeo sem link: o robô reage com 👀 e em poucos segundos pergunta **em cada vídeo**: responda o vídeo com o link (só ele) ou
  mande um link solto (vale para todos os vídeos sem link). Os outros vídeos não ficam esperando;
- a fila fica gravada: se o robô reiniciar (ex.: numa atualização), ele retoma os vídeos da fila, os que
  esperam link e os agendamentos em andamento;
- o robô prepara 2 vídeos ao mesmo tempo (`VIDEOS_AO_MESMO_TEMPO`): um vídeo com problema não segura os outros;
- se o robô não achar o produto, **responda a mensagem de erro (ou o próprio vídeo) com o link certo**:
  ele refaz o vídeo sem você reenviar nada (vale mesmo depois de o robô reiniciar);
- se o vídeo mostra **outra variação** do produto do link (outra cor, estampa ou modelo), o robô avisa e
  pede: toque **✅ Pode seguir** para usar o mesmo link, ou responda com o link da variação certa.
  O link que você confirma ou reenvia não passa de novo pela conferência da IA.

**Vídeos da Central Post TikTok** — o bot precisa estar no grupo do TikTok como **administrador**
(sem permissões especiais). Mande **`/brutos`** uma vez dentro do tópico Brutos: a partir daí cada
vídeo novo ali é copiado para 📥 Envios, onde o robô pede o link. Nada é escrito no grupo do TikTok.

Reações: 👌 recebido · ✍ link guardado para a próxima leva · 👍 editado · 🤔 não deu (o robô explica).

**✅ Editados** — capa + vídeo + textos e links. Se houver loja pagando mais, primeiro vem a pergunta da troca. Logo abaixo, o robô pede **o print das variações**:
responda essa mensagem com o print do app/site (a tela com as miniaturas) e ele recorta e monta o
cartão "N Variações Disponíveis" na capa; para produto sem variações, toque em **Sem variações**.
A capa só pode ser aprovada depois disso. Botões **✅ Aprovar capa** · **🔄 Outra headline** ·
**✅ Aprovar legenda** · **📝 Outra legenda** · **✅ Aprovar e agendar** (só com capa e legenda aprovadas) ·
**❌ Descartar**. Trocar a headline pede nova aprovação da capa. **Responda** a mensagem dos textos com
um texto curto para usar uma headline sua, ou com um texto com #hashtags para usar uma legenda sua (já
entra aprovada).
Nos botões, **⬜** = falta aprovar e **✔️ … APROVADA** = já aprovado (tocar de novo não faz nada); o
**🔒 Aprovar e agendar** vira **📅** quando capa e legenda estão aprovadas e **⏳ Agendando…** depois do toque.

Ao **✅ Aprovar e agendar**, o robô junta a capa na abertura do vídeo (`CAPA_SEGUNDOS`, padrão 1 s):
esse vídeo final é o que vai para a Agenda.

**⏰ Agenda** — aprovados com dia e horário. Na hora, o robô manda o vídeo final para a **LiA**
(@Liaautomacao_bot), toca em **Publicar** no resumo dela e move o post para 🚀 Postados. Se algo
falhar, ele avisa na Agenda com os botões **📤 Enviar à LiA** (tentar de novo) e **✅ Postei**.
Sem a LiA configurada: aviso "⏰ Hora de postar!" e botão **✅ Postei**.

**📌 Pendências** — uma mensagem fixada que o robô mantém atualizada com tudo que espera uma ação sua,
separado por tópico (vídeo sem link, link a corrigir, variação a confirmar, loja a escolher, print das
variações, capa a aprovar, aprovar e agendar, post que não foi para a LiA). Cada item é um link que abre a
mensagem certa. Quando não há nada: "✅ Nada esperando por você". (Para fixar, o bot precisa da permissão
**Fixar mensagens**; sem ela a lista funciona igual, só não fica fixada.)

**📊 Relatório** — todo dia às 22:30 (`RELATORIO_HORA`) o robô manda o resumo do dia: postados (meta,
pela LiA × manual, horário, loja e comissão de cada um), descartados, comissão média e maior dos itens
divulgados, trocas por loja de comissão maior, o que está em Editados/Agenda/Pendências e o gráfico dos
últimos 7 dias. A qualquer hora: **`/relatorio`** (hoje) ou **`/relatorio 10/10`** (outro dia), em
qualquer tópico do grupo.

**💡 Ideias** — todo dia às 7:30 (`IDEIAS_HORA`) e quando você pede **`/sugestoes`**: pelo menos 15 produtos
para gravar, das datas comemorativas dos próximos 90 dias e de **20 nichos** (cozinha, organização,
banheiro, limpeza, decoração, quarto, pet, bebê, beleza, moda, calçados/roupas, tecnologia, casa inteligente,
escritório, fitness, carro, jardim, ferramentas, viagem, festa/presentes), 12 por dia em rodízio, com uma
palavra-chave diferente por dia e no máximo 2 ideias por nicho. Regras do Garimpo: comissão ≥ R$ 9 por venda, nota ≥ 4,7, ≥ 100 vendas, nunca suplementos; sem
produtos já postados/agendados nem sugeridos nos últimos 30 dias, nem o mesmo tipo de produto de outra loja
(ex.: "capa de almofada natal" de lojas diferentes conta como repetido). Ordenadas por comissão × vendas (a API de
afiliados não informa "mais buscados", o sinal de procura é o total de vendas). Cada ideia traz preço,
comissão, vendas, nota, a data/categoria e o link do produto para gravar.
Além das 15 principais, até 10 de **💸 Preço acessível** (o que mais gira no Shopee Vídeo): até R$ 60
(`IDEIAS_PRECO_ACESSIVEL`), comissão ≥ R$ 3 por venda (`IDEIAS_COMISSAO_ACESSIVEL`), 500+ vendas, nota ≥ 4,7.

**🎬 Prompts** — prompts para gerar os vídeos com IA (YouTube Create), usando a mesma OpenAI do robô. Mande o **link do
produto** (com uma observação, se quiser): o robô olha a foto do anúncio e devolve os detalhes que não podem mudar
(contagem de peças, estampas, flores, formato), o prompt em inglês para usar com a foto como imagem inicial, o que
evitar e 3 cenas. **Responda o prompt** para ajustar (ex.: "mais movimento"). Quando um vídeo é barrado por detalhe
diferente, a mensagem em 📥 Envios tem **🎬 Prompt corrigido**, que gera um prompt reforçando o detalhe que mudou.

**💵 Vendas reais** (relatório de conversões da API de afiliados): o relatório do dia traz os pedidos e a
comissão do dia; **`/vendas`** (últimos 7 dias), **`/vendas hoje`** ou **`/vendas 30`** mostram as vendas por
vídeo (pelo sub_id de cada um), pendente × concluída, cancelados e o que veio de links fora do robô. A
Shopee pode levar algumas horas para mostrar uma venda, e só deixa consultar de novo depois de 30 segundos.

**Proteção da conta (Produto Irrelevante):**
- **`/pausar 25/10 18:30`** (ou só `/pausar`, até **`/retomar`**): nada vai para a LiA; ao fim, os vídeos que ficaram para
  trás ganham novos horários em sequência, com as regras da agenda.
- **`/validaragenda`**: validação rigorosa (6 quadros, mesmo modelo) de todos os posts da Agenda; tira lojas extras que
  não batem e **retém** (não manda para a LiA) o post cujo produto divulgado não bate com o vídeo.
- **`LIA_MAX_LINKS`** (padrão 2): quantos links vão para a LiA (o divulgado + os extras de maior comissão). Cada link
  extra é mais um produto que a Shopee pode julgar irrelevante.

## LiA (bot que posta no Shopee Video)

Bot não conversa com bot no Telegram, então o envio sai **pela sua conta** (o que você faria à mão).
O que vai para a LiA:
- o vídeo final (capa na abertura + logo) com `#semcapa #semmarca`, para ela não colocar de novo;
- os 5 links (`LINKS_POR_VIDEO`) do **menor para o maior** comissionamento e, por último (em destaque), a loja que você escolheu divulgar;
- a descrição + hashtags do robô com `#semia` (`LIA_LEGENDA=ia` deixa a LiA escrever);
- `#postar` (ou `#rascunho` com `LIA_MODO=rascunho`).

Configuração (uma vez):
1. Em **my.telegram.org** → *API development tools*, crie um app (nome e descrição quaisquer) e
   copie **api_id** e **api_hash** para `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` no `.env`.
2. Rode o comando de instalação de novo (instala a biblioteca) e depois, no VPS:
   `cd /opt/shopee-video/shopee-video-automation && .venv/bin/python lia_login.py`
   — digite seu telefone (+55…), o código que chega no seu Telegram e a senha de duas etapas, se tiver.
3. `sudo systemctl restart shopee-video`. O log mostra `LiA: ligada (agenda)`.

**Confirmação da publicação:** tocar em Publicar só põe o vídeo na fila da LiA; quem publica é o
tablet/celular. O post fica **🤖 na LiA** e, a cada 5 minutos, o robô lê a conversa com ela: "Vídeo salvo na
Shopee ✅" → vai para 🚀 Postados com a data/hora dessa mensagem (horário real da postagem); "Não consegui publicar" (ex.: tablet desligado) ou erro ao mandar → **reagendado** no próximo horário
livre da agenda (mesmas regras), com aviso do motivo, e reenviado nesse horário até ser publicado; sem resposta em 2 h (`LIA_ALERTA_HORAS`) → aviso. **`/verificarlia`** confere a conversa
toda pela última tentativa de cada vídeo: se falhou e foi reenviado com sucesso, fica em Postados com a
data/hora real da postagem; se a última tentativa falhou, volta para a Agenda (feito uma vez, sozinho, ao ligar
esta versão).

O login fica em `lia.session`, só no VPS (nunca no GitHub). Ele dá acesso à sua conta: não copie esse
arquivo para lugar nenhum. Para desligar o envio: `LIA_ENVIAR=nao`. Para mandar logo ao aprovar, em vez de
no horário da agenda: `LIA_ENVIAR=aprovar`. Para só mandar e você tocar em Publicar: `LIA_PUBLICAR_AUTO=nao`.

## Regras

| Tema | Regra |
|---|---|
| Produto | Descoberto pelo link (produto, link curto ou link de vídeo); a IA confere nos quadros do vídeo, inclusive a variação (cor/estampa/modelo) |
| Conferência de detalhes | Vídeos gerados por IA costumam mudar detalhes (outra flor na estampa, 4 barras em vez de 2). A conferência rigorosa (8 quadros em alta resolução) compara detalhe por detalhe: quantidade de peças/barras/prateleiras, estampas, flores, desenhos, textos, formato e acessórios, e diz qual detalhe difere. Ela roda **já na chegada do vídeo** (antes de capa e textos) e de novo antes da Agenda |
| Validação antes da Agenda | Ao tocar **Aprovar e agendar**, a IA compara 6 quadros do vídeo com a foto de cada link e exige o **mesmo modelo** (formato, design, quantidade/kit). O **produto divulgado** (o que a Shopee confere no "Produto Irrelevante") precisa ser **idêntico ao vídeo, na mesma variação da foto do anúncio**: outra cor/estampa/modelo bloqueia o agendamento. Nesse caso o robô procura outro anúncio cuja foto seja igual ao vídeo e oferece **🔁 Usar <loja> (idêntico)**; há também **📅 Agendar mesmo assim (risco)**. Lojas extras que não passam saem e são repostas com outras validadas. O resultado aparece na Agenda |
| Conferir e trocar links | Cada link mostra **🔎 conferir o anúncio** (página normal do produto, sem gerar clique no seu link de afiliado). Para trocar por um link que você achou, responda a mensagem dos textos com o **número e o link** (ex.: `3 https://s.shopee.com.br/…`): o robô troca, gera o seu link de afiliado com o mesmo sub_id e mostra preço, nota e comissão |
| Link esgotado | A API da Shopee não informa estoque. Em ✅ Editados, toque **🚫 N** no link esgotado: o robô tira, repõe com a próxima loja já conferida (se for o 1º, a próxima vira a divulgada) e não sugere esse anúncio por 7 dias |
| Links extras | Mesmo produto (**mesmo modelo**; variação parecida fica de fora) em outras lojas (**cada loja aparece uma vez só**, com o anúncio de maior comissão dela), maior comissão (sem piso), nota ≥ 4,5, confirmado pela IA (até 10 lojas conferidas ao mesmo tempo). A mensagem mostra a comissão estimada de cada link |
| Escolha da loja divulgada | Se outras lojas pagam mais que a do seu link, o robô lista até 5 em ✅ Editados com **preço, nota e comissão** de cada uma (e da sua) e o link para abrir. Toque na loja que quer divulgar (ou **Manter o meu**): ela vira o 1º link e os outros são as maiores comissões. O pedido do print das variações vem depois dessa escolha |
| Sub_id | `SV-<data da publicação>-<produto>` (ex.: `SV-14Out26-SapateiraBanco`), `V2`/`V3` se repetir; o mesmo em todos os links do vídeo. Vai como 3 sub_ids (SV, data, produto), que o relatório da Shopee junta com "-". Em Editados é provisório (data de hoje); ao agendar, o robô refaz com a data agendada |
| Capa | Tudo dentro do recorte 3:4 da grade do perfil (logo a 14%; cartão ancorado logo acima do contador de views, crescendo para cima até quase a headline). Quadro do vídeo com logo, headline e **cartão "N Variações Disponíveis"** (miniaturas das variações do produto principal: cor, modelo, voltagem, kit…), à esquerda, sem inclinação |
| Headline | Gerada pela IA, até 60 caracteres, vende a transformação; gatilhos em rodízio (Choque, Urgência, Curiosidade, Dor, Autoridade); nunca repete para o mesmo produto. Termina com **um emoji** sorteado pelo gatilho: Choque 😱 🤯 😳 · Urgência 🔥 ⚡ 💥 · Curiosidade 👀 🤔 🤫 · Dor 🙌 🥹 😌 · Autoridade ⭐ 🏆 🫶 (listas em `EMOJIS_FINAIS`, `content_generator.py`). Headline digitada por você vai como está |
| CTA | Nos 5 segundos finais do vídeo (`CTA_SEGUNDOS`), uma CTA sorteada em faixas brancas, um pouco abaixo do meio: "Adicione já ao carrinho!", "Clique na sacolinha e garanta o seu!", "Leva esse achadinho pra casa!", "Já coloca no carrinho e garante o seu!", "Compre agora e aproveite o desconto!", "Aproveita o preço especial!", "Compre com o cupom!" (lista `CTAS` em `pipeline.py`) |
| Legenda | Descrição + **3 hashtags** em até **150 caracteres no total** (cortada no fim de uma palavra se precisar). SEO + persuasão: começa pela palavra-chave como as pessoas buscam, cita quantidade/kit/tamanho/modelo (regra de relevância), benefício sensorial e específico, chamada para ação; hashtags = palavra-chave principal + categoria/cauda longa + uso/ocasião |
| CTA | Laranja Shopee com letra branca e sombra (aparece em vídeo claro ou escuro), na área segura da tela cheia: longe do corte lateral (~9% de cada lado), dos botões da direita e do card do produto |
| Logo no vídeo | 11% da borda esquerda e 12% do topo: inteiro na tela cheia (o app corta as laterais) e abaixo da seta/busca |
| Compliance | Sem preço, sem falsa escassez, sem inventar características, avaliações ou descontos |
| Agenda | Em sequência, entre 9h e 22h, até 10 por dia (os já postados contam), horários quebrados (ex.: 14:37). Cada vídeo entra de 1 a 2 h depois do anterior; quando é preciso para caberem os 10 do dia, o intervalo encurta, nunca abaixo de 1 h. Nunca o mesmo produto no mesmo dia (vai para a manhã seguinte e os outros seguem o dia). `AGENDA_INTERVALO_MIN`/`MAX` mudam o intervalo |

Ajustes no `.env`: `LINKS_POR_VIDEO`, `AGENDA_POSTS_POR_DIA`, `AGENDA_INICIO`, `AGENDA_FIM`, `AGENDA_INTERVALO_MIN`, `AGENDA_INTERVALO_MAX`.

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
| Campos que a API devolve (procura estoque) | `.venv/bin/python campos_api.py` |
| Diagnóstico do cartão de variações | `.venv/bin/python diagnostico.py <link do produto>` (manda o print da página para Envios) |

**Páginas da Shopee desligadas** (`SHOPEE_ACESSAR_PAGINAS=nao`) — a Shopee bloqueia o navegador do VPS
como robô e as tentativas ficam associadas à conta logada. Por isso o robô não abre páginas da Shopee:
as variações vêm do print que você manda, e links de vídeo (`sv.shopee`) precisam do link do produto.

## Arquivos

| Arquivo | Função |
|---|---|
| `bot.py` | Robô: Telegram, botões, fila, agenda |
| `pipeline.py` | Prepara um vídeo do início ao fim |
| `shopee_affiliate.py` | API de afiliados: produto, outros vendedores, link de afiliado |
| `video_page_reader.py` | Abre a página do Shopee Video e acha os produtos |
| `variations_print.py` | Recorta as miniaturas do print das variações (IA) |
| `product_page_capture.py` | Captura pela página da Shopee (desligada) |
| `product_matcher.py` | Conferência vídeo × produto por IA |
| `content_generator.py` | Headline (rodízio de 5 gatilhos), descrição, hashtags, SEO |
| `ai_client.py` | Chamada à OpenAI com resposta em JSON por esquema |
| `video_processor.py` / `cover_generator.py` | Vídeo 9:16 com logo / capa |
| `scheduler.py` / `storage.py` | Agenda / estado (SQLite `estado.db`) |
| `sub_id.py` | Sub_id dos links |
| `prompts.py` | Prompts de vídeo com IA (🎬 Prompts) |
| `ideas.py` | Ideias de produtos para gravar (💡 Ideias e /sugestoes) |
| `conversions.py` | Vendas reais por sub_id (relatório de conversões da Shopee) |
| `shopee_session.py` | Login da Shopee no navegador do robô (cookies via /cookies) |
| `lia_sender.py` / `lia_login.py` | Envio à LiA pela sua conta / login dessa conta (uma vez) |
| `setup_topics.py` / `instalar.sh` | Configuração inicial |

## Limites conhecidos

- O Telegram só deixa o bot baixar arquivos de até **20 MB**.
- Cada vídeo usa várias chamadas à OpenAI (conferência de até 7 produtos + textos).
