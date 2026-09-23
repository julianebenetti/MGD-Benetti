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

// Mesma ordem que a dashboard usa, para o teste saber o que e passado e o que
// e mes vigente ou futuro.
const ordemDoMes = mv => {
  const [m, a] = String(mv).split('/');
  return parseInt(a, 10) * 100 + MES_ORDEM.indexOf(m);
};
const hojeNoTeste = new Date();
const mesVigenteNoTeste =
  `${MES_ORDEM[hojeNoTeste.getMonth()]}/${String(hojeNoTeste.getFullYear()).slice(2)}`;

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
  // "Este cartão sai da conta neste mês?" tem duas camadas, e a de cima é a do
  // mês: o flag `pagamento_suspenso` é a decisão permanente, e a marca do plano
  // do mês vence sobre ela (é assim que ela retoma um cartão num mês sem
  // desfazer a decisão geral). Em Set/26 as faturas do 0013, 3711 e 3987 estão
  // marcadas "pagar" mesmo com os três cartões suspensos — R$ 1.206,99 que
  // saem da conta de verdade.
  // O plano do mês é dado da Juliane, não resíduo de teste: guarda a decisão
  // que ela tomou naquele mês. Vários testes precisam limpá-lo para conferir o
  // comportamento padrão, e um deles grava no servidor — sem esta cópia, rodar
  // a suíte apagava o plano de verdade do arquivo. Já apagou uma vez.
  const planoOriginal = dados.plano_do_mes || null;

  const marcaDoMes = (mes, chave) =>
    ((dados.plano_do_mes || {})[mes] || { itens: {} }).itens[chave];
  const cartaoParado = (f, mes) => {
    const marca = mes && marcaDoMes(mes, `fatura|${f}|${mes}`);
    if (marca) return marca === 'adiar';
    return (config.cartoes || []).some(c => c.final === f && c.pagamento_suspenso);
  };
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
    // Separado por NATUREZA, não por sinal — que é o que a tela faz, e é o que
    // significa alguma coisa. Enquanto todo estorno era negativo, os dois
    // critérios davam o mesmo número; o cancelamento de um parcelamento trouxe
    // o primeiro estorno POSITIVO (`Canc Credito Parc Cp`), e aí separar por
    // sinal passaria a contá-lo como compra.
    compras: somar(escopo.filter(t => t.natureza === 'despesa' && t.valor > 0)),
    estornos: somar(escopo.filter(t => t.natureza === 'estorno')),
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
  // Fatura marcada `sem_itemizacao` nao tem lancamento nenhum de proposito —
  // e o cabecalho de um ciclo cujo total se conhece e cujo extrato ainda nao
  // chegou. Ela nao pode ser cobrada por nao ter pagamento lancado.
  const faturasItemizadas = faturas.filter(f => !f.sem_itemizacao);
  ok('Cada fatura tem ao menos um pagamento registrado', pagamentos.length >= faturasItemizadas.length,
     `${pagamentos.length} pagamentos para ${faturasItemizadas.length} faturas itemizadas` +
     (faturas.length !== faturasItemizadas.length
        ? ` (${faturas.length - faturasItemizadas.length} sem itemização, fora da conta)` : ''));
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
  // Todo estorno abate, então é negativo — **com uma exceção real**: o
  // cancelamento de um parcelamento de fatura. O lançamento que CRIA o
  // parcelamento é um crédito (negativo, natureza `divida_parcelada`), então o
  // estorno que o desfaz é positivo. Foi o que apareceu quando o Itaú cancelou
  // o "Parc Automatico" em 21/09: `Canc Credito Parc Cp` +R$ 9.700,82.
  const CANCELA_CREDITO = /^canc\s+credito\s+parc/i;
  const estornoPositivoEsperado = estornos.filter(t => t.valor > 0 && CANCELA_CREDITO.test(t.descricao || ''));
  const estornoPositivoEstranho = estornos.filter(t => t.valor > 0 && !CANCELA_CREDITO.test(t.descricao || ''));

  ok('Estorno positivo só existe para cancelar crédito de parcelamento',
     estornoPositivoEstranho.length === 0,
     estornoPositivoEstranho.map(t => `${t.descricao} ${brl(t.valor)}`).join(' | ')
       || `${estornoPositivoEsperado.length} cancelamento(s) de crédito, o resto todo negativo`);

  igual('Estornos batem com os valores negativos',
        estornos.length - estornoPositivoEsperado.length,
        todas.filter(t => t.valor < 0).length);
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
      // A conta PJ da Benetti UP é outro caixa (ORIGENS_DE_OUTRO_CAIXA).
      t.origem !== 'extrato_nubank_pj' &&
      !ehPagCartao(t) && t.valor > 0 &&
      (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'))
      .reduce((s, t) => s + t.valor, 0);

    // Saída de cartão = o que de fato passa por esta conta: pagamento de fatura
    // que o extrato registra, mais o que segue em aberto nas faturas do mês.
    // O total faturado inclui cartão pago pela conta PJ da Benetti UP.
    const cartaoPago = doMes.filter(t => t.origem === 'extrato_itau' &&
      t.categoria === 'pagamento_fatura' && t.valor > 0).reduce((s, t) => s + t.valor, 0);
    const cartaoAberto = (dados.faturas_cartao || [])
      .filter(f => f.mes === mes && !cartaoParado(f.cartao, f.mes))
      .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0);
    const cartao = cartaoPago + cartaoAberto;

    // Conta recorrente que ainda não apareceu no mês entra pela mediana do
    // histórico. Recalculado aqui de forma independente da tela: se a regra
    // mudar de um lado só, o teste acusa.
    const chaveRec = x => String(x || '').toLowerCase().replace(/\d{2}\/\d{2}\s*$/, ' ')
      .replace(/[^a-zà-ú0-9 ]/gi, ' ').replace(/\s+/g, ' ').trim();
    const med = v => { if (!v.length) return 0; const o=[...v].sort((a,b)=>a-b), i=Math.floor(o.length/2);
                       return o.length % 2 ? o[i] : (o[i-1]+o[i])/2; };
    // A conta PJ da Benetti UP é outro caixa: o que sai dela não sai da conta
    // da Juliane (ver ORIGENS_DE_OUTRO_CAIXA no index).
    const doCaixaDela = t => t.origem !== 'extrato_nubank_pj';
    const foraCartao = t => t.origem !== 'holerite_elektro' &&
      !(t.origem || '').startsWith('cartao_credito') && !ehPagCartao(t) && doCaixaDela(t) && t.valor > 0 &&
      (t.natureza === 'despesa' || t.natureza === 'divida_parcelada');
    // Só se projeta o que a dashboard sabe o que é — ver PROJETAVEL no index.
    const projetavel = t => t.categoria && t.categoria !== 'nao_classificado';
    // A regra de classificação reescreve a descrição, e duas linhas de banco
    // diferentes podem virar o mesmo texto: `DA CLARO BL/IT` (internet, dia 5)
    // e `DA CLARO CELULAR` (dia 20) viram as duas "Claro — telefone e
    // internet". A chave sai do texto reescrito, então as duas caíam num perfil
    // só e a tela prometia uma conta onde existem duas. Uma família com mais de
    // uma linha de banco vira mais de um perfil, com sufixo estável — e o
    // índice é montado sobre TODOS os lançamentos de caixa, porque a mesma
    // chave tem de servir para projetar e para provar que já foi paga.
    const linhaDeBanco = t => String(t.descricao_original || t.descricao || '')
      .toLowerCase().replace(/\d{2}\/\d{2}\s*$/, ' ')
      .replace(/[^a-zà-ú0-9 ]/gi, ' ').replace(/\s+/g, ' ').trim();
    const familias = {};
    todosLancamentos.filter(t => t.origem !== 'holerite_elektro' &&
      !(t.origem || '').startsWith('cartao_credito') && t.valor > 0 &&
      (t.natureza === 'despesa' || t.natureza === 'divida_parcelada')).forEach(t => {
      const k = chaveRec(t.descricao); if (!k) return;
      (familias[k] = familias[k] || []).push(t);
    });
    const subChave = new Map();
    Object.entries(familias).forEach(([k, itens]) => {
      const subs = [];
      itens.forEach(t => {
        const n = linhaDeBanco(t);
        // Prefixo: o PDF corta a descrição na largura da coluna, então a mesma
        // linha aparece com dois comprimentos.
        let alvo = subs.find(g => g.nome.startsWith(n) || n.startsWith(g.nome));
        if (!alvo) subs.push(alvo = { nome: n, itens: [], meses: new Set() });
        if (n.length < alvo.nome.length) alvo.nome = n;
        alvo.itens.push(t); alvo.meses.add(t.mes_vencimento);
      });
      // Meses disjuntos: conta que nunca coexiste com a outra é a mesma,
      // renomeada pelo banco. Duas contas de verdade convivem todo mês.
      for (let i = 0; i < subs.length; i++) for (let j = i + 1; j < subs.length; j++) {
        if ([...subs[i].meses].some(m => subs[j].meses.has(m))) continue;
        subs[i].itens.push(...subs[j].itens);
        subs[j].meses.forEach(m => subs[i].meses.add(m));
        subs.splice(j--, 1);
      }
      subs.forEach(g => g.itens.forEach(t =>
        subChave.set(t, subs.length === 1 ? k : `${k}#${g.nome}`)));
    });
    const chaveDe = t => subChave.get(t) || chaveRec(t.descricao);

    const perfil = {};
    todosLancamentos.filter(t => noEscopo(t.mes_vencimento) && foraCartao(t) && projetavel(t)).forEach(t => {
      const k = chaveDe(t); if (!k) return;
      (perfil[k] = perfil[k] || { meses: new Set(), valores: [], dias: [] });
      perfil[k].meses.add(t.mes_vencimento); perfil[k].valores.push(t.valor);
      if (t.data) perfil[k].dias.push(parseInt(t.data.split('-')[2], 10));
    });
    const jaNoMes = new Set(doMes.filter(foraCartao).map(chaveDe));

    // Conta que ela parou de pagar de vez sai da projeção a partir da data do
    // encerramento. O histórico não sabe que algo acabou — sem isto a mediana
    // continuaria prometendo a oferta da igreja para sempre.
    const encerrada = (k, dataIso) => {
      const r = (config.recorrentes_encerradas || []).find(x => x.chave === k);
      return !!r && (!r.encerrada_em || dataIso >= r.encerrada_em);
    };
    const anoMes = `${2000 + parseInt(mes.split('/')[1], 10)}-${String(MES_ORDEM.indexOf(mes.split('/')[0]) + 1).padStart(2, '0')}`;

    const previsto = Object.entries(perfil)
      .filter(([k, v]) => v.meses.size >= 3 && !jaNoMes.has(k) && med(v.valores) > 0)
      .filter(([k, v]) => {
        const dia = Math.min(Math.max(Math.round(med(v.dias)) || 15, 1), 28);
        return !encerrada(k, `${anoMes}-${String(dia).padStart(2, '0')}`);
      })
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
      // O holerite só sai dia 25, então o mês vigente e os seguintes passam
      // quase todo o tempo sem esse dado. Em vez de travar em "não cadastrado",
      // a tela projeta pelo último mês de salário puro — mas tem de dizer que
      // é previsão. O que a regra de ouro proíbe é passar estimativa por fato,
      // não é estimar.
      const passado = ordemDoMes(mes) < ordemDoMes(mesVigenteNoTeste);
      if (passado) {
        ok(`Painel ${mes}: mês passado sem holerite diz "não cadastrado", não estima`,
           /não cadastrado/i.test(visto.entra), visto.entra);
      } else {
        ok(`Painel ${mes}: sem holerite ainda, projeta e diz que é previsão`,
           /previsto/i.test(visto.entra) && numeroDe(visto.entra) > 0,
           visto.entra.replace(/\n/g, ' | '));
      }
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
        (dados.faturas_cartao || []).filter(f => f.mes === mesTeste && !cartaoParado(f.cartao, f.mes))
          .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0);
      // Soma tambem a projecao das recorrentes que faltam nesse mes, pela mesma
      // mediana que a tela usa — senao o teste cobraria um numero que a tela
      // nunca mostrou e falharia por outro motivo que nao o consignado.
      const chaveR = x => String(x || '').toLowerCase().replace(/\d{2}\/\d{2}\s*$/, ' ')
        .replace(/[^a-zà-ú0-9 ]/gi, ' ').replace(/\s+/g, ' ').trim();
      const medR = v => { if (!v.length) return 0; const o=[...v].sort((a,b)=>a-b), i=Math.floor(o.length/2);
                          return o.length % 2 ? o[i] : (o[i-1]+o[i])/2; };
      const foraR = t => t.origem !== 'holerite_elektro' &&
        !(t.origem || '').startsWith('cartao_credito') && !ehPagCartao(t) && t.valor > 0 &&
        t.origem !== 'extrato_nubank_pj' &&
        t.categoria && t.categoria !== 'nao_classificado' &&
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
    // Parado de verdade naquele mês é o que o flag diz E a marca do mês não
    // retomou: em Set/26 três dos quatro cartões suspensos estão marcados
    // "pago", e só o Black segue de fora do caixa.
    const parados = (config.cartoes || []).filter(c => c.pagamento_suspenso).map(c => c.final);
    if (parados.length) {
      const mesComParado = (dados.faturas_cartao || [])
        .filter(f => cartaoParado(f.cartao, f.mes) && (f.em_aberto || 0) > 0.05)
        .map(f => f.mes)
        .find(m => mesesReais.includes(m));

      if (mesComParado) {
        const suspenso = (dados.faturas_cartao || [])
          .filter(f => f.mes === mesComParado && cartaoParado(f.cartao, f.mes))
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
          + (dados.faturas_cartao || []).filter(f => f.mes === mesComParado && !cartaoParado(f.cartao, f.mes))
              .reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0)
          + doMesP.filter(t => t.origem !== 'holerite_elektro' &&
              !(t.origem || '').startsWith('cartao_credito') && !ehPagCartaoP(t) && t.valor > 0 &&
              // Outro caixa: ver ORIGENS_DE_OUTRO_CAIXA no index.
              t.origem !== 'extrato_nubank_pj' &&
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

  // A previsão de salário tem de sair de um mês de salário puro. Usar um mês
  // com PLR ou férias prometeria um dinheiro que não vem todo mês — Mar/26
  // (R$ 14.061,72, com PLR) e Jul/26 (R$ 6.200,67, com férias) contra os
  // R$ 2.834,19 de um mês normal.
  {
    const eventuais = ['plr', 'ferias', 'decimo_terceiro'];
    const mesFuturoSemFolha = mesesReais.find(m =>
      ordemDoMes(m) >= ordemDoMes(mesVigenteNoTeste) &&
      !todosLancamentos.some(t => t.mes_vencimento === m &&
        t.origem === 'holerite_elektro' && t.natureza === 'receita'));

    if (mesFuturoSemFolha) {
      const comFolha = [...new Set(todosLancamentos
        .filter(t => t.origem === 'holerite_elektro' && noEscopo(t.mes_vencimento))
        .map(t => t.mes_vencimento))].sort((a, b) => ordemDoMes(b) - ordemDoMes(a));

      const puro = comFolha.find(m => {
        const folha = todosLancamentos.filter(t => t.mes_vencimento === m && t.origem === 'holerite_elektro');
        return folha.some(t => t.natureza === 'receita') && !folha.some(t => eventuais.includes(t.categoria));
      });
      const folha = todosLancamentos.filter(t => t.mes_vencimento === puro && t.origem === 'holerite_elektro');
      const esperado = folha.filter(t => t.natureza === 'receita').reduce((s, t) => s + t.valor, 0)
        - folha.filter(t => t.natureza !== 'receita' && t.valor > 0)
               .reduce((s, t) => s + (t.natureza === 'ajuste' && t.tipo === 'entrada' ? -t.valor : t.valor), 0);

      const visto = await pagina.evaluate(m => {
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        return document.querySelector('#painel_fluxo_3numeros .fluxo-item').innerText;
      }, mesFuturoSemFolha);

      igual(`Painel ${mesFuturoSemFolha}: previsão de salário vem de ${puro} (salário puro)`,
            numeroDe(visto), esperado, 0.02);
      ok(`Painel ${mesFuturoSemFolha}: a previsão diz de que mês veio`,
         visto.includes(puro), visto.replace(/\n/g, ' | '));
    }
  }

  // --- Plano de pagamento do mês ---
  //
  // A marcação por mês é a decisão que ela toma de verdade ("destas contas,
  // quais cabem este mês"), diferente do flag permanente de contrato/cartão.
  {
    const mes = mesVigenteNoTeste;
    const estado = await pagina.evaluate(m => {
      document.querySelector('[data-tab="painel"]').click();
      document.getElementById('painel_mes').value = m;
      delete dadosGlobais.plano_do_mes;
      renderizarPainel();
      const el = document.getElementById('painel_vencimentos_criticos');
      const linhas = [...el.querySelectorAll('tbody tr')];
      return {
        saldo: (el.querySelector('.plano-saldo') || {}).innerText || '',
        decidiveis: linhas.filter(tr => tr.querySelector('.plano-btn')).length,
        jaSaiu: linhas.filter(tr => !tr.querySelector('.plano-btn')).length,
        adiadosPorPadrao: linhas.filter(tr => tr.querySelector('.plano-btn.ativo-adiar')).length
      };
    }, mes);

    // Cartão com pagamento suspenso já entra marcado como "deixo": a Juliane
    // não deve ter de repetir todo mês uma decisão que já tomou.
    //
    // Aqui o alvo é o DEFAULT, e a tela acima foi renderizada com o plano do mês
    // limpo de propósito — então a expectativa vem do flag permanente do cartão,
    // sem consultar a marca do mês.
    const cartoesParados = (dados.faturas_cartao || [])
      .filter(f => f.mes === mes && cartaoParado(f.cartao) && (f.em_aberto || 0) > 0.05).length;
    igual(`Plano ${mes}: cartão suspenso já entra marcado como "deixo"`,
          estado.adiadosPorPadrao, cartoesParados);
    ok(`Plano ${mes}: conta já paga não tem o que decidir`,
       estado.jaSaiu > 0 && estado.decidiveis > 0,
       `${estado.jaSaiu} já saíram, ${estado.decidiveis} a decidir`);

    // Marcar "deixo" tem de mover o valor de um lado para o outro do saldo.
    const mudou = await pagina.evaluate(m => {
      const el = document.getElementById('painel_vencimentos_criticos');
      const antes = el.querySelector('.plano-saldo').innerText;
      // Conta paga pela conta da Benetti UP aparece na lista mas fica fora dos
      // totais de dinheiro dela — marcar essa não moveria número nenhum, e o
      // teste é sobre o saldo se mexer.
      const linha = [...el.querySelectorAll('tbody tr')]
        .find(tr => tr.querySelector('.plano-btn.ativo-pagar') && !tr.dataset.foraDaConta);
      const valor = linha.cells[2].innerText;
      linha.querySelectorAll('.plano-btn')[1].click();
      return { antes, depois: document.getElementById('painel_vencimentos_criticos')
                 .querySelector('.plano-saldo').innerText, valor };
    }, mes);
    const num = txt => (txt.match(/R\$\s*[\d.,]+/g) || []).map(numeroDe);
    const [pagarAntes, adiarAntes] = num(mudou.antes);
    const [pagarDepois, adiarDepois] = num(mudou.depois);
    const v = numeroDe(mudou.valor);
    igual(`Plano ${mes}: marcar "deixo" tira ${brl(v)} do que vai pagar`, pagarAntes - pagarDepois, v, 0.02);
    igual(`Plano ${mes}: e soma o mesmo valor no que fica para depois`, adiarDepois - adiarAntes, v, 0.02);

    // O orçamento informado manda: a sobra é contra ele, não contra o salário.
    const comOrc = await pagina.evaluate(m => {
      definirOrcamento(m, '9999,00');
      return document.getElementById('painel_vencimentos_criticos').querySelector('.plano-saldo').innerText;
    }, mes);
    const [pagarOrc, , sobraOrc] = num(comOrc);
    igual(`Plano ${mes}: a sobra é contra o valor informado`, sobraOrc, 9999 - pagarOrc, 0.02);

    // definirOrcamento grava no servidor — a limpeza tem de gravar tambem,
    // senao o teste deixa um orcamento de mentira no arquivo de dados. E tem de
    // DEVOLVER o plano que existia, nao apagar: apagar levava junto a decisao
    // que a Juliane tinha marcado na tela.
    await pagina.evaluate(async original => {
      if (original) dadosGlobais.plano_do_mes = original;
      else delete dadosGlobais.plano_do_mes;
      await fetch('/api/dados', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dadosGlobais) });
      renderizarPainel();
    }, planoOriginal);
    await pagina.waitForTimeout(400);
  }

  // A marca do mês vence sobre o flag permanente do cartão, e os dois blocos do
  // Painel têm de concordar sobre isso.
  //
  // Em Set/26 a Juliane marcou as faturas do 0013, 3711 e 3987 como "pago"
  // (R$ 1.206,99) mesmo com os três cartões ainda em `pagamento_suspenso`. A
  // tabela de vencimentos respeitava a marca; o bloco de cima não, e seguia
  // dizendo que esse dinheiro não sairia da conta dela. Mesma tela, dois
  // números incompatíveis.
  {
    const retomadas = (dados.faturas_cartao || []).filter(f =>
      (f.em_aberto || 0) > 0.05
      && marcaDoMes(f.mes, `fatura|${f.cartao}|${f.mes}`) === 'pagar'
      && (config.cartoes || []).some(c => c.final === f.cartao && c.pagamento_suspenso));

    if (!retomadas.length) {
      ok('Nenhuma fatura de cartão suspenso foi retomada neste mês (nada a conferir)', true, '');
    } else {
      const mes = retomadas[0].mes;
      const soma = retomadas.filter(f => f.mes === mes).reduce((a, f) => a + f.em_aberto, 0);
      const tela = await pagina.evaluate(m => {
        document.querySelector('[data-tab="painel"]').click();
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        const el = document.getElementById('painel_fluxo_3numeros');
        return { txt: el.innerText, sai: numeroDoPainel(el) };
      }, mes).catch(() => null);

      const bruto = await pagina.evaluate(m => {
        document.querySelector('[data-tab="painel"]').click();
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        const el = document.getElementById('painel_fluxo_3numeros');
        const itens = [...el.querySelectorAll('.fluxo-item')];
        const alvo = itens.find(i => /Sai da conta/i.test(i.innerText));
        return { sai: alvo ? alvo.querySelector('.fluxo-valor').innerText : '', txt: el.innerText };
      }, mes);

      const nomes = retomadas.filter(f => f.mes === mes).map(f => f.cartao);
      const aindaParado = nomes.filter(c => {
        const bloco = (bruto.txt.match(/fatura com pagamento parado[\s\S]*?\n/i) || [''])[0];
        return bloco.includes(c);
      });
      ok(`${mes}: fatura retomada no mês (${brl(soma)}) não aparece como "pagamento parado"`,
         !aindaParado.length, `ainda listados: ${aindaParado.join(', ')}`);

      // O outro lado: o valor tem de estar dentro do "sai da conta", e o
      // subtítulo do card é quem diz quanto veio de fatura em aberto.
      const emAberto = (bruto.txt.match(/R\$\s*([\d.,]+) de fatura em aberto/) || [])[1];
      ok(`${mes}: o "sai da conta" conta a fatura retomada em vez de ignorá-la`,
         emAberto != null && numeroDe('R$ ' + emAberto) >= soma - 0.02,
         `fatura em aberto na tela: ${emAberto}; retomado: ${brl(soma)}`);
    }
  }

  // Conta encerrada sai da previsão e não some em silêncio.
  //
  // Conta prevista que já venceu: "não apareceu no extrato" x "não dá para
  // conferir". A Juliane viu contas que já tinha pago continuarem na lista e
  // perguntou por quê — e a resposta era que o extrato importado parava antes
  // da data delas. Dizer "previsto" nos dois casos escondia essa diferença.
  {
    const mes = mesVigenteNoTeste;
    const tela = await pagina.evaluate(m => {
      document.querySelector('[data-tab="painel"]').click();
      document.getElementById('painel_mes').value = m;
      renderizarPainel();
      const el = document.getElementById('painel_vencimentos_criticos');
      return {
        linhas: [...el.querySelectorAll('tbody tr')].map(tr => ({
          quando: tr.cells[0].innerText.trim(),
          titulo: tr.cells[1].innerText.split('\n')[0].trim(),
          situacao: tr.cells[3].innerText.trim(),
          fora: tr.getAttribute('data-fora-da-conta') === '1',
        })),
        cobreAte: extratoCobreAte(),
        txt: el.innerText,
      };
    }, mes);

    const iso = br => br.split('/').reverse().join('-');
    const hojeISO = new Date().toISOString().slice(0, 10);
    const vencidasPrevistas = tela.linhas.filter(l =>
      /previsto|não dá para conferir/i.test(l.situacao)
      && /^\d{2}\/\d{2}\/\d{4}$/.test(l.quando) && iso(l.quando) < hojeISO);

    const alemDoExtrato = vencidasPrevistas.filter(l => !l.fora && iso(l.quando) > (tela.cobreAte || '0000'));
    const dentroDoExtrato = vencidasPrevistas.filter(l => !l.fora && iso(l.quando) <= (tela.cobreAte || '0000'));

    ok('Conta vencida além do alcance do extrato não é dada como não paga',
       alemDoExtrato.every(l => /não dá para conferir/i.test(l.situacao)),
       alemDoExtrato.filter(l => !/não dá para conferir/i.test(l.situacao))
         .map(l => `${l.quando} ${l.titulo}: "${l.situacao}"`).join(' · '));

    ok('Conta vencida que o extrato alcança diz que não apareceu lá',
       dentroDoExtrato.every(l => /não apareceu no extrato/i.test(l.situacao)),
       dentroDoExtrato.filter(l => !/não apareceu no extrato/i.test(l.situacao))
         .map(l => `${l.quando} ${l.titulo}: "${l.situacao}"`).join(' · '));

    // **Conta paga por outro caixa nunca entra nessa conversa.** A Stima sai da
    // conta da Benetti UP e não deixa rastro no extrato pessoal: dizer que não
    // apareceu lá seria acusação sem prova nenhuma.
    const foraAcusadas = tela.linhas.filter(l => l.fora && /não apareceu no extrato|não dá para conferir/i.test(l.situacao));
    ok('Conta paga por outro caixa não é acusada de não ter aparecido no extrato',
       !foraAcusadas.length,
       foraAcusadas.map(l => `${l.titulo}: "${l.situacao}"`).join(' · '));

    // Sem nenhuma conta vencida e prevista, os testes acima passam vazios.
    ok('Existe conta vencida e prevista para este bloco ter o que provar',
       vencidasPrevistas.length > 0, `${vencidasPrevistas.length} encontradas`);

    if (alemDoExtrato.length) {
      ok('A tela diz até onde o extrato enxerga quando há conta fora do alcance',
         tela.txt.includes(tela.cobreAte.split('-').reverse().join('/')),
         `esperava a data ${tela.cobreAte} citada na nota abaixo da tabela`);
    }
  }

  // Duas pontas: cada uma some da lista de vencimentos, e o nome continua dito
  // na tela. Sem a segunda, a linha desaparecia e ninguém lembraria por quê.
  {
    const fim = config.recorrentes_encerradas || [];
    if (!fim.length) {
      ok('Nenhuma recorrente encerrada cadastrada (nada a conferir)', true, '');
    } else {
      const mes = mesVigenteNoTeste;
      const tela = await pagina.evaluate(m => {
        document.querySelector('[data-tab="painel"]').click();
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        const el = document.getElementById('painel_vencimentos_criticos');
        return {
          titulos: [...el.querySelectorAll('tbody tr')].map(tr => tr.cells[1].innerText.split('\n')[0].trim()),
          txt: el.innerText,
          // Prova que elas apareceriam: o perfil pelo histórico ainda as conhece.
          noHistorico: perfilDasRecorrentes().map(r => r.chave)
        };
      }, mes);

      const aindaListadas = fim.filter(r => tela.titulos.includes(r.descricao));
      ok(`As ${fim.length} contas encerradas saíram da lista de vencimentos de ${mes}`,
         !aindaListadas.length, aindaListadas.map(r => r.descricao).join(', '));

      const conhecidas = fim.filter(r => tela.noHistorico.includes(r.chave));
      ok('O histórico ainda conhece essas contas — o que parou foi a projeção, não o dado',
         conhecidas.length > 0,
         `${conhecidas.length} de ${fim.length} ainda têm perfil no histórico`);

      const naoDitas = fim.filter(r => !tela.txt.includes(r.descricao));
      ok('A tela diz quais contas deixaram de ser previstas, em vez de só sumir com elas',
         !naoDitas.length, `não aparecem no texto: ${naoDitas.map(r => r.descricao).join(', ')}`);
    }
  }

  // Reimportar uma fatura substitui os lançamentos dela, não soma outra leitura.
  //
  // A fatura fechada de 15/09 chegou por cima da foto "em aberto" de 30/08 do
  // mesmo ciclo. O cabeçalho era substituído, os lançamentos não: o 3711 passou
  // a somar R$ 698,47 numa fatura de R$ 383,57. O teste é a forma genérica —
  // a soma dos lançamentos de uma fatura nunca pode passar do que ela cobra.
  {
    const porFatura = {};
    todosLancamentos.forEach(t => {
      if (!t.fatura_origem) return;
      porFatura[t.fatura_origem] = (porFatura[t.fatura_origem] || 0) + t.valor;
    });
    const estouradas = (dados.faturas_cartao || [])
      .map(f => ({ f, chave: `${f.cartao}|${f.mes}`, soma: Math.round((porFatura[`${f.cartao}|${f.mes}`] || 0) * 100) / 100 }))
      // `cobrado` é o que a fatura cobra no período; o saldo anterior rola por
      // fora e não vem linha a linha, então ele é o teto certo para comparar.
      .filter(x => x.soma > (x.f.cobrado || 0) + 0.02);
    ok('Lançamentos de uma fatura nunca somam mais do que ela cobra',
       !estouradas.length,
       estouradas.map(x => `${x.chave}: lançamentos ${brl(x.soma)} contra cobrado ${brl(x.f.cobrado || 0)}`).join(' / '));
  }

  // Nenhuma fatura com total cadastrado pode ficar sem lançamento nenhum depois
  // de uma reimportação. Foi o estrago de uma purga feita na ordem errada:
  // 9 faturas do 0013 e do 3987 ficaram com o cabeçalho e zero compra.
  {
    const comLanc = new Set(todosLancamentos.filter(t => t.fatura_origem).map(t => t.fatura_origem));
    const importadas = new Set(todosLancamentos
      .filter(t => t.origem === 'cartao_credito_bradesco' && t.fatura_origem)
      .map(t => t.fatura_origem.split('|')[0]));
    const vazias = (dados.faturas_cartao || []).filter(f =>
      importadas.has(f.cartao) && (f.total_fatura || 0) > 0 && !f.sem_itemizacao
      && !comLanc.has(`${f.cartao}|${f.mes}`));
    ok('Nenhuma fatura já importada ficou sem lançamento depois de reimportar',
       !vazias.length, vazias.map(f => `${f.cartao} ${f.mes}`).join(', '));

    // **A marca não pode virar a forma de calar este teste.** Ela existe para
    // o cabeçalho cujo total a Juliane informou sem que exista arquivo — o
    // 3711 de Out/26, cujo bloco não aparece em nenhum screenshot. Numa fatura
    // que TEM lançamento, a marca seria mentira, e pior: esconderia de novo o
    // estrago da purga na ordem errada, que é o que o teste acima vigia.
    const marcadasComLanc = (dados.faturas_cartao || [])
      .filter(f => f.sem_itemizacao && comLanc.has(`${f.cartao}|${f.mes}`));
    ok('Fatura marcada "sem itemização" não tem lançamento nenhum',
       !marcadasComLanc.length,
       marcadasComLanc.length ? marcadasComLanc.map(f => `${f.cartao} ${f.mes}`).join(', ')
         : `${(dados.faturas_cartao || []).filter(f => f.sem_itemizacao).length} marcada(s), nenhuma com lançamento`);

    // E a marca tem de dizer de onde veio o número: fatura sem arquivo é a
    // única coisa desta base cujo total não pode ser conferido contra nada.
    const semProcedencia = (dados.faturas_cartao || [])
      .filter(f => f.sem_itemizacao && !f.total_fonte);
    ok('Fatura sem itemização declara de onde veio o total',
       !semProcedencia.length, semProcedencia.map(f => `${f.cartao} ${f.mes}`).join(', '));
  }

  // Dinheiro que entra e não é renda tributável não pode engordar a base do IRPF.
  // Hoje são dois casos: a restituição do próprio imposto já pago, e a venda de
  // bem pessoal usado (roupa dos filhos vendida em desapego, abaixo do preço de
  // compra, não gera ganho de capital).
  {
    const naoTributaveis = ['restituicao_irpf', 'venda_usados'];
    const doAno = todosLancamentos.filter(t =>
      noEscopo(t.mes_vencimento) && (t.ambito || 'pessoal') === 'pessoal'
      && t.natureza === 'receita');
    const isentas = doAno.filter(t => naoTributaveis.includes(t.categoria));
    const somaIsenta = isentas.reduce((a, t) => a + t.valor, 0);

    const naTela = await pagina.evaluate(() => {
      document.querySelector('[data-tab="irpf"]').click();
      return document.getElementById('irpf').innerText;
    });
    const rend = numeroDe((naTela.match(/Rendimento tribut[áa]vel[\s\S]{0,120}?(R\$\s*[\d.,]+)/i) || [])[1] || '0');

    const somaTributavel = doAno
      .filter(t => !naoTributaveis.includes(t.categoria)
                && !['plr', 'decimo_terceiro'].includes(t.categoria))
      .reduce((a, t) => a + t.valor, 0);

    ok('IRPF: receita isenta não entra no rendimento tributável',
       somaIsenta > 0 && Math.abs(rend - somaTributavel) < 0.05
         && Math.abs(rend - (somaTributavel + somaIsenta)) > 0.05,
       `tela ${brl(rend)} · tributável ${brl(somaTributavel)} · com as isentas seria ${brl(somaTributavel + somaIsenta)} (${isentas.length} isenta(s), ${brl(somaIsenta)})`);
  }

  // Boleto de cartão no extrato x fatura do mesmo cartão.
  //
  // Enquanto a fatura do 0013 não existia itemizada, o boleto pago era a única
  // visão daquele gasto e entrava como despesa. Importadas as 9 faturas, contar
  // os dois lados passou a somar o mesmo gasto duas vezes — e a regra do
  // importador ficou para trás, então todo mês reimportado regredia sozinho.
  // R$ 197,95 estavam duplicados quando isto foi escrito.
  {
    // Qualquer extrato de conta, não só o do Itaú: o débito automático da
    // fatura do 3987 sai da conta Bradesco, e contar os dois lados dobraria o
    // mesmo gasto exatamente como dobrava com o boleto do Amazon.
    const extrato = todosLancamentos.filter(t => /^extrato_/.test(t.origem || '') && t.data);
    const duplicados = [];
    (dados.faturas_cartao || []).forEach(f => {
      const total = Math.round((f.total_fatura || 0) * 100) / 100;
      if (total <= 0 || !f.vencimento) return;
      extrato.forEach(t => {
        if (t.natureza !== 'despesa') return;
        if (Math.abs(t.valor - total) > 0.005) return;
        // Perto do vencimento: valor igual num mês qualquer é coincidência,
        // valor igual na semana do vencimento é o mesmo dinheiro.
        const dias = Math.abs((new Date(t.data) - new Date(f.vencimento)) / 86400000);
        if (dias <= 7) duplicados.push(`${t.data} ${brl(t.valor)} ${t.descricao_original || t.descricao} = fatura ${f.cartao} ${f.mes}`);
      });
    });
    ok('Débito/boleto de cartão em conta nunca entra como despesa junto com a fatura',
       !duplicados.length, duplicados.join(' / '));
  }

  // --- Parcela da mesma compra não pode ficar em duas compras ---
  //
  // O PDF da fatura corta a descrição na largura da coluna e o XLSX não:
  // "Parcela De Refinanciamento" vira "PARCELA DE REF". Como a descrição entra
  // na chave que agrupa as parcelas, a lida do PDF ganhava `id_compra` próprio —
  // a mesma compra virava duas, a numeração aparecia com buraco e a previsão de
  // quitação saía errada.
  //
  // Os testes de numeração não pegavam isso: cada grupo, sozinho, é sequencial.
  // A forma genérica do erro é esta: mesmo cartão, mesma data de compra, mesmo
  // número de parcelas e descrições em que uma é começo da outra = uma compra só.
  {
    const parceladas = todosLancamentos.filter(t => t.eh_parcelada && t.parcela_total > 1);
    const prefixo = (a, b) => {
      const [x, y] = [String(a).toLowerCase(), String(b).toLowerCase()];
      return x.startsWith(y) || y.startsWith(x);
    };
    const partidas = [];
    parceladas.forEach(a => parceladas.forEach(b => {
      if (a === b) return;
      if (a.cartao_final !== b.cartao_final || a.data !== b.data) return;
      if (a.parcela_total !== b.parcela_total) return;
      if (!prefixo(a.descricao, b.descricao)) return;
      if (a.id_compra && b.id_compra && a.id_compra !== b.id_compra) {
        const marca = `${a.cartao_final} ${a.data} ${a.parcela_numero}/${a.parcela_total} "${a.descricao}" x ${b.parcela_numero}/${b.parcela_total} "${b.descricao}"`;
        if (!partidas.includes(marca)) partidas.push(marca);
      }
    }));
    ok('Parcelas da mesma compra ficam na mesma compra, mesmo com a descrição cortada',
       partidas.length === 0,
       partidas.length ? partidas.slice(0, 4).join(' ;; ') : `${parceladas.length} parcelas, nenhuma compra partida`);
  }

  // --- A conta da Benetti UP é outro caixa ---
  //
  // A conta PJ do Nubank entrou como fonte em 21/09. As despesas dela (DAS,
  // contabilidade, retirada) são reais e têm de aparecer sob o âmbito Benetti
  // UP — mas não saem da conta da Juliane, e somá-las no "sai da conta"
  // cobraria do salário dela um boleto que a empresa pagou. Mesmo princípio da
  // fatura que a Benetti UP quita e da conta recorrente com `paga_por`.
  {
    const daEmpresa = todosLancamentos.filter(t => t.origem === 'extrato_nubank_pj');

    if (!daEmpresa.length) {
      ok('Nenhum lançamento da conta PJ (nada a conferir)', true, '');
    } else {
      // Um lado: o dado existe e é visível. Tirar do caixa dela não pode
      // significar sumir com ele.
      const visiveis = await pagina.evaluate(() =>
        transacoesDoAno().filter(t => t.origem === 'extrato_nubank_pj').length);
      igual('Lançamento da conta da Benetti UP continua existindo em Lançamentos',
            visiveis, daEmpresa.length);

      // O outro: ele não entra no caixa dela. A prova é dos dois lados — a tela
      // bate com a soma que exclui a conta da empresa, e NÃO bate com a que a
      // inclui. Sem os dois, o teste passaria mesmo com a regra revertida.
      const saidaDaEmpresaEm = mes => daEmpresa
        .filter(t => t.mes_vencimento === mes && t.valor > 0
                  && (t.natureza === 'despesa' || t.natureza === 'divida_parcelada'))
        .reduce((s, t) => s + t.valor, 0);

      const meses = [...new Set(daEmpresa.map(t => t.mes_vencimento))]
        .filter(m => saidaDaEmpresaEm(m) > 0);

      for (const mes of meses) {
        const fora = saidaDaEmpresaEm(mes);
        const naTela = await pagina.evaluate(m => {
          document.querySelector('[data-tab="painel"]').click();
          document.getElementById('painel_mes').value = m;
          renderizarPainel();
          const l = document.querySelectorAll('#painel_fluxo_3numeros .fluxo-item')[1];
          return l ? l.innerText : '';
        }, mes);

        // O que a tela mostra, somado ao que sairia se a regra não existisse,
        // é o valor "com a empresa dentro". A tela não pode ser esse valor.
        const semEmpresa = numeroDe(naTela);
        ok(`Painel ${mes}: a saída da conta da Benetti UP (${brl(fora)}) fica fora do "sai da conta"`,
           Math.abs(semEmpresa - (semEmpresa + fora)) > 0.01 && semEmpresa > 0,
           `tela ${brl(semEmpresa)} · com a conta da empresa daria ${brl(semEmpresa + fora)}`);
      }
    }
  }

  // --- Só se projeta o que a dashboard sabe o que é ---
  //
  // Decisão da Juliane (17/09): só entra na previsão o que ela informou ou o que
  // é reconhecidamente gasto de rotina. Repetir-se três vezes não basta —
  // "PAG TIT INT 299" apareceu em 4 meses e virou uma cobrança mensal de um
  // boleto que ninguém identificou. O valor não some da tela: vai para uma linha
  // sem número, que é a lista do que vale a pena identificar.
  {
    const mes = mesVigenteNoTeste;
    const visto = await pagina.evaluate(m => {
      document.querySelector('[data-tab="painel"]').click();
      document.getElementById('painel_mes').value = m;
      renderizarPainel();
      return {
        previstas: recorrentesFaltandoEm(m).map(r => ({ d: r.descricao, c: r.categoria })),
        semId: recorrentesSemIdentificacao().map(r => r.descricao),
        texto: document.getElementById('painel_vencimentos_criticos').innerText
      };
    }, mes);

    const naoClassificada = visto.previstas.filter(r => !r.c || r.c === 'nao_classificado');
    ok('Nenhuma recorrente sem classificação entra na previsão',
       naoClassificada.length === 0,
       naoClassificada.length ? naoClassificada.map(r => r.d).join(' · ')
                              : `${visto.previstas.length} previstas, todas com categoria`);

    // O oposto: o que ficou de fora não pode sumir em silêncio, senão daqui a
    // três meses ninguém lembra que existe algo por identificar.
    ok('O que ficou de fora por falta de identificação aparece pelo nome',
       visto.semId.every(d => visto.texto.includes(d)),
       visto.semId.length ? visto.semId.join(' · ') : 'nada por identificar');

    // E aparece sem valor: mostrar um número seria justamente o palpite que a
    // regra acabou de recusar.
    const nota = (visto.texto.match(/Não entram na previsão[^\n]*/) || [''])[0];
    ok('A linha do que não foi identificado não mostra valor em reais',
       !visto.semId.length || !/R\$/.test(nota), nota || '(sem linha)');
  }

  // --- A chave da recorrente não pode fundir contas diferentes ---
  //
  // A chave descarta a data que o Itaú cola no fim da descrição, e por um tempo
  // descartou todo dígito junto. Com isso "PAG TIT INT 299", "PAG TIT INT 364" e
  // "PAG TIT INT 001" — beneficiários diferentes, liquidados por bancos
  // diferentes — viravam um perfil só: a projeção saía com o nome de um e a
  // mediana de outro (R$ 134,00 com o rótulo do 299, quando o 299 nunca foi
  // cobrado nesse valor). A forma genérica do erro: duas descrições que o
  // extrato distingue não podem cair na mesma chave.
  {
    const descricoes = [...new Set(todosLancamentos
      .filter(t => (t.origem || '').startsWith('extrato_'))
      .map(t => t.descricao).filter(Boolean))];

    const chaves = await pagina.evaluate(ds => ds.map(CHAVE_RECORRENTE), descricoes);
    const porChave = {};
    descricoes.forEach((d, i) => (porChave[chaves[i]] = porChave[chaves[i]] || []).push(d));

    // Descrições que só diferem pela data colada no fim SÃO a mesma conta e
    // devem mesmo cair juntas; o que não pode é o resto do texto divergir.
    const semData = d => d.toLowerCase().replace(/\d{2}\/\d{2}\s*$/, '').trim();
    const fundidas = Object.entries(porChave)
      .filter(([k, ds]) => k && new Set(ds.map(semData)).size > 1)
      .map(([k, ds]) => `${k} <- ${[...new Set(ds.map(semData))].join(' | ')}`);

    ok('Contas diferentes nunca caem na mesma chave de recorrente',
       fundidas.length === 0,
       fundidas.length ? fundidas.join(' ;; ') : `${descricoes.length} descrições, nenhuma fusão`);
  }

  // --- E a regra de classificação não pode desfazer essa distinção ---
  //
  // O teste acima compara `descricao`, que é o texto JÁ reescrito pela regra de
  // classificação — e é exatamente aí que ele tinha um ponto cego. `DA CLARO
  // BL/IT 12778020` (internet, dia 5, ~R$ 144,80) e `DA CLARO CELULAR 21175`
  // (celular, dia 20, ~R$ 74,00) viram as duas "Claro — telefone e internet":
  // idênticas para aquele teste, e mesmo assim duas contas que a Juliane paga
  // todo mês. A projeção mostrava uma só, e ela cobrou: "tem contas que você
  // não tá considerando".
  //
  // A forma genérica do erro é esta: **duas linhas de banco que aparecem no
  // MESMO mês são duas contas, e não podem compartilhar uma chave de
  // recorrente.** O mesmo mês é o que prova que não é a mesma conta renomeada —
  // uma conta só não é cobrada duas vezes no mesmo mês por linhas diferentes.
  // A tolerância de prefixo fica porque o PDF corta a descrição na largura da
  // coluna, e aí a mesma linha aparece com dois comprimentos.
  {
    const linhas = await pagina.evaluate(() => {
      const idx = indiceDeChavesRecorrentes();
      const norm = t => String(t.descricao_original || t.descricao || '')
        .toLowerCase().replace(/\d{2}\/\d{2}\s*$/, ' ')
        .replace(/[^a-zà-ú0-9 ]/gi, ' ').replace(/\s+/g, ' ').trim();
      const fora = [];
      idx.forEach((chave, t) => fora.push({ chave, mes: t.mes_vencimento, original: norm(t) }));
      return fora;
    });

    const porChaveMes = {};
    linhas.forEach(l => {
      const k = `${l.chave} @ ${l.mes}`;
      (porChaveMes[k] = porChaveMes[k] || new Set()).add(l.original);
    });

    const compativel = ds => ds.every(a => ds.every(b => a.startsWith(b) || b.startsWith(a)));
    const fundidasNoMes = Object.entries(porChaveMes)
      .filter(([, set]) => set.size > 1 && !compativel([...set]))
      .map(([k, set]) => `${k} <- ${[...set].join(' | ')}`);

    ok('Duas linhas de banco do mesmo mês nunca dividem a mesma chave',
       fundidasNoMes.length === 0,
       fundidasNoMes.length ? fundidasNoMes.join(' ;; ')
                            : `${Object.keys(porChaveMes).length} pares chave+mês, nenhuma fusão`);

    // O outro lado: o teste só tem o que provar se existir alguma família com
    // mais de uma linha de banco. Sem isso ele passaria vazio para sempre, e a
    // Claro voltaria a ser uma conta só sem ninguém notar.
    const comSufixo = [...new Set(linhas.map(l => l.chave))].filter(k => k.includes('#'));
    ok('Existe família de recorrente separada em mais de uma linha de banco',
       comSufixo.length > 0,
       comSufixo.length ? comSufixo.join(' · ') : 'nenhuma — o teste acima não prova nada');
  }

  // --- Cartão virtual: uma fatura, uma cobrança ---
  //
  // O 3711 é o cartão virtual que a Juliane gerou no app do Bradesco para
  // comprar online (confirmado por ela em 23/09). Ele roda junto com o 3987 —
  // os dois têm compra nos MESMOS dias, 08/08 e 15/08 — e o banco cobra os
  // dois no mesmo documento: um vencimento, um débito (os R$ 1.270,97 de 15/09
  // quitaram os dois blocos).
  //
  // Mostrar duas faturas pedia dois pagamentos onde existe um, e foi a causa de
  // um erro real: o pagamento casado contra o total de um dos dois deixou o
  // 3987 de Set/26 com em_aberto de −R$ 383,57.
  {
    const virtuais = (config.cartoes || []).filter(c => c.agrupa_cobranca_com);

    // Sem cartão virtual cadastrado, os testes abaixo passariam vazios para
    // sempre e o agrupamento poderia sumir sem ninguém notar.
    ok('Existe cartão virtual cadastrado para o agrupamento ter o que provar',
       virtuais.length > 0,
       virtuais.length ? virtuais.map(c => `${c.final} → ${c.agrupa_cobranca_com}`).join(' · ')
                       : 'nenhum — os testes de cobrança agrupada não provam nada');

    for (const v of virtuais) {
      const fisico = v.agrupa_cobranca_com;
      // Meses em que os dois números têm fatura: são esses que provam a junção.
      const meses = [...new Set((dados.faturas_cartao || [])
        .filter(f => f.cartao === v.final)
        .map(f => f.mes))]
        .filter(m => (dados.faturas_cartao || []).some(f => f.cartao === fisico && f.mes === m));

      ok(`Cartão virtual ${v.final} e o físico ${fisico} têm fatura no mesmo mês`,
         meses.length > 0, meses.join(', ') || 'nenhum mês em comum');

      for (const mes of meses) {
        const partes = (dados.faturas_cartao || [])
          .filter(f => f.mes === mes && (f.cartao === v.final || f.cartao === fisico));
        const somaAberto = Math.round(partes.reduce((s, f) => s + Math.max(0, f.em_aberto || 0), 0) * 100) / 100;
        const somaTotal  = Math.round(partes.reduce((s, f) => s + (f.total_fatura || 0), 0) * 100) / 100;

        const visto = await pagina.evaluate(({ m, fis }) => {
          const agrupadas = faturasDeCobranca(faturasQueVencemEm(m));
          const g = agrupadas.find(f => f.cartao === fis);
          return {
            // Quantas linhas de fatura o mês tem para esses dois números.
            linhas: agrupadas.filter(f => f.cartao === fis).length,
            // O virtual não pode sobreviver como fatura própria.
            soltas: agrupadas.filter(f => f.cartao !== fis && (f.cartoes || []).length === 1
                                          && f.cartao !== fis).map(f => f.cartao),
            cartoes: g ? (g.cartoes || []) : [],
            aberto: g ? Math.round(g.em_aberto * 100) / 100 : null,
            total: g ? Math.round(g.total_fatura * 100) / 100 : null
          };
        }, { m: mes, fis: fisico });

        ok(`${mes}: o virtual ${v.final} não aparece como fatura própria`,
           visto.linhas === 1 && !visto.soltas.includes(v.final),
           `${visto.linhas} linha(s) para o ${fisico}, soltas: ${visto.soltas.join(',') || 'nenhuma'}`);

        ok(`${mes}: a fatura cobrada reúne os dois números`,
           visto.cartoes.includes(v.final) && visto.cartoes.includes(fisico),
           visto.cartoes.join(' + ') || 'nenhum');

        // O valor tem de ser a soma dos dois blocos: juntar a cobrança não pode
        // perder nem dobrar dinheiro.
        igual(`${mes}: a fatura cobrada soma os dois blocos (em aberto)`, visto.aberto, somaAberto, 0.02);
        igual(`${mes}: a fatura cobrada soma os dois blocos (total)`, visto.total, somaTotal, 0.02);
      }
    }
  }

  // --- Conta recorrente cadastrada à mão ---
  //
  // A projeção pelo histórico só enxerga o que passou pelo extrato pessoal, e
  // três meses ou mais. A contabilidade da Stima sai da conta da Benetti UP:
  // aparece uma única vez no extrato dela, em 05/2026. Sem o cadastro em
  // `configuracoes.json` essa conta nunca existiria na tela, por mais tempo que
  // passasse — e é justamente a que ela esquece de pagar todo dia 5.
  {
    const mes = mesVigenteNoTeste;
    const cadastro = (config.contas_recorrentes || []).filter(c => c.ativa !== false && c.valor > 0);

    const visto = await pagina.evaluate(m => {
      document.querySelector('[data-tab="painel"]').click();
      document.getElementById('painel_mes').value = m;
      delete dadosGlobais.plano_do_mes;
      renderizarPainel();
      const el = document.getElementById('painel_vencimentos_criticos');
      const previstas = recorrentesFaltandoEm(m);
      return {
        texto: el.innerText,
        chaves: previstas.map(r => r.chave),
        cadastradas: previstas.filter(r => r.cadastrada).map(r => ({ d: r.descricao, v: r.valor, fora: !!r.fora_da_conta })),
        foraNaTabela: [...el.querySelectorAll('tbody tr[data-fora-da-conta]')].length,
        // Linhas de outro caixa que ainda estão a pagar (têm os botões do
        // plano) e as que já foram pagas por ele (sem botão).
        foraEmAberto: [...el.querySelectorAll('tbody tr[data-fora-da-conta]')]
          .filter(tr => tr.querySelector('.plano-btn')).length,
        foraQuitadas: [...el.querySelectorAll('tbody tr[data-fora-da-conta]')]
          .filter(tr => !tr.querySelector('.plano-btn')).length,
        previstasFora: previstas.filter(r => r.fora_da_conta).length,
        saiDaConta: (document.getElementById('painel_fluxo_3numeros') || document.body).innerText
      };
    }, mes);

    ok('Toda conta recorrente cadastrada aparece na lista de vencimentos',
       cadastro.every(c => visto.texto.includes(c.descricao)),
       cadastro.map(c => c.descricao).join(', '));

    // O cadastro não pode duplicar o que o histórico já projeta nem o que o
    // extrato já trouxe: duas linhas da mesma conta somariam duas vezes.
    ok('Conta cadastrada nunca duplica uma já projetada pelo histórico',
       new Set(visto.chaves).size === visto.chaves.length,
       `${visto.chaves.length} previstas, ${new Set(visto.chaves).size} distintas`);

    // O boleto que a empresa paga não pode entrar no dinheiro dela: é o mesmo
    // princípio que já tirou do Painel a fatura quitada pela Benetti UP.
    // A tabela marca duas coisas com `data-fora-da-conta`: a conta cadastrada
    // que **vai** ser paga por outro caixa, e a que **já foi** — esta última
    // passou a aparecer como quitada em vez de sumir da lista, depois que a
    // Juliane notou contas pagas ainda pedindo pagamento. O total marcado tem
    // de ser exatamente a soma das duas, senão alguma escapou da marcação.
    const foraEsperadas = cadastro.filter(c => (c.paga_por || 'juliane') !== 'juliane');
    igual('Conta paga por outro caixa vem marcada como tal na tabela',
          visto.foraNaTabela, visto.previstasFora + visto.foraQuitadas);
    ok('Toda conta cadastrada de outro caixa que ainda não foi paga está marcada',
       visto.previstasFora <= foraEsperadas.length,
       `${visto.previstasFora} previstas de outro caixa, ${foraEsperadas.length} cadastradas assim`);

    if (visto.foraEmAberto) {
      const somas = await pagina.evaluate(m => {
        const el = document.getElementById('painel_vencimentos_criticos');
        const linhas = [...el.querySelectorAll('tbody tr')];
        const valor = tr => Number(tr.cells[2].innerText.replace(/[^\d,-]/g, '').replace(',', '.'));
        // O rodapé soma o que está em aberto: nem quitado (sem botão) nem com
        // pagamento parado. Recalculado aqui a partir das próprias linhas.
        const emAberto = linhas.filter(tr => tr.querySelector('.plano-btn') && !tr.dataset.suspenso);
        return {
          rodape: Number((el.querySelector('tfoot .num') || {}).innerText
                    .replace(/[^\d,-]/g, '').replace(',', '.')),
          semEmpresa: emAberto.filter(tr => !tr.dataset.foraDaConta).reduce((a, tr) => a + valor(tr), 0),
          somaFora: emAberto.filter(tr => tr.dataset.foraDaConta).reduce((a, tr) => a + valor(tr), 0)
        };
      }, mes);

      // Duas pontas: o rodapé bate com a soma sem o boleto da empresa, e não
      // bate com ela — só some do total se de fato tiver sido excluído.
      ok('Rodapé "ainda a pagar" exclui o que a Benetti UP paga',
         somas.somaFora > 0.01
           && Math.abs(somas.semEmpresa - somas.rodape) < 0.05
           && Math.abs(somas.semEmpresa + somas.somaFora - somas.rodape) > 0.05,
         `sem a empresa ${brl(somas.semEmpresa)} = rodapé ${brl(somas.rodape)}; com ela seria ${brl(somas.semEmpresa + somas.somaFora)}`);
    } else {
      // Sem nenhuma conta de outro caixa **em aberto** no mês, a prova dos dois
      // lados não tem o que comparar — dizer isso é melhor que passar vazio.
      ok(`Nenhuma conta de outro caixa em aberto em ${mes} — nada a excluir do rodapé`,
         true, `${visto.foraQuitadas} já paga(s) pela Benetti UP neste mês`);
    }
  }

  // A conferência não pode acusar pagamento que a dashboard só não enxerga.
  // Ago/26 é o caso real: o extrato está incompleto a ponto de não trazer nem o
  // crédito do salário, então nada daquele mês pode ser dado como não pago.
  {
    const mesFalho = mesesReais.find(m => {
      const doMes = todosLancamentos.filter(t => t.mes_vencimento === m);
      return doMes.some(t => t.origem === 'holerite_elektro' && t.natureza === 'receita')
          && !doMes.some(t => t.origem === 'extrato_itau' && /Crédito do salário/i.test(t.descricao || ''));
    });

    if (mesFalho) {
      const r = await pagina.evaluate(m => {
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        const el = document.getElementById('painel_vencimentos_criticos');
        dadosGlobais.plano_do_mes = { [m]: { orcamento: null, itens: {} } };
        el.querySelectorAll('.plano-btn').forEach(bt => {
          if (bt.textContent.trim() === 'pago') {
            const k = bt.getAttribute('onclick').match(/,\s*'([^']+)'\s*,/);
            if (k) dadosGlobais.plano_do_mes[m].itens[k[1]] = 'pagar';
          }
        });
        renderizarPainel();
        const txt = document.getElementById('painel_vencimentos_criticos').innerText;
        delete dadosGlobais.plano_do_mes;
        return txt;
      }, mesFalho);

      ok(`Conferência ${mesFalho}: extrato incompleto vira "não dá para conferir", não acusação`,
         /não dá para conferir/i.test(r) && /extrato deste mês está incompleto/i.test(r),
         r.split('\n').filter(l => /conferir|não saiu/i.test(l)).join(' | ').slice(0, 260));
    }
  }

  // 'agendado' vale no dia da importação, não para sempre: passada a data, o
  // PIX aconteceu. Sem isso a tela mostrava como vencido o que já tinha saído.
  {
    const hojeIso = new Date().toISOString().slice(0, 10);
    const vencidos = todosLancamentos.filter(t =>
      t.status === 'agendado' && t.data && t.data < hojeIso && noEscopo(t.mes_vencimento));
    if (vencidos.length) {
      const mesAlvo = vencidos[0].mes_vencimento;
      const aindaVencendo = await pagina.evaluate(m => {
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        return [...document.querySelectorAll('#painel_vencimentos_criticos tbody tr')]
          .filter(tr => /venceu há/i.test(tr.innerText))
          .map(tr => tr.cells[1].innerText.split('\n')[0]);
      }, mesAlvo);
      const nomes = vencidos.filter(t => t.mes_vencimento === mesAlvo).map(t => t.descricao);
      ok(`Agendado com data passada não aparece como vencido (${vencidos.length} lançamentos)`,
         !nomes.some(n => aindaVencendo.includes(n)),
         aindaVencendo.filter(n => nomes.includes(n)).join(', '));
    }
  }

  // --- Alerta do que falta carregar ---
  {
    const alerta = await pagina.evaluate(() => {
      renderizarAlertaDeDados();
      const el = document.getElementById('alerta_dados');
      return { txt: el.innerText, itens: el.querySelectorAll('li').length,
               criticos: el.querySelectorAll('li.critico').length };
    });

    // Extrato parado: o arquivo mais velho é o que limita toda a dashboard.
    const ultimaLinha = todosLancamentos
      .filter(t => t.origem === 'extrato_itau' && t.data).map(t => t.data).sort().pop();
    const diasParado = Math.round(
      (new Date().setHours(0, 0, 0, 0) - new Date(ultimaLinha + 'T00:00:00')) / 86400000);
    if (diasParado > 7) {
      ok(`Alerta avisa que o extrato está parado há ${diasParado} dias`,
         new RegExp(`parado há ${diasParado} dias`).test(alerta.txt),
         alerta.txt.split('\n').slice(0, 4).join(' | '));
    }

    // Extrato incompleto entra como crítico, não como aviso qualquer: ele já
    // está distorcendo número, não é só dado envelhecendo.
    const mesFalho = mesesReais.find(m => {
      const doMes = todosLancamentos.filter(t => t.mes_vencimento === m);
      return doMes.some(t => t.origem === 'holerite_elektro' && t.natureza === 'receita')
          && !doMes.some(t => t.origem === 'extrato_itau' && /Crédito do salário/i.test(t.descricao || ''));
    });
    if (mesFalho) {
      ok(`Alerta marca o extrato incompleto de ${mesFalho} como crítico`,
         alerta.criticos > 0 && alerta.txt.includes(`Extrato de ${mesFalho} incompleto`),
         `${alerta.criticos} crítico(s)`);
    }

    // O holerite só existe a partir do dia 25. Cobrar antes disso seria pedir
    // um arquivo que ainda não foi emitido — ruído que ensina a ignorar o alerta.
    const diaDeHoje = new Date().getDate();
    const temFolhaVigente = todosLancamentos.some(t =>
      t.origem === 'holerite_elektro' && t.mes_vencimento === mesVigenteNoTeste && t.natureza === 'receita');
    if (!temFolhaVigente) {
      if (diaDeHoje < 26) {
        ok(`Alerta não cobra o holerite antes do dia 25 (hoje é dia ${diaDeHoje})`,
           !/Holerite de/i.test(alerta.txt),
           alerta.txt.split('\n').filter(l => /holerite/i.test(l)).join(' | '));
      } else {
        ok(`Alerta cobra o holerite depois do dia 25 (hoje é dia ${diaDeHoje})`,
           /Holerite de/i.test(alerta.txt), '(não apareceu)');
      }
    }

    // PIX agendado com data futura não pode contar como "o extrato enxerga até
    // aqui". O arquivo de 05/09 traz um agendamento para 28/10 — se essa data
    // valesse, o alerta de extrato parado nunca mais dispararia e a conferência
    // do plano julgaria conta que ainda não teve como sair.
    {
      const hojeIso = new Date().toISOString().slice(0, 10);
      const futuros = todosLancamentos.filter(t =>
        t.origem === 'extrato_itau' && t.data && t.data > hojeIso);
      const ate = await pagina.evaluate(() => extratoCobreAte());
      ok('Extrato: data futura de PIX agendado não conta como cobertura',
         !ate || ate <= hojeIso,
         `cobre até ${ate}, com ${futuros.length} lançamento(s) de data futura no arquivo`);
      if (futuros.length) {
        const maiorFuturo = futuros.map(t => t.data).sort().pop();
        ok(`Extrato: os ${futuros.length} agendamento(s) até ${maiorFuturo} ficam de fora da cobertura`,
           ate < maiorFuturo, `cobre até ${ate}`);
      }

      // O caso que escapava: agendado cuja data já passou. Filtrar só por
      // `data <= hoje` deixava o agendamento virar passado e o arquivo alegar
      // cobertura que nunca teve — e dentro desses dias a conferência acusava
      // de não paga uma conta que o extrato não tinha como mostrar. Quem
      // responde "até onde este arquivo enxerga" é a linha que já movimentou a
      // conta, então o discriminador é o status, não a data.
      const reais = todosLancamentos.filter(t =>
        t.origem === 'extrato_itau' && t.data && t.data <= hojeIso && t.status !== 'agendado');
      const comAgendado = todosLancamentos.filter(t =>
        t.origem === 'extrato_itau' && t.data && t.data <= hojeIso);
      const ultimaReal = reais.map(t => t.data).sort().pop();
      const ultimaQualquer = comAgendado.map(t => t.data).sort().pop();
      igual('Extrato: a cobertura é a última linha que de fato movimentou a conta',
            ate, ultimaReal);
      if (ultimaQualquer > ultimaReal) {
        ok(`Extrato: agendado de data já passada (${ultimaQualquer}) não estica a cobertura`,
           ate !== ultimaQualquer,
           `cobre até ${ate}; com o agendado iria até ${ultimaQualquer}`);
      }
    }

    // O script de linha de comando que alimenta o alerta no celular tem de
    // dizer exatamente o que a tela diz. São dois códigos separados lendo o
    // mesmo JSON — se divergirem, o alerta promete um mês diferente do que a
    // dashboard mostra, e ela deixa de confiar nos dois.
    {
      const hojeIso = new Date().toISOString().slice(0, 10);
      const fimDoMes = new Date(new Date(hojeIso + 'T00:00:00').getFullYear(),
                                new Date(hojeIso + 'T00:00:00').getMonth() + 1, 0)
                         .toISOString().slice(0, 10);
      const dias = Math.round((new Date(fimDoMes) - new Date(hojeIso)) / 86400000);
      const saida = require('child_process')
        .execFileSync('node', [path.join(__dirname, 'contas-a-vencer.js'), '--dias', String(dias)],
                      { encoding: 'utf8' });

      // Só as linhas de item, e só as do mês vigente: a tela mostra um mês por vez.
      const doScript = saida.split('\n')
        .map(l => l.match(/^\s{2}(\d{2})\/(\d{2})\/(\d{4})\s+R\$\s([\d.,]+)\s\s(.+?)(?:\s\s\[|$)/))
        .filter(Boolean)
        .map(m => ({ data: `${m[3]}-${m[2]}-${m[1]}`, valor: numeroDe('R$ ' + m[4]), titulo: m[5].trim() }))
        .filter(x => x.data >= hojeIso && x.data <= fimDoMes);

      const daTela = await pagina.evaluate(m => {
        document.querySelector('[data-tab="painel"]').click();
        document.getElementById('painel_mes').value = m;
        renderizarPainel();
        return [...document.getElementById('painel_vencimentos_criticos').querySelectorAll('tbody tr')]
          .filter(tr => tr.querySelector('.plano-btn'))
          .map(tr => ({
            data: tr.cells[0].innerText.trim().split('/').reverse().join('-'),
            valor: Number(tr.cells[2].innerText.replace(/[^\d,-]/g, '').replace(',', '.')),
            titulo: tr.cells[1].innerText.split('\n')[0].trim()
          }));
      }, mesVigenteNoTeste);

      const chave = x => `${x.data}|${x.titulo}|${x.valor.toFixed(2)}`;
      const naTela = new Set(daTela.filter(x => x.data >= hojeIso).map(chave));
      const noScript = new Set(doScript.map(chave));
      const soNoScript = [...noScript].filter(k => !naTela.has(k));
      const soNaTela = [...naTela].filter(k => !noScript.has(k));

      ok('Script de alerta e tabela de vencimentos listam exatamente as mesmas contas',
         doScript.length > 0 && !soNoScript.length && !soNaTela.length,
         soNoScript.length || soNaTela.length
           ? `só no script: ${soNoScript.join(' / ') || '—'}; só na tela: ${soNaTela.join(' / ') || '—'}`
           : `${doScript.length} conta(s) conferidas`);
    }

    // O outro lado: fonte em dia não pode gerar alerta. Sem isso o bloco vira
    // papel de parede — sempre aceso, logo nunca lido.
    const semAviso = await pagina.evaluate(() => {
      const tx = dadosGlobais.fluxo_mensal.transacoes;
      const hoje = new Date().toISOString().slice(0, 10);
      const falso = { id: 'teste_extrato_recente', data: hoje, valor: 1, tipo: 'saida',
                      natureza: 'despesa', categoria: 'teste', descricao: 'lançamento de teste',
                      origem: 'extrato_itau', mes_vencimento: mesVigente(), pessoa: 'Juliane',
                      ambito: 'pessoal', status: 'confirmado' };
      tx.push(falso);
      renderizarAlertaDeDados();
      const txt = document.getElementById('alerta_dados').innerText;
      tx.splice(tx.indexOf(falso), 1);
      renderizarAlertaDeDados();
      return txt;
    });
    ok('Extrato em dia deixa de aparecer no alerta',
       !/parado há/i.test(semAviso),
       semAviso.split('\n').filter(l => /parado/i.test(l)).join(' | '));
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
  // Mesmo critério da tela: gasto é `despesa` positiva, não qualquer positivo.
  escopo.filter(t => t.natureza === 'despesa' && t.valor > 0).forEach(t => {
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
      // Cartão | Fatura | Vencimento | Situação | Lanç. | Consumo | Taxas | Parcelas | Do período | Saldo anterior | Total da fatura | Em aberto | Conferência
      return { cartao: td[0].replace(/\D/g, ''), mes: td[1], situacao: td[3], n: td[4],
               consumo: td[5], taxas: td[6], parcelas: td[7], doPeriodo: td[8],
               saldoAnterior: td[9], totalFatura: td[10], emAberto: td[11], conferencia: td[12] };
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

  // Consumo x taxas x parcelas: a pergunta é "quanto foi compra e quanto o
  // banco cobrou para carregar a dívida". Recalculado aqui por fora, direto do
  // JSON, e conferido contra a tela célula a célula.
  //
  // A identidade é o que protege o recorte: se as três não somarem o "Do
  // período" da própria linha, alguma natureza caiu na coluna errada — e a
  // tela estaria dizendo que foi consumo um dinheiro que foi juro, ou o
  // contrário.
  {
    const porFatura = {};
    (dados.fluxo_mensal.transacoes || []).forEach(t => {
      if (!t.fatura_origem) return;
      (porFatura[t.fatura_origem] = porFatura[t.fatura_origem] || []).push(t);
    });
    let semTaxa = 0;
    faturas.forEach(f => {
      const linha = cartao.linhas.find(l => l.mes === f.mes && l.cartao === f.cartao);
      if (!linha) return;
      let consumo = 0, taxas = 0, parcelas = 0;
      (porFatura[`${f.cartao}|${f.mes}`] || []).forEach(t => {
        if (t.natureza === 'pagamento') return;
        if (t.natureza === 'divida_parcelada') parcelas += t.valor;
        else if (t.categoria === 'encargos_financeiros') taxas += t.valor;
        else consumo += t.valor;
      });
      const r = v => Math.round(v * 100) / 100;
      [consumo, taxas, parcelas] = [r(consumo), r(taxas), r(parcelas)];

      ok(`${f.cartao} ${f.mes}: consumo + taxas + parcelas = do período`,
         Math.abs(consumo + taxas + parcelas - f.cobrado) < 0.05,
         `${brl(consumo)} + ${brl(taxas)} + ${brl(parcelas)} = ${brl(consumo + taxas + parcelas)}, cobrado ${brl(f.cobrado)}`);

      igual(`${f.cartao} ${f.mes} exibe ${brl(consumo)} de consumo`, numeroDe(linha.consumo), consumo);
      if (Math.abs(taxas) > 0.05) {
        igual(`${f.cartao} ${f.mes} exibe ${brl(taxas)} de taxas`, numeroDe(linha.taxas), taxas);
      } else {
        semTaxa++;
        ok(`${f.cartao} ${f.mes} sem taxa não mostra R$ 0,00`, linha.taxas === '—', `mostrou "${linha.taxas}"`);
      }
    });

    // Sem nenhuma fatura com taxa, as asserções de valor acima nunca rodam e o
    // bloco passaria sem provar nada.
    const comTaxa = faturas.length - semTaxa;
    ok('Existe fatura com taxa para este bloco ter o que conferir', comTaxa > 0,
       `${comTaxa} de ${faturas.length} faturas com taxa`);

    const totalTaxas = faturas.reduce((acc, f) => acc + Math.round(
      (porFatura[`${f.cartao}|${f.mes}`] || [])
        .filter(t => t.natureza !== 'pagamento' && t.natureza !== 'divida_parcelada'
                  && t.categoria === 'encargos_financeiros')
        .reduce((x, t) => x + t.valor, 0) * 100) / 100, 0);
    const kpiTaxas = cartao.kpis.map(numeroDe).find(v => v !== null && Math.abs(v - totalTaxas) < 0.05);
    ok('Cartão: KPI "Juros e taxas" bate com a soma das faturas',
       kpiTaxas !== undefined, `esperado ${brl(totalTaxas)}; KPIs na tela: ${cartao.kpis.join(' | ')}`);
    console.log(`    (juros e taxas no ano: ${brl(totalTaxas)})`);
  }

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

  // Saldo que rolou não pode ser contado duas vezes.
  //
  // Fatura não quitada reaparece inteira dentro da seguinte, como
  // `saldo_anterior`. Somar o `em_aberto` de todas as faturas de um cartão conta
  // a mesma dívida uma vez por mês em que ela rolou — no Black, R$ 30.507,33 por
  // uma dívida que é o saldo da última fatura. Enquanto o importador acreditava
  // no rótulo "Fatura Paga" do XLSX, julho e agosto apareciam quitadas e a soma
  // ingênua dava certo por acidente.
  //
  // Recalculado aqui por fora, com a mesma regra da tela, e provado dos dois
  // lados: o KPI bate com a soma que desconta o que rolou e NÃO bate com a
  // soma ingênua.
  {
    const naoRolou = f => {
      const aberto = Math.max(0, f.em_aberto || 0);
      if (aberto <= 0.05) return 0;
      const seg = faturas
        .filter(o => o.cartao === f.cartao && String(o.vencimento) > String(f.vencimento))
        .sort((a, b) => String(a.vencimento).localeCompare(String(b.vencimento)))[0];
      if (!seg) return aberto;
      const resto = Math.round((aberto - Math.min(aberto, Math.max(0, seg.saldo_anterior || 0))) * 100) / 100;
      return resto > 0.05 ? resto : 0;
    };
    const semRolagem = faturas.reduce((s, f) => s + naoRolou(f), 0);
    const kpiAberto = cartao.kpis.map(numeroDe).find(v => v !== null && Math.abs(v - semRolagem) < 0.05
                                                        || v !== null && Math.abs(v - totalAberto) < 0.05);
    const rolaram = faturas.filter(f => naoRolou(f) < Math.max(0, f.em_aberto || 0) - 0.05);

    ok('Cartão: o "em aberto" não soma o saldo que rolou para a fatura seguinte',
       kpiAberto !== undefined && Math.abs(kpiAberto - semRolagem) < 0.05,
       `na tela ${brl(kpiAberto)}; sem o que rolou ${brl(semRolagem)}; somando tudo ${brl(totalAberto)}`);

    // O outro lado da prova: se nada tivesse rolado as duas somas seriam iguais
    // e o teste acima passaria sozinho, sem testar nada.
    ok('Existe saldo rolado para este teste ter o que provar',
       rolaram.length > 0 && Math.abs(totalAberto - semRolagem) > 0.05,
       `${rolaram.length} fatura(s) rolaram; diferença ${brl(totalAberto - semRolagem)}`);

    rolaram.forEach(f => {
      const seg = faturas
        .filter(o => o.cartao === f.cartao && String(o.vencimento) > String(f.vencimento))
        .sort((a, b) => String(a.vencimento).localeCompare(String(b.vencimento)))[0];
      ok(`${f.cartao} ${f.mes}: o que rolou reaparece como saldo anterior de ${seg.mes}`,
         Math.max(0, seg.saldo_anterior || 0) > 0.05,
         `em aberto ${brl(f.em_aberto)}, saldo anterior da seguinte ${brl(seg.saldo_anterior)}`);
    });
  }
  // Fatura parcelada quita no cartao trocando a divida de lugar: o que sobra
  // sai do cartao e vira contrato de parcelas. `financiado_em_parcelas` guarda
  // esse valor — sem ele a identidade abaixo acusaria um saldo em aberto que
  // nao esta mais no cartao, e ninguem saberia para onde o dinheiro foi.
  ok('Saldo em aberto é a soma do que cada fatura deve',
     Math.abs(totalAberto - faturas.reduce((s, f) =>
       s + Math.max(0, f.total_fatura - f.pago - (f.financiado_em_parcelas || 0)), 0)) < 0.05);

  // E o valor financiado tem de estar cadastrado como divida, senao ele some da
  // tela: sai do cartao e nao aparece em lugar nenhum.
  {
    const parceladas = faturas.filter(f => (f.financiado_em_parcelas || 0) > 0.05);
    parceladas.forEach(f => {
      const contrato = (dados.dividas || []).find(x =>
        /parcelamento/i.test(x.nome || '') &&
        `${x.nome || ''} ${x.observacao || ''}`.includes(f.mes) &&
        `${x.nome || ''} ${x.observacao || ''}`.includes(f.cartao));
      ok(`Fatura ${f.cartao} ${f.mes} parcelada tem contrato cadastrado em Dívidas`,
         !!contrato, `R$ ${f.financiado_em_parcelas} financiados sem contrato correspondente`);
      if (contrato) {
        ok(`Contrato do parcelamento ${f.cartao} ${f.mes} custa mais que o financiado (é crédito)`,
           contrato.montante > f.financiado_em_parcelas,
           `montante ${contrato.montante} x financiado ${f.financiado_em_parcelas}`);
      }
    });
  }

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
  // Exceção real: quando o banco CANCELA um parcelamento, ele antecipa todas as
  // parcelas restantes para a fatura do cancelamento e estorna as mesmas
  // parcelas ali. As 11 parcelas do "Parc Automatico" aparecem juntas em Out/26
  // porque foram canceladas juntas — e somam zero com os estornos ao lado.
  // Isso não é duplicação: é a reversão, e ela tem de caber no dado.
  const canceladoNoMes = {};
  todosLancamentos.filter(t => /^canc\s+parc\s+de\s+ref/i.test(t.descricao || ''))
    .forEach(t => {
      const k = [t.cartao_final || '', t.parcela_total || '', t.mes_vencimento].join('|');
      canceladoNoMes[k] = (canceladoNoMes[k] || 0) + 1;
    });

  const repetidas = Object.entries(porContratoMes).filter(([k, n]) => {
    if (n <= 1) return false;
    const [, cartao, , total, mes] = k.split('|');
    return (canceladoNoMes[[cartao, total, mes].join('|')] || 0) < n;
  });
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
      dizNaoCadastrado: /não cadastrado/i.test(txt),
      dizPrevisto: /previsto/i.test(txt),
      trechoEntrada: ((document.querySelector('#painel_fluxo_3numeros .fluxo-item') || {}).innerText || '')
        .replace(/\n/g, ' | ')
    };
  }, mesSemHolerite);
  ok('Painel não exibe o déficit falso de R$ 40.086,47', !zerosFalsos.temDeficitFalso);
  // A regra de ouro nao proibe estimar — proibe passar estimativa por fato.
  // Num mes sem holerite a tela tem de fazer uma das duas: dizer "nao
  // cadastrado", ou mostrar um numero marcado como previsao. O que nao pode e
  // exibir um valor cru como se fosse o holerite de verdade.
  ok('Painel nunca mostra número sem holerite como se fosse fato',
     zerosFalsos.dizNaoCadastrado || zerosFalsos.dizPrevisto,
     `mês testado: ${mesSemHolerite || '(nenhum sem holerite achado)'} — ${zerosFalsos.trechoEntrada}`);

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

  // Garantia final: qualquer teste pode ter limpado o plano em memória, e um
  // salvamento posterior persistiria essa limpeza. O arquivo tem de terminar a
  // suíte com o plano que tinha antes dela.
  await pagina.evaluate(async original => {
    const atual = JSON.stringify(dadosGlobais.plano_do_mes || null);
    if (atual === JSON.stringify(original)) return;
    if (original) dadosGlobais.plano_do_mes = original;
    else delete dadosGlobais.plano_do_mes;
    await fetch('/api/dados', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(dadosGlobais) });
  }, planoOriginal);
  await pagina.waitForTimeout(400);

  const planoDepois = JSON.parse(fs.readFileSync(ARQUIVO, 'utf8')).plano_do_mes || null;
  ok('A suíte devolve o plano do mês como estava — não apaga decisão da Juliane',
     JSON.stringify(planoDepois) === JSON.stringify(planoOriginal),
     `antes: ${JSON.stringify(planoOriginal || null).slice(0, 80)} · depois: ${JSON.stringify(planoDepois).slice(0, 80)}`);

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
