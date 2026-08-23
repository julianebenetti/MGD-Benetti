#!/usr/bin/env node
/**
 * Importa os comprovantes de pagamento (holerite) em PDF.
 *
 * O comprovante traz o bruto, cada desconto linha a linha e o liquido
 * depositado. Guardar so o liquido perderia o que mais interessa saber: que
 * R$ 1.310 por mes vao embora em consignado antes de o dinheiro chegar na conta,
 * e que plano de saude e previdencia sao despesa recorrente. Entao entra o
 * provento bruto como receita e cada desconto como lancamento proprio — o saldo
 * fecha no liquido, e o custo fica visivel.
 *
 * O mes e o da DATA DE CREDITO, nao o de referencia: regime de caixa, igual ao
 * resto da dashboard. A PLR de marco caiu em 31.03 e conta em marco.
 *
 * O PDF nao usa stream comprimido nem string literal: o texto vem em hexadecimal
 * posicionado por coordenada, entao o layout e remontado por x e y.
 *
 * Uso:
 *   node scripts/importar-holerites.js <arquivo.pdf|pasta> [...]      (simulacao)
 *   node scripts/importar-holerites.js <arquivo.pdf|pasta> --aplicar
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const aplicar = process.argv.includes('--aplicar');

const brl = v => `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;
const dinheiro = t => {
  const n = parseFloat(String(t).trim().replace(/\./g, '').replace(',', '.'));
  return isNaN(n) ? 0 : Math.round(n * 100) / 100;
};

// ---------- leitura do PDF ----------

function streamsDo(buf) {
  const out = [];
  let i = 0;
  while (true) {
    const ini = buf.indexOf('stream', i);
    if (ini < 0) break;
    let p = ini + 6;
    if (buf[p] === 0x0d) p++;
    if (buf[p] === 0x0a) p++;
    const fim = buf.indexOf('endstream', p);
    if (fim < 0) break;
    out.push(buf.slice(p, fim));
    i = fim + 9;
  }
  return out;
}

const deHex = h => h.replace(/\s+/g, '').replace(/[0-9a-f]{2}/gi, b => String.fromCharCode(parseInt(b, 16)));

function linhasDoPdf(caminho) {
  const buf = fs.readFileSync(caminho);
  const pedacos = [];

  for (const s of streamsDo(buf)) {
    let bruto;
    try { bruto = zlib.inflateSync(s); }
    catch { try { bruto = zlib.inflateRawSync(s); } catch { bruto = s; } }

    const conteudo = bruto.toString('latin1');
    const re = /([\d.]+)\s+([\d.]+)\s+Td[^<(]*(?:<([0-9A-Fa-f\s]*)>|\(((?:[^()\\]|\\.)*)\))\s*Tj/g;
    let m;
    while ((m = re.exec(conteudo)) !== null) {
      pedacos.push({
        x: parseFloat(m[1]),
        y: parseFloat(m[2]),
        txt: m[3] !== undefined ? deHex(m[3]) : m[4].replace(/\\([()\\])/g, '$1'),
      });
    }
  }

  const porLinha = {};
  pedacos.forEach(p => {
    const y = Math.round(p.y * 2) / 2;
    (porLinha[y] = porLinha[y] || []).push(p);
  });

  return Object.keys(porLinha).map(Number).sort((a, b) => b - a).map(y => {
    let linha = '';
    porLinha[y].sort((a, b) => a.x - b.x).forEach(p => {
      const col = Math.round(p.x / 4.8);
      if (linha.length < col) linha += ' '.repeat(col - linha.length);
      linha += p.txt;
    });
    return linha.replace(/\s+$/, '');
  });
}

// ---------- classificacao das rubricas ----------
//
// A rubrica e o codigo do sistema de folha, estavel entre os meses — bem mais
// confiavel que o texto da descricao, que varia com abreviacao e acento.
//
// natureza:
//   receita           dinheiro entrando
//   despesa           desconto que e gasto de verdade
//   divida_parcelada  parcela de emprestimo: quita divida, nao e consumo novo
//   ajuste            acerto de competencia; entra e sai, nao muda o caixa

const RUBRICAS = {
  // proventos
  'M010': { natureza: 'receita', categoria: 'salario',          descricao: 'Salário' },
  '/T50': { natureza: 'receita', categoria: 'salario',          descricao: 'Licença médica' },
  '/T21': { natureza: 'receita', categoria: 'salario',          descricao: 'DSR sobre horas extras' },
  '/T22': { natureza: 'receita', categoria: 'salario',          descricao: 'DSR sobre adicional noturno' },
  '303N': { natureza: 'receita', categoria: 'salario',          descricao: 'Adicional noturno' },
  '206N': { natureza: 'receita', categoria: 'beneficio',        descricao: 'Auxílio-creche' },
  '/332': { natureza: 'receita', categoria: 'decimo_terceiro',  descricao: 'Adiantamento do 13º' },
  '/B10': { natureza: 'receita', categoria: 'plr',              descricao: 'Participação nos lucros' },

  // descontos
  //
  // A folha e da Juliane, entao a pessoa e ela por padrao. A excecao e o plano
  // de saude: o convenio desconta na folha dela, mas cobre a familia inteira, e
  // pela regra da casa a pessoa da despesa e quem se beneficia dela.
  '/314': { natureza: 'despesa', categoria: 'inss',                descricao: 'INSS' },
  '/401': { natureza: 'despesa', categoria: 'imposto_renda',       descricao: 'Imposto de renda retido' },
  '/405': { natureza: 'despesa', categoria: 'imposto_renda',       descricao: 'Imposto de renda sobre a PLR' },
  '55AN': { natureza: 'despesa', categoria: 'previdencia_privada', descricao: 'Previdência NEOS' },
  '/505': { natureza: 'despesa', categoria: 'alimentacao',         descricao: 'Vale-refeição/alimentação' },
  '55CN': { natureza: 'despesa', categoria: 'alimentacao',         descricao: 'Cesta básica' },
  '578N': { natureza: 'despesa', categoria: 'saude', pessoa: 'Família', descricao: 'Bradesco — coparticipação médica' },
  '57AN': { natureza: 'despesa', categoria: 'saude', pessoa: 'Família', descricao: 'Bradesco Saúde' },
  '6A9N': { natureza: 'despesa', categoria: 'saude', pessoa: 'Família', descricao: 'Bradesco Odonto' },

  // emprestimo consignado: o principal quita divida, nao e consumo novo
  '1CT1': { natureza: 'divida_parcelada', categoria: 'consignado', pessoa: 'Juliane', descricao: 'Empréstimo consignado 1' },
  'MCT0': { natureza: 'divida_parcelada', categoria: 'consignado', pessoa: 'Juliane', descricao: 'Empréstimo consignado 2' },

  // desconto do adiantamento de PLR ja recebido: nao e gasto, e acerto
  '6F5N': { natureza: 'ajuste', categoria: 'ajuste_folha', pessoa: 'Juliane', descricao: 'Desconto do adiantamento da PLR' },
};

// ---------- interpretacao do holerite ----------

// O comprovante diz em que conta o salario cai — banco, agencia e numero. Ler
// dali evita fixar no codigo uma conta que pode mudar, e deixa o lancamento
// dizer para onde o dinheiro foi de verdade.
const BANCOS = { '341': 'Itaú', '001': 'Banco do Brasil', '033': 'Santander', '104': 'Caixa', '237': 'Bradesco', '260': 'Nubank' };

function contaDeCredito(linhas) {
  const i = linhas.findIndex(l => /Banco\s*\|\s*Ag[êe]ncia\s*\|\s*Conta/i.test(l));
  if (i < 0 || !linhas[i + 1]) return null;

  const col = linhas[i + 1].split('|').map(c => c.trim());
  const banco = (col[3] || '').match(/^\d{3}$/) ? col[3] : null;
  const agencia = (col[4] || '').match(/^\d+$/) ? col[4] : null;
  const conta = (col[5] || '').match(/^[\d-]+$/) ? col[5] : null;
  if (!banco) return null;

  return {
    banco, agencia, conta,
    nome: BANCOS[banco] || `Banco ${banco}`,
    rotulo: `${BANCOS[banco] || `Banco ${banco}`} ag. ${agencia || '?'} c/c ${conta || '?'}`,
  };
}

function lerHolerite(caminho) {
  const linhas = linhasDoPdf(caminho);
  const tudo = linhas.join('\n');

  const credito = (tudo.match(/(\d{2})\.(\d{2})\.(\d{4})/g) || []).pop();
  const refer = tudo.match(/\|\s*([A-Za-zç]+)\s+(\d{4})\s*\|/);
  const liquido = (() => {
    const i = linhas.findIndex(l => /Valor L[íi]quido/i.test(l));
    if (i < 0 || !linhas[i + 1]) return null;
    const nums = linhas[i + 1].match(/[\d.]+,\d{2}/g) || [];
    return nums.length ? dinheiro(nums[0]) : null;
  })();

  const itens = [];
  linhas.forEach(l => {
    // | RUBRICA | qtde | descricao | retifica | proventos | descontos |
    const m = l.match(/^\|\s*([A-Z0-9/]{4})\s+\|\s*([\d.,]+)\|\s*(.+?)\s*\|(.*)$/);
    if (!m) return;

    const [, rubrica, , descricaoPdf, resto] = m;
    const colunas = resto.split('|');
    if (colunas.length < 3) return;

    const provento = dinheiro((colunas[colunas.length - 3] || '').trim());
    const desconto = dinheiro((colunas[colunas.length - 2] || '').trim());
    if (!provento && !desconto) return;

    itens.push({
      rubrica,
      descricaoPdf: descricaoPdf.replace(/\s+/g, ' ').trim(),
      retifica: (colunas[colunas.length - 4] || '').trim(),
      valor: provento || desconto,
      ehProvento: provento > 0,
    });
  });

  const totais = (() => {
    const l = linhas.find(x => /T\s*O\s*T\s*A\s*I\s*S/i.test(x));
    const nums = l ? (l.match(/[\d.]+,\d{2}/g) || []) : [];
    return nums.length >= 2
      ? { proventos: dinheiro(nums[0]), descontos: dinheiro(nums[1]) }
      : null;
  })();

  return {
    arquivo: path.basename(caminho),
    dataCredito: credito ? credito.split('.').reverse().join('-') : null,
    referencia: refer ? `${refer[1]} ${refer[2]}` : null,
    conta: contaDeCredito(linhas),
    liquido, totais, itens,
  };
}

// ---------- execucao ----------

const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
if (!alvos.length) {
  console.error('Informe os PDFs dos comprovantes (ou a pasta que os contém).');
  process.exit(1);
}

const pdfs = alvos.flatMap(a => {
  const st = fs.existsSync(a) ? fs.statSync(a) : null;
  if (!st) { console.error(`Não encontrei ${a}`); process.exit(1); }
  return st.isDirectory()
    ? fs.readdirSync(a).filter(f => /\.pdf$/i.test(f)).map(f => path.join(a, f))
    : [a];
});

const holerites = pdfs.map(lerHolerite)
  .filter(h => h.dataCredito && h.itens.length)
  .sort((a, b) => a.dataCredito.localeCompare(b.dataCredito));

if (!holerites.length) {
  console.error('Nenhum comprovante legível nos arquivos informados.');
  process.exit(1);
}

console.log(`\n=== HOLERITES ${aplicar ? '(APLICADO)' : '(SIMULAÇÃO)'} ===\n`);

const transacoes = [];
const desconhecidas = new Set();
let seq = 0, problemas = 0;

holerites.forEach(h => {
  const [ano, mes] = h.dataCredito.split('-');
  const mesVencimento = `${MESES[+mes - 1]}/${ano.slice(-2)}`;

  let entrou = 0, saiu = 0;
  h.itens.forEach(item => {
    const r = RUBRICAS[item.rubrica];
    if (!r) { desconhecidas.add(`${item.rubrica} ${item.descricaoPdf}`); return; }

    // A retificacao lanca o mesmo valor dos dois lados para acertar competencia:
    // nao muda o caixa, e contar so um lado criaria receita ou despesa do nada.
    const natureza = item.retifica && /^\d{2}\/\d{4}$/.test(item.retifica) ? 'ajuste' : r.natureza;

    // A conferencia segue o lado em que o valor esta no comprovante, nao a
    // natureza: a retificacao lanca o mesmo valor como provento e como desconto,
    // e contar os dois como desconto faria abril fechar R$ 354,38 a menos.
    if (item.ehProvento) entrou += item.valor; else saiu += item.valor;

    transacoes.push({
      id: `folha_${mesVencimento.replace('/', '')}_${String(++seq).padStart(3, '0')}`,
      data: h.dataCredito,
      tipo: item.ehProvento ? 'entrada' : 'saida',
      natureza,
      descricao: r.descricao + (item.retifica ? ` (acerto de ${item.retifica})` : ''),
      valor: item.valor,
      pessoa: r.pessoa || 'Juliane',
      ambito: 'pessoal',
      categoria: r.categoria,
      classificado_por: 'rubrica_folha',
      rubrica: item.rubrica,
      conta_origem: 'Elektro Redes S.A.',
      // O provento cai na conta que o proprio comprovante indica. O desconto
      // nunca chega la — sai antes, na folha.
      conta_destino: item.ehProvento
        ? (h.conta ? h.conta.rotulo : 'conta não cadastrada')
        : 'descontado em folha',
      banco_credito: h.conta ? h.conta.nome : null,
      agencia_credito: h.conta ? h.conta.agencia : null,
      conta_credito: h.conta ? h.conta.conta : null,
      status: 'confirmado',
      origem: 'holerite_elektro',
      mes_vencimento: mesVencimento,
      mes_referencia: h.referencia || mesVencimento,
      data_vencimento_fatura: h.dataCredito,
      eh_parcelada: false,
      parcela_numero: null,
      parcela_total: null,
      carga_id: 'holerites_elektro_2026',
    });
  });

  // O saldo tem de dar o liquido depositado. Se nao der, alguma rubrica foi lida
  // errado — melhor parar do que gravar numero que nao fecha.
  const saldo = Math.round((entrou - saiu) * 100) / 100;
  const confere = h.liquido !== null && Math.abs(saldo - h.liquido) < 0.02;
  if (!confere) problemas++;

  console.log(`${mesVencimento}  creditado em ${h.dataCredito.split('-').reverse().join('/')}  (ref. ${h.referencia || '?'})` +
    `  →  ${h.conta ? h.conta.rotulo : 'conta não identificada no comprovante'}`);
  console.log(`   proventos ${brl(entrou).padStart(13)}   descontos ${brl(saiu).padStart(12)}   saldo ${brl(saldo).padStart(12)}`);
  console.log(`   líquido no comprovante ${brl(h.liquido || 0).padStart(12)}   ${confere ? 'confere' : '*** NÃO CONFERE ***'}`);
  console.log('');
});

if (desconhecidas.size) {
  console.log('Rubricas sem regra — precisam ser cadastradas antes de importar:');
  [...desconhecidas].forEach(d => console.log(`   ${d}`));
  console.log('');
  problemas++;
}

const receitas = transacoes.filter(t => t.natureza === 'receita');
const despesas = transacoes.filter(t => t.natureza === 'despesa');
const divida = transacoes.filter(t => t.natureza === 'divida_parcelada');
const ajustes = transacoes.filter(t => t.natureza === 'ajuste');

// Conferencia da classificacao: uma linha por rubrica, para bater o olho e ver
// se algo foi para a categoria ou a pessoa errada.
console.log('Como cada rubrica foi classificada:');
const porRubrica = {};
transacoes.forEach(t => {
  const k = `${t.rubrica}|${t.natureza}|${t.categoria}|${t.pessoa}`;
  porRubrica[k] = porRubrica[k] || { ...t, n: 0, soma: 0 };
  porRubrica[k].n++;
  porRubrica[k].soma += t.valor;
});
const ordem = { receita: 0, despesa: 1, divida_parcelada: 2, ajuste: 3 };
Object.values(porRubrica)
  .sort((a, b) => ordem[a.natureza] - ordem[b.natureza] || b.soma - a.soma)
  .forEach(r => console.log(
    `   ${r.rubrica.padEnd(5)} ${r.descricao.slice(0, 30).padEnd(32)}` +
    `${brl(r.soma).padStart(13)}  ${String(r.n).padStart(2)}x   ` +
    `${r.natureza.padEnd(17)} ${r.categoria.padEnd(20)} ${r.pessoa}`));
console.log('');

console.log(`${transacoes.length} lançamentos em ${holerites.length} comprovantes`);
console.log(`   receita ............ ${brl(receitas.reduce((s, t) => s + t.valor, 0)).padStart(13)}  (${receitas.length})`);
console.log(`   desconto que é gasto ${brl(despesas.reduce((s, t) => s + t.valor, 0)).padStart(13)}  (${despesas.length})`);
console.log(`   consignado ......... ${brl(divida.reduce((s, t) => s + t.valor, 0)).padStart(13)}  (${divida.length})  não é consumo`);
if (ajustes.length) console.log(`   acerto de competência ${brl(ajustes.reduce((s, t) => s + t.valor, 0)).padStart(12)}  (${ajustes.length})  não muda o caixa`);

if (problemas) {
  console.error(`\n${problemas} problema(s) encontrado(s). Nada foi gravado.\n`);
  process.exit(1);
}

// ---------- mesclagem ----------

const base = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const anteriores = (base.fluxo_mensal || {}).transacoes || [];
const mesesLidos = new Set(transacoes.map(t => t.mes_vencimento));

// Substitui so os meses relidos, e so o que veio de holerite: fatura de cartao
// do mesmo mes nao pode ser tocada aqui.
const preservadas = anteriores.filter(t =>
  t.origem !== 'holerite_elektro' || !mesesLidos.has(t.mes_vencimento));
const substituidas = anteriores.length - preservadas.length;

const finais = [...preservadas, ...transacoes].sort((a, b) => {
  const ia = MESES.indexOf(a.mes_vencimento.split('/')[0]) + 12 * +a.mes_vencimento.split('/')[1];
  const ib = MESES.indexOf(b.mes_vencimento.split('/')[0]) + 12 * +b.mes_vencimento.split('/')[1];
  return ia - ib || a.data.localeCompare(b.data);
});

if (substituidas) console.log(`\nMesclagem: ${substituidas} lançamentos de folha substituídos`);
console.log(`Total após a mesclagem: ${finais.length} lançamentos`);

if (aplicar) {
  base.fluxo_mensal = { ...(base.fluxo_mensal || {}), transacoes: finais };
  fs.writeFileSync(ARQUIVO, JSON.stringify(base, null, 2), 'utf8');
  console.log(`\n✅ Gravado em ${ARQUIVO}\n`);
} else {
  console.log('\nRode com --aplicar para gravar.\n');
}
