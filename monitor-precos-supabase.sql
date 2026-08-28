-- ============================================================
-- Monitor de Preços — Supermercados de Campinas
-- Rode este script inteiro no SQL Editor do Supabase
-- (mesmo projeto usado pelo Garimpo de Produtos — tabelas isoladas
-- com prefixo monitor_, não interferem em nada que já existe).
-- ============================================================

create table if not exists monitor_mercados (
  id serial primary key,
  nome text not null unique,
  bairro text,
  ativo boolean not null default true,
  criado_em timestamptz not null default now()
);

create table if not exists monitor_produtos (
  id serial primary key,
  nome text not null unique,
  unidade text not null default 'un', -- un, kg, L, pacote, dz...
  categoria text,
  criado_em timestamptz not null default now()
);

create table if not exists monitor_precos (
  id serial primary key,
  produto_id integer not null references monitor_produtos(id) on delete cascade,
  mercado_id integer not null references monitor_mercados(id) on delete cascade,
  preco numeric(10,2) not null,
  data date not null default current_date,
  observacao text,
  criado_em timestamptz not null default now()
);

create index if not exists idx_monitor_precos_produto on monitor_precos(produto_id);
create index if not exists idx_monitor_precos_mercado on monitor_precos(mercado_id);
create index if not exists idx_monitor_precos_data on monitor_precos(data);

-- ── RLS: aberto para a chave anon (mesmo padrão já usado no Garimpo) ──
alter table monitor_mercados enable row level security;
alter table monitor_produtos enable row level security;
alter table monitor_precos enable row level security;

drop policy if exists "anon full access" on monitor_mercados;
create policy "anon full access" on monitor_mercados for all using (true) with check (true);

drop policy if exists "anon full access" on monitor_produtos;
create policy "anon full access" on monitor_produtos for all using (true) with check (true);

drop policy if exists "anon full access" on monitor_precos;
create policy "anon full access" on monitor_precos for all using (true) with check (true);

-- ── Seed: mercados que você indicou perto do CEP 13036-135 (Parque Itália) ──
insert into monitor_mercados (nome, bairro) values
  ('Savegnago', null),
  ('Extra', null),
  ('Assaí', null),
  ('Atacadão', null),
  ('Paulistão', null)
on conflict (nome) do nothing;
