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
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'configuracoes.json'), 'utf8'));
  // Cartão com pagamento suspenso: a fatura continua sendo cobrada, mas o valor
  // não sai da conta, então não pode entrar no que a tela diz que ela tem de pagar.
  const cartaoParado = f => (config.cartoes || []).some(c => c.final === f && c.pagamento_suspenso);
  const todosLancamentos = dados.fluxo_mensal.transacoes;
  const faturas = dados.faturas_cartao || [];

  // Duas naturezas aparecem no extrato do cartao mas nao sao gasto: o pagamento,
  // que quita a fatura anterior, e a parcela da fatura renegociada, que quita
  // parceladamente compras ja contadas na epoca. Somar junto cobraria as mesmas
  // compras duas vezes. Tem de casar com NAO_E_CONSUMO no index.html.
  const NAO_E_CONSUMO = ['pagamento', 'divida_parcelada', 'receita', 'ajuste', 'transferencia', 'emprestimo'];
  const todas = todosLancamentos.filter(t => !NAO_E_CONSUMO.includes(t.natureza));
  const pagamentos = todosLancamentos.filter(t => t.natureza === 'pagamento');
  const dividaParcelada = todosLancamentos.filter(t => t.natureza === 'divida_parcelada');
  const escopo = todas.filter(t => noEscopo(t.mes_vencimento));

  // A aba Lançamentos é o razão completo (equivalente a transacoesDoAno no
  // index.html), não o recorte de consumo: mostra também receita, dívida
  // parcelada, transferência etc., para que o clique de "explodir" um valor
  // de Dívidas ou Fluxo de Caixa sempre ache o lançamento correspondente.
  const escopoCompleto = todosLancamentos.filter(t => noEscopo(t.mes_vencimento));

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
  // A reconciliacao contra a fatura soma tambem a parcela da fatura renegociada:
  // a fatura cobra ela, e o 'cobrado' do cabecalho a inclui. Ela sai dos totais
  // de gasto, nao do que o cartao esta cobrando.
  const veioDoCartao = t => (t.origem || '').startsWith('cartao_credito');
  [...escopo, ...dividaParcelada.filter(t => noEscopo(t.mes_vencimento))].filter(veioDoCartao).forEach(t => {
    const chaveFatura = `${t.cartao_final || '4846'}|${t.mes_vencimento}`;
    ref.porFatura[chaveFatura] = Math.round(((ref.porFatura[chaveFatura] || 0) + t.valor) * 100) / 100;
  });
  escopo.forEach(t => {
    ref.porMes[t.mes_vencimento] = Math.round(((ref.porMes[t.mes_vencimento] || 0) + t.valor) * 100) / 100;
    ref.porPessoa[t.pessoa] = Math.round(((ref.porPessoa[t.pessoa] || 0) + t.valor) * 100) / 100;
    if (t.valor > 0) ref.porCategoria[t.categoria] = Math.round(((ref.porCategoria[t.categoria] || 0) + t.valor) * 100) / 100;
  });

  // =====================================================================
  console.log('\n▸ INTEGRIDADE DOS DADOS\n');
  // =====================================================================

  // O cobrado do cabecalho inclui a parcela da fatura renegociada, que sai do
  // total de gasto. Descontar aqui e o que faz as duas contas falarem da mesma
  // coisa: consumo de um lado, consumo do outro.
  //
  // Compara so o que veio de cartao: desconto em folha e gasto, mas nenhuma
  // fatura o cobra, e somar os dois faria a conta nunca fechar.
  const cobradoTotal = Math.round(faturas.reduce((s, f) => s + f.cobrado, 0) * 100) / 100;
  const dividaNoCartao = dividaParcelada.filter(t => noEscopo(t.mes_vencimento) && veioDoCartao(t));
  const dividaTotal = Math.round(somar(dividaNoCartao) * 100) / 100;
  const gastoNoCartao = Math.round(somar(todas.filter(veioDoCartao)) * 100) / 100;
  const foraDoCartao = todas.filter(t => !veioDoCartao(t));
  console.log(`    (${faturas.length} faturas · ${ref.totalLinhas} lançamentos de gasto · ` +
    `${pagamentos.length} pagamentos · ${dividaParcelada.length} de dívida parcelada, ${brl(dividaTotal)})`);
  if (foraDoCartao.length) {
    console.log(`    (${foraDoCartao.length} lançamentos fora do cartão — desconto em folha, ${brl(somar(foraDoCartao))})`);
  }
  igual('Gasto no cartão bate com o cobrado, fora a dívida parcelada',
        gastoNoCartao, Math.round((cobradoTotal - dividaTotal) * 100) / 100);
  ok('Cada fatura tem ao menos um pagamento registrado', pagamentos.length >= faturas.length,
     `${pagamentos.length} pagamentos para ${faturas.length} faturas`);
  ok('Todo pagamento tem valor negativo', pagamentos.every(t => t.valor < 0));
  igual('Compras menos estornos fecha com o total', ref.compras + ref.estornos, ref.escopoTotal);

  // Custo de crédito é despesa financeira, nunca despesa comum. Pagar a fatura a
  // menor financia o saldo, e o que o banco cobra por isso tem de ficar visível
  // como tal — diluído entre as categorias de consumo, some.
  const custoDeCredito = todosLancamentos.filter(t =>
    /juros|encargo|mora|multa|anuidade|^iof|refinanc|rotativ/i.test(t.descricao)
    && !/^canc|^cancelamento|sem juros/i.test(t.descricao)
    && t.natureza !== 'pagamento' && t.natureza !== 'divida_parcelada');
  const foraDaFinanceira = custoDeCredito.filter(t => t.categoria !== 'encargos_financeiros');
  console.log(`    (${custoDeCredito.length} lançamentos de custo financeiro, ${brl(somar(custoDeCredito))})`);
  ok('Todo custo de crédito está em encargos_financeiros', foraDaFinanceira.length === 0,
     [...new Set(foraDaFinanceira.map(t => `${t.descricao.trim().slice(0, 30)} → ${t.categoria}`))].slice(0, 5).join(' | '));

  // O principal que rola não é despesa: são as mesmas compras sendo carregadas.
  // Se algum dia virar lançamento com natureza de despesa, o gasto do mês passa
  // a contar duas vezes a mesma compra.
  const principalComoDespesa = todosLancamentos.filter(t =>
    /^(parc\s+fatura|parcela\s+de\s+refinanciamento|credito\s+por\s+parcelamento)/i.test(t.descricao)
    && t.natureza !== 'divida_parcelada');
  ok('Principal de dívida parcelada nunca entra como despesa', principalComoDespesa.length === 0,
     principalComoDespesa.map(t => `${t.descricao.trim().slice(0, 30)} (${t.natureza})`).join(' | '));

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
  const FATURAS_IMPORTADAS = faturas.map(f => f.mes);

  // Cada fatura tem de trazer exatamente os lancamentos que o proprio cabecalho
  // declara. Um piso generico de volume nao serve para isso: o 4846 passa de
  // cem lancamentos por mes e o 0442 as vezes tem seis, ambos legitimos.
  //
  // O que este teste pega e fatura pela metade ou contada duas vezes — julho,
  // agosto e setembro do 4846 ficaram com cada linha em dobro porque a mesma
  // fatura foi lida duas vezes na mesma importacao.
  // Conta sobre todos os lancamentos, nao sobre 'escopo': o cabecalho declara as
  // linhas da fatura, e a fatura inclui as de pagamento que 'escopo' descarta.
  const contar = f => todosLancamentos
    .filter(t => veioDoCartao(t) && (t.cartao_final || '4846') === f.cartao && t.mes_vencimento === f.mes).length;
  const divergentes = faturas.filter(f => contar(f) !== f.lancamentos);
  ok(`As ${faturas.length} faturas trazem os lançamentos que o cabeçalho declara`,
     divergentes.length === 0,
     divergentes.map(f => `${f.cartao} ${f.mes}: ${contar(f)} gravados x ${f.lancamentos} declarados`).join(' | '));

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

  // Uma parcela por fatura, sempre avancando. Pular um mes com a numeracao
  // inteira nao e erro: quando o vencimento do cartao muda de dia, um ciclo pode
  // nao vencer em mes nenhum — foi o que houve no 3794 entre maio e julho. O que
  // denuncia fatura faltando e buraco na numeracao, e disso cuida o teste
  // seguinte. Aqui so pega o que nao tem explicacao: duas parcelas na mesma
  // fatura, ou uma parcela posterior vencendo antes da anterior.
  const mesOrdinal = t => MES_ORDEM.indexOf(t.mes_vencimento.split('/')[0]) + 12 * +t.mes_vencimento.split('/')[1];
  const saltos = [];
  const sequenciaFatura = Object.entries(compras)
    .filter(([, ps]) => new Set(ps.map(p => p.mes_vencimento)).size > 1)
    .filter(([, ps]) => !foiEstornada(ps))
    .filter(([, ps]) => {
      const ord = [...ps].sort((a, b) => a.parcela_numero - b.parcela_numero);
      let ruim = false;
      for (let i = 1; i < ord.length; i++) {
        const d = mesOrdinal(ord[i]) - mesOrdinal(ord[i - 1]);
        if (d < 1) ruim = true;
        else if (d > 1 && ord[i].parcela_numero === ord[i - 1].parcela_numero + 1) {
          saltos.push(`${ord[i].descricao.trim().slice(0, 24)} ${ord[i - 1].mes_vencimento}→${ord[i].mes_vencimento}`);
        }
      }
      return ruim;
    });
  if (saltos.length) {
    console.log(`    (${saltos.length} parcelamento(s) pulam um mês sem perder parcela — vencimento mudou de dia: ${saltos.slice(0, 3).join(', ')})`);
  }
  ok('Cada parcela cai numa fatura, e sempre adiante da anterior', sequenciaFatura.length === 0,
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

  // --- Painel: contabilidade de caixa ---
  //
  // O Painel deixou de mostrar "gasto do mês" e passou a responder o que entra
  // na conta e o que sai dela. Os testes abaixo recalculam os dois lados
  // direto do JSON, pela mesma definição que a tela usa, e comparam com o que
  // o navegador renderiza — se a regra mudar num lado só, quebra aqui.
  for (const mes of mesesReais.sort((a, b) => {
    const [ma, aa] = a.split('/'), [mb, ab] = b.split('/');
    return (aa - ab) || (MES_ORDEM.indexOf(ma) - MES_ORDEM.indexOf(mb));
  })) {
    const doMes = todosLancamentos.filter(t => t.mes_vencimento === mes);
    const folha = doMes.filter(t => t.origem === 'holerite_elektro');
    const proventos = folha.filter(t => t.natureza === 'receita')
                           .reduce((s, t) => s + t.valor, 0);
    const descontos = folha.filter(t => t.natureza !== 'receita' && t.valor > 0)
      .reduce((s, t) => s + (t.natureza === 'ajuste' && t.tipo === 'entrada' ? -t.valor : t.valor), 0);
    const liquido = proventos - descontos;
    const temFolha = folha.some(t => t.natureza === 'receita');

    const ehPagCartao = t => t.origem === 'extrato_itau' &&
      (/^Cart[\u00e3a]o\s/i.test(t.descricao || '') ||
       /bradescard/i.test((t.descricao || '') + ' ' + (t.descricao_original || '')));
    const saidasFora = doMes.filter(t =>
      t.origem !== 'holerite_elektro' &&
      !(t.origem || '').startsWith('cartao_credito') &&
      !ehPagCartao(t) && t.valor > 0 &&
      (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'))
      .reduce((s, t) => s + t.valor, 0);

    // Saída de cartão = o que de fato passa por esta conta: pagamento de fatura
    // que o extrato registra, mais o que segue em aberto nas faturas do mês.
    // O total faturado inclui cartão pago pela conta PJ da Benetti UP.
    const cartaoPago = doMes.filter(t => t.origem === 'extrato_itau' &&
      t.categoria === 'pagamento_fatura' && t.valor > 0).reduce((s, t) => s + t.valor, 0);
    const cartaoAberto = (dados.faturas_cartao || [])
      .filter(f => f.mes === mes && !cartaoParado(f.cartao))
      .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0);
    const cartao = cartaoPago + cartaoAberto;

    // Conta recorrente que ainda não apareceu no mês entra pela mediana do
    // histórico. Recalculado aqui de forma independente da tela: se a regra
    // mudar de um lado só, o teste acusa.
    const chaveRec = x => String(x || '').toLowerCase().replace(/\d+/g, '')
      .replace(/[^a-zà-ú ]/gi, ' ').replace(/\s+/g, ' ').trim();
    const med = v => { if (!v.length) return 0; const o=[...v].sort((a,b)=>a-b), i=Math.floor(o.length/2);
                       return o.length % 2 ? o[i] : (o[i-1]+o[i])/2; };
    const foraCartao = t => t.origem !== 'holerite_elektro' &&
      !(t.origem || '').startsWith('cartao_credito') && !ehPagCartao(t) && t.valor > 0 &&
      (t.natureza === 'despesa' || t.natureza === 'divida_parcelada');
    const perfil = {};
    todosLancamentos.filter(t => noEscopo(t.mes_vencimento) && foraCartao(t)).forEach(t => {
      const k = chaveRec(t.descricao); if (!k) return;
      (perfil[k] = perfil[k] || { meses: new Set(), valores: [] });
      perfil[k].meses.add(t.mes_vencimento); perfil[k].valores.push(t.valor);
    });
    const jaNoMes = new Set(doMes.filter(foraCartao).map(t => chaveRec(t.descricao)));
    const previsto = Object.entries(perfil)
      .filter(([k, v]) => v.meses.size >= 3 && !jaNoMes.has(k) && med(v.valores) > 0)
      .reduce((s, [, v]) => s + Math.round(med(v.valores) * 100) / 100, 0);

    const visto = await pagina.evaluate(m => {
      document.querySelector('[data-tab="painel"]').click();
      document.getElementById('painel_mes').value = m;
      renderizarPainel();
      const linhas = [...document.querySelectorAll('#painel_fluxo_3numeros .fluxo-item')]
        .map(el => el.innerText);
      return {
        entra: linhas[0] || '',
        sai: linhas[1] || '',
        info: document.getElementById('painel_periodo_info').textContent
      };
    }, mes);

    if (temFolha) {
      igual(`Painel ${mes}: entra na conta = líquido da folha ${brl(liquido)}`,
            numeroDe(visto.entra), liquido);
    } else {
      ok(`Painel ${mes}: sem holerite, diz "não cadastrado" em vez de zero`,
         /não cadastrado/i.test(visto.entra), visto.entra);
    }
    igual(`Painel ${mes}: sai da conta = cartão + boleto/PIX + recorrente prevista ${brl(cartao + saidasFora + previsto)}`,
          numeroDe(visto.sai), cartao + saidasFora + previsto, 0.05);
  }

  // O provento bruto nunca pode ser o número da entrada: ele não chega na
  // conta. Este teste existe porque o Painel já mostrou o bruto por engano,
  // inflando a receita em mais de R$ 3 mil.
  {
    const comFolha = mesesReais.filter(m => todosLancamentos.some(t =>
      t.mes_vencimento === m && t.origem === 'holerite_elektro' && t.natureza === 'receita'));
    let brutoNaTela = 0;
    for (const mes of comFolha) {
      const folha = todosLancamentos.filter(t => t.mes_vencimento === mes && t.origem === 'holerite_elektro');
      const bruto = folha.filter(t => t.natureza === 'receita').reduce((s, t) => s + t.valor, 0);
      const desc = folha.filter(t => t.natureza !== 'receita' && t.valor > 0)
                        .reduce((s, t) => s + (t.natureza === 'ajuste' && t.tipo === 'entrada' ? -t.valor : t.valor), 0);
      if (desc < 0.01) continue; // sem desconto, bruto e liquido coincidem
      const visto = await pagina.evaluate(m => {
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        return document.querySelector('#painel_fluxo_3numeros .fluxo-item').innerText;
      }, mes);
      if (Math.abs(numeroDe(visto) - bruto) < 0.01) brutoNaTela++;
    }
    ok('Painel nunca mostra o provento bruto como entrada', brutoNaTela === 0,
       `${brutoNaTela} mês(es) exibindo o bruto`);
  }

  // Desconto de folha não pode aparecer também como saída de caixa: ele já
  // está abatido no líquido. O consignado descontado na folha é o caso real
  // que fez o Painel cobrar o mesmo dinheiro dos dois lados.
  {
    const mesTeste = mesesReais.find(m => todosLancamentos.some(t =>
      t.mes_vencimento === m && t.origem === 'holerite_elektro' && t.natureza === 'divida_parcelada'));
    if (mesTeste) {
      const consignadoFolha = todosLancamentos.filter(t =>
        t.mes_vencimento === mesTeste && t.origem === 'holerite_elektro' &&
        t.natureza === 'divida_parcelada').reduce((s, t) => s + t.valor, 0);
      const saidaVista = await pagina.evaluate(m => {
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        return [...document.querySelectorAll('#painel_fluxo_3numeros .fluxo-item')][1].innerText;
      }, mesTeste);
      const doMes = todosLancamentos.filter(t => t.mes_vencimento === mesTeste);
      const ehPagCartao = t => t.origem === 'extrato_itau' &&
        (/^Cart[\u00e3a]o\s/i.test(t.descricao || '') ||
         /bradescard/i.test((t.descricao || '') + ' ' + (t.descricao_original || '')));
      const esperado = doMes.filter(t =>
        t.origem !== 'holerite_elektro' && !(t.origem || '').startsWith('cartao_credito') &&
        !ehPagCartao(t) && t.valor > 0 &&
        (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'))
        .reduce((s, t) => s + t.valor, 0) +
        doMes.filter(t => t.origem === 'extrato_itau' && t.categoria === 'pagamento_fatura' && t.valor > 0)
             .reduce((s, t) => s + t.valor, 0) +
        (dados.faturas_cartao || []).filter(f => f.mes === mesTeste && !cartaoParado(f.cartao))
          .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0);
      // Soma tambem a projecao das recorrentes que faltam nesse mes, pela mesma
      // mediana que a tela usa — senao o teste cobraria um numero que a tela
      // nunca mostrou e falharia por outro motivo que nao o consignado.
      const chaveR = x => String(x || '').toLowerCase().replace(/\d+/g, '')
        .replace(/[^a-zà-ú ]/gi, ' ').replace(/\s+/g, ' ').trim();
      const medR = v => { if (!v.length) return 0; const o=[...v].sort((a,b)=>a-b), i=Math.floor(o.length/2);
                          return o.length % 2 ? o[i] : (o[i-1]+o[i])/2; };
      const foraR = t => t.origem !== 'holerite_elektro' &&
        !(t.origem || '').startsWith('cartao_credito') && !ehPagCartao(t) && t.valor > 0 &&
        (t.natureza === 'despesa' || t.natureza === 'divida_parcelada');
      const perfR = {};
      todosLancamentos.filter(t => noEscopo(t.mes_vencimento) && foraR(t)).forEach(t => {
        const k = chaveR(t.descricao); if (!k) return;
        (perfR[k] = perfR[k] || { meses: new Set(), valores: [] });
        perfR[k].meses.add(t.mes_vencimento); perfR[k].valores.push(t.valor);
      });
      const jaR = new Set(doMes.filter(foraR).map(t => chaveR(t.descricao)));
      const previstoR = Object.entries(perfR)
        .filter(([k, v]) => v.meses.size >= 3 && !jaR.has(k) && medR(v.valores) > 0)
        .reduce((s, [, v]) => s + Math.round(medR(v.valores) * 100) / 100, 0);
      ok(`Painel ${mesTeste}: consignado da folha (${brl(consignadoFolha)}) não entra como saída`,
         Math.abs(numeroDe(saidaVista) - (esperado + previstoR)) < 0.05,
         `tela ${brl(numeroDe(saidaVista))} x esperado ${brl(esperado + previstoR)}`);
    }
  }

  // A prova mais forte de que a conta do líquido está certa: ele tem de bater
  // com o valor que o banco de fato creditou. O extrato marca esse crédito como
  // transferência (para não contar duas vezes com o holerite), então os dois
  // números vêm de fontes independentes — folha de um lado, banco do outro.
  {
    const creditos = {};
    todosLancamentos
      .filter(t => t.origem === 'extrato_itau' && /Crédito do salário/i.test(t.descricao || ''))
      .forEach(t => { creditos[t.mes_vencimento] = (creditos[t.mes_vencimento] || 0) + t.valor; });

    let conferidos = 0, divergentes = [];
    for (const [mes, creditado] of Object.entries(creditos)) {
      const folha = todosLancamentos.filter(t => t.mes_vencimento === mes && t.origem === 'holerite_elektro');
      if (!folha.some(t => t.natureza === 'receita')) continue;
      const liquido = folha.filter(t => t.natureza === 'receita').reduce((s, t) => s + t.valor, 0)
                    - folha.filter(t => t.natureza !== 'receita' && t.valor > 0)
                           .reduce((s, t) => s + (t.natureza === 'ajuste' && t.tipo === 'entrada' ? -t.valor : t.valor), 0);
      // PLR e férias chegam em comprovante separado e podem cair num mês de
      // calendário diferente do crédito — esses ficam de fora da conferência
      // exata, mas os meses de salário puro têm de bater ao centavo.
      const temExtra = folha.some(t => ['plr', 'ferias', 'decimo_terceiro'].includes(t.categoria));
      if (temExtra) continue;
      conferidos++;
      if (Math.abs(liquido - creditado) > 0.02) {
        divergentes.push(`${mes}: folha ${brl(liquido)} x banco ${brl(creditado)}`);
      }
    }
    ok(`Líquido da folha bate com o crédito no banco (${conferidos} meses de salário puro)`,
       conferidos > 0 && divergentes.length === 0,
       divergentes.join(' · ') || (conferidos === 0 ? 'nenhum mês comparável' : null));
  }

  // Fatura de cartão com pagamento suspenso não pode entrar no "sai da conta":
  // ela continua sendo cobrada, mas o dinheiro não sai. Contar ela cobraria da
  // Juliane um pagamento que ela decidiu não fazer — exatamente o tipo de
  // número inflado que fez a dashboard perder a confiança dela antes.
  {
    const parados = (config.cartoes || []).filter(c => c.pagamento_suspenso).map(c => c.final);
    if (parados.length) {
      const mesComParado = (dados.faturas_cartao || [])
        .filter(f => parados.includes(f.cartao) && (f.em_aberto || 0) > 0.05)
        .map(f => f.mes)
        .find(m => mesesReais.includes(m));

      if (mesComParado) {
        const suspenso = (dados.faturas_cartao || [])
          .filter(f => f.mes === mesComParado && parados.includes(f.cartao))
          .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0);

        const tela = await pagina.evaluate(m => {
          document.getElementById('painel_mes').value = m;
          renderizarPainel();
          return {
            sai: [...document.querySelectorAll('#painel_fluxo_3numeros .fluxo-item')][1].innerText,
            bloco: document.getElementById('painel_fluxo_3numeros').innerText
          };
        }, mesComParado);

        // A projeção das recorrentes daquele mês, lida do próprio subtítulo do
        // card: aqui o alvo é a fatura parada, não a mediana, que já tem teste
        // próprio recalculando de forma independente.
        const previstoNoMesParado = numeroDe((tela.sai.match(/([\d.]+,\d{2}) de conta recorrente/) || [])[1] || '0');

        // Recalcula o "sai da conta" pelas partes, e confere que a soma bate
        // com a tela SEM o valor parado e não bate COM ele. As duas metades
        // importam: a primeira prova que a conta está certa, a segunda prova
        // que ela erraria se a fatura parada entrasse.
        const doMesP = todosLancamentos.filter(t => t.mes_vencimento === mesComParado);
        const ehPagCartaoP = t => t.origem === 'extrato_itau' &&
          (/^Cart[\u00e3a]o\s/i.test(t.descricao || '') ||
           /bradescard/i.test((t.descricao || '') + ' ' + (t.descricao_original || '')));
        const semParado = doMesP.filter(t => t.origem === 'extrato_itau' &&
            t.categoria === 'pagamento_fatura' && t.valor > 0).reduce((s, t) => s + t.valor, 0)
          + (dados.faturas_cartao || []).filter(f => f.mes === mesComParado && !cartaoParado(f.cartao))
              .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0)
          + doMesP.filter(t => t.origem !== 'holerite_elektro' &&
              !(t.origem || '').startsWith('cartao_credito') && !ehPagCartaoP(t) && t.valor > 0 &&
              (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'))
              .reduce((s, t) => s + t.valor, 0);
        const naTelaP = numeroDe(tela.sai);
        ok(`Painel ${mesComParado}: fatura parada (${brl(suspenso)}) fica fora do "sai da conta"`,
           Math.abs(naTelaP - (semParado + previstoNoMesParado)) < 0.05 &&
           Math.abs(naTelaP - (semParado + previstoNoMesParado + suspenso)) > 0.05,
           `tela ${brl(naTelaP)} · sem o parado ${brl(semParado + previstoNoMesParado)} · com ele ${brl(semParado + previstoNoMesParado + suspenso)}`);
        ok(`Painel ${mesComParado}: o valor parado aparece na tela, não some em silêncio`,
           tela.bloco.includes(brl(suspenso)) && /pagamento parado/i.test(tela.bloco),
           tela.bloco.split('\n').filter(l => /parado/i.test(l)).join(' | ') || '(nada sobre pagamento parado)');
      }
    }
  }

  // O boleto do cartão Amazon no extrato é o pagamento da fatura 0013 — os
  // dois não podem ser somados.
  {
    const dup = todosLancamentos.filter(t => t.origem === 'extrato_itau' &&
      (/^Cart[\u00e3a]o\s/i.test(t.descricao || '') ||
       /bradescard/i.test((t.descricao || '') + ' ' + (t.descricao_original || ''))));
    const casam = dup.filter(t => (dados.faturas_cartao || []).some(f =>
      f.mes === t.mes_vencimento && Math.abs((f.cobrado || 0) - t.valor) < 0.01));
    ok('Boleto de cartão no extrato bate com a fatura correspondente (seria dupla contagem)',
       dup.length === 0 || casam.length === dup.length,
       `${casam.length} de ${dup.length} casam com uma fatura`);
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
  igual('Lançamentos sem filtro mostra todas as linhas', parseInt(semFiltro.qtd, 10), escopoCompleto.length);
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
    const doMes = escopoCompleto.filter(t => t.mes_vencimento === mes);
    const esperadoN = doMes.length;
    const esperadoSoma = somar(doMes);
    ok(`Filtro fatura ${mes}: ${esperadoN} linhas, ${brl(esperadoSoma)}`,
       r.n === esperadoN && Math.abs(r.soma - esperadoSoma) < 0.01,
       `obtido: ${r.n} linhas, ${brl(r.soma)}`);
  }

  // --- Filtro por pessoa ---
  const pessoasCompletas = [...new Set(escopoCompleto.map(t => t.pessoa).filter(Boolean))];
  for (const pessoa of pessoasCompletas) {
    const r = await pagina.evaluate(p => {
      limparFiltros();
      document.getElementById('filter_pessoa').value = p;
      aplicarFiltros();
      return { n: transacoesFiltradas.length, soma: transacoesFiltradas.reduce((s, t) => s + t.valor, 0) };
    }, pessoa);
    const doPessoa = escopoCompleto.filter(t => t.pessoa === pessoa);
    const esperadoN = doPessoa.length;
    ok(`Filtro pessoa ${pessoa}: ${esperadoN} linhas`,
       r.n === esperadoN && Math.abs(r.soma - somar(doPessoa)) < 0.01,
       `obtido: ${r.n} linhas, ${brl(r.soma)}`);
  }

  // --- Filtro de parceladas ---
  // O ledger completo inclui parcela de dívida também (consignado,
  // refinanciamento), que também é eh_parcelada — não só a compra no cartão.
  const parceladasCompletas = escopoCompleto.filter(t => t.eh_parcelada);
  const filtroParc = await pagina.evaluate(() => {
    limparFiltros();
    document.getElementById('filter_tipo_gasto').value = 'parcelada';
    aplicarFiltros();
    return transacoesFiltradas.length;
  });
  igual('Filtro "Parceladas" devolve só parcelas', filtroParc, parceladasCompletas.length);

  const estornosCompletos = escopoCompleto.filter(t => t.natureza === 'estorno');
  const filtroEst = await pagina.evaluate(() => {
    limparFiltros();
    document.getElementById('filter_tipo_gasto').value = 'estorno';
    aplicarFiltros();
    return transacoesFiltradas.length;
  });
  igual('Filtro "Estornos" devolve só estornos', filtroEst, estornosCompletos.length);

  // --- Filtros combinados ---
  const combinado = await pagina.evaluate(() => {
    limparFiltros();
    document.getElementById('filter_pessoa').value = 'Juliane';
    document.getElementById('filter_mes_venc').value = 'Mar/26';
    aplicarFiltros();
    return { n: transacoesFiltradas.length, soma: transacoesFiltradas.reduce((s, t) => s + t.valor, 0) };
  });
  const combRef = escopoCompleto.filter(t => t.pessoa === 'Juliane' && t.mes_vencimento === 'Mar/26');
  const espCombN = combRef.length;
  const espCombS = somar(combRef);
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
  const empresaNoCartaoPessoal = todas.filter(t => t.ambito === 'empresa' && veioDoCartao(t) && (t.cartao_final || '4846') === '4846');
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
  //
  // A fatura do Bradesco lança o pagamento da fatura anterior como linha dentro
  // dela mesma, coisa que a do Itaú não faz. Por isso a identidade geral é
  //   total = saldo anterior + cobrado − pagamentos
  // e não simplesmente total − cobrado: onde não há pagamento embutido,
  // `pagamentos` é zero e as duas formas coincidem.
  faturas.filter(f => Math.abs(f.saldo_anterior) > 0.05 && (f.pagamentos || 0) > 0.05).forEach(f => {
    igual(`${f.cartao} ${f.mes}: total = saldo anterior + cobrado − pagamento embutido`,
          Math.round((f.saldo_anterior + f.cobrado - f.pagamentos) * 100) / 100,
          Math.round(f.total_fatura * 100) / 100);
  });
  faturas.filter(f => Math.abs(f.saldo_anterior) > 0.05 && !((f.pagamentos || 0) > 0.05)).forEach(f => {
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

  // A cronologia so faz sentido dentro de um cartao: sao tres, e a lista vem
  // agrupada por cartao, entao a sequencia reinicia a cada troca.
  const porCartao = {};
  faturas.forEach(f => (porCartao[f.cartao] = porCartao[f.cartao] || []).push(f.vencimento));
  const foraDeOrdem = Object.entries(porCartao)
    .filter(([, vs]) => vs.some((v, i) => i > 0 && v <= vs[i - 1]));
  ok('Vencimentos em ordem cronológica dentro de cada cartão',
     foraDeOrdem.length === 0,
     Object.entries(porCartao).map(([c, vs]) => `${c}: ${vs.join(' ')}`).join('\n      '));

  // --- Todas as abas renderizam ---
  for (const [id, nome] of [['painel', 'Painel'], ['lancamentos', 'Lançamentos'],
                            ['para_onde_vai', 'Para Onde Vai'], ['cartao', 'Cartão & Faturas'],
                            ['dividas', 'Dívidas & Patrimônio'], ['fluxocaixa', 'Fluxo de Caixa'],
                            ['irpf', 'Imposto de Renda']]) {
    await pagina.click(`[data-tab="${id}"]`);
    await pagina.waitForTimeout(800);
    const r = await pagina.evaluate(i => {
      const el = document.getElementById(i);
      return { ativo: el.classList.contains('active'), chars: el.innerText.trim().length };
    }, id);
    ok(`Aba ${nome} renderiza conteúdo`, r.ativo && r.chars > 100, `${r.chars} caracteres`);
  }

  // --- Fluxo de caixa das dívidas ---
  //
  // O risco desta tela e projetar parcela que nao existe: um numero N/M lido do
  // lugar errado inventa um parcelamento, e a projecao vira compromisso
  // imaginario. E o oposto tambem — contrato sem prazo nao pode ganhar uma data
  // de fim inventada.
  await pagina.click('[data-tab="dividas"]');
  await pagina.waitForTimeout(900);
  const dividas = await pagina.evaluate(() => document.getElementById('dividas_conteudo').innerText);

  const parcelasDeDivida = todosLancamentos.filter(t =>
    t.natureza === 'divida_parcelada' && t.valor > 0 && noEscopo(t.mes_vencimento));
  const pagoEmDivida = somar(parcelasDeDivida);
  const naTela = numeroDe((dividas.match(/PAGO EM \d{4}\s*\n\s*(R\$ [\d.,]+)/) || [])[1]);
  igual('Dívidas: pago no ano bate com o calculado do JSON', naTela, pagoEmDivida, 0.02);

  // Contrato marcado `em_pagamento: false` continua na lista — a dívida existe —
  // mas a parcela dele não pode entrar no "Parcelas por mês", que é o número
  // usado pra se programar. Somar as duas coisas prometeria um pagamento que
  // não vai acontecer.
  {
    const todosContratos = dados.dividas || [];
    const suspensos = todosContratos.filter(d => d.em_pagamento === false);
    const emDia = todosContratos.filter(d => d.em_pagamento !== false);
    const esperado = emDia.reduce((s, d) => s + (d.parcela_mensal || 0), 0);

    const kpi = await pagina.evaluate(() => {
      const card = [...document.querySelectorAll('#dividas_conteudo .kpi-card')]
        .find(c => /Parcelas por m/i.test(c.innerText));
      return card ? card.innerText : '';
    });
    igual(`Dívidas: "Parcelas por mês" soma só os ${emDia.length} contratos em dia`,
          numeroDe(kpi.split('\n')[1] || ''), esperado, 0.02);

    if (suspensos.length) {
      const soma = suspensos.reduce((s, d) => s + (d.parcela_mensal || 0), 0);
      ok('Dívidas: o total suspenso aparece na tela, não some em silêncio',
         Math.abs(numeroDe((kpi.match(/R\$\s*[\d.,]+/g) || []).slice(-1)[0] || '') - soma) < 0.02,
         kpi.replace(/\n/g, ' | '));
      ok(`Dívidas: os ${suspensos.length} contratos suspensos continuam listados`,
         suspensos.every(d => dividas.includes(d.nome)),
         suspensos.filter(d => !dividas.includes(d.nome)).map(d => d.nome).join(', '));
      ok('Dívidas: cada contrato suspenso é marcado como tal na tabela',
         (dividas.match(/não está sendo paga/gi) || []).length === suspensos.length,
         `${(dividas.match(/não está sendo paga/gi) || []).length} marcações para ${suspensos.length} contratos`);
    }
  }

  // Uma parcela por mês, por contrato: se um contrato mostrasse duas parcelas no
  // mesmo mês, ou o agrupamento está errado ou há lançamento duplicado.
  const porContratoMes = {};
  parcelasDeDivida.forEach(t => {
    const k = [t.origem, t.rubrica || t.cartao_final || '', t.descricao.trim().replace(/\s+/g, ' '),
               t.parcela_total || '', t.mes_vencimento].join('|');
    porContratoMes[k] = (porContratoMes[k] || 0) + 1;
  });
  const repetidas = Object.entries(porContratoMes).filter(([, n]) => n > 1);
  ok('Nenhum contrato com duas parcelas no mesmo mês', repetidas.length === 0,
     repetidas.slice(0, 3).map(([k, n]) => `${k.split('|')[2]} ${k.split('|')[4]}: ${n}x`).join(' | '));

  // Contrato sem total de parcelas não pode aparecer com projeção.
  const semTotalNaTela = /total de parcelas não cadastrado/.test(dividas);
  const temContratoSemTotal = parcelasDeDivida.some(t => !t.parcela_total);
  ok('Contrato sem prazo é declarado como tal, não projetado',
     temContratoSemTotal === semTotalNaTela,
     `no JSON há contrato sem total: ${temContratoSemTotal} · a tela declara: ${semTotalNaTela}`);

  // --- Fluxo de Caixa (previsto x realizado) ---
  //
  // O risco desta aba e o compromisso do mes futuro sair menor do que o que ja
  // foi de fato lancado nele — pode acontecer quando uma fatura fecha com
  // vencimento adiante (parcela real, nao projetada) e o calculo so soma o que
  // foi projetado, ignorando o que ja existe. Foi um bug real desta sessao.
  // Um passo anterior da suite deixa o ambito em 'tudo'. O fluxo de caixa
  // respeita o ambito em exibicao (ao contrario do IRPF, que e sempre pessoal),
  // entao o teste fixa 'pessoal' para comparar com o que o cálculo abaixo
  // reproduz — sem isso, a comparacao dependeria de ordem de execucao.
  await pagina.evaluate(() => trocarAmbito('pessoal'));
  await pagina.click('[data-tab="fluxocaixa"]');
  await pagina.waitForTimeout(900);
  const fluxo = await pagina.evaluate(() => document.getElementById('fluxocaixa_conteudo').innerText);
  const linhasFluxo = fluxo.split('\n');

  const agora = new Date();
  const hojeOrdinal = agora.getMonth() + 12 * agora.getFullYear();
  const ordinalMes = mv => MES_ORDEM.indexOf(mv.split('/')[0]) + 12 * (2000 + +mv.split('/')[1]);
  const mesesAno = MES_ORDEM.map(m => `${m}/${ANO}`);

  const pessoalNoAno = todosLancamentos.filter(t =>
    (t.ambito || 'pessoal') === 'pessoal' && t.mes_vencimento !== A_CONFIRMAR && noEscopo(t.mes_vencimento));

  const saldoAteAgoraEsperado = Math.round(mesesAno
    .filter(mv => ordinalMes(mv) <= hojeOrdinal)
    .reduce((s, mv) => {
      const ts = pessoalNoAno.filter(t => t.mes_vencimento === mv);
      if (!ts.length) return s;
      // Estorno tambem e consumo (natureza fora de NAO_E_CONSUMO), so que com
      // valor negativo — soma tudo em vez de filtrar so valor>0, senao o
      // estorno nunca abate nada e diverge do Painel, que soma gasto+estorno
      // pelo mesmo criterio (bug real corrigido em dadosFluxoDeCaixa, 29/08).
      return s + somar(ts.filter(t => t.natureza === 'receita'))
                - somar(ts.filter(t => !NAO_E_CONSUMO.includes(t.natureza)));
    }, 0) * 100) / 100;
  const saldoNaTela = numeroDe((fluxo.match(/SALDO ATÉ HOJE\s*\n\s*(R\$ -?[\d.,]+)/) || [])[1]);
  igual('Fluxo de caixa: saldo até hoje bate com o calculado do JSON', saldoNaTela, saldoAteAgoraEsperado, 0.05);

  const subestimou = [];
  const classificacaoErrada = [];
  mesesAno.forEach(mv => {
    const linha = linhasFluxo.find(l => l.trim().startsWith(mv));
    if (!linha) return;

    const esperado = ordinalMes(mv) <= hojeOrdinal ? 'realizado' : 'previsto';
    const situacao = /previsto/i.test(linha) ? 'previsto' : /realizado|sem dado/i.test(linha) ? 'realizado' : null;
    if (situacao && situacao !== esperado) classificacaoErrada.push(mv);

    if (situacao !== 'previsto') return;
    const compromisso = numeroDe((linha.match(/compromisso (R\$ [\d.,]+)/) || [])[1]);
    const ts = pessoalNoAno.filter(t => t.mes_vencimento === mv);
    const lancado = somar(ts.filter(t =>
      (t.natureza === 'divida_parcelada' && t.valor > 0) || (t.natureza === 'despesa' && t.valor > 0 && t.eh_parcelada)));
    if (compromisso < lancado - 0.05) subestimou.push(`${mv}: compromisso ${brl(compromisso)} < já lançado ${brl(lancado)}`);
  });
  ok('Fluxo de caixa classifica cada mês como realizado ou previsto pela data certa',
     classificacaoErrada.length === 0, classificacaoErrada.join(', '));
  ok('Fluxo de caixa: compromisso do mês futuro nunca é menor que o já lançado nele',
     subestimou.length === 0, subestimou.join(' | '));

  // --- Imposto de Renda ---
  //
  // O risco desta aba e mandar a pessoa deduzir o que nao pode. Farmacia esta em
  // saude e papelaria esta em educacao, mas nenhuma das duas deduz: se caissem
  // no total, a declaracao sairia errada. E o ano-base tem de aparecer escrito,
  // porque a declaracao de um ano apura o anterior.
  await pagina.click('[data-tab="irpf"]');
  await pagina.waitForTimeout(900);
  const irpf = await pagina.evaluate(() => document.getElementById('irpf_conteudo').innerText);

  const naoDedutiveis = /farm[áa]cia|drogal|drogasil|drogaria|papelaria/i;
  const blocosDeExclusao = irpf.split('não entram').slice(1).join(' ');
  ok('IRPF separa farmácia e papelaria do que é dedutível',
     naoDedutiveis.test(blocosDeExclusao),
     'as exceções deveriam aparecer no bloco "não entram"');

  ok('IRPF diz o ano-base e o ano da entrega',
     /Ano-base 2026/.test(irpf) && /entregue em 2027/.test(irpf),
     irpf.slice(0, 80));

  const dedutivelNaTela = numeroDe((irpf.match(/DEDUÇÕES QUE APROVEITAM\s*\n\s*(R\$ [\d.,]+)/) || [])[1]);
  const esperadoDedutivel = (() => {
    const regras = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'regras-irpf.json'), 'utf8'));
    const pessoais = todosLancamentos.filter(t => noEscopo(t.mes_vencimento)
      && (t.ambito || 'pessoal') === 'pessoal' && t.valor > 0
      && !['receita', 'pagamento', 'ajuste'].includes(t.natureza));
    let soma = 0;
    const porGrupoPessoa = {};
    pessoais.forEach(t => {
      const r = (regras.classificacao || []).find(x => (x.categorias || []).includes(t.categoria));
      if (!r || !r.dedutivel) return;
      if (r.excecoes_nao_dedutiveis && new RegExp(r.excecoes_nao_dedutiveis.padrao, 'i').test(t.descricao)) return;
      const g = regras.grupos[r.grupo] || {};
      if (g.limite_por_pessoa) {
        const k = `${r.grupo}|${t.pessoa}`;
        porGrupoPessoa[k] = (porGrupoPessoa[k] || 0) + t.valor;
      } else {
        soma += t.valor;
      }
    });
    Object.entries(porGrupoPessoa).forEach(([k, v]) => {
      const teto = regras.grupos[k.split('|')[0]].limite_por_pessoa;
      soma += Math.min(v, teto);
    });
    const config = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'configuracoes.json'), 'utf8'));
    const dependentes = (config.pessoas || []).filter(p => p.dependente_irpf);
    soma += dependentes.length * (regras.limites.dependente || 0);
    return Math.round(soma * 100) / 100;
  })();
  igual('Total dedutível do IRPF bate com o calculado do JSON', dedutivelNaTela, esperadoDedutivel, 0.02);

  // --- Zeros falsos ---
  // O Painel abre no mes vigente por padrao, que pode ter tudo cadastrado —
  // "diz nao cadastrado" so faz sentido testado num mes que de verdade nao
  // tem holerite ainda, senao o teste depende de sorte de qual mes e "hoje".
  const mesSemHolerite = [...new Set(escopoCompleto.map(t => t.mes_vencimento))]
    .find(m => !escopoCompleto.some(t => t.mes_vencimento === m && t.origem === 'holerite_elektro'));
  const zerosFalsos = await pagina.evaluate((mes) => {
    document.querySelector('[data-tab="painel"]').click();
    if (mes) {
      const sel = document.getElementById('painel_mes');
      sel.value = mes;
      sel.dispatchEvent(new Event('change'));
    }
    const txt = document.getElementById('painel').innerText;
    return {
      temDeficitFalso: /R\$\s*-?\s*40\.086,47/.test(txt),
      dizNaoCadastrado: /não cadastrado/i.test(txt)
    };
  }, mesSemHolerite);
  ok('Painel não exibe o déficit falso de R$ 40.086,47', !zerosFalsos.temDeficitFalso);
  ok('Painel informa o que não está cadastrado', zerosFalsos.dizNaoCadastrado,
     `mês testado: ${mesSemHolerite || '(nenhum sem holerite achado)'}`);

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
