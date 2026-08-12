# Conversor XLS/XLSX para CSV

Robô para converter automaticamente seus arquivos Excel (XLS, XLSX, XLSM) para CSV.

## 📋 Requisitos

- **Python 3.7+** ([Baixar](https://www.python.org/downloads/))
- Windows 10/11 ou superior

## ⚡ Instalação Rápida

### 1️⃣ Instalação do Python

Se ainda não tem Python instalado:

1. Acesse [python.org/downloads](https://www.python.org/downloads/)
2. Baixe a versão mais recente (Python 3.11+)
3. **Importante**: Marque a opção "Add Python to PATH" durante a instalação
4. Clique em "Install Now"

### 2️⃣ Instalação das Dependências

Abra o Prompt de Comando (CMD) ou PowerShell na pasta do conversor e execute:

```bash
pip install -r requirements_converter.txt
```

Ou execute o script `converter.bat` que faz isso automaticamente.

## 🚀 Como Usar

### Opção 1: Executar via Batch (Mais Fácil)

Simplesmente clique duas vezes em:

```
converter.bat
```

O script vai:
- Verificar se Python está instalado
- Instalar/atualizar dependências
- Converter todos os arquivos Excel da pasta `C:\Users\Juliane\OneDrive\Documentos\Itaú`
- Mostrar um resumo das conversões
- Manter a janela aberta para visualizar o resultado

### Opção 2: Executar via PowerShell

Abra PowerShell na pasta do conversor e execute:

```powershell
# Converte todos os arquivos
.\converter.ps1

# Converte um arquivo específico
.\converter.ps1 -Action convert -File arquivo.xlsx

# Agenda conversão automática diária (às 6 da manhã)
.\converter.ps1 -Action schedule
```

### Opção 3: Executar via Prompt de Comando

```bash
# Converte todos
python xlsx_to_csv_converter.py

# Converte um arquivo
python xlsx_to_csv_converter.py --single arquivo.xlsx

# Mostra ajuda
python xlsx_to_csv_converter.py --help
```

### Opção 4: Linha de Comando com Argumentos

```bash
# Converte todos e salva log
python xlsx_to_csv_converter.py > conversao.log 2>&1

# Executa com Python diretamente
python -u xlsx_to_csv_converter.py
```

## 📁 Como Funciona

```
C:\Users\Juliane\OneDrive\Documentos\Itaú\
├── arquivo1.xlsx          ──→  arquivo1.csv
├── arquivo2.xlsx          ──→  arquivo2.csv
├── relatorio.xlsx (5 abas)  ──→  relatorio.csv
│                            ──→  relatorio_Aba2.csv
│                            ──→  relatorio_Aba3.csv
│                            ──→  relatorio_Aba4.csv
│                            ──→  relatorio_Aba5.csv
└── subpasta/
    └── arquivo3.xls       ──→  arquivo3.csv
```

### Características:

✅ **Detecta automaticamente** todos os arquivos Excel (XLS, XLSX, XLSM)
✅ **Converte múltiplas abas** - cada aba vira um CSV separado
✅ **Preserva codificação UTF-8** com BOM (caracteres especiais funcionam corretamente)
✅ **Ignora arquivos temporários** (que começam com `~`)
✅ **Gera log completo** de todas as operações (`converter_log.txt`)
✅ **Mantém a estrutura** - CSVs são salvos na mesma pasta que os Excel

## 📊 Exemplos de Saída

### Arquivo com uma aba:
```
entrada: extrato_completo.xlsx
saída:   extrato_completo.csv
```

### Arquivo com múltiplas abas:
```
entrada: planejamento.xlsx (abas: Receita, Despesa, Resumo)
saída:   planejamento.csv
         planejamento_Receita.csv
         planejamento_Despesa.csv
         planejamento_Resumo.csv
```

## 🤖 Agendamento Automático Diário

Para que o conversor execute **automaticamente todo dia** às 6 da manhã:

### Via PowerShell:

```powershell
.\converter.ps1 -Action schedule
```

Para cancelar o agendamento, abra o Agendador de Tarefas do Windows e delete a tarefa "Conversor XLS para CSV - Itaú".

### Manualmente (Agendador de Tarefas):

1. Pressione `Win + R` e digite: `taskschd.msc`
2. Clique em "Criar Tarefa Básica"
3. Nome: `Conversor XLS para CSV`
4. Gatilho: Diário, 06:00
5. Ação: Iniciar programa
   - Programa: `C:\Windows\System32\cmd.exe`
   - Argumentos: `/c "C:\caminho\para\converter.bat"`

## 📋 Log de Operações

Toda conversão gera um arquivo `converter_log.txt` com:
- Data e hora de cada operação
- Arquivos convertidos com sucesso
- Erros encontrados
- Número total de conversões

Exemplo de log:
```
2024-08-12 10:15:32 - INFO - Encontrados 3 arquivo(s) Excel
2024-08-12 10:15:32 - INFO - Iniciando conversão de 3 arquivo(s)...
2024-08-12 10:15:33 - INFO - ✓ Convertido: extrato.xlsx → extrato.csv
2024-08-12 10:15:34 - INFO - ✓ Convertido: orcamento.xlsx → orcamento.csv
2024-08-12 10:15:35 - INFO - ✓ Convertido: planejamento.xlsx → planejamento.csv
```

## ❌ Solução de Problemas

### "Python não encontrado"
- Verifique se Python foi instalado com "Add to PATH" marcado
- Reinicie o computador após instalar Python
- Tente: `python --version` no CMD para verificar

### "ModuleNotFoundError: No module named 'openpyxl'"
- Execute: `pip install openpyxl pandas`
- Ou simplesmente execute `converter.bat` que instala automaticamente

### Arquivo com erro ao converter
- Verifique se o arquivo não está aberto em outro programa
- Verifique se não é um arquivo corrompido
- Tente abrir o arquivo no Excel e salvar novamente

### Encodng/Caracteres especiais incorretos
- O conversor salva com `UTF-8 com BOM` por padrão
- Se precisar de outro encoding, edite a linha no script:
  ```python
  df.to_csv(csv_path, index=False, encoding='utf-8-sig')
  ```

## 🔧 Personalizações

### Alterar pasta de origem:

Edite `xlsx_to_csv_converter.py`, linha 123:
```python
itau_folder = r"C:\Novo\Caminho\Aqui"
```

### Mudar horário do agendamento:

No script `converter.ps1`, altere a linha:
```powershell
$taskTime = "06:00"  # Mude para o horário desejado
```

### Ignorar múltiplas abas:

Na linha de comando:
```bash
python xlsx_to_csv_converter.py  # Converte todas as abas
```

Para converter apenas a primeira aba, edite o script ou crie um wrapper.

## 📝 Estrutura dos Arquivos

```
MGD-Benetti/
├── xlsx_to_csv_converter.py          # Script principal
├── requirements_converter.txt         # Dependências Python
├── converter.bat                      # Script Batch (Windows)
├── converter.ps1                      # Script PowerShell (Windows)
├── CONVERTER_README.md               # Este arquivo
└── converter_log.txt                 # Log de operações (gerado automaticamente)
```

## 🎯 Próximos Passos

1. ✅ Copie os arquivos para uma pasta fácil de acessar
2. ✅ Execute `converter.bat` para fazer a primeira conversão
3. ✅ Verifique os CSVs gerados
4. ✅ (Opcional) Configure o agendamento automático
5. ✅ Verifique o `converter_log.txt` para confirmar tudo funcionou

## 💡 Dicas

- Coloque um atalho de `converter.bat` na área de trabalho para fácil acesso
- Revise o `converter_log.txt` periodicamente para garantir que as conversões estão funcionando
- Se houver muitos arquivos, a primeira conversão pode levar alguns minutos
- O script é seguro - não delete os arquivos originais (XLS/XLSX)

## 📞 Suporte

Se encontrar problemas:

1. Verifique o `converter_log.txt` para detalhes do erro
2. Confirme que o arquivo Excel não está aberto
3. Tente converter um arquivo manualmente: `python xlsx_to_csv_converter.py --single arquivo.xlsx`
4. Verifique se Python e as dependências estão corretamente instaladas

---

**Versão**: 1.0  
**Última atualização**: 2024-08-12  
**Compatibilidade**: Python 3.7+, Windows 10/11
