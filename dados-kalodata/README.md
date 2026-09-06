# Exports do Kalodata

Largue aqui o CSV (ou XLSX) exportado do Kalodata e faça commit. O GitHub Actions
importa sozinho pro Supabase e a página `espiao-tiktok-moda.html` passa a mostrar
os números.

## Como exportar

1. No Kalodata, filtre **moda feminina** e o período de **7 dias**.
2. Exporte a tela de **Lojas** e a tela de **Produtos** (dois arquivos separados).
3. Jogue os dois arquivos nesta pasta e faça commit.

Não precisa renomear. O script descobre sozinho se o arquivo é de loja ou de produto
pelas colunas, e aceita cabeçalho em português ou em inglês.

## Rodar na mão

```bash
export SUPABASE_KEY="a chave do projeto"
python tiktok-sync.py                          # importa tudo desta pasta
python tiktok-sync.py arquivo.csv --dry-run    # só mostra o mapeamento, não grava
python tiktok-sync.py arquivo.csv --periodo 30d --data 2026-09-06
```

O `--dry-run` imprime qual coluna do arquivo virou qual campo do banco, e lista as
colunas que ele não reconheceu. Se aparecer coluna importante em "não mapeadas",
é só acrescentar o rótulo em `ALIASES_LOJA` ou `ALIASES_PRODUTO`, no topo do
`tiktok-sync.py`.

## Sobre os números

O Kalodata **estima** GMV e unidades a partir de sinais públicos do TikTok. Não é
dado oficial da plataforma. Serve pra comparar loja com loja e ver tendência, não
pra tratar como faturamento auditado.
