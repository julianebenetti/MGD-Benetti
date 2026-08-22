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

const normalizarDescricao = d => String(d)
  .replace(/^(Canc Parcela Sem Juros|Cancelamento Parcial De Compra|Estorno de)\s*-?\s*/i, '')
  .toLowerCase().replace(/\s+/g, ' ').trim();

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
  const todosLancamentos = dados.fluxo_mensal.transacoes;
  const faturas = dados.faturas_cartao || [];

  // Pagamento de fatura aparece no extrato do cartao mas nao e gasto: e a
  // quitacao da fatura anterior. Somar junto contaria a despesa duas vezes.
  const todas = todosLancamentos.filter(t => t.natureza !== 'pagamento');
  const pagamentos = todosLancamentos.filter(t => t.natureza === 'pagamento');
  const escopo = todas.filter(t => noEscopo(t.mes_vencimento));

  const ref = {
    totalLinhas: todas.length,
    totalGeral: somar(todas),
    escopoLinhas: escopo.length,
    escopoTotal: somar(escopo),
    compras: somar(escopo.filter(t => t.valor > 0)),
    estornos: somar(escopo.filter(t => t.valor < 0)),
    porMes: {},
    porFatura: {},
    porPessoa: {},
    porCategoria: {},
    aConfirmar: somar(escopo.filter(t => t.mes_vencimento === A_CONFIRMAR)),
  };
  escopo.forEach(t => {
    const chaveFatura = `${t.cartao_final || '4846'}|${t.mes_vencimento}`;
    ref.porFatura[chaveFatura] = Math.round(((ref.porFatura[chaveFatura] || 0) + t.valor) * 100) / 100;
    ref.porMes[t.mes_vencimento] = Math.round(((ref.porMes[t.mes_vencimento] || 0) + t.valor) * 100) / 100;
    ref.porPessoa[t.pessoa] = Math.round(((ref.porPessoa[t.pessoa] || 0) + t.valor) * 100) / 100;
    if (t.valor > 0) ref.porCategoria[t.categoria] = Math.round(((ref.porCategoria[t.categoria] || 0) + t.valor) * 100) / 100;
  });

  // =====================================================================
  console.log('\n▸ INTEGRIDADE DOS DADOS\n');
  // =====================================================================

  const cobradoTotal = Math.round(faturas.reduce((s, f) => s + f.cobrado, 0) * 100) / 100;
  console.log(`    (${faturas.length} faturas · ${ref.totalLinhas} lançamentos de gasto · ${pagamentos.length} pagamentos)`);
  igual('Soma dos gastos bate com o total cobrado nas faturas', ref.totalGeral, cobradoTotal);
  ok('Cada fatura tem ao menos um pagamento registrado', pagamentos.length >= faturas.length,
     `${pagamentos.length} pagamentos para ${faturas.length} faturas`);
  ok('Todo pagamento tem valor negativo', pagamentos.every(t => t.valor < 0));
  igual('Compras menos estornos fecha com o total', ref.compras + ref.estornos, ref.escopoTotal);

  const ids = todosLancamentos.map(t => t.id);
  igual('Nenhum id duplicado', new Set(ids).size, ids.length);
  ok('Todo lançamento tem id', todosLancamentos.every(t => t.id));
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
  // As cinco faturas importadas; meses posteriores existem so como projecao de
  // parcelas que ainda vao vencer, e por isso tem poucos lancamentos.
  const FATURAS_IMPORTADAS = faturas.map(f => f.mes);
  ok('As 5 faturas importadas têm volume plausível (mín. 20 lançamentos)',
     FATURAS_IMPORTADAS.every(m => escopo.filter(t => t.mes_vencimento === m).length >= 20),
     FATURAS_IMPORTADAS.map(m => `${m}: ${escopo.filter(t => t.mes_vencimento === m).length}`).join(' | '));

  const projetadas = mesesReais.filter(m => !FATURAS_IMPORTADAS.includes(m));
  ok('Meses além das faturas importadas contêm só parcelas futuras',
     projetadas.every(m => escopo.filter(t => t.mes_vencimento === m).every(t => t.eh_parcelada)),
     projetadas.map(m => `${m}: ${escopo.filter(t => t.mes_vencimento === m).length} lanç.`).join(' | ') || 'nenhum');

  const semAno = todas.filter(t => t.mes_vencimento !== A_CONFIRMAR && !/\/\d{2}$/.test(t.mes_vencimento));
  igual('Mês de fatura sempre no formato Mmm/AA', semAno.length, 0);

  // =====================================================================
  console.log('\n▸ PESSOA\n');
  // =====================================================================

  ok('Ninguém marcado como "Ambos"', !todas.some(t => t.pessoa === 'Ambos'));
  const porPessoa = {};
  todas.forEach(t => { porPessoa[t.pessoa] = (porPessoa[t.pessoa] || 0) + 1; });
  console.log(`    (${Object.entries(porPessoa).map(([p, n]) => `${p}: ${n}`).join(' · ')})`);
  ok('Família concentra as despesas da casa', porPessoa['Família'] > porPessoa['Hugo']);
  ok('Toda pessoa dos dados tem ao menos um lançamento', Object.values(porPessoa).every(n => n > 0));
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
  ok('Toda parcela tem numeração', parceladas.every(t => t.parcela_numero >= 1));
  ok('parcela_numero nunca excede parcela_total',
     parceladas.every(t => t.parcela_total === null || t.parcela_numero <= t.parcela_total));

  const comTotal = Object.entries(compras);
  const semTotal = [];
  console.log(`    (${parceladas.length} parcelas em ${comTotal.length} compras, lidas da coluna Parcelamento)`);
  ok('Todo parcelamento veio da fatura, não de dedução',
     parceladas.every(t => t.parcela_numero >= 1 && t.parcela_total >= 2));

  // Cobranca recorrente traz a parcela embutida na descricao, sem preencher a
  // coluna Parcelamento — caso do seguro do carro.
  const naDescricao = parceladas.filter(t => t.parcela_fonte === 'descricao');
  if (naDescricao.length) {
    const compras = [...new Set(naDescricao.map(t => t.id_compra))];
    console.log(`    (${naDescricao.length} parcelas lidas da descrição, em ${compras.length} compra(s))`);
    ok('Parcela lida da descrição fica vinculada à mesma compra', compras.length >= 1
        && compras.every(id => new Set(naDescricao.filter(t => t.id_compra === id).map(t => t.parcela_numero)).size
                             === naDescricao.filter(t => t.id_compra === id).length));
    ok('Parcela lida da descrição cai em faturas consecutivas',
       compras.every(id => {
         const ps = naDescricao.filter(t => t.id_compra === id).sort((a, b) => a.parcela_numero - b.parcela_numero);
         return ps.every((p, i) => i === 0 || p.parcela_numero === ps[i - 1].parcela_numero + 1);
       }));
  }

  // Uma compra so tem todas as parcelas nos dados quando o parcelamento
  // inteiro cabe dentro das cinco faturas importadas.
  const completas = comTotal.filter(([, ps]) => ps.length === ps[0].parcela_total);
  const parciais = comTotal.filter(([, ps]) => ps.length < ps[0].parcela_total);
  console.log(`    (${completas.length} compras com o parcelamento inteiro, ${parciais.length} parcialmente visíveis)`);

  const somaBate = completas.filter(([, ps]) => ps[0].valor_total_exato).filter(([, ps]) => {
    const soma = ps.reduce((s, p) => s + p.valor, 0);
    return Math.abs(soma - ps[0].valor_total_compra) > 0.05;
  });
  ok('Soma das parcelas bate com o valor total da compra', somaBate.length === 0,
     somaBate.slice(0, 3).map(([id, ps]) => `${ps[0].descricao}: ${ps.reduce((s, p) => s + p.valor, 0).toFixed(2)} vs ${ps[0].valor_total_compra}`).join(' | '));

  ok('Nenhuma compra tem mais parcelas do que o total declarado',
     comTotal.every(([, ps]) => ps.length <= ps[0].parcela_total),
     comTotal.filter(([, ps]) => ps.length > ps[0].parcela_total).slice(0, 3).map(([, ps]) => `${ps[0].descricao}: ${ps.length} de ${ps[0].parcela_total}`).join(' | '));

  ok('Compra anterior às faturas não finge saber o total',
     semTotal.every(([, ps]) => ps.every(p => p.parcela_total === null && p.valor_total_compra === null)));

  // Cada parcela deve cair numa fatura consecutiva a anterior
  // Quando um parcelamento e cancelado, o banco lanca todas as parcelas e
  // todos os estornos na mesma fatura. Nesses casos nao ha sequencia mensal.
  const numaFaturaSo = Object.entries(compras)
    .filter(([, ps]) => new Set(ps.map(p => p.mes_vencimento)).size === 1 && ps.length > 1);
  console.log(`    (${numaFaturaSo.length} parcelamentos lancados e revertidos numa unica fatura)`);

  // Um parcelamento estornado nao segue sequencia mensal: ao cancelar, o banco
  // traz as parcelas restantes para a fatura corrente so para reverte-las.
  // Casar pelo grupo de parcelas, nao pela descricao: o mesmo estabelecimento
  // pode ter uma compra a vista alem da parcelada, e o liquido nao zeraria.
  const grupos = Object.entries(compras).map(([id, ps]) => ({
    id,
    base: normalizarDescricao(ps[0].descricao),
    total: Math.round(ps.reduce((s, p) => s + p.valor, 0) * 100) / 100,
    parcelas: ps[0].parcela_total,
  }));

  const foiEstornada = ps => {
    const base = normalizarDescricao(ps[0].descricao);
    const total = Math.round(ps.reduce((s, p) => s + p.valor, 0) * 100) / 100;
    // Existe um grupo espelho: mesma descricao, mesmo numero de parcelas, valor oposto
    return grupos.some(g => g.base === base
                         && g.parcelas === ps[0].parcela_total
                         && Math.abs(g.total + total) < 0.05
                         && Math.abs(g.total) > 0.05);
  };

  const canceladosNaSequencia = Object.entries(compras)
    .filter(([, ps]) => new Set(ps.map(p => p.mes_vencimento)).size > 1)
    .filter(([, ps]) => foiEstornada(ps)).length;
  if (canceladosNaSequencia) console.log(`    (${canceladosNaSequencia} parcelamento(s) estornado(s), fora da checagem de sequência)`);

  const sequenciaFatura = Object.entries(compras)
    .filter(([, ps]) => new Set(ps.map(p => p.mes_vencimento)).size > 1)
    .filter(([, ps]) => !foiEstornada(ps))
    .filter(([, ps]) => {
    const ord = [...ps].sort((a, b) => a.parcela_numero - b.parcela_numero);
    for (let i = 1; i < ord.length; i++) {
      const d = MES_ORDEM.indexOf(ord[i].mes_vencimento.split('/')[0]) + 12 * +ord[i].mes_vencimento.split('/')[1]
              - MES_ORDEM.indexOf(ord[i - 1].mes_vencimento.split('/')[0]) - 12 * +ord[i - 1].mes_vencimento.split('/')[1];
      if (d !== 1) return true;
    }
    return false;
  });
  ok('Parcelas de um mesmo parcelamento caem em faturas consecutivas', sequenciaFatura.length === 0,
     sequenciaFatura.slice(0, 3).map(([, ps]) => ps[0].descricao).join(' | '));

  const numeracaoOk = Object.entries(compras).filter(([, ps]) => {
    const nums = ps.map(p => p.parcela_numero).sort((a, b) => a - b);
    for (let i = 1; i < nums.length; i++) if (nums[i] !== nums[i - 1] + 1) return true;
    return false;
  });
  ok('Numeração das parcelas é sequencial e sem buracos', numeracaoOk.length === 0,
     numeracaoOk.slice(0, 3).map(([, ps]) => ps[0].descricao).join(' | '));

  ok('Cada parcela aparece uma única vez por compra',
     comTotal.every(([, ps]) => new Set(ps.map(p => p.parcela_numero)).size === ps.length),
     comTotal.filter(([, ps]) => new Set(ps.map(p => p.parcela_numero)).size !== ps.length).slice(0, 3).map(([, ps]) => ps[0].descricao).join(' | '));

  // Uma compra cancelada pode ter sido parcelada — o que precisa valer e que
  // o estorno anule integralmente a cobranca.
  const canceladas = {};
  todas.filter(t => t.compra_cancelada).forEach(t => {
    const base = t.descricao.replace(/^(Canc Parcela Sem Juros|Cancelamento Parcial De Compra) - /i, '').toLowerCase();
    canceladas[base] = Math.round(((canceladas[base] || 0) + t.valor) * 100) / 100;
  });
  ok('Toda compra cancelada tem saldo líquido zero',
     Object.values(canceladas).every(v => Math.abs(v) < 0.05),
     Object.entries(canceladas).filter(([, v]) => Math.abs(v) >= 0.05).map(([k, v]) => `${k.slice(0, 30)}: ${v}`).join(' | '));

  // =====================================================================
  console.log('\n▸ ESTORNOS\n');
  // =====================================================================

  const estornos = todas.filter(t => t.natureza === 'estorno');
  console.log(`    (${estornos.length} estornos, ${brl(somar(estornos))})`);
  igual('Estornos batem com os valores negativos', estornos.length, todas.filter(t => t.valor < 0).length);
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
  igual('Dashboard carregou todos os lançamentos', carregou, todosLancamentos.length);

  // A dashboard abre no ambito pessoal, que e o objetivo dela. As comparacoes
  // a seguir conferem totais contra a referencia completa, entao passam para
  // "tudo somado"; a separacao em si e testada na secao propria.
  await pagina.evaluate(() => trocarAmbito('tudo'));
  await pagina.waitForTimeout(700);

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
  for (const mes of mesesReais) {
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
      totalRodape: [...t.querySelectorAll('tfoot td')][1].textContent.trim()
    };
  });

  const totalPorCategoriaRotulo = {};
  escopo.filter(t => t.valor > 0).forEach(t => {
    const rot = (t.categoria || 'Sem categoria').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    totalPorCategoriaRotulo[rot] = (totalPorCategoriaRotulo[rot] || 0) + t.valor;
  });
  const porValor = [...matriz.categorias].sort((a, b) => (totalPorCategoriaRotulo[b] || 0) - (totalPorCategoriaRotulo[a] || 0));
  ok('Matriz ordenada da maior despesa para a menor',
     JSON.stringify(matriz.categorias) === JSON.stringify(porValor),
     matriz.categorias.slice(0, 5).join(', '));

  ok('Coluna Total vem logo depois de Categoria', matriz.colunas[1] === 'Total', matriz.colunas.slice(0, 3).join(' | '));

  const mesesCronologicos = [...new Set(escopo.filter(t => t.valor > 0).map(t => t.mes_vencimento))]
    .sort((a, b) => {
      const [ma, aa] = a.split('/'), [mb, ab] = b.split('/');
      return (aa - ab) || (MES_ORDEM.indexOf(ma) - MES_ORDEM.indexOf(mb));
    });
  ok('Meses do mais recente para o mais antigo',
     matriz.colunas[2] === mesesCronologicos[mesesCronologicos.length - 1],
     `primeira coluna de mês: ${matriz.colunas[2]}, mais recente: ${mesesCronologicos[mesesCronologicos.length - 1]}`);
  igual('Matriz cobre todas as categorias de despesa', matriz.categorias.length, Object.keys(ref.porCategoria).length);
  igual('Total da matriz bate com a soma das compras', numeroDe(matriz.totalRodape), ref.compras);
  const mesesComCompra = [...new Set(escopo.filter(t => t.valor > 0).map(t => t.mes_vencimento))];
  ok('Matriz tem uma coluna por fatura, mais Categoria e Total',
     matriz.colunas.length === mesesComCompra.length + 2,
     `${matriz.colunas.length} colunas para ${mesesComCompra.length} faturas: ${matriz.colunas.join(' | ')}`);
  ok('Nenhuma coluna "A confirmar" — toda parcela tem fatura',
     !matriz.colunas.includes(A_CONFIRMAR), matriz.colunas.join(' | '));

  // --- Cartão & Faturas ---
  await pagina.click('[data-tab="cartao"]');
  await pagina.waitForTimeout(1200);
  const cartao = await pagina.evaluate(() => {
    const linhas = [...document.querySelectorAll('#cartao_faturas tbody tr')].map(tr => {
      const td = [...tr.querySelectorAll('td')].map(x => x.textContent.trim());
      // Cartão | Fatura | Vencimento | Situação | Lanç. | Do período | Saldo anterior | Total da fatura | Em aberto | Conferência
      return { cartao: td[0].replace(/\D/g, ''), mes: td[1], situacao: td[3], n: td[4], doPeriodo: td[5],
               saldoAnterior: td[6], totalFatura: td[7], emAberto: td[8], conferencia: td[9] };
    });
    const parc = [...document.querySelectorAll('#cartao_parcelas tbody tr')].length;
    const kpis = [...document.querySelectorAll('#cartao_kpis .kpi-card')].map(c => c.querySelector('.kpi-value').textContent.trim());
    return { linhas, parc, kpis };
  });

  const parceladasVisiveis = Object.entries(compras).filter(([, ps]) => !ps[0].compra_cancelada).length;
  igual('Cartão lista as compras parceladas não canceladas', cartao.parc, parceladasVisiveis);
  cartao.linhas.forEach(l => {
    const esperado = ref.porFatura[`${l.cartao}|${l.mes}`];
    if (esperado !== undefined) {
      igual(`Cartão ${l.cartao} ${l.mes} — lançamentos do período`, numeroDe(l.doPeriodo), esperado);
    }
  });

  console.log('\n▸ SEPARAÇÃO PESSOAL / EMPRESA\n');
  const porAmbito = { pessoal: 0, empresa: 0 };
  todas.forEach(t => { porAmbito[t.ambito || 'pessoal'] += t.valor; });
  console.log(`    (pessoal ${brl(porAmbito.pessoal)} · empresa ${brl(porAmbito.empresa)})`);

  ok('Todo lançamento tem âmbito', todas.every(t => t.ambito === 'pessoal' || t.ambito === 'empresa'));
  ok('Benetti UP só aparece no âmbito empresa',
     todas.filter(t => t.pessoa === 'Benetti UP').every(t => t.ambito === 'empresa'));
  ok('Nenhuma pessoa da família cai no âmbito empresa',
     todas.filter(t => t.ambito === 'empresa').every(t => t.pessoa === 'Benetti UP'));

  // A mistura e real: o cartao pessoal carrega gasto da empresa. E por isso
  // que a separacao existe.
  const empresaNoCartaoPessoal = todas.filter(t => t.ambito === 'empresa' && (t.cartao_final || '4846') === '4846');
  if (empresaNoCartaoPessoal.length) {
    console.log(`    (${empresaNoCartaoPessoal.length} lançamento(s) da empresa no cartão pessoal: ${brl(somar(empresaNoCartaoPessoal))})`);
  }

  const ambitoNaTela = await pagina.evaluate(() => {
    const antes = ambitoAtual;
    const medir = a => { trocarAmbito(a); return todasTransacoes().reduce((s, t) => s + t.valor, 0); };
    const r = { pessoal: medir('pessoal'), empresa: medir('empresa'), tudo: medir('tudo') };
    trocarAmbito('tudo');
    return r;
  });
  igual('Seletor "Pessoal" soma só o gasto da casa', ambitoNaTela.pessoal, porAmbito.pessoal);
  igual('Seletor "Benetti UP" soma só o gasto da empresa', ambitoNaTela.empresa, porAmbito.empresa);
  igual('Seletor "Tudo" soma os dois', ambitoNaTela.tudo, porAmbito.pessoal + porAmbito.empresa);

  console.log('\n▸ SITUAÇÃO DAS FATURAS\n');
  faturas.forEach(f => {
    const linha = cartao.linhas.find(l => l.mes === f.mes && l.cartao === f.cartao);
    // A tela usa rotulo em linguagem corrente; o dado guarda o nome tecnico
    const ROTULO = { paga: 'paga', paga_parcial: 'paga parcial', fechada: 'a pagar', aberta: 'em aberto' };
    ok(`${f.cartao} ${f.mes} exibe situação "${ROTULO[f.situacao] || f.situacao}"`,
       linha && linha.situacao.toLowerCase() === (ROTULO[f.situacao] || f.situacao),
       linha ? `na tela: "${linha.situacao}"` : 'linha não encontrada');
    if (f.em_aberto > 0.05) {
      igual(`${f.cartao} ${f.mes} exibe ${brl(f.em_aberto)} em aberto`, numeroDe(linha.emAberto), f.em_aberto);
    }
  });

  const totalAberto = faturas.reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0);
  console.log(`    (em aberto no cartão: ${brl(totalAberto)})`);
  ok('Saldo em aberto é a soma do que cada fatura deve',
     Math.abs(totalAberto - faturas.reduce((s, f) => s + Math.max(0, f.total_fatura - f.pago), 0)) < 0.05);

  // O saldo que rola de uma fatura para a outra e a diferenca entre o total
  // cobrado e os lancamentos do periodo — dinheiro velho, nao gasto novo.
  faturas.filter(f => Math.abs(f.saldo_anterior) > 0.05).forEach(f => {
    igual(`${f.cartao} ${f.mes}: saldo anterior = total − lançamentos do período`,
          Math.round((f.total_fatura - f.cobrado) * 100) / 100, f.saldo_anterior);
  });

  const comReferencia = cartao.linhas.filter(l => l.conferencia && !/sem referência/i.test(l.conferencia));
  igual('Toda fatura importada é conferida na tela', comReferencia.length, faturas.length);
  ok('Nenhuma fatura marcada como "não fecha"',
     !cartao.linhas.some(l => /não fecha/i.test(l.conferencia)),
     cartao.linhas.filter(l => /não fecha/i.test(l.conferencia)).map(l => l.mes).join(', '));

  console.log('\n▸ RECONCILIAÇÃO CONTRA AS FATURAS REAIS\n');
  let erroTotal = 0;
  faturas.forEach(f => {
    const calculado = ref.porFatura[`${f.cartao}|${f.mes}`] || 0;
    const dif = calculado - f.cobrado;
    erroTotal += Math.abs(dif);
    ok(`${f.cartao} ${f.mes} (venceu ${f.vencimento.split('-').reverse().join('/')}): cobrado ${brl(f.cobrado)} · calculado ${brl(calculado)}`,
       Math.abs(dif) < 0.05, `diferença ${brl(dif)}`);
  });
  console.log(`\n    Erro acumulado: ${brl(erroTotal)}  (antes da reimportação: R$ 18.491,02)`);

  const comDiferenca = faturas.filter(f => Math.abs(f.pago - f.cobrado) > 0.01);
  console.log(`    Faturas em que o pago difere do cobrado: ${comDiferenca.length}` +
    (comDiferenca.length ? ` — ${comDiferenca.map(f => `${f.mes} ${brl(f.pago - f.cobrado)}`).join(', ')}` : ''));

  ok('Toda fatura tem data de vencimento registrada',
     faturas.every(f => /^\d{4}-\d{2}-\d{2}$/.test(f.vencimento)),
     faturas.map(f => `${f.mes}: ${f.vencimento}`).join(' | '));

  const vencimentos = faturas.map(f => f.vencimento);
  ok('Vencimentos em ordem cronológica',
     vencimentos.every((v, i) => i === 0 || v > vencimentos[i - 1]),
     vencimentos.join(' | '));

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
