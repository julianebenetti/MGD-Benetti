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

## Próximos levantamentos

A cada 14 dias o robô manda o levantamento em 📊 Relatório (o próximo por volta de **20/11/2026**). Junto, mandar
os prints da análise do app do Shopee Vídeo (visualizações por horário, público/seguidores, vídeos mais vistos) e,
se possível, o relatório de vendas do site exportado com **Canal = vídeo**. Perguntas para cada levantamento:

- O vídeo fixado continua vendendo? Qual é o novo vencedor?
- As versões novas dos vencedores venderam?
- Beleza e Natal seguem na frente? Moda/pet (teste) e 🌱 oportunidades venderam alguma coisa?
- Os horários de compra mudaram? Ajustar `AGENDA_LOTES`.
- Cancelamento abaixo de 10%? Alguma punição nova (registrar com `/nota`)?
