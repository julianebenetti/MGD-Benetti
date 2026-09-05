#!/usr/bin/env node
/**
 * Confere uma fatura .xlsx antes de importar.
 *
 * Responde as tres perguntas que decidem se vale importar:
 *   - de que mes ela e, de verdade? (o vencimento manda, nao o nome da aba)
 *   - ja esta gravada?
 *   - se ja esta, o conteudo bate com o que foi gravado?
 *
 * Nao grava nada. E so leitura.
 *
 * Uso:
 *   node scripts/conferir-fatura.js arquivo.xlsx [outro.xlsx ...]
 *   node scripts/conferir-fatura.js            (confere a pasta DIR_FATURAS inteira)
 */

const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const ABA_FATURA = /^Fatura\s+(\d{2})-(\d{2})$/i;
const SITUACOES = [
  [/Fatura\s+Paga\s+Parcial/i, 'paga_parcial'],
  [/Fatura\s+Paga/i, 'paga'],
  [/Fatura\s+Fechada/i, 'fechada'],
  [/Fatura\s+Aberta/i, 'aberta'],
];

const brl = v => `R$ ${v.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`;

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

function ler(caminho) {
  const wb = XLSX.readFile(caminho);
  const aba = wb.SheetNames.find(n => ABA_FATURA.test(n.trim()));
  if (!aba) return null;

  const linhas = XLSX.utils.sheet_to_json(wb.Sheets[aba], { header: 1, raw: false, defval: '' });
  const situacao = (SITUACOES.find(([re]) => re.test(linhas.slice(0, 12).flat().map(String).join(' '))) || [null, '?'])[1];

  const celulas = (linhas.find(l => l.some(c => /final\s+\d{4}/i.test(String(c)))) || []).filter(c => String(c).trim());
  const cartao = (String(celulas[0] || '').match(/final\s+(\d{4})/i) || [])[1] || '????';
  const venc = String(celulas[celulas.length - 1]).trim();

  const valores = celulas.flatMap(c => (String(c).match(/R\$\s*[\d.,]+/g) || []).map(dinheiro));
  const total = valores.length ? valores[valores.length - 1] : 0;

  const itens = linhas.filter(l => /^\d{2}\/\d{2}\/\d{4}$/.test(String(l[1]).trim()));
  const pagamentos = itens.filter(l => /^pagamento/i.test(String(l[2]).trim()))
    .map(l => ({ data: String(l[1]).trim(), valor: dinheiro(l[4]) }));

  const [, dd, mm, aaaa] = venc.match(/^(\d{2})\/(\d{2})\/(\d{4})$/) || [];
  const mes = mm ? `${MESES[+mm - 1]}/${aaaa.slice(-2)}` : null;
  const [, abaMM, abaAA] = aba.trim().match(ABA_FATURA);

  return {
    arquivo: path.basename(caminho), aba, cartao, situacao, venc, mes,
    mesDaAba: `${MESES[+abaMM - 1]}/${abaAA}`,
    total, itens: itens.length, pagamentos,
  };
}

const alvos = process.argv.slice(2).filter(a => !a.startsWith('--'));
const caminhos = alvos.length
  ? alvos
  : fs.readdirSync(process.env.DIR_FATURAS || '.')
      .filter(f => /\.xlsx$/i.test(f) && !f.startsWith('~$'))
      .map(f => path.join(process.env.DIR_FATURAS || '.', f));

const base = fs.existsSync(ARQUIVO) ? JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')) : {};
const gravadas = {};
(base.faturas_cartao || []).forEach(f => { gravadas[`${f.cartao}|${f.mes}`] = f; });

let novas = 0, jaTem = 0, divergem = 0;

caminhos.forEach(c => {
  const f = ler(c);
  if (!f) { console.log(`\n${path.basename(c)}\n   não é fatura (nenhuma aba "Fatura MM-AA")`); return; }

  console.log(`\n${f.arquivo}`);
  console.log(`   cartão ${f.cartao} · vence ${f.venc} · ${f.situacao} · ${f.itens} lançamentos · ${brl(f.total)}`);
  if (f.mes !== f.mesDaAba) {
    console.log(`   conta em ${f.mes} (a aba diz "${f.aba}", mas o mês vem do vencimento)`);
  }

  const g = gravadas[`${f.cartao}|${f.mes}`];
  if (!g) {
    novas++;
    console.log(`   ► NOVA — ${f.cartao} ${f.mes} ainda não está na dashboard`);
  } else if (Math.abs(g.total_fatura - f.total) < 0.01 && g.lancamentos === f.itens) {
    jaTem++;
    console.log(`   já gravada, e o conteúdo bate — nada a fazer`);
  } else {
    divergem++;
    console.log(`   ► DIVERGE do que está gravado:`);
    console.log(`       gravado: ${g.lancamentos} lançamentos · ${brl(g.total_fatura)} · ${g.situacao}`);
    console.log(`       arquivo: ${f.itens} lançamentos · ${brl(f.total)} · ${f.situacao}`);
  }

  // O pagamento de uma fatura quita a anterior: e o fio que liga uma na outra e
  // deixa ver qual esta faltando no meio.
  f.pagamentos.forEach(p => console.log(`   quita a fatura anterior: ${brl(Math.abs(p.valor))} em ${p.data}`));
});

console.log(`\n${'-'.repeat(60)}`);
console.log(`${novas} nova(s) · ${jaTem} já gravada(s) · ${divergem} divergente(s)`);
console.log(novas ? 'Importe com: node scripts/importar-faturas-itau.js --aplicar\n' : 'Nada a importar.\n');
