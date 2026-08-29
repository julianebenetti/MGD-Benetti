-- ============================================================
-- Seed: preços reais extraídos dos cupons fiscais da Tenda Atacado
-- (unidade Amoreiras, Campinas) — 5 compras entre 11/06 e 07/08/2026.
-- Rode DEPOIS do monitor-precos-supabase.sql, no SQL Editor do Supabase.
-- ============================================================

-- ── Novo mercado descoberto nos cupons ──
insert into monitor_mercados (nome, bairro) values
  ('Tenda Atacado', 'Amoreiras')
on conflict (nome) do nothing;

-- ── Produtos (criados se ainda não existirem) ──
insert into monitor_produtos (nome, unidade, categoria) values
  ('Bolacha Cream Cracker Adria Folhada 3x170g', 'pacote', 'Mercearia'),
  ('Banana da Terra', 'kg', 'Hortifruti'),
  ('Banana Prata', 'kg', 'Hortifruti'),
  ('Salsicha Hot Dog Sadia', 'pacote', 'Frios/Congelados'),
  ('Batata Palito Congelada Uai 2kg', 'pacote', 'Congelados'),
  ('Chocolate Tablete Lacta Diamante Negro 80g', 'un', 'Doces'),
  ('Chocolate Tablete Neugebauer Amendoim 80g', 'un', 'Doces'),
  ('Queijo Mussarela Apolo', 'kg', 'Frios'),
  ('Suco Life Laranja 1,5L', 'un', 'Bebidas'),
  ('Maionese Hellmann''s 800g', 'un', 'Mercearia'),
  ('Bacon Tablete Seara Gourmet', 'kg', 'Frios'),
  ('Goma de Mascar Mentos Tutti Frutti 92g', 'un', 'Doces'),
  ('Amendoim Select Japonês 1,01kg', 'pacote', 'Salgadinhos'),
  ('Batata Lavada Extra', 'kg', 'Hortifruti'),
  ('Chocolate Nestlé Surpresa 20g (display)', 'display', 'Doces'),
  ('Batata Lisa Select 500g', 'pacote', 'Salgadinhos'),
  ('Pão de Hambúrguer Select 200g', 'pacote', 'Padaria'),
  ('Macarrão Instantâneo Renata Galinha Caipira 85g', 'un', 'Mercearia'),
  ('Macarrão Instantâneo Renata Lamen Galinha 85g', 'un', 'Mercearia'),
  ('Milho de Pipoca Premium Kicaldo 400g', 'un', 'Mercearia'),
  ('Cerveja Pilsen Império 350ml', 'un', 'Bebidas'),
  ('Pão de Forma Seven Boys Tradicional 450g', 'pacote', 'Padaria'),
  ('Queijo Mussarela Litoral', 'kg', 'Frios'),
  ('Presunto Cozido Seara Fatiado', 'kg', 'Frios'),
  ('Batata Palha Kari-Kari Crocante 400g', 'un', 'Salgadinhos'),
  ('Achocolatado Nescau 620g', 'un', 'Mercearia'),
  ('Papel Higiênico Deluxe 12x1un 20m', 'pacote', 'Limpeza/Higiene'),
  ('Achocolatado 3 Corações 350g', 'un', 'Mercearia'),
  ('Achocolatado Toddy 370g', 'un', 'Mercearia'),
  ('Bebida de Soja Mupy Maçã 200ml', 'un', 'Bebidas'),
  ('Bebida de Soja Mupy Morango 200ml', 'un', 'Bebidas'),
  ('Refresco em Pó Tang Limão 18g', 'un', 'Bebidas'),
  ('Refresco em Pó Tang Morango 18g', 'un', 'Bebidas'),
  ('Refresco em Pó Tang Laranja Mamão 18g', 'un', 'Bebidas'),
  ('Refresco em Pó Tang Laranja Docinha 18g', 'un', 'Bebidas'),
  ('Refresco em Pó Tang Abacaxi 18g', 'un', 'Bebidas'),
  ('Sabão em Pó Ypê Primavera 800g', 'pacote', 'Limpeza/Higiene'),
  ('Ovos Extra Brancos 20un', 'bandeja', 'Hortifruti'),
  ('Batata Palha Select 400g', 'pacote', 'Salgadinhos'),
  ('Detergente Líquido Ypê Clear 500ml', 'un', 'Limpeza/Higiene')
on conflict (nome) do nothing;

-- ── Preços (produto, preço, data, observação) — mercado = Tenda Atacado ──
insert into monitor_precos (produto_id, mercado_id, preco, data, observacao)
select p.id, m.id, v.preco, v.data::date, v.obs
from (values
  -- Cupom 07/08/2026 (Nº 37720)
  ('Bolacha Cream Cracker Adria Folhada 3x170g', 10.05, '2026-08-07', null),
  ('Banana da Terra',                             12.50, '2026-08-07', 'R$/kg'),
  ('Banana Prata',                                  9.99, '2026-08-07', 'R$/kg'),
  ('Salsicha Hot Dog Sadia',                       34.47, '2026-08-07', null),
  ('Batata Palito Congelada Uai 2kg',              20.90, '2026-08-07', null),
  ('Chocolate Tablete Lacta Diamante Negro 80g',    7.39, '2026-08-07', null),
  ('Chocolate Tablete Neugebauer Amendoim 80g',     4.79, '2026-08-07', null),
  ('Queijo Mussarela Apolo',                       47.90, '2026-08-07', 'R$/kg'),
  ('Suco Life Laranja 1,5L',                       14.50, '2026-08-07', null),
  ('Maionese Hellmann''s 800g',                    20.90, '2026-08-07', null),
  ('Bacon Tablete Seara Gourmet',                  46.90, '2026-08-07', 'R$/kg'),
  ('Goma de Mascar Mentos Tutti Frutti 92g',       19.90, '2026-08-07', null),
  ('Amendoim Select Japonês 1,01kg',               18.90, '2026-08-07', null),
  ('Batata Lavada Extra',                           6.59, '2026-08-07', 'R$/kg'),
  ('Chocolate Nestlé Surpresa 20g (display)',      69.30, '2026-08-07', null),
  ('Batata Lisa Select 500g',                      21.50, '2026-08-07', null),
  ('Pão de Hambúrguer Select 200g',                 5.00, '2026-08-07', null),

  -- Cupom 31/07/2026 (Nº 63928)
  ('Macarrão Instantâneo Renata Galinha Caipira 85g', 1.59, '2026-07-31', null),
  ('Macarrão Instantâneo Renata Lamen Galinha 85g',   1.59, '2026-07-31', null),
  ('Milho de Pipoca Premium Kicaldo 400g',            3.29, '2026-07-31', null),

  -- Cupom 18/07/2026 (Nº 36428)
  ('Cerveja Pilsen Império 350ml',                 3.39, '2026-07-18', null),
  ('Pão de Forma Seven Boys Tradicional 450g',     5.49, '2026-07-18', null),
  ('Queijo Mussarela Litoral',                    45.90, '2026-07-18', 'R$/kg'),
  ('Presunto Cozido Seara Fatiado',                32.90, '2026-07-18', 'R$/kg'),

  -- Cupom 23/06/2026 (Nº 56700)
  ('Batata Palha Kari-Kari Crocante 400g',        11.90, '2026-06-23', null),
  ('Achocolatado Nescau 620g',                    18.50, '2026-06-23', null),
  ('Papel Higiênico Deluxe 12x1un 20m',           12.50, '2026-06-23', null),
  ('Macarrão Instantâneo Renata Galinha Caipira 85g', 1.69, '2026-06-23', null),
  ('Achocolatado 3 Corações 350g',                 7.49, '2026-06-23', null),
  ('Achocolatado Toddy 370g',                      9.05, '2026-06-23', null),
  ('Bebida de Soja Mupy Maçã 200ml',               2.49, '2026-06-23', null),
  ('Bebida de Soja Mupy Morango 200ml',            2.49, '2026-06-23', null),
  ('Macarrão Instantâneo Renata Lamen Galinha 85g',1.59, '2026-06-23', null),
  ('Refresco em Pó Tang Limão 18g',                 0.95, '2026-06-23', null),
  ('Refresco em Pó Tang Morango 18g',               0.95, '2026-06-23', null),
  ('Refresco em Pó Tang Laranja Mamão 18g',         0.95, '2026-06-23', null),
  ('Refresco em Pó Tang Laranja Docinha 18g',       0.95, '2026-06-23', null),
  ('Refresco em Pó Tang Abacaxi 18g',               0.95, '2026-06-23', null),

  -- Cupom 11/06/2026 (Nº 31359)
  ('Sabão em Pó Ypê Primavera 800g',                7.99, '2026-06-11', null),
  ('Ovos Extra Brancos 20un',                      12.90, '2026-06-11', null),
  ('Batata Palha Select 400g',                     14.30, '2026-06-11', null),
  ('Detergente Líquido Ypê Clear 500ml',            2.49, '2026-06-11', null),
  ('Detergente Líquido Ypê Clear 500ml',            2.49, '2026-06-11', null),
  ('Detergente Líquido Ypê Clear 500ml',            2.19, '2026-06-11', 'último item com desconto')
) as v(produto_nome, preco, data, obs)
join monitor_produtos p on p.nome = v.produto_nome
join monitor_mercados m on m.nome = 'Tenda Atacado';
