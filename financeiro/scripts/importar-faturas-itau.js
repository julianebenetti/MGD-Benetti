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

const dinheiro = v => {
  const n = parseFloat(String(v).replace(/[R$\s]/g, '').replace(/,/g, ''));
  return isNaN(n) ? 0 : Math.round(n * 100) / 100;
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

function lerFatura(caminho) {
  const wb = XLSX.readFile(caminho);
  const aba = wb.SheetNames.find(n => ABA_FATURA.test(n.trim()));
  const linhas = XLSX.utils.sheet_to_json(wb.Sheets[aba], { header: 1, raw: false, defval: '' });

  const [, mm, aa] = aba.trim().match(ABA_FATURA);
  const mesVencimento = `${MESES[parseInt(mm, 10) - 1]}/${aa}`;

  // O cabeçalho traz "Cartão | Valor | Vencimento"; o vencimento é a última célula preenchida
  const cabecalho = (linhas.find(l => l.some(c => /^\d{2}\/\d{2}\/\d{4}$/.test(String(c).trim()))) || [])
    .filter(c => String(c).trim());
  const vencimento = paraISO(cabecalho[cabecalho.length - 1]);
  const totalPago = dinheiro((linhas[9] || []).find(c => /^R\$/.test(String(c).trim())));

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

  return { aba, mesVencimento, vencimento, totalPago, itens };
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

function classificarNatureza(item) {
  if (/^pagamento/i.test(item.descricao)) return 'pagamento';
  if (/^(canc|cancelamento|estorno)/i.test(item.descricao) || item.valor < 0) return 'estorno';
  return 'despesa';
}

function lerParcelamento(texto) {
  const m = texto.match(/Parcela\s+(\d+)\s+de\s+(\d+)/i);
  if (!m) return null;
  return { numero: parseInt(m[1], 10), total: parseInt(m[2], 10) };
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
const faturas = arquivos.map(lerFatura)
  .sort((a, b) => a.mesVencimento.slice(-2).localeCompare(b.mesVencimento.slice(-2))
                || MESES.indexOf(a.mesVencimento.split('/')[0]) - MESES.indexOf(b.mesVencimento.split('/')[0]));

const transacoes = [];
const resumo = [];
let seq = 0;

faturas.forEach(f => {
  let compras = 0, pagamentos = 0, estornos = 0, nParceladas = 0;

  f.itens.forEach(item => {
    const natureza = classificarNatureza(item);
    const parcela = lerParcelamento(item.parcelamento);
    const herdado = classificacao[normalizar(item.descricao)] || {};
    const regra = aplicarRegra(item.descricao, regras);

    if (natureza === 'pagamento') pagamentos += item.valor;
    else if (natureza === 'estorno') estornos += item.valor;
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
      categoria: (regra && regra.categoria) || herdado.categoria || 'nao_classificado',
      classificado_por: regra ? 'regra' : (herdado.categoria ? 'herdado' : null),
      conta_origem: 'Cartão de Crédito Itaú',
      conta_destino: natureza === 'pagamento' ? 'Itaú' : 'Comerciante',
      status: 'confirmado',
      origem: 'cartao_credito_itau',
      // O mês e o vencimento vêm da própria fatura, não são deduzidos
      mes_vencimento: f.mesVencimento,
      data_vencimento_fatura: f.vencimento,
      mes_referencia: f.mesVencimento,
      fatura_origem: f.aba,
      eh_parcelada: !!parcela,
      parcela_numero: parcela ? parcela.numero : null,
      parcela_total: parcela ? parcela.total : null,
      descricao_parcela: parcela ? `${parcela.numero}/${parcela.total}` : null,
      valor_total_compra: parcela ? Math.round(item.valor * parcela.total * 100) / 100 : null,
      titularidade: item.titularidade,
      portador: item.portador,
      tipo_cartao: item.tipoCartao,
      final_cartao: item.finalCartao,
      carga_id: 'faturas_itau_2026',
    });
  });

  resumo.push({
    mes: f.mesVencimento,
    vencimento: f.vencimento,
    lancamentos: f.itens.length,
    compras: Math.round(compras * 100) / 100,
    estornos: Math.round(estornos * 100) / 100,
    pagamentos: Math.round(pagamentos * 100) / 100,
    cobrado: Math.round((compras + estornos) * 100) / 100,
    pago: f.totalPago,
    parceladas: nParceladas,
  });
});

// ---------- vincular parcelas da mesma compra ----------
//
// A mesma compra parcelada aparece em varias faturas, sempre com a data e o
// valor de parcela originais. Isso identifica a compra atraves das faturas.

const porCompra = {};
transacoes.filter(t => t.eh_parcelada).forEach(t => {
  const chave = `${t.data}|${normalizar(t.descricao)}|${t.parcela_total}`;
  (porCompra[chave] = porCompra[chave] || []).push(t);
});

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

const comprasParceladas = Object.keys(porCompra).length;

// ---------- relatório ----------

console.log(`\n=== IMPORTAÇÃO DAS FATURAS ${aplicar ? '(APLICADA)' : '(SIMULAÇÃO)'} ===\n`);
console.log('Fatura   Vencimento   Lanç.  Parcel.      Compras     Estornos       Cobrado         Pago');
console.log('-'.repeat(94));
resumo.forEach(r => {
  console.log(
    `${r.mes.padEnd(8)} ${r.vencimento.split('-').reverse().join('/')}   ` +
    `${String(r.lancamentos).padStart(4)}  ${String(r.parceladas).padStart(6)}  ` +
    `${r.compras.toFixed(2).padStart(11)}  ${r.estornos.toFixed(2).padStart(11)}  ` +
    `${r.cobrado.toFixed(2).padStart(11)}  ${r.pago.toFixed(2).padStart(11)}`
  );
});
console.log('-'.repeat(94));

const totalCobrado = resumo.reduce((s, r) => s + r.cobrado, 0);
const totalPagamentos = resumo.reduce((s, r) => s + r.pagamentos, 0);
console.log(`Total de lançamentos: ${transacoes.length}`);
console.log(`Compras parceladas distintas: ${comprasParceladas}`);
console.log(`Classificados por regra: ${transacoes.filter(t => t.classificado_por === 'regra').length} (${regras.length} regras ativas)`);
console.log(`Total cobrado ${resumo.length === 1 ? 'nesta fatura' : `nas ${resumo.length} faturas`}: R$ ${totalCobrado.toFixed(2)}`);
console.log(`Pagamentos registrados: R$ ${totalPagamentos.toFixed(2)} (não são despesa)`);

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
const mesesImportados = new Set(faturas.map(f => f.mesVencimento));

const preservadas = substituirTudo
  ? []
  : anteriores.filter(t => !mesesImportados.has(t.mes_vencimento));

const substituidas = anteriores.length - preservadas.length;
const finais = [...preservadas, ...transacoes].sort((a, b) => {
  const ia = MESES.indexOf(a.mes_vencimento.split('/')[0]) + 12 * +a.mes_vencimento.split('/')[1];
  const ib = MESES.indexOf(b.mes_vencimento.split('/')[0]) + 12 * +b.mes_vencimento.split('/')[1];
  return ia - ib || a.data.localeCompare(b.data);
});

// Cabecalhos: os das faturas lidas agora substituem os antigos de mesmo mes
const resumoAnterior = (base.faturas_cartao || []).filter(f => !mesesImportados.has(f.mes));
const resumoFinal = [...resumoAnterior, ...resumo].sort((a, b) => {
  const ia = MESES.indexOf(a.mes.split('/')[0]) + 12 * +a.mes.split('/')[1];
  const ib = MESES.indexOf(b.mes.split('/')[0]) + 12 * +b.mes.split('/')[1];
  return ia - ib;
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
