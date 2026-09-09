"""Testes rapidos: python3 testes.py"""
import sys

sys.path.insert(0, ".")
import legenda

NOMES = [
    "Vestido Longo Feminino Fluido Frete Gratis Promocao",
    "Fone de Ouvido Bluetooth Sem Fio TWS Original",
    "Organizador de Gaveta Dobravel Kit 4 Un",
    "Coleira Ajustavel para Cachorro Porte Medio",
    "Batom Matte Longa Duracao Vermelho",
    "Panela Antiaderente Frigideira 24cm",
    "Body Bebe Menina Algodao Manga Curta",
    "Produto Aleatorio Sem Categoria Definida",
    "Tenis Feminino Casual Leve Confortavel",
    "Caixa de Som Bluetooth Portatil a Prova d'Agua",
]

falhas = 0
for nome in NOMES:
    resultado = legenda.montar(
        {"nome": nome, "preco": "49,90", "nota": 4.7, "vendas": 900},
        "https://s.shopee.com.br/AbC123",
    )
    problemas = []
    if resultado["conferencia"]:
        problemas.append(f"palavras repetidas: {resultado['conferencia']}")
    if len(resultado["hashtags"]) != 5:
        problemas.append(f"{len(resultado['hashtags'])} hashtags (esperado 5)")
    if len(resultado["seo"]) != 10:
        problemas.append(f"{len(resultado['seo'])} palavras de SEO (esperado 10)")
    if problemas:
        falhas += 1
        print(f"❌ {nome}\n   " + "\n   ".join(problemas))
    else:
        print(f"✅ {nome} [{resultado['categoria']}]")

try:
    legenda.montar({"nome": "Whey Protein Isolado 900g"}, "x")
    print("❌ suplemento passou pelo bloqueio")
    falhas += 1
except ValueError:
    print("✅ suplemento bloqueado")

print(f"\n{'tudo certo' if not falhas else str(falhas) + ' falha(s)'}")
sys.exit(1 if falhas else 0)
