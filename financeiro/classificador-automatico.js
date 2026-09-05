#!/usr/bin/env node
/**
 * Classificador Automático de Transações - AfiliDash Financeiro
 *
 * Classifica transações com base em padrões conhecidos e regras de negócio
 * Salva automaticamente as mudanças no financeiro.json
 */

const fs = require('fs');
const path = require('path');

const FINANCEIRO_PATH = path.join(__dirname, 'data', 'financeiro.json');
const CLASSIFICACOES_PATH = path.join(__dirname, 'data', 'classificacoes.json');

// Padrões de Juliane (pessoal/negócio)
const JULIANE_PATTERNS = [
  'ELEKTRO', 'MASTERCARD BLACK', 'APPLE', 'SPOTIFY',
  'GOOGLE ONE', 'KIWIFY', 'UNIAO', 'MAGALU', '99APP',
  '99RIDE', 'BENETTI', 'MGD', 'DONA TEREZINHA', 'INSTAMAGIC'
];

// Padrões de Hugo (transporte/alimentação)
const HUGO_PATTERNS = [
  'COMBUSTIVEL', 'POSTO', 'AUTO PEÇA', 'TOKIO MARINE',
  'SEGURO CARRO', 'SAVEGNAGO', 'SUPERMERCADOS JL',
  'MARCIA DE CARLA'
];

// Padrões genéricos de categoria
const CATEGORIA_PATTERNS = {
  alimentacao: [
    'MERCADO', 'SUPER', 'PADARIA', 'RESTAUR', 'LANCHON',
    'PIZZARIA', 'AÇAI', 'CAFE', 'DONA TERE', 'MARCIA',
    'SAVEGNAGO', 'JL'
  ],
  transporte: [
    'COMBUSTIVEL', 'UBER', '99', 'TAXI', 'POSTO',
    'AUTO PEÇA', 'SEGURO', 'TOKIO', 'UBER'
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
    'DROGAL', 'ORTODONTIA', 'CLINICA', 'HOSPITAL'
  ],
  educacao: [
    'ESCOLA', 'CURSO', 'VAN', 'KIWIFY', 'UDEMY',
    'LIVRO', 'EDUCACAO'
  ],
  lazer: [
    'CINEMA', 'STREAMING', 'SPOTIFY', 'NETFLIX',
    'DECATHLON', 'ACADEMIA', 'OMEGA', 'CLUBE'
  ],
  pessoal: [
    'ROUPA', 'CABELO', 'BELEZA', 'PERFUME', 'HIGIENE',
    'MAGALU', 'UNIAO', 'CAMISETA'
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

  // Verificar padrões conhecidos de Juliane
  for (const pattern of JULIANE_PATTERNS) {
    if (desc.includes(pattern)) {
      return 'Juliane';
    }
  }

  // Verificar padrões conhecidos de Hugo
  for (const pattern of HUGO_PATTERNS) {
    if (desc.includes(pattern)) {
      return 'Hugo';
    }
  }

  // Padrão genérico - se for combustível/posto, é Hugo
  if (desc.includes('COMBUSTIVEL') || desc.includes('POSTO')) {
    return 'Hugo';
  }

  // Se for compra de supermercado/alimentação genérica, precisa de contexto
  if (desc.includes('SUPER') || desc.includes('MERCADO')) {
    // Verificar pela pessoa padrão (Hugo compra mais)
    return 'Ambos';
  }

  return 'Ambos';
}

function identificarCategoria(descricao, pessoa) {
  const desc = normalizarDescricao(descricao);

  // Verificar cada padrão de categoria
  for (const [categoria, patterns] of Object.entries(CATEGORIA_PATTERNS)) {
    for (const pattern of patterns) {
      if (desc.includes(pattern)) {
        return categoria;
      }
    }
  }

  // Heurística por pessoa
  if (pessoa === 'Hugo') {
    if (desc.includes('COMBUSTIVEL') || desc.includes('POSTO')) {
      return 'transporte';
    }
    if (desc.includes('SUPER') || desc.includes('MERCADO')) {
      return 'alimentacao';
    }
  }

  if (pessoa === 'Juliane') {
    if (desc.includes('99') || desc.includes('UBER')) {
      return 'transporte';
    }
    if (desc.includes('APPLE') || desc.includes('SPOTIFY') || desc.includes('GOOGLE')) {
      return 'assinatura';
    }
  }

  // Padrões comuns a ambos
  if (desc.includes('ESCOLA') || desc.includes('VAN')) {
    return 'educacao';
  }
  if (desc.includes('FARMACIA') || desc.includes('MEDICO')) {
    return 'saude';
  }

  // Padrão por transação de débito
  if (desc.includes('TRANSFERENCIA') || desc.includes('PIX')) {
    // Verificar se tem padrão de categoria baseado no destinatário
    if (desc.includes('ESCOLA')) return 'educacao';
    if (desc.includes('UBER') || desc.includes('TAXI')) return 'transporte';
    return 'pessoal';
  }

  return null; // Sem categoria identificada
}

function verificarContraClassificacoesConhecidas(descricao, classificacoes) {
  const desc = normalizarDescricao(descricao);

  for (const [pattern, config] of Object.entries(classificacoes.descricoes_conhecidas)) {
    if (desc === normalizarDescricao(pattern) || desc.includes(normalizarDescricao(pattern))) {
      return {
        categoria: config.categoria,
        pessoa: config.pessoa,
        descricao_ref: config.descricao
      };
    }
  }

  return null;
}

function classificarTransacao(transacao, classificacoes) {
  // Se já tem classificação e pessoa, não modificar
  if (transacao.categoria && transacao.pessoa) {
    return { modificada: false };
  }

  let modificacoes = {};

  // 1. Primeiro, verificar contra classificações conhecidas
  const conhecida = verificarContraClassificacoesConhecidas(transacao.descricao, classificacoes);
  if (conhecida) {
    if (!transacao.categoria) {
      transacao.categoria = conhecida.categoria;
      modificacoes.categoria = conhecida.categoria;
    }
    if (!transacao.pessoa) {
      transacao.pessoa = conhecida.pessoa;
      modificacoes.pessoa = conhecida.pessoa;
    }
    return { modificada: true, modificacoes, origem: 'padrão_conhecido' };
  }

  // 2. Tentar identificar pessoa e categoria por heurística
  if (!transacao.pessoa) {
    transacao.pessoa = identificarPessoa(transacao.descricao);
    modificacoes.pessoa = transacao.pessoa;
  }

  if (!transacao.categoria) {
    const categoria = identificarCategoria(transacao.descricao, transacao.pessoa);
    if (categoria) {
      transacao.categoria = categoria;
      modificacoes.categoria = categoria;
    }
  }

  const modificada = Object.keys(modificacoes).length > 0;
  return {
    modificada,
    modificacoes: modificada ? modificacoes : null,
    origem: modificada ? 'heuristica' : null
  };
}

function executarClassificacao() {
  console.log('\n=== CLASSIFICADOR AUTOMÁTICO DE TRANSAÇÕES ===\n');

  // Ler dados
  const financeiro = readJSON(FINANCEIRO_PATH);
  const classificacoes = readJSON(CLASSIFICACOES_PATH);

  if (!financeiro) {
    console.error('Erro: financeiro.json não encontrado');
    process.exit(1);
  }
  if (!classificacoes) {
    console.error('Erro: classificacoes.json não encontrado');
    process.exit(1);
  }

  // Verificar transações
  if (!financeiro.fluxo_mensal || !financeiro.fluxo_mensal.transacoes) {
    console.log('Nenhuma transação encontrada para classificar');
    process.exit(0);
  }

  const transacoes = financeiro.fluxo_mensal.transacoes;
  console.log(`Total de transações: ${transacoes.length}\n`);

  // Classificar
  let totalClassificadas = 0;
  let totalSemClassificacao = 0;
  const relatorio = [];

  transacoes.forEach((txn, idx) => {
    const resultado = classificarTransacao(txn, classificacoes);

    if (resultado.modificada) {
      totalClassificadas++;
      const msg = `[${idx + 1}] ${txn.descricao} → ${resultado.modificacoes.categoria || 'N/A'} (${resultado.modificacoes.pessoa || 'N/A'})`;
      console.log(msg);
      relatorio.push({
        indice: idx + 1,
        descricao: txn.descricao,
        modificacoes: resultado.modificacoes,
        origem: resultado.origem
      });
    } else if (!txn.categoria) {
      totalSemClassificacao++;
      console.log(`[${idx + 1}] ⚠️  ${txn.descricao} - SEM CLASSIFICAÇÃO`);
    }
  });

  // Salvar dados atualizados
  if (totalClassificadas > 0) {
    if (writeJSON(FINANCEIRO_PATH, financeiro)) {
      console.log(`\n✅ Dados salvos com sucesso!\n`);
    } else {
      console.error('\n❌ Erro ao salvar dados\n');
    }
  }

  // Relatório final
  console.log('\n=== RELATÓRIO FINAL ===');
  console.log(`Total de transações: ${transacoes.length}`);
  console.log(`Transações classificadas nesta execução: ${totalClassificadas}`);
  console.log(`Transações ainda sem classificação: ${totalSemClassificacao}`);
  console.log(`Taxa de cobertura: ${((transacoes.length - totalSemClassificacao) / transacoes.length * 100).toFixed(1)}%\n`);

  if (totalSemClassificacao > 0) {
    console.log('Transações que precisam de classificação manual:');
    transacoes.forEach((txn, idx) => {
      if (!txn.categoria) {
        console.log(`  [${idx + 1}] ${txn.descricao}`);
      }
    });
    console.log('');
  }

  return {
    totalClassificadas,
    totalSemClassificacao,
    relatorio
  };
}

// Executar
if (require.main === module) {
  const resultado = executarClassificacao();
  process.exit(resultado.totalSemClassificacao > 0 ? 1 : 0);
}

module.exports = { executarClassificacao, classificarTransacao };
