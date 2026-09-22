#!/usr/bin/env node
/**
 * Importa o extrato da conta corrente do Bradesco (PDF do app "Bradesco Celular").
 *
 * É a QUARTA conta da Juliane, e a segunda conta corrente: ag. 2389, c/c
 * 555440-3. Ela quase não movimenta — mas é por ela que sai o débito automático
 * de alguns cartões Bradesco, e quando o saldo não cobre, o banco empresta pelo
 * limite e cobra IOF e encargo todo mês. Esse custo não aparecia em lugar nenhum.
 *
 * Lê o PDF do app e também o CSV que o internet banking exporta. O CSV é
 * melhor fonte: traz crédito e débito em colunas próprias, sem depender da
 * posição do número na linha.
 *
 * Uso:
 *   node scripts/importar-extrato-bradesco-cc.js <arquivo.pdf|.csv> [...]   (simulação)
 *   node scripts/importar-extrato-bradesco-cc.js <arquivo.csv> --aplicar
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const aplicar = process.argv.includes('--aplicar');
const brl = v => `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
const hoje = () => new Date().toISOString().slice(0, 10);
const num = s => parseFloat(String(s).replace(/\./g, '').replace(',', '.'));

// ---------- classificação ----------
//
// O mesmo vocabulário do extrato do Itaú, e pelos mesmos motivos: o que já foi
// contado por outra fonte vira transferência, e o custo do crédito é despesa
// financeira de verdade.
const REGRAS = [
  {
    padrao: /GASTOS CARTAO DE CREDITO/i,
    natureza: 'transferencia', categoria: 'pagamento_fatura', pessoa: 'Juliane',
    descricao: 'Débito automático da fatura do cartão Bradesco',
    nota: 'As compras já estão lançadas uma a uma pela fatura. Contar o débito também somaria o mesmo gasto duas vezes.',
  },
  {
    padrao: /IOF S\/ UTILIZACAO LIMITE|ENCARGOS LIMITE DE CRED/i,
    natureza: 'despesa', categoria: 'encargos_financeiros', pessoa: 'Juliane',
    descricao: 'Juros e IOF do limite (conta Bradesco)',
    nota: 'Custo de usar o limite da conta — é despesa nova, não é a compra de novo.',
  },
  {
    padrao: /PIX RECEBIDO[\s\S]*JULIANE FERREIRA|REM: JULIANE FERREIRA/i,
    natureza: 'transferencia', categoria: 'entre_contas_proprias', pessoa: 'Juliane',
    descricao: 'Transferência entre contas próprias',
    nota: 'Dinheiro dela indo de uma conta dela para outra: mexe no saldo, não é receita.',
  },
];
const classificar = d => REGRAS.find(r => r.padrao.test(d)) || null;

// ---------- leitura ----------
//
// O PDF imprime "Saldo" sem sinal. Nesta conta o saldo fica NEGATIVO quase o
// tempo todo (limite usado), então cada débito faz o número impresso SUBIR — e
// ler isso como saldo positivo inverteria a conta inteira.
//
// Em vez de supor, o sinal do saldo inicial é descoberto: tenta os dois, e vale
// o que reproduz todos os saldos impressos. Se nenhum fechar, a leitura está
// errada e o script não grava.
function lerExtrato(caminho) {
  const txt = execFileSync('pdftotext', ['-layout', caminho, '-'], { encoding: 'utf8' })
    .replace(/\f/g, ' ');
  const linhas = txt.split('\n');

  const agencia = (txt.match(/Ag[êe]ncia:\s*(\d+)/i) || [])[1] || null;
  const conta = (txt.match(/Conta:\s*([\d-]+)/i) || [])[1] || null;
  const emitidoEm = (txt.match(/Data:\s*(\d{2}\/\d{2}\/\d{4})[^\n]*/i) || [])[1] || null;

  // Uma linha de lançamento começa com a data e termina com 2 ou 3 números: o
  // valor (crédito ou débito) e o saldo. A descrição às vezes quebra na linha
  // de cima, então ela é remontada com a vizinha quando o histórico vem vazio.
  const itens = [];
  linhas.forEach((linha, i) => {
    const m = linha.match(/^\s*(\d{2})\/(\d{2})\/(\d{4})\s+(.*)$/);
    if (!m) return;
    const resto = m[4];
    const nums = [...resto.matchAll(/-?\d{1,3}(?:\.\d{3})*,\d{2}/g)];
    if (nums.length < 2) return;

    const saldo = num(nums[nums.length - 1][0]);
    const valor = num(nums[nums.length - 2][0]);
    let desc = resto.slice(0, nums[nums.length - 2].index).replace(/\s{2,}\d+\s*$/, '').trim();
    // "ENCARGOS LIMITE DE CRED" vem na linha de cima e o "ENCARGO - 08,00%" na
    // de baixo; sem juntar, a descrição fica vazia e a regra não casa.
    if (!desc || /^\d+$/.test(desc)) {
      const antes = (linhas[i - 1] || '').trim(), depois = (linhas[i + 1] || '').trim();
      desc = [antes, depois].filter(x => x && !/^\d/.test(x) && !/^Total/i.test(x)).join(' ').trim();
    }
    desc = desc.replace(/\s+/g, ' ');

    // Coluna: crédito e débito ocupam posições diferentes. O cabeçalho diz onde.
    const cab = linhas.find(l => /Cr[ée]dito \(R\$\)/.test(l)) || '';
    const iCred = cab.indexOf('Crédito'), iDeb = cab.indexOf('Débito');
    const pos = nums[nums.length - 2].index + resto.length - resto.length + linha.indexOf(resto) + nums[nums.length - 2].index;
    const ehCredito = iCred > -1 && iDeb > iCred ? pos < (iCred + iDeb) / 2 + 6 : false;

    itens.push({
      data: `${m[3]}-${m[2]}-${m[1]}`,
      descricao: desc,
      valor: ehCredito ? valor : -valor,
      saldoImpresso: saldo,
    });
  });

  const datas = itens.map(t => t.data).sort();
  return { arquivo: path.basename(caminho), agencia, conta, emitidoEm, itens,
           de: datas[0], ate: datas[datas.length - 1] };
}

// O CSV do internet banking. Formato:
//
//   Extrato de: Ag: 2389 | Conta: 555440-3;;;;;
//   Data;Histórico;Docto.;Crédito (R$);Débito (R$);Saldo (R$)
//   11/09/2026;COD. LANC. 0;0; ;0,00;277,62
//
// Duas vantagens sobre o PDF: crédito e débito têm coluna própria (no PDF o
// sinal sai da POSIÇÃO do número na linha), e o arquivo declara o período que
// cobre. O saldo continua vindo sem sinal, então a descoberta do sinal inicial
// segue valendo — e aqui ela é o que revela que a conta estava em −R$ 277,62.
//
// `COD. LANC. 0` com crédito e débito zerados é marcador de saldo de abertura,
// não lançamento: entra com valor 0 só para a conferência ter por onde começar.
function lerCSV(caminho) {
  // O arquivo vem em UTF-8 com BOM; o PDF do app vem em latin-1. Ler o CSV
  // como latin-1 quebraria "Movimentação" e o filtro de período não seria
  // encontrado — o arquivo deixaria de declarar o que cobre.
  const bruto = fs.readFileSync(caminho);
  const texto = bruto.toString('utf8').replace(/^\uFEFF/, '');
  const linhas = texto.split(/\r?\n/);

  const cab = linhas.find(l => /Extrato de:/i.test(l)) || '';
  const agencia = (cab.match(/Ag:\s*(\d+)/i) || [])[1] || null;
  const conta = (cab.match(/Conta:\s*([\d-]+)/i) || [])[1] || null;
  const emitidoEm = (texto.match(/tem como base\s*(\d{2}\/\d{2}\/\d{4})/i) || [])[1] || null;

  // O próprio arquivo diz o que cobre. É isso que impede a reimportação de
  // apagar o que está fora da janela dele — o CSV de 13 a 22/09 não sabe nada
  // do IOF de 02/09, e substituir o mês inteiro faria esse custo sumir.
  const jan = texto.match(/Movimenta[çc][ãa]o entre:\s*(\d{2}\/\d{2}\/\d{4})\s*e\s*(\d{2}\/\d{2}\/\d{4})/i);
  const iso = br => br.split('/').reverse().join('-');

  const itens = [];
  linhas.forEach(linha => {
    const c = linha.split(';');
    if (c.length < 6) return;
    const m = String(c[0]).trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!m) return;
    const valorDe = x => { const t = String(x).trim(); return t && /\d/.test(t) ? num(t) : 0; };
    const credito = valorDe(c[3]), debito = valorDe(c[4]);
    itens.push({
      data: `${m[3]}-${m[2]}-${m[1]}`,
      descricao: String(c[1]).trim().replace(/\s+/g, ' '),
      valor: Math.round((credito - debito) * 100) / 100,
      saldoImpresso: valorDe(c[5]),
    });
  });

  const datas = itens.map(t => t.data).sort();
  return {
    arquivo: path.basename(caminho), agencia, conta, emitidoEm, itens,
    de: jan ? iso(jan[1]) : datas[0],
    ate: jan ? iso(jan[2]) : datas[datas.length - 1],
  };
}

const lerArquivo = c => /\.csv$/i.test(c) ? lerCSV(c) : lerExtrato(c);

// Confere a leitura contra o próprio extrato, como o importador do Itaú faz.
function conferir(e) {
  const mov = e.itens.filter(t => t.valor !== 0);
  if (!mov.length) return null;
  for (const sinalInicial of [-1, 1]) {
    const primeiro = e.itens[0];
    let saldo = sinalInicial * primeiro.saldoImpresso;
    let ok = true;
    for (const t of e.itens.slice(1)) {
      saldo = Math.round((saldo + t.valor) * 100) / 100;
      if (Math.abs(Math.abs(saldo) - t.saldoImpresso) > 0.005) { ok = false; break; }
    }
    if (ok) return { fecha: true, sinalInicial, saldoFinal: saldo };
  }
  return { fecha: false };
}

// ---------- execução ----------

const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
if (!alvos.length) { console.error('Informe o(s) PDF(s) ou CSV(s) do extrato Bradesco.'); process.exit(1); }

const extratos = alvos.map(lerArquivo);
console.log(`\n=== EXTRATO BRADESCO CC ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);

let travou = false;
extratos.forEach(e => {
  const c = conferir(e);
  const ds = e.itens.map(t => t.data).sort();
  console.log(`${e.arquivo}`);
  console.log(`   ag. ${e.agencia || '?'} c/c ${e.conta || '?'} · ${e.itens.length} linhas · ${ds[0]} a ${ds[ds.length - 1]}${e.emitidoEm ? ` · emitido ${e.emitidoEm}` : ''}`);
  if (!c || !c.fecha) {
    console.log('   ⚠️  o saldo impresso NÃO fecha com os lançamentos lidos');
    travou = true;
  } else {
    console.log(`   ✓ saldo fecha em todas as linhas · a conta ${c.sinalInicial < 0 ? 'começa NEGATIVA (limite usado)' : 'começa positiva'} e termina em ${brl(c.saldoFinal)}`);
  }
});

if (travou) {
  console.error('\n❌ Não gravei: a leitura não reproduz o saldo do próprio extrato.\n');
  process.exit(1);
}

// **PIX recebido sem nome só vira transferência própria se a outra ponta
// existir.** O CSV escreve apenas "PIX RECEBIDO", sem o remetente — e carimbar
// todo Pix recebido como dinheiro dela mudando de conta esconderia receita de
// verdade no dia em que outra pessoa lhe mandar dinheiro. A prova é do outro
// lado: uma saída de mesmo valor, no mesmo dia, numa conta dela já importada.
// Sem essa prova o lançamento fica `nao_classificado`, para ela dizer o que é.
const baseAtual = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const jaGravadas = ((baseAtual.fluxo_mensal || {}).transacoes) || [];
const OUTRAS_CONTAS_DELA = ['extrato_itau', 'extrato_bradesco_cc'];
function temAOutraPonta(item) {
  return jaGravadas.some(t =>
    OUTRAS_CONTAS_DELA.includes(t.origem)
    && t.data === item.data
    && t.natureza === 'transferencia'
    && t.categoria === 'entre_contas_proprias'
    && Math.abs(Math.abs(t.valor) - Math.abs(item.valor)) < 0.01);
}
const PIX_SEM_NOME = /^PIX RECEBIDO$/i;

const transacoes = [];
const semRegra = [];
const provados = [];
let seq = 0;
extratos.forEach(e => e.itens.filter(t => t.valor !== 0).forEach(item => {
  let r = classificar(item.descricao);
  if (!r && PIX_SEM_NOME.test(item.descricao.trim()) && item.valor > 0 && temAOutraPonta(item)) {
    r = {
      natureza: 'transferencia', categoria: 'entre_contas_proprias', pessoa: 'Juliane',
      descricao: 'Transferência entre contas próprias',
      nota: 'O CSV não traz o remetente. Classificado assim porque a saída de mesmo valor, no mesmo dia, já está lançada em outra conta dela.',
    };
    provados.push(item);
  }
  if (!r) semRegra.push(item);
  const entrada = item.valor > 0;
  const mes = `${MESES[+item.data.slice(5, 7) - 1]}/${item.data.slice(2, 4)}`;
  transacoes.push({
    id: `brcc_${mes.replace('/', '')}_${String(++seq).padStart(4, '0')}`,
    data: item.data,
    tipo: entrada ? 'entrada' : 'saida',
    natureza: r ? r.natureza : (entrada ? 'receita' : 'despesa'),
    descricao: r ? r.descricao : item.descricao,
    descricao_original: item.descricao,
    valor: Math.abs(item.valor),
    pessoa: r ? r.pessoa : 'Juliane',
    ambito: 'pessoal',
    categoria: r ? r.categoria : 'nao_classificado',
    classificado_por: r ? 'regra_bradesco_cc' : null,
    nota_classificacao: r ? r.nota || null : null,
    conta_origem: `Bradesco ag. ${e.agencia || '?'} c/c ${e.conta || '?'}`,
    conta_destino: entrada ? 'Bradesco (conta corrente)' : 'Terceiros',
    status: item.data > hoje() ? 'agendado' : 'confirmado',
    origem: 'extrato_bradesco_cc',
    mes_vencimento: mes,
    mes_referencia: mes,
    data_vencimento_fatura: item.data,
    eh_parcelada: false, parcela_numero: null, parcela_total: null,
    carga_id: 'extrato_bradesco_cc_2026',
  });
}));

const soma = a => Math.round(a.reduce((s, t) => s + t.valor, 0) * 100) / 100;
const por = n => transacoes.filter(t => t.natureza === n);
console.log('\nO que entra nos totais:');
console.log(`   despesa ............... ${brl(soma(por('despesa'))).padStart(12)}  (${por('despesa').length})  juros e IOF do limite`);
console.log('O que fica fora, e por quê:');
console.log(`   já contado por outra fonte ${brl(soma(por('transferencia'))).padStart(12)}  (${por('transferencia').length})  fatura e conta própria`);
transacoes.forEach(t => console.log(
  `   ${t.data.split('-').reverse().join('/')}  ${(t.tipo === 'entrada' ? '+' : '-') + brl(t.valor).padStart(10)}  ${t.natureza.padEnd(13)} ${t.descricao_original.slice(0, 44)}`));
if (provados.length) {
  console.log(`\n${provados.length} Pix recebido sem nome, classificado pela outra ponta:`);
  provados.forEach(t => console.log(`   ${t.data.split('-').reverse().join('/')}  ${brl(t.valor)}  há saída igual no mesmo dia em conta dela`));
}
if (semRegra.length) {
  console.log(`\n${semRegra.length} sem regra:`);
  semRegra.forEach(t => console.log(`   ${t.data} ${brl(Math.abs(t.valor))} ${t.descricao}`));
}

const base = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const anteriores = (base.fluxo_mensal || {}).transacoes || [];

// **A mesclagem respeita a janela do arquivo, não o mês inteiro.**
//
// O CSV exportado do internet banking cobre um intervalo curto — este vai de
// 13 a 22/09 — e substituir todo o mês de setembro apagaria o IOF de 02/09 e o
// encargo de 08/09, que vieram do PDF e que o CSV não tem como conhecer. Some
// custo real sem ninguém notar. Cada arquivo diz o período que cobre, e só
// dentro dele o que estava gravado é trocado.
const janelas = extratos.map(e => [e.de, e.ate]).filter(([a, b]) => a && b);
const dentroDeAlgumaJanela = d => janelas.some(([a, b]) => d >= a && d <= b);
const preservadas = anteriores.filter(t =>
  t.origem !== 'extrato_bradesco_cc' || !dentroDeAlgumaJanela(t.data));
const finais = [...preservadas, ...transacoes].sort((a, b) => {
  const i = x => MESES.indexOf(x.mes_vencimento.split('/')[0]) + 12 * +x.mes_vencimento.split('/')[1];
  return i(a) - i(b) || a.data.localeCompare(b.data);
});
console.log(`\nMesclagem: ${anteriores.length - preservadas.length} substituídos, ${preservadas.length} preservados · total ${finais.length}`);
console.log(`   janela coberta pelos arquivos: ${janelas.map(([a, b]) => `${a} a ${b}`).join(' · ')}`);

if (aplicar) {
  base.fluxo_mensal = { ...(base.fluxo_mensal || {}), transacoes: finais };
  fs.writeFileSync(ARQUIVO, JSON.stringify(base, null, 2), 'utf8');
  console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
} else {
  console.log('\nRode com --aplicar para gravar.\n');
}
