CREATE TABLE IF NOT EXISTS classification_centers (
  id BIGINT PRIMARY KEY,
  name VARCHAR NOT NULL,
  is_cost_center BOOLEAN,
  is_revenue_center BOOLEAN,
  use_count INTEGER DEFAULT 0,
  created_at TIMESTAMP
);

INSERT INTO classification_centers VALUES ([object Object], 'Moradia', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Aplicações', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Financeiras', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Supérfluas', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Saúde', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Educação', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Impostos', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Seguros', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Cultura e Lazer', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Pessoais', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Rendas de Trabalho', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Transferência', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Rendas de Capital', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Cartão de Crédito', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'EROC - Igreja de Cristo', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Depósito / Saque', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Empréstimo', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Rendas de Vendas', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'Despesas de Trabalho', false, false, 0, '[object Object]');
INSERT INTO classification_centers VALUES ([object Object], 'CashBack', false, false, 0, '[object Object]');


CREATE TABLE IF NOT EXISTS categories (
  id BIGINT PRIMARY KEY,
  name VARCHAR NOT NULL,
  full_name VARCHAR,
  is_cost BOOLEAN,
  is_revenue BOOLEAN,
  parent_id BIGINT,
  use_count INTEGER DEFAULT 0,
  created_at TIMESTAMP
);



CREATE TABLE IF NOT EXISTS users_data (
  email VARCHAR PRIMARY KEY,
  first_name VARCHAR,
  last_name VARCHAR
);

INSERT INTO users_data VALUES ('julianebenetti@yahoo.com.br', 'Juliane', 'Benetti');


CREATE TABLE IF NOT EXISTS entities (
  id BIGINT PRIMARY KEY,
  name VARCHAR NOT NULL,
  account_id BIGINT,
  cpf VARCHAR,
  created_at TIMESTAMP
);

INSERT INTO entities VALUES ([object Object], 'Juliane Benetti', [object Object], '26124131897', '[object Object]');
