#!/usr/bin/env node
/**
 * Importador de Cartão de Crédito - AfiliDash Financeiro
 *
 * Importa transações de cartão de crédito (CSV ou JSON)
 * Classifica automaticamente as transações
 * Mescla com dados existentes
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

const FINANCEIRO_PATH = path.join(__dirname, 'data', 'financeiro.json');
const CLASSIFICACOES_PATH = path.join(__dirname, 'data', 'classificacoes.json');

// Padrões de classificação (mesmo do classificador-automatico.js)
const JULIANE_PATTERNS = [
  'ELEKTRO', 'MASTERCARD BLACK', 'APPLE', 'SPOTIFY',
  'GOOGLE ONE', 'KIWIFY', 'UNIAO', 'MAGALU', '99APP',
  '99RIDE', 'BENETTI', 'MGD', 'DONA TEREZINHA', 'INSTAMAGIC'
];

const HUGO_PATTERNS = [
  'COMBUSTIVEL', 'POSTO', 'AUTO PEÇA', 'TOKIO MARINE',
  'SEGURO CARRO', 'SAVEGNAGO', 'SUPERMERCADOS JL',
  'MARCIA DE CARLA'
];

const CATEGORIA_PATTERNS = {
  entrada: [
    'SALARIO', 'REMUNERACAO', 'ALUGUEL GARAGEM', 'PIX TRANSF'
  ],
  alimentacao: [
    'MERCADO', 'SUPER', 'PADARIA', 'RESTAUR', 'LANCHON',
    'PIZZARIA', 'AÇAI', 'CAFE', 'DONA TERE', 'MARCIA',
    'SAVEGNAGO', 'JL'
  ],
  transporte: [
    'COMBUSTIVEL', 'UBER', '99', 'TAXI', 'POSTO',
    'AUTO PEÇA', 'SEGURO', 'TOKIO'
  ],
  moradia: [
    'ALUGUEL', 'CONDOMINIO', 'CONDO', 'CASA'
  ],
  utilidades: [
    'ENERGIA', 'AGUA', 'LUZ', 'GAS', 'CPFL', 'SANASA',
    'INTERNET', 'CLARO', 'OI', 'CELULAR', 'VIVO'
  ],
  saude: [
    'FARMACIA', 'MEDICO', 'DENTISTA', 'DROGARIA',
    'DROGAL', 'ORTODONTIA', 'CLINICA'
  ],
  educacao: [
    'ESCOLA', 'CURSO', 'VAN', 'KIWIFY', 'UDEMY', 'GUILHERME'
  ],
  assinatura: [
    'APPLE', 'SPOTIFY', 'GOOGLE ONE', 'NETFLIX', 'IFOOD', 'PRIME'
  ],
  lazer: [
    'CINEMA', 'STREAMING', 'DECATHLON', 'ACADEMIA', 'OMEGA'
  ],
  pessoal: [
    'ROUPA', 'CABELO', 'BELEZA', 'PERFUME', 'HIGIENE', 'MAGALU',
    'UNIAO', 'LOJA'
  ],
  doacao: [
    'IGREJA', 'CARIDADE', 'PIX TRANSF IGREJA'
  ]
};

function readJSON(path) {
  try {
    return JSON.parse(fs.readFileSync(path, 'utf8'));
  } catch (err) {
    console.error(`Erro lendo ${path}:`, err.message);
    return null;
  }
}

function writeJSON(path, data) {
  try {
    fs.writeFileSync(path, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error(`Erro escrevendo ${path}:`, err.message);
    return false;
  }
}

function normalizarDescricao(descricao) {
  return (descricao || '').toUpperCase().trim();
}

function identificarPessoa(descricao) {
  const desc = normalizarDescricao(descricao);

  for (const pattern of JULIANE_PATTERNS) {
    if (desc.includes(pattern)) {
      return 'Juliane';
    }
  }

  for (const pattern of HUGO_PATTERNS) {
    if (desc.includes(pattern)) {
      return 'Hugo';
    }
  }

  return 'Ambos';
}

function identificarCategoria(descricao) {
  const desc = normalizarDescricao(descricao);

  for (const [categoria, patterns] of Object.entries(CATEGORIA_PATTERNS)) {
    for (const pattern of patterns) {
      if (desc.includes(pattern)) {
        return categoria;
      }
    }
  }

  return null;
}

function gerarID() {
  return 'txn_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function parsearCSV(conteudo) {
  const linhas = conteudo.trim().split('\n');
  if (linhas.length < 2) {
    throw new Error('CSV deve ter cabeçalho e pelo menos uma linha de dados');
  }

  const cabecalho = linhas[0].split(',').map(h => h.trim().toLowerCase());
  const transacoes = [];

  for (let i = 1; i < linhas.length; i++) {
    const valores = linhas[i].split(',').map(v => v.trim());
    if (valores.length < 3) continue;

    const obj = {};
    cabecalho.forEach((col, idx) => {
      obj[col] = valores[idx];
    });

    // Mapear colunas comuns
    const data = obj.data || obj.date || obj.data_transacao || '';
    const descricao = obj.descricao || obj.description || obj.desc || '';
    const valor = parseFloat(obj.valor || obj.value || obj.amount || '0');

    if (!descricao || !data || !valor) {
      console.warn(`⚠️  Linha ${i} incompleta, pulando...`);
      continue;
    }

    transacoes.push({
      data: data.trim(),
      descricao: descricao.trim(),
      valor: valor,
      tipo: valor > 0 ? 'entrada' : 'saida'
    });
  }

  return transacoes;
}

function importarTransacoes(arquivoPath) {
  console.log(`\n=== IMPORTADOR DE CARTÃO DE CRÉDITO ===\n`);
  console.log(`Lendo arquivo: ${arquivoPath}\n`);

  // Ler arquivo
  let conteudo;
  try {
    conteudo = fs.readFileSync(arquivoPath, 'utf8');
  } catch (err) {
    console.error(`Erro lendo arquivo: ${err.message}`);
    process.exit(1);
  }

  // Determinar formato
  let transacoesImportadas = [];

  try {
    if (arquivoPath.endsWith('.json')) {
      const dados = JSON.parse(conteudo);
      transacoesImportadas = dados.transacoes || dados.fluxo_mensal?.transacoes || [dados];
    } else {
      transacoesImportadas = parsearCSV(conteudo);
    }
  } catch (err) {
    console.error(`Erro ao processar arquivo: ${err.message}`);
    process.exit(1);
  }

  if (transacoesImportadas.length === 0) {
    console.log('Nenhuma transação encontrada no arquivo');
    process.exit(0);
  }

  console.log(`Total de transações encontradas: ${transacoesImportadas.length}\n`);

  // Ler dados existentes
  const financeiro = readJSON(FINANCEIRO_PATH);
  const classificacoes = readJSON(CLASSIFICACOES_PATH);

  if (!financeiro) {
    console.error('Erro: financeiro.json não encontrado');
    process.exit(1);
  }

  // Garantir estrutura
  if (!financeiro.fluxo_mensal) {
    financeiro.fluxo_mensal = { transacoes: [] };
  }
  if (!financeiro.fluxo_mensal.transacoes) {
    financeiro.fluxo_mensal.transacoes = [];
  }

  // Classificar e adicionar transações importadas
  const transacoesProcessadas = [];
  let totalClassificadas = 0;
  let totalSemClassificacao = 0;

  transacoesImportadas.forEach((txn, idx) => {
    // Garantir estrutura
    const novaTransacao = {
      id: txn.id || gerarID(),
      data: txn.data,
      tipo: txn.tipo || 'saida',
      descricao: txn.descricao,
      valor: txn.valor,
      pessoa: txn.pessoa || identificarPessoa(txn.descricao),
      categoria: txn.categoria || identificarCategoria(txn.descricao),
      conta_origem: txn.conta_origem || 'Cartão de Crédito',
      conta_destino: txn.conta_destino || 'Comerciante',
      status: txn.status || 'confirmado',
      origem: 'importacao',
      hash: txn.hash || `cc_${Date.now()}_${idx}`
    };

    if (novaTransacao.categoria) {
      console.log(`[${idx + 1}] ✅ ${novaTransacao.descricao} → ${novaTransacao.categoria} (${novaTransacao.pessoa})`);
      totalClassificadas++;
    } else {
      console.log(`[${idx + 1}] ⚠️  ${novaTransacao.descricao} - SEM CLASSIFICAÇÃO`);
      totalSemClassificacao++;
    }

    transacoesProcessadas.push(novaTransacao);
  });

  // Mesclar com dados existentes
  const transacoesAntes = financeiro.fluxo_mensal.transacoes.length;
  financeiro.fluxo_mensal.transacoes.push(...transacoesProcessadas);

  // Salvar
  if (writeJSON(FINANCEIRO_PATH, financeiro)) {
    console.log(`\n✅ Dados salvos com sucesso!\n`);
  } else {
    console.error('\n❌ Erro ao salvar dados\n');
    process.exit(1);
  }

  // Relatório
  console.log('=== RELATÓRIO DE IMPORTAÇÃO ===');
  console.log(`Transações importadas: ${transacoesProcessadas.length}`);
  console.log(`Total anterior: ${transacoesAntes}`);
  console.log(`Total agora: ${financeiro.fluxo_mensal.transacoes.length}`);
  console.log(`Classificadas: ${totalClassificadas}`);
  console.log(`Sem classificação: ${totalSemClassificacao}`);
  console.log(`Taxa de cobertura: ${((totalClassificadas / transacoesProcessadas.length) * 100).toFixed(1)}%\n`);

  return {
    importadas: transacoesProcessadas.length,
    classificadas: totalClassificadas,
    semClassificacao: totalSemClassificacao
  };
}

// CLI
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log('Uso: node importador-cc.js <arquivo.csv|arquivo.json>');
    console.log('\nExemplo:');
    console.log('  node importador-cc.js transacoes.csv');
    console.log('  node importador-cc.js cartao_credito.json');
    console.log('\nFormato CSV esperado:');
    console.log('  data,descricao,valor');
    console.log('  2026-08-01,SUPER MERCADO,50.00');
    console.log('  2026-08-02,UBER,35.50');
    process.exit(1);
  }

  const arquivo = args[0];
  importarTransacoes(arquivo);
}

module.exports = { importarTransacoes, parsearCSV };
