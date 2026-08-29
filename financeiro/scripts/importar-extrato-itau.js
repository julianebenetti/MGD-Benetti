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
  {
    padrao: /FATURA\s*ITAU|FATURA PAGA ITAU|PGTO MIN ITAU|INT AZUL VISA|CARTAO TUDOAZUL|PAG ENTR PARC/i,
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
    padrao: /PIX (TRANSF|QRS) Juliane/i,
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

function lerExtrato(caminho) {
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

  return { arquivo: path.basename(caminho), agencia, conta, itens };
}

// ---------- execução ----------

const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
if (!alvos.length) {
  console.error('Informe o(s) arquivo(s) .xls do extrato.');
  process.exit(1);
}

const extratos = alvos.map(lerExtrato);
const todos = extratos.flatMap(e => e.itens);

if (!todos.length) {
  console.error('Nenhum lançamento encontrado.');
  process.exit(1);
}

console.log(`\n=== EXTRATO ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);
extratos.forEach(e => {
  const ds = e.itens.map(x => x.data).sort();
  console.log(`${e.arquivo}`);
  console.log(`   ag. ${e.agencia || '?'} c/c ${e.conta || '?'} · ${e.itens.length} lançamentos · ${ds[0]} a ${ds[ds.length - 1]}`);
});
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

console.log(`\nMesclagem: ${substituidas} lançamentos de extrato substituídos, ${preservadas.length} preservados`);
console.log(`Total após a mesclagem: ${finais.length} lançamentos`);

if (aplicar) {
  base.fluxo_mensal = { ...(base.fluxo_mensal || {}), transacoes: finais };
  fs.writeFileSync(ARQUIVO, JSON.stringify(base, null, 2), 'utf8');
  console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
} else {
  console.log('\nRode com --aplicar para gravar.\n');
}
