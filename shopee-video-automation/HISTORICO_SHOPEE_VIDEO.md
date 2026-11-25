# Histórico do Shopee Vídeo — Juliane (Achados Relâmpagos)

Diário da operação no Shopee Vídeo: o que aconteceu, o que os números mostraram e o que foi decidido. Serve para
avaliar a conta de tempos em tempos e direcionar o trabalho. **Vale só o que é do Shopee Vídeo** (canal vídeo da
Shopee); as vendas de outros links (grupos, sub_ids `…VEA…`) ficam de fora.

No Telegram, o robô mantém a versão viva deste histórico: **`/historico`** mostra, **`/nota texto`** acrescenta um
marco, e o **levantamento automático a cada 14 dias** (`/estudo` para pedir na hora) entra sozinho.

## Linha do tempo

| Data | O que aconteceu |
|---|---|
| 07/09/2026 | Primeira venda pelo Shopee Vídeo. |
| início de out | Robô de vídeos (Telegram) + LiA postando no Shopee Vídeo. |
| 06–17/10 | Fase boa: 6 a 9 pedidos/dia, quase tudo do vídeo da **Escova Rotativa Elétrica 2 em 1**. |
| **10/10** | **Pico: 19 pedidos no dia.** |
| 12–22/10 | Remoções por **"Produto irrelevante"**: vídeo da loja pedrita.bambam.store (12/10), estrela ponteira (16/10), pisca-pisca (17/10), toalha de Natal (20/10), arara e sapateira (22/10). Causas: até 5 links por vídeo (produtos "adicionais") e vídeo de IA com detalhes diferentes do anúncio (ex.: arara com 4 barras, anúncio com 2). |
| 19/10 em diante | Vendas pelo vídeo caem para quase zero (punições derrubam o alcance da conta). |
| 23/10 | **7 pontos, banida até 25/10.** Robô passa a validar "idêntico ao anúncio" detalhe por detalhe e manda só 1 link à LiA. |
| **28/10** | **"Produto irrelevante": kit com 10 baldes de gelo, vídeo mostrava 1. 8 pontos, banida até 31/10.** Robô passa a exigir a quantidade do kit ("Kit 10", "Jogo 3", "6 unidades"). |
| 31/10 | Agenda em lotes de 5, 30 vídeos/dia. Postagens também na outra conta do Shopee Vídeo. LiA lança app de criar vídeos a partir de links. |
| 05/11 | **Primeiro estudo só com Shopee Vídeo** (relatório Canal = vídeo, abaixo). |
| 06/11 | Decisões do estudo (abaixo). Criado este histórico e o levantamento automático. |
| **17/11** | **"Produto irrelevante": vídeo do casaco de pelo teddy feminino (postado 17/11 20:29), removido em 1 min. 8 pontos, banida até 20/11 20:30.** Apelação em andamento. |

## Estudo de 05/11/2026 (relatório Canal = vídeo, 07/09 a 04/11)

- **236 pedidos · 156 válidos · 80 cancelados (34%)** · comissão líquida **R$ 311,53** · **R$ 2,00 por pedido** ·
  R$ 15.762 vendidos.
- **Um vídeo fez a conta:** Escova Rotativa Elétrica 2 em 1 = 134 pedidos, **73% da comissão**; outras escovas Mondial
  +12%. **Beleza/cabelo = 93% dos pedidos.** Natal começando (Papai Noel 40 cm com comissão extra: R$ 7,50/venda).
  Moda: 4 pedidos. **Pet: 0** pelo vídeo.
- **Cancelamentos:** 73 dos 80 foram da escova, porque **a escova vendida não era a mesma do vídeo** (a pessoa
  recebia outro produto e devolvia). Mesmo problema das punições: o link precisa ser exatamente o produto do vídeo.
- **Todas as compras são do próprio produto do vídeo, sem sub_id**, e acontecem **na hora** (0 min entre clique e
  compra): compra por impulso, assistindo.
- **Horários das compras:** tarde 32% (pico 13–15h), noite 37% (picos 18h e 20–21h), manhã 21% (10h). Sábado o melhor
  dia, sexta o pior. *(Amostra dominada por um vídeo: reavaliar.)*
- **Mais vídeos não trouxeram mais vendas:** o melhor período foi antes do aumento de volume e das punições.

## Decisões de 06/11/2026

1. **Ideias do dia pelo que vende no vídeo:** 10 mais buscados + 12 beleza/cabelo + 8 Natal (só na temporada) +
   5 moda + 3 tapete higiênico + 2 pet (moda e pet como teste) + 5 🌱 oportunidades (teste).
2. **Lotes da agenda antes dos picos:** 9h, 11h, 13h, 17h, 19h e 20h (10 manhã, 10 tarde, 10 noite).
3. **Estratégia:** 📌 fixar no perfil o vídeo que mais vende (relatório 🏆 Vencedores, todo dia 7:45);
   🔁 fazer mais versões dos vídeos que vendem (botão 🎬 nos Vencedores); 🌱 testar produtos com poucas vendas
   ainda / comissão extra; ranqueamento: gancho forte nos 3 primeiros segundos, constância e **nenhuma punição**.
4. **Vídeo modelo:** mandar o vídeo vencedor ao Gemini, pedir o JSON do vídeo e colar no 🎬 Prompts; o robô faz
   prompts de outros produtos com a mesma estrutura.
5. **Quantidade:** 10 a 15 vídeos/dia por conta, todos validados; metade versões do que já vendeu.

## Ajuste de 06/11/2026 (Juliane)

Lista do dia muda para: 15 mais buscados · **10 casa e decoração (nicho novo, em teste)** · 5 beleza/cabelo ·
10 Natal · 10 moda · 5 pet (tapete incluído) · 5 oportunidades = 60 ideias por dia (o app da LiA cria 40 por dia).

## Levantamento de 15/11/2026 (Insights do app, conta pedrita.bambam.store, Shopee Video, 01/11 a 14/11)

- **Métricas:** 7 vídeos com receita (+75%) · **3 mil visualizações (−94%)** · tempo médio de visualização 45 s
  (+114%) · 709 cliques (−19%) · **15 pedidos (+7%)** · R$ 574,80 vendidos (−63%) · **comissão R$ 68,30 (+53%)** ·
  **R$ 4,55 por pedido** (no estudo de 05/11 eram R$ 2,00).
- **Vendas por dia:** pico em 03/11 (~R$ 125), 09–10/11 (~R$ 75), zero em 07/11 e 12/11, ~R$ 50 em 13–14/11.
- **O que vendeu:** vestido midi floral (vídeo de 24/08) 6 itens, **R$ 44,40 = 65% da comissão** · Papai Noel 40 cm
  2 itens, R$ 13,50 · sapatilha croco 1, R$ 7,30 · árvore de Natal MDF 3 itens, só R$ 0,60 · kit 3 luminárias
  (vídeo de 14/10/2025), lego Minecraft e vestido infantil: R$ 0,40 a R$ 1,70 cada. **Beleza/escova não aparece.**
- **Público (30 dias):** 79% mulheres · **45+ = 49%**, 35–44 = 24%, 25–34 = 20% · SP 35%, RJ 18%, Salvador 13%,
  Fortaleza 8%, Brasília 8%.
- **Leitura:** o alcance ainda não voltou depois das punições (visualizações −94%), mas quem assiste fica mais tempo
  e a comissão por pedido dobrou. Moda (vestido) virou o principal; Natal vende, mas produto de comissão baixa
  (árvore MDF, lego, vestido infantil) não paga o vídeo. Vídeos antigos seguem vendendo (vestido de agosto,
  luminárias de 2025). Público maduro: mulheres 35+.

## Decisões de 15/11/2026

1. **Comissão mínima de R$ 3 por venda** nas ideias (antes: sem piso).
2. **Lista do dia:** 10 mais buscados · 10 casa · 5 beleza · 10 Natal · **15 moda** · 5 pet · 5 oportunidades ·
   5 móveis · 5 eletrodomésticos (+ 📈 em alta pelo datafeed). Lotes da LiA: moda + beleza · casa + mais buscados ·
   Natal + pet + oportunidades · móveis + eletro + em alta.
3. **Narrações e cenas para o público real:** mulheres 35+ (conforto, caimento, praticidade, casa, família, Natal),
   pessoas adultas no vídeo.
4. Fixar e fazer versões do **vestido midi floral** (65% da comissão); conferir se a cor do vídeo está no anúncio.

## Levantamento de 19/11/2026 (Insights, conta pedrita.bambam.store)

- **Últimos 7 dias (12–18/11):** 3 vídeos com receita (−40%) · **50,2 mil visualizações (+1.525%)** · tempo médio
  24 s (−27%) · 600 cliques (+71%) · 10 pedidos (+25%) · R$ 845,30 vendidos (+204%) · **comissão R$ 68,50 (+113%)**.
  Vendas: picos em 15/11 (~R$ 310) e 17/11 (~R$ 290); a punição de 17/11 20:30 interrompeu.
- **Mês (01–18/11):** 9 vídeos com receita · 52,1 mil visualizações · tempo médio 59 s · 1,1 mil cliques · 23 pedidos ·
  R$ 1,3 mil vendidos · **comissão R$ 121,80** (R$ 5,30 por pedido).
- **O que vendeu (mês):** vestido midi floral (vídeo de 24/08) **11 itens, R$ 81,70 = 67% da comissão** · Papai Noel
  2, R$ 13,50 · escova rotativa (vídeo de 07/08/2025) 2 itens, **R$ 465,90 vendidos e só R$ 8,90 de comissão (~2%)** ·
  sapatilha 1, R$ 7,30 · suporte PS5 1, R$ 7,30 · árvore MDF 3, R$ 0,60 · luminárias, lego (anúncio inválido) e
  vestido infantil: centavos. Nos 7 dias, as vendas vieram de vídeos antigos (vestido, escova, PS5).
- **Público:** 45+ = 50%, 35–44 = 23%, 25–34 = 19%.
- **Leitura:** a entrega VOLTOU (de 3 mil para 50 mil visualizações em 7 dias) antes da punição de 17/11. O vestido
  segue sendo o carro-chefe. A escova vende bem, mas o link paga ~2%: o mesmo modelo (Mondial ER-10 5 em 1) paga
  8% (≈ R$ 19) em outras lojas.

## Levantamento de 22/11/2026 (Insights, conta pedrita.bambam.store)

- **Últimos 7 dias (15–21/11):** 5 vídeos com receita · **51,3 mil visualizações (+1.583%)** · tempo médio 27 s ·
  558 cliques · 11 pedidos (+57%) · R$ 869,60 vendidos · **comissão R$ 72,40 (+122%)**. Vendas por dia: 15/11 ~R$ 310,
  17/11 ~R$ 290, depois da punição 18/11 ~R$ 50, 19/11 ~R$ 10, 20–21/11 ~R$ 55/dia.
- **Últimos 30 dias (23/10–21/11):** 13 vídeos com receita · 54 mil visualizações · tempo médio 1 min 10 s ·
  1,6 mil cliques · 30 pedidos · R$ 2 mil · **comissão R$ 162**.
- **O que vendeu (30 dias):** vestido midi floral 11 itens, **R$ 83,10 (51%)** · Papai Noel 3, R$ 22,60 · escova
  rotativa 4 itens, R$ 892 vendidos e só R$ 17 de comissão (~2%) · porta-cartão (vídeo de 31/10) 1, R$ 10 ·
  macaquinho plus size 1, R$ 8,40 · sapatilha, suporte PS5 R$ 7,30 cada · centavos: árvore MDF, lego, luminárias,
  almofada, vestido infantil, película (R$ 0,70).
- **Leitura:** as visualizações se mantiveram (~50 mil/semana), mas as vendas caíram depois da punição de 17/11 e
  ainda não voltaram ao nível de 15–17/11. Vídeos antigos seguem fazendo quase tudo (vestido de agosto, escova de
  2025); os produtos novos de novembro venderam pouco ou centavos.

## Decisão de 24/11/2026

Vídeos estão sendo entregues (~50 mil visualizações/semana) mas vendem pouco. **Teste:** vídeos limpos, **sem
figurinhas e sem o botão de compra (CTA) no fim**. Comparar a conversão (pedidos ÷ cliques e ÷ visualizações) nos
próximos levantamentos com o período anterior (15–21/11: 558 cliques, 11 pedidos = 2,0% dos cliques).

## Levantamento de 25/11/2026 (Insights, conta pedrita.bambam.store)

- **Últimos 7 dias (18–24/11):** 3 vídeos com receita · **2,9 mil visualizações (−94%)** · tempo médio 12 s (−65%) ·
  475 cliques · 5 pedidos (−50%) · R$ 225,20 · **comissão R$ 34,40**. Vendas: ~R$ 50/dia até 22/11, **zero em 23 e
  24/11**. Conversão 5/475 = 1,1% dos cliques (antes 2,0%).
- **Mês (01–24/11):** 53,6 mil visualizações · 1,5 mil cliques · 26 pedidos · **comissão R$ 142,10**; vestido midi
  12 itens, **R$ 91,30 (64%)**.
- **Leitura:** a entrega CAIU DE NOVO depois da punição de 17/11 (de ~50 mil para 2,9 mil visualizações/semana),
  igual à queda de 01–14/11 depois das punições de outubro. O que ainda vende são vídeos antigos (vestido de agosto,
  porta-cartão de 31/10). Os vídeos sem CTA começaram a sair só agora: o teste ainda não dá para medir.

## Próximos levantamentos

A cada 14 dias o robô manda o levantamento em 📊 Relatório (o próximo por volta de **20/11/2026**). Junto, mandar
os prints da análise do app do Shopee Vídeo (visualizações por horário, público/seguidores, vídeos mais vistos) e,
se possível, o relatório de vendas do site exportado com **Canal = vídeo**. Perguntas para cada levantamento:

- O vídeo fixado continua vendendo? Qual é o novo vencedor?
- As versões novas dos vencedores venderam?
- Beleza e Natal seguem na frente? Moda/pet (teste) e 🌱 oportunidades venderam alguma coisa?
- Os horários de compra mudaram? Ajustar `AGENDA_LOTES`.
- Cancelamento abaixo de 10%? Alguma punição nova (registrar com `/nota`)?
