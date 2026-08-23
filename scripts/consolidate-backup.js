#!/usr/bin/env node

const fs = require('fs');

// Read categories
let categories = [];
try {
  const categoriesJson = JSON.parse(
    fs.readFileSync('/home/user/MGD-Benetti/categories-parsed.json', 'utf-8')
  );
  categories = categoriesJson.categories || [];
} catch (e) {
  console.warn('Could not read categories');
}

// Hardcode classification centers from XML
const classificationCentersData = [
  { id: 81956, name: 'Moradia', isCostCenter: true, isRevenueCenter: true },
  { id: 81957, name: 'Aplicações', isCostCenter: true, isRevenueCenter: true },
  { id: 81958, name: 'Financeiras', isCostCenter: true, isRevenueCenter: true },
  { id: 81959, name: 'Supérfluas', isCostCenter: true, isRevenueCenter: true },
  { id: 81960, name: 'Saúde', isCostCenter: true, isRevenueCenter: true },
  { id: 81961, name: 'Educação', isCostCenter: true, isRevenueCenter: true },
  { id: 81962, name: 'Impostos', isCostCenter: true, isRevenueCenter: true },
  { id: 81963, name: 'Seguros', isCostCenter: true, isRevenueCenter: true },
  { id: 81964, name: 'Cultura e Lazer', isCostCenter: true, isRevenueCenter: true },
  { id: 81965, name: 'Pessoais', isCostCenter: true, isRevenueCenter: true },
  { id: 81966, name: 'Rendas de Trabalho', isCostCenter: true, isRevenueCenter: true },
  { id: 81968, name: 'Transferência', isCostCenter: true, isRevenueCenter: true },
  { id: 81969, name: 'Rendas de Capital', isCostCenter: true, isRevenueCenter: true },
  { id: 81970, name: 'Cartão de Crédito', isCostCenter: true, isRevenueCenter: true },
  { id: 81971, name: 'EROC - Igreja de Cristo', isCostCenter: false, isRevenueCenter: true },
  { id: 94496, name: 'Depósito / Saque', isCostCenter: true, isRevenueCenter: true },
  { id: 120677, name: 'Empréstimo', isCostCenter: true, isRevenueCenter: true },
  { id: 160715, name: 'Rendas de Vendas', isCostCenter: true, isRevenueCenter: true },
  { id: 185046, name: 'Despesas de Trabalho', isCostCenter: true, isRevenueCenter: true },
  { id: 282283, name: 'CashBack', isCostCenter: true, isRevenueCenter: true },
];

// Consolidate
const backup = {
  version: '1.0',
  exportedAt: new Date().toISOString(),
  user: {
    name: 'Juliane Benetti',
    email: 'julianebenetti@gmail.com',
  },
  classificationCenters: classificationCentersData,
  categories: categories,
  stats: {
    totalClassificationCenters: classificationCentersData.length,
    totalCategories: categories.length,
    mainCategoriesCount: categories.filter(c => !c.parentId).length,
  },
};

// Write consolidated backup
fs.writeFileSync(
  '/home/user/MGD-Benetti/financial-backup.json',
  JSON.stringify(backup, null, 2)
);

console.log('✅ Backup consolidado com sucesso!');
console.log(`📊 Centros de Classificação: ${backup.stats.totalClassificationCenters}`);
console.log(`📂 Total de Categorias: ${backup.stats.totalCategories}`);
console.log(`📁 Categorias Principais: ${backup.stats.mainCategoriesCount}`);
console.log('📄 Arquivo: financial-backup.json');
