# 📋 Fluxo de Alimentação de Dados - Dashboard Financeiro

## 🎯 Objetivo
Documentar o processo padrão para atualizar dados do dashboard financeiro através de extração de documentos bancários e confirmação do usuário.

---

## 📊 Processo Completo (5 Etapas)

### **Etapa 1: Você Envia os Documentos** 📁

Compartilhe conosco:

| Documento | Formato | Frequência | Prioridade |
|-----------|---------|-----------|-----------|
| **Extrato Bancário** | PDF (Itaú/BB/outro) | Mensal | 🔴 Alta |
| **Fatura Black Card** | PDF ou print | Mensal | 🔴 Alta |
| **Fatura Outros Cartões** | PDF (Azul, Infinite, etc) | Mensal | 🟡 Média |
| **Holerite** | PDF | Quando houver mudança | 🟡 Média |
| **Comprovantes** | Print/PDF | Conforme necessário | 🟢 Baixa |

**Exemplo de mensagem:**
```
"Oi Claude! Tenho aqui:
- Extrato Itaú agosto/2026 (PDF)
- Fatura Black Card agosto/2026 (PDF)
- Holerite de agosto (PDF - houve adiantamento)

Vocês conseguem atualizar o dashboard?"
```

---

### **Etapa 2: Eu Leio e Extraio os Dados** 🔍

O Claude vai:

1. ✅ Abrir cada PDF/imagem
2. ✅ Identificar **TODAS** as transações
3. ✅ Classificar cada uma:
   - **Entrada** (salário, renda, outros)
   - **Saída fixa** (dívidas, aluguel, escola)
   - **Saída variável** (alimentação, transporte, saúde)
4. ✅ Sinalizar itens **desconhecidos** ou **dúvidas**
5. ✅ Organizar em uma **listagem clara**

**Exemplo de extração:**

```
EXTRATO ITAÚ - AGOSTO 2026
═══════════════════════════════════════════════════════════

✅ ENTRADAS:
• 05/ago - Depósito Salário Juliane: +R$ 4.500,00
• 10/ago - PIX Hugo (renda): +R$ 2.050,00
→ Subtotal Entradas: +R$ 6.550,00

✅ SAÍDAS FIXAS:
• 01/ago - Consignado (folha): -R$ 1.564,00
• 05/ago - Aluguel: -R$ 1.254,00
• 10/ago - Escola infantil: -R$ 1.500,00
• 15/ago - Parcela Cenira: -R$ 646,00
→ Subtotal Fixas: -R$ 4.964,00

❓ SAÍDAS DESCONHECIDAS (CONFIRMAÇÃO NECESSÁRIA):
• 08/ago - PIX BENETTI: -R$ 200,00 (de quem? para quê?)
• 12/ago - HUB DO: -R$ 85,00 (assinatura? serviço?)
• 20/ago - Daniela: -R$ 150,00 (pessoal? trabalho?)
→ Subtotal Desconhecidas: -R$ 435,00

✅ SAÍDAS VARIÁVEIS:
• 03/ago - Supermercado: -R$ 350,00
• 07/ago - Farmácia: -R$ 120,00
• 14/ago - Transporte: -R$ 85,00
• 18/ago - Alimentação: -R$ 220,00
→ Subtotal Variáveis: -R$ 775,00

═══════════════════════════════════════════════════════════
RESUMO DO MÊS:
Entradas: +R$ 6.550,00
Saídas: -R$ 6.174,00
Saldo: +R$ 376,00
```

---

### **Etapa 3: Você Confirma os Itens em Dúvida** ✔️

Eu pergunto **item por item**:

```
Achei algumas transações que não entendi:

1️⃣ PIX BENETTI (08/ago): -R$ 200,00
   ➜ O que é? (Pessoa da família? Trabalho? Empréstimo?)

2️⃣ HUB DO (12/ago): -R$ 85,00
   ➜ Continua assinado? (Streaming? Software?)

3️⃣ Daniela (20/ago): -R$ 150,00
   ➜ Quem é? (Amiga? Colega? Categoria: Pessoal ou Trabalho?)

Por favor, confirme cada um para eu atualizar corretamente 👇
```

**Você responde:**
```
1. PIX BENETTI = Transferência para meu pai (Pessoal - Saída Variável)
2. HUB DO = Assinatura de um app de gerenciamento (Fixo - Serviço)
3. Daniela = Colega que paguei uma dívida (Pessoal - Saída Variável)
```

**Nota Importante:** Você **NUNCA precisa adivinhar** — se não tem certeza, a gente marca como "revisar depois" e segue com o resto! 🟡

---

### **Etapa 4: Eu Proponho as Atualizações** 📝

Antes de fazer QUALQUER mudança, eu listo:

**RESUMO DAS MUDANÇAS PROPOSTAS - AGOSTO 2026**
```
═══════════════════════════════════════════════════════════

📊 DADOS GLOBAIS QUE VÃOCHEAR:

Pessoas:
  • Juliane.salario: 4500 → 4500 (SEM MUDANÇA)
  • Hugo.renda: 2050 → 2050 (SEM MUDANÇA)

Receitas:
  • Total mensal: 6300 → 6550 (+R$ 250)

Dívidas:
  ✅ Black Card: 5692 → 4800 (REDUÇÃO -R$ 892)
  ✅ Consignado C/C: 28743 → 28097 (pagamento -R$ 646)
  ✅ Cenira: 23252 → 22606 (pagamento -R$ 646)

Despesas:
  • Necessidades: 5518 → 5518 (sem mudança)
  • Avaliar: 1208 → 1393 (+R$ 185 alimentação maior)
  • Parar: 166 → 251 (+R$ 85 novo HUB DO)

Novo histórico Black Card:
  • Agosto/2026: R$ 4.800 (adicionado ao gráfico)

═══════════════════════════════════════════════════════════

✅ TUDO CERTO? Confirma que devo salvar essas mudanças? 👇
```

---

### **Etapa 5: Você Confirma e eu Executo** ✅

Depois que você fala "tudo certo!" ou "sim, pode fazer":

1. ✅ Atualizo o arquivo `data/financeiro.json` do servidor
2. ✅ Dashboard atualiza **automaticamente em tempo real**
3. ✅ Todas as 5 abas refletem os novos dados
4. ✅ Você baixa backup do arquivo atualizado

**Resultado no Dashboard:**
- KPIs mudam
- Gráficos atualizam
- Timeline recalcula
- Cenários futuros ajustam

---

## 📋 CHECKLIST - Como Preparar sua Próxima Sessão

Antes de chamar o Claude para atualizar, tenha pronto:

- [ ] **Extrato bancário PDF** do mês (Itaú, BB, Nubank, etc)
- [ ] **Faturas de cartão PDF** (Black, Azul, etc)
- [ ] **Holerite PDF** se houve mudança salarial
- [ ] **Prints de tela** de qualquer transação desconhecida
- [ ] **Anotações pessoais** de despesas não bancárias (ex: dinheiro vivo)

**Exemplo de mensagem ideal:**
```
"Claude, tenho documentos para atualizar o dashboard:

Anexados:
1. Extrato_Itau_agosto_2026.pdf
2. Fatura_BlackCard_agosto_2026.pdf
3. Holerite_agosto_2026.pdf

Mudanças conhecidas:
- Tive adiantamento de R$ 500 no salário
- Cancelei assinatura de um serviço

Pode extrair os dados?"
```

---

## 🎯 Exemplos de Itens Que Você Deve Confirmar

| Transação | Por que preciso de confirmação? | Sua resposta esperada |
|-----------|----------------------------------|----------------------|
| **PIX para pessoa desconhecida** | Pode ser empréstimo, presente, trabalho? | "Empréstimo para meu pai" |
| **Novo serviço/assinatura** | Fixo ou variável? Continua? | "Sim, é fixo; cancelar em dezembro" |
| **Compra em valor alto** | Necessário ou discricionário? | "Compra de roupa, discricionário" |
| **Transação de app desconhecido** | Qual categoria? | "HUB DO é um app de gerenciamento, fixo" |
| **Transferência entre contas** | É entrada/saída real ou just transferência? | "É só transferência Itaú→CC" |

---

## 🔄 Ciclo de Atualização Recomendado

**Frequência:** A cada **fim de mês**

### Dia 5-10 do mês seguinte:
1. Você coleta os PDFs (extrato + cartões)
2. Chama o Claude: "Dados de agosto para atualizar"
3. Eu extrao os dados
4. Você confirma itens em dúvida (15-30 minutos)
5. Eu proponho mudanças (você revisa)
6. Você confirma finalmente
7. ✅ Dashboard atualizado, você baixa backup

**Total do processo:** 30-45 minutos de trabalho real

---

## 💡 Dicas para Facilitar

✅ **Organize os PDFs assim:**
```
Financeiro_Agosto_2026/
├── Extrato_Itau.pdf
├── Fatura_BlackCard.pdf
├── Holerite.pdf
└── Notas_observacoes.txt
```

✅ **Se algo tiver dúvida, anote:**
```
Transação desconhecida em 15/ago:
- PIX para +55 11 9999-9999
- Valor: R$ 300
- Pode ter sido de quem?
```

✅ **Use a mesma conversa** — não precisa criar chat novo

✅ **Se errar, é fácil corrigir** — basta re-enviar o PDF atualizado

---

## ❌ O QUE NÃO FAZER

- ❌ Não edite JSON diretamente (deixe comigo)
- ❌ Não apague transações sem confirmar
- ❌ Não misture meses diferentes num único update
- ❌ Não presuma categorias — sempre confirme

---

## 📞 Resumo em Uma Frase

**"Você envia PDFs → Eu extraio → Você confirma → Eu proponho → Você aprova → Dashboard atualiza"**

---

## 📎 Template para Próximas Sessões

Copie e cole isso quando quiser atualizar:

```
🔄 ATUALIZAÇÃO DE DADOS - DASHBOARD FINANCEIRO

Mês: _____ / 2026

Documentos anexados:
☐ Extrato bancário
☐ Fatura Black Card
☐ Fatura outros cartões
☐ Holerite (se houver mudança)
☐ Outros: _____________

Mudanças que eu SEI que houve:
- Mudança de salário? Qual valor?
- Cancelei alguma dívida?
- Novas despesas?
- Outros:

Dúvidas/Observações:
(escreva aqui tudo que não tem certeza)

Pronto para extrair dados? 👇
```

---

**Versão:** 1.0  
**Data:** 2026-08-11  
**Próxima revisão:** Após primeira atualização
