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

const num = s => {
  if (s == null) return null;
  const m = String(s).replace(/\s/g, '').match(/^-?[\d.]*\d,\d{2}$/);
  if (!m) return null;
  return parseFloat(String(s).replace(/\s/g, '').replace(/\./g, '').replace(',', '.'));
};
const brl = v => (v < 0 ? '-' : '') + 'R$ ' + Math.abs(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// As seções que o PDF imprime. `futuro` marca o que NÃO é desta fatura:
// "Compras parceladas - próximas faturas" lista parcela que ainda vai ser
// cobrada, e somá-la aqui dobraria a fatura inteira.
const SECOES = [
  { re: /^Pagamentos efetuados/i,              nome: 'pagamento' },
  { re: /^Lançamentos:\s*compras e saques/i,   nome: 'compras' },
  { re: /^Lançamentos internacionais/i,        nome: 'internacional' },
  { re: /^Lançamentos:\s*produtos e serviços/i, nome: 'servicos' },
  { re: /^Compras parceladas\s*-\s*próximas/i, nome: 'proximas', futuro: true },
  { re: /^Limites de crédito/i,                nome: 'fim', futuro: true },
  { re: /^Encargos cobrados nesta fatura/i,    nome: 'fim', futuro: true },
];

function textoDoPdf(arquivo) {
  return execFileSync('pdftotext', ['-layout', arquivo, '-'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
}

// Onde a segunda coluna começa. O PDF imprime duas tabelas lado a lado, e a
// linha de cabeçalho que traz dois "DATA" é o próprio documento dizendo a
// posição — mais confiável que medir a olho uma linha de compra qualquer.
function colunaDaDireita(linhas) {
  const posicoes = [];
  linhas.forEach(l => {
    const i = l.indexOf('DATA');
    if (i < 0) return;
    const j = l.indexOf('DATA', i + 4);
    if (j > 0) posicoes.push(j);
  });
  if (!posicoes.length) return null;
  posicoes.sort((a, b) => a - b);
  return posicoes[Math.floor(posicoes.length / 2)];
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
    const corte = colunaDaDireita(linhas) || corteGlobal;
    if (!corte) return linhas;
    const esq = [], dir = [];
    linhas.forEach(l => {
      esq.push(l.slice(0, corte).trimEnd());
      dir.push(l.slice(corte).trimEnd());
    });
    return [...esq, ...dir];
  });
}

const LANC = /^(\d{2})\/(\d{2})\s+(.*?)\s{2,}(-?[\d.]*\d,\d{2})\s*$/;
const PARCELA = /\s(\d{2})\/(\d{2})\s*$/;

function ler(arquivo) {
  const texto = textoDoPdf(arquivo);

  const acha = re => { const m = texto.match(re); return m ? num(m[1]) : null; };
  const cabecalho = {
    total_fatura:    acha(/Total desta fatura\s+([\d.]*\d,\d{2})/i),
    fatura_anterior: acha(/Total da fatura anterior\s+([\d.]*\d,\d{2})/i),
    saldo_financiado: acha(/Saldo financiado\s+([\d.]*\d,\d{2})/i),
    lancamentos_atuais: acha(/Lançamentos atuais\s+([\d.]*\d,\d{2})/i),
    total_lancamentos: acha(/Total dos lançamentos atuais\s+([\d.]*\d,\d{2})/i),
    pagamento_anterior: acha(/Pagamento efetuado em \d{2}\/\d{2}\/\d{4}\s+(-?[\d.]*\d,\d{2})/i),
  };
  const mv = texto.match(/Vencimento:\s*(\d{2})\/(\d{2})\/(\d{4})/i);
  cabecalho.vencimento = mv ? `${mv[3]}-${mv[2]}-${mv[1]}` : null;
  const mc = texto.match(/Cart[ãa]o\s+[\d.X]*\.(\d{4})/i);
  cabecalho.cartao = mc ? mc[1] : null;
  const mp = texto.match(/Pagamento efetuado em (\d{2})\/(\d{2})\/(\d{4})/i);
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
    const s = SECOES.find(x => x.re.test(t));
    if (s) { secao = s; return; }
    if (!secao || secao.futuro || secao.nome === 'pagamento') return;

    // O repasse de IOF da compra internacional vem sem data — é a única linha
    // de valor da fatura que não começa por dia/mês. Sem ela a soma não fecha.
    const iof = t.match(/^Repasse de IOF em R\$\s+([\d.]*\d,\d{2})$/i);
    if (iof) {
      itens.push({
        data: cabecalho.vencimento,
        descricao: 'Repasse de IOF (compra internacional)',
        valor: num(iof[1]), parcela: null, de_parcelas: null, secao: 'internacional',
      });
      return;
    }

    const m = t.match(LANC);
    if (!m) return;
    const valor = num(m[4]);
    if (valor == null) return;

    let desc = m[3].replace(/\s+/g, ' ').trim();
    // O valor em dólar da linha internacional vem colado na descrição.
    desc = desc.replace(/\s+[\d.]*\d,\d{2}\s*(USD|BRL|EUR)$/i, '').trim();
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

  const soma = itens.reduce((s, i) => s + i.valor, 0);
  const alvo = cabecalho.total_lancamentos ?? cabecalho.lancamentos_atuais;
  if (alvo == null) {
    erros.push('a fatura não imprime o total dos lançamentos — não há contra o que conferir a leitura');
  } else if (Math.abs(soma - alvo) > 0.01) {
    erros.push(`a soma dos ${itens.length} lançamentos lidos dá ${brl(soma)}, e a fatura diz ${brl(alvo)} (${brl(soma - alvo)} de diferença)`);
  }

  const fecha = (cabecalho.fatura_anterior || 0)
              + (cabecalho.pagamento_anterior || 0)
              + (cabecalho.saldo_financiado || 0)
              + (cabecalho.lancamentos_atuais || 0);
  if (Math.abs(fecha - cabecalho.total_fatura) > 0.01) {
    erros.push(`o resumo não fecha: anterior + pagamento + financiado + atuais = ${brl(fecha)}, e o total impresso é ${brl(cabecalho.total_fatura)}`);
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
