const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = 3001;
const DATA_FILE = path.join(__dirname, 'data', 'financeiro.json');

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Garantir diretório de dados
if (!fs.existsSync(path.join(__dirname, 'data'))) {
  fs.mkdirSync(path.join(__dirname, 'data'), { recursive: true });
}

// Estrutura padrão de dados
const DEFAULT_DATA = {
  updatedAt: new Date().toISOString(),
  pessoa: {
    juliane: {
      nome: 'Juliane Benetti',
      empresa: 'Elektro Redes S.A.',
      cargo: 'Analista',
      salarioLiquido: 3500,
      cidade: 'Campinas'
    },
    hugo: {
      nome: 'Hugo',
      profissao: 'Taxista',
      rendaLiquida: 2350,
      observacao: 'Renda descontado combustivel'
    }
  },
  contas: {
    saldoAtual: 5587,
    dataAtualizacao: '2026-08-09'
  },
  dividas: {
    consignadosFolha: {
      total: 52084,
      parcelas: [
        { nome: 'Econsignado 1', saldo: 28152, parcelaMensal: 676 },
        { nome: 'Econsignado 2', saldo: 14762, parcelaMensal: 634 },
        { nome: 'Econsignado 3', saldo: 9170, parcelaMensal: 254 }
      ]
    },
    consignadoContaCorrente: {
      saldo: 28743,
      parcelaMensal: 1403,
      parcelaAtual: 32,
      totalParcelas: 60
    },
    emprestimoFamiliar: {
      nome: 'Cenira',
      saldo: 23252,
      parcelaMensal: 646,
      totalParcelas: 36
    },
    cartoes: {
      black: { saldo: 5692, limite: 15000 },
      azul: { saldo: 0, uso: 'negócio' },
      infinite: { saldo: 0, uso: 'negócio' }
    },
    mercadoPago: {
      saldo: 11057,
      parcelaMensal: 1943,
      parcelaAtual: 1,
      totalParcelas: 6
    }
  },
  despesas: {
    fixas: [
      { categoria: 'Escola Valentina', valor: 1249, dia: 10 },
      { categoria: 'Escola Luca', valor: 546, dia: 15 },
      { categoria: 'Van escolar', valor: 480, dia: 28 },
      { categoria: 'Condomínio', valor: 623, dia: 10 },
      { categoria: 'CPFL energia', valor: 146, dia: 15 },
      { categoria: 'SANASA água', valor: 142, dia: 15 },
      { categoria: 'Claro internet', valor: 145, dia: 5 },
      { categoria: 'Celular', valor: 74, dia: 20 },
      { categoria: 'APE Lockers', valor: 223, dia: 25 },
      { categoria: 'DAS MEI', valor: 87, dia: 20 },
      { categoria: 'Edileia (vaga)', valor: 200, dia: 12 },
      { categoria: 'Nilza (faxina)', valor: 150, dia: 18 }
    ]
  },
  cenarios: []
};

// GET - Carregar dados
app.get('/api/dados', (req, res) => {
  try {
    if (fs.existsSync(DATA_FILE)) {
      const dados = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
      const merged = {
        ...DEFAULT_DATA,
        pessoa: { ...DEFAULT_DATA.pessoa, ...dados.pessoa },
        despesas: { ...DEFAULT_DATA.despesas, ...dados.despesas },
        receitas: dados.receitas || DEFAULT_DATA.receitas,
        investimentos: dados.investimentos || DEFAULT_DATA.investimentos,
        contas: { ...DEFAULT_DATA.contas, ...dados.contas },
        dividas: { ...DEFAULT_DATA.dividas, ...dados.dividas },
        lastUpdated: dados.lastUpdated || new Date().toISOString()
      };
      res.json(merged);
    } else {
      // Se não existir, retorna padrão
      res.json(DEFAULT_DATA);
    }
  } catch (error) {
    console.error('Erro ao carregar dados:', error);
    res.status(500).json({ error: 'Erro ao carregar dados' });
  }
});

// POST - Salvar dados
app.post('/api/dados', (req, res) => {
  try {
    const dados = req.body;
    dados.updatedAt = new Date().toISOString();

    fs.writeFileSync(DATA_FILE, JSON.stringify(dados, null, 2), 'utf8');
    res.json({ success: true, message: 'Dados salvos com sucesso', data: dados });
  } catch (error) {
    console.error('Erro ao salvar dados:', error);
    res.status(500).json({ error: 'Erro ao salvar dados' });
  }
});

// PUT - Atualizar seção específica
app.put('/api/dados/:secao', (req, res) => {
  try {
    const { secao } = req.params;
    const novosDados = req.body;

    let dados = DEFAULT_DATA;
    if (fs.existsSync(DATA_FILE)) {
      dados = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    }

    // Atualizar seção específica (ex: /api/dados/contas)
    if (secao in dados) {
      dados[secao] = { ...dados[secao], ...novosDados };
    } else {
      dados[secao] = novosDados;
    }

    dados.updatedAt = new Date().toISOString();
    fs.writeFileSync(DATA_FILE, JSON.stringify(dados, null, 2), 'utf8');
    res.json({ success: true, message: `Seção '${secao}' atualizada`, data: dados });
  } catch (error) {
    console.error('Erro ao atualizar dados:', error);
    res.status(500).json({ error: 'Erro ao atualizar dados' });
  }
});

// DELETE - Resetar dados
app.delete('/api/dados/reset', (req, res) => {
  try {
    fs.writeFileSync(DATA_FILE, JSON.stringify(DEFAULT_DATA, null, 2), 'utf8');
    res.json({ success: true, message: 'Dados resetados', data: DEFAULT_DATA });
  } catch (error) {
    console.error('Erro ao resetar dados:', error);
    res.status(500).json({ error: 'Erro ao resetar dados' });
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`💰 Servidor financeiro rodando em http://localhost:${PORT}`);
  console.log(`📁 Dados armazenados em: ${DATA_FILE}`);
});
