#!/usr/bin/env node
/**
 * Reconstrói financeiro.json a partir das faturas originais do Itaú (XLSX).
 *
 * Por que reimportar em vez de corrigir o que já está gravado:
 *
 * A importação anterior perdeu a informação de qual fatura cada linha veio e
 * passou a deduzir o mês a partir da data da compra. Isso funciona para compra
 * à vista, mas não para parcela: a fatura traz toda parcela com a data da
 * compra original, então parcelas de meses diferentes acabavam empilhadas no
 * mesmo mês. Também não distinguia pagamento de despesa.
 *
 * O arquivo da fatura tem tudo isso de forma explícita:
 *   - o mês da fatura é o próprio arquivo;
 *   - a data de vencimento está no cabeçalho;
 *   - a coluna "Parcelamento" traz "Parcela N de M";
 *   - as linhas de pagamento vêm identificadas.
 *
 * Categoria e pessoa não vêm na fatura — são classificação da usuária. Saem
 * das regras de data/regras-classificacao.json e, onde não houver regra, do
 * que já estava gravado para a mesma descrição.
 *
 * A importação é incremental: substitui apenas as faturas presentes nos
 * arquivos lidos e preserva as demais. Mandar só a fatura nova basta.
 *
 * Uso:
 *   node scripts/importar-faturas-itau.js                     (simulação)
 *   node scripts/importar-faturas-itau.js --aplicar           (grava, mesclando)
 *   node scripts/importar-faturas-itau.js --aplicar --substituir-tudo
 *   DIR_FATURAS=/caminho node scripts/importar-faturas-itau.js --aplicar
 */

const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const DIR_FATURAS = process.env.DIR_FATURAS
  || '/root/.claude/uploads/30a0a797-34c2-5ab7-8b83-56ad8b2a637d';
const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

const aplicar = process.argv.includes('--aplicar');

// ---------- leitura ----------

// O arquivo mistura dois formatos: as celulas de valor vem no padrao americano
// ("R$ 6,149.17") e o texto do cabecalho no brasileiro ("Voce pagou R$ 6.149,17
// de"). Tratar os dois igual faria 6.149,17 virar 6,15.
const dinheiro = v => {
  let t = String(v).replace(/[R$\s]/g, '');
  if (!t) return 0;

  const negativo = t.startsWith('-');
  t = t.replace(/^-/, '');

  const ultimaVirgula = t.lastIndexOf(',');
  const ultimoPonto = t.lastIndexOf('.');

  if (ultimaVirgula > -1 && ultimoPonto > -1) {
    // Ambos presentes: o que vier por ultimo e o separador decimal
    t = ultimaVirgula > ultimoPonto
      ? t.replace(/\./g, '').replace(',', '.')   // 6.149,17
      : t.replace(/,/g, '');                     // 6,149.17
  } else if (ultimaVirgula > -1) {
    // So virgula: decimal se separar 1 ou 2 casas, senao milhar
    t = t.length - ultimaVirgula - 1 <= 2 ? t.replace(',', '.') : t.replace(/,/g, '');
  } else if (ultimoPonto > -1 && t.length - ultimoPonto - 1 === 3 && !/\.\d{3}$/.test(t.slice(0, ultimoPonto))) {
    // So ponto separando exatamente 3 casas: milhar (1.500), nao decimal
    const semPonto = t.replace(/\./g, '');
    if (!/^\d+$/.test(t.slice(ultimoPonto + 1))) t = semPonto;
    else t = semPonto;
  }

  const n = parseFloat(t);
  return isNaN(n) ? 0 : (negativo ? -1 : 1) * Math.round(Math.abs(n) * 100) / 100;
};

const paraISO = br => {
  const [d, m, a] = String(br).trim().split('/');
  return `${a}-${m}-${d}`;
};

const ehLinhaDeData = v => /^\d{2}\/\d{2}\/\d{4}$/.test(String(v).trim());

// A pasta pode conter outras planilhas (a de classificação, por exemplo).
// Uma fatura se identifica pela aba no formato "Fatura MM-AA".
const ABA_FATURA = /^Fatura\s+(\d{2})-(\d{2})$/i;

function ehFatura(caminho) {
  try {
    return XLSX.readFile(caminho, { bookSheets: true }).SheetNames.some(n => ABA_FATURA.test(n.trim()));
  } catch (err) {
    return false;
  }
}

// Situacao em que a fatura foi exportada. Muda o que os numeros significam:
//   paga          quitada integralmente
//   paga_parcial  parte foi paga; o restante rola para a fatura seguinte com juros
//   fechada       ja fechou e ainda nao venceu
//   aberta        ainda acumulando lancamentos; o valor nao e final
const SITUACOES = [
  [/Fatura\s+Paga\s+Parcial/i, 'paga_parcial'],
  [/Fatura\s+Paga/i, 'paga'],
  [/Fatura\s+Fechada/i, 'fechada'],
  [/Fatura\s+Aberta/i, 'aberta'],
];

function lerFatura(caminho) {
  const wb = XLSX.readFile(caminho);
  const aba = wb.SheetNames.find(n => ABA_FATURA.test(n.trim()));
  const linhas = XLSX.utils.sheet_to_json(wb.Sheets[aba], { header: 1, raw: false, defval: '' });

  const textoTodo = linhas.slice(0, 12).flat().map(String).join(' ');
  const situacao = (SITUACOES.find(([re]) => re.test(textoTodo)) || [null, 'desconhecida'])[1];

  // Linha do cartao: "Itau Uniclass Black Mastercard - final 4846 | ... | vencimento"
  const linhaCartao = linhas.find(l => l.some(c => /final\s+\d{4}/i.test(String(c)))) || [];
  const celulas = linhaCartao.filter(c => String(c).trim());
  const descricaoCartao = String(celulas[0] || '').trim();
  const finalCartao = (descricaoCartao.match(/final\s+(\d{4})/i) || [])[1] || 'sem-numero';

  const vencimento = paraISO(celulas[celulas.length - 1]);

  // O mes vem do vencimento, nao do nome da aba.
  //
  // O Itau nomeia a aba pelo ciclo, e o ciclo do 0442 e do 3794 fecha num mes e
  // vence no dia 1o do seguinte: a aba diz "Fatura 06-26" e o vencimento diz
  // 01/07/2026. Lendo a aba, cinco faturas caiam um mes antes de sair o dinheiro
  // e o registro se contradizia — mes_vencimento "Jun/26" ao lado de
  // data_vencimento_fatura "2026-07-01". Pior: duas faturas seguidas do mesmo
  // cartao caiam no mesmo mes e uma sobrescrevia a outra na mesclagem.
  //
  // O mes usado na dashboard e regime de caixa: conta quando o dinheiro sai da
  // conta. Isso e a data de vencimento.
  const mesVencimento = /^\d{4}-\d{2}-\d{2}$/.test(vencimento)
    ? `${MESES[parseInt(vencimento.slice(5, 7), 10) - 1]}/${vencimento.slice(2, 4)}`
    : (() => {
        const [, mm, aa] = aba.trim().match(ABA_FATURA);
        console.warn(`  ${path.basename(caminho)}: vencimento ilegível, usando o mês da aba (${aba})`);
        return `${MESES[parseInt(mm, 10) - 1]}/${aa}`;
      })();

  // Valores monetarios da linha do cartao, na ordem em que aparecem.
  // Fatura paga:          "Voce pagou R$ X de" | R$ X        -> pago e total sao o mesmo
  // Fatura paga parcial:  "Voce pagou R$ P de" | R$ T        -> P pago de T
  // Fechada ou aberta:    R$ T                               -> so o total, nada pago
  const valores = celulas.flatMap(c => (String(c).match(/R\$\s*[\d.,]+/g) || []).map(dinheiro));
  const totalFatura = valores.length ? valores[valores.length - 1] : 0;
  const pago = situacao === 'aberta' || situacao === 'fechada'
    ? 0
    : (valores.length > 1 ? valores[0] : totalFatura);

  const itens = linhas
    .filter(l => ehLinhaDeData(l[1]))
    .map(l => ({
      data: paraISO(l[1]),
      descricao: String(l[2]).trim(),
      parcelamento: String(l[3]).trim(),
      valor: dinheiro(l[4]),
      titularidade: String(l[6]).trim(),
      portador: String(l[7]).trim(),
      tipoCartao: String(l[8]).trim(),
      finalCartao: String(l[9]).trim().replace(/\*/g, ''),
    }));

  return { arquivo: path.basename(caminho), aba, mesVencimento, vencimento, situacao, descricaoCartao, finalCartao, totalFatura, pago, itens };
}

// ---------- a mesma fatura lida duas vezes ----------
//
// A mesclagem no fim protege contra reimportar uma fatura ja gravada, mas nao
// contra ler a mesma fatura duas vezes na mesma rodada: as duas leituras
// empilhavam seus lancamentos e o gasto do mes aparecia em dobro. Foi o que
// aconteceu com julho, agosto e setembro do 4846 — a pasta tinha duas copias do
// mesmo arquivo e cada linha entrou duas vezes.
//
// Copia repetida do mesmo arquivo se resolve sozinha: usa uma e ignora as
// outras. Versoes que divergem no conteudo, nao — qual delas vale e decisao de
// quem exportou, entao o script para e mostra a diferenca em vez de escolher.

function impressaoDigital(f) {
  return JSON.stringify([f.situacao, f.totalFatura, f.pago,
    f.itens.map(i => [i.data, i.descricao, i.valor])]);
}

function resolverRepetidas(lidas) {
  const porChave = {};
  lidas.forEach(f => {
    const chave = `${f.finalCartao}|${f.mesVencimento}`;
    (porChave[chave] = porChave[chave] || []).push(f);
  });

  const escolhidas = [], conflitos = [];
  let copiasIgnoradas = 0;

  Object.entries(porChave).forEach(([chave, versoes]) => {
    const distintas = [...new Map(versoes.map(f => [impressaoDigital(f), f])).values()];
    if (distintas.length === 1) {
      escolhidas.push(distintas[0]);
      copiasIgnoradas += versoes.length - 1;
    } else {
      conflitos.push({ chave, versoes: distintas });
    }
  });

  return { escolhidas, conflitos, copiasIgnoradas };
}

// ---------- classificação ----------
//
// Duas fontes, nesta ordem: as regras de data/regras-classificacao.json, que
// são a memória do que já foi decidido, e o que já estava gravado para a mesma
// descrição. A regra vem primeiro porque decide também a pessoa — e a pessoa
// da despesa é quem se beneficia dela, não quem passou o cartão.

const normalizar = d => d.toLowerCase().replace(/\s+/g, ' ').trim();

const ARQ_REGRAS = path.join(__dirname, '..', 'data', 'regras-classificacao.json');

function carregarRegras() {
  if (!fs.existsSync(ARQ_REGRAS)) return [];
  return (JSON.parse(fs.readFileSync(ARQ_REGRAS, 'utf8')).regras || [])
    .map(r => ({ ...r, re: new RegExp(r.padrao, 'i') }));
}

function aplicarRegra(descricao, regras) {
  const alvo = normalizar(descricao);
  return regras.find(r => r.re.test(alvo)) || null;
}

// Uma pessoa cadastrada com tipo "empresa" marca o lancamento como despesa da
// empresa. As contas da Juliane ainda nao estao separadas na pratica, entao o
// mesmo extrato traz gasto da casa e da Benetti UP; sem essa marca os dois se
// somariam num total que nao significa nada.
const ARQ_CONFIG = path.join(__dirname, '..', 'data', 'configuracoes.json');

function pessoasDeEmpresa() {
  if (!fs.existsSync(ARQ_CONFIG)) return new Set();
  const cfg = JSON.parse(fs.readFileSync(ARQ_CONFIG, 'utf8'));
  return new Set((cfg.pessoas || []).filter(p => p.tipo === 'empresa').map(p => p.nome));
}

function carregarClassificacaoAtual() {
  if (!fs.existsSync(ARQUIVO)) return {};
  const atual = JSON.parse(fs.readFileSync(ARQUIVO, 'utf8'));
  const mapa = {};
  ((atual.fluxo_mensal || {}).transacoes || []).forEach(t => {
    const chave = normalizar(t.descricao);
    if (!mapa[chave]) mapa[chave] = { categoria: t.categoria, pessoa: t.pessoa };
  });
  return mapa;
}

// ---------- natureza do lançamento ----------
//
// Fatura renegociada: a Juliane parcelou o pagamento do total, e as parcelas vem
// cobradas nos meses seguintes. Elas sao dinheiro saindo da conta, mas nao sao
// consumo novo — as compras que geraram a divida ja foram contadas uma a uma na
// fatura em que aconteceram. Contar a parcela como despesa cobraria as mesmas
// compras duas vezes, e em agosto, setembro e outubro isso pesava de R$ 4 mil a
// R$ 6 mil por mes.
//
// Ficam com natureza propria: somem dos totais de gasto e do "Para Onde Vai",
// e aparecem como divida a pagar. Ja os juros, o IOF e os encargos do
// parcelamento sao custo novo de verdade, e seguem como despesa.
const DIVIDA_PARCELADA = /^(parc\s+fatura|parcela\s+de\s+refinanciamento|credito\s+por\s+parcelamento)/i;

function classificarNatureza(item) {
  if (/^pagamento/i.test(item.descricao)) return 'pagamento';
  if (DIVIDA_PARCELADA.test(item.descricao)) return 'divida_parcelada';
  if (/^(canc|cancelamento|estorno)/i.test(item.descricao) || item.valor < 0) return 'estorno';
  return 'despesa';
}

// A coluna Parcelamento e a fonte primaria: "Parcela 3 de 12".
//
// Alguns lancamentos recorrentes nao usam essa coluna e trazem a parcela
// embutida na descricao — o seguro do carro aparece como
// "Tokio Marine*auto05d12sao Paulobra", que e a parcela 5 de 12. Sem ler isso,
// as 12 parcelas ficam como despesas avulsas e o compromisso que falta vencer
// nao aparece em lugar nenhum.
const PARCELA_NA_DESCRICAO = /(\d{2})d(\d{2})/i;

function lerParcelamento(texto, descricao) {
  const naColuna = texto.match(/Parcela\s+(\d+)\s+de\s+(\d+)/i);
  if (naColuna) {
    return { numero: parseInt(naColuna[1], 10), total: parseInt(naColuna[2], 10), fonte: 'coluna' };
  }

  const naDescricao = String(descricao || '').match(PARCELA_NA_DESCRICAO);
  if (naDescricao) {
    const numero = parseInt(naDescricao[1], 10);
    const total = parseInt(naDescricao[2], 10);
    // Guarda contra falso positivo: so aceita se formar um parcelamento plausivel
    if (numero >= 1 && total >= 2 && numero <= total && total <= 48) {
      return { numero, total, fonte: 'descricao' };
    }
  }
  return null;
}

// Numa cobranca recorrente a descricao muda a cada parcela. Normalizar permite
// reconhecer que sao a mesma compra.
function chaveDaCompra(t) {
  const desc = normalizar(t.descricao).replace(PARCELA_NA_DESCRICAO, 'NNdMM');
  return t.parcela_fonte === 'descricao'
    ? `recorrente|${desc}|${t.parcela_total}`          // a data varia todo mes
    : `${t.data}|${desc}|${t.parcela_total}`;          // parcelas com data unica
}

// ---------- execução ----------

const candidatos = fs.readdirSync(DIR_FATURAS)
  .filter(f => /\.xlsx$/i.test(f) && !f.startsWith('~$'))
  .map(f => path.join(DIR_FATURAS, f));

const arquivos = candidatos.filter(ehFatura);
const ignorados = candidatos.length - arquivos.length;

if (!arquivos.length) {
  console.error(`Nenhuma fatura encontrada em ${DIR_FATURAS}`);
  console.error(`(${candidatos.length} .xlsx examinados; uma fatura tem aba no formato "Fatura MM-AA")`);
  process.exit(1);
}
if (ignorados) console.log(`\n${ignorados} arquivo(s) .xlsx ignorado(s) por não serem fatura`);

const classificacao = carregarClassificacaoAtual();
const regras = carregarRegras();
const empresas = pessoasDeEmpresa();
const { escolhidas, conflitos, copiasIgnoradas } = resolverRepetidas(arquivos.map(lerFatura));

if (copiasIgnoradas) {
  console.log(`\n${copiasIgnoradas} arquivo(s) ignorado(s) por serem cópia de uma fatura já lida`);
}

if (conflitos.length) {
  console.error('\n=== FATURAS COM VERSÕES DIFERENTES NA MESMA PASTA ===\n');
  conflitos.forEach(({ chave, versoes }) => {
    console.error(`${chave} veio em ${versoes.length} versões que não batem:`);
    versoes.forEach(v => {
      const soma = v.itens.reduce((s, i) => s + i.valor, 0);
      console.error(`   ${v.situacao.padEnd(13)} ${String(v.itens.length).padStart(3)} lançamentos  ` +
        `soma R$ ${soma.toFixed(2).padStart(10)}  total R$ ${v.totalFatura.toFixed(2).padStart(10)}   ${v.arquivo}`);
    });
    console.error('');
  });
  console.error('Importar as duas somaria a mesma fatura duas vezes. Deixe na pasta');
  console.error('apenas a versão que vale e rode de novo.\n');
  process.exit(1);
}

const faturas = escolhidas
  .sort((a, b) => a.mesVencimento.slice(-2).localeCompare(b.mesVencimento.slice(-2))
                || MESES.indexOf(a.mesVencimento.split('/')[0]) - MESES.indexOf(b.mesVencimento.split('/')[0]));

const transacoes = [];
const resumo = [];
let seq = 0;

faturas.forEach(f => {
  let compras = 0, pagamentos = 0, estornos = 0, divida = 0, nParceladas = 0;

  f.itens.forEach(item => {
    const natureza = classificarNatureza(item);
    const parcela = lerParcelamento(item.parcelamento, item.descricao);
    const herdado = classificacao[normalizar(item.descricao)] || {};
    const regra = aplicarRegra(item.descricao, regras);

    if (natureza === 'pagamento') pagamentos += item.valor;
    else if (natureza === 'estorno') estornos += item.valor;
    else if (natureza === 'divida_parcelada') divida += item.valor;
    else compras += item.valor;
    if (parcela) nParceladas++;

    transacoes.push({
      id: `txn_${f.mesVencimento.replace('/', '')}_${String(++seq).padStart(4, '0')}`,
      data: item.data,
      tipo: item.valor >= 0 ? 'saida' : 'entrada',
      natureza,
      descricao: item.descricao,
      valor: item.valor,
      pessoa: (regra && regra.pessoa) || herdado.pessoa || (/hugo/i.test(item.portador) ? 'Hugo' : 'Juliane'),

      categoria: natureza === 'divida_parcelada'
        ? 'divida_parcelada'
        : (regra && regra.categoria) || herdado.categoria || 'nao_classificado',
      classificado_por: regra ? 'regra' : (herdado.categoria ? 'herdado' : null),
      conta_origem: f.descricaoCartao || 'Cartão de Crédito Itaú',
      cartao_final: f.finalCartao,
      conta_destino: natureza === 'pagamento' ? 'Itaú' : 'Comerciante',
      status: 'confirmado',
      origem: 'cartao_credito_itau',
      // O mês e o vencimento vêm da própria fatura, não são deduzidos
      mes_vencimento: f.mesVencimento,
      data_vencimento_fatura: f.vencimento,
      mes_referencia: f.mesVencimento,
      fatura_origem: `${f.finalCartao}|${f.mesVencimento}`,
      fatura_situacao: f.situacao,
      eh_parcelada: !!parcela,
      parcela_numero: parcela ? parcela.numero : null,
      parcela_total: parcela ? parcela.total : null,
      descricao_parcela: parcela ? `${parcela.numero}/${parcela.total}` : null,
      parcela_fonte: parcela ? parcela.fonte : null,
      valor_total_compra: parcela ? Math.round(item.valor * parcela.total * 100) / 100 : null,
      titularidade: item.titularidade,
      portador: item.portador,
      tipo_cartao: item.tipoCartao,
      final_cartao: item.finalCartao,
      carga_id: 'faturas_itau_2026',
    });
  });

  // A parcela da fatura renegociada entra no cobrado: a fatura cobra ela de
  // fato, e sem ela o total nao fecharia e a diferenca viraria saldo anterior
  // fantasma. O que ela nao e e consumo — disso cuida a natureza.
  const doPeriodo = Math.round((compras + estornos + divida) * 100) / 100;
  // A fatura pode cobrar mais do que os lancamentos do periodo: quando a
  // anterior nao foi quitada, o saldo rola com juros e entra no total sem
  // aparecer linha a linha.
  const saldoAnterior = Math.round((f.totalFatura - doPeriodo) * 100) / 100;

  resumo.push({
    cartao: f.finalCartao,
    cartao_descricao: f.descricaoCartao,
    mes: f.mesVencimento,
    vencimento: f.vencimento,
    situacao: f.situacao,
    lancamentos: f.itens.length,
    compras: Math.round(compras * 100) / 100,
    estornos: Math.round(estornos * 100) / 100,
    pagamentos: Math.round(pagamentos * 100) / 100,
    // Parcela da fatura renegociada: cobrada nesta fatura, mas nao e consumo
    divida_parcelada: Math.round(divida * 100) / 100,
    // Lancamentos do proprio periodo
    cobrado: doPeriodo,
    // Total que a fatura cobra, incluindo saldo que rolou
    total_fatura: f.totalFatura,
    saldo_anterior: Math.abs(saldoAnterior) > 0.05 ? saldoAnterior : 0,
    pago: f.pago,
    em_aberto: Math.round((f.totalFatura - f.pago) * 100) / 100,
    parceladas: nParceladas,
  });
});

// ---------- ambito: pessoal ou empresa ----------

transacoes.forEach(t => { t.ambito = empresas.has(t.pessoa) ? 'empresa' : 'pessoal'; });

// ---------- vincular parcelas da mesma compra ----------
//
// A mesma compra parcelada aparece em varias faturas, sempre com a data e o
// valor de parcela originais. Isso identifica a compra atraves das faturas.
//
// Roda sobre o conjunto inteiro depois da mesclagem, nunca so sobre o lote
// recem-lido: importando fatura por fatura, cada parcela formaria sozinha uma
// "compra" de uma parcela so, sem enxergar as irmas ja gravadas.

// O mesmo estabelecimento vem ora com a cidade, ora sem: "Magic Kids" numa
// fatura e "Magic Kids        Jundiai       Br" na seguinte. Pela descricao as
// duas viram compras diferentes, e o parcelamento aparece partido ao meio.
//
// Fundir so quando tudo mais coincide — mesma data de compra, mesmo numero de
// parcelas, mesmo valor — e uma descricao e prefixo da outra. Duas compras
// distintas que casem nos tres numeros ainda ficam separadas se o nome divergir
// no meio.
function fundirVariacoesDeNome(grupos) {
  const porNumeros = {};
  Object.entries(grupos).forEach(([chave, ps]) => {
    if (ps[0].parcela_fonte === 'descricao') return;   // recorrente: a data varia
    const k = `${ps[0].data}|${ps[0].parcela_total}|${ps[0].valor.toFixed(2)}`;
    (porNumeros[k] = porNumeros[k] || []).push(chave);
  });

  let fundidos = 0;
  Object.values(porNumeros).filter(cs => cs.length > 1).forEach(chaves => {
    const nome = c => normalizar(grupos[c][0].descricao);
    const base = chaves.reduce((a, b) => (nome(a).length <= nome(b).length ? a : b));
    const juntar = chaves.filter(c => c === base || nome(c).startsWith(nome(base)));
    if (juntar.length < 2) return;

    const destino = juntar.reduce((a, b) => (grupos[a].length >= grupos[b].length ? a : b));
    juntar.filter(c => c !== destino).forEach(c => {
      grupos[destino].push(...grupos[c]);
      delete grupos[c];
      fundidos++;
    });
  });
  return fundidos;
}

function vincularParcelas(todas) {
  const porCompra = {};
  todas.filter(t => t.eh_parcelada).forEach(t => {
    (porCompra[chaveDaCompra(t)] = porCompra[chaveDaCompra(t)] || []).push(t);
  });

  fundirVariacoesDeNome(porCompra);

  Object.values(porCompra).forEach(parcelas => {
    parcelas.sort((a, b) => a.parcela_numero - b.parcela_numero);
    const idCompra = `compra_${parcelas[0].id}`;
    const completa = parcelas.length === parcelas[0].parcela_total;
    // Com o parcelamento inteiro a vista, o total e a soma real das parcelas —
    // a ultima costuma trazer alguns centavos de ajuste. Sem ele, o total e uma
    // estimativa a partir do valor da parcela.
    const valorTotal = completa
      ? Math.round(parcelas.reduce((acc, p) => acc + p.valor, 0) * 100) / 100
      : Math.round(parcelas[0].valor * parcelas[0].parcela_total * 100) / 100;
    parcelas.forEach(p => {
      p.id_compra = idCompra;
      p.data_compra_original = p.data;
      p.valor_total_compra = valorTotal;
      p.valor_total_exato = completa;
      // Parcelas que caem fora das faturas importadas: as anteriores a primeira
      // e as posteriores a ultima.
      p.parcelas_no_periodo = parcelas.length;
    });
  });

  return Object.keys(porCompra).length;
}

const porCompra = {};
transacoes.filter(t => t.eh_parcelada).forEach(t => {
  (porCompra[chaveDaCompra(t)] = porCompra[chaveDaCompra(t)] || []).push(t);
});

const comprasParceladas = Object.keys(porCompra).length;

// ---------- relatório ----------

console.log(`\n=== IMPORTAÇÃO DAS FATURAS ${aplicar ? '(APLICADA)' : '(SIMULAÇÃO)'} ===\n`);
console.log('Cartão  Fatura   Vencimento   Situação       Lanç.   Do período   Saldo ant.   Total fatura         Pago    Em aberto');
console.log('-'.repeat(122));
resumo.forEach(r => {
  console.log(
    `${r.cartao.padEnd(7)} ${r.mes.padEnd(8)} ${r.vencimento.split('-').reverse().join('/')}   ` +
    `${r.situacao.padEnd(13)} ${String(r.lancamentos).padStart(5)}  ` +
    `${r.cobrado.toFixed(2).padStart(11)}  ${(r.saldo_anterior || 0).toFixed(2).padStart(11)}  ` +
    `${r.total_fatura.toFixed(2).padStart(12)} ${r.pago.toFixed(2).padStart(12)} ${r.em_aberto.toFixed(2).padStart(12)}`
  );
});
console.log('-'.repeat(122));

const totalCobrado = resumo.reduce((s, r) => s + r.cobrado, 0);
const comSaldo = resumo.filter(r => r.saldo_anterior > 0.05);
const emAberto = resumo.filter(r => r.em_aberto > 0.05);
const totalPagamentos = resumo.reduce((s, r) => s + r.pagamentos, 0);
console.log(`Total de lançamentos: ${transacoes.length}`);
console.log(`Compras parceladas distintas: ${comprasParceladas}`);
console.log(`Classificados por regra: ${transacoes.filter(t => t.classificado_por === 'regra').length} (${regras.length} regras ativas)`);
const porDescricao = transacoes.filter(t => t.parcela_fonte === 'descricao');
if (porDescricao.length) {
  console.log(`Parcelas lidas da descrição (sem coluna Parcelamento): ${porDescricao.length}`);
  [...new Set(porDescricao.map(t => t.descricao.replace(PARCELA_NA_DESCRICAO, 'NNdMM')))]
    .forEach(d => console.log(`   ${d}`));
}
console.log(`Total cobrado ${resumo.length === 1 ? 'nesta fatura' : `nas ${resumo.length} faturas`}: R$ ${totalCobrado.toFixed(2)}`);
console.log(`Pagamentos registrados: R$ ${totalPagamentos.toFixed(2)} (não são despesa)`);
if (comSaldo.length) {
  console.log(`\nFaturas com saldo rolado da anterior (rotativo):`);
  comSaldo.forEach(r => console.log(`   ${r.mes}: R$ ${r.saldo_anterior.toFixed(2)} veio da fatura anterior`));
}
if (emAberto.length) {
  console.log(`\nEm aberto:`);
  emAberto.forEach(r => console.log(`   ${r.mes} (${r.situacao}): R$ ${r.em_aberto.toFixed(2)} de R$ ${r.total_fatura.toFixed(2)}`));
}

const semCategoria = transacoes.filter(t => t.categoria === 'nao_classificado' && t.natureza === 'despesa').length;
if (semCategoria) console.log(`\nSem categoria herdada: ${semCategoria} lançamentos`);

// ---------- mesclagem ----------
//
// A importacao e incremental: substitui apenas as faturas presentes nos
// arquivos lidos e preserva as demais. Assim da para mandar uma fatura nova
// sem precisar reenviar as anteriores. Com --substituir-tudo, descarta o que
// havia antes e fica so com o que foi lido agora.

const substituirTudo = process.argv.includes('--substituir-tudo');
const base = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const anteriores = (base.fluxo_mensal || {}).transacoes || [];
// A chave e cartao + mes: dois cartoes tem fatura do mesmo mes, e uma nao
// pode sobrescrever a outra.
const faturasImportadas = new Set(faturas.map(f => `${f.finalCartao}|${f.mesVencimento}`));
const chaveDe = t => `${t.cartao_final || '4846'}|${t.mes_vencimento}`;

const preservadas = substituirTudo
  ? []
  : anteriores.filter(t => !faturasImportadas.has(chaveDe(t)));

const substituidas = anteriores.length - preservadas.length;
const finais = [...preservadas, ...transacoes].sort((a, b) => {
  const ia = MESES.indexOf(a.mes_vencimento.split('/')[0]) + 12 * +a.mes_vencimento.split('/')[1];
  const ib = MESES.indexOf(b.mes_vencimento.split('/')[0]) + 12 * +b.mes_vencimento.split('/')[1];
  return ia - ib || a.data.localeCompare(b.data);
});

// So agora da para ligar as parcelas: e aqui que as recem-lidas encontram as
// irmas que ja estavam gravadas.
const comprasLigadas = vincularParcelas(finais);
if (preservadas.length) {
  console.log(`\nParcelamentos religados com o que já estava gravado: ${comprasLigadas} compras`);
}

// Cabecalhos: os das faturas lidas agora substituem os antigos de mesmo mes.
// Com --substituir-tudo os antigos vao junto com os lancamentos — mante-los
// deixaria na aba Cartao & Faturas fatura sem nenhum lancamento por tras.
const resumoAnterior = substituirTudo
  ? []
  : (base.faturas_cartao || []).filter(f => !faturasImportadas.has(`${f.cartao || '4846'}|${f.mes}`));
const resumoFinal = [...resumoAnterior, ...resumo].sort((a, b) => {
  const ia = MESES.indexOf(a.mes.split('/')[0]) + 12 * +a.mes.split('/')[1];
  const ib = MESES.indexOf(b.mes.split('/')[0]) + 12 * +b.mes.split('/')[1];
  return (a.cartao || '').localeCompare(b.cartao || '') || ia - ib;
});

if (preservadas.length || substituidas) {
  console.log(`\nMesclagem: ${substituidas} lançamentos substituídos, ${preservadas.length} preservados de outras faturas`);
  console.log(`Total após a mesclagem: ${finais.length} lançamentos em ${resumoFinal.length} faturas`);
}

if (aplicar) {
  base.fluxo_mensal = { ...(base.fluxo_mensal || {}), transacoes: finais };
  base.faturas_cartao = resumoFinal;
  fs.writeFileSync(ARQUIVO, JSON.stringify(base, null, 2), 'utf8');
  console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
} else {
  console.log('\nRode com --aplicar para gravar.\n');
}
