"""Testes rapidos: python3 testes.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import automacao_android as android
import capa
import identidade
import legenda
import roteiro

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


# ── legenda sem link, versao do Shopee Video ─────────────────────
sem_link = legenda.montar({"nome": "Vestido Longo Feminino", "preco": "49,90"},
                          "https://s.shopee.com.br/AbC", com_link=False)
if "http" in sem_link["texto"]:
    print("❌ a legenda do Shopee Video veio com link colado")
    falhas += 1
elif sem_link["conferencia"]:
    print(f"❌ legenda sem link repetiu {sem_link['conferencia']}")
    falhas += 1
else:
    print("✅ legenda do Shopee Video sem link e sem repeticao")

# ── roteiro ──────────────────────────────────────────────────────
guia = roteiro.montar({
    "produto": {"nome": "Vestido Longo Feminino Frete Gratis", "loja": "Loja X"},
    "video": {"saida": "/tmp/video.mp4"},
    "capa": {"arquivo": "capa.jpg"},
    "link_original": "https://shopee.com.br/x-i.1.2",
})
no_app = [p for p in guia["passos"] if p["etapa"] == roteiro.APP]
preparo = [p for p in guia["passos"] if p["etapa"] == roteiro.PREPARO]
if len(no_app) == 16 and len(preparo) == 4:
    print(f"✅ roteiro com {len(preparo)} itens prontos e {len(no_app)} passos no app")
else:
    print(f"❌ roteiro saiu com {len(preparo)} prontos e {len(no_app)} no app")
    falhas += 1

if "gratis" in guia["termo_busca"].lower():
    print("❌ termo de busca manteve palavra de ruido")
    falhas += 1
else:
    print(f'✅ termo de busca do produto: "{guia["termo_busca"]}"')

for esperado in ("Adicionar Produto", "Favoritar", "Feito", "Postar"):
    if not any(esperado.lower() in p["titulo"].lower() for p in no_app):
        print(f"❌ roteiro sem o passo {esperado}")
        falhas += 1

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


# ── automacao do app ─────────────────────────────────────────────
TELA_EDITOR = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node class="android.widget.TextView" text="Adicionar legenda"
        resource-id="com.shopee.br:id/caption_edit" bounds="[40,300][1040,420]"/>
  <node class="android.widget.EditText" text=""
        resource-id="com.shopee.br:id/content_edit" bounds="[40,300][1040,420]"/>
  <node class="android.widget.Button" text="Adicionar Produto" clickable="true"
        bounds="[40,900][1040,1010]"/>
  <node class="android.widget.Button" text="Concluído" clickable="true"
        bounds="[700,1800][1040,1900]"/>
</hierarchy>"""

tela = android.Tela(TELA_EDITOR)
mapa = android.carregar_mapa()

alvo = tela.achar(mapa["adicionar_produto"]["texto"])
if alvo and alvo.centro == (540, 955):
    print(f"✅ achou o botao Adicionar Produto em {alvo.centro}")
else:
    print(f"❌ nao localizou o Adicionar Produto: {alvo}")
    falhas += 1

# o mapa tem "Concluido" sem acento e a tela mostra "Concluído"
if tela.achar(mapa["feito"]["texto"]):
    print("✅ acento nao atrapalha a busca do botao Feito")
else:
    print("❌ a busca falhou por causa do acento")
    falhas += 1

# o campo de legenda tem que ser o EditText, nao o rotulo
campo = tela.achar(mapa["legenda"]["texto"], mapa["legenda"]["id"], editavel=True)
if campo and campo.editavel:
    print("✅ pegou o campo de digitar, nao o rotulo")
else:
    print(f"❌ pegou o elemento errado para a legenda: {campo}")
    falhas += 1

GALERIA = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node class="android.widget.TextView" text="Galeria" bounds="[0,0][300,100]"/>
  <node class="android.widget.ImageView" clickable="true" bounds="[20,400][360,740]"/>
  <node class="android.widget.ImageView" clickable="true" bounds="[380,400][720,740]"/>
  <node class="android.widget.ImageView" clickable="true" bounds="[20,760][360,1100]"/>
</hierarchy>"""
primeiro = android.primeiro_da_galeria(android.Tela(GALERIA))
if primeiro and primeiro.caixa == [20, 400, 360, 740]:
    print("✅ escolhe a primeira miniatura da galeria, que e o video mais novo")
else:
    print(f"❌ escolheu a miniatura errada: {primeiro}")
    falhas += 1

if android.sem_acento("Concluído") == "concluido":
    print("✅ normalizacao de acento")
else:
    print("❌ normalizacao de acento")
    falhas += 1

print(f"\n{'tudo certo' if not falhas else str(falhas) + ' falha(s)'}")
sys.exit(1 if falhas else 0)
