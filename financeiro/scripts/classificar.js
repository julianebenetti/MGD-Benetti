#!/usr/bin/env node
/**
 * Classificação de lançamentos — regras, exportação e reimportação.
 *
 * As regras ficam em data/regras-classificacao.json e são a memória do que já
 * foi decidido: quem se beneficia da despesa e em que categoria ela entra.
 * A primeira regra que casa com a descrição vence, então o específico vem
 * antes do genérico.
 *
 * Um ponto que vale registrar: a pessoa da despesa é quem se beneficia dela,
 * não quem passou o cartão. Supermercado pago no cartão do Hugo é despesa da
 * Família. Por isso a regra sobrepõe o portador.
 *
 * Comandos:
 *   node scripts/classificar.js aplicar [--aplicar]
 *       Roda as regras sobre os lançamentos. Sem --aplicar só simula.
 *
 *   node scripts/classificar.js exportar [arquivo.xlsx] [--so-pendentes]
 *       Gera uma planilha com um estabelecimento por linha, para revisar em
 *       lote. São 225 estabelecimentos para 604 lançamentos.
 *
 *   node scripts/classificar.js importar arquivo.xlsx [--aplicar]
 *       Lê a planilha revisada e aplica. Onde a linha estiver marcada para
 *       virar regra, grava também em regras-classificacao.json, para valer
 *       nas próximas importações.
 */

const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const DIR_DADOS = path.join(__dirname, '..', 'data');
const ARQ_FINANCEIRO = path.join(DIR_DADOS, 'financeiro.json');
const ARQ_REGRAS = path.join(DIR_DADOS, 'regras-classificacao.json');
const ARQ_CONFIG = path.join(DIR_DADOS, 'configuracoes.json');

const comando = process.argv[2];
const aplicar = process.argv.includes('--aplicar');

const ler = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const normalizar = s => String(s).toLowerCase().replace(/\s+/g, ' ').trim();
const brl = v => 'R$ ' + (v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 });

// ---------------------------------------------------------------- regras

function casar(descricao, regras) {
  const alvo = normalizar(descricao);
  return regras.find(r => new RegExp(r.padrao, 'i').test(alvo)) || null;
}

function cmdAplicar() {
  const dados = ler(ARQ_FINANCEIRO);
  const { regras } = ler(ARQ_REGRAS);
  const transacoes = dados.fluxo_mensal.transacoes;

  const mudancas = [];
  transacoes.forEach(t => {
    if (t.natureza === 'pagamento') return;
    const regra = casar(t.descricao, regras);
    if (!regra) return;

    const novaCategoria = regra.categoria || t.categoria;
    const novaPessoa = regra.pessoa || t.pessoa;
    if (novaCategoria === t.categoria && novaPessoa === t.pessoa) return;

    mudancas.push({
      descricao: t.descricao,
      valor: t.valor,
      de: `${t.categoria} / ${t.pessoa}`,
      para: `${novaCategoria} / ${novaPessoa}`,
      nota: regra.nota,
    });

    t.categoria = novaCategoria;
    t.pessoa = novaPessoa;
    t.classificado_por = 'regra';
  });

  console.log(`\n=== APLICAR REGRAS ${aplicar ? '' : '(SIMULAÇÃO)'} ===\n`);
  console.log(`${regras.length} regras · ${transacoes.length} lançamentos · ${mudancas.length} mudanças\n`);

  // Agrupa por tipo de mudança, para o relatório caber na tela
  const porMudanca = {};
  mudancas.forEach(m => {
    const chave = `${m.de} -> ${m.para}`;
    if (!porMudanca[chave]) porMudanca[chave] = { n: 0, valor: 0, nota: m.nota, exemplos: [] };
    porMudanca[chave].n++;
    porMudanca[chave].valor += m.valor;
    if (porMudanca[chave].exemplos.length < 2) porMudanca[chave].exemplos.push(m.descricao.slice(0, 34));
  });

  Object.entries(porMudanca)
    .sort((a, b) => b[1].valor - a[1].valor)
    .forEach(([chave, info]) => {
      console.log(`${chave}`);
      console.log(`   ${info.n} lançamentos · ${brl(info.valor)} · ${info.nota}`);
      info.exemplos.forEach(e => console.log(`   - ${e}`));
      console.log('');
    });

  const semRegra = transacoes.filter(t => t.natureza !== 'pagamento' && !casar(t.descricao, regras));
  const estabSemRegra = new Set(semRegra.map(t => normalizar(t.descricao)));
  console.log(`Sem regra: ${semRegra.length} lançamentos em ${estabSemRegra.size} estabelecimentos`);
  console.log(`           ${brl(semRegra.reduce((s, t) => s + t.valor, 0))} — mantêm a classificação atual`);

  if (aplicar) {
    fs.writeFileSync(ARQ_FINANCEIRO, JSON.stringify(dados, null, 2), 'utf8');
    console.log(`\n✅ Gravado em ${ARQ_FINANCEIRO}\n`);
  } else {
    console.log('\nRode com --aplicar para gravar.\n');
  }
}

// ------------------------------------------------------------- exportar

function cmdExportar() {
  const saida = process.argv[3] && !process.argv[3].startsWith('--')
    ? process.argv[3]
    : path.join(DIR_DADOS, 'classificacao-para-revisar.xlsx');

  const dados = ler(ARQ_FINANCEIRO);
  const { regras } = ler(ARQ_REGRAS);
  const config = ler(ARQ_CONFIG);
  const transacoes = dados.fluxo_mensal.transacoes.filter(t => t.natureza !== 'pagamento');

  // Um estabelecimento por linha: 604 lançamentos viram 225 decisões
  const porEstabelecimento = {};
  transacoes.forEach(t => {
    const chave = normalizar(t.descricao);
    if (!porEstabelecimento[chave]) {
      porEstabelecimento[chave] = {
        descricao: t.descricao,
        lancamentos: 0,
        total: 0,
        categoria: t.categoria,
        pessoa: t.pessoa,
        portadores: new Set(),
        meses: new Set(),
      };
    }
    const e = porEstabelecimento[chave];
    e.lancamentos++;
    e.total += t.valor;
    if (t.portador) e.portadores.add(t.portador.split(' ')[0]);
    e.meses.add(t.mes_vencimento);
  });

  // --so-pendentes deixa de fora o que ja esta coberto por regra, para nao
  // pedir revisao do que ja foi decidido.
  const soPendentes = process.argv.includes('--so-pendentes');

  const linhas = Object.values(porEstabelecimento)
    .filter(e => !soPendentes || !casar(e.descricao, regras))
    .sort((a, b) => b.total - a.total)
    .map(e => {
      const regra = casar(e.descricao, regras);
      return {
        'Estabelecimento': e.descricao,
        'Lançamentos': e.lancamentos,
        'Total': Math.round(e.total * 100) / 100,
        'Categoria atual': e.categoria,
        'Pessoa atual': e.pessoa,
        'NOVA CATEGORIA': '',
        'NOVA PESSOA': '',
        'Virar regra?': '',
        'Observação': '',
        'Regra que já aplica': regra ? regra.nota : '',
        'Cartão de': [...e.portadores].join(', '),
        'Meses': [...e.meses].join(', '),
      };
    });

  const wb = XLSX.utils.book_new();

  const ws = XLSX.utils.json_to_sheet(linhas);
  ws['!cols'] = [{ wch: 42 }, { wch: 12 }, { wch: 12 }, { wch: 20 }, { wch: 14 },
                 { wch: 22 }, { wch: 16 }, { wch: 13 }, { wch: 30 }, { wch: 34 },
                 { wch: 16 }, { wch: 26 }];
  ws['!autofilter'] = { ref: XLSX.utils.encode_range({ s: { c: 0, r: 0 }, e: { c: 11, r: linhas.length } }) };
  ws['!freeze'] = { xSplit: 1, ySplit: 1 };
  XLSX.utils.book_append_sheet(wb, ws, 'Classificar');

  // Aba de apoio com os valores aceitos, para não haver dúvida na digitação
  const categorias = [...new Set([
    ...transacoes.map(t => t.categoria),
    ...regras.map(r => r.categoria),
  ])].filter(Boolean).sort();

  const pessoas = (config.pessoas || []).map(p => p.nome);

  const apoio = [
    { 'Como preencher': '1. Preencha NOVA CATEGORIA e/ou NOVA PESSOA só nas linhas que quiser mudar.' },
    { 'Como preencher': '2. Linha em branco fica como está.' },
    { 'Como preencher': '3. Em "Virar regra?" escreva SIM para valer nas próximas importações.' },
    { 'Como preencher': '4. Salve e devolva o arquivo.' },
    { 'Como preencher': '' },
    { 'Como preencher': 'CATEGORIAS EM USO:' },
    ...categorias.map(c => ({ 'Como preencher': `   ${c}` })),
    { 'Como preencher': '' },
    { 'Como preencher': 'PESSOAS CADASTRADAS:' },
    ...pessoas.map(p => ({ 'Como preencher': `   ${p}` })),
  ];
  const wsApoio = XLSX.utils.json_to_sheet(apoio);
  wsApoio['!cols'] = [{ wch: 76 }];
  XLSX.utils.book_append_sheet(wb, wsApoio, 'Instruções');

  XLSX.writeFile(wb, saida);

  const semRegra = linhas.filter(l => !l['Regra que já aplica']).length;
  const valor = linhas.reduce((s, l) => s + l['Total'], 0);
  console.log(`\n✅ ${saida}\n`);
  console.log(`${linhas.length} estabelecimentos · ${brl(valor)}`);
  if (!soPendentes) console.log(`${linhas.length - semRegra} já cobertos por regra · ${semRegra} sem regra`);
  else console.log('Só os que ainda não têm regra — o que já foi decidido ficou de fora');
  console.log(`\nPreencha NOVA CATEGORIA / NOVA PESSOA e devolva. Depois:`);
  console.log(`  node scripts/classificar.js importar ${path.basename(saida)} --aplicar\n`);
}

// ------------------------------------------------------------- importar

function cmdImportar() {
  const entrada = process.argv[3];
  if (!entrada) {
    console.error('Informe a planilha: node scripts/classificar.js importar arquivo.xlsx');
    process.exit(1);
  }
  const caminho = path.isAbsolute(entrada) ? entrada : path.join(DIR_DADOS, entrada);
  if (!fs.existsSync(caminho)) {
    console.error(`Arquivo não encontrado: ${caminho}`);
    process.exit(1);
  }

  const wb = XLSX.readFile(caminho);
  const linhas = XLSX.utils.sheet_to_json(wb.Sheets['Classificar'] || wb.Sheets[wb.SheetNames[0]], { defval: '' });

  const dados = ler(ARQ_FINANCEIRO);
  const arquivoRegras = ler(ARQ_REGRAS);
  const transacoes = dados.fluxo_mensal.transacoes;

  let alterados = 0, novasRegras = 0;
  const relatorio = [];

  linhas.forEach(linha => {
    const novaCategoria = String(linha['NOVA CATEGORIA'] || '').trim();
    const novaPessoa = String(linha['NOVA PESSOA'] || '').trim();
    if (!novaCategoria && !novaPessoa) return;

    const alvo = normalizar(linha['Estabelecimento']);
    const atingidos = transacoes.filter(t => normalizar(t.descricao) === alvo && t.natureza !== 'pagamento');
    if (!atingidos.length) return;

    const de = `${atingidos[0].categoria} / ${atingidos[0].pessoa}`;
    atingidos.forEach(t => {
      if (novaCategoria) t.categoria = novaCategoria;
      if (novaPessoa) t.pessoa = novaPessoa;
      t.classificado_por = 'revisao_manual';
      alterados++;
    });

    relatorio.push({
      descricao: linha['Estabelecimento'],
      n: atingidos.length,
      valor: atingidos.reduce((s, t) => s + t.valor, 0),
      de,
      para: `${novaCategoria || atingidos[0].categoria} / ${novaPessoa || atingidos[0].pessoa}`,
    });

    if (/^s(im)?$/i.test(String(linha['Virar regra?'] || '').trim())) {
      // Escapa o texto para virar um padrão literal seguro
      const padrao = alvo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      if (!arquivoRegras.regras.some(r => r.padrao === padrao)) {
        arquivoRegras.regras.unshift({
          padrao,
          ...(novaCategoria ? { categoria: novaCategoria } : {}),
          ...(novaPessoa ? { pessoa: novaPessoa } : {}),
          nota: String(linha['Observação'] || '').trim() || 'Definida na revisão manual',
          origem: 'revisao_manual',
        });
        novasRegras++;
      }
    }
  });

  console.log(`\n=== IMPORTAR CLASSIFICAÇÃO ${aplicar ? '' : '(SIMULAÇÃO)'} ===\n`);
  relatorio.sort((a, b) => b.valor - a.valor).forEach(r => {
    console.log(`${r.descricao.slice(0, 40).padEnd(42)} ${String(r.n).padStart(3)}x ${brl(r.valor).padStart(13)}`);
    console.log(`   ${r.de}  ->  ${r.para}`);
  });
  console.log(`\n${relatorio.length} estabelecimentos · ${alterados} lançamentos · ${novasRegras} novas regras`);

  if (aplicar) {
    fs.writeFileSync(ARQ_FINANCEIRO, JSON.stringify(dados, null, 2), 'utf8');
    if (novasRegras) {
      arquivoRegras.atualizado_em = new Date().toISOString().slice(0, 10);
      arquivoRegras.versao = (arquivoRegras.versao || 1) + 1;
      fs.writeFileSync(ARQ_REGRAS, JSON.stringify(arquivoRegras, null, 2), 'utf8');
    }
    console.log('\n✅ Gravado\n');
  } else {
    console.log('\nRode com --aplicar para gravar.\n');
  }
}

// ---------------------------------------------------------------- rotas

switch (comando) {
  case 'aplicar': cmdAplicar(); break;
  case 'exportar': cmdExportar(); break;
  case 'importar': cmdImportar(); break;
  default:
    console.log(`
Uso:
  node scripts/classificar.js aplicar [--aplicar]      roda as regras
  node scripts/classificar.js exportar [saida.xlsx]    gera planilha de revisão
  node scripts/classificar.js importar entrada.xlsx [--aplicar]
`);
}
