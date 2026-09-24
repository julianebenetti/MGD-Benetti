#!/usr/bin/env node
/**
 * comparar-dados.js — compara dois financeiro.json e, opcionalmente, traz de
 * volta as DECISÕES que foram tomadas na tela sem perder o que foi importado.
 *
 * Existe por causa de um caso real (24/09/26): o `atualizar.sh` guarda a edição
 * pendente da tela antes do `git pull` e devolve depois. Quando os dois lados
 * mexem no mesmo arquivo — a Juliane marcando o plano no VPS, eu importando
 * documento aqui —, o `git stash pop` dá conflito e para. Está certo em parar:
 * `financeiro.json` tem 2 MB numa linha só, e marcador de conflito no meio dele
 * não é coisa para resolver à mão.
 *
 * O que este script resolve é outra coisa: os dois arquivos não são versões
 * rivais do mesmo texto, são duas fontes de verdade sobre coisas DIFERENTES.
 * A tela manda no que é decisão (o plano do mês, a classificação que ela
 * corrigiu); o repositório manda no que foi lido de documento (fatura, extrato,
 * dívida). Juntar é escolher campo a campo, não linha a linha.
 *
 *   node scripts/comparar-dados.js <da-tela.json> <do-repo.json>
 *   node scripts/comparar-dados.js <da-tela.json> <do-repo.json> --trazer-decisoes --aplicar
 *
 * Sem --aplicar, só conta o que faria.
 *
 * "A tela manda" tem uma condição que a primeira versão deste script esqueceu:
 * **só vale se a tela for mais nova.** O stash é uma foto tirada ANTES do `git
 * pull`, então ele pode guardar decisão já superada — na primeira vez que este
 * script rodou de verdade, a tela marcava "adiar" nas quatro contas que ela
 * tinha acabado de decidir pagar. Por isso o plano do mês só é trazido quando
 * `atualizado_em` da tela é maior que o do repo; senão o mês é recusado e o
 * motivo é impresso, e trazer exige `--plano-da-tela <mes>` explícito.
 *
 * REGRA DO SCRIPT: ele carrega só o que sabe carregar, e **grita** o que não
 * sabe. Diferença que ele não traz aparece na saída, sempre. Merge que resolve
 * em silêncio é pior do que conflito, porque ninguém fica sabendo o que sumiu.
 */

const fs = require('fs');

// Campos que a tela edita (ver "Edição em Lançamentos" no CLAUDE.md). São
// decisão de quem olhou o lançamento — o importador não tem como saber melhor.
const CAMPOS_DE_DECISAO = ['categoria', 'pessoa', 'ambito', 'fixa_variavel',
                           'nota_classificacao', 'observacao'];

const moeda = v => (v === null || v === undefined)
  ? 'não cadastrado'
  : 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function porId(lista) {
  const m = new Map();
  for (const x of (lista || [])) if (x && x.id) m.set(x.id, x);
  return m;
}

/** Diferenças de plano_do_mes: é o que a Juliane marcou na tela. */
function compararPlano(aTela, aRepo) {
  const pa = aTela.plano_do_mes || {}, pb = aRepo.plano_do_mes || {};
  const meses = [...new Set([...Object.keys(pa), ...Object.keys(pb)])].sort();
  const achados = [];
  for (const mes of meses) {
    const a = pa[mes], b = pb[mes];
    if (a && !b) { achados.push({ mes, tipo: 'só na tela', a, b: null }); continue; }
    if (!a && b) { achados.push({ mes, tipo: 'só no repo', a: null, b }); continue; }
    const itens = [];
    const chaves = [...new Set([...Object.keys(a.itens || {}), ...Object.keys(b.itens || {})])].sort();
    for (const k of chaves) {
      const va = (a.itens || {})[k], vb = (b.itens || {})[k];
      if (va !== vb) itens.push({ chave: k, tela: va, repo: vb });
    }
    const orcDifere = Number(a.orcamento) !== Number(b.orcamento);
    const obsDifere = (a.observacao || '') !== (b.observacao || '');
    if (itens.length || orcDifere || obsDifere) {
      // Quem e mais novo decide. "A tela manda" so vale se a tela for a versao
      // mais recente — e o stash guarda justamente uma foto do PASSADO, tirada
      // antes do `git pull`. Sem este teste o script desfaz decisao nova com
      // decisao velha, em silencio, que e o erro que ele existe para impedir.
      const ta = a.atualizado_em || null, tb = b.atualizado_em || null;
      const quemEMaisNovo = (!ta || !tb) ? 'nao_da_para_saber'
        : ta > tb ? 'tela' : ta < tb ? 'repo' : 'empate';
      achados.push({ mes, tipo: 'diverge', a, b, itens, orcDifere, obsDifere, ta, tb, quemEMaisNovo });
    }
  }
  return achados;
}

/** Diferenças em fluxo_mensal.transacoes, separando decisão de dado importado. */
function compararTransacoes(aTela, aRepo) {
  const ta = porId(aTela.fluxo_mensal && aTela.fluxo_mensal.transacoes);
  const tb = porId(aRepo.fluxo_mensal && aRepo.fluxo_mensal.transacoes);
  const soNaTela = [], soNoRepo = [], decisao = [], outros = [];
  for (const [id, x] of ta) if (!tb.has(id)) soNaTela.push(x);
  for (const [id, x] of tb) if (!ta.has(id)) soNoRepo.push(x);
  for (const [id, x] of ta) {
    const y = tb.get(id);
    if (!y) continue;
    for (const campo of [...new Set([...Object.keys(x), ...Object.keys(y)])]) {
      if (igual(x[campo], y[campo])) continue;
      const linha = { id, campo, tela: x[campo], repo: y[campo], descricao: x.descricao, data: x.data };
      (CAMPOS_DE_DECISAO.includes(campo) ? decisao : outros).push(linha);
    }
  }
  return { soNaTela, soNoRepo, decisao, outros };
}

/** Listas declarativas com id: dívidas, investimentos, pessoas... */
function compararLista(aTela, aRepo, chave) {
  const ma = porId(aTela[chave]), mb = porId(aRepo[chave]);
  const soNaTela = [...ma.keys()].filter(k => !mb.has(k));
  const soNoRepo = [...mb.keys()].filter(k => !ma.has(k));
  const mudaram = [];
  for (const [id, x] of ma) {
    const y = mb.get(id);
    if (y && !igual(x, y)) {
      const campos = [...new Set([...Object.keys(x), ...Object.keys(y)])]
        .filter(c => !igual(x[c], y[c]));
      mudaram.push({ id, campos, x, y });
    }
  }
  return { soNaTela, soNoRepo, mudaram };
}

function compararFaturas(aTela, aRepo) {
  const chave = f => `${f.cartao}|${f.mes}`;
  const ma = new Map((aTela.faturas_cartao || []).map(f => [chave(f), f]));
  const mb = new Map((aRepo.faturas_cartao || []).map(f => [chave(f), f]));
  const soNaTela = [...ma.keys()].filter(k => !mb.has(k));
  const soNoRepo = [...mb.keys()].filter(k => !ma.has(k));
  const mudaram = [];
  for (const [k, f] of ma) {
    const g = mb.get(k);
    if (g && !igual(f, g)) {
      mudaram.push({ k, campos: [...new Set([...Object.keys(f), ...Object.keys(g)])].filter(c => !igual(f[c], g[c])) });
    }
  }
  return { soNaTela, soNoRepo, mudaram };
}

function main() {
  const args = process.argv.slice(2);
  const aplicar = args.includes('--aplicar');
  const trazer = args.includes('--trazer-decisoes');
  // `--plano-da-tela Out/26` traz um valor junto; ele nao e nome de arquivo.
  const arquivos = args.filter((a, i) =>
    !a.startsWith('--') && args[i - 1] !== '--plano-da-tela');

  if (arquivos.length !== 2) {
    console.error('uso: node scripts/comparar-dados.js <da-tela.json> <do-repo.json> [--trazer-decisoes] [--aplicar]');
    process.exit(2);
  }
  const [ARQ_TELA, ARQ_REPO] = arquivos;
  for (const f of arquivos) if (!fs.existsSync(f)) { console.error('não achei ' + f); process.exit(2); }

  const tela = JSON.parse(fs.readFileSync(ARQ_TELA, 'utf8'));
  const repo = JSON.parse(fs.readFileSync(ARQ_REPO, 'utf8'));

  console.log('');
  console.log('  DA TELA (o que estava guardado no VPS): ' + ARQ_TELA);
  console.log('  DO REPO (o que foi importado aqui):     ' + ARQ_REPO);
  console.log('  ' + '─'.repeat(72));

  // ── 1. O plano do mês ──────────────────────────────────────────────────
  const plano = compararPlano(tela, repo);
  console.log('\n▸ PLANO DO MÊS  (decisão dela — a tela manda)\n');
  if (!plano.length) {
    console.log('  Os dois lados têm o mesmo plano. Nada a trazer.');
  } else for (const p of plano) {
    if (p.tipo === 'só na tela') {
      console.log(`  ${p.mes}: existe SÓ na tela — ${Object.keys(p.a.itens || {}).length} itens, orçamento ${moeda(p.a.orcamento)}`);
      console.log('     → seria criado no repo');
      continue;
    }
    if (p.tipo === 'só no repo') {
      console.log(`  ${p.mes}: existe SÓ no repo — ${Object.keys(p.b.itens || {}).length} itens, orçamento ${moeda(p.b.orcamento)}`);
      console.log('     → mantido; a tela não conhecia este mês');
      continue;
    }
    console.log(`  ${p.mes}:`);
    console.log(`     marcado na tela em ${p.ta || '(não diz)'}   ·   no repo em ${p.tb || '(não diz)'}`);
    if (p.quemEMaisNovo === 'repo') {
      console.log('     ⚠ A TELA ESTÁ MAIS VELHA QUE O REPO. O stash é uma foto tirada antes do');
      console.log('       `git pull`, então ela pode ser decisão já superada. Este mês NÃO é');
      console.log('       trazido — para trazer assim mesmo: --plano-da-tela ' + p.mes);
    } else if (p.quemEMaisNovo === 'nao_da_para_saber') {
      console.log('     ⚠ Um dos lados não diz quando foi marcado. Sem saber qual é mais novo,');
      console.log('       este mês NÃO é trazido — para trazer assim mesmo: --plano-da-tela ' + p.mes);
    }
    if (p.orcDifere) console.log(`     orçamento  tela ${moeda(p.a.orcamento)}  x  repo ${moeda(p.b.orcamento)}`);
    if (p.obsDifere) console.log('     observação difere');
    for (const it of p.itens) {
      console.log(`     ${it.chave}\n        tela: ${it.tela === undefined ? '(não marcado)' : it.tela}   repo: ${it.repo === undefined ? '(não marcado)' : it.repo}`);
    }
  }

  // ── 2. Lançamentos ─────────────────────────────────────────────────────
  const t = compararTransacoes(tela, repo);
  console.log('\n▸ LANÇAMENTOS\n');
  console.log(`  ${t.decisao.length} campo(s) de classificação divergem  (a tela manda: ${CAMPOS_DE_DECISAO.join(', ')})`);
  for (const l of t.decisao.slice(0, 40)) {
    console.log(`     ${l.data}  ${l.campo.padEnd(18)} tela: ${String(l.tela)}   repo: ${String(l.repo)}   — ${l.descricao}`);
  }
  if (t.decisao.length > 40) console.log(`     ... e mais ${t.decisao.length - 40}`);

  console.log(`\n  ${t.soNaTela.length} lançamento(s) existem só na tela`);
  for (const x of t.soNaTela.slice(0, 20)) console.log(`     ${x.data}  ${moeda(x.valor)}  ${x.descricao}  [${x.origem}]`);
  if (t.soNaTela.length > 20) console.log(`     ... e mais ${t.soNaTela.length - 20}`);

  console.log(`\n  ${t.soNoRepo.length} lançamento(s) existem só no repo  (importados depois do stash)`);

  console.log(`\n  ${t.outros.length} divergência(s) em campo que NÃO é decisão — o script não traz nenhuma.`);
  if (t.outros.length) {
    const porCampo = {};
    for (const l of t.outros) (porCampo[l.campo] = porCampo[l.campo] || []).push(l);
    for (const [campo, linhas] of Object.entries(porCampo)) {
      console.log(`     ${campo}: ${linhas.length}`);
      for (const l of linhas.slice(0, 6)) {
        console.log(`        ${l.data}  tela: ${JSON.stringify(l.tela)}   repo: ${JSON.stringify(l.repo)}   — ${l.descricao}`);
      }
      if (linhas.length > 6) console.log(`        ... e mais ${linhas.length - 6}`);
    }
    console.log('     ↑ OLHE ESTA LISTA. Se algo aqui foi você editando na tela, tem de');
    console.log('       ser resolvido à mão — o script não adivinha.');
  }

  // ── 3. O que foi importado ─────────────────────────────────────────────
  console.log('\n▸ DADO IMPORTADO  (o repo manda — nada daqui é trazido da tela)\n');
  for (const chave of ['dividas', 'investimentos', 'pessoas', 'receitas', 'despesas']) {
    if (!Array.isArray(tela[chave]) && !Array.isArray(repo[chave])) continue;
    const c = compararLista(tela, repo, chave);
    if (!c.soNaTela.length && !c.soNoRepo.length && !c.mudaram.length) continue;
    console.log(`  ${chave}: ${c.soNoRepo.length} só no repo, ${c.soNaTela.length} só na tela, ${c.mudaram.length} com campo diferente`);
    for (const id of c.soNoRepo) console.log(`     + repo: ${id}`);
    for (const id of c.soNaTela) console.log(`     ! só na tela: ${id}  ← confira, pode ser edição sua`);
    for (const m of c.mudaram) console.log(`     ~ ${m.id}: ${m.campos.join(', ')}`);
  }
  const f = compararFaturas(tela, repo);
  if (f.soNaTela.length || f.soNoRepo.length || f.mudaram.length) {
    console.log(`  faturas_cartao: ${f.soNoRepo.length} só no repo, ${f.soNaTela.length} só na tela, ${f.mudaram.length} com campo diferente`);
    for (const k of f.soNaTela) console.log(`     ! só na tela: ${k}  ← confira`);
  }

  // ── 4. Aplicar ─────────────────────────────────────────────────────────
  if (!trazer) {
    console.log('\n  Só comparei. Para trazer o plano e a classificação da tela para o');
    console.log('  arquivo do repo:  --trazer-decisoes --aplicar\n');
    return;
  }

  const destino = JSON.parse(JSON.stringify(repo));
  let mudouPlano = 0, mudouCampo = 0;

  const forcados = new Set();
  for (let i = 0; i < process.argv.length; i++) {
    if (process.argv[i] === '--plano-da-tela' && process.argv[i + 1]) forcados.add(process.argv[i + 1]);
  }
  const recusados = [];
  destino.plano_do_mes = destino.plano_do_mes || {};
  for (const p of plano) {
    const mes = p.mes;
    if (p.tipo === 'só no repo') continue;
    if (p.tipo === 'diverge' && p.quemEMaisNovo !== 'tela' && !forcados.has(mes)) {
      recusados.push(p);
      continue;
    }
    destino.plano_do_mes[mes] = tela.plano_do_mes[mes];
    mudouPlano++;
  }

  const idx = porId(destino.fluxo_mensal && destino.fluxo_mensal.transacoes);
  for (const l of t.decisao) {
    const alvo = idx.get(l.id);
    if (!alvo) continue;
    if (l.tela === undefined) delete alvo[l.campo]; else alvo[l.campo] = l.tela;
    mudouCampo++;
  }

  console.log('\n▸ O QUE SERIA GRAVADO EM ' + ARQ_REPO + '\n');
  console.log(`  ${mudouPlano} mês(es) de plano vindos da tela`);
  for (const p of recusados) {
    const motivo = p.quemEMaisNovo === 'repo' ? 'a tela é mais velha' : 'não dá para saber qual é mais novo';
    console.log(`  ${p.mes}: NÃO trazido — ${motivo} (tela ${p.ta || '?'} · repo ${p.tb || '?'})`);
    console.log(`     para trazer assim mesmo: --plano-da-tela ${p.mes}`);
  }
  console.log(`  ${mudouCampo} campo(s) de classificação vindos da tela`);
  console.log(`  ${t.soNaTela.length} lançamento(s) que só existem na tela: NÃO são criados — se algum for`);
  console.log('     seu, ele precisa ser lançado à mão ou reimportado da fonte.');

  if (!aplicar) {
    console.log('\n  Simulação. Nada foi gravado. Rode de novo com --aplicar.\n');
    return;
  }

  fs.copyFileSync(ARQ_REPO, ARQ_REPO + '.antes-do-merge');
  fs.writeFileSync(ARQ_REPO, JSON.stringify(destino, null, 2));
  console.log('\n  ✓ Gravado. Cópia do anterior em ' + ARQ_REPO + '.antes-do-merge\n');
}

main();
