#!/usr/bin/env node

const fs = require('fs');

const xmlPath = '/root/.claude/uploads/f8d9727c-f942-53d5-9960-05b92cd886e1/096b2d5e-categories.xml';
const content = fs.readFileSync(xmlPath, 'utf-8');

const categories = [];

// Split by <category> tags
const categoryMatches = content.split('<category>').slice(1);

categoryMatches.forEach((categoryBlock, idx) => {
  const endIndex = categoryBlock.indexOf('</category>');
  if (endIndex === -1) return;

  const catContent = categoryBlock.substring(0, endIndex);

  // Extract fields with regex
  const getId = () => {
    const match = catContent.match(/<id[^>]*>(\d+)<\/id>/);
    return match ? match[1] : null;
  };

  const getName = () => {
    const match = catContent.match(/<name>([^<]+)<\/name>/);
    return match ? match[1] : null;
  };

  const getFullName = () => {
    const match = catContent.match(/<full-name>([^<]+)<\/full-name>/);
    return match ? match[1] : null;
  };

  const getParentId = () => {
    const match = catContent.match(/<parent-id[^>]*>(\d+)<\/parent-id>/);
    return match ? match[1] : null;
  };

  const getCost = () => {
    const match = catContent.match(/<cost[^>]*>([^<]+)<\/cost>/);
    return match ? match[1] === 'true' : false;
  };

  const getRevenue = () => {
    const match = catContent.match(/<revenue[^>]*>([^<]+)<\/revenue>/);
    return match ? match[1] === 'true' : false;
  };

  const getUseCount = () => {
    const match = catContent.match(/<use-count[^>]*>(\d+)<\/use-count>/);
    return match ? parseInt(match[1]) : 0;
  };

  const getCreatedAt = () => {
    const match = catContent.match(/<created-at[^>]*>([^<]+)<\/created-at>/);
    return match ? match[1] : null;
  };

  const id = getId();
  const name = getName();

  if (id && name) {
    categories.push({
      id,
      name,
      fullName: getFullName(),
      isCost: getCost(),
      isRevenue: getRevenue(),
      parentId: getParentId(),
      useCount: getUseCount(),
      createdAt: getCreatedAt(),
    });
  }
});

console.log(`✅ Parsed ${categories.length} categories`);

// Save as JSON
const output = {
  categories,
  exportedAt: new Date().toISOString(),
};

fs.writeFileSync(
  '/home/user/MGD-Benetti/categories-parsed.json',
  JSON.stringify(output, null, 2)
);

console.log('💾 Saved to categories-parsed.json');

// Generate SQL for insertion
let sql = `CREATE TABLE IF NOT EXISTS categories (
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
  const escapedFullName = cat.fullName ? cat.fullName.replace(/'/g, "''") : '';
  const parentId = cat.parentId || 'NULL';
  sql += `INSERT INTO categories VALUES ('${cat.id}', '${escapedName}', '${escapedFullName}', ${cat.isCost}, ${cat.isRevenue}, ${parentId}, ${cat.useCount}, '${cat.createdAt}');\n`;
});

fs.writeFileSync('/home/user/MGD-Benetti/categories-insert.sql', sql);
console.log('📄 SQL saved to categories-insert.sql');
