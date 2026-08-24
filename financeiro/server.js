const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3001;

// financeiro.json sozinho já passa de 2MB, bem acima do limite padrão do
// body-parser (100kb) — todo POST de /api/dados vinha voltando 413 e a
// edição feita na tela nunca era gravada, silenciosamente (Juliane, 24/08).
app.use(bodyParser.json({ limit: '20mb' }));
app.use(cors());
app.use(express.static('public'));

const FINANCEIRO_PATH = path.join(__dirname, 'data', 'financeiro.json');
const APONTAMENTOS_PATH = path.join(__dirname, 'data', 'apontamentos.json');
const CLASSIFICACOES_PATH = path.join(__dirname, 'data', 'classificacoes.json');
const CONFIGURACOES_PATH = path.join(__dirname, 'data', 'configuracoes.json');
const CARGAS_PATH = path.join(__dirname, 'data', 'cargas.json');

function readFinanceiro() {
  try {
    if (!fs.existsSync(FINANCEIRO_PATH)) {
      return null;
    }
    return JSON.parse(fs.readFileSync(FINANCEIRO_PATH, 'utf8'));
  } catch (err) {
    console.error('Erro lendo financeiro.json:', err);
    return null;
  }
}

function writeFinanceiro(data) {
  try {
    fs.writeFileSync(FINANCEIRO_PATH, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Erro escrevendo financeiro.json:', err);
    return false;
  }
}

function readApontamentos() {
  try {
    if (!fs.existsSync(APONTAMENTOS_PATH)) {
      return [];
    }
    return JSON.parse(fs.readFileSync(APONTAMENTOS_PATH, 'utf8'));
  } catch (err) {
    console.error('Erro lendo apontamentos.json:', err);
    return [];
  }
}

function writeApontamentos(data) {
  try {
    fs.writeFileSync(APONTAMENTOS_PATH, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Erro escrevendo apontamentos.json:', err);
    return false;
  }
}

function readClassificacoes() {
  try {
    if (!fs.existsSync(CLASSIFICACOES_PATH)) {
      return null;
    }
    return JSON.parse(fs.readFileSync(CLASSIFICACOES_PATH, 'utf8'));
  } catch (err) {
    console.error('Erro lendo classificacoes.json:', err);
    return null;
  }
}

function writeClassificacoes(data) {
  try {
    fs.writeFileSync(CLASSIFICACOES_PATH, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Erro escrevendo classificacoes.json:', err);
    return false;
  }
}

function readConfiguracoes() {
  try {
    if (!fs.existsSync(CONFIGURACOES_PATH)) {
      return null;
    }
    return JSON.parse(fs.readFileSync(CONFIGURACOES_PATH, 'utf8'));
  } catch (err) {
    console.error('Erro lendo configuracoes.json:', err);
    return null;
  }
}

function writeConfiguracoes(data) {
  try {
    fs.writeFileSync(CONFIGURACOES_PATH, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Erro escrevendo configuracoes.json:', err);
    return false;
  }
}

function readCargas() {
  try {
    if (!fs.existsSync(CARGAS_PATH)) {
      return { cargas: [] };
    }
    return JSON.parse(fs.readFileSync(CARGAS_PATH, 'utf8'));
  } catch (err) {
    console.error('Erro lendo cargas.json:', err);
    return { cargas: [] };
  }
}

function writeCargas(data) {
  try {
    fs.writeFileSync(CARGAS_PATH, JSON.stringify(data, null, 2), 'utf8');
    return true;
  } catch (err) {
    console.error('Erro escrevendo cargas.json:', err);
    return false;
  }
}

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/api/dados', (req, res) => {
  const dados = readFinanceiro();
  if (dados) {
    res.json(dados);
  } else {
    res.status(404).json({ error: 'Dados não encontrados' });
  }
});

app.post('/api/dados', (req, res) => {
  const dados = req.body;
  if (writeFinanceiro(dados)) {
    res.json({ success: true, message: 'Dados salvos com sucesso' });
  } else {
    res.status(500).json({ error: 'Erro ao salvar dados' });
  }
});

app.get('/api/apontamentos', (req, res) => {
  const apontamentos = readApontamentos();
  res.json(apontamentos);
});

app.post('/api/apontamentos', (req, res) => {
  const apontamentos = readApontamentos();
  const novo = {
    id: Date.now().toString(),
    texto: req.body.texto,
    data: new Date().toISOString(),
    confirmada: false
  };
  apontamentos.push(novo);
  if (writeApontamentos(apontamentos)) {
    res.json(novo);
  } else {
    res.status(500).json({ error: 'Erro ao criar apontamento' });
  }
});

app.post('/api/apontamentos/:id/confirmar', (req, res) => {
  const apontamentos = readApontamentos();
  const ap = apontamentos.find(a => a.id === req.params.id);
  if (ap) {
    ap.confirmada = true;
    if (writeApontamentos(apontamentos)) {
      res.json(ap);
    } else {
      res.status(500).json({ error: 'Erro ao confirmar apontamento' });
    }
  } else {
    res.status(404).json({ error: 'Apontamento não encontrado' });
  }
});

app.delete('/api/apontamentos/:id', (req, res) => {
  const apontamentos = readApontamentos();
  const filtered = apontamentos.filter(a => a.id !== req.params.id);
  if (writeApontamentos(filtered)) {
    res.json({ success: true });
  } else {
    res.status(500).json({ error: 'Erro ao deletar apontamento' });
  }
});

app.get('/api/classificacoes', (req, res) => {
  const classificacoes = readClassificacoes();
  if (classificacoes) {
    res.json(classificacoes);
  } else {
    res.status(404).json({ error: 'Classificações não encontradas' });
  }
});

app.post('/api/classificacoes', (req, res) => {
  const classificacoes = req.body;
  if (writeClassificacoes(classificacoes)) {
    res.json({ success: true, message: 'Classificações salvas com sucesso' });
  } else {
    res.status(500).json({ error: 'Erro ao salvar classificações' });
  }
});

app.get('/api/configuracoes', (req, res) => {
  const configuracoes = readConfiguracoes();
  if (configuracoes) {
    res.json(configuracoes);
  } else {
    res.status(404).json({ error: 'Configurações não encontradas' });
  }
});

app.post('/api/configuracoes', (req, res) => {
  const configuracoes = req.body;
  if (writeConfiguracoes(configuracoes)) {
    res.json({ success: true, message: 'Configurações salvas com sucesso' });
  } else {
    res.status(500).json({ error: 'Erro ao salvar configurações' });
  }
});

app.post('/api/importar-dados', (req, res) => {
  try {
    const { fluxo_mensal } = req.body;

    if (!fluxo_mensal || !fluxo_mensal.transacoes || !Array.isArray(fluxo_mensal.transacoes)) {
      return res.status(400).json({ error: 'Formato de importação inválido' });
    }

    const financeiro = readFinanceiro();
    if (!financeiro.fluxo_mensal) {
      financeiro.fluxo_mensal = { transacoes: [] };
    }
    if (!financeiro.fluxo_mensal.transacoes) {
      financeiro.fluxo_mensal.transacoes = [];
    }

    const novasTransacoes = fluxo_mensal.transacoes;
    const transacoesAntes = financeiro.fluxo_mensal.transacoes.length;

    financeiro.fluxo_mensal.transacoes.push(...novasTransacoes);

    if (writeFinanceiro(financeiro)) {
      res.json({
        success: true,
        message: `${novasTransacoes.length} transações importadas com sucesso`,
        imported: novasTransacoes.length,
        total_transacoes: financeiro.fluxo_mensal.transacoes.length
      });
    } else {
      res.status(500).json({ error: 'Erro ao salvar transações importadas' });
    }
  } catch (err) {
    console.error('Erro na importação:', err);
    res.status(500).json({ error: 'Erro ao processar importação: ' + err.message });
  }
});

app.get('/api/cargas', (req, res) => {
  const cargas = readCargas();
  res.json(cargas);
});

app.post('/api/cargas', (req, res) => {
  const { tipoArquivo, quantidadeRegistros, transacaoIds } = req.body;

  if (!tipoArquivo || !quantidadeRegistros || !Array.isArray(transacaoIds)) {
    return res.status(400).json({ error: 'Dados de carga inválidos' });
  }

  const cargas = readCargas();
  const cargaId = `carga_${Date.now()}`;

  const novaCarga = {
    id: cargaId,
    data_importacao: new Date().toISOString(),
    tipo_arquivo: tipoArquivo,
    quantidade_registros: quantidadeRegistros,
    status: 'ativa',
    transacoes_ids: transacaoIds
  };

  cargas.cargas.push(novaCarga);

  if (writeCargas(cargas)) {
    res.json({ success: true, carga: novaCarga });
  } else {
    res.status(500).json({ error: 'Erro ao registrar carga' });
  }
});

app.delete('/api/cargas/:cargaId', (req, res) => {
  const cargaId = req.params.cargaId;
  const cargas = readCargas();
  const financeiro = readFinanceiro();

  const carga = cargas.cargas.find(c => c.id === cargaId);
  if (!carga) {
    return res.status(404).json({ error: 'Carga não encontrada' });
  }

  if (!financeiro.fluxo_mensal || !financeiro.fluxo_mensal.transacoes) {
    return res.status(400).json({ error: 'Nenhuma transação para remover' });
  }

  // Remover transações dessa carga
  const transacoesAntes = financeiro.fluxo_mensal.transacoes.length;
  financeiro.fluxo_mensal.transacoes = financeiro.fluxo_mensal.transacoes.filter(
    txn => txn.carga_id !== cargaId
  );
  const removidas = transacoesAntes - financeiro.fluxo_mensal.transacoes.length;

  // Marcar carga como deletada
  carga.status = 'deletada';

  if (writeCargas(cargas) && writeFinanceiro(financeiro)) {
    res.json({
      success: true,
      message: `${removidas} transações removidas`,
      removidas
    });
  } else {
    res.status(500).json({ error: 'Erro ao deletar carga' });
  }
});

// A aba Reconciliação buscava /data/totais_esperados.json, caminho que nunca
// foi servido (só 'public' é estático), então a aba nunca funcionou.
app.get('/api/totais-esperados', (req, res) => {
  const caminho = path.join(__dirname, 'data', 'totais_esperados.json');
  try {
    if (!fs.existsSync(caminho)) {
      return res.json({ faturas: {} });
    }
    res.json(JSON.parse(fs.readFileSync(caminho, 'utf8')));
  } catch (err) {
    console.error('Erro lendo totais_esperados.json:', err);
    res.status(500).json({ error: 'Erro ao ler totais esperados' });
  }
});

app.get('/api/regras-irpf', (req, res) => {
  const caminho = path.join(__dirname, 'data', 'regras-irpf.json');
  try {
    if (!fs.existsSync(caminho)) {
      return res.status(404).json({ error: 'Regras do IRPF não cadastradas' });
    }
    res.json(JSON.parse(fs.readFileSync(caminho, 'utf8')));
  } catch (err) {
    console.error('Erro lendo regras-irpf.json:', err);
    res.status(500).json({ error: 'Erro ao ler as regras do IRPF' });
  }
});

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`Dashboard Financeiro rodando em porta ${PORT}`);
});
