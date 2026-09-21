#!/usr/bin/env node
'use strict';
//
// Lê a fatura do cartão Itaú em PDF.
//
// Até aqui só existia leitura do XLSX do internet banking. A Juliane passou a
// mandar o PDF que o app gera, e ele traz exatamente a mesma fatura — mas em
// duas colunas na mesma linha de texto, o que faz uma leitura ingênua embaralhar
// a compra de um bloco com o valor de outro.
//
// Duas disciplinas, as mesmas dos outros leitores:
//
//  1. A coluna é descoberta do próprio documento, não chutada: a linha de
//     cabeçalho que traz DOIS "DATA" diz onde a segunda coluna começa.
//  2. A fatura tem de fechar sozinha. `Total desta fatura` = fatura anterior +
//     pagamentos + saldo financiado + lançamentos atuais, e a soma dos
//     lançamentos lidos tem de dar o `Total dos lançamentos atuais` impresso.
//     Sem isso o leitor não devolve nada — número lido errado não entra em
//     silêncio.
//
// Só leitura. Quem grava é `importar-fatura-itau-pdf.js`.

const { execFileSync } = require('child_process');

// O pdftotext às vezes injeta espaço DENTRO do número ("6.917 ,01",
// "10.66 7,16"), e vários campos da fatura são negativos ("Lançamentos atuais
// -4.164,86" quando o mês teve mais crédito que compra). O padrão tolera as
// duas coisas; `num()` limpa os espaços antes de converter.
const NUM = String.raw`-?[\d.\s]*\d\s*,\s*\d{2}`;

const num = s => {
  if (s == null) return null;
  const limpo = String(s).replace(/\s/g, '');
  if (!/^-?[\d.]*\d,\d{2}$/.test(limpo)) return null;
  return parseFloat(limpo.replace(/\./g, '').replace(',', '.'));
};
const brl = v => (v < 0 ? '-' : '') + 'R$ ' + Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// As seções que o PDF imprime. `futuro` marca o que NÃO é desta fatura:
// "Compras parceladas - próximas faturas" lista parcela que ainda vai ser
// cobrada, e somá-la aqui dobraria a fatura inteira.
const semEspacos = re => new RegExp(re.source.replace(/\\s\*|\\s\+|\s/g, ''), re.flags);

const SECOES_BASE = [
  { re: /^Pagamentos efetuados/i,              nome: 'pagamento' },
  { re: /^Lançamentos:\s*compras e saques/i,   nome: 'compras' },
  { re: /^Lançamentos internacionais/i,        nome: 'internacional' },
  { re: /^Lançamentos:\s*produtos e serviços/i, nome: 'servicos' },
  { re: /^Compras parceladas\s*-\s*próximas/i, nome: 'proximas', futuro: true },
  { re: /^Limites de crédito/i,                nome: 'fim', futuro: true },
  // Os encargos do mês (juros do rotativo, mora, multa, IOF de financiamento)
  // são despesa de verdade e têm de virar lançamento — R$ 848,60 numa fatura e
  // R$ 818,31 em outra ficariam invisíveis. Eles NÃO entram no "Total dos
  // lançamentos atuais" impresso: têm subtotal próprio, e é contra ele que a
  // leitura é conferida.
  { re: /^Encargos cobrados nesta fatura/i,    nome: 'encargos' },
];
const SECOES = SECOES_BASE.map(x => ({ ...x, reSemEspaco: semEspacos(x.re) }));

// Alguns PDFs do Itaú saem do pdftotext com espaço injetado DENTRO de palavras
// e números: "Lan çamen tos", "10.66 7,16", "28/ 07", "2.283, 42". A causa é o
// espaçamento entre caracteres no próprio PDF, não a extração.
//
// O conserto toca **só espaçamento**, nunca dígito: junta o espaço que separa
// dois dígitos, ou um dígito de uma vírgula/ponto/barra. Nenhum algarismo é
// criado, removido ou reordenado — e, se ainda assim a leitura sair errada, as
// duas conferências lá embaixo recusam a fatura. Tentar `-raw` não resolve: ele
// recupera as palavras mas funde as duas colunas na mesma linha, destruindo a
// separação entre um lançamento e outro.
function repararEspacos(linha) {
  let a = linha;
  for (let i = 0; i < 4; i++) {
    a = a.replace(/(\d)\s([\d.,/])/g, '$1$2').replace(/([.,/])\s(\d)/g, '$1$2');
  }
  return a;
}

function textoDoPdf(arquivo) {
  const bruto = execFileSync('pdftotext', ['-layout', arquivo, '-'],
    { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  return bruto.split('\n').map(repararEspacos).join('\n');
}

// Onde a segunda coluna começa. O PDF imprime duas tabelas lado a lado, e a
// linha de cabeçalho que traz dois "DATA" é o próprio documento dizendo a
// posição — mais confiável que medir a olho uma linha de compra qualquer.
// "DATA" pode vir quebrado ("DAT A"), então procura-se a letra inicial de cada
// ocorrência com espaço opcional entre os caracteres.
const DOIS_DATA = /D\s?A\s?T\s?A/g;

function colunaDaDireita(linhas) {
  const posicoes = [];
  linhas.forEach(l => {
    const achados = [...l.matchAll(DOIS_DATA)];
    if (achados.length >= 2) posicoes.push(achados[1].index);
  });
  if (!posicoes.length) return null;
  posicoes.sort((a, b) => a - b);
  return posicoes[Math.floor(posicoes.length / 2)];
}

// Quando a página não tem linha de cabeçalho com dois "DATA" (a página 2 da
// fatura do Black é assim), a posição da coluna é descoberta pela **calha**: a
// faixa vertical de espaço em branco que separa as duas tabelas. Para cada
// posição, conta-se em quantas linhas com conteúdo ali há espaço; a calha é uma
// faixa contígua onde isso vale para todas elas.
//
// Sem isso a página 2 herdava o corte da página 1, o texto da coluna direita
// entrava colado na linha da esquerda e o lançamento deixava de casar — foi o
// que fez sumir R$ 3.875,81 de uma fatura só, incluindo o parcelamento
// automático inteiro.
function calhaDaPagina(linhas) {
  const uteis = linhas.filter(l => l.trim().length > 20);
  if (uteis.length < 6) return null;
  const largura = Math.max(...uteis.map(l => l.length));
  if (largura < 40) return null;

  // Exigir espaço em TODAS as linhas não funciona: uma descrição longa ou um
  // rodapé atravessa a calha e a apaga. 98% é o suficiente para ignorar essas
  // poucas linhas sem inventar calha onde não há — abaixo disso, o espaço entre
  // colunas da mesma tabela começa a competir com a calha de verdade.
  const LIMIAR = 0.98;
  const vazia = [];
  for (let x = 0; x < largura; x++) {
    const livres = uteis.filter(l => x >= l.length || l[x] === ' ').length;
    vazia[x] = livres / uteis.length >= LIMIAR;
  }

  // Faixas contíguas de espaço, com pelo menos 4 colunas, no miolo da página.
  const faixas = [];
  let ini = null;
  for (let x = 0; x <= largura; x++) {
    if (vazia[x]) { if (ini === null) ini = x; }
    else if (ini !== null) { faixas.push([ini, x]); ini = null; }
  }
  const candidatas = faixas.filter(([a, b]) =>
    b - a >= 4 && a > largura * 0.25 && a < largura * 0.75);
  if (!candidatas.length) return null;

  // A mais larga: a calha entre as tabelas é maior que o espaço entre colunas
  // de uma mesma tabela.
  candidatas.sort((u, v) => (v[1] - v[0]) - (u[1] - u[0]));
  // Devolve onde a coluna DIREITA começa (o fim da calha), não onde a calha
  // começa. Cortando na borda esquerda, um valor que encosta na calha perde o
  // último dígito — "1.734,19" virava "1.734,1" e o lançamento sumia inteiro,
  // porque a linha deixava de casar. É a mesma coisa que `colunaDaDireita`
  // devolve: a posição do segundo "DATA".
  return candidatas[0][1];
}

// Desembaralha as duas colunas: primeiro a da esquerda inteira, depois a da
// direita inteira, mantendo a ordem de leitura de cada uma.
//
// **Página por página.** Concatenar a esquerda do documento inteiro e só então
// a direita inteira parece equivalente, mas não é: a seção aberta no fim da
// coluna direita da página 1 continua na coluna esquerda da página 2, e com as
// páginas embaralhadas essa continuação herda a seção errada. Foi o que jogou a
// "Redução Mensalidade" de produtos e serviços para dentro de compras.
function linearizar(texto) {
  const corteGlobal = colunaDaDireita(texto.split(/\n/));
  return texto.split('\f').flatMap(pagina => {
    const linhas = pagina.split('\n');
    const corte = colunaDaDireita(linhas) || calhaDaPagina(linhas) || corteGlobal;
    if (!corte) return linhas;
    const esq = [], dir = [];
    linhas.forEach(l => {
      esq.push(l.slice(0, corte).trimEnd());
      dir.push(l.slice(corte).trimEnd());
    });
    return [...esq, ...dir];
  });
}

// Os rótulos que o Itaú usa na seção de encargos, comparados sem espaço porque
// a extração às vezes quebra a palavra.
const ROTULO_DE_ENCARGO = /^(jurosdorotativo|jurosdemora|multaporatraso|iofdefinanciamento|encargosderefinanciamento|multacontratualdeatraso|jurosdemoradeatraso)/i;

const LANC = new RegExp(String.raw`^(\d{2})\/(\d{2})\s+(.*?)\s{2,}(` + NUM + String.raw`)\s*$`);
const PARCELA = /\s(\d{2})\/(\d{2})\s*$/;

function ler(arquivo) {
  const texto = textoDoPdf(arquivo);

  // Procura um rótulo e devolve o número que vem logo depois dele.
  //
  // O rótulo pode estar quebrado por espaços ("E Tota l de encargos em R$"),
  // então a busca é feita numa cópia da linha sem espaço nenhum. Mas o VALOR
  // não pode sair dessa cópia: sem espaços, o número da coluna vizinha cola no
  // primeiro e vira outro número. Por isso guarda-se o mapa de posições, e o
  // valor é lido do texto original, a partir de onde o rótulo termina.
  const acha = rotulo => {
    const semEsp = new RegExp(rotulo.replace(/\\s[*+]|\s/g, ''), 'i');
    const re = new RegExp(String.raw`^\s*(` + NUM + `)`);
    for (const linha of texto.split('\n')) {
      let compacta = '', posicoes = [];
      for (let i = 0; i < linha.length; i++) {
        if (!/\s/.test(linha[i])) { compacta += linha[i]; posicoes.push(i); }
      }
      const m = compacta.match(semEsp);
      if (!m) continue;
      const fimNaCompacta = m.index + m[0].length;
      if (fimNaCompacta >= posicoes.length) continue;
      const v = linha.slice(posicoes[fimNaCompacta - 1] + 1).match(re);
      if (v) return num(v[1]);
    }
    return null;
  };
  const cabecalho = {
    total_fatura:       acha(String.raw`Total desta fatura`),
    fatura_anterior:    acha(String.raw`Total da fatura anterior`),
    saldo_financiado:   acha(String.raw`Saldo financiado`),
    lancamentos_atuais: acha(String.raw`Lan[çc]amentos atuais`),
    total_lancamentos:  acha(String.raw`Total dos lan[çc]amentos atuais`),
    pagamento_anterior: acha(String.raw`Pagamento efetuado em \d{2}\/\d{2}\/\d{4}`),
    encargos:           acha(String.raw`E?\s*Total de encargos em R\$`),
  };
  // O rótulo também pode vir quebrado ("Car tã o", "Vencime nto"), e aí a busca
  // é feita num texto sem espaço nenhum. Só os RÓTULOS são procurados assim; os
  // valores continuam vindo do texto já reparado, para não colar dois números
  // vizinhos num só.
  const semEspacos = texto.replace(/\s+/g, '');

  const mv = texto.match(/Vencimento:\s*(\d{2})\/(\d{2})\/(\d{4})/i)
          || semEspacos.match(/Vencimento:(\d{2})\/(\d{2})\/(\d{4})/i);
  cabecalho.vencimento = mv ? `${mv[3]}-${mv[2]}-${mv[1]}` : null;

  const mc = texto.match(/Cart[ãa]o\s+[\d.X]*\.(\d{4})/i)
          || semEspacos.match(/Cart[ãa]o[\d.X]*\.(\d{4})/i);
  cabecalho.cartao = mc ? mc[1] : null;

  const mp = texto.match(/Pagamento efetuado em (\d{2})\/(\d{2})\/(\d{4})/i)
          || semEspacos.match(/Pagamentoefetuadoem(\d{2})\/(\d{2})\/(\d{4})/i);
  cabecalho.pago_em = mp ? `${mp[3]}-${mp[2]}-${mp[1]}` : null;

  if (!cabecalho.total_fatura || !cabecalho.vencimento || !cabecalho.cartao) {
    throw new Error(`${arquivo}: não parece uma fatura do Itaú (faltou total, vencimento ou número do cartão).`);
  }

  const ano = +cabecalho.vencimento.slice(0, 4);
  const mesVenc = +cabecalho.vencimento.slice(5, 7);

  const itens = [];
  let secao = null;
  linearizar(texto).forEach(linha => {
    const t = linha.trim();
    if (!t) return;
    // A corrupção quebra palavras ("Lan çamen tos"), então o cabeçalho de seção
    // é reconhecido pela linha sem espaço nenhum.
    const semEspaco = t.replace(/\s+/g, '');
    const s = SECOES.find(x => x.re.test(t) || x.reSemEspaco.test(semEspaco));
    if (s) { secao = s; return; }
    if (!secao || secao.futuro || secao.nome === 'pagamento') return;

    // O repasse de IOF da compra internacional vem sem data — é a única linha
    // de valor da fatura que não começa por dia/mês. Sem ela a soma não fecha.
    const iof = t.match(new RegExp(String.raw`^Repasse de IOF em R\$\s+(` + NUM + `)$`, 'i'));
    if (iof) {
      itens.push({
        data: cabecalho.vencimento,
        descricao: 'Repasse de IOF (compra internacional)',
        valor: num(iof[1]), parcela: null, de_parcelas: null, secao: 'internacional',
      });
      return;
    }

    // A linha de encargo não começa por data e às vezes traz a alíquota antes do
    // valor ("Juros do rotativo   15,10 %   657,53"). O valor é o último número
    // da linha; o que vem com % é taxa, não dinheiro.
    if (secao.nome === 'encargos') {
      // A seção de encargos termina no próprio subtotal. Depois dele o PDF
      // continua com "Novo teto de juros", "Crédito Rotativo / Atraso",
      // "Simulação de compras" — tudo cheio de número que NÃO é cobrança deste
      // mês. Sem esse fim, os encargos somavam R$ 72 mil.
      if (/^E?\s*Total de encargos/i.test(t.replace(/\s+/g, ' '))
       || /^E?Totaldeencargos/i.test(semEspaco)) { secao = { nome: 'fim', futuro: true }; return; }
      // Só vira encargo o que tem rótulo conhecido. A seção não termina sozinha
      // quando todos os encargos são zero (aí o Itaú nem imprime o subtotal), e
      // sem essa lista a leitura seguia engolindo "Simulação de compras",
      // "Limite de crédito" e tudo mais que viesse depois — R$ 152 mil de
      // encargo numa fatura que não tinha nenhum.
      if (!ROTULO_DE_ENCARGO.test(semEspaco)) return;
      const partes = [...t.matchAll(new RegExp(String.raw`(` + NUM + String.raw`)(\s*%)?`, 'g'))]
        .filter(x => !x[2]);
      const rotulo = t.split(/\s{2,}/)[0].trim();
      if (!partes.length || !rotulo) return;
      const v = num(partes[partes.length - 1][1]);
      if (v == null || Math.abs(v) < 0.005) return;
      itens.push({ data: cabecalho.vencimento, descricao: rotulo, valor: v,
                   parcela: null, de_parcelas: null, secao: 'encargos' });
      return;
    }

    const m = t.match(LANC);
    if (!m) return;
    const valor = num(m[4]);
    if (valor == null) return;

    let desc = m[3].replace(/\s+/g, ' ').trim();
    // O valor em dólar da linha internacional vem colado na descrição.
    desc = desc.replace(new RegExp(String.raw`\s+` + NUM + String.raw`\s*(USD|BRL|EUR)$`, 'i'), '').trim();
    if (!desc || /^D[óo]lar de Convers/i.test(desc)) return;

    // A compra parcelada traz "N de M" emendado no fim do estabelecimento.
    let parcela = null, deParcelas = null;
    const pm = desc.match(PARCELA);
    if (pm && +pm[2] > 1 && +pm[1] <= +pm[2]) {
      parcela = +pm[1]; deParcelas = +pm[2];
      desc = desc.slice(0, pm.index).trim();
    }

    // A compra é do ciclo anterior ao vencimento: dia/mês sem ano. Mês maior
    // que o do vencimento só pode ser do ano anterior (fatura de janeiro
    // cobrando compra de dezembro).
    const dd = +m[1], mm = +m[2];
    const anoCompra = mm > mesVenc ? ano - 1 : ano;

    itens.push({
      data: `${anoCompra}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`,
      descricao: desc,
      valor,
      parcela,
      de_parcelas: deParcelas,
      secao: secao.nome,
    });
  });

  // ---- as duas conferências ----
  const erros = [];

  const somaEncargos = Math.round(itens.filter(i => i.secao === 'encargos')
    .reduce((s, i) => s + i.valor, 0) * 100) / 100;
  if (cabecalho.encargos != null && Math.abs(somaEncargos - cabecalho.encargos) > 0.01) {
    erros.push(`os encargos lidos somam ${brl(somaEncargos)}, e a fatura diz ${brl(cabecalho.encargos)}`);
  }
  // Ler encargo sem que a fatura imprima o subtotal significa que a leitura
  // pegou número de outra seção: não há contra o que conferir, então recusa.
  if (cabecalho.encargos == null && Math.abs(somaEncargos) > 0.01) {
    erros.push(`foram lidos ${brl(somaEncargos)} de encargos, mas a fatura não imprime "Total de encargos" — não há contra o que conferir`);
  }

  const soma = itens.filter(i => i.secao !== 'encargos').reduce((s, i) => s + i.valor, 0);
  const alvo = cabecalho.total_lancamentos ?? cabecalho.lancamentos_atuais;
  if (alvo == null) {
    erros.push('a fatura não imprime o total dos lançamentos — não há contra o que conferir a leitura');
  } else if (Math.abs(soma - alvo) > 0.01) {
    erros.push(`a soma dos ${itens.filter(i => i.secao !== 'encargos').length} lançamentos lidos dá ${brl(soma)}, e a fatura diz ${brl(alvo)} (${brl(soma - alvo)} de diferença)`);
  }

  // A identidade do resumo, lida certo.
  //
  // Eu tinha escrito `anterior + pagamento + financiado + atuais = total`, e ela
  // passou na primeira fatura só porque lá o saldo financiado era zero. **O
  // saldo financiado não é uma parcela a mais: ele É `anterior + pagamento`** —
  // o que sobrou da fatura passada e entrou no rotativo. Somá-lo de novo conta
  // a dívida velha duas vezes.
  //
  // E os encargos do mês (juros do rotativo, mora, multa, IOF) têm seção
  // própria e **ficam de fora** do "Total dos lançamentos atuais", mas entram
  // no total a pagar.
  const financiadoEsperado = Math.round(((cabecalho.fatura_anterior || 0)
                                       + (cabecalho.pagamento_anterior || 0)) * 100) / 100;
  if (cabecalho.saldo_financiado != null
      && Math.abs(financiadoEsperado - cabecalho.saldo_financiado) > 0.01) {
    erros.push(`o saldo financiado não fecha: anterior ${brl(cabecalho.fatura_anterior || 0)} + pagamento ${brl(cabecalho.pagamento_anterior || 0)} = ${brl(financiadoEsperado)}, e a fatura diz ${brl(cabecalho.saldo_financiado)}`);
  }

  const fecha = (cabecalho.saldo_financiado != null ? cabecalho.saldo_financiado : financiadoEsperado)
              + (cabecalho.lancamentos_atuais || 0)
              + (cabecalho.encargos || 0);
  if (Math.abs(fecha - cabecalho.total_fatura) > 0.01) {
    erros.push(`o resumo não fecha: saldo financiado + lançamentos atuais + encargos = ${brl(fecha)}, e o total impresso é ${brl(cabecalho.total_fatura)}`);
  }

  return { arquivo, cabecalho, itens, soma, erros };
}

module.exports = { ler, brl };

if (require.main === module) {
  const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
  if (!alvos.length) {
    console.error('uso: node scripts/ler-fatura-itau-pdf.js <fatura.pdf> [...]');
    process.exit(1);
  }
  let ruim = 0;
  alvos.forEach(a => {
    const f = ler(a);
    const c = f.cabecalho;
    console.log(`\n${f.arquivo}`);
    console.log(`   cartão ${c.cartao} · vence ${c.vencimento.split('-').reverse().join('/')} · total ${brl(c.total_fatura)}`);
    console.log(`   anterior ${brl(c.fatura_anterior || 0)} · pagamento ${brl(c.pagamento_anterior || 0)} · atuais ${brl(c.lancamentos_atuais || 0)}`);
    console.log(`   ${f.itens.length} lançamentos lidos, somando ${brl(f.soma)}`);
    const porSecao = {};
    f.itens.forEach(i => { porSecao[i.secao] = (porSecao[i.secao] || 0) + i.valor; });
    Object.entries(porSecao).forEach(([s, v]) => console.log(`      ${s.padEnd(14)} ${brl(v)}`));
    if (f.erros.length) { ruim++; f.erros.forEach(e => console.log(`   ❌ ${e}`)); }
    else console.log('   ✓ fecha: a soma dos lançamentos bate com o total impresso, e o resumo fecha consigo mesmo');
  });
  process.exit(ruim ? 1 : 0);
}
