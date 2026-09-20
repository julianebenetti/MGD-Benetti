"""Testes rapidos: python3 testes.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capa
import identidade
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


# ── capa e identidade ────────────────────────────────────────────
from PIL import Image  # noqa: E402

ident = identidade.carregar()
pasta = tempfile.mkdtemp()
quadro = os.path.join(pasta, "quadro.png")
Image.linear_gradient("L").convert("RGB").resize((1280, 720)).save(quadro)

produto = {"nome": "Vestido Longo Feminino Fluido Frete Gratis Kit",
           "preco": "59,90", "nota": 4.8}

if legenda.normalizar("Gratis") not in capa.titulo_curto(produto["nome"]).lower():
    print("✅ titulo da capa sem as palavras de ruido")
else:
    print("❌ titulo da capa manteve palavra de ruido")
    falhas += 1

for modelo in ("faixa", "minimo", "cartao"):
    conf = identidade.carregar()
    conf["capa"]["modelo"] = modelo
    destino = os.path.join(pasta, f"capa_{modelo}.jpg")
    capa.montar_capa(quadro, destino, produto, conf)
    with Image.open(destino) as arte:
        if arte.size == (1080, 1920):
            print(f"✅ capa {modelo} em 1080x1920")
        else:
            print(f"❌ capa {modelo} saiu {arte.size}")
            falhas += 1

# produto sem preco e sem nota (API fora do ar) nao pode quebrar a capa
capa.montar_capa(quadro, os.path.join(pasta, "capa_seca.jpg"),
                 {"nome": "Produto Sem Dados"}, ident)
print("✅ capa sem preco e sem nota")

marca = capa.marca_dagua(ident, os.path.join(pasta, "marca.png"))
with Image.open(marca) as arte:
    if arte.mode == "RGBA" and arte.width > 100:
        print("✅ marca d'agua gerada da identidade")
    else:
        print(f"❌ marca d'agua saiu {arte.mode} {arte.size}")
        falhas += 1

print(f"\n{'tudo certo' if not falhas else str(falhas) + ' falha(s)'}")
sys.exit(1 if falhas else 0)
