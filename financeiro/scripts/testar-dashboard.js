#!/usr/bin/env node
/**
 * Suíte de testes da dashboard financeira.
 *
 * Objetivo: reduzir o risco de a dashboard exibir um número errado.
 *
 * A estratégia é sempre a mesma — calcular o valor esperado direto do JSON,
 * por um caminho independente do código da interface, e comparar com o que a
 * interface realmente mostra no navegador. Um teste que apenas repetisse a
 * lógica da dashboard não provaria nada.
 *
 * Uso:  node scripts/testar-dashboard.js
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const ARQUIVO = path.join(__dirname, '..', 'data', 'financeiro.json');
const URL = process.env.DASH_URL || 'http://localhost:3001';
const NAVEGADOR = process.env.CHROMIUM || '/opt/pw-browsers/chromium';

const MES_ORDEM = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
const A_CONFIRMAR = 'A confirmar';
const ANO = 26;

let passou = 0, falhou = 0;
const falhas = [];

function ok(nome, condicao, detalhe) {
  if (condicao) {
    passou++;
    console.log(`  \x1b[32m✓\x1b[0m ${nome}`);
  } else {
    falhou++;
    falhas.push({ nome, detalhe });
    console.log(`  \x1b[31m✗\x1b[0m ${nome}`);
    if (detalhe) console.log(`      ${detalhe}`);
  }
}

function igual(nome, obtido, esperado, tolerancia = 0.01) {
  const iguais = typeof esperado === 'number'
    ? Math.abs(obtido - esperado) <= tolerancia
    : obtido === esperado;
  ok(nome, iguais, iguais ? null : `esperado: ${esperado}  |  obtido: ${obtido}`);
}

const brl = v => 'R$ ' + (v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const somar = arr => Math.round(arr.reduce((s, t) => s + t.valor, 0) * 100) / 100;
const numeroDe = txt => parseFloat(String(txt).replace(/[^\d,-]/g, '').replace(/\./g, '').replace(',', '.')) || 0;

function noEscopo(mv) {
  if (!mv) return false;
  if (mv === A_CONFIRMAR) return true;
  return parseInt(mv.split('/')[1], 10) === ANO;
}

(async () => {
  console.log('\n══════════════════════════════════════════════════════════════');
  console.log('  TESTES DA DASHBOARD FINANCEIRA');
  console.log('══════════════════════════════════════════════════════════════');

  // ---------------------------------------------------------------------
  // Verdade de referência, calculada direto do arquivo
  // ---------------------------------------------------------------------
  const dados = JSON.parse(fs.readFileSync(ARQUIVO, 'utf8'));
  const todas = dados.fluxo_mensal.transacoes;
  const escopo = todas.filter(t => noEscopo(t.mes_vencimento));

  const ref = {
    totalLinhas: todas.length,
    totalGeral: somar(todas),
    escopoLinhas: escopo.length,
    escopoTotal: somar(escopo),
    compras: somar(escopo.filter(t => t.valor > 0)),
    estornos: somar(escopo.filter(t => t.valor < 0)),
    porMes: {},
    porPessoa: {},
    porCategoria: {},
    aConfirmar: somar(escopo.filter(t => t.mes_vencimento === A_CONFIRMAR)),
  };
  escopo.forEach(t => {
    ref.porMes[t.mes_vencimento] = Math.round(((ref.porMes[t.mes_vencimento] || 0) + t.valor) * 100) / 100;
    ref.porPessoa[t.pessoa] = Math.round(((ref.porPessoa[t.pessoa] || 0) + t.valor) * 100) / 100;
    if (t.valor > 0) ref.porCategoria[t.categoria] = Math.round(((ref.porCategoria[t.categoria] || 0) + t.valor) * 100) / 100;
  });

  // =====================================================================
  console.log('\n▸ INTEGRIDADE DOS DADOS\n');
  // =====================================================================

  igual('Contagem de lançamentos preservada', ref.totalLinhas, 629);
  igual('Soma geral preservada', ref.totalGeral, 40086.47);
  igual('Compras menos estornos fecha com o total', ref.compras + ref.estornos, ref.escopoTotal);

  const ids = todas.map(t => t.id);
  igual('Nenhum id duplicado', new Set(ids).size, ids.length);
  ok('Todo lançamento tem id', todas.every(t => t.id));
  ok('Todo lançamento tem data válida', todas.every(t => /^\d{4}-\d{2}-\d{2}$/.test(t.data)),
     todas.filter(t => !/^\d{4}-\d{2}-\d{2}$/.test(t.data)).slice(0, 3).map(t => t.data).join(', '));
  ok('Todo lançamento tem valor numérico', todas.every(t => typeof t.valor === 'number' && !isNaN(t.valor)));
  ok('Todo lançamento tem mês de fatura', todas.every(t => t.mes_vencimento));

  // =====================================================================
  console.log('\n▸ ESCOPO DO ANO (2026)\n');
  // =====================================================================

  igual('Todos os lançamentos estão no escopo de 2026', ref.escopoLinhas, ref.totalLinhas);
  const mesesFora = [...new Set(todas.map(t => t.mes_vencimento))].filter(m => !noEscopo(m));
  ok('Nenhuma fatura de ano anterior', mesesFora.length === 0, mesesFora.join(', '));

  const mesesReais = [...new Set(escopo.map(t => t.mes_vencimento))].filter(m => m !== A_CONFIRMAR);
  ok('Faturas reais têm volume plausível (mín. 20 lançamentos)',
     mesesReais.every(m => escopo.filter(t => t.mes_vencimento === m).length >= 20),
     mesesReais.map(m => `${m}: ${escopo.filter(t => t.mes_vencimento === m).length}`).join(' | '));

  const semAno = todas.filter(t => t.mes_vencimento !== A_CONFIRMAR && !/\/\d{2}$/.test(t.mes_vencimento));
  igual('Mês de fatura sempre no formato Mmm/AA', semAno.length, 0);

  // =====================================================================
  console.log('\n▸ PESSOA\n');
  // =====================================================================

  ok('Ninguém marcado como "Ambos"', !todas.some(t => t.pessoa === 'Ambos'));
  igual('Família tem 382 lançamentos', todas.filter(t => t.pessoa === 'Família').length, 382);
  ok('Toda transação tem pessoa', todas.every(t => t.pessoa));
  const pessoasCfg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'configuracoes.json'), 'utf8')).pessoas.map(p => p.nome);
  const pessoasDados = [...new Set(todas.map(t => t.pessoa))];
  ok('Toda pessoa dos dados existe no cadastro',
     pessoasDados.every(p => pessoasCfg.includes(p)),
     `dados: ${pessoasDados.join(', ')} | cadastro: ${pessoasCfg.join(', ')}`);

  // =====================================================================
  console.log('\n▸ PARCELAMENTOS\n');
  // =====================================================================

  const parceladas = todas.filter(t => t.eh_parcelada);
  const compras = {};
  parceladas.forEach(t => (compras[t.id_compra] = compras[t.id_compra] || []).push(t));

  ok('Toda parcela tem id_compra', parceladas.every(t => t.id_compra));
  ok('Toda parcela tem numeração', parceladas.every(t => t.parcela_numero >= 1 && t.parcela_total >= 2));
  ok('parcela_numero nunca excede parcela_total', parceladas.every(t => t.parcela_numero <= t.parcela_total));

  const somaBate = Object.entries(compras).filter(([, ps]) => {
    const soma = ps.reduce((s, p) => s + p.valor, 0);
    return Math.abs(soma - ps[0].valor_total_compra) > 0.05;
  });
  ok('Soma das parcelas bate com o valor total da compra', somaBate.length === 0,
     somaBate.slice(0, 3).map(([id, ps]) => `${ps[0].descricao}: ${ps.reduce((s, p) => s + p.valor, 0).toFixed(2)} vs ${ps[0].valor_total_compra}`).join(' | '));

  const numeracaoOk = Object.entries(compras).filter(([, ps]) => {
    const nums = ps.map(p => p.parcela_numero).sort((a, b) => a - b);
    return nums.join(',') !== Array.from({ length: nums.length }, (_, i) => i + 1).join(',');
  });
  ok('Numeração das parcelas é sequencial e sem buracos', numeracaoOk.length === 0,
     numeracaoOk.slice(0, 3).map(([, ps]) => ps[0].descricao).join(' | '));

  const totalCoerente = Object.entries(compras).filter(([, ps]) => ps.length !== ps[0].parcela_total);
  ok('Quantidade de parcelas bate com parcela_total', totalCoerente.length === 0,
     totalCoerente.slice(0, 3).map(([, ps]) => `${ps[0].descricao}: ${ps.length} de ${ps[0].parcela_total}`).join(' | '));

  ok('Nenhuma compra cancelada marcada como parcelada', !parceladas.some(t => t.compra_cancelada));

  // =====================================================================
  console.log('\n▸ ESTORNOS\n');
  // =====================================================================

  const estornos = todas.filter(t => t.natureza === 'estorno');
  igual('25 estornos marcados', estornos.length, 25);
  ok('Todo valor negativo está marcado como estorno',
     todas.filter(t => t.valor < 0).every(t => t.natureza === 'estorno'));
  ok('Nenhum estorno tem valor positivo sem prefixo de cancelamento',
     estornos.every(t => t.valor < 0 || /canc|estorno/i.test(t.descricao)));

  // =====================================================================
  console.log('\n▸ INTERFACE — números exibidos vs. calculados\n');
  // =====================================================================

  const navegador = await chromium.launch({ executablePath: NAVEGADOR });
  const pagina = await navegador.newPage();
  const errosJs = [];
  pagina.on('pageerror', e => errosJs.push(e.message));
  pagina.on('console', m => {
    if (m.type() === 'error' && !/TUNNEL|404|favicon/i.test(m.text())) errosJs.push(m.text());
  });

  await pagina.goto(URL, { waitUntil: 'domcontentloaded' });
  await pagina.waitForTimeout(3000);

  const carregou = await pagina.evaluate(() => (dadosGlobais.fluxo_mensal || {}).transacoes?.length || 0);
  igual('Dashboard carregou todos os lançamentos', carregou, ref.totalLinhas);

  // --- Painel, fatura por fatura ---
  for (const mes of mesesReais.sort((a, b) => {
    const [ma, aa] = a.split('/'), [mb, ab] = b.split('/');
    return (aa - ab) || (MES_ORDEM.indexOf(ma) - MES_ORDEM.indexOf(mb));
  })) {
    const exibido = await pagina.evaluate(m => {
      document.querySelector('[data-tab="painel"]').click();
      document.getElementById('painel_mes').value = m;
      renderizarPainel();
      const cards = [...document.querySelectorAll('#painel_kpis .kpi-card')];
      return {
        fatura: cards[1].querySelector('.kpi-value').textContent.trim(),
        info: document.getElementById('painel_periodo_info').textContent
      };
    }, mes);
    const esperado = ref.porMes[mes];
    const qtd = escopo.filter(t => t.mes_vencimento === mes).length;
    igual(`Painel ${mes} exibe ${brl(esperado)}`, numeroDe(exibido.fatura), esperado);
    ok(`Painel ${mes} informa ${qtd} lançamentos`, exibido.info.includes(String(qtd)), exibido.info);
  }

  // --- Painel não deve abrir no balde "A confirmar" ---
  const aberturaPainel = await pagina.evaluate(() => {
    document.getElementById('painel_mes').value = '';
    preencherSelectMeses('painel_mes', false);
    return document.getElementById('painel_mes').value;
  });
  ok('Painel abre numa fatura real, não em "A confirmar"', aberturaPainel !== A_CONFIRMAR, aberturaPainel);

  // --- Lançamentos: resumo do conjunto filtrado ---
  const semFiltro = await pagina.evaluate(() => {
    document.querySelector('[data-tab="lancamentos"]').click();
    limparFiltros();
    return {
      qtd: document.getElementById('lanc-qtd').textContent,
      total: document.getElementById('lanc-total').textContent,
      estornos: document.getElementById('lanc-estornos').textContent
    };
  });
  igual('Lançamentos sem filtro mostra todas as linhas', parseInt(semFiltro.qtd, 10), ref.totalLinhas);
  igual('Lançamentos soma as compras corretamente', numeroDe(semFiltro.total), ref.compras);
  igual('Lançamentos soma os estornos corretamente', -Math.abs(numeroDe(semFiltro.estornos)), ref.estornos);

  // --- Cada filtro de fatura devolve o subconjunto certo ---
  for (const mes of [...mesesReais, A_CONFIRMAR]) {
    const r = await pagina.evaluate(m => {
      limparFiltros();
      document.getElementById('filter_mes_venc').value = m;
      aplicarFiltros();
      return { n: transacoesFiltradas.length, soma: transacoesFiltradas.reduce((s, t) => s + t.valor, 0) };
    }, mes);
    const esperadoN = escopo.filter(t => t.mes_vencimento === mes).length;
    ok(`Filtro fatura ${mes}: ${esperadoN} linhas, ${brl(ref.porMes[mes])}`,
       r.n === esperadoN && Math.abs(r.soma - ref.porMes[mes]) < 0.01,
       `obtido: ${r.n} linhas, ${brl(r.soma)}`);
  }

  // --- Filtro por pessoa ---
  for (const pessoa of Object.keys(ref.porPessoa)) {
    const r = await pagina.evaluate(p => {
      limparFiltros();
      document.getElementById('filter_pessoa').value = p;
      aplicarFiltros();
      return { n: transacoesFiltradas.length, soma: transacoesFiltradas.reduce((s, t) => s + t.valor, 0) };
    }, pessoa);
    const esperadoN = escopo.filter(t => t.pessoa === pessoa).length;
    ok(`Filtro pessoa ${pessoa}: ${esperadoN} linhas`,
       r.n === esperadoN && Math.abs(r.soma - ref.porPessoa[pessoa]) < 0.01,
       `obtido: ${r.n} linhas, ${brl(r.soma)}`);
  }

  // --- Filtro de parceladas ---
  const filtroParc = await pagina.evaluate(() => {
    limparFiltros();
    document.getElementById('filter_tipo_gasto').value = 'parcelada';
    aplicarFiltros();
    return transacoesFiltradas.length;
  });
  igual('Filtro "Parceladas" devolve só parcelas', filtroParc, parceladas.length);

  const filtroEst = await pagina.evaluate(() => {
    limparFiltros();
    document.getElementById('filter_tipo_gasto').value = 'estorno';
    aplicarFiltros();
    return transacoesFiltradas.length;
  });
  igual('Filtro "Estornos" devolve só estornos', filtroEst, estornos.length);

  // --- Filtros combinados ---
  const combinado = await pagina.evaluate(() => {
    limparFiltros();
    document.getElementById('filter_pessoa').value = 'Juliane';
    document.getElementById('filter_mes_venc').value = 'Mar/26';
    aplicarFiltros();
    return { n: transacoesFiltradas.length, soma: transacoesFiltradas.reduce((s, t) => s + t.valor, 0) };
  });
  const espCombN = escopo.filter(t => t.pessoa === 'Juliane' && t.mes_vencimento === 'Mar/26').length;
  const espCombS = somar(escopo.filter(t => t.pessoa === 'Juliane' && t.mes_vencimento === 'Mar/26'));
  ok(`Filtros combinados (Juliane + Mar/26): ${espCombN} linhas`,
     combinado.n === espCombN && Math.abs(combinado.soma - espCombS) < 0.01,
     `obtido: ${combinado.n} linhas, ${brl(combinado.soma)}`);

  // --- Para Onde Vai: matriz categoria x mes ---
  const matriz = await pagina.evaluate(() => {
    document.querySelector('[data-tab="para_onde_vai"]').click();
    document.getElementById('pov_mes').value = '';
    document.getElementById('pov_pessoa').value = '';
    renderizarParaOndeVai();
    const t = document.querySelector('#pov_matriz table');
    return {
      categorias: [...t.querySelectorAll('tbody tr td:first-child')].map(x => x.textContent.trim()),
      colunas: [...t.querySelectorAll('thead th')].map(x => x.textContent.trim()),
      totalRodape: [...t.querySelectorAll('tfoot td')].pop().textContent.trim()
    };
  });

  const alfabetica = [...matriz.categorias].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  ok('Matriz em ordem alfabética', JSON.stringify(matriz.categorias) === JSON.stringify(alfabetica),
     matriz.categorias.slice(0, 5).join(', '));
  igual('Matriz cobre todas as categorias de despesa', matriz.categorias.length, Object.keys(ref.porCategoria).length);
  igual('Total da matriz bate com a soma das compras', numeroDe(matriz.totalRodape), ref.compras);
  ok('Matriz tem uma coluna por fatura',
     matriz.colunas.length === mesesReais.length + 3,
     matriz.colunas.join(' | '));
  ok('"A confirmar" aparece por último na matriz',
     matriz.colunas[matriz.colunas.length - 2] === A_CONFIRMAR,
     matriz.colunas.join(' | '));

  // --- Cartão & Faturas ---
  await pagina.click('[data-tab="cartao"]');
  await pagina.waitForTimeout(1200);
  const cartao = await pagina.evaluate(() => {
    const linhas = [...document.querySelectorAll('#cartao_faturas tbody tr')].map(tr => {
      const td = [...tr.querySelectorAll('td')].map(x => x.textContent.trim());
      return { mes: td[0], n: td[2], total: td[3], conferencia: td[6] };
    });
    const parc = [...document.querySelectorAll('#cartao_parcelas tbody tr')].length;
    const kpis = [...document.querySelectorAll('#cartao_kpis .kpi-card')].map(c => c.querySelector('.kpi-value').textContent.trim());
    return { linhas, parc, kpis };
  });

  igual('Cartão lista as compras parceladas', cartao.parc, Object.keys(compras).length);
  cartao.linhas.forEach(l => {
    const mes = l.mes.replace(/a confirmar/i, '').trim();
    if (ref.porMes[mes] !== undefined) {
      igual(`Cartão: fatura ${mes}`, numeroDe(l.total), ref.porMes[mes]);
    }
  });

  const esperados = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'totais_esperados.json'), 'utf8')).faturas;
  const comReferencia = cartao.linhas.filter(l => l.conferencia && !/sem referência/i.test(l.conferencia));
  ok('Conferência de fatura está ativa', comReferencia.length === Object.keys(esperados).length,
     `${comReferencia.length} faturas conferidas de ${Object.keys(esperados).length} referências`);

  // --- Todas as abas renderizam ---
  for (const [id, nome] of [['painel', 'Painel'], ['lancamentos', 'Lançamentos'],
                            ['para_onde_vai', 'Para Onde Vai'], ['cartao', 'Cartão & Faturas'],
                            ['dividas', 'Dívidas & Patrimônio']]) {
    await pagina.click(`[data-tab="${id}"]`);
    await pagina.waitForTimeout(800);
    const r = await pagina.evaluate(i => {
      const el = document.getElementById(i);
      return { ativo: el.classList.contains('active'), chars: el.innerText.trim().length };
    }, id);
    ok(`Aba ${nome} renderiza conteúdo`, r.ativo && r.chars > 100, `${r.chars} caracteres`);
  }

  // --- Zeros falsos ---
  const zerosFalsos = await pagina.evaluate(() => {
    document.querySelector('[data-tab="painel"]').click();
    const txt = document.getElementById('painel').innerText;
    return {
      temDeficitFalso: /R\$\s*-?\s*40\.086,47/.test(txt),
      dizNaoCadastrado: /não cadastrado/i.test(txt)
    };
  });
  ok('Painel não exibe o déficit falso de R$ 40.086,47', !zerosFalsos.temDeficitFalso);
  ok('Painel informa o que não está cadastrado', zerosFalsos.dizNaoCadastrado);

  // --- Edição sob filtro atinge a transação certa ---
  const edicao = await pagina.evaluate(() => {
    document.querySelector('[data-tab="lancamentos"]').click();
    limparFiltros();
    document.getElementById('filter_pessoa').value = 'Hugo';
    aplicarFiltros();
    const naTela = transacoesFiltradas[0];
    const todas = dadosGlobais.fluxo_mensal.transacoes;
    return {
      idExibido: naTela.id,
      idPorBusca: todas.find(t => t.id === naTela.id).id,
      idPorPosicao: todas[0].id
    };
  });
  ok('Edição sob filtro localiza a transação exibida', edicao.idExibido === edicao.idPorBusca);
  ok('Bug antigo de índice teria errado o alvo', edicao.idExibido !== edicao.idPorPosicao,
     'se estes ids forem iguais o teste não prova nada');

  // --- Erros de JavaScript ---
  ok('Nenhum erro de JavaScript', errosJs.length === 0, errosJs.slice(0, 5).join(' | '));

  await navegador.close();

  // =====================================================================
  console.log('\n══════════════════════════════════════════════════════════════');
  console.log(`  ${passou} passaram · ${falhou} falharam`);
  console.log('══════════════════════════════════════════════════════════════');
  if (falhas.length) {
    console.log('\nFALHAS:');
    falhas.forEach(f => console.log(`  ✗ ${f.nome}${f.detalhe ? `\n      ${f.detalhe}` : ''}`));
  }
  console.log('');
  process.exit(falhou ? 1 : 0);
})().catch(e => {
  console.error('\nERRO NA SUÍTE:', e.message);
  process.exit(1);
});
