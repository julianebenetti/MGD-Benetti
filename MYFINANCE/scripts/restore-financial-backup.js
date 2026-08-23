#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const xml2js = require('xml2js');

// Parse XML files
async function parseXML(filePath) {
  const xmlContent = fs.readFileSync(filePath, 'utf-8');
  const parser = new xml2js.Parser();
  return await parser.parseStringPromise(xmlContent);
}

// Extract classification centers
async function extractClassificationCenters(filePath) {
  const data = await parseXML(filePath);
  return data['classification-centers']['classification-center'].map(cc => ({
    id: cc.id[0],
    name: cc.name[0],
    isCostCenter: cc['cost-center'][0] === 'true',
    isRevenueCenter: cc['revenue-center'][0] === 'true',
    useCount: parseInt(cc['use-count'][0]) || 0,
    createdAt: cc['created-at'][0],
  }));
}

// Extract categories with hierarchy
async function extractCategories(filePath) {
  const data = await parseXML(filePath);
  const categories = [];

  function processCategory(category, parentId = null) {
    const cat = {
      id: category.id[0],
      name: category.name[0],
      fullName: category['full-name'][0],
      isCost: category.cost[0] === 'true',
      isRevenue: category.revenue[0] === 'true',
      parentId: parentId,
      useCount: parseInt(category['use-count'][0]) || 0,
      createdAt: category['created-at'][0],
    };
    categories.push(cat);

    if (category.categories && category.categories[0].category) {
      category.categories[0].category.forEach(subCat => {
        processCategory(subCat, cat.id);
      });
    }
  }

  data.categories.category.forEach(cat => {
    processCategory(cat);
  });

  return categories;
}

// Extract users
async function extractUsers(filePath) {
  const data = await parseXML(filePath);
  return data.users.user.map(u => ({
    firstName: u['first-name'][0],
    lastName: u['last-name'][0],
    email: u.email[0],
  }));
}

// Extract entities
async function extractEntities(filePath) {
  const data = await parseXML(filePath);
  return data.entities.entity.map(e => ({
    id: e.id[0],
    name: e.name[0],
    accountId: e['account-id'][0],
    cpf: e['federation-subscription-number'] ? e['federation-subscription-number'][0] : null,
    createdAt: e['created-at'][0],
  }));
}

// Generate SQL for Supabase
function generateSQL(classificationCenters, categories, users, entities) {
  let sql = '';

  // Classification Centers table
  sql += `CREATE TABLE IF NOT EXISTS classification_centers (
  id BIGINT PRIMARY KEY,
  name VARCHAR NOT NULL,
  is_cost_center BOOLEAN,
  is_revenue_center BOOLEAN,
  use_count INTEGER DEFAULT 0,
  created_at TIMESTAMP
);\n\n`;

  classificationCenters.forEach(cc => {
    const escapedName = cc.name.replace(/'/g, "''");
    sql += `INSERT INTO classification_centers VALUES (${cc.id}, '${escapedName}', ${cc.isCostCenter}, ${cc.isRevenueCenter}, ${cc.useCount}, '${cc.createdAt}');\n`;
  });

  // Categories table
  sql += `\n\nCREATE TABLE IF NOT EXISTS categories (
  id BIGINT PRIMARY KEY,
  name VARCHAR NOT NULL,
  full_name VARCHAR,
  is_cost BOOLEAN,
  is_revenue BOOLEAN,
  parent_id BIGINT,
  use_count INTEGER DEFAULT 0,
  created_at TIMESTAMP
);\n\n`;

  categories.forEach(cat => {
    const escapedName = cat.name.replace(/'/g, "''");
    const escapedFullName = cat.fullName.replace(/'/g, "''");
    const parentId = cat.parentId ? cat.parentId : 'NULL';
    sql += `INSERT INTO categories VALUES (${cat.id}, '${escapedName}', '${escapedFullName}', ${cat.isCost}, ${cat.isRevenue}, ${parentId}, ${cat.useCount}, '${cat.createdAt}');\n`;
  });

  // Users table
  sql += `\n\nCREATE TABLE IF NOT EXISTS users_data (
  email VARCHAR PRIMARY KEY,
  first_name VARCHAR,
  last_name VARCHAR
);\n\n`;

  users.forEach(u => {
    sql += `INSERT INTO users_data VALUES ('${u.email}', '${u.firstName}', '${u.lastName}');\n`;
  });

  // Entities table
  sql += `\n\nCREATE TABLE IF NOT EXISTS entities (
  id BIGINT PRIMARY KEY,
  name VARCHAR NOT NULL,
  account_id BIGINT,
  cpf VARCHAR,
  created_at TIMESTAMP
);\n\n`;

  entities.forEach(e => {
    const escapedName = e.name.replace(/'/g, "''");
    const cpf = e.cpf ? `'${e.cpf}'` : 'NULL';
    sql += `INSERT INTO entities VALUES (${e.id}, '${escapedName}', ${e.accountId}, ${cpf}, '${e.createdAt}');\n`;
  });

  return sql;
}

// Main
async function main() {
  try {
    const uploadsDir = '/root/.claude/uploads/f8d9727c-f942-53d5-9960-05b92cd886e1';

    console.log('📦 Extracting backup data...');

    let classificationCenters = [];
    try {
      classificationCenters = await extractClassificationCenters(
        path.join(uploadsDir, 'e700ff13-classification_centers.xml')
      );
    } catch (e) {
      console.warn('⚠️  Could not parse classification centers:', e.message);
    }

    let categories = [];
    try {
      categories = await extractCategories(
        path.join(uploadsDir, '096b2d5e-categories.xml')
      );
    } catch (e) {
      console.warn('⚠️  Could not parse categories:', e.message);
    }

    let users = [];
    try {
      users = await extractUsers(
        path.join(uploadsDir, 'de58060f-users.xml')
      );
    } catch (e) {
      console.warn('⚠️  Could not parse users:', e.message);
    }

    let entities = [];
    try {
      entities = await extractEntities(
        path.join(uploadsDir, '756a0bfd-entities.xml')
      );
    } catch (e) {
      console.warn('⚠️  Could not parse entities:', e.message);
    }

    console.log(`✅ Found ${classificationCenters.length} classification centers`);
    console.log(`✅ Found ${categories.length} categories`);
    console.log(`✅ Found ${users.length} users`);
    console.log(`✅ Found ${entities.length} entities`);

    // Generate SQL
    const sql = generateSQL(classificationCenters, categories, users, entities);
    const outputPath = '/home/user/MGD-Benetti/backup-restore.sql';
    fs.writeFileSync(outputPath, sql);

    console.log(`\n💾 SQL backup saved to: ${outputPath}`);

    // Save JSON for dashboard
    const jsonData = {
      classificationCenters,
      categories,
      users,
      entities,
      exportedAt: new Date().toISOString(),
    };

    const jsonPath = '/home/user/MGD-Benetti/financial-backup.json';
    fs.writeFileSync(jsonPath, JSON.stringify(jsonData, null, 2));
    console.log(`📄 JSON backup saved to: ${jsonPath}`);

  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

main();
