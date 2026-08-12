const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3001;

app.use(bodyParser.json());
app.use(cors());
app.use(express.static('public'));

const FINANCEIRO_PATH = path.join(__dirname, 'data', 'financeiro.json');
const APONTAMENTOS_PATH = path.join(__dirname, 'data', 'apontamentos.json');
const CLASSIFICACOES_PATH = path.join(__dirname, 'data', 'classificacoes.json');

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

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const server = app.listen(PORT, '0.0.0.0', () => {
  console.log(`Dashboard Financeiro rodando em porta ${PORT}`);
});
