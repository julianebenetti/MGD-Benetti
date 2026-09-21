#!/usr/bin/env node
/**
 * Importa o extrato da conta corrente do Itaú (.xls do internet banking).
 *
 * O extrato é a terceira fonte da dashboard, ao lado da fatura do cartão e do
 * holerite. Ele traz o que nenhuma das outras vê: boleto, débito automático,
 * PIX e o custo do cheque especial.
 *
 * O risco aqui é contar duas vezes. O extrato repete, como movimento de caixa,
 * coisas que já entraram linha a linha por outra fonte:
 *
 *   - o crédito do salário, que o holerite já lançou como provento e descontos;
 *   - o pagamento da fatura, cujas compras já estão lançadas uma a uma.
 *
 * As duas ficam com natureza "transferencia": aparecem no extrato, mexem no
 * saldo da conta, e não entram em receita nem em despesa. Somá-las dobraria o
 * mesmo dinheiro.
 *
 * Uso:
 *   node scripts/importar-extrato-itau.js <arquivo.xls> [...]      (simulação)
 *   node scripts/importar-extrato-itau.js <arquivo.xls> --aplicar
 */

const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const aplicar = process.argv.includes('--aplicar');

const brl = v => `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
const hoje = () => new Date().toISOString().slice(0, 10);

// O .xls do Itau traz valor no padrao americano ("-1,402.67"). Detectar qual
// separador e o decimal evita transformar mil e quatrocentos em um e quarenta.
const dinheiro = v => {
  let t = String(v).replace(/[R$\s]/g, '');
  if (!t) return 0;
  const neg = t.startsWith('-');
  t = t.replace(/^-/, '');
  const vir = t.lastIndexOf(','), pon = t.lastIndexOf('.');
  if (vir > -1 && pon > -1) t = vir > pon ? t.replace(/\./g, '').replace(',', '.') : t.replace(/,/g, '');
  else if (vir > -1) t = t.length - vir - 1 <= 2 ? t.replace(',', '.') : t.replace(/,/g, '');
  else if (pon > -1 && t.length - pon - 1 === 3) t = t.replace(/\./g, '');
  const n = parseFloat(t);
  return isNaN(n) ? 0 : (neg ? -1 : 1) * Math.round(Math.abs(n) * 100) / 100;
};

// O arquivo vem em latin-1 lido como utf-8: "cartÃ£o" no lugar de "cartão".
const consertarAcento = s => String(s)
  .replace(/Ã£/g, 'ã').replace(/Ã§/g, 'ç').replace(/Ãµ/g, 'õ')
  .replace(/Ã©/g, 'é').replace(/Ã¡/g, 'á').replace(/Ãº/g, 'ú')
  .replace(/Ã­/g, 'í').replace(/Ã³/g, 'ó').replace(/Ãª/g, 'ê')
  .replace(/Ã‰/g, 'É').replace(/Ã•/g, 'Õ').replace(/Ã‡/g, 'Ç')
  .replace(/Ã/g, 'Í');

// ---------- classificação ----------
//
// A ordem importa: a primeira regra que casar decide. As de "ja contado" vem
// primeiro, senao um pagamento de fatura viraria despesa comum.

const REGRAS = [
  // --- já contado por outra fonte: não é receita nem despesa ---
  {
    padrao: /^REMUNERACAO\/SALARIO/i,
    natureza: 'transferencia', categoria: 'salario_ja_lancado', pessoa: 'Juliane',
    descricao: 'Crédito do salário (já lançado pelo holerite)',
    nota: 'O holerite lança o provento bruto e cada desconto. Contar o crédito de novo dobraria a renda.',
  },
  // O 0442 (Infinite) e o cartao de trafego pago da Benetti UP. Essa descricao
  // especifica e a unica, entre as variacoes de "fatura" que aparecem nesta
  // conta pessoal, que paga o cartao da empresa — as demais (Black, Azul) sao
  // pessoais. Tem de vir antes da regra generica abaixo (Juliane, 23/08).
  {
    padrao: /^FATURA PAGA ITAU UNICLAS/i,
    natureza: 'transferencia', categoria: 'pagamento_fatura', pessoa: 'Benetti UP',
    descricao: 'Pagamento da fatura do 0442 (Infinite, tráfego pago)',
    nota: 'As demais faturas pagas por esta conta são pessoais; só esta é da empresa.',
  },
  // Boleto do cartao Amazon (Bradescard, final 0013). Ate 31/08 este boleto era
  // classificado como despesa/compras, porque nao havia fatura desse cartao
  // cadastrada e o boleto era a unica visao que existia do gasto. Desde que as
  // 8 faturas do 0013 foram importadas itemizadas, contar os dois lados seria
  // dupla contagem: as compras ja estao lancadas uma a uma dentro da fatura.
  // O texto varia entre o normalizado e a string crua do banco.
  {
    padrao: /BRADESCARD|CART[AÃ]O AMAZON/i,
    natureza: 'transferencia', categoria: 'pagamento_fatura', pessoa: 'Juliane',
    descricao: 'Pagamento da fatura do cartão Amazon (0013)',
    nota: 'As compras já estão lançadas uma a uma pela fatura do 0013.',
  },
  {
    // "FATURA PAGA AZUL ITAU IN" (21/08, R$14.270,31) escapava: a regra pedia
    // "FATURA ITAU" grudado e o "AZUL" no meio furava o padrao, entao o
    // pagamento da fatura do 3794 caia em nao_classificado.
    padrao: /FATURA\s*ITAU|FATURA PAGA (\w+\s+)?ITAU|PGTO MIN ITAU|INT AZUL VISA|CARTAO TUDOAZUL|PAG ENTR PARC/i,
    natureza: 'transferencia', categoria: 'pagamento_fatura', pessoa: 'Família',
    descricao: 'Pagamento de fatura de cartão',
    nota: 'As compras já estão lançadas uma a uma pela fatura. Contar o pagamento seria contar tudo duas vezes.',
  },

  // --- empréstimo consignado debitado direto na conta ---
  // Este é um quarto contrato, além dos três que descontam em folha.
  {
    padrao: /^CREDITO CONSIGNADO\s+\d+\/\d+/i,
    natureza: 'divida_parcelada', categoria: 'consignado', pessoa: 'Juliane',
    descricao: 'Empréstimo consignado (débito em conta)',
    nota: 'Parcela de empréstimo: quita dívida, não é consumo novo.',
  },
  {
    padrao: /^CREDITO CONSIGNADO\s*$/i, entrada: true,
    natureza: 'emprestimo', categoria: 'emprestimo_tomado', pessoa: 'Juliane',
    descricao: 'Liberação de empréstimo consignado',
    nota: 'Dinheiro entrando que é dívida contraída, não renda. Vira obrigação de pagar.',
  },

  // --- decisões da Juliane sobre as transferências (23/08) ---
  // Vale nos dois sentidos: se a conta do outro lado é dela, o dinheiro só muda
  // de lugar tanto na ida quanto na volta.
  {
    // A devolucao de um PIX dela para ela mesma e a mesma transferencia
    // voltando: "DEV PIX JULIANE FER" (28/08, R$1.300) caia sem regra porque o
    // padrao so cobria a ida.
    padrao: /(DEV )?PIX (TRANSF|QRS) Juliane|DEV PIX JULIANE/i,
    natureza: 'transferencia', categoria: 'entre_contas_proprias', pessoa: 'Juliane',
    descricao: 'Transferência entre contas próprias',
    nota: 'Dinheiro que já era dela, mudando de conta. Não é renda nem gasto.',
  },
  {
    padrao: /PIX (TRANSF|QRS) BENETTI/i, entrada: true,
    natureza: 'receita', categoria: 'pro_labore', pessoa: 'Juliane',
    descricao: 'Pró-labore da Benetti UP',
    nota: 'Remuneração da sócia: sai da empresa e entra como renda pessoal.',
  },
  {
    padrao: /PIX (TRANSF|QRS) BENETTI/i, entrada: false,
    natureza: 'transferencia', categoria: 'aporte_na_empresa', pessoa: 'Juliane',
    descricao: 'Aporte na Benetti UP',
    nota: 'Dinheiro pessoal indo para a empresa. Não é consumo da casa.',
  },
  {
    padrao: /PIX TRANSF Hugo/i, entrada: true,
    natureza: 'receita', categoria: 'contribuicao_casa', pessoa: 'Hugo',
    descricao: 'Contribuição do Hugo para a casa',
    nota: 'Dinheiro de fora entrando para pagar despesa comum.',
  },

  // --- custo de crédito: despesa financeira, nunca despesa comum ---
  {
    padrao: /JUROS LIMITE DA CONTA|JUROS DO EXCESSO|^IOF$|^IOF\s/i,
    natureza: 'despesa', categoria: 'encargos_financeiros', pessoa: 'Família',
    descricao: 'Juros e IOF do cheque especial',
    nota: 'Custo de usar o limite da conta.',
  },
  {
    padrao: /ITAU SEGURO|SEGURO CREDITO/i,
    natureza: 'despesa', categoria: 'seguro', pessoa: 'Família',
    descricao: 'Seguro do Itaú',
  },
  {
    padrao: /REND PAGO APLIC|RENDIMENTO/i, entrada: true,
    natureza: 'receita', categoria: 'rendimento_aplicacao', pessoa: 'Juliane',
    descricao: 'Rendimento de aplicação',
  },

  // --- contas de casa em débito automático ---
  { padrao: /^DA CPFL/i,   natureza: 'despesa', categoria: 'utilidades', pessoa: 'Família', descricao: 'CPFL — energia elétrica' },
  { padrao: /^DA SANASA/i, natureza: 'despesa', categoria: 'utilidades', pessoa: 'Família', descricao: 'Sanasa — água' },
  { padrao: /^DA CLARO/i,  natureza: 'despesa', categoria: 'utilidades', pessoa: 'Família', descricao: 'Claro — telefone e internet' },
  { padrao: /^DA PM CAMP/i, natureza: 'despesa', categoria: 'imposto_municipal', pessoa: 'Família', descricao: 'Prefeitura de Campinas' },

  // DAS do MEI: imposto da empresa, não da casa.
  {
    padrao: /DAS MEI/i,
    natureza: 'despesa', categoria: 'imposto_empresa', pessoa: 'Benetti UP',
    descricao: 'DAS do MEI',
    nota: 'Imposto da empresa. Entra no âmbito empresa, não no gasto pessoal.',
  },

  // Oferta semanal (Juliane, 23/08). Nao deduz no imposto de renda: a lei so
  // permite doacao a fundo da crianca e do idoso, Rouanet, audiovisual, desporto
  // e PRONAS/PRONON. Instituicao religiosa fica de fora.
  {
    padrao: /PIX (TRANSF|QRS) IGREJA/i,
    natureza: 'despesa', categoria: 'doacao', pessoa: 'Família',
    descricao: 'Oferta à igreja',
  },

  // --- boletos identificáveis pelo nome ---
  { padrao: /ESC INF NO MUND|MUNDO CORES/i, natureza: 'despesa', categoria: 'educacao', pessoa: 'Valentina', descricao: 'Escola Mundo Cores' },
  { padrao: /SOCIUM CONDOMIN|CONDOMINIO/i,  natureza: 'despesa', categoria: 'moradia',  pessoa: 'Família',   descricao: 'Condomínio' },
  { padrao: /AVANTRA BASKET/i,              natureza: 'despesa', categoria: 'esportes', pessoa: 'Filhos',    descricao: 'Basquete' },
  { padrao: /SERVICO SOCIAL|SESI/i,         natureza: 'despesa', categoria: 'educacao', pessoa: 'Luca',      descricao: 'Sesi' },

  // --- boletos sem nome de beneficiário, so o codigo do banco liquidante ---
  //
  // "PAG TIT INT 237" e "PAG TIT INT 001" nao identificam quem recebeu: 237 e
  // 001 sao os codigos do Bradesco e do Banco do Brasil, os bancos que
  // liquidaram o boleto, nao um beneficiario unico. Cada codigo paga MAIS de um
  // boleto diferente — o condominio (~R$623) divide o "237" com outro boleto
  // bem menor, e a escola do Luca (~R$546) divide o "001" com outro tambem
  // menor. So o valor na faixa conhecida e classificado; o resto fica de fora
  // em vez de herdar uma classificacao que pode nao ser dele (Juliane, 23/08).
  {
    padrao: /^PAG TIT INT 237$/i, valorEntre: [600, 650],
    natureza: 'despesa', categoria: 'moradia', pessoa: 'Família',
    descricao: 'Condomínio',
  },
  // O mesmo código 237 (Bradesco) também liquida o boleto do cartão
  // Amazon/Bradescard dela — confirmado por 2 comprovantes (R$431,58 venc.
  // 15/01 e R$459,31 venc. 18/02, Juliane, 30/08). Vem depois da regra do
  // condomínio, de propósito: a faixa específica (600-650) vence primeiro,
  // essa pega o resto.
  //
  // Era `despesa`, e a razão era boa enquanto durou: o boleto pago era a única
  // visão que existia desse cartão, então marcá-lo como pagamento o tornaria
  // invisível. Essa premissa morreu em 31/08, quando as 9 faturas do 0013
  // entraram itemizadas — e este arquivo já avisava que, no dia em que isso
  // acontecesse, os boletos teriam de virar pagamento de fatura.
  //
  // Só a regra ficou para trás. A que foi criada naquele dia casa o texto
  // normalizado ("BRADESCARD", "Cartão Amazon"), e o Itaú também liquida o
  // mesmo boleto como "PAG TIT INT 237", que caía aqui e voltava a ser
  // despesa. Resultado: todo mês reimportado regredia, e R$ 197,95 apareciam
  // ao mesmo tempo como gasto no extrato e como fatura do 0013 a pagar
  // (73,27 em Ago/26 e 124,68 em Set/26).
  //
  // Os 9 valores fora da faixa do condomínio batem um a um com o total de uma
  // fatura do 0013 — 431,58 · 459,31 · 459,67 · 357,87 · 333,71 · 128,66 ·
  // 107,68 · 73,27 · 124,68. Não sobra nenhum, então a troca é segura.
  //
  // Achado por agente de validação (30/08): o Itaú varia a ordem das palavras
  // no mesmo boleto ("INT PAG TIT 237", "PAG TIT BANCO 237") — regex de match
  // exato perdia essas variações. Basta terminar em "237" com "TIT" no meio.
  {
    padrao: /TIT.*\b237$/i,
    natureza: 'transferencia', categoria: 'pagamento_fatura', pessoa: 'Juliane',
    descricao: 'Pagamento da fatura do cartão Amazon (0013)',
    nota: 'As compras já estão lançadas uma a uma pela fatura do 0013. Contar o boleto também somaria o mesmo gasto duas vezes.',
  },
  {
    padrao: /^PAG TIT INT 001$/i, valorEntre: [500, 600],
    natureza: 'despesa', categoria: 'educacao', pessoa: 'Luca',
    descricao: 'Escola do Luca',
  },
  // "199060387000" já é o código do beneficiário em si (não do banco
  // liquidante), então identifica só esse boleto — cobre o valor inteiro sem
  // precisar de faixa.
  {
    padrao: /^PAG TIT INT 199060387000$/i,
    natureza: 'despesa', categoria: 'educacao', pessoa: 'Valentina',
    descricao: 'Escola da Valentina',
  },

  // --- pessoas fixas e negócio, do guia de classificação da Juliane (23/08) ---
  {
    padrao: /PIX (TRANSF|QRS) MARCOS/i, entrada: true,
    natureza: 'receita', categoria: 'aluguel_recebido', pessoa: 'Juliane',
    descricao: 'Aluguel de garagem',
  },
  {
    padrao: /PIX (TRANSF|QRS) GUILHER/i,
    natureza: 'despesa', categoria: 'transporte', pessoa: 'Luca',
    descricao: 'Van escolar do Luca',
  },
  {
    padrao: /PIX (TRANSF|QRS) EDILEIA/i,
    natureza: 'despesa', categoria: 'moradia', pessoa: 'Família',
    descricao: 'Aluguel da vaga de carro',
  },
  {
    padrao: /PIX (TRANSF|QRS) Nilza/i,
    natureza: 'despesa', categoria: 'servicos', pessoa: 'Família',
    descricao: 'Faxina',
  },
  {
    // Sem \b depois de APE: o Itau emenda a data no fim ("APE25/01"), e a
    // fronteira de palavra nao existe entre letra e digito.
    padrao: /PIX (TRANSF|QRS) APE(?![A-Z])/i,
    natureza: 'despesa', categoria: 'casa', pessoa: 'Família',
    descricao: 'Locker de guarda-móveis',
  },
  {
    padrao: /PIX (TRANSF|QRS) STIMA/i,
    natureza: 'despesa', categoria: 'contabilidade', pessoa: 'Benetti UP',
    descricao: 'Contabilidade STIMA',
  },

  // Empréstimo da mãe (Cenira): ela tomou um crédito parcelado pra emprestar
  // pra Juliane, que paga de volta em parcelas fixas de R$646. O deposito de
  // R$10.000 (12/05/26) e as demais PIX pra/da Cenira antes dessa data nao
  // sao deste emprestimo (Juliane, 29/08).
  {
    padrao: /PIX (TRANSF|QRS) CENIRA/i, entrada: true, valorEntre: [9000, 11000],
    natureza: 'emprestimo', categoria: 'emprestimo_tomado', pessoa: 'Juliane',
    descricao: 'Empréstimo tomado com a mãe (Cenira)',
    nota: 'Dinheiro entrando que é dívida contraída com a mãe, não renda.',
  },
  {
    // Faixa em vez do valor exato: a parcela é R$645,91 no contrato da mãe,
    // mas o Pix que a Juliane manda de fato varia um pouco (R$646,00 e
    // possíveis pequenos ajustes) — sem casar o valor teria de confiar só no
    // texto, que também casa com PIX antigos não relacionados a este contrato
    // (ex: R$300 em jan/26, R$500 em abr/26, antes do empréstimo existir).
    padrao: /PIX (TRANSF|QRS) CENIRA/i, entrada: false, valorEntre: [600, 700],
    natureza: 'divida_parcelada', categoria: 'emprestimo_familiar', pessoa: 'Juliane',
    descricao: 'Pagamento do empréstimo da mãe (Cenira)',
    nota: 'Parcela de empréstimo: quita dívida com a mãe, não é consumo novo.',
  },
  // Qualquer outro Pix pra Cenira (fora da faixa da parcela) é ajuda de
  // custo avulsa, não empréstimo — confirmado pela Juliane (29/08). Vem
  // depois da regra da parcela de propósito: a mais específica vence.
  {
    padrao: /PIX (TRANSF|QRS) CENIRA/i, entrada: false,
    natureza: 'despesa', categoria: 'ajuda_familiar', pessoa: 'Juliane',
    descricao: 'Ajuda de custo para a mãe (Cenira)',
  },
  // Lote de reclassificação do "não classificado" do extrato (Juliane, 29/08).
  {
    padrao: /PIX QRS SEM PARAR/i,
    natureza: 'despesa', categoria: 'transporte', pessoa: 'Família',
    descricao: 'Sem Parar — pedágio',
  },
  {
    padrao: /PIX QRS FACEBOOK/i,
    natureza: 'despesa', categoria: 'trafego_pago', pessoa: 'Benetti UP',
    descricao: 'Facebook Ads',
  },
  {
    padrao: /PIX QRS AMERICANAS/i,
    natureza: 'despesa', categoria: 'compras', pessoa: 'Família',
    descricao: 'Americanas',
  },
  {
    padrao: /PIX QRS CINEPOLIS/i,
    natureza: 'despesa', categoria: 'lazer_esportes', pessoa: 'Família',
    descricao: 'Cinépolis',
  },
  // A Juliane ja tinha definido Transurc como transporte dela para o trabalho
  // (regras-classificacao.json, 23/08). Aquele arquivo so vale para a fatura do
  // cartao; quando a mesma catraca e paga por Pix no extrato, a regra tem de
  // existir aqui tambem, senao cai em nao_classificado.
  {
    padrao: /PIX (TRANSF|QRS) TRANSURC/i,
    natureza: 'despesa', categoria: 'transporte', pessoa: 'Juliane',
    descricao: 'Transurc — transporte para o trabalho',
    nota: 'Mesma regra que já valia para a fatura do cartão (Juliane, 23/08).',
  },
  // Mesmo caso do Transurc: "Tokio Marine -> seguro do carro / Familia" ja era
  // decisao dela (23/08), mas so existia em regras-classificacao.json, que vale
  // para a fatura. Quando o seguro e pago por boleto no extrato, a regra precisa
  // existir aqui tambem.
  {
    padrao: /(PAG BOLETO )?TOKIO MARINE/i,
    natureza: 'despesa', categoria: 'seguro', pessoa: 'Família',
    descricao: 'Seguro do carro (Tokio Marine)',
    nota: 'Mesma regra que já valia para a fatura do cartão (Juliane, 23/08).',
  },
  {
    padrao: /PIX TRANSF Vanders/i,
    natureza: 'despesa', categoria: 'cuidados_pessoais', pessoa: 'Juliane',
    descricao: 'Manicure — unha em gel (Vanders)',
    nota: 'Confirmado pela Juliane (29/08).',
  },
  // Doacao mensal para o Instituto dos Cegos de Campinas, confirmada pela
  // Juliane (13/09). Cai todo dia 27; o de 02/03 veio R$ 40,00 em vez dos
  // R$ 20,00 de sempre, e e o mesmo recebedor — por isso a regra nao filtra
  // valor. Nao deduz no IR: a lei so permite doacao a fundo da crianca e do
  // idoso, Rouanet, audiovisual, desporto e PRONAS/PRONON.
  {
    padrao: /PIX (TRANSF|QRS) INSTITU/i, entrada: false,
    natureza: 'despesa', categoria: 'doacao', pessoa: 'Juliane',
    descricao: 'Doação ao Instituto dos Cegos de Campinas',
    nota: 'Confirmado pela Juliane (13/09). Não dedutível no IRPF.',
  },
  // Venda de desapego: a Juliane vendeu roupas usadas dos filhos e a Symara
  // pagou por Pix (confirmado 13/09). Entra como receita, mas NAO e rendimento
  // tributavel — venda de bem pessoal usado abaixo do preco de compra nao gera
  // ganho de capital, e contar aqui inflaria a base do IRPF dela.
  //
  // So na entrada: se um dia ela mandar dinheiro PARA a Symara, e outra coisa,
  // e a regra nao pode carimbar o motivo errado.
  {
    padrao: /PIX (TRANSF|QRS) Symara/i, entrada: true,
    natureza: 'receita', categoria: 'venda_usados', pessoa: 'Juliane',
    descricao: 'Venda de roupas usadas dos filhos (Symara)',
    nota: 'Desapego, confirmado pela Juliane (13/09). Não é rendimento tributável.',
  },
  // O Itau nao traz nome nesse Pix, so um pedaco do documento do recebedor.
  // Confirmado pela Juliane (13/09): doce comprado de um amigo. Regra presa ao
  // identificador e ao sentido de saida — sem nome, e o unico traco estavel que
  // este lancamento tem.
  {
    padrao: /PIX (TRANSF|QRS) 55\.873/i, entrada: false,
    natureza: 'despesa', categoria: 'alimentacao', pessoa: 'Juliane',
    descricao: 'Doce comprado de um amigo',
    nota: 'Confirmado pela Juliane (13/09): todo Pix para este recebedor é doce.',
  },
  {
    padrao: /PIX TRANSF KARINA/i,
    natureza: 'despesa', categoria: 'doacao', pessoa: 'Juliane',
    descricao: 'Ajuda de custo para Karina Patricia Marcello Ponte',
    nota: 'Ajuda pontual, sem volta, pessoa fora do círculo familiar próximo — não dedutível (Juliane, 30/08).',
  },
  {
    padrao: /PIX TRANSF DANIELA/i,
    natureza: 'despesa', categoria: 'compras_diversas', pessoa: 'Juliane',
    descricao: 'Roupas (Daniela)',
    nota: 'Confirmado pela Juliane (30/08).',
  },
  {
    padrao: /PIX (TRANSF|QRS) RHUANN/i,
    natureza: 'despesa', categoria: 'educacao_profissional', pessoa: 'Benetti UP',
    descricao: 'Mentoria (Rhuann)',
    nota: 'Confirmado pela Juliane (30/08).',
  },
  {
    padrao: /PIX (TRANSF|QRS) ELISABE/i,
    natureza: 'despesa', categoria: 'trafego_pago', pessoa: 'Benetti UP',
    descricao: 'Collab / Instagram (Elisabe)',
    nota: 'Confirmado pela Juliane (30/08) para uma ocorrência; aplicado às demais por mesmo valor/nome.',
  },
  // A viagem do Airbnb (dez/25, categoria viagem/Família) foi da família
  // estendida, não só da casa da Juliane — irmãos, cunhadas e sobrinhos
  // foram junto. Estes pagamentos são o reembolso da parte de cada família
  // no custo, não renda dela: tratados como transferencia (mexe no saldo,
  // não conta como receita nem infla o rendimento tributável do IRPF).
  // Confirmado pela Juliane, 30/08.
  {
    padrao: /PIX (TRANSF|QRS) Fabio G/i, entrada: true,
    natureza: 'transferencia', categoria: 'reembolso_viagem_familia', pessoa: 'Juliane',
    descricao: 'Reembolso viagem em família (Fabio)',
  },
  {
    padrao: /PIX (TRANSF|QRS) ROGERIO/i, entrada: true,
    natureza: 'transferencia', categoria: 'reembolso_viagem_familia', pessoa: 'Juliane',
    descricao: 'Reembolso viagem em família (Rogério)',
  },
  {
    padrao: /PIX (TRANSF|QRS) MIRIAM/i, entrada: true,
    natureza: 'transferencia', categoria: 'reembolso_viagem_familia', pessoa: 'Juliane',
    descricao: 'Reembolso viagem em família (Miriam)',
  },
  {
    padrao: /DEV PIX Fabio Gomes/i,
    natureza: 'transferencia', categoria: 'reembolso_viagem_familia', pessoa: 'Juliane',
    descricao: 'Devolução de reembolso da viagem (Fabio)',
    nota: 'Corrigido (30/08): não é gasto novo de viagem, é estorno de um dos pagamentos de reembolso do Fabio.',
  },
];

function classificar(desc, valor) {
  const entrada = valor > 0;
  const abs = Math.abs(valor);
  return REGRAS.find(r =>
    r.padrao.test(desc)
    && (r.entrada === undefined || r.entrada === entrada)
    && (!r.valorEntre || (abs >= r.valorEntre[0] && abs <= r.valorEntre[1]))) || null;
}

// ---------- leitura ----------

// O extrato chega em dois formatos. O .xls do internet banking traz a descricao
// inteira; o PDF do app corta a descricao na largura da coluna ("DA CPFL PTA
// 1007780" no lugar de "DA CPFL PTA 10077803899"). As duas leituras devolvem a
// mesma forma, e a classificacao nao muda: as regras casam pelo comeco do texto.
function lerExtrato(caminho) {
  return /\.pdf$/i.test(caminho) ? lerExtratoPdf(caminho) : lerExtratoXls(caminho);
}

// ---------- PDF (app / internet banking) ----------
//
// O layout tem duas colunas de numero: "valor (R$)", que e o movimento, e
// "saldo (R$)", que e o saldo do dia. Ler a segunda como se fosse movimento
// criaria uma despesa de milhares de reais do nada, entao a coluna e decidida
// pela posicao do numero na linha, lida do proprio cabecalho.
function lerExtratoPdf(caminho) {
  const txt = require('child_process')
    .execFileSync('pdftotext', ['-layout', caminho, '-'], { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });

  const cab = txt.split('\n').find(l => /valor \(R\$\)/.test(l)) || '';
  const fimValor = cab.indexOf('valor') + 'valor (R$)'.length;
  const iniSaldo = cab.indexOf('saldo');
  // Fronteira no meio das duas colunas: numero que comece depois dela e saldo.
  const limite = iniSaldo > fimValor ? Math.floor((fimValor + iniSaldo) / 2) : 120;

  const agencia = (txt.match(/ag[êe]ncia:\s*(\d+)/i) || [])[1] || null;
  const conta = (txt.match(/conta:\s*([\d-]+)/i) || [])[1] || null;
  const emitidoEm = (txt.match(/emitido em:\s*(\d{2}\/\d{2}\/\d{4})(?:\s+([\d:]+))?/i) || []).slice(1, 3)
    .filter(Boolean).join(' ') || null;
  const periodo = txt.match(/per[íi]odo de visualiza[çc][ãa]o:\s*(\d{2}\/\d{2}\/\d{4})\s*at[ée]\s*(\d{2}\/\d{2}\/\d{4})/i);

  const NUM = /-?\d{1,3}(?:\.\d{3})*,\d{2}/g;
  const itens = [], saldos = [];

  // A quebra de pagina entra como \f colado na primeira linha da pagina
  // seguinte. Exigir o dia no inicio absoluto da linha fazia esse lancamento
  // sumir sem avisar — foi assim que um estorno de R$ 1.300,00 ficou de fora
  // da primeira leitura, e so a conferencia de saldo denunciou. O \f e trocado
  // por espaco, e nao removido, para as colunas nao andarem um caractere.
  txt.replace(/\f/g, ' ').split('\n').forEach(linha => {
    const d = linha.match(/^\s*(\d{2})\/(\d{2})\/(\d{4})\s+\S/);
    if (!d) return;
    const data = `${d[3]}-${d[2]}-${d[1]}`;
    let m, achado = null;
    NUM.lastIndex = 0;
    while ((m = NUM.exec(linha)) !== null) achado = { pos: m.index, txt: m[0] };
    if (!achado) return;

    const descricao = linha.slice(0, achado.pos)
      .replace(/^\s*\d{2}\/\d{2}\/\d{4}/, '').trim().replace(/\s+/g, ' ');
    const valor = dinheiro(achado.txt);

    if (achado.pos >= limite || /^SALDO/i.test(descricao)) {
      // Saldo do dia: nao e movimento, mas e o que permite conferir a leitura.
      saldos.push({ data, valor });
      return;
    }
    if (valor !== 0) itens.push({ data, descricao: consertarAcento(descricao), valor });
  });

  return {
    arquivo: path.basename(caminho), agencia, conta, emitidoEm, saldos,
    periodo: periodo ? [periodo[1].split('/').reverse().join('-'), periodo[2].split('/').reverse().join('-')] : null,
    itens,
  };
}

// Confere a leitura contra o proprio extrato: o saldo de cada dia tem de ser o
// saldo do dia anterior mais os movimentos do periodo entre os dois. Um valor
// lido errado (a virgem decimal no lugar errado, uma coluna trocada) aparece
// aqui como diferenca, em vez de entrar em silencio na dashboard.
function conferirSaldos(e) {
  if (!e.saldos || e.saldos.length < 2) return null;
  const ordem = [...e.saldos].sort((a, b) => a.data.localeCompare(b.data));
  const falhas = [];
  for (let i = 1; i < ordem.length; i++) {
    const de = ordem[i - 1], ate = ordem[i];
    // O ultimo saldo do extrato e o "saldo em conta" do topo: o Itau ja abate
    // nele o que esta agendado para depois da data. Fechar esse intervalo so
    // com o que ja liquidou acusaria uma diferenca do tamanho dos agendamentos.
    const ultimo = i === ordem.length - 1;
    const mov = e.itens
      .filter(t => t.data > de.data && (ultimo || t.data <= ate.data))
      .reduce((s, t) => s + t.valor, 0);
    const esperado = Math.round((de.valor + mov) * 100) / 100;
    const gap = Math.round((ate.valor - esperado) * 100) / 100;
    if (Math.abs(gap) > 0.005) falhas.push({ data: ate.data, esperado, lido: ate.valor, gap });
  }
  return { dias: ordem.length, falhas, total: falhas.reduce((s, f) => s + Math.abs(f.gap), 0) };
}

// ---------- XLS (internet banking) ----------

function lerExtratoXls(caminho) {
  const wb = XLSX.readFile(caminho);
  const aba = wb.SheetNames.find(n => /lan[çc]amento/i.test(n)) || wb.SheetNames[0];
  const linhas = XLSX.utils.sheet_to_json(wb.Sheets[aba], { header: 1, raw: false, defval: '' });

  const cabecalho = linhas.slice(0, 10).map(l => l.map(String).join(' ')).join('\n');
  const agencia = (cabecalho.match(/Ag[êe]ncia:?\s*\|?\s*(\d+)/i) || [])[1] || null;
  const conta = (cabecalho.match(/Conta:?\s*\|?\s*([\d-]+)/i) || [])[1] || null;

  const ehData = v => /^\d{2}\/\d{2}\/\d{4}$/.test(String(v).trim());

  const itens = linhas
    .filter(l => ehData(l[0]) && String(l[3]).trim())
    .map(l => ({
      data: String(l[0]).trim().split('/').reverse().join('-'),
      descricao: consertarAcento(String(l[1]).trim().replace(/\s+/g, ' ')),
      valor: dinheiro(l[3]),
    }))
    // Linha de saldo diario nao e lancamento: nao tem valor na coluna de valor,
    // mas se escapar viraria despesa gigante.
    .filter(x => x.valor !== 0 && !/^SALDO/i.test(x.descricao));

  const emitidoEm = (cabecalho.match(/Atualiza[çc][ãa]o:?\s*\|?\s*(\d{2}\/\d{2}\/\d{4}[^\n|]*)/i) || [])[1] || null;
  return { arquivo: path.basename(caminho), agencia, conta, emitidoEm, itens, saldos: null, periodo: null };
}

// ---------- reclassificar o que já está gravado ----------
//
// Regra nova só alcança lançamento que passe pelo importador de novo, e a
// mesclagem só substitui os meses dos arquivos informados. Quando a Juliane
// identifica um Pix antigo — a doação mensal ao Instituto dos Cegos, que vinha
// desde março — o arquivo daquele mês muitas vezes não existe mais para reler.
//
// Corrigir o lançamento à mão não resolve: na próxima importação daquele mês a
// correção some. Por isso a regra é sempre o lugar certo, e este modo existe
// para ela alcançar o que já está gravado.
//
// Só mexe no que está em `nao_classificado`. Classificação que alguém decidiu e
// que nenhuma regra cobre não pode ser sobrescrita por este caminho.
if (process.argv.includes('--reclassificar')) {
  const base = JSON.parse(fs.readFileSync(ARQUIVO, 'utf8'));
  const todasT = (base.fluxo_mensal || {}).transacoes || [];
  const mudancas = [];

  todasT.forEach(t => {
    if (t.origem !== 'extrato_itau' || t.categoria !== 'nao_classificado') return;
    const sinal = t.tipo === 'entrada' ? 1 : -1;
    const r = classificar(t.descricao_original || t.descricao, sinal * t.valor);
    if (!r) return;
    mudancas.push({ t, r, antes: `${t.natureza}/${t.categoria}` });
    t.natureza = r.natureza;
    t.categoria = r.categoria;
    t.pessoa = r.pessoa;
    t.ambito = r.pessoa === 'Benetti UP' ? 'empresa' : 'pessoal';
    t.descricao = r.descricao;
    t.classificado_por = 'regra_extrato';
    t.nota_classificacao = r.nota || null;
    t.tipo = sinal > 0 ? 'entrada' : 'saida';
  });

  console.log(`\n=== RECLASSIFICAR ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);
  if (!mudancas.length) {
    console.log('Nenhum lançamento em "nao_classificado" casou com alguma regra.\n');
  } else {
    console.log(`${mudancas.length} lançamento(s) saem de "nao_classificado":\n`);
    mudancas.forEach(m => console.log(
      `   ${m.t.data.split('-').reverse().join('/')}  ${brl(m.t.valor).padStart(11)}  ` +
      `${m.antes} → ${m.t.natureza}/${m.t.categoria}  ·  ${m.t.descricao}`));
    const restam = todasT.filter(t => t.origem === 'extrato_itau' && t.categoria === 'nao_classificado');
    console.log(`\nContinuam sem regra: ${restam.length} lançamento(s).`);
    restam.forEach(t => console.log(
      `   ${t.data.split('-').reverse().join('/')}  ${brl(t.valor).padStart(11)}  ${t.descricao_original || t.descricao}`));
  }

  if (aplicar && mudancas.length) {
    fs.writeFileSync(ARQUIVO, JSON.stringify(base, null, 2), 'utf8');
    console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
  } else {
    console.log(aplicar ? '' : '\nRode com --aplicar para gravar.\n');
  }
  process.exit(0);
}

// ---------- execução ----------

const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
if (!alvos.length) {
  console.error('Informe o(s) arquivo(s) .xls do extrato.');
  process.exit(1);
}

const extratos = alvos.map(lerExtrato);

// A conferência de saldo tem de ser feita sobre o arquivo COMO FOI LIDO.
// Logo abaixo, o extrato mais antigo perde os lançamentos que o mais novo já
// cobre — conferir depois disso compara os saldos impressos contra uma fração
// dos movimentos, e o arquivo acusa erro de leitura que não existe. Pior: a
// guarda que recusa gravar deixaria de distinguir leitura errada de corte
// legítimo, e um extrato perfeito seria recusado.
extratos.forEach(e => { e.conferencia = conferirSaldos(e); });

// Dois extratos do mesmo periodo nao podem ser somados: o mesmo PIX apareceria
// duas vezes. E casar linha a linha nao resolve — o que estava agendado num
// arquivo pode aparecer no seguinte com outra data e outro texto (o PIX da vaga
// de carro estava em 12/09 no extrato de 05/09 e saiu em 14/09 no de 13/09).
//
// Quem manda no periodo que cobre e o extrato mais novo. O mais antigo so
// contribui com o que esta fora da janela dele — o comeco do mes que o novo nao
// alcanca, e os agendamentos mais distantes que o novo ainda nao lista.
function janelaDe(e) {
  const datas = e.itens.map(t => t.data).sort();
  if (!datas.length) return null;
  const ini = e.periodo ? e.periodo[0] : datas[0];
  const fim = e.periodo && e.periodo[1] > datas[datas.length - 1] ? e.periodo[1] : datas[datas.length - 1];
  return [ini < datas[0] ? ini : datas[0], fim];
}
const ordemEmissao = e => {
  const m = String(e.emitidoEm || '').match(/(\d{2})\/(\d{2})\/(\d{4})(?:\D+(\d{2}):(\d{2}))?/);
  return m ? `${m[3]}-${m[2]}-${m[1]} ${m[4] || '00'}:${m[5] || '00'}` : '';
};

const superpostos = [];
extratos.forEach(e => {
  const maisNovos = extratos.filter(o => o !== e && ordemEmissao(o) > ordemEmissao(e) && janelaDe(o));
  if (!maisNovos.length) return;
  const antes = e.itens.length;
  e.itens = e.itens.filter(t => !maisNovos.some(o => {
    const [a, b] = janelaDe(o);
    return t.data >= a && t.data <= b;
  }));
  if (antes !== e.itens.length) superpostos.push({ arquivo: e.arquivo, n: antes - e.itens.length });
});

const todos = extratos.flatMap(e => e.itens);

if (!todos.length) {
  console.error('Nenhum lançamento encontrado.');
  process.exit(1);
}

console.log(`\n=== EXTRATO ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);
extratos.forEach(e => {
  const ds = e.itens.map(x => x.data).sort();
  console.log(`${e.arquivo}`);
  console.log(`   ag. ${e.agencia || '?'} c/c ${e.conta || '?'} · ${e.itens.length} lançamentos · ${ds[0] || '—'} a ${ds[ds.length - 1] || '—'}${e.emitidoEm ? ` · emitido ${e.emitidoEm}` : ''}`);
  const c = e.conferencia;
  if (c) {
    console.log(c.falhas.length
      ? `   ⚠️  saldo do dia não fecha em ${c.falhas.length} de ${c.dias - 1} intervalo(s), ${brl(c.total)} sem explicação`
      : `   ✓ saldo do dia fecha em todos os ${c.dias - 1} intervalos — a leitura bate com o próprio extrato`);
    c.falhas.forEach(f => console.log(
      `      ${f.data.split('-').reverse().join('/')}  extrato diz ${brl(f.lido)}, a soma dá ${brl(f.esperado)}  (${brl(f.gap)})`));
  }
});
// Diferenca grande e erro de leitura, nao detalhe do banco: gravar assim
// levaria o erro para dentro da dashboard sem ninguem perceber. Centavos de
// rendimento de aplicacao automatica o proprio extrato nao itemiza.
const LIMITE_SALDO = 1.00;
const naoFecham = extratos.map(e => e.conferencia).filter(c => c && c.total > LIMITE_SALDO);
if (naoFecham.length && aplicar) {
  console.error(`\n❌ Não gravei: o saldo do extrato não fecha com os lançamentos lidos (${brl(naoFecham.reduce((s2, c) => s2 + c.total, 0))}).`);
  console.error('   Isso quase sempre é linha que a leitura não pegou. Corrija o leitor antes de importar.\n');
  process.exit(1);
}

if (superpostos.length) {
  console.log('');
  superpostos.forEach(s2 => console.log(
    `${s2.n} lançamento(s) de ${s2.arquivo} ficaram de fora: período já coberto por um extrato mais novo.`));
}
console.log('');

const transacoes = [];
const semRegra = [];
let seq = 0;

// Meses em que o holerite ja foi importado. O credito do salario so pode ser
// tratado como "ja lancado" nesses: nos outros, marcar como transferencia faria
// a renda do mes simplesmente desaparecer da dashboard.
const baseAtual = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const mesesComHolerite = new Set(((baseAtual.fluxo_mensal || {}).transacoes || [])
  .filter(t => t.origem === 'holerite_elektro')
  .map(t => t.mes_vencimento));

const salarioSemHolerite = [];

todos.sort((a, b) => a.data.localeCompare(b.data)).forEach(item => {
  let r = classificar(item.descricao, item.valor);
  const mes = `${MESES[+item.data.slice(5, 7) - 1]}/${item.data.slice(2, 4)}`;
  const entrada = item.valor > 0;

  // Sem o holerite do mes, o credito volta a ser a unica noticia daquela renda.
  if (r && r.categoria === 'salario_ja_lancado' && !mesesComHolerite.has(mes)) {
    salarioSemHolerite.push({ ...item, mes });
    r = {
      natureza: 'receita', categoria: 'salario', pessoa: 'Juliane',
      descricao: 'Crédito do salário (holerite ainda não importado)',
      nota: 'Conta como receita porque o holerite deste mês não foi importado. Ao importá-lo, reimporte o extrato para não contar duas vezes.',
    };
  }

  if (!r) semRegra.push(item);

  const natureza = r ? r.natureza : (entrada ? 'receita' : 'despesa');
  const conta = extratos.find(e => e.itens.includes(item));

  transacoes.push({
    id: `ext_${mes.replace('/', '')}_${String(++seq).padStart(4, '0')}`,
    data: item.data,
    tipo: entrada ? 'entrada' : 'saida',
    natureza,
    // O valor fica sempre positivo, como no resto da dashboard: o sentido vem
    // do tipo e da natureza, nao do sinal.
    descricao: r ? r.descricao : item.descricao,
    descricao_original: item.descricao,
    valor: Math.abs(item.valor),
    pessoa: r ? r.pessoa : 'Juliane',
    ambito: r && r.pessoa === 'Benetti UP' ? 'empresa' : 'pessoal',
    categoria: r ? r.categoria : 'nao_classificado',
    classificado_por: r ? 'regra_extrato' : null,
    nota_classificacao: r ? r.nota || null : null,
    conta_origem: `Itaú ag. ${(conta && conta.agencia) || '?'} c/c ${(conta && conta.conta) || '?'}`,
    conta_destino: entrada ? 'Itaú (conta corrente)' : 'Terceiros',
    // O extrato lista o que ja saiu junto com o que esta agendado. Pelo regime
    // de caixa o agendado ainda nao aconteceu: fica marcado para nao virar fato
    // consumado numa conferencia de saldo.
    status: item.data > hoje() ? 'agendado' : 'confirmado',
    origem: 'extrato_itau',
    mes_vencimento: mes,
    mes_referencia: mes,
    data_vencimento_fatura: item.data,
    // "CREDITO CONSIGNADO 28/60" diz em que ponto do contrato a parcela esta.
    // Sem ler isso, nao da para saber quantas faltam nem projetar o que ainda
    // vai vencer — a divida vira um debito mensal sem fim a vista.
    //
    // So vale onde o numero e mesmo de parcela. O PIX traz a data no fim da
    // descricao ("PIX TRANSF IGREJA 01/02"), e ler aquilo como "parcela 1 de 2"
    // inventava um parcelamento que nao existe.
    ...(() => {
      const ehParcelamento = natureza === 'divida_parcelada';
      const p = ehParcelamento && item.descricao.match(/\b(\d{1,3})\/(\d{1,3})\s*$/);
      const n = p ? parseInt(p[1], 10) : null;
      const total = p ? parseInt(p[2], 10) : null;
      return p && n >= 1 && total >= 2 && n <= total && total <= 120
        ? { eh_parcelada: true, parcela_numero: n, parcela_total: total, descricao_parcela: `${n}/${total}` }
        : { eh_parcelada: false, parcela_numero: null, parcela_total: null };
    })(),
    carga_id: 'extrato_itau_2026',
  });
});

// ---------- relatório ----------

const por = n => transacoes.filter(t => t.natureza === n);
const soma = arr => Math.round(arr.reduce((s, t) => s + t.valor, 0) * 100) / 100;

console.log('O que entra nos totais:');
console.log(`   receita ............... ${brl(soma(por('receita'))).padStart(14)}  (${por('receita').length})`);
console.log(`   despesa ............... ${brl(soma(por('despesa'))).padStart(14)}  (${por('despesa').length})`);
console.log('');
console.log('O que fica fora, e por quê:');
console.log(`   já lançado por outra fonte ${brl(soma(por('transferencia'))).padStart(14)}  (${por('transferencia').length})  salário e fatura`);
console.log(`   parcela de dívida ..... ${brl(soma(por('divida_parcelada'))).padStart(14)}  (${por('divida_parcelada').length})  quita empréstimo`);
console.log(`   empréstimo tomado ..... ${brl(soma(por('emprestimo'))).padStart(14)}  (${por('emprestimo').length})  entra como dívida, não renda`);
console.log('');

const g = {};
transacoes.forEach(t => {
  const k = `${t.natureza}|${t.categoria}`;
  g[k] = g[k] || { n: 0, soma: 0, natureza: t.natureza, categoria: t.categoria };
  g[k].n++; g[k].soma += t.valor;
});
if (salarioSemHolerite.length) {
  console.log(`${salarioSemHolerite.length} crédito(s) de salário contam como receita: o holerite do mês não foi importado.`);
  salarioSemHolerite.forEach(x =>
    console.log(`   ${x.data.split('-').reverse().join('/')}  ${brl(x.valor).padStart(12)}  ${x.mes}`));
  console.log('   Ao importar esses holerites, rode o extrato de novo — senão a renda conta duas vezes.\n');
}

const agendados = transacoes.filter(t => t.status === 'agendado');
if (agendados.length) {
  console.log(`${agendados.length} lançamento(s) ainda agendados, ${brl(soma(agendados))} — marcados, porque o dinheiro não saiu:`);
  agendados.forEach(t => console.log(`   ${t.data.split('-').reverse().join('/')}  ${brl(t.valor).padStart(11)}  ${t.descricao_original}`));
  console.log('');
}

console.log('Por categoria:');
Object.values(g).sort((a, b) => b.soma - a.soma).forEach(x =>
  console.log(`   ${brl(x.soma).padStart(14)}  ${String(x.n).padStart(3)}x  ${x.natureza.padEnd(17)} ${x.categoria}`));

if (semRegra.length) {
  console.log(`\n${semRegra.length} lançamentos sem regra, em "nao_classificado" — ${brl(soma(transacoes.filter(t => t.categoria === 'nao_classificado')))}:`);
  const s = {};
  semRegra.forEach(x => {
    const k = x.descricao.replace(/\d{2}\/\d{2}$/, '').replace(/\s+\d{4,}.*$/, '').trim().slice(0, 30);
    s[k] = s[k] || { n: 0, soma: 0 };
    s[k].n++; s[k].soma += x.valor;
  });
  Object.entries(s).sort((a, b) => Math.abs(b[1].soma) - Math.abs(a[1].soma)).slice(0, 14)
    .forEach(([k, v]) => console.log(`   ${brl(v.soma).padStart(13)}  ${String(v.n).padStart(3)}x  ${k}`));
}

// ---------- mesclagem ----------

const base = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const anteriores = (base.fluxo_mensal || {}).transacoes || [];

// Substitui so o que veio de extrato, e so nos meses relidos: fatura e holerite
// do mesmo mes ficam de pe.
const mesesLidos = new Set(transacoes.map(t => t.mes_vencimento));
const preservadas = anteriores.filter(t =>
  t.origem !== 'extrato_itau' || !mesesLidos.has(t.mes_vencimento));
const substituidas = anteriores.length - preservadas.length;

const finais = [...preservadas, ...transacoes].sort((a, b) => {
  const ia = MESES.indexOf(a.mes_vencimento.split('/')[0]) + 12 * +a.mes_vencimento.split('/')[1];
  const ib = MESES.indexOf(b.mes_vencimento.split('/')[0]) + 12 * +b.mes_vencimento.split('/')[1];
  return ia - ib || a.data.localeCompare(b.data);
});

// Classificar um lançamento à mão é legítimo e às vezes é o único caminho certo
// (o mesmo texto pode significar coisas diferentes — "COLEGIO" já foi
// mensalidade e ballet). Mas essa classificação vive só dentro do lançamento, e
// a mesclagem abaixo troca todos os do mês relido: ela some sem avisar.
//
// Avisar é o mínimo. Quem decide se vale virar regra é quem está importando.
const perdidas = anteriores.filter(t =>
  t.origem === 'extrato_itau' && mesesLidos.has(t.mes_vencimento)
  && t.categoria !== 'nao_classificado' && t.classificado_por !== 'regra_extrato');
if (perdidas.length) {
  console.log(`\n⚠️  ${perdidas.length} lançamento(s) destes meses estavam classificados à mão, sem regra.`);
  console.log('   A importação substitui todos, então essa classificação se perde. Vire regra o que for repetir:');
  perdidas.slice(0, 12).forEach(t => console.log(
    `   ${t.data.split('-').reverse().join('/')}  ${brl(t.valor).padStart(11)}  ${t.categoria.padEnd(18)} ${t.descricao_original || t.descricao}`));
  if (perdidas.length > 12) console.log(`   ... e mais ${perdidas.length - 12}.`);
}

console.log(`\nMesclagem: ${substituidas} lançamentos de extrato substituídos, ${preservadas.length} preservados`);
console.log(`Total após a mesclagem: ${finais.length} lançamentos`);

if (aplicar) {
  base.fluxo_mensal = { ...(base.fluxo_mensal || {}), transacoes: finais };
  fs.writeFileSync(ARQUIVO, JSON.stringify(base, null, 2), 'utf8');
  console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
} else {
  console.log('\nRode com --aplicar para gravar.\n');
}
